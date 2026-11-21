"""Authenticated billing API: server-selected Stripe prices, access and scholarships.

RevenueCat native purchases happen via the official Capacitor SDK.
The native client must identify its user by the backend UUID; never put a
Stripe browser checkout inside an App Store IAP flow without current policy review.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID
from urllib.parse import urlparse

import asyncpg
import jwt
import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.billing import (
    User, consume_teacher_question, consume_verse_unlock, create_family_group,
    get_daily_usage, require_entitlement, resolve_entitlement,
)

router = APIRouter(prefix="/api/billing", tags=["billing"])
_jwks_client = None


async def db_conn(request: Request):
    async with request.app.state.pg.acquire() as conn:
        yield conn


async def current_user(
    authorization: Annotated[str | None, Header()] = None,
    conn: asyncpg.Connection = Depends(db_conn),
) -> User:
    """Require a verified OIDC JWT. Never accept arbitrary user IDs in headers."""
    global _jwks_client
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in to use your personal study account")
    token = authorization.removeprefix("Bearer ").strip()
    issuer = os.environ.get("OIDC_ISSUER")
    audience = os.environ.get("OIDC_AUDIENCE")
    jwks_url = os.environ.get("OIDC_JWKS_URL")
    if not all([issuer, audience, jwks_url]):
        raise HTTPException(503, "Authentication service is not configured")
    try:
        if _jwks_client is None:
            _jwks_client = jwt.PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300)
        signing_key = await asyncio.to_thread(_jwks_client.get_signing_key_from_jwt, token)
        claims = jwt.decode(
            token, signing_key.key, algorithms=["RS256"],
            audience=audience, issuer=issuer,
            options={"require": ["sub", "exp", "iat"]},
        )
    except (jwt.InvalidTokenError, jwt.PyJWKClientError, ValueError):
        raise HTTPException(401, "Session expired or invalid")
    subject = str(claims["sub"])
    # A provider-verified email is optional; do not collect additional demographics.
    email = claims.get("email") if claims.get("email_verified") is True else None
    row = await conn.fetchrow(
        """INSERT INTO users(auth_subject,email)
           VALUES ($1,$2)
           ON CONFLICT(auth_subject)
           DO UPDATE SET email=COALESCE(EXCLUDED.email,users.email)
           RETURNING id,quota_timezone_name""",
        subject, email,
    )
    return User(id=row["id"], quota_timezone_name=row["quota_timezone_name"])


@router.get("/me")
async def billing_me(
    user: User = Depends(current_user),
    conn: asyncpg.Connection = Depends(db_conn),
):
    ent = await resolve_entitlement(conn, user.id)
    return {
        "user_id": str(user.id),
        "tier": ent.tier,
        "access_via": ent.via,
        "features": sorted(ent.features),
        "expires_at": ent.expires_at.isoformat() if ent.expires_at else None,
        "daily_usage": await get_daily_usage(conn, user),
    }


@router.get("/prices")
async def prices(
    user: User = Depends(current_user),
    conn: asyncpg.Connection = Depends(db_conn),
):
    row = await conn.fetchrow("SELECT country_code FROM users WHERE id=$1", user.id)
    # Country is assigned by an approved server billing process; never trust
    # a client-selected currency as authority to grant regional discounts.
    country = row["country_code"] or "GB"
    rows = await conn.fetch(
        """SELECT tier::text, currency, amount_minor, trial_days
           FROM billing_price_catalog
           WHERE provider='stripe' AND enabled AND country_code=$1
           ORDER BY CASE tier WHEN 'pro_annual' THEN 0 WHEN 'pro_monthly'
                             THEN 1 ELSE 2 END""",
        country,
    )
    return {"country": country, "plans": [dict(item) for item in rows]}


class CheckoutRequest(BaseModel):
    tier: Literal["pro_monthly", "pro_annual", "family_annual"]
    # Idempotency key is bound server-side to user/tier; not a user ID.
    request_id: UUID


def _web_origin() -> str:
    origin = os.environ.get("PUBLIC_WEB_ORIGIN", "")
    parsed = urlparse(origin)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/"):
        raise HTTPException(503, "Secure web checkout origin is not configured")
    return origin.rstrip("/")


@router.post("/checkout")
async def start_checkout(
    params: CheckoutRequest,
    user: User = Depends(current_user),
    conn: asyncpg.Connection = Depends(db_conn),
):
    if not os.environ.get("STRIPE_SECRET_KEY"):
        raise HTTPException(503, "Web checkout not configured")
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    customer = await conn.fetchrow(
        "SELECT country_code,stripe_customer_id,email FROM users WHERE id=$1", user.id
    )
    region = customer["country_code"] or "GB"
    catalog = await conn.fetchrow(
        """SELECT provider_price_or_product_id,trial_days
           FROM billing_price_catalog
           WHERE provider='stripe' AND tier=$1::am_tier AND country_code=$2
             AND enabled LIMIT 1""", params.tier, region,
    )
    if not catalog:
        raise HTTPException(409, "Price is not available in your verified region")
    # Trial is limited to Pro Annual on the web; native trial eligibility is
    # determined by the relevant app store and RevenueCat offerings.
    past = await conn.fetchval(
        "SELECT 1 FROM subscriptions WHERE user_id=$1 LIMIT 1", user.id
    )
    trial = False
    if params.tier == "pro_annual" and int(catalog["trial_days"]) == 7 and not past:
        reserved = await conn.fetchval(
            """INSERT INTO trial_claims(
                 user_id,provider,status,reservation_expires_at)
               VALUES($1,'stripe','reserved',now()+interval '1 hour')
               ON CONFLICT(user_id)
               DO UPDATE SET provider='stripe',status='reserved',
                 reservation_expires_at=now()+interval '1 hour',
                 checkout_session_id=NULL
               WHERE trial_claims.status='reserved'
                 AND trial_claims.reservation_expires_at <= now()
               RETURNING user_id""", user.id,
        )
        trial = reserved is not None
    origin = _web_origin()
    sub_data: dict = {"metadata": {"al_muallim_user_id": str(user.id)}}
    if trial:
        sub_data["trial_period_days"] = 7
        sub_data["trial_settings"] = {"end_behavior": {"missing_payment_method": "cancel"}}

    checkout: dict = {
        "mode": "subscription",
        "line_items": [{"price": catalog["provider_price_or_product_id"], "quantity": 1}],
        "client_reference_id": str(user.id),
        "success_url": origin + "/account/billing?checkout=success",
        "cancel_url": origin + "/pricing?checkout=canceled",
        "metadata": {"al_muallim_user_id": str(user.id), "tier": params.tier},
        "subscription_data": sub_data,
        "billing_address_collection": "required",
        "allow_promotion_codes": False,
    }
    if customer["stripe_customer_id"]:
        checkout["customer"] = customer["stripe_customer_id"]
    elif customer["email"]:
        checkout["customer_email"] = customer["email"]

    try:
        session = await asyncio.to_thread(
            stripe.checkout.Session.create,
            **checkout, idempotency_key=f"alm:{user.id}:{params.tier}:{params.request_id}",
        )
    except stripe.error.StripeError:
        if trial:
            await conn.execute(
                """DELETE FROM trial_claims
                   WHERE user_id=$1 AND status='reserved' AND checkout_session_id IS NULL""",
                user.id,
            )
        raise HTTPException(503, "Secure checkout is temporarily unavailable")
    if trial:
        await conn.execute(
            """UPDATE trial_claims SET checkout_session_id=$2
               WHERE user_id=$1 AND status='reserved'""", user.id, session.id,
        )
    return {"checkout_url": session.url, "trial_available": trial}


class ScholarshipRequest(BaseModel):
    months: Literal[3, 6]
    note: str | None = Field(default=None, max_length=500)


@router.post("/scholarships/requests", status_code=202)
async def request_scholarship(
    body: ScholarshipRequest,
    user: User = Depends(current_user),
    conn: asyncpg.Connection = Depends(db_conn),
):
    existing = await conn.fetchval(
        """SELECT 1 FROM scholarships
           WHERE user_id=$1 AND request_status='pending'""", user.id,
    )
    if existing:
        return {"status": "pending", "message": "Your request is already being considered."}
    await conn.execute(
        """INSERT INTO scholarships(user_id,months_requested,request_note)
           VALUES($1,$2,$3)""", user.id, body.months, body.note,
    )
    return {
        "status": "pending",
        "message": "Your request was received. No financial evidence is required.",
    }


@router.post("/scholarships/gift-checkout")
async def gift_checkout(
    user: User = Depends(current_user),
    conn: asyncpg.Connection = Depends(db_conn),
):
    price_id = os.environ.get("STRIPE_GIFT_YEAR_GBP_PRICE_ID")
    if not price_id or not os.environ.get("STRIPE_SECRET_KEY"):
        raise HTTPException(503, "Student sponsorship checkout is not configured")
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    origin = _web_origin()
    try:
        session = await asyncio.to_thread(
            stripe.checkout.Session.create,
            mode="payment",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=origin + "/sponsor?gift=received",
            cancel_url=origin + "/sponsor?gift=canceled",
            client_reference_id=str(user.id),
            metadata={"kind": "sponsor_a_student"},
            billing_address_collection="required",
        )
    except stripe.error.StripeError:
        raise HTTPException(503, "Gift checkout is temporarily unavailable")
    await conn.execute(
        """INSERT INTO scholarship_gifts(
            checkout_session_id,donor_user_id,currency,amount_minor)
            VALUES($1,$2,'GBP',3999)
            ON CONFLICT(checkout_session_id) DO NOTHING""",
        session.id, user.id,
    )
    return {"checkout_url": session.url}


@router.post("/family/create")
@require_entitlement("family_members")
async def family_create(
    user: User = Depends(current_user),
    conn: asyncpg.Connection = Depends(db_conn),
):
    gid = await create_family_group(conn, user)
    return {"group_id": str(gid), "member_cap": 5}


@router.post("/family/invite")
@require_entitlement("family_members")
async def family_invite(
    user: User = Depends(current_user),
    conn: asyncpg.Connection = Depends(db_conn),
):
    group = await conn.fetchval(
        """SELECT id FROM family_groups
           WHERE owner_user_id=$1 AND dissolved_at IS NULL""", user.id,
    )
    if group is None:
        group = await create_family_group(conn, user)
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    await conn.execute(
        """INSERT INTO family_invites(family_group_id,token_hash,expires_at)
           VALUES ($1,$2,now()+interval '48 hours')""", group, digest,
    )
    return {
        "invite_url": _web_origin() + "/family/join?code=" + token,
        "expires_in_hours": 48,
    }


class AcceptInvite(BaseModel):
    code: str = Field(min_length=25, max_length=128)


@router.post("/family/accept")
async def family_accept(
    body: AcceptInvite,
    user: User = Depends(current_user),
    conn: asyncpg.Connection = Depends(db_conn),
):
    digest = hashlib.sha256(body.code.encode("utf-8")).hexdigest()
    async with conn.transaction():
        invite = await conn.fetchrow(
            """SELECT family_group_id FROM family_invites
               WHERE token_hash=$1 AND accepted_at IS NULL
                 AND expires_at > now() FOR UPDATE""", digest,
        )
        if not invite:
            raise HTTPException(410, "This invitation has expired or was used")
        group_id = invite["family_group_id"]
        owner = await conn.fetchval(
            "SELECT owner_user_id FROM family_groups WHERE id=$1", group_id,
        )
        owner_ent = await resolve_entitlement(conn, owner)
        if owner_ent.tier != "family_annual":
            raise HTTPException(409, "The family plan is not active")
        # Capacity check is enforced transactionally by the SQL trigger.
        try:
            await conn.execute(
                """INSERT INTO family_memberships(family_group_id,user_id,role)
                   VALUES($1,$2,'member')""", group_id, user.id,
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(409, "You already belong to a family group")
        await conn.execute(
            """UPDATE family_invites SET accepted_by=$2,accepted_at=now()
               WHERE token_hash=$1""", digest, user.id,
        )
    return {"status": "joined", "independent_profile": True}
