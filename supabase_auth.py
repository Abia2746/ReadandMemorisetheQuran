"""Supabase email OTP authentication for the Streamlit preview.

No paid entitlement is inferred from an authenticated session.
Only public Supabase URL/publishable key are embedded; private credentials must stay in Secrets.
"""
import re
from urllib.parse import parse_qs, urlsplit
import requests
import streamlit as st

# Public project settings, not secret credentials.
DEFAULT_SUPABASE_URL = "https://edkqwqepnlidenxyveoj.supabase.co"
DEFAULT_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_wpPRWa2YTlZwuukdxOa50g_TznBIqcn"

def _public_config():
    try:
        url = str(st.secrets.get("SUPABASE_URL", DEFAULT_SUPABASE_URL)).rstrip("/")
        key = str(st.secrets.get("SUPABASE_ANON_KEY", DEFAULT_SUPABASE_PUBLISHABLE_KEY))
    except Exception:
        url, key = DEFAULT_SUPABASE_URL, DEFAULT_SUPABASE_PUBLISHABLE_KEY
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

def request_magic_link(email):
    """Ask Supabase to email its standard one-time sign-in link."""
    email = email.strip().lower()
    if not re.fullmatch(r"[^\\s@]+@[^\\s@]+\\.[^\\s@]+", email) or len(email) > 254:
        raise ValueError("Enter a valid email address.")
    # No redirect is needed for this Streamlit fallback: the link is
    # redeemed securely by the backend when pasted into the login form.
    _post("otp", {"email": email, "create_user": True})
    return email


def verify_magic_link(link):
    """Consume a default Supabase email link without exposing its tokens in URLs.

    Streamlit's server cannot read a browser's URL fragment. The temporary
    fallback is to paste an unclicked magic link into the protected input.
    """
    url, key = _settings()
    link = link.strip()
    if len(link) > 4096:
        raise ValueError("That sign-in link is too long.")
    source = urlsplit(link)
    expected = urlsplit(url)
    if (source.scheme != "https" or source.hostname != expected.hostname
            or source.path != "/auth/v1/verify"
            or source.username or source.password or source.port not in (None, 443)):
        raise ValueError("Paste the original sign-in link from your Al-Mu'allim email.")
    query = parse_qs(source.query, keep_blank_values=False)
    token = query.get("token", [""])[0]
    token_type = query.get("type", [""])[0]
    if (not re.fullmatch(r"[A-Za-z0-9_-]{16,2048}", token)
            or token_type not in ("magiclink", "signup", "email")):
        raise ValueError("This is not a valid Supabase sign-in link.")
    # Never follow the redirect or output its Location header. The fragment
    # contains bearer tokens and must remain server-side.
    response = requests.get(
        url + "/auth/v1/verify", headers={"apikey": key},
        params={"token": token, "type": token_type},
        allow_redirects=False, timeout=15,
    )
    if response.status_code not in (301, 302, 303, 307, 308):
        raise ValueError("This sign-in link is invalid, expired or already used. Request a new link.")
    location = response.headers.get("Location", "")
    redirect = urlsplit(location)
    parts = parse_qs(redirect.fragment)
    access = parts.get("access_token", [""])[0]
    refresh = parts.get("refresh_token", [""])[0]
    if not access or not refresh:
        raise ValueError("The sign-in link could not create a session. Request another link.")
    validation = requests.get(
        url + "/auth/v1/user",
        headers={"apikey": key, "Authorization": "Bearer " + access},
        timeout=15,
    )
    if validation.status_code != 200 or not validation.json().get("id"):
        raise ValueError("Supabase couldn't confirm this account. Request a new link.")
    user = validation.json()
    return {
        "access_token": access, "refresh_token": refresh,
        "user_id": user["id"], "email": user.get("email", ""),
    }


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
            if resp.status_code != 200 or resp.json().get("id") != session["user_id"]:
                st.session_state.pop("am_auth", None)
                st.warning("Your session expired. Please sign in again.")
                return
        except requests.RequestException:
            st.warning("Could not verify your session. Please try again.")
            return
        st.success("Signed in securely.")
        st.caption("Membership: Free. Premium access is not yet linked to Stripe.")
        with st.form("am_cloud_profile"):
            display_name = st.text_input("Cloud profile name", value=st.session_state.get("name", ""), max_chars=80)
            save_profile = st.form_submit_button("Save name to my cloud account")
        if save_profile:
            try:
                _table_request("learner_profiles", "POST",
                    [{"user_id": session["user_id"], "display_name": display_name}],
                    params={"on_conflict": "user_id"}, upsert=True)
                st.success("Profile name saved securely.")
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
            st.session_state.pop("am_auth", None)
            st.rerun()
        return
    st.caption("Sign in by email without a password.")
    with st.form("am_magic_link_request"):
        email = st.text_input("Email address", key="am_auth_email")
        send = st.form_submit_button("Email me a sign-in link")
    if send:
        try:
            st.session_state["am_pending_email"] = request_magic_link(email)
            st.success("If your address is eligible to receive email, check your inbox.")
        except ValueError as exc:
            st.error(str(exc))
        except (requests.RequestException, RuntimeError):
            st.error("Could not contact the sign-in service. Please try again.")
    if st.session_state.get("am_pending_email"):
        st.info(
            "For this early Streamlit preview: copy the link address from the "
            "Supabase sign-in email **without opening it**, then paste it below. "
            "The link works only once. If you already tapped it, request a new one."
        )
        with st.form("am_magic_link_redeem", clear_on_submit=True):
            link = st.text_input("Paste your private sign-in link", type="password")
            confirm = st.form_submit_button("Sign in securely")
        if confirm:
            try:
                st.session_state["am_auth"] = verify_magic_link(link)
                st.session_state.pop("am_pending_email", None)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except (requests.RequestException, RuntimeError):
                st.error("Sign-in service unavailable. Please try again.")
