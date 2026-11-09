import datetime as dt
import html
import json

import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Live Recitation Coach", page_icon="✨", layout="centered")
st.title("✨ Live Recitation Coach")
st.write("Recite an ayah aloud: recognised words glow as you go, and the AI voice coach can respond when you pause.")
st.caption("AI study aid only — not a human teacher, certified Tajweed assessment, or replacement for a qualified Quran teacher.")

API_KEY = st.secrets.get("GEMINI_API_KEY", "")
MODEL = st.secrets.get("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025")

col1, col2 = st.columns(2)
with col1:
    surah = st.number_input("Surah", min_value=1, max_value=114, value=1, step=1)
with col2:
    ayah = st.number_input("Ayah", min_value=1, max_value=286, value=1, step=1)

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
st.caption("The live highlight follows speech recognition and may lag, miss words, or vary by browser, microphone, and recitation style.")

if not API_KEY:
    st.error("Add GEMINI_API_KEY to Streamlit secrets to enable the live voice coach. The long-lived API key remains on the server; only a short-lived, single-use session token is sent to the browser.")
    st.stop()


def issue_token() -> str:
    now = dt.datetime.now(dt.timezone.utc)
    prompt = (
        "You are a kind, concise Quran recitation practice assistant. The student is reciting "
        f"Surah {int(surah)}, ayah {int(ayah)}: {verse}. Be attentive and encouraging. "
        "Let the student complete a phrase; when they pause, offer brief, actionable feedback "
        "on what was actually audible. Do not invent errors, claim exact Tajweed diagnosis, or "
        "pretend to be a human teacher or qualified scholar. If audio is unclear, say so and ask "
        "them to repeat a short phrase. Explain that automated feedback is approximate. Answer "
        "their questions in clear English. Allow natural interruption and stop speaking when the "
        "student speaks. For personal religious rulings, recommend a qualified scholar."
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
*{box-sizing:border-box}body{margin:0;padding:8px;background:#faf6ec;color:#302719;font:15px system-ui,sans-serif}.card{padding:18px;border:1px solid #e6dcc8;border-radius:22px;background:linear-gradient(145deg,#fffdf8,#f5eddb);box-shadow:0 12px 34px #5c45141c}.status{display:flex;align-items:center;justify-content:center;gap:8px;color:#625844;min-height:28px}.dot{width:9px;height:9px;border-radius:50%;background:#a89c83}.dot.live{background:#45a16d;box-shadow:0 0 0 5px #45a16d20;animation:pulse 1.4s infinite}.dot.talking{background:#c9a227;box-shadow:0 0 0 5px #c9a22722}@keyframes pulse{50%{box-shadow:0 0 0 9px #45a16d08}}.verse{direction:rtl;text-align:center;font:2rem/2.1 Georgia,serif;padding:15px 3px}.word{display:inline-block;margin:2px;padding:2px 6px;border:1px solid transparent;border-radius:10px;color:#453b30;transition:.22s}.word.hit{background:linear-gradient(135deg,#fff2c4,#f6df9d);border-color:#d0ad5540;color:#73540d;box-shadow:0 3px 12px #a77b2018}.word.active{background:linear-gradient(135deg,#ffeaa4,#f4d36e);border-color:#b07f1880;box-shadow:0 0 0 3px #dcb44d25,0 0 22px #d5a83570;transform:translateY(-2px) scale(1.04);animation:glow 1.4s ease-in-out infinite alternate}@keyframes glow{to{box-shadow:0 0 0 4px #dcb44d30,0 0 25px #d5a83580}}.meter{height:5px;border-radius:99px;background:#eee7d9;overflow:hidden}.meter span{display:block;height:100%;width:0;background:linear-gradient(90deg,#c9a227,#efcf69);transition:width .25s}.buttons{display:flex;justify-content:center;gap:10px;flex-wrap:wrap;margin-top:16px}button{padding:12px 20px;border:0;border-radius:999px;background:#c9a227;color:#241c17;font-weight:700;cursor:pointer}button.stop{background:#8c473c;color:white}button:disabled{opacity:.5;cursor:not-allowed}#transcript{min-height:28px;margin-top:12px;text-align:center;direction:rtl;color:#655832}.tip{font-size:12px;line-height:1.55;text-align:center;color:#766e60;margin:12px 0 0}.label{font-size:12px;color:#887a5d;text-transform:uppercase;letter-spacing:.13em;text-align:center}
</style></head><body><main class="card"><div class="label">Live recitation · Surah __SURAH__ · Ayah __AYAH__</div><div class="verse" id="verse" lang="ar" dir="rtl"></div><div class="meter" aria-label="Recognised words"><span id="progress"></span></div><div class="status" role="status" aria-live="polite"><i id="dot" class="dot"></i><span id="state">Ready when you are</span></div><div id="transcript" lang="ar"></div><div class="buttons"><button id="start">Start listening</button><button id="stop" class="stop" disabled>End session</button></div><p class="tip">Allow microphone access. Use headphones to prevent feedback. Speak naturally; the AI usually responds after you pause. Gold highlights reflect speech recognition, not verified Tajweed grading.</p></main>
<script>
const TOKEN=__TOKEN__, MODEL=__MODEL__, WORDS=__WORDS__;
const verseEl=document.getElementById('verse'), progressEl=document.getElementById('progress'), stateEl=document.getElementById('state'), dotEl=document.getElementById('dot'), transcriptEl=document.getElementById('transcript'), startBtn=document.getElementById('start'), stopBtn=document.getElementById('stop');
const marks=WORDS.map(()=>false);let elements=[],ws=null,stream=null,ctx=null,processor=null,source=null,active=false,ready=false,playedUntil=0,allTranscript='';
const norm=s=>s.replace(/[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]/g,'').replace(/[إأآٱ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه').replace(/[^\u0621-\u064A\s]/g,' ').replace(/\s+/g,' ').trim();
const expected=WORDS.map(w=>norm(w).replace(/\s/g,''));
function renderWords(){verseEl.replaceChildren();elements=WORDS.map((word,i)=>{const span=document.createElement('span');span.className='word';span.textContent=word;span.setAttribute('aria-label','Ayah word '+(i+1));verseEl.appendChild(span);return span;});}
function setStatus(text,kind=''){stateEl.textContent=text;dotEl.className='dot '+kind;}
function mergeTranscript(previous,next){next=norm(next);previous=norm(previous);if(!previous)return next;if(!next)return previous;if(next.startsWith(previous))return next;if(previous.endsWith(next))return previous;let overlap=Math.min(previous.length,next.length);while(overlap>0&&previous.slice(-overlap)!==next.slice(0,overlap))overlap--;return (previous+(overlap?' ':' ')+next.slice(overlap)).trim();}
function alignText(text){const heard=norm(text).split(' ').filter(Boolean);let j=0,last=-1;for(let i=0;i<expected.length&&j<heard.length;i++){for(let k=j;k<Math.min(j+3,heard.length);k++){const a=expected[i],b=heard[k];if(a===b||(b.length>=2&&a.startsWith(b))||(Math.min(a.length,b.length)>=3&&Math.abs(a.length-b.length)<=1)){marks[i]=true;last=i;j=k+1;break;}}}let count=0;for(let i=0;i<marks.length;i++){if(marks[i])count++;elements[i].classList.toggle('hit',marks[i]);elements[i].classList.toggle('active',i===last);}progressEl.style.width=(WORDS.length?Math.round(count/WORDS.length*100):0)+'%';}
function decode64(s){const raw=atob(s),bytes=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);return bytes;}
function playPcm(encoded){if(!ctx)return;const bytes=decode64(encoded),pcm=new Int16Array(bytes.buffer,bytes.byteOffset,Math.floor(bytes.byteLength/2));const buffer=ctx.createBuffer(1,pcm.length,24000),data=buffer.getChannelData(0);for(let i=0;i<pcm.length;i++)data[i]=pcm[i]/32768;const node=ctx.createBufferSource();node.buffer=buffer;node.connect(ctx.destination);playedUntil=Math.max(ctx.currentTime,playedUntil);node.start(playedUntil);playedUntil+=buffer.duration;setStatus('AI coach speaking · you can interrupt','talking');node.onended=()=>{if(active&&ctx.currentTime>=playedUntil-.05)setStatus('Listening · recite or ask a question','live');};}
function onMessage(event){let m;try{m=JSON.parse(event.data);}catch{return;}if(m.setupComplete){ready=true;setStatus('Listening · recite or ask a question','live');return;}const content=m.serverContent;if(!content)return;const input=content.inputTranscription?.text;if(input){allTranscript=mergeTranscript(allTranscript,input);transcriptEl.textContent=allTranscript;alignText(allTranscript);}const output=content.outputTranscription?.text;if(output)transcriptEl.textContent=allTranscript?allTranscript+' · AI: '+output:'AI: '+output;for(const part of content.modelTurn?.parts||[]){const audio=part.inlineData||part.inline_data;if(audio?.data&&(audio.mimeType||audio.mime_type||'').includes('audio/pcm'))playPcm(audio.data);}if(content.interrupted){playedUntil=ctx?.currentTime||0;setStatus('Listening · go ahead','live');}if(content.turnComplete&&active)setStatus('Listening · recite or ask a question','live');}
function pcm16(floatArray){const out=new Int16Array(floatArray.length);for(let i=0;i<floatArray.length;i++){const x=Math.max(-1,Math.min(1,floatArray[i]));out[i]=x<0?x*32768:x*32767;}return out;}
function resample(input,from,to){if(from===to)return input;const step=from/to,length=Math.floor(input.length/step),out=new Float32Array(length);for(let i=0;i<length;i++){const p=i*step,l=Math.floor(p),r=Math.min(l+1,input.length-1),f=p-l;out[i]=input[l]*(1-f)+input[r]*f;}return out;}
function b64(bytes){let text='';for(let i=0;i<bytes.length;i+=0x8000)text+=String.fromCharCode(...bytes.subarray(i,i+0x8000));return btoa(text);}
async function start(){startBtn.disabled=true;setStatus('Requesting microphone…');try{stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});ctx=new(window.AudioContext||window.webkitAudioContext)();await ctx.resume();const url='wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained?access_token='+encodeURIComponent(TOKEN);ws=new WebSocket(url);active=true;ws.onopen=()=>ws.send(JSON.stringify({setup:{model:MODEL,generationConfig:{responseModalities:['AUDIO']},systemInstruction:{parts:[{text:'You are a careful, kind Quran recitation practice assistant. Listen to the student reciting the selected ayah. Give short, grounded feedback after they pause; never invent an error or pretend to provide certified Tajweed grading. If uncertain, say so and ask for a short repeat. Speak clear English. You are an AI, not a human teacher or scholar. Allow interruption and stop speaking when the student begins.'}]},inputAudioTranscription:{},outputAudioTranscription:{}}));ws.onmessage=onMessage;ws.onerror=()=>setStatus('Connection failed. Check Live API model access and try again.');ws.onclose=()=>{if(active){setStatus('Live connection ended. Start a new session.');cleanup(false);}};ws.addEventListener('message',function onReady(e){let m;try{m=JSON.parse(e.data);}catch{return;}if(!m.setupComplete||!active||processor)return;ws.removeEventListener('message',onReady);ready=true;source=ctx.createMediaStreamSource(stream);processor=ctx.createScriptProcessor(4096,1,1);processor.onaudioprocess=e=>{if(!active||!ready||ws?.readyState!==WebSocket.OPEN)return;const samples=resample(e.inputBuffer.getChannelData(0),ctx.sampleRate,16000),pcm=pcm16(samples);ws.send(JSON.stringify({realtimeInput:{mediaChunks:[{mimeType:'audio/pcm;rate=16000',data:b64(new Uint8Array(pcm.buffer))}]}}));};source.connect(processor);processor.connect(ctx.destination);setStatus('Listening · recite or ask a question','live');});stopBtn.disabled=false;}catch(e){setStatus(e?.message||'Could not start. Allow microphone access and try again.');cleanup(false);}}
function cleanup(show){active=false;ready=false;if(processor){processor.disconnect();processor.onaudioprocess=null;processor=null;}if(source){source.disconnect();source=null;}if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}if(ws){ws.onclose=null;try{ws.close();}catch{}ws=null;}if(ctx){ctx.close().catch(()=>{});ctx=null;}playedUntil=0;startBtn.disabled=false;stopBtn.disabled=true;if(show)setStatus('Session ended');}
renderWords();startBtn.addEventListener('click',start);stopBtn.addEventListener('click',()=>cleanup(true));window.addEventListener('beforeunload',()=>cleanup(false));
</script></body></html>"""

if st.button("Create secure live lesson", type="primary"):
    try:
        with st.spinner("Creating a single-use, short-lived live session…"):
            token = issue_token()
        page = PAGE.replace("__TOKEN__", json.dumps(token)).replace("__MODEL__", json.dumps(f"models/{MODEL}"))
        page = page.replace("__WORDS__", json.dumps([word for word in verse.split() if word], ensure_ascii=True))
        page = page.replace("__SURAH__", str(int(surah))).replace("__AYAH__", str(int(ayah)))
        components.html(page, height=610, scrolling=False)
        st.caption("Start the microphone inside the lesson panel. If the deployed Streamlit page reloads, create a fresh session token.")
    except (requests.RequestException, RuntimeError) as error:
        st.error(str(error))
else:
    st.caption("Choose the ayah and create a lesson to get a secure, one-use connection token. Microphone permission is requested only when you start listening.")

st.caption(f"Live model: {MODEL}. Model availability can vary by Google project and may change; set GEMINI_LIVE_MODEL in Streamlit secrets to a currently enabled Gemini Live model.")
