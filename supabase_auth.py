"""Supabase email OTP authentication for the Streamlit preview.

No paid entitlement is inferred from an authenticated session.
Only public Supabase URL/publishable key are embedded; private credentials must stay in Secrets.
"""
import re
import requests
import streamlit as st

# Public project settings, not secret credentials.
DEFAULT_SUPABASE_URL = "https://edkqwqepnlidenxyveoj.supabase.co"
DEFAULT_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_wpPRWa2YTlZwuukdxOa50g_TznBIqcn"

def _public_config():
    """Public settings are usable even if Streamlit Secrets is unavailable or empty."""
    url, key = DEFAULT_SUPABASE_URL, DEFAULT_SUPABASE_PUBLISHABLE_KEY
    try:
        override_url = str(st.secrets.get("SUPABASE_URL", "") or "").strip().rstrip("/")
        override_key = str(st.secrets.get("SUPABASE_ANON_KEY", "") or "").strip()
        # Ignore partial/malformed overrides instead of disabling the app.
        if override_url.startswith("https://") and override_key:
            url, key = override_url, override_key
    except Exception:
        pass
    return url, key

def configured():
    try:
        url, key = _public_config()
        return url.startswith("https://") and bool(key)
    except Exception:
        return False

def _settings():
    if not configured():
        raise RuntimeError("Supabase is not configured")
    return _public_config()

def _post(endpoint, data, params=None):
    url, key = _settings()
    response = requests.post(
        url + "/auth/v1/" + endpoint,
        headers={"apikey": key, "Content-Type": "application/json"},
        json=data, params=params, timeout=15,
    )
    if response.status_code >= 400:
        # Never display arbitrary server errors, tokens or personal data.
        if response.status_code == 429:
            raise ValueError("Too many attempts. Please try again later.")
        raise ValueError("Email sign-in could not be started. Check the Supabase email provider and recipient restrictions.")
    return response.json() if response.content else {}

def request_magic_link(email, create_account=True):
    """Ask Supabase to email its standard one-time sign-in link."""
    email = email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        raise ValueError("Enter a valid email address.")
    # The Supabase link redirects to the approved app URL after verification.
    _post("otp", {"email": email, "create_user": bool(create_account)},
          params={"redirect_to": "https://readandmemorisethequran-9uvtv8lpn9ozytdqtk6ceh.streamlit.app/"})
    return email


def _table_request(table, method="GET", payload=None, params=None, upsert=False):
    url, key = _settings()
    session = st.session_state.get("am_auth")
    if not session or not session.get("access_token"):
        raise RuntimeError("No authenticated learner")
    headers = {
        "apikey": key,
        "Authorization": "Bearer " + session["access_token"],
        "Content-Type": "application/json",
    }
    if upsert:
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
    response = requests.request(
        method, url + "/rest/v1/" + table, headers=headers,
        params=params, json=payload, timeout=12,
    )
    if response.status_code >= 400:
        raise RuntimeError("Cloud save was not completed.")
    return response.json() if response.content and method == "GET" else None

def save_review_progress(surah_number, ayah_numbers):
    """Best-effort cloud revision record; never awards memorised status."""
    session = st.session_state.get("am_auth")
    if not session:
        return False
    rows = [
        {"user_id": session["user_id"], "surah_number": int(surah_number),
         "ayah_number": int(ayah), "practice_status": "reviewing"}
        for ayah in ayah_numbers
    ]
    if rows:
        _table_request("hifdh_progress", "POST", rows,
                       params={"on_conflict": "user_id,surah_number,ayah_number"}, upsert=True)
    return True

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
            if resp.status_code == 401 and session.get("refresh_token"):
                renewed = requests.post(
                    url + "/auth/v1/token", params={"grant_type": "refresh_token"},
                    headers={"apikey": key, "Content-Type": "application/json"},
                    json={"refresh_token": session["refresh_token"]},
                    timeout=12,
                )
                if renewed.status_code == 200:
                    payload = renewed.json()
                    if payload.get("access_token") and payload.get("refresh_token"):
                        session["access_token"] = payload["access_token"]
                        session["refresh_token"] = payload["refresh_token"]
                        resp = requests.get(
                            url + "/auth/v1/user",
                            headers={"apikey": key, "Authorization": "Bearer " + session["access_token"]},
                            timeout=12,
                        )
            if resp.status_code != 200 or resp.json().get("id") != session["user_id"]:
                st.session_state.pop("am_auth", None)
                st.warning("Your session expired. Please sign in again.")
                return
        except requests.RequestException:
            st.warning("Could not verify your session. Please try again.")
            return
        st.success("Your account is verified and signed in.")
        if session.get("email"):
            st.caption("Signed in as " + session["email"])
        st.caption("Membership: Free. Premium access is not yet linked to Stripe.")
        with st.form("am_cloud_profile"):
            display_name = st.text_input("Cloud profile name", value=st.session_state.get("name", ""), max_chars=80)
            save_profile = st.form_submit_button("Save name to my cloud account")
        if save_profile:
            try:
                _table_request("learner_profiles", "POST",
                    [{"user_id": session["user_id"], "display_name": display_name}],
                    params={"on_conflict": "user_id"}, upsert=True)
                st.session_state["name"] = display_name
                st.success("Your profile name has been saved.")
            except (RuntimeError, requests.RequestException):
                st.error("Could not save profile. Try again.")
        try:
            progress = _table_request("hifdh_progress", params={
                "select": "surah_number,ayah_number,practice_status",
                "order": "surah_number.asc,ayah_number.asc",
                "limit": "250",
            })
            st.caption(f"Verses recorded for cloud revision: {len(progress or [])}" +
                       (" (showing first 250)" if len(progress or []) == 250 else ""))
        except (RuntimeError, requests.RequestException):
            st.caption("Cloud revision count is temporarily unavailable.")
        if st.button("Sign out", key="am_signout"):
            try:
                requests.post(
                    url + "/auth/v1/logout",
                    headers={"apikey": key, "Authorization": "Bearer " + session["access_token"]},
                    timeout=8,
                )
            except requests.RequestException:
                pass
            st.session_state.pop("am_auth", None)
            st.rerun()
        return
    if st.session_state.get("am_auth_error"):
        st.warning(st.session_state.pop("am_auth_error"))

    st.caption("Continue with your email. No password required.")
    mode = st.radio(
        "Choose an option",
        ["Sign in", "Create account"],
        horizontal=True,
        key="am_account_mode",
    )
    with st.form("am_magic_link_request"):
        email = st.text_input("Email address", key="am_auth_email",
                              placeholder="you@example.com")
        send = st.form_submit_button(
            "Send secure sign-in link" if mode == "Sign in" else "Create my free account",
            use_container_width=True, type="primary",
        )
    if send:
        try:
            st.session_state["am_pending_email"] = request_magic_link(
                email, create_account=(mode == "Create account")
            )
            st.session_state["am_pending_mode"] = mode
        except ValueError as exc:
            st.error(str(exc))
        except (requests.RequestException, RuntimeError):
            st.error("Could not contact the email service. Please try again.")
    if st.session_state.get("am_pending_email"):
        st.success("Check your inbox for a secure email link.")
        st.caption(
            "Tap the link in the email to return to Al-Mu’allim automatically. "
            "The link can only be used once. If you have not received it, "
            "check Spam or Junk."
        )
    st.divider()
    st.caption("You can read the Qur’an for free without registering. "
               "An account lets you save your learning progress.")
