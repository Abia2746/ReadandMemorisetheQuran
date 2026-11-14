# app.py — Al-Mu'allim · Ultimate Streamlit Build
import base64, json, re, time
import html as _h
import datetime, math, random, pathlib
import io, threading, wave, os
import numpy as np
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_mic_recorder import mic_recorder

# ──────────────────────────────────────────────────────────────────────────────
# Constants & Config
# ──────────────────────────────────────────────────────────────────────────────
API = "https://generativelanguage.googleapis.com/v1beta/models"
VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ROOT = pathlib.Path(__file__).parent

st.set_page_config(layout="wide", page_title="Al-Mu'allim", page_icon="🕌")

_DEFAULTS = {
    "user_name": "", "app_phase": "onboarding",
    "current_surah": 2, "current_ayah": 60,
    "listens": {}, "chat": [], "tafsir_text": {}, "last_analysis": {},
    "lessons": {}, "coach": [],
    "xp": 0, "streak": 0, "last_day": None, "perfect_ayahs": 0, "total_listens": 0,
    "badges": [], "cfg_teacher": "Female", "cfg_theme": "Night",
    "cfg_style": "Warm & casual", "cfg_level": "Beginner", "cfg_detail": 2,
    "cfg_quality": "Best", "cfg_strict": "Standard", "cfg_gain": 12, "cfg_voice": True,
    "deep_analysis": False, "cfg_reciter": "Mishary Alafasy", "conceal_text": True
}
for k, v in _DEFAULTS.items():
    st.session_state.setdefault(k, v)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers (API, Audio, Text)
# ──────────────────────────────────────────────────────────────────────────────
def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
        if value: return str(value)
    except Exception: pass
    return os.getenv(name, default)

def audio_part(b, mime):
    return {"inline_data": {"mime_type": mime, "data": base64.b64encode(b).decode()}}

@st.cache_data(ttl=3600, show_spinner=False)
def list_models():
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key: return ["gemini-2.5-flash"]
    try:
        r = requests.get(API, headers={"x-goog-api-key": api_key}, params={"pageSize": 200}, timeout=15)
        r.raise_for_status()
        bad = ("image", "tts", "live", "embed", "audio", "robotics", "computer")
        names = []
        for model in r.json().get("models", []):
            name = model.get("name", "").split("/")[-1]
            if name and "generateContent" in model.get("supportedGenerationMethods", []) and not any(x in name.lower() for x in bad):
                names.append(name)
        return names or ["gemini-2.5-flash"]
    except Exception:
        return ["gemini-2.5-flash"]

def pick_models(pro):
    ms = list_models()
    def version(name):
        nums = re.findall(r"\d+(?:\.\d+)?", name)
        return tuple(float(x) for x in nums[:2]) if nums else (0.0,)
    pro_models = sorted([m for m in ms if "pro" in m.lower()], key=version, reverse=True)
    flash_models = sorted([m for m in ms if "flash" in m.lower() and "lite" not in m.lower()], key=version, reverse=True)
    lite_models = sorted([m for m in ms if "lite" in m.lower()], key=version, reverse=True)
    ordered = (pro_models[:2] + flash_models[:3] + lite_models[:1]) if pro else (flash_models[:3] + pro_models[:1] + lite_models[:1])
    return list(dict.fromkeys(ordered)) or ["gemini-2.5-flash"]

def call_gemini(parts, expect_json=False, pro=False):
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key: raise RuntimeError("Gemini API key missing.")
    
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    payload = {"contents": [{"parts": parts}]}
    if expect_json: payload["generationConfig"] = {"responseMimeType": "application/json"}
    
    last_error = "No model available."
    for model in pick_models(pro):
        for attempt in range(2):
            try:
                response = requests.post(f"{API}/{model}:generateContent", json=payload, headers=headers, timeout=(30, 300))
            except requests.RequestException as exc:
                last_error = f"Network error ({model}): {exc}"
                break
            if response.status_code == 200:
                try:
                    body = response.json()
                    cands = body.get("candidates") or []
                    if not cands: break
                    rp = cands[0].get("content", {}).get("parts", [])
                    answer = "".join(p.get("text", "") for p in rp if not p.get("thought")).strip()
                    if not answer: break
                    if expect_json:
                        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", answer, flags=re.IGNORECASE).strip()
                        try: return json.loads(cleaned)
                        except json.JSONDecodeError:
                            m = re.search(r"\{.*\}", cleaned, re.DOTALL)
                            if m:
                                try: return json.loads(m.group(0))
                                except: pass
                            raise RuntimeError("Invalid JSON response.")
                    return answer
                except Exception as exc:
                    last_error = f"{model} unreadable: {exc}"
                    break
            if response.status_code in (500, 502, 503, 504) and attempt == 0:
                time.sleep(1.5)
                continue
            break
    raise RuntimeError("AI Error: " + last_error)

