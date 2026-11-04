import base64
import json

import requests
import streamlit as st
from streamlit_mic_recorder import mic_recorder

# --- CONFIG ---
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
VOICE_ID = "pNInz6obpgDQGcFmaJgB"
QARI_EDITION = "ar.alafasy"  # Mishary Alafasy

st.set_page_config(layout="wide", page_title="Al-Mu'allim: Premium Tajweed AI", page_icon="🕌")
st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #0d1310 0%, #111615 100%); }
    h1, h2, h3, p, label, .stMarkdown, .stMetric { color: #f4f6f5 !important; }
    .arabic-container { font-family: 'Amiri', 'Scheherazade New', serif; font-size: 2.9rem !important; color: #e5c158 !important; text-align: right; direction: rtl; line-height: 2.3; padding: 24px; background: rgba(20, 28, 24, 0.65); border-radius: 12px; border-right: 6px solid #c5a85c; margin-bottom: 25px; }
    div.stButton > button { background: linear-gradient(135deg, #c5a85c 0%, #b39243 100%) !important; color: #0b0f0d !important; font-weight: 700 !important; border-radius: 8px !important; border: none !important; padding: 12px 28px !important; box-shadow: 0 4px 14px rgba(179, 146, 67, 0.25); }
    .card { background-color: #121a16; border: 1px solid #1e2924; border-radius: 10px; padding: 20px; margin-bottom: 15px; }
    </style>
""", unsafe_allow_html=True)

# --- SESSION ---
if "user_name" not in st.session_state: st.session_state.user_name = ""
if "app_phase" not in st.session_state: st.session_state.app_phase = "onboarding"
if "current_surah" not in st.session_state: st.session_state.current_surah = 1
if "current_ayah" not in st.session_state: st.session_state.current_ayah = 2


# --- GEMINI ---
def audio_part(audio_bytes, mime):
    return {"inline_data": {"mime_type": mime, "data": base64.b64encode(audio_bytes).decode()}}


def call_gemini(parts, expect_json=False):
    """Returns text (or parsed JSON). Raises with a readable message on failure."""
    api_key = st.secrets["GEMINI_API_KEY"]
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    payload = {"contents": [{"parts": parts}]}
    if expect_json:
        payload["generationConfig"] = {"responseMimeType": "application/json"}
    r = requests.post(GEMINI_URL, json=payload, headers=headers, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini error {r.status_code}: {r.text[:300]}")
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    return json.loads(text) if expect_json else text


# --- ELEVENLABS ---
def speak(text):
    try:
        api_key = st.secrets["ELEVENLABS_API_KEY"]
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": api_key}
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.6, "similarity_boost": 0.8},
        }
        resp = requests.post(url, json=data, headers=headers, timeout=60)
        if resp.status_code == 200:
            return resp.content
        st.sidebar.error(f"ElevenLabs Error {resp.status_code}: {resp.text[:300]}")
    except Exception as e:
        st.sidebar.error(f"Voice Connection Error: {e}")
    return None


# --- CONTENT ---
@st.cache_data(show_spinner=False)
def fetch_verse_data(surah, ayah):
    try:
        u = requests.get(f"https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/quran-uthmani", timeout=15).json()
        t = requests.get(f"https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/ar.muyassar", timeout=15).json()
        return {"uthmani": u["data"]["text"], "tafsir": t["data"]["text"]}
    except Exception:
        return {"uthmani": "الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ", "tafsir": "(could not load tafsir)"}


@st.cache_data(show_spinner=False)
def fetch_qari_audio(surah, ayah):
    """Downloads the reference recitation (mp3 bytes) for this ayah."""
    try:
        meta = requests.get(f"https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/{QARI_EDITION}", timeout=15).json()
        audio_url = meta["data"]["audio"]
        return requests.get(audio_url, timeout=30).content
    except Exception:
        return None


# --- TEACHER LOGIC ---
def analyse_recitation(student_name, surah, ayah, verse_text, student_wav, qari_mp3):
    prompt = f"""You are a patient, expert Tajweed teacher. The student, {student_name}, was asked to recite Surah {surah}, Ayah {ayah}:
{verse_text}

You are given two audio clips. Clip 1 is the reference recitation by a qari. Clip 2 is the student's recitation.
Listen to both and compare the student against the reference, word by word, covering: harakat (fatha/kasra/damma), sukoon, madd lengths (in counts), ghunnah, idgham/ikhfa/iqlab/izhar, qalqalah, makharij (letter articulation), heavy/light letters, and waqf at the end.

Rules:
- Write everything in English. Quote Arabic words in Arabic script followed by a transliteration in brackets.
- Only report issues you can actually hear. If you are unsure, say so rather than guessing. Do not invent mistakes.
- If the student's clip is silent, too short, or not the requested ayah, say that plainly.
- Be kind and encouraging but specific.

Return JSON only, in exactly this shape:
{{
  "overall_score": <integer 0-100, honest estimate>,
  "spoken_summary": "<max 60 words, warm, spoken-style English summary and the single most important thing to fix>",
  "words": [
    {{"word": "<Arabic word> (<transliteration>)", "status": "good" or "needs_work", "student_did": "<what you heard>", "correction": "<what the qari does / how to fix it>"}}
  ],
  "practice_tip": "<one concrete exercise>"
}}
Include every word of the ayah in "words", in order."""
    parts = [
        {"text": prompt},
        {"text": "Clip 1 (reference qari):"},
        audio_part(qari_mp3, "audio/mpeg"),
        {"text": "Clip 2 (student):"},
        audio_part(student_wav, "audio/wav"),
    ]
    return call_gemini(parts, expect_json=True)


def answer_question(student_name, surah, ayah, verse_text, question_text=None, question_wav=None):
    system = (
        f"You are a kind, knowledgeable Quran and Tajweed teacher speaking to your student {student_name}. "
        f"They are currently studying Surah {surah}, Ayah {ayah}: {verse_text}. "
        "Answer in English, in under 120 words, conversationally, with no markdown symbols. "
        "Write Arabic terms in transliteration. If you are not sure about something, say so honestly."
    )
    parts = [{"text": system}]
    if question_wav:
        parts.append({"text": "The student's spoken question is in this audio:"})
        parts.append(audio_part(question_wav, "audio/wav"))
    else:
        parts.append({"text": f"Student's question: {question_text}"})
    return call_gemini(parts)


# --- UI ---
if st.session_state.app_phase == "onboarding":
    st.title("🕌 Welcome to Al-Mu'allim AI Studio")
    name_entry = st.text_input("What is your name?", placeholder="e.g., Abia")
    if st.button("Begin Session"):
        if name_entry.strip():
            st.session_state.user_name = name_entry.strip()
            st.session_state.app_phase = "classroom"
            st.rerun()
else:
    st.sidebar.markdown(f"### 🧑‍🎓 Student: **{st.session_state.user_name}**")
    s_input = st.sidebar.number_input("Surah", min_value=1, max_value=114, value=st.session_state.current_surah)
    a_input = st.sidebar.number_input("Ayah", min_value=1, max_value=286, value=st.session_state.current_ayah)
    if st.sidebar.button("Update Target Location"):
        st.session_state.current_surah = s_input
        st.session_state.current_ayah = a_input
        st.rerun()

    surah, ayah = st.session_state.current_surah, st.session_state.current_ayah
    verse = fetch_verse_data(surah, ayah)

    tab_study, tab_recite, tab_ask, tab_progress = st.tabs(
        ["📖 Study & Tafsir", "🎙️ Recite & Get Corrections", "💬 Ask the Teacher", "📊 Progress"]
    )

    with tab_study:
        st.markdown(f'<div class="arabic-container">{verse["uthmani"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card"><h4>📘 Tafsir al-Muyassar</h4><p>{verse["tafsir"]}</p></div>', unsafe_allow_html=True)

    with tab_recite:
        st.subheader("Interactive Tajweed Classroom")
        st.markdown(f'<div class="arabic-container">{verse["uthmani"]}</div>', unsafe_allow_html=True)

        qari_audio = fetch_qari_audio(surah, ayah)
        if qari_audio:
            st.markdown("**1. Listen to the reference qari (Mishary Alafasy):**")
            st.audio(qari_audio, format="audio/mp3")
        else:
            st.warning("Could not load the reference recitation, so I can't compare yet. Try again in a moment.")

        st.markdown("**2. Now recite the same ayah:**")
        mic_input = mic_recorder(
            start_prompt="🎙️ Start Recitation Recording",
            stop_prompt="⏹️ Stop Recording & Analyze",
            key="muallim_mic",
            just_once=True,
        )

        if mic_input and qari_audio:
            st.audio(mic_input["bytes"], format="audio/wav")
            try:
                with st.spinner("🧠 Comparing your recitation to the qari, word by word..."):
                    result = analyse_recitation(
                        st.session_state.user_name, surah, ayah,
                        verse["uthmani"], mic_input["bytes"], qari_audio,
                    )

                st.metric("Estimated accuracy", f"{result.get('overall_score', '?')}%")
                st.caption("This is an AI estimate, not a certified assessment. Please confirm with a qualified teacher.")
                st.markdown(f'<div class="card" style="border-left: 5px solid #c5a85c;"><h4 style="color:#c5a85c;">📝 Teacher says</h4><p>{result.get("spoken_summary", "")}</p></div>', unsafe_allow_html=True)

                st.markdown("### Word-by-word feedback")
                for w in result.get("words", []):
                    icon = "✅" if w.get("status") == "good" else "⚠️"
                    with st.expander(f"{icon} {w.get('word', '')}", expanded=(w.get("status") != "good")):
                        st.markdown(f"**What I heard:** {w.get('student_did', '')}")
                        st.markdown(f"**Correction:** {w.get('correction', '')}")

                if result.get("practice_tip"):
                    st.info(f"💡 Practice tip: {result['practice_tip']}")

                with st.spinner("🔊 Preparing spoken feedback..."):
                    speech = speak(result.get("spoken_summary", ""))
                if speech:
                    st.markdown("### 🔊 Spoken feedback")
                    st.audio(speech, format="audio/mp3")
            except Exception as e:
                st.error(f"Analysis failed: {e}")

    with tab_ask:
        st.subheader("Ask your teacher anything")
        st.caption("Type a question or record it. Your teacher answers in English.")
        typed_q = st.text_input("Type your question", key="typed_q", placeholder="e.g., How long should I hold the madd in 'ar-Rahman'?")
        ask_clicked = st.button("Ask", key="ask_btn")
        st.markdown("**Or ask by voice:**")
        q_mic = mic_recorder(start_prompt="🎙️ Record question", stop_prompt="⏹️ Stop & Ask", key="ask_mic", just_once=True)

        question_text, question_wav = None, None
        if q_mic:
            question_wav = q_mic["bytes"]
        elif ask_clicked and typed_q.strip():
            question_text = typed_q.strip()

        if question_text or question_wav:
            try:
                with st.spinner("🧠 Thinking..."):
                    answer = answer_question(
                        st.session_state.user_name, surah, ayah, verse["uthmani"],
                        question_text=question_text, question_wav=question_wav,
                    )
                st.markdown(f'<div class="card" style="border-left: 5px solid #c5a85c;"><h4 style="color:#c5a85c;">🧑‍🏫 Teacher</h4><p>{answer}</p></div>', unsafe_allow_html=True)
                speech = speak(answer)
                if speech:
                    st.audio(speech, format="audio/mp3")
            except Exception as e:
                st.error(f"Could not get an answer: {e}")

    with tab_progress:
        st.subheader("Hifdh Progress Management Dashboard")
        c1, c2, c3 = st.columns(3)
        c1.metric("Sabaq (Current Target)", f"Ayah {ayah}")
        c2.metric("Sabqi (Recent Review)", "Not tracked yet")
        c3.metric("Manzil (Long-Distance Review)", "Not tracked yet")
        st.caption("Progress tracking is placeholder for now: nothing is saved between sessions.")
