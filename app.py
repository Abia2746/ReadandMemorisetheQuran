import base64
import datetime
import json
import os
import pathlib
import re
import sqlite3
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


# ----------------------------- Gemini API -----------------------------

def api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")


@st.cache_data(ttl=1800, show_spinner=False)
def get_available_flash_model(api_key_value):
    """
    Ask the Gemini API which models this key can access.
    This avoids hard-coding retired or unavailable model IDs.
    """
    response = requests.get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        headers={"x-goog-api-key": api_key_value},
        timeout=15,
    )
    response.raise_for_status()

    models = response.json().get("models", [])
    available = []

    for model in models:
        methods = model.get("supportedGenerationMethods", [])
        name = model.get("name", "")

        if "generateContent" in methods and "flash" in name.lower():
            available.append(name)

    if not available:
        raise RuntimeError(
            "No Flash model supporting generateContent is available to this "
            "API key. Check that the key belongs to the correct Google "
            "Cloud project and that the Gemini API is enabled."
        )

    # Prefer a current, efficient model if it is actually available.
    preferences = (
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    )

    for preferred in preferences:
        matches = [name for name in available if name.endswith(preferred)]
        if matches:
            return matches[0]

    # Otherwise use the first Flash model returned by Google's API.
    return available[0]


def analyse_recitation(
    audio_bytes,
    mime_type,
    words,
    strictness,
    teacher_gender,
):
    key = api_key()
    if not key:
        raise RuntimeError(
            "Gemini API key missing. Add GEMINI_API_KEY to Streamlit secrets."
        )

    if len(audio_bytes) > 12_000_000:
        raise RuntimeError(
            "The recording is too large. Please record a shorter passage."
        )

    model_name = get_available_flash_model(key)

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

    prompt = f"""
You are {teacher_description}. Assess the attached recording of Qur'an
recitation against the exact Uthmani text supplied below.

Strictness: {strictness}.

Assess only what can reasonably be heard. Do not invent errors. If you
cannot confidently identify a sound or align it to a particular letter,
mark it "uncertain", not "review".

Pay attention to:
- Fathah, kasrah, dammah and tanween
- Sukoon and shaddah
- Madd and its duration
- Ghunnah
- Qalqalah
- Idgham, ikhfa, iqlab and izhar
- Letter articulation and clarity

The supplied text is divided into indexed words and indexed letter-graphemes.
Use the exact indexes. Do not rewrite or alter the Qur'anic text.

Return JSON only in this structure:
{{
  "letters": [
    {{
      "word_i": 0,
      "letter_i": 0,
      "status": "good",
      "rule": "Fathah",
      "feedback": "The vowel is clear.",
      "confidence": "high"
    }}
  ],
  "word_feedback": [
    {{
      "word_i": 0,
      "status": "good",
      "feedback": "The word was recited clearly."
    }}
  ],
  "feedback": "Brief overall feedback and priorities for practice."
}}

Allowed letter and word statuses: good, review, uncertain.
Use "review" only for an audible issue you can identify with reasonable
confidence. Use "uncertain" when the audio is unclear or alignment is
uncertain. Do not claim to measure exact millisecond durations unless
they are reliably apparent.

Expected text:
{json.dumps(expected_text, ensure_ascii=False)}
"""

    request_body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type or "audio/webm",
                            "data": base64.b64encode(audio_bytes).decode("utf-8"),
                        },
                    },
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1,
            "maxOutputTokens": 3500,
        },
    }

    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent",
        headers={"x-goog-api-key": key},
        json=request_body,
        timeout=75,
    )

    if response.status_code != 200:
        try:
            detail = response.json().get("error", {}).get("message", response.text)
        except Exception:
            detail = response.text

        raise RuntimeError(
            f"Gemini request failed ({response.status_code}): {detail}"
        )

    payload = response.json()

    try:
        candidate = payload["candidates"][0]
        response_text = "".join(
            part.get("text", "")
            for part in candidate["content"]["parts"]
        )
        response_text = re.sub(
            r"^```(?:json)?|```$",
            "",
            response_text.strip(),
        ).strip()
        data = json.loads(response_text)
    except Exception as exc:
        raise RuntimeError(
            "Gemini returned a response that could not be read as JSON. "
            "Try a shorter recording."
        ) from exc

    # Validate the letter-level feedback indexes.
    letter_results = {}
    for item in data.get("letters", []):
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

        letter_results[f"{word_index}:{letter_index}"] = {
            "status": status,
            "rule": str(item.get("rule", "")),
            "feedback": str(item.get("feedback", "")),
            "confidence": str(item.get("confidence", "unknown")),
        }

    # Word status defaults to uncertain; unreturned words are not assumed good.
    states = ["uncertain"] * len(words)
    word_feedback = {}

    for item in data.get("word_feedback", []):
        word_index = item.get("word_i")
        if not isinstance(word_index, int) or not 0 <= word_index < len(words):
            continue

        status = item.get("status", "uncertain")
        if status not in ("good", "review", "uncertain"):
            status = "uncertain"

        states[word_index] = status
        word_feedback[word_index] = str(item.get("feedback", ""))

    overall_feedback = str(data.get("feedback", ""))
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
  filter: blur(11px);
  opacity: .25;
  user-select: none;
}
.audio-controls { display: flex; flex-direction: column; gap: 9px; }
audio { width: 100%; }
.trackline { color: #a8987f; font-size: 12px; text-align: center; }
.feedback-grid {
  display: grid;
  grid-template-columns: 140px 1fr;
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
const arabicArea = el("div", "arabic-area" + (D.mode === "blind" && !D.states ? " blind" : ""));
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
    } else if (letter.marks && letter.marks.length) {
      unit.title = letter.marks.join(", ");
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

function loadTrack(index, autoplay) {
  if (index < 0 || index >= tracks.length) return;
  trackIndex = index;
  audio.src = tracks[index];
  audio.load();
  trackLabel.textContent = "Playing ayah " + (D.meta.a + index) +
    " of " + (D.meta.end || D.meta.a);
  if (autoplay) {
    audio.play().catch(() => {
      trackLabel.textContent += " — press Play if playback was blocked";
    });
  }
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
  else trackLabel.textContent = "Passage finished";
});

const trackLabel = el("div", "trackline", "");
if (tracks.length) {
  audioControls.appendChild(audio);
  audioControls.appendChild(trackLabel);
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
    accuracy === null ? "Not enough confidently judged words for a score."
      : accuracy + "% of confidently judged words marked correct."
  ));
  feedbackGrid.appendChild(scoreCard);

  const overallCard = el("div", "feedback-card");
  overallCard.appendChild(el("div", "feedback-title", "Teacher feedback"));
  overallCard.appendChild(el("div", "feedback-text", D.feedback));
  feedbackGrid.appendChild(overallCard);
  shell.appendChild(feedbackGrid);
}

