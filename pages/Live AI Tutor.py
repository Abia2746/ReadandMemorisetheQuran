import base64
import datetime as dt
import html
import json
import time

import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Live AI Quran Tutor", page_icon="🎙️", layout="centered")
st.title("🎙️ Live AI Quran Tutor")
st.caption("Have a real-time spoken conversation with an AI study assistant. This is not a human teacher or a certified Tajweed assessment.")

API_KEY = st.secrets.get("GEMINI_API_KEY", "")
MODEL = st.secrets.get("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025")

surah = st.number_input("Surah", min_value=1, max_value=114, value=1, step=1)
ayah = st.number_input("Ayah", min_value=1, max_value=286, value=1, step=1)
verse = ""
try:
    response = requests.get(
        f"https://api.alquran.cloud/v1/ayah/{int(surah)}:{int(ayah)}/quran-uthmani",
        timeout=10,
    )
    if response.ok:
        verse = response.json().get("data", {}).get("text", "")
except requests.RequestException:
    pass

if verse:
    st.markdown(f"**Current ayah:** {html.escape(verse)}", help=f"Surah {int(surah)}, ayah {int(ayah)}")

st.info("The AI listens and replies with streamed voice while the session is active. Use headphones to reduce audio feedback. Your microphone audio is sent to Google Gemini Live API for processing.")

if not API_KEY:
    st.error("Live voice needs GEMINI_API_KEY configured in Streamlit secrets. The key stays on the server; a short-lived, single-use token is issued for the browser session.")
    st.stop()


