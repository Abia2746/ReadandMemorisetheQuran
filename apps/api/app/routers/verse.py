"""Metered Verse Studio APIs with shared read-through cache and free access.

No paid gate exists on the Mushaf/audio routes; these endpoints cover optional
AI study modules only.
"""
from __future__ import annotations

import os
from typing import Literal
from uuid import UUID

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.prompts.verse import PROMPT_VERSION
from app.routers.billing import current_user, db_conn
from app.services.billing import (
    User, consume_teacher_question, consume_verse_unlock,
    refund_teacher_question, refund_verse_unlock,
)
from app.services.verse_cache import read_through_verse
from app.services.verse_generation import (
    _gemini_json, canonical_verse, generate_drills,
    generate_tafsir, retrieved_tafsir,
)

router = APIRouter(prefix="/api", tags=["study"])


async def _verse_studio(
    request: Request, conn: asyncpg.Connection, user: User,
    surah: int, ayah: int, lang: str, kind: Literal["tafsir", "drills"]
):
    if lang != "en":
        # Preserve the specified English translation edition until a
        # trustworthy language-specific translation is configured.
        raise HTTPException(422, "This study language has not yet been configured")
    if not 1 <= surah <= 114 or not 1 <= ayah <= 286:
        raise HTTPException(422, "Invalid verse reference")
    allowed, charged = await consume_verse_unlock(conn, user, surah, ayah)
    if not allowed:
        raise HTTPException(403, detail={
            "code": "verse_limit_reached",
            "message": "You've completed your 3 free deep-study lessons today.",
            "upgrade": "pro_annual",
            "free_content_available": True,
        })
    try:
        async with httpx.AsyncClient(follow_redirects=False) as client:
            verse, words = await canonical_verse(client, surah, ayah, lang)
            sources = await retrieved_tafsir(client, surah, ayah)
            if not sources:
                raise HTTPException(503, "Classical tafsir sources are currently unavailable")
            async def generate():
                if kind == "tafsir":
                    return await generate_tafsir(client, verse, sources)
                return await generate_drills(client, verse, words, sources)
            # Content version changes when the source edition, translation,
            # prompt contract or AI model changes; published output stays reusable.
            version = f"{PROMPT_VERSION}:qf-v4:131:{os.environ.get('GEMINI_MODEL','unconfigured')}"
            return await read_through_verse(
                pool=request.app.state.pg, redis=request.app.state.redis,
                surah=surah, ayah=ayah, lang=lang,
                version=version, sources=sources,
                kind=kind, generate=generate,
            )
    except Exception:
        if charged:
            await refund_verse_unlock(conn, user, surah, ayah)
        raise


@router.get("/verse/{surah}/{ayah}/tafsir")
async def verse_tafsir(
    request: Request, surah: int, ayah: int, lang: str = "en",
    user: User = Depends(current_user),
    conn: asyncpg.Connection = Depends(db_conn),
):
    return await _verse_studio(request, conn, user, surah, ayah, lang, "tafsir")


@router.get("/verse/{surah}/{ayah}/study-drills")
async def verse_drills(
    request: Request, surah: int, ayah: int, lang: str = "en",
    user: User = Depends(current_user),
    conn: asyncpg.Connection = Depends(db_conn),
):
    return await _verse_studio(request, conn, user, surah, ayah, lang, "drills")


class TeacherQuestion(BaseModel):
    request_id: UUID
    question: str = Field(min_length=3, max_length=1200)
    language: Literal["en"] = "en"


@router.post("/teacher/questions")
async def teacher_question(
    body: TeacherQuestion, request: Request,
    user: User = Depends(current_user),
    conn: asyncpg.Connection = Depends(db_conn),
):
    # Anti-abuse capacity safeguard; not a daily usage paywall for Pro.
    key = f"teacher-burst:{user.id}"
    count = await request.app.state.redis.incr(key)
    if count == 1:
        await request.app.state.redis.expire(key, 60)
    if count > 15:
        raise HTTPException(429, "Please slow down and retry shortly")

    allowed = await consume_teacher_question(conn, user, body.request_id)
    if not allowed:
        raise HTTPException(403, detail={
            "code": "teacher_daily_limit_reached",
            "message": "You've used your five free AI teacher questions today.",
            "free_content_available": True,
        })
    # Only an exact reviewed FAQ lookup can be safely served at no model cost.
    topic = " ".join(body.question.lower().strip().split())
    reviewed = await conn.fetchrow(
        """SELECT answer_json FROM approved_faq_cache
           WHERE canonical_topic=$1 AND language='en'
             AND prompt_version=$2 AND review_status='reviewed'""",
        topic, PROMPT_VERSION,
    )
    if reviewed:
        return reviewed["answer_json"]
    try:
        async with httpx.AsyncClient() as client:
            answer = await _gemini_json(
                client,
                """You are a careful Qur'anic Arabic study assistant.
                Answer with educational explanations, not fatwas.
                Never fabricate Qur'an, hadith, Companion narrations,
                references, or claims of scholarly consensus.
                If uncertain, explain that a scholar should be consulted.
                Output JSON: { "answer": string, "source_notes": [] }.""",
                "User question: " + body.question,
            )
            if not isinstance(answer.get("answer"), str) or not answer["answer"].strip():
                raise ValueError("Incomplete teacher answer")
            return {"answer": answer["answer"], "source_notes": answer.get("source_notes", [])}
    except Exception:
        await refund_teacher_question(conn, user, body.request_id)
        raise HTTPException(503, "The teacher is temporarily unavailable; your credit was restored")
