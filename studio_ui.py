"""Al-Mu'allim original visual studio frontend.

Streamlit Components v2 mounts directly in the app page instead of an iframe.
All user data is passed as structured JSON through data; never interpolate
user input into HTML, CSS or JavaScript source.
"""
from pathlib import Path
import time

import streamlit as st
from live_auth import configured_api_key, issue_live_token
from prayer_room import get_room_state, earn, buy, equip, unequip

_ROOT = Path(__file__).resolve().parent
_STUDIO_CSS = (
    (_ROOT / "studio.css").read_text(encoding="utf-8")
    + "\n" + (_ROOT / "prayer_room.css").read_text(encoding="utf-8")
)
# The helper/source files are composed into a single JavaScript module.
# Prayer-room scene assets load only when the user selects that tab.
_STUDIO_JS = (
    (_ROOT / "prayer_room_scene.js").read_text(encoding="utf-8")
    + "\n" + (_ROOT / "prayer_room_ui.js").read_text(encoding="utf-8")
    + "\n" + (_ROOT / "studio.js").read_text(encoding="utf-8")
)

_studio = st.components.v2.component(
    "al_muallim_studio_20261119_r6",
    html='<div class="am-mount"></div>',
    css=_STUDIO_CSS,
    js=_STUDIO_JS,
    isolate_styles=True,
)


def render_studio(
    *,
    words,
    meta,
    profile,
    tracks,
    inline_audio=None,
    reciter,
    segments,
    word_counts,
    mode="full",
    teacher_name="Ustadha Noor",
    avatar="",
    surah_arabic="",
    surah_english="",
    review=None,
):
    """Mount the complete Qur'an classroom without iframe microphone restrictions.

    The browser recogniser follows approximate words; it does not claim to
    grade the pronunciation of individual vowels or all Tajweed rules.
    """
    reviewed = sum(
        1 for x in (review or {}).get("states", [])
        if x in {"good", "review"}
    )
    key = f"studio_r6_{meta['s']}_{meta['a']}_{meta['end']}"
    room_data = get_room_state(profile)
    last_study_tab = st.session_state.get("_am_studio_active_tab")
    cloud_session = st.session_state.get("_am_live_cloud_session")
    cloud_view = st.session_state.get("_am_live_cloud_view", {})
    # Tokens are tied to exactly one selected passage and expire quickly.
    if cloud_session and (
        time.time() >= cloud_session.get("startUntil", 0)
        or cloud_session.get("passage") != key
    ):
        cloud_session = None
        st.session_state.pop("_am_live_cloud_session", None)
    data = {
        "buildVersion": "2026-11-19-r6",
        "room": room_data,
        "roomMessage": st.session_state.get("_am_room_feedback", ""),
        "cloudAvailable": bool(configured_api_key()),
        "cloudSession": cloud_session,
        "cloudError": st.session_state.get("_am_live_cloud_error", ""),
        "resumeTab": last_study_tab or cloud_view.get("tab"),
        "resumeWord": cloud_view.get("cursor", -1),
        "words": words,
        "meta": meta,
        "audio": tracks or [],
        "inlineAudio": inline_audio or [],
        "reciter": reciter,
        "trackWordCounts": word_counts or [],
        "segments": segments or [],
        "mode": mode,
        "teacherName": teacher_name,
        "avatar": avatar,
        "surahArabic": surah_arabic,
        "surahEnglish": surah_english,
        "reviewed": reviewed,
        "states": (review or {}).get("states", []),
        "letterResults": (review or {}).get("letter_results", {}),
        "wordFeedback": (review or {}).get("word_feedback", {}),
    }
    result = _studio(
        data=data,
        key=key,
        on_request_cloud_change=lambda: None,
        on_room_action_change=lambda: None,
    )
    room_action = result.get("room_action")
    if isinstance(room_action, dict):
        action_id = str(room_action.get("id", ""))[:90]
        if action_id and action_id != st.session_state.get("_am_last_room_action"):
            st.session_state["_am_last_room_action"] = action_id
            chosen_tab = room_action.get("tab", "room")
            if chosen_tab not in ("room", "read", "cover"):
                chosen_tab = "room"
            st.session_state["_am_studio_active_tab"] = chosen_tab
            action = room_action.get("action")
            try:
                if action in ("read", "memorise"):
                    if (
                        type(room_action.get("surah")) is not int
                        or room_action["surah"] != int(meta["s"])
                        or type(room_action.get("ayah")) is not int
                        or not int(meta["a"]) <= room_action["ayah"] <= int(meta["end"])
                    ):
                        raise ValueError("The selected verse is outside the current passage.")
                    feedback = earn(
                        profile, action, int(meta["s"]), room_action["ayah"]
                    )
                elif action in ("buy", "equip"):
                    item_id = room_action.get("item_id")
                    if not isinstance(item_id, str) or len(item_id) > 60:
                        raise ValueError("Invalid decoration.")
                    feedback = buy(profile, item_id) if action == "buy" else equip(profile, item_id)
                elif action == "unequip":
                    category = room_action.get("category")
                    if not isinstance(category, str) or len(category) > 50:
                        raise ValueError("Invalid decoration slot.")
                    feedback = unequip(profile, category)
                else:
                    feedback = {"ok": False, "message": "This room action is not supported."}
                st.session_state["_am_room_feedback"] = feedback["message"]
            except (ValueError, OSError, RuntimeError) as exc:
                st.session_state["_am_room_feedback"] = str(exc)[:200]
            st.rerun()
    request = result.get("request_cloud")
    if isinstance(request, dict):
        request_id = str(request.get("id", ""))[:80]
        if request_id and request_id != st.session_state.get("_am_live_request_id"):
            st.session_state["_am_live_request_id"] = request_id
            requested_tab = request.get("tab", "read")
            if requested_tab not in ("read", "cover"):
                requested_tab = "read"
            cursor = request.get("cursor", -1)
            if not isinstance(cursor, int) or isinstance(cursor, bool):
                cursor = -1
            st.session_state["_am_live_cloud_view"] = {
                "tab": requested_tab,
                "cursor": max(-1, min(cursor, len(words) - 1)),
            }
            # Limit accidental repeated requests from the same browser session.
            now = time.time()
            attempts = [
                t for t in st.session_state.get("_am_live_request_times", [])
                if now - t < 3600
            ]
            attempts.append(now)
            st.session_state["_am_live_request_times"] = attempts
            if len(attempts) > 8:
                st.session_state["_am_live_cloud_error"] = (
                    "This session has requested too many live connections. "
                    "Try again later or use Browser recognition."
                )
                st.session_state.pop("_am_live_cloud_session", None)
            else:
                try:
                    token = issue_live_token()
                    token["id"] = request_id
                    token["passage"] = key
                    token["startUntil"] = now + 85
                    st.session_state["_am_live_cloud_session"] = token
                    st.session_state["_am_live_cloud_error"] = ""
                except RuntimeError as exc:
                    st.session_state.pop("_am_live_cloud_session", None)
                    st.session_state["_am_live_cloud_error"] = str(exc)
            st.rerun()
    return result
