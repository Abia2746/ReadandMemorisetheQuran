"""Al-Mu'allim — editable adaptive Hifdh planner.

This planning engine uses Quran ayah counts (Hafs edition), explicitly
self-reported progress and local UK dates. Daily new-work counts are a practical
starting estimate only: ayah length and learning difficulty vary widely.

A calendar export provides native calendar reminders *after* the user imports
it and enables notifications. No hidden background push service is claimed.
"""
from __future__ import annotations

import calendar
import hashlib
import datetime as dt
import json
import math
import pathlib
import sqlite3
import uuid
from contextlib import closing
from zoneinfo import ZoneInfo

_DB=pathlib.Path(__file__).resolve().with_name("muallim.db")
AYAHS=[0,7,286,200,176,120,165,206,75,129,109,123,111,43,
52,99,128,111,110,98,135,112,78,118,64,77,227,93,
88,69,60,34,30,73,54,45,83,182,88,75,85,54,53,
89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,
22,24,13,14,11,11,18,12,12,30,52,52,44,28,28,
20,56,40,31,50,40,46,42,29,19,36,25,22,17,19,
26,30,20,15,21,11,8,8,19,5,8,8,11,11,8,3,
9,5,4,7,3,6,3,5,4,5,6]
assert len(AYAHS)==115 and sum(AYAHS)==6236

SURAHS=[
"Al-Fatihah","Al-Baqarah","Ali 'Imran","An-Nisa","Al-Ma'idah","Al-An'am",
"Al-A'raf","Al-Anfal","At-Tawbah","Yunus","Hud","Yusuf","Ar-Ra'd",
"Ibrahim","Al-Hijr","An-Nahl","Al-Isra","Al-Kahf","Maryam","Ta-Ha",
"Al-Anbiya","Al-Hajj","Al-Mu'minun","An-Nur","Al-Furqan","Ash-Shu'ara",
"An-Naml","Al-Qasas","Al-Ankabut","Ar-Rum","Luqman","As-Sajdah",
"Al-Ahzab","Saba","Fatir","Ya-Sin","As-Saffat","Sad","Az-Zumar",
"Ghafir","Fussilat","Ash-Shura","Az-Zukhruf","Ad-Dukhan","Al-Jathiyah",
"Al-Ahqaf","Muhammad","Al-Fath","Al-Hujurat","Qaf","Adh-Dhariyat",
"At-Tur","An-Najm","Al-Qamar","Ar-Rahman","Al-Waqi'ah","Al-Hadid",
"Al-Mujadilah","Al-Hashr","Al-Mumtahanah","As-Saff","Al-Jumu'ah",
"Al-Munafiqun","At-Taghabun","At-Talaq","At-Tahrim","Al-Mulk",
"Al-Qalam","Al-Haqqah","Al-Ma'arij","Nuh","Al-Jinn","Al-Muzzammil",
"Al-Muddaththir","Al-Qiyamah","Al-Insan","Al-Mursalat","An-Naba",
"An-Nazi'at","Abasa","At-Takwir","Al-Infitar","Al-Mutaffifin",
"Al-Inshiqaq","Al-Buruj","At-Tariq","Al-A'la","Al-Ghashiyah",
"Al-Fajr","Al-Balad","Ash-Shams","Al-Layl","Ad-Duha","Ash-Sharh",
"At-Tin","Al-Alaq","Al-Qadr","Al-Bayyinah","Az-Zalzalah",
"Al-Adiyat","Al-Qari'ah","At-Takathur","Al-Asr","Al-Humazah",
"Al-Fil","Quraysh","Al-Ma'un","Al-Kawthar","Al-Kafirun",
"An-Nasr","Al-Masad","Al-Ikhlas","Al-Falaq","An-Nas"]
assert len(SURAHS)==114

TZ=ZoneInfo("Europe/London")
DEFAULT={
    "goal":"surah", "surah":2, "months":24, "weekdays":[0,1,2,3,4,5],
    "minutes":35, "review_minutes":15, "time":"18:30", "remind_before":10,
    "focus":False, "start":None,
}
MINUTES_MIN,MINUTES_MAX=10,120


