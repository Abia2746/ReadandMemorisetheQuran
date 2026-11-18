import base64
import datetime
import json
import os
import pathlib
import random
import re
import sqlite3
import time
import unicodedata
import io
import wave
import numpy as np

import requests
import streamlit as st


# ============================================================
# AL-MU'ALLIM — Advanced Qur'an Recitation & 4-Stage Academy
# ============================================================

st.set_page_config(
    page_title="Al-Mu'allim Live",
    page_icon="🕌",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from studio_ui import render_studio

QURAN_API = "https://api.quran.com/api/v4"
EVERY_AYAH = "https://everyayah.com/data"
GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"

GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
]

SUPPORTED_AUDIO_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mp3",
    "audio/mpeg",
    "audio/aiff",
    "audio/aac",
    "audio/ogg",
    "audio/flac",
    "audio/webm",
}

RECITERS = {
    "Mishary Alafasy": {"folder": "Alafasy_128kbps", "id": 7},
    "Yasser Al-Dosari": {"folder": "Yasser_Ad-Dussary_128kbps", "id": 8},
}

AYAHS = [
    0, 7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43,
    52, 99, 128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93,
    88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53,
    89, 59, 37, 35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29,
    22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28,
    20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19,
    26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3,
    9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6,
]

HARAKAH_NAMES = {
    "\u064b": "Fathatayn", "\u064c": "Dammatayn", "\u064d": "Kasratayn",
    "\u064e": "Fathah", "\u064f": "Dammah", "\u0650": "Kasrah",
    "\u0651": "Shaddah", "\u0652": "Sukoon", "\u0653": "Maddah",
    "\u0654": "Hamza above", "\u0655": "Hamza below", "\u0670": "Superscript alif",
}


# ----------------------------- Helper to load local image as Base64 -----------------------------

