"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { practiceAudioEvent, takeAudioTurn } from "@/lib/practiceAudio";

export function RecitationReplay() {
  const [phase,setPhase]=useState<"idle"|"requesting"|"recording">("idle");
  const [clip,setClip]=useState("");
  const [message,setMessage]=useState("");
  const epoch=useRef(0);
  const recorder=useRef<MediaRecorder|null>(null);
  const stream=useRef<MediaStream|null>(null);
  const player=useRef<HTMLAudioElement|null>(null);
  const url=useRef("");
  const timer=useRef<ReturnType<typeof setTimeout>|null>(null);

  const finish=useCallback(()=>{
    epoch.current++;
    if(timer.current)clearTimeout(timer.current);
    timer.current=null;
    if(recorder.current?.state==="recording")recorder.current.stop();
    stream.current?.getTracks().forEach(track=>track.stop());
    stream.current=null;
    setPhase("idle");
  },[]);
  const discard=useCallback(()=>{
    if(recorder.current)recorder.current.onstop=null;
    finish();
    recorder.current=null;
    if(url.current)URL.revokeObjectURL(url.current);
    url.current="";
    setClip("");
  },[finish]);
  useEffect(()=>{
    const interrupt=(event:Event)=>{
      if(player.current && (event as CustomEvent).detail===player.current)return;
      player.current?.pause();
      finish();
    };
    window.addEventListener(practiceAudioEvent,interrupt);
    window.addEventListener("pagehide",discard);
    return ()=>{
      window.removeEventListener(practiceAudioEvent,interrupt);
      window.removeEventListener("pagehide",discard);
      discard();
    };
  },[finish,discard]);

  async function record() {
    takeAudioTurn();
    discard();
    const turn=epoch.current;
    setMessage("");
    setPhase("requesting");
    try {
      if(!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder==="undefined")
        throw Error("This browser does not support local recording.");
      const mic=await navigator.mediaDevices.getUserMedia({audio:true,video:false});
      if(turn!==epoch.current){mic.getTracks().forEach(track=>track.stop());return;}
      stream.current=mic;
      const capture=new MediaRecorder(mic);
      recorder.current=capture;
      const parts:Blob[]=[];
      capture.ondataavailable=e=>{if(e.data.size)parts.push(e.data)};
      capture.onstop=()=>{
        if(recorder.current!==capture)return;
        recorder.current=null;
        finish();
        if(!parts.length){setMessage("The recording was empty. Try again.");return;}
        url.current=URL.createObjectURL(new Blob(parts,{type:capture.mimeType}));
        setClip(url.current);
      };
      capture.onerror=()=>{discard();setMessage("Recording interrupted. Please try again.");};
      capture.start();
      setPhase("recording");
      timer.current=setTimeout(finish,30000);
    } catch(error) {
      if(epoch.current!==turn)return;
      discard();
      setMessage(error instanceof Error?error.message:"Recording unavailable.");
    }
  }
  return <fieldset className="mt-4 rounded-xl border border-[#5C4A32] p-3">
    <legend className="px-2 text-sm text-[#EDD39F]">Listen to your own recitation</legend>
    <p className="text-xs text-[#E6D5B8]">Record up to 30 seconds for your own comparison. The clip stays in this tab and clears when you leave the ayah.</p>
    <button type="button" className="am-small-action mt-2" onClick={()=>phase==="idle"?void record():finish()}>
      {phase==="recording"?"Finish recording":phase==="requesting"?"Cancel microphone request":clip?"Record again":"Record my recitation"}
    </button>
    {clip && <div className="mt-2 flex flex-wrap items-center gap-2">
      <audio ref={player} controls src={clip} aria-label="Your recitation" className="max-w-full"
        onPlay={e=>takeAudioTurn(e.currentTarget)}/>
      <button type="button" onClick={discard} className="am-small-action">Discard recording</button>
    </div>}
    <p role="status" className="mt-1 text-xs text-[#E6D5B8]">{message || (phase==="recording"?"Recording…":clip?"Ready to replay.":"")}</p>
  </fieldset>;
}
