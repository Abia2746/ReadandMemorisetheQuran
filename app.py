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
    return ((P[:2] + F[:2] + L[:1]) if pro else (F[:2] + P[:1] + L[:1])) or ["gemini-3.8-flash"]
def call_gemini(parts, expect_json=False, pro=False):
    """
    Optimized fast engine. Passes the key directly in the URL 
    and targets a fast model directly to eliminate the 404 error and loading lag.
    """
    model_target = "gemini-1.5-flash" if not pro else "gemini-1.5-pro"
    url = f"https://googleapis.com{model_target}:generateContent?key={st.secrets['GEMINI_API_KEY']}"
    headers = {"Content-Type": "application/json"}
    
    p = {"contents": [{"parts": parts}]}
    if expect_json: 
        p["generationConfig"] = {"responseMimeType": "application/json"}
        
    for attempt in range(3):
        try:
            r = requests.post(url, json=p, headers=headers, timeout=45)
            if r.status_code == 200:
                try: 
                    ps = r.json()["candidates"]["content"]["parts"]
                    t = "".join(x.get("text", "") for x in ps if not x.get("thought")).strip()
                    if expect_json:
                        return json.loads(re.sub(r"^```(?:json)?|```$", "", t).strip())
                    return t
                except (KeyError, IndexError):
                    break
            if r.status_code in (429, 500, 503): 
                time.sleep(2 ** attempt)
                continue
            break
        except Exception:
            if attempt == 2: pass
    return ""

def speak(text):
    try:
        r = requests.post(f"https://elevenlabs.io{VOICE_ID}",
            headers={"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": st.secrets["ELEVENLABS_API_KEY"]},
            json={"text": text[:1500], "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": .6, "similarity_boost": .8}}, timeout=60)
        if r.status_code == 200: return r.content
        st.sidebar.error(f"ElevenLabs {r.status_code}: {r.text[:200]}")
    except Exception as e:
        st.sidebar.error(f"Voice error: {e}")

@st.cache_data(show_spinner=False)
def fetch_verse(s, a):
    try:
        r = requests.get(f"https://alquran.cloud{s}:{a}/quran-uthmani", timeout=15).json()
        return r["data"]["text"]
    except Exception:
        return ""

@st.cache_data(show_spinner=False)
def fetch_words(s, a):
    """Restored your exact dictionary structure mapping 'ar', 'en', and 'tr' keys"""
    try:
        r = requests.get(f"https://quran.com{s}:{a}",
            params={"words": "true", "word_fields": "text_uthmani", "language": "en"}, timeout=20).json()
        return [{"ar": w["text_uthmani"], "en": (w.get("translation") or {}).get("text", ""),
                 "tr": (w.get("transliteration") or {}).get("text") or ""}
                for w in r["verse"]["words"] if w.get("char_type_name") == "word"]
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def fetch_reciter(s, a):
    """Sheikh Yasser Al-Dosari (everyayah.com); cleanly falls back to Alafasy if unavailable."""
    url = f"https://everyayah.com{s:03d}{a:03d}.mp3"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200 and len(r.content) > 2000:
            return url, r.content, "Sheikh Yasser Al-Dosari"
    except Exception:
        pass
    
    fallback_url = f"https://everyayah.com{s:03d}{a:03d}.mp3"
    try:
        r = requests.get(fallback_url, timeout=30)
        if r.status_code == 200 and len(r.content) > 2000:
            return fallback_url, r.content, "Mishary Rashid Alafasy"
    except Exception:
        pass
    return None, b"", ""

        return []

@st.cache_data(show_spinner=False)
def fetch_reciter(s, a):
    """Sheikh Yasser Al-Dosari (everyayah.com); cleanly falls back to Alafasy if unavailable."""
    url = f"https://everyayah.com{s:03d}{a:03d}.mp3"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200 and len(r.content) > 2000:
            return url, r.content, "Sheikh Yasser Al-Dosari"
    except Exception:
        pass
    
    # Fallback to Alafasy if Al-Dosari is down
    fallback_url = f"https://everyayah.com{s:03d}{a:03d}.mp3"
    try:
        r = requests.get(fallback_url, timeout=30)
        if r.status_code == 200 and len(r.content) > 2000:
            return fallback_url, r.content, "Mishary Rashid Alafasy"
    except Exception:
        pass
    return None, b"", ""

        pass
    try:
        meta = requests.get(f"https://api.alquran.cloud/v1/ayah/{s}:{a}/ar.alafasy", timeout=15).json()["data"]["audio"]
        return meta, requests.get(meta, timeout=30).content, "Mishary Alafasy (Dosari unavailable)"
    except Exception:
        return None, None, None

@st.cache_data(show_spinner=False)
def fetch_ibn_kathir(s, a):
    try:
        r = requests.get(f"https://api.quran.com/api/v4/tafsirs/169/by_ayah/{s}:{a}", timeout=20).json()
        t = re.sub(r"<[^>]+>", " ", r["tafsir"]["text"])
        return re.sub(r"\s+", " ", t).strip()[:7000]
    except Exception:
        return ""

