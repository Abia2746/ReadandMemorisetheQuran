"""Public pricing preview for the Streamlit Community Cloud edition of Al-Mu'allim.

This page displays proposed plans only. It never collects payment information,
claims subscriptions are active, or calls a checkout provider.
"""
import html
import streamlit as st

PLANS = (
    ("Free", "£0", "forever", "Read the Qur'an without a subscription.",
     ("Full Qur'an reading", "Reciter audio", "Basic memorisation", "One Hifz study plan")),
    ("Pro Monthly", "£5.99", "per month", "Optional expanded study features.",
     ("Everything in Free", "Advanced word review (planned)", "Expanded AI study tools (planned)", "Premium sanctuary themes (planned)")),
    ("Pro Annual", "£39.99", "per year", "The proposed annual Pro plan.",
     ("Everything in Pro Monthly", "Annual subscription (not yet available)", "Optional soundscapes (planned)", "Personal learning progress")),
    ("Family Annual", "£69.99", "per year", "A proposed plan for households.",
     ("Pro study features", "Up to five profiles (planned)", "Separate Hifz progress (planned)", "Family management (planned)")),
)

def render_pricing():
    st.markdown('<div style="text-align:center;padding:16px 0 24px"><div style="color:#C8A96E;letter-spacing:.2em;font-size:12px;font-weight:700">AL-MU\'ALLIM MEMBERSHIP</div><h1 style="font-size:clamp(32px,5vw,54px);margin:10px 0;color:#F5EBE0!important">A place for every learner</h1><p style="color:#E6D5B8">Qur\'an reading stays free. Explore our proposed optional memberships.</p></div>', unsafe_allow_html=True)
    st.info("Pricing preview only. Subscriptions and checkout are not live. Features and final prices may change before launch.")
    for start in (0, 2):
        cols = st.columns(2, gap="medium")
        for col, (name, price, cadence, desc, features) in zip(cols, PLANS[start:start+2]):
            with col:
                safe = lambda value: html.escape(str(value), quote=True)
                items = "".join('<li style="padding:5px 0;color:#F5EBE0">✦ '+safe(feature)+'</li>' for feature in features)
                st.markdown(
                    '<div style="background:#241913;border:1px solid '+('#D4AF37' if name == 'Pro Annual' else '#65503D')+';border-radius:20px;padding:24px;min-height:350px;margin-bottom:16px">'
                    '<h2 style="color:#EDD39F!important;font-size:24px;margin:0">'+safe(name)+'</h2>'
                    '<p style="margin:16px 0 8px"><strong style="font-size:32px;color:#F5EBE0">'+safe(price)+'</strong> <span style="color:#C8B6A1">'+safe(cadence)+'</span></p>'
                    '<p style="color:#E6D5B8">'+safe(desc)+'</p>'
                    '<ul style="list-style:none;padding:0;margin-top:18px">'+items+'</ul>'
                    '<div style="margin-top:20px;color:#C8A96E;font-size:13px">'+('Free access' if name == 'Free' else 'Coming soon — no payment taken')+'</div></div>',
                    unsafe_allow_html=True,
                )
    st.caption("Scholarship and sponsored-access options are planned. No payment is collected through this page.")
