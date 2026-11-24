"""Streamlit Components v2 bridge for Supabase email authentication.

Preview-only persistence: browser localStorage has XSS exposure and must be
replaced with HttpOnly cookie sessions before taking real payments.
Supabase Auth validates every received token before the browser persists it.
Do not log email callback fragments or bearer/refresh tokens.
"""
import requests
import streamlit as st

MAGIC_LINK_JS = r"""
export default function({setTriggerValue, data}) {
  const key = "al-muallim.preview-auth.v1";
  const active = data?.session;
  const clear = !!data?.clear;
  const fingerprint = (v) => typeof v === "string" && v.length > 20 ? v.slice(-16) : "";
  try {
    if (clear) {
      localStorage.removeItem(key);
      window.__amRestoreAttempted = null;
      if (!window.__amClearAcknowledged) {
        window.__amClearAcknowledged = true;
        setTriggerValue("storage_cleared", true);
      }
      return;
    }
    window.__amClearAcknowledged = false;
    if (active?.access_token && active?.refresh_token) {
      const saved = localStorage.getItem(key);
      const next = JSON.stringify({
        access_token: active.access_token,
        refresh_token: active.refresh_token
      });
      if (saved !== next) localStorage.setItem(key, next);
    }
    // The Supabase verification URL returns token details in its fragment.
    // Components v2 run in the same document, not a cross-origin iframe.
    const hash = window.location.hash;
    if (hash && (hash.includes("access_token=") || hash.includes("error="))) {
      const p = new URLSearchParams(hash.slice(1));
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
      if (p.get("error")) {
        localStorage.removeItem(key);
        setTriggerValue("auth_error", p.get("error_code") === "otp_expired" ? "expired" : "failed");
        return;
      }
      const access = p.get("access_token");
      const refresh = p.get("refresh_token");
      if (access && refresh && p.get("token_type") === "bearer") {
        // Do not persist these unverified credentials.
        setTriggerValue("tokens", {access_token: access, refresh_token: refresh});
      }
      return;
    }
    if (active?.access_token) return;
    const raw = localStorage.getItem(key);
    if (!raw) return;
    const tokens = JSON.parse(raw);
    if (!tokens?.access_token || !tokens?.refresh_token) {
      localStorage.removeItem(key);
      return;
    }
    const id = fingerprint(tokens.refresh_token);
    // Only one restoration attempt per credential on this page.
    if (window.__amRestoreAttempted === id) return;
    window.__amRestoreAttempted = id;
    setTriggerValue("tokens", tokens);
  } catch {
    localStorage.removeItem(key);
  }
}
"""

def _verify_credentials(access, refresh):
    """Resolve session to a verified Supabase account, refreshing if necessary."""
    from supabase_auth import _settings
    if not (isinstance(access, str) and isinstance(refresh, str)
            and 20 < len(access) < 8192 and 20 < len(refresh) < 8192):
        return None
    url, key = _settings()
    headers = {"apikey": key, "Authorization": "Bearer " + access}
    response = requests.get(url + "/auth/v1/user", headers=headers, timeout=12)
    if response.status_code == 401:
        renewed = requests.post(
            url + "/auth/v1/token", params={"grant_type": "refresh_token"},
            headers={"apikey": key, "Content-Type": "application/json"},
            json={"refresh_token": refresh}, timeout=12,
        )
        if renewed.status_code != 200:
            return None
        tokens = renewed.json()
        access, refresh = tokens.get("access_token"), tokens.get("refresh_token")
        if not (isinstance(access, str) and isinstance(refresh, str)
                and 20 < len(access) < 8192 and 20 < len(refresh) < 8192):
            return None
        response = requests.get(
            url + "/auth/v1/user",
            headers={"apikey": key, "Authorization": "Bearer " + access},
            timeout=12,
        )
    if response.status_code != 200:
        return None
    user = response.json()
    if not isinstance(user.get("id"), str) or not user.get("id"):
        return None
    if not user.get("email_confirmed_at"):
        # An unconfirmed identity must not be silently treated as verified.
        return None
    return {"access_token": access, "refresh_token": refresh,
            "user_id": user["id"], "email": user.get("email", "")}


def accept_magic_link_tokens():
    """Accept email callback and saved sessions; fail closed on bad credentials."""
    from supabase_auth import _settings
    callback = st.components.v2.component(
        "al_muallim_magic_link_callback",
        html="<div aria-hidden='true' style='height:0'></div>",
        js=MAGIC_LINK_JS,
    )
    session = st.session_state.get("am_auth")
    clear = bool(st.session_state.get("am_auth_signout")
                 or st.session_state.get("am_auth_clear_storage"))
    result = callback(
        key="am_magic_link_callback",
        data={
            "session": {
                "access_token": session.get("access_token"),
                "refresh_token": session.get("refresh_token"),
            } if session else None,
            "clear": clear,
        },
        on_tokens_change=lambda: None,
        on_auth_error_change=lambda: None,
        on_storage_cleared_change=lambda: None,
    )
    if result.storage_cleared:
        st.session_state["am_auth_signout"] = False
        st.session_state["am_auth_clear_storage"] = False
        return
    if clear or session:
        return
    if result.auth_error:
        st.session_state["am_auth_error"] = (
            "This email link has expired or was already used. Please request a new one."
            if result.auth_error == "expired"
            else "The confirmation link could not be completed. Request a fresh email."
        )
        st.session_state["am_auth_clear_storage"] = True
        return
    payload = result.tokens
    if not isinstance(payload, dict):
        return
    try:
        verified = _verify_credentials(
            payload.get("access_token"), payload.get("refresh_token")
        )
    except (requests.RequestException, RuntimeError, ValueError):
        st.session_state["am_auth_error"] = (
            "Could not reach the login service. Please try again."
        )
        return
    if not verified:
        st.session_state["am_auth_error"] = (
            "That session is invalid, unverified or expired. Request a new link."
        )
        st.session_state["am_auth_clear_storage"] = True
        return
    st.session_state["am_auth"] = verified
    st.session_state["am_cloud_loaded_for"] = None
    st.session_state["am_new_login"] = True
    st.session_state.pop("am_pending_email", None)
    st.session_state.pop("am_auth_error", None)
