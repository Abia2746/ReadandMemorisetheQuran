"use client";
import type { QuranVerse, QuranWord, WordStatus } from "@/lib/verseApi";
import { WordToken } from "./WordToken";
type Props={verse:QuranVerse;statuses:Record<string,WordStatus>;
 onSelect:(word:QuranWord,anchor:DOMRect)=>void;};
export function MushafReader({verse,statuses,onSelect}:Props){
 return <article className="am-ayah-panel" aria-label={`Qur'an ${verse.surah}:${verse.ayah}`}>
   <div className="flex items-center justify-between border-b border-[#4A3828] px-4 py-2 text-xs text-[#C8A96E]">
     <span>الْقُرْآنُ الْكَرِيمُ</span>
     <span>Surah {verse.surah} · Ayah {verse.ayah}</span>
   </div>
   <div className="am-quran" dir="rtl" lang="ar" aria-label="Uthmani Qur'an text">
     {verse.words.length===0 && verse.arabic_uthmani}
     {verse.words.map((word,i)=><span key={word.id} className="inline">
       <WordToken word={word} status={statuses[word.id]||"unknown"} onSelect={onSelect}/>
       {i<verse.words.length-1?" ":""}
     </span>)}
     <span className="mx-3 inline-block align-middle text-xl text-[#C8A96E]" aria-hidden="true">۝</span>
   </div>
   <div className="border-t border-[#4A3828] px-5 py-4">
     <p className="text-sm leading-7 text-[#E6D5B8]">{verse.translation || "An English verse translation is currently unavailable."}</p>
     {verse.translation && <p className="mt-2 text-[11px] text-[#C0AB90]">English translation: {verse.translation_attribution}</p>}
   </div>
 </article>;
}
