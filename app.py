import base64
import json
import re
import time
import requests
import streamlit as st
from streamlit_mic_recorder import mic_recorder

# --- Configurations ---
API = "https://googleapis.com"
st.set_page_config(layout="wide", page_title="Al-Mu'allim", page_icon="🕌")

# --- Optimized Styling ---
st.markdown("""<style>
@import url('https://googleapis.com');
.stApp { background: #FAF6EC !important; }
p, li, label, span, div { font-family: Inter, system-ui, sans-serif; }
h1, h2, h3, h4 { font-family: 'Cormorant Garamond', serif !important; font-weight: 600 !important; color: #241C17 !important; }
.glass { background: #FDFBF6 !important; border: 1px solid #E6DCC8 !important; border-radius: 20px !important; box-shadow: 0 8px 28px -12px rgba(36,28,23,.18) !important; padding: 24px; margin: 16px 0; }

.ayahbox { direction: rtl; text-align: center; font-family: 'Amiri Quran', serif !important; font-size: 2.6rem; line-height: 2.4; padding: 20px; color: #7a5c12; }

/* Lighting up the words beautifully */
.word-badge { display: inline-block; margin: 6px; padding: 6px 14px; border-radius: 12px; font-family: 'Amiri Quran', serif; font-size: 2.2rem; direction: rtl; transition: all 0.3s ease; }
.word-badge.correct { background: #E8D9A8; color: #241C17; border: 2px solid #C9A227; box-shadow: 0 0 12px rgba(201,162,39,0.3); }
.word-badge.missed { background: #fce8e6; color: #C0453A; border: 2px solid #f5baba; }
.word-badge.pending { background: #F2EADA; color: #8A8273; border: 2px solid #E6DCC8; opacity: 0.6; }
</style>""", unsafe_allow_html=True)

# --- State Management ---
for k, v in {
    "user_name": "", 
    "app_phase": "onboarding", 
    "current_surah": 1, 
    "current_ayah": 1,
    "last_analysis": None
}.items():
    st.session_state.setdefault(k, v)

# --- Ultra-Fast Fixed Gemini Call ---
def call_gemini_speed(audio_bytes, target_verse):
    """Sends the audio directly to a fast model without crawling the model directory."""
    url = f"{API}/gemini-1.5-flash:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": st.secrets["GEMINI_API_KEY"]}
    
    # Bundle the audio bytes and the text prompt cleanly
    payload = {
        "contents": [{
            "parts": [
                {
                    "inline_data": {
                        "mime_type": "audio/wav",
                        "data": base64.b64encode(audio_bytes).decode("utf-8")
                    }
                },
                {
                    "text": f"""
                    You are an expert Quran and Tajweed teacher. Listen carefully to the user's recitation.
                    Compare their speech against this target verse: "{target_verse}"
                    
                    Break down the target verse word by word. For every word in the target verse, determine if the user recited it accurately.
                    Return a JSON object with a single key "analysis" containing a list of objects. Each object must have:
                    1. "word": The exact Arabic word from the target verse.
                    2. "status": State either "correct" if recited well or "missed" if mispronounced/skipped.
                    
                    Strictly output ONLY valid JSON without markdown wrapping.
                    """
                }
            ]
        }],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        else:
            st.error(f"API Error ({response.status_code}): {response.text}")
    except Exception as e:
        st.error(f"Connection failed: {e}")
    return None

@st.cache_data(show_spinner=False)
def fetch_verse(s, a):
    try:
        r = requests.get(f"https://alquran.cloud{s}:{a}/quran-uthmani", timeout=10).json()
        return r["data"]["text"]
    except Exception:
        return "الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ"  # Fallback example

# --- UI Application Router ---
if st.session_state.app_phase == "onboarding":
    st.markdown("<div class='glass'>", unsafe_allow_html=True)
    st.title("Welcome to Al-Mu'allim 🕌")
    st.markdown("### Accelerate your Quranic pronunciation with immediate feedback.")
    name = st.text_input("Enter your name to begin:")
    if st.button("Enter Dashboard") and name:
        st.session_state.user_name = name
        st.session_state.app_phase = "dashboard"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.app_phase == "dashboard":
    st.title(f"Assalamu Alaikum, {st.session_state.user_name}")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("<div class='glass'>", unsafe_allow_html=True)
        st.markdown("### Target Verse for Recitation")
        
        target_text = fetch_verse(st.session_state.current_surah, st.session_state.current_ayah)
        words = target_text.split()
        
        # Display the verse engine dynamically
        st.markdown("#### Click record and read the words below:")
        
        # Render the text beautifully based on current analysis state
        html_rendering = "<div class='ayahbox'>"
        analysis_data = st.session_state.last_analysis
        
        if analysis_data and "analysis" in analysis_data:
            # Map statuses directly into their specific CSS layout states
            for item in analysis_data["analysis"]:
                w = item.get("word", "")
                status = item.get("status", "pending")
                html_rendering += f"<span class='word-badge {status}'>{w}</span>"
        else:
            # If no recitation has occurred yet, keep all words sitting in 'pending' mode
            for w in words:
                html_rendering += f"<span class='word-badge pending'>{w}</span>"
        html_rendering += "</div>"
        
        st.markdown(html_rendering, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col2:
        st.markdown("<div class='glass' style='text-align: center;'>", unsafe_allow_html=True)
        st.markdown("### Recitation Input")
        
        # Fixed Streamlit Mic Recorder deployment
        audio_feed = mic_recorder(
            start_prompt="🎙️ Start Reciting",
            stop_prompt="🛑 Stop & Analyze",
            just_once=False,
            format="wav", # Changed to wav format for cleaner model translation API blocks
            key="quran_mic"
        )
        
        if audio_feed and "bytes" in audio_feed:
            with st.spinner("Analyzing audio vectors instantly..."):
                raw_response = call_gemini_speed(audio_feed["bytes"], target_text)
                if raw_response:
                    try:
                        # Clean up formatting artifacts and parse JSON securely
                        cleaned_json = re.sub(r"^```(?:json)?|```$", "", raw_response).strip()
                        st.session_state.last_analysis = json.loads(cleaned_json)
                        st.success("Analysis complete! Check your text window to see highlighted feedback.")
                        st.rerun()
                    except Exception:
                        st.warning("Could not map your pronunciation data clean. Please try reading again.")
        
        st.markdown("</div>", unsafe_allow_html=True)
