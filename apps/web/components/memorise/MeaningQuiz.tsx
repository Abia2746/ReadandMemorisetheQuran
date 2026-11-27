"use client";
import { useEffect, useRef, useState } from "react";
import { mountMeaningQuiz } from "@/lib/meaningQuiz.mjs";
import { fetchVerse, type QuranVerse } from "@/lib/verseApi";
import { AYAHS_PER_SURAH, type ReciterId } from "@/lib/quranMetadata";

export function MeaningQuiz({verse, reciter, language, profile}: {verse:QuranVerse; reciter:ReciterId; language:string; profile:string}) {
  const [end,setEnd]=useState(verse.ayah);
  const [attempt,setAttempt]=useState(0);
  const [message,setMessage]=useState("");
  const container=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    const host=container.current;
    if (!host) return;
    host.replaceChildren();
    if (!attempt) {setMessage(""); return;}
    const controller=new AbortController();
    async function load(){
      const cards=[];
      for(let ayah=verse.ayah; ayah<=end; ayah++){
        setMessage("Loading word meanings for "+verse.surah+":"+ayah+"…");
        const data=ayah===verse.ayah ? verse : await fetchVerse(verse.surah,ayah,reciter,language,controller.signal);
        if(controller.signal.aborted)return;
        if(data.surah!==verse.surah || data.ayah!==ayah || !data.words.length)
          throw Error("Word meanings are unavailable for "+verse.surah+":"+ayah+". Try again or select a shorter passage.");
        for(const word of data.words) cards.push({arabic:word.arabic,meaning:word.meaning||"",ref:word.id});
      }
      setMessage("");
      mountMeaningQuiz(host!,cards,profile,language);
    }
    void load().catch(error=>{if(!controller.signal.aborted)setMessage(error instanceof Error?error.message:"Word meanings unavailable.")});
    return ()=>controller.abort();
  },[attempt,end,verse,reciter,language,profile]);
  return <section className="am-ayah-panel am-meaning-quiz p-5">
    <h2 className="font-editorial text-xl">Word meanings</h2>
    <label>From {verse.surah}:{verse.ayah} through ayah <select className="am-field" value={end}
      onChange={event=>{setAttempt(0);setEnd(Number(event.target.value))}}>
      {Array.from({length:AYAHS_PER_SURAH[verse.surah]-verse.ayah+1},(_,i)=>verse.ayah+i).map(a=><option key={a}>{a}</option>)}
    </select></label>
    <button className="am-small-action" onClick={()=>setAttempt(n=>n+1)}>{attempt?"Restart quiz":"Start quiz"}</button>
    <p role="status">{message}</p><div ref={container}/>
  </section>;
}