def get_image_base64(filename):
    try:
        path = pathlib.Path(__file__).with_name(filename)
        if path.exists():
            with open(path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
                return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        pass
    return ""

OMAR_B64 = get_image_base64("IMG_6147.jpeg")
NOOR_B64 = get_image_base64("IMG_6146.jpeg")


# ----------------------------- Database & Analytics -----------------------------

try:
    DB_PATH = pathlib.Path(__file__).with_name("muallim.db")
except NameError:
    DB_PATH = pathlib.Path.cwd() / "muallim.db"


def db():
    connection = sqlite3.connect(DB_PATH)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            name TEXT PRIMARY KEY,
            xp INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            last_day TEXT
        )
        """
    )
    return connection


def get_user(name):
    with db() as connection:
        connection.execute("INSERT OR IGNORE INTO users(name) VALUES(?)", (name,))
        row = connection.execute("SELECT xp, streak, last_day FROM users WHERE name=?", (name,)).fetchone()
    return row


def award_xp(name, xp=10):
    today = datetime.date.today()
    current_xp, streak, last_day = get_user(name)
    if last_day != today.isoformat():
        yesterday = (today - datetime.timedelta(days=1)).isoformat()
        streak = streak + 1 if last_day == yesterday else 1
    with db() as connection:
        connection.execute(
            "UPDATE users SET xp=?, streak=?, last_day=? WHERE name=?",
            (current_xp + xp, streak, today.isoformat(), name),
        )


# ----------------------------- Qur'an API & Exact Timings -----------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_words(surah, ayah):
    response = requests.get(
        f"{QURAN_API}/verses/by_key/{surah}:{ayah}",
        params={"words": "true", "word_fields": "text_uthmani", "language": "en"},
        timeout=20,
    )
    response.raise_for_status()
    verse = response.json().get("verse", {})
    output = []
    for item in verse.get("words", []):
        if item.get("char_type_name") != "word":
            continue
        arabic = item.get("text_uthmani", "")
        if not arabic:
            continue
        output.append({
            "ar": arabic,
            "en": (item.get("translation") or {}).get("text", ""),
            "tr": (item.get("transliteration") or {}).get("text", ""),
            "ayah": int(ayah),
        })
    if not output:
        raise RuntimeError(f"No words returned for {surah}:{ayah}.")
    return output


def split_arabic_graphemes(text):
    graphemes = []
    for character in text:
        if unicodedata.category(character).startswith("M") and graphemes:
            graphemes[-1] += character
        else:
            graphemes.append(character)
    return graphemes


def harakah_labels(grapheme):
    return [HARAKAH_NAMES[c] for c in grapheme if c in HARAKAH_NAMES]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_passage(surah, start_ayah, end_ayah, reciter_id):
    passage_words = []
    track_word_counts = []
    all_segments = []
    global_word_idx = 0
    
    for ayah in range(start_ayah, end_ayah + 1):
        verse_words = fetch_words(surah, ayah)
        track_word_counts.append(len(verse_words))
        
        try:
            tr = requests.get(f"{QURAN_API}/recitations/{reciter_id}/by_ayah/{surah}:{ayah}", timeout=10)
            segs = tr.json().get("audio_files", [{}])[0].get("segments", [])
            for s in segs:
                all_segments.append({"ayah": ayah, "word_idx": s[0] + global_word_idx, "start": s[1], "end": s[2]})
        except Exception:
            pass
            
        global_word_idx += len(verse_words)
        
        for word in verse_words:
            item = dict(word)
            item["letters"] = [
                {"text": g, "marks": harakah_labels(g)}
                for g in split_arabic_graphemes(word["ar"])
            ]
            passage_words.append(item)
            
    if not passage_words:
        raise RuntimeError("No words returned for this passage.")
    return passage_words, track_word_counts, all_segments


def audio_url(surah, ayah, reciter_folder):
    return f"{EVERY_AYAH}/{reciter_folder}/{surah:03d}{ayah:03d}.mp3"


# ----------------------------- Audio Compression & Gemini Scholarly Fallback -----------------------------

def compress_audio(b):
    try:
        with wave.open(io.BytesIO(b)) as w:
            ch, sw, fr = w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(w.getnframes())
        if sw != 2 or not raw: return b
        
        x = np.frombuffer(raw, "<i2").astype(np.float32)
        if ch > 1: x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
        if fr != 16000 and len(x) > 1:
            x = np.interp(np.linspace(0, len(x) - 1, round(len(x) * 16000 / fr)), np.arange(len(x)), x)
            
        p = float(np.percentile(np.abs(x), 99.5))
        if p > 30: x = x * min(30.0, 0.9 * 32767 / p)
        
        out = io.BytesIO()
        with wave.open(out, "wb") as w2:
            w2.setnchannels(1); w2.setsampwidth(2); w2.setframerate(16000)
            w2.writeframes(np.clip(x, -32768, 32767).astype("<i2").tobytes())
        return out.getvalue()
    except Exception:
        return b


def api_key():
    try:
        secret_key = st.secrets.get("GEMINI_API_KEY", "")
        if secret_key:
            return str(secret_key).strip()
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip()


def normalize_audio_mime_type(mime_type):
    if not mime_type:
        return "audio/wav"
    cleaned = mime_type.split(";")[0].strip().lower()
    aliases = {"audio/x-wav": "audio/wav", "audio/wave": "audio/wav", "audio/mpeg": "audio/mp3"}
    normalized = aliases.get(cleaned, cleaned)
    if normalized not in SUPPORTED_AUDIO_MIME_TYPES:
        raise RuntimeError("Unsupported audio format.")
    return normalized


@st.cache_data(ttl=1800, show_spinner=False)
def get_available_models(api_key_value):
    try:
        response = requests.get(GEMINI_MODELS_URL, headers={"x-goog-api-key": api_key_value}, timeout=10)
    except requests.RequestException as exc:
        raise RuntimeError("Network error connecting to Gemini API.") from exc
    if response.status_code in (401, 403):
        raise RuntimeError("Invalid or unauthorized GEMINI_API_KEY.")
    if response.status_code != 200:
        raise RuntimeError(f"Gemini model lookup failed (HTTP {response.status_code}).")
    models = response.json().get("models", [])
    supported = {
        item.get("name", "").removeprefix("models/")
        for item in models if isinstance(item, dict)
        and "generateContent" in item.get("supportedGenerationMethods", ["generateContent"])
    }
    available = [name for name in GEMINI_MODELS if name in supported]
    if not available:
        available = sorted((name for name in supported if "flash" in name and "live" not in name and "image" not in name), reverse=True)
    if not available:
        raise RuntimeError("No Gemini Flash model supporting generateContent is available for this key.")
    return available


def parse_tajweed_json(raw_text):
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text.strip()).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    letters, word_feedback, tajweed_assessments = [], [], []
    letters_match = re.search(r'"letters"\s*:\s*\[', cleaned)
    words_match = re.search(r'"word_feedback"\s*:\s*\[', cleaned)
    rules_match = re.search(r'"tajweed_assessments"\s*:\s*\[', cleaned)
    if letters_match:
        end_pos = words_match.start() if words_match else len(cleaned)
        for obj_match in re.finditer(r'\{[^{}]*\}', cleaned[letters_match.end():end_pos]):
            try: letters.append(json.loads(obj_match.group(0)))
            except Exception: pass
    if words_match:
        for obj_match in re.finditer(r'\{[^{}]*\}', cleaned[words_match.end():]):
            try: word_feedback.append(json.loads(obj_match.group(0)))
            except Exception: pass
    if rules_match:
        for obj_match in re.finditer(r'\{[^{}]*\}', cleaned[rules_match.end():]):
            try: tajweed_assessments.append(json.loads(obj_match.group(0)))
            except Exception: pass
    feedback_match = re.search(r'"feedback"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    teacher_label_match = re.search(r'"teacher_label"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    tafsir_match = re.search(r'"tafsir_summary"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    return {
        "letters": letters, "word_feedback": word_feedback, "tajweed_assessments": tajweed_assessments,
        "feedback": feedback_match.group(1) if feedback_match else "Evaluation complete.",
        "teacher_label": teacher_label_match.group(1) if teacher_label_match else "Mashallah, well recited.",
        "tafsir_summary": tafsir_match.group(1) if tafsir_match else "Contextual commentary provided.",
    }


def tajweed_response_schema():
    return {
        "type": "object",
        "properties": {
            "teacher_label": {"type": "string"},
            "feedback": {"type": "string"},
            "tafsir_summary": {"type": "string"},
            "letters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "word_i": {"type": "integer"}, "letter_i": {"type": "integer"},
                        "status": {"type": "string", "enum": ["good", "review", "uncertain"]},
                        "rule": {"type": "string"}, "feedback": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    },
                    "required": ["word_i", "letter_i", "status", "rule", "feedback", "confidence"],
                },
            },
            "word_feedback": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "word_i": {"type": "integer"},
                        "status": {"type": "string", "enum": ["good", "review", "uncertain"]},
                        "feedback": {"type": "string"},
                    },
                    "required": ["word_i", "status", "feedback"],
                },
            },
            "tajweed_assessments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "rule_id": {"type": "integer"}, "rule_name": {"type": "string"},
                        "applied_correctly": {"type": "boolean"}, "location": {"type": "string"},
                        "mistake_description": {"type": "string"}, "correction_guide": {"type": "string"},
                        "repetition_exercise": {"type": "string"},
                    },
                    "required": ["rule_id", "rule_name", "applied_correctly", "location", "mistake_description", "correction_guide", "repetition_exercise"],
                },
            },
        },
        "required": ["teacher_label", "feedback", "tafsir_summary", "letters", "word_feedback", "tajweed_assessments"],
    }


def post_interaction_with_retry(key, base_request_body, candidate_models):
    last_error = "No model succeeded."
    for model_id in candidate_models:
        url = f"{GEMINI_INTERACTIONS_URL}/{model_id}:generateContent"
        body = {
            "contents": [{"parts": [{"text": base_request_body["input"][0]["text"]}, 
                                    {"inline_data": {"mime_type": base_request_body["input"][1]["mime_type"], "data": base_request_body["input"][1]["data"]}}]}],
            "systemInstruction": {"parts": [{"text": base_request_body["system_instruction"]}]},
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": base_request_body["response_format"]["schema"], "temperature": 0.1, "maxOutputTokens": 4096}
        }
        
        for attempt in range(2):
            try:
                response = requests.post(url, headers={"x-goog-api-key": key, "Content-Type": "application/json"}, json=body, timeout=45)
                if response.status_code == 200:
                    return response
                try:
                    detail = response.json().get("error", {}).get("message", "")
                except ValueError:
                    detail = ""
                last_error = f"{model_id}: HTTP {response.status_code}" + (f" — {detail[:180]}" if detail else "")
                if response.status_code in (400, 401, 403, 404):
                    break
            except requests.RequestException as exc:
                last_error = f"{model_id}: network or timeout error ({type(exc).__name__})"
    raise RuntimeError("AI audio review is currently unavailable. " + last_error)


def analyse_recitation(audio_bytes, mime_type, words, strictness, teacher_gender):
    key = api_key()
    if not key: raise RuntimeError("API key missing.")
    if not audio_bytes: raise RuntimeError("Audio recording is empty.")
    
    audio_bytes = compress_audio(audio_bytes)
    
    normalized_mime = normalize_audio_mime_type(mime_type)
    candidate_models = get_available_models(key)
    expected_text = [{"word_i": i, "ayah": w["ayah"], "text": w["ar"]} for i, w in enumerate(words)]
    system_instruction = (
        f"You are an AI Qur'an practice assistant in a {teacher_gender.lower()} tutor persona, "
        "not a certified scholar or a human listening teacher. Use the reference in Hafs. "
        "Assess ONLY observations supported by the recording. If a vowel, articulation point, "
        "elongation or specific Tajweed rule cannot be heard reliably, label it 'uncertain'. "
        "Do not invent a score, mistake, timestamp, rule assessment or evidence. "
        "Distinguish actual omission and substitution from pronunciation uncertainty. "
        "Focus on a few actionable corrections, accounting for noise and accent. "
        "The supplied reference identifies expected words, not what was actually spoken. "
        "Return the requested JSON."
    )
    prompt = (
        f"Review this recitation carefully, emphasizing verifiable observations. "
        f"Strictness: {strictness}. If the audio is insufficiently clear, return uncertain. "
        f"Expected words: {json.dumps(expected_text, ensure_ascii=False)}"
    )
    encoded_audio = base64.b64encode(audio_bytes).decode("ascii")
    base_request_body = {
        "system_instruction": system_instruction, "store": False,
        "input": [{"type": "text", "text": prompt}, {"type": "audio", "data": encoded_audio, "mime_type": normalized_mime}],
        "response_format": {"type": "text", "mime_type": "application/json", "schema": tajweed_response_schema()},
        "generation_config": {"temperature": 0.1, "max_output_tokens": 2048},
    }
    response = post_interaction_with_retry(key, base_request_body, candidate_models)
    
    try:
        txt = "".join(p.get("text", "") for p in response.json()["candidates"][0]["content"]["parts"])
    except Exception:
        raise RuntimeError("Failed to parse Gemini response.")
        
    data = parse_tajweed_json(txt)
    states = ["uncertain"] * len(words)
    for item in data.get("word_feedback", []):
        if isinstance(item, dict) and 0 <= item.get("word_i", -1) < len(words):
            states[item["word_i"]] = item.get("status", "uncertain")
    return (
        states,
        {f"{k['word_i']}:{k['letter_i']}": k for k in data.get("letters", [])},
        {k["word_i"]: k["feedback"] for k in data.get("word_feedback", []) if "word_i" in k},
        data.get("tajweed_assessments", []),
        data.get("feedback", "Evaluation complete."),
        data.get("tafsir_summary", "Contextual wisdom provided."),
        data.get("teacher_label", "Mashallah, beautiful recitation."),
    )


def ask_teacher_scholar(query, surah, start_ayah, end_ayah):
    key = api_key()
    if not key: return "API key missing."
    candidate_models = get_available_models(key)
    system_instruction = "You are an eminent master Qur'an scholar. Answer student inquiries with academic depth and professional courtesy."
    prompt = f"Inquiry for Surah {surah} (Ayahs {start_ayah}-{end_ayah}): {query}"
    request_body = {"system_instruction": system_instruction, "store": False, "input": [{"type": "text", "text": prompt}], "generation_config": {"temperature": 0.3, "max_output_tokens": 1024}}
    for model_id in candidate_models:
        try:
            url = f"{GEMINI_INTERACTIONS_URL}/{model_id}:generateContent"
            body = {"contents": [{"parts": [{"text": prompt}]}], "systemInstruction": {"parts": [{"text": system_instruction}]}, "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024}}
            resp = requests.post(url, headers={"x-goog-api-key": key, "Content-Type": "application/json"}, json=body, timeout=20)
            if resp.status_code == 200:
                return "".join(p.get("text", "") for p in resp.json()["candidates"][0]["content"]["parts"])
        except Exception:
            continue
    return "Scholar consultation currently unavailable."



# =============================================================
# AL-MU'ALLIM — Original premium Quran studio
# =============================================================
import html as html_escape

SURAH_TITLES = {
    1: ("الفاتحة", "Al-Fatihah"),
    2: ("البقرة", "Al-Baqarah"),
    3: ("آل عمران", "Ali 'Imran"),
    4: ("النساء", "An-Nisa"),
    5: ("المائدة", "Al-Ma'idah"),
    6: ("الأنعام", "Al-An'am"),
    7: ("الأعراف", "Al-A'raf"),
    18: ("الكهف", "Al-Kahf"),
    19: ("مريم", "Maryam"),
    20: ("طه", "Ta-Ha"),
    36: ("يس", "Ya-Sin"),
    55: ("الرحمن", "Ar-Rahman"),
    56: ("الواقعة", "Al-Waqi'ah"),
    67: ("الملك", "Al-Mulk"),
    78: ("النبأ", "An-Naba"),
    112: ("الإخلاص", "Al-Ikhlas"),
    113: ("الفلق", "Al-Falaq"),
    114: ("الناس", "An-Nas"),
}

APP_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@400;600;700&display=swap');
.stApp {
  background: radial-gradient(ellipse at 60% 0%,#453022 0%,#241712 46%,#1d1310 100%) !important;
  color:#f5e7ce !important;
  font-family:'DM Sans',sans-serif !important;
}
[data-testid="stAppViewContainer"] {background:transparent}
[data-testid="stMainBlockContainer"] {max-width:1370px;padding-top:1.5rem;padding-bottom:3rem}
[data-testid="stSidebar"] {background:#2d2019 !important;border-right:1px solid #97744540}
[data-testid="stSidebar"] * {color:#e9d7b7}
[data-testid="stHeader"] {background:transparent}
[data-testid="stToolbar"] {opacity:.85}
h1,h2,h3,h4 {color:#ebca88 !important; font-family:'Playfair Display',serif !important}
[data-testid="stExpander"] {background:#30231c!important;border:1px solid #b288523f!important;border-radius:17px!important}
[data-testid="stAudioInput"],[data-testid="stTextInput"],[data-testid="stNumberInput"] {color:#f5e7ce!important}
.stButton button[kind="primary"],[data-testid="stFormSubmitButton"] button {
  background:linear-gradient(110deg,#eed293,#c79540)!important;color:#2b1a10!important;
  border-color:#ddb775!important;border-radius:999px!important;font-weight:700!important;
}
.stButton button {border-radius:999px!important}
.stMarkdown p,.stCaption {color:#d6c1a1}
.am-python-section {
  padding:20px 24px;border:1px solid #b288523b;border-radius:20px;
  background:linear-gradient(130deg,#33231b,#281b15);margin-top:22px;
}
.am-python-section .eyebrow {text-transform:uppercase;letter-spacing:.2em;color:#cba365;font-size:11px;font-weight:700}
.am-python-section h2 {margin:.2em 0 .4em;font-size:24px}
.am-onboarding {max-width:600px;margin:10vh auto;text-align:center;padding:40px 20px;border-radius:24px;border:1px solid #b68a514d;background:#302017}
.am-onboarding .ar {font:42px 'Amiri',serif;color:#e5c17c}
.am-onboarding h1 {font-size:40px}
.am-teacher-reply {padding:16px 20px;background:#30231c;border:1px solid #b288523a;border-radius:14px;margin:12px 0;color:#f3debd}
@media(max-width:640px) {
  [data-testid="stMainBlockContainer"]{padding:1rem .65rem 2rem}
  .am-python-section{padding:15px 12px}
}
</style>
"""
st.markdown(APP_STYLE, unsafe_allow_html=True)

