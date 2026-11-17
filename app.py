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

import requests
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# AL-MU'ALLIM — Advanced Qur'an Recitation & 16-Rule Tajweed Academy
# ============================================================

st.set_page_config(
    page_title="Al-Mu'allim",
    page_icon="🕌",
    layout="wide",
    initial_sidebar_state="expanded",
)

QURAN_API = "https://api.quran.com/api/v4"
EVERY_AYAH = "https://everyayah.com/data"
GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"

GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
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
    "Mishary Alafasy": "Alafasy_128kbps",
    "Yasser Al-Dosari": "Yasser_Ad-Dussary_128kbps",
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

TAJWEED_RULES_DEFINITIONS = {
    1: {"name": "Madd Tabii (Natural Madd)", "category": "Madd duration", "desc": "Elongating a harf madd by 2 vowel counts."},
    2: {"name": "Madd Muttasil (Connected Madd)", "category": "Madd duration", "desc": "Madd followed by hamza in the same word (4-5 counts)."},
    3: {"name": "Madd Munfasil (Separated Madd)", "category": "Madd duration", "desc": "Madd at word end followed by hamza in next word (2-5 counts)."},
    4: {"name": "Madd Lazim (Compulsory Madd)", "category": "Madd duration", "desc": "Madd followed by permanent sukoon or shaddah (6 counts)."},
    5: {"name": "Ghunnah (Nasalization)", "category": "Ghunnah", "desc": "Nasal sound for 2 counts on Noon/Meem with shaddah."},
    6: {"name": "Idgham with Ghunnah", "category": "Noon sakinah", "desc": "Merging Noon sakinah into ي, ن, م, و with ghunnah."},
    7: {"name": "Idgham without Ghunnah", "category": "Noon sakinah", "desc": "Merging Noon sakinah into ل or ر without ghunnah."},
    8: {"name": "Ikhfa (Concealment)", "category": "Noon sakinah", "desc": "Concealing Noon sakinah before 15 letters with nasal sound."},
    9: {"name": "Iqlab (Conversion)", "category": "Noon sakinah", "desc": "Converting Noon sakinah into hidden Meem before Baa."},
    10: {"name": "Izhar (Clear Pronunciation)", "category": "Noon sakinah", "desc": "Pronouncing Noon sakinah clearly before throat letters."},
    11: {"name": "Idgham Shafawi", "category": "Meem sakinah", "desc": "Merging Meem sakinah into Meem with ghunnah."},
    12: {"name": "Ikhfa Shafawi", "category": "Meem sakinah", "desc": "Concealing Meem sakinah gently before Baa."},
    13: {"name": "Izhar Shafawi", "category": "Meem sakinah", "desc": "Pronouncing Meem sakinah clearly except before Baa and Meem."},
    14: {"name": "Qalqalah (Echo/Bounce)", "category": "Qalqalah", "desc": "Bouncing sukoon letters (ق ط ب ج د)."},
    15: {"name": "Tafkhim & Tarqiq", "category": "Sifaat", "desc": "Heavy vs light letter pronunciations."},
    16: {"name": "Waqf and Ibtida", "category": "Waqf and ibtida", "desc": "Pausing and resumption rules at verse stops."},
}

HARAKAH_NAMES = {
    "\u064b": "Fathatayn", "\u064c": "Dammatayn", "\u064d": "Kasratayn",
    "\u064e": "Fathah", "\u064f": "Dammah", "\u0650": "Kasrah",
    "\u0651": "Shaddah", "\u0652": "Sukoon", "\u0653": "Maddah",
    "\u0654": "Hamza above", "\u0655": "Hamza below", "\u0670": "Superscript alif",
}


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
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS error_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            rule_name TEXT,
            timestamp TEXT
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


def log_recurring_error(name, rule_name):
    with db() as connection:
        connection.execute(
            "INSERT INTO error_logs(name, rule_name, timestamp) VALUES(?, ?, ?)",
            (name, rule_name, datetime.datetime.now().isoformat()),
        )


