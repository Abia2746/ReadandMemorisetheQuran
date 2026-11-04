import base64, json, re
import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_mic_recorder import mic_recorder

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"
VOICE_ID = "pNInz6obpgDQGcFmaJgB"

st.set_page_config(layout="wide", page_title="Al-Mu'allim", page_icon="🕌")
st.markdown("""
<style>
.stApp { background: linear-gradient(160deg,#fbf8f1 0%,#f1ede2 60%,#e9efe9 100%); }
h1,h2,h3,h4,p,label,li,.stMarkdown { color:#2b2a26 !important; font-family:Georgia,'Times New Roman',serif; }
.glass { background:rgba(255,255,255,.55); backdrop-filter:blur(10px); border:1px solid rgba(197,168,92,.35);
  border-radius:16px; padding:20px 24px; margin:12px 0; box-shadow:0 6px 24px rgba(120,100,50,.08); }
.ar-big { font-family:'Amiri','Scheherazade New',serif; font-size:2.6rem; direction:rtl; text-align:center; line-height:2.2; color:#7a5c12; }
div.stButton > button { background:linear-gradient(135deg,#c5a85c,#b39243)!important; color:#fff!important; border:none!important; border-radius:10px!important; font-weight:600!important; }
</style>""", unsafe_allow_html=True)

for k, v in {"user_name": "", "app_phase": "onboarding", "current_surah": 2, "current_ayah": 57,
             "listens": {}, "chat": [], "tafsir_text": {}}.items():
    st.session_state.setdefault(k, v)

# ---------- helpers ----------
def audio_part(b, mime):
    return {"inline_data": {"mime_type": mime, "data": base64.b64encode(b).decode()}}

def call_gemini(parts, expect_json=False):
    h = {"x-goog-api-key": st.secrets["GEMINI_API_KEY"], "Content-Type": "application/json"}
    p = {"contents": [{"parts": parts}]}
    if expect_json: p["generationConfig"] = {"responseMimeType": "application/json"}
    r = requests.post(GEMINI_URL, json=p, headers=h, timeout=120)
    if r.status_code != 200: raise RuntimeError(f"Gemini {r.status_code}: {r.text[:250]}")
    t = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    return json.loads(t) if expect_json else t

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
        r = requests.get(f"https://api.quran.com/api/v4/verses/by_key/{s}:{a}",
            params={"words": "true", "word_fields": "text_uthmani", "language": "en"}, timeout=20).json()
        return [{"ar": w["text_uthmani"], "en": (w.get("translation") or {}).get("text", ""),
                 "tr": (w.get("transliteration") or {}).get("text") or ""}
                for w in r["verse"]["words"] if w.get("char_type_name") == "word"]
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def fetch_reciter(s, a):
    """Sheikh Yasser Al-Dosari (everyayah.com); falls back to Alafasy if unavailable."""
    url = f"https://everyayah.com/data/Yasser_Ad-Dussary_128kbps/{s:03d}{a:03d}.mp3"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200 and len(r.content) > 2000:
            return url, r.content, "Sheikh Yasser Al-Dosari"
    except Exception:
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
<div id="w"></div><audio id="a" controls src="__URL__"></audio>
<script>
const W=__WORDS__,a=document.getElementById('a'),box=document.getElementById('w');
const els=W.map(w=>{const d=document.createElement('div');d.className='c';
d.innerHTML='<div class="ar">'+w.ar+'</div><div class="tr">'+w.tr+'</div><div class="en">'+w.en+'</div>';box.appendChild(d);return d;});
let cum=[];
function build(){const d=a.duration||1,l=d*.05,sp=d*.88,tot=W.reduce((s,w)=>s+w.ar.length,0);let t=l;
cum=W.map(w=>{t+=sp*w.ar.length/tot;return t;});}
a.onloadedmetadata=build;
a.ontimeupdate=()=>{if(!cum.length)build();const t=a.currentTime;let i=cum.findIndex(c=>t<c);if(a.ended)i=-1;
els.forEach((e,k)=>e.classList.toggle('on',k===i));};
a.onended=()=>els.forEach(e=>e.classList.remove('on'));
</script>"""
    return tpl.replace("__URL__", audio_url).replace("__WORDS__", json.dumps(words, ensure_ascii=False))

# ---------- AI teachers ----------
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

def analyse(verse, ref_mp3, student_wav, reciter):
    prompt = f"""You are an expert Tajweed teacher. The student recited this ayah from memory: {verse}
Clip 1 is the reference by {reciter}. Clip 2 is the student.
Compare word by word: harakat, sukoon, madd length, ghunnah, idgham/ikhfa/iqlab/izhar, qalqalah, makharij, waqf. Also say if any words were skipped or wrong (memorisation errors).
Write in English; Arabic words in script plus transliteration. Report only what you can actually hear; admit uncertainty; never invent mistakes. If the clip is silent or the wrong ayah, say so.
Return JSON only: {{"overall_score":int,"spoken_summary":"max 60 words, warm","words":[{{"word":"","status":"good|needs_work","student_did":"","correction":""}}],"practice_tip":""}}"""
    return call_gemini([{"text": prompt}, {"text": "Clip 1 (reference):"}, audio_part(ref_mp3, "audio/mpeg"),
                        {"text": "Clip 2 (student):"}, audio_part(student_wav, "audio/wav")], True)

def plan_sessions(goal, s, a):
    prompt = f"""Create a realistic 7-day Quran memorisation plan for {st.session_state.user_name}, currently at Surah {s}, Ayah {a}. Their goal: {goal}.
