import base64, json, re, time
import html as _h
import difflib
import datetime, math, random, pathlib
import io, threading, wave
import numpy as np
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_mic_recorder import mic_recorder

API = "https://generativelanguage.googleapis.com/v1beta/models"
VOICE_ID = "pNInz6obpgDQGcFmaJgB"
TAJWEED_16 = "1 Izhar Halqi; 2 Idgham with ghunnah; 3 Idgham without ghunnah; 4 Iqlab; 5 Ikhfa Haqiqi; 6 Ghunnah (mushaddad noon/meem); 7 Meem Sakinah rules (ikhfa/idgham/izhar shafawi); 8 Madd Tabii; 9 Madd Muttasil; 10 Madd Munfasil; 11 Madd Lazim; 12 Madd Arid lil-Sukun and Madd Leen; 13 Qalqalah; 14 Tafkhim and Tarqiq (heavy/light letters, Ra, Lam of Allah); 15 Idgham of similar/close letters (mithlayn, mutaqaribayn, mutajanisayn); 16 Waqf, ibtida, sakt and silat ha"

st.set_page_config(layout="wide", page_title="Al-Mu'allim", page_icon="🕌")
st.markdown("""
<style>
.stApp { background: linear-gradient(160deg,#fbf8f1 0%,#f1ede2 60%,#e9efe9 100%); }
h1,h2,h3,h4,p,label,li,.stMarkdown { color:#2b2a26 !important; font-family:Georgia,'Times New Roman',serif; }
.glass { background:rgba(255,255,255,.55); backdrop-filter:blur(10px); border:1px solid rgba(197,168,92,.35);
  border-radius:16px; padding:20px 24px; margin:12px 0; box-shadow:0 6px 24px rgba(120,100,50,.08); }
.ar-big { font-family:'Amiri','Scheherazade New',serif; font-size:2.6rem; direction:rtl; text-align:center; line-height:2.2; color:#7a5c12; }
[data-testid="stAudioInput"]{background:rgba(255,255,255,.55)!important;border:1px solid rgba(197,168,92,.5)!important;border-radius:999px!important;box-shadow:0 6px 24px rgba(120,100,50,.14);}
[data-testid="stStatusWidget"]{display:none!important;}
.ld{position:relative;overflow:hidden;margin:10px auto;max-width:560px;padding:16px 22px;border-radius:14px;color:#fff;font-weight:700;text-align:center;
 background:linear-gradient(135deg,#c5a85c,#b39243);box-shadow:0 0 24px rgba(229,193,88,.75);animation:flick 1.3s infinite;}
.ld::after{content:"";position:absolute;top:0;left:-60%;width:40%;height:100%;background:linear-gradient(100deg,transparent,rgba(255,255,255,.8),transparent);animation:shine 1.4s infinite;}
.ld .bar{position:absolute;left:0;bottom:0;height:5px;background:rgba(255,255,255,.85);transition:width .25s;}
@keyframes shine{to{left:120%}}
@keyframes flick{0%,100%{opacity:1}45%{opacity:.8}50%{opacity:1}57%{opacity:.88}}
[data-testid="stSidebar"]{background:rgba(255,255,255,.55)!important;backdrop-filter:blur(10px);}
div.stButton > button { background:linear-gradient(135deg,#c5a85c,#b39243)!important; color:#fff!important; border:none!important; border-radius:10px!important; font-weight:600!important; }
</style>""", unsafe_allow_html=True)

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Cormorant+Garamond:wght@500;600&family=Inter:wght@400;500&display=swap');
.stApp{background:#FAF6EC!important}
p,li,label,span,div{font-family:Inter,system-ui,sans-serif}
h1,h2,h3,h4{font-family:'Cormorant Garamond',serif!important;font-weight:600!important;color:#241C17!important}
.glass{background:#FDFBF6!important;border:1px solid #E6DCC8!important;border-radius:20px!important;box-shadow:0 8px 28px -12px rgba(36,28,23,.18)!important;backdrop-filter:none!important}
.ar-big,.ayahbox{font-family:'Amiri Quran','Amiri',serif!important}
.ayahbox{direction:rtl;text-align:center;font-size:2.4rem;line-height:2.2;padding:20px}
div.stButton>button{background:#C9A227!important;color:#241C17!important;border-radius:999px!important;box-shadow:none!important;font-weight:500!important;min-height:44px}
.ft{display:inline-block;margin:6px;padding:2px 12px;border-radius:14px;opacity:0;animation:rev .24s forwards}
.ft small{font:12px Inter;margin-left:6px}.ft.correct{background:#E8D9A8;color:#241C17}.ft.correct small{color:#2E7D5B}
.ft.close{background:#F1E3B5;box-shadow:inset 0 -3px #C9A227;color:#241C17}.ft.missed{color:#C0453A}
.ft.hide{opacity:1;animation:none;background:#F2EADA;height:1.6em;vertical-align:middle}
@keyframes rev{to{opacity:1}}
.ban{border-radius:20px;padding:16px 20px;color:#fff;margin:12px 0}
.cells{display:grid;grid-template-columns:repeat(10,1fr);gap:4px}.cells i{aspect-ratio:1;border-radius:4px;display:block}
@media(prefers-reduced-motion:reduce){.ft{animation:none;opacity:1}}
</style>""", unsafe_allow_html=True)

for k, v in {"user_name": "", "app_phase": "onboarding", "current_surah": 2, "current_ayah": 57,
             "listens": {}, "chat": [], "tafsir_text": {}, "last_analysis": {}, "lessons": {}}.items():
    st.session_state.setdefault(k, v)

# ---------- helpers ----------
def audio_part(b, mime):
    return {"inline_data": {"mime_type": mime, "data": base64.b64encode(b).decode()}}

@st.cache_data(ttl=3600, show_spinner=False)
def list_models():
    try:
        r = requests.get(API, headers={"x-goog-api-key": st.secrets["GEMINI_API_KEY"]}, params={"pageSize": 200}, timeout=20).json()
        bad = ("image", "tts", "live", "embed", "audio", "robotics", "computer")
        return [m["name"].split("/")[-1] for m in r.get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", []) and not any(x in m["name"] for x in bad)]
    except Exception:
        return []

def pick_models(pro):
    ms = list_models()
    def ver(n):
        v = re.findall(r"\d+(?:\.\d+)?", n); return float(v[0]) if v else 0
    P = sorted([m for m in ms if "pro" in m], key=ver, reverse=True)
    F = sorted([m for m in ms if "flash" in m and "lite" not in m], key=ver, reverse=True)
    L = sorted([m for m in ms if "lite" in m], key=ver, reverse=True)
    return ((P[:2] + F[:2] + L[:1]) if pro else (F[:2] + P[:1] + L[:1])) or ["gemini-1.5-flash"]

def call_gemini(parts, expect_json=False, pro=False):
    """
    Highly optimized call engine targeting production instances directly.
    Bypasses background scanning latencies to ensure immediate responses.
    """
    model_target = "gemini-1.5-flash" if not pro else "gemini-1.5-pro"
    url = f"{API}/{model_target}:generateContent?key={st.secrets['GEMINI_API_KEY']}"
    headers = {"Content-Type": "application/json"}
    
    p = {"contents": [{"parts": parts}]}
    if expect_json: 
        p["generationConfig"] = {"responseMimeType": "application/json"}
        
    for attempt in range(3):
        try:
            r = requests.post(url, json=p, headers=headers, timeout=45)
            if r.status_code == 200:
                try: 
                    ps = r.json()["candidates"][0]["content"]["parts"]
                except (KeyError, IndexError):
                    break
                t = "".join(x.get("text", "") for x in ps if not x.get("thought")).strip()
                if expect_json:
                    return json.loads(re.sub(r"^```(?:json)?|```$", "", t).strip())
                return t
            if r.status_code in (429, 500, 503): 
                time.sleep(2 ** attempt)
                continue
            break
        except Exception:
            if attempt == 2: pass
    return ""

def speak(text):
    try:
        r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
            headers={"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": st.secrets["ELEVENLABS_API_KEY"]},
            json={"text": text[:1500], "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": .6, "similarity_boost": .8}}, timeout=60)
        if r.status_code == 200: return r.content
        st.sidebar.error(f"ElevenLabs {r.status_code}: {r.text[:200]}")
    except Exception as e:
        st.sidebar.error(f"Voice error: {e}")

@st.cache_data(show_spinner=False)
def fetch_verse(s, a):
    try:
        r = requests.get(f"https://api.alquran.cloud/v1/ayah/{s}:{a}/quran-uthmani", timeout=15).json()
        return r["data"]["text"]
    except Exception:
        return ""

@st.cache_data(show_spinner=False)
def fetch_words(s, a):
    try:
        r = requests.get(
            f"https://api.quran.com/api/v4/verses/by_key/{s}:{a}",
            params={"words": "true", "word_fields": "text_uthmani"},
            timeout=15
        ).json()
        return r.get("verse", {}).get("words", [])
    except Exception:
        return []
