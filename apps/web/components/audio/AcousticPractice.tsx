"use client";
/** Opt-in rolling microphone-to-acoustic-model analysis.
 * Deliberately separate from text ASR and word verification. */
import { useCallback, useEffect, useRef, useState } from "react";
import { apiPath } from "@/lib/verseApi";
import { accessToken, useStudyAuth } from "@/lib/auth";

type Phone = {phone:string;approx_start_ms:number;approx_end_ms:number;uncertainty:string};
type AlignmentEvent = {kind:string;expected:string|null;observed:string|null;outcome:string;explanation:string};
type Result = {status:string;phones:Phone[];message:string;tajweed_verified:false;
  alignment?:{status:string;events:AlignmentEvent[];reference:string;verified_tajweed:false};
  audio_quality?:{usable:boolean;reasons:string[]}};
type Capabilities = {available:boolean;reason:string;model_id?:string};
const HZ=16000;

function pcm16(values:number[]):Uint8Array {
  const out=new Uint8Array(values.length*2);
  const view=new DataView(out.buffer);
  values.forEach((v,i)=>view.setInt16(i*2,Math.max(-32768,Math.min(32767,Math.round(v*32767))),true));
  return out;
}
function resample(values:Float32Array,sourceRate:number):number[] {
  if(!sourceRate||!Number.isFinite(sourceRate))return [];
  const length=Math.floor(values.length*HZ/sourceRate);
  const out:number[]=[];
  for(let i=0;i<length;i++){
    const pos=i*sourceRate/HZ;
    const j=Math.floor(pos);
    const delta=pos-j;
    out.push((values[j]||0)*(1-delta)+(values[Math.min(values.length-1,j+1)]||0)*delta);
  }
  return out;
}