# ---------- highlighting player ----------
def player_html(words, audio_url):
    tpl = """
<style>
body{margin:0;font-family:Georgia,serif;background:transparent}
#w{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;direction:rtl}
.c{padding:10px 14px;border-radius:14px;text-align:center;background:rgba(255,255,255,.6);border:1px solid rgba(197,168,92,.3);transition:all .15s}
.ar{font-family:Amiri,'Scheherazade New',serif;font-size:2.1rem;color:#7a5c12;line-height:1.8}
.tr{font-size:.8rem;color:#8a8574;font-style:italic}.en{font-size:1rem;color:#2b2a26}
.on{background:rgba(229,193,88,.45);transform:scale(1.07);box-shadow:0 0 18px rgba(197,168,92,.6)}
audio{width:100%;margin-top:18px}
</style>
<div id="w"></div><audio id="a" controls src="__URL__"></audio><div id="n" style="text-align:center;margin-top:10px;color:#7a5c12;font-weight:600"></div><div style="text-align:center;margin-top:8px">🔈 <input id="v" type="range" min="0" max="100" value="50" style="width:60%"> 🔊 <button id="sp" style="margin-left:10px;border-radius:999px;border:1px solid #E6DCC8;background:#FDFBF6;padding:6px 12px">1×</button></div>
<script>
const W=__WORDS__,a=document.getElementById('a'),box=document.getElementById('w');
const els=W.map(w=>{const d=document.createElement('div');d.className='c';
d.innerHTML='<div class="ar">'+w.ar+'</div><div class="tr">'+w.tr+'</div><div class="en">'+w.en+'</div>';box.appendChild(d);return d;});
let cum=[];
const L=w=>Math.max(1,w.ar.replace(/[\u064B-\u0652\u0670\u06D6-\u06ED\u0640]/g,'').length);function build(){const d=a.duration||1,l=d*.05,sp=d*.88,tot=W.reduce((s,w)=>s+L(w),0);let t=l;
cum=W.map(w=>{t+=sp*L(w)/tot;return t;});}
a.onloadedmetadata=build;
a.ontimeupdate=()=>{if(!cum.length)build();const t=a.currentTime;let i=cum.findIndex(c=>t<c);if(a.ended)i=-1;
els.forEach((e,k)=>e.classList.toggle('on',k===i));};
const ctx=new (window.AudioContext||window.webkitAudioContext)();const g=ctx.createGain();
ctx.createMediaElementSource(a).connect(g);g.connect(ctx.destination);
const vs=document.getElementById('v');g.gain.value=vs.value/100;
vs.oninput=()=>{g.gain.value=vs.value/100;ctx.resume();};
a.addEventListener('play',()=>ctx.resume());
const sb=document.getElementById('sp');sb.onclick=()=>{a.playbackRate=a.playbackRate==1?1.25:a.playbackRate==1.25?.75:1;sb.textContent=a.playbackRate+'×';};
let n=1,done=false;const cn=document.getElementById('n');
function upd(){cn.textContent=done?'✅ All 5 listens complete':'Listen '+n+' of 5';}
a.onplay=()=>{if(done){n=1;done=false;}upd();};
a.onended=()=>{els.forEach(e=>e.classList.remove('on'));if(n<5){n++;upd();setTimeout(()=>a.play(),1500);}else{done=true;upd();}};
upd();
</script>"""
    t = T()
    for o, n in (("#7a5c12", t["word"]), ("#2b2a26", t["word"]), ("#8a8574", t["dim"]), ("rgba(255,255,255,.6)", "rgba(128,128,128,.10)"), ("rgba(197,168,92,.3)", t["rule"]), ("rgba(229,193,88,.45)", t["glow"] + "66")):
        tpl = tpl.replace(o, n)
    return tpl.replace("__URL__", audio_url).replace("__WORDS__", json.dumps(words, ensure_ascii=False))

# ---------- AI teachers ----------
@st.cache_data(show_spinner=False)
def explain_tafsir(verse_ref, verse, source):
    prompt = f"""You are a warm, learned Quran teacher. Explain {verse_ref} ({verse}) to a student in beautiful, clear English (about 250 words).
Base your explanation ONLY on the tafsir source text below, and say it comes from Ibn Kathir (abridged). Structure: context of the verse, meaning, lessons to take to heart.
If the source is empty or unrelated, say the source could not be loaded and keep to well-established basics only. Do not invent narrations or attribute sayings you can't see in the source.

SOURCE:
{source or '(unavailable)'}"""
    return call_gemini([{"text": prompt}])

def scholar_reply(verse_ref, verse, source, history, question):
    convo = "\n".join(f"{m['role']}: {m['text']}" for m in history[-6:])
    prompt = f"""You are a gentle, knowledgeable Quran teacher chatting with {st.session_state.user_name} about {verse_ref}: {verse}
Answer in English, under 150 words, no markdown symbols. Ground answers in the tafsir source below and say when you are drawing on it (Ibn Kathir).
If the source doesn't cover the question, say so plainly and give only what is widely agreed, never inventing hadith, narrations or scholar names.
You are an AI study aid, not a mufti: for fiqh rulings or personal religious questions, advise asking a qualified scholar.

TAFSIR SOURCE:
{source or '(unavailable)'}

CONVERSATION:
{convo}
student: {question}"""
    return call_gemini([{"text": prompt}])

@st.cache_data(show_spinner=False)
def tajweed_rules(verse):
    return call_gemini([{"text": "List every tajweed rule that truly applies in this ayah, word by word in order, one short line each: word (Arabic + transliteration) - rule - what to do (counts for madd, etc). Use these 16 categories, starting each line with its category number, and include only categories that actually occur: " + TAJWEED_16 + ". No invention, no markdown symbols.\n\n" + verse}], pro=True)

