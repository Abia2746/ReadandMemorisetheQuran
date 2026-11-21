"""Server-authoritative entitlements, quota accounting, and family membership.

No frontend value can grant paid access. The two free AI quotas are tracked
atomically in the user's recorded IANA timezone; timezone changes are not
automatically accepted for the quota clock.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Literal, TypeVar
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import asyncpg
from fastapi import HTTPException

Tier = Literal["free", "pro_monthly", "pro_annual", "family_annual"]
FREE_FEATURES = frozenset({
    "mushaf", "translations", "qari_audio", "basic_follow_along",
    "one_hifdh_plan", "calendar_export", "basic_prayer_room",
})
PRO_FEATURES = FREE_FEATURES | frozenset({
    "live_precision", "phrase_loop", "difficult_words",
    "memorise_with_meaning", "unlimited_verse_studio", "unlimited_teacher",
})
ANNUAL_FEATURES = PRO_FEATURES | frozenset({
    "premium_sanctuaries", "rain_ambience"
})
FAMILY_FEATURES = ANNUAL_FEATURES | frozenset({"family_members"})
FEATURES = {
    "free": FREE_FEATURES,
    "pro_monthly": PRO_FEATURES,
    "pro_annual": ANNUAL_FEATURES,
    "family_annual": FAMILY_FEATURES,
}
TIER_RANK = {"free": 0, "pro_monthly": 1, "pro_annual": 2, "family_annual": 3}
VERSE_LIMIT = 3
TEACHER_LIMIT = 5


@dataclass(frozen=True)
class User:
    id: UUID
    quota_timezone_name: str


@dataclass(frozen=True)
class Entitlement:
    tier: Tier
    via: str
    features: frozenset[str]
    expires_at: datetime | None = None

    def allows(self, feature: str) -> bool:
        return feature in self.features


def _safe_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def local_day_for_user(user: User, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    return now.astimezone(_safe_timezone(user.quota_timezone_name)).date()


async def resolve_entitlement(conn: asyncpg.Connection, user_id: UUID) -> Entitlement:
    """Merge all eligible billing/grant channels; never let a cancellation
    for one provider remove a separate valid provider's subscription.
    """
    rows = await conn.fetch(
        """
        SELECT tier::text AS tier, provider::text AS via, current_period_end AS expiry
          FROM subscriptions
         WHERE user_id=$1 AND environment='production'
           AND status IN ('active','trialing')
           AND coalesce(current_period_end,trial_end) > now()
        UNION ALL
        SELECT 'pro_annual' AS tier, 'scholarship' AS via, valid_until AS expiry
          FROM scholarships
         WHERE user_id=$1 AND request_status='approved'
           AND granted_at <= now() AND valid_until > now()
        UNION ALL
        SELECT 'family_annual' AS tier, 'family_membership' AS via,
               s.current_period_end AS expiry
          FROM family_memberships fm
          JOIN family_groups fg ON fg.id=fm.family_group_id
          JOIN subscriptions s ON s.user_id=fg.owner_user_id
         WHERE fm.user_id=$1 AND fg.dissolved_at IS NULL
           AND s.tier='family_annual' AND s.environment='production'
           AND s.status IN ('active','trialing')
           AND coalesce(s.current_period_end,s.trial_end) > now()
        """,
        user_id,
    )
    if not rows:
        return Entitlement("free", "free", FREE_FEATURES)
    best = max(rows, key=lambda r: TIER_RANK[r["tier"]])
    tier: Tier = best["tier"]
    return Entitlement(tier, best["via"], FEATURES[tier], best["expiry"])


def require_entitlement(feature: str):
    """Decorator for routes receiving injected keyword arguments 'user' and 'conn'.

    Example:
      @router.get("/premium")
      @require_entitlement("live_precision")
      async def premium(user: Annotated[User,Depends(current_user)],
                        conn: Annotated[asyncpg.Connection,Depends(db_conn)]): ...
    Keep FastAPI's route decorator OUTERMOST.
    """
    if feature not in FAMILY_FEATURES:
        raise ValueError("Unknown entitlement feature")

    def decorate(handler: Callable):
        @wraps(handler)
        async def wrapped(*args, **kwargs):
            user = kwargs.get("user")
            conn = kwargs.get("conn")
            if not isinstance(user, User) or conn is None:
                raise RuntimeError("Protected route requires injected user and conn")
            active = await resolve_entitlement(conn, user.id)
            if not active.allows(feature):
                raise HTTPException(403, detail={
                    "code": "upgrade_available",
                    "feature": feature,
                    "message": "This optional feature is part of Al-Mu'allim Pro.",
                })
            return await handler(*args, **kwargs)
        return wrapped
    return decorate


async def get_daily_usage(conn: asyncpg.Connection, user: User) -> dict[str, Any]:
    local_day = local_day_for_user(user)
    row = await conn.fetchrow(
        "SELECT verse_unlocks_used,qna_used FROM daily_ai_quotas WHERE user_id=$1 AND local_day=$2",
        user.id, local_day,
    )
    return {
        "date": local_day.isoformat(),
        "timezone": user.quota_timezone_name,
        "verse_studio": {"used": int(row["verse_unlocks_used"]) if row else 0, "limit": VERSE_LIMIT},
        "teacher_qna": {"used": int(row["qna_used"]) if row else 0, "limit": TEACHER_LIMIT},
    }


async def _locked_quota_row(conn: asyncpg.Connection, user: User, day):
    await conn.execute(
        """INSERT INTO daily_ai_quotas(user_id,local_day,timezone_name)
           VALUES($1,$2,$3) ON CONFLICT (user_id,local_day) DO NOTHING""",
        user.id, day, user.quota_timezone_name,
    )
    return await conn.fetchrow(
        "SELECT * FROM daily_ai_quotas WHERE user_id=$1 AND local_day=$2 FOR UPDATE",
        user.id, day,
    )


async def consume_verse_unlock(
    conn: asyncpg.Connection, user: User, surah: int, ayah: int,
) -> tuple[bool, bool]:
    """Return (allowed, newly_charged) for a distinct free lesson.
    Re-opening an already-unlocked verse is free for the local day.
    """
    if not (1 <= surah <= 114 and 1 <= ayah <= 286):
        raise HTTPException(422, "Invalid Qur'an verse")
    entitlement = await resolve_entitlement(conn, user.id)
    if entitlement.allows("unlimited_verse_studio"):
        return True, False
    day = local_day_for_user(user)
    async with conn.transaction():
        row = await _locked_quota_row(conn, user, day)
        already = await conn.fetchval(
            """SELECT 1 FROM verse_daily_unlocks
               WHERE user_id=$1 AND local_day=$2 AND surah=$3 AND ayah=$4""",
            user.id, day, surah, ayah,
        )
        if already:
            return True, False
        if row["verse_unlocks_used"] >= VERSE_LIMIT:
            return False, False
        await conn.execute(
            """INSERT INTO verse_daily_unlocks(user_id,local_day,surah,ayah)
               VALUES ($1,$2,$3,$4)""", user.id, day, surah, ayah,
        )
        await conn.execute(
            """UPDATE daily_ai_quotas
               SET verse_unlocks_used=verse_unlocks_used+1,updated_at=now()
               WHERE user_id=$1 AND local_day=$2""", user.id, day,
        )
        return True, True


async def consume_teacher_question(
    conn: asyncpg.Connection, user: User, request_id: UUID,
) -> bool:
    """Concurrency-safe and retry-idempotent, keyed by a server-checked UUID.

    Set the same request_id for a retry of the same teacher request. A failed
    model invocation can be refunded using refund_teacher_question().
    """
    entitlement = await resolve_entitlement(conn, user.id)
    paid = entitlement.allows("unlimited_teacher")
    day = local_day_for_user(user)
    async with conn.transaction():
        prior = await conn.fetchrow(
            "SELECT user_id,charged FROM ai_usage_events WHERE request_id=$1 FOR UPDATE",
            request_id,
        )
        if prior:
            if prior["user_id"] != user.id:
                raise HTTPException(409, "Idempotency key belongs to another user")
            return True
        if not paid:
            row = await _locked_quota_row(conn, user, day)
            if row["qna_used"] >= TEACHER_LIMIT:
                return False
            await conn.execute(
                """UPDATE daily_ai_quotas
                   SET qna_used=qna_used+1,updated_at=now()
                   WHERE user_id=$1 AND local_day=$2""", user.id, day,
            )
        await conn.execute(
            """INSERT INTO ai_usage_events(request_id,user_id,operation,charged)
               VALUES ($1,$2,'teacher_qna',$3)""", request_id, user.id, not paid,
        )
        return True


async def refund_teacher_question(
    conn: asyncpg.Connection, user: User, request_id: UUID,
) -> None:
    """Compensate an unsuccessful generation without penalising users."""
    async with conn.transaction():
        row = await conn.fetchrow(
            """SELECT request_id,charged,created_at
               FROM ai_usage_events WHERE request_id=$1 AND user_id=$2
               FOR UPDATE""",
            request_id, user.id,
        )
        if not row:
            return
        if row["charged"]:
            day = row["created_at"].astimezone(_safe_timezone(user.quota_timezone_name)).date()
            await conn.execute(
                """UPDATE daily_ai_quotas
                   SET qna_used=greatest(0,qna_used-1), updated_at=now()
                   WHERE user_id=$1 AND local_day=$2""", user.id, day,
            )
        await conn.execute(
            "DELETE FROM ai_usage_events WHERE request_id=$1 AND user_id=$2",
            request_id, user.id,
        )


async def create_family_group(conn: asyncpg.Connection, owner: User) -> UUID:
    entitlement = await resolve_entitlement(conn, owner.id)
    if entitlement.tier != "family_annual":
        raise HTTPException(403, "An active Family subscription is required")
    async with conn.transaction():
        gid = await conn.fetchval(
            """INSERT INTO family_groups(owner_user_id) VALUES ($1)
               ON CONFLICT(owner_user_id)
               DO UPDATE SET dissolved_at=NULL RETURNING id""", owner.id,
        )
        await conn.execute(
            """INSERT INTO family_memberships(family_group_id,user_id,role)
               VALUES ($1,$2,'owner') ON CONFLICT(user_id) DO NOTHING""",
            gid, owner.id,
        )
        return gid


async def refund_verse_unlock(
    conn: asyncpg.Connection, user: User, surah: int, ayah: int,
) -> None:
    """Do not spend a free lesson if the canonical source or AI request failed.

    This is safe only when invoked for a failed lesson within its local day.
    """
    day = local_day_for_user(user)
    async with conn.transaction():
        await _locked_quota_row(conn, user, day)
        deleted = await conn.fetchval(
            """DELETE FROM verse_daily_unlocks
               WHERE user_id=$1 AND local_day=$2 AND surah=$3 AND ayah=$4
               RETURNING 1""", user.id, day, surah, ayah,
        )
        if deleted:
            await conn.execute(
                """UPDATE daily_ai_quotas
                   SET verse_unlocks_used=greatest(0,verse_unlocks_used-1),
                       updated_at=now()
                   WHERE user_id=$1 AND local_day=$2""", user.id, day,
            )
