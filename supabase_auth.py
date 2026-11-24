"""Supabase email OTP authentication for the Streamlit preview.

No paid entitlement is inferred from an authenticated session.
Only public Supabase URL/publishable key are embedded; private credentials must stay in Secrets.
"""
import re
import time
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
        # Do not expose raw API errors, account existence, tokens or request data.
        if response.status_code == 429:
            st.session_state["am_auth_retry_after"] = time.time() + 600
            raise ValueError("Email requests are temporarily limited. Please continue as a guest and try later.")
        if response.status_code in (400, 422):
            raise ValueError("The email sign-in service needs configuration. Please try again later.")
        raise ValueError("Email sign-in is unavailable. Please try again later.")
    return response.json() if response.content else {}

def request_magic_link(email, create_account=True):
    """Ask Supabase to email its standard one-time sign-in link."""
    email = email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        raise ValueError("Enter a valid email address.")
    # One request per learner per cooldown; prevents repeated accidental taps.
    now = time.time()
    if now < float(st.session_state.get("am_auth_retry_after", 0)):
        raise ValueError("Please allow the email request limit to reset before asking for another link.")
    # The Supabase link redirects only to the configured app origin.
    _post("otp", {"email": email, "create_user": bool(create_account)},
          params={"redirect_to": "https://readandmemorisethequran-9uvtv8lpn9ozytdqtk6ceh.streamlit.app/"})
    st.session_state["am_auth_retry_after"] = now + 90
    return email


def verify_email_code(email, token):
    """Verify a Supabase email OTP and accept only a confirmed identity.

    The Magic Link email template must include the {{ .Token }} variable to
    deliver an OTP. The code is never logged or persisted in browser storage.
    """
    email = str(email or "").strip().lower()
    token = str(token or "").strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        raise ValueError("Enter a valid email address.")
    if not re.fullmatch(r"[0-9]{6,8}", token):
        raise ValueError("Enter the numeric code from your latest email.")
    now = time.time()
    if now < float(st.session_state.get("am_verify_backoff_until", 0)):
        raise ValueError("Too many incorrect codes. Please try again later.")
    # A few local attempts are allowed; Supabase also enforces server-side
    # one-time code validity and rate limiting.
    attempts = int(st.session_state.get("am_verify_attempts", 0))
    if attempts >= 5:
        st.session_state["am_verify_backoff_until"] = now + 600
        raise ValueError("Too many incorrect codes. Please try again later.")
    st.session_state["am_verify_attempts"] = attempts + 1
    try:
        reply = _post("verify", {"email": email, "token": token, "type": "email"})
    except ValueError:
        if st.session_state["am_verify_attempts"] >= 5:
            st.session_state["am_verify_backoff_until"] = now + 600
        raise ValueError("The code is incorrect, expired or already used.")
    access = reply.get("access_token")
    refresh = reply.get("refresh_token")
    # Independently revalidate the returned session with Supabase before
    # populating account data, rather than trusting the email field.
    from auth_callback import _verify_credentials
    verified = _verify_credentials(access, refresh)
    if not verified:
        raise ValueError("Email verification could not be confirmed.")
    if verified.get("email", "").lower() != email:
        raise ValueError("The verified account does not match this email.")
    st.session_state["am_auth"] = verified
    st.session_state["am_auth_signout"] = False
    st.session_state["am_auth_clear_storage"] = False
    st.session_state["am_cloud_loaded_for"] = None
    st.session_state["am_new_login"] = True
    st.session_state["am_verify_attempts"] = 0
    st.session_state.pop("am_pending_email", None)
    st.session_state.pop("am_pending_mode", None)
    return True


def ensure_session_valid():
    """Validate or renew an existing Supabase session before private data is used."""
    session = st.session_state.get("am_auth")
    if not session or not session.get("access_token"):
        return False
    url, key = _settings()
    try:
        response = requests.get(
            url + "/auth/v1/user",
            headers={"apikey": key, "Authorization": "Bearer " + session["access_token"]},
            timeout=12,
        )
        if response.status_code == 401 and session.get("refresh_token"):
            renewed = requests.post(
                url + "/auth/v1/token",
                params={"grant_type": "refresh_token"},
                headers={"apikey": key, "Content-Type": "application/json"},
                json={"refresh_token": session["refresh_token"]},
                timeout=12,
            )
            if renewed.status_code == 200:
                next_tokens = renewed.json()
                if next_tokens.get("access_token") and next_tokens.get("refresh_token"):
                    session["access_token"] = next_tokens["access_token"]
                    session["refresh_token"] = next_tokens["refresh_token"]
                    response = requests.get(
                        url + "/auth/v1/user",
                        headers={"apikey": key, "Authorization": "Bearer " + session["access_token"]},
                        timeout=12,
                    )
        if response.status_code == 401 or response.status_code == 403:
            st.session_state.pop("am_auth", None)
            st.session_state["am_auth_error"] = "Your session expired. Please sign in again."
            st.session_state["am_auth_signout"] = True
            return False
        if response.status_code != 200:
            return False
        user = response.json()
        # Protect against a stale/revoked account and any account which has
        # not completed email verification. Never authorize based on profile.
        if (user.get("id") != session.get("user_id")
                or not user.get("email_confirmed_at")):
            st.session_state.pop("am_auth", None)
            st.session_state["am_auth_signout"] = True
            st.session_state["am_cloud_loaded_for"] = None
            st.session_state["am_auth_error"] = (
                "Please verify your email address before signing in."
            )
            return False
        return True
    except requests.RequestException:
        return False


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
        # Next render reloads the authoritative cloud history and updated count.
        st.session_state["am_cloud_loaded_for"] = None
    return True

