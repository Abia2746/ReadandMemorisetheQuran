"""Al-Mu'allim Prayer Room economy: server-authoritative rewards and inventory.

XP is permanent study progress; coins are spendable. Progress is stored in
SQLite alongside the existing users table and is transactional/idempotent.

Note: Streamlit Community Cloud's local SQLite is ephemeral across deployments.
For cross-device / permanent persistence, migrate to a managed authenticated DB.
"""
import datetime as dt
import json
import pathlib
import sqlite3
from contextlib import closing

_DB = pathlib.Path(__file__).resolve().with_name("muallim.db")

# Prices in spendable *coins*, not lifetime XP.
ITEMS = [
    {"id":"wallpaper_sage","name":"Sage Silk Wallpaper","category":"wallpaper","price":180,"unlock_xp":0,"description":"A muted sage botanical silk wallcovering with delicate gold stems. Replaces the room's limewash walls."},
    {"id":"wallpaper_almond","name":"Almond Arabesque Wallpaper","category":"wallpaper","price":420,"unlock_xp":350,"description":"Warm ivory-on-ivory arabesque motifs, fine metallic tracery and boutique-hotel elegance."},
    {"id":"wallpaper_midnight","name":"Midnight Celestial Wallpaper","category":"wallpaper","price":780,"unlock_xp":950,"description":"Deep midnight blue with understated gold eight-point stars for a tranquil evening sanctuary."},
    {"id":"rug_rose","name":"Rose Quartz Prayer Rug","category":"rug","price":310,"unlock_xp":180,"description":"Dusty rose velvet, champagne-gold borders and an ornate woven arch. Changes the 3D rug."},
    {"id":"rug_ivory","name":"Pearl Ivory Prayer Rug","category":"rug","price":580,"unlock_xp":600,"description":"Cream wool with luminous pearl details and a finely woven gold mihrab motif."},
    {"id":"floor_marble","name":"Pearl Marble Flooring","category":"floor","price":680,"unlock_xp":650,"description":"Polished pale marble tiles with subtle warm-grey veining throughout the 3D room."},
    {"id":"floor_onyx","name":"Midnight Onyx Flooring","category":"floor","price":1250,"unlock_xp":1600,"description":"Deep charcoal stone tiles with refined bronze veins for a dramatic sanctuary."},
    {"id":"plant_olive","name":"Olive Tree","category":"plant","price":110,"unlock_xp":0,"description":"Sculptural greenery in a hand-thrown planter"},
    {"id":"lantern_brass","name":"Brass Floor Lantern","category":"lamp","price":160,"unlock_xp":0,"description":"Warm amber light and filigree"},
    {"id":"rug_emerald","name":"Emerald Prayer Rug","category":"rug","price":200,"unlock_xp":100,"description":"An intricate jade-and-gold woven prayer rug"},
    {"id":"stand_walnut","name":"Walnut Rehal","category":"rehal","price":240,"unlock_xp":150,"description":"An open walnut Qur'an stand"},
    {"id":"art_geometry","name":"Geometric Wall Art","category":"art","price":280,"unlock_xp":200,"description":"An original eight-point Islamic star composition"},
    {"id":"shelf_walnut","name":"Walnut Library","category":"shelf","price":340,"unlock_xp":300,"description":"Curved wooden shelf with books"},
    {"id":"cushions_sage","name":"Sage Floor Cushions","category":"cushion","price":390,"unlock_xp":400,"description":"Soft linen cushions at the reading corner"},
    {"id":"curtains_linen","name":"Linen Window Drapes","category":"curtain","price":450,"unlock_xp":500,"description":"Soft ivory drapery around the arch window"},
    {"id":"pendant_moon","name":"Golden Pendant","category":"pendant","price":520,"unlock_xp":650,"description":"Suspended warm metallic lighting"},
    {"id":"window_rain","name":"Rainy Window","category":"window","price":600,"unlock_xp":800,"description":"Rain-speckled glass and blue twilight"},
    {"id":"mihrab_marble","name":"Marble Mihrab","category":"mihrab","price":760,"unlock_xp":1000,"description":"A sculpted marble prayer niche with brass edging"},
    {"id":"floor_travertine","name":"Travertine Flooring","category":"floor","price":900,"unlock_xp":1300,"description":"A calm cream stone floor"},
    {"id":"rug_midnight","name":"Midnight Prayer Rug","category":"rug","price":1050,"unlock_xp":1700,"description":"Midnight sapphire wool with subtle gilding"},
    {"id":"light_evening","name":"Candlelit Atmosphere","category":"ambience","price":1200,"unlock_xp":2000,"description":"Moody evening lighting for quiet reflection"},
]
BY_ID = {item["id"]: item for item in ITEMS}
CATEGORIES = {item["category"] for item in ITEMS}
STARTER_EQUIPPED = {
    "rug": None, "plant": None, "lamp": None, "rehal": None, "wallpaper": None,
    "art": None, "shelf": None, "cushion": None, "curtain": None,
    "pendant": None, "window": None, "mihrab": None, "floor": None, "ambience": None,
}
REWARDS = {
    "read": {"xp": 50, "coins": 25},
    "memorise": {"xp": 75, "coins": 40},
    "review": {"xp": 100, "coins": 50},
}


