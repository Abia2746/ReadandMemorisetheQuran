# app.py — Al-Mu'allim · Tilawa.ai Ultimate Parity Build
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
ASSETS = pathlib.Path(__file__).parent / "assets"

# Aesthetic fallback if user hasn't provided images yet
_FALLBACK_MALE = "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&q=80&w=600&h=800"
_FALLBACK_FEMALE = "https://images.unsplash.com/photo-1580489944761-15a19d654956?auto=format&fit=crop&q=80&w=600&h=800"

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
    "deep_analysis": False,
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
    except Exception:
        pass
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
    if not api_key: raise RuntimeError("Gemini API key missing. Add GEMINI_API_KEY to Streamlit secrets.")
    
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
                    if not cands:
                        last_error = f"{model} blocked: {body.get('promptFeedback', {}).get('blockReason', 'empty')}"
                        break
                    rp = cands[0].get("content", {}).get("parts", [])
                    answer = "".join(p.get("text", "") for p in rp if not p.get("thought")).strip()
                    if not answer:
                        last_error = f"{model} returned empty."
                        break
                    if expect_json:
                        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", answer, flags=re.IGNORECASE).strip()
                        try:
                            return json.loads(cleaned)
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
            last_error = f"{model} ({response.status_code}): {response.text[:200]}"
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
def fetch_reciter(s, a):
    url = f"https://everyayah.com/data/Yasser_Ad-Dussary_128kbps/{s:03d}{a:03d}.mp3"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200 and len(r.content) > 2000: return url, r.content, "Sheikh Yasser Al-Dosari"
    except: pass
    try:
        meta = requests.get(f"https://api.alquran.cloud/v1/ayah/{s}:{a}/ar.alafasy", timeout=15).json()["data"]["audio"]
        return meta, requests.get(meta, timeout=30).content, "Mishary Alafasy"
    except: return None, None, None

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
# AI Prompts
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def tajweed_rules(verse):
    return call_gemini([{"text": "List every tajweed rule that applies in this ayah, word by word in order, one short line each: word (Arabic) - rule - what to do. No invention, no markdown.\n\n" + verse}], pro=True)

def analyse(verse, ref_mp3, student_wav, reciter, rules, heard=""):
    student_wav = _valid_wav(student_wav)
    prompt = f"""You are an expert Tajweed teacher. The student recited this ayah from memory: {verse}
Clip 1 is the reference. Clip 2 is the student.
Compare word by word: harakat, sukoon, madd, ghunnah, idgham/ikhfa, qalqalah, makharij, waqf.
Checklist: {rules}. Marking strictness: {st.session_state.get("cfg_strict", "Standard")}. 
ASR transcript: {heard or "(none)"}.
Write in heard_text exactly what the student recited (Arabic script). If no clear recitation, set heard_text="" and overall_score=0.
Return JSON only: {{"overall_score":int,"rules_check":[{{"rule":"","word":"","verdict":"correct|partly|missed|unclear","evidence":""}}],"heard_text":"","spoken_summary":"max 60 words, warm","words":[{{"word":"","status":"good|needs_work","student_did":"","correction":""}}],"practice_tip":""}}"""
    return call_gemini([{"text": prompt}, {"text": "Ref:"}, audio_part(ref_mp3, "audio/mpeg"), {"text": "Student:"}, audio_part(student_wav, "audio/wav")], True, pro=True)

def understand_and_answer(ref, verse, ctx, hist, q):
    style = {"Warm & casual": "a warm, casual sheikh", "Classical scholar": "a dignified, precise scholar", "Concise coach": "a crisp coach"}[st.session_state.get("cfg_style", "Warm & casual")]
    words = {1: 60, 2: 130, 3: 250}[st.session_state.get("cfg_detail", 2)]
    convo = "\n".join(f"{m['role']}: {m['text']}" for m in hist[-10:])
    prompt = f"""You are {style}, teaching {st.session_state.user_name} on {ref}: {verse}.
Answer directly in ~{words} words, spoken style, no markdown. Never invent hadith. For fiqh, suggest a scholar.
Return JSON only: {{"understood":"<rewritten question>","answer":"<answer>"}}
CONTEXT: {ctx}
CONVO: {convo}
STUDENT: {q}"""
    return call_gemini([{"text": prompt}], True, pro=True)

