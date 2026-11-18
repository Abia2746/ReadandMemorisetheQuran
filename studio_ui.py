"""Al-Mu'allim original visual studio frontend.

Streamlit Components v2 mounts directly in the app page instead of an iframe.
All user data is passed as structured JSON through data; never interpolate
user input into HTML, CSS or JavaScript source.
"""
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parent
_STUDIO_CSS = (_ROOT / "studio.css").read_text(encoding="utf-8")
_STUDIO_JS = (_ROOT / "studio.js").read_text(encoding="utf-8")

_studio = st.components.v2.component(
    "al_muallim_studio",
    html='<div class="am-mount"></div>',
    css=_STUDIO_CSS,
    js=_STUDIO_JS,
    isolate_styles=True,
)


def render_studio(
    *,
    words,
    meta,
    tracks,
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
    data = {
        "words": words,
        "meta": meta,
        "audio": tracks or [],
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
    key = f"studio_{meta['s']}_{meta['a']}_{meta['end']}"
    return _studio(data=data, key=key)
