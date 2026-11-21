"""Shared read-through Verse Studio cache: Redis single-flight + PostgreSQL JSONB.

For exact versions and vetted source data, an approved cache hit incurs no
new language-model inference. It still incurs database, bandwidth and hosting
costs. Never substitute 'cached' for 'scholar-verified'.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any, Awaitable, Callable, Literal

import asyncpg
from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import LockError

from app.schemas.verse import VerseStudyDrillsResponse, VerseTafsirResponse

CacheKind = Literal["tafsir", "drills"]


def source_digest(sources: list[dict[str, Any]]) -> str:
    stable = [
        {
            "source_id": s.get("source_id"),
            "text": s.get("text"),
            "edition_verified": s.get("edition_verified", False),
            "url": s.get("url"),
        }
        for s in sources
    ]
    return hashlib.sha256(
        json.dumps(stable, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


async def _cached_record(
    conn: asyncpg.Connection,
    surah: int,
    ayah: int,
    lang: str,
    version: str,
    digest: str,
    kind: CacheKind,
) -> dict | None:
    col = "tafsir_json" if kind == "tafsir" else "drills_json"
    # col is hardcoded from a checked enum, not user-supplied SQL.
    row = await conn.fetchrow(
        f"""SELECT {col} AS body
            FROM verse_studio_cache
            WHERE surah=$1 AND ayah=$2 AND language=$3
              AND content_version=$4 AND source_digest=$5
              AND validation_status IN ('automated_pass','scholar_reviewed')""",
        surah, ayah, lang, version, digest,
    )
    if row and row["body"] is not None:
        body = row["body"]
        return json.loads(body) if isinstance(body, str) else dict(body)
    return None


async def read_through_verse(
    *,
    pool: asyncpg.Pool,
    redis: Redis,
    surah: int,
    ayah: int,
    lang: str,
    version: str,
    sources: list[dict[str, Any]],
    kind: CacheKind,
    generate: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    if not (1 <= surah <= 114 and 1 <= ayah <= 286):
        raise ValueError("Invalid verse reference")
    if kind not in ("tafsir", "drills"):
        raise ValueError("Invalid cache kind")
    if not 1 <= len(lang) <= 12 or not lang.replace("-", "").isalpha():
        raise ValueError("Invalid language")
    digest = source_digest(sources)
    async with pool.acquire() as conn:
        hit = await _cached_record(conn, surah, ayah, lang, version, digest, kind)
    if hit is not None:
        return hit

    lock_key = f"verse-cache:{surah}:{ayah}:{lang}:{version}:{digest}:{kind}"
    # Cache writes are single-flight; do not hold a PostgreSQL transaction
    # open while awaiting an external AI provider.
    lock = redis.lock(lock_key, timeout=180, blocking_timeout=2)
    try:
        async with lock:
            async with pool.acquire() as conn:
                hit = await _cached_record(conn, surah, ayah, lang, version, digest, kind)
            if hit is not None:
                return hit
            raw = await generate()
            model = (VerseTafsirResponse if kind == "tafsir"
                     else VerseStudyDrillsResponse).model_validate(raw)
            if model.completion != "complete":
                # Partial material is returned with clear status but NOT
                # distributed worldwide as a complete lesson.
                return model.model_dump(mode="json")
            body = model.model_dump(mode="json")
            field = "tafsir_json" if kind == "tafsir" else "drills_json"
            async with pool.acquire() as conn:
                await conn.execute(
                    f"""INSERT INTO verse_studio_cache(
                          surah,ayah,language,content_version,source_digest,
                          {field},verified_sources,validation_status,generated_at
                        )
                        VALUES($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,'automated_pass',now())
                        ON CONFLICT(surah,ayah,language,content_version,source_digest)
                        DO UPDATE SET {field}=EXCLUDED.{field},
                           verified_sources=EXCLUDED.verified_sources,
                           validation_status='automated_pass', updated_at=now()
                        WHERE verse_studio_cache.validation_status <> 'scholar_reviewed'""",
                    surah, ayah, lang, version, digest,
                    json.dumps(body, ensure_ascii=False),
                    json.dumps(sources, ensure_ascii=False),
                )
            return body
    except LockError:
        # Another request is generating the content; return the existing
        # validated result if it becomes available rather than stampeding AI.
        for _ in range(10):
            await asyncio.sleep(0.2)
            async with pool.acquire() as conn:
                hit = await _cached_record(conn, surah, ayah, lang, version, digest, kind)
            if hit is not None:
                return hit
        raise RuntimeError("Verse study generation is currently in progress")
