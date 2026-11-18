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
import streamlit.components.v1 as components


# ============================================================
# AL-MU'ALLIM — Advanced Qur'an Recitation & 4-Stage Academy
# ============================================================

st.set_page_config(
    page_title="Al-Mu'allim Live",
    page_icon="🕌",
    layout="wide",
    initial_sidebar_state="expanded",
)

QURAN_API = "https://api.quran.com/api/v4"
EVERY_AYAH = "https://everyayah.com/data"
GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
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
    returned_names = {item.get("name", "").removeprefix("models/") for item in response.json().get("models", []) if isinstance(item, dict)}
    available = [m for m in GEMINI_MODELS if m in returned_names]
    if not available:
        available = [m for m in returned_names if "flash" in m]
    if not available:
        raise RuntimeError("None of the supported Gemini models are enabled.")
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
    for model_id in candidate_models:
        url = f"{GEMINI_INTERACTIONS_URL}/{model_id}:generateContent"
        body = {
            "contents": [{"parts": [{"text": base_request_body["input"][0]["text"]}, 
                                    {"inline_data": {"mime_type": base_request_body["input"][1]["mime_type"], "data": base_request_body["input"][1]["data"]}}]}],
            "systemInstruction": {"parts": [{"text": base_request_body["system_instruction"]}]},
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": base_request_body["response_format"]["schema"], "temperature": 0.1}
        }
        
        for attempt in range(2):
            try:
                response = requests.post(url, headers={"x-goog-api-key": key, "Content-Type": "application/json"}, json=body, timeout=45)
                if response.status_code == 200:
                    return response
            except Exception:
                pass
    raise RuntimeError("Gemini service temporarily unavailable.")


def analyse_recitation(audio_bytes, mime_type, words, strictness, teacher_gender):
    key = api_key()
    if not key: raise RuntimeError("API key missing.")
    if not audio_bytes: raise RuntimeError("Audio recording is empty.")
    
    audio_bytes = compress_audio(audio_bytes)
    
    normalized_mime = normalize_audio_mime_type(mime_type)
    candidate_models = get_available_models(key)
    expected_text = [{"word_i": i, "ayah": w["ayah"], "text": w["ar"]} for i, w in enumerate(words)]
    system_instruction = f"You are a master Qur'an teacher ({teacher_gender}). Evaluate recitation with professional academic precision. Return precise JSON assessing letter-by-letter Tajweed statuses ('good' or 'review'), word feedback, tafsir summary, and teacher label."
    prompt = f"Evaluate this recitation against the Uthmani text. Strictness: {strictness}.\nExpected words: {json.dumps(expected_text, ensure_ascii=False)}"
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


# ----------------------------- Player HTML with Official @tilawa/core ESM Module -----------------------------

