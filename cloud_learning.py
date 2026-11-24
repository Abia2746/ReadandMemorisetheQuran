"""Authenticated user-owned study preferences and Hifdh plan backup.

RLS enforces ownership. Never accept a user_id from the browser.
Only purpose-specific JSON settings are stored, not authentication tokens,
microphone recordings, private messages, or AI-generated judgement.
"""
import requests
import streamlit as st
from supabase_auth import _table_request

PREFERENCE_KEYS = {
    "teacher_gender", "strictness", "recite_from_memory",
    "quran_language", "quran_nav_surah", "quran_nav_start",
    "quran_nav_end", "quran_nav_reciter",
}
ALLOWED_TEACHERS = {"Female", "Male"}
ALLOWED_STRICTNESS = {"Lenient", "Balanced", "Strict"}
MAX_PREFS = 8192


def planner_key(user_id):
    return "account:" + str(user_id)


def _valid_preferences(raw):
    """Ignore malformed/unknown fields from old clients."""
    if not isinstance(raw, dict):
        return {}
    result = {}
    if raw.get("teacher_gender") in ALLOWED_TEACHERS:
        result["teacher_gender"] = raw["teacher_gender"]
    if raw.get("strictness") in ALLOWED_STRICTNESS:
        result["strictness"] = raw["strictness"]
    if type(raw.get("recite_from_memory")) is bool:
        result["recite_from_memory"] = raw["recite_from_memory"]
    language = raw.get("quran_language")
    if isinstance(language, str) and 1 <= len(language) <= 8 and language.isalpha():
        result["quran_language"] = language.lower()
    from hifdh_planner import AYAHS
    surah = raw.get("quran_nav_surah")
    if type(surah) is int and 1 <= surah <= 114:
        result["quran_nav_surah"] = surah
        start = raw.get("quran_nav_start")
        end = raw.get("quran_nav_end")
        if type(start) is int and 1 <= start <= AYAHS[surah]:
            result["quran_nav_start"] = start
            if type(end) is int and start <= end <= min(AYAHS[surah], start + 9):
                result["quran_nav_end"] = end
    reciter = raw.get("quran_nav_reciter")
    if isinstance(reciter, str) and 1 <= len(reciter) <= 75:
        result["quran_nav_reciter"] = reciter
    return result


def get_preference_values():
    values = {key: st.session_state.get(key) for key in PREFERENCE_KEYS}
    return _valid_preferences(values)


def save_preferences():
    session = st.session_state.get("am_auth")
    if not session:
        return False
    values = get_preference_values()
    _table_request(
        "learner_settings", "POST",
        [{"user_id": session["user_id"], "preferences": values}],
        params={"on_conflict": "user_id"}, upsert=True,
    )
    st.session_state["am_cloud_preferences_snapshot"] = values
    return True


def restore_preferences(user_id):
    rows = _table_request(
        "learner_settings", params={
            "select": "preferences", "user_id": "eq." + user_id, "limit": "1"
        },
    ) or []
    preferences = _valid_preferences(rows[0].get("preferences", {})) if rows else {}
    st.session_state["am_cloud_preferences_snapshot"] = preferences
    for key, value in preferences.items():
        st.session_state[key] = value
        if key == "quran_nav_surah": st.session_state["surah"] = value
        elif key == "quran_nav_start": st.session_state["ayah"] = value
        elif key == "quran_nav_end": st.session_state["end_ayah"] = value
        elif key == "quran_nav_reciter": st.session_state["selected_reciter"] = value
    return bool(rows)


def restore_hifdh_plan(user_id):
    """Fetch one account-owned cloud snapshot into its isolated SQLite cache."""
    from hifdh_planner import import_cloud_snapshot
    rows = _table_request(
        "learner_hifdh_plans", params={
            "select": "plan,completed,sessions",
            "user_id": "eq." + user_id, "limit": "1",
        },
    ) or []
    # No cloud snapshot: no imported plan and no silent upload of guest data.
    if rows:
        import_cloud_snapshot(planner_key(user_id), rows[0])
    return bool(rows)


def backup_hifdh_plan():
    """Called only after a successful local planner mutation."""
    from hifdh_planner import export_cloud_snapshot
    session = st.session_state.get("am_auth")
    if not session:
        return False
    user_id = session["user_id"]
    snapshot = export_cloud_snapshot(planner_key(user_id))
    _table_request(
        "learner_hifdh_plans", "POST",
        [{"user_id": user_id, **snapshot}],
        params={"on_conflict": "user_id"}, upsert=True,
    )
    return True