def analyse(verse, ref_mp3, student_wav, reciter, heard=""):
    prompt = f"""You are an expert Tajweed teacher. The student recited this ayah from memory: {verse}
Clip 1 is the reference by {reciter}. Clip 2 is the student.
Compare word by word: harakat, sukoon, madd length, ghunnah, idgham/ikhfa/iqlab/izhar, qalqalah, makharij, waqf. Also say if any words were skipped or wrong (memorisation errors).
Write in English; Arabic words in script plus transliteration. Report only what you can actually hear; admit uncertainty; never invent mistakes. If the clip is silent or the wrong ayah, say so.
Checklist of tajweed rules in this ayah:
{tajweed_rules(verse)}
Also compare breath control (where each reciter breathes or pauses, and whether the student's breath lasted each phrase). Marking strictness: {st.session_state.get("cfg_strict", "Standard")}. Independent ASR transcript of the student (cross-check only; trust your own hearing if they differ): {heard or "(none)"}. First write in heard_text, in Arabic script, exactly the words the student recited as you hear them (use [unclear] where you cannot tell). If you hear no clear recitation, set heard_text to "" and overall_score to 0 and give no word feedback; never invent mistakes. Judge each checklist rule separately, citing roughly where (seconds) you heard it in each clip, with a confidence level.
Return JSON only: {{"overall_score":int,"rules_check":[{{"rule":"","word":"","verdict":"correct|partly|missed|unclear","evidence":"","confidence":"high|medium|low"}}],"heard_text":"","breath":{{"reference":"","student":"","tip":""}},"spoken_summary":"max 60 words, warm","words":[{{"word":"","status":"good|needs_work","student_did":"","correction":""}}],"practice_tip":""}}"""
    return call_gemini([{"text": prompt}, {"text": "Clip 1 (reference):"}, audio_part(ref_mp3, "audio/mpeg"),
                        {"text": "Clip 2 (student):"}, audio_part(student_wav, "audio/wav")], True, pro=True)

def plan_sessions(goal, s, a):
    prompt = f"""Create a realistic 7-day Quran memorisation plan for {st.session_state.user_name}, currently at Surah {s}, Ayah {a}. Their goal: {goal}.
Use the Sabaq (new), Sabqi (recent review), Manzil (old review) structure, with the 5-listen method, tafsir reading and recitation check each day. Plain English, short, one line per day, no markdown symbols."""
    return call_gemini([{"text": prompt}])

def boost(wav_bytes):
    """Amplifies quiet recordings (normalises to ~90% of full scale, max 30x). Returns (wav, peak_fraction_before)."""
    try:
        with wave.open(io.BytesIO(wav_bytes)) as w:
            ch, sw, fr = w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(w.getnframes())
        if sw != 2: return wav_bytes, 1.0
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        if x.size == 0: return wav_bytes, 0.0
        peak = float(np.percentile(np.abs(x), 99.5))
        frac = peak / 32768
        if peak < 30: return wav_bytes, frac
        y = np.clip(x * min(float(st.session_state.get("cfg_gain", 12)), 0.9 * 32767 / peak), -32768, 32767).astype(np.int16)
        out = io.BytesIO()
        with wave.open(out, "wb") as w2:
            w2.setnchannels(ch); w2.setsampwidth(2); w2.setframerate(fr); w2.writeframes(y.tobytes())
        return out.getvalue(), frac
    except Exception:
        return wav_bytes, 1.0

def loader_html(label, secs):
    return f'<div class="ld"><div class="ind"></div>✨ {label} · {secs}s</div>'

def run_with_progress(fn, label, est=15):
    """Indeterminate loader with a real elapsed-seconds counter. Gives up after est*2.5 s with an error instead of hanging."""
    box, out = st.empty(), {}
    def work():
        try: out["v"] = fn()
        except Exception as e: out["e"] = e
    t = threading.Thread(target=work)
    add_script_run_ctx(t, get_script_run_ctx())
    t.start(); t0 = time.time()
    while t.is_alive():
        el = time.time() - t0
        if el > est * 2.5:
            box.empty()
            raise TimeoutError("This is taking too long. Check your connection and try again.")
        box.markdown(loader_html(label, int(el)), unsafe_allow_html=True)
        time.sleep(0.25)
    box.empty()
    if "e" in out: raise out["e"]
    return out["v"]

def transcribe(wav, orig=None):
    p = "This is a short voice message from a Quran student speaking English (they may use words like tajweed, madd, ghunnah, ayah, surah, qalqalah, ikhfa, waqf). Transcribe it word for word. Output only the transcript. Use [inaudible] only if there is truly no speech."
    for audio, pro in ((wav, False), (orig or wav, False), (wav, True)):
        t = call_gemini([{"text": p}, audio_part(audio, "audio/wav")], pro=pro).strip()
        if t and "[inaudible]" not in t.lower(): return t
    return ""

def asr_arabic(wav, orig=None):
    p = "Transcribe this Quran recitation exactly as actually spoken, in Arabic script (diacritics optional). Do NOT correct it and do NOT complete it from memory: write only what you hear, including mistakes, repeats and skipped words. If there is no speech output exactly: [inaudible]"
    for audio, pro in ((wav, False), (orig or wav, False), (wav, True)):
        t = call_gemini([{"text": p}, audio_part(audio, "audio/wav")], pro=pro).strip()
        if t and "[inaudible]" not in t.lower(): return t
    return ""

def norm_ar(t):
    t = re.sub("[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]", "", t)
    t = re.sub("[إأآٱ]", "ا", t).replace("ى", "ي").replace("ة", "ه")
    return re.sub("[^\u0621-\u064A\\s]", "", t).split()

def nw_align(exp, heard):
    n, m = len(exp), len(heard)
    sc = lambda e, h: 2 if e == h else (1 if e[:2] == h[:2] and abs(len(e) - len(h)) <= 1 else 0)
    D = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1): D[i][0] = -i
    for j in range(1, m + 1): D[0][j] = -j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i][j] = max(D[i-1][j-1] + sc(exp[i-1], heard[j-1]), D[i-1][j] - 1, D[i][j-1] - 1)
    st_, i, j, extra = ["missed"] * n, n, m, 0
    while i > 0 or j > 0:
        if i and j and D[i][j] == D[i-1][j-1] + sc(exp[i-1], heard[j-1]):
            x = sc(exp[i-1], heard[j-1]); st_[i-1] = {2: "correct", 1: "close"}.get(x, "missed"); extra += (x == 0); i -= 1; j -= 1
        elif i and D[i][j] == D[i-1][j] - 1: i -= 1
        else: extra += 1; j -= 1
    return st_, extra

