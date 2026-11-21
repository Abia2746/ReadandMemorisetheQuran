"use client";
import { useState } from "react";
import { RotateCcw, BookOpen } from "lucide-react";
export type VocabItem={
 id:string;arabic:string;root:string|null;root_state:string;
 meaning:string;grammar?:string|null;
};
function Flashcard({entry}:{entry:VocabItem}){
  const [flipped,setFlipped]=useState(false);
  return <button type="button" onClick={()=>setFlipped(value=>!value)}
    aria-pressed={flipped}
    aria-label={flipped?`Show Arabic word ${entry.arabic}`:`Reveal meaning and root for ${entry.arabic}`}
    className="min-h-[148px] rounded-xl border border-[#4A3828] bg-[#2A1F18] p-4 text-center transition-colors hover:border-[#C8A96E] focus-visible:outline-2 focus-visible:outline-[#D4AF37]">
    {!flipped?<><span lang="ar" dir="rtl" className="block font-quran text-3xl leading-[2]">{entry.arabic}</span>
      <span className="text-xs text-[#C8A96E]">Tap to reveal</span></>:
      <><span className="block text-sm font-semibold text-[#F5EBE0]">{entry.meaning}</span>
        <span className="mt-3 block font-quran text-lg text-[#D4AF37]" lang="ar" dir="rtl">
          {entry.root??"—"}
        </span>
        <span className="mt-1 block text-[11px] text-[#C0AB90]">
          {entry.root_state==="lexicon_verified"?"Lexicon-grounded root":
            entry.root_state==="not_applicable"?"Particle or no applicable triliteral root":
            "Root requires lexical verification"}
        </span>{entry.grammar&&<span className="mt-1 block text-[11px] text-[#E6D5B8]">{entry.grammar}</span>}
      </>}
  </button>;
}
export function RootFlashcards({quran,commentary}:{
  quran:VocabItem[];commentary:VocabItem[];
}){
  const [part,setPart]=useState<"quran"|"commentary">("quran");
  const entries=part==="quran"?quran:commentary;
  return <div className="py-2">
    <div className="mb-4 flex flex-wrap gap-2">
      <button type="button" aria-pressed={part==="quran"} onClick={()=>setPart("quran")}
        className={`am-small-action ${part==="quran"?"border-[#D4AF37]":""}`}>
        <BookOpen size={14}/> Part A · Qur&apos;anic words ({quran.length})
      </button>
      <button type="button" aria-pressed={part==="commentary"} onClick={()=>setPart("commentary")}
        className={`am-small-action ${part==="commentary"?"border-[#D4AF37]":""}`}>
        Part B · Commentary ({commentary.length})
      </button>
    </div>
    <p className="mb-4 text-xs leading-relaxed text-[#C0AB90]">
      Part A contains only Qur&apos;anic words, in their original order.
      Part B contains terms from retrieved classical commentary.
      Roots awaiting independent verification are marked clearly.
    </p>
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
      {entries.map(entry=><Flashcard key={entry.id} entry={entry}/>)}
    </div>
  </div>;
}
