"""Persistent learner endpoints for Noor planner, difficult words and room XP.

All mutations require verified user identity. Daily completion and self-graded
drills are self-reported; XP is modest, server-awarded and retry-idempotent.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone, time as clock_time
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from app.routers.billing import current_user, db_conn
from app.services.billing import User, resolve_entitlement
from app.services.learning import compute_plan_state, build_ics, reward_milestone
from app.services.quran_metadata import AYAHS, valid_verse

router=APIRouter(prefix="/api/learning",tags=["learning"])


class PlanInput(BaseModel):
    title: str = Field(default="A Plan with Noor",max_length=100)
    goal: Literal["surah","whole"]="surah"
    surah: int = Field(default=2,ge=1,le=114)
    months: int = Field(default=24,ge=1,le=120)
    weekdays: list[int] = Field(default=[0,1,2,3,4,5],min_length=1,max_length=7)
    sabq_minutes: int = Field(default=35,ge=10,le=120)
    review_minutes: int = Field(default=15,ge=0,le=90)
    study_time: str = Field(default="18:30",pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    reminder_minutes: int = Field(default=10,ge=0,le=60)

    @field_validator("weekdays")
    @classmethod
    def valid_days(cls,value:list[int]):
        if len(value)!=len(set(value)) or any(x<0 or x>6 for x in value):
            raise ValueError("Choose distinct weekdays 0 through 6")
        return sorted(value)


def _day(user:User)->date:
    try:return datetime.now(timezone.utc).astimezone(ZoneInfo(user.quota_timezone_name)).date()
    except ZoneInfoNotFoundError:return datetime.now(timezone.utc).date()


async def _owned_plan(conn:asyncpg.Connection,user:User,plan_id:UUID|None=None):
    query="""SELECT * FROM learning_plans
             WHERE user_id=$1 AND status='active'"""
    params=[user.id]
    if plan_id:
        query+=" AND id=$2"
        params.append(plan_id)
    query+=" ORDER BY created_at LIMIT 1"
    row=await conn.fetchrow(query,*params)
    if not row:raise HTTPException(404,"No active Noor plan is saved")
    return dict(row)


@router.get("/profile")
async def profile(user:User=Depends(current_user),conn:asyncpg.Connection=Depends(db_conn)):
    row=await conn.fetchrow(
        "SELECT xp,coins,streak,last_study_day FROM learning_totals WHERE user_id=$1",user.id
    )
    return {"xp":row["xp"] if row else 0,"coins":row["coins"] if row else 0,
            "streak":row["streak"] if row else 0,
            "last_study_day":str(row["last_study_day"]) if row and row["last_study_day"] else None}


@router.get("/plans")
async def get_plans(user:User=Depends(current_user),conn:asyncpg.Connection=Depends(db_conn)):
    plans=await conn.fetch("""SELECT id,title,goal,surah,target_months,status,modified_at
                          FROM learning_plans WHERE user_id=$1
                          ORDER BY created_at DESC""",user.id)
    return {"plans":[{"id":str(p["id"]),"title":p["title"],"goal":p["goal"],
                       "surah":p["surah"],"months":p["target_months"],
                       "status":p["status"],"modified_at":p["modified_at"].isoformat()} for p in plans]}


@router.post("/plans")
async def create_plan(body:PlanInput,user:User=Depends(current_user),
                      conn:asyncpg.Connection=Depends(db_conn)):
    entitlement=await resolve_entitlement(conn,user.id)
    async with conn.transaction():
        # Serialise plan creation for a user; prevent race to multiple free plans.
        await conn.execute("SELECT 1 FROM users WHERE id=$1 FOR UPDATE",user.id)
        active=await conn.fetchval(
            "SELECT count(*) FROM learning_plans WHERE user_id=$1 AND status='active'",user.id
        )
        if active>=1 and entitlement.tier=="free":
            raise HTTPException(409,detail={
                "code":"free_plan_limit",
                "message":"Your free Noor plan is still active. You can edit it any time without losing progress."
            })
        plan_id=await conn.fetchval(
            """INSERT INTO learning_plans(
                user_id,title,goal,surah,start_date,target_months,weekdays,
                sabq_minutes,review_minutes,study_time,reminder_minutes,timezone_name)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
               RETURNING id""",user.id,body.title,body.goal,body.surah,
            _day(user),body.months,body.weekdays,body.sabq_minutes,
            body.review_minutes,clock_time.fromisoformat(body.study_time),
            body.reminder_minutes,user.quota_timezone_name,
        )
    return {"plan_id":str(plan_id),"message":"Noor has prepared an editable plan; there are no missed-day penalties."}


@router.put("/plans/{plan_id}")
async def edit_plan(plan_id:UUID,body:PlanInput,user:User=Depends(current_user),
                    conn:asyncpg.Connection=Depends(db_conn)):
    result=await conn.execute(
        """UPDATE learning_plans SET title=$3,goal=$4,surah=$5,
           target_months=$6,weekdays=$7,sabq_minutes=$8,
           review_minutes=$9,study_time=$10,reminder_minutes=$11,
           modified_at=now()
           WHERE id=$1 AND user_id=$2 AND status='active'""",
        plan_id,user.id,body.title,body.goal,body.surah,body.months,
        body.weekdays,body.sabq_minutes,body.review_minutes,
        clock_time.fromisoformat(body.study_time),body.reminder_minutes,
    )
    if result=="UPDATE 0":raise HTTPException(404,"Plan not found")
    return {"plan_id":str(plan_id),"message":"Your plan was updated. Earlier memorisation and XP are preserved."}


@router.get("/plan/today")
async def today_plan(user:User=Depends(current_user),conn:asyncpg.Connection=Depends(db_conn)):
    row=await conn.fetchrow(
        """SELECT * FROM learning_plans WHERE user_id=$1 AND status='active'
           ORDER BY created_at LIMIT 1""",user.id
    )
    if not row:return {"configured":False,"message":"Choose a Surah or whole Qur'an to create your first free plan."}
    state=await compute_plan_state(conn,user.id,dict(row))
    return {"configured":True,**state}


class CompleteDay(BaseModel):
    plan_id: UUID


@router.post("/plan/complete-day")
async def complete_day(body:CompleteDay,user:User=Depends(current_user),
                       conn:asyncpg.Connection=Depends(db_conn)):
    async with conn.transaction():
        plan=await _owned_plan(conn,user,body.plan_id)
        state=await compute_plan_state(conn,user.id,plan)
        day=date.fromisoformat(state["today"])
        if not state["study_today"]:
            raise HTTPException(409,"Today is a planned rest or catch-up day")
        if state["completed_today"]:
            return {"saved":True,"already_completed":True,"message":"Today is already complete; no extra work is required."}
        saved=await conn.fetchval(
            """INSERT INTO study_sessions(user_id,plan_id,local_day,scope,verse_reference)
               VALUES($1,$2,$3,'sabq','daily')
               ON CONFLICT DO NOTHING RETURNING 1""",user.id,body.plan_id,day,
        )
        if not saved:return {"saved":True,"already_completed":True}
        for v in state["sabq"]:
            await conn.execute(
                """INSERT INTO memorised_verses(user_id,surah,ayah)
                   VALUES($1,$2,$3) ON CONFLICT(user_id,surah,ayah)
                   DO UPDATE SET last_reviewed_at=now(),
                                 review_count=memorised_verses.review_count+1""",
                user.id,v["surah"],v["ayah"],
            )
        await reward_milestone(conn,user.id,
            f"sabq:{body.plan_id}:{day.isoformat()}",30,10,day)
    return {"saved":True,"verses_self_reported":len(state["sabq"]),
            "message":"Alhamdulillah. Your saved progress remains; future targets recalculate gently."}


class FlagWord(BaseModel):
    surah:int=Field(ge=1,le=114)
    ayah:int=Field(ge=1,le=286)
    index:int=Field(ge=1,le=300)
    arabic:str=Field(min_length=1,max_length=250)
    meaning:str=Field(default="",max_length=300)
    reason:str=Field(default="Needs revision",max_length=160)


@router.post("/difficult/flag")
async def flag_word(body:FlagWord,user:User=Depends(current_user),
                    conn:asyncpg.Connection=Depends(db_conn)):
    if not valid_verse(body.surah,body.ayah):
        raise HTTPException(422,"Invalid Qur'an reference")
    await conn.execute(
        """INSERT INTO difficult_words(
           user_id,surah,ayah,word_index,arabic,gloss,reason,due_on)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8)
           ON CONFLICT(user_id,surah,ayah,word_index)
           DO UPDATE SET reason=EXCLUDED.reason,due_on=EXCLUDED.due_on,
             strength=0""",
        user.id,body.surah,body.ayah,body.index,
        body.arabic,body.meaning,body.reason,_day(user),
    )
    return {"saved":True,"word_id":f"{body.surah}:{body.ayah}:{body.index}"}


@router.get("/difficult")
async def difficult(user:User=Depends(current_user),
                    conn:asyncpg.Connection=Depends(db_conn)):
    rows=await conn.fetch(
        """SELECT surah,ayah,word_index,arabic,gloss,reason,strength,due_on
           FROM difficult_words WHERE user_id=$1
           ORDER BY due_on ASC, strength ASC LIMIT 200""",user.id
    )
    return {"words":[{**dict(r),"due_on":r["due_on"].isoformat()} for r in rows]}


class ReviewWord(BaseModel):
    correct:bool


@router.post("/difficult/{surah}/{ayah}/{word_index}/review")
async def review_word(surah:int,ayah:int,word_index:int,body:ReviewWord,
                      user:User=Depends(current_user),conn:asyncpg.Connection=Depends(db_conn)):
    day=_day(user)
    async with conn.transaction():
        row=await conn.fetchrow(
            """SELECT strength FROM difficult_words
               WHERE user_id=$1 AND surah=$2 AND ayah=$3 AND word_index=$4 FOR UPDATE""",
            user.id,surah,ayah,word_index,
        )
        if row is None:raise HTTPException(404,"Difficult word not found")
        strength=min(5,int(row["strength"])+1) if body.correct else 0
        intervals=(1,2,4,8,16,30)
        due=day+timedelta(days=intervals[strength])
        await conn.execute(
            """UPDATE difficult_words SET strength=$5,due_on=$6,last_reviewed_at=now()
               WHERE user_id=$1 AND surah=$2 AND ayah=$3 AND word_index=$4""",
            user.id,surah,ayah,word_index,strength,due,
        )
        if strength>=4 and body.correct:
            await reward_milestone(conn,user.id,
                f"word-mastered:{surah}:{ayah}:{word_index}",10,3,day)
    return {"strength":strength,"due_on":due.isoformat(),"self_reported":True}


@router.delete("/difficult/{surah}/{ayah}/{word_index}")
async def remove_flag(surah:int,ayah:int,word_index:int,user:User=Depends(current_user),
                      conn:asyncpg.Connection=Depends(db_conn)):
    await conn.execute(
        """DELETE FROM difficult_words WHERE user_id=$1
           AND surah=$2 AND ayah=$3 AND word_index=$4""",user.id,surah,ayah,word_index,
    )
    return {"removed":True}


class CompletedDrills(BaseModel):
    surah:int=Field(ge=1,le=114)
    ayah:int=Field(ge=1,le=286)


@router.post("/drills/complete")
async def drills_complete(body:CompletedDrills,user:User=Depends(current_user),
                          conn:asyncpg.Connection=Depends(db_conn)):
    if not valid_verse(body.surah,body.ayah):
        raise HTTPException(422,"Invalid verse")
    async with conn.transaction():
        awarded=await reward_milestone(conn,user.id,
            f"drills:{body.surah}:{body.ayah}",20,5,_day(user))
    return {"recorded":True,"awarded":awarded,
            "xp":20 if awarded else 0,"self_reported":True}


@router.get("/calendar.ics")
async def calendar_export(plan_id:UUID,user:User=Depends(current_user),
                          conn:asyncpg.Connection=Depends(db_conn)):
    plan=await _owned_plan(conn,user,plan_id)
    content=build_ics(plan,90)
    return Response(content=content,media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition":'attachment; filename="almuallim-noor-90-days.ics"',
                             "Cache-Control":"no-store"})


@router.get("/sanctuary")
async def sanctuary(user:User=Depends(current_user),
                    conn:asyncpg.Connection=Depends(db_conn)):
    row=await conn.fetchrow(
        """SELECT lighting,theme,rain_enabled,audio_enabled FROM sanctuary_preferences
           WHERE user_id=$1""",user.id,
    )
    stats=await profile(user,conn)
    return {"settings":dict(row) if row else {
        "lighting":"auto","theme":"walnut","rain_enabled":False,"audio_enabled":False
    },"xp":stats["xp"],"coins":stats["coins"]}


class SanctuarySettings(BaseModel):
    lighting:Literal["auto","fajr","asr","isha"]="auto"
    theme:Literal["walnut","midnight","fajr_mist","andalusian"]="walnut"
    rain_enabled:bool=False
    audio_enabled:bool=False


@router.put("/sanctuary")
async def update_sanctuary(body:SanctuarySettings,user:User=Depends(current_user),
                           conn:asyncpg.Connection=Depends(db_conn)):
    entitlement=await resolve_entitlement(conn,user.id)
    if (body.theme!="walnut" or body.audio_enabled) and not entitlement.allows("premium_sanctuaries"):
        raise HTTPException(403,detail={"code":"upgrade_available",
            "message":"Premium sanctuary themes and soundscapes are optional Pro Annual features."})
    await conn.execute(
        """INSERT INTO sanctuary_preferences(
           user_id,lighting,theme,rain_enabled,audio_enabled)
           VALUES($1,$2,$3,$4,$5)
           ON CONFLICT(user_id) DO UPDATE SET lighting=EXCLUDED.lighting,
           theme=EXCLUDED.theme,rain_enabled=EXCLUDED.rain_enabled,
           audio_enabled=EXCLUDED.audio_enabled,updated_at=now()""",
        user.id,body.lighting,body.theme,body.rain_enabled,body.audio_enabled,
    )
    return {"saved":True,"settings":body.model_dump()}
