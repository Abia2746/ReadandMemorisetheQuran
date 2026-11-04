import streamlit as st
from streamlit_mic_recorder import mic_recorder
import requests
import time
import json
import base64

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

# --- GLOBAL LIVE VOICE ENGINE ---
def ask_sheikh_to_speak(text_to_say):
    try:
        api_key = st.secrets["ELEVENLABS_API_KEY"]
        my_copied_voice_id = "pNInz6obpgDQGcFmaJgB" # Adam's Voice ID
        url = f"https://elevenlabs.io{my_copied_voice_id}"
        
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": api_key}
        data = {
            "text": text_to_say,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.6, "similarity_boost": 0.8}
        }
        
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            return response.content
        else:
            st.sidebar.error(f"ElevenLabs Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        st.sidebar.error(f"Voice Connection Error: {str(e)}")
        return None

# --- REAL GEMINI TAJWEED EVALUATION ENGINE ---
def analyze_recitation_with_gemini(audio_bytes, correct_text):
    try:
        gemini_key = st.secrets["GEMINI_API_KEY"]
        url = f"https://googleapis.com{gemini_key}"
        headers = {"Content-Type": "application/json"}
        
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        
        prompt_text = f"""
        You are an expert traditional Quran and Tajweed teacher. Listen to the user's audio recitation and compare it closely to the expected Uthmani verse text provided below.
        
        Expected text: "{correct_text}"
        
        Analyze the audio for real:
        1. Vowel/Diacritic Accuracy (Harakat / Fathah, Kasrah, Dammah).
        2. Articulation points (Makhraj).
        3. Elongations/Rules (Madd, Ghunnah).
        
        You must return a raw JSON object containing exactly these fields, with no markdown backticks, no code blocks, and no extra text outside the JSON object:
        {{
            "harakat_score": "e.g., 92%",
            "harakat_feedback": "Short feedback note in English about vowels",
            "makhraj_score": "e.g., 85%",
            "makhraj_feedback": "Short feedback note in English about letters",
            "madd_score": "e.g., 78%",
            "madd_feedback": "Short feedback note in English about elongations",
            "teacher_voice_script_arabic": "Write a 1-2 sentence gentle, encouraging, and highly specific spoken correction entirely in Arabic. Start by greeting them by their name ({st.session_state.user_name}). Tell them exactly what specific word or letter rule to adjust."
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
        st.sidebar.error(f"Gemini Analysis Error: {str(e)}")
    return None

# --- GLOBAL CONTENT FETCHERS ---
def fetch_verse_data(surah, ayah):
    try:
        u_res = requests.get(f"https://alquran.cloud{surah}:{ayah}/quran-uthmani").json()
        t_res = requests.get(f"https://alquran.cloud{surah}:{ayah}/ar.muyassar").json()
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
            
            with st.spinner("Gemini is listening to your recording and assessing Tajweed rules..."):
                analysis_results = analyze_recitation_with_gemini(mic_input['bytes'], verse_payload["uthmani"])
            
            if analysis_results:
                st.markdown("### 📊 AI Phoneme Vowel Alignment Evaluation")
                col_v1, col_v2, col_v3 = st.columns(3)
                col_v1.metric(label="Vowels & Harakat", value=analysis_results.get("harakat_score", "N/A"), delta=analysis_results.get("harakat_feedback", ""))
                col_v2.metric(label="Articulation Points (Makhraj)", value=analysis_results.get("makhraj_score", "N/A"), delta=analysis_results.get("makhraj_feedback", ""))
                col_v3.metric(label="Elongation rules (Madd)", value=analysis_results.get("madd_score", "N/A"), delta=analysis_results.get("madd_feedback", ""))
                
                live_generated_script = analysis_results.get("teacher_voice_script_arabic", "قراءة طيبة بارك الله فيك.")
                
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
            else:
                st.error("Gemini was unable to evaluate the audio file. Please check that your GEMINI_API_KEY is properly saved in your Streamlit secrets settings.")

    with tab_tajweed:
        st.subheader("Your Progress Tracker")
        st.write("Tracking dynamic recitation logs provided by your Gemini evaluation pipeline.")
        st.info("Practise consistently to see shifts in your vowel and articulation scores.")