# ──────────────────────────────────────────────────────────────────────────────
# UI Theming (Tilawa Style)
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
.ayah-text{{font-family:'Amiri Quran',serif;font-size:3.2rem;line-height:2.4;direction:rtl;text-align:center;padding:20px;letter-spacing:1px;word-wrap:break-word}}
.ayah-text span{{position:relative;display:inline-block;transition:all .3s;border-radius:8px;padding:0 4px;margin:0 2px}}
.ayah-text span.highlight{{background:var(--wash);color:var(--glow);text-shadow:0 0 12px var(--wash)}}
.ayah-text span.correct{{color:var(--ok);border-bottom:2px solid var(--ok)}}
.ayah-text span.missed{{color:var(--bad);border-bottom:2px solid var(--bad)}}
.tw-tag{{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:999px;background:var(--bg2);border:1px solid var(--rule);font-size:.85rem;font-weight:500;margin:4px}}
.tw-dot{{width:8px;height:8px;border-radius:50%}}
.portrait-container{{position:relative;width:100%;max-width:460px;margin:0 auto;border-radius:32px;overflow:hidden;box-shadow:0 0 60px var(--wash);aspect-ratio: 4/5;display:flex;justify-content:center;align-items:center;background:#000}}
.portrait-img{{width:100%;height:100%;object-fit:cover;object-position:center 15%;transition:filter .5s;opacity:0.85}}
.listening-pill{{position:absolute;top:24px;left:50%;transform:translateX(-50%);background:rgba(20,15,10,.7);backdrop-filter:blur(12px);border:1px solid var(--rule);border-radius:999px;padding:10px 20px;display:flex;align-items:center;gap:12px;color:var(--word);font-weight:500;z-index:10;box-shadow:0 8px 32px rgba(0,0,0,.5)}}
.wave-bar{{display:flex;gap:3px;align-items:center;height:16px}}
.wave-bar span{{display:block;width:3px;background:var(--glow);border-radius:2px;animation:wave 1.2s ease-in-out infinite}}
.wave-bar span:nth-child(1){{height:8px;animation-delay:0s}} .wave-bar span:nth-child(2){{height:16px;animation-delay:.2s}} .wave-bar span:nth-child(3){{height:10px;animation-delay:.4s}} .wave-bar span:nth-child(4){{height:14px;animation-delay:.1s}} .wave-bar span:nth-child(5){{height:6px;animation-delay:.3s}}
@keyframes wave{{0%,100%{{transform:scaleY(.5);opacity:.5}}50%{{transform:scaleY(1);opacity:1}}}}
.recite-btn{{background:linear-gradient(90deg, #D4AF37, #F3E5AB, #D4AF37);background-size:200% auto;color:#000!important;border:none!important;border-radius:999px!important;padding:16px!important;font-size:1.1rem!important;font-weight:700!important;width:100%;animation:shine 3s linear infinite;box-shadow:0 0 20px rgba(212,175,55,.4)}}
@keyframes shine{{to{{background-position:200% center}}}}
.blur-text{{filter:blur(12px);user-select:none;opacity:0.6;transition:filter .4s}}
</style>""", unsafe_allow_html=True)

def teacher_portrait(state: str = "idle"):
    choice = st.session_state.get("cfg_teacher", "Female")
    name = "Omar" if choice == "Male" else "Noor"
    
    # Try to load local assets, fallback to Unsplash if missing
    img_name = "teacher_male.jpg" if choice == "Male" else "teacher_female.jpg"
    p = ASSETS / img_name
    if p.is_file():
        b = p.read_bytes()
        mime = "image/png" if img_name.endswith(".png") else "image/jpeg"
        img_src = f"data:{mime};base64,{base64.b64encode(b).decode()}"
    else:
        img_src = _FALLBACK_MALE if choice == "Male" else _FALLBACK_FEMALE

    pill = ""
    if state in ["listening", "thinking"]:
        pill = f"""<div class="listening-pill">
            <div style="width:8px;height:8px;background:var(--ok);border-radius:50%"></div>
            {name} is listening <div class="wave-bar"><span></span><span></span><span></span><span></span><span></span></div>
        </div>"""
    
    st.markdown(f'<div class="portrait-container"><img class="portrait-img" src="{img_src}">{pill}</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# HTML/JS Players
# ──────────────────────────────────────────────────────────────────────────────
def _data_uri(b, mime="audio/mpeg"):
    return f"data:{mime};base64,{base64.b64encode(b).decode()}"

def player_html(words, audio_url):
    payload = [{"ar": w.get("ar", ""), "tr": w.get("tr", ""), "en": w.get("en", "")} for w in words]
    t = {"word": "#E8D5B5", "glow": "#D4AF37", "wash": "rgba(212,175,55,.15)"}
    
    tpl = r"""
<style>
body{margin:0;font-family:'Amiri Quran',serif;background:transparent;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh}
#text{font-size:2.6rem;line-height:2.2;direction:rtl;text-align:center;color:__WORD__;padding:20px;max-width:900px}
span{transition:all .2s;display:inline-block;padding:0 4px;border-radius:8px;margin:0 2px}
span.on{background:__WASH__;color:__GLOW__;text-shadow:0 0 16px __WASH__}
audio{width:80%;max-width:600px;margin-top:30px;border-radius:999px;outline:none;filter:drop-shadow(0 8px 16px rgba(0,0,0,.4))}
audio::-webkit-media-controls-panel{background-color:__WASH__}
</style>
<div id="text"></div><audio id="a" controls src="__URL__"></audio>
<script>
const W=__WORDS__,a=document.getElementById('a'),box=document.getElementById('text');
const els=W.map(w=>{const s=document.createElement('span');s.textContent=w.ar;box.appendChild(s);return s;});
let cum=[]; const L=w=>Math.max(1,(w.ar||'').replace(/[\u064B-\u0652\u0670\u06D6-\u06ED\u0640]/g,'').length);
function build(){const d=a.duration||1,l=d*.05,sp=d*.88,tot=W.reduce((s,w)=>s+L(w),0);let t=l;
cum=W.map(w=>{t+=sp*L(w)/tot;return t;});}
a.onloadedmetadata=build;
a.ontimeupdate=()=>{if(!cum.length)build();const t=a.currentTime;let i=cum.findIndex(c=>t<c);if(a.ended)i=-1;
els.forEach((e,k)=>e.classList.toggle('on',k===i));};
</script>"""
    for k, v in {"__WORD__": t["word"], "__GLOW__": t["glow"], "__WASH__": t["wash"]}.items():
        tpl = tpl.replace(k, v)
    return tpl.replace("__URL__", audio_url).replace("__WORDS__", json.dumps(payload, ensure_ascii=False))

def feedback_html(words, states, rules):
    # Tilawa-style inline glowing text with correctness indicators
    spans = []
    for i, (word, state) in enumerate(zip(words, states)):
        arabic = _h.escape(str(word.get("ar", "")))
        cls = state if state in ["correct", "missed"] else ""
        spans.append(f'<span class="{cls}">{arabic}</span>')
    text = " ".join(spans)
    
    tags = []
    for r in rules:
        is_ok = r.get("verdict") == "correct"
        color = "var(--ok)" if is_ok else ("var(--glow)" if r.get("verdict") == "partly" else "var(--bad)")
        icon = "✓" if is_ok else "✕"
        tag = f'<div class="tw-tag"><div class="tw-dot" style="background:{color}"></div>{r.get("rule","")} <span style="color:{color};margin-left:4px">{icon}</span></div>'
        tags.append(tag)
    
    return f'<div class="ayah-text">{text}</div>' + '<div style="display:flex;flex-wrap:wrap;justify-content:center;margin-top:10px">' + "".join(tags) + '</div>'

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

with sb.expander("⚙️ Settings"):
    st.radio("Teacher", ["Female", "Male"], key="cfg_teacher", horizontal=True)

# Layout Container (mimics mobile app width)
st.markdown('<div style="max-width: 700px; margin: 0 auto; padding-top: 10px;">', unsafe_allow_html=True)

s, a = st.session_state.current_surah, st.session_state.current_ayah
key, ref = f"{s}:{a}", f"Surah {s}, Ayah {a}"

verse = fetch_verse(s, a)
words = fetch_words(s, a)
if not verse:
    st.error("Network error loading Qur'an text.")
    st.stop()

audio_url, ref_mp3, reciter = fetch_reciter(s, a)
tafsir_src = fetch_ibn_kathir(s, a)

# Top Header
st.markdown(f"<div style='text-align:center;color:var(--dim);font-size:.9rem;letter-spacing:2px;text-transform:uppercase'>Surah</div>", unsafe_allow_html=True)
st.markdown(f"<h2 style='text-align:center;margin-top:-5px'>{ref}</h2>", unsafe_allow_html=True)

# Portrait
teacher_portrait("idle")

t1, t2, t3 = st.tabs(["Study", "Recite", "Chat"])

# ─── TAB 1: STUDY ───
with t1:
    st.markdown("<div style='text-align:center;color:var(--glow);margin-bottom:10px'>Listen to the reference</div>", unsafe_allow_html=True)
    if audio_url and words:
        components.html(player_html(words, _data_uri(ref_mp3)), height=400)
    
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
    
    # Text Display (Blurred if not analyzed yet, to encourage memory)
    if not res:
        st.markdown(f'<div class="ayah-text blur-text">{verse}</div>', unsafe_allow_html=True)
    else:
        m_ = res.get("match")
        if m_ and words:
            st.markdown(feedback_html(words, m_["states"], res.get("rules_check", [])), unsafe_allow_html=True)
            st.markdown(f"<div style='text-align:center;color:var(--glow);font-size:1.2rem;margin:20px 0'>Score: {res.get('overall_score',0)}%</div>", unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="ayah-text">{verse}</div>', unsafe_allow_html=True)

    # Native Mic Input
    st.markdown("<div style='text-align:center;color:var(--dim);margin:20px 0'>Tap below and recite from memory</div>", unsafe_allow_html=True)
    
    wav = None
    if hasattr(st, "audio_input"):
        clip = st.audio_input("Recite", label_visibility="collapsed")
        if clip: wav = boost(_valid_wav(clip.getvalue()))[0]
    else:
        m = mic_recorder(start_prompt="🎙️ Tap to talk", stop_prompt="⏹️ Send", key="recite", just_once=True, format="wav")
        if m: wav = boost(m["bytes"])[0]
    
    if wav and ref_mp3:
        teacher_portrait("thinking")
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
        teacher_portrait("idle")
        st.rerun()
    
    if res:
        if st.button("Try Again", use_container_width=True, type="primary"):
            st.session_state.last_analysis.pop(key, None)
            st.rerun()

# ─── TAB 3: CHAT ───
with t3:
    st.markdown("<div style='text-align:center;color:var(--glow);margin-bottom:20px'>Chat with your AI Teacher</div>", unsafe_allow_html=True)
    
    hist = st.session_state.setdefault("chat", [])
    for msg in hist:
        with st.chat_message("user" if msg["role"] == "student" else "assistant"):
            st.write(msg["text"])
    
    txt = st.chat_input("Ask a question...")
    if txt:
        hist.append({"role": "student", "text": txt})
        try:
            with st.spinner("Thinking..."):
                r = understand_and_answer(ref, verse, f"Translation: {fetch_translation(s,a)}", hist, txt)
                hist.append({"role": "teacher", "text": r.get("answer","")})
        except Exception as e: st.error(e)
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)