const legend = el("div", "legend");
[
  ["#4ade80", "Good"],
  ["#f87171", "Review"],
  ["#fbbf24", "Uncertain"],
  ["#F4EBDD", "Not assessed"]
].forEach(([colour, label]) => {
  const item = el("span");
  const dot = el("span", "dot");
  dot.style.background = colour;
  item.appendChild(dot);
  item.appendChild(document.createTextNode(label));
  legend.appendChild(item);
});
shell.appendChild(legend);
root.appendChild(shell);
</script>
</body>
</html>
"""


def render_player(
    words,
    mode,
    states=None,
    audio_tracks=None,
    feedback="",
    meta=None,
    letter_results=None,
    track_word_counts=None,
):
    payload = {
        "words": words,
        "mode": mode,
        "states": states,
        "audio": audio_tracks or [],
        "feedback": feedback,
        "meta": meta or {},
        "letterResults": letter_results or {},
        "trackWordCounts": track_word_counts or [],
    }
    serialized = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = PLAYER_HTML.replace("__DATA__", serialized)
    components.html(html, height=680, scrolling=True)


# ----------------------------- Session state -----------------------------

DEFAULTS = {
    "name": "",
    "surah": 2,
    "ayah": 60,
    "end_ayah": 60,
    "step": 0,
    "count": 0,
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
        step=0,
        count=0,
        tries=0,
        results={},
    )
    st.rerun()

sidebar.caption("Passage playback supports up to 10 ayahs per selection.")


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


# ----------------------------- Main content -----------------------------

st.markdown(
    "<h1 style='text-align:center'>Al-Mu'allim</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<p style='text-align:center;color:#a8987f'>"
    f"Surah {surah} · Ayahs {start_ayah}–{end_ayah}</p>",
    unsafe_allow_html=True,
)

step = st.session_state.step
step_titles = [
    "Step 1 · Listen and repeat",
    "Step 2 · Memorise and recite",
    "Step 3 · Review with your teacher",
]
st.markdown(
    f"<h3 style='text-align:center'>{step_titles[min(step, 2)]}</h3>",
    unsafe_allow_html=True,
)


def listen_step():
    render_player(
        words,
        "full",
        audio_tracks=audio_tracks,
        meta=meta,
        track_word_counts=track_word_counts,
    )

    st.markdown(
        f"<p style='text-align:center;color:#a8987f'>"
        f"Repetitions: {st.session_state.count} / 5</p>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    if col1.button("I repeated once", use_container_width=True):
        st.session_state.count += 1
        if st.session_state.count >= 5:
            st.session_state.update(step=1, count=0)
        st.rerun()

    if col2.button("Skip", use_container_width=True):
        st.session_state.update(step=1, count=0)
        st.rerun()


def record_step():
    saved_result = st.session_state.results.get(result_key)

    if saved_result is None:
        render_player(
            words,
            "blind",
            audio_tracks=audio_tracks,
            meta=meta,
            track_word_counts=track_word_counts,
        )

        st.markdown(
            """
            <p style='text-align:center;font-size:1.1rem;
            color:#D4AF37;font-weight:600'>
            🎙 Record your recitation of the selected passage
            </p>
            """,
            unsafe_allow_html=True,
        )

        left, centre, right = st.columns([1, 2, 1])
        with centre:
            recording = st.audio_input(
                "Record recitation",
                key=f"recording_{passage_key}_{st.session_state.tries}",
            )

        if recording is not None:
            st.audio(recording)

            if st.button(
                "Submit for Tajweed analysis",
                type="primary",
                use_container_width=True,
            ):
                try:
                    with st.spinner(
                        "Listening to your recitation and preparing feedback..."
                    ):
                        states, letter_results, word_feedback, feedback = (
                            analyse_recitation(
                                recording.getvalue(),
                                recording.type or "audio/webm",
                                words,
                                st.session_state.strictness,
                                st.session_state.teacher_gender,
                            )
                        )

                    st.session_state.results[result_key] = {
                        "states": states,
                        "letter_results": letter_results,
                        "word_feedback": word_feedback,
                        "feedback": feedback,
                    }

                    judged = [
                        state for state in states
                        if state in ("good", "review")
                    ]
                    correct = states.count("good")

                    if (
                        judged
                        and correct / len(judged) >= 0.8
                        and result_key not in st.session_state.paid
                    ):
                        award_xp(st.session_state.name, 10)
                        st.session_state.paid.append(result_key)

                    st.rerun()

                except Exception as error:
                    st.error(str(error))

        return

    show_result(saved_result)


def show_result(result):
    render_player(
        words,
        "review",
        states=result["states"],
        meta=meta,
        feedback=result["feedback"],
        letter_results=result["letter_results"],
    )

    st.markdown("#### Word-by-word feedback")

    rows = []
    for index, word in enumerate(words):
        status = result["states"][index]
        comment = result["word_feedback"].get(index, "")
        rows.append(
            {
                "Ayah": word["ayah"],
                "Word": word["ar"],
                "Assessment": status.capitalize(),
                "Feedback": comment,
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Letter-level Tajweed observations"):
        any_results = False

        for index, word in enumerate(words):
            for letter_index, letter in enumerate(word["letters"]):
                assessment = result["letter_results"].get(
                    f"{index}:{letter_index}"
                )
                if not assessment:
                    continue

                any_results = True
                st.markdown(
                    f"**Ayah {word['ayah']} · {letter['text']}** — "
                    f"{assessment['status'].capitalize()}"
                )

                marks = ", ".join(letter["marks"]) or "No displayed harakah"
                st.caption(
                    f"Harakah: {marks} · Rule: "
                    f"{assessment['rule'] or 'Not specified'}"
                )

                if assessment["feedback"]:
                    st.write(assessment["feedback"])

        if not any_results:
            st.info(
                "No individual letters were confidently assessed in this "
                "response. Try a shorter, clearer recording."
            )

    col1, col2 = st.columns(2)

    if col1.button("Try again", use_container_width=True):
        st.session_state.results.pop(result_key, None)
        st.session_state.tries += 1
        st.rerun()

    if col2.button(
        "Continue",
        use_container_width=True,
        type="primary",
    ):
        st.session_state.update(step=2, count=0)
        st.rerun()


if step == 0:
    listen_step()

elif step == 1:
    record_step()

elif step == 2:
    saved_result = st.session_state.results.get(result_key)

    if saved_result:
        show_result(saved_result)

        if st.button("Start again with this passage", use_container_width=True):
            st.session_state.update(step=0, count=0)
            st.rerun()
    else:
        st.info("Complete Step 2 before opening the teacher review.")
        if st.button("Return to recitation", use_container_width=True):
            st.session_state.step = 1
            st.rerun()


# ----------------------------- Footer / limitations -----------------------------

st.markdown("---")
st.caption(
    "Learning aid only: automated audio feedback can make mistakes and "
    "cannot replace a qualified Qur'an teacher. The written harakah labels "
    "come from the displayed Qur'anic text; audio judgements may be uncertain."
)
