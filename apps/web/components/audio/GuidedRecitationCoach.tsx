"use client";

/** Guided practice is a real learner workflow, not simulated Tajweed certification.
 * A selected Qari recording is used for reference rather than synthetic Qur'an audio.
 */
import { useEffect, useMemo, useState } from "react";
import { RecitationReplay } from "./RecitationReplay";
import Link from "next/link";

type PracticeStep = "listen"|"recite"|"compare"|"revise";
type PracticeLog = {
  verse:string;
  practisedAt:string;
  steps:PracticeStep[];
  uncertainSounds:string[];
  learnerNotes:string;
  teacherVerified:false;
};
const STEPS: {id:PracticeStep;heading:string;instruction:string}[] = [
  {id:"listen",heading:"Listen closely",instruction:"Play the verified Qari audio. Notice each short vowel, doubled consonant, and place of stopping."},
  {id:"recite",heading:"Recite from memory",instruction:"Read or recite at a comfortable pace. The existing microphone can track approximate words, not certify vowels."},
  {id:"compare",heading:"Compare carefully",instruction:"Listen again. Compare a short phrase with the reference recording. A matching transcript is not proof of matching pronunciation."},
  {id:"revise",heading:"Choose a sound to revise",instruction:"Note one uncertain sound and revisit it later. Ask a qualified Tajweed teacher about subtle articulation."},
];

