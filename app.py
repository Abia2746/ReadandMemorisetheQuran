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

import numpy as np
import requests
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

try:
    import streamlit.components.v1 as components
except Exception:  # newer Streamlit removes the shim; html_block() handles it
    components = None

st.set_page_config(layout="wide", page_title="Al-Mu'allim", page_icon="🕌")


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


# ------------------------------------------------------------------------ Gemini

def audio_part(data: bytes, mime: str) -> dict:
    return {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}}


@st.cache_data(ttl=3600, show_spinner=False)
def list_models() -> list:
    if not GEMINI_KEY:
        return []
    try:
        r = requests.get(
            GEMINI_HOST, headers={"x-goog-api-key": GEMINI_KEY},
            params={"pageSize": 200}, timeout=15,
        )
        r.raise_for_status()
        payload = r.json()
    except Exception:
        return []

    skip = ("image", "tts", "live", "embed", "audio", "robotics", "computer", "vision")
    out = []
    for m in payload.get("models", []):
        name = m.get("name", "").split("/")[-1]
        methods = m.get("supportedGenerationMethods", [])
        if not name or "generateContent" not in methods:
            continue
        if any(token in name for token in skip):
            continue
        out.append(name)
    return out


def _version(name: str) -> float:
    found = re.findall(r"\d+(?:\.\d+)?", name)
    try:
        return float(found[0]) if found else 0.0
    except ValueError:
        return 0.0


def pick_models(pro: bool) -> list:
    """Ordered candidates. Never a bare list with one unverified name in it."""
    pool = list_models()
    pro_models = sorted([m for m in pool if "pro" in m], key=_version, reverse=True)
    flash = sorted([m for m in pool if "flash" in m and "lite" not in m], key=_version, reverse=True)
    lite = sorted([m for m in pool if "lite" in m], key=_version, reverse=True)

    ordered = (pro_models[:2] + flash[:2] + lite[:1]) if pro else (flash[:2] + pro_models[:1] + lite[:1])
    if ordered:
        return ordered
    # Listing failed (no key, offline, quota). Fall back to names that have
    # existed for a long time rather than inventing one.
    return ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"] if not pro else \
           ["gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro"]


def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}


_ERRORS: list = []
_ERR_LOCK = threading.Lock()


def _record(message: str) -> None:
    """Workers cannot touch session_state; they queue a message instead."""
    with _ERR_LOCK:
        _ERRORS.append(message)


def _drain() -> list:
    with _ERR_LOCK:
        items = list(_ERRORS)
        _ERRORS.clear()
    return items


def call_gemini(parts: list, expect_json: bool = False, pro: bool = False) -> object:
    """One request per candidate model, inside a hard wall-clock deadline.

    Returns "" (or {}) on failure, and records the reason in `last_error` so the
    UI can say something true instead of showing an empty card.
    """
    if not GEMINI_KEY:
        _record("No Gemini key is configured. Add GEMINI_API_KEY in Streamlit → Settings → Secrets.")
        return {} if expect_json else ""

    payload = {"contents": [{"parts": parts}]}
    if expect_json:
        payload["generationConfig"] = {"responseMimeType": "application/json"}

    deadline = time.time() + (AUDIO_DEADLINE if any("inline_data" in p for p in parts) else TEXT_DEADLINE)
    errors = []

    for model in pick_models(pro):
        remaining = deadline - time.time()
        if remaining <= 1:
            errors.append("deadline reached")
            break
        url = f"{GEMINI_HOST}/{model}:generateContent"
        try:
            r = requests.post(
                url,
                headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_KEY},
                json=payload,
                timeout=min(REQUEST_TIMEOUT, remaining),
            )
        except requests.Timeout:
            errors.append(f"{model}: timeout")
            continue
        except Exception as exc:
            errors.append(f"{model}: {type(exc).__name__}")
            continue

        if r.status_code == 200:
            try:
                body = r.json()
                chunk = body["candidates"][0]["content"]["parts"]
                text = "".join(p.get("text", "") for p in chunk if not p.get("thought")).strip()
            except (KeyError, IndexError, ValueError):
                errors.append(f"{model}: unreadable response")
                continue
            if not text:
                errors.append(f"{model}: empty")
                continue
            return _extract_json(text) if expect_json else text

        if r.status_code in (400, 403):
            # Bad key or bad request: trying other models will not help.
            detail = r.text[:180].replace("\n", " ")
            _record(f"Gemini rejected the request ({r.status_code}). {detail}")
            return {} if expect_json else ""
        if r.status_code == 404:
            errors.append(f"{model}: not available")
            continue
        if r.status_code == 429:
            errors.append(f"{model}: rate limited")
            time.sleep(min(2.0, max(0.0, deadline - time.time())))
            continue
        errors.append(f"{model}: HTTP {r.status_code}")

    _record("The language model did not answer. " + "; ".join(errors[:4]))
    return {} if expect_json else ""


def speak(text: str):
    """ElevenLabs. Returns bytes, None, or an error string. Never touches st."""
    if not ELEVEN_KEY:
        return "Spoken replies need ELEVENLABS_API_KEY in Streamlit secrets."
    clean = (text or "").strip()
    if not clean:
        return None
    try:
        r = requests.post(
            f"{ELEVEN_HOST}/{VOICE_ID}",
            headers={
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": ELEVEN_KEY,
            },
            json={
                "text": clean[:1500],
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.6, "similarity_boost": 0.8},
            },
            timeout=45,
        )
        if r.status_code == 200 and len(r.content) > 1000:
            return r.content
        return f"Voice service returned {r.status_code}."
    except Exception as exc:
        return f"Voice error: {type(exc).__name__}"


# -------------------------------------------------------------------- Qur'an data
# Verified shapes:
#   api.alquran.cloud/v1/ayah/{s}:{a}/quran-uthmani  -> data.text
#   api.quran.com/api/v4/verses/by_key/{s}:{a}       -> verse.words[].text_uthmani
#   api.quran.com/api/v4/tafsirs/169/by_ayah/{s}:{a} -> tafsir.text
#   everyayah.com/data/{reciter}/{sss}{aaa}.mp3

RECITERS = [
    ("Yasser_Ad-Dussary_128kbps", "Sheikh Yasser Al-Dosari"),
    ("Alafasy_128kbps", "Mishary Rashid Alafasy"),
    ("Husary_128kbps", "Mahmoud Khalil Al-Husary"),
]


@st.cache_data(show_spinner=False)
def fetch_verse(s: int, a: int) -> str:
    try:
        r = requests.get(f"https://api.alquran.cloud/v1/ayah/{s}:{a}/quran-uthmani", timeout=15)
        return r.json()["data"]["text"]
    except Exception:
        return ""


@st.cache_data(show_spinner=False)
def fetch_translation(s: int, a: int) -> str:
    try:
        r = requests.get(f"https://api.alquran.cloud/v1/ayah/{s}:{a}/en.sahih", timeout=15)
        return r.json()["data"]["text"]
    except Exception:
        return ""