def speak(text):
    if not text: return None
    try:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
            headers={"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": get_secret("ELEVENLABS_API_KEY")},
            json={"text": text[:1500], "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": .6, "similarity_boost": .8}},
            timeout=60,
        )
        if r.status_code == 200: return r.content
    except: pass
    return None

@st.cache_data(show_spinner=False)
def fetch_verse(s, a):
    try:
        r = requests.get(f"https://api.alquran.cloud/v1/ayah/{s}:{a}/quran-uthmani", timeout=15).json()
        return r["data"]["text"]
    except: return ""

@st.cache_data(show_spinner=False)
def fetch_words(s, a):
    try:
        r = requests.get(f"https://api.quran.com/api/v4/verses/by_key/{s}:{a}", params={"words": "true", "word_fields": "text_uthmani", "language": "en"}, timeout=20).json()
        return [{"ar": w["text_uthmani"], "en": (w.get("translation") or {}).get("text", ""), "tr": (w.get("transliteration") or {}).get("text") or ""} for w in r["verse"]["words"] if w.get("char_type_name") == "word"]
    except: return []

@st.cache_data(show_spinner=False)
def fetch_reciter(s, a, choice):
    if choice == "Yasser Al-Dosari":
        url = f"https://everyayah.com/data/Yasser_Ad-Dussary_128kbps/{s:03d}{a:03d}.mp3"
    else:
        url = f"https://everyayah.com/data/Alafasy_128kbps/{s:03d}{a:03d}.mp3"
    
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200 and len(r.content) > 2000: return url, r.content, choice
    except: pass
    return None, None, None

@st.cache_data(show_spinner=False)
def fetch_ibn_kathir(s, a):
    try:
        r = requests.get(f"https://api.quran.com/api/v4/tafsirs/169/by_ayah/{s}:{a}", timeout=20).json()
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r["tafsir"]["text"])).strip()[:7000]
    except: return ""

@st.cache_data(show_spinner=False)
def fetch_translation(s, a):
    try: return requests.get(f"https://api.alquran.cloud/v1/ayah/{s}:{a}/en.sahih", timeout=15).json()["data"]["text"]
    except: return ""

