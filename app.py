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

/* Al-Mu'allim immersive Mushaf theme */
:root {color-scheme:dark;--gold:#e5ba57;--gold-soft:#f5d891;--ink:#211710;--cream:#f7ead1;}
body {background:radial-gradient(ellipse at 50% 0%,#493122 0%,#271a14 48%,#170f0c 100%);min-height:100vh;color:var(--cream);}
.shell {max-width:1160px;padding:22px 16px 32px;gap:22px;}
.panel {background:linear-gradient(145deg,rgba(69,49,33,.78),rgba(25,17,13,.9));border:1px solid rgba(232,188,100,.24);border-radius:26px;padding:24px;box-shadow:0 16px 55px #0b08073d;}
.topline {background:transparent;border:none;box-shadow:none;padding:12px 8px;}
.brand {font-size:17px;letter-spacing:.15em;color:var(--gold-soft);}
.meta {font-size:13px;color:#c4ad8e;}
.pill {background:linear-gradient(120deg,#614522,#38291d);border:1px solid #a77c3d;color:#f5d891;padding:10px 15px;font-weight:600;}
.arabic-area {min-height:350px;max-height:650px;gap:22px 7px;padding:34px 16px;scroll-behavior:smooth;scrollbar-color:#927144 transparent;}
.word {padding:8px 10px;min-width:54px;border-radius:15px;}
.arabic-word {font-size:clamp(32px,4.5vw,53px);line-height:2.05;}
.letter {margin:0;padding:0 1px;}
.mark-label {display:none;}
.word.active-sheikh,.word.live-active {transform:none;background:rgba(219,167,66,.19);border:1px solid #e5ba57;box-shadow:0 0 18px #e5ba5740;}
.word.live-good {background:rgba(65,173,123,.14);border-color:#5ecb94;}
.word.live-error {background:rgba(228,109,99,.13);border-color:#e77c70;}
.live-controls {gap:13px;padding:14px 0;}
.btn-tilawa {border-radius:99px;background:linear-gradient(120deg,#f5dfaa,#d6a33c);box-shadow:0 7px 24px #d6a33c44;padding:16px 30px;font-size:15px;min-height:54px;}
.btn-tilawa:focus-visible,.tool-btn:focus-visible {outline:3px solid white;outline-offset:3px;}
.live-status {font-style:normal;line-height:1.6;color:#f0d7a5;}
.audio-box {background:#20171088;border:1px solid #8e6a3c44;padding:14px;border-radius:16px;}
audio {filter:sepia(.25);}
.mushaf-intro {text-align:center;padding:15px 4px 0;color:var(--gold-soft);}
.mushaf-intro .bismillah {font-family:'Amiri Quran',serif;font-size:35px;line-height:2.2;color:#e5ba57;}
.mushaf-intro .ornament {letter-spacing:10px;opacity:.65;}
.study-toolbar {display:flex;gap:9px;flex-wrap:wrap;justify-content:center;margin:10px 0 4px;}
.tool-btn {background:#3e3026;color:#f1d6a3;border:1px solid #b58b4c77;border-radius:100px;padding:10px 14px;cursor:pointer;font:600 12px Inter,sans-serif;}
.tool-btn[aria-pressed="true"] {background:#e5ba57;color:#24180f;}
.tracker-panel {margin-top:14px;background:#19120fc4;border:1px solid #c79a4a55;border-radius:18px;padding:17px;text-align:center;}
.tracker-title {font-weight:700;color:#f5d891;margin-bottom:8px;}
.tracker-hint {font-size:12px;color:#c5b094;line-height:1.6;}
.track-progress {height:7px;border-radius:99px;background:#4d3b2a;overflow:hidden;margin:13px auto 0;max-width:500px;}
.track-progress-fill {height:100%;width:0;background:linear-gradient(90deg,#c18d35,#f4dc9b);transition:width .25s;}
.teacher-note {font-size:12px;color:#d9c09b;line-height:1.5;margin:9px 0;}
@media(max-width:640px){.shell{padding:8px;gap:10px}.panel{padding:12px;border-radius:18px}.arabic-area{max-height:520px;padding:18px 4px;gap:12px 2px}.arabic-word{font-size:32px}.word{padding:5px;min-width:30px}.pill{padding:7px 10px}.brand{font-size:13px}.mushaf-intro .bismillah{font-size:27px}}

/* Continuous Mushaf layout: preserve Arabic joining and avoid translation overlap */
body {background:#241812;}
.shell {max-width:1050px;}
.arabic-area {display:block;direction:rtl;text-align:justify;text-align-last:center;max-height:690px;min-height:300px;overflow-y:auto;padding:26px 22px 44px;line-height:3.05;word-spacing:.15em;scroll-padding-top:80px;}
.word {display:inline;position:relative;min-width:0;padding:0 2px;margin:0 3px;border:0;border-radius:6px;line-height:inherit;vertical-align:baseline;white-space:nowrap;}
.arabic-word {display:inline;font-family:'Amiri Quran',serif;font-size:clamp(33px,4vw,49px);line-height:inherit;direction:rtl;white-space:nowrap;}
.letter {display:inline;vertical-align:baseline;margin:0;padding:0;border-radius:3px;}
.letter-char {display:inline;line-height:inherit;}
.word .meta,.translation {display:none!important;}
.mark-label {display:none!important;}
.verse-marker {font:600 17px Inter,sans-serif;color:#e8c575;display:inline-block;direction:ltr;vertical-align:middle;margin:0 9px;}
.word.active-sheikh,.word.live-active {transform:none;background:#d9aa483b;box-shadow:0 0 0 4px #d9aa4820;border:0;}
.word.live-good {background:#2cae6d36;border:0;}
.word.live-error {background:#ef756b36;border:0;}
.live-controls {margin:10px auto;position:relative;}
.btn-tilawa {font-size:16px;min-height:60px;padding:17px 32px;}
.tracker-panel {background:#1a120e;border-radius:16px;}
.panel {overflow:hidden;}
.stApp {background:#241812!important;}
[data-testid="stHeader"] {background:#241812!important;}
h1,h2,h3 {color:#e9bd61!important;}
.teacher-container {background:#302119!important;border-color:#98723f!important;}
@media(max-width:700px){.arabic-area{padding:15px 9px 30px;line-height:2.85;text-align:right}.arabic-word{font-size:35px}.word{margin:0 2px}.panel{padding:12px}.shell{padding:6px}}

.study-annotations[hidden] {display:none!important;}
.study-annotations {margin-top:20px;padding:18px;background:#211710;border:1px solid #a47b414f;border-radius:20px;}
.study-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:15px;}
.study-entry {border:1px solid #8b6a3d66;background:#35271e;border-radius:12px;padding:12px;text-align:center;min-width:0;}
.study-arabic {font:30px/2 'Amiri Quran',serif;color:#f9ebd5;direction:rtl;}
.study-translit {font:600 13px/1.5 Inter,sans-serif;color:#f0ca80;overflow-wrap:anywhere;}
.study-meaning {font:12px/1.5 Inter,sans-serif;color:#cdbca7;margin-top:5px;}
.study-marks {font:11px/1.7 Inter,sans-serif;color:#e3b65d;margin-top:8px;}
@media(max-width:640px){.study-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.study-entry{padding:8px}}

/* Distinct, readable Qur'an typography: never split shaping letters. */
.arabic-area {font-family:'Amiri Quran',serif;line-height:2.7;text-align:right;}
.word {display:inline-block;white-space:nowrap;vertical-align:baseline;margin:0 2px;padding:0 3px;}
.arabic-word {display:inline;white-space:nowrap;direction:rtl;unicode-bidi:isolate;}
.word.live-heard:not(.live-active){background:rgba(203,173,100,.09);}
.engine-select {font:600 13px Inter,sans-serif;border-radius:12px;background:#34251c;color:#f6dfb0;padding:10px 13px;border:1px solid #99733d;width:min(100%,350px);}
.heard-text {font:12px/1.6 Inter,sans-serif;color:#e9d0a4;max-width:92%;overflow-wrap:anywhere;text-align:center;margin-top:6px;}
.verse-marker {font-family:'Amiri Quran',serif;}

.word {cursor:pointer;}
.word:focus-visible {outline:2px solid #f5d891;outline-offset:2px;}
.word-detail[hidden]{display:none!important;}
.word-detail {margin:14px 0 20px;padding:20px;background:#221710;border:1px solid #e3b65d66;border-radius:18px;text-align:center;}
.word-detail-arabic{font:43px/1.9 'Amiri Quran',serif;direction:rtl;color:#f7e5c3;}
.word-detail-marks{font:12px/1.9 Inter,sans-serif;color:#e0ae65;margin:10px 0 13px;overflow-wrap:anywhere;}
.word-tap-hint{font:12px Inter,sans-serif;color:#cdb890;flex-basis:100%;text-align:center;}

/* English-first cover mode: no Arabic, transliteration or rule labels unless requested. */
.mushaf-intro .bismillah[hidden], .cover-hints[hidden] {display:none!important;}
.cover-english, .cover-verse {display:none;}
.arabic-area.cover-mode {
  direction:ltr;
  display:flex;
  flex-wrap:wrap;
  align-content:flex-start;
  align-items:stretch;
  justify-content:center;
  gap:13px 10px;
  text-align:center;
  line-height:1.5;
  padding:30px 16px;
  font-family:Inter,sans-serif;
}
.arabic-area.cover-mode .word {
  display:inline-flex;
  flex-direction:column;
  justify-content:center;
  align-items:center;
  text-align:center;
  vertical-align:top;
  min-width:108px;
  max-width:215px;
  flex:0 1 auto;
  margin:0;
  padding:14px 12px;
  border-radius:14px;
  border:1px solid rgba(218,176,94,.29);
  background:rgba(70,48,34,.64);
  color:#f5e6ce;
  box-shadow:0 5px 16px rgba(0,0,0,.12);
  white-space:normal;
  overflow-wrap:anywhere;
}
.arabic-area.cover-mode .arabic-word,
.arabic-area.cover-mode .verse-marker {display:none!important;}
.arabic-area.cover-mode .cover-english {
  display:block;
  font:600 clamp(13px,1.5vw,17px)/1.55 Inter,sans-serif;
  color:#f4e4cc;
}
.arabic-area.cover-mode .cover-verse {
  display:block;
  direction:ltr;
  margin-top:5px;
  font:11px Inter,sans-serif;
  color:#d8b772;
}
.arabic-area.cover-mode .cover-hints:not([hidden]) {
  display:flex;
  width:100%;
  flex-direction:column;
  gap:8px;
  margin-top:10px;
  padding-top:10px;
  border-top:1px solid rgba(230,183,99,.2);
}
.cover-transliteration {
  color:#f2cb7e;
  font:600 13px/1.5 Inter,sans-serif;
  overflow-wrap:anywhere;
}
.cover-vowels {display:flex;justify-content:center;flex-wrap:wrap;gap:5px;}
.cover-hint-heading {width:100%;font:11px Inter,sans-serif;color:#cbbb9e;margin-bottom:1px;}
.cover-vowel-chip {
  display:inline-flex;
  padding:4px 6px;
  border-radius:7px;
  background:rgba(202,152,57,.2);
  color:#ffe0a1;
  font:11px/1.5 Inter,sans-serif;
}
.cover-hint-empty {color:#cbbb9e;font:12px Inter,sans-serif;}
.arabic-area.cover-mode .word.live-active {border:1px solid #e4b558;background:rgba(216,172,78,.22);}
@media(max-width:640px) {
  .arabic-area.cover-mode {gap:8px 6px;padding:18px 8px;}
  .arabic-area.cover-mode .word {min-width:100px;max-width:165px;padding:11px 8px;}
  .arabic-area.cover-mode .cover-english {font-size:13px;}
}
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
      import("https://esm.sh/onnxruntime-web@1.30.0/wasm")
    ]);
    if (typeof core.createTilawa !== "function") throw new Error("Tracking engine did not expose createTilawa.");
    createTilawa = core.createTilawa;
    ort = runtime;
    // Safari has no WebGPU on many iPads. Prefer the WASM backend and explicitly
    // resolve its binaries instead of relying on bundler-relative paths.
    if (ort.env?.wasm) {
      ort.env.wasm.wasmPaths = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.30.0/dist/";
      ort.env.wasm.numThreads = 1;
      ort.env.wasm.proxy = false;
    }
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
  headLeft.appendChild(el("div", "brand", "✦ AL-MU\u0027ALLIM · RECITE WITH CLARITY"));
  const endAyah = D.meta.end && D.meta.end !== D.meta.a ? "–" + D.meta.end : "";
  headLeft.appendChild(el("div", "meta", "Surah " + D.meta.s + " · Ayahs " + D.meta.a + (endAyah)));
  header.appendChild(headLeft);

  const headRight = el("div", "topline");
  headRight.appendChild(el("span", "pill", "⭐ " + (D.meta.xp || 0) + " XP"));
  headRight.appendChild(el("span", "pill", "🔥 " + (D.meta.streak || 0) + " days"));
  header.appendChild(headRight);
  shell.appendChild(header);

  const recitationPanel = el("div", "panel");
  const intro = el("div", "mushaf-intro");
  intro.appendChild(el("div", "ornament", "✦ ───── ✦"));
  // A passage beginning mid-surah should not imply the basmalah is part of that ayah.
  if(Number(D.meta.a)===1 && Number(D.meta.s)!==9){
    intro.appendChild(el("div", "bismillah", "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"));
  }
  recitationPanel.appendChild(intro);
  const toolbar = el("div", "study-toolbar");
  const memoryBtn = el("button", "tool-btn", D.reciteFromMemory ? "◉ Cover mode" : "◉ Reading mode");
  memoryBtn.type = "button";
  memoryBtn.setAttribute("aria-pressed", String(!!D.reciteFromMemory));
  const marksBtn = el("button", "tool-btn", "Show vowels + transliteration");
  marksBtn.type = "button";
  marksBtn.setAttribute("aria-pressed", "false");
  toolbar.append(memoryBtn, marksBtn);
  const toolbarHint = el("span", "word-tap-hint", "Tap an Arabic word to study it");
  toolbar.append(toolbarHint);
  recitationPanel.appendChild(toolbar);
  const arabicArea = el("div", "arabic-area");
  arabicArea.setAttribute("lang", "ar");
  arabicArea.setAttribute("aria-label", "Qur'an passage in Uthmani script");
  const wordNodes = [];

  D.words.forEach((word, index) => {
    const wrapper = el("div", "word");
    const arabic = el("div", "arabic-word");
    // Render each word as one text node so Arabic shaping remains intact.
    // Splitting connected Arabic letters across spans destroys the Mushaf typography.
    arabic.textContent = word.ar || (word.letters || []).map(l => l.text).join("");
    arabic.setAttribute("lang", "ar");
    wrapper.title = "Tap to study this word";
    wrapper.tabIndex = 0;
    wrapper.setAttribute("role", "button");
    wrapper.setAttribute("aria-label", "Word " + (index + 1) + " study controls");
    wrapper.onclick = () => showWordDetails(index);
    wrapper.onkeydown = (event) => {
      if(event.key==="Enter" || event.key===" "){event.preventDefault();showWordDetails(index);}
    };
    wrapper.appendChild(arabic);
    // Cover mode displays an English clue, not a blurred Arabic word.
    const englishClue = el("span", "cover-english", word.en || "Meaning unavailable");
    wrapper.appendChild(englishClue);
    const coverHints = el("div", "cover-hints");
    coverHints.hidden = true;
    if (word.tr) coverHints.appendChild(el("div", "cover-transliteration", word.tr));
    const vowelNames = (word.letters || []).flatMap(letter => letter.marks || []);
    if (vowelNames.length) {
      const vowels = el("div", "cover-vowels");
      vowels.appendChild(el("div", "cover-hint-heading", "Vowel & letter signs"));
      vowelNames.forEach(mark => vowels.appendChild(el("span", "cover-vowel-chip", mark)));
      coverHints.appendChild(vowels);
    }
    if (!word.tr && !vowelNames.length) {
      coverHints.appendChild(el("span", "cover-hint-empty", "No pronunciation hints available"));
    }
    wrapper.appendChild(coverHints);
    if (index === D.words.length - 1 || D.words[index + 1].ayah !== word.ayah) {
      const arabicNumber=String(word.ayah).replace(/[0-9]/g,d=>"٠١٢٣٤٥٦٧٨٩"[Number(d)]);
      wrapper.appendChild(el("span", "verse-marker", "۝" + arabicNumber));
      wrapper.appendChild(el("span", "cover-verse", "Ayah " + word.ayah));
    }
    if (D.states && D.states[index]) wrapper.classList.add(D.states[index]);
    arabicArea.appendChild(wrapper);
    wordNodes.push(wrapper);
  });
  recitationPanel.appendChild(arabicArea);
  const detailPanel = el("div", "word-detail");
  detailPanel.hidden = true;
  detailPanel.setAttribute("aria-live", "polite");
  recitationPanel.appendChild(detailPanel);
  function showWordDetails(index) {
    if (memoryHidden) {
      const hints = wordNodes[index]?.querySelector(".cover-hints");
      if (hints) {
        hints.hidden = !hints.hidden;
        if (!hints.hidden) wordNodes[index].scrollIntoView({behavior:"smooth",block:"nearest"});
      }
      return;
    }
    const word = D.words[index];
    if(!word) return;
    detailPanel.replaceChildren();
    detailPanel.appendChild(el("div", "tracker-title", "✦ Word " + (index+1) + " · Ayah " + word.ayah));
    detailPanel.appendChild(el("div", "word-detail-arabic", word.ar || ""));
    if(word.tr) detailPanel.appendChild(el("div", "study-translit", word.tr));
    if(word.en) detailPanel.appendChild(el("div", "study-meaning", word.en));
    const marks=(word.letters||[]).flatMap(letter => (letter.marks||[]).map(mark => mark+" · "+letter.text));
    if(marks.length)detailPanel.appendChild(el("div", "word-detail-marks", marks.join("  |  ")));
    const audioButton=el("button", "tool-btn", "▶ Listen to this ayah");
    audioButton.type="button";
    audioButton.onclick=()=>{
      const ayahIndex=word.ayah-D.meta.a;
      const available=D.audio||[];
      if(ayahIndex<0 || ayahIndex>=available.length)return;
      audio.pause();
      audio.src=available[ayahIndex];
      trackIndex=ayahIndex;
      audio.currentTime=0;
      audio.play().catch(()=>{liveStatus.textContent="Audio playback could not start. Try the audio controls.";});
    };
    detailPanel.appendChild(audioButton);
    detailPanel.hidden=false;
  }
  const studyPanel = el("div", "study-annotations");
  studyPanel.hidden = true;
  studyPanel.appendChild(el("div", "tracker-title", "Word-by-word pronunciation guide"));
  const studyGrid = el("div", "study-grid");
  D.words.forEach((word, index) => {
    const entry = el("div", "study-entry");
    entry.appendChild(el("div", "study-arabic", (word.letters || []).map(l => l.text).join("")));
    if (word.tr) entry.appendChild(el("div", "study-translit", word.tr));
    if (word.en) entry.appendChild(el("div", "study-meaning", word.en));
    const marks = (word.letters || []).flatMap(l => (l.marks || []).map(m => m + " (" + l.text + ")"));
    if (marks.length) entry.appendChild(el("div", "study-marks", marks.join(" · ")));
    studyGrid.appendChild(entry);
  });
  studyPanel.appendChild(studyGrid);
  recitationPanel.appendChild(studyPanel);
  let memoryHidden = !!D.reciteFromMemory;
  let hintsVisible = false;
  function applyDisplayMode() {
    const cover = memoryHidden;
    arabicArea.classList.toggle("cover-mode", cover);
    arabicArea.setAttribute("lang", cover ? "en" : "ar");
    arabicArea.setAttribute("aria-label", cover
      ? "English memory clues. Tap a clue to reveal its pronunciation hints."
      : "Qur'an passage in Uthmani script");
    memoryBtn.textContent = cover ? "◉ Cover mode" : "◉ Reading mode";
    memoryBtn.setAttribute("aria-pressed", String(cover));
    marksBtn.textContent = hintsVisible
      ? "Hide hints"
      : (cover ? "Show hints" : "Show vowels + transliteration");
    marksBtn.setAttribute("aria-pressed", String(hintsVisible));
    toolbarHint.textContent = cover
      ? "English clues only · tap a clue for its transliteration and vowel hints"
      : "Tap an Arabic word to study it";
    studyPanel.hidden = cover || !hintsVisible;
    const basmalah = intro.querySelector(".bismillah");
    if (basmalah) basmalah.hidden = cover;
    if (cover) detailPanel.hidden = true;
    wordNodes.forEach((node,index) => {
      node.title = cover ? "Tap for pronunciation hints" : "Study this word";
      node.setAttribute("aria-label", cover
        ? "English clue "+(index+1)+": "+(D.words[index].en || "Meaning unavailable")+". Tap for pronunciation hints."
        : "Study Arabic word "+(D.words[index].tr || D.words[index].ar));
      const hints=node.querySelector(".cover-hints");
      if(hints) hints.hidden = !cover || !hintsVisible;
    });
  }
  memoryBtn.onclick = () => {
    memoryHidden = !memoryHidden;
    hintsVisible = false;
    applyDisplayMode();
  };
  marksBtn.onclick = () => {
    hintsVisible = !hintsVisible;
    applyDisplayMode();
    if (hintsVisible && !memoryHidden) {
      studyPanel.scrollIntoView({behavior:"smooth",block:"nearest"});
    }
  };
  applyDisplayMode();

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
  // Audio playback is secondary to live recitation.
  recitationPanel.appendChild(audioBox);

  // Stage 2: Client-side Live Tracking via @tilawa/core
  const liveControls = el("div", "live-controls");
  const startLiveBtn = el("button", "btn-tilawa", "🎙️ Start Live Tilawa Tracking");
  const liveStatus = el("div", "live-status", "Click to download/load on-device AI model & start live mic tracking...");
  
  const trackerPanel = el("div", "tracker-panel");
  trackerPanel.appendChild(el("div", "tracker-title", "✦ Your live recitation"));
  trackerPanel.appendChild(el("div", "tracker-hint", "Follow along as you recite. Gold indicates the detected word; green and coral indicate provisional checks. Tajweed detail requires separate review."));
  const progressTrack = el("div", "track-progress");
  const progressFill = el("div", "track-progress-fill");
  progressTrack.appendChild(progressFill);
  trackerPanel.appendChild(progressTrack);
  liveControls.appendChild(trackerPanel);
  liveControls.appendChild(startLiveBtn);
  recitationPanel.insertBefore(liveControls, arabicArea);
  recitationPanel.insertBefore(liveStatus, arabicArea);

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
    const hint = /permission|notallowed|denied/i.test(message) ? " Allow microphone access in Safari settings." : /wasm|webgpu|onnx|module script|backend/i.test(message) ? " The browser could not initialise the speech model. Try desktop Chrome; iPad Safari support is not yet confirmed. This is not a pronunciation mistake." : /secure|https/i.test(message) ? " Open this app over HTTPS." : "";
    liveStatus.textContent = "Tracking unavailable: " + message + hint;
  }


  // Browser speech following is a lightweight fallback for iPad Safari.
  // It tracks approximate word positions. It NEVER claims to score tajweed.
  const engineSelect = el("select", "engine-select");
  [["auto","Automatic · recommended"],["browser","Browser speech · iPad friendly"],["onnx","On-device AI · experimental"]]
    .forEach(([value,label]) => {
      const option = el("option", "", label);
      option.value = value; engineSelect.appendChild(option);
    });
  engineSelect.setAttribute("aria-label", "Live tracking engine");
  const engineHelp = el("div", "tracker-hint",
    "iPad mode: browser speech follows approximate Arabic words and may use your browser's speech service. Experimental local AI loads a large model. Detailed Tajweed still requires recording review and teacher verification.");
  engineSelect.value="auto";
  liveControls.insertBefore(engineSelect, startLiveBtn);
  liveControls.insertBefore(engineHelp, startLiveBtn);
  const heardText = el("div", "heard-text");
  heardText.setAttribute("role", "status");
  liveControls.appendChild(heardText);

  function normalizeArabic(input) {
    return String(input || "")
      .normalize("NFKD")
      .replace(/[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]/g, "")
      .replace(/[ٱأإآا]/g,"ا")
      .replace(/[ى]/g,"ي")
      .replace(/[ؤ]/g,"و")
      .replace(/[ئ]/g,"ي")
      .replace(/[ة]/g,"ه")
      .replace(/[^\u0621-\u064A\s]/g,"")
      .replace(/\s+/g," ").trim();
  }
  const expectedWords = D.words.map(w => normalizeArabic(w.ar || (w.letters || []).map(l => l.text).join("")));
  function smallEditDistance(a,b) {
    if (a === b) return 0;
    if (Math.abs(a.length-b.length)>1) return 2;
    let d = Array.from({length:b.length+1},(_,i)=>i);
    for(let i=1;i<=a.length;i++){
      let previous=d[0]; d[0]=i;
      for(let j=1;j<=b.length;j++){
        const stored=d[j];
        d[j]=Math.min(d[j]+1,d[j-1]+1,previous+(a[i-1]===b[j-1]?0:1));
        previous=stored;
      }
    }
    return d[b.length];
  }
  function matchSpeech(phrase, start) {
    const heard = normalizeArabic(phrase).split(/\s+/).filter(Boolean);
    let cursor=start, last=-1;
    for (const token of heard) {
      let found=-1;
      // Do not jump far ahead based on a single ambiguous word.
      for(let i=Math.max(0,cursor);i<Math.min(expectedWords.length,cursor+7);i++){
        const target=expectedWords[i];
        if(!target)continue;
        if(target===token || (token.length>=5 && target.length>=5 && smallEditDistance(target,token)<=1)){
          found=i;break;
        }
      }
      if(found>=0){last=found;cursor=found+1;}
    }
    return last;
  }
  function showCurrentWord(index, confirmed) {
    if(index<0||index>=wordNodes.length)return;
    wordNodes.forEach((node,i)=>{
      node.classList.toggle("live-active",i===index);
      if(confirmed && i<=index){
        node.classList.add("live-heard");
        // Never reveal Arabic automatically in Cover mode; the English clue remains the test.
      }
    });
    const node=wordNodes[index];
    if(node)node.scrollIntoView({behavior:"smooth",block:"nearest",inline:"center"});
    progressFill.style.width=Math.round((index+1)*100/Math.max(wordNodes.length,1))+"%";
  }
  async function startBrowserTracking(reason) {
    const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!SpeechRecognition)throw new Error("This browser does not offer live speech recognition. Try Safari or Chrome, or use the recording and review feature below.");
    let recognition = new SpeechRecognition();
    recognition.lang="ar-SA";
    recognition.continuous=true;
    recognition.interimResults=true;
    recognition.maxAlternatives=1;
    let stopped=false, confirmedCursor=0, lastObserved=-1;
    recognition.onresult=(event)=>{
      let interim="";
      let finalized="";
      for(let i=event.resultIndex;i<event.results.length;i++){
        const item=event.results[i];
        const phrase=item?.[0]?.transcript || "";
        if(item.isFinal)finalized+=" "+phrase;
        else interim+=" "+phrase;
      }
      if(finalized.trim()){
        const match=matchSpeech(finalized,confirmedCursor);
        if(match>=0){
          confirmedCursor=Math.max(confirmedCursor,match+1);
          showCurrentWord(match,true);
          lastObserved=match;
        }
      }
      if(interim.trim()){
        const match=matchSpeech(interim,confirmedCursor);
        if(match>=0) {showCurrentWord(match,false);lastObserved=match;}
      }
      const heard=(finalized+" "+interim).trim();
      if(heard) {
        heardText.textContent="Heard (approximate): "+heard.slice(0,150);
        liveStatus.textContent=lastObserved>=0
          ? "Live word following · word "+(lastObserved+1)+" of "+wordNodes.length
          : "Listening · speech received, waiting for a Quran word match";
      }
    };
    recognition.onerror=(event)=>{
      if(stopped)return;
      liveStatus.textContent="Browser speech recognition: "+(event.error||"unknown error")+
        ". This browser may restrict recognition in an embedded Streamlit player.";
    };
    recognition.onend=()=>{
      if(stopped)return;
      isLiveActive=false;
      stopTilawaFn=null;
      startLiveBtn.disabled=false;
      startLiveBtn.className="btn-tilawa";
      startLiveBtn.textContent="🎙️ Start Live Tracking";
      liveStatus.textContent="Speech recognition ended. Tap Start to begin another listening session.";
    };
    try {recognition.start();} catch(error) {
      throw new Error("Browser microphone could not start: "+(error?.message||error));
    }
    stopTilawaFn=async()=>{
      stopped=true;
      try {recognition.stop();}catch(_){}
      recognition.onresult=null;
      recognition.onerror=null;
      recognition.onend=null;
      recognition=null;
    };
    isLiveActive=true;
    startLiveBtn.className="btn-tilawa stop";
    startLiveBtn.textContent="■ Stop live tracking";
    startLiveBtn.disabled=false;
    liveStatus.textContent=reason || "Listening for Arabic words. Position estimates are not pronunciation grades.";
    heardText.textContent="Speak clearly in Arabic. The gold highlight follows detected words.";
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
        const isAppleMobile=/iPad|iPhone|iPod/.test(navigator.userAgent) ||
          (navigator.platform==="MacIntel" && navigator.maxTouchPoints>1);
        if(engineSelect.value==="browser" || (engineSelect.value==="auto" && isAppleMobile)){
          await startBrowserTracking("Using browser speech following (iPad mode). This is an approximate word position, not a Tajweed score.");
          return;
        }
        if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone API unavailable. Use HTTPS and a supported browser.");
        await loadTrackingEngine();
        liveStatus.textContent = "Preparing the speech model. On iPad this may take time; the browser must support WebAssembly.";
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
                // In Cover mode, only English clues and explicitly requested hints are shown.
                node.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }
            });
            if (wordIdx >= 0) progressFill.style.width = Math.round(100 * (wordIdx + 1) / Math.max(1, wordNodes.length)) + "%";
            liveStatus.textContent = wordIdx >= 0 ? `Following your recitation · Word ${wordIdx + 1} of ${wordNodes.length}` : "Listening · waiting for a confirmed position";
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
        if(engineSelect.value==="auto" && (window.SpeechRecognition||window.webkitSpeechRecognition)){
          try {
            await startBrowserTracking("The local model could not load, so browser speech following is active. This is approximate and may use your browser provider.");
            return;
          } catch(fallbackError) {
            showTrackingError(new Error(String(err?.message||err)+"; browser speech: "+String(fallbackError?.message||fallbackError)));
          }
        } else {
          showTrackingError(err);
        }
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
      heardText.textContent="";
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
    components.html(PLAYER_HTML.replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")), height=850, scrolling=True)


# ----------------------------- Session & UI -----------------------------

DEFAULTS = {"name": "", "surah": 2, "ayah": 60, "end_ayah": 64, "recite_from_memory": False, "results": {}, "paid": [], "tries": 0, "teacher_gender": "Male", "strictness": "Balanced", "theme": "Starry Night", "teacher_label": "Stage 1: Listen to the Sheikh with exact timing sync, then start live browser tracking.", "scholar_chat": []}
for k, v in DEFAULTS.items(): st.session_state.setdefault(k, v)

theme_colours = {"Starry Night": "#0a0f1c", "Brown": "#1A1510", "Black": "#000000"}
st.markdown(f"""
<style>
.stApp {{ background: #241812; color: #E8D5B5; font-family: Inter, sans-serif; }}
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
st.session_state.recite_from_memory = sidebar.toggle("🧠 Cover mode · English clues", value=st.session_state.recite_from_memory)

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

st.markdown("<h1 style='text-align:center;font-size:clamp(1.5rem,4vw,2.4rem)'>✦ Al-Mu'allim ✦</h1>", unsafe_allow_html=True)
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
st.markdown("### 🎙️ Stage 3: Recorded Recitation Review")
st.caption("AI-assisted practice feedback, not a certified teacher's Tajweed assessment. Subtle vowel and articulation details may be uncertain.")
_, centre, _ = st.columns([1, 2, 1])
with centre:
    recording = st.audio_input("Record a short passage for optional AI review", key=f"rec_{passage_key}_{st.session_state.tries}")

if recording:
    st.audio(recording)
    if st.button("Review my recording with AI", type="primary", use_container_width=True):
        try:
            with st.spinner("Reviewing your recording..."):
                states, l_res, w_fb, taj_assess, fb, tafsir, t_label = analyse_recitation(
                    recording.getvalue(), recording.type or "audio/wav", words,
                    st.session_state.strictness, st.session_state.teacher_gender
                )

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
            st.error(f"AI recording review failed: {e}")

# Stage 3 & 4: Feedback, Corrections & Tafsir Dashboard
if saved:
    st.markdown("---")
    st.markdown("### 🏛️ Stage 3 & 4: Feedback Dashboard & Tafsir Commentary")
    c1, c2 = st.columns(2)
    with c1: 
        st.markdown("#### 🔍 Stage 3: What to Repeat & Correct")
        st.info(saved["feedback"])
    with c2: 
        st.markdown("#### 📖 Stage 4: Tafsir Context & Meaning")
        st.info(saved.get("tafsir_summary", ""))

    st.markdown("#### 🛠️ Possible Tajweed Practice Points")
    st.caption("Preliminary AI observations: verify subtle makharij, harakat and elongation with a qualified teacher.")
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
