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
# AL-MU'ALLIM — Qur'an recitation practice and Tajweed feedback
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

# Primary model followed by Interactions API fallback models for 503 high-demand spikes
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

# Number of ayahs in each surah, indexed from 1.
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

# Arabic combining marks used for harakah / Tajweed display.
HARAKAH_NAMES = {
    "\u064b": "Fathatayn",
    "\u064c": "Dammatayn",
    "\u064d": "Kasratayn",
    "\u064e": "Fathah",
    "\u064f": "Dammah",
    "\u0650": "Kasrah",
    "\u0651": "Shaddah",
    "\u0652": "Sukoon",
    "\u0653": "Maddah",
    "\u0654": "Hamza above",
    "\u0655": "Hamza below",
    "\u0670": "Superscript alif",
}


# ----------------------------- Database -----------------------------

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
        connection.execute(
            "INSERT OR IGNORE INTO users(name) VALUES(?)", (name,)
        )
        row = connection.execute(
            "SELECT xp, streak, last_day FROM users WHERE name=?",
            (name,),
        ).fetchone()
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


# ----------------------------- Qur'an API -----------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_words(surah, ayah):
    response = requests.get(
        f"{QURAN_API}/verses/by_key/{surah}:{ayah}",
        params={
            "words": "true",
            "word_fields": "text_uthmani",
            "language": "en",
        },
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

        output.append(
            {
                "ar": arabic,
                "en": (item.get("translation") or {}).get("text", ""),
                "tr": (item.get("transliteration") or {}).get("text", ""),
                "ayah": int(ayah),
            }
        )

    if not output:
        raise RuntimeError(f"No words were returned for {surah}:{ayah}.")

    return output


def split_arabic_graphemes(text):
    """Keep each Arabic base character together with its combining marks."""
    graphemes = []

    for character in text:
        if unicodedata.category(character).startswith("M") and graphemes:
            graphemes[-1] += character
        else:
            graphemes.append(character)

    return graphemes


def harakah_labels(grapheme):
    return [
        HARAKAH_NAMES[character]
        for character in grapheme
        if character in HARAKAH_NAMES
    ]


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
                {
                    "text": grapheme,
                    "marks": harakah_labels(grapheme),
                }
                for grapheme in split_arabic_graphemes(word["ar"])
            ]
            passage_words.append(item)

    if not passage_words:
        raise RuntimeError("No words were returned for this passage.")

    return passage_words, track_word_counts


def audio_url(surah, ayah, reciter_folder):
    return (
        f"{EVERY_AYAH}/{reciter_folder}/"
        f"{surah:03d}{ayah:03d}.mp3"
    )


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
    aliases = {
        "audio/x-wav": "audio/wav",
        "audio/wave": "audio/wav",
        "audio/mpeg": "audio/mp3",
    }
    normalized = aliases.get(cleaned, cleaned)

    if normalized not in SUPPORTED_AUDIO_MIME_TYPES:
        raise RuntimeError(
            f"Unsupported audio format ({cleaned}). Please record directly in the browser "
            "or upload WAV, MP3, OGG, FLAC, AAC, AIFF, or WEBM audio."
        )

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
        raise RuntimeError(
            "Network error while connecting to the Gemini API. "
            "Check your internet connection and try again."
        ) from exc

    if response.status_code in (401, 403):
        raise RuntimeError(
            "Invalid or unauthorized GEMINI_API_KEY. Verify your key in "
            "Streamlit secrets or environment variables."
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Unable to verify Gemini model availability (HTTP {response.status_code})."
        )

    returned_names = {
        item.get("name", "").removeprefix("models/")
        for item in response.json().get("models", [])
        if isinstance(item, dict)
    }

    available = [m for m in GEMINI_MODELS if m in returned_names]
    if not available:
        raise RuntimeError(
            "None of the supported Gemini Flash models are enabled for this API key."
        )

    return available


def extract_interaction_text(payload):
    status = payload.get("status")
    if status == "failed":
        errors = payload.get("errors") or []
        detail = (
            errors[0].get("message")
            if errors and isinstance(errors[0], dict)
            else "Interaction failed."
        )
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
        raise RuntimeError(
            "Gemini completed the request but returned no text output."
        )

    return combined, (status == "incomplete")