def issue_live_token() -> str:
    """Mint a single-use, short-lived Gemini Live token without exposing the API key."""
    now = dt.datetime.now(dt.timezone.utc)
    system_text = (
        "You are a warm, careful Quran recitation study assistant speaking with a student. "
        f"The student is studying Surah {int(surah)}, ayah {int(ayah)}: {verse or 'the selected ayah'}. "
        "Listen conversationally and answer briefly in clear English. Help with memorisation, "
        "pronunciation practice, and general learning. Never claim to be a human or a qualified "
        "scholar. Do not claim to verify Tajweed with certainty from audio; explain uncertainty. "
        "For personal religious rulings, recommend asking a qualified scholar. Let the student "
        "interrupt you naturally, and stop speaking when they begin talking."
    )
    payload = {
        "uses": 1,
        "expireTime": (now + dt.timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        "newSessionExpireTime": (now + dt.timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "liveConnectConstraints": {
            "model": f"models/{MODEL}",
            "config": {
                "responseModalities": ["AUDIO"],
                "systemInstruction": {"parts": [{"text": system_text}]},
                "inputAudioTranscription": {},
                "outputAudioTranscription": {},
            },
        },
    }
    result = requests.post(
        "https://generativelanguage.googleapis.com/v1alpha/authTokens",
        params={"key": API_KEY},
        json=payload,
        timeout=20,
    )
    if not result.ok:
        detail = result.text[:500]
        raise RuntimeError(f"Gemini could not create a Live session token ({result.status_code}): {detail}")
    token = result.json().get("name")
    if not token:
        raise RuntimeError("Gemini returned no session token. Check the Live API model and project access.")
    return token


LIVE_HTML = r"""<!doctype html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
*{box-sizing:border-box}body{margin:0;background:#faf6ec;color:#302719;font:15px system-ui,sans-serif}.panel{padding:18px;border:1px solid #e6dcc8;border-radius:20px;background:linear-gradient(145deg,#fffdf7,#f6efdf);box-shadow:0 10px 32px #6d552016;text-align:center}.actions{display:flex;justify-content:center;gap:10px;flex-wrap:wrap}button{border:0;border-radius:999px;padding:12px 20px;font-weight:700;cursor:pointer;background:#c9a227;color:#241c17}button.stop{background:#9e453d;color:white}button:disabled{opacity:.55;cursor:not-allowed}.dot{display:inline-block;width:9px;height:9px;background:#b8a785;border-radius:50%;margin-right:7px}.dot.live{background:#43a36f;box-shadow:0 0 0 5px #43a36f20;animation:pulse 1.4s infinite}.dot.talking{background:#c9a227;box-shadow:0 0 0 5px #c9a22722}@keyframes pulse{50%{box-shadow:0 0 0 9px #43a36f08}}#state{min-height:26px;margin:12px 0;color:#6b6255}#transcript{min-height:28px;direction:rtl;color:#665627}.note{font-size:12px;color:#777;margin-top:12px}
</style></head><body><main class="panel"><div id="state"><i id="dot" class="dot"></i><span id="label">Ready when you are</span></div><div class="actions"><button id="start">Start live lesson</button><button id="stop" class="stop" disabled>End lesson</button></div><div id="transcript" aria-live="polite"></div><p class="note">Allow microphone access. Audio is streamed to Gemini Live API. You can interrupt the AI by speaking.</p></main>
<script>
const TOKEN=__TOKEN__, MODEL=__MODEL__;
const startBtn=document.getElementById('start'), stopBtn=document.getElementById('stop'), label=document.getElementById('label'), dot=document.getElementById('dot'), transcript=document.getElementById('transcript');
let socket=null, stream=null, audioContext=null, processor=null, source=null, playbackAt=0, active=false, ready=false;
const wsUrl='wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained?access_token='+encodeURIComponent(TOKEN);
function status(text, cls=''){label.textContent=text;dot.className='dot '+cls;}
function b64(bytes){let binary='';const chunk=0x8000;for(let i=0;i<bytes.length;i+=chunk)binary+=String.fromCharCode(...bytes.subarray(i,i+chunk));return btoa(binary);}
function toPcm16(samples){const output=new Int16Array(samples.length);for(let i=0;i<samples.length;i++){const value=Math.max(-1,Math.min(1,samples[i]));output[i]=value<0?value*32768:value*32767;}return output;}
function resample(input, fromRate, toRate){if(fromRate===toRate)return input;const ratio=fromRate/toRate;const length=Math.floor(input.length/ratio);const out=new Float32Array(length);for(let i=0;i<length;i++){const position=i*ratio;const left=Math.floor(position);const right=Math.min(left+1,input.length-1);const fraction=position-left;out[i]=input[left]*(1-fraction)+input[right]*fraction;}return out;}
function playPcm(encoded){const binary=atob(encoded);const pcm=new Int16Array(binary.length/2);for(let i=0;i<pcm.length;i++)pcm[i]=(binary.charCodeAt(2*i)|(binary.charCodeAt(2*i+1)<<8));const buffer=audioContext.createBuffer(1,pcm.length,24000);const channel=buffer.getChannelData(0);for(let i=0;i<pcm.length;i++)channel[i]=pcm[i]/32768;const node=audioContext.createBufferSource();node.buffer=buffer;node.connect(audioContext.destination);const now=audioContext.currentTime;playbackAt=Math.max(now,playbackAt);node.start(playbackAt);playbackAt+=buffer.duration;status('AI teacher is speaking · you can interrupt','talking');node.onended=()=>{if(active&&audioContext.currentTime>=playbackAt-.05)status('Live lesson · speak whenever you like','live');};}
function handleMessage(event){let message;try{message=JSON.parse(event.data);}catch{return;}if(message.setupComplete){ready=true;status('Live lesson · listening','live');return;}const content=message.serverContent;if(!content)return;if(content.inputTranscription?.text)transcript.textContent='You: '+content.inputTranscription.text;if(content.outputTranscription?.text)transcript.textContent='AI: '+content.outputTranscription.text;for(const part of content.modelTurn?.parts||[]){const inline=part.inlineData||part.inline_data;if(inline?.data&&(inline.mimeType||inline.mime_type||'').includes('audio/pcm'))playPcm(inline.data);}if(content.interrupted){playbackAt=audioContext?.currentTime||0;status('Listening · go ahead','live');}if(content.turnComplete&&active)status('Live lesson · speak whenever you like','live');}
async function begin(){startBtn.disabled=true;status('Requesting microphone and connecting…');try{stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});audioContext=new (window.AudioContext||window.webkitAudioContext)();await audioContext.resume();socket=new WebSocket(wsUrl);socket.onopen=()=>{socket.send(JSON.stringify({setup:{model:MODEL, generationConfig:{responseModalities:['AUDIO']}, systemInstruction:{parts:[{text:'You are a warm, careful Quran recitation study assistant. Speak briefly and clearly in English. Help the student learn and memorise; do not pretend to be a human teacher or a qualified scholar. Never claim Tajweed accuracy you cannot establish. Recommend a qualified scholar for personal religious rulings. Listen naturally, allow interruption, and stop speaking when the student begins speaking.'}]}, inputAudioTranscription:{}, outputAudioTranscription:{}}}));};socket.onmessage=handleMessage;socket.onerror=()=>status('Connection error. Check Live API access and try again.');socket.onclose=(event)=>{if(active){status(event.reason||'Live connection closed. Start a new lesson.');cleanup(false);}};const track=stream.getAudioTracks()[0];if(!track)throw new Error('No microphone track was available.');socket.addEventListener('message',async function setupReady(event){let message;try{message=JSON.parse(event.data);}catch{return;}if(!message.setupComplete||!active||processor)return;socket.removeEventListener('message',setupReady);source=audioContext.createMediaStreamSource(stream);processor=audioContext.createScriptProcessor(4096,1,1);processor.onaudioprocess=(audioEvent)=>{if(!active||!ready||socket?.readyState!==WebSocket.OPEN)return;const input=audioEvent.inputBuffer.getChannelData(0);const pcm=toPcm16(resample(input,audioContext.sampleRate,16000));socket.send(JSON.stringify({realtimeInput:{mediaChunks:[{mimeType:'audio/pcm;rate=16000',data:b64(new Uint8Array(pcm.buffer))}]}}));};source.connect(processor);processor.connect(audioContext.destination);status('Live lesson · listening','live');});active=true;ready=false;startBtn.disabled=true;stopBtn.disabled=false;}catch(error){status(error?.message||'Could not start. Allow microphone access and try again.');cleanup(false);}}
function cleanup(update=true){active=false;ready=false;if(processor){processor.disconnect();processor.onaudioprocess=null;processor=null;}if(source){source.disconnect();source=null;}if(stream){stream.getTracks().forEach(track=>track.stop());stream=null;}if(socket){socket.onclose=null;try{socket.close();}catch{}socket=null;}if(audioContext){audioContext.close().catch(()=>{});audioContext=null;}playbackAt=0;startBtn.disabled=false;stopBtn.disabled=true;if(update)status('Lesson ended');}
startBtn.addEventListener('click',begin);stopBtn.addEventListener('click',()=>cleanup(true));window.addEventListener('beforeunload',()=>cleanup(false));
</script></body></html>"""

if st.button("Start a real-time AI voice lesson", type="primary"):
    try:
        with st.spinner("Securing a one-time live session…"):
            token = issue_live_token()
        encoded_token = json.dumps(token)
        encoded_model = json.dumps(f"models/{MODEL}")
        html_doc = LIVE_HTML.replace("__TOKEN__", encoded_token).replace("__MODEL__", encoded_model)
        components.html(html_doc, height=230, scrolling=False)
        st.caption("The session token is single-use and short-lived. Start another session to get a new token.")
    except (requests.RequestException, RuntimeError) as error:
        st.error(str(error))
else:
    st.caption("Press the button to open the live microphone and voice session. Configure GEMINI_API_KEY in Streamlit secrets first.")

st.caption(f"Configured Live API model: {MODEL}. If Google retires or does not enable this model for your project, set GEMINI_LIVE_MODEL in Streamlit secrets to a currently supported Live API model.")
