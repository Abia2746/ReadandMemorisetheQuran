"""Adaptive, penalty-free Qur'an learning and milestone accounting.

Sabq: new memorisation. Sabqi: recently memorised verses and difficult words.
Manzil: older memorisation revision. Counts are planning suggestions, not
Tajweed assessments or guarantees of a memorisation deadline.
"""
from __future__ import annotations
import calendar
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import asyncpg
from app.services.quran_metadata import AYAHS, valid_verse

def add_months(day:date,months:int)->date:
    y=day.year+(day.month-1+months)//12
    m=(day.month-1+months)%12+1
    return date(y,m,min(day.day,calendar.monthrange(y,m)[1]))

def plan_goal_items(config:dict)->list[tuple[int,int]]:
    surahs=range(1,115) if config["goal"]=="whole" else (config["surah"],)
    return [(s,a) for s in surahs for a in range(1,AYAHS[s]+1)]

def _local_day(timezone_name:str)->date:
    try:return datetime.now(timezone.utc).astimezone(ZoneInfo(timezone_name)).date()
    except ZoneInfoNotFoundError:return datetime.now(timezone.utc).date()

async def reward_milestone(conn:asyncpg.Connection,user_id:UUID,key:str,
                           xp:int,coins:int,local_day:date):
    """Invoke inside a DB transaction: one immutable milestone, no duplicate XP."""
    inserted=await conn.fetchval(
        """INSERT INTO reward_ledger(user_id,milestone_key,xp_awarded,coins_awarded)
           VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING RETURNING 1""",
        user_id,key,xp,coins,
    )
    if not inserted:return False
    await conn.execute(
        """INSERT INTO learning_totals(user_id,xp,coins,streak,last_study_day)
           VALUES($1,$2,$3,1,$4)
           ON CONFLICT(user_id) DO UPDATE
           SET xp=learning_totals.xp+$2,coins=learning_totals.coins+$3,
             streak=CASE
               WHEN learning_totals.last_study_day=$4 THEN learning_totals.streak
               WHEN learning_totals.last_study_day=$4-1 THEN learning_totals.streak+1
               ELSE 1 END,
             last_study_day=GREATEST(learning_totals.last_study_day,$4),
             updated_at=now()""",user_id,xp,coins,local_day,
    )
    return True