def parse_tajweed_json(raw_text, is_incomplete=False):
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text.strip()).strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    letters = []
    word_feedback = []

    letters_match = re.search(r'"letters"\s*:\s*\[', cleaned)
    words_match = re.search(r'"word_feedback"\s*:\s*\[', cleaned)

    if letters_match:
        end_pos = words_match.start() if words_match else len(cleaned)
        letters_section = cleaned[letters_match.end():end_pos]
        for obj_match in re.finditer(r'\{[^{}]*\}', letters_section):
            try:
                letters.append(json.loads(obj_match.group(0)))
            except Exception:
                continue

    if words_match:
        words_section = cleaned[words_match.end():]
        for obj_match in re.finditer(r'\{[^{}]*\}', words_section):
            try:
                word_feedback.append(json.loads(obj_match.group(0)))
            except Exception:
                continue

    feedback_match = re.search(r'"feedback"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    overall_feedback = ""
    if feedback_match:
        try:
            overall_feedback = json.loads(f'"{feedback_match.group(1)}"')
        except Exception:
            overall_feedback = feedback_match.group(1)

    if letters or word_feedback:
        if is_incomplete and not overall_feedback:
            overall_feedback = (
                "Partial assessment recovered."
            )
        return {
            "letters": letters,
            "word_feedback": word_feedback,
            "feedback": overall_feedback,
        }

    raise RuntimeError(
        "Gemini response was truncated. Please try recording a shorter passage."
    )


def tajweed_response_schema():
    return {
        "type": "object",
        "properties": {
            "letters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "word_i": {"type": "integer"},
                        "letter_i": {"type": "integer"},
                        "status": {
                            "type": "string",
                            "enum": ["good", "review", "uncertain"],
                        },
                        "rule": {"type": "string"},
                        "feedback": {"type": "string"},
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                    },
                    "required": [
                        "word_i",
                        "letter_i",
                        "status",
                        "rule",
                        "feedback",
                        "confidence",
                    ],
                },
            },
            "word_feedback": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "word_i": {"type": "integer"},
                        "status": {
                            "type": "string",
                            "enum": ["good", "review", "uncertain"],
                        },
                        "feedback": {"type": "string"},
                    },
                    "required": ["word_i", "status", "feedback"],
                },
            },
            "feedback": {"type": "string"},
        },
        "required": ["letters", "word_feedback", "feedback"],
    }


