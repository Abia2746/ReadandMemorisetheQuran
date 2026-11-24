"""Load learner-owned cloud profile and revision markers after verified sign-in.

Progress is read using the learner's JWT and Supabase row-level security.
Guest learning is kept separate from authenticated learning.
"""
import requests
import streamlit as st

def restore_cloud_learning():
    from supabase_auth import _table_request
    session = st.session_state.get("am_auth")
    if not session or not session.get("user_id"):
        st.session_state["am_cloud_loaded_for"] = None
        st.session_state["am_cloud_review_rows"] = []
        return
    user_id = session["user_id"]
    if st.session_state.get("am_cloud_loaded_for") == user_id:
        return
    try:
        profiles = _table_request("learner_profiles", params={
            "select": "display_name",
            "user_id": "eq." + user_id,
            "limit": "1",
        }) or []
        progress = _table_request("hifdh_progress", params={
            "select": "surah_number,ayah_number,practice_status",
            "user_id": "eq." + user_id,
            "order": "surah_number.asc,ayah_number.asc",
            "limit": "1000",
        }) or []
    except (requests.RequestException, RuntimeError, ValueError):
        st.session_state["am_cloud_load_error"] = True
        return
    # Never claim progress for a different account, nor overwrite server
    # progress with unsaved practice from a guest session.
    if st.session_state.get("am_profile_user") != user_id:
        st.session_state["results"] = {}
        st.session_state["am_profile_user"] = user_id
        st.session_state["name"] = ""
    if profiles and profiles[0].get("display_name"):
        st.session_state["name"] = str(profiles[0]["display_name"])[:80]
    st.session_state["am_cloud_review_rows"] = progress
    st.session_state["am_cloud_loaded_for"] = user_id
    st.session_state.pop("am_cloud_load_error", None)