def match_report(words_ar, heard):
    exp = ["".join(norm_ar(w)) for w in words_ar]; hw = norm_ar(heard)
    if not hw or len(hw) < 0.25 * len(exp): return None
    st_, extra = nw_align(exp, hw)
    pts = sum(1 if x == "correct" else .5 if x == "close" else 0 for x in st_)
    return {"pct": round(100 * pts / len(exp)), "states": st_, "missing": [w for w, x in zip(exp, st_) if x == "missed"], "extra": extra, "n_ok": st_.count("correct"), "total": len(exp)}

def feedback_tiles(words, states):
    mark = {"correct": "✓", "close": "•", "missed": "✕"}
    h = "".join(f'<span class="ft {x}" style="animation-delay:{200 + i * 40}ms">{w["ar"]}<small>{mark[x]}</small></span>' for i, (w, x) in enumerate(zip(words, states)))
    return f'<div class="glass ayahbox">{h}</div>'

def tajweed_hints(words):
    out = []
    for w in words:
        t, name = w["ar"], w.get("tr") or w["ar"]
        if re.search("[نم]\u0651", t): out.append(("Ghunnah", name, "hold the sound through the nose for two counts."))
        if re.search("ٱل[\u0621-\u064A]\u0651", t): out.append(("Lam Shamsiyyah", name, "the lam is silent and the next letter is doubled."))
    return out

SS = [1,2,50,77,106,128,151,177,187,208,221,235,249,255,262,267,282,293,305,312,322,332,342,350,359,367,377,385,396,404,411,415,418,428,434,440,446,453,458,467,477,483,489,496,499,502,507,511,515,518,520,523,526,528,531,534,537,542,545,549,551,553,554,556,558,560,562,564,566,568,570,572,574,575,577,578,580,582,583,585,586,587,587,589,590,591,591,592,593,594,595,595,596,596,597,597,598,598,599,599,600,600,601,601,601,602,602,602,603,603,603,604,604,604]
MPP = {"none": 60, "juz30": 45, "some": 32, "most": 22}

def compute_plan(goal, t, deadline, minutes, known):
    today = datetime.date.today(); avail = max(1, (deadline - today).days)
    total = (21 if t == 1 else 23 if t == 30 else 20) if goal == "juz" else max(1, (605 if t == 114 else SS[t]) - SS[t-1]) if goal == "surah" else 604
    base = (1 if t == 1 else 22 + (t - 2) * 20) if goal == "juz" else SS[t-1] if goal == "surah" else 1
    strengthen = goal == "strengthen"; mpp = 12 if strengthen else MPP[known]
    held = 0 if strengthen else min(21, total) if known == "juz30" else round(total * .3) if known == "some" else round(total * .7) if known == "most" else 0
    rem = max(0, total - held); ppd = (minutes if strengthen else minutes * .65) / mpp
    need = math.ceil(rem / ppd) if rem else 0; hours = rem * mpp / 60
    band = "feasible" if rem == 0 or need / avail <= 1 else "tight" if need / avail <= 1.3 else "infeasible"
    alt = ""
    if band == "infeasible":
        maxp = int(ppd * avail) + held
        if goal in ("full", "strengthen"):
            i = 114
            while i > 1 and 604 - SS[i-2] + 1 <= maxp: i -= 1
            n = 115 - i; alt = "a single ayah a day" if maxp < 1 else f"the last {n} sūrah{'s' if n > 1 else ''} (sūrahs {i}–114)"
        else: alt = f"the first {max(1, min(total, maxp))} pages of this target"
    sched, cur = [], 0.0
    for d in range(min(60, need)):
        f, tt = int(cur) + 1, min(rem, math.ceil(cur + ppd))
        sched.append({"date": today + datetime.timedelta(d), "f": base + held + f - 1, "t": base + held + tt - 1,
                      "rev": round(minutes * (1 if strengthen else .35)), "new": 0 if strengthen else round(minutes * .65)}); cur += ppd
    return dict(avail=avail, total=total, held=held, rem=rem, ppd=ppd, need=need, hours=hours, band=band, alt=alt, sched=sched, finish=today + datetime.timedelta(need))

