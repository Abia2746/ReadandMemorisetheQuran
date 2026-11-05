import base64, json, re, time
import html as _h
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
div.stButton > button { background:linear-gradient(135deg,#c5a85c,#b39243)!important; color:#fff!important; border:none!important; border-radius:10px!important; font-weight:600!important; }
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
    """Retries busy errors, then falls back through other models (best Pro first when pro=True)."""
    h = {"x-goog-api-key": st.secrets["GEMINI_API_KEY"], "Content-Type": "application/json"}
    p = {"contents": [{"parts": parts}]}
    if expect_json: p["generationConfig"] = {"responseMimeType": "application/json"}
    last = ""
    for model in pick_models(pro):
        for attempt in range(3):
            r = requests.post(f"{API}/{model}:generateContent", json=p, headers=h, timeout=150)
            if r.status_code == 200:
                ps = r.json()["candidates"][0]["content"]["parts"]
                t = "".join(x.get("text", "") for x in ps if not x.get("thought")).strip()
                if expect_json:
                    return json.loads(re.sub(r"^```(?:json)?|```$", "", t).strip())
                return t
            last = f"{model} {r.status_code}: {r.text[:150]}"
            if r.status_code in (429, 500, 503): time.sleep(2 ** attempt); continue
            break
    raise RuntimeError("Gemini is busy or unavailable right now. Try again shortly. " + last)

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
<div id="w"></div><audio id="a" controls src="__URL__"></audio><div id="n" style="text-align:center;margin-top:10px;color:#7a5c12;font-weight:600"></div><div style="text-align:center;margin-top:8px">🔈 <input id="v" type="range" min="0" max="100" value="50" style="width:60%"> 🔊</div>
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
const ctx=new (window.AudioContext||window.webkitAudioContext)();const g=ctx.createGain();
ctx.createMediaElementSource(a).connect(g);g.connect(ctx.destination);
const vs=document.getElementById('v');g.gain.value=vs.value/100;
vs.oninput=()=>{g.gain.value=vs.value/100;ctx.resume();};
a.addEventListener('play',()=>ctx.resume());
let n=1,done=false;const cn=document.getElementById('n');
function upd(){cn.textContent=done?'✅ All 5 listens complete':'Listen '+n+' of 5';}
a.onplay=()=>{if(done){n=1;done=false;}upd();};
a.onended=()=>{els.forEach(e=>e.classList.remove('on'));if(n<5){n++;upd();setTimeout(()=>a.play(),1500);}else{done=true;upd();}};
upd();
</script>"""
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

def analyse(verse, ref_mp3, student_wav, reciter):
    prompt = f"""You are an expert Tajweed teacher. The student recited this ayah from memory: {verse}
Clip 1 is the reference by {reciter}. Clip 2 is the student.
Compare word by word: harakat, sukoon, madd length, ghunnah, idgham/ikhfa/iqlab/izhar, qalqalah, makharij, waqf. Also say if any words were skipped or wrong (memorisation errors).
Write in English; Arabic words in script plus transliteration. Report only what you can actually hear; admit uncertainty; never invent mistakes. If the clip is silent or the wrong ayah, say so.
Checklist of tajweed rules in this ayah:
{tajweed_rules(verse)}
Also compare breath control (where each reciter breathes or pauses, and whether the student's breath lasted each phrase). Judge each checklist rule separately, citing roughly where (seconds) you heard it in each clip, with a confidence level.
Return JSON only: {{"overall_score":int,"rules_check":[{{"rule":"","word":"","verdict":"correct|partly|missed|unclear","evidence":"","confidence":"high|medium|low"}}],"breath":{{"reference":"","student":"","tip":""}},"spoken_summary":"max 60 words, warm","words":[{{"word":"","status":"good|needs_work","student_did":"","correction":""}}],"practice_tip":""}}"""
    return call_gemini([{"text": prompt}, {"text": "Clip 1 (reference):"}, audio_part(ref_mp3, "audio/mpeg"),
                        {"text": "Clip 2 (student):"}, audio_part(student_wav, "audio/wav")], True, pro=True)

def plan_sessions(goal, s, a):
    prompt = f"""Create a realistic 7-day Quran memorisation plan for {st.session_state.user_name}, currently at Surah {s}, Ayah {a}. Their goal: {goal}.
Use the Sabaq (new), Sabqi (recent review), Manzil (old review) structure, with the 5-listen method, tafsir reading and recitation check each day. Plain English, short, one line per day, no markdown symbols."""
    return call_gemini([{"text": prompt}])

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
    """Aesthetic mic (st.audio_input); falls back to mic_recorder on older Streamlit. Returns wav bytes once per recording."""
    st.markdown(f"<div style='text-align:center;color:#7a5c12'>🎙️ {label}</div>", unsafe_allow_html=True)
    if not hasattr(st, "audio_input"):
        m = mic_recorder(start_prompt="🎙️ Tap to talk", stop_prompt="⏹️ Send", key=key, just_once=True)
        return m["bytes"] if m else None
    clip = st.audio_input(label, key=key, label_visibility="collapsed")
    if clip is None: return None
    b = clip.getvalue(); hs = hash(b)
    if st.session_state.get("seen_" + key) == hs: return None
    st.session_state["seen_" + key] = hs
    return b

def live_reply(ref, verse, ctx, hist, text, wav):
    convo = "\n".join(f"{m['role']}: {m['text']}" for m in hist[-10:])
    sysmsg = f"""You are a warm, casual, learned Quran teacher (a kind sheikh chatting over tea) talking with {st.session_state.user_name} about {ref}: {verse}
Speak naturally in English, 2-5 short sentences (about 80 words), because your answer is read aloud. No markdown, no lists. Arabic terms in transliteration. Ask at most one gentle follow-up question.
Ground explanations in the CONTEXT. If it does not cover the question, say so; never invent hadith, narrations or scholar names. You are not a mufti: for fiqh rulings advise a qualified scholar. Never claim to have heard something you did not.
CONTEXT:
{ctx}
CONVERSATION:
{convo}"""
    parts = [{"text": sysmsg}]
    if wav: parts += [{"text": "The student's spoken message is in this audio. Answer it:"}, audio_part(wav, "audio/wav")]
    else: parts.append({"text": "student: " + text})
    return call_gemini(parts)

def teacher_turn(key, ctx, ref, verse, hist_key):
    wav = voice_in(key + "_v", "Tap the mic and talk to your teacher")
    txt = st.chat_input("...or type here", key=key + "_t")
    hist = st.session_state.setdefault(hist_key, [])
    audio = None
    if wav or txt:
        try:
            with st.spinner("Your teacher is thinking..."):
                ans = live_reply(ref, verse, ctx, hist, txt, wav)
            hist += [{"role": "student", "text": txt or "🎙️ (voice message)"}, {"role": "teacher", "text": ans}]
            audio = speak(ans)
        except Exception as e:
            st.error(e)
    if audio: play(audio)
    for m in hist:
        with st.chat_message("user" if m["role"] == "student" else "assistant"):
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

    t1, t2, t3, t4 = st.tabs(["1 · Listen ×5", "2 · Teacher & Lesson", "3 · Recite & Coach", "4 · Plan"])

    with t1:
        st.markdown(f'<div class="glass"><div class="ar-big">{verse}</div></div>', unsafe_allow_html=True)
        if audio_url and words:
            st.caption(f"Reciter: {reciter}. Words light up as they are recited (timing is estimated from word length).")
            components.html(player_html(words, "data:audio/mpeg;base64," + base64.b64encode(ref_mp3).decode()), height=420 + 40 * (len(words) // 6), scrolling=True)
        else:
            st.warning("Could not load audio or word-by-word data. Check your connection and reload.")
        st.progress(min(listens, 5) / 5, text=f"Listens completed: {min(listens, 5)} / 5")
        if st.button("✅ I listened once more"):
            st.session_state.listens[key] = listens + 1
            st.rerun()
        if listens >= 5: st.success("Five listens done. Read the tafsir, then try reciting from memory.")

    with t2:
        src = fetch_ibn_kathir(s, a)
        c1, c2 = st.columns(2)
        if c1.button("📖 Explain this ayah to me"):
            try:
                with st.spinner("Preparing tafsir..."):
                    st.session_state.tafsir_text[key] = explain_tafsir(ref, verse, src)
            except Exception as e:
                st.error(e)
        if c2.button("🎓 Teach me to recite it") and ref_mp3:
            try:
                with st.spinner("Your teacher is listening to the reference recitation..."):
                    st.session_state.lessons[key] = recitation_lesson(s, a, verse, tajweed_rules(verse), ref_mp3, reciter)
            except Exception as e:
                st.error(e)
        if key in st.session_state.tafsir_text:
            card(st.session_state.tafsir_text[key])
            st.caption("Based on Ibn Kathir (abridged) via quran.com. AI-written: verify important points with a qualified teacher.")
        if key in st.session_state.lessons:
            st.markdown("#### 🎓 Recitation lesson and breath map")
            card(st.session_state.lessons[key])
        st.markdown("#### 🎙️ Talk to your teacher")
        teacher_turn("t2", src, ref, verse, "chat")

    with t3:
        st.caption("Listen on tab 1 first, then recite from memory. Your teacher stays in the conversation afterwards.")
        wav = voice_in("recite", "Tap the mic, recite the ayah from memory, then stop")
        spoken = None
        if wav and ref_mp3:
            play(wav, "audio/wav", False)
            try:
                with st.spinner("Comparing with the reference recitation..."):
                    res = analyse(verse, ref_mp3, wav, reciter)
                st.session_state.last_analysis[key] = res
                st.session_state.coach = []
                spoken = speak(res.get("spoken_summary", ""))
            except Exception as e:
                st.error(f"Analysis failed: {e}")
        res = st.session_state.last_analysis.get(key)
        if res:
            st.metric("Estimated accuracy", f"{res.get('overall_score','?')}%")
            st.caption("AI estimate, not a certified assessment.")
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
        goal = st.text_input("Your goal", placeholder="e.g., memorise 5 ayat a week, 20 minutes a day")
        if st.button("🗓️ Plan my sessions") and goal.strip():
            try:
                st.markdown(f'<div class="glass">{plan_sessions(goal, s, a)}</div>'.replace("\n", "<br>"), unsafe_allow_html=True)
            except Exception as e:
                st.error(e)