export function GuidedRecitationCoach({verseRef,onListen,onStartReciting}:{
  verseRef:string;onListen:()=>void;onStartReciting:()=>void;
}){
  const [done,setDone]=useState<PracticeStep[]>([]);
  const [sound,setSound]=useState("");
  const [question,setQuestion]=useState<"stuck"|"sound"|"ready"|null>(null);
  const [notes,setNotes]=useState("");
  const [saved,setSaved]=useState(false);
  const [log,setLog]=useState<PracticeLog|null>(null);
  useEffect(()=>{setDone([]);setQuestion(null);setSound("");setNotes("");setSaved(false);setLog(null)},[verseRef]);
  const allDone=done.length===STEPS.length;
  const count=useMemo(()=>done.length, [done]);
  const toggle=(step:PracticeStep)=>{
    setSaved(false);
    setDone(prev=>prev.includes(step)?prev.filter(v=>v!==step):[...prev,step]);
  };
  const finish=()=>{
    if(!allDone)return;
    const result:PracticeLog={
      verse:verseRef,practisedAt:new Date().toISOString(),steps:done,
      uncertainSounds:sound.trim()?[sound.trim().slice(0,100)]:[],
      learnerNotes:notes.trim().slice(0,500),
      teacherVerified:false,
    };
    // Deliberately not saved to cloud or persistent storage.
    setLog(result);setSaved(true);
  };
  const exportReport=()=>{
    if(!log)return;
    const text=[
      "Al-Mu'allim • Practice reflection (self-reported)",
      "Verse: "+log.verse,"Date: "+log.practisedAt,
      "Steps: "+log.steps.join(", "),
      "Sound to revise: "+(log.uncertainSounds.join(", ")||"None noted"),
      "Learner notes: "+(log.learnerNotes||"None"),
      "Actual microphone evidence: See acoustic analysis if a validated model is available.",
      "Teacher-verified Tajweed accuracy: NOT VERIFIED",
      "This report records practice, not a pronunciation grade."
    ].join("\n");
    const blob=new Blob([text],{type:"text/plain;charset=utf-8"});
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");a.href=url;a.download="almuallim-practice-reflection.txt";
    document.body.appendChild(a);a.click();a.remove();
    window.setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  return <section className="mt-3 rounded-2xl border border-[#C8A96E]/25 bg-[#241913] p-4 sm:p-5"
    aria-label="Guided practice with Noor">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-xs uppercase tracking-[.15em] text-[#C8A96E]">Guided teacher practice</p>
        <h3 className="mt-1 font-editorial text-xl text-[#EDD39F]">Practice with Noor · {verseRef}</h3>
        <p className="mt-1 text-xs text-[#E6D5B8]">Four gentle steps. Noor guides the routine, but does not claim to have verified Tajweed.</p>
      </div>
      <span className="rounded-full border border-[#7A6548] px-3 py-1 text-xs text-[#EDD39F]">{count}/4 steps</span>
    </div>
    <div className="mt-4 grid gap-2 sm:grid-cols-2">
      {STEPS.map((step,i)=><div key={step.id} className="rounded-xl border border-[#4A3828] bg-[#2A1F18] p-3">
        <div className="flex items-start gap-2">
          <input id={`practice-${step.id}`} type="checkbox" checked={done.includes(step.id)}
            onChange={()=>toggle(step.id)} className="mt-1 accent-[#C8A96E]"/>
          <label htmlFor={`practice-${step.id}`} className="cursor-pointer">
            <span className="block text-sm font-semibold text-[#EDD39F]">{i+1}. {step.heading}</span>
            <span className="mt-1 block text-xs leading-relaxed text-[#E6D5B8]">{step.instruction}</span>
          </label>
        </div>
        {step.id==="listen"&&<button type="button" className="am-small-action mt-2" onClick={onListen}>Hear reference Qari</button>}
        {step.id==="recite"&&<button type="button" className="am-small-action mt-2" onClick={onStartReciting}>Open microphone</button>}
      </div>)}
    </div>
    <RecitationReplay/>
    <fieldset className="mt-4 rounded-xl border border-[#5C4A32] p-3">
      <legend className="px-2 text-sm text-[#EDD39F]">Ask Noor about this ayah</legend>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="am-small-action" aria-pressed={question==="stuck"}
          onClick={()=>setQuestion("stuck")}>I lost my place</button>
        <button type="button" className="am-small-action" aria-pressed={question==="sound"}
          onClick={()=>setQuestion("sound")}>How do I practise this sound?</button>
        <button type="button" className="am-small-action" aria-pressed={question==="ready"}
          onClick={()=>setQuestion("ready")}>What should I revise next?</button>
      </div>
      <p role="status" className="mt-2 text-sm text-[#E6D5B8]">
        {question==="stuck" && "Replay the ayah. Pause at the last word you remember and listen for the next word. Now cover the text and try joining those two words."}
        {question==="sound" && (sound
          ? `You chose ${sound}. Listen for it in one word, repeat that word, then return it to its phrase. Write down the word if you would like a teacher to hear it.`
          : "Choose the sound you are unsure about below. Use the same word from this ayah each time you compare.")}
        {question==="ready" && (sound
          ? `Return to the word you marked for ${sound}. Try it once from memory before replaying the reciter.`
          : "Try this ayah once with the text covered. If you need a prompt, note the word where you paused and start your next revision there.")}
      </p>
      {question && <button type="button" className="am-small-action" onClick={onListen}>Replay ayah {verseRef}</button>}
    </fieldset>
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      <label className="text-xs text-[#E6D5B8]">Uncertain sound (optional)
        <select className="am-field mt-1 w-full" value={sound} onChange={e=>{setSound(e.target.value);setSaved(false)}}>
          <option value="">No specific sound identified</option>
          <option value="fathah /a/">Fathah · /a/</option>
          <option value="kasrah /i/">Kasrah · /i/</option>
          <option value="dammah /u/">Dammah · /u/</option>
          <option value="consonant articulation">Consonant articulation / makharij</option>
          <option value="shaddah">Shaddah · doubling</option>
          <option value="madd">Madd · length</option>
          <option value="ghunnah">Ghunnah · nasalisation</option>
          <option value="stopping">Waqf · stopping</option>
        </select>
      </label>
      <label className="text-xs text-[#E6D5B8]">My reflection (optional)
        <textarea value={notes} onChange={e=>{setNotes(e.target.value);setSaved(false)}} maxLength={500} rows={3}
          placeholder="Which word or sound did I practise, and what do I want to ask my teacher?"
          className="am-field mt-1 w-full"/>
      </label>
    </div>
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <button type="button" className="am-gold-action" onClick={finish} disabled={!allDone}>Finish my practice reflection</button>
      {saved&&<button type="button" className="am-small-action" onClick={exportReport}>Export report</button>}
      <Link href="/journey/" className="am-small-action">Open adaptive Hifdh plan</Link>
    </div>
    {saved&&<p role="status" className="mt-3 text-sm text-[#E6D5B8]">Practice reflected. This records what you practised, not what the microphone verified. Your reflection is held only in this page until you export it.</p>}
  </section>;
}