def card(t):
    st.markdown(f'<div class="glass">{_h.escape(str(t)).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

AUDIO_TPL = """<style>body{margin:0;font-family:Georgia,serif;background:transparent;text-align:center}audio{width:100%}input{width:60%}</style>
<audio id="a" controls __AUTO__ src="__URI__"></audio>
<div>🔈 <input id="v" type="range" min="0" max="100" value="50"> 🔊</div>
<script>
const a=document.getElementById('a'),v=document.getElementById('v');
const ctx=new (window.AudioContext||window.webkitAudioContext)();
const g=ctx.createGain();ctx.createMediaElementSource(a).connect(g);g.connect(ctx.destination);
g.gain.value=v.value/100;
v.oninput=()=>{g.gain.value=v.value/100;ctx.resume();};
a.addEventListener('play',()=>ctx.resume());
</script>"""

def play(b, mime="audio/mpeg", auto=True):
    uri = f"data:{mime};base64," + base64.b64encode(b).decode()
    components.html(AUDIO_TPL.replace("__URI__", uri).replace("__AUTO__", "autoplay" if auto else ""), height=110)

def voice_in(key, label):
    """Aesthetic mic; quiet recordings are amplified before use. Returns wav bytes once per recording."""
    st.markdown(f"<div style='text-align:center;color:#7a5c12'>🎙️ {label}</div>", unsafe_allow_html=True)
    if not hasattr(st, "audio_input"):
        m = mic_recorder(start_prompt="🎙️ Tap to talk", stop_prompt="⏹️ Send", key=key, just_once=True)
        if not m: return None
        b = m["bytes"]
    else:
        clip = st.audio_input(label, key=key, label_visibility="collapsed")
        if clip is None: return None
        b = clip.getvalue(); hs = hash(b)
        if st.session_state.get("seen_" + key) == hs: return None
        st.session_state["seen_" + key] = hs
    b2, frac = boost(b)
    st.session_state["lvl_" + key] = frac
    st.session_state["orig_" + key] = b
    try:
        with wave.open(io.BytesIO(b)) as w: dur = w.getnframes() / w.getframerate()
    except Exception: dur = 0
    st.session_state["diag_" + key] = f"Captured {dur:.1f}s of audio · mic level {frac*100:.0f}%"
    return b2

def understand_and_answer(ref, verse, ctx, hist, q):
    g = st.session_state.get
    style = {"Warm & casual": "a warm, casual sheikh chatting over tea", "Classical scholar": "a dignified, precise and gentle classical scholar", "Concise coach": "a crisp, friendly tajweed coach"}[g("cfg_style", "Warm & casual")]
    words = {1: 60, 2: 130, 3: 250}[g("cfg_detail", 2)]
    convo = "\n".join(f"{m['role']}: {m['text']}" for m in hist[-10:])
    prompt = f"""You are {style}, teaching {st.session_state.user_name} (level: {g('cfg_level', 'Beginner')}). They are on {ref}: {verse}, but they may ask about ANYTHING related to the Quran, tajweed, Arabic, memorisation, tafsir, the Prophets, seerah, Islamic basics or this app. Answer the question they actually asked, even if it is unrelated to the current ayah.
Step 1: work out what they really mean (use the conversation to resolve words like 'it' or 'that', and fix likely speech-recognition errors).
Step 2: answer directly in about {words} words, spoken style, no markdown, no lists, Arabic terms in transliteration. Use the REFERENCE MATERIAL when relevant but do not limit yourself to it. Say plainly when you rely on general knowledge. Never invent hadith, narrations or scholar names; if unsure, say so. For fiqh rulings give the mainstream view briefly and suggest a qualified scholar. If the message is truly unclear, ask one short clarifying question instead of guessing. End with at most one short follow-up question.
Return JSON only: {{"understood":"<their question rewritten clearly in one sentence>","answer":"<your answer>"}}
REFERENCE MATERIAL:
{ctx}
CONVERSATION:
{convo}
STUDENT'S MESSAGE: {q}"""
    return call_gemini([{"text": prompt}], True, pro=(g("cfg_quality", "Best") == "Best"))

@st.cache_data(show_spinner=False)
def fetch_translation(s, a):
    try: return requests.get(f"https://api.alquran.cloud/v1/ayah/{s}:{a}/en.sahih", timeout=15).json()["data"]["text"]
    except Exception: return ""

def ctx_for(s, a, src):
    return f"English translation (Sahih International): {fetch_translation(s, a)}\nTafsir Ibn Kathir (abridged): {src}"

def teacher_turn(key, ctx, ref, verse, hist_key):
    wav = voice_in(key + "_v", "Tap the mic and talk to your teacher")
    st.caption(st.session_state.get("diag_" + key + "_v", ""))
    txt = st.chat_input("...or type here", key=key + "_t")
    hist = st.session_state.setdefault(hist_key, [])
    audio = None
    if wav or txt:
        def job():
            q = transcribe(wav, st.session_state.get("orig_" + key + "_v")) if wav else txt
            if not q: return "", "", "I couldn't make out any speech in that recording. Check the mic level above, move a little closer and try again.", False
            r = understand_and_answer(ref, verse, ctx, hist, q)
            return q, r.get("understood", ""), r.get("answer", ""), True
        try:
            q, und, ans, heard = run_with_progress(job, "Listening and thinking", 20)
            if heard:
                hist += [{"role": "student", "text": ("🎙️ You said: " if wav else "") + q}, {"role": "teacher", "text": ans, "u": und}]
                if st.session_state.get("cfg_voice", True): audio = run_with_progress(lambda: speak(ans), "Preparing voice", 6)
            else:
                st.warning(ans)
        except Exception as e:
            st.error(e)
    if audio: play(audio)
    for m in hist:
        with st.chat_message("user" if m["role"] == "student" else "assistant"):
            if m.get("u"): st.caption("Understood: " + m["u"])
            st.write(m["text"])

@st.cache_data(show_spinner=False)
def recitation_lesson(s, a, verse, rules, _mp3, reciter):
    prompt = f"""You are a master Quran reciter-teacher. Listen to this reference recitation by {reciter} of: {verse}
Teach it step by step in plain English (Arabic in script plus transliteration), no markdown symbols, with these capitalised sections:
PHRASES: split into natural phrases; for each give transliteration, tricky letters (makharij) and tajweed rules with counts, using this checklist: {rules}
BREATH MAP: where the reciter breathes or pauses, roughly how many seconds each phrase lasts, the best places for a beginner to breathe, and safe waqf points.
PACING: three short tips for steady air (long madds, ghunnah, ending the ayah).
COMMON MISTAKES: three typical errors for this ayah.
Only describe what you can hear or what the rules require; say where you are unsure."""
    return call_gemini([{"text": prompt}, audio_part(_mp3, "audio/mpeg")], pro=True)

THEMES = {
 "White": dict(bg="#FDFBF6", bg2="#F4EEE1", word="#241C17", dim="#8A7A66", glow="#B8912F", rule="rgba(36,28,23,.10)", wash="rgba(184,145,47,.16)", ok="#2E7D5B", bad="#C0453A"),
 "Brown": dict(bg="#241B15", bg2="#3A2C22", word="#F4E8D2", dim="#8A7A66", glow="#C9A227", rule="rgba(244,232,210,.14)", wash="rgba(201,162,39,.22)", ok="#7FD1A8", bad="#FF8A7E"),
 "Night": dict(bg="#0A0E18", bg2="#151B2B", word="#F3EEE2", dim="#6E7789", glow="#D9B45B", rule="rgba(243,238,226,.12)", wash="rgba(217,180,91,.20)", ok="#7FD1A8", bad="#FF8A7E"),
 "Black": dict(bg="#000000", bg2="#0A0A0A", word="#FFFFFF", dim="#5A5A5A", glow="#FFD166", rule="rgba(255,255,255,.12)", wash="rgba(255,209,102,.18)", ok="#7FD1A8", bad="#FF8A7E"),
}
def T(): return THEMES[st.session_state.get("cfg_theme", "White")]

def apply_theme():
    t, name = T(), st.session_state.get("cfg_theme", "White")
    rnd = random.Random(7)
    stars = ",".join(f"{rnd.randint(0,100)}vw {rnd.randint(0,100)}vh 0 {rnd.choice([0,0,1])}px rgba(243,238,226,{rnd.uniform(.25,.9):.2f})" for _ in range(140))
    star_css = ".stApp::before{content:'';position:fixed;left:0;top:0;width:1px;height:1px;box-shadow:" + stars + ";animation:tw 7s ease-in-out infinite;pointer-events:none;z-index:0}@keyframes tw{0%,100%{opacity:.5}50%{opacity:1}}@media(prefers-reduced-motion:reduce){.stApp::before{animation:none}}" if name == "Night" else ""
    st.markdown(f"""<style>
:root{{--bg:{t['bg']};--bg2:{t['bg2']};--word:{t['word']};--dim:{t['dim']};--wash:{t['wash']};--glow:{t['glow']};--rule:{t['rule']};--ok:{t['ok']};--bad:{t['bad']}}}
.stApp{{background:var(--bg)!important;transition:background-color .24s}}
[data-testid="stSidebar"]{{background:var(--bg2)!important}}
.stApp p,.stApp li,.stApp label,.stApp span,.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp [data-testid="stCaptionContainer"]{{color:var(--word)!important}}
div.stButton>button,div.stButton>button *{{color:#241C17!important}}
.ban p,.ld{{color:#fff!important}}
.glass{{background:var(--bg2)!important;border-color:var(--rule)!important}}
.ayahbox{{background:transparent!important;border:0!important;box-shadow:none!important}}
.ft.correct{{background:var(--wash);color:var(--word)}}.ft.correct small{{color:var(--ok)}}
.ft.close{{background:var(--wash);box-shadow:inset 0 -3px var(--glow);color:var(--word)}}.ft.missed{{color:var(--bad)}}.ft.hide{{background:var(--bg2)}}
.ld{{position:relative;overflow:hidden}}.ld .ind{{position:absolute;bottom:0;left:-35%;width:35%;height:5px;background:rgba(255,255,255,.9);animation:slide 1.2s ease-in-out infinite}}
@keyframes slide{{to{{left:100%}}}}
@media(prefers-reduced-motion:reduce){{.ld .ind{{animation:none;left:0;width:100%;opacity:.6}}}}
{star_css}
</style>""", unsafe_allow_html=True)

ASSETS = pathlib.Path(__file__).parent / "assets"
@st.cache_data(show_spinner=False)
def _b64(name):
    f = ASSETS / name
    return base64.b64encode(f.read_bytes()).decode() if name and f.is_file() else ""

MOTIF = '<svg width="96" height="128" viewBox="0 0 96 128" aria-hidden="true"><g transform="translate(48 64)" fill="none" stroke="#C9A227" stroke-width="2"><rect x="-22" y="-22" width="44" height="44"/><rect x="-22" y="-22" width="44" height="44" transform="rotate(45)"/></g></svg>'

def portrait():
    c = st.session_state.get("cfg_teacher", "None")
    b = _b64({"Male": "teacher_male.webp", "Female": "teacher_female.webp"}.get(c, ""))
    inner = f'<img alt="" aria-hidden="true" src="data:image/webp;base64,{b}" style="width:96px;height:128px;object-fit:cover;border-radius:16px;box-shadow:0 0 0 2px var(--glow)">' if b else MOTIF
    st.markdown(f'<div style="display:flex;justify-content:center;margin:8px 0">{inner}</div>', unsafe_allow_html=True)

# ---------- UI ----------
apply_theme()
if st.session_state.app_phase == "onboarding":
    st.title("🕌 Al-Mu'allim")
    n = st.text_input("What is your name?", placeholder="e.g., Abia")
    if st.button("Begin Session") and n.strip():
        st.session_state.user_name, st.session_state.app_phase = n.strip(), "classroom"
        st.rerun()
else:
    sb = st.sidebar
    sb.markdown(f"### 🧑‍🎓 {st.session_state.user_name}")
    si = sb.number_input("Surah", 1, 114, st.session_state.current_surah)
    ai = sb.number_input("Ayah", 1, 286, st.session_state.current_ayah)
    if sb.button("Go to this ayah"):
        st.session_state.current_surah, st.session_state.current_ayah = si, ai
        st.session_state.chat = []
        st.rerun()

    with sb.expander("⚙️ Teacher settings"):
        st.selectbox("Teacher style", ["Warm & casual", "Classical scholar", "Concise coach"], key="cfg_style")
        st.selectbox("My level", ["Beginner", "Intermediate", "Advanced"], key="cfg_level")
        st.select_slider("Answer detail", options=[1, 2, 3], value=2, format_func=lambda x: {1: "Short", 2: "Medium", 3: "Detailed"}[x], key="cfg_detail")
        st.radio("Answer quality", ["Best", "Fast"], key="cfg_quality", horizontal=True)
        st.select_slider("Recitation strictness", options=["Gentle", "Standard", "Strict"], value="Standard", key="cfg_strict")
        st.slider("Mic boost (max x)", 1, 30, 12, key="cfg_gain")
        st.toggle("Spoken replies", True, key="cfg_voice")
        st.radio("Study companion", ["None", "Male", "Female"], key="cfg_teacher", horizontal=True)
        st.caption("Illustrative portraits. Your study companion is not a person.")
        st.radio("Theme", ["White", "Brown", "Night", "Black"], key="cfg_theme", horizontal=True)

    s, a = st.session_state.current_surah, st.session_state.current_ayah
    key, ref = f"{s}:{a}", f"Surah {s}, Ayah {a}"
    verse, words = fetch_verse(s, a), fetch_words(s, a)
    audio_url, ref_mp3, reciter = fetch_reciter(s, a)
    listens = st.session_state.listens.get(key, 0)

    t1, t2, t3, t4 = st.tabs(["1 · Listen ×5", "2 · Teacher & Lesson", "3 · Recite & Coach", "4 · Plan"])

    with t1:
        st.markdown(f'<div class="glass"><div class="ar-big">{verse}</div></div>', unsafe_allow_html=True)
        if audio_url and words:
            st.caption(f"Reciter: {reciter}. Words light up as they are recited (~ timing is estimated from letter count, not measured, so it can drift).")
            components.html(player_html(words, "data:audio/mpeg;base64," + base64.b64encode(ref_mp3).decode()), height=420 + 40 * (len(words) // 6), scrolling=True)
        else:
            st.warning("Could not load audio or word-by-word data. Check your connection and reload.")
        st.progress(min(listens, 5) / 5, text=f"Listens completed: {min(listens, 5)} / 5")
        if st.button("✅ I listened once more"):
            st.session_state.listens[key] = listens + 1
            st.rerun()
        if listens >= 5: st.success("Five listens done. Read the tafsir, then try reciting from memory.")

    with t2:
        portrait()
        src = fetch_ibn_kathir(s, a)
        c1, c2 = st.columns(2)
        if c1.button("📖 Explain this ayah to me"):
            try:
                st.session_state.tafsir_text[key] = run_with_progress(lambda: explain_tafsir(ref, verse, src), "Preparing tafsir", 15)
            except Exception as e:
                st.error(e)
        if c2.button("🎓 Teach me to recite it") and ref_mp3:
            try:
                st.session_state.lessons[key] = run_with_progress(lambda: recitation_lesson(s, a, verse, tajweed_rules(verse), ref_mp3, reciter), "Teacher is listening to the reference", 45)
            except Exception as e:
                st.error(e)
        if key in st.session_state.tafsir_text:
            card(st.session_state.tafsir_text[key])
            st.caption("Based on Ibn Kathir (abridged) via quran.com. AI-written: verify important points with a qualified teacher.")
        if key in st.session_state.lessons:
            st.markdown("#### 🎓 Recitation lesson and breath map")
            card(st.session_state.lessons[key])
        hs = tajweed_hints(words)
        if hs:
            st.markdown("#### Watch for")
            card("\n".join(f"{r} in “{w}”: {n}" for r, w, n in hs) + "\nHints come from the text of the ayah, not from your audio.")
        st.markdown("#### 🎙️ Talk to your teacher")
        teacher_turn("t2", ctx_for(s, a, src), ref, verse, "chat")

    with t3:
        portrait()
        st.caption("Listen on tab 1 first, then recite from memory. Your teacher stays in the conversation afterwards.")
        conceal = st.toggle("Recite from memory", True, key="conceal")
        if not st.session_state.last_analysis.get(key):
            if conceal:
                blocks = "".join(f'<span class="ft hide" style="width:{max(2, len("".join(norm_ar(w["ar"])))) * 0.7}em"></span>' for w in words)
                st.markdown(f'<div class="glass ayahbox" aria-hidden="true">{blocks}</div><p>The text stays hidden</p>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="glass ayahbox">{verse}</div><p>Text visible</p>', unsafe_allow_html=True)
        wav = voice_in("recite", "Tap the mic, recite the ayah from memory, then stop")
        st.caption(st.session_state.get("diag_recite", ""))
        spoken = None
        if wav and ref_mp3:
            play(wav, "audio/wav", False)
            if st.session_state.get("lvl_recite", 1) < 0.05:
                st.warning("Your recording was very faint. I amplified it, but moving closer to the mic will make the feedback more accurate.")
            try:
                orig = st.session_state.get("orig_recite", wav)
                def job():
                    heard = asr_arabic(wav, orig)
                    if not heard: return None
                    r = analyse(verse, ref_mp3, wav, reciter, heard)
                    r["asr"], r["match"] = heard, match_report([w["ar"] for w in words] or verse.split(), heard)
                    return r
                res = run_with_progress(job, "Listening to your recitation", 50)
                if res is None:
                    st.warning("I couldn't pick up any recitation in that recording. Check the level shown under the mic, move closer and try again.")
                else:
                    st.session_state.last_analysis[key] = res
                    st.session_state.coach = []
                    spoken = run_with_progress(lambda: speak(res.get("spoken_summary", "")), "Preparing voice", 6)
            except Exception as e:
                st.error(f"Analysis failed: {e}")
        res = st.session_state.last_analysis.get(key)
        if res:
            st.metric("Estimated accuracy", f"{res.get('overall_score','?')}%")
            st.caption("AI estimate, not a certified assessment.")
            m_ = res.get("match")
            if m_:
                st.markdown(feedback_tiles(words, m_["states"]), unsafe_allow_html=True)
                card(f"{m_['n_ok']} of {m_['total']} words correct" + (". Every word. Move to the next ayah." if not m_["missing"] else f", {len(m_['missing'])} missed.") + f"\nExtra words: {m_['extra']} · score {m_['pct']}% (close counts half)")
                b1, b2 = st.columns(2)
                if b1.button("Once more"):
                    st.session_state.last_analysis.pop(key, None); st.rerun()
                if b2.button("Next ayah"):
                    st.session_state.current_ayah = a + 1; st.rerun()
            else:
                st.warning("I didn't hear enough of the ayah to score it. Check your microphone and try again.")
            card("What I heard you recite: " + (res.get("heard_text") or "(nothing clear)"))
            card(res.get("spoken_summary", ""))
            if spoken: play(spoken)
            b = res.get("breath") or {}
            if b:
                st.markdown("#### 🌬️ Breath control")
                card(f"Reference: {b.get('reference','')}\nYou: {b.get('student','')}\nTip: {b.get('tip','')}")
            st.markdown("#### Tajweed rule check (16 categories)")
            for r_ in res.get("rules_check", []):
                ic = {"correct": "✅", "partly": "🟡", "missed": "❌"}.get(r_.get("verdict"), "❔")
                st.markdown(f"{ic} **{r_.get('rule','')}** ({r_.get('word','')}), {r_.get('confidence','')} confidence  \n{r_.get('evidence','')}")
            for w in res.get("words", []):
                ok = w.get("status") == "good"
                with st.expander(f"{'✅' if ok else '⚠️'} {w.get('word','')}", expanded=not ok):
                    st.write(f"Heard: {w.get('student_did','')}")
                    st.write(f"Fix: {w.get('correction','')}")
            st.info(f"💡 {res.get('practice_tip','')}")
            st.markdown("#### 💬 Talk it through with your teacher")
            ctx = "Latest recitation analysis (AI estimate): " + json.dumps(res, ensure_ascii=False)[:6000] + "\nRule checklist:\n" + tajweed_rules(verse)
            teacher_turn("t3", ctx, ref, verse, "coach")

    with t4:
        P = st.session_state.setdefault("plan", {"step": 0, "goal": "full", "t": 1, "dl": datetime.date.today() + datetime.timedelta(30), "min": 30, "known": "none", "when": datetime.time(20, 0)})
        if P["step"] < 4:
            st.markdown(f"<p class='mi'>Step {P['step'] + 1} of 4 · Tell us what you want to memorise, and by when.</p>", unsafe_allow_html=True)
            st.progress((P["step"] + 1) / 4)
            if P["step"] == 0:
                gl = {"full": "The whole Qur'an", "juz": "A juz", "surah": "A sūrah", "strengthen": "Strengthen what I know"}
                P["goal"] = st.radio("What do you want to memorise?", list(gl), format_func=gl.get, index=list(gl).index(P["goal"]))
                if P["goal"] in ("juz", "surah"):
                    P["t"] = st.number_input("Which one?", 1, 30 if P["goal"] == "juz" else 114, min(P["t"], 30 if P["goal"] == "juz" else 114))
            elif P["step"] == 1:
                P["dl"] = st.date_input("By when?", P["dl"], min_value=datetime.date.today())
            elif P["step"] == 2:
                P["min"] = st.radio("How long each day?", [15, 30, 60, 120], format_func=lambda x: f"{x} minutes", index=[15, 30, 60, 120].index(P["min"]), horizontal=True)
            else:
                kn = {"none": "Nothing yet", "juz30": "Juz 30", "some": "Some of it", "most": "Most of it"}
                P["known"] = st.radio("What do you already know?", list(kn), format_func=kn.get, index=list(kn).index(P["known"]))
                st.caption("Based on what you told us.")
                P["when"] = st.time_input("When will you sit down?", P.get("when", datetime.time(20, 0)))
            c1, c2 = st.columns(2)
            if P["step"] and c1.button("Back"):
                P["step"] -= 1; st.rerun()
            if c2.button("Build my plan" if P["step"] == 3 else "Next"):
                P["step"] += 1; st.rerun()
        else:
            c = compute_plan(P["goal"], int(P["t"]), P["dl"], P["min"], P["known"])
            col = {"feasible": "#2E7D5B", "tight": "#B8912F", "infeasible": "#C0453A"}[c["band"]]
            hd = {"feasible": "This fits your time.", "tight": "This is tight. Missing a day costs you the deadline.", "infeasible": "This doesn't fit the time you've given it."}[c["band"]]
            ar_ = (f"At {P['min']} minutes a day you memorise about {c['ppd']:.1f} pages. This target is {c['total']} pages" + (f" ({c['held']} already held)" if c["held"] else "")
                   + f", so {c['rem']} pages take about {c['need']} days against the {c['avail']} you have. That is about {c['hours']:.0f} hours of memorisation inside that window.") if c["rem"] else "You've told us you hold all of this; the schedule is revision only."
            st.markdown(f'<div class="ban" style="background:{col}"><b style="font-size:1.1rem">{hd}</b><p style="color:#fff!important;margin:8px 0 0">{ar_}</p></div>', unsafe_allow_html=True)
            if c["band"] == "infeasible":
                card(f"Nearest goal that fits: {c['alt']}.\nOr keep the goal and move the date: {c['finish']} ({c['need']} days from today).")
            if c["sched"]:
                d0 = c["sched"][0]
                card(f"TODAY at {P['when'].strftime('%H:%M')} · pages {d0['f']}–{d0['t']}\n" + (f"New: {d0['new']} min · " if d0["new"] else "") + f"Review: {d0['rev']} min" + (" · Consolidate: last 8 min, from memory" if d0["new"] else ""))
                mx = max(d["rev"] + d["new"] for d in c["sched"]); pal = ["#F2EADA", "#E8D9A8", "#D9BE62", "#C9A227"]
                cells = "".join(f'<i title="{d["date"]}" style="background:{pal[min(3, math.ceil((d["rev"] + d["new"]) / mx * 3))]}"></i>' for d in c["sched"])
                st.markdown(f'<div class="glass" style="padding:16px"><p class="mi">Next {len(c["sched"])} days</p><div class="cells">{cells}</div></div>', unsafe_allow_html=True)
            if st.button("Change plan"):
                P["step"] = 0; st.rerun()