DEFAULTS = {
    "name": "", "surah": 2, "ayah": 60, "end_ayah": 64,
    "recite_from_memory": False, "results": {}, "paid": [],
    "tries": 0, "teacher_gender": "Female", "strictness": "Balanced",
    "teacher_label": "Begin with a short passage. Listen, repeat and review.",
    "scholar_chat": [],
}
for key, default in DEFAULTS.items():
    st.session_state.setdefault(key, default)

if not st.session_state.name:
    st.markdown(
        "<div class='am-onboarding'><div class='ar'>بِسْمِ اللَّهِ</div>"
        "<h1>Al-Mu'allim</h1><p>A quiet space to read, memorise and understand the Qur'an.</p>"
        "</div>", unsafe_allow_html=True
    )
    with st.form("start_al_muallim"):
        learner_name = st.text_input("How should your practice profile be labelled?",
                                     placeholder="Your name or nickname", max_chars=50)
        entered = st.form_submit_button("Enter the academy", use_container_width=True)
        if entered:
            if learner_name.strip():
                st.session_state.name = learner_name.strip()
                st.rerun()
            else:
                st.warning("Enter a name to start.")
    st.stop()

# Sidebar configuration remains accessible, without dominating the reading page.
with st.sidebar:
    st.markdown("### ✦ Al-Mu'allim")
    st.caption("Choose a passage and customise your practice.")
    st.markdown("**Your practice profile**")
    st.write(html_escape.escape(st.session_state.name))
    st.divider()
    surah = int(st.number_input("Surah number", min_value=1, max_value=114,
                                value=int(st.session_state.surah), step=1))
    max_ayah = AYAHS[surah]
    ayah = int(st.number_input("Start ayah", min_value=1, max_value=max_ayah,
                               value=min(int(st.session_state.ayah), max_ayah), step=1))
    stop_max = min(max_ayah, ayah + 9)
    end_ayah = int(st.number_input("End ayah (up to ten verses)", min_value=ayah,
                                   max_value=stop_max,
                                   value=min(max(ayah, int(st.session_state.end_ayah)), stop_max),
                                   step=1))
    reciter = st.selectbox("Listen to", list(RECITERS),
                           index=1 if "Yasser Al-Dosari" in RECITERS else 0)
    st.session_state.teacher_gender = st.selectbox(
        "AI teacher", ["Female", "Male"],
        index=0 if st.session_state.teacher_gender == "Female" else 1,
    )
    st.session_state.strictness = st.select_slider(
        "Recording review sensitivity", ["Lenient", "Balanced", "Strict"],
        value=st.session_state.strictness,
    )
    st.session_state.recite_from_memory = st.toggle(
        "Begin in English-clue memorisation mode",
        value=st.session_state.recite_from_memory,
    )
    if st.button("Load this passage", type="primary", use_container_width=True):
        st.session_state.update(
            surah=surah, ayah=ayah, end_ayah=end_ayah, tries=0,
            teacher_label="Let's begin with the words you've selected.",
        )
        st.rerun()
    st.divider()
    st.caption("For accurate Tajweed, listen to a qualified teacher and compare with a reliable recitation.")
    if st.button("Switch practice profile", use_container_width=True):
        st.session_state.name = ""
        st.rerun()

