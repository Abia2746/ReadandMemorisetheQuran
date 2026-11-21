"""Signed Stripe and RevenueCat webhooks with deduplication and safe entitlements.

Set STRIPE_WEBHOOK_SECRET and REVENUECAT_WEBHOOK_SIGNING_SECRET in the server
environment. Neither provider's raw client payload is trusted to grant access
until its signature is verified. Never store card numbers or payment secrets.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import asyncpg
import stripe
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
STRIPE_TYPES = frozenset({
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
})


def _datetime(seconds: int | float | None):
    if not seconds:
        return None
    return datetime.fromtimestamp(float(seconds), tz=timezone.utc)


def _signature_rc(body: bytes, header: str | None) -> bool:
    secret = os.environ.get("REVENUECAT_WEBHOOK_SIGNING_SECRET", "")
    if not secret or not header:
        return False
    try:
        pairs = dict(item.strip().split("=", 1) for item in header.split(","))
        timestamp = int(pairs["t"])
        signature = pairs["v1"]
        if abs(time.time() - timestamp) > 300:
            return False
        expected = hmac.new(
            secret.encode(), str(timestamp).encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except (ValueError, KeyError, TypeError):
        return False


async def _first_event(
    conn: asyncpg.Connection,
    provider: str,
    event_id: str,
    event_type: str,
    event_at: datetime | None,
) -> bool:
    result = await conn.fetchval(
        """INSERT INTO billing_webhook_events(provider,event_id,event_type,event_at)
           VALUES($1::am_provider,$2,$3,$4)
           ON CONFLICT(provider,event_id) DO NOTHING
           RETURNING event_id""",
        provider, event_id, event_type, event_at,
    )
    return result is not None


def _get_field(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def _stripe_sub_period(sub: Any):
    """Stripe Basil API stores the billing period on subscription items."""
    items = _get_field(_get_field(sub, "items", {}), "data", [])
    first = items[0] if items else {}
    end = _get_field(first, "current_period_end") or _get_field(sub, "current_period_end")
    start = _get_field(first, "current_period_start") or _get_field(sub, "current_period_start")
    return _datetime(start), _datetime(end)


async def _sync_stripe_subscription(
    conn: asyncpg.Connection,
    sub_id: str,
    event_at: datetime,
):
    if not sub_id or not sub_id.startswith("sub_"):
        return
    if not os.environ.get("STRIPE_SECRET_KEY"):
        raise RuntimeError("Stripe secret unavailable")
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    # Latest authoritative state prevents delayed events from undoing renewals.
    subscription = await asyncio.to_thread(stripe.Subscription.retrieve, sub_id)
    metadata = _get_field(subscription, "metadata", {})
    external_id = _get_field(metadata, "al_muallim_user_id", "")
    try:
        user_id = UUID(str(external_id))
    except (ValueError, TypeError):
        return
    owner = await conn.fetchrow("SELECT id FROM users WHERE id=$1", user_id)
    if not owner:
        return
    items = _get_field(_get_field(subscription, "items", {}), "data", [])
    if len(items) != 1:
        return  # Only one approved subscription product at a time.
    price_id = _get_field(_get_field(items[0], "price", {}), "id")
    catalog = await conn.fetchrow(
        """SELECT tier::text AS tier FROM billing_price_catalog
           WHERE provider='stripe' AND provider_price_or_product_id=$1
             AND enabled LIMIT 1""", price_id,
    )
    if not catalog:
        await conn.execute(
            """INSERT INTO billing_reconciliation_queue(provider,external_user_id,reason)
               VALUES('stripe',$1,'Unknown subscription price')
               ON CONFLICT(provider,external_user_id)
               DO UPDATE SET reason=EXCLUDED.reason,created_at=now()""",
            str(user_id),
        )
        return
    start, end = _stripe_sub_period(subscription)
    trial_end = _datetime(_get_field(subscription, "trial_end"))
    status = str(_get_field(subscription, "status", "pending"))
    allowed_statuses = {
        "trialing", "active", "past_due", "paused", "canceled",
        "incomplete", "incomplete_expired", "unpaid",
    }
    status = (status if status in allowed_statuses else "pending")
    if status in {"incomplete", "incomplete_expired"}:
        status = "pending"
    mode = "production" if _get_field(subscription, "livemode", False) else "sandbox"
    # No positive entitlement may exist without a provider-authenticated end.
    if status in {"trialing", "active"} and not (end or trial_end):
        status = "pending"
    await conn.execute(
        """INSERT INTO subscriptions(
             user_id,provider,provider_subscription_id,product_id,tier,status,
             period_started_at,current_period_end,trial_end,cancel_at_period_end,
             source_event_at,environment,last_verified_at
           )
           VALUES($1,'stripe',$2,$3,$4::am_tier,$5,$6,$7,$8,$9,$10,$11,now())
           ON CONFLICT(provider,provider_subscription_id,environment)
           DO UPDATE SET tier=EXCLUDED.tier,status=EXCLUDED.status,
             product_id=EXCLUDED.product_id,current_period_end=EXCLUDED.current_period_end,
             period_started_at=EXCLUDED.period_started_at,trial_end=EXCLUDED.trial_end,
             cancel_at_period_end=EXCLUDED.cancel_at_period_end,
             source_event_at=EXCLUDED.source_event_at,last_verified_at=now(),updated_at=now()
           WHERE subscriptions.user_id=EXCLUDED.user_id
             AND (subscriptions.source_event_at IS NULL OR
                  subscriptions.source_event_at <= EXCLUDED.source_event_at)""",
        user_id, sub_id, price_id, catalog["tier"], status, start, end, trial_end,
        bool(_get_field(subscription, "cancel_at_period_end", False)), event_at, mode,
    )
    if mode == "production" and status == "trialing":
        await conn.execute(
            """INSERT INTO trial_claims(
                   user_id,provider,status,reservation_expires_at)
               VALUES ($1,'stripe','redeemed',NULL)
               ON CONFLICT(user_id) DO UPDATE
               SET status='redeemed',reservation_expires_at=NULL
               WHERE trial_claims.provider='stripe'""", user_id,
        )
    customer_id = _get_field(subscription, "customer")
    if isinstance(customer_id, str) and customer_id.startswith("cus_"):
        await conn.execute(
            """UPDATE users SET stripe_customer_id=COALESCE(stripe_customer_id,$2)
               WHERE id=$1 AND (stripe_customer_id IS NULL OR stripe_customer_id=$2)""",
            user_id, customer_id,
        )


def _session_sub_id(obj) -> str | None:
    sub = _get_field(obj, "subscription")
    if not sub:
        parent = _get_field(obj, "parent", {})
        sub = _get_field(_get_field(parent, "subscription_details", {}), "subscription")
    return _get_field(sub, "id") if sub and not isinstance(sub, str) else sub


@router.post("/stripe", status_code=200)
async def stripe_webhook(request: Request):
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(503, "Stripe webhook not configured")
    raw = await request.body()
    signature = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(raw, signature, secret, tolerance=300)
    except (ValueError, stripe.error.SignatureVerificationError, TypeError):
        raise HTTPException(400, "Invalid Stripe signature")
    etype = event["type"]
    if etype not in STRIPE_TYPES:
        return {"received": True, "ignored": True}
    obj = event["data"]["object"]
    event_at = _datetime(event.get("created")) or datetime.now(timezone.utc)
    try:
        async with request.app.state.pg.acquire() as conn:
            async with conn.transaction():
                if not await _first_event(conn, "stripe", event["id"], etype, event_at):
                    return {"received": True, "duplicate": True}
                if etype in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
                    if obj.get("mode") == "payment" and obj.get("payment_status") == "paid":
                        checkout_id = obj.get("id")
                        amount = obj.get("amount_total")
                        currency = str(obj.get("currency", "")).upper()
                        # Only a previously server-created £39.99 sponsorship can be credited.
                        if currency == "GBP" and amount == 3999:
                            await conn.execute(
                                """UPDATE scholarship_gifts
                                   SET payment_status='paid',received_at=now()
                                   WHERE checkout_session_id=$1
                                     AND currency='GBP' AND amount_minor=3999
                                     AND payment_status='pending'""", checkout_id,
                            )
                    elif obj.get("mode") == "subscription":
                        sub_id = _session_sub_id(obj)
                        if sub_id:
                            await _sync_stripe_subscription(conn, sub_id, event_at)
                else:
                    sub_id = (
                        obj.get("id") if etype.startswith("customer.subscription.")
                        else _session_sub_id(obj)
                    )
                    if sub_id:
                        await _sync_stripe_subscription(conn, sub_id, event_at)
        return {"received": True}
    except stripe.error.StripeError:
        # Provider outage: return non-2xx to request a signed retry.
        raise HTTPException(503, "Unable to reconcile Stripe subscription")


RC_EVENTS = frozenset({
    "INITIAL_PURCHASE", "RENEWAL", "PRODUCT_CHANGE", "UNCANCELLATION",
    "CANCELLATION", "EXPIRATION", "BILLING_ISSUE", "SUBSCRIPTION_EXTENDED",
    "REFUND", "REFUND_REVERSED", "TRANSFER", "SUBSCRIPTION_PAUSED",
    "TEMPORARY_ENTITLEMENT_GRANT", "PURCHASE_REDEEMED",
})


@router.post("/revenuecat", status_code=200)
async def revenuecat_webhook(request: Request):
    raw = await request.body()
    if not _signature_rc(raw, request.headers.get("X-RevenueCat-Webhook-Signature")):
        raise HTTPException(401, "Invalid RevenueCat signature")
    required_auth = os.environ.get("REVENUECAT_WEBHOOK_AUTHORIZATION")
    if required_auth and not hmac.compare_digest(
        request.headers.get("Authorization", ""), required_auth
    ):
        raise HTTPException(401, "Invalid RevenueCat webhook authorization")
    try:
        payload = json.loads(raw)
        event = payload["event"]
        event_id = str(event["id"])
        event_type = str(event["type"])
        event_at = _datetime(int(event["event_timestamp_ms"]) / 1000)
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(422, "Invalid RevenueCat event")
    if event_type not in RC_EVENTS:
        return {"received": True, "ignored": True}

    # Keep Stripe web checkout under Stripe: two billing providers must not
    # double-grant the same purchase.
    native_store = event.get("store") in {"APP_STORE", "PLAY_STORE"}
    prod = event.get("environment") == "PRODUCTION"
    async with request.app.state.pg.acquire() as conn:
        async with conn.transaction():
            if not await _first_event(conn, "revenuecat", event_id, event_type, event_at):
                return {"received": True, "duplicate": True}
            app_user_id = str(event.get("app_user_id", ""))
            if event_type == "TRANSFER":
                # Transfer involves former + current owners; NEVER assign a
                # store receipt to a guessed account. Reconcile via RC REST API.
                await conn.execute(
                    """INSERT INTO billing_reconciliation_queue(provider,external_user_id,reason)
                       VALUES('revenuecat',$1,'Purchase transfer requires subscriber verification')
                       ON CONFLICT(provider,external_user_id)
                       DO UPDATE SET reason=EXCLUDED.reason,created_at=now()""",
                    app_user_id,
                )
                return {"received": True, "reconciliation_required": True}
            if not native_store or not prod:
                return {"received": True, "ignored": True}
            try:
                canonical_user_id = UUID(app_user_id)
            except (ValueError, TypeError):
                return {"received": True, "unlinked": True}
            user = await conn.fetchrow(
                """SELECT id FROM users WHERE id=$1 AND
                   (revenuecat_app_user_id=$2 OR revenuecat_app_user_id IS NULL)""",
                canonical_user_id, app_user_id,
            )
            if not user:
                return {"received": True, "unlinked": True}
            external_sub = event.get("original_transaction_id") or event.get("transaction_id")
            product_id = str(event.get("product_id") or "")
            if not external_sub or not product_id:
                return {"received": True, "ignored": True}
            product = await conn.fetchrow(
                """SELECT tier::text AS tier FROM billing_price_catalog
                   WHERE provider='revenuecat' AND provider_price_or_product_id=$1
                     AND enabled LIMIT 1""",
                product_id,
            )
            if not product:
                return {"received": True, "unmapped_product": True}
            end = _datetime((event.get("expiration_at_ms") or 0)/1000)
            start = _datetime((event.get("purchased_at_ms") or 0)/1000)
            status = "active"
            cancel_at_end = event_type == "CANCELLATION"
            if event_type in {"EXPIRATION", "REFUND"}:
                status = "expired"
            elif event_type == "SUBSCRIPTION_PAUSED":
                status = "paused"
            elif event_type == "BILLING_ISSUE":
                # Expiration is distinct: keep access until valid paid expiry.
                status = "active"
            elif event_type == "TEMPORARY_ENTITLEMENT_GRANT":
                # Temporary entitlement grants should be independently queried;
                # not blindly converted to a full paid subscription.
                return {"received": True, "reconciliation_required": True}
            if status == "active" and (end is None or end <= datetime.now(timezone.utc)):
                status = "expired"
            await conn.execute(
                """INSERT INTO subscriptions(
                    user_id,provider,provider_subscription_id,product_id,tier,
                    status,period_started_at,current_period_end,
                    cancel_at_period_end,source_event_at,environment,last_verified_at)
                   VALUES($1,'revenuecat',$2,$3,$4::am_tier,$5,$6,$7,$8,$9,'production',now())
                   ON CONFLICT(provider,provider_subscription_id,environment)
                   DO UPDATE SET status=EXCLUDED.status,
                     tier=EXCLUDED.tier,product_id=EXCLUDED.product_id,
                     current_period_end=EXCLUDED.current_period_end,
                     period_started_at=EXCLUDED.period_started_at,
                     cancel_at_period_end=EXCLUDED.cancel_at_period_end,
                     source_event_at=EXCLUDED.source_event_at,
                     last_verified_at=now(),updated_at=now()
                   WHERE subscriptions.user_id=EXCLUDED.user_id
                     AND (subscriptions.source_event_at IS NULL OR
                          subscriptions.source_event_at <= EXCLUDED.source_event_at)""",
                canonical_user_id, str(external_sub), product_id,
                product["tier"], status, start, end, cancel_at_end, event_at,
            )
            if event.get("period_type") == "TRIAL" and status == "active":
                await conn.execute(
                    """INSERT INTO trial_claims(
                         user_id,provider,status,reservation_expires_at)
                       VALUES($1,'revenuecat','redeemed',NULL)
                       ON CONFLICT(user_id) DO UPDATE
                       SET status='redeemed',reservation_expires_at=NULL
                       WHERE trial_claims.provider='revenuecat'""",
                    canonical_user_id,
                )
            await conn.execute(
                """UPDATE users SET revenuecat_app_user_id=$2
                   WHERE id=$1 AND revenuecat_app_user_id IS NULL""",
                canonical_user_id, app_user_id,
            )
    return {"received": True}