@st.cache_data(show_spinner=False)
def fetch_words(s: int, a: int) -> list:
    try:
        r = requests.get(
            f"https://api.quran.com/api/v4/verses/by_key/{s}:{a}",
            params={"words": "true", "word_fields": "text_uthmani,transliteration", "language": "en"},
            timeout=20,
        )
        rows = r.json()["verse"]["words"]
    except Exception:
        return []

    out = []
    for w in rows:
        if w.get("char_type_name") != "word":
            continue
        tr = w.get("transliteration") or {}
        en = w.get("translation") or {}
        out.append({
            "ar": w.get("text_uthmani", ""),
            "tr": tr.get("text", "") if isinstance(tr, dict) else "",
            "en": re.sub(r"<[^>]+>", "", en.get("text", "") if isinstance(en, dict) else "").strip(),
        })
    return out


@st.cache_data(show_spinner=False)
def fetch_reciter(s: int, a: int) -> tuple:
    """Try reciters in order. The old fallback used the same URL as the primary,
    so it re-requested the identical file and could never recover."""
    stem = f"{s:03d}{a:03d}"
    for folder, label in RECITERS:
        url = f"https://everyayah.com/data/{folder}/{stem}.mp3"
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200 and len(r.content) > 2000:
                return url, r.content, label
        except Exception:
            continue

    # Last resort: alquran.cloud's per-ayah CDN link.
    try:
        meta = requests.get(
            f"https://api.alquran.cloud/v1/ayah/{s}:{a}/ar.alafasy", timeout=15
        ).json()["data"]["audio"]
        audio = requests.get(meta, timeout=25)
        if audio.status_code == 200 and len(audio.content) > 2000:
            return meta, audio.content, "Mishary Alafasy (CDN)"
    except Exception:
        pass
    return None, b"", ""


@st.cache_data(show_spinner=False)
def fetch_ibn_kathir(s: int, a: int) -> str:
    try:
        r = requests.get(f"https://api.quran.com/api/v4/tafsirs/169/by_ayah/{s}:{a}", timeout=20)
        text = re.sub(r"<[^>]+>", " ", r.json()["tafsir"]["text"])
        return re.sub(r"\s+", " ", text).strip()[:7000]
    except Exception:
        return ""


# ------------------------------------------------------------ word-by-word player

_PLAYER = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body{margin:0;font-family:Inter,system-ui,sans-serif;background:transparent;color:@@WORD@@}
#w{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;direction:rtl}
.c{padding:8px 12px;border-radius:14px;text-align:center;background:@@CARD@@;
   border:1px solid @@RULE@@;transition:all .16s ease}
.ar{font-family:'Amiri Quran',Amiri,serif;font-size:2rem;line-height:1.9;color:@@WORD@@}
.tr{font-size:.78rem;color:@@DIM@@;font-style:italic}
.en{font-size:.95rem;color:@@WORD@@;opacity:.9}
.on{background:@@WASH@@;transform:scale(1.06);box-shadow:0 0 18px @@GLOW@@55}
.bar{display:flex;align-items:center;gap:12px;margin-top:16px;justify-content:center}
#n{color:@@WORD@@;font-weight:600;font-size:13px;letter-spacing:.02em}
button{font:inherit;border-radius:999px;border:1px solid @@RULE@@;background:@@CARD@@;
  color:@@WORD@@;padding:7px 14px;cursor:pointer;min-width:52px}
input[type=range]{width:170px;accent-color:@@GLOW@@}
audio{display:none}
@media(prefers-reduced-motion:reduce){.on{transform:none}}
</style></head><body>
<div id="w"></div>
<div class="bar">
  <button id="pp">Play</button>
  <button id="sp">1&times;</button>
  <span aria-hidden="true">&#128264;</span>
  <input id="v" type="range" min="0" max="100" value="80" aria-label="Volume">
  <span id="n">Listen 1 of 5</span>
</div>
<audio id="a" preload="auto" src="@@URL@@"></audio>
<script>
const W = @@WORDS@@;
const a = document.getElementById('a');
const box = document.getElementById('w');
const label = document.getElementById('n');
const diacritics = /[\u064B-\u0652\u0670\u06D6-\u06ED\u0640]/g;

const els = W.map(function (w) {
  const d = document.createElement('div');
  d.className = 'c';
  const ar = document.createElement('div'); ar.className = 'ar'; ar.textContent = w.ar;
  d.appendChild(ar);
  if (w.tr) { const t = document.createElement('div'); t.className = 'tr'; t.textContent = w.tr; d.appendChild(t); }
  if (w.en) { const e = document.createElement('div'); e.className = 'en'; e.textContent = w.en; d.appendChild(e); }
  box.appendChild(d);
  return d;
});

/* Weight each word by the letters it takes to pronounce, not its raw length:
   a long word with a short sound is what makes naive timing drift. */
function weight(w) { return Math.max(1, (w.ar || '').replace(diacritics, '').length); }

let cum = [];
function build() {
  const dur = a.duration;
  if (!isFinite(dur) || dur <= 0) { cum = []; return; }
  const lead = dur * 0.04, span = dur * 0.90;
  const total = W.reduce(function (s, w) { return s + weight(w); }, 0) || 1;
  let t = lead;
  cum = W.map(function (w) { t += span * weight(w) / total; return t; });
}

a.addEventListener('loadedmetadata', build);
a.addEventListener('durationchange', build);

function paint(i) {
  els.forEach(function (e, k) { e.classList.toggle('on', k === i); });
}

a.addEventListener('timeupdate', function () {
  if (!cum.length) build();
  if (!cum.length) return;
  const t = a.currentTime;
  let idx = -1;
  for (let i = 0; i < cum.length; i++) { if (t < cum[i]) { idx = i; break; } }
  paint(a.ended ? -1 : idx);
});

/* Volume through a gain node so it also works on iOS, where element.volume is read-only. */
let gain = null;
try {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  const ctx = new Ctx();
  gain = ctx.createGain();
  ctx.createMediaElementSource(a).connect(gain);
  gain.connect(ctx.destination);
  const vs = document.getElementById('v');
  gain.gain.value = vs.value / 100;
  vs.addEventListener('input', function () { gain.gain.value = vs.value / 100; ctx.resume(); });
  a.addEventListener('play', function () { ctx.resume(); });
} catch (e) { /* Safari can refuse; playback still works at system volume */ }

const speeds = [1, 1.25, 0.75];
let si = 0;
document.getElementById('sp').addEventListener('click', function () {
  si = (si + 1) % speeds.length;
  a.playbackRate = speeds[si];
  this.innerHTML = speeds[si] + '&times;';
});

document.getElementById('pp').addEventListener('click', function () {
  if (a.paused) { a.play(); } else { a.pause(); }
});

let listens = 0;
function upd() { label.textContent = listens >= 5 ? 'All 5 listens complete' : 'Listen ' + (listens + 1) + ' of 5'; }
a.addEventListener('play', function () { this.dataset.playing = '1'; document.getElementById('pp').textContent = 'Pause'; });
a.addEventListener('pause', function () { document.getElementById('pp').textContent = 'Play'; });