def _db():
    connection = sqlite3.connect(_DB, timeout=15, isolation_level=None)
    connection.execute("PRAGMA busy_timeout=15000")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""CREATE TABLE IF NOT EXISTS users (
        name TEXT PRIMARY KEY, xp INTEGER DEFAULT 0, streak INTEGER DEFAULT 0,
        last_day TEXT)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS room_wallet (
        name TEXT PRIMARY KEY, coins INTEGER NOT NULL DEFAULT 100,
        equipped_json TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY(name) REFERENCES users(name))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS room_owned (
        name TEXT NOT NULL, item_id TEXT NOT NULL,
        PRIMARY KEY(name,item_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS room_earnings (
        name TEXT NOT NULL, event_key TEXT NOT NULL, xp INTEGER NOT NULL,
        coins INTEGER NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(name,event_key))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS room_transactions (
        name TEXT NOT NULL, item_id TEXT NOT NULL, cost INTEGER NOT NULL,
        created_at TEXT NOT NULL, PRIMARY KEY(name,item_id))""")
    return connection


def _profile(con, name):
    con.execute("INSERT OR IGNORE INTO users(name) VALUES(?)", (name,))
    con.execute("INSERT OR IGNORE INTO room_wallet(name) VALUES(?)", (name,))


def get_room_state(name):
    """Public room state suitable for Streamlit component data."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("A practice profile is needed.")
    with closing(_db()) as con:
        _profile(con, name)
        xp, streak = con.execute(
            "SELECT xp,streak FROM users WHERE name=?", (name,)
        ).fetchone()
        coins, equip_json = con.execute(
            "SELECT coins,equipped_json FROM room_wallet WHERE name=?", (name,)
        ).fetchone()
        owned = [r[0] for r in con.execute(
            "SELECT item_id FROM room_owned WHERE name=?", (name,)
        ).fetchall()]
        try:
            parsed = json.loads(equip_json)
        except (TypeError, ValueError):
            parsed = {}
        equipped = {
            key: value if value in BY_ID and BY_ID[value]["category"] == key
            and value in owned else None
            for key, value in {**STARTER_EQUIPPED, **parsed}.items()
            if key in CATEGORIES
        }
        return {
            "xp": max(0,int(xp or 0)),
            "streak": int(streak or 0),
            "coins": max(0,int(coins)),
            "owned": owned,
            "equipped": equipped,
            "items": ITEMS,
            "prices": {"read": REWARDS["read"], "memorise": REWARDS["memorise"]},
        }


def earn(name, action, surah, ayah, *, today=None):
    """Award once per action/verse/day. Self-reported reading ≠ verified mastery."""
    if action not in ("read", "memorise"):
        raise ValueError("Unsupported study action.")
    if not (type(surah) is int and 1 <= surah <= 114
            and type(ayah) is int and 1 <= ayah <= 286):
        raise ValueError("Invalid verse.")
    today = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
    key = f"{action}:{surah}:{ayah}:{today}"
    reward = REWARDS[action]
    with closing(_db()) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            _profile(con, name)
            if con.execute(
                "SELECT 1 FROM room_earnings WHERE name=? AND event_key=?",
                (name, key)
            ).fetchone():
                con.execute("COMMIT")
                return {"ok": False, "message":"Already rewarded for this ayah today."}
            con.execute(
                "INSERT INTO room_earnings(name,event_key,xp,coins,created_at) VALUES(?,?,?,?,?)",
                (name,key,reward["xp"],reward["coins"],dt.datetime.now(dt.timezone.utc).isoformat())
            )
            con.execute(
                "UPDATE users SET xp=COALESCE(xp,0)+? WHERE name=?",
                (reward["xp"],name)
            )
            con.execute(
                "UPDATE room_wallet SET coins=coins+? WHERE name=?",
                (reward["coins"],name)
            )
            con.execute("COMMIT")
            return {"ok":True,"message":f"+{reward['xp']} XP and +{reward['coins']} coins for {surah}:{ayah}."}
        except BaseException:
            con.execute("ROLLBACK")
            raise


def earn_recording_review(name, surah, first, last, review_id, *, today=None):
    """Reward successful analysis once per unique completed audio review."""
    if not (type(surah) is int and 1 <= surah <= 114):
        raise ValueError("Invalid surah.")
    if not (type(first) is int and type(last) is int and 1 <= first <= last <= 286):
        raise ValueError("Invalid ayah range.")
    if not isinstance(review_id, str) or not 10 <= len(review_id) <= 128:
        raise ValueError("Invalid review id.")
    today = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
    key = f"review:{surah}:{first}-{last}:{review_id}:{today}"
    reward = REWARDS["review"]
    with closing(_db()) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            _profile(con,name)
            # Limit successful recording rewards to 3 per day to prevent
            # noisy repeat submissions from farming currency.
            day_prefix = f"review:%:{today}"
            count=con.execute(
                "SELECT COUNT(*) FROM room_earnings WHERE name=? AND event_key LIKE ?",
                (name,day_prefix)
            ).fetchone()[0]
            if count >= 3:
                con.execute("COMMIT")
                return {"ok":False,"message":"Three recording rewards claimed today."}
            if con.execute(
                "SELECT 1 FROM room_earnings WHERE name=? AND event_key=?",
                (name,key)
            ).fetchone():
                con.execute("COMMIT")
                return {"ok":False,"message":"This recording was already rewarded."}
            con.execute(
                "INSERT INTO room_earnings(name,event_key,xp,coins,created_at) VALUES(?,?,?,?,?)",
                (name,key,reward["xp"],reward["coins"],dt.datetime.now(dt.timezone.utc).isoformat())
            )
            con.execute("UPDATE users SET xp=COALESCE(xp,0)+? WHERE name=?",
                        (reward["xp"],name))
            con.execute("UPDATE room_wallet SET coins=coins+? WHERE name=?",
                        (reward["coins"],name))
            con.execute("COMMIT")
            return {"ok":True,"message":"+100 XP and +50 coins for completing a recording review."}
        except BaseException:
            con.execute("ROLLBACK")
            raise


def buy(name, item_id):
    item = BY_ID.get(item_id)
    if item is None:
        return {"ok":False,"message":"Unknown item."}
    with closing(_db()) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            _profile(con,name)
            if con.execute(
                "SELECT 1 FROM room_owned WHERE name=? AND item_id=?",
                (name,item_id)
            ).fetchone():
                con.execute("COMMIT")
                return {"ok":False,"message":"You already own this item."}
            xp = con.execute("SELECT xp FROM users WHERE name=?", (name,)).fetchone()[0] or 0
            coins = con.execute("SELECT coins FROM room_wallet WHERE name=?", (name,)).fetchone()[0]
            if int(xp) < item["unlock_xp"]:
                con.execute("COMMIT")
                return {"ok":False,"message":f"Reach {item['unlock_xp']} lifetime XP to unlock this item."}
            if int(coins) < item["price"]:
                con.execute("COMMIT")
                return {"ok":False,"message":f"You need {item['price']-coins} more coins."}
            equipped_raw=con.execute(
                "SELECT equipped_json FROM room_wallet WHERE name=?", (name,)
            ).fetchone()[0]
            try:
                equipped=json.loads(equipped_raw)
            except (ValueError, TypeError):
                equipped={}
            equipped[item["category"]]=item_id
            con.execute("UPDATE room_wallet SET coins=coins-?,equipped_json=? WHERE name=?",
                        (item["price"],json.dumps(equipped),name))
            con.execute("INSERT INTO room_owned(name,item_id) VALUES (?,?)", (name,item_id))
            con.execute(
                "INSERT INTO room_transactions(name,item_id,cost,created_at) VALUES(?,?,?,?)",
                (name,item_id,item["price"],dt.datetime.now(dt.timezone.utc).isoformat())
            )
            con.execute("COMMIT")
            return {"ok":True,"message":f"{item['name']} purchased and placed in your prayer room."}
        except BaseException:
            con.execute("ROLLBACK")
            raise


def equip(name, item_id):
    item = BY_ID.get(item_id)
    if item is None:
        return {"ok":False,"message":"Unknown item."}
    with closing(_db()) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            _profile(con,name)
            owned=con.execute(
                "SELECT 1 FROM room_owned WHERE name=? AND item_id=?",
                (name,item_id)
            ).fetchone()
            if not owned:
                con.execute("COMMIT")
                return {"ok":False,"message":"Purchase this item before placing it."}
            raw=con.execute(
                "SELECT equipped_json FROM room_wallet WHERE name=?",(name,)
            ).fetchone()[0]
            try:
                equipped=json.loads(raw)
            except (ValueError,TypeError):
                equipped={}
            equipped[item["category"]]=item_id
            con.execute("UPDATE room_wallet SET equipped_json=? WHERE name=?",
                        (json.dumps(equipped),name))
            con.execute("COMMIT")
            return {"ok":True,"message":f"{item['name']} added to your room."}
        except BaseException:
            con.execute("ROLLBACK")
            raise


def unequip(name, category):
    if category not in CATEGORIES:
        return {"ok":False,"message":"Unknown decoration slot."}
    with closing(_db()) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            _profile(con,name)
            raw=con.execute(
                "SELECT equipped_json FROM room_wallet WHERE name=?",(name,)
            ).fetchone()[0]
            try:
                equipped=json.loads(raw)
            except (ValueError,TypeError):
                equipped={}
            equipped[category]=None
            con.execute("UPDATE room_wallet SET equipped_json=? WHERE name=?",
                        (json.dumps(equipped),name))
            con.execute("COMMIT")
            return {"ok":True,"message":"Decoration removed from the room. You still own it."}
        except BaseException:
            con.execute("ROLLBACK")
            raise


def export_room_snapshot(name):
    """Read cosmetic XP, inventory and reward history for authenticated backup."""
    if not isinstance(name, str) or not name.startswith("account:"):
        raise ValueError("Only account-owned rooms may be backed up.")
    with closing(_db()) as con:
        _profile(con, name)
        user = con.execute("SELECT xp,streak,last_day FROM users WHERE name=?", (name,)).fetchone()
        wallet = con.execute("SELECT coins,equipped_json FROM room_wallet WHERE name=?", (name,)).fetchone()
        owned = [row[0] for row in con.execute(
            "SELECT item_id FROM room_owned WHERE name=? ORDER BY item_id", (name,)
        )]
        earnings = con.execute(
            "SELECT event_key,xp,coins,created_at FROM room_earnings WHERE name=? ORDER BY created_at LIMIT 5000",
            (name,)
        ).fetchall()
        transactions = con.execute(
            "SELECT item_id,cost,created_at FROM room_transactions WHERE name=? ORDER BY created_at LIMIT 300",
            (name,)
        ).fetchall()
    return {
        "version": 1, "xp": max(0,int(user[0] or 0)),
        "streak": max(0,int(user[1] or 0)),
        "last_day": user[2],
        "coins": max(0,int(wallet[0] or 0)),
        "equipped": json.loads(wallet[1] or "{}"),
        "owned": owned,
        "earnings": [
            {"key": key, "xp": xp, "coins": coins, "at": timestamp}
            for key,xp,coins,timestamp in earnings
        ],
        "transactions": [
            {"item": item, "cost": cost, "at": stamp}
            for item,cost,stamp in transactions
        ],
    }


def import_room_snapshot(name, snapshot):
    """Restore an account's cosmetic state atomically, validating inventory.

    This is a convenience backup, NOT authoritative billing or financial value.
    """
    if not isinstance(name,str) or not name.startswith("account:"):
        raise ValueError("Invalid account-owned room.")
    if not isinstance(snapshot,dict) or snapshot.get("version") != 1:
        raise ValueError("Unsupported room backup")
    owned = snapshot.get("owned")
    equipped = snapshot.get("equipped")
    earnings = snapshot.get("earnings")
    transactions = snapshot.get("transactions")
    if (not isinstance(owned,list) or len(owned)>len(ITEMS)
        or not isinstance(equipped,dict) or len(equipped)>len(CATEGORIES)
        or not isinstance(earnings,list) or len(earnings)>5000
        or not isinstance(transactions,list) or len(transactions)>300):
        raise ValueError("Invalid room backup collections")
    if any(not isinstance(item,str) or item not in BY_ID for item in owned):
        raise ValueError("Unknown room item")
    if len(set(owned)) != len(owned):
        raise ValueError("Duplicate owned room item")
    for category,item in equipped.items():
        if category not in CATEGORIES or (item is not None and (
            item not in owned or BY_ID[item]["category"] != category)):
            raise ValueError("Invalid room decoration")
    xp, coins, streak = snapshot.get("xp"), snapshot.get("coins"), snapshot.get("streak")
    if any(type(x) is not int or x < 0 or x > 10000000 for x in (xp,coins,streak)):
        raise ValueError("Invalid room score")
    day = snapshot.get("last_day")
    if day is not None:
        if not isinstance(day,str):
            raise ValueError("Invalid streak date")
        try:
            dt.date.fromisoformat(day)
        except ValueError:
            raise ValueError("Invalid streak date")
    clean_earnings=[]
    for r in earnings:
        if not isinstance(r,dict):
            raise ValueError("Invalid earning")
        key,rx,rc,stamp=r.get("key"),r.get("xp"),r.get("coins"),r.get("at")
        if (not isinstance(key,str) or not 1<=len(key)<=180
           or type(rx) is not int or not 0<=rx<=500
           or type(rc) is not int or not 0<=rc<=500
           or not isinstance(stamp,str) or len(stamp)>70):
            raise ValueError("Invalid earning details")
        clean_earnings.append((name,key,rx,rc,stamp))
    if len({r[1] for r in clean_earnings}) != len(clean_earnings):
        raise ValueError("Duplicate earnings")
    clean_transactions=[]
    for r in transactions:
        item,cost,stamp=r.get("item"),r.get("cost"),r.get("at")
        if (not isinstance(item,str) or item not in owned
            or type(cost) is not int or cost != BY_ID[item]["price"]
            or not isinstance(stamp,str) or len(stamp)>70):
            raise ValueError("Invalid room purchase")
        clean_transactions.append((name,item,cost,stamp))
    if len({r[1] for r in clean_transactions}) != len(clean_transactions):
        raise ValueError("Duplicate purchases")
    with closing(_db()) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            _profile(con,name)
            for table in ("room_owned","room_earnings","room_transactions"):
                con.execute(f"DELETE FROM {table} WHERE name=?", (name,))
            con.execute(
                "UPDATE users SET xp=?,streak=?,last_day=? WHERE name=?",
                (xp,streak,day,name))
            con.execute(
                "UPDATE room_wallet SET coins=?,equipped_json=? WHERE name=?",
                (coins,json.dumps(equipped),name))
            con.executemany("INSERT INTO room_owned(name,item_id) VALUES (?,?)",
                            [(name,item) for item in owned])
            con.executemany(
                "INSERT INTO room_earnings(name,event_key,xp,coins,created_at) VALUES (?,?,?,?,?)",
                clean_earnings)
            con.executemany(
                "INSERT INTO room_transactions(name,item_id,cost,created_at) VALUES (?,?,?,?)",
                clean_transactions)
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
