"""Stripe TEST-MODE hosted Checkout for Al-Mu'allim.

Checkout is intentionally disabled for live keys and does not grant entitlements.
A verified webhook plus persistent authentication must be deployed before launch.
Never put Stripe secret keys in this repository.
"""
import streamlit as st

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

def create_test_checkout(plan):
    """Create a test-only subscription checkout URL, not a paid entitlement."""
    if plan not in PLAN_PRICE_KEYS:
        raise ValueError("Unknown subscription plan")
    if not checkout_ready():
        raise RuntimeError("Stripe test mode is not configured")
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
        metadata={"app": "al-muallim", "plan": plan, "environment": "test"},
    )
    return session.url