# ----------------------------- Qur'an API -----------------------------

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
def fetch_passage(surah, start_ayah, end_ayah):
    passage_words = []
    track_word_counts = []

    for ayah in range(start_ayah, end_ayah + 1):
        verse_words = fetch_words(surah, ayah)
        track_word_counts.append(len(verse_words))
        for word in verse_words:
            item = dict(word)
            item["letters"] = [
                {"text": g, "marks": harakah_labels(g)}
                for g in split_arabic_graphemes(word["ar"])
            ]
            passage_words.append(item)

    if not passage_words:
        raise RuntimeError("No words returned for this passage.")
    return passage_words, track_word_counts


def audio_url(surah, ayah, reciter_folder):
    return f"{EVERY_AYAH}/{reciter_folder}/{surah:03d}{ayah:03d}.mp3"


# ----------------------------- Gemini Interactions API -----------------------------

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
        raise RuntimeError("Unsupported audio format. Please record directly in the browser.")
    return normalized


@st.cache_data(ttl=1800, show_spinner=False)
def get_available_models(api_key_value):
    try:
        response = requests.get(
            GEMINI_MODELS_URL,
            headers={"x-goog-api-key": api_key_value},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise RuntimeError("Network error connecting to Gemini API.") from exc

    if response.status_code in (401, 403):
        raise RuntimeError("Invalid or unauthorized GEMINI_API_KEY.")

    if response.status_code != 200:
        raise RuntimeError(f"Unable to verify Gemini model availability (HTTP {response.status_code}).")

    returned_names = {
        item.get("name", "").removeprefix("models/")
        for item in response.json().get("models", [])
        if isinstance(item, dict)
    }

    available = [m for m in GEMINI_MODELS if m in returned_names]
    if not available:
        raise RuntimeError("None of the supported Gemini Flash models are enabled.")
    return available


def extract_interaction_text(payload):
    status = payload.get("status")
    if status == "failed":
        errors = payload.get("errors") or []
        detail = errors[0].get("message") if errors and isinstance(errors[0], dict) else "Interaction failed."
        raise RuntimeError(f"Gemini interaction failed: {detail}")

    text_chunks = []
    steps = payload.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            if step.get("type") == "model_output":
                for block in step.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_chunks.append(block.get("text", ""))

    if not text_chunks and isinstance(payload.get("outputs"), list):
        for item in payload["outputs"]:
            if isinstance(item, dict) and item.get("type") == "text":
                text_chunks.append(item.get("text", ""))

    combined = "".join(text_chunks).strip()
    if not combined:
        raise RuntimeError("Gemini completed the request but returned no text output.")
    return combined, (status == "incomplete")


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
        "letters": letters,
        "word_feedback": word_feedback,
        "tajweed_assessments": tajweed_assessments,
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
                        "word_i": {"type": "integer"},
                        "letter_i": {"type": "integer"},
                        "status": {"type": "string", "enum": ["good", "review", "uncertain"]},
                        "rule": {"type": "string"},
                        "feedback": {"type": "string"},
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
                        "rule_id": {"type": "integer"},
                        "rule_name": {"type": "string"},
                        "applied_correctly": {"type": "boolean"},
                        "location": {"type": "string"},
                        "mistake_description": {"type": "string"},
                        "correction_guide": {"type": "string"},
                        "repetition_exercise": {"type": "string"},
                    },
                    "required": ["rule_id", "rule_name", "applied_correctly", "location", "mistake_description", "correction_guide", "repetition_exercise"],
                },
            },
        },
        "required": ["teacher_label", "feedback", "tafsir_summary", "letters", "word_feedback", "tajweed_assessments"],
    }


