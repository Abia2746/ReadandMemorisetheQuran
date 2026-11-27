"use client";
import { useState } from "react";
import type { QuranWord, WordStatus } from "@/lib/verseApi";
import { Eye, Sparkles } from "lucide-react";
type Props={preview:number|null;words:QuranWord[];statuses:Record<string,WordStatus>;revealed?:Set<string>;
  onSelect:(word:QuranWord,anchor:DOMRect)=>void};
export function MeaningTileGrid({preview,words,statuses,revealed,onSelect}:Props) {
  const [hints,setHints]=useState<Set<string>>(()=>new Set());
  const flipHint=(id:string)=>setHints(prev=>{
    const n=new Set(prev);if(n.has(id))n.delete(id);else n.add(id);return n;
  });
  return <div>
    <p className="mb-4 text-sm leading-relaxed text-[#E6D5B8]">
      Recite the Arabic from each English clue. A gold outline follows the current word. Recognised words reveal themselves;
      tap the small hint for only the first Arabic letter.
    </p>
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4" role="group"
      aria-label="English clue recall tiles">
      {words.map((word,i)=>{
        const status=statuses[word.id]||"unknown";
        const shown=status==="confirmed"||status==="review"||Boolean(revealed?.has(word.id));
        const showHint=hints.has(word.id);
        return <div key={word.id}
          className={`am-meaning-tile group relative min-h-[112px] rounded-2xl border p-3 text-center transition-colors duration-100 motion-reduce:transition-none
          ${preview===i?"ring-2 ring-[#D4AF37]":""}
          ${status==="confirmed"?"border-[#2E7D32] bg-[#2E7D32]/20":
          status==="review"?"border-[#C62828] bg-[#C62828]/15":
          "border-[#4A3828] bg-[#2A1F18]"}`}
          aria-current={preview===i?"location":undefined} data-status={status}>
          <button type="button" aria-label={`Open practice actions for clue ${word.index}`}
            onClick={event=>onSelect(word,event.currentTarget.getBoundingClientRect())}
            className="flex h-full min-h-[74px] w-full flex-col items-center justify-center gap-2 focus-visible:outline-2 focus-visible:outline-[#D4AF37]">
            {shown?<span className="am-meaning-flip font-quran text-3xl leading-relaxed" lang="ar" dir="rtl">{word.arabic}</span>
              :<span className="text-sm font-semibold text-[#F5EBE0]">{word.meaning||"Meaning unavailable"}</span>}
            <span className="text-[10px] text-[#C8A96E]">{status==="confirmed"?"Matched in sequence":status==="review"?"Review suggested":revealed?.has(word.id)?"Phrase revealed for practice":`Word ${word.index}`}</span>
          </button>
          {(!shown)&&<button type="button" onClick={()=>flipHint(word.id)}
            className="absolute bottom-1 right-1 grid h-8 w-8 place-items-center rounded-full text-[#D4AF37] hover:bg-[#4A3828]"
            aria-label={showHint?"Hide first Arabic letter":"Peek first Arabic letter"}>
            {showHint?<span dir="rtl" className="font-quran text-xl">{Array.from(word.arabic)[0]}</span>:<Eye size={15}/>}
          </button>}
        </div>;
      })}
    </div>
    <p className="mt-4 text-xs text-[#C0AB90]">Recognition confirms approximate word sequence, not subtle ghunnah, madd or makharij. Use Qari audio or a qualified teacher for Tajweed.</p>
  </div>;
}