passage_key = f"{surah}:{ayah}-{end_ayah}"
result_key = f"{passage_key}|recitation"

try:
    words, track_word_counts, segments = fetch_passage(
        surah, ayah, end_ayah, RECITERS[reciter]["id"]
    )
    tracks = [audio_url(surah, a, RECITERS[reciter]["folder"])
              for a in range(ayah, end_ayah + 1)]
except Exception as exc:
    st.error("Unable to load the selected Quran passage. Try reloading or selecting fewer verses.")
    with st.expander("Technical details"):
        st.code(str(exc))
    st.stop()

xp, streak, _ = get_user(st.session_state.name)
meta = {"s": surah, "a": ayah, "end": end_ayah, "xp": xp, "streak": streak}
surah_arabic, surah_english = SURAH_TITLES.get(surah, ("القرآن الكريم", f"Surah {surah}"))
teacher_name = "Ustadha Noor" if st.session_state.teacher_gender == "Female" else "Ustadh Omar"
avatar = NOOR_B64 if st.session_state.teacher_gender == "Female" else OMAR_B64
saved = st.session_state.results.get(result_key)

# The full study environment is provided through a modern non-iframe Streamlit component.
render_studio(
    words=words,
    meta=meta,
    tracks=tracks,
    reciter=reciter,
    segments=segments,
    word_counts=track_word_counts,
    mode="blind" if st.session_state.recite_from_memory else "full",
    teacher_name=teacher_name,
    avatar=avatar,
    surah_arabic=surah_arabic,
    surah_english=surah_english,
    review=saved,
)

