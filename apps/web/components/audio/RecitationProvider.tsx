"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { practiceAudioEvent, takeAudioTurn } from "@/lib/practiceAudio";
import type { ReactNode } from "react";

export type SpeechObservation = {
  transcript: string;
  final: boolean;
  confidence: number | null;
  recognizer: "browser" | "whisper";
};
type SpeechResult = {
  isFinal: boolean;
  length: number;
  [n: number]: { transcript: string; confidence?: number };
};
type SpeechEvent = { resultIndex: number; results: ArrayLike<SpeechResult> };
type BrowserRecognition = {
  lang: string; continuous: boolean; interimResults: boolean;
  onresult: ((event: SpeechEvent) => void) | null;
  onerror: ((event: {error: string}) => void) | null;
  onend: (() => void) | null;
  start: () => void; stop: () => void;
};
type RecognizerConstructor = new () => BrowserRecognition;
type PlayerState = {
  playing: boolean; listening: boolean; micLevel: number;
  time: number; duration: number; verseId: string|null;
  speechSupported: boolean; note:string;
};
type AudioActions = {
  state: PlayerState;
  playVerse: (url:string,verseId:string)=>Promise<void>;
  playRange: (url:string,verseId:string,startMs:number,endMs:number,repeats?:number)=>Promise<void>;
  pause: ()=>void; stop: ()=>void;
  setSpeed: (rate:number)=>void;
  startMicrophone: (onObservation:(observation:SpeechObservation)=>void, engine?:"browser"|"whisper")=>Promise<void>;
  stopMicrophone: ()=>void;
};
const Context = createContext<AudioActions | null>(null);
const initial:PlayerState = {
  playing:false,listening:false,micLevel:0,time:0,duration:0,
  verseId:null,speechSupported:false,note:"Ready to listen or practise."
};

