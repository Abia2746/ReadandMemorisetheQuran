"use client";
import type { QuranWord, WordStatus } from "@/lib/verseApi";
type Props={
 word:QuranWord; status:WordStatus;
 onSelect:(word:QuranWord,anchor:DOMRect)=>void;
};
export function WordToken({word,status,onSelect}:Props){
 return <button type="button" lang="ar" dir="rtl"
   className="am-word rounded-lg border border-transparent px-1 font-quran text-[clamp(2rem,4vw,2.75rem)] leading-[2.3] text-[#F5EBE0] transition-colors focus-visible:outline-2 focus-visible:outline-[#D4AF37]"
   data-status={status} aria-label={`Study word ${word.index}, ${word.arabic}`}
   onClick={event=>onSelect(word,event.currentTarget.getBoundingClientRect())}>
   {word.arabic}
 </button>;
}