PLAYER_HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* { box-sizing: border-box; }
body { margin: 0; color: #E8D5B5; background: transparent; font-family: Inter, sans-serif; }
.shell { max-width: 1100px; margin: 0 auto; padding: 12px; display: flex; flex-direction: column; gap: 14px; }
.panel { background: rgba(30,25,20,.72); border: 1px solid rgba(212,175,55,.20); border-radius: 20px; padding: 18px; box-shadow: 0 8px 32px rgba(0,0,0,.22); }
.topline { display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap; }
.brand { color: #D4AF37; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; font-size: 12px; }
.meta { color: #a8987f; font-size: 12px; margin-top: 4px; }
.pill { border: 1px solid rgba(212,175,55,.3); color: #D4AF37; border-radius: 99px; padding: 6px 10px; font-size: 12px; }
.arabic-area { direction: rtl; text-align: center; min-height: 210px; max-height: 360px; overflow-y: auto; display: flex; flex-wrap: wrap; justify-content: center; align-content: flex-start; gap: 14px 6px; padding: 10px 5px 18px; }
.word { display: inline-flex; flex-direction: column; align-items: center; padding: 6px 8px; border: 1px solid transparent; border-radius: 12px; min-width: 42px; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); }
.word.active-sheikh { background: rgba(212,175,55,0.35); border-color: #D4AF37; box-shadow: 0 0 22px rgba(212,175,55,0.7); transform: scale(1.08); }
.word.live-active { background: rgba(212,175,55,0.5); border-color: #D4AF37; box-shadow: 0 0 25px rgba(212,175,55,0.9); transform: scale(1.1); }
.word.live-good { background: rgba(74,222,128,0.3); border-color: #4ade80; }
.word.live-error { background: rgba(248,113,113,0.3); border-color: #f87171; }
.arabic-word { font-family: 'Amiri Quran', serif; font-size: 36px; line-height: 1.9; direction: rtl; white-space: nowrap; }
.letter { display: inline-flex; flex-direction: column; align-items: center; vertical-align: middle; border-radius: 6px; margin: 0 1px; padding: 0 2px; }
.letter.good { color: #4ade80 !important; text-shadow: 0 0 10px rgba(74,222,128,0.6); background: rgba(74,222,128,0.1); }
.letter.review { color: #f87171 !important; text-decoration: underline wavy #f87171; text-shadow: 0 0 10px rgba(248,113,113,0.6); background: rgba(248,113,113,0.1); }
.letter.uncertain { color: #fbbf24; }
.letter.ungraded { color: #F4EBDD; }
.letter-char { line-height: 1.35; }
.mark-label { direction: ltr; font: 8px Inter, sans-serif; color: #D4AF37; opacity: .9; white-space: nowrap; line-height: 1.2; }
.translation { color: #a8987f; font-size: 10px; max-width: 125px; text-align: center; line-height: 1.4; margin-top: 3px; }
.audio-box { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
audio { width: 100% !important; }
.live-controls { margin-top: 14px; display: flex; gap: 10px; justify-content: center; align-items: center; flex-direction: column; }
.btn-tilawa { background: #D4AF37; color: #1a1510; border: none; padding: 10px 22px; font-weight: 700; border-radius: 8px; cursor: pointer; transition: background 0.2s; font-size: 14px; }
.btn-tilawa:hover { background: #e6c55c; }
.btn-tilawa.stop { background: #ef4444; color: white; }
.live-status { font-size: 13px; color: #D4AF37; font-style: italic; text-align: center; margin-top: 4px; }
</style>
</head>
<body>
<div id="app"></div>

<script type="module">
  // Load the tracking engine on demand so a CDN failure does not blank the Mushaf.
  let createTilawa, ort;
  async function loadTrackingEngine() {
    const [core, runtime] = await Promise.all([
      import("https://esm.sh/@tilawa/core@next/web"),
      import("https://esm.sh/onnxruntime-web@1.30.0")
    ]);
    if (typeof core.createTilawa !== "function") throw new Error("Tracking engine did not expose createTilawa.");
    createTilawa = core.createTilawa;
    ort = runtime;
  }

  const D = __DATA__;
  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }
  const root = document.getElementById("app");
  const shell = el("div", "shell");
  const header = el("div", "panel topline");
  const headLeft = el("div");
  headLeft.appendChild(el("div", "brand", "Al-Mu'allim Academy · @tilawa/core Engine"));
  const endAyah = D.meta.end && D.meta.end !== D.meta.a ? "–" + D.meta.end : "";
  headLeft.appendChild(el("div", "meta", "Surah " + D.meta.s + " · Ayahs " + D.meta.a + (endAyah)));
  header.appendChild(headLeft);

  const headRight = el("div", "topline");
  headRight.appendChild(el("span", "pill", "⭐ " + (D.meta.xp || 0) + " XP"));
  headRight.appendChild(el("span", "pill", "🔥 " + (D.meta.streak || 0) + " days"));
  header.appendChild(headRight);
  shell.appendChild(header);

  const recitationPanel = el("div", "panel");
  const arabicArea = el("div", "arabic-area");
  const wordNodes = [];

  D.words.forEach((word, index) => {
    const wrapper = el("div", "word");
    const arabic = el("div", "arabic-word");
    (word.letters || []).forEach((letter, letterIndex) => {
      const result = D.letterResults ? D.letterResults[index + ":" + letterIndex] : null;
      const status = result ? result.status : "ungraded";
      const unit = el("span", "letter " + status);
      unit.appendChild(el("span", "letter-char", letter.text));
      if (letter.marks && letter.marks.length) {
        unit.appendChild(el("span", "mark-label", letter.marks.join(" · ")));
      }
      arabic.appendChild(unit);
    });
    wrapper.appendChild(arabic);
    if (word.en && !D.reciteFromMemory) wrapper.appendChild(el("div", "translation", word.en));
    if (D.reciteFromMemory) { arabic.style.filter = "blur(9px)"; arabic.style.transition = "filter 180ms ease"; wrapper.dataset.memoryHidden = "true"; }
    wrapper.appendChild(el("div", "meta", "Ayah " + word.ayah));
    if (D.states && D.states[index]) wrapper.classList.add(D.states[index]);
    arabicArea.appendChild(wrapper);
    wordNodes.push(wrapper);
  });
  recitationPanel.appendChild(arabicArea);

  // Stage 1: Sheikh Listening Audio Player with Exact Quran.com Segments
  const audioBox = el("div", "audio-box");
  const audio = document.createElement("audio");
  audio.controls = true;
  const tracks = Array.isArray(D.audio) ? D.audio : [];
  let trackIndex = 0;

  if (tracks.length) {
    audio.src = tracks[0];
    audioBox.appendChild(audio);
    let lastActiveIdx = -1;

    audio.ontimeupdate = () => {
      if (!audio.duration || isNaN(audio.duration)) return;
      const timeMs = audio.currentTime * 1000;
      const currentAyah = D.meta.a + trackIndex;
      let activeIdx = -1;

      if (D.segments && D.segments.length > 0) {
        const active = D.segments.find(s => s.ayah === currentAyah && timeMs >= s.start && timeMs < s.end);
        if (active) activeIdx = active.word_idx;
      }

      if (activeIdx === -1 && D.trackWordCounts && D.trackWordCounts.length > trackIndex) {
        let startWordIdx = 0;
        for (let i = 0; i < trackIndex; i++) startWordIdx += D.trackWordCounts[i];
        let wordsInThisAyah = D.trackWordCounts[trackIndex];
        const pct = audio.currentTime / audio.duration;
        const relativeIdx = Math.floor(pct * wordsInThisAyah);
        activeIdx = startWordIdx + Math.min(relativeIdx, wordsInThisAyah - 1);
      }

      if (activeIdx !== lastActiveIdx) {
        wordNodes.forEach((node, idx) => {
          if (idx === activeIdx) node.classList.add("active-sheikh");
          else node.classList.remove("active-sheikh");
        });
        if (activeIdx !== -1 && wordNodes[activeIdx]) {
          wordNodes[activeIdx].scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        }
        lastActiveIdx = activeIdx;
      }
    };

    audio.onended = () => {
      trackIndex++;
      lastActiveIdx = -1;
      if (trackIndex < tracks.length) {
        audio.src = tracks[trackIndex];
        audio.play();
      } else {
        wordNodes.forEach(node => node.classList.remove("active-sheikh"));
      }
    };
  }
  recitationPanel.appendChild(audioBox);

  // Stage 2: Client-side Live Tracking via @tilawa/core
  const liveControls = el("div", "live-controls");
  const startLiveBtn = el("button", "btn-tilawa", "🎙️ Start Live Tilawa Tracking");
  const liveStatus = el("div", "live-status", "Click to download/load on-device AI model & start live mic tracking...");
  
  liveControls.appendChild(startLiveBtn);
  recitationPanel.appendChild(liveControls);
  recitationPanel.appendChild(liveStatus);

  let stopTilawaFn = null;
  let isLiveActive = false;
  let starting = false;
  const verseOffsets = [];
  let totalWords = 0;
  (D.trackWordCounts || []).forEach(count => { verseOffsets.push(totalWords); totalWords += count; });
  function globalIndex(location) {
    if (!location || !Number.isInteger(location.word) || location.word < 1) return -1;
    const ayah = Number(location.ayah ?? location.verse ?? D.meta.a);
    const verseIndex = ayah - D.meta.a;
    if (verseIndex < 0 || verseIndex >= verseOffsets.length) return -1;
    if (location.word > D.trackWordCounts[verseIndex]) return -1;
    return verseOffsets[verseIndex] + location.word - 1;
  }
  function showTrackingError(error) {
    const message = String(error?.message || error || "Unknown tracking error");
    const hint = /permission|notallowed|denied/i.test(message) ? " Allow microphone access in your browser settings." : /secure|https/i.test(message) ? " Open this app over HTTPS." : "";
    liveStatus.textContent = "Tracking unavailable: " + message + hint;
  }

  startLiveBtn.onclick = async () => {
    if (!isLiveActive) {
      if (starting) return;
      starting = true;
      startLiveBtn.textContent = "Loading AI Model...";
      startLiveBtn.disabled = true;
      let tilawa = null;
      let mic = null;
      try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone API unavailable. Use HTTPS and a supported browser.");
        await loadTrackingEngine();
        tilawa = await createTilawa({
          ort,
          onProgress: (p) => {
            liveStatus.textContent = `Loading browser model (${p.stage}): ${Math.round(p.fraction * 100)}%`;
          }
        });

        const session = tilawa.startMemorization(
          { surah: D.meta.s, fromAyah: D.meta.a, toAyah: D.meta.end },
          { confirm: { after: "next-word" } }
        );

        session.subscribe((event) => {
          if (event.type === "position" && event.state === "locked" && event.observed?.[0]) {
            const wordIdx = globalIndex(event.observed[0]);
            wordNodes.forEach((node, idx) => {
              node.classList.remove("live-active");
              if (idx === wordIdx) {
                node.classList.add("live-active");
                if (D.reciteFromMemory) { const arabic = node.querySelector(".arabic-word"); if (arabic) arabic.style.filter = "none"; }
                node.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }
            });
            liveStatus.textContent = `Live tracking active · Word ${event.observed[0].word}`;
          }
          if (event.type === "checker" && event.state === "confirmed") {
            const errWordIdx = globalIndex(event.location);
            if (wordNodes[errWordIdx]) {
              if (event.errorClass === "correct") {
                wordNodes[errWordIdx].classList.add("live-good");
              } else {
                wordNodes[errWordIdx].classList.add("live-error");
              }
            }
          }
        });

        mic = await tilawa.listen(session);
        stopTilawaFn = async () => {
          try { await mic?.stop?.(); } finally { await tilawa?.dispose?.(); }
        };

        isLiveActive = true;
        startLiveBtn.textContent = "🛑 Stop Live Tracking";
        startLiveBtn.className = "btn-tilawa stop";
        startLiveBtn.disabled = false;
        liveStatus.textContent = "🔴 Listening live... Speak clearly into your mic!";
      } catch (err) {
        showTrackingError(err);
        try { await mic?.stop?.(); } catch (_) {}
        try { await tilawa?.dispose?.(); } catch (_) {}
        stopTilawaFn = null;
        startLiveBtn.textContent = "🎙️ Start Live Tilawa Tracking";
        startLiveBtn.disabled = false;
      } finally {
        starting = false;
      }
    } else {
      startLiveBtn.disabled = true;
      try { if (stopTilawaFn) await stopTilawaFn(); } catch (err) { showTrackingError(err); }
      stopTilawaFn = null;
      isLiveActive = false;
      startLiveBtn.textContent = "🎙️ Start Live Tilawa Tracking";
      startLiveBtn.className = "btn-tilawa";
      liveStatus.textContent = "Live tracking ended.";
      startLiveBtn.disabled = false;
      wordNodes.forEach(node => node.classList.remove("live-active"));
    }
  };

  window.addEventListener("pagehide", () => { if (stopTilawaFn) void stopTilawaFn(); });
  shell.appendChild(recitationPanel);
  root.appendChild(shell);
</script>
"""

def render_player(words, mode, states=None, audio_tracks=None, feedback="", meta=None, letter_results=None, word_feedback=None, track_word_counts=None, recite_from_memory=False, segments=None):
    payload = {
        "words": words, "mode": mode, "states": states, "audio": audio_tracks or [],
        "feedback": feedback, "meta": meta or {}, "letterResults": letter_results or {},
        "wordFeedback": {str(k): v for k, v in (word_feedback or {}).items()},
        "trackWordCounts": track_word_counts or [], "reciteFromMemory": recite_from_memory,
        "segments": segments or []
    }
    components.html(PLAYER_HTML.replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")), height=620, scrolling=True)


# ----------------------------- Session & UI -----------------------------

DEFAULTS = {"name": "", "surah": 2, "ayah": 60, "end_ayah": 64, "recite_from_memory": False, "results": {}, "paid": [], "tries": 0, "teacher_gender": "Male", "strictness": "Balanced", "theme": "Starry Night", "teacher_label": "Stage 1: Listen to the Sheikh with exact timing sync, then start live browser tracking.", "scholar_chat": []}
for k, v in DEFAULTS.items(): st.session_state.setdefault(k, v)

theme_colours = {"Starry Night": "#0a0f1c", "Brown": "#1A1510", "Black": "#000000"}
st.markdown(f"""
<style>
.stApp {{ background: {theme_colours.get(st.session_state.theme, '#0a0f1c')}; color: #E8D5B5; font-family: Inter, sans-serif; }}
h1, h2, h3, h4 {{ color: #D4AF37 !important; }}
.teacher-container {{
    display: flex; align-items: center; background: rgba(30,25,20,0.85);
    border: 1px solid rgba(212,175,55,0.3); border-radius: 20px; padding: 16px 20px; gap: 20px; margin-bottom: 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}}
.teacher-avatar {{ width: 90px; height: 90px; border-radius: 50%; object-fit: cover; border: 2px solid #D4AF37; box-shadow: 0 0 12px rgba(212,175,55,0.4); }}
.teacher-bubble {{ flex-grow: 1; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 12px 16px; }}
.teacher-name {{ color: #D4AF37; font-weight: 700; font-size: 0.95rem; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.05em; }}
.teacher-speech {{ color: #F3E5AB; font-size: 1.05rem; font-style: italic; }}
.stProgress > div > div > div > div {{ background-color: #D4AF37 !important; }}
</style>
""", unsafe_allow_html=True)

if not st.session_state.name:
    st.markdown("<div style='text-align:center;padding-top:12vh'><h1>Al-Mu'allim</h1><p>Advanced 4-Stage Qur'an Academy</p></div>", unsafe_allow_html=True)
    with st.form("start"):
        name = st.text_input("Your name", placeholder="Enter name")
        if st.form_submit_button("Enter", use_container_width=True) and name.strip():
            st.session_state.name = name.strip()
            st.rerun()
    st.stop()

# Sidebar Setup
sidebar = st.sidebar
sidebar.markdown(f"<h2 style='text-align:center'>{st.session_state.name}</h2>", unsafe_allow_html=True)
st.session_state.theme = sidebar.selectbox("Theme", ["Starry Night", "Brown", "Black"], index=["Starry Night", "Brown", "Black"].index(st.session_state.theme))
st.session_state.teacher_gender = sidebar.selectbox("Teacher Persona", ["Male", "Female"])
st.session_state.strictness = sidebar.select_slider("Strictness", ["Lenient", "Balanced", "Strict"], value=st.session_state.strictness)
sidebar.markdown("---")
st.session_state.recite_from_memory = sidebar.toggle("🧠 Blind Memory Mode", value=st.session_state.recite_from_memory)

surah = sidebar.number_input("Surah", 1, 114, int(st.session_state.surah))
surah_max = AYAHS[int(surah)]
ayah = sidebar.number_input("Starting ayah (Memory Block start)", 1, surah_max, min(int(st.session_state.ayah), surah_max))
end_ayah = sidebar.number_input("Ending ayah (5-Verse block limit)", int(ayah), min(surah_max, int(ayah) + 9), min(surah_max, int(ayah) + 4))
reciter = sidebar.selectbox("Reciter", list(RECITERS.keys()))

if sidebar.button("Load 5-Verse Memory Block", use_container_width=True):
    st.session_state.update(surah=int(surah), ayah=int(ayah), end_ayah=int(end_ayah), tries=0, results={}, teacher_label="Stage 1: Listen to the Sheikh with exact timing sync, then start live browser tracking.")
    st.rerun()

passage_key = f"{surah}:{ayah}-{end_ayah}"
result_key = f"{passage_key}|recitation"

try:
    words, track_word_counts, segments = fetch_passage(surah, ayah, end_ayah, RECITERS[reciter]["id"])
    audio_tracks = [audio_url(surah, a, RECITERS[reciter]["folder"]) for a in range(ayah, end_ayah + 1)]
except Exception as e:
    st.error(f"Error loading passage: {e}")
    st.stop()

xp, streak, _ = get_user(st.session_state.name)
meta = {"s": surah, "a": ayah, "end": end_ayah, "xp": xp, "streak": streak}

st.markdown("<h1 style='text-align:center'>Al-Mu'allim Academy</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center;color:#a8987f'>Surah {surah} · Ayahs {ayah}–{end_ayah} (Advanced 5-Verse Memory Block)</p>", unsafe_allow_html=True)

# Teacher Avatar & Stage Guidance
teacher_name = "Ustadh Omar" if st.session_state.teacher_gender == "Male" else "Ustadha Noor"
active_avatar_b64 = OMAR_B64 if st.session_state.teacher_gender == "Male" else NOOR_B64

st.markdown(f"""
<div class="teacher-container">
    <img src="{active_avatar_b64}" class="teacher-avatar" alt="Teacher Avatar">
    <div class="teacher-bubble">
        <div class="teacher-name">💬 {teacher_name}</div>
        <div class="teacher-speech">"{st.session_state.teacher_label}"</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Render Player with Tilawa Core and Exact Timings
saved = st.session_state.results.get(result_key)
render_player(
    words, "blind" if st.session_state.recite_from_memory else "full",
    states=saved["states"] if saved else None, audio_tracks=audio_tracks,
    feedback=saved["feedback"] if saved else "", meta=meta,
    letter_results=saved["letter_results"] if saved else None,
    word_feedback=saved.get("word_feedback", {}) if saved else None,
    track_word_counts=track_word_counts, recite_from_memory=st.session_state.recite_from_memory, segments=segments
)

st.markdown("<br>", unsafe_allow_html=True)

# Optional Post-Session Deep Analysis Upload
st.markdown("### 🎙️ Stage 3: Deep Tajweed Scoring & Scholarly Feedback")
_, centre, _ = st.columns([1, 2, 1])
with centre:
    recording = st.audio_input("Optional: Upload final recording for deep Gemini Tajweed report", key=f"rec_{passage_key}_{st.session_state.tries}")

if recording:
    st.audio(recording)
    if st.button("Submit for Deep Scholarly Report", type="primary", use_container_width=True):
        progress_bar = st.progress(0, text="Initializing Deep Tajweed analysis...")
        for percent in range(1, 100):
            time.sleep(0.015)
            if percent == 30:
                progress_bar.progress(percent, text="Evaluating harakah & vowel precision (30%)...")
            elif percent == 70:
                progress_bar.progress(percent, text="Compiling 16 Tajweed rules assessment (70%)...")
            elif percent == 90:
                progress_bar.progress(percent, text="Generating scholarly feedback & tafsir (90%)...")

        try:
            states, l_res, w_fb, taj_assess, fb, tafsir, t_label = analyse_recitation(
                recording.getvalue(), recording.type or "audio/wav", words, st.session_state.strictness, st.session_state.teacher_gender
            )
            progress_bar.progress(100, text="Analysis complete!")
            time.sleep(0.3)
            
            st.session_state.teacher_label = t_label
            st.session_state.results[result_key] = {
                "states": states, "letter_results": l_res, "word_feedback": w_fb,
                "tajweed_assessments": taj_assess, "feedback": fb, "tafsir_summary": tafsir
            }
            if states.count("good") / max(len(states), 1) >= 0.8 and result_key not in st.session_state.paid:
                award_xp(st.session_state.name, 10)
                st.session_state.paid.append(result_key)
            st.rerun()
        except Exception as e:
            progress_bar.empty()
            st.error(f"Analysis failed: {e}")

# Stage 3 & 4: Feedback, Corrections & Tafsir Dashboard
if saved:
    st.markdown("---")
    st.markdown("### 🏛️ Stage 3 & 4: Feedback Dashboard & Tafsir Commentary")
    c1, c2 = st.columns(2)
    with c1: 
        st.markdown("#### 🔍 Stage 3: What to Repeat & Correct")
        st.success(saved["feedback"])
    with c2: 
        st.markdown("#### 📖 Stage 4: Tafsir Context & Meaning")
        st.info(saved.get("tafsir_summary", ""))

    st.markdown("#### 🛠️ Detailed 16-Rule Tajweed Breakdown")
    for ta in saved.get("tajweed_assessments", []):
        correctly_applied = ta.get("applied_correctly", True)
        icon = "✅" if correctly_applied else "❌"
        status_text = "Correctly Applied" if correctly_applied else "Requires Repetition"
        with st.expander(f"{icon} Rule {ta.get('rule_id')}: {ta.get('rule_name')} — {ta.get('location')} ({status_text})"):
            st.markdown(f"**Observation:** {ta.get('mistake_description')}")
            st.markdown(f"**Correction:** {ta.get('correction_guide')}")
            st.markdown(f"**Repetition Exercise to Master:** *\"{ta.get('repetition_exercise')}\"*")

    st.markdown("---")
    st.markdown("### 🎓 Stage 4: Ask the Master Teacher (Further Questions & Tafsir)")
    q = st.text_input("Inquiry:", placeholder="Ask about Ibn Kathir's tafsir, makharij, or rule details...")
    if st.button("Consult Scholar", use_container_width=True) and q.strip():
        with st.spinner("Consulting scholar..."):
            ans = ask_teacher_scholar(q.strip(), surah, ayah, end_ayah)
            st.session_state.scholar_chat.append((q.strip(), ans))

    for u_q, s_a in reversed(st.session_state.scholar_chat[-3:]):
        st.markdown(f"**You:** {u_q}\n\n**Scholar:** {s_a}\n---")

    if st.button("🔄 Start New 5-Verse Block Recitation", use_container_width=True):
        st.session_state.results.pop(result_key, None)
        st.session_state.tries += 1
        st.rerun()
