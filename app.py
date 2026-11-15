import base64, datetime, hashlib, io, json, math, os, pathlib, re, sqlite3, tempfile, wave
import numpy as np
import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Al-Mu'allim", page_icon="🕌", layout="centered", initial_sidebar_state="expanded")

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

# ───────────────────────────── AI & Audio ─────────────────────────────
def api_key():
    try: return st.secrets["GEMINI_API_KEY"]
    except: return os.environ.get("GEMINI_API_KEY", "")

@st.cache_data(ttl=3600, show_spinner=False)
def flash_models(k):
    try:
        r = requests.get(GEMINI, headers={"x-goog-api-key": k}, params={"pageSize": 200}, timeout=15).json()
        names = [m["name"].split("/")[-1] for m in r.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        names = [n for n in names if "flash" in n and not any(x in n for x in ("lite", "image", "tts", "live", "audio", "embed", "preview", "exp"))]
        ver = lambda n: float((re.findall(r"\d+(?:\.\d+)?", n) or ["0"])[0])
        return sorted(names, key=ver, reverse=True)[:3]
    except: return []

def prep(b):
    try:
        with wave.open(io.BytesIO(b)) as w:
            ch, sw, fr = w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(w.getnframes())
        if sw != 2 or not raw: return b
        x = np.frombuffer(raw, "<i2").astype(np.float32)
        if ch > 1: x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
        if fr != 16000 and len(x) > 1: x = np.interp(np.linspace(0, len(x) - 1, round(len(x) * 16000 / fr)), np.arange(len(x)), x)
        p = float(np.percentile(np.abs(x), 99.5))
        if p > 30: x = x * min(30.0, 0.9 * 32767 / p)
        out = io.BytesIO()
        with wave.open(out, "wb") as w2:
            w2.setnchannels(1); w2.setsampwidth(2); w2.setframerate(16000)
            w2.writeframes(np.clip(x, -32768, 32767).astype("<i2").tobytes())
        return out.getvalue()
    except: return b

def analyse_recitation(wav, words, strictness, teacher_gender):
    k = api_key()
    if not k: raise RuntimeError("Add GEMINI_API_KEY in Streamlit secrets.")
    
    teacher = "a strict, expert male Sheikh" if teacher_gender == "Male" else "a gentle, expert female Sheikh"
    strict_prompt = "Be very critical of Tajweed (Madd, Ghunnah, Qalqalah)." if strictness == "Strict" else "Be encouraging and only point out major errors."
    
    prompt = (f"You are {teacher}. A student recited from memory these words: "
              + json.dumps([w["ar"] for w in words], ensure_ascii=False)
              + f'. {strict_prompt} Listen to the audio. Evaluate the 16 Tajweed rules. '
              'For each word, decide "good" or "missed". Also provide a general tajweed_feedback (max 40 words). '
              'Return JSON only: {"words":[{"i":0,"status":"good"}],"feedback":"..."}')
              
    body = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(wav).decode()}}]}],
            "generationConfig": {"responseMimeType": "application/json"}}
            
    for m in (flash_models(k) or ["gemini-2.5-flash"]):
        try:
            r = requests.post(f"{GEMINI}/{m}:generateContent", headers={"x-goog-api-key": k}, json=body, timeout=120)
            if r.status_code != 200: continue
            txt = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
            data = json.loads(re.sub(r"^```(?:json)?|```$", "", txt.strip()).strip())
            states = ["missed"] * len(words)
            for w in data.get("words", []):
                if isinstance(w.get("i"), int) and 0 <= w["i"] < len(words):
                    states[w["i"]] = "good" if w.get("status") == "good" else "missed"
            return states, str(data.get("feedback", ""))
        except: pass
    raise RuntimeError("Gemini could not analyse the recording.")

