"""Issue short-lived, single-use Gemini Live transcription access tokens.

The permanent GEMINI_API_KEY remains on the Streamlit server. A Live token
is returned only after an explicit user action and is constrained to the
speech-to-text model; no raw API key ever reaches the browser.
"""
import datetime as dt
import os
import requests

MODEL = "gemini-3.5-transcribe-live"
TOKEN_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/auth_tokens"


def configured_api_key():
    import streamlit as st

    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
        if key:
            return str(key).strip()
    except (FileNotFoundError, KeyError, AttributeError):
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip()


def issue_live_token():
    key = configured_api_key()
    if not key:
        raise RuntimeError(
            "Live cloud transcription requires GEMINI_API_KEY in Streamlit secrets. "
            "Your API key is never sent to the browser."
        )
    now = dt.datetime.now(dt.timezone.utc)
    expiry = (now + dt.timedelta(minutes=9)).isoformat(timespec="seconds").replace("+00:00", "Z")
    session_deadline = (now + dt.timedelta(seconds=90)).isoformat(timespec="seconds").replace("+00:00", "Z")
    request_body = {
        "uses": 1,
        "expireTime": expiry,
        "newSessionExpireTime": session_deadline,
    }
    try:
        response = requests.post(
            TOKEN_ENDPOINT,
            headers={
                "x-goog-api-key": key,
                "Content-Type": "application/json",
            },
            json=request_body,
            timeout=18,
        )
    except requests.RequestException as exc:
        raise RuntimeError("Could not reach Gemini's Live token service.") from exc
    if not response.ok:
        try:
            detail = response.json().get("error", {}).get("message", "")
        except ValueError:
            detail = ""
        raise RuntimeError(
            f"Live transcription token request returned HTTP {response.status_code}. "
            + detail[:180]
        )
    try:
        token = response.json()["name"]
    except (ValueError, KeyError) as exc:
        raise RuntimeError("The Live token service returned no valid access token.") from exc
    if not isinstance(token, str) or not token.startswith("auth_tokens/"):
        raise RuntimeError("The Live token service returned an unexpected token format.")
    return {"token": token, "model": MODEL, "expiresAt": expiry}