export function AcousticPractice({verseRef}:{verseRef:string}){
  const auth=useStudyAuth();
  const [caps,setCaps]=useState<Capabilities|null>(null);
  const [running,setRunning]=useState(false);
  const [status,setStatus]=useState("Not started. Acoustic accuracy is not certified.");
  const [reports,setReports]=useState<Result[]>([]);
  const stream=useRef<MediaStream|null>(null);
  const ctx=useRef<AudioContext|null>(null);
  const node=useRef<AudioWorkletNode|null>(null);
  const gain=useRef<GainNode|null>(null);
  const data=useRef<number[]>([]);
  const busy=useRef(false);
  const alive=useRef(false);
  const interval=useRef<ReturnType<typeof setInterval>|null>(null);
  const abort=useRef<AbortController|null>(null);
  const epoch=useRef(0);

  const stop=useCallback(()=>{
    alive.current=false;
    epoch.current++;
    if(interval.current){clearInterval(interval.current);interval.current=null;}
    abort.current?.abort();abort.current=null;
    node.current?.disconnect();node.current=null;
    gain.current?.disconnect();gain.current=null;
    stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;
    void ctx.current?.close().catch(()=>{});ctx.current=null;
    data.current=[];busy.current=false;setRunning(false);
  },[]);
  useEffect(()=>()=>stop(),[stop]);
  useEffect(()=>{
    let active=true;
    fetch(apiPath("/api/acoustic/capabilities"),{cache:"no-store"})
      .then(r=>r.ok?r.json():Promise.reject())
      .then((c:Capabilities)=>{if(active)setCaps(c)})
      .catch(()=>{if(active)setCaps({available:false,reason:"Acoustic API unreachable"})});
    return ()=>{active=false};
  },[]);

  const sendWindow=useCallback(async()=>{
    if(!alive.current||busy.current||data.current.length<2*HZ)return;
    // Hard cap at 4 s and discard older buffers if offline/slow.
    const segment=data.current.splice(0,Math.min(data.current.length,4*HZ));
    const currentEpoch=epoch.current;
    busy.current=true;
    const controller=new AbortController();abort.current=controller;
    try{
      const token=await accessToken();
      if(!token)throw Error("Sign in before starting acoustic analysis");
      const response=await fetch(apiPath("/api/acoustic/analyse"),{
        method:"POST",headers:{"Content-Type":"application/octet-stream","X-Quran-Verse":verseRef,
          "Authorization":`Bearer ${token}`},
        body:new Blob([pcm16(segment).buffer as ArrayBuffer],{type:"application/octet-stream"}),signal:controller.signal,cache:"no-store",
      });
      const result=await response.json().catch(()=>null);
      if(!alive.current||epoch.current!==currentEpoch)return;
      if(!response.ok){
        setStatus(response.status===503
          ?"A trained and reviewed phoneme model is not deployed. Text recognition remains separate."
          :`Acoustic service unavailable (${response.status}).`);
        if(response.status===503)stop();
        return;
      }
      const report=result as Result;
      setReports(p=>[...p.slice(-7),report]);
      setStatus(report.message||"Audio analysed; review uncertainty.");
    }catch(e){
      if(alive.current&&epoch.current===currentEpoch)
        setStatus("The acoustic request failed; check API connection.");
    }finally{
      busy.current=false;
    }
  },[stop]);

  const start=async()=>{
    if(!auth.isSignedIn){
      setStatus("Please sign in to use the acoustic inference service.");
      return;
    }
    if(!caps?.available){
      setStatus(caps?.reason||"Checking whether a trained model is available.");
      return;
    }
    stop();setReports([]);setStatus("Requesting microphone permission…");
    try{
      if(!navigator.mediaDevices?.getUserMedia)throw Error("Microphone access requires HTTPS and a compatible browser.");
      const mic=await navigator.mediaDevices.getUserMedia({
        audio:{channelCount:1,echoCancellation:false,noiseSuppression:false,autoGainControl:false},
        video:false,
      });
      stream.current=mic;
      const context=new AudioContext();ctx.current=context;
      if(!context.audioWorklet)throw Error("AudioWorklet is not supported.");
      await context.audioWorklet.addModule("/worklets/pcm-processor.js");
      const source=context.createMediaStreamSource(mic);
      const processor=new AudioWorkletNode(context,"almuallim-pcm");node.current=processor;
      const silent=context.createGain();gain.current=silent;silent.gain.value=0;
      processor.port.onmessage=(event:MessageEvent<{pcm:Float32Array;sourceRate:number}>)=>{
        if(!alive.current)return;
        const raw=event.data.pcm;
        if(!(raw instanceof Float32Array))return;
        data.current.push(...resample(raw,event.data.sourceRate||context.sampleRate));
        if(data.current.length>HZ*8)data.current.splice(0,data.current.length-HZ*8);
      };
      source.connect(processor);processor.connect(silent);silent.connect(context.destination);
      await context.resume();
      alive.current=true;setRunning(true);
      setStatus("Listening to actual microphone audio; analysing 2–4 second windows.");
      interval.current=setInterval(()=>{void sendWindow()},2500);
    }catch(e){
      stop();setStatus(e instanceof Error?e.message:"Microphone capture failed.");
    }
  };
  return <section className="mt-3 rounded-2xl border border-[#5C4A32] bg-[#241913] p-4"
    aria-label="Experimental acoustic phoneme practice">
    <h3 className="font-editorial text-lg text-[#EDD39F]">Acoustic phoneme laboratory</h3>
    <p className="mt-2 text-xs leading-relaxed text-[#C0AB90]">
      Optional experimental analysis of your microphone signal for {verseRef}.
      These are acoustic phone hypotheses, not verified makharij, harakat, Tajweed grades,
      or proof of a complete Qur&apos;anic phrase. Audio windows are sent to the configured
      API only after you press Start; this UI does not save them.
    </p>
    <p className="mt-2 text-xs text-[#E6D5B8]">
      {caps?.available?"Acoustic model configured":"Acoustic model unavailable"} · {caps?.reason||"Checking model availability"}
    </p>
    <button type="button" className="am-small-action mt-3" onClick={()=>{if(running)stop();else void start()}}>
      {running?"Stop acoustic analysis":"Start acoustic analysis"}
    </button>
    <p role="status" aria-live="polite" className="mt-3 text-xs text-[#E6D5B8]">{status}</p>
    {reports.length>0&&<div className="mt-3 space-y-2">
      <h4 className="text-xs font-semibold text-[#EDD39F]">What was heard (uncertified)</h4>
      {reports.slice(-3).map((report,i)=><div key={i} className="rounded-lg bg-[#352820] p-3 text-xs">
        <p>{report.phones?.length?report.phones.map(p=>p.phone).join(" · "):
          "No reliable phonemes detected in this window."}</p>
        <p className="mt-1 text-[#C0AB90]">
          {report.audio_quality?.reasons.join(", ")||
            "Uncertain until validated with teacher-labelled examples"}
        </p>
        <p className="mt-1 text-[#EDD39F]">
          {report.alignment?.status==="candidate_alignment"
            ? "Phone-to-reference alignment (all differences unverified)"
            : "Expert-reviewed phoneme reference unavailable"}
        </p>
        {report.alignment?.events?.filter(e=>e.kind!=="match").slice(0,6).map((e,j)=>
          <p key={j} className="mt-1 text-[#C0AB90]">
            Expected {e.expected||"—"} · model suggested {e.observed||"—"}.
            Possible alignment difference; repeat this sound and compare with a qualified teacher.
          </p>
        )}
      </div>)}
    </div>}
  </section>;
}
