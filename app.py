import base64, datetime, hashlib, io, json, math, os, pathlib, re, sqlite3, tempfile, time, wave
import numpy as np
import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Al-Mu'allim", page_icon="🕌", layout="wide", initial_sidebar_state="expanded")

try:
    DB_PATH = pathlib.Path(__file__).with_name("muallim.db")
except NameError:
    DB_PATH = pathlib.Path.cwd() / "muallim.db"

GEMINI = "https://generativelanguage.googleapis.com/v1beta/models"
RECITERS = {"Mishary Alafasy": "Alafasy_128kbps", "Yasser Al-Dosari": "Yasser_Ad-Dussary_128kbps"}
AYAHS = [0, 7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6]

# ───────────────────────────── Database ─────────────────────────────
def db():
    c = sqlite3.connect(DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS users(name TEXT PRIMARY KEY, xp INTEGER DEFAULT 0, streak INTEGER DEFAULT 0, last_day TEXT)")
    return c

def get_user(name):
    with db() as c:
        c.execute("INSERT OR IGNORE INTO users(name) VALUES(?)", (name,))
        return c.execute("SELECT xp, streak, last_day FROM users WHERE name=?", (name,)).fetchone()

def award_xp(name, xp=10, today=None):
    today = today or datetime.date.today()
    xp0, streak, last = get_user(name)
    if last != today.isoformat():
        streak = streak + 1 if last == (today - datetime.timedelta(days=1)).isoformat() else 1
    with db() as c:
        c.execute("UPDATE users SET xp=?, streak=?, last_day=? WHERE name=?", (xp0 + xp, streak, today.isoformat(), name))

# ───────────────────────────── Quran API ─────────────────────────────
@st.cache_data(show_spinner=False)
def fetch_words(s, a):
    r = requests.get(f"https://api.quran.com/api/v4/verses/by_key/{s}:{a}",
                     params={"words": "true", "word_fields": "text_uthmani", "language": "en"}, timeout=20)
    r.raise_for_status()
    out = []
    for w in r.json()["verse"]["words"]:
        if w.get("char_type_name") == "word":
            out.append({"ar": w["text_uthmani"], "en": (w.get("translation") or {}).get("text", ""),
                        "tr": (w.get("transliteration") or {}).get("text") or ""})
    if not out: raise RuntimeError("No words returned.")
    return out

@st.cache_data(show_spinner=False)
def fetch_audio(s, a, folder):
    r = requests.get(f"https://everyayah.com/data/{folder}/{s:03d}{a:03d}.mp3", timeout=30)
    if r.status_code != 200 or len(r.content) < 2000: raise RuntimeError("Audio not available.")
    return r.content

# ───────────────────────────── Audio Compression (Prevents Timeouts) ─────────────────────────────
def prep_audio(b):
    """Converts heavy mic audio into a tiny, fast-processing 16kHz mono WAV."""
    try:
        with wave.open(io.BytesIO(b)) as w:
            ch, sw, fr = w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(w.getnframes())
        if sw != 2 or not raw: return b
        
        x = np.frombuffer(raw, "<i2").astype(np.float32)
        if ch > 1:
            x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
        if fr != 16000 and len(x) > 1:
            x = np.interp(np.linspace(0, len(x) - 1, round(len(x) * 16000 / fr)), np.arange(len(x)), x)
            
        p = float(np.percentile(np.abs(x), 99.5))
        if p > 30: x = x * min(30.0, 0.9 * 32767 / p)
        
        out = io.BytesIO()
        with wave.open(out, "wb") as w2:
            w2.setnchannels(1); w2.setsampwidth(2); w2.setframerate(16000)
            w2.writeframes(np.clip(x, -32768, 32767).astype("<i2").tobytes())
        return out.getvalue()
    except Exception:
        return b

# ───────────────────────────── AI (Dynamic Model) ─────────────────────────────
def api_key():
    try: return st.secrets["GEMINI_API_KEY"]
    except: return os.environ.get("GEMINI_API_KEY", "")

def get_best_model(k):
    try:
        r = requests.get(GEMINI, headers={"x-goog-api-key": k}, params={"pageSize": 100}, timeout=10).json()
        models = [m["name"].split("/")[-1] for m in r.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        
        # Prioritize the latest models
        for pref in ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-1.5-flash-latest"]:
            if pref in models: return pref
            
        flash_models = [m for m in models if "flash" in m and "image" not in m and "tts" not in m]
        if flash_models:
            def ver(m):
                match = re.search(r'(\d+\.\d+)', m)
                return float(match.group(1)) if match else 0.0
            return sorted(flash_models, key=ver, reverse=True)[0]
    except Exception: pass
    return "gemini-3.8-flash"

def analyse_recitation_fast(wav_bytes, words, strictness, teacher_gender):
    k = api_key()
    if not k: raise RuntimeError("Add GEMINI_API_KEY in Streamlit secrets.")
    
    model = get_best_model(k)
    teacher = "a strict male Sheikh" if teacher_gender == "Male" else "a gentle female Sheikh"
    
    prompt = (f"You are {teacher}. Analyze this recitation of: "
              + json.dumps([w["ar"] for w in words], ensure_ascii=False)
              + f'. Evaluate Tajweed (Madd, Ghunnah, Qalqalah, Idgham). Strictness: {strictness}. '
              'Return JSON only: {"words":[{"i":0,"status":"good","rule":"Madd"}], "feedback":"..."}')
              
    body = {
        "contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(wav_bytes).decode()}}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1}
    }
    
    try:
        # INCREASED TIMEOUT TO 120 SECONDS
        r = requests.post(f"{GEMINI}/{model}:generateContent", headers={"x-goog-api-key": k}, json=body, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"API Error {r.status_code}: {r.text}")
            
        txt = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
        data = json.loads(re.sub(r"^```(?:json)?|```$", "", txt.strip()).strip())
        
        states = ["missed"] * len(words)
        rules = ["none"] * len(words)
        for w in data.get("words", []):
            i = w.get("i")
            if isinstance(i, int) and 0 <= i < len(words):
                states[i] = "good" if w.get("status") == "good" else "missed"
                rules[i] = w.get("rule", "none")
                
        return states, rules, str(data.get("feedback", ""))
    except Exception as e:
        raise RuntimeError(f"Analysis failed: {e}")

# ───────────────────────────── Visual Engine (React) ─────────────────────────────
PLAYER_HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<style>
body{margin:0;background:transparent;color:#E8D5B5;font-family:Inter,sans-serif;}
.ar-text{font-family:'Amiri Quran',serif; font-size: 2.2rem; line-height: 2.4; direction: rtl;}
.glass{background: rgba(30, 25, 20, 0.5); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border: 1px solid rgba(212, 175, 55, 0.15); box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);}
.glass-card{background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 16px;}
.blur-text{filter: blur(12px); opacity: 0.3; transition: all 0.5s ease; user-select: none; pointer-events: none;}

/* Tilawa.ai Style Aesthetic Highlight */
.word-span{
  display: inline-flex; flex-direction: column; align-items: center; 
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
  padding: 6px 12px; border-radius: 16px; border: 1px solid transparent;
}
.word-active{
  background: linear-gradient(135deg, rgba(212, 175, 55, 0.25), rgba(212, 175, 55, 0.05));
  border: 1px solid rgba(212, 175, 55, 0.6);
  box-shadow: 0 0 30px rgba(212, 175, 55, 0.3), inset 0 0 10px rgba(212, 175, 55, 0.1);
  transform: scale(1.08) translateY(-2px);
  backdrop-filter: blur(8px);
  z-index: 10;
}
.word-active .ar-text { color: #FFF; text-shadow: 0 0 15px rgba(212,175,55,0.9); }
.word-good{color: #4ade80; text-shadow: 0 0 15px rgba(74, 222, 128, 0.6);}
.word-missed{color: #f87171; text-shadow: 0 0 15px rgba(248, 113, 113, 0.6);}

/* Custom Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(212, 175, 55, 0.3); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: rgba(212, 175, 55, 0.6); }
</style></head>
<body><div id="root"></div><script>
const h=React.createElement,{useState,useEffect,useRef}=React,D=__DATA__;

function parseTajweed(text) {
  let html = text;
  html = html.replace(/([\u064B-\u0652]*[\u0627\u0648\u064A][\u064B-\u0652]*)/g, '<span style="color:#ff6b6b">$1</span>');
  html = html.replace(/([\u0646\u0645][\u0651])/g, '<span style="color:#4ecdc4">$1</span>');
  html = html.replace(/([\u0642\u0637\u0628\u062C\u062F][\u0652])/g, '<span style="color:#ffd93d">$1</span>');
  return html;
}

function App(){
 const [activeWord, setActiveWord] = useState(-1);
 const audioRef = useRef(null);
 const containerRef = useRef(null);

 const handleTimeUpdate = () => {
   if (!audioRef.current) return;
   const time = audioRef.current.currentTime;
   const dur = audioRef.current.duration || 1;
   const pct = time / dur;
   const idx = Math.floor(pct * D.words.length);
   setActiveWord(idx);
   
   // Auto-scroll active word into view smoothly
   if (containerRef.current) {
     const activeEl = containerRef.current.querySelector('.word-active');
     if (activeEl) activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
   }
 };

 const isBlind = D.mode === 'blind' && !D.states;

 return h('div',{className:'p-4 max-w-5xl mx-auto flex flex-col gap-4'},
   
   // Header Bar
   h('div',{className:'glass rounded-2xl p-4 flex items-center justify-between'},
     h('div',{className:'flex items-center gap-4'},
       h('div', null,
         h('div',{className:'text-[#D4AF37] text-sm font-bold tracking-wider uppercase'}, 'Al-Mu\'allim'),
         h('div',{className:'text-xs text-gray-400'}, 'Surah ' + D.meta.s + ' · Ayah ' + D.meta.a)
       )
     ),
     h('div',{className:'flex gap-3'},
        h('span',{className:'px-3 py-1 rounded-full bg-[#D4AF37]/10 border border-[#D4AF37]/30 text-[#D4AF37] text-xs font-bold'}, '⭐ ' + D.meta.xp + ' XP'),
        h('span',{className:'px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/30 text-orange-400 text-xs font-bold'}, '🔥 ' + D.meta.streak + ' Days')
     )
   ),

   // Main Recitation Area
   h('div',{className:'glass rounded-3xl p-6 relative flex flex-col'},
     
     // Scrollable Arabic Container (FORCED RTL)
     h('div',{ref:containerRef, dir:'rtl', className:'max-h-[40vh] overflow-y-auto pr-2 flex flex-wrap justify-center gap-y-4 gap-x-2 z-10'},
       D.words.map((w, i) => {
         const isActive = activeWord === i;
         const isGood = D.states && D.states[i] === 'good';
         const isMissed = D.states && D.states[i] === 'missed';
         
         let cls = 'word-span ';
         if (isGood) cls += 'word-good ';
         else if (isMissed) cls += 'word-missed ';
         else if (isActive) cls += 'word-active ';

         return h('div', {key:i, className:cls},
           // Arabic (Blurred only if blind)
           h('span', {className:'ar-text ' + (isBlind ? 'blur-text' : ''), dangerouslySetInnerHTML:{__html: parseTajweed(w.ar)}}),
           
           // Transliteration (ALWAYS VISIBLE)
           w.tr ? h('span',{className:'text-[11px] italic text-[#D4AF37] mt-1 font-semibold'}, w.tr) : null,
           
           // English Hints (ALWAYS VISIBLE)
           w.en ? h('span',{className:'text-[11px] text-[#a8987f] text-center max-w-[120px] mt-1'}, w.en) : null
         )
       })
     ),
     
     // Audio Player
     D.audio ? h('audio', {ref:audioRef, src:D.audio, controls:true, onTimeUpdate:handleTimeUpdate, className:'w-full mt-6 rounded-full outline-none sepia-[.6] saturate-150'}) : null
   ),

   // Feedback Panel
   D.states ? h('div',{className:'grid grid-cols-3 gap-4 mt-2'},
     h('div',{className:'glass-card p-4 text-center col-span-1 flex flex-col justify-center'},
       h('div',{className:'text-3xl font-bold text-green-400'}, Math.round((D.states.filter(s=>s==='good').length/D.states.length)*100)+'%'),
       h('div',{className:'text-xs text-gray-400 uppercase mt-1'}, 'Accuracy')
     ),
     h('div',{className:'glass-card p-6 col-span-2 flex flex-col justify-center'},
       h('div',{className:'text-[#D4AF37] text-sm font-bold uppercase mb-2 flex items-center gap-2'}, '🎙 Teacher Feedback'),
       h('p',{className:'text-sm text-gray-300 leading-relaxed'}, D.feedback)
     )
   ) : null
 )
}
ReactDOM.createRoot(document.getElementById('root')).render(h(App));
</script></body></html>"""

# ───────────────────────────── 3D Background ─────────────────────────────
GARDEN_HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#05080a;overflow:hidden}canvas{display:block;width:100vw;height:100vh}</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script></head><body><script>
const W=innerWidth,H=innerHeight,R=new THREE.WebGLRenderer({antialias:true,alpha:true});R.setSize(W,H);R.setPixelRatio(Math.min(devicePixelRatio,2));document.body.appendChild(R.domElement);
const S=new THREE.Scene();S.fog=new THREE.FogExp2(0x05080a,.03);
const C=new THREE.PerspectiveCamera(60,W/H,.1,100);S.add(new THREE.AmbientLight(0x2a3a4a,.6));
const dir=new THREE.DirectionalLight(0x6a8aaa,.4);dir.position.set(5,10,7);S.add(dir);

const gr=new THREE.Mesh(new THREE.PlaneGeometry(200,200),new THREE.MeshStandardMaterial({color:0x0a1216,roughness:0.1,metalness:0.9}));gr.rotation.x=-Math.PI/2;S.add(gr);
const rnd=(a,b)=>a+Math.random()*(b-a);
for(let i=0;i<100;i++){
 const x=rnd(-40,40),z=rnd(-40,40);if(Math.hypot(x,z)<8)continue;
 const h=rnd(3,6);
 const t=new THREE.Mesh(new THREE.CylinderGeometry(.15,.3,h,7),new THREE.MeshStandardMaterial({color:0x1a1005,roughness:1}));t.position.set(x,h/2,z);S.add(t);
 const layers = Math.floor(rnd(3,6));
 for(let k=0;k<layers;k++){
  const c=new THREE.Mesh(new THREE.ConeGeometry(2-k*.3, 2.5, 8),new THREE.MeshStandardMaterial({color:new THREE.Color().setHSL(.35,.7,.05+k*.02),roughness:1}));
  c.position.set(x,h+k*.9,z);S.add(c);
 }
}
const pole=new THREE.Mesh(new THREE.CylinderGeometry(.05,.08,3,8),new THREE.MeshStandardMaterial({color:0x111}));pole.position.y=1.5;S.add(pole);
const lamp=new THREE.Mesh(new THREE.CylinderGeometry(.4,.4,.8,16),new THREE.MeshStandardMaterial({color:0xffddaa,emissive:0xff8800,emissiveIntensity:3, metalness:0.5}));lamp.position.y=3;S.add(lamp);
const light=new THREE.PointLight(0xff8800,4,30);light.position.set(0,3,0);S.add(light);

const N=4000,pos=new Float32Array(N*6),sp=new Float32Array(N);
for(let i=0;i<N;i++){const x=rnd(-30,30),y=rnd(0,25),z=rnd(-30,30);pos.set([x,y,z,x,y-.8,z],i*6);sp[i]=rnd(.5,.9)}
const rg=new THREE.BufferGeometry();rg.setAttribute('position',new THREE.BufferAttribute(pos,3));
S.add(new THREE.LineSegments(rg,new THREE.LineBasicMaterial({color:0x6a8aaa,transparent:true,opacity:.2})));

let T=0;
function loop(){
 requestAnimationFrame(loop);T+=.01;
 for(let i=0;i<N;i++){pos[i*6+1]-=sp[i];pos[i*6+4]-=sp[i];if(pos[i*6+4]<0){pos[i*6+1]=25;pos[i*6+4]=24.2}}
 rg.attributes.position.needsUpdate=true;
 light.intensity=4+Math.sin(T*10)*.5;
 const angle=T*.05;
 C.position.set(Math.sin(angle)*15, 5+Math.sin(T*.2)*.5, Math.cos(angle)*15);
 C.lookAt(0,2,0);
 R.render(S,C);
}
loop();
</script></body></html>"""

def embed_bg(html):
    components.html(html, height=0, width=0)

def player(words, mode, states=None, audio=None, feedback="", meta={}):
    data = json.dumps({"words": words, "mode": mode, "states": states, "audio": audio, "feedback": feedback, "meta": meta}, ensure_ascii=False).replace("</", "<\\/")
    h = 600 
    embed = PLAYER_HTML.replace("__DATA__", data)
    components.html(embed, height=h, scrolling=False)

# ───────────────────────────── Styling & State ─────────────────────────────
for k, v in {"name": "", "surah": 2, "ayah": 60, "step": 0, "count": 0, "results": {}, "paid": [], "tries": 0,
             "teacher_gender": "Male", "strictness": "Balanced", "theme": "Starry Night"}.items():
    st.session_state.setdefault(k, v)

bg_color = "#0a0f1c" if st.session_state.theme == "Starry Night" else "#1A1510" if st.session_state.theme == "Brown" else "#000000"

st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Cormorant+Garamond:wght@600&family=Inter:wght@400;600&display=swap');
.stApp{{background:{bg_color};color:#E8D5B5;font-family:Inter,sans-serif}}
[data-testid="stSidebar"]{{background:rgba(10, 8, 6, 0.8); backdrop-filter: blur(20px); border-right:1px solid #D4AF3733}}
h1,h2,h3{{font-family:'Cormorant Garamond',serif!important;color:#D4AF37!important}}
div.stButton>button{{background:linear-gradient(135deg, #D4AF37, #F3E5AB)!important;color:#1A1510!important;border:none!important;border-radius:999px!important;font-weight:700!important;min-height:46px;box-shadow:0 0 20px rgba(212,175,55,.4)}}
div.stButton>button:hover{{box-shadow:0 0 30px rgba(212,175,55,.8)}}
[data-testid="stAudioInput"]{{
    background:linear-gradient(135deg,#D4AF37,#F3E5AB,#D4AF37)!important;
    border-radius:50px!important; padding:10px 20px!important;
    box-shadow:0 0 40px rgba(212,175,55,.6); border: 2px solid #FFF;
}}
[data-testid="stAudioInput"] *{{color:#1A1510!important;font-weight:700!important}}
</style>""", unsafe_allow_html=True)

embed_bg(GARDEN_HTML)

if not st.session_state.name:
    st.markdown("<h1 style='text-align:center;margin-top:20vh;font-size:4rem;text-shadow:0 0 30px rgba(212,175,55,0.5)'>🕌 Al-Mu'allim</h1>", unsafe_allow_html=True)
    with st.form("start", clear_on_submit=True):
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            n = st.text_input("Enter your name to begin", label_visibility="collapsed", placeholder="Your name...")
            if st.form_submit_button("Enter Academy", use_container_width=True) and n.strip():
                st.session_state.name = n.strip(); st.rerun()
    st.stop()

# ───────────────────────────── Sidebar ─────────────────────────────
sb = st.sidebar
sb.markdown(f"<h2 style='text-align:center;color:#D4AF37'>{st.session_state.name}</h2>", unsafe_allow_html=True)
st.session_state.theme = sb.selectbox("Theme", ["Starry Night", "Brown", "Black"], index=["Starry Night", "Brown", "Black"].index(st.session_state.theme))
st.session_state.teacher_gender = sb.selectbox("Teacher Voice", ["Male", "Female"], index=["Male", "Female"].index(st.session_state.teacher_gender))
st.session_state.strictness = sb.select_slider("Strictness", options=["Lenient", "Balanced", "Strict"], value=st.session_state.strictness)

sb.markdown("---")
s_in = sb.number_input("Surah", 1, 114, st.session_state.surah)
a_in = sb.number_input("Ayah", 1, AYAHS[int(s_in)], min(st.session_state.ayah, AYAHS[int(s_in)]))
reciter = sb.selectbox("Reciter Audio", list(RECITERS))
if sb.button("Load Ayah", use_container_width=True):
    st.session_state.update(surah=int(s_in), ayah=int(a_in), step=0, count=0, tries=0, results={})
    st.rerun()

s, a = st.session_state.surah, min(st.session_state.ayah, AYAHS[st.session_state.surah])
key = f"{s}:{a}"
try:
    words = fetch_words(s, a)
    mp3 = fetch_audio(s, a, RECITERS[reciter])
except Exception as e:
    st.error(f"Error loading ayah: {e}"); st.stop()

audio_uri = "data:audio/mpeg;base64," + base64.b64encode(mp3).decode()
xp, streak, _ = get_user(st.session_state.name)
meta_data = {"s": s, "a": a, "xp": xp, "streak": streak}

step = st.session_state.step
titles = ["Step 1 · Listen & Repeat", "Step 2 · Memorise (Blind)", "Step 3 · Talk to Teacher"]
st.markdown(f"<h3 style='text-align:center;color:#D4AF37;margin-top:10px;font-size:1.8rem'>{titles[min(step, 2)]}</h3>", unsafe_allow_html=True)

def listen_step(next_step):
    player(words, "full", None, audio_uri, "", meta_data)
    st.markdown(f"<p style='text-align:center;color:#a8987f'>Repeats: {st.session_state.count} / 5</p>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("I repeated once", use_container_width=True):
        st.session_state.count += 1
        if st.session_state.count >= 5: st.session_state.update(step=next_step, count=0)
        st.rerun()
    if c2.button("Skip", use_container_width=True):
        st.session_state.update(step=next_step, count=0); st.rerun()

def record_step(kind, next_step):
    rk = f"{key}|{kind}"
    res = st.session_state.results.get(rk)
    
    if res is None:
        player(words, kind, None, None, "", meta_data)
        
        st.markdown("<p style='text-align:center; font-size:1.2rem; margin:20px 0; color:#D4AF37; font-weight:600;'>🎙 Tap the golden mic to recite</p>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            clip = st.audio_input("Recite", key=f"mic_{rk}_{st.session_state.tries}", label_visibility="collapsed")
        
        if clip is not None:
            with st.spinner("Analyzing Tajweed rules..."):
                try:
                    # Compress audio using numpy first to avoid timeout, then send
                    states, rules, feedback = analyse_recitation_fast(prep_audio(clip.getvalue()), words, st.session_state.strictness, st.session_state.teacher_gender)
                except Exception as e:
                    st.error(str(e)); return
            
            st.session_state.results[rk] = (states, feedback)
            if states.count("good") / len(states) >= 0.8 and rk not in st.session_state.paid:
                award_xp(st.session_state.name, 10)
                st.session_state.paid.append(rk)
            st.rerun()
        return
    
    states, feedback = res
    player(words, kind, states, None, feedback, meta_data)
    
    c1, c2 = st.columns(2)
    if c1.button("Try again", use_container_width=True):
        st.session_state.results.pop(rk, None)
        st.session_state.tries += 1
        st.rerun()
    if c2.button("Continue", use_container_width=True, type="primary"):
        st.session_state.update(step=next_step, count=0)
        st.rerun()

# Render UI
if step == 0: listen_step(1)
elif step == 1: record_step("blind", 2)
elif step == 2: 
    rk = f"{key}|blind"
    if rk in st.session_state.results:
        states, feedback = st.session_state.results[rk]
        player(words, "blind", states, None, feedback, meta_data)
        if st.button("Start Over (New Ayah)", use_container_width=True):
            st.session_state.update(step=0, count=0, results={})
            st.rerun()
    else:
        st.info("Please complete Step 2 first.")
