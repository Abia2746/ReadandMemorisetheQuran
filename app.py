import base64
import datetime
import hashlib
import html as _h
import io
import json
import math
import pathlib
import random
import re
import threading
import time
import wave
from collections import deque
from threading import Lock

import av
import numpy as np
import requests
import streamlit as st
from aiortc import RTCConfiguration, RTCIceServer
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
from streamlit_webrtc import AudioProcessorBase, WebRtcMode, webrtc_streamer

try:
    import streamlit.components.v1 as components
except Exception:  # newer Streamlit removes the shim; html_block() handles it
    components = None

st.set_page_config(layout="wide", page_title="Al-Mu'allim", page_icon="🕌")

# Corrected Google STUN configuration for browser media access on HTTPS hosts.
RTC_CONFIGURATION = RTCConfiguration(
    iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
)


# ---------------------------------------------------------------- configuration


def _secret(name: str, default: str = "") -> str:
    """st.secrets raises when the key is absent; a missing key must not crash boot."""
    try:
        value = st.secrets.get(name, default)
    except Exception:
        return default
    return str(value) if value is not None else default


# Read once, at import time, on the main thread. Workers must never call
# st.secrets themselves.
GEMINI_KEY = _secret("GEMINI_API_KEY")
ELEVEN_KEY = _secret("ELEVENLABS_API_KEY")
VOICE_ID = _secret("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")

GEMINI_HOST = "https://generativelanguage.googleapis.com/v1beta/models"
ELEVEN_HOST = "https://api.elevenlabs.io/v1/text-to-speech"

TAJWEED_16 = (
    "1 Izhar Halqi; 2 Idgham with ghunnah; 3 Idgham without ghunnah; 4 Iqlab; "
    "5 Ikhfa Haqiqi; 6 Ghunnah (mushaddad noon/meem); 7 Meem Sakinah rules "
    "(ikhfa/idgham/izhar shafawi); 8 Madd Tabii; 9 Madd Muttasil; 10 Madd Munfasil; "
    "11 Madd Lazim; 12 Madd Arid lil-Sukun and Madd Leen; 13 Qalqalah; "
    "14 Tafkhim and Tarqiq (heavy/light letters, Ra, Lam of Allah); "
    "15 Idgham of similar/close letters (mithlayn, mutaqaribayn, mutajanisayn); "
    "16 Waqf, ibtida, sakt and silat ha"
)

# Budgets. The deadline is a hard ceiling on the whole call, not per attempt,
# which is what stops a single ayah from hanging the page for half an hour.
TEXT_DEADLINE = 45.0
AUDIO_DEADLINE = 90.0
REQUEST_TIMEOUT = 22.0


# ---------------------------------------------------------------------- styling

_BASE_CSS = """
.stApp{background:var(--bg)!important;transition:background-color .24s}
[data-testid="stSidebar"]{background:var(--bg2)!important}
.stApp p,.stApp li,.stApp label,.stApp span,.stApp h1,.stApp h2,.stApp h3,.stApp h4,
.stApp [data-testid="stCaptionContainer"]{color:var(--word)!important}
.stApp h1,.stApp h2,.stApp h3,.stApp h4{font-family:'Cormorant Garamond',serif!important;font-weight:600!important}
.stApp p,.stApp li,.stApp label,.stApp span{font-family:Inter,system-ui,sans-serif}
div.stButton>button{background:var(--glow)!important;color:#241C17!important;border:none!important;
 border-radius:999px!important;box-shadow:none!important;font-weight:600!important;min-height:44px}
div.stButton>button:hover{filter:brightness(1.06)}
div.stButton>button *{color:#241C17!important}
.glass{background:var(--bg2);border:1px solid var(--rule);border-radius:20px;padding:18px 22px;
 margin:12px 0;box-shadow:0 8px 28px -12px rgba(36,28,23,.18)}
.ayahbox{background:transparent!important;border:0!important;box-shadow:none!important;
 direction:rtl;text-align:center;font-family:'Amiri Quran','Amiri',serif;font-size:2.4rem;
 line-height:2.2;padding:18px;color:var(--word)}
.ar-big{font-family:'Amiri Quran','Amiri',serif;font-size:2.5rem;direction:rtl;text-align:center;
 line-height:2.2;color:var(--word)}
.mi{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--dim)!important}
.ft{display:inline-block;margin:6px;padding:2px 12px;border-radius:14px;opacity:0;animation:rev .24s forwards}
.ft small{font:12px Inter;margin-left:6px}
.ft.correct{background:var(--wash);color:var(--word)}.ft.correct small{color:var(--ok)}
.ft.close{background:var(--wash);box-shadow:inset 0 -3px var(--glow);color:var(--word)}
.ft.missed{color:var(--bad)}
.ft.hide{opacity:1;animation:none;background:var(--bg2);height:1.6em;vertical-align:middle}
@keyframes rev{to{opacity:1}}
.ban{border-radius:20px;padding:16px 20px;color:#fff;margin:12px 0}
.ban p{color:#fff!important}
.cells{display:grid;grid-template-columns:repeat(10,1fr);gap:4px}
.cells i{aspect-ratio:1;border-radius:4px;display:block}
.ld{position:relative;overflow:hidden;margin:10px auto;max-width:560px;padding:16px 22px;
 border-radius:14px;color:#fff!important;font-weight:700;text-align:center;
 background:linear-gradient(135deg,var(--glow),var(--glow));box-shadow:0 0 24px var(--wash)}
.ld .ind{position:absolute;bottom:0;left:-35%;width:35%;height:5px;background:rgba(255,255,255,.9);
 animation:slide 1.2s ease-in-out infinite}
@keyframes slide{to{left:100%}}
[data-testid="stStatusWidget"]{display:none!important}
@media(prefers-reduced-motion:reduce){
  .ft{animation:none;opacity:1}
  .ld .ind{animation:none;left:0;width:100%;opacity:.6}
}
"""

