"use client";
import { useEffect, useState } from "react";
import { Check, RotateCcw, Sparkles } from "lucide-react";
export type StudyDrill={
 drill_id:string;kind:"idafah_preposition"|"root_construction"|"reverse_translation";
 question:string;expected_answer:string;explanation:string;
 hint:string|null;text_origin:string;source_ids:string[];
};
const heading:Record<StudyDrill["kind"],string>={
 idafah_preposition:"Idāfah & Prepositional Parsing",
 root_construction:"Root Construction · Ishtiqāq",
 reverse_translation:"Original Reverse-Translation Practice",
};
export function MasteryDrills({drills,verseKey,onComplete}:{
  drills:StudyDrill[];verseKey:string;onComplete:()=>void;
}){
  const [answers,setAnswers]=useState<Record<string,string>>({});
  const [revealed,setRevealed]=useState<Set<string>>(()=>new Set());
  const [correct,setCorrect]=useState<Set<string>>(()=>new Set());
  const [completed,setCompleted]=useState(false);
  useEffect(()=>{setAnswers({});setRevealed(new Set());setCorrect(new Set());setCompleted(false)},[verseKey]);
  useEffect(()=>{
    if(!completed&&drills.length>=10&&correct.size===drills.length){
      setCompleted(true);onComplete();
    }
  },[completed,drills.length,correct.size,onComplete]);
  return <div>
    <p className="mb-5 text-sm leading-relaxed text-[#E6D5B8]">
      Answer before revealing the key. Judge your own answer, allowing legitimate
      variants in Arabic translation. Practice examples are not Qur&apos;anic or Prophetic quotations.
    </p>
    <div className="mb-5 h-2 overflow-hidden rounded-full bg-[#4A3828]" aria-label="Drill progress">
      <div className="h-full bg-[#2E7D32] transition-[width] duration-300"
        style={{width:`${drills.length?correct.size/drills.length*100:0}%`}}/>
    </div>
    {(["idafah_preposition","root_construction","reverse_translation"] as const).map(kind=>{
      const items=drills.filter(item=>item.kind===kind);
      return <section key={kind} className="mb-6">
        <h3 className="mb-3 font-editorial text-lg text-[#EDD39F]">{heading[kind]}</h3>
        <div className="space-y-3">
          {items.map((item,index)=>{
            const show=revealed.has(item.drill_id);
            const passed=correct.has(item.drill_id);
            return <article key={item.drill_id}
              className={`rounded-xl border bg-[#241913] p-4 ${passed?"border-[#2E7D32]":"border-[#4A3828]"}`}>
              <div className="flex items-center justify-between gap-3">
                <strong className="text-xs text-[#C8A96E]">Question {index+1}</strong>
                {item.text_origin==="original_practice"&&
                  <span className="text-[10px] text-[#E6D5B8]">Original practice · not scripture</span>}
              </div>
              <p dir="auto" className="mt-2 whitespace-pre-wrap text-sm leading-7">{item.question}</p>
              <label className="mt-3 block text-xs text-[#E6D5B8]">
                Your answer
                <textarea dir="auto" value={answers[item.drill_id]||""}
                  onChange={e=>setAnswers(v=>({...v,[item.drill_id]:e.target.value}))}
                  rows={2} className="am-field mt-1 block resize-y" placeholder="Write or say your interpretation…"/>
              </label>
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" className="am-small-action" onClick={()=>setRevealed(previous=>new Set(previous).add(item.drill_id))}>
                  Reveal answer
                </button>
                {item.hint&&<details className="self-center text-xs text-[#C8A96E]">
                  <summary className="cursor-pointer">Hint</summary><p className="mt-1">{item.hint}</p>
                </details>}
              </div>
              {show&&<div className="mt-3 rounded-lg border border-[#C8A96E]/20 bg-[#2A1F18] p-3 text-sm">
                <strong className="text-[#EDD39F]">Model answer</strong>
                <p dir="auto" className="mt-1 whitespace-pre-wrap">{item.expected_answer}</p>
                <p className="mt-2 text-xs leading-relaxed text-[#C0AB90]">{item.explanation}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" className="am-small-action"
                    onClick={()=>setCorrect(p=>new Set(p).add(item.drill_id))}><Check size={14}/> I understood</button>
                  <button type="button" className="am-small-action"
                    onClick={()=>setCorrect(p=>{const n=new Set(p);n.delete(item.drill_id);return n})}>
                    <RotateCcw size={14}/> Review again
                  </button>
                </div>
              </div>}
            </article>;
          })}
        </div>
      </section>;
    })}
    {completed&&<p role="status" className="rounded-xl border border-[#2E7D32] bg-[#2E7D32]/15 p-4 text-sm text-[#E6D5B8]">
      <Sparkles size={16} className="mr-2 inline"/> Alhamdulillah — you&apos;ve reviewed all of this verse&apos;s exercises.
      You can revisit them at any time.
    </p>}
  </div>;
}