async def compute_plan_state(conn:asyncpg.Connection,user_id:UUID,plan:dict)->dict[str,Any]:
    day=_local_day(plan["timezone_name"])
    items=plan_goal_items(plan)
    completed_rows=await conn.fetch(
        "SELECT surah,ayah,first_completed_at,last_reviewed_at FROM memorised_verses WHERE user_id=$1",
        user_id,
    )
    done={(row["surah"],row["ayah"]) for row in completed_rows}
    remaining=[x for x in items if x not in done]
    deadline=add_months(plan["start_date"],int(plan["target_months"]))
    weekdays=list(plan["weekdays"])
    if not weekdays:weekdays=[0,1,2,3,4,5]
    available_days=sum(1 for i in range(max(0,(deadline-day).days)+1)
                       if (day+timedelta(days=i)).weekday() in weekdays)
    required=math.ceil(len(remaining)/max(1,available_days))
    today_study=day.weekday() in weekdays
    session=await conn.fetchval(
        """SELECT 1 FROM study_sessions
           WHERE user_id=$1 AND plan_id=$2 AND local_day=$3 AND scope='sabq'
           LIMIT 1""",user_id,plan["id"],day,
    )
    suggested=min(15,required) if today_study and not session else 0
    # Always preserve a manageable suggestion instead of pretending to
    # meet an impossible deadline; user can extend months without penalty.
    new_passage=remaining[:suggested]
    learned={(r["surah"],r["ayah"]):r for r in completed_rows}
    recent=[key for key in done if (day-learned[key]["first_completed_at"].date()).days<=7]
    older=[key for key in done if key not in recent]
    recent.sort(key=lambda x: learned[x]["last_reviewed_at"])
    older.sort(key=lambda x: learned[x]["last_reviewed_at"])
    difficult=await conn.fetch(
        """SELECT surah,ayah,word_index,arabic,gloss,due_on,strength
           FROM difficult_words WHERE user_id=$1 AND due_on<=$2
           ORDER BY due_on, strength LIMIT 18""",
        user_id, day,
    )
    priority=list(dict.fromkeys((r["surah"],r["ayah"]) for r in difficult))
    sabqi=list(dict.fromkeys(priority+[v for v in recent if v not in new_passage]))[:8]
    manzil=[v for v in older if v not in sabqi][:8]
    return {
        "plan_id":str(plan["id"]),"title":plan["title"],
        "today":day.isoformat(),"goal":plan["goal"],"surah":plan["surah"],
        "deadline":deadline.isoformat(),"goal_total":len(items),
        "memorised":len(items)-len(remaining),"remaining":len(remaining),
        "progress_pct":round(100*(len(items)-len(remaining))/max(1,len(items)),1),
        "days_left":available_days,"required_per_study_day":required,
        "recommended_sabq":suggested,
        "sabq":[{"surah":s,"ayah":a} for s,a in new_passage],
        "sabqi":[{"surah":s,"ayah":a} for s,a in sabqi],
        "manzil":[{"surah":s,"ayah":a} for s,a in manzil],
        "difficult_words":[dict(item) for item in difficult],
        "study_today":today_study,"completed_today":bool(session),
        "overload":required>15 or (required>=12 and plan["sabq_minutes"]<45),
        "settings":{
            "months":plan["target_months"],"weekdays":weekdays,
            "sabq_minutes":plan["sabq_minutes"],
            "review_minutes":plan["review_minutes"],
            "study_time":plan["study_time"].strftime("%H:%M"),
            "reminder_minutes":plan["reminder_minutes"],
            "timezone_name":plan["timezone_name"],
        },
        "noor_message":(
            "Today is a rest or catch-up day. No missed-day penalties."
            if not today_study else
            "Your previous study remains saved. Revise gently; tomorrow recalculates."
            if session else
            "The target needs more study days or a longer timeline; slow, accurate learning matters more."
            if required>15 else
            "Begin with Sabqi and Manzil revision, then approach the new passage in small groups."
        ),
    }

def _escape_ics(value:str)->str:
    return str(value).replace("\\","\\\\").replace(";","\\;").replace(",","\\,").replace("\n","\\n")

def build_ics(plan:dict,horizon:int=90)->str:
    try:tz=ZoneInfo(plan["timezone_name"])
    except ZoneInfoNotFoundError:tz=ZoneInfo("UTC")
    today=datetime.now(timezone.utc).astimezone(tz).date()
    hour,minute=map(int,plan["study_time"].strftime("%H:%M").split(":"))
    weekdays=set(plan["weekdays"])
    output=["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//AlMuallim//NoorPlanner//EN",
      "CALSCALE:GREGORIAN","METHOD:PUBLISH","X-WR-CALNAME:Al-Muallim Study Plan"]
    for d in range(min(90,max(1,horizon))):
        day=today+timedelta(days=d)
        if day.weekday() not in weekdays:continue
        local_start=datetime(day.year,day.month,day.day,hour,minute,tzinfo=tz)
        utc_start=local_start.astimezone(timezone.utc)
        when=utc_start.strftime("%Y%m%dT%H%M%SZ")
        ref=f"alm-{plan['id']}-{day.isoformat()}@almuallim"
        duration=int(plan["sabq_minutes"])+int(plan["review_minutes"])
        lead=int(plan["reminder_minutes"])
        output.extend([
          "BEGIN:VEVENT",f"UID:{ref}",
          "DTSTAMP:"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
          "DTSTART:"+when,"DURATION:PT"+str(duration)+"M",
          "SUMMARY:"+_escape_ics("Al-Mu'allim · Sabq, Sabqi & Manzil"),
          "DESCRIPTION:"+_escape_ics("Review gently before new Qur'an memorisation. Missed days never carry a penalty."),
          "BEGIN:VALARM","ACTION:DISPLAY",
          "DESCRIPTION:Qur'an study reminder",
          "TRIGGER:-PT"+str(lead)+"M",
          "END:VALARM","END:VEVENT",
        ])
    output.extend(["END:VCALENDAR",""])
    return "\r\n".join(output)