def post_interaction_with_retry(key, base_request_body, candidate_models):
    last_error = "Gemini service temporarily unavailable."
    for model_id in candidate_models:
        request_body = dict(base_request_body, model=model_id)
        for attempt in range(2):
            try:
                response = requests.post(
                    GEMINI_INTERACTIONS_URL,
                    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                    json=request_body,
                    timeout=30,
                )
            except requests.Timeout:
                last_error = f"Request to {model_id} timed out."
                if attempt < 1: continue
                break
            except requests.RequestException:
                raise RuntimeError("Network connection error.")

            if response.status_code == 200:
                return response
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < 1:
                    time.sleep(0.8)
                    continue
                break
            break
    raise RuntimeError(f"{last_error} Please try again.")


def analyse_recitation(audio_bytes, mime_type, words, strictness, teacher_gender):
    key = api_key()
    if not key: raise RuntimeError("API key missing.")
    if not audio_bytes: raise RuntimeError("Audio recording is empty.")

    normalized_mime = normalize_audio_mime_type(mime_type)
    candidate_models = get_available_models(key)
    expected_text = [{"word_i": i, "ayah": w["ayah"], "text": w["ar"]} for i, w in enumerate(words)]

    system_instruction = (
        f"You are a master Qur'an teacher ({teacher_gender}). Evaluate recitation with professional academic precision. "
        "If speech is unclear, set teacher_label to 'I couldn\\'t hear you clearly. Please repeat.' "
        "If there are errors, set teacher_label to encouraing corrective feedback. "
        "Return concise JSON assessing Tajweed rules, word feedback, tafsir summary, and teacher label."
    )

    prompt = f"Evaluate this recitation against the Uthmani text. Strictness: {strictness}.\nExpected words: {json.dumps(expected_text, ensure_ascii=False)}"
    encoded_audio = base64.b64encode(audio_bytes).decode("ascii")

    base_request_body = {
        "system_instruction": system_instruction,
        "store": False,
        "input": [
            {"type": "text", "text": prompt},
            {"type": "audio", "data": encoded_audio, "mime_type": normalized_mime},
        ],
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": tajweed_response_schema(),
        },
        "generation_config": {
            "temperature": 0.1,
            "max_output_tokens": 2048,
        },
    }

    response = post_interaction_with_retry(key, base_request_body, candidate_models)
    response_text, is_incomplete = extract_interaction_text(response.json())
    data = parse_tajweed_json(response_text)

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

    request_body = {
        "system_instruction": system_instruction,
        "store": False,
        "input": [{"type": "text", "text": prompt}],
        "generation_config": {"temperature": 0.3, "max_output_tokens": 1024},
    }

    for model_id in candidate_models:
        try:
            resp = requests.post(GEMINI_INTERACTIONS_URL, headers={"x-goog-api-key": key, "Content-Type": "application/json"}, json=dict(request_body, model=model_id), timeout=20)
            if resp.status_code == 200:
                text, _ = extract_interaction_text(resp.json())
                return text
        except Exception:
            continue
    return "Scholar consultation currently unavailable."


