"""Stripe TEST-MODE hosted Checkout for Al-Mu'allim.

Checkout is intentionally disabled for live keys and does not grant entitlements.
A verified webhook plus persistent authentication must be deployed before launch.
Never put Stripe secret keys in this repository.
"""
import streamlit as st
import requests

PLAN_PRICE_KEYS = {
    "Pro Monthly": "STRIPE_PRICE_PRO_MONTHLY",
    "Pro Annual": "STRIPE_PRICE_PRO_ANNUAL",
    "Family Annual": "STRIPE_PRICE_FAMILY_ANNUAL",
}

# Public sandbox Price IDs; secret key remains in Streamlit secrets.
SANDBOX_PRICE_IDS = {
    "Pro Monthly": "price_1UecayRyfWQC5psUg8pXdLRq",
    "Pro Annual": "price_1UeciwRyfWQC5psU1n56spbe",
    "Family Annual": "price_1UecgVRyfWQC5psUPS3B8LWa",
}

def _price_id(plan):
    return str(st.secrets.get(PLAN_PRICE_KEYS[plan], SANDBOX_PRICE_IDS[plan]))

def checkout_ready():
    try:
        key = str(st.secrets.get("STRIPE_SECRET_KEY", ""))
        return key.startswith("sk_test_") and all(
            _price_id(plan).startswith("price_")
            for plan in PLAN_PRICE_KEYS
        )
    except Exception:
        return False

def _verified_user():
    """Confirm a Supabase identity server-side before making a checkout."""
    from supabase_auth import _settings
    session = st.session_state.get("am_auth") or {}
    access = session.get("access_token")
    if not access:
        raise PermissionError("Sign in before testing a subscription.")
    url, key = _settings()
    response = requests.get(
        url + "/auth/v1/user",
        headers={"apikey": key, "Authorization": "Bearer " + access},
        timeout=12,
    )
    if response.status_code != 200:
        raise PermissionError("Your sign-in expired. Please sign in again.")
    user = response.json()
    if not user.get("id") or user["id"] != session.get("user_id"):
        raise PermissionError("Could not verify your account.")
    return user

def create_test_checkout(plan):
    """Create a test-only subscription checkout URL, not a paid entitlement."""
    if plan not in PLAN_PRICE_KEYS:
        raise ValueError("Unknown subscription plan")
    if not checkout_ready():
        raise RuntimeError("Stripe test mode is not configured")
    user = _verified_user()
    import stripe
    stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]
    base_url = "https://readandmemorisethequran-9uvtv8lpn9ozytdqtk6ceh.streamlit.app"
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": _price_id(plan), "quantity": 1}],
        success_url=base_url + "/?checkout=success",
        cancel_url=base_url + "/?checkout=cancel",
        billing_address_collection="auto",
        allow_promotion_codes=True,
        client_reference_id=user["id"],
        customer_email=user.get("email"),
        subscription_data={"metadata": {
            "supabase_user_id": user["id"], "plan": plan, "environment": "test"}},
        metadata={"app": "al-muallim", "plan": plan,
                  "supabase_user_id": user["id"], "environment": "test"},
    )
    return session.url