st.markdown(
    "<div class='am-python-section'>"
    "<div class='eyebrow'>Review your recitation</div>"
    "<h2>Listen deeply. Improve gently.</h2>"
    "<p>Record a short passage below for optional AI-supported review. "
    "A qualified Tajweed teacher should confirm subtle pronunciation and articulation.</p>"
    "</div>",
    unsafe_allow_html=True,
)

left, right = st.columns([3, 2], gap="large")
with left:
    recording = st.audio_input(
        "Record your recitation",
        key=f"academy_rec_{passage_key}_{st.session_state.tries}",
    )
    if recording:
        if st.button("Analyse this recording", type="primary", use_container_width=True):
            try:
                with st.spinner("Reviewing your audio against the selected Quran text..."):
                    states, letter_results, word_feedback, tajweed, feedback, tafsir, teacher_label = analyse_recitation(
                        recording.getvalue(),
                        recording.type or "audio/wav",
                        words,
                        st.session_state.strictness,
                        st.session_state.teacher_gender,
                    )
                st.session_state.teacher_label = teacher_label
                st.session_state.results[result_key] = {
                    "states": states, "letter_results": letter_results,
                    "word_feedback": word_feedback,
                    "tajweed_assessments": tajweed, "feedback": feedback,
                    "tafsir_summary": tafsir,
                }
                if result_key not in st.session_state.paid:
                    award_xp(st.session_state.name, 10)
                    st.session_state.paid.append(result_key)
                st.rerun()
            except Exception as exc:
                st.error("The audio review was unsuccessful. Your recitation has not been graded.")
                with st.expander("Technical details"):
                    st.code(str(exc))