export function RecitationProvider({children}:{children:ReactNode}) {
  const [state,setState] = useState<PlayerState>(initial);
  const audioRef = useRef<HTMLAudioElement|null>(null);
  const rangeRef = useRef<{from:number;to:number;remaining:number}|null>(null);
  const streamRef = useRef<MediaStream|null>(null);
  const ctxRef = useRef<AudioContext|null>(null);
  const recognitionRef = useRef<BrowserRecognition|null>(null);
  const workerRef = useRef<Worker|null>(null);
  const workletRef = useRef<AudioWorkletNode|null>(null);
  const whisperNodeRef = useRef<GainNode|null>(null);
  const meterTimer = useRef<number|undefined>(undefined);
  const onObservation = useRef<((o:SpeechObservation)=>void)|null>(null);

  const generation = useRef(0);
  const playbackGeneration = useRef(0);

  const stopMicrophone = useCallback(() => {
    generation.current++;
    onObservation.current=null;
    if(workerRef.current)workerRef.current.onmessage=null;
    const rec=recognitionRef.current; recognitionRef.current=null;
    if(rec){rec.onend=null;rec.onresult=null;rec.onerror=null;try{rec.stop()}catch{}}
    workletRef.current?.disconnect();
    workletRef.current=null;
    whisperNodeRef.current?.disconnect();
    whisperNodeRef.current=null;
    streamRef.current?.getTracks().forEach(track=>track.stop());
    streamRef.current=null;
    if(meterTimer.current!==undefined)window.cancelAnimationFrame(meterTimer.current);
    meterTimer.current=undefined;
    void ctxRef.current?.close().catch(()=>{});
    ctxRef.current=null;
    setState(s=>({...s,listening:false,micLevel:0}));
  },[]);

  useEffect(()=>{
    const audio = new Audio();
    audio.preload="metadata";
    audioRef.current=audio;
    const interrupt=()=>{
      playbackGeneration.current++;
      rangeRef.current=null;
      audio.pause();
      stopMicrophone();
    };
    window.addEventListener(practiceAudioEvent,interrupt);
    window.addEventListener("pagehide",interrupt);
    const onPlay=()=>setState(s=>({...s,playing:true}));
    const onPause=()=>setState(s=>({...s,playing:false}));
    const onDuration=()=>setState(s=>({...s,duration:Number.isFinite(audio.duration)?audio.duration:0}));
    const onTick=()=>{
      setState(s=>({...s,time:audio.currentTime}));
      const loop=rangeRef.current;
      if(!loop || audio.currentTime+0.035<loop.to)return;
      if(loop.remaining>1){
        loop.remaining-=1;
        audio.currentTime=loop.from;
        void audio.play().catch(()=>{});
      } else {
        rangeRef.current=null;
        audio.pause();
      }
    };
    audio.addEventListener("play",onPlay);
    audio.addEventListener("pause",onPause);
    audio.addEventListener("durationchange",onDuration);
    audio.addEventListener("timeupdate",onTick);
    const BrowserAPI = (window as unknown as {SpeechRecognition?:RecognizerConstructor;webkitSpeechRecognition?:RecognizerConstructor}).SpeechRecognition ||
      (window as unknown as {webkitSpeechRecognition?:RecognizerConstructor}).webkitSpeechRecognition;
    setState(s=>({...s,speechSupported:Boolean(BrowserAPI)}));
    return ()=>{
      window.removeEventListener(practiceAudioEvent,interrupt);
      window.removeEventListener("pagehide",interrupt);
      interrupt();
      workerRef.current?.terminate();workerRef.current=null;
      audio.pause();
      audio.src="";
      audio.removeEventListener("play",onPlay);
      audio.removeEventListener("pause",onPause);
      audio.removeEventListener("durationchange",onDuration);
      audio.removeEventListener("timeupdate",onTick);
      audioRef.current=null;
    };
  },[stopMicrophone]);

  const playVerse=useCallback(async (url:string,verseId:string)=>{
    const audio=audioRef.current;if(!audio)return;
    takeAudioTurn(); rangeRef.current=null;
    if(audio.src!==url){audio.src=url;audio.load();}
    setState(s=>({...s,verseId,note:"Playing the selected Qari recording."}));
    await audio.play();
  },[stopMicrophone]);

  const playRange=useCallback(async (url:string,verseId:string,startMs:number,endMs:number,repeats=3)=>{
    const audio=audioRef.current;if(!audio)return;
    if(!Number.isFinite(startMs)||!Number.isFinite(endMs)||startMs<0||endMs<=startMs){
      throw Error("Exact source-matched timing is not available for that phrase.");
    }
    takeAudioTurn();
    const turn=playbackGeneration.current;
    const from=startMs/1000,to=endMs/1000;
    rangeRef.current={from,to,remaining:Math.max(1,Math.min(10,repeats))};
    if(audio.src!==url){audio.src=url;audio.load();}
    setState(s=>({...s,verseId,note:`Looping the selected phrase ${repeats} times.`}));
    if(audio.readyState<1){
      await new Promise<void>((resolve,reject)=>{
        const timeout=window.setTimeout(()=>reject(new Error("Reciter audio did not load.")),12000);
        audio.addEventListener("loadedmetadata",()=>{window.clearTimeout(timeout);resolve()},{once:true});
        audio.addEventListener("error",()=>{window.clearTimeout(timeout);reject(Error("Audio unavailable"))},{once:true});
      });
    }
    if(turn!==playbackGeneration.current)return;
    audio.currentTime=from;
    await audio.play();
  },[stopMicrophone]);

  const pause=useCallback(()=>{playbackGeneration.current++;audioRef.current?.pause()},[]);
  const stop=useCallback(()=>{playbackGeneration.current++;rangeRef.current=null;const audio=audioRef.current;if(audio){audio.pause();audio.currentTime=0;}},[]);
  const setSpeed=useCallback((speed:number)=>{
    if(audioRef.current)audioRef.current.playbackRate=Math.min(1.4,Math.max(0.65,speed));
  },[]);

  const startMicrophone=useCallback(async (observer:(o:SpeechObservation)=>void, engine:"browser"|"whisper"="browser")=>{
    if(!navigator.mediaDevices?.getUserMedia)throw Error("Your browser does not provide microphone access.");
    takeAudioTurn();
    const session=generation.current;
    setState(s=>({...s,listening:true,note:"Requesting microphone access…"}));
    try {
    const stream=await navigator.mediaDevices.getUserMedia({
      audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false
    });
    if(session!==generation.current){stream.getTracks().forEach(track=>track.stop());return;}
    streamRef.current=stream;onObservation.current=observer;
    const ContextCtor=window.AudioContext;
    if(ContextCtor){
      const audioCtx=new ContextCtor();
      ctxRef.current=audioCtx;
      await audioCtx.resume();
      if(session!==generation.current)return;
      const source=audioCtx.createMediaStreamSource(stream);
      if(engine==="whisper"){
        if(!audioCtx.audioWorklet)throw Error("AudioWorklet unavailable for on-device recognition.");
        await audioCtx.audioWorklet.addModule("/worklets/pcm-processor.js");
        if(session!==generation.current)return;
        if(!workerRef.current){
          workerRef.current=new Worker(new URL("../../workers/whisper.worker.ts",import.meta.url),{type:"module"});
        }
        const worker=workerRef.current;
        const blocks:Float32Array[]=[];
        let samples=0;let ready=false;
        worker.onmessage=(event:MessageEvent<{type:string;session:number;text?:string;message?:string}>)=>{
          if(event.data.session!==session || generation.current!==session)return;
          if(event.data.type==="ready"){ready=true;setState(state=>({...state,note:"Whisper is ready. Your Arabic speech stays on this device."}));}
          if(event.data.type==="transcript" && event.data.text){
            onObservation.current?.({transcript:event.data.text,final:true,confidence:null,recognizer:"whisper"});
          }
          if(event.data.type==="error"){stopMicrophone();setState(state=>({...state,note:"On-device model: "+(event.data.message||"unavailable")}));}
        };
        worker.postMessage({type:"init",session});
        const worklet=new AudioWorkletNode(audioCtx,"almuallim-pcm");
        workletRef.current=worklet;
        worklet.port.onmessage=(event:MessageEvent<{pcm:Float32Array;sourceRate:number}>)=>{
          if(!ready||!streamRef.current)return;
          const chunk=event.data.pcm;
          if(!(chunk instanceof Float32Array))return;
          blocks.push(chunk);samples+=chunk.length;
          const rate=event.data.sourceRate||audioCtx.sampleRate;
          if(samples<rate*5)return;
          const joined=new Float32Array(samples);let offset=0;
          for(const block of blocks){joined.set(block,offset);offset+=block.length;}
          blocks.length=0;samples=0;
          const scale=rate/16000;
          const resampled=new Float32Array(Math.floor(joined.length/scale));
          for(let i=0;i<resampled.length;i++)resampled[i]=joined[Math.min(joined.length-1,Math.floor(i*scale))];
          worker.postMessage({type:"transcribe",session,audio:resampled,sampleRate:16000},[resampled.buffer]);
        };
        const muted=audioCtx.createGain();muted.gain.value=0;
        whisperNodeRef.current=muted;
        source.connect(worklet);worklet.connect(muted);muted.connect(audioCtx.destination);
      }
      const analyser=audioCtx.createAnalyser();
      analyser.fftSize=512;
      source.connect(analyser);
      const bins=new Uint8Array(analyser.frequencyBinCount);
      let last=0;
      const tick=(now:number)=>{
        if(!streamRef.current)return;
        if(now-last>110){
          analyser.getByteFrequencyData(bins);
          const rms=Math.sqrt(bins.reduce((sum,n)=>sum+n*n,0)/bins.length)/255;
          setState(s=>({...s,micLevel:Math.min(1,rms*2.5)}));
          last=now;
        }
        meterTimer.current=window.requestAnimationFrame(tick);
      };
      meterTimer.current=window.requestAnimationFrame(tick);
    }
    if(engine==="whisper"){
      if(!ctxRef.current)throw Error("Audio capture is unavailable in this browser.");
      setState(state=>({...state,listening:true,note:"Preparing on-device Arabic Whisper. First use downloads a model; microphone audio remains local."}));
      return;
    }
    const w=window as unknown as {SpeechRecognition?:RecognizerConstructor;webkitSpeechRecognition?:RecognizerConstructor};
    const Recognition=w.SpeechRecognition||w.webkitSpeechRecognition;
    setState(s=>({...s,listening:true,note:Recognition
      ?"Listening with browser speech recognition (not certified Tajweed)."
      :"Microphone active; Arabic recognition unavailable here. Use manual flagging."}));
    if(!Recognition)throw Error("Browser speech recognition is unavailable. Choose on-device Whisper.");
    const recognition=new Recognition();
    recognition.lang="ar-SA";recognition.continuous=true;recognition.interimResults=true;
    recognition.onresult=e=>{
      for(let i=e.resultIndex;i<e.results.length;i++){
        const result=e.results[i];
        if(!result?.[0]?.transcript)continue;
        onObservation.current?.({
          transcript:result[0].transcript,final:result.isFinal,
          confidence:typeof result[0].confidence==="number"?result[0].confidence:null,
          recognizer:"browser",
        });
      }
    };
    recognition.onerror=e=>{
      stopMicrophone();
      setState(s=>({...s,note:`Speech recognition stopped (${e.error}).`}));
    };
    recognition.onend=()=>{stopMicrophone();setState(s=>({...s,note:"Listening finished."}));};
    recognitionRef.current=recognition;
    recognition.start();
    } catch (error) {
      if(session!==generation.current)return;
      stopMicrophone();
      throw error;
    }
  },[stop,stopMicrophone]);

  return <Context.Provider value={{state,playVerse,playRange,pause,stop,setSpeed,startMicrophone,stopMicrophone}}>
    {children}
  </Context.Provider>;
}

export function useRecitation(){
  const value=useContext(Context);
  if(!value)throw Error("RecitationProvider must surround the Qur'an reader.");
  return value;
}
