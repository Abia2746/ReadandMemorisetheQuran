import datetime as dt
import html
import json

import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Live Recitation Coach", page_icon="✨", layout="centered")
st.title("✨ Live Recitation Coach")
st.write("A real-time practice space: follow live word highlights, hear a spoken AI coach, and review a cautious transcript comparison after reciting.")
st.caption("AI study aid only — not a human teacher, certified Tajweed assessment, or replacement for a qualified Quran teacher.")

API_KEY = st.secrets.get("GEMINI_API_KEY", "")
MODEL = st.secrets.get("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025")

col1, col2 = st.columns(2)
with col1:
    surah = st.number_input("Surah", min_value=1, max_value=114, value=1, step=1)
with col2:
    ayah = st.number_input("Ayah", min_value=1, max_value=286, value=1, step=1)

level = st.selectbox("Practice level", ["New learner", "Building confidence", "Confident reciter"], index=0)
feedback_style = st.selectbox("Coach style", ["Gentle encouragement", "Focused and specific"], index=0)

verse = ""
try:
    result = requests.get(
        f"https://api.alquran.cloud/v1/ayah/{int(surah)}:{int(ayah)}/quran-uthmani",
        timeout=10,
    )
    if result.ok:
        verse = result.json().get("data", {}).get("text", "")
except requests.RequestException:
    pass

if not verse:
    st.warning("The ayah text could not be loaded. Check your connection and try again.")
    st.stop()

st.markdown(f"<div dir='rtl' style='font-family:serif;font-size:2rem;line-height:2.1;text-align:center;padding:1rem'>{html.escape(verse)}</div>", unsafe_allow_html=True)
st.caption("Gold highlights show words matched from the live speech transcript. The end-of-practice comparison measures transcript matching only—not pronunciation or Tajweed correctness.")

if not API_KEY:
    st.error("Add GEMINI_API_KEY to Streamlit secrets to enable the live voice coach. The long-lived API key remains on the server; only a short-lived, single-use session token is sent to the browser.")
    st.stop()


