import base64, datetime, hashlib, io, json, math, os, pathlib, re, sqlite3, tempfile, wave
import numpy as np
import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Al-Mu'allim", page_icon="🕌", layout="centered")

# Database path fallback for cloud environments
try:
    DB_PATH = pathlib.Path(__file__).with_name("muallim.db")
except NameError:
    DB_PATH = pathlib.Path.cwd() / "muallim.db"

GEMINI = "https://generativelanguage.googleapis.com/v1beta/models"
RECITERS = {"Mishary Alafasy": "Alafasy_128kbps", "Yasser Al-Dosari": "Yasser_Ad-Dussary_128kbps"}
AYAHS = [0, 7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6]

# ───────────────────────────── database (XP and streak) ─────────────────────────────
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

# ───────────────────────────── Qur'an data ─────────────────────────────
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
    if not out:
        raise RuntimeError("No words returned.")
    return out

@st.cache_data(show_spinner=False)
def fetch_audio(s, a, folder):
    r = requests.get(f"https://everyayah.com/data/{folder}/{s:03d}{a:03d}.mp3", timeout=30)
    if r.status_code != 200 or len(r.content) < 2000:
        raise RuntimeError("Audio not available.")
    return r.content

# ───────────────────────────── Gemini analysis ─────────────────────────────
def api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")

@st.cache_data(ttl=3600, show_spinner=False)
def flash_models(k):
    try:
        r = requests.get(GEMINI, headers={"x-goog-api-key": k}, params={"pageSize": 200}, timeout=15).json()
        names = [m["name"].split("/")[-1] for m in r.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        names = [n for n in names if "flash" in n and not any(x in n for x in ("lite", "image", "tts", "live", "audio", "embed", "preview", "exp"))]
        ver = lambda n: float((re.findall(r"\d+(?:\.\d+)?", n) or ["0"])[0])
        return sorted(names, key=ver, reverse=True)[:3]
    except Exception:
        return []

def prep(b):
    """16 kHz mono WAV, quiet recordings lifted to about 90% of full scale."""
    try:
        with wave.open(io.BytesIO(b)) as w:
            ch, sw, fr = w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(w.getnframes())
        if sw != 2 or not raw:
            return b
        x = np.frombuffer(raw, "<i2").astype(np.float32)
        if ch > 1:
            x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
        if fr != 16000 and len(x) > 1:
            x = np.interp(np.linspace(0, len(x) - 1, round(len(x) * 16000 / fr)), np.arange(len(x)), x)
        p = float(np.percentile(np.abs(x), 99.5))
        if p > 30:
            x = x * min(30.0, 0.9 * 32767 / p)
        out = io.BytesIO()
        with wave.open(out, "wb") as w2:
            w2.setnchannels(1); w2.setsampwidth(2); w2.setframerate(16000)
            w2.writeframes(np.clip(x, -32768, 32767).astype("<i2").tobytes())
        return out.getvalue()
    except Exception:
        return b

def analyse(wav, words):
    k = api_key()
    if not k:
        raise RuntimeError("Add GEMINI_API_KEY in Streamlit secrets.")
    prompt = ("You are a Qur'an recitation examiner. A student recited from memory these words, in order: "
              + json.dumps([w["ar"] for w in words], ensure_ascii=False)
              + '. Listen to the audio. For each word index decide status "good" (clearly recited correctly) or "missed" '
                "(skipped, wrong or unclear). Never assume a word was said because you know the verse. "
                'Return JSON only: {"words":[{"i":0,"status":"good"}],"feedback":"max 40 words, warm, English"}')
    body = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(wav).decode()}}]}],
            "generationConfig": {"responseMimeType": "application/json"}}
    err = ""
    for m in (flash_models(k) or ["gemini-2.5-flash"]):
        try:
            r = requests.post(f"{GEMINI}/{m}:generateContent", headers={"x-goog-api-key": k}, json=body, timeout=120)
        except requests.RequestException as e:
            err = str(e); continue
        if r.status_code != 200:
            err = f"{m}: HTTP {r.status_code}"; continue
        try:
            txt = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
            data = json.loads(re.sub(r"^```(?:json)?|```$", "", txt.strip()).strip())
            states = ["missed"] * len(words)
            for w in data.get("words", []):
                if isinstance(w.get("i"), int) and 0 <= w["i"] < len(words):
                    states[w["i"]] = "good" if w.get("status") == "good" else "missed"
            return states, str(data.get("feedback", ""))
        except Exception as e:
            err = f"{m}: {e}"
    raise RuntimeError("Gemini could not analyse the recording. " + err)