def _connection():
    con=sqlite3.connect(_DB,timeout=12,isolation_level=None)
    con.execute("PRAGMA busy_timeout=12000")
    con.execute("""CREATE TABLE IF NOT EXISTS hifdh_plans(
        name TEXT PRIMARY KEY, plan_json TEXT NOT NULL, updated TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hifdh_completed(
        name TEXT NOT NULL,surah INTEGER NOT NULL,ayah INTEGER NOT NULL,
        completed TEXT NOT NULL,
        PRIMARY KEY(name,surah,ayah)
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hifdh_sessions(
        name TEXT NOT NULL,day TEXT NOT NULL,scope TEXT NOT NULL,
        surah INTEGER NOT NULL,first_ayah INTEGER NOT NULL,last_ayah INTEGER NOT NULL,
        completed_at TEXT NOT NULL,
        PRIMARY KEY(name,day,scope)
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hifdh_review(
        name TEXT NOT NULL, surah INTEGER NOT NULL, ayah INTEGER NOT NULL,
        stage INTEGER NOT NULL, due TEXT NOT NULL, PRIMARY KEY(name,surah,ayah)
    )""")
    return con


def today_local() -> dt.date:
    return dt.datetime.now(TZ).date()


def plus_months(date:dt.date,months:int)->dt.date:
    y=date.year+(date.month-1+months)//12
    m=(date.month-1+months)%12+1
    return dt.date(y,m,min(date.day,calendar.monthrange(y,m)[1]))


REVIEW_DAYS = (1, 3, 7, 14, 30, 60)


def _initial_due(stamp):
    learned = dt.datetime.fromisoformat(stamp)
    day = learned.astimezone(TZ).date() if learned.tzinfo else learned.date()
    return (day + dt.timedelta(days=1)).isoformat()


def verse_reviews(name):
    with closing(_connection()) as con:
        rows = con.execute("""SELECT c.surah,c.ayah,c.completed,r.due
            FROM hifdh_completed c LEFT JOIN hifdh_review r USING(name,surah,ayah)
            WHERE c.name=?""", (name,)).fetchall()
    items = []
    for surah, ayah, stamp, due in rows:
        try:
            items.append({"surah": surah, "ayah": ayah, "due": due or _initial_due(stamp)})
        except (ValueError, TypeError, OverflowError):
            continue
    return sorted(items, key=lambda item: (item["due"], item["surah"], item["ayah"]))


def record_verse_recall(name, surah, ayah, rating, *, day=None):
    if type(surah) is not int or not 1 <= surah <= 114 or type(ayah) is not int or not 1 <= ayah <= AYAHS[surah]:
        raise ValueError("Invalid verse.")
    if rating not in ("learnt", "prompt", "meaning", "recalled"):
        raise ValueError("Choose a recall result.")
    day = day or today_local()
    with closing(_connection()) as con, con:
        con.execute("BEGIN IMMEDIATE")
        ref = (name, surah, ayah)
        if rating == "learnt":
            result = con.execute("INSERT OR IGNORE INTO hifdh_completed VALUES(?,?,?,?)",
                                 (*ref, day.isoformat()))
            if not result.rowcount:
                return {"ok": False, "message": "This ayah is already scheduled."}
            stage = 0
        else:
            row = con.execute("""SELECT c.completed,r.stage,r.due FROM hifdh_completed c
                LEFT JOIN hifdh_review r USING(name,surah,ayah)
                WHERE c.name=? AND c.surah=? AND c.ayah=?""", ref).fetchone()
            if not row or (row[2] or _initial_due(row[0])) > day.isoformat():
                return {"ok": False, "message": "This ayah is not due for review yet."}
            stage = min((row[1] or 0)+1, len(REVIEW_DAYS)-1) if rating == "recalled" else 0
        due = (day + dt.timedelta(days=REVIEW_DAYS[stage])).isoformat()
        con.execute("INSERT OR REPLACE INTO hifdh_review VALUES(?,?,?,?,?)", (*ref,stage,due))
    return {"ok": True, "message": f"{surah}:{ayah} saved. Next review on {due}."}