# ----------------------------- Player HTML -----------------------------

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
.arabic-area { direction: rtl; text-align: center; min-height: 210px; max-height: 360px; overflow-y: auto; display: flex; flex-wrap: wrap; justify-content: center; align-content: flex-start; gap: 13px 5px; padding: 10px 5px 18px; }
.word { display: inline-flex; flex-direction: column; align-items: center; padding: 5px 7px; border: 1px solid transparent; border-radius: 12px; min-width: 42px; }
.word.active { background: rgba(212,175,55,.16); border-color: rgba(212,175,55,.65); box-shadow: 0 0 18px rgba(212,175,55,.16); }
.word.good { background: rgba(74,222,128,.09); }
.word.review { background: rgba(248,113,113,.10); }
.word.uncertain { background: rgba(251,191,36,.07); }
.arabic-word { font-family: 'Amiri Quran', serif; font-size: 34px; line-height: 1.9; direction: rtl; white-space: nowrap; }
.letter { display: inline-flex; flex-direction: column; align-items: center; vertical-align: middle; border-radius: 5px; margin: 0 1px; padding: 0 1px; }
.letter.good { color: #4ade80; }
.letter.review { color: #f87171; text-decoration: underline wavy #f87171; }
.letter.uncertain { color: #fbbf24; }
.letter.ungraded { color: #F4EBDD; }
.letter-char { line-height: 1.35; }
.mark-label { direction: ltr; font: 8px Inter, sans-serif; color: #D4AF37; opacity: .9; white-space: nowrap; line-height: 1.2; }
.translit { display: none !important; }
.translation { color: #a8987f; font-size: 10px; max-width: 125px; text-align: center; line-height: 1.4; margin-top: 3px; }
.blind .arabic-word { filter: blur(12px); opacity: .2; user-select: none; }
.audio-controls { display: flex; flex-direction: column; gap: 9px; }
audio { width: 100%; }
</style>
</head>
<body>
<div id="app"></div>
<script>
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
headLeft.appendChild(el("div", "brand", "Al-Mu'allim"));
const endAyah = D.meta.end && D.meta.end !== D.meta.a ? "–" + D.meta.end : "";
headLeft.appendChild(el("div", "meta", "Surah " + D.meta.s + " · Ayah " + D.meta.a + endAyah));
header.appendChild(headLeft);

const headRight = el("div", "topline");
headRight.appendChild(el("span", "pill", "⭐ " + (D.meta.xp || 0) + " XP"));
headRight.appendChild(el("span", "pill", "🔥 " + (D.meta.streak || 0) + " days"));
header.appendChild(headRight);
shell.appendChild(header);

const recitationPanel = el("div", "panel");
const isBlind = D.reciteFromMemory && !D.states;
const arabicArea = el("div", "arabic-area" + (isBlind ? " blind" : ""));
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
  if (word.en) wrapper.appendChild(el("div", "translation", word.en));
  wrapper.appendChild(el("div", "meta", "Ayah " + word.ayah));
  if (D.states && D.states[index]) wrapper.classList.add(D.states[index]);
  arabicArea.appendChild(wrapper);
  wordNodes.push(wrapper);
});
recitationPanel.appendChild(arabicArea);

const audioControls = el("div", "audio-controls");
const audio = document.createElement("audio");
audio.controls = true;
const tracks = Array.isArray(D.audio) ? D.audio : [];
if (tracks.length) {
  audio.src = tracks[0];
  audioControls.appendChild(audio);
}
recitationPanel.appendChild(audioControls);
shell.appendChild(recitationPanel);
root.appendChild(shell);
</script>
</body>
"""

def render_player(words, mode, states=None, audio_tracks=None, feedback="", meta=None, letter_results=None, word_feedback=None, track_word_counts=None, recite_from_memory=False):
    payload = {
        "words": words, "mode": mode, "states": states, "audio": audio_tracks or [],
        "feedback": feedback, "meta": meta or {}, "letterResults": letter_results or {},
        "wordFeedback": {str(k): v for k, v in (word_feedback or {}).items()},
        "trackWordCounts": track_word_counts or [], "reciteFromMemory": recite_from_memory,
    }
    components.html(PLAYER_HTML.replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")), height=620, scrolling=True)


# ----------------------------- Session & UI -----------------------------

DEFAULTS = {"name": "", "surah": 2, "ayah": 60, "end_ayah": 60, "recite_from_memory": False, "results": {}, "paid": [], "tries": 0, "teacher_gender": "Male", "strictness": "Balanced", "theme": "Starry Night", "teacher_label": "I'm listening to your recitation...", "scholar_chat": []}
for k, v in DEFAULTS.items(): st.session_state.setdefault(k, v)

theme_colours = {"Starry Night": "#0a0f1c", "Brown": "#1A1510", "Black": "#000000"}
st.markdown(f"""
<style>
.stApp {{ background: {theme_colours.get(st.session_state.theme, '#0a0f1c')}; color: #E8D5B5; font-family: Inter, sans-serif; }}
h1, h2, h3, h4 {{ color: #D4AF37 !important; }}
.teacher-container {{
    display: flex;
    align-items: center;
    background: rgba(30,25,20,0.85);
    border: 1px solid rgba(212,175,55,0.3);
    border-radius: 20px;
    padding: 16px 20px;
    gap: 20px;
    margin-bottom: 20px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}}
.teacher-avatar {{
    width: 90px;
    height: 90px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid #D4AF37;
    box-shadow: 0 0 12px rgba(212,175,55,0.4);
}}
.teacher-bubble {{
    flex-grow: 1;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 12px 16px;
}}
.teacher-name {{
    color: #D4AF37;
    font-weight: 700;
    font-size: 0.95rem;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.teacher-speech {{
    color: #F3E5AB;
    font-size: 1.05rem;
    font-style: italic;
}}
</style>
""", unsafe_allow_html=True)

if not st.session_state.name:
    st.markdown("<div style='text-align:center;padding-top:12vh'><h1>Al-Mu'allim</h1><p>Advanced Qur'an Academy</p></div>", unsafe_allow_html=True)
    with st.form("start"):
        name = st.text_input("Your name", placeholder="Enter name")
        if st.form_submit_button("Enter", use_container_width=True) and name.strip():
            st.session_state.name = name.strip()
            st.rerun()
    st.stop()

# Sidebar
sidebar = st.sidebar
sidebar.markdown(f"<h2 style='text-align:center'>{st.session_state.name}</h2>", unsafe_allow_html=True)
st.session_state.theme = sidebar.selectbox("Theme", ["Starry Night", "Brown", "Black"], index=["Starry Night", "Brown", "Black"].index(st.session_state.theme))
st.session_state.teacher_gender = sidebar.selectbox("Teacher Persona", ["Male", "Female"])
st.session_state.strictness = sidebar.select_slider("Strictness", ["Lenient", "Balanced", "Strict"], value=st.session_state.strictness)
sidebar.markdown("---")
st.session_state.recite_from_memory = sidebar.toggle("🧠 Recite from memory", value=st.session_state.recite_from_memory)

surah = sidebar.number_input("Surah", 1, 114, int(st.session_state.surah))
surah_max = AYAHS[int(surah)]
ayah = sidebar.number_input("Starting ayah", 1, surah_max, min(int(st.session_state.ayah), surah_max))
end_ayah = sidebar.number_input("Ending ayah", int(ayah), min(surah_max, int(ayah) + 9), min(surah_max, int(st.session_state.end_ayah)))
reciter = sidebar.selectbox("Reciter", list(RECITERS.keys()))

if sidebar.button("Load passage", use_container_width=True):
    st.session_state.update(surah=int(surah), ayah=int(ayah), end_ayah=int(end_ayah), tries=0, results={}, teacher_label="I'm listening to your recitation...")
    st.rerun()

passage_key = f"{surah}:{ayah}-{end_ayah}"
result_key = f"{passage_key}|recitation"

try:
    words, track_word_counts = fetch_passage(surah, ayah, end_ayah)
    audio_tracks = [audio_url(surah, a, RECITERS[reciter]) for a in range(ayah, end_ayah + 1)]
except Exception as e:
    st.error(f"Error loading passage: {e}")
    st.stop()

xp, streak, _ = get_user(st.session_state.name)
meta = {"s": surah, "a": ayah, "end": end_ayah, "xp": xp, "streak": streak}

st.markdown("<h1 style='text-align:center'>Al-Mu'allim</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center;color:#a8987f'>Surah {surah} · Ayahs {ayah}–{end_ayah}</p>", unsafe_allow_html=True)

# Teacher Avatar & Live Status Display (Omar for Male, Noor for Female matching uploaded photo references)
teacher_name = "Ustadh Omar" if st.session_state.teacher_gender == "Male" else "Ustadha Noor"
avatar_url = "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80" if st.session_state.teacher_gender == "Male" else "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150&auto=format&fit=crop&q=80"

st.markdown(f"""
<div class="teacher-container">
    <img src="{avatar_url}" class="teacher-avatar" alt="Teacher Avatar">
    <div class="teacher-bubble">
        <div class="teacher-name">💬 {teacher_name}</div>
        <div class="teacher-speech">"{st.session_state.teacher_label}"</div>
    </div>
</div>
""", unsafe_allow_html=True)

saved = st.session_state.results.get(result_key)
render_player(words, "blind" if st.session_state.recite_from_memory else "full", states=saved["states"] if saved else None, audio_tracks=audio_tracks, feedback=saved["feedback"] if saved else "", meta=meta, letter_results=saved["letter_results"] if saved else None, word_feedback=saved.get("word_feedback", {}) if saved else None, track_word_counts=track_word_counts, recite_from_memory=st.session_state.recite_from_memory)

st.markdown("<br>", unsafe_allow_html=True)
_, centre, _ = st.columns([1, 2, 1])
with centre:
    recording = st.audio_input("🎙 Record live recitation", key=f"rec_{passage_key}_{st.session_state.tries}")

if recording:
    st.audio(recording)
    if st.button("Submit for Live Tajweed Assessment", type="primary", use_container_width=True):
        try:
            with st.spinner("Analyzing live recitation & Tajweed rules..."):
                states, l_res, w_fb, taj_assess, fb, tafsir, t_label = analyse_recitation(
                    recording.getvalue(), recording.type or "audio/wav", words, st.session_state.strictness, st.session_state.teacher_gender
                )
            st.session_state.teacher_label = t_label
            st.session_state.results[result_key] = {"states": states, "letter_results": l_res, "word_feedback": w_fb, "tajweed_assessments": taj_assess, "feedback": fb, "tafsir_summary": tafsir}
            for ta in taj_assess:
                if not ta.get("applied_correctly", True): log_recurring_error(st.session_state.name, ta.get("rule_name", "Tajweed Rule"))
            if states.count("good") / max(len(states), 1) >= 0.8 and result_key not in st.session_state.paid:
                award_xp(st.session_state.name, 10)
                st.session_state.paid.append(result_key)
            st.rerun()
        except Exception as e:
            st.error(f"Analysis failed: {e}")

if saved:
    st.markdown("---")
    st.markdown("### 🏛️ Professional Scholarly Feedback & 16-Rule Assessment Dashboard")
    c1, c2 = st.columns(2)
    with c1: st.success(saved["feedback"])
    with c2: st.info(saved.get("tafsir_summary", ""))

    for ta in saved.get("tajweed_assessments", []):
        icon = "✅" if ta.get("applied_correctly") else "❌"
        with st.expander(f"{icon} Rule {ta.get('rule_id')}: {ta.get('rule_name')} — {ta.get('location')}"):
            st.markdown(f"**Observation:** {ta.get('mistake_description')}")
            st.markdown(f"**Correction:** {ta.get('correction_guide')}")
            st.markdown(f"**Exercise:** *\"{ta.get('repetition_exercise')}\"*")

    st.markdown("---")
    st.markdown("### 🎓 Ask the Master Teacher")
    q = st.text_input("Inquiry:", placeholder="Ask about makharij, rules, or meaning...")
    if st.button("Consult Scholar", use_container_width=True) and q.strip():
        with st.spinner("Consulting..."):
            ans = ask_teacher_scholar(q.strip(), surah, ayah, end_ayah)
            st.session_state.scholar_chat.append((q.strip(), ans))

    for u_q, s_a in reversed(st.session_state.scholar_chat[-3:]):
        st.markdown(f"**You:** {u_q}\n\n**Scholar:** {s_a}\n---")

    if st.button("🔄 New Recording", use_container_width=True):
        st.session_state.results.pop(result_key, None)
        st.session_state.tries += 1
        st.rerun()
