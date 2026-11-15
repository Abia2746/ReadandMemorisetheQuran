# app.py — Al-Mu'allim · React UI + Native Streamlit Mic + 3D Garden
import streamlit as st
import streamlit.components.v1 as components
import requests
import json
import base64
import os
import re

# --- CONFIGURATION ---
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

st.set_page_config(layout="wide", page_title="Al-Mu'allim", page_icon="🕌")

# Hide Streamlit padding so the UI fills the screen
st.markdown("""
    <style>
        .block-container { padding: 0 !important; max-width: 100% !important; }
        header { display: none !important; }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- DATA ---
words = [
  { "ar": "وَإِذِ", "tr": "wa-idh", "en": "And when" },
  { "ar": "اسْتَقَىٰ", "tr": "is'tasqā", "en": "asked for water" },
  { "ar": "مُوسَىٰ", "tr": "mūsā", "en": "Musa" },
  { "ar": "لِقَوْمِهِ", "tr": "liqawmihi", "en": "for his people" },
  { "ar": "اضْرِب", "tr": "iḍrib", "en": "Strike" },
  { "ar": "بِعَصَاكَ", "tr": "bi'aṣāka", "en": "with your staff" },
  { "ar": "الْحَجَرَ", "tr": "al-ḥajara", "en": "the stone" },
]

# --- SESSION STATE ---
if "analysis" not in st.session_state:
    st.session_state.analysis = None

# --- GEMINI LOGIC ---
def analyze_recitation(audio_bytes):
    if not GEMINI_API_KEY:
        return {"error": "Gemini API key missing in Streamlit secrets."}
    
    b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
    
    prompt = f"""You are an expert Tajweed teacher.
The expected words are: {json.dumps([w["ar"] for w in words])}
Listen to the student's recitation. Compare it word by word.
Return JSON ONLY (no markdown, no extra text): 
{{"score": int, "words": [{{"word": "arabic_word_here", "status": "good" | "missed" | "close"}}], "summary": "Short feedback"}}"""

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "audio/webm", "data": b64_audio}}
            ]
        }],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    headers = {"Content-Type": "application/json"}
    
    for model in ["gemini-1.5-pro", "gemini-1.5-flash"]:
        try:
            response = requests.post(f"{API_URL}/{model}:generateContent?key={GEMINI_API_KEY}", json=payload, headers=headers, timeout=60)
            if response.status_code == 200:
                text = response.json()['candidates'][0]['content']['parts'][0]['text']
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
                m = re.search(r"\{.*\}", cleaned, re.DOTALL)
                if m: cleaned = m.group(0)
                return json.loads(cleaned)
        except Exception:
            continue
            
    return {"error": "Failed to analyze audio with Gemini."}

# --- PREPARE VARIABLES ---
analysis_json = json.dumps(st.session_state.analysis) if st.session_state.analysis else "null"
teacher_img = "https://raw.githubusercontent.com/Abia2746/ReadandMemoriseTheQuran/main/IMG_6146.jpeg"
words_json = json.dumps(words)

# --- THE REACT UI (Using raw string to avoid Python f-string errors) ---
html_code = r"""
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Amiri+Quran&display=swap" rel="stylesheet">
  <style>
    body { background-color: #1A1510; color: #E8D5B5; margin: 0; overflow-x: hidden; }
    .font-arabic { font-family: 'Amiri Quran', serif; }
    ::-webkit-scrollbar { width: 0px; background: transparent; }
  </style>
  <script>
    tailwind.config = {
      theme: { extend: { fontFamily: { arabic: ['"Amiri Quran"', 'serif'] } } }
    }
  </script>
</head>
<body>
  <div id="root"></div>
  <script type="text/babel">
    const { useState, useEffect, useRef } = React;
    const mockWords = __WORDS__;
    const analysis = __ANALYSIS__;

    function Garden() {
      const mountRef = useRef(null);
      useEffect(() => {
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x0a0805, 0.05);
        const camera = new THREE.PerspectiveCamera(60, mountRef.current.clientWidth / mountRef.current.clientHeight, 0.1, 1000);
        camera.position.set(0, 5, 15);
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
        mountRef.current.appendChild(renderer.domElement);
        scene.add(new THREE.AmbientLight(0xffffff, 0.5));
        const dirLight = new THREE.DirectionalLight(0xffeedd, 1);
        dirLight.position.set(10, 20, 10);
        scene.add(dirLight);
        
        const ground = new THREE.Mesh(new THREE.PlaneGeometry(100, 100), new THREE.MeshStandardMaterial({ color: 0x1a2020, roughness: 0.1, metalness: 0.8 }));
        ground.rotation.x = -Math.PI / 2;
        scene.add(ground);
        
        const rainCount = 3000;
        const rainGeo = new THREE.BufferGeometry();
        const rainPositions = new Float32Array(rainCount * 3);
        for(let i=0; i<rainCount*3; i+=3) {
          rainPositions[i] = (Math.random() - 0.5) * 60;
          rainPositions[i+1] = Math.random() * 40;
          rainPositions[i+2] = (Math.random() - 0.5) * 60;
        }
        rainGeo.setAttribute('position', new THREE.BufferAttribute(rainPositions, 3));
        const rain = new THREE.Points(rainGeo, new THREE.PointsMaterial({ color: 0xaaccff, size: 0.15, transparent: true, opacity: 0.6 }));
        scene.add(rain);
        
        for(let i=0; i<15; i++) {
          const tree = new THREE.Mesh(new THREE.ConeGeometry(1.5, 6, 8), new THREE.MeshStandardMaterial({ color: 0x0a2a1a, roughness: 1 }));
          tree.position.set((Math.random()-0.5)*40, 3, (Math.random()-0.5)*40 - 10);
          scene.add(tree);
        }
        
        const lantern = new THREE.Mesh(new THREE.BoxGeometry(1, 1.5, 1), new THREE.MeshStandardMaterial({ color: 0x332200, emissive: 0xffaa00, emissiveIntensity: 2 }));
        lantern.position.set(0, 2, 0);
        scene.add(lantern);
        const pointLight = new THREE.PointLight(0xffaa00, 2, 20);
        pointLight.position.set(0, 2, 0);
        scene.add(pointLight);
        
        let time = 0; let animationFrameId;
        const animate = () => {
          animationFrameId = requestAnimationFrame(animate);
          time += 0.01;
          const positions = rain.geometry.attributes.position.array;
          for(let i=1; i<rainCount*3; i+=3) {
            positions[i] -= 0.5;
            if(positions[i] < 0) positions[i] = 40;
          }
          rain.geometry.attributes.position.needsUpdate = true;
          camera.position.x = Math.sin(time * 0.2) * 5;
          camera.position.z = Math.cos(time * 0.2) * 5 + 10;
          camera.lookAt(0, 2, 0);
          renderer.render(scene, camera);
        };
        animate();
        return () => { cancelAnimationFrame(animationFrameId); if (mountRef.current) mountRef.current.removeChild(renderer.domElement); };
      }, []);
      return <div ref={mountRef} className="w-full h-[300px] rounded-2xl overflow-hidden border border-[#D4AF37]/30 shadow-[0_0_30px_rgba(212,175,55,0.15)] bg-black" />;
    }

    function App() {
      const hasAnalysis = analysis && analysis.words;

      return (
        <div className="min-h-screen bg-[#1A1510] text-[#E8D5B5] font-sans pb-32">
          <nav className="flex justify-between items-center p-6 border-b border-[#D4AF37]/20">
            <div className="text-[#D4AF37] font-serif text-2xl tracking-wide">Al-Mu'allim</div>
          </nav>
          
          <div className="max-w-2xl mx-auto px-4 mt-6">
            <div className="text-center mb-6">
              <p className="text-[#8A7A66] text-sm tracking-widest uppercase mb-1">Surah</p>
              <h1 className="text-3xl font-serif text-[#D4AF37]">Al-Baqarah · Ayah 60</h1>
            </div>

            <div className="flex justify-center mb-6">
              <div className="relative w-32 h-40 rounded-3xl overflow-hidden shadow-[0_0_40px_rgba(212,175,55,0.15)] border border-[#D4AF37]/30">
                <img src="__TEACHER_IMG__" alt="Teacher" className="w-full h-full object-cover opacity-80" />
              </div>
            </div>

            {hasAnalysis && (
              <div className="text-center mb-6 bg-[#2A221B] p-4 rounded-2xl border border-[#D4AF37]/50">
                <h2 className="text-2xl font-bold text-[#D4AF37]">Score: {analysis.score}%</h2>
                <p className="text-[#8A7A66] mt-2">{analysis.summary}</p>
              </div>
            )}

            <div className="flex flex-wrap gap-3 justify-center mb-8" dir="rtl">
              {mockWords.map((word, idx) => {
                let borderClass = 'border-[#D4AF37]/10';
                let bgClass = 'bg-[#2A221B]';
                
                if (hasAnalysis) {
                  const result = analysis.words.find((w) => w.word === word.ar || w.word.includes(word.ar));
                  if (result) {
                    if (result.status === 'good') { borderClass = 'border-green-500'; bgClass = 'bg-green-500/10'; }
                    if (result.status === 'missed') { borderClass = 'border-red-500'; bgClass = 'bg-red-500/10'; }
                    if (result.status === 'close') { borderClass = 'border-yellow-500'; bgClass = 'bg-yellow-500/10'; }
                  } else {
                     borderClass = 'border-red-500'; bgClass = 'bg-red-500/10';
                  }
                }

                return (
                  <div key={idx} className={`flex flex-col items-center justify-center p-4 min-w-[100px] rounded-2xl border transition-all duration-300 ${borderClass} ${bgClass}`}>
                    
                    {/* ENGLISH IS PROMINENT */}
                    <div className={`text-xl font-bold text-[#E8D5B5] ${!hasAnalysis ? 'mb-2' : 'mb-1 opacity-50'}`}>
                      {word.en}
                    </div>
                    
                    {/* ARABIC IS HIDDEN UNTIL ANALYZED */}
                    <div className={`font-arabic text-4xl mb-1 text-[#D4AF37] leading-relaxed transition-opacity duration-500 ${hasAnalysis ? 'opacity-100' : 'opacity-0 h-0 overflow-hidden'}`}>
                      {word.ar}
                    </div>

                  </div>
                );
              })}
            </div>

            <div className="mb-10">
              <div className="flex items-center gap-2 mb-4 text-[#D4AF37]">
                <h2 className="text-xl font-serif">Your Private Garden</h2>
              </div>
              <Garden />
            </div>
          </div>
        </div>
      );
    }
    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(<App />);
  </script>
</body>
</html>
"""

# Inject variables safely (bypasses Python f-string limits)
html_code = html_code.replace("__WORDS__", words_json)
html_code = html_code.replace("__ANALYSIS__", analysis_json)
html_code = html_code.replace("__TEACHER_IMG__", teacher_img)

# 1. Render the Vercel-style UI
components.html(html_code, height=1000, scrolling=True)

# 2. Render the Streamlit Mic underneath
st.markdown("---")
st.markdown("<h3 style='text-align: center; color: #D4AF37; margin-bottom: 0;'>🎙️ Recite the Ayah</h3>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #8A7A66; font-size: 0.9rem;'>Recite from memory. The AI will reveal the Arabic words and highlight your mistakes.</p>", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    audio_value = st.audio_input("Record", label_visibility="collapsed")
    
    if audio_value is not None:
        if st.button("Analyze My Recitation", use_container_width=True, type="primary"):
            with st.spinner("Listening to your voice..."):
                result = analyze_recitation(audio_value.getvalue())
                
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.session_state.analysis = result
                    st.rerun()

    if st.session_state.analysis:
        if st.button("Reset / Try Again", use_container_width=True):
            st.session_state.analysis = None
            st.rerun()