def _valid_wav(data):
    try:
        with wave.open(io.BytesIO(data), "rb") as wf:
            channels, width, rate = wf.getnchannels(), wf.getsampwidth(), wf.getframerate()
            frames = wf.readframes(wf.getnframes())
        if not frames: raise ValueError("Empty recording.")
        if width == 1: samples = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128) * 256
        elif width == 2: samples = np.frombuffer(frames, dtype="<i2").astype(np.float32)
        elif width == 4: samples = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 65536
        else: raise ValueError("Unsupported WAV.")
        if channels > 1: samples = samples[:(len(samples)//channels)*channels].reshape(-1, channels).mean(axis=1)
        if rate != 16000 and len(samples):
            samples = np.interp(np.linspace(0, len(samples)-1, max(1, round(len(samples) * 16000 / rate))), np.arange(len(samples)), samples)
        samples = np.clip(samples, -32768, 32767).astype("<i2")
        out = io.BytesIO()
        with wave.open(out, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000); wf.writeframes(samples.tobytes())
        return out.getvalue()
    except wave.Error as exc: raise ValueError("Unsupported mic container.") from exc

def boost(wav_bytes):
    try:
        with wave.open(io.BytesIO(wav_bytes)) as w:
            ch, sw, fr = w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(w.getnframes())
        if sw != 2: return wav_bytes, 1.0
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        peak = float(np.percentile(np.abs(x), 99.5))
        frac = peak / 32768
        if peak < 30: return wav_bytes, frac
        y = np.clip(x * min(float(st.session_state.get("cfg_gain", 12)), 0.9 * 32767 / peak), -32768, 32767).astype(np.int16)
        out = io.BytesIO()
        with wave.open(out, "wb") as w2:
            w2.setnchannels(ch); w2.setsampwidth(2); w2.setframerate(fr); w2.writeframes(y.tobytes())
        return out.getvalue(), frac
    except: return wav_bytes, 1.0

def transcribe(wav, orig=None, arabic=False):
    prompt = ("Transcribe this Quran recitation exactly as spoken, in Arabic script. Preserve mistakes. Return [inaudible] if empty." if arabic 
              else "Transcribe this student's message in English. Return only the transcript. Return [inaudible] if empty.")
    for audio in (wav, orig):
        if not audio: continue
        try: prepared = _valid_wav(audio)
        except: prepared = audio
        try:
            result = call_gemini([{"text": prompt}, audio_part(prepared, "audio/wav")], pro=False).strip()
            if result and "[inaudible]" not in result.lower(): return result
        except: pass
    return ""

def norm_ar(t):
    t = re.sub("[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]", "", t)
    t = re.sub("[إأآٱ]", "ا", t).replace("ى", "ي").replace("ة", "ه")
    return re.sub("[^\u0621-\u064A\\s]", "", t).split()

def match_report(words_ar, heard):
    exp = ["".join(norm_ar(w)) for w in words_ar]
    hw = norm_ar(heard)
    if not hw or len(hw) < 0.2 * len(exp): return None
    
    n, m = len(exp), len(hw)
    sc = lambda e, h: 2 if e == h else (1 if e[:2] == h[:2] and abs(len(e)-len(h)) <= 1 else 0)
    D = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1): D[i][0] = -i
    for j in range(1, m + 1): D[0][j] = -j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i][j] = max(D[i-1][j-1] + sc(exp[i-1], hw[j-1]), D[i-1][j] - 1, D[i][j-1] - 1)
            
    st_, i, j, extra = ["missed"] * n, n, m, 0
    while i > 0 or j > 0:
        if i and j and D[i][j] == D[i-1][j-1] + sc(exp[i-1], hw[j-1]):
            x = sc(exp[i-1], hw[j-1])
            st_[i-1] = {2: "correct", 1: "close"}.get(x, "missed")
            extra += (x == 0); i -= 1; j -= 1
        elif i and D[i][j] == D[i-1][j] - 1: i -= 1
        else: extra += 1; j -= 1
        
    pts = sum(1 if x == "correct" else .5 if x == "close" else 0 for x in st_)
    return {"pct": round(100 * pts / len(exp)), "states": st_}

# ──────────────────────────────────────────────────────────────────────────────
# UI Theming
# ──────────────────────────────────────────────────────────────────────────────
def apply_theme():
    t = {"bg": "#1A1510", "bg2": "#2A221B", "word": "#E8D5B5", "dim": "#8A7A66", "glow": "#D4AF37", "rule": "rgba(212,175,55,.15)", "wash": "rgba(212,175,55,.08)", "ok": "#4ADE80", "bad": "#F87171"}
    
    st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Cormorant+Garamond:wght@600&family=Inter:wght@400;500;600&display=swap');
