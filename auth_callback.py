"""Supabase default magic-link callback for Streamlit Components v2.

The frontend safely captures the URL fragment delivered by Supabase Auth.
It removes the fragment before sending the tokens over Streamlit's component
channel; the Python backend independently validates the user at Supabase.
No login information is logged or put in query parameters.
"""
import requests
import streamlit as st

MAGIC_LINK_JS = r"""
export default function({setTriggerValue}) {
  const fragment = window.location.hash;
  if (!fragment) return;
  const values = new URLSearchParams(fragment.slice(1));
  const access = values.get("access_token");
  const authError = values.get("error");
  const authCode = values.get("error_code");
  const refresh = values.get("refresh_token");
  const tokenType = values.get("token_type");
  // Clear the browser URL before anything else handles the token.
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
  if (authError) {
    setTriggerValue("auth_error", authCode === "otp_expired" ? "expired" : "failed");
    return;
  }
  if (access && refresh && tokenType === "bearer") {
    setTriggerValue("tokens", {access_token: access, refresh_token: refresh});
  }
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
    result = callback(key="am_magic_link_callback", on_tokens_change=lambda: None,
                      on_auth_error_change=lambda: None)
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
        if resp.status_code != 200:
            st.session_state["am_auth_error"] = "Your sign-in link expired or could not be verified. Request a fresh link."
            return
        user = resp.json()
        if not isinstance(user.get("id"), str) or not user["id"]:
            st.session_state["am_auth_error"] = "Your account could not be verified. Please try again."
            return
        st.session_state["am_auth"] = {
            "access_token": access,
            "refresh_token": refresh,
            "user_id": user["id"],
            "email": user.get("email", ""),
        }
        st.session_state.pop("am_pending_email", None)
        st.session_state.pop("am_auth_error", None)
        st.session_state["am_new_login"] = True
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