_FONTS = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Amiri+Quran&family=Cormorant+Garamond:wght@500;600&family=Inter:wght@400;500&display=swap');"
)

THEMES = {
    "White":  dict(bg="#FDFBF6", bg2="#F4EEE1", word="#241C17", dim="#7A6A5C",
                    glow="#C9A227", rule="rgba(36,28,23,.10)", wash="rgba(184,145,47,.16)",
                    ok="#2E7D5B", bad="#C0453A"),
    "Brown":  dict(bg="#241B15", bg2="#3A2C22", word="#F4E8D2", dim="#A08D74",
                    glow="#C9A227", rule="rgba(244,232,210,.14)", wash="rgba(201,162,39,.22)",
                    ok="#7FD1A8", bad="#FF8A7E"),
    "Night":  dict(bg="#0A0E18", bg2="#151B2B", word="#F3EEE2", dim="#8390A6",
                    glow="#D9B45B", rule="rgba(243,238,226,.12)", wash="rgba(217,180,91,.20)",
                    ok="#7FD1A8", bad="#FF8A7E"),
    "Black":  dict(bg="#000000", bg2="#0A0A0A", word="#FFFFFF", dim="#8A8A8A",
                    glow="#FFD166", rule="rgba(255,255,255,.12)", wash="rgba(255,209,102,.18)",
                    ok="#7FD1A8", bad="#FF8A7E"),
}


def theme() -> dict:
    return THEMES.get(st.session_state.get("cfg_theme", "White"), THEMES["White"])


def _stars() -> str:
    rnd = random.Random(7)
    spots = ",".join(
        f"{rnd.randint(0, 100)}vw {rnd.randint(0, 100)}vh 0 {rnd.choice([0, 0, 1])}px "
        f"rgba(243,238,226,{rnd.uniform(.25, .9):.2f})"
        for _ in range(140)
    )
    return (
        ".stApp::before{content:'';position:fixed;left:0;top:0;width:1px;height:1px;"
        "box-shadow:" + spots + ";animation:tw 7s ease-in-out infinite;"
        "pointer-events:none;z-index:0}"
        "@keyframes tw{0%,100%{opacity:.5}50%{opacity:1}}"
        "@media(prefers-reduced-motion:reduce){.stApp::before{animation:none}}"
    )


def apply_theme() -> None:
    """Variables first, then the rules that consume them."""
    t = theme()
    name = st.session_state.get("cfg_theme", "White")
    variables = (
        ":root{"
        f"--bg:{t['bg']};--bg2:{t['bg2']};--word:{t['word']};--dim:{t['dim']};"
        f"--wash:{t['wash']};--glow:{t['glow']};--rule:{t['rule']};"
        f"--ok:{t['ok']};--bad:{t['bad']};"
        "}"
    )
    stars = _stars() if name == "Night" else ""
    st.markdown(
        "<style>" + _FONTS + variables + _BASE_CSS + stars + "</style>",
        unsafe_allow_html=True,
    )


_HTML_CACHE = pathlib.Path(__file__).parent / ".noor_html"


def html_block(markup: str, height: int = 420, scrolling: bool = False) -> None:
    """One place that emits raw HTML, so the deprecation is handled once.

    `st.iframe` is the documented replacement for `components.html`, which is now
    past its removal date. It takes a path, so the markup is written to a file
    named by its own hash — stable across reruns, so it is written once.
    """
    if hasattr(st, "iframe"):
        try:
            _HTML_CACHE.mkdir(exist_ok=True)
            target = _HTML_CACHE / (hashlib.sha1(markup.encode("utf-8")).hexdigest()[:20] + ".html")
            if not target.exists():
                target.write_text(markup, encoding="utf-8")
            st.iframe(target, height=height)
            return
        except Exception:
            pass

    if components is not None and hasattr(components, "html"):
        try:
            components.html(markup, height=height, scrolling=scrolling)
            return
        except Exception:
            pass

    if hasattr(st, "html"):
        st.html(markup)
        st.caption("This Streamlit build cannot run the embedded player; the audio controls "
                   "elsewhere on this page still work.")


# ------------------------------------------------------------------ session state

_DEFAULTS = {
    "user_name": "",
    "app_phase": "onboarding",
    "current_surah": 2,
    "current_ayah": 57,
    "listens": {},
    "chat": [],
    "tafsir_text": {},
    "last_analysis": {},
    "lessons": {},
    "coach": [],
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


class LiveAudioProcessor(AudioProcessorBase):
    """Measure the live microphone signal without blocking the app thread."""

    def __init__(self):
        self._lock = Lock()
        self._rms = 0.0
        self._history = deque(maxlen=50)

    def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
        samples = frame.to_ndarray()
        if samples.size == 0:
            return frame

        if samples.ndim == 2:
            values = samples.mean(axis=1)
        else:
            values = samples

        values = np.asarray(values, dtype=np.float32)
        if np.issubdtype(values.dtype, np.integer):
            info = np.iinfo(values.dtype)
            values = values.astype(np.float32)
            values /= max(abs(info.min), info.max)

        rms = float(np.sqrt(np.mean(np.square(values)))) if values.size else 0.0
        with self._lock:
            self._rms = rms
            self._history.append(rms)
        return frame

    def snapshot(self):
        with self._lock:
            return self._rms, list(self._history)


# ------------------------------------------------------------------------ Gemini

# The rest of the file is unchanged below this point.
# The inserted WebRTC code is added later in the UI before the app renders the tabs.