def issue_token() -> str:
    now = dt.datetime.now(dt.timezone.utc)
    prompt = (
        "You are a kind, concise Quran recitation practice assistant. The student is reciting "
        f"Surah {int(surah)}, ayah {int(ayah)}: {verse}. Student level: {level}. Coaching style: {feedback_style}. "
        "Listen carefully and do not interrupt a continuous recitation. After a natural pause, "
        "offer one short, encouraging, actionable observation grounded only in the audio you "
        "actually heard. If uncertain or the audio is unclear, say so and ask the student to repeat "
        "a short phrase. Never invent skipped words, pronunciation errors, or Tajweed mistakes. "
        "Do not claim exact Tajweed diagnosis, a numeric recitation score, or certified assessment. "
        "Answer questions briefly in clear English. You are an AI, not a human teacher or qualified "
        "scholar. Allow natural interruption and stop speaking when the student speaks. For personal "
        "religious rulings, recommend asking a qualified scholar."
    )
    payload = {
        "uses": 1,
        "expireTime": (now + dt.timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        "newSessionExpireTime": (now + dt.timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "liveConnectConstraints": {
            "model": f"models/{MODEL}",
            "config": {
                "responseModalities": ["AUDIO"],
                "systemInstruction": {"parts": [{"text": prompt}]},
                "inputAudioTranscription": {},
                "outputAudioTranscription": {},
            },
        },
    }
    response = requests.post(
        "https://generativelanguage.googleapis.com/v1alpha/authTokens",
        params={"key": API_KEY},
        json=payload,
        timeout=20,
    )
    if not response.ok:
        raise RuntimeError(f"Gemini Live token request failed ({response.status_code}): {response.text[:400]}")
    token = response.json().get("name")
    if not token:
        raise RuntimeError("Gemini did not return a Live session token. Verify model access and API configuration.")
    return token


PAGE = r"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
*{box-sizing:border-box}body{margin:0;padding:8px;background:#faf6ec;color:#302719;font:15px system-ui,sans-serif}.card{padding:18px;border:1px solid #e6dcc8;border-radius:22px;background:linear-gradient(145deg,#fffdf8,#f5eddb);box-shadow:0 12px 34px #5c45141c}.label{font-size:12px;color:#887a5d;text-transform:uppercase;letter-spacing:.13em;text-align:center}.verse{direction:rtl;text-align:center;font:2rem/2.1 Georgia,serif;padding:15px 3px}.word{display:inline-block;margin:2px;padding:2px 6px;border:1px solid transparent;border-radius:10px;color:#453b30;transition:.22s}.word.hit{background:linear-gradient(135deg,#fff2c4,#f6df9d);border-color:#d0ad5540;color:#73540d;box-shadow:0 3px 12px #a77b2018}.word.active{background:linear-gradient(135deg,#ffeaa4,#f4d36e);border-color:#b07f1880;box-shadow:0 0 0 3px #dcb44d25,0 0 22px #d5a83570;transform:translateY(-2px) scale(1.04);animation:glow 1.4s ease-in-out infinite alternate}.word.missed{background:#f7e5df;border-color:#c66b5438;color:#8e3829}@keyframes glow{to{box-shadow:0 0 0 4px #dcb44d30,0 0 25px #d5a83580}}.meter{height:5px;border-radius:99px;background:#eee7d9;overflow:hidden}.meter span{display:block;height:100%;width:0;background:linear-gradient(90deg,#c9a227,#efcf69);transition:width .25s}.status{display:flex;align-items:center;justify-content:center;gap:8px;color:#625844;min-height:28px}.dot{width:9px;height:9px;border-radius:50%;background:#a89c83}.dot.live{background:#45a16d;box-shadow:0 0 0 5px #45a16d20;animation:pulse 1.4s infinite}.dot.talking{background:#c9a227;box-shadow:0 0 0 5px #c9a22722}@keyframes pulse{50%{box-shadow:0 0 0 9px #45a16d08}}.buttons{display:flex;justify-content:center;gap:10px;flex-wrap:wrap;margin-top:16px}button{padding:12px 20px;border:0;border-radius:999px;background:#c9a227;color:#241c17;font-weight:700;cursor:pointer}button.stop{background:#8c473c;color:white}button:disabled{opacity:.5;cursor:not-allowed}#transcript{min-height:28px;margin-top:12px;text-align:center;direction:rtl;color:#655832;overflow-wrap:anywhere}.review{display:none;margin-top:16px;padding:12px;border-radius:14px;background:#fffdf7;border:1px solid #e6dcc8;text-align:center}.review.show{display:block}.tip{font-size:12px;line-height:1.55;text-align:center;color:#766e60;margin:12px 0 0}.legend{display:flex;justify-content:center;gap:14px;font-size:11px;color:#766e60;margin:4px 0 10px}.legend b{color:#8a650d}.legend .miss{color:#9e453d}
</style></head><body><main class="card"><div class="label">Live recitation · Surah __SURAH__ · Ayah __AYAH__</div><div class="verse" id="verse" lang="ar" dir="rtl"></div><div class="legend"><span><b>Gold</b> recognised</span><span class="miss"><b>Rose</b> not matched in transcript</span></div><div class="meter" aria-label="Recognised words"><span id="progress"></span></div><div class="status" role="status" aria-live="polite"><i id="dot" class="dot"></i><span id="state">Ready when you are</span></div><div id="transcript" lang="ar"></div><div class="review" id="review" aria-live="polite"></div><div class="buttons"><button id="start">Start listening</button><button id="stop" class="stop" disabled>End session &amp; review</button></div><p class="tip">Allow microphone access. Headphones help prevent feedback. Speak naturally; the AI coach responds after pauses. Transcript matching is approximate and is not Tajweed grading. Your audio is streamed to Gemini while the session is active.</p></main>
<script>
const TOKEN=__TOKEN__, MODEL=__MODEL__, WORDS=__WORDS__;
const verseEl=document.getElementById('verse'), progressEl=document.getElementById('progress'), stateEl=document.getElementById('state'), dotEl=document.getElementById('dot'), transcriptEl=document.getElementById('transcript'), startBtn=document.getElementById('start'), stopBtn=document.getElementById('stop'), reviewEl=document.getElementById('review');
let elements=[],ws=null,stream=null,ctx=null,processor=null,source=null,monitor=null,active=false,ready=false,playedUntil=0,allTranscript='',lastInput='';
const norm=s=>s.replace(/[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]/g,'').replace(/[إأآٱ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه').replace(/[^\u0621-\u064A\s]/g,' ').replace(/\s+/g,' ').trim();
const expected=WORDS.map(w=>norm(w).replace(/\s/g,''));
function renderWords(){verseEl.replaceChildren();elements=WORDS.map((word,i)=>{const span=document.createElement('span');span.className='word';span.textContent=word;span.setAttribute('aria-label','Ayah word '+(i+1));verseEl.appendChild(span);return span;});}
function status(text,kind=''){stateEl.textContent=text;dotEl.className='dot '+kind;}
function mergeTranscript(previous,next){previous=norm(previous);next=norm(next);if(!previous)return next;if(!next)return previous;if(next.startsWith(previous))return next;if(previous.endsWith(next))return previous;let overlap=Math.min(previous.length,next.length);while(overlap>0&&previous.slice(-overlap)!==next.slice(0,overlap))overlap--;return (previous+' '+next.slice(overlap)).trim();}
function editDistance(a,b){let row=Array.from({length:b.length+1},(_,i)=>i);for(let i=1;i<=a.length;i++){const next=[i];for(let j=1;j<=b.length;j++)next[j]=Math.min(next[j-1]+1,row[j]+1,row[j-1]+(a[i-1]===b[j-1]?0:1));row=next;}return row[b.length];}
function wordScore(a,b){if(a===b)return 3;if((b.length>=2&&a.startsWith(b))||(a.length>=3&&b.startsWith(a)))return 1;if(Math.min(a.length,b.length)>=3&&Math.abs(a.length-b.length)<=1&&editDistance(a,b)<=1)return 1;return -2;}
function alignment(text,final=false){const heard=norm(text).split(' ').filter(Boolean),n=expected.length,m=heard.length;const dp=Array.from({length:n+1},()=>Array(m+1).fill(0));const back=Array.from({length:n+1},()=>Array(m+1).fill(''));for(let i=1;i<=n;i++){dp[i][0]=-2*i;back[i][0]='up';}for(let j=1;j<=m;j++){dp[0][j]=-2*j;back[0][j]='left';}for(let i=1;i<=n;i++)for(let j=1;j<=m;j++){const diag=dp[i-1][j-1]+wordScore(expected[i-1],heard[j-1]),up=dp[i-1][j]-2,left=dp[i][j-1]-2;const best=Math.max(diag,up,left);dp[i][j]=best;back[i][j]=best===diag?'diag':best===up?'up':'left';}const states=Array(n).fill('pending');let i=n,j=m;while(i||j){if(i&&j&&back[i][j]==='diag'){const score=wordScore(expected[i-1],heard[j-1]);states[i-1]=score>=3?'correct':score>0?'close':'missed';i--;j--;}else if(i&&(!j||back[i][j]==='up')){states[i-1]='missed';i--;}else j--;}
// Live interim text can be revised, so leave unmatched trailing words pending until final review.
if(!final){let last=-1;for(let k=0;k<n;k++)if(states[k]==='correct'||states[k]==='close')last=k;for(let k=last+1;k<n;k++)states[k]='pending';}
return states;}
function updateWords(text,final=false){const states=alignment(text,final);let matched=0,last=-1;for(let i=0;i<states.length;i++){const old=elements[i].classList.contains('hit');const hit=states[i]==='correct'||states[i]==='close';if(hit)matched++;if(hit)last=i;elements[i].classList.toggle('hit',hit||(!final&&old));elements[i].classList.toggle('missed',final&&states[i]==='missed');elements[i].classList.toggle('active',!final&&hit&&i===last);}progressEl.style.width=(WORDS.length?Math.round(matched/WORDS.length*100):0)+'%';return {states,matched};}
function decode64(s){const raw=atob(s),bytes=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);return bytes;}
function playPcm(encoded){if(!ctx)return;const bytes=decode64(encoded),pcm=new Int16Array(bytes.buffer,bytes.byteOffset,Math.floor(bytes.byteLength/2));const buffer=ctx.createBuffer(1,pcm.length,24000),data=buffer.getChannelData(0);for(let i=0;i<pcm.length;i++)data[i]=pcm[i]/32768;const node=ctx.createBufferSource();node.buffer=buffer;node.connect(ctx.destination);playedUntil=Math.max(ctx.currentTime,playedUntil);node.start(playedUntil);playedUntil+=buffer.duration;status('AI coach speaking · you can interrupt','talking');node.onended=()=>{if(active&&ctx.currentTime>=playedUntil-.05)status('Listening · recite or ask a question','live');};}
function handleMessage(event){let m;try{m=JSON.parse(event.data);}catch{return;}if(m.setupComplete){ready=true;status('Listening · recite or ask a question','live');return;}const content=m.serverContent;if(!content)return;const input=content.inputTranscription?.text;if(input){if(input===lastInput)return;lastInput=input;allTranscript=mergeTranscript(allTranscript,input);transcriptEl.textContent=allTranscript;updateWords(allTranscript);}const output=content.outputTranscription?.text;if(output)transcriptEl.textContent=(allTranscript?allTranscript+' · ':'')+'AI: '+output;for(const part of content.modelTurn?.parts||[]){const audio=part.inlineData||part.inline_data;if(audio?.data&&(audio.mimeType||audio.mime_type||'').includes('audio/pcm'))playPcm(audio.data);}if(content.interrupted){playedUntil=ctx?.currentTime||0;status('Listening · go ahead','live');}if(content.turnComplete&&active)status('Listening · recite or ask a question','live');}
function pcm16(input){const out=new Int16Array(input.length);for(let i=0;i<input.length;i++){const x=Math.max(-1,Math.min(1,input[i]));out[i]=x<0?x*32768:x*32767;}return out;}
function resample(input,from,to){if(from===to)return input;const step=from/to,length=Math.floor(input.length/step),out=new Float32Array(length);for(let i=0;i<length;i++){const p=i*step,l=Math.floor(p),r=Math.min(l+1,input.length-1),f=p-l;out[i]=input[l]*(1-f)+input[r]*f;}return out;}
function b64(bytes){let text='';for(let i=0;i<bytes.length;i+=0x8000)text+=String.fromCharCode(...bytes.subarray(i,i+0x8000));return btoa(text);}
function finishReview(){if(!allTranscript){reviewEl.textContent='No readable transcript was captured, so no word comparison is available. You can still ask the voice coach to repeat or try again.';reviewEl.classList.add('show');return;}const result=updateWords(allTranscript,true),percent=WORDS.length?Math.round(result.matched/WORDS.length*100):0;reviewEl.textContent=`Transcript match: ${result.matched} of ${WORDS.length} words (${percent}%). This is an approximate speech-to-text comparison, not a recitation or Tajweed accuracy score.`;reviewEl.classList.add('show');try{const key='quran-live-practice-v1';const history=JSON.parse(localStorage.getItem(key)||'[]');history.unshift({date:new Date().toISOString(),surah:__SURAH__,ayah:__AYAH__,matched:result.matched,total:WORDS.length,transcriptMatch:percent});localStorage.setItem(key,JSON.stringify(history.slice(0,20)));}catch{}}
async function start(){startBtn.disabled=true;reviewEl.classList.remove('show');setStatus('Requesting microphone…');try{stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});ctx=new(window.AudioContext||window.webkitAudioContext)();await ctx.resume();const url='wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained?access_token='+encodeURIComponent(TOKEN);ws=new WebSocket(url);active=true;ready=false;allTranscript='';lastInput='';renderWords();transcriptEl.textContent='';ws.onopen=()=>ws.send(JSON.stringify({setup:{model:MODEL,generationConfig:{responseModalities:['AUDIO']},systemInstruction:{parts:[{text:'You are a careful, kind Quran recitation practice assistant. Listen without interrupting continuous recitation. When the student pauses naturally, offer one brief observation grounded only in the audio actually heard. Never invent a missed word, pronunciation error, Tajweed fault, numeric score, or certainty. If unclear, say so and ask them to repeat a short phrase. Speak clearly in English, allow interruption, and stop speaking if the student starts. You are AI, not a human teacher or scholar.'}]},inputAudioTranscription:{},outputAudioTranscription:{}}));ws.onmessage=handleMessage;ws.onerror=()=>setStatus('Connection failed. Check Gemini Live API access and try again.');ws.onclose=()=>{if(active){status('Connection ended. Review is ready below.');cleanup(false);finishReview();}};ws.addEventListener('message',function onReady(e){let m;try{m=JSON.parse(e.data);}catch{return;}if(!m.setupComplete||!active||processor)return;ws.removeEventListener('message',onReady);ready=true;source=ctx.createMediaStreamSource(stream);processor=ctx.createScriptProcessor(4096,1,1);monitor=ctx.createGain();monitor.gain.value=0;processor.onaudioprocess=e=>{if(!active||!ready||ws?.readyState!==WebSocket.OPEN)return;const samples=resample(e.inputBuffer.getChannelData(0),ctx.sampleRate,16000),pcm=pcm16(samples);ws.send(JSON.stringify({realtimeInput:{mediaChunks:[{mimeType:'audio/pcm;rate=16000',data:b64(new Uint8Array(pcm.buffer))}]}}));};source.connect(processor);processor.connect(monitor);monitor.connect(ctx.destination);status('Listening · recite or ask a question','live');});stopBtn.disabled=false;}catch(e){setStatus(e?.message||'Could not start. Allow microphone access and try again.');cleanup(false);}}
function cleanup(show){active=false;ready=false;if(processor){processor.disconnect();processor.onaudioprocess=null;processor=null;}if(source){source.disconnect();source=null;}if(monitor){monitor.disconnect();monitor=null;}if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}if(ws){ws.onclose=null;try{ws.close();}catch{}ws=null;}if(ctx){ctx.close().catch(()=>{});ctx=null;}playedUntil=0;startBtn.disabled=false;stopBtn.disabled=true;if(show){status('Session ended · reviewing transcript');finishReview();}}
renderWords();startBtn.addEventListener('click',start);stopBtn.addEventListener('click',()=>cleanup(true));window.addEventListener('beforeunload',()=>cleanup(false));
</script></body></html>"""

if st.button("Create secure live lesson", type="primary"):
    try:
        with st.spinner("Creating a single-use, short-lived live session…"):
            token = issue_token()
        page = PAGE.replace("__TOKEN__", json.dumps(token)).replace("__MODEL__", json.dumps(f"models/{MODEL}"))
        page = page.replace("__WORDS__", json.dumps([word for word in verse.split() if word], ensure_ascii=True))
        page = page.replace("__SURAH__", str(int(surah))).replace("__AYAH__", str(int(ayah)))
        components.html(page, height=650, scrolling=False)
        st.caption("Transcript reviews are kept in this browser only (up to 20 entries). Raw audio is not saved by this page. Start a fresh lesson if the page reloads.")
    except (requests.RequestException, RuntimeError) as error:
        st.error(str(error))
else:
    st.caption("Choose the ayah and create a lesson to get a secure, one-use connection token. Microphone permission is requested only when you start listening.")

st.caption(f"Live model: {MODEL}. Availability depends on your Google project. Set GEMINI_LIVE_MODEL in Streamlit secrets to a currently supported Gemini Live model.")
