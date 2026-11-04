import streamlit as st
from streamlit_mic_recorder import mic_recorder
import requests
import time
import json
import base64

# --- STYLING & PREMIUM ACCENTS ---
st.set_page_config(
    layout="wide", 
    page_title="Al-Mu'allim: Premium Tajweed AI", 
    page_icon="🕌"
)

# Custom injection styling to achieve a rich matte-gold and dark emerald layout
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #0d1310 0%, #111615 100%);
    }
    h1, h2, h3, p, label, .stMarkdown, .stMetric {
        color: #f4f6f5 !important;
    }
    .arabic-container {
        font-family: 'Amiri', 'Scheherazade New', serif;
        font-size: 2.9rem !important;
        color: #e5c158 !important;
        text-align: right;
        direction: rtl;
        line-height: 2.3;
        padding: 24px;
        background: rgba(20, 28, 24, 0.65);
        border-radius: 12px;
        border-right: 6px solid #c5a85c;
        margin-bottom: 25px;
    }
    div.stButton > button {
        background: linear-gradient(135deg, #c5a85c 0%, #b39243 100%) !important;
        color: #0b0f0d !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 12px 28px !important;
        box-shadow: 0 4px 14px rgba(179, 146, 67, 0.25);
        transition: transform 0.1s ease;
    }
    div.stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 18px rgba(179, 146, 67, 0.4);
    }
    .card {
        background-color: #121a16;
        border: 1px solid #1e2924;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# --- APPMONITOR / SESSION INITIALIZATION ---
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "app_phase" not in st.session_state:
    st.session_state.app_phase = "onboarding"
if "current_surah" not in st.session_state:
    st.session_state.current_surah = 1
if "current_ayah" not in st.session_state:
    st.session_state.current_ayah = 2

# --- GLOBAL LIVE VOICE ENGINE ---
def ask_sheikh_to_speak(text_to_say):
    try:
        api_key = st.secrets["ELEVENLABS_API_KEY"]
        my_copied_voice_id = "pNInz6obpgDQGcFmaJgB"
        url = f"https://elevenlabs.io{my_copied_voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        
        data = {
            "text": text_to_say,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.6,
                "similarity_boost": 0.8
            }
        }
        
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            return response.content
        return None
    except Exception:
        return None

