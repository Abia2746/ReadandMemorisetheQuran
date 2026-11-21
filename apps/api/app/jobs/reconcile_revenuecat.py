"""Reconcile native RevenueCat receipts after transfers and provider changes.

Run under a monitored scheduled worker; only REST-authenticated subscribers
may grant Pro. The original sender and destination of a TRANSFER are both
queued by the verified webhook. Unknown IDs/products remain queued for review.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from uuid import UUID

import asyncpg
import httpx


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return date.astimezone(timezone.utc) if date.tzinfo else date.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


async def reconcile_one(
    conn: asyncpg.Connection, client: httpx.AsyncClient, app_user_id: str,
) -> bool:
    """Return True only when the account was safely reconciled."""
    try:
        user_id = UUID(app_user_id)
    except ValueError:
        return False  # Anonymous aliases need manual ownership verification.
    user = await conn.fetchrow(
        """SELECT id,revenuecat_app_user_id FROM users WHERE id=$1""", user_id,
    )
    if not user or (
        user["revenuecat_app_user_id"] is not None
        and user["revenuecat_app_user_id"] != app_user_id
    ):
        return False

    secret = os.environ.get("REVENUECAT_SECRET_API_KEY")
    if not secret:
        raise RuntimeError("REVENUECAT_SECRET_API_KEY is not configured")
    response = await client.get(
        f"https://api.revenuecat.com/v1/subscribers/{app_user_id}",
        headers={"Authorization": f"Bearer {secret}", "Accept": "application/json"},
        timeout=15,
    )
    response.raise_for_status()
    subscriber = response.json().get("subscriber")
    if not isinstance(subscriber, dict):
        return False
    subscriptions = subscriber.get("subscriptions") or {}
    if not isinstance(subscriptions, dict):
        return False
    now = datetime.now(timezone.utc)
    approved = []
    for product_id, entry in subscriptions.items():
        if not isinstance(entry, dict):
            return False
        if entry.get("is_sandbox", True):
            continue
        if entry.get("store") not in ("app_store", "play_store"):
            continue
        end = _parse_date(entry.get("expires_date"))
        if not end or end <= now or entry.get("refunded_at"):
            continue
        # Google Play base plan suffixes can differ between webhook and
        # REST representations; fail closed rather than guessing its tier.
        product = await conn.fetchrow(
            """SELECT tier::text FROM billing_price_catalog
               WHERE provider='revenuecat' AND enabled
                 AND provider_price_or_product_id=$1 LIMIT 1""", product_id,
        )
        if not product:
            return False
        start = _parse_date(entry.get("purchase_date"))
        trial = entry.get("period_type", "").lower() == "trial"
        approved.append((product_id, product["tier"], start, end, trial))

    async with conn.transaction():
        # The complete provider REST snapshot is authoritative for this
        # user. No other provider subscription or scholarship is touched.
        await conn.execute(
            """UPDATE subscriptions
               SET status='expired',current_period_end=least(
                   coalesce(current_period_end,now()),now()
               ),updated_at=now(),last_verified_at=now()
               WHERE user_id=$1 AND provider='revenuecat'
                 AND environment='production'""", user_id,
        )
        for product_id, tier, started, expires, trial in approved:
            receipt_key = f"rest:{app_user_id}:{product_id}"
            await conn.execute(
                """INSERT INTO subscriptions(
                     user_id,provider,provider_subscription_id,
                     product_id,tier,status,period_started_at,
                     current_period_end,trial_end,environment,
                     source_event_at,last_verified_at)
                   VALUES($1,'revenuecat',$2,$3,$4::am_tier,'active',
                          $5,$6,$7,'production',now(),now())
                   ON CONFLICT(provider,provider_subscription_id,environment)
                   DO UPDATE SET tier=EXCLUDED.tier,status='active',
                     period_started_at=EXCLUDED.period_started_at,
                     current_period_end=EXCLUDED.current_period_end,
                     trial_end=EXCLUDED.trial_end,
                     source_event_at=now(),last_verified_at=now(),
                     updated_at=now()
                   WHERE subscriptions.user_id=EXCLUDED.user_id""",
                user_id, receipt_key, product_id, tier, started,
                expires, expires if trial else None,
            )
        await conn.execute(
            """UPDATE users SET revenuecat_app_user_id=$2
               WHERE id=$1 AND revenuecat_app_user_id IS NULL""",
            user_id, app_user_id,
        )
        await conn.execute(
            """DELETE FROM billing_reconciliation_queue
               WHERE provider='revenuecat' AND external_user_id=$1""",
            app_user_id,
        )
    return True


async def run() -> dict:
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("Missing DATABASE_URL")
    if not os.environ.get("REVENUECAT_SECRET_API_KEY"):
        raise RuntimeError("Missing REVENUECAT_SECRET_API_KEY")
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=3)
    processed = 0
    unresolved = 0
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT external_user_id FROM billing_reconciliation_queue
                   WHERE provider='revenuecat'
                   ORDER BY created_at LIMIT 100"""
            )
            async with httpx.AsyncClient(follow_redirects=False) as client:
                for item in rows:
                    try:
                        ok = await reconcile_one(conn, client, item["external_user_id"])
                    except (httpx.HTTPError, asyncpg.PostgresError):
                        ok = False
                    if ok:
                        processed += 1
                    else:
                        unresolved += 1
        return {"reconciled": processed, "requires_review_or_retry": unresolved}
    finally:
        await pool.close()


if __name__ == "__main__":
    print(asyncio.run(run()))
