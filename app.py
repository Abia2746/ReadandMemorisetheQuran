# app.py — Al-Mu'allim · The Absolute Premium Build (Fixed Audio & UI)
import base64, json, re, time
import html as _h
import datetime, math, pathlib
import io, wave, os, sqlite3
import numpy as np
import requests
import streamlit as st
import streamlit.components.v1 as components

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG & DATABASE
# ──────────────────────────────────────────────────────────────────────────────
API = "https://generativelanguage.googleapis.com/v1beta/models"
ROOT = pathlib.Path(__file__).parent
DB_PATH = "al_muallim_master.db"

st.set_page_config(layout="wide", page_title="Al-Mu'allim Academy", page_icon="🕌")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (name TEXT PRIMARY KEY, xp INTEGER, streak INTEGER, last_login TEXT)''')
        conn.commit()

def get_user(name):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT xp, streak, last_login FROM users WHERE name=?", (name,))
        row = c.fetchone()
        if not row:
            today = datetime.date.today().isoformat()
            c.execute("INSERT INTO users (name, xp, streak, last_login) VALUES (?, 0, 1, ?)", (name, today))
            conn.commit()
            return {"xp": 0, "streak": 1}
        
        xp, streak, last_login = row
        today = datetime.date.today()
        last_date = datetime.date.fromisoformat(last_login)
        
        if last_date == today - datetime.timedelta(days=1):
            streak += 1
            c.execute("UPDATE users SET streak=?, last_login=? WHERE name=?", (streak, today.isoformat(), name))
        elif last_date < today - datetime.timedelta(days=1):
            streak = 1
            c.execute("UPDATE users SET streak=?, last_login=? WHERE name=?", (streak, today.isoformat(), name))
        conn.commit()
        return {"xp": xp, "streak": streak}

def add_xp(name, amount):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET xp = xp + ? WHERE name=?", (amount, name))
        conn.commit()

init_db()

_DEFAULTS = {
    "user_name": "", "app_phase": "onboarding",
    "current_surah": 2, "current_ayah": 60,
    "chat": [], "tafsir_text": {}, "last_analysis": {},
    "cfg_teacher": "Female", "cfg_gain": 12, "cfg_reciter": "Mishary Alafasy",
    "mem_step": 0, "mem_listens": 0, "show_reward": False
}
for k, v in _DEFAULTS.items():
    st.session_state.setdefault(k, v)

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS & API
# ──────────────────────────────────────────────────────────────────────────────
def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
        if value: return str(value)
    except Exception: pass
    return os.getenv(name, default)

def audio_part(b, mime):
    return {"inline_data": {"mime_type": mime, "data": base64.b64encode(b).decode()}}

def call_gemini(parts, expect_json=False, pro=False):
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key: raise RuntimeError("Gemini API key missing.")
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    payload = {"contents": [{"parts": parts}]}
    if expect_json: payload["generationConfig"] = {"responseMimeType": "application/json"}
    
    model = "gemini-1.5-pro" if pro else "gemini-1.5-flash"
    try:
        res = requests.post(f"{API}/{model}:generateContent", json=payload, headers=headers, timeout=90)
        if res.status_code == 200:
            body = res.json()
            cands = body.get("candidates") or []
            if cands:
                rp = cands[0].get("content", {}).get("parts", [])
                answer = "".join(p.get("text", "") for p in rp).strip()
                if expect_json:
                    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", answer, flags=re.IGNORECASE).strip()
                    return json.loads(cleaned)
                return answer
    except Exception as e:
        raise RuntimeError(f"AI Error: {str(e)}")

def analyze_recitation(audio_bytes, expected_words, ref_audio_bytes):
    wav = audio_bytes
    prompt = f"""You are an expert Tajweed teacher.
Expected Arabic words: {json.dumps(expected_words)}
The student recited the audio attached.
Compare word by word: harakat, madd, ghunnah, qalqalah.
Return JSON ONLY: 
{{"overall_score": int, "words": [{{"word": "arabic_word", "status": "good" | "missed"}}], "summary": "Short feedback"}}"""
    
    try:
        res = call_gemini([{"text": prompt}, {"text": "Ref:"}, audio_part(ref_audio_bytes, "audio/mpeg"), {"text": "Student:"}, audio_part(wav, "audio/webm")], expect_json=True, pro=True)
        return res
    except Exception as e:
        return {"error": str(e)}

@st.cache_data(show_spinner=False)
def fetch_verse(s, a):
    try: return requests.get(f"https://api.alquran.cloud/v1/ayah/{s}:{a}/quran-uthmani", timeout=15).json()["data"]["text"]
    except: return ""

@st.cache_data(show_spinner=False)
def fetch_words(s, a):
    try:
        r = requests.get(f"https://api.quran.com/api/v4/verses/by_key/{s}:{a}", params={"words": "true", "word_fields": "text_uthmani", "language": "en"}, timeout=20).json()
        return [{"ar": w["text_uthmani"], "en": (w.get("translation") or {}).get("text", ""), "tr": (w.get("transliteration") or {}).get("text") or ""} for w in r["verse"]["words"] if w.get("char_type_name") == "word"]
    except: return []

@st.cache_data(show_spinner=False)
def fetch_reciter(s, a, choice):
    url = f"https://everyayah.com/data/{'Yasser_Ad-Dussary' if choice == 'Yasser Al-Dosari' else 'Alafasy'}_128kbps/{s:03d}{a:03d}.mp3"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200: return url, r.content
    except: pass
    return None, None

# ──────────────────────────────────────────────────────────────────────────────
# PREMIUM REACT COMPONENTS
# ──────────────────────────────────────────────────────────────────────────────
def apply_theme():
    st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Inter:wght@400;600&display=swap');
html,body,.stApp { background-color: #1A1510 !important; color: #E8D5B5 !important; font-family: Inter, sans-serif; }
h1,h2,h3,h4 { color: #D4AF37 !important; font-family: serif !important; }
[data-testid="stSidebar"] { background-color: #110D09 !important; border-right: 1px solid #D4AF37; }
.stButton>button { background: #D4AF37 !important; color: #000 !important; border-radius: 999px !important; font-weight: bold !important; }
/* Style the native Streamlit mic to match the gold theme */
div[data-testid="stAudioInput"] { background: linear-gradient(135deg, #D4AF37, #F3E5AB) !important; border-radius: 999px !important; padding: 10px !important; box-shadow: 0 0 20px rgba(212,175,55,0.4) !important; }
</style>""", unsafe_allow_html=True)

def render_premium_player(words, audio_b64, teacher_img, analysis):
    html = f"""
    <!DOCTYPE html><html><head><style>
    body {{ background: transparent; color: #E8D5B5; margin: 0; font-family: 'Inter', sans-serif; }}
    .header {{ text-align: center; margin-bottom: 10px; }}
    .portrait {{ width: 100px; height: 120px; border-radius: 20px; border: 2px solid #D4AF37; object-fit: cover; margin: 0 auto; display: block; box-shadow: 0 0 30px rgba(212,175,55,0.2); }}
    .title {{ color: #D4AF37; font-family: serif; font-size: 1.5rem; margin: 10px 0; }}
    
    /* FIXED AUDIO PLAYER AT TOP */
    audio {{ width: 100%; max-width: 500px; margin: 10px auto; border-radius: 999px; display: block; outline: none; }}
    
    #w {{ display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; direction: rtl; padding: 10px; }}
    .card {{ display: flex; flex-direction: column; align-items: center; padding: 10px 15px; border-radius: 16px; background: #2A221B; border: 2px solid rgba(212,175,55,.15); transition: all .3s; min-width: 100px; text-align: center; }}
    .ar {{ font-family: 'Amiri Quran', serif; font-size: 2rem; color: #E8D5B5; line-height: 1.4; }}
    .tr {{ font-size: 0.8rem; color: #D4AF37; font-style: italic; margin-top: 4px; }}
    .en {{ font-size: 0.85rem; color: #8A7A66; margin-top: 2px; }}
    
    /* Highlighting */
    .card.on {{ box-shadow: 0 0 20px rgba(212,175,55,.4); border-color: #D4AF37; transform: translateY(-3px) scale(1.05); background: rgba(212,175,55,.15); }}
    
    /* Analysis Colors */
    .card.correct {{ border-color: #4ADE80; background: rgba(74,222,128,.1); }}
    .card.missed {{ border-color: #F87171; background: rgba(248,113,113,.1); }}
    </style></head><body>
    
    <div class="header">
        <img src="{teacher_img}" class="portrait" alt="Teacher">
        <div class="title">Surah {st.session_state.current_surah} · Ayah {st.session_state.current_ayah}</div>
    </div>

    <audio id="a" controls src="data:audio/mpeg;base64,{audio_b64}"></audio>
    <div id="w"></div>
    
    <script>
        const W = {json.dumps(words)};
        const analysis = {json.dumps(analysis)};
        const box = document.getElementById('w'); const a = document.getElementById('a');
        
        const els = W.map((w, idx) => {{
            const d = document.createElement('div');
            let border = '';
            if (analysis && analysis.words) {{
                const res = analysis.words.find(r => r.word === w.ar || r.word.includes(w.ar) || w.ar.includes(r.word));
                if (res) {{
                    if (res.status === 'good') border = 'correct';
                    if (res.status === 'missed') border = 'missed';
                }}
            }}
            d.className = 'card ' + border;
            d.innerHTML = `<div class="ar">${{w.ar}}</div><div class="tr">${{w.tr}}</div><div class="en">${{w.en}}</div>`;
            box.appendChild(d); return d;
        }});
        
        let cum = [];
        function build() {{
            const d = a.duration || 1; let total = 0;
            const weights = W.map(w => {{
                let weight = Math.max(1, (w.ar||'').replace(/[\\u064B-\\u0652\\u0670\\u06D6-\\u06ED\\u0640]/g,'').length);
                if (/[آإأٱ]/.test(w.ar)) weight += 3; // Madd
                if (/[\\u0651]/.test(w.ar)) weight += 2; // Shaddah
                if (/[\\u06D6-\\u06ED]/.test(w.ar)) weight += 5; // Waqf
                total += weight; return weight;
            }});
            let cur = d * 0.05; const sp = d * 0.90;
            cum = weights.map(w => {{ cur += (w/total)*sp; return cur; }});
        }}
        a.onloadedmetadata = build;
        function update() {{
            if (a.paused || a.ended) return;
            const t = a.currentTime; let idx = cum.findIndex(c => t < c);
            if (a.ended) idx = -1;
            els.forEach((e, k) => e.classList.toggle('on', k === idx));
            requestAnimationFrame(update);
        }}
        a.addEventListener('play', () => requestAnimationFrame(update));
    </script></body></html>"""
    components.html(html, height=600, scrolling=True)

def render_3d_garden():
    html = """
    <!DOCTYPE html><html><head><style>body{margin:0;overflow:hidden;background:#0a0805;border-radius:20px;}</style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script></head><body>
    <script>
        const scene = new THREE.Scene(); scene.fog = new THREE.FogExp2(0x0a0805, 0.06);
        const camera = new THREE.PerspectiveCamera(60, window.innerWidth/window.innerHeight, 0.1, 1000); camera.position.set(0, 4, 12);
        const renderer = new THREE.WebGLRenderer({antialias:true, alpha:true}); renderer.setSize(window.innerWidth, window.innerHeight); document.body.appendChild(renderer.domElement);
        
        scene.add(new THREE.AmbientLight(0xffffff, 0.3));
        const dirLight = new THREE.DirectionalLight(0xffeedd, 0.8); dirLight.position.set(10, 20, 10); scene.add(dirLight);
        
        // Ground
        const ground = new THREE.Mesh(new THREE.PlaneGeometry(100, 100), new THREE.MeshStandardMaterial({color: 0x0a0a0a, roughness: 0.1, metalness: 0.9}));
        ground.rotation.x = -Math.PI / 2; scene.add(ground);
        
        // Rain
        const rainCount = 5000; const rainGeo = new THREE.BufferGeometry(); const rainPos = new Float32Array(rainCount * 3);
        for(let i=0; i<rainCount*3; i+=3){ rainPos[i]=(Math.random()-0.5)*60; rainPos[i+1]=Math.random()*40; rainPos[i+2]=(Math.random()-0.5)*60; }
        rainGeo.setAttribute('position', new THREE.BufferAttribute(rainPos, 3));
        const rain = new THREE.Points(rainGeo, new THREE.PointsMaterial({color: 0x88bbff, size: 0.1, transparent: true, opacity: 0.4})); scene.add(rain);
        
        // Better Trees
        for(let i=0; i<25; i++){ 
            const x = (Math.random()-0.5)*50; const z = (Math.random()-0.5)*50 - 10;
            const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.4, 4), new THREE.MeshStandardMaterial({color: 0x221100})); 
            trunk.position.set(x, 2, z); scene.add(trunk);
            const leaves = new THREE.Mesh(new THREE.ConeGeometry(2, 5, 8), new THREE.MeshStandardMaterial({color: 0x051a0a})); 
            leaves.position.set(x, 5, z); scene.add(leaves);
        }
        
        // Glowing Lantern
        const lantern = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 1.5, 8), new THREE.MeshStandardMaterial({color: 0xffaa00, emissive: 0xffaa00, emissiveIntensity: 3})); 
        lantern.position.set(0, 1.5, 0); scene.add(lantern);
        const pointLight = new THREE.PointLight(0xffaa00, 3, 25); pointLight.position.set(0, 2, 0); scene.add(pointLight);
        
        let time = 0; const animate = () => { requestAnimationFrame(animate); time += 0.01;
            const pos = rain.geometry.attributes.position.array; for(let i=1; i<rainCount*3; i+=3){ pos[i] -= 0.6; if(pos[i]<0) pos[i]=40; } rain.geometry.attributes.position.needsUpdate = true;
            camera.position.x = Math.sin(time*0.1)*4; camera.position.z = Math.cos(time*0.1)*4 + 12; camera.lookAt(0,2,0); renderer.render(scene, camera);
        }; animate();
    </script></body></html>"""
    components.html(html, height=250)

# ──────────────────────────────────────────────────────────────────────────────
# MAIN APP
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
user_data = get_user(st.session_state.user_name)
sb = st.sidebar
sb.markdown(f"### 🧑‍🎓 {st.session_state.user_name}")
sb.metric("Total XP", user_data["xp"])
sb.metric("Day Streak", f"🔥 {user_data['streak']}")
sb.divider()

si = sb.number_input("Surah", 1, 114, st.session_state.current_surah)
ai = sb.number_input("Ayah", 1, 286, st.session_state.current_ayah)
if sb.button("Go to Ayah", use_container_width=True):
    st.session_state.current_surah, st.session_state.current_ayah = si, ai
    st.session_state.mem_step = 0
    st.rerun()

with sb.expander("⚙️ Settings"):
    st.selectbox("Reciter", ["Mishary Alafasy", "Yasser Al-Dosari"], key="cfg_reciter")
    st.radio("Teacher", ["Female", "Male"], key="cfg_teacher", horizontal=True)

s, a = st.session_state.current_surah, st.session_state.current_ayah
key = f"{s}:{a}"
verse = fetch_verse(s, a)
words = fetch_words(s, a)
audio_url, ref_mp3 = fetch_reciter(s, a, st.session_state.cfg_reciter)

if not verse or not words:
    st.error("Could not load Quran data.")
    st.stop()

# 1. PREMIUM PLAYER (Audio Player at Top, All Features)
img_name = "IMG_6147.jpeg" if st.session_state.cfg_teacher == "Male" else "IMG_6146.jpeg"
teacher_img = f"https://raw.githubusercontent.com/Abia2746/ReadandMemoriseTheQuran/main/{img_name}"
audio_b64 = base64.b64encode(ref_mp3).decode("utf-8") if ref_mp3 else ""

analysis = st.session_state.last_analysis.get(key, None)

if audio_b64:
    render_premium_player(words, audio_b64, teacher_img, analysis)

# 2. RECITE BUTTON ON MAIN SCREEN
st.markdown("<h3 style='text-align:center;color:#D4AF37;margin-top:10px;'>🎙️ Recite the Ayah</h3>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;color:#8A7A66;font-size:0.9rem;'>Recite from memory. The cards above will turn green/red.</p>", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    audio_val = st.audio_input("Record", label_visibility="collapsed")
    if audio_val and ref_mp3:
        if st.button("Analyze Recitation", use_container_width=True, type="primary"):
            with st.spinner("Listening to your voice..."):
                res = analyze_recitation(audio_val.getvalue(), [w["ar"] for w in words], ref_mp3)
                if "error" in res: st.error(res["error"])
                else:
                    st.session_state.last_analysis[key] = res
                    if res.get("overall_score", 0) >= 80:
                        add_xp(st.session_state.user_name, 10)
                        st.balloons()
                    st.rerun()

st.divider()

# 3. TABS (Memorise & Study)
t1, t2 = st.tabs(["Memorise (Hifz)", "Study"])

with t1:
    st.markdown(f"<h4 style='text-align:center;'>Step {st.session_state.mem_step + 1} of 4</h4>", unsafe_allow_html=True)
    
    if st.session_state.mem_step == 0:
        st.info("Step 1: Listen to the reference 5 times.")
        if ref_mp3: st.audio(ref_mp3, format="audio/mp3")
        if st.button("✅ I listened once", use_container_width=True):
            st.session_state.mem_listens += 1
            if st.session_state.mem_listens >= 5:
                st.session_state.mem_step = 1
                st.session_state.mem_listens = 0
            st.rerun()
        st.caption(f"Listens: {st.session_state.mem_listens}/5")
        
    elif st.session_state.mem_step == 1:
        st.info("Step 2: Recite using English hints.")
        cols = st.columns(3)
        for i, w in enumerate(words[:3]): 
            with cols[i]:
                st.markdown(f"<div style='background:#2A221B;border:1px solid #D4AF37;border-radius:15px;padding:10px;text-align:center;'><div style='color:#E8D5B5;font-weight:bold;'>{w['en']}</div></div>", unsafe_allow_html=True)
        
        audio_val = st.audio_input("Record step 2", label_visibility="collapsed")
        if audio_val and ref_mp3:
            if st.button("Analyze Hifz Chunk", use_container_width=True, type="primary"):
                with st.spinner("Analyzing..."):
                    res = analyze_recitation(audio_val.getvalue(), [w["ar"] for w in words], ref_mp3)
                    if "error" in res: st.error(res["error"])
                    else:
                        st.session_state.last_analysis[key] = res
                        st.session_state.mem_step = 2
                        st.rerun()

    elif st.session_state.mem_step == 2:
        st.success("Masha'Allah! You passed this chunk.")
        if st.button("Next Step (Repeat x5)", use_container_width=True, type="primary"):
            st.session_state.mem_step = 3
            st.rerun()

    elif st.session_state.mem_step == 3:
        st.info("Step 3: Repeat x5 without looking at the Arabic.")
        if ref_mp3: st.audio(ref_mp3, format="audio/mp3")
        if st.button("✅ I repeated once", use_container_width=True):
            st.session_state.mem_listens += 1
            if st.session_state.mem_listens >= 5:
                st.session_state.mem_step = 4
                st.session_state.mem_listens = 0
            st.rerun()
        st.caption(f"Repeats: {st.session_state.mem_listens}/5")

    elif st.session_state.mem_step == 4:
        if st.session_state.show_reward:
            st.balloons()
            st.markdown("<h3 style='text-align:center;color:#D4AF37'>Alhamdulillah!</h3>", unsafe_allow_html=True)
            if st.button("Complete Ritual", use_container_width=True, type="primary"):
                st.session_state.show_reward = False
                st.session_state.mem_step = 0
                add_xp(st.session_state.user_name, 20)
                st.rerun()
        else:
            st.info("Step 4: Final Blind Recitation.")
            audio_val = st.audio_input("Record final", label_visibility="collapsed")
            if audio_val and ref_mp3:
                if st.button("Analyze Final", use_container_width=True, type="primary"):
                    with st.spinner("Analyzing..."):
                        res = analyze_recitation(audio_val.getvalue(), [w["ar"] for w in words], ref_mp3)
                        if "error" in res: st.error(res["error"])
                        else:
                            st.success(f"Score: {res.get('overall_score', 0)}%")
                            st.session_state.show_reward = True
                            st.rerun()

with t2:
    st.markdown(f"<div style='direction:rtl; font-family:Amiri Quran; font-size:2.5rem; text-align:center; color:#D4AF37; padding:20px;'>{verse}</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align:center; color:#8A7A66; margin-top:10px;'>Translation: {requests.get(f'https://api.alquran.cloud/v1/ayah/{s}:{a}/en.sahih').json()['data']['text']}</div>", unsafe_allow_html=True)

# ─── 3D GARDEN ───
st.divider()
st.markdown("<h4 style='text-align:center;color:#D4AF37'>Your Private Garden</h4>", unsafe_allow_html=True)
render_3d_garden()
