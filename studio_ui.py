"""Al-Mu'allim original visual studio frontend.

Streamlit Components v2 mounts directly in the app page instead of an iframe.
All user data is passed as structured JSON through data; never interpolate
user input into HTML, CSS or JavaScript source.
"""
from pathlib import Path
import hashlib
import json
import logging
import sqlite3
import time

import streamlit as st
from live_auth import configured_api_key, issue_live_token
from prayer_room import get_room_state, earn, buy, equip, unequip
from prayer_clock import room_prayer_times, CITIES
from hifdh_planner import get_state as hifdh_state, save_plan as hifdh_save, finish_today as hifdh_finish, build_calendar as hifdh_calendar

_ROOT = Path(__file__).resolve().parent
_STUDIO_CSS = (
    (_ROOT / "studio.css").read_text(encoding="utf-8")
    + "\n" + (_ROOT / "prayer_room.css").read_text(encoding="utf-8")
    + "\n" + (_ROOT / "hifdh_planner.css").read_text(encoding="utf-8")
)
# The helper/source files are composed into a single JavaScript module.
# Prayer-room scene assets load only when the user selects that tab.
_STUDIO_JS = (
    (_ROOT / "prayer_room_lounge_scene.js").read_text(encoding="utf-8")
    + "\n" + (_ROOT / "prayer_room_ui.js").read_text(encoding="utf-8")
    + "\n" + (_ROOT / "hifdh_planner_ui.js").read_text(encoding="utf-8")
    + "\n" + (_ROOT / "studio_locales.js").read_text(encoding="utf-8")
    + "\n" + (_ROOT / "studio.js").read_text(encoding="utf-8")
)

_studio = st.components.v2.component(
    "al_muallim_studio_20261120_r9_live_tracking",
    html='<div class="am-mount"></div>',
    css=_STUDIO_CSS,
    js=_STUDIO_JS,
    isolate_styles=True,
)

_LOG = logging.getLogger(__name__)


def render_studio(
    *,
    words,
    meta,
    profile,
    tracks,
    inline_audio=None,
    reciter,
    language="en",
    ui_strings=None,
    ui_catalogue=None,
    verse_translations=None,
    segments=None,
    word_counts=None,
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
    key = f"studio_r8_{meta['s']}_{meta['a']}_{meta['end']}"
    try:
        room_data = get_room_state(profile)
    except (TypeError, ValueError, sqlite3.Error, OSError) as exc:
        _LOG.exception("R6 Prayer Room storage failed during profile load")
        st.warning(
            "Prayer Room storage encountered a startup problem. "
            "The Qur'an reader can still be used. Error type: "
            + type(exc).__name__ + "."
        )
        room_data = {
            "xp": int(meta.get("xp", 0) or 0),
            "coins": 0, "streak": int(meta.get("streak", 0) or 0),
            "owned": [], "equipped": {}, "items": [],
        }
    # Planner files are isolated by Supabase account ID, not learner nickname.
    account = st.session_state.get("am_auth")
    plan_profile = ("account:" + account["user_id"]) if account else profile
    last_study_tab = st.session_state.get("_am_studio_active_tab")
    preferred_city = st.session_state.get("_am_room_prayer_city", "London")
    if preferred_city not in CITIES:
        preferred_city = "London"
    prayer_clock = room_prayer_times(preferred_city)
    try:
        plan_data = hifdh_state(plan_profile)
        calendar_data = hifdh_calendar(plan_profile) if plan_data["configured"] else ""
    except (ValueError, TypeError, sqlite3.Error, OSError) as exc:
        _LOG.exception("Noor's Hifdh plan could not be loaded")
        st.warning("Noor's saved Hifdh plan is temporarily unavailable. Qur'an reading remains accessible.")
        plan_data, calendar_data = {}, ""
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
        "reviewProfile": hashlib.sha256(plan_profile.encode("utf-8")).hexdigest(),
        "buildVersion": "2026-11-24-phrase-following",
        "hifdhPlan": plan_data,
        "hifdhCalendar": calendar_data,
        "planMessage": st.session_state.get("_am_plan_feedback", ""),
        "room": room_data,
        "prayerClock": prayer_clock,
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
        "language": language,
        "uiStrings": ui_strings or {},
        "uiCatalogue": ui_catalogue if ui_catalogue is not None else (ui_strings or {}),
        "verseTranslations": verse_translations or {},
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
    # Force an ordinary JSON tree: Streamlit component payloads must not
    # contain numpy scalars, dates, DB adapters or arbitrary Python objects.
    # Converted values cannot execute code and are not interpolated into JS.
    try:
        data = json.loads(json.dumps(data, ensure_ascii=False, default=str))
    except (TypeError, ValueError) as exc:
        _LOG.exception("R6 component JSON normalization failed")
        st.warning("Room payload could not be serialized; restoring safe defaults.")
        data["room"] = {
            "xp": 0, "coins": 0, "owned": [], "equipped": {}, "items": [],
        }
        data = json.loads(json.dumps(data, ensure_ascii=False, default=str))

    # app.py provides a basic text and audio reader if the component fails.
    result = _studio(
        data=data,
        key=key,
        on_request_cloud_change=lambda: None,
        on_room_action_change=lambda: None,
        on_plan_action_change=lambda: None,
    )
    plan_action = result.get("plan_action")
    if isinstance(plan_action, dict):
        action_id = str(plan_action.get("id", ""))[:90]
        if action_id and action_id != st.session_state.get("_am_last_plan_action"):
            st.session_state["_am_last_plan_action"] = action_id
            st.session_state["_am_studio_active_tab"] = "journey"
            try:
                action = plan_action.get("action")
                if action == "save":
                    settings = plan_action.get("settings")
                    if not isinstance(settings, dict):
                        raise ValueError("Invalid study plan.")
                    response = hifdh_save(plan_profile, settings)
                elif action == "done":
                    response = hifdh_finish(plan_profile)
                else:
                    response = {"ok": False, "message": "Unknown plan action."}
                st.session_state["_am_plan_feedback"] = response["message"]
                if response.get("ok") and account:
                    try:
                        from cloud_learning import backup_hifdh_plan
                        backup_hifdh_plan()
                        st.session_state["_am_plan_cloud_saved"] = True
                    except Exception:
                        st.session_state["_am_plan_cloud_saved"] = False
                        st.session_state["_am_plan_feedback"] += (
                            " Saved here, but cloud backup failed. Please retry after reconnecting."
                        )
            except (ValueError, TypeError, sqlite3.Error, OSError) as exc:
                st.session_state["_am_plan_feedback"] = "Plan could not be saved: " + str(exc)[:160]
            st.rerun()
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
                elif action == "set_prayer_city":
                    city = room_action.get("city")
                    if not isinstance(city, str) or city not in CITIES:
                        raise ValueError("Choose a supported UK city.")
                    st.session_state["_am_room_prayer_city"] = city
                    feedback = {
                        "ok": True,
                        "message": "Using indicative prayer-period lighting for "
                        + city + ". Verify actual prayer times with your mosque.",
                    }
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
                if account and feedback.get("ok") and action in (
                    "read", "memorise", "buy", "equip", "unequip"
                ):
                    try:
                        from cloud_learning import backup_prayer_room
                        backup_prayer_room()
                        st.session_state.pop("_am_room_sync_failed", None)
                    except Exception:
                        st.session_state["_am_room_sync_failed"] = True
                        st.session_state["_am_room_feedback"] += (
                            " Your room was saved locally, but cloud backup is pending."
                        )
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