/* Auto-repeat until five listens, then stop and say so. */
a.addEventListener('ended', function () {
  paint(-1);
  listens += 1;
  if (listens < 5) { upd(); setTimeout(function () { a.play(); }, 1400); }
  else { upd(); }
});
upd();
</script></body></html>"""


def player_html(words: list, data_uri: str) -> str:
    t = theme()
    out = _PLAYER
    for token, value in (
        ("@@WORD@@", t["word"]),
        ("@@DIM@@", t["dim"]),
        ("@@RULE@@", t["rule"]),
        ("@@WASH@@", t["wash"]),
        ("@@GLOW@@", t["glow"]),
        ("@@CARD@@", t["bg2"]),
    ):
        out = out.replace(token, value)
    out = out.replace("@@URL@@", data_uri)
    # json.dumps escapes quotes and non-ASCII safely; </script> inside the data
    # would break the tag, so it is escaped explicitly.
    out = out.replace("@@WORDS@@", json.dumps(words, ensure_ascii=False).replace("</", "<\\/"))
    return out


# --------------------------------------------------------------- AI teacher work

@st.cache_data(ttl=900, show_spinner=False)
def explain_tafsir(verse_ref: str, verse: str, source: str) -> str:
    prompt = f"""You are a warm, learned Qur'an teacher. Explain {verse_ref} ({verse}) to a student in clear English, about 250 words.
Base the explanation ONLY on the tafsir source below, and say it comes from Ibn Kathir (abridged). Structure it as: the context of the verse, what it means, and two or three lessons to take to heart.
If the source is empty or unrelated, say plainly that the source could not be loaded and keep to well-established basics. Do not invent narrations or attribute sayings you cannot see in the source.

SOURCE:
{source or '(unavailable)'}"""
    return call_gemini([{"text": prompt}])


@st.cache_data(ttl=900, show_spinner=False)
def tajweed_rules(verse: str) -> str:
    return call_gemini([{
        "text": "List every tajweed rule that truly applies in this ayah, word by word in order, one short line each: "
                "word (Arabic + transliteration) - rule - what to do (counts for madd, etc). Use these 16 categories, "
                "starting each line with its category number, and include only categories that actually occur: "
                + TAJWEED_16 + ". No invention, no markdown symbols.\n\n" + verse
    }], pro=True)


@st.cache_data(ttl=900, show_spinner=False)
def recitation_lesson(verse: str, rules: str, mp3: bytes, reciter: str) -> str:
    prompt = f"""You are a master Qur'an reciter-teacher. Listen to this reference recitation by {reciter} of: {verse}
Teach it step by step in plain English (Arabic in script plus transliteration), no markdown symbols, with these capitalised sections:
PHRASES: split into natural phrases; for each give transliteration, tricky letters (makharij) and tajweed rules with counts, using this checklist: {rules}
BREATH MAP: where the reciter breathes or pauses, roughly how many seconds each phrase lasts, the best places for a beginner to breathe, and safe waqf points.
PACING: three short tips for steady air (long madds, ghunnah, ending the ayah).
COMMON MISTAKES: three typical errors for this ayah.
Only describe what you can hear or what the rules require; say where you are unsure."""
    return call_gemini([{"text": prompt}, audio_part(mp3, "audio/mpeg")], pro=True)


@st.cache_data(ttl=900, show_spinner=False)
def analyse(verse: str, ref_mp3: bytes, student_wav: bytes, reciter: str,
            rules: str, strict: str, heard: str) -> dict:
    """Compare the reference and the student. Pure: every input is an argument."""
    prompt = f"""You are an expert Tajweed teacher. The student recited this ayah from memory: {verse}
