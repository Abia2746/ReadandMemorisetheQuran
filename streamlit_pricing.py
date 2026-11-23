"""Al-Mu'allim memberships — transparent pricing and Sandbox-only checkout."""
import html
import re
import streamlit as st
from stripe_checkout import checkout_ready, create_test_checkout, create_test_billing_portal
from stripe_membership import get_verified_test_membership

PLANS = (
    ("Free", "£0", "Forever", "A thoughtful beginning for every learner.",
     ("Qur’an reading", "Reciter audio", "Basic memorisation", "One Hifdh plan")),
    ("Pro Monthly", "£5.99", "/month", "For learners who want more guided practice.",
     ("Everything in Free", "Advanced revision tools (planned)",
      "AI-supported learning (planned)", "Premium sanctuary themes (planned)")),
    ("Pro Annual", "£39.99", "/year", "A year of consistent Qur’an learning.",
     ("Everything in Pro Monthly", "Same Pro features, billed annually",
      "Premium soundscapes (planned)", "Expanded progress insights (planned)")),
    ("Family Annual", "£69.99", "/year", "A shared space for household learning.",
     ("Pro features (planned)", "Up to five profiles (planned)",
      "Separate Hifdh progress (planned)", "Family dashboard (planned)")),
)

def _checkout_error(exc):
    import stripe
    if isinstance(exc, PermissionError):
        return "Please sign in to a verified Al-Mu’allim account before testing checkout."
    if isinstance(exc, stripe.error.AuthenticationError):
        return "Stripe rejected the Sandbox key. Confirm the key matches these test products."
    if isinstance(exc, stripe.error.InvalidRequestError):
        code = str(getattr(exc, "code", None) or "invalid_request")
        message = str(getattr(exc, "user_message", None) or "Stripe rejected a checkout setting.")
        message = re.sub(r"(?:sk|rk|pk)_(?:test|live)_[A-Za-z0-9]+", "[REDACTED]", message)
        return "Stripe: " + message[:260] + " (" + code + ")"
    return "Could not open Stripe Sandbox checkout. Check your test configuration and app logs."

def render_pricing():
    st.markdown("""
<style>
.am-price-hero{text-align:center;max-width:690px;margin:0 auto;padding:28px 10px 28px}
.am-price-kicker{letter-spacing:.23em;color:#c7a36a;font-size:11px;font-weight:700}
.am-price-title{font-family:Georgia,serif;color:#f8e8ca;font-size:clamp(32px,5vw,52px);
line-height:1.12;margin:12px 0 12px}
.am-price-description{color:#d8c8b4;line-height:1.7;font-size:15px}
.am-plan{border-radius:22px;background:linear-gradient(145deg,rgba(33,64,52,.78),rgba(27,43,35,.9));
border:1px solid rgba(207,179,123,.28);padding:23px 20px;min-height:320px;margin-bottom:8px}
.am-plan--featured{border-color:#d8b573;box-shadow:0 9px 36px rgba(0,0,0,.11)}
.am-plan-name{color:#edd3a1;font-size:23px;font-family:Georgia,serif;margin:2px 0 13px}
.am-plan-price{color:#fff6e7;font-weight:700;font-size:34px;letter-spacing:-.04em}
.am-plan-cadence{color:#cfbca1;font-size:14px;letter-spacing:0;font-weight:400}
.am-plan-blurb{color:#e2d4c4;font-size:13px;line-height:1.55;min-height:42px;margin-top:10px}
.am-plan ul{list-style:none;padding:0;margin:15px 0 0}
.am-plan li{color:#e9e0d1;padding:6px 0;font-size:13px}
.am-plan li:before{content:'✓';color:#d9b977;margin-right:10px}
.am-plan-tag{color:#d7b874;font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
</style>
<div class="am-price-hero">
<div class="am-price-kicker">AL-MU’ALLIM MEMBERSHIP</div>
<h1 class="am-price-title">A place for every learner.</h1>
<div class="am-price-description">Read the Qur’an freely. Explore optional study
memberships designed to deepen memorisation, reflection and consistency.</div>
</div>
""", unsafe_allow_html=True)

    st.info("These memberships are a preview. The paid features are still in development. "
            "Checkout is available only for test payments; no real charges are being accepted.")

    membership = None
    if st.session_state.get("am_auth"):
        membership = get_verified_test_membership()
    if membership:
        st.success("Stripe Sandbox verified: " + membership +
                   ". This is a test membership and does not enable paid features.")
    elif st.session_state.get("am_auth"):
        st.caption("Current membership: Free. No verified Sandbox subscription found.")

    if membership and checkout_ready():
        with st.expander("Manage Sandbox subscription", expanded=False):
            st.caption("Use the Stripe-hosted billing portal to review or cancel a test subscription. "
                       "The portal must first be configured in your Stripe Sandbox dashboard.")
            if st.button("Open test billing management", use_container_width=True,
                         key="am_manage_test_billing"):
                try:
                    st.link_button("Continue to Stripe billing portal",
                                   create_test_billing_portal(), use_container_width=True)
                except Exception:
                    st.error("The Sandbox billing portal isn't ready. "
                             "Check Stripe Billing → Customer portal settings.")

    for group_start in (0, 2):
        cols = st.columns(2, gap="medium")
        for col, (name, price, cadence, desc, features) in zip(cols, PLANS[group_start:group_start+2]):
            with col:
                safe = lambda value: html.escape(str(value), quote=True)
                items = "".join("<li>" + safe(item) + "</li>" for item in features)
                st.markdown(
                    '<div class="am-plan' + (' am-plan--featured' if name == "Pro Annual" else '') + '">' +
                    '<div class="am-plan-tag">' + ("Best annual value" if name == "Pro Annual" else
                                                  "Always accessible" if name == "Free" else
                                                  "Premium membership preview") + '</div>' +
                    '<h2 class="am-plan-name">' + safe(name) + '</h2>' +
                    '<div class="am-plan-price">' + safe(price) +
                    '<span class="am-plan-cadence"> ' + safe(cadence) + '</span></div>' +
                    '<p class="am-plan-blurb">' + safe(desc) + '</p>' +
                    '<ul>' + items + '</ul></div>',
                    unsafe_allow_html=True,
                )
                if name == "Free":
                    st.caption("Free Qur’an reading is always available without purchasing a plan.")
                elif checkout_ready():
                    if not st.session_state.get("am_auth"):
                        st.caption("Sign in to your account to test this subscription.")
                    elif st.button("Test " + name + " checkout", key="am_test_checkout_"+name,
                                   use_container_width=True):
                        try:
                            link = create_test_checkout(name)
                            st.link_button("Continue to Stripe Sandbox", link, use_container_width=True)
                        except Exception as exc:
                            st.error(_checkout_error(exc))
                else:
                    st.caption("Test checkout is not configured on this deployment.")
        st.write("")

    st.divider()
    st.markdown("#### Your Qur’an is not behind a paywall")
    st.write("Reading, listening and basic memorisation stay free. "
             "The optional memberships will become purchasable only when their "
             "promised features, billing safeguards and cancellation tools are ready.")
    st.caption("All paid prices are in GBP. Annual plans renew yearly; monthly plans renew monthly. "
               "No live subscription, payment, or automatic premium activation is available yet.")
