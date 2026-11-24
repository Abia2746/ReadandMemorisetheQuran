"""Supabase default magic-link callback for Streamlit Components v2.

The frontend safely captures the URL fragment delivered by Supabase Auth.
It removes the fragment before sending the tokens over Streamlit's component
channel; the Python backend independently validates the user at Supabase.
No login information is logged or put in query parameters.
"""
import requests
import streamlit as st

MAGIC_LINK_JS = r"""
export default function({setTriggerValue, data}) {
  const key = "al-muallim.preview-auth.v1";
  try {
    if (data?.signout) { localStorage.removeItem(key); return; }
    const active = data?.session;
    if (active?.access_token && active?.refresh_token) {
      localStorage.setItem(key, JSON.stringify(active));
    }
    const fragment = window.location.hash;
    if (fragment && (fragment.includes("access_token=") || fragment.includes("error="))) {
      const p = new URLSearchParams(fragment.slice(1));
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
      if (p.get("error")) {
        setTriggerValue("auth_error", p.get("error_code") === "otp_expired" ? "expired" : "failed");
        return;
      }
      const access = p.get("access_token");
      const refresh = p.get("refresh_token");
      if (access && refresh && p.get("token_type") === "bearer") {
        const credentials = {access_token:access, refresh_token:refresh};
        localStorage.setItem(key, JSON.stringify(credentials));
        setTriggerValue("tokens", credentials);
      }
      return;
    }
    if (active?.access_token) return;
    const saved = localStorage.getItem(key);
    if (saved && !window.__alMuallimRestoreAttempted) {
      window.__alMuallimRestoreAttempted = true;
      const credentials = JSON.parse(saved);
      if (credentials?.refresh_token) setTriggerValue("tokens", credentials);
    }
  } catch { localStorage.removeItem(key); }
}
"""

def accept_magic_link_tokens():
    """Run at the top level, even when the account panel is collapsed."""
    from supabase_auth import _settings
    callback = st.components.v2.component(
        "al_muallim_magic_link_callback",
        html="<div aria-hidden='true' style='height:0'></div>",
        js=MAGIC_LINK_JS,
    )
    session = st.session_state.get("am_auth")
    result = callback(
        key="am_magic_link_callback",
        data={
            "session": {
                "access_token": session.get("access_token"),
                "refresh_token": session.get("refresh_token"),
            } if session else None,
            "signout": bool(st.session_state.get("am_auth_signout")),
        },
        on_tokens_change=lambda: None,
                      on_auth_error_change=lambda: None)
    if st.session_state.get("am_auth_signout") or st.session_state.get("am_auth"):
        return
    if result.auth_error:
        st.session_state["am_auth_error"] = "That sign-in link expired. Request a new link." if result.auth_error == "expired" else "Sign-in could not be completed. Request a fresh link."
    payload = result.tokens
    if not payload or not isinstance(payload, dict):
        return
    access = payload.get("access_token")
    refresh = payload.get("refresh_token")
    if not isinstance(access, str) or not isinstance(refresh, str):
        st.session_state["am_auth_error"] = "The sign-in link was incomplete. Request a new link."
        return
    if not (20 < len(access) < 8192 and 20 < len(refresh) < 8192):
        st.session_state["am_auth_error"] = "The sign-in link was incomplete. Request a new link."
        return
    url, key = _settings()
    try:
        resp = requests.get(
            url + "/auth/v1/user",
            headers={"apikey": key, "Authorization": "Bearer " + access},
            timeout=12,
        )
        if resp.status_code == 401:
            renewed = requests.post(
                url + "/auth/v1/token",
                params={"grant_type": "refresh_token"},
                headers={"apikey": key, "Content-Type": "application/json"},
                json={"refresh_token": refresh}, timeout=12,
            )
            if renewed.status_code == 200:
                new_tokens = renewed.json()
                access = new_tokens.get("access_token", "")
                refresh = new_tokens.get("refresh_token", "")
                resp = requests.get(
                    url + "/auth/v1/user",
                    headers={"apikey": key, "Authorization": "Bearer " + access},
                    timeout=12,
                )
        if resp.status_code != 200:
            st.session_state["am_auth_error"] = "Your session expired. Request a fresh sign-in link."
            return
        user = resp.json()
        if not isinstance(user.get("id"), str) or not user["id"]:
            st.session_state["am_auth_error"] = "Your account could not be verified. Please try again."
            return
        st.session_state["am_auth_signout"] = False
        st.session_state["am_auth"] = {
            "access_token": access,
            "refresh_token": refresh,
            "user_id": user["id"],
            "email": user.get("email", ""),
        }
        st.session_state.pop("am_pending_email", None)
        st.session_state.pop("am_auth_error", None)
        st.session_state["am_new_login"] = True
        st.session_state["am_cloud_loaded_for"] = None
        if not st.session_state.get("name"):
            try:
                from supabase_auth import _table_request
                rows = _table_request("learner_profiles", params={"select": "display_name", "user_id": "eq." + user["id"], "limit": "1"})
                if rows and rows[0].get("display_name"):
                    st.session_state["name"] = rows[0]["display_name"]
            except (requests.RequestException, RuntimeError, ValueError):
                pass
    except (requests.RequestException, RuntimeError):
        st.session_state["am_auth_error"] = "The login service is temporarily unavailable. Please try again."