Clip 1 is the reference by {reciter}. Clip 2 is the student.
Compare word by word: harakat, sukoon, madd length, ghunnah, idgham/ikhfa/iqlab/izhar, qalqalah, makharij, waqf. Also say if any words were skipped or wrong (memorisation errors).
Write in English; Arabic words in script plus transliteration. Report only what you can actually hear; admit uncertainty; never invent mistakes. If the clip is silent or the wrong ayah, say so.
Checklist of tajweed rules in this ayah:
{rules}
Also compare breath control (where each reciter breathes or pauses, and whether the student's breath lasted each phrase). Marking strictness: {strict}. Independent ASR transcript of the student (cross-check only; trust your own hearing if they differ): {heard or "(none)"}. First write in heard_text, in Arabic script, exactly the words the student recited as you hear them (use [unclear] where you cannot tell). If you hear no clear recitation, set heard_text to "" and overall_score to 0 and give no word feedback; never invent mistakes. Judge each checklist rule separately, citing roughly where (seconds) you heard it in each clip, with a confidence level.
Return JSON only: {{"overall_score":int,"rules_check":[{{"rule":"","word":"","verdict":"correct|partly|missed|unclear","evidence":"","confidence":"high|medium|low"}}],"heard_text":"","breath":{{"reference":"","student":"","tip":""}},"spoken_summary":"max 60 words, warm","words":[{{"word":"","status":"good|needs_work","student_did":"","correction":""}}],"practice_tip":""}}"""
    result = call_gemini(
        [{"text": prompt}, {"text": "Clip 1 (reference):"}, audio_part(ref_mp3, "audio/mpeg"),
         {"text": "Clip 2 (student):"}, audio_part(student_wav, "audio/wav")],
        True, pro=True,
    )
    return result if isinstance(result, dict) else {}


@st.cache_data(ttl=900, show_spinner=False)
def transcribe_english(wav: bytes, orig: bytes) -> str:
    prompt = ("This is a short voice message from a Qur'an student speaking English (they may use words like "
              "tajweed, madd, ghunnah, ayah, surah, qalqalah, ikhfa, waqf). Transcribe it word for word. "
              "Output only the transcript. Use [inaudible] only if there is truly no speech.")
    for audio in (wav, orig, wav):
        t = call_gemini([{"text": prompt}, audio_part(audio, "audio/wav")]).strip()
        if t and "[inaudible]" not in t.lower():
            return t
    return ""


@st.cache_data(ttl=900, show_spinner=False)
def transcribe_arabic(wav: bytes, orig: bytes) -> str:
    prompt = ("Transcribe this Qur'an recitation exactly as actually spoken, in Arabic script (diacritics optional). "
              "Do NOT correct it and do NOT complete it from memory: write only what you hear, including mistakes, "
              "repeats and skipped words. If there is no speech output exactly: [inaudible]")
    for audio in (wav, orig, wav):
        t = call_gemini([{"text": prompt}, audio_part(audio, "audio/wav")]).strip()
        if t and "[inaudible]" not in t.lower():
            return t
    return ""


@st.cache_data(ttl=900, show_spinner=False)
def answer_question(ref: str, verse: str, ctx: str, convo: str, question: str,
                    name: str, style: str, level: str, detail: int, quality: str) -> dict:
    style_desc = {
        "Warm & casual": "a warm, casual sheikh chatting over tea",
        "Classical scholar": "a dignified, precise and gentle classical scholar",
        "Concise coach": "a crisp, friendly tajweed coach",
    }.get(style, "a warm, casual sheikh chatting over tea")
    words = {1: 60, 2: 130, 3: 250}.get(detail, 130)

    prompt = f"""You are {style_desc}, teaching {name} (level: {level}). They are on {ref}: {verse}, but they may ask about ANYTHING related to the Qur'an, tajweed, Arabic, memorisation, tafsir, the Prophets, seerah, Islamic basics or this app. Answer the question they actually asked, even if it is unrelated to the current ayah.
Step 1: work out what they really mean (use the conversation to resolve words like 'it' or 'that', and fix likely speech-recognition errors).
Step 2: answer directly in about {words} words, spoken style, no markdown, no lists, Arabic terms in transliteration. Use the REFERENCE MATERIAL when relevant but do not limit yourself to it. Say plainly when you rely on general knowledge. Never invent hadith, narrations or scholar names; if unsure, say so. For fiqh rulings give the mainstream view briefly and suggest a qualified scholar. If the message is truly unclear, ask one short clarifying question instead of guessing. End with at most one short follow-up question.
Return JSON only: {{"understood":"<their question rewritten clearly in one sentence>","answer":"<your answer>"}}
REFERENCE MATERIAL:
{ctx}
CONVERSATION:
{convo}
STUDENT'S MESSAGE: {question}"""
    out = call_gemini([{"text": prompt}], True, pro=(quality == "Best"))
    return out if isinstance(out, dict) else {}


# ------------------------------------------------------------------- alignment

_DIACRITICS = re.compile("[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")


def norm_ar(text: str) -> list:
    """Strip diacritics and unify the letters Arabic keyboards disagree about."""
    t = _DIACRITICS.sub("", text)
    t = re.sub("[إأآٱ]", "ا", t).replace("ى", "ي").replace("ة", "ه")
    t = re.sub("[^\u0621-\u064A\\s]", "", t)
    return t.split()


def _score(expected: str, heard: str) -> int:
    if expected == heard:
        return 2
    if expected[:2] == heard[:2] and abs(len(expected) - len(heard)) <= 1:
        return 1
    return 0


def nw_align(expected: list, heard: list) -> tuple:
    """Needleman-Wunsch, match 2 / near 1 / gap -1.

    Returns per-expected-word states so a skipped word is marked as missed
    instead of the text silently closing the gap.
    """
    n, m = len(expected), len(heard)
    if n == 0:
        return [], 0
    if m == 0:
        return ["missed"] * n, 0

    table = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        table[i][0] = -i
    for j in range(1, m + 1):
        table[0][j] = -j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            table[i][j] = max(
                table[i - 1][j - 1] + _score(expected[i - 1], heard[j - 1]),
                table[i - 1][j] - 1,
                table[i][j - 1] - 1,
            )

    states = ["missed"] * n
    i, j, extra = n, m, 0
    while i > 0 or j > 0:
        if i and j and table[i][j] == table[i - 1][j - 1] + _score(expected[i - 1], heard[j - 1]):
            s = _score(expected[i - 1], heard[j - 1])
            states[i - 1] = {2: "correct", 1: "close"}.get(s, "missed")
            if s == 0:
                extra += 1
            i -= 1
            j -= 1
        elif i and table[i][j] == table[i - 1][j] - 1:
            i -= 1
        else:
            extra += 1
            j -= 1
    return states, extra


def match_report(words_ar: list, heard: str):
    """Guard rails first: a quarter of the ayah is a failed capture, not a 12% score."""
    expected = ["".join(norm_ar(w)) for w in words_ar]
    expected = [w for w in expected if w]
    spoken = norm_ar(heard)
    if not expected or not spoken:
        return None
    if len(spoken) < 0.25 * len(expected):
        return None

    states, extra = nw_align(expected, spoken)
    points = sum(1.0 if s == "correct" else 0.5 if s == "close" else 0.0 for s in states)
    return {
        "pct": round(100 * points / len(expected)),
        "states": states,
        "missing": [w for w, s in zip(expected, states) if s == "missed"],
        "extra": extra,
        "n_ok": states.count("correct"),
        "total": len(expected),
    }


def feedback_tiles(words: list, states: list) -> str:
    marks = {"correct": "✓", "close": "•", "missed": "✕"}
    tiles = "".join(
        f'<span class="ft {s}" style="animation-delay:{200 + i * 40}ms">{_h.escape(w["ar"])}'
        f'<small>{marks.get(s, "")}</small></span>'
        for i, (w, s) in enumerate(zip(words, states))
    )
    return f'<div class="glass ayahbox">{tiles}</div>'


def tajweed_hints(words: list) -> list:
    """Text-derived only. This never claims to have heard the student."""
    out = []
    for w in words:
        text = w.get("ar", "")
        name = w.get("tr") or text
        if re.search("[\u0646\u0645]\u0651", text):
            out.append(("Ghunnah", name, "hold the sound through the nose for two counts."))
        elif re.search("\u0644[\u0621-\u064A]\u0651", text):
            out.append(("Lam Shamsiyyah", name, "the lām is silent and the next letter is doubled."))
    return out[:6]


# ------------------------------------------------------------------------ plan
# Two conventions of the printed mushaf, used exactly: 604 pages, 30 juz.
# Index 0 is unused so the list can be read by sūrah number directly.

SURAH_START = [
    0, 1, 2, 50, 77, 106, 128, 151, 177, 187, 208, 221, 235, 249, 255, 262, 267,
    282, 293, 305, 312, 322, 332, 342, 350, 359, 367, 377, 385, 396, 404, 411,
    415, 418, 428, 434, 440, 446, 453, 458, 467, 477, 483, 489, 496, 499, 502,
    507, 511, 515, 518, 520, 523, 526, 528, 531, 534, 537, 542, 545, 549, 551,
    553, 554, 556, 558, 560, 562, 564, 566, 568, 570, 572, 574, 575, 577, 578,
    580, 582, 583, 585, 586, 587, 587, 589, 590, 591, 591, 592, 593, 594, 595,
    595, 596, 596, 597, 597, 598, 598, 599, 599, 600, 600, 601, 601, 601, 602,
    602, 602, 603, 603, 603, 604, 604, 604,
]

MINUTES_PER_PAGE = {"none": 60, "juz30": 45, "some": 32, "most": 22}
TOTAL_PAGES = 604

# Real juz boundaries in the Madinah mushaf. Dividing 604 by 30 gives 20.13 and
# rounds juz 30 down to 20 pages when it is 23; these are the printed values.
JUZ_START = [1, 22, 42, 62, 82, 102, 121, 142, 162, 182, 201, 222, 242, 262, 282,
             302, 322, 342, 362, 382, 402, 422, 442, 462, 482, 502, 522, 542, 562, 582]


def _range_for(goal: str, target: int) -> tuple:
    if goal == "juz":
        j = max(1, min(30, int(target)))
        start = JUZ_START[j - 1]
        end = JUZ_START[j] - 1 if j < 30 else TOTAL_PAGES
    elif goal == "surah":
        s = max(1, min(114, int(target)))
        start = SURAH_START[s]
        end = SURAH_START[s + 1] - 1 if s < 114 else TOTAL_PAGES
    else:
        start, end = 1, TOTAL_PAGES
    return start, max(start, end)


def compute_plan(goal: str, target: int, deadline: datetime.date, minutes: int,
                 known: str, today: datetime.date = None) -> dict:
    today = today or datetime.date.today()
    available = max(1, (deadline - today).days)
    strengthen = goal == "strengthen"

    start, end = (1, TOTAL_PAGES) if strengthen else _range_for(goal, target)
    total = max(1, end - start + 1)
    mpp = 12 if strengthen else MINUTES_PER_PAGE.get(known, 60)

    held = 0
    if not strengthen:
        if goal == "juz" and int(target) == 30 and known == "juz30":
            held = total
        elif known == "juz30":
            held = min(21, total)
        elif known == "some":
            held = round(total * 0.3)
        elif known == "most":
            held = round(total * 0.7)

    remaining = max(0, total - held)
    per_day = (minutes if strengthen else minutes * 0.65) / mpp
    days_needed = math.ceil(remaining / per_day) if remaining else 0
    hours = remaining * mpp / 60

    ratio = (days_needed / available) if remaining else 0
    band = "feasible" if remaining == 0 or ratio <= 1 else "tight" if ratio <= 1.3 else "infeasible"

    alternative = ""
    if band == "infeasible":
        reachable = int(per_day * available) + held
        if reachable < 1:
            alternative = "a single ayah a day"
        elif strengthen or goal == "full":
            best = 114
            for i in range(114, 1, -1):
                if TOTAL_PAGES - SURAH_START[i] + 1 <= reachable:
                    best = i
            count = 115 - best
            alternative = ("sūrah " + str(best) + " alone") if count == 1 else \
                          (f"the last {count} sūrahs (sūrahs {best}–114)")
        else:
            alternative = f"the first {max(1, min(total, reachable))} pages of this target"

    schedule = []
    cursor = 0.0
    for day in range(min(days_needed, 3660)):
        today_pages = min(remaining - cursor, per_day)
        if today_pages <= 0:
            break
        first = start + held + int(cursor)
        last = min(end, first + max(0, math.ceil(today_pages) - 1))
        review = round(minutes * (1 if strengthen else 0.35))
        new_minutes = 0 if strengthen else round(minutes * 0.65)
        schedule.append({
            "date": today + datetime.timedelta(days=day),
            "f": first, "t": last,
            "rev": review, "new": new_minutes,
            "pages": today_pages,
        })
        cursor += today_pages

    return {
        "avail": available, "total": total, "held": held, "rem": remaining,
        "ppd": per_day, "need": days_needed, "hours": hours, "band": band,
        "alt": alternative, "sched": schedule,
        "finish": today + datetime.timedelta(days=days_needed),
        "start": start, "end": end,
    }


# ------------------------------------------------------------------- audio I/O

def boost(wav_bytes: bytes, gain_cap: float = 400.0) -> tuple:
    """Normalise a recording to about 90% of full scale.

    Returns (wav_bytes, peak_fraction_before). The cap exists so a file that is
    almost pure digital silence is not multiplied into a wall of hiss; at 12x,
    which the old slider default used, a -48 dBFS laptop mic stayed effectively
    inaudible and every transcription came back empty.
    """
    try:
        with wave.open(io.BytesIO(wav_bytes)) as w:
            channels, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(w.getnframes())
        if width != 2 or not raw:
            return wav_bytes, 1.0
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return wav_bytes, 0.0
        peak = float(np.percentile(np.abs(samples), 99.5))
        fraction = peak / 32768.0
        if peak < 30:
            return wav_bytes, fraction
        # Never attenuate, never amplify pure silence, otherwise lift to ~90%.
        factor = max(1.0, min(float(gain_cap), 0.9 * 32767.0 / peak))
        scaled = np.clip(samples * factor, -32768, 32767).astype(np.int16)
        out = io.BytesIO()
        with wave.open(out, "wb") as w2:
            w2.setnchannels(channels)
            w2.setsampwidth(2)
            w2.setframerate(rate)
            w2.writeframes(scaled.tobytes())
        return out.getvalue(), fraction
    except Exception:
        return wav_bytes, 1.0


_AUDIO_TPL = """<style>body{margin:0;font-family:Inter,sans-serif;background:transparent;text-align:center}
audio{width:100%}input{width:55%;accent-color:@@GLOW@@}</style>
<audio id="a" controls @@AUTO@@ src="@@URI@@"></audio>
<div style="margin-top:6px">&#128264; <input id="v" type="range" min="0" max="100" value="80"
 aria-label="Volume"> &#128266;</div>
<script>
const a=document.getElementById('a'),v=document.getElementById('v');
try{
 const ctx=new (window.AudioContext||window.webkitAudioContext)();
 const g=ctx.createGain();ctx.createMediaElementSource(a).connect(g);g.connect(ctx.destination);
 g.gain.value=v.value/100;
 v.addEventListener('input',()=>{g.gain.value=v.value/100;ctx.resume();});
 a.addEventListener('play',()=>ctx.resume());
}catch(e){}
</script>"""


def play(data: bytes, mime: str = "audio/mpeg", auto: bool = True, height: int = 105) -> None:
    if not data:
        return
    uri = f"data:{mime};base64," + base64.b64encode(data).decode()
    markup = (_AUDIO_TPL.replace("@@GLOW@@", theme()["glow"])
              .replace("@@URI@@", uri)
              .replace("@@AUTO@@", "autoplay" if auto else ""))
    html_block(markup, height=height)


def _sha(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


def voice_in(key: str, label: str):
    """Record once per press. Returns WAV bytes, or None if nothing new.

    The original used hash(b), which is salted per process: the de-duplication
    silently failed on every re-run and re-triggered analysis of a stale clip.
    """
    st.markdown(f"<div style='text-align:center;color:var(--dim)'>🎙️ {label}</div>",
                unsafe_allow_html=True)

    blob = None
    if hasattr(st, "audio_input"):
        clip = st.audio_input(label, key=key, label_visibility="collapsed")
        if clip is not None:
            blob = clip.getvalue()
    else:
        try:
            from streamlit_mic_recorder import mic_recorder
            recorded = mic_recorder(start_prompt="🎙️ Tap to talk", stop_prompt="⏹️ Send",
                                    key=key, just_once=True)
            if recorded:
                blob = recorded["bytes"]
        except Exception as exc:
            st.error(f"The microphone widget is unavailable: {exc}")
            return None

    if not blob:
        return None

    digest = _sha(blob)
    if st.session_state.get("seen_" + key) == digest:
        return None
    st.session_state["seen_" + key] = digest

    boosted, fraction = boost(blob)
    st.session_state["lvl_" + key] = fraction
    st.session_state["orig_" + key] = blob

    try:
        with wave.open(io.BytesIO(blob)) as w:
            seconds = w.getnframes() / w.getframerate()
    except Exception:
        seconds = 0.0
    st.session_state["diag_" + key] = f"Captured {seconds:.1f}s · mic level {fraction * 100:.0f}%"
    return boosted


def clear_recording(key: str) -> None:
    for prefix in ("seen_", "lvl_", "orig_", "diag_"):
        st.session_state.pop(prefix + key, None)


# ------------------------------------------------------- long job with a clock

def loader_markup(label: str, seconds: int) -> str:
    return f'<div class="ld"><div class="ind"></div>✨ {label} · {seconds}s</div>'


def run_with_progress(fn, label: str, budget: float):
    """Run `fn` on a worker thread with a visible clock and a hard ceiling.

    The worker touches no Streamlit API — it only calls pure functions. Every
    `st.*` call happens here, on the script thread, which is what the thread
    safety contract actually requires.
    """
    box = st.empty()
    boxed = {}

    def work():
        try:
            boxed["value"] = fn()
        except BaseException as exc:  # surfaced below
            boxed["error"] = exc

    thread = threading.Thread(target=work, daemon=True)
    try:
        add_script_run_ctx(thread, get_script_run_ctx())
    except Exception:
        pass

    started = time.time()
    thread.start()
    while thread.is_alive():
        elapsed = time.time() - started
        if elapsed > budget:
            box.empty()
            raise TimeoutError(
                f"This took longer than {int(budget)}s and was stopped. "
                "Check your connection and try again."
            )
        box.markdown(loader_markup(label, int(elapsed)), unsafe_allow_html=True)
        time.sleep(0.25)
    box.empty()

    drained = _drain()
    if drained:
        st.session_state["api_error"] = drained[-1]

    if "error" in boxed:
        raise boxed["error"]
    return boxed.get("value")


# ------------------------------------------------------------- teacher dialogue

def context_for(s: int, a: int, tafsir: str) -> str:
    return (f"English translation (Sahih International): {fetch_translation(s, a)}\n"
            f"Tafsir Ibn Kathir (abridged): {tafsir}")


def _config_snapshot() -> dict:
    """Read every setting on the script thread, so workers never touch session_state."""
    return {
        "name": st.session_state.user_name or "the student",
        "style": st.session_state.get("cfg_style", "Warm & casual"),
        "level": st.session_state.get("cfg_level", "Beginner"),
        "detail": int(st.session_state.get("cfg_detail", 2)),
        "quality": st.session_state.get("cfg_quality", "Best"),
        "strict": st.session_state.get("cfg_strict", "Standard"),
        "voice": bool(st.session_state.get("cfg_voice", True)),
    }


def teacher_turn(slot: str, ctx: str, ref: str, verse: str, history_key: str) -> None:
    cfg = _config_snapshot()
    history = st.session_state.setdefault(history_key, [])

    mic_key = f"{slot}_voice"
    wav = voice_in(mic_key, "Tap the mic and talk to your teacher")
    if st.session_state.get(f"diag_{mic_key}"):
        st.caption(st.session_state[f"diag_{mic_key}"])
    if wav:
        st.audio(wav, format="audio/wav")

    typed = None
    with st.form(key=f"{slot}_ask", clear_on_submit=True):
        typed = st.text_input("…or type your question", key=f"{slot}_text",
                              label_visibility="collapsed",
                              placeholder="…or type your question")
        submitted = st.form_submit_button("Ask")

    audio_reply = None
    if wav or (submitted and typed and typed.strip()):
        question_source = wav
        original = st.session_state.get(f"orig_{mic_key}", wav)

        def job():
            spoken = transcribe_english(question_source, original) if question_source else ""
            question = spoken or (typed or "").strip()
            if not question:
                return {"unheard": True}
            convo = "\n".join(f"{m['role']}: {m['text']}" for m in history[-8:])
            reply = answer_question(ref, verse, ctx, convo, question, cfg["name"],
                                    cfg["style"], cfg["level"], cfg["detail"], cfg["quality"])
            return {"question": question, "spoken": bool(spoken),
                    "understood": reply.get("understood", ""),
                    "answer": reply.get("answer", "")}

        try:
            result = run_with_progress(job, "Listening and thinking", 70)
        except Exception as exc:
            st.error(str(exc))
            result = None

        if result and result.get("unheard"):
            st.warning("I couldn't make out any speech in that recording. Check the mic level shown "
                       "above, move a little closer, and try again.")
        elif result and result.get("answer"):
            prefix = "🎙️ You said: " if result.get("spoken") else ""
            history.append({"role": "student", "text": prefix + result["question"]})
            history.append({"role": "teacher", "text": result["answer"],
                            "u": result.get("understood", "")})
            if cfg["voice"]:
                try:
                    spoken_reply = run_with_progress(lambda: speak(result["answer"]),
                                                     "Preparing voice", 25)
                    if isinstance(spoken_reply, bytes):
                        audio_reply = spoken_reply
                    elif isinstance(spoken_reply, str) and spoken_reply:
                        st.caption(spoken_reply)
                except Exception:
                    pass

        error = st.session_state.get("api_error")
        if error and not (result and result.get("answer")):
            st.error(error)

    if audio_reply:
        play(audio_reply)

    for message in history:
        with st.chat_message("user" if message["role"] == "student" else "assistant"):
            if message.get("u"):
                st.caption("Understood: " + message["u"])
            st.write(message["text"])


# ----------------------------------------------------------------------- assets

ASSETS = pathlib.Path(__file__).parent / "assets"

_MOTIF = ('<svg width="96" height="128" viewBox="0 0 96 128" aria-hidden="true">'
          '<g transform="translate(48 64)" fill="none" stroke="var(--glow)" stroke-width="2">'
          '<rect x="-22" y="-22" width="44" height="44"/>'
          '<rect x="-22" y="-22" width="44" height="44" transform="rotate(45)"/>'
          '<circle r="9"/></g></svg>')


@st.cache_data(show_spinner=False)
def _b64_asset(name: str) -> str:
    if not name:
        return ""
    path = ASSETS / name
    try:
        return base64.b64encode(path.read_bytes()).decode() if path.is_file() else ""
    except Exception:
        return ""


def portrait() -> None:
    choice = st.session_state.get("cfg_teacher", "None")
    name = {"Male": "teacher_male.webp", "Female": "teacher_female.webp"}.get(choice, "")
    data = _b64_asset(name)
    if data:
        inner = (f'<img alt="Illustrative portrait" src="data:image/webp;base64,{data}" '
                 'style="width:96px;height:128px;object-fit:cover;border-radius:16px;'
                 'box-shadow:0 0 0 2px var(--glow)">')
    else:
        inner = _MOTIF
    st.markdown(f'<div style="display:flex;justify-content:center;margin:8px 0">{inner}</div>',
                unsafe_allow_html=True)


def card(text: str) -> None:
    body = _h.escape(str(text)).replace("\n", "<br>")
    st.markdown(f'<div class="glass">{body}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------- UI

apply_theme()

if st.session_state.app_phase == "onboarding":
    st.markdown("<h1 style='text-align:center;margin-top:8vh'>Al-Mu'allim</h1>",
                unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:var(--dim)'>Listen five times, understand the "
                "ayah, then recite it from memory.</p>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        name = st.text_input("What is your name?", placeholder="e.g. Abia")
        if st.button("Begin session", use_container_width=True) and name.strip():
            st.session_state.user_name = name.strip()
            st.session_state.app_phase = "classroom"
            st.rerun()
        if not GEMINI_KEY:
            st.caption("No Gemini key yet: the tafsir, lesson and recitation coach need one. "
                       "Add GEMINI_API_KEY in Streamlit → Settings → Secrets.")
else:
    sidebar = st.sidebar
    sidebar.markdown(f"### {st.session_state.user_name}")

    surah_in = sidebar.number_input("Surah", 1, 114, int(st.session_state.current_surah))
    ayah_in = sidebar.number_input("Ayah", 1, 286, int(st.session_state.current_ayah))
    if sidebar.button("Go to this ayah"):
        st.session_state.current_surah = int(surah_in)
        st.session_state.current_ayah = int(ayah_in)
        for slot in ("chat", "coach"):
            st.session_state[slot] = []
        st.rerun()

    with sidebar.expander("Teacher settings"):
        st.selectbox("Teacher style", ["Warm & casual", "Classical scholar", "Concise coach"],
                     key="cfg_style")
        st.selectbox("My level", ["Beginner", "Intermediate", "Advanced"], key="cfg_level")
        st.select_slider("Answer detail", options=[1, 2, 3], value=2,
                         format_func=lambda x: {1: "Short", 2: "Medium", 3: "Detailed"}[x],
                         key="cfg_detail")
        st.radio("Answer quality", ["Best", "Fast"], key="cfg_quality", horizontal=True)
        st.select_slider("Recitation strictness", options=["Gentle", "Standard", "Strict"],
                         value="Standard", key="cfg_strict")
        st.toggle("Spoken replies", True, key="cfg_voice")
        st.radio("Study companion", ["None", "Male", "Female"], key="cfg_teacher", horizontal=True)
        st.caption("Illustrative portraits. Your study companion is not a person.")
        st.radio("Theme", ["White", "Brown", "Night", "Black"], key="cfg_theme", horizontal=True)

    s = int(st.session_state.current_surah)
    a = int(st.session_state.current_ayah)
    key = f"{s}:{a}"
    ref = f"Surah {s}, Ayah {a}"

    verse = fetch_verse(s, a)
    words = fetch_words(s, a)
    audio_url, ref_mp3, reciter = fetch_reciter(s, a)
    listens = int(st.session_state.listens.get(key, 0))

    if not verse:
        st.error("Could not load this ayah. Check the connection and reload.")
        st.stop()

    tab1, tab2, tab3, tab4 = st.tabs(
        ["1 · Listen ×5", "2 · Teacher & lesson", "3 · Recite & coach", "4 · Plan"]
    )

    # ---------------------------------------------------------------- listen
    with tab1:
        st.markdown(f'<div class="glass"><div class="ar-big">{_h.escape(verse)}</div></div>',
                    unsafe_allow_html=True)
        if audio_url and words:
            st.caption(f"Reciter: {reciter}. Timings are estimated from letter count, not measured "
                       "from the file, so highlighting can drift slightly on long words.")
            data_uri = "data:audio/mpeg;base64," + base64.b64encode(ref_mp3).decode()
            html_block(player_html(words, data_uri),
                       height=min(760, 300 + 46 * (len(words) // 4)), scrolling=True)
        else:
            st.warning("Could not load audio or word-by-word data. Check the connection and reload.")

        st.progress(min(listens, 5) / 5, text=f"Listens completed: {min(listens, 5)} of 5")
        if st.button("I listened once more"):
            st.session_state.listens[key] = listens + 1
            st.rerun()
        if listens >= 5:
            st.success("Five listens done. Read the tafsir, then recite from memory on tab 3.")
        if fetch_translation(s, a):
            st.markdown("#### Meaning")
            card(fetch_translation(s, a))

    # --------------------------------------------------------------- teacher
    with tab2:
        portrait()
        tafsir = fetch_ibn_kathir(s, a)
        left, right = st.columns(2)
        if left.button("Explain this ayah to me", use_container_width=True):
            try:
                st.session_state.tafsir_text[key] = run_with_progress(
                    lambda: explain_tafsir(ref, verse, tafsir), "Preparing tafsir", 60
                )
            except Exception as exc:
                st.error(str(exc))
        if right.button("Teach me to recite it", use_container_width=True) and ref_mp3:
            try:
                rules = tajweed_rules(verse)
                st.session_state.lessons[key] = run_with_progress(
                    lambda: recitation_lesson(verse, rules, ref_mp3, reciter),
                    "Teacher is listening to the reference", 100,
                )
            except Exception as exc:
                st.error(str(exc))

        if st.session_state.tafsir_text.get(key):
            st.session_state.pop("api_error", None)
            card(st.session_state.tafsir_text[key])
            st.caption("Based on Ibn Kathir (abridged) via quran.com. AI-written: check anything "
                       "important with a qualified teacher.")
        elif st.session_state.get("api_error"):
            st.error(st.session_state["api_error"])

        if st.session_state.lessons.get(key):
            st.markdown("#### Recitation lesson and breath map")
            card(st.session_state.lessons[key])

        hints = tajweed_hints(words)
        if hints:
            st.markdown("#### Watch for")
            card("\n".join(f"{rule} in “{word}”: {note}" for rule, word, note in hints)
                 + "\nThese come from the text of the ayah, not from your audio.")
            st.caption("Full 16-category rules: " + TAJWEED_16)

        st.markdown("#### Talk to your teacher")
        teacher_turn("t2", context_for(s, a, tafsir), ref, verse, "chat")

    # ---------------------------------------------------------------- recite
    with tab3:
        portrait()
        st.caption("Listen on tab 1 first, then recite from memory. Your teacher stays in the "
                   "conversation afterwards.")
        conceal = st.toggle("Recite from memory", True, key="conceal")
        analysis = st.session_state.last_analysis.get(key)

        if not analysis:
            if conceal and words:
                blanks = "".join(
                    f'<span class="ft hide" style="width:{max(2, len("".join(norm_ar(w["ar"])))) * 0.7}em"></span>'
                    for w in words
                )
                st.markdown(f'<div class="glass ayahbox" aria-hidden="true">{blanks}</div>',
                            unsafe_allow_html=True)
                st.caption("The text stays hidden while you recite from memory.")
            else:
                st.markdown(f'<div class="glass ayahbox">{_h.escape(verse)}</div>',
                            unsafe_allow_html=True)

        wav = voice_in("recite", "Tap the mic, recite the ayah from memory, then stop")
        if st.session_state.get("diag_recite"):
            st.caption(st.session_state["diag_recite"])

        if wav and ref_mp3:
            play(wav, "audio/wav", auto=False)
            if st.session_state.get("lvl_recite", 1) < 0.05:
                st.warning("That recording was very faint. I amplified it, but moving closer to the "
                           "mic will make the feedback more accurate.")

            original = st.session_state.get("orig_recite", wav)
            strictness = st.session_state.get("cfg_strict", "Standard")

            def job():
                heard = transcribe_arabic(wav, original)
                if not heard:
                    return None
                result = analyse(verse, ref_mp3, wav, reciter, tajweed_rules(verse),
                                 strictness, heard)
                if not result:
                    return None
                result["asr"] = heard
                result["match"] = match_report([w["ar"] for w in words] or verse.split(), heard)
                return result

            try:
                result = run_with_progress(job, "Listening to your recitation", 130)
            except Exception as exc:
                st.error(str(exc))
                result = None

            if result is None:
                st.warning("I couldn't pick up any recitation in that recording. Check the level "
                           "shown under the mic, move closer, and try again.")
            else:
                st.session_state.last_analysis[key] = result
                st.session_state.coach = []
                st.session_state.pop("api_error", None)
                if st.session_state.get("cfg_voice") and result.get("spoken_summary"):
                    try:
                        spoken = run_with_progress(
                            lambda: speak(result["spoken_summary"]), "Preparing voice", 25)
                        if isinstance(spoken, bytes):
                            play(spoken)
                        elif isinstance(spoken, str) and spoken:
                            st.caption(spoken)
                    except Exception:
                        pass

        analysis = st.session_state.last_analysis.get(key)
        if analysis:
            st.metric("Estimated accuracy", f"{analysis.get('overall_score', 0)}%")
            st.caption("An AI estimate, not a certified tajweed assessment.")

            match = analysis.get("match")
            if match and words:
                st.markdown(feedback_tiles(words, match["states"]), unsafe_allow_html=True)
                tail = (". Every word. Move to the next ayah."
                        if not match["missing"] else f", {len(match['missing'])} missed.")
                card(f"{match['n_ok']} of {match['total']} words correct" + tail
                     + f"\nExtra words: {match['extra']} · score {match['pct']}% (a near word counts half)")
            elif analysis.get("heard_text"):
                st.info("Word-level scoring needs the word list; here is what the teacher heard instead.")

            card("What I heard you recite: " + (analysis.get("heard_text") or "(nothing clear)"))
            if analysis.get("spoken_summary"):
                card(analysis["spoken_summary"])

            breath = analysis.get("breath") or {}
            if breath:
                st.markdown("#### Breath control")
                card(f"Reference: {breath.get('reference', '')}\n"
                     f"You: {breath.get('student', '')}\n"
                     f"Tip: {breath.get('tip', '')}")

            rules = analysis.get("rules_check") or []
            if rules:
                st.markdown("#### Tajweed rule check (16 categories)")
                for row in rules:
                    icon = {"correct": "✅", "partly": "🟡", "missed": "❌"}.get(
                        row.get("verdict"), "❔")
                    st.markdown(f"{icon} **{row.get('rule', '')}** ({row.get('word', '')}), "
                                f"{row.get('confidence', '')} confidence  \n{row.get('evidence', '')}")

            for word_row in analysis.get("words") or []:
                good = word_row.get("status") == "good"
                with st.expander(f"{'✅' if good else '⚠️'} {word_row.get('word', '')}",
                                 expanded=not good):
                    st.write(f"Heard: {word_row.get('student_did', '')}")
                    st.write(f"Fix: {word_row.get('correction', '')}")

            if analysis.get("practice_tip"):
                st.info(f"💡 {analysis['practice_tip']}")

            again, nxt = st.columns(2)
            if again.button("Once more", use_container_width=True):
                st.session_state.last_analysis.pop(key, None)
                clear_recording("recite")
                st.rerun()
            if nxt.button("Next ayah", use_container_width=True):
                st.session_state.current_ayah = a + 1
                st.session_state.last_analysis.pop(key, None)
                clear_recording("recite")
                st.rerun()

            st.markdown("#### Talk it through with your teacher")
            coach_ctx = ("Latest recitation analysis (AI estimate): "
                         + json.dumps(analysis, ensure_ascii=False)[:6000]
                         + "\nRule checklist:\n" + tajweed_rules(verse))
            teacher_turn("t3", coach_ctx, ref, verse, "coach")

    # ------------------------------------------------------------------ plan
    with tab4:
        if "plan" not in st.session_state:
            st.session_state["plan"] = {
                "step": 0, "goal": "full", "t": 1,
                "dl": datetime.date.today() + datetime.timedelta(days=30),
                "min": 30, "known": "none", "when": datetime.time(20, 0),
            }
        plan = st.session_state["plan"]

        if plan["step"] < 4:
            st.markdown(f"<p class='mi'>Step {plan['step'] + 1} of 4 · what you want to memorise, "
                        "and by when</p>", unsafe_allow_html=True)
            st.progress((plan["step"] + 1) / 4)

            if plan["step"] == 0:
                labels = {"full": "The whole Qur'an", "juz": "A juz",
                          "surah": "A sūrah", "strengthen": "Strengthen what I know"}
                options = list(labels)
                plan["goal"] = st.radio("What do you want to memorise?", options,
                                        format_func=labels.get,
                                        index=options.index(plan["goal"]))
                if plan["goal"] in ("juz", "surah"):
                    plan["t"] = st.number_input(
                        "Which one?", 1, 30 if plan["goal"] == "juz" else 114,
                        min(int(plan["t"]), 30 if plan["goal"] == "juz" else 114))
            elif plan["step"] == 1:
                plan["dl"] = st.date_input("By when?", plan["dl"],
                                           min_value=datetime.date.today())
            elif plan["step"] == 2:
                plan["min"] = st.radio("How long each day?", [15, 30, 60, 120],
                                       format_func=lambda x: f"{x} minutes",
                                       index=[15, 30, 60, 120].index(plan["min"]),
                                       horizontal=True)
            else:
                known_labels = {"none": "Nothing yet", "juz30": "Juz 30",
                                "some": "Some of it", "most": "Most of it"}
                known_options = list(known_labels)
                plan["known"] = st.radio("What do you already know?", known_options,
                                         format_func=known_labels.get,
                                         index=known_options.index(plan["known"]))
                plan["when"] = st.time_input("When will you sit down?",
                                             plan.get("when", datetime.time(20, 0)))

            back, forward = st.columns(2)
            if plan["step"] and back.button("Back", use_container_width=True):
                plan["step"] -= 1
                st.rerun()
            label = "Build my plan" if plan["step"] == 3 else "Next"
            if forward.button(label, use_container_width=True):
                plan["step"] += 1
                st.rerun()
        else:
            computed = compute_plan(plan["goal"], int(plan["t"]), plan["dl"],
                                    int(plan["min"]), plan["known"])
            colour = {"feasible": "#2E7D5B", "tight": "#B8912F", "infeasible": "#C0453A"}[computed["band"]]
            headline = {
                "feasible": "This fits your time.",
                "tight": "This is tight. Missing a day costs you the deadline.",
                "infeasible": "This doesn't fit the time you've given it.",
            }[computed["band"]]

            if computed["rem"]:
                arithmetic = (
                    f"At {plan['min']} minutes a day you memorise about {computed['ppd']:.1f} pages. "
                    f"This target is {computed['total']} pages"
                    + (f" ({computed['held']} already held)" if computed["held"] else "")
                    + f", so {computed['rem']} pages take about {computed['need']} days against the "
                    f"{computed['avail']} you have. That is about {computed['hours']:.0f} hours of "
                    "memorisation inside that window."
                )
            else:
                arithmetic = "You've told us you hold all of this; the schedule is revision only."

            st.markdown(
                f'<div class="ban" style="background:{colour}">'
                f'<b style="font-size:1.1rem">{headline}</b>'
                f'<p style="margin:8px 0 0">{arithmetic}</p></div>',
                unsafe_allow_html=True,
            )

            if computed["band"] == "infeasible":
                card(f"Nearest goal that fits: {computed['alt']}.\n"
                     f"Or keep the goal and move the date to {computed['finish'].isoformat()} "
                     f"({computed['need']} days from today).")

            if computed["sched"]:
                first = computed["sched"][0]
                block_line = (f"TODAY at {plan['when'].strftime('%H:%M')} · pages "
                              f"{first['f']}–{first['t']}\n"
                              + (f"New: {first['new']} min · " if first["new"] else "")
                              + f"Review: {first['rev']} min"
                              + (" · Consolidate: last 8 min, from memory" if first["new"] else ""))
                card(block_line)

                busiest = max(d["rev"] + d["new"] for d in computed["sched"]) or 1
                palette = ["#F2EADA", "#E8D9A8", "#D9BE62", "#C9A227"]
                shown = computed["sched"][:120]
                cells = "".join(
                    f'<i title="{d["date"].isoformat()}: pages {d["f"]}–{d["t"]}" '
                    f'style="background:{palette[min(3, math.ceil((d["rev"] + d["new"]) / busiest * 3))]}"></i>'
                    for d in shown
                )
                st.markdown(
                    f'<div class="glass" style="padding:16px"><p class="mi">Next '
                    f'{len(shown)} days</p><div class="cells">{cells}</div></div>',
                    unsafe_allow_html=True,
                )
                if len(computed["sched"]) > len(shown):
                    st.caption(f"The grid shows the first {len(shown)} of "
                               f"{len(computed['sched'])} scheduled days. Darker cells are heavier "
                               "days; each cell is one day.")

            if st.button("Change plan"):
                plan["step"] = 0
                st.rerun()
