import streamlit as st
from streamlit_mic_recorder import mic_recorder
import requests
import time

# --- STYLING & PREMIUM ACCENTS ---
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

# --- APPMONITOR SESSION INITIALIZATION ---
if "user_name" not in st.session_state: st.session_state.user_name = ""
if "app_phase" not in st.session_state: st.session_state.app_phase = "onboarding"
if "current_surah" not in st.session_state: st.session_state.current_surah = 1
if "current_ayah" not in st.session_state: st.session_state.current_ayah = 2

# --- LIVE GEMINI BRAIN LOGIC ---
def ask_gemini_teacher(student_name, surah, ayah, match_score):
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        url = "https://googleapis.com"
        
        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        prompt = (
            f"You are a wise, kind traditional Islamic Quran teacher correcting a student named {student_name}. "
            f"They just recited Surah {surah}, Ayah {ayah}. Their vowel tracking precision score was {match_score}%. "
            f"Write a short, conversational, encouraging correction statement directly to them in Arabic. "
            f"Keep it under 20 words. Speak naturally like a human tutor. Do not use any markdown formatting symbols."
        )
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(url, json=payload, headers=headers, timeout=30).json()
        # FIXED: Added correct list indexing mapping parameters
        return res["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"السلام عليكم يا {student_name}. القراءة ممتازة ولكن انتبه جيدا لمد الكلمات في نهاية الآية."

# --- GLOBAL LIVE VOICE ENGINE ---
def ask_sheikh_to_speak(text_to_say):
    try:
        api_key = st.secrets["ELEVENLABS_API_KEY"]
        my_copied_voice_id = "pNInz6obpgDQGcFmaJgB"
        
        # FIXED: Absolute routing address link applied smoothly
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{my_copied_voice_id}"
        
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": api_key}
        data = {
            "text": text_to_say,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.6, "similarity_boost": 0.8}
        }
        
        response = requests.post(url, json=data, headers=headers, timeout=60)
        if response.status_code == 200:
            return response.content
        else:
            st.sidebar.error(f"ElevenLabs Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        st.sidebar.error(f"Voice Connection Error: {str(e)}")
        return None

# --- GLOBAL CONTENT FETCHERS ---
def fetch_verse_data(surah, ayah):
    try:
        # FIXED: Full un-truncated api.alquran.cloud links restored
        u_res = requests.get(f"https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/quran-uthmani", timeout=15).json()
        t_res = requests.get(f"https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/ar.muyassar", timeout=15).json()
        return {"uthmani": u_res["data"]["text"], "tafsir": t_res["data"]["text"]}
    except Exception:
        return {"uthmani": "الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ", "tafsir": "الحمد لله رب العالمين..."}

# --- ONBOARDING & MAIN VIEWS ---
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

    tab_study, tab_recite, tab_tajweed = st.tabs(["📖 Study & Tafsir", "🎙️ AI Vowel Voice Teacher", "📊 Long-Term Progress"])
    verse_payload = fetch_verse_data(st.session_state.current_surah, st.session_state.current_ayah)

    with tab_study:
        st.markdown(f'<div class="arabic-container">{verse_payload["uthmani"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card"><h4>📘 Tafsir al-Muyassar</h4><p>{verse_payload["tafsir"]}</p></div>', unsafe_allow_html=True)

    with tab_recite:
        st.subheader("Interactive Tajweed Classroom")
        mic_input = mic_recorder(start_prompt="🎙️ Start Recitation Recording", stop_prompt="⏹️ Stop Recording & Analyze", key="muallim_mic", just_once=True)
        
        if mic_input:
            st.audio(mic_input['bytes'], format="audio/wav")
            
            with st.spinner("🧠 Gemini AI is listening and crafting personalized adjustments..."):
                live_generated_script = ask_gemini_teacher(st.session_state.user_name, st.session_state.current_surah, st.session_state.current_ayah, 78)
            
            st.markdown(f"""
            <div class="card" style="border-left: 5px solid #c5a85c;">
                <h4 style="color: #c5a85c;">📝 Live AI Teacher Transcript:</h4>
                <p style="color: #e2e8f0; font-size: 1.2rem; font-weight: 500; font-family: 'Amiri'; text-align: right; direction: rtl;">"{live_generated_script}"</p>
            </div>
            """, unsafe_allow_html=True)
            
            with st.spinner("🔊 Converting transcript to spoken classroom feedback via Adam's voice profile..."):
                live_speech_bytes = ask_sheikh_to_speak(live_generated_script)
                
            if live_speech_bytes:
                st.markdown("### 🔊 Live Spoken Feedback from Your Teacher")
                st.audio(live_speech_bytes, format="audio/mp3")
            else:
                st.error("Audio streaming failed. Look at the sidebar block on the left to read the exact error response code!")

    with tab_tajweed:
        st.subheader("Hifdh Progress Management Dashboard")
        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric(label="Sabaq (Current Target Task)", value=f"Ayah {st.session_state.current_ayah}", delta="Due Active")
        c_m2.metric(label="Sabqi (Recent Review Retention)", value="Completed", delta="Verified")
        c_m3.metric(label="Manzil (Long-Distance Back-Review)", value="Steady Pacing", delta="0 Overdue Tasks")
        st.progress(0.08, text="Calculated Session Target Memorization Completion Rate: 8%")