Use the Sabaq (new), Sabqi (recent review), Manzil (old review) structure, with the 5-listen method, tafsir reading and recitation check each day. Plain English, short, one line per day, no markdown symbols."""
    return call_gemini([{"text": prompt}])

# ---------- UI ----------
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

    s, a = st.session_state.current_surah, st.session_state.current_ayah
    key, ref = f"{s}:{a}", f"Surah {s}, Ayah {a}"
    verse, words = fetch_verse(s, a), fetch_words(s, a)
    audio_url, ref_mp3, reciter = fetch_reciter(s, a)
    listens = st.session_state.listens.get(key, 0)

    t1, t2, t3, t4 = st.tabs(["1 · Listen ×5", "2 · Tafsir & Teacher", "3 · Recite from memory", "4 · Plan"])

    with t1:
        st.markdown(f'<div class="glass"><div class="ar-big">{verse}</div></div>', unsafe_allow_html=True)
        if audio_url and words:
            st.caption(f"Reciter: {reciter}. Words light up as they are recited (timing is estimated from word length).")
            components.html(player_html(words, audio_url), height=420 + 40 * (len(words) // 6), scrolling=True)
        else:
            st.warning("Could not load audio or word-by-word data. Check your connection and reload.")
        st.progress(min(listens, 5) / 5, text=f"Listens completed: {min(listens, 5)} / 5")
        if st.button("✅ I listened once more"):
            st.session_state.listens[key] = listens + 1
            st.rerun()
        if listens >= 5: st.success("Five listens done. Read the tafsir, then try reciting from memory.")

    with t2:
        src = fetch_ibn_kathir(s, a)
        if st.button("📖 Explain this ayah to me"):
            try:
                with st.spinner("Preparing tafsir..."):
                    st.session_state.tafsir_text[key] = explain_tafsir(ref, verse, src)
            except Exception as e:
                st.error(e)
        if key in st.session_state.tafsir_text:
            st.markdown(f'<div class="glass">{st.session_state.tafsir_text[key]}</div>', unsafe_allow_html=True)
            st.caption("Based on Ibn Kathir (abridged) via quran.com. AI-written explanation: verify important points with a qualified teacher.")
        st.markdown("#### 💬 Ask your teacher")
        for m in st.session_state.chat:
            with st.chat_message("user" if m["role"] == "student" else "assistant"):
                st.write(m["text"])
        q = st.chat_input("Ask about this ayah...")
        if q:
            try:
                ans = scholar_reply(ref, verse, src, st.session_state.chat, q)
                st.session_state.chat += [{"role": "student", "text": q}, {"role": "teacher", "text": ans}]
                st.rerun()
            except Exception as e:
                st.error(e)

    with t3:
        if listens < 5:
            st.info(f"Complete 5 listens first ({listens}/5). Then recite without looking.")
        else:
            st.write("Recite the ayah from memory:")
            mic = mic_recorder(start_prompt="🎙️ Start", stop_prompt="⏹️ Stop & get feedback", key="rec", just_once=True)
            if mic and ref_mp3:
                st.audio(mic["bytes"], format="audio/wav")
                try:
                    with st.spinner("Comparing with the reference recitation..."):
                        res = analyse(verse, ref_mp3, mic["bytes"], reciter)
                    st.metric("Estimated accuracy", f"{res.get('overall_score','?')}%")
                    st.caption("AI estimate, not a certified assessment.")
                    st.markdown(f'<div class="glass">{res.get("spoken_summary","")}</div>', unsafe_allow_html=True)
                    for w in res.get("words", []):
                        ok = w.get("status") == "good"
                        with st.expander(f"{'✅' if ok else '⚠️'} {w.get('word','')}", expanded=not ok):
                            st.write(f"Heard: {w.get('student_did','')}")
                            st.write(f"Fix: {w.get('correction','')}")
                    st.info(f"💡 {res.get('practice_tip','')}")
                    audio = speak(res.get("spoken_summary", ""))
                    if audio: st.audio(audio, format="audio/mp3")
                except Exception as e:
                    st.error(f"Analysis failed: {e}")

    with t4:
        goal = st.text_input("Your goal", placeholder="e.g., memorise 5 ayat a week, 20 minutes a day")
        if st.button("🗓️ Plan my sessions") and goal.strip():
            try:
                st.markdown(f'<div class="glass">{plan_sessions(goal, s, a)}</div>'.replace("\n", "<br>"), unsafe_allow_html=True)
            except Exception as e:
                st.error(e)