def _safe_config(data, previous=None, *, now=None):
    if not isinstance(data,dict):
        raise ValueError("Plan settings must be an object.")
    old=previous or {}
    d={**DEFAULT,**old,**data}
    goal=d.get("goal")
    if goal not in ("whole","surah"):
        raise ValueError("Choose the whole Qur'an or one surah.")
    surah=d.get("surah",2)
    if type(surah) is not int or not 1<=surah<=114:
        raise ValueError("Choose a surah from 1 to 114.")
    months=d.get("months",24)
    if type(months) is not int or not 1<=months<=120:
        raise ValueError("Choose 1–120 months.")
    weekdays=d.get("weekdays")
    if not isinstance(weekdays,list) or len(weekdays)!=len(set(map(str,weekdays))) or not weekdays:
        raise ValueError("Choose at least one study day.")
    if any(type(x) is not int or x<0 or x>6 for x in weekdays):
        raise ValueError("Study weekdays must be valid.")
    minutes=d.get("minutes")
    if type(minutes) is not int or not MINUTES_MIN<=minutes<=MINUTES_MAX:
        raise ValueError("New-work session must be 10–120 minutes.")
    review=d.get("review_minutes")
    if type(review) is not int or not 0<=review<=90:
        raise ValueError("Review must be 0–90 minutes.")
    hour=d.get("time")
    if not isinstance(hour,str) or len(hour)!=5 or hour[2]!=":" or not (
        hour[:2].isdigit() and hour[3:].isdigit() and 0<=int(hour[:2])<24
        and 0<=int(hour[3:])<=59
    ):
        raise ValueError("Use a 24-hour reminder time, e.g. 18:30.")
    advance=d.get("remind_before",10)
    if type(advance) is not int or not 0<=advance<=60:
        raise ValueError("Reminder lead time must be 0–60 minutes.")
    if type(d.get("focus")) is not bool:
        raise ValueError("Focus companion must be enabled or disabled.")
    now=now or today_local()
    start=old.get("start") or data.get("start") or now.isoformat()
    try: dt.date.fromisoformat(start)
    except (ValueError,TypeError):raise ValueError("Invalid start date.")
    return {
        "goal":goal,"surah":surah,"months":months,
        "weekdays":sorted(weekdays),"minutes":minutes,
        "review_minutes":review,"time":hour,"remind_before":advance,
        "focus":d["focus"],"start":start
    }


def save_plan(name:str, values:dict):
    if not isinstance(name,str) or not name.strip():
        raise ValueError("Select a study profile.")
    with closing(_connection()) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            row=con.execute("SELECT plan_json FROM hifdh_plans WHERE name=?",(name,)).fetchone()
            old=json.loads(row[0]) if row else None
            config=_safe_config(values,old)
            con.execute(
                """INSERT INTO hifdh_plans(name,plan_json,updated)
                VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET
                plan_json=excluded.plan_json,updated=excluded.updated""",
                (name,json.dumps(config),dt.datetime.now(dt.timezone.utc).isoformat())
            )
            con.execute("COMMIT")
            return {"ok":True,"message":"Noor has updated your plan. Existing memorisation progress is preserved."}
        except BaseException:
            con.execute("ROLLBACK")
            raise


def _target_list(config):
    surahs=range(1,115) if config["goal"]=="whole" else [config["surah"]]
    return [(s,a) for s in surahs for a in range(1,AYAHS[s]+1)]


def _study_days_between(today,deadline,weekdays):
    # Include today if today is a chosen study day.
    return sum((today+dt.timedelta(days=i)).weekday() in weekdays
               for i in range(max(0,(deadline-today).days)+1))


def _format_ranges(items):
    if not items:return []
    out=[];a=b=items[0]
    for item in items[1:]:
        if item[0]==b[0] and item[1]==b[1]+1:
            b=item
        else:
            out.append({"surah":a[0],"from":a[1],"to":b[1],
                        "label":f"{SURAHS[a[0]-1]} {a[0]}:{a[1]}"+
                        (f"–{b[1]}" if a[1]!=b[1] else "")})
            a=b=item
    out.append({"surah":a[0],"from":a[1],"to":b[1],
                "label":f"{SURAHS[a[0]-1]} {a[0]}:{a[1]}"+
                (f"–{b[1]}" if a[1]!=b[1] else "")})
    return out