def post_interaction_with_retry(key, base_request_body, candidate_models):
    last_error = "Gemini service is temporarily unavailable."

    for model_id in candidate_models:
        request_body = dict(base_request_body, model=model_id)

        for attempt in range(2):
            try:
                response = requests.post(
                    GEMINI_INTERACTIONS_URL,
                    headers={
                        "x-goog-api-key": key,
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                    timeout=60,
                )
            except requests.Timeout:
                last_error = f"Request to {model_id} timed out."
                if attempt < 1:
                    time.sleep(1.0)
                    continue
                break
            except requests.RequestException as exc:
                raise RuntimeError(
                    "Network failure while sending the recording to Gemini."
                ) from exc

            if response.status_code == 200:
                return response

            detail = f"HTTP {response.status_code}"
            try:
                err_obj = response.json().get("error", {})
                if isinstance(err_obj, dict) and err_obj.get("message"):
                    detail = err_obj["message"]
            except Exception:
                if response.text:
                    detail = response.text[:300]

            if response.status_code in (401, 403):
                raise RuntimeError("Gemini API authentication failed. Check your key.")
            if response.status_code == 400:
                raise RuntimeError(f"Gemini rejected the request: {detail}")
            if response.status_code == 404:
                last_error = f"Model '{model_id}' is unavailable."
                break

            if response.status_code in (429, 500, 502, 503, 504):
                last_error = f"Gemini request failed ({response.status_code}): {detail}"
                if attempt < 1:
                    time.sleep(1.5 + random.uniform(0.1, 0.5))
                    continue
                break

            raise RuntimeError(f"Gemini request failed ({response.status_code}): {detail}")

    raise RuntimeError(f"{last_error} Please try again.")


def analyse_recitation(
    audio_bytes,
    mime_type,
    words,
    strictness,
    teacher_gender,
):
    key = api_key()
    if not key:
        raise RuntimeError("Gemini API key missing in Streamlit secrets.")

    if not audio_bytes:
        raise RuntimeError("The audio recording is empty.")

    if len(audio_bytes) > 12_000_000:
        raise RuntimeError("Recording is too large (> 12MB).")

    normalized_mime = normalize_audio_mime_type(mime_type)
    candidate_models = get_available_models(key)

    teacher_description = (
        "a knowledgeable male Qur'an recitation teacher"
        if teacher_gender == "Male"
        else "a knowledgeable female Qur'an recitation teacher"
    )

    expected_text = []
    for word_index, word in enumerate(words):
        expected_text.append(
            {
                "word_i": word_index,
                "ayah": word["ayah"],
                "text": word["ar"],
                "letters": [
                    {"letter_i": letter_index, "text": letter["text"]}
                    for letter_index, letter in enumerate(word["letters"])
                ],
            }
        )

    system_instruction = (
        f"You are {teacher_description} evaluating Qur'anic recitation with Tajweed. "
        "Assess strictly what is audibly present against the exact Uthmani text. "
        "Never invent mistakes. Distinguish clearly between 'review' (error) and 'uncertain'."
    )

    prompt = f"""
Assess the attached Qur'an recitation audio against the exact Uthmani text supplied below.
Strictness level: {strictness}.

Expected text:
{json.dumps(expected_text, ensure_ascii=False)}
"""

    encoded_audio = base64.b64encode(audio_bytes).decode("ascii")

    base_request_body = {
        "system_instruction": system_instruction,
        "store": False,
        "input": [
            {
                "type": "text",
                "text": prompt,
            },
            {
                "type": "audio",
                "data": encoded_audio,
                "mime_type": normalized_mime,
            },
        ],
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": tajweed_response_schema(),
        },
        "generation_config": {
            "temperature": 0.1,
            "max_output_tokens": 8192,
        },
    }

    response = post_interaction_with_retry(key, base_request_body, candidate_models)

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Gemini returned a non-JSON HTTP response.") from exc

    response_text, is_incomplete = extract_interaction_text(payload)
    data = parse_tajweed_json(response_text, is_incomplete=is_incomplete)

    letter_results = {}
    for item in data.get("letters", []):
        if not isinstance(item, dict):
            continue
        word_index = item.get("word_i")
        letter_index = item.get("letter_i")

        if not isinstance(word_index, int) or not isinstance(letter_index, int):
            continue
        if not 0 <= word_index < len(words):
            continue
        if not 0 <= letter_index < len(words[word_index]["letters"]):
            continue

        status = item.get("status", "uncertain")
        if status not in ("good", "review", "uncertain"):
            status = "uncertain"

        confidence = str(item.get("confidence", "low")).lower()
        if confidence not in ("high", "medium", "low"):
            confidence = "low"

        if confidence == "low" and status == "good":
            status = "uncertain"

        letter_results[f"{word_index}:{letter_index}"] = {
            "status": status,
            "rule": str(item.get("rule", "")),
            "feedback": str(item.get("feedback", "")),
            "confidence": confidence,
        }

    states = ["uncertain"] * len(words)
    word_feedback = {}

    for item in data.get("word_feedback", []):
        if not isinstance(item, dict):
            continue
        word_index = item.get("word_i")
        if not isinstance(word_index, int) or not 0 <= word_index < len(words):
            continue

        status = item.get("status", "uncertain")
        if status not in ("good", "review", "uncertain"):
            status = "uncertain"

        states[word_index] = status
        word_feedback[word_index] = str(item.get("feedback", ""))

    overall_feedback = str(data.get("feedback", "")).strip()
    if not overall_feedback:
        overall_feedback = "Assessment complete."

    return states, letter_results, word_feedback, overall_feedback


