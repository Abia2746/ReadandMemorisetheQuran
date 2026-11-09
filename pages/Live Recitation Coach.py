import datetime as dt
import html
import json
import re

import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Live Recitation Coach", page_icon="✨", layout="centered")
st.title("✨ Live Recitation Coach")
st.write("A focused practice loop: recite, review an approximate word match, get a short AI coaching response, then retry.")
st.caption("AI study aid only — not a human teacher, certified Tajweed assessment, or replacement for a qualified Quran teacher.")

API_KEY = st.secrets.get("GEMINI_API_KEY", "")
MODEL = st.secrets.get("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025")

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        surah = st.number_input("Surah", min_value=1, max_value=114, value=1, step=1)
    with col2:
        ayah = st.number_input("Ayah", min_value=1, max_value=286, value=1, step=1)
    learner = st.text_input("Practice profile (saved only in this browser)", value="Learner", max_chars=32)
    mode = st.radio("Workspace", ["Learner practice", "Teacher review"], horizontal=True)
    level = st.selectbox("Practice level", ["New learner", "Building confidence", "Confident reciter"], index=0)
    style = st.selectbox("Coach style", ["Gentle encouragement", "Focused and specific"], index=0)

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

st.markdown(
    f"<div dir='rtl' style='font-family:serif;font-size:2rem;line-height:2.1;text-align:center;padding:1rem;background:#fffdf8;border:1px solid #ece0c7;border-radius:18px'>{html.escape(verse)}</div>",
    unsafe_allow_html=True,
)
st.caption("The live gold highlight and ayah practice score are based on speech-to-text alignment only. They do not measure makharij, madd, ghunnah, or overall Tajweed accuracy.")

if mode == "Teacher review":
    st.info("Teacher review shows the practice records saved in this browser profile. It does not upload recordings or create a teacher account; review feedback with a qualified Quran teacher.")

if not API_KEY:
    st.error("Add GEMINI_API_KEY to Streamlit secrets to enable the live voice coach. The long-lived API key remains on the server; only a short-lived, single-use session token is sent to the browser.")
    st.stop()