def get_state(name:str, *, day:dt.date|None=None):
    day=day or today_local()
    with closing(_connection()) as con:
        row=con.execute("SELECT plan_json FROM hifdh_plans WHERE name=?",(name,)).fetchone()
        saved=bool(row)
        config=_safe_config(json.loads(row[0]) if row else {},now=day)
        complete={(s,a):stamp for s,a,stamp in con.execute(
            "SELECT surah,ayah,completed FROM hifdh_completed WHERE name=?",(name,)).fetchall()}
        daily=con.execute(
            "SELECT scope,surah,first_ayah,last_ayah FROM hifdh_sessions WHERE name=? AND day=?",
            (name,day.isoformat())
        ).fetchall()
    goal_items=_target_list(config)
    total=len(goal_items)
    done=sum(verse in complete for verse in goal_items)
    remaining=[v for v in goal_items if v not in complete]
    start=dt.date.fromisoformat(config["start"])
    deadline=plus_months(start,config["months"])
    study_today=day.weekday() in config["weekdays"]
    days_left=_study_days_between(day,deadline,config["weekdays"])
    required=math.ceil(len(remaining)/max(1,days_left)) if remaining else 0
    cap=30  # a prudent UI cap, never falsely claimed to meet an impossible deadline
    recommended=min(cap,required) if study_today else 0
    todays_items=remaining[:recommended] if study_today else []
    # A completed daily session is not instantly replaced by the *next* day's
    # work: avoid pushing users into endless extra tasks.
    already_done=bool(daily)
    if already_done:
        session_items=[]
        for _,surah,first,last in daily:
            session_items.extend((surah,i) for i in range(first,last+1))
        today_ranges=_format_ranges(session_items)
    else:
        today_ranges=_format_ranges(todays_items)
    minutes=config["minutes"]
    review=config["review_minutes"]
    recent=[]
    older=[]
    if saved and review and study_today:
        for verse in goal_items:
            if verse not in complete:
                continue
            try:
                stamp=dt.datetime.fromisoformat(complete[verse])
                completed_day=stamp.astimezone(TZ).date() if stamp.tzinfo else stamp.date()
            except (ValueError,TypeError):
                continue
            age=(day-completed_day).days
            if 1<=age<=7:
                recent.append(verse)
            elif age>7:
                older.append(verse)
    # Rotate within each learner's own history; the time budget is a suggestion.
    def rotation(pool,limit):
        if not pool or not limit:
            return []
        offset=day.toordinal()%len(pool)
        selected=(pool[offset:]+pool[:offset])[:limit]
        return _format_ranges(sorted(selected))
    budget=max(1,review//2)
    recent_budget=(budget+1)//2 if older else budget
    recent_budget=min(recent_budget,len(recent))
    older_budget=min(budget-recent_budget,len(older))
    recent_budget=min(len(recent),budget-older_budget)
    overload=required>cap or (required>=18 and minutes<45)
    if not saved:
        speech=("Assalamu alaikum. Choose a surah or the full Qur'an, tell me "
                "when you're usually free, and I will prepare a gentle, "
                "editable memorisation and revision timetable.")
    elif not remaining:
        speech=("Alhamdulillah — you've marked every ayah in this goal as memorised. "
                "Keep regular revision and have your memorisation checked with a teacher.")
    elif not study_today:
        speech=("Today is one of your chosen rest or catch-up days. "
                "You can listen or revise a small passage if you wish, without pressure.")
    elif already_done:
        speech=("Alhamdulillah, you've completed today's planned new passage. "
                "Use your remaining time to revise and rest. Tomorrow's plan will adapt.")
    elif overload:
        speech=(f"Your {config['months']}-month goal needs about {required} new ayahs "
                "per study day at your current progress. Some ayahs are much longer "
                "than others, so this may be demanding. I recommend more time "
                "or additional study days rather than rushing pronunciation.")
    else:
        speech=(f"Today we'll approach about {recommended} ayahs in small parts. "
                f"Begin with {review} minutes reviewing earlier memorisation, "
                f"then spend {minutes} minutes on the new passage. "
                "Listen once, repeat short groups and check subtle Tajweed with your teacher.")
    return {
        "configured":saved,"config":config,"surahs":[{"n":i+1,"name":name,"count":AYAHS[i+1]}
                                             for i,name in enumerate(SURAHS)],
        "goal_total":total,"done":done,"left":len(remaining),
        "progress_pct":round(done/max(1,total)*100,1),
        "deadline":deadline.isoformat(),"days_left":days_left,
        "study_today":study_today,"finished_today":already_done,
        "required_ayahs_per_day":required,"recommended_ayahs":recommended,
        "overload":overload,"today":day.isoformat(),
        "today_ranges":today_ranges,
        "sabqi_ranges":rotation(recent,recent_budget),
        "manzil_ranges":rotation(older,older_budget),
        "teacher_message":speech,
        "reminder_supported":"calendar_export",
        "notification_explanation":(
            "Download the schedule and enable alerts in Apple Calendar. "
            "Background push from a Safari tab is not provided."
        ),
        "focus_explanation":(
            "Optional in-app focus companion only; a website cannot lock "
            "other iPad apps. Set app limits separately in Apple Screen Time."
        ),
    }


def finish_today(name):
    state=get_state(name)
    if not state["configured"]:
        return {"ok":False,"message":"Create your plan first."}
    if state["finished_today"]:
        return {"ok":False,"message":"Today's planned session has already been marked complete."}
    if not state["study_today"]:
        return {"ok":False,"message":"Today is a rest day in your plan. You can edit your weekdays."}
    items=state["today_ranges"]
    if not items:
        return {"ok":False,"message":"There are no new ayahs left in this goal."}
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    with closing(_connection()) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            current=con.execute(
                "SELECT 1 FROM hifdh_sessions WHERE name=? AND day=?",
                (name,state["today"])
            ).fetchone()
            if current:
                con.execute("COMMIT")
                return {"ok":False,"message":"Already completed today."}
            for idx,r in enumerate(items):
                con.execute(
                    "INSERT INTO hifdh_sessions(name,day,scope,surah,first_ayah,last_ayah,completed_at) VALUES(?,?,?,?,?,?,?)",
                    (name,state["today"],str(idx),r["surah"],r["from"],r["to"],now)
                )
                for ayah in range(r["from"],r["to"]+1):
                    con.execute(
                        "INSERT OR IGNORE INTO hifdh_completed(name,surah,ayah,completed) VALUES(?,?,?,?)",
                        (name,r["surah"],ayah,now)
                    )
            con.execute("COMMIT")
            return {"ok":True,"message":"Alhamdulillah. Today's self-reported passage is saved. Your next target will adapt."}
        except BaseException:
            con.execute("ROLLBACK")
            raise


def _escape_ics(s):
    return str(s).replace("\\","\\\\").replace("\n","\\n").replace(",","\\,").replace(";","\\;")


def build_calendar(name, *, start:dt.date|None=None, horizon_days=90):
    """Produce an iOS/Apple Calendar-compatible .ics with alarm requests.

    Importing the .ics alone does not guarantee alerts; Calendar settings
    control whether notifications appear on the actual device.
    """
    state=get_state(name,day=start or today_local())
    if not state["configured"]:
        raise ValueError("Save a plan before exporting reminders.")
    config=state["config"]
    day=start or today_local()
    events=[]
    for i in range(min(max(horizon_days,1),180)):
        current=day+dt.timedelta(days=i)
        if current.weekday() not in config["weekdays"]:continue
        h,m=map(int,config["time"].split(":"))
        stamp=current.strftime("%Y%m%d")+f"T{h:02d}{m:02d}00"
        uid=f"hifdh-{hashlib.sha256(name.encode('utf8')).hexdigest()[:20]}-{current.strftime('%Y%m%d')}@almuallim"
        reminder=config["remind_before"]
        events.extend([
            "BEGIN:VEVENT",
            "UID:"+uid,"DTSTAMP:"+dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "DTSTART;TZID=Europe/London:"+stamp,
            "DURATION:PT"+str(config["minutes"]+config["review_minutes"])+"M",
            "SUMMARY:"+_escape_ics("Al-Mu'allim · Qur'an memorisation and revision"),
            "DESCRIPTION:"+_escape_ics("Open Al-Mu'allim. Review first, then memorise gently. Adjust your daily target in My Journey."),
            "BEGIN:VALARM",
            "ACTION:DISPLAY","DESCRIPTION:"+_escape_ics("Qur'an study session"),
            "TRIGGER:-PT"+str(reminder)+"M","END:VALARM","END:VEVENT"
        ])
    return "\r\n".join([
        "BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//AlMuallim//HifdhPlan//EN",
        "CALSCALE:GREGORIAN","METHOD:PUBLISH",
        "X-WR-CALNAME:Al-Mu'allim Hifdh Plan",
        "X-WR-TIMEZONE:Europe/London",*events,"END:VCALENDAR",""
    ])


def export_cloud_snapshot(name: str) -> dict:
    """Export only the learner's own planner data, not recordings or scores."""
    if not name or len(name) > 128:
        raise ValueError("Invalid learner profile")
    with closing(_connection()) as con:
        row = con.execute("SELECT plan_json FROM hifdh_plans WHERE name=?", (name,)).fetchone()
        completed = con.execute(
            """SELECT surah,ayah,completed,stage,due FROM hifdh_completed
            LEFT JOIN hifdh_review USING(name,surah,ayah) WHERE name=? ORDER BY surah,ayah""",
            (name,),
        ).fetchall()
        sessions = con.execute(
            "SELECT day,scope,surah,first_ayah,last_ayah,completed_at "
            "FROM hifdh_sessions WHERE name=? ORDER BY day,scope",
            (name,),
        ).fetchall()
    return {
        "plan": json.loads(row[0]) if row else {},
        "completed": [
            {"surah": s, "ayah": a, "completed": stamp,
             **({"stage": stage, "due": due} if due else {})}
            for s, a, stamp, stage, due in completed
        ],
        "sessions": [
            {"day": day, "scope": scope, "surah": surah,
             "first_ayah": first, "last_ayah": last, "completed_at": stamp}
            for day, scope, surah, first, last, stamp in sessions
        ],
    }


def import_cloud_snapshot(name: str, snapshot: dict) -> None:
    """Restore validated cloud planner state atomically into a user's local cache.

    The owner-only Supabase table is authoritative for signed-in learners.
    """
    if not isinstance(name, str) or not name or len(name) > 128:
        raise ValueError("Invalid profile")
    if not isinstance(snapshot, dict):
        raise ValueError("Invalid cloud planner snapshot")
    raw_plan = snapshot.get("plan", {})
    completed = snapshot.get("completed", [])
    sessions = snapshot.get("sessions", [])
    if not isinstance(raw_plan, dict) or not isinstance(completed, list) or not isinstance(sessions, list):
        raise ValueError("Invalid cloud planner fields")
    if len(completed) > 6236 or len(sessions) > 2000:
        raise ValueError("Cloud planner exceeds supported limits")
    config = _safe_config(raw_plan) if raw_plan else None
    clean_reviews = []
    clean_completed = []
    for r in completed:
        if not isinstance(r, dict):
            raise ValueError("Invalid completed verse")
        s, a, stamp = r.get("surah"), r.get("ayah"), r.get("completed")
        if type(s) is not int or not 1 <= s <= 114 or type(a) is not int or not 1 <= a <= AYAHS[s]:
            raise ValueError("Invalid verse coordinates")
        if not isinstance(stamp, str) or len(stamp) > 60:
            raise ValueError("Invalid completion timestamp")
        if "stage" in r or "due" in r:
            stage = r.get("stage")
            if type(stage) is not int or not 0 <= stage < len(REVIEW_DAYS) or not isinstance(r.get("due"), str):
                raise ValueError("Invalid review schedule")
            due = dt.date.fromisoformat(r["due"])
            clean_reviews.append((name,s,a,stage,due.isoformat()))
        clean_completed.append((name, s, a, stamp))
    clean_sessions = []
    for r in sessions:
        if not isinstance(r, dict):
            raise ValueError("Invalid completed session")
        s, first, last = r.get("surah"), r.get("first_ayah"), r.get("last_ayah")
        if type(s) is not int or not 1 <= s <= 114 or type(first) is not int or type(last) is not int or not 1 <= first <= last <= AYAHS[s]:
            raise ValueError("Invalid session range")
        day, scope, stamp = r.get("day"), r.get("scope"), r.get("completed_at")
        try:
            dt.date.fromisoformat(day)
        except (TypeError, ValueError):
            raise ValueError("Invalid session date")
        if not isinstance(scope, str) or len(scope) > 40 or not isinstance(stamp, str) or len(stamp) > 60:
            raise ValueError("Invalid session metadata")
        clean_sessions.append((name, day, scope, s, first, last, stamp))
    with closing(_connection()) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            for table in ("hifdh_plans", "hifdh_completed", "hifdh_sessions", "hifdh_review"):
                con.execute(f"DELETE FROM {table} WHERE name=?", (name,))
            if config is not None:
                con.execute(
                    "INSERT INTO hifdh_plans(name,plan_json,updated) VALUES(?,?,?)",
                    (name, json.dumps(config), dt.datetime.now(dt.timezone.utc).isoformat()),
                )
            con.executemany("INSERT INTO hifdh_review VALUES(?,?,?,?,?)", clean_reviews)
            con.executemany(
                "INSERT INTO hifdh_completed(name,surah,ayah,completed) VALUES(?,?,?,?)",
                clean_completed,
            )
            con.executemany(
                "INSERT INTO hifdh_sessions(name,day,scope,surah,first_ayah,last_ayah,completed_at) "
                "VALUES(?,?,?,?,?,?,?)", clean_sessions,
            )
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