:root{{--bg:{t['bg']};--bg2:{t['bg2']};--word:{t['word']};--dim:{t['dim']};--wash:{t['wash']};--glow:{t['glow']};--rule:{t['rule']};--ok:{t['ok']};--bad:{t['bad']}}}
html,body,.stApp{{background:var(--bg)!important;color:var(--word)}}
.stApp p,.stApp li,.stApp label,.stApp span,.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp [data-testid="stCaptionContainer"]{{color:var(--word)!important;font-family:Inter,system-ui,sans-serif}}
h1,h2,h3,h4{{font-family:'Cormorant Garamond',serif!important;font-weight:600!important;color:var(--glow)!important}}
[data-testid="stSidebar"]{{background:#110D09!important;border-right:1px solid var(--rule)}}
div.stButton>button{{background:var(--glow)!important;color:#000!important;border-radius:999px!important;font-weight:600!important;min-height:44px;border:none!important;transition:transform .2s}}
div.stButton>button:hover{{transform:scale(1.02)}}
.glass{{background:var(--bg2)!important;border:1px solid var(--rule)!important;border-radius:20px!important;padding:18px 22px;margin:10px 0;box-shadow:0 8px 28px -12px rgba(0,0,0,.4)!important}}

/* Word Cards */
.word-grid{{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;direction:rtl;padding:10px}}
.word-card{{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:12px 18px;border-radius:16px;background:var(--bg2);border:1px solid var(--rule);transition:all .3s ease;min-width:100px}}
.word-card .ar{{font-family:'Amiri Quran',serif;font-size:2.2rem;color:var(--word);line-height:1.4}}
.word-card .tr{{font-size:0.8rem;color:var(--glow);font-style:italic;margin-top:6px;opacity:0.9}}
.word-card .en{{font-size:0.9rem;color:var(--dim);margin-top:2px}}
.word-card.correct{{border-color:var(--ok);box-shadow:0 0 15px rgba(74,222,128,.2)}}
.word-card.missed{{border-color:var(--bad);box-shadow:0 0 15px rgba(248,113,113,.2)}}

/* Portrait */
.portrait-container{{position:relative;width:100%;max-width:380px;margin:0 auto 20px;border-radius:32px;overflow:hidden;box-shadow:0 0 40px var(--wash);aspect-ratio: 3/4;background:#000}}
.portrait-img{{width:100%;height:100%;object-fit:cover;object-position:center 25%;opacity:0.9}}

/* Mic Button */
.mic-container div[data-testid="stAudioInput"] {{
    background: linear-gradient(135deg, #D4AF37, #F3E5AB, #D4AF37) !important;
    border-radius: 999px !important;
    padding: 12px 24px !important;
    box-shadow: 0 0 30px rgba(212,175,55,0.5) !important;
    border: none !important;
    width: 100% !important;
}}
.mic-container div[data-testid="stAudioInput"] * {{
    color: black !important;
    font-weight: 700 !important;
}}
</style>""", unsafe_allow_html=True)

def teacher_portrait():
    choice = st.session_state.get("cfg_teacher", "Female")
    img_name = "IMG_6147.jpeg" if choice == "Male" else "IMG_6146.jpeg"
    p = ROOT / img_name
    if p.is_file():
        b = p.read_bytes()
        img_src = f"data:image/jpeg;base64,{base64.b64encode(b).decode()}"
    else:
        img_src = "https://via.placeholder.com/380x506/2A221B/D4AF37?text=Missing+Image"
    st.markdown(f'<div class="portrait-container"><img class="portrait-img" src="{img_src}"></div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# HTML/JS Players
# ──────────────────────────────────────────────────────────────────────────────
def _data_uri(b, mime="audio/mpeg"):
    return f"data:{mime};base64,{base64.b64encode(b).decode()}"

def player_html(words, audio_url):
    payload = [{"ar": w.get("ar", ""), "tr": w.get("tr", ""), "en": w.get("en", "")} for w in words]
    t = {"word": "#E8D5B5", "glow": "#D4AF37", "wash": "rgba(212,175,55,.15)", "bg2": "#2A221B", "rule": "rgba(212,175,55,.15)", "dim": "#8A7A66"}
    
    tpl = r"""
<style>
body{margin:0;font-family:Inter,system-ui,sans-serif;background:transparent;color:__WORD__;}
audio{width:100%;max-width:600px;margin:15px auto 0 auto;border-radius:999px;outline:none;filter:drop-shadow(0 4px 12px rgba(0,0,0,.3));display:block;}
audio::-webkit-media-controls-panel{background-color:__BG2__;}
#w{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;direction:rtl;padding:10px;}
.word-card{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:12px 18px;border-radius:16px;background:__BG2__;border:1px solid __RULE__;transition:all .3s ease;min-width:100px;}
.word-card .ar{font-family:'Amiri Quran',serif;font-size:2.2rem;color:__WORD__;line-height:1.4;}
.word-card .tr{font-size:0.8rem;color:__GLOW__;font-style:italic;margin-top:6px;opacity:0.9;}
.word-card .en{font-size:0.9rem;color:__DIM__;margin-top:2px;}
.word-card.on{box-shadow:0 0 20px rgba(212,175,55,.4);border-color:__GLOW__;transform:translateY(-3px) scale(1.05);background:__WASH__;}
</style>
<div id="w"></div>
<audio id="a" controls src="__URL__"></audio>
<script>
const W=__WORDS__,a=document.getElementById('a'),box=document.getElementById('w');
const els=W.map(w=>{
    const d=document.createElement('div');d.className='word-card';
    d.innerHTML=`<div class="ar">${w.ar}</div><div class="tr">${w.tr}</div><div class="en">${w.en}</div>`;
    box.appendChild(d);return d;
});
let cum=[]; const L=w=>Math.max(1,(w.ar||'').replace(/[\u064B-\u0652\u0670\u06D6-\u06ED\u0640]/g,'').length);
function build(){const d=a.duration||1,l=d*.05,sp=d*.88,tot=W.reduce((s,w)=>s+L(w),0);let t=l;
cum=W.map(w=>{t+=sp*L(w)/tot;return t;});}
a.onloadedmetadata=build;
a.ontimeupdate=()=>{if(!cum.length)build();const t=a.currentTime;let i=cum.findIndex(c=>t<c);if(a.ended)i=-1;
els.forEach((e,k)=>e.classList.toggle('on',k===i));};
</script>"""
    for k, v in {"__WORD__": t["word"], "__GLOW__": t["glow"], "__WASH__": t["wash"], "__BG2__": t["bg2"], "__RULE__": t["rule"], "__DIM__": t["dim"]}.items():
        tpl = tpl.replace(k, v)
    return tpl.replace("__URL__", audio_url).replace("__WORDS__", json.dumps(payload, ensure_ascii=False))

def feedback_html(words, states, rules):
    cards = []
    for i, (word, state) in enumerate(zip(words, states)):
        arabic = _h.escape(str(word.get("ar", "")))
        tr = _h.escape(str(word.get("tr", "")))
        en = _h.escape(str(word.get("en", "")))
        cls = state if state in ["correct", "missed"] else ""
        cards.append(f'<div class="word-card {cls}"><div class="ar">{arabic}</div><div class="tr">{tr}</div><div class="en">{en}</div></div>')
    
    grid = '<div class="word-grid" dir="rtl">' + "".join(cards) + '</div>'
    
    tags = []
    for r in rules:
        is_ok = r.get("verdict") == "correct"
        color = "var(--ok)" if is_ok else ("var(--glow)" if r.get("verdict") == "partly" else "var(--bad)")
        icon = "✓" if is_ok else "✕"
        tag = f'<div class="tw-tag"><div class="tw-dot" style="background:{color}"></div>{r.get("rule","")} <span style="color:{color};margin-left:4px">{icon}</span></div>'
        tags.append(tag)
    
    return grid + '<div style="display:flex;flex-wrap:wrap;justify-content:center;margin-top:15px">' + "".join(tags) + '</div>'

# ──────────────────────────────────────────────────────────────────────────────
# Main UI
# ──────────────────────────────────────────────────────────────────────────────
apply_theme()

if st.session_state.app_phase == "onboarding":
    st.markdown("<h1 style='text-align:center;margin-top:20vh;font-size:4rem'>🕌</h1>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center'>Al-Mu'allim</h2>", unsafe_allow_html=True)
    with st.form("onboard"):
        n = st.text_input("What is your name?", placeholder="e.g., Abia")
        if st.form_submit_button("Begin Session", use_container_width=True) and n.strip():
            st.session_state.user_name = n.strip()
            st.session_state.app_phase = "classroom"
            st.rerun()
    st.stop()

# Sidebar
sb = st.sidebar
sb.markdown(f"### 🧑‍🎓 {st.session_state.user_name}")
sb.divider()
si = sb.number_input("Surah", 1, 114, st.session_state.current_surah)
ai = sb.number_input("Ayah", 1, 286, st.session_state.current_ayah)
if sb.button("Go to Ayah", use_container_width=True):
    st.session_state.current_surah, st.session_state.current_ayah = si, ai
    st.session_state.chat = []
    st.rerun()

with sb.expander("⚙️ Teacher Settings"):
    st.selectbox("Reciter", ["Mishary Alafasy", "Yasser Al-Dosari"], key="cfg_reciter")
    st.selectbox("Teacher Style", ["Warm & casual", "Classical scholar", "Concise coach"], key="cfg_style")
    st.radio("Study Companion", ["Female", "Male"], key="cfg_teacher", horizontal=True)

# Layout Container
st.markdown('<div style="max-width: 700px; margin: 0 auto; padding-top: 10px;">', unsafe_allow_html=True)

s, a = st.session_state.current_surah, st.session_state.current_ayah
key, ref = f"{s}:{a}", f"Surah {s}, Ayah {a}"

verse = fetch_verse(s, a)
words = fetch_words(s, a)
if not verse:
    st.error("Network error loading Qur'an text.")
    st.stop()

audio_url, ref_mp3, reciter = fetch_reciter(s, a, st.session_state.cfg_reciter)
tafsir_src = fetch_ibn_kathir(s, a)

# Top Header
st.markdown(f"<div style='text-align:center;color:var(--dim);font-size:.9rem;letter-spacing:2px;text-transform:uppercase'>Surah</div>", unsafe_allow_html=True)
st.markdown(f"<h2 style='text-align:center;margin-top:-5px'>{ref}</h2>", unsafe_allow_html=True)

# Portrait
teacher_portrait()

t1, t2 = st.tabs(["Study", "Recite"])

# ─── TAB 1: STUDY ───
with t1:
    st.markdown(f"<div style='text-align:center;color:var(--glow);margin-bottom:10px'>Reciter: {reciter}</div>", unsafe_allow_html=True)
    if audio_url and words:
        # Exact dynamic height calculation for tight spacing
        rows = math.ceil(len(words) / 3)
        iframe_height = max(250, rows * 130 + 80)
        components.html(player_html(words, _data_uri(ref_mp3)), height=iframe_height, scrolling=False)
    
    st.divider()
    if st.button("📖 Generate Tafsir", use_container_width=True):
        try:
            with st.spinner("Preparing tafsir..."):
                st.session_state.tafsir_text[key] = call_gemini([{"text": f"Explain {ref} ({verse}) in ~200 words based on Ibn Kathir. Source:\n{tafsir_src}"}])
        except Exception as e: st.error(e)
    
    if key in st.session_state.tafsir_text:
        st.markdown(f'<div class="glass">{_h.escape(st.session_state.tafsir_text[key])}</div>', unsafe_allow_html=True)

# ─── TAB 2: RECITE ───
with t2:
    res = st.session_state.last_analysis.get(key)
    
    if not res:
        st.markdown(f'<div class="ayah-text blur-text">{verse}</div>', unsafe_allow_html=True)
    else:
        m_ = res.get("match")
        if m_ and words:
            st.markdown(feedback_html(words, m_["states"], res.get("rules_check", [])), unsafe_allow_html=True)
            st.markdown(f"<div style='text-align:center;color:var(--glow);font-size:1.2rem;margin:20px 0'>Score: {res.get('overall_score',0)}%</div>", unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="ayah-text">{verse}</div>', unsafe_allow_html=True)

    st.markdown("<div style='text-align:center;color:var(--dim);margin:20px 0'>Tap below and recite from memory</div>", unsafe_allow_html=True)
    
    st.markdown('<div class="mic-container">', unsafe_allow_html=True)
    wav = None
    if hasattr(st, "audio_input"):
        clip = st.audio_input("Recite", label_visibility="collapsed")
        if clip: wav = boost(_valid_wav(clip.getvalue()))[0]
    else:
        m = mic_recorder(start_prompt="🎙️ Tap to talk", stop_prompt="⏹️ Send", key="recite", just_once=True, format="wav")
        if m: wav = boost(m["bytes"])[0]
    st.markdown('</div>', unsafe_allow_html=True)
    
    if wav and ref_mp3:
        with st.spinner("Analyzing your recitation..."):
            try:
                heard = transcribe(wav, arabic=True)
                if not heard: st.warning("I couldn't hear the recitation.")
                else:
                    rules = tajweed_rules(verse)
                    r = analyse(verse, ref_mp3, wav, reciter, rules, heard)
                    r["match"] = match_report([w["ar"] for w in words], heard)
                    st.session_state.last_analysis[key] = r
            except Exception as e:
                st.error(f"Analysis error: {e}")
        st.rerun()
    
    if res:
        if st.button("Try Again", use_container_width=True, type="primary"):
            st.session_state.last_analysis.pop(key, None)
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True)