# ----------------------------- Audio / Arabic player -----------------------------

PLAYER_HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* { box-sizing: border-box; }
body {
  margin: 0;
  color: #E8D5B5;
  background: transparent;
  font-family: Inter, sans-serif;
}
.shell {
  max-width: 1100px;
  margin: 0 auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.panel {
  background: rgba(30,25,20,.72);
  border: 1px solid rgba(212,175,55,.20);
  border-radius: 20px;
  padding: 18px;
  box-shadow: 0 8px 32px rgba(0,0,0,.22);
}
.topline {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.brand {
  color: #D4AF37;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  font-size: 12px;
}
.meta { color: #a8987f; font-size: 12px; margin-top: 4px; }
.pill {
  border: 1px solid rgba(212,175,55,.3);
  color: #D4AF37;
  border-radius: 99px;
  padding: 6px 10px;
  font-size: 12px;
}
.arabic-area {
  direction: rtl;
  text-align: center;
  min-height: 210px;
  max-height: 360px;
  overflow-y: auto;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-content: flex-start;
  gap: 13px 5px;
  padding: 10px 5px 18px;
}
.word {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  padding: 5px 7px;
  border: 1px solid transparent;
  border-radius: 12px;
  min-width: 42px;
}
.word.active {
  background: rgba(212,175,55,.16);
  border-color: rgba(212,175,55,.65);
  box-shadow: 0 0 18px rgba(212,175,55,.16);
}
.word.good { background: rgba(74,222,128,.09); }
.word.review { background: rgba(248,113,113,.10); }
.word.uncertain { background: rgba(251,191,36,.07); }
.arabic-word {
  font-family: 'Amiri Quran', serif;
  font-size: 34px;
  line-height: 1.9;
  direction: rtl;
  white-space: nowrap;
}
.letter {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  vertical-align: middle;
  border-radius: 5px;
  margin: 0 1px;
  padding: 0 1px;
}
.letter.good { color: #4ade80; }
.letter.review { color: #f87171; text-decoration: underline wavy #f87171; }
.letter.uncertain { color: #fbbf24; }
.letter.ungraded { color: #F4EBDD; }
.letter-char { line-height: 1.35; }
.mark-label {
  direction: ltr;
  font: 8px Inter, sans-serif;
  color: #D4AF37;
  opacity: .9;
  white-space: nowrap;
  line-height: 1.2;
}
.translit { color: #D4AF37; font-size: 10px; font-style: italic; }
.translation {
  color: #a8987f;
  font-size: 10px;
  max-width: 125px;
  text-align: center;
  line-height: 1.4;
  margin-top: 3px;
}
.blind .arabic-word {
  filter: blur(12px);
  opacity: .2;
  user-select: none;
}
.audio-controls { display: flex; flex-direction: column; gap: 9px; }
audio { width: 100%; }
.trackline { color: #a8987f; font-size: 12px; text-align: center; }
.feedback-grid {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 12px;
}
.feedback-card {
  background: rgba(255,255,255,.035);
  border: 1px solid rgba(255,255,255,.07);
  border-radius: 14px;
  padding: 14px;
}
.feedback-title {
  color: #D4AF37;
  font-weight: 700;
  font-size: 12px;
  text-transform: uppercase;
  margin-bottom: 7px;
}
.feedback-text { color: #d8cbb8; font-size: 13px; line-height: 1.6; }
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #a8987f;
  font-size: 11px;
}
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; }
@media(max-width:600px) {
  .feedback-grid { grid-template-columns: 1fr; }
  .arabic-word { font-size: 29px; }
}
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
// Dynamic class injection based on Recite from Memory toggle state
const isBlind = D.reciteFromMemory && !D.states;
const arabicArea = el("div", "arabic-area" + (isBlind ? " blind" : ""));
const wordNodes = [];

function renderWord(word, index) {
  const wrapper = el("div", "word");
  wrapper.dataset.index = index;

  const arabic = el("div", "arabic-word");
  const letters = word.letters || [];

  letters.forEach((letter, letterIndex) => {
    const result = D.letterResults
      ? D.letterResults[index + ":" + letterIndex]
      : null;
    const status = result ? result.status : "ungraded";

    const unit = el("span", "letter " + status);
    const character = el("span", "letter-char", letter.text);
    unit.appendChild(character);

    if (letter.marks && letter.marks.length) {
      unit.appendChild(el("span", "mark-label", letter.marks.join(" · ")));
    }

    if (result) {
      const detail = [
        result.rule || "",
        result.feedback || "",
        result.confidence ? "Confidence: " + result.confidence : ""
      ].filter(Boolean).join(" — ");
      if (detail) unit.title = detail;
    }

    arabic.appendChild(unit);
  });

  wrapper.appendChild(arabic);

  if (word.tr) wrapper.appendChild(el("div", "translit", word.tr));
  if (word.en) wrapper.appendChild(el("div", "translation", word.en));
  wrapper.appendChild(el("div", "meta", "Ayah " + word.ayah));

  if (D.states && D.states[index]) {
    wrapper.classList.add(D.states[index]);
  }

  arabicArea.appendChild(wrapper);
  wordNodes.push(wrapper);
}

D.words.forEach(renderWord);
recitationPanel.appendChild(arabicArea);

const audioControls = el("div", "audio-controls");
const audio = document.createElement("audio");
audio.controls = true;
audio.preload = "metadata";

const tracks = Array.isArray(D.audio) ? D.audio : (D.audio ? [D.audio] : []);
const counts = D.trackWordCounts || [];
let trackIndex = 0;
let activeWord = -1;

function wordsBeforeTrack(index) {
  return counts.slice(0, index).reduce((sum, n) => sum + n, 0);
}

function setActiveWord(index) {
  if (index < 0 || index >= wordNodes.length) return;
  if (activeWord >= 0 && wordNodes[activeWord]) {
    wordNodes[activeWord].classList.remove("active");
  }
  activeWord = index;
  wordNodes[index].classList.add("active");
  wordNodes[index].scrollIntoView({
    behavior: "smooth",
    block: "nearest",
    inline: "center"
  });
}

audio.addEventListener("timeupdate", () => {
  const count = counts[trackIndex] || 0;
  if (!count || !audio.duration || !isFinite(audio.duration)) return;
  const localIndex = Math.min(
    count - 1,
    Math.floor((audio.currentTime / audio.duration) * count)
  );
  setActiveWord(wordsBeforeTrack(trackIndex) + localIndex);
});

audio.addEventListener("ended", () => {
  if (trackIndex + 1 < tracks.length) loadTrack(trackIndex + 1, true);
});

function loadTrack(index, autoplay) {
  if (index < 0 || index >= tracks.length) return;
  trackIndex = index;
  audio.src = tracks[index];
  audio.load();
  if (autoplay) audio.play().catch(() => {});
}

if (tracks.length) {
  audioControls.appendChild(audio);
  loadTrack(0, false);
}
recitationPanel.appendChild(audioControls);
shell.appendChild(recitationPanel);

if (D.feedback) {
  const feedbackGrid = el("div", "feedback-grid");
  const judged = (D.states || []).filter(s => s === "good" || s === "review");
  const correct = (D.states || []).filter(s => s === "good").length;
  const accuracy = judged.length ? Math.round(correct / judged.length * 100) : null;

  const scoreCard = el("div", "feedback-card");
  scoreCard.appendChild(el("div", "feedback-title", "Word assessment"));
  scoreCard.appendChild(el("div", "feedback-text",
    accuracy === null ? "Assessment complete." : accuracy + "% accuracy."
  ));
  feedbackGrid.appendChild(scoreCard);

  const overallCard = el("div", "feedback-card");
  overallCard.appendChild(el("div", "feedback-title", "Teacher feedback"));
  overallCard.appendChild(el("div", "feedback-text", D.feedback));
  feedbackGrid.appendChild(overallCard);
  shell.appendChild(feedbackGrid);
}

root.appendChild(shell);
</script>
</body>
"""


def render_player(
    words,
    mode,
    states=None,
    audio_tracks=None,
    feedback="",
    meta=None,
    letter_results=None,
    word_feedback=None,
    track_word_counts=None,
    recite_from_memory=False,
):
    payload = {
        "words": words,
        "mode": mode,
        "states": states,
        "audio": audio_tracks or [],
        "feedback": feedback,
        "meta": meta or {},
        "letterResults": letter_results or {},
        "wordFeedback": {str(k): v for k, v in (word_feedback or {}).items()},
        "trackWordCounts": track_word_counts or [],
        "reciteFromMemory": recite_from_memory,
    }
    serialized = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = PLAYER_HTML.replace("__DATA__", serialized)
    components.html(html, height=620, scrolling=True)


# ----------------------------- Session state -----------------------------

DEFAULTS = {
    "name": "",
    "surah": 2,
    "ayah": 60,
    "end_ayah": 60,
    "recite_from_memory": False,
    "results": {},
    "paid": [],
    "tries": 0,
    "teacher_gender": "Male",
    "strictness": "Balanced",
    "theme": "Starry Night",
}

for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)


# ----------------------------- Styling -----------------------------

theme_colours = {
    "Starry Night": "#0a0f1c",
    "Brown": "#1A1510",
    "Black": "#000000",
}
bg_color = theme_colours.get(st.session_state.theme, "#0a0f1c")

st.markdown(
    f"""
    <style>
    .stApp {{
        background: {bg_color};
        color: #E8D5B5;
        font-family: Inter, sans-serif;
    }}
    [data-testid="stSidebar"] {{
        background: rgba(10, 8, 6, .88);
        border-right: 1px solid #D4AF3733;
    }}
    h1, h2, h3 {{
        color: #D4AF37 !important;
        font-family: Georgia, serif !important;
    }}
    div.stButton > button {{
        background: linear-gradient(135deg, #D4AF37, #F3E5AB);
        color: #1A1510;
        border: none;
        border-radius: 999px;
        font-weight: 700;
        min-height: 44px;
    }}
    div.stButton > button:hover {{
        border: 1px solid #fff;
        color: #1A1510;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------- Welcome screen -----------------------------

if not st.session_state.name:
    st.markdown(
        """
        <div style="text-align:center;padding-top:12vh">
          <div style="font-size:58px">🕌</div>
          <h1 style="font-size:3.4rem">Al-Mu'allim</h1>
          <p style="color:#a8987f">Qur'an recitation and Tajweed practice</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("start_form"):
        name = st.text_input("Your name", placeholder="Enter your name")
        submitted = st.form_submit_button("Enter Academy", use_container_width=True)

    if submitted and name.strip():
        st.session_state.name = name.strip()
        st.rerun()

    st.stop()


# ----------------------------- Sidebar -----------------------------

sidebar = st.sidebar
sidebar.markdown(
    f"<h2 style='text-align:center'>{st.session_state.name}</h2>",
    unsafe_allow_html=True,
)

theme_options = ["Starry Night", "Brown", "Black"]
st.session_state.theme = sidebar.selectbox(
    "Theme",
    theme_options,
    index=theme_options.index(st.session_state.theme),
)

st.session_state.teacher_gender = sidebar.selectbox(
    "Teacher voice",
    ["Male", "Female"],
    index=["Male", "Female"].index(st.session_state.teacher_gender),
)

st.session_state.strictness = sidebar.select_slider(
    "Assessment strictness",
    options=["Lenient", "Balanced", "Strict"],
    value=st.session_state.strictness,
)

sidebar.markdown("---")

# Tilawa-style "Recite from memory" interactive toggle switch
st.session_state.recite_from_memory = sidebar.toggle(
    "🧠 Recite from memory",
    value=st.session_state.recite_from_memory,
    help="When enabled, the text stays hidden so you can recite from memory and get checked."
)

sidebar.markdown("---")
surah_input = sidebar.number_input(
    "Surah",
    min_value=1,
    max_value=114,
    value=int(st.session_state.surah),
    step=1,
)

surah_max = AYAHS[int(surah_input)]
ayah_input = sidebar.number_input(
    "Starting ayah",
    min_value=1,
    max_value=surah_max,
    value=min(int(st.session_state.ayah), surah_max),
    step=1,
)

max_end = min(surah_max, int(ayah_input) + 9)
default_end = max(
    int(ayah_input),
    min(int(st.session_state.end_ayah), max_end),
)

end_input = sidebar.number_input(
    "Ending ayah",
    min_value=int(ayah_input),
    max_value=max_end,
    value=default_end,
    step=1,
    help="Select up to ten ayahs at a time.",
)

reciter = sidebar.selectbox("Reciter audio", list(RECITERS.keys()))

if sidebar.button("Load passage", use_container_width=True):
    st.session_state.update(
        surah=int(surah_input),
        ayah=int(ayah_input),
        end_ayah=int(end_input),
        tries=0,
        results={},
    )
    st.rerun()


# ----------------------------- Load passage -----------------------------

surah = int(st.session_state.surah)
start_ayah = int(st.session_state.ayah)
end_ayah = max(
    start_ayah,
    min(int(st.session_state.end_ayah), AYAHS[surah]),
)

passage_key = f"{surah}:{start_ayah}-{end_ayah}"
result_key = f"{passage_key}|recitation"

try:
    with st.spinner("Loading Qur'an text..."):
        words, track_word_counts = fetch_passage(
            surah, start_ayah, end_ayah
        )

    audio_tracks = [
        audio_url(surah, ayah, RECITERS[reciter])
        for ayah in range(start_ayah, end_ayah + 1)
    ]

except Exception as error:
    st.error(f"Unable to load the passage: {error}")
    st.stop()

xp, streak, _ = get_user(st.session_state.name)
meta = {
    "s": surah,
    "a": start_ayah,
    "end": end_ayah,
    "xp": xp,
    "streak": streak,
}


# ----------------------------- Main content (Live Tilawa Style) -----------------------------

st.markdown(
    "<h1 style='text-align:center'>Al-Mu'allim</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<p style='text-align:center;color:#a8987f'>"
    f"Surah {surah} · Ayahs {start_ayah}–{end_ayah}</p>",
    unsafe_allow_html=True,
)

saved_result = st.session_state.results.get(result_key)

# Render player with current memorization toggle state
render_player(
    words,
    mode="blind" if st.session_state.recite_from_memory else "full",
    states=saved_result["states"] if saved_result else None,
    audio_tracks=audio_tracks,
    feedback=saved_result["feedback"] if saved_result else "",
    meta=meta,
    letter_results=saved_result["letter_results"] if saved_result else None,
    word_feedback=saved_result.get("word_feedback", {}) if saved_result else None,
    track_word_counts=track_word_counts,
    recite_from_memory=st.session_state.recite_from_memory,
)

st.markdown("<br>", unsafe_allow_html=True)

# Direct record widget for immediate live submission
left, centre, right = st.columns([1, 2, 1])
with centre:
    recording = st.audio_input(
        "🎙 Record your recitation",
        key=f"recording_{passage_key}_{st.session_state.tries}",
    )

if recording is not None:
    st.audio(recording)

    if st.button("Submit for Live Tajweed Analysis", type="primary", use_container_width=True):
        try:
            with st.spinner("Analyzing recitation quickly..."):
                states, letter_results, word_feedback, feedback = analyse_recitation(
                    recording.getvalue(),
                    recording.type or "audio/wav",
                    words,
                    st.session_state.strictness,
                    st.session_state.teacher_gender,
                )

            st.session_state.results[result_key] = {
                "states": states,
                "letter_results": letter_results,
                "word_feedback": word_feedback,
                "feedback": feedback,
            }

            judged = [s for s in states if s in ("good", "review")]
            correct = states.count("good")

            if judged and correct / len(judged) >= 0.8 and result_key not in st.session_state.paid:
                award_xp(st.session_state.name, 10)
                st.session_state.paid.append(result_key)

            st.rerun()

        except Exception as error:
            st.error(f"Tajweed analysis failed: {error}")

if saved_result:
    if st.button("🔄 Try Again / New Recording", use_container_width=True):
        st.session_state.results.pop(result_key, None)
        st.session_state.tries += 1
        st.rerun()