with right:
    st.markdown("#### Review guidance")
    st.write("1. Recite just the chosen passage.")
    st.write("2. Use a quiet place.")
    st.write("3. Review uncertain words before attempting the passage again.")
    st.caption("Speech recognition and language-model feedback cannot certify every vowel, ghunnah or madd duration.")

if saved:
    st.markdown("### Your last practice review")
    st.info(saved.get("feedback") or "No general feedback was returned.")
    for point in saved.get("tajweed_assessments", []):
        with st.expander(
            f"{point.get('rule_name','Practice point')} · {point.get('location','Selected passage')}"
        ):
            st.write(point.get("mistake_description") or "Insufficient evidence for a definite assessment.")
            st.write(point.get("correction_guide") or "Repeat this part with a trusted reciter.")
            st.caption(point.get("repetition_exercise") or "")
    with st.expander("Reflection and context"):
        st.write(saved.get("tafsir_summary") or "No explanation was returned.")
    if st.button("Start a fresh recording", use_container_width=True):
        st.session_state.tries += 1
        st.rerun()

st.markdown("### Ask your AI teacher")
st.caption(
    "Ask about the selected verses, Qur'anic vocabulary or Tajweed terminology. "
    "AI responses can contain mistakes; verify religious rulings and precise recitation with reliable scholars."
)
with st.form("teacher_question", clear_on_submit=True):
    question = st.text_input(
        "Your question",
        placeholder="What is the difference between Fathah and Kasrah?",
    )
    send = st.form_submit_button("Ask the teacher")
if send and question.strip():
    try:
        with st.spinner("Preparing your answer..."):
            answer = ask_teacher_scholar(question.strip(), surah, ayah, end_ayah)
        st.session_state.scholar_chat.append((question.strip(), answer))
    except Exception as exc:
        st.warning("The AI teacher is temporarily unavailable.")
        st.caption(str(exc))
for user_q, reply in reversed(st.session_state.scholar_chat[-4:]):
    with st.expander(user_q):
        st.write(reply)

st.caption("Al-Mu'allim · A focused Qur'an learning workspace. Your progress shown here is practice activity, not certified recitation mastery.")