# ───────────────────────────── React Player ─────────────────────────────
PLAYER_HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<style>
body{margin:0;background:transparent;color:#E8D5B5;font-family:Inter,sans-serif;overflow:hidden}
.ar{font-family:'Amiri Quran',serif}
audio{filter:sepia(.6) saturate(1.4); width:100%; border-radius:20px; outline:none}
</style></head>
<body><div id="r"></div><script>
const h=React.createElement,{useState,useEffect,useRef}=React,D=__DATA__;
const MARKS=/[\u064B-\u0652\u0670\u06D6-\u06ED\u0640]/g;

function weight(w){
 let x=Math.max(1,w.replace(MARKS,'').length);
 if(/\u0651/.test(w))x+=1;
 if(/[\u0653\u0670\u06E4]/.test(w))x+=2;
 if(/[\u06D6-\u06DC]/.test(w))x+=4;
 return x
}

function App(){
 const [on,setOn]=useState(-1), a=useRef(null), cum=useRef([]);
 const [src, setSrc] = useState(D.audio);

 useEffect(()=>{
  const el=a.current; if(!el)return; let raf=0;
  const build=()=>{
   const d=el.duration||1, ws=D.words.map(w=>weight(w.ar)), T=ws.reduce((s,x)=>s+x,0);
   let t=d*.02; cum.current=ws.map(x=>t+=d*.96*x/T)
  };
  const tick=()=>{ if(!el.paused&&!el.ended){ setOn(cum.current.findIndex(c=>el.currentTime<c)); raf=requestAnimationFrame(tick) } };
  const play=()=>{ build(); raf=requestAnimationFrame(tick) }, end=()=>setOn(-1);
  el.addEventListener('play',play); el.addEventListener('ended',end); el.addEventListener('loadedmetadata',build);
  return()=>{ cancelAnimationFrame(raf); el.removeEventListener('play',play); el.removeEventListener('ended',end); el.removeEventListener('loadedmetadata',build) }
 },[src]);

 const reveal = D.mode==='full' || !!D.states;

 return h('div',{className:'flex flex-col gap-4 p-2'},
  // Top Controls
  h('div',{className:'flex gap-2 justify-center mb-2'},
    D.userAudio ? h('button',{onClick:()=>setSrc(D.audio), className:`px-4 py-2 rounded-full text-sm font-bold ${src===D.audio?'bg-[#D4AF37] text-black':'bg-[#2A221B] text-[#D4AF37]'}`}, '👨‍🏫 Teacher') : null,
    D.userAudio ? h('button',{onClick:()=>setSrc(D.userAudio), className:`px-4 py-2 rounded-full text-sm font-bold ${src===D.userAudio?'bg-[#D4AF37] text-black':'bg-[#2A221B] text-[#D4AF37]'}`}, '🎙 My Voice') : null
  ),
  h('audio',{ref:a,controls:true,src:src,className:'mb-2'}),
  
  // Word Cards
  h('div',{className:'flex flex-wrap justify-center gap-2',dir:'rtl'},D.words.map((w,i)=>{
   const st=D.states?D.states[i]:null;
   const base = 'rounded-xl border px-3 py-2 text-center transition-all duration-200 min-w-[80px] ';
   let cls = base;
   if (st==='good') cls += 'border-green-400 bg-green-900/40 shadow-[0_0_15px_#4ade8055]';
   else if (st==='missed') cls += 'border-red-400 bg-red-900/40 shadow-[0_0_15px_#f8717155]';
   else if (on===i) cls += 'border-[#D4AF37] bg-[#D4AF37]/30 scale-110 shadow-[0_0_20px_#D4AF37]';
   else cls += 'border-[#D4AF3733] bg-[#2A221B]';

   return h('div',{key:i,className:cls},
    h('div',{className:'ar text-[1.8rem] leading-tight '+(reveal?'':'text-[#8A7A66] tracking-widest')},reveal?w.ar:'• • •'),
    reveal&&w.tr?h('div',{className:'text-[10px] italic text-[#D4AF37]'},w.tr):null,
    D.mode!=='blind'?h('div',{className:'text-xs text-[#a8987f] mt-1'},w.en):null
   )
  }))
 )
}
ReactDOM.createRoot(document.getElementById('r')).render(h(App));
</script></body></html>"""

# ───────────────────────────── 3D Garden ─────────────────────────────
GARDEN_HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#070b0d;overflow:hidden}canvas{display:block;border-radius:16px;width:100%!important;height:100%!important}</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script></head><body><script>
const W=innerWidth,H=innerHeight,R=new THREE.WebGLRenderer({antialias:true});R.setSize(W,H);R.setPixelRatio(Math.min(devicePixelRatio,2));document.body.appendChild(R.domElement);
const S=new THREE.Scene();S.background=new THREE.Color(0x050a0d);S.fog=new THREE.FogExp2(0x050a0d,.04);
const C=new THREE.PerspectiveCamera(60,W/H,.1,100);S.add(new THREE.AmbientLight(0x2a3a4a,.6));
const dir=new THREE.DirectionalLight(0x6a8aaa,.4);dir.position.set(5,10,7);S.add(dir);

// Ground
const gr=new THREE.Mesh(new THREE.PlaneGeometry(100,100),new THREE.MeshStandardMaterial({color:0x0d1812,roughness:1}));gr.rotation.x=-Math.PI/2;S.add(gr);

const rnd=(a,b)=>a+Math.random()*(b-a);
// Trees
for(let i=0;i<150;i++){
 const x=rnd(-35,35),z=rnd(-35,35);if(Math.hypot(x,z)<5)continue;
 const h=rnd(2,4);
 const t=new THREE.Mesh(new THREE.CylinderGeometry(.1,.2,h,7),new THREE.MeshStandardMaterial({color:0x2b1d14,roughness:1}));t.position.set(x,h/2,z);S.add(t);
 const layers = Math.floor(rnd(2,5));
 for(let k=0;k<layers;k++){
  const c=new THREE.Mesh(new THREE.ConeGeometry(1.5-k*.25, 1.8, 8),new THREE.MeshStandardMaterial({color:new THREE.Color().setHSL(.35,.6,.05+k*.03),roughness:1}));
  c.position.set(x,h+k*.7,z);S.add(c);
 }
}

// Lantern
const pole=new THREE.Mesh(new THREE.CylinderGeometry(.04,.06,2.5,8),new THREE.MeshStandardMaterial({color:0x111}));pole.position.y=1.25;S.add(pole);
const lamp=new THREE.Mesh(new THREE.CylinderGeometry(.3,.3,.6,16),new THREE.MeshStandardMaterial({color:0xffddaa,emissive:0xffaa33,emissiveIntensity:2}));lamp.position.y=2.65;S.add(lamp);
const cap=new THREE.Mesh(new THREE.ConeGeometry(.4,.3,16),new THREE.MeshStandardMaterial({color:0x111}));cap.position.y=3.1;S.add(cap);
const light=new THREE.PointLight(0xffa533,3.5,25);light.position.set(0,2.65,0);S.add(light);

// Fireflies
const fN=50, fPos=new Float32Array(fN*3);
for(let i=0;i<fN;i++){fPos[i*3]=rnd(-15,15);fPos[i*3+1]=rnd(0.5,3);fPos[i*3+2]=rnd(-15,15)}
const fGeo=new THREE.BufferGeometry();fGeo.setAttribute('position',new THREE.BufferAttribute(fPos,3));
const fMat=new THREE.PointsMaterial({color:0xffcc55,size:.15,transparent:true,opacity:.8,blending:THREE.AdditiveBlending});
S.add(new THREE.Points(fGeo,fMat));

// Rain
const N=3000,pos=new Float32Array(N*6),sp=new Float32Array(N);
for(let i=0;i<N;i++){const x=rnd(-20,20),y=rnd(0,20),z=rnd(-20,20);pos.set([x,y,z,x,y-.7,z],i*6);sp[i]=rnd(.4,.7)}
const rg=new THREE.BufferGeometry();rg.setAttribute('position',new THREE.BufferAttribute(pos,3));
S.add(new THREE.LineSegments(rg,new THREE.LineBasicMaterial({color:0x5a8aaa,transparent:true,opacity:.25})));

let T=0;
function loop(){
 requestAnimationFrame(loop);T+=.01;
 
 // Rain
 for(let i=0;i<N;i++){pos[i*6+1]-=sp[i];pos[i*6+4]-=sp[i];if(pos[i*6+4]<0){pos[i*6+1]=20;pos[i*6+4]=19.3}}
 rg.attributes.position.needsUpdate=true;
 
 // Fireflies
 const fp=fGeo.attributes.position.array;
 for(let i=0;i<fN;i++){
   fp[i*3] += Math.sin(T*2+i)*0.01; fp[i*3+1] += Math.cos(T*1.5+i)*0.01; fp[i*3+2] += Math.sin(T*1.8+i)*0.01;
 }
 fGeo.attributes.position.needsUpdate=true;
 
 // Flicker
 light.intensity=3.5+Math.sin(T*12)*.3+Math.random()*.1;
 
 // Camera
 const angle=T*.15;
 C.position.set(Math.sin(angle)*12, 4+Math.sin(T*.4)*.5, Math.cos(angle)*12);
 C.lookAt(0,2,0);
 R.render(S,C);
}
loop();
</script></body></html>"""

def embed(html, height):
    components.html(html, height=height, scrolling=False)

def player(words, mode, states=None, audio=None, user_audio=None):
    data = json.dumps({"words": words, "mode": mode, "states": states, "audio": audio, "userAudio": user_audio}, ensure_ascii=False).replace("</", "<\\/")
    rows = math.ceil(len(words) / 5)
    h = 140 + 100 * rows
    embed(PLAYER_HTML.replace("__DATA__", data), h)

# ───────────────────────────── Styling ─────────────────────────────
for k, v in {"name": "", "surah": 2, "ayah": 60, "step": 0, "count": 0, "results": {}, "paid": [], "tries": 0,
             "teacher_gender": "Male", "strictness": "Balanced", "theme": "Starry Night"}.items():
    st.session_state.setdefault(k, v)

bg_color = "#0a0f1c" if st.session_state.theme == "Starry Night" else "#1A1510" if st.session_state.theme == "Brown" else "#000000"
gold = "#D4AF37"

st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Cormorant+Garamond:wght@600&family=Inter:wght@400;600&display=swap');
.stApp{{background:{bg_color};color:#E8D5B5;font-family:Inter,sans-serif}}
[data-testid="stSidebar"]{{background:{bg_color};border-right:1px solid #D4AF3733}}
h1,h2,h3{{font-family:'Cormorant Garamond',serif!important;color:{gold}!important}}
div.stButton>button{{background:{gold}!important;color:{bg_color}!important;border:none!important;border-radius:999px!important;font-weight:600!important;min-height:46px}}
[data-testid="stAudioInput"]{{background:linear-gradient(135deg,{gold},#F3E5AB,{gold})!important;border-radius:999px!important;padding:6px 14px!important;box-shadow:0 0 30px rgba(212,175,55,.5)}}
[data-testid="stAudioInput"] *{{color:{bg_color}!important;font-weight:700!important}}
.chip{{display:inline-block;padding:6px 16px;margin:4px;border:1px solid {gold}55;border-radius:999px;background:{bg_color};color:#E8D5B5}}
.step{{text-align:center;color:{gold};font-size:1.4rem;margin:10px 0}}
</style>""", unsafe_allow_html=True)

if not st.session_state.name:
    st.markdown("<h1 style='text-align:center;margin-top:14vh'>🕌 Al-Mu'allim</h1>", unsafe_allow_html=True)
    with st.form("start"):
        n = st.text_input("What is your name?")
        if st.form_submit_button("Begin", use_container_width=True) and n.strip():
            st.session_state.name = n.strip(); st.rerun()
    st.stop()

# ───────────────────────────── Sidebar Settings ─────────────────────────────
sb = st.sidebar
sb.markdown(f"<h2 style='text-align:center'>{st.session_state.name}</h2>", unsafe_allow_html=True)
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

st.markdown(f"<h2 style='text-align:center;margin-bottom:0'>Surah {s} · Ayah {a}</h2>"
            f"<div style='text-align:center'><span class='chip'>⭐ {xp} XP</span><span class='chip'>🔥 {streak} day streak</span></div>", unsafe_allow_html=True)

step = st.session_state.step
titles = ["Step 1 · Listen & Repeat", "Step 2 · Memorise (Blind)", "Step 3 · Talk to Teacher"]
st.markdown(f"<div class='step'>{titles[min(step, 2)]}</div>", unsafe_allow_html=True)

def listen_step(next_step):
    player(words, "full", None, audio_uri)
    st.markdown(f"<p style='text-align:center'>Repeats: {st.session_state.count} / 5</p>", unsafe_allow_html=True)
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
    user_b64 = None
    
    if res is None:
        player(words, kind)
        st.markdown("<p style='text-align:center; font-size:1.1rem; margin-top:10px;'>🎙 Recite now</p>", unsafe_allow_html=True)
        clip = st.audio_input("Recite", key=f"mic_{rk}_{st.session_state.tries}", label_visibility="collapsed")
        
        if clip is not None:
            user_b64 = "data:audio/wav;base64," + base64.b64encode(clip.getvalue()).decode()
            with st.spinner("Teacher is listening and analyzing Tajweed..."):
                try:
                    res = analyse_recitation(prep(clip.getvalue()), words, st.session_state.strictness, st.session_state.teacher_gender)
                except Exception as e:
                    st.error(str(e)); return
            
            st.session_state.results[rk] = (res[0], res[1], user_b64)
            if res[0].count("good") / len(res[0]) >= 0.8 and rk not in st.session_state.paid:
                award_xp(st.session_state.name, 10)
                st.session_state.paid.append(rk)
            st.rerun()
        return
    
    states, feedback, user_b64 = res
    player(words, kind, states, None, user_b64)
    
    good = states.count("good")
    st.markdown(f"<h2 style='text-align:center;color:#4ade80'>{round(100 * good / len(states))}%</h2>", unsafe_allow_html=True)
    st.info(f"**Teacher Feedback:** {feedback}")
    
    c1, c2 = st.columns(2)
    if c1.button("Try again", use_container_width=True):
        st.session_state.results.pop(rk, None)
        st.session_state.tries += 1
        st.rerun()
    if c2.button("Continue", use_container_width=True, type="primary"):
        st.session_state.update(step=next_step, count=0)
        st.rerun()

if step == 0: listen_step(1)
elif step == 1: record_step("blind", 2)
elif step == 2: 
    # Teacher Chat Mode
    rk = f"{key}|blind"
    if rk in st.session_state.results:
        states, feedback, user_b64 = st.session_state.results[rk]
        player(words, "blind", states, None, user_b64)
        st.success(f"**Teacher's Tajweed Notes:** {feedback}")
    else:
        st.info("Please complete Step 2 first.")
    
    if st.button("Start Over (New Ayah)", use_container_width=True):
        st.session_state.update(step=0, count=0, results={})
        st.rerun()

st.markdown("<h3 style='text-align:center;margin-top:30px'>Your Garden</h3>", unsafe_allow_html=True)
embed(GARDEN_HTML, 300)