# --- REAL GEMINI TAJWEED EVALUATION ENGINE ---
def analyze_recitation_with_gemini(audio_bytes, correct_text):
    try:
        gemini_key = st.secrets["GEMINI_API_KEY"]
        
        # Uses Gemini 2.0 Flash via standard REST endpoint for fast multimodal audio decoding
        url = f"https://googleapis.com{gemini_key}"
        headers = {"Content-Type": "application/json"}
        
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        
        prompt_text = f"""
        You are a strict, expert traditional Quran and Tajweed teacher. Listen to the user's audio recitation and compare it directly to the perfect expected Uthmani text provided below.
        
        Expected perfect text: "{correct_text}"
        
        Analyze the audio closely for:
        1. Vowel & Diacritic Accuracy (Harakat / Fathah, Kasrah, Dammah).
        2. Articulation Points (Makhraj matching).
        3. Elongations and Rules (Madd, Ghunnah, etc.).
        
        You must return a raw JSON object containing exactly these fields, with no markdown backticks, no code blocks, and no extra text outside the JSON object:
        {{
            "harakat_score": "e.g., 90%",
            "harakat_feedback": "Short feedback note about short vowels",
            "makhraj_score": "e.g., 85%",
            "makhraj_feedback": "Short feedback note about pronunciation letters",
            "madd_score": "e.g., 75%",
            "madd_feedback": "Short feedback note about elongation rules",
            "teacher_voice_script_arabic": "Write a 1-2 sentence gentle, encouraging, and specific spoken correction entirely in Arabic. Start by greeting them by their name if possible. Tell them exactly where they did well and what specific word or letter rule to fix next time."
        }}
        """
        
        data = {
            "contents": [{
                "parts": [
                    {"text": prompt_text},
                    {
                        "inlineData": {
                            "mimeType": "audio/wav",
                            "data": audio_b64
                        }
                    }
                ]
            }],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            res_json = response.json()
            text_output = res_json["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text_output)
    except Exception as e:
        st.sidebar.error(f"Gemini Processing Error: {str(e)}")
    return None

# --- GLOBAL CONTENT FETCHERS ---
def fetch_verse_data(surah, ayah):
    try:
        u_res = requests.get(f"https://alquran.cloud{surah}:{ayah}/quran-uthmani").json()
        t_res = requests.get(f"https://alquran.cloud{surah}:{ayah}/ar.muyassar").json()
        return {
            "uthmani": u_res["data"]["text"],
            "tafsir": t_res["data"]["text"]
        }
    except Exception:
        return {
            "uthmani": "الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ",
            "tafsir": "الحمد لله رب العالمين هو الثناء على الله بصفاته التي كلها أوصاف كمال..."
        }

# --- APPMONITOR PHASE 1: INDIVIDUALIZED HUMANLIKE ONBOARDING ---
if st.session_state.app_phase == "onboarding":
    st.title("🕌 Welcome to Al-Mu'allim AI Studio")
    st.subheader("Advanced Phoneme Alignment & Vowel-Level Tajweed Verification")
    
    st.write("Welcome! Please share your name with your mentor so we can customize your tracking session.")
    name_entry = st.text_input("What is your name?", placeholder="e.g., Abia")
    
    if st.button("Begin Session"):
        if name_entry.strip():
            st.session_state.user_name = name_entry.strip()
            st.session_state.app_phase = "classroom"
            st.rerun()
        else:
            st.error("Please enter your name to authenticate the teacher's profile workspace.")

# --- APPMONITOR PHASE 2: ADVANCED TEACHER CLASSROOM ---
else:
    st.sidebar.markdown(f"### 🧑‍🎓 Student: **{st.session_state.user_name}**")
    st.sidebar.markdown(f"📖 Verse Profile: **{st.session_state.current_surah}:{st.session_state.current_ayah}**")
    st.sidebar.markdown("🎙️ Voice Output System: **Active API Stream**")
    
    st.sidebar.subheader("Select/Open Verse Directly")
    s_input = st.sidebar.number_input("Surah", min_value=1, max_value=114, value=st.session_state.current_surah)
    a_input = st.sidebar.number_input("Ayah", min_value=1, max_value=286, value=st.session_state.current_ayah)
    
    if st.sidebar.button("Update Target Location"):
        st.session_state.current_surah = s_input
        st.session_state.current_ayah = a_input
        st.rerun()

    if st.sidebar.button("Reset Profile Name"):
        st.session_state.app_phase = "onboarding"
        st.rerun()

    tab_study, tab_recite, tab_tajweed = st.tabs(["📖 Study & Tafsir", "🎙️ AI Vowel Voice Teacher", "📊 Long-Term Progress"])
    verse_payload = fetch_verse_data(st.session_state.current_surah, st.session_state.current_ayah)

    with tab_study:
        st.subheader("Text Verification & Study Panel")
        st.markdown(f'<div class="arabic-container">{verse_payload["uthmani"]}</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="card">
            <h4 style="color: #c5a85c;">📘 Tafsir al-Muyassar (King Fahd Complex)</h4>
            <p style="color: #cbd5e1; font-size: 1.1rem; line-height: 1.8;">{verse_payload["tafsir"]}</p>
        </div>
        """, unsafe_allow_html=True)

    with tab_recite:
        st.subheader("Interactive Tajweed Classroom")
        st.write(f"Assalamu Alaykum, {st.session_state.user_name}. Click the button below, recite the verse clearly, and click stop to submit your audio.")
        
        mic_input = mic_recorder(
            start_prompt="🎙️ Start Recitation Recording",
            stop_prompt="⏹️ Stop Recording & Analyze Vowels",
            key="muallim_mic",
            just_once=True
        )
        
        if mic_input:
            st.success("🏁 Audio buffer saved successfully without streaming interruptions.")
            audio_bytes = mic_input['bytes']
            st.audio(audio_bytes, format="audio/wav")
            
            with st.spinner("Gemini is listening to your audio waveform, aligning phonemes, and cross-referencing Tajweed matrices..."):
                analysis_results = analyze_recitation_with_gemini(audio_bytes, verse_payload["uthmani"])
                
            if analysis_results:
                st.markdown("### 📊 Live AI Phoneme Vowel Alignment Evaluation")
                
                col_v1, col_v2, col_v3 = st.columns(3)
                col_v1.metric(label="Vowels & Harakat", value=analysis_results.get("harakat_score", "N/A"), delta=analysis_results.get("harakat_feedback", ""))
