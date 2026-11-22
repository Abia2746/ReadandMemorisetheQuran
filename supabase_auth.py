"""Supabase email OTP authentication for the Streamlit preview.

No paid entitlement is inferred from an authenticated session.
Credentials belong in Streamlit Secrets, never in source control.
"""
import re
import requests
import streamlit as st

BASE = "https://readandmemorisethequran-9uvtv8lpn9ozytdqtk6ceh.streamlit.app"

def configured():
    try:
        url = str(st.secrets.get("SUPABASE_URL", "")).rstrip("/")
        key = str(st.secrets.get("SUPABASE_ANON_KEY", ""))
        return url.startswith("https://") and bool(key)
    except Exception:
        return False

def _settings():
    if not configured():
        raise RuntimeError("Supabase is not configured")
    return str(st.secrets["SUPABASE_URL"]).rstrip("/"), str(st.secrets["SUPABASE_ANON_KEY"])

def _post(endpoint, data):
    url, key = _settings()
    response = requests.post(
        url + "/auth/v1/" + endpoint,
        headers={"apikey": key, "Content-Type": "application/json"},
        json=data, timeout=15,
    )
    if response.status_code >= 400:
        # Never display arbitrary server errors, tokens or personal data.
        if response.status_code == 429:
            raise ValueError("Too many attempts. Please try again later.")
        raise ValueError("Authentication was not completed. Check your email code and Supabase settings.")
    return response.json() if response.content else {}

def request_code(email):
    email = email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        raise ValueError("Enter a valid email address.")
    _post("otp", {"email": email, "create_user": True})
    return email

def verify_code(email, code):
    if not re.fullmatch(r"\d{6,8}", code.strip()):
        raise ValueError("Enter the code from your email.")
    result = _post("verify", {"email": email, "token": code.strip(), "type": "email"})
    token = result.get("access_token")
    if not token or not result.get("user", {}).get("id"):
        raise ValueError("Could not verify this code.")
    return {"access_token": token, "refresh_token": result.get("refresh_token"),
            "user_id": result["user"]["id"], "email": result["user"].get("email", email)}

def render_account():
    st.subheader("Your Al-Mu'allim account")
    if not configured():
        st.info("Secure account sign-in is being prepared. Qur'an reading remains free without signing in.")
        return
    session = st.session_state.get("am_auth")
    if session:
        # Check token against Supabase on every render; do not trust session state alone.
        url, key = _settings()
        try:
            resp = requests.get(url + "/auth/v1/user",
                headers={"apikey": key, "Authorization": "Bearer " + session["access_token"]},
                timeout=12)
            if resp.status_code != 200 or resp.json().get("id") != session["user_id"]:
                st.session_state.pop("am_auth", None)
                st.warning("Your session expired. Please sign in again.")
                return
        except requests.RequestException:
            st.warning("Could not verify your session. Please try again.")
            return
        st.success("Signed in securely.")
        st.caption("Membership: Free. Premium access is not yet linked to Stripe.")
        if st.button("Sign out", key="am_signout"):
            st.session_state.pop("am_auth", None)
            st.rerun()
        return
    st.caption("Sign in with an email code. No password needed.")
    with st.form("am_email_code_request"):
        email = st.text_input("Email address", key="am_auth_email")
        send = st.form_submit_button("Send sign-in code")
    if send:
        try:
            st.session_state["am_pending_email"] = request_code(email)
            st.success("If this address can receive sign-in emails, check your inbox.")
        except ValueError as exc:
            st.error(str(exc))
        except (requests.RequestException, RuntimeError):
            st.error("Could not contact the sign-in service. Please try again.")
    if st.session_state.get("am_pending_email"):
        with st.form("am_email_code_verify"):
            code = st.text_input("Email code", max_chars=8)
            confirm = st.form_submit_button("Verify and sign in")
        if confirm:
            try:
                st.session_state["am_auth"] = verify_code(st.session_state["am_pending_email"], code)
                st.session_state.pop("am_pending_email", None)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except (requests.RequestException, RuntimeError):
                st.error("Sign-in service unavailable. Please try again.")
