"""Read verified, per-user Stripe Sandbox subscription state from Supabase.

Billing data can only be written by the private Stripe webhook.
This module never trusts checkout query parameters as payment proof.
"""
from datetime import datetime, timezone
from supabase_auth import _table_request
import requests

PRICE_PLANS = {
    "price_1UecayRyfWQC5psUg8pXdLRq": "Pro Monthly",
    "price_1UeciwRyfWQC5psU1n56spbe": "Pro Annual",
    "price_1UecgVRyfWQC5psUPS3B8LWa": "Family Annual",
}

def get_verified_test_membership():
    """Return an eligible Sandbox plan, or None. No network exceptions leak."""
    try:
        rows = _table_request(
            "billing_subscriptions",
            params={
                "select": "stripe_price_id,status,current_period_end",
                "order": "updated_at.desc",
                "limit": "20",
            },
        ) or []
    except (requests.RequestException, RuntimeError, ValueError):
        return None
    now = datetime.now(timezone.utc)
    for row in rows:
        plan = PRICE_PLANS.get(row.get("stripe_price_id"))
        status = row.get("status")
        expiry = row.get("current_period_end")
        if not plan or status not in ("active", "trialing"):
            continue
        if expiry:
            try:
                if datetime.fromisoformat(expiry.replace("Z", "+00:00")) <= now:
                    continue
            except (ValueError, TypeError):
                continue
        # This is TEST status, not real-world financial entitlement.
        return plan
    return None