def render_account():
    st.markdown("""
<style>
div[data-testid="stDialog"] div[data-testid="stForm"] {border:1px solid rgba(214,186,128,.23);border-radius:17px;padding:20px;background:rgba(255,255,255,.025)}
div[data-testid="stDialog"] input {min-height:48px!important;border-radius:11px!important;background:rgba(255,255,255,.055)!important}
div[data-testid="stDialog"] button[kind="primaryFormSubmit"] {background:linear-gradient(110deg,#c99c51,#ead29b)!important;color:#211810!important;border:0!important;border-radius:11px!important;min-height:48px;font-weight:700!important}
.am-auth-hero {text-align:center;padding:5px 0 15px}
.am-auth-emblem {display:flex;align-items:center;justify-content:center;width:46px;height:46px;border-radius:14px;border:1px solid rgba(229,198,139,.35);margin:0 auto 14px;color:#e4c581;background:rgba(220,188,122,.07);font-size:25px}
.am-auth-overline {color:#d2b477;font-size:10px;letter-spacing:.18em;font-weight:700}
.am-auth-title {font-family:Georgia,serif;color:#eed9b2;font-size:clamp(26px,4vw,34px);margin:10px 0 5px;line-height:1.2}
.am-auth-subtitle {font-size:13px;color:#cfbea5;max-width:350px;margin:0 auto;line-height:1.6}
.am-auth-note {color:#c0ad90;font-size:12px;text-align:center;line-height:1.6;padding:8px 0}
@media(max-width:600px){div[data-testid="stDialog"] div[data-testid="stForm"]{padding:14px}.am-auth-hero{padding-top:0}}
</style>
<div class="am-auth-hero">
<div class="am-auth-emblem" aria-hidden="true">✧</div>
<div class="am-auth-overline">AL-MU’ALLIM · YOUR QUR’AN COMPANION</div>
<div class="am-auth-title">Your journey, beautifully kept.</div>
<p class="am-auth-subtitle">Continue your Qur’an learning, memorisation and reflection from wherever you are.</p>
</div>
""", unsafe_allow_html=True)
    if not configured():
        st.info("Secure account sign-in is being prepared. Qur'an reading remains free without signing in.")
        return
    session = st.session_state.get("am_auth")
    if session:
        # Supabase, not Streamlit session state, is the account authority.
        if not ensure_session_valid():
            st.warning("Your session could not be verified. Please sign in again if needed.")
            return
        url, key = _settings()
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
            st.session_state["am_auth_signout"] = True
            st.session_state["am_cloud_loaded_for"] = None
            st.session_state["am_cloud_review_rows"] = []
            st.session_state["am_profile_user"] = None
            st.session_state["name"] = ""
            st.session_state["results"] = {}
            st.rerun()
        return
    if st.session_state.get("am_auth_error"):
        st.warning(st.session_state.pop("am_auth_error"))

    mode = st.segmented_control(
        "Account mode", options=["Sign in", "Create account"],
        default="Sign in", key="am_account_mode",
        label_visibility="collapsed", width="stretch",
    )
    if not mode:
        mode = "Sign in"
    st.markdown(
        "<div class='am-auth-note'>" +
        ("Welcome back. We'll send a secure sign-in link to your email."
         if mode == "Sign in" else
         "Create a free account to keep your Qur’an progress together.") +
        "</div>", unsafe_allow_html=True,
    )

    if st.session_state.get("am_pending_email") and st.session_state.get("am_pending_mode") == mode:
        st.success("A secure email link has been requested.")
        st.caption("Open the newest confirmation or sign-in email and use the "
                   "link once. It should bring you back to Al-Mu’allim. "
                   "A new account may need to confirm its email first.")
        if st.button("Request a fresh link or change email", key="am_switch_email",
                     use_container_width=True):
            st.session_state.pop("am_pending_email", None)
            st.session_state.pop("am_pending_mode", None)
            st.rerun()
        st.caption("If no email arrives, check Spam/Junk. Sending is rate-limited; "
                   "please do not repeatedly tap the request button.")
        st.markdown("**Enter the verification code**")
        st.caption("If your email includes a six-digit code, enter it here instead "
                   "of opening the confirmation link. If the email only has a link, "
                   "use that link; code login needs the Supabase email template "
                   "to include its OTP token.")
        with st.form("am_verify_otp"):
            otp = st.text_input(
                "Email verification code", max_chars=8,
                placeholder="6-digit code",
                key="am_email_otp_input",
            )
            verify = st.form_submit_button(
                "Verify and sign in", use_container_width=True, type="primary")
        if verify:
            try:
                verify_email_code(st.session_state["am_pending_email"], otp)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except (requests.RequestException, RuntimeError):
                st.error("Verification is temporarily unavailable. Please try again later.")
    else:
        with st.form("am_magic_link_request"):
            email = st.text_input("Email address", placeholder="name@example.com", key="am_auth_email")
            send = st.form_submit_button("Continue with email", use_container_width=True, type="primary")
        if send:
            try:
                st.session_state["am_pending_email"] = request_magic_link(
                    email, create_account=(mode == "Create account"))
                st.session_state["am_pending_mode"] = mode
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except (requests.RequestException, RuntimeError):
                st.error("The email service is temporarily unavailable. Please try again later.")

    st.markdown(
        "<div class='am-auth-note'>No password required · One-time secure email link"
        "<br>Qur’an reading remains free without an account.</div>",
        unsafe_allow_html=True,
    )
