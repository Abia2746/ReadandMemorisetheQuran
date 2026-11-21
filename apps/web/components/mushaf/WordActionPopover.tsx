"use client";
import { createPortal } from "react-dom";
import { useEffect, useRef } from "react";
import { Play, Repeat2, Eye, Flag, Check } from "lucide-react";
import type { QuranWord } from "@/lib/verseApi";
type Props={
  word:QuranWord;anchor:DOMRect;
  canLoop:boolean;isReview:boolean;
  onHear:()=>void;onLoop:()=>void;onReveal:()=>void;
  onFlag:()=>void;onCorrect:()=>void;onClose:()=>void;
};
export function WordActionPopover(props:Props){
  const popover=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    const close=(event:PointerEvent)=>{
      if(popover.current?.contains(event.target as Node))return;
      props.onClose();
    };
    const esc=(event:KeyboardEvent)=>{if(event.key==="Escape")props.onClose()};
    document.addEventListener("pointerdown",close);
    document.addEventListener("keydown",esc);
    const onScroll=()=>props.onClose();
    window.addEventListener("scroll",onScroll,{passive:true});
    return ()=>{document.removeEventListener("pointerdown",close);
      document.removeEventListener("keydown",esc);window.removeEventListener("scroll",onScroll)};
  },[props.onClose]);
  if(typeof document==="undefined")return null;
  const left=Math.max(12,Math.min(window.innerWidth-12,props.anchor.left+props.anchor.width/2));
  const top=Math.max(8,props.anchor.top-12);
  const button="flex min-h-10 items-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 text-xs text-[#F5EBE0] hover:bg-[#4A3828] focus-visible:outline-2 focus-visible:outline-[#D4AF37]";
  return createPortal(
    <div ref={popover} role="dialog" aria-label={`Actions for ${props.word.arabic}`}
      className="fixed z-[100] flex max-w-[95vw] -translate-x-1/2 -translate-y-full flex-wrap justify-center gap-1 rounded-xl border border-[#C8A96E]/40 bg-[#2A1F18] p-2 shadow-2xl"
      style={{left,top}}>
      <button className={button} type="button" onClick={props.onHear}><Play size={14}/> Hear from here</button>
      <button className={button} type="button" disabled={!props.canLoop}
        title={props.canLoop?"Repeat a source-timed phrase 3 times":"Word timings unavailable for this recording"}
        onClick={props.onLoop}><Repeat2 size={14}/> Loop 3×</button>
      <button className={button} type="button" onClick={props.onReveal}><Eye size={14}/> Reveal phrase</button>
      <button className={button} type="button" onClick={props.onFlag}><Flag size={14}/> Flag word</button>
      {props.isReview&&<button className={button} type="button" onClick={props.onCorrect}><Check size={14}/> Flagged incorrectly</button>}
    </div>,document.body);
}