def issue_token() -> str:
    now = dt.datetime.now(dt.timezone.utc)
    teacher_direction = (
        "Act as an instructional facilitator: prompt one small recitation goal, wait for the learner, "
        "then give one evidence-based observation and invite a retry."
        if mode == "Teacher review"
        else "Coach the learner directly with one short, encouraging, actionable observation after a natural pause."
    )
    prompt = (
        "You are a careful Quran recitation practice assistant. The learner is working on "
        f"Surah {int(surah)}, ayah {int(ayah)}: {verse}. Their level is {level}; style is {style}. "
        f"{teacher_direction} Ground every comment only in audio you actually heard. Never invent errors, skipped words, "
        "makharij faults, or Tajweed mistakes. Do not provide a numeric score or claim certified assessment. "
        "If speech is unclear, say so and ask for a short repeat. Answer direct questions briefly in clear English. "
        "You are an AI, not a human teacher or qualified scholar; recommend a qualified scholar for religious rulings. "
        "Allow natural interruption and stop speaking when the learner starts talking again."
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


words = [word for word in verse.split() if word]
profile_key = re.sub(r"[^a-z0-9_-]+", "-", learner.strip().lower()).strip("-")[:32] or "learner"

PAGE = r"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
*{box-sizing:border-box}body{margin:0;padding:8px;background:#faf6ec;color:#302719;font:15px system-ui,sans-serif}.card{padding:18px;border:1px solid #e6dcc8;border-radius:22px;background:linear-gradient(145deg,#fffdf8,#f5eddb);box-shadow:0 12px 34px #5c45141c}.label{font-size:12px;color:#887a5d;text-transform:uppercase;letter-spacing:.13em;text-align:center}.verse{direction:rtl;text-align:center;font:2rem/2.1 Georgia,serif;padding:16px 3px}.word{display:inline-block;margin:2px;padding:3px 7px;border:1px solid transparent;border-radius:10px;color:#453b30;transition:.22s}.word.hit{background:linear-gradient(135deg,#fff2c4,#f6df9d);border-color:#d0ad5540;color:#73540d;box-shadow:0 3px 12px #a77b2018}.word.active{background:linear-gradient(135deg,#ffeaa4,#f4d36e);border-color:#b07f1880;box-shadow:0 0 0 3px #dcb44d25,0 0 22px #d5a83570;transform:translateY(-2px) scale(1.04);animation:glow 1.4s ease-in-out infinite alternate}.word.missed{background:#f7e5df;border-color:#c66b5438;color:#8e3829}@keyframes glow{to{box-shadow:0 0 0 4px #dcb44d30,0 0 25px #d5a83580}}.meter{height:5px;border-radius:99px;background:#eee7d9;overflow:hidden}.meter span{display:block;height:100%;width:0;background:linear-gradient(90deg,#c9a227,#efcf69);transition:width .25s}.status{display:flex;align-items:center;justify-content:center;gap:8px;color:#625844;min-height:28px}.dot{width:9px;height:9px;border-radius:50%;background:#a89c83}.dot.live{background:#45a16d;box-shadow:0 0 0 5px #45a16d20;animation:pulse 1.4s infinite}.dot.talking{background:#c9a227;box-shadow:0 0 0 5px #c9a22722}@keyframes pulse{50%{box-shadow:0 0 0 9px #45a16d08}}.btns{display:flex;justify-content:center;gap:10px;flex-wrap:wrap;margin-top:16px}button{padding:11px 17px;border:0;border-radius:999px;background:#c9a227;color:#241c17;font-weight:700;cursor:pointer}button.stop{background:#8c473c;color:white}button.secondary{background:#eee7d9;color:#332d29}button:disabled{opacity:.5;cursor:not-allowed}.review{margin-top:16px;padding:14px;border-radius:14px;background:#fffdf7;border:1px solid #e6dcc8;display:none}.review.show{display:block}.tip{font-size:12px;line-height:1.55;text-align:center;color:#766e60;margin:12px 0 0}#transcript{min-height:30px;margin-top:12px;text-align:center;direction:rtl;color:#655832;overflow-wrap:anywhere}.legend{display:flex;justify-content:center;gap:14px;font-size:11px;color:#766e60;margin:4px 0 10px}.legend b{color:#8a650d}.legend .miss{color:#9e453d}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0}.stat{background:#fffdf7;border:1px solid #ece3d1;border-radius:13px;padding:10px;text-align:center}.stat strong{display:block;font-size:20px;color:#896713}.stat small{color:#766e60}.attempt{margin-top:8px;padding:10px;border:1px solid #eee5d4;border-radius:12px;background:#fffdf9}.attempt summary{cursor:pointer;font-weight:600}.attempt p{margin:7px 0;font-size:13px;line-height:1.5;overflow-wrap:anywhere}.warn{color:#8e3829}.ok{color:#2e7d5b}.history-empty{font-size:13px;color:#766e60;text-align:center;padding:10px}
</style></head><body><main class="card"><div class="label">__MODE__ · Surah __SURAH__ · Ayah __AYAH__</div><div class="verse" id="verse" lang="ar" dir="rtl"></div><div class="legend"><span><b>Gold</b> matched by transcript</span><span class="miss"><b>Rose</b> not matched</span></div><div class="meter"><span id="progress"></span></div><div class="status" role="status" aria-live="polite"><i id="dot" class="dot"></i><span id="state">Ready when you are</span></div><div id="transcript" lang="ar"></div><div class="review" id="review"></div><div class="btns"><button id="start">Start practice</button><button id="retry" class="secondary" hidden>Retry this ayah</button><button id="stop" class="stop" disabled>End session &amp; review</button></div><p class="tip">Gold highlights and the practice score reflect approximate Arabic speech-to-text alignment only—not makharij, Tajweed, or certified assessment. Audio is streamed to Gemini during the live session. Local history can be cleared below.</p></main><section class="card" style="margin-top:12px"><div class="label">Progress · saved in this browser only</div><div class="stats"><div class="stat"><strong id="streak">0</strong><small>day streak</small></div><div class="stat"><strong id="attemptCount">0</strong><small>practice attempts</small></div><div class="stat"><strong id="bestScore">—</strong><small>best transcript match</small></div></div><div id="history"></div><div class="btns"><button id="clearHistory" class="secondary">Clear local history</button></div></section>
<script>
const WORDS=__WORDS__,TOKEN=__TOKEN__,MODEL=__MODEL__,PROFILE=__PROFILE__,MODE=__MODE__;
const verseEl=document.getElementById('verse'),progressEl=document.getElementById('progress'),stateEl=document.getElementById('state'),dotEl=document.getElementById('dot'),transcriptEl=document.getElementById('transcript'),reviewEl=document.getElementById('review'),startBtn=document.getElementById('start'),retryBtn=document.getElementById('retry'),stopBtn=document.getElementById('stop');
const storageKey='quran-live-practice-v2-'+PROFILE;
function norm(s){return(s||'').replace(/[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]/g,'').replace(/[إأآٱ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه').replace(/[^\u0621-\u064A\s]/g,' ').replace(/\s+/g,' ').trim();}
const expected=WORDS.map(w=>norm(w).replace(/\s/g,''));let elements=[],ws=null,stream=null,ctx=null,processor=null,source=null,monitor=null,active=false,ready=false,played=[],allTranscript='',lastInput='';
function loadHistory(){try{const value=JSON.parse(localStorage.getItem(storageKey)||'[]');return Array.isArray(value)?value:[];}catch(e){return[];}}
function saveHistory(items){try{localStorage.setItem(storageKey,JSON.stringify(items.slice(0,100)));}catch(e){setStatus('Browser storage is full; this practice was not saved.','');}}
function renderDashboard(){const items=loadHistory();document.getElementById('attemptCount').textContent=items.length;const scores=items.map(x=>Number(x.score)||0);document.getElementById('bestScore').textContent=scores.length?Math.max(...scores)+'%':'—';const days=[...new Set(items.map(x=>x.day).filter(Boolean))].sort().reverse();let streak=0;if(days.length){let date=new Date();date.setHours(0,0,0,0);const today=date.toISOString().slice(0,10);if(days[0]!==today)date.setDate(date.getDate()-1);for(const day of days){if(day===date.toISOString().slice(0,10)){streak++;date.setDate(date.getDate()-1);}else break;}}document.getElementById('streak').textContent=streak;const history=document.getElementById('history');history.replaceChildren();if(!items.length){const empty=document.createElement('div');empty.className='history-empty';empty.textContent='No attempts saved for this profile yet. Finish a recitation to begin tracking.';history.appendChild(empty);return;}for(const item of items.slice(0,8)){const details=document.createElement('details');details.className='attempt';const summary=document.createElement('summary');summary.textContent=`${item.day||'Practice'} · Surah ${item.surah}, Ayah ${item.ayah} · transcript ${item.score}%`;const body=document.createElement('div');const verdict=document.createElement('p');verdict.textContent=`Exact ${item.exact||0} · close ${item.close||0} · not matched ${item.missed||0} · extra ${item.extra||0}`;const target=document.createElement('p');target.className=item.missed?'warn':'ok';target.textContent=item.missedWords?.length?`Review next: ${item.missedWords.join(' · ')}`:'No unmatched expected words in this transcript. This does not certify recitation accuracy.';const heard=document.createElement('p');heard.dir='rtl';heard.textContent=`Transcript: ${item.transcript||'(none)'}`;body.append(verdict,target,heard);details.append(summary,body);history.appendChild(details);}}
function renderWords(){verseEl.replaceChildren();elements=WORDS.map((word,i)=>{const span=document.createElement('span');span.className='word';span.textContent=word;span.setAttribute('aria-label','word '+(i+1));verseEl.appendChild(span);return span;});}
function setStatus(text,kind=''){stateEl.textContent=text;dotEl.className='dot '+kind;}
function mergeTranscript(previous,next){previous=norm(previous);next=norm(next);if(!previous)return next;if(!next)return previous;if(next.startsWith(previous))return next;if(previous.endsWith(next))return previous;let overlap=Math.min(previous.length,next.length);while(overlap>0&&previous.slice(-overlap)!==next.slice(0,overlap))overlap--;return(previous+' '+next.slice(overlap)).trim();}
function editDistance(a,b){let row=Array.from({length:b.length+1},(_,i)=>i);for(let i=1;i<=a.length;i++){const next=[i];for(let j=1;j<=b.length;j++)next[j]=Math.min(next[j-1]+1,row[j]+1,row[j-1]+(a[i-1]===b[j-1]?0:1));row=next;}return row[b.length];}
function wordScore(a,b){if(a===b)return 3;if((b.length>=2&&a.startsWith(b))||(a.length>=3&&b.startsWith(a)))return 1;if(Math.min(a.length,b.length)>=3&&Math.abs(a.length-b.length)<=1&&editDistance(a,b)<=1)return 1;return-2;}
function align(text,final=false){const heard=norm(text).split(' ').filter(Boolean),n=expected.length,m=heard.length;const dp=Array.from({length:n+1},()=>Array(m+1).fill(0)),back=Array.from({length:n+1},()=>Array(m+1).fill(''));for(let i=1;i<=n;i++){dp[i][0]=-2*i;back[i][0]='up';}for(let j=1;j<=m;j++){dp[0][j]=-2*j;back[0][j]='left';}for(let i=1;i<=n;i++)for(let j=1;j<=m;j++){const diagonal=dp[i-1][j-1]+wordScore(expected[i-1],heard[j-1]),up=dp[i-1][j]-2,left=dp[i][j-1]-2,best=Math.max(diagonal,up,left);dp[i][j]=best;back[i][j]=best===diagonal?'diag':best===up?'up':'left';}let i=n,j=m;const states=Array(n).fill('pending');while(i>0||j>0){if(i>0&&j>0&&back[i][j]==='diag'){const score=wordScore(expected[i-1],heard[j-1]);states[i-1]=score>=3?'correct':score>0?'close':'missed';i--;j--;}else if(i>0&&back[i][j]==='up'){states[i-1]='missed';i--;}else if(j>0)j--;}
if(!final){let last=-1;for(let k=0;k<n;k++)if(states[k]==='correct'||states[k]==='close')last=k;for(let k=last+1;k<n;k++)states[k]='pending';}return{states,heard};}
function updateWords(text,final=false){const result=align(text,final),states=result.states;let exact=0,close=0,last=-1;for(let i=0;i<states.length;i++){const hit=states[i]==='correct'||states[i]==='close';if(states[i]==='correct')exact++;if(states[i]==='close')close++;if(hit)last=i;elements[i].classList.toggle('hit',hit||(!final&&elements[i].classList.contains('hit')));elements[i].classList.toggle('missed',final&&states[i]==='missed');elements[i].classList.toggle('active',!final&&hit&&i===last);}const extras=Math.max(0,result.heard.length-states.filter(s=>s==='correct'||s==='close'||s==='missed').length);const weighted=exact+close*.65;const score=WORDS.length?Math.max(0,Math.min(100,Math.round((weighted-.15*extras)/WORDS.length*100))):0;progressEl.style.width=score+'%';return{states,exact,close,missed:states.filter(s=>s==='missed').length,extras,score,missedWords:states.map((s,i)=>s==='missed'?WORDS[i]:null).filter(Boolean)};}
function decode64(s){const raw=atob(s),bytes=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);return bytes;}
function stopPlayback(){played.forEach(node=>{try{node.stop();}catch(e){}});played=[];}
function playPcm(encoded){if(!ctx)return;const bytes=decode64(encoded),pcm=new Int16Array(bytes.buffer,bytes.byteOffset,Math.floor(bytes.byteLength/2)),buffer=ctx.createBuffer(1,pcm.length,24000),data=buffer.getChannelData(0);for(let i=0;i<pcm.length;i++)data[i]=pcm[i]/32768;const node=ctx.createBufferSource();node.buffer=buffer;node.connect(ctx.destination);node.start();played.push(node);setStatus('AI coach speaking · you can interrupt','talking');node.onended=()=>{played=played.filter(item=>item!==node);if(active&&played.length===0)setStatus('Listening · recite or ask a question','live');};}
function onMessage(event){let m;try{m=JSON.parse(event.data);}catch{return;}if(m.setupComplete){ready=true;setStatus('Listening · recite or ask a question','live');return;}const content=m.serverContent;if(!content)return;if(content.interrupted){stopPlayback();setStatus('Listening · go ahead','live');}const input=content.inputTranscription?.text;if(input&&input!==lastInput){lastInput=input;allTranscript=mergeTranscript(allTranscript,input);transcriptEl.textContent=allTranscript;updateWords(allTranscript);}const output=content.outputTranscription?.text;if(output)transcriptEl.textContent=(allTranscript?allTranscript+' · ':'')+'AI: '+output;for(const part of content.modelTurn?.parts||[]){const audio=part.inlineData||part.inline_data;if(audio?.data&&(audio.mimeType||audio.mime_type||'').includes('audio/pcm'))playPcm(audio.data);}if(content.turnComplete&&active&&!played.length)setStatus('Listening · recite or ask a question','live');}
function pcm16(input){const out=new Int16Array(input.length);for(let i=0;i<input.length;i++){const x=Math.max(-1,Math.min(1,input[i]));out[i]=x<0?x*32768:x*32767;}return out;}
function resample(input,from,to){if(from===to)return input;const step=from/to,length=Math.floor(input.length/step),out=new Float32Array(length);for(let i=0;i<length;i++){const p=i*step,l=Math.floor(p),r=Math.min(l+1,input.length-1),f=p-l;out[i]=input[l]*(1-f)+input[r]*f;}return out;}
function b64(bytes){let text='';for(let i=0;i<bytes.length;i+=0x8000)text+=String.fromCharCode(...bytes.subarray(i,i+0x8000));return btoa(text);}
function showReview(){if(!allTranscript){reviewEl.textContent='No readable transcript was captured. Check the microphone and try a shorter phrase.';reviewEl.classList.add('show');return;}const result=updateWords(allTranscript,true);reviewEl.replaceChildren();const title=document.createElement('strong');title.textContent=`Ayah transcript match · ${result.score}%`;const detail=document.createElement('p');detail.textContent=`${result.exact} exact · ${result.close} close · ${result.missed} not matched · ${result.extras} extra recognized words.`;const caution=document.createElement('p');caution.textContent='This is an alignment-based transcript practice score only; it does not assess pronunciation or Tajweed.';const drill=document.createElement('p');drill.textContent=result.missedWords.length?`Next drill: repeat the phrase around “${result.missedWords.slice(0,3).join(' · ')}” slowly, then retry.`:'Next drill: recite again at a steady pace and compare the transcript. No unmatched expected words were detected.';reviewEl.append(title,detail,caution,drill);reviewEl.classList.add('show');const item={day:new Date().toISOString().slice(0,10),time:new Date().toISOString(),surah:__SURAH__,ayah:__AYAH__,score:result.score,exact:result.exact,close:result.close,missed:result.missed,extra:result.extras,missedWords:result.missedWords,transcript:allTranscript};const history=loadHistory();history.unshift(item);saveHistory(history);renderDashboard();}
async function start(){startBtn.disabled=true;retryBtn.disabled=true;reviewEl.classList.remove('show');setStatus('Requesting microphone…');try{stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});ctx=new(window.AudioContext||window.webkitAudioContext)();await ctx.resume();const url='wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained?access_token='+encodeURIComponent(TOKEN);ws=new WebSocket(url);active=true;ready=false;allTranscript='';lastInput='';played=[];renderWords();transcriptEl.textContent='';ws.onopen=()=>ws.send(JSON.stringify({setup:{model:MODEL,generationConfig:{responseModalities:['AUDIO']},systemInstruction:{parts:[{text:'You are a calm, concise Quran recitation coach. Listen without interrupting continuous recitation. After a natural pause, offer one brief observation grounded only in the audio you actually heard. Never invent a missed word, Tajweed fault, pronunciation error, numeric score, or certainty. If unclear, say so and ask for a short repeat. Speak clear English. Allow interruption and stop speaking immediately when the student begins.'}]},inputAudioTranscription:{},outputAudioTranscription:{}}));ws.onmessage=onMessage;ws.onerror=()=>setStatus('Connection failed. Check Live API model access and try again.');ws.onclose=()=>{if(active){setStatus('Connection ended · review is ready');cleanup(false);showReview();}};ws.addEventListener('message',function onReady(event){let msg;try{msg=JSON.parse(event.data);}catch{return;}if(!msg.setupComplete||!active||processor)return;ws.removeEventListener('message',onReady);ready=true;source=ctx.createMediaStreamSource(stream);processor=ctx.createScriptProcessor(4096,1,1);monitor=ctx.createGain();monitor.gain.value=0;processor.onaudioprocess=event=>{if(!active||!ready||ws?.readyState!==WebSocket.OPEN)return;const samples=resample(event.inputBuffer.getChannelData(0),ctx.sampleRate,16000),pcm=pcm16(samples);ws.send(JSON.stringify({realtimeInput:{mediaChunks:[{mimeType:'audio/pcm;rate=16000',data:b64(new Uint8Array(pcm.buffer))}]}}));};source.connect(processor);processor.connect(monitor);monitor.connect(ctx.destination);setStatus('Listening · recite or ask a question','live');});stopBtn.disabled=false;}catch(error){setStatus(error?.message||'Could not start. Allow microphone access and try again.');cleanup(false);}}
function cleanup(show){active=false;ready=false;stopPlayback();if(processor){processor.disconnect();processor.onaudioprocess=null;processor=null;}if(source){source.disconnect();source=null;}if(monitor){monitor.disconnect();monitor=null;}if(stream){stream.getTracks().forEach(track=>track.stop());stream=null;}if(ws){ws.onclose=null;try{ws.close();}catch(e){}ws=null;}if(ctx){ctx.close().catch(()=>{});ctx=null;}startBtn.disabled=false;retryBtn.disabled=false;stopBtn.disabled=true;if(show)setStatus('Session ended · reviewing transcript');}
function clearHistory(){if(!confirm('Clear all practice scores and correction history for this browser profile?'))return;localStorage.removeItem(storageKey);renderDashboard();reviewEl.classList.remove('show');setStatus('Local practice history cleared');}
renderWords();renderDashboard();startBtn.addEventListener('click',start);retryBtn.addEventListener('click',start);stopBtn.addEventListener('click',()=>{cleanup(true);showReview();});document.getElementById('clearHistory').addEventListener('click',clearHistory);window.addEventListener('beforeunload',()=>cleanup(false));
</script></body></html>"""

if st.button("Create live practice session", type="primary"):
    try:
        with st.spinner("Creating a one-use, short-lived live session…"):
            token = issue_token()
        final_page = PAGE.replace("__TOKEN__", json.dumps(token)).replace("__MODEL__", json.dumps(f"models/{MODEL}"))
        final_page = final_page.replace("__WORDS__", json.dumps(words, ensure_ascii=True))
        final_page = final_page.replace("__SURAH__", str(int(surah))).replace("__AYAH__", str(int(ayah)))
        final_page = final_page.replace("__PROFILE__", json.dumps(profile_key))
        final_page = final_page.replace("__MODE__", html.escape(mode))
        components.html(final_page, height=920, scrolling=True)
        st.caption("Score model = weighted word alignment (exact, close, missing, and extra transcript tokens). Streaks and correction history stay in this browser profile; raw audio is not saved by this page.")
    except (requests.RequestException, RuntimeError) as error:
        st.error(str(error))
else:
    st.caption("Build a lesson session to start live listening, score transcript alignment, review corrections, and retry. Teacher review can inspect records saved for the selected browser profile.")

st.caption(f"Live model: {MODEL}. Availability depends on your Google project and may change; set GEMINI_LIVE_MODEL in Streamlit secrets to a currently supported Gemini Live model.")