# ───────────────────────────── React player (iframe) ─────────────────────────────
PLAYER_HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<style>body{margin:0;background:transparent;color:#E8D5B5;font-family:Inter,system-ui,sans-serif}.ar{font-family:'Amiri Quran',serif}audio{filter:sepia(.6) saturate(1.4)}</style></head>
<body><div id="r"></div><script>
const h=React.createElement,{useState,useEffect,useRef}=React,D=__DATA__;
const MARKS=/[\u064B-\u0652\u0670\u06D6-\u06ED\u0640]/g;
function weight(w){let x=Math.max(1,w.replace(MARKS,'').length);
 if(/\u0651/.test(w))x+=1;            /* shaddah: held longer */
 if(/[\u0653\u0670\u06E4]/.test(w))x+=2; /* madd */
 if(/[\u06D6-\u06DC]/.test(w))x+=4;   /* waqf mark: pause */
 return x}
function App(){
 const [on,setOn]=useState(-1),a=useRef(null),cum=useRef([]);
 useEffect(()=>{const el=a.current;if(!el)return;let raf=0;
  const build=()=>{const d=el.duration||1,ws=D.words.map(w=>weight(w.ar)),T=ws.reduce((s,x)=>s+x,0);let t=d*.04;cum.current=ws.map(x=>t+=d*.9*x/T)};
  const tick=()=>{if(!el.paused&&!el.ended){setOn(cum.current.findIndex(c=>el.currentTime<c));raf=requestAnimationFrame(tick)}};
  const play=()=>{build();raf=requestAnimationFrame(tick)},end=()=>setOn(-1);
  el.addEventListener('play',play);el.addEventListener('ended',end);el.addEventListener('loadedmetadata',build);
  return()=>{cancelAnimationFrame(raf);el.removeEventListener('play',play);el.removeEventListener('ended',end);el.removeEventListener('loadedmetadata',build)}},[]);
 const reveal=D.mode==='full'||!!D.states;
 return h('div',{className:'p-3'},
  D.audio?h('audio',{ref:a,controls:true,src:D.audio,className:'w-full mb-5 rounded-full'}):null,
  h('div',{className:'flex flex-wrap justify-center gap-3',dir:'rtl'},D.words.map((w,i)=>{
   const st=D.states?D.states[i]:null;
   const cls='rounded-2xl border px-4 py-3 text-center transition-all duration-300 min-w-[96px] '+
    (st==='good'?'border-green-400 bg-green-900/30 shadow-[0_0_18px_#4ade8055]':st==='missed'?'border-red-400 bg-red-900/30 shadow-[0_0_18px_#f8717155]':
     on===i?'border-[#D4AF37] bg-[#D4AF37]/20 scale-105 shadow-[0_0_26px_#D4AF37aa]':'border-[#D4AF3733] bg-[#2A221B]');
   return h('div',{key:i,className:cls},
    h('div',{className:'ar text-[2.1rem] leading-[1.5] '+(reveal?'':'text-[#8A7A66] tracking-widest')},reveal?w.ar:'• • •'),
    reveal&&w.tr?h('div',{className:'text-xs italic text-[#D4AF37] mt-1'},w.tr):null,
    D.mode!=='blind'?h('div',{className:'text-sm text-[#a8987f] mt-1'},w.en):null)}))) }
ReactDOM.createRoot(document.getElementById('r')).render(h(App));
</script></body></html>"""

# ───────────────────────────── 3D garden (Three.js) ─────────────────────────────
GARDEN_HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#070b0d;overflow:hidden}canvas{display:block;border-radius:20px}</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script></head><body><script>
const W=innerWidth,H=340,R=new THREE.WebGLRenderer({antialias:true});R.setSize(W,H);R.setPixelRatio(Math.min(devicePixelRatio,2));document.body.appendChild(R.domElement);
const S=new THREE.Scene();S.background=new THREE.Color(0x070b0d);S.fog=new THREE.FogExp2(0x070b0d,.05);
const C=new THREE.PerspectiveCamera(60,W/H,.1,100);S.add(new THREE.AmbientLight(0x3a4a5a,.55));
const gr=new THREE.Mesh(new THREE.PlaneGeometry(90,90),new THREE.MeshStandardMaterial({color:0x10201a,roughness:1}));gr.rotation.x=-Math.PI/2;S.add(gr);
const rnd=(a,b)=>a+Math.random()*(b-a);
for(let i=0;i<80;i++){const x=rnd(-28,28),z=rnd(-28,28);if(Math.hypot(x,z)<4.5)continue;
 const t=new THREE.Mesh(new THREE.CylinderGeometry(.14,.24,3,8),new THREE.MeshStandardMaterial({color:0x3b2a1c,roughness:1}));t.position.set(x,1.5,z);S.add(t);
 for(let k=0;k<3;k++){const c=new THREE.Mesh(new THREE.ConeGeometry(1.5-k*.35,2.2,10),new THREE.MeshStandardMaterial({color:new THREE.Color().setHSL(.36,.5,.1+k*.03),roughness:1}));c.position.set(x,3+k*1.05,z);S.add(c)}}
const pole=new THREE.Mesh(new THREE.CylinderGeometry(.04,.05,2,8),new THREE.MeshStandardMaterial({color:0x2a1d12}));pole.position.y=1;S.add(pole);
const lamp=new THREE.Mesh(new THREE.CylinderGeometry(.26,.26,.55,14),new THREE.MeshStandardMaterial({color:0xffc45e,emissive:0xffa733,emissiveIntensity:1.8}));lamp.position.y=2.25;S.add(lamp);
const cap=new THREE.Mesh(new THREE.ConeGeometry(.34,.25,14),new THREE.MeshStandardMaterial({color:0x2a1d12}));cap.position.y=2.65;S.add(cap);
const light=new THREE.PointLight(0xffb347,2.4,18);light.position.set(0,2.3,0);S.add(light);
const N=2200,pos=new Float32Array(N*6),sp=new Float32Array(N);
for(let i=0;i<N;i++){const x=rnd(-14,14),y=rnd(0,16),z=rnd(-14,14);pos.set([x,y,z,x,y-.55,z],i*6);sp[i]=rnd(.25,.45)}
const rg=new THREE.BufferGeometry();rg.setAttribute('position',new THREE.BufferAttribute(pos,3));
S.add(new THREE.LineSegments(rg,new THREE.LineBasicMaterial({color:0x9fb8c8,transparent:true,opacity:.45})));
let T=0;function loop(){requestAnimationFrame(loop);T+=.016;
 for(let i=0;i<N;i++){pos[i*6+1]-=sp[i];pos[i*6+4]-=sp[i];if(pos[i*6+4]<0){pos[i*6+1]=16;pos[i*6+4]=15.45}}
 rg.attributes.position.needsUpdate=true;
 light.intensity=2.3+Math.sin(T*9)*.15+Math.random()*.08;
 const a=T*.12;C.position.set(Math.sin(a)*10,3+Math.sin(T*.3)*.4,Math.cos(a)*10);C.lookAt(0,1.8,0);R.render(S,C)}
loop();
</script></body></html>"""

def embed(html, height):
    try:
        components.html(html, height=height, scrolling=True)
    except Exception:
        p = pathlib.Path(tempfile.gettempdir()) / (hashlib.sha1(html.encode()).hexdigest()[:16] + ".html")
        p.write_text(html, encoding="utf-8")
        st.warning("This Streamlit version cannot embed the player inline.")

def player(words, mode, states=None, audio=None):
    data = json.dumps({"words": words, "mode": mode, "states": states, "audio": audio}, ensure_ascii=False).replace("</", "<\\/")
    rows = math.ceil(len(words) / 4)
    embed(PLAYER_HTML.replace("__DATA__", data), 120 + 150 * rows + (70 if audio else 0))

# ───────────────────────────── styling ─────────────────────────────
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Cormorant+Garamond:wght@600&family=Inter:wght@400;600&display=swap');
.stApp{background:#1A1510;color:#E8D5B5;font-family:Inter,system-ui,sans-serif}
[data-testid="stSidebar"]{background:#110D09}
h1,h2,h3{font-family:'Cormorant Garamond',serif!important;color:#D4AF37!important}
.stApp p,.stApp label,.stApp li{color:#E8D5B5}
div.stButton>button{background:#D4AF37!important;color:#1A1510!important;border:none!important;border-radius:999px!important;font-weight:600!important;min-height:46px}
[data-testid="stAudioInput"]{background:linear-gradient(135deg,#D4AF37,#F3E5AB,#D4AF37)!important;border-radius:999px!important;padding:6px 14px!important;box-shadow:0 0 30px rgba(212,175,55,.5);animation:glow 2s infinite}
[data-testid="stAudioInput"] *{color:#1A1510!important;font-weight:700!important}
@keyframes glow{50%{box-shadow:0 0 44px rgba(212,175,55,.85)}}
.chip{display:inline-block;padding:6px 16px;margin:4px;border:1px solid rgba(212,175,55,.35);border-radius:999px;background:#2A221B;color:#E8D5B5}
.step{text-align:center;color:#D4AF37;font-size:1.3rem;margin:6px 0 12px}
</style>""", unsafe_allow_html=True)

# ───────────────────────────── state ─────────────────────────────
for k, v in {"name": "", "surah": 2, "ayah": 60, "step": 0, "count": 0, "results": {}, "paid": [], "tries": 0}.items():
    st.session_state.setdefault(k, v)

if not st.session_state.name:
    st.markdown("<h1 style='text-align:center;margin-top:14vh'>🕌 Al-Mu'allim</h1>", unsafe_allow_html=True)
    with st.form("start"):
        n = st.text_input("What is your name?", placeholder="e.g. Abia")
        if st.form_submit_button("Begin", use_container_width=True) and n.strip():
            st.session_state.name = n.strip()
            st.rerun()
    st.stop()

sb = st.sidebar
sb.markdown(f"### {st.session_state.name}")
s_in = sb.number_input("Surah", 1, 114, st.session_state.surah)
a_in = sb.number_input("Ayah", 1, AYAHS[int(s_in)], min(st.session_state.ayah, AYAHS[int(s_in)]))
reciter = sb.selectbox("Reciter", list(RECITERS))
if sb.button("Go to this ayah", use_container_width=True):
    st.session_state.update(surah=int(s_in), ayah=int(a_in), step=0, count=0, tries=0)
    st.rerun()

s, a = st.session_state.surah, min(st.session_state.ayah, AYAHS[st.session_state.surah])
key = f"{s}:{a}"
try:
    words = fetch_words(s, a)
    mp3 = fetch_audio(s, a, RECITERS[reciter])
except Exception as e:
    st.error(f"Could not load this ayah ({e}). Check the connection and reload.")
    st.stop()
audio_uri = "data:audio/mpeg;base64," + base64.b64encode(mp3).decode()

xp, streak, _ = get_user(st.session_state.name)
st.markdown(f"<h2 style='text-align:center;margin-bottom:0'>Surah {s} · Ayah {a}</h2>"
            f"<div style='text-align:center'><span class='chip'>⭐ {xp} XP</span><span class='chip'>🔥 {streak} day streak</span>"
            f"<span class='chip'>🎙 {reciter}</span></div>", unsafe_allow_html=True)

step = st.session_state.step
titles = ["Step 1 · Listen 5 times", "Step 2 · Recite with English hints", "Step 3 · Repeat 5 times", "Step 4 · Blind recitation"]
st.markdown(f"<div class='step'>{titles[min(step, 3)] if step < 4 else 'Ayah memorised'}</div>", unsafe_allow_html=True)

def listen_step(next_step):
    player(words, "full", None, audio_uri)
    st.markdown(f"<p style='text-align:center'>Listens: {st.session_state.count} / 5</p>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("I listened once", use_container_width=True):
        st.session_state.count += 1
        if st.session_state.count >= 5:
            st.session_state.update(step=next_step, count=0)
        st.rerun()
    if c2.button("Skip", use_container_width=True):
        st.session_state.update(step=next_step, count=0)
        st.rerun()

def recite_step(kind, next_step):
    rk = f"{key}|{kind}"
    res = st.session_state.results.get(rk)
    if res is None:
        player(words, kind)
        
        # This adds the text right above the mic as seen in your screenshot
        st.markdown("<p style='text-align:center; font-size:1.1rem; margin-top:10px;'>🎙 Recite the verse</p>", unsafe_allow_html=True)
        
        clip = st.audio_input("Recite", key=f"mic_{rk}_{st.session_state.tries}", label_visibility="collapsed")
        if clip is not None:
            with st.spinner("Listening to your recitation…"):
                try:
                    res = analyse(prep(clip.getvalue()), words)
                except Exception as e:
                    st.error(str(e))
                    return
            st.session_state.results[rk] = res
            if res[0].count("good") / len(res[0]) >= 0.8 and rk not in st.session_state.paid:
                award_xp(st.session_state.name, 10)
                st.session_state.paid.append(rk)
            st.rerun()
        return
    states, feedback = res
    player(words, kind, states)
    good = states.count("good")
    st.markdown(f"<h2 style='text-align:center'>{round(100 * good / len(states))}%</h2><p style='text-align:center'>{good} of {len(states)} words correct. {feedback}</p>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("Try again", use_container_width=True):
        st.session_state.results.pop(rk, None)
        st.session_state.tries += 1
        st.rerun()
    if c2.button("Next", use_container_width=True, type="primary"):
        st.session_state.update(step=next_step, count=0)
        st.rerun()

if step == 0:
    listen_step(1)
elif step == 1:
    recite_step("hints", 2)
elif step == 2:
    listen_step(3)
elif step == 3:
    recite_step("blind", 4)
else:
    st.success("Beautiful. This ayah is done.")
    if st.button("Restart this ayah", use_container_width=True):
        st.session_state.update(step=0, count=0)
        for kk in [x for x in st.session_state.results if x.startswith(key + "|")]:
            st.session_state.results.pop(kk)
        st.rerun()

st.markdown("<h3 style='text-align:center;margin-top:28px'>Your garden</h3>", unsafe_allow_html=True)
embed(GARDEN_HTML, 350)
