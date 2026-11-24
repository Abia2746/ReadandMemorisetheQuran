"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AYAHS_PER_SURAH, SURAH_NAMES, validVerse } from "@/lib/quranMetadata";

const prefix="almuallim:practice:v1:";
const settingsKey=prefix+"settings";
type Entry={ayah:number;first:string;last:string};
function dayKey(date:Date) {
  return [date.getFullYear(),String(date.getMonth()+1).padStart(2,"0"),String(date.getDate()).padStart(2,"0")].join("-");
}
function entries(surah:number):Entry[] {
  const result:Entry[]=[];
  for(let ayah=1;ayah<=AYAHS_PER_SURAH[surah];ayah++){
    const raw=localStorage.getItem(prefix+surah+":"+ayah);
    if(!raw)continue;
    try {
      const item=JSON.parse(raw);
      if(typeof item.first==="string" && typeof item.last==="string")
        result.push({ayah,first:item.first,last:item.last});
    } catch {}
  }
  return result;
}

export function DevicePractice(){
  const [surah,setSurah]=useState(1);
  const [target,setTarget]=useState(2);
  const [ready,setReady]=useState(false);
  const [records,setRecords]=useState<Entry[]>([]);
  const [today,setToday]=useState("");
  const [notice,setNotice]=useState("");
  useEffect(()=>{
    function refresh(){
      try {
        const settings=JSON.parse(localStorage.getItem(settingsKey)||"{}");
        const chapter=validVerse(settings.surah,1)?settings.surah:1;
        setSurah(chapter);
        const count=settings.target;
        setTarget(Number.isInteger(count)&&count>=1&&count<=10?count:2);
        setRecords(entries(chapter));setToday(dayKey(new Date()));setReady(true);
      } catch {setReady(false);setNotice("This browser could not open your saved practice.");}
    }
    refresh();
    const timer=window.setInterval(refresh,60000);
    window.addEventListener("storage",refresh);
    window.addEventListener("focus",refresh);
    return ()=>{clearInterval(timer);window.removeEventListener("storage",refresh);window.removeEventListener("focus",refresh)};
  },[]);
  function configure(chapter:number,count:number){
    try{
      localStorage.setItem(settingsKey,JSON.stringify({surah:chapter,target:count}));
      setRecords(entries(chapter));setSurah(chapter);setTarget(count);setNotice("");
    }catch {setNotice("Could not save these settings on this device.");}
  }
  function mark(ayah:number){
    try{
      const key=prefix+surah+":"+ayah;
      const date=dayKey(new Date());
      const existing=records.find(r=>r.ayah===ayah);
      localStorage.setItem(key,JSON.stringify({first:existing?.first||date,last:date}));
      setRecords(entries(surah));setToday(date);setNotice(`Saved your practice of ${surah}:${ayah}.`);
    }catch{setNotice("Could not save this practice on this device.");}
  }
  const studied=new Set(records.map(r=>r.ayah));
  const remaining=Math.max(0,target-records.filter(r=>r.first===today).length);
  const newVerses=Array.from({length:AYAHS_PER_SURAH[surah]},(_,i)=>i+1).filter(a=>!studied.has(a)).slice(0,remaining);
  const cutoff=new Date(today+"T12:00:00");cutoff.setDate(cutoff.getDate()-7);
  const due=records.filter(r=>r.last<today).sort((a,b)=>a.last.localeCompare(b.last)||a.ayah-b.ayah);
  const groups=[
    {name:"Sabqi · Recent revision",verses:due.filter(r=>r.first>=dayKey(cutoff)).slice(0,3).map(r=>r.ayah)},
    {name:"Manzil · Older revision",verses:due.filter(r=>r.first<dayKey(cutoff)).slice(0,3).map(r=>r.ayah)},
    {name:"Sabq · New practice",verses:newVerses},
  ];
  return <section className="mb-5 rounded-2xl border border-[#91A793] bg-[#F6F3E8] p-5 text-[#283D32]">
    <h2 className="font-editorial text-2xl">My practice on this device</h2>
    <p className="mt-1 text-sm">Save the ayahs you practise here. Each new day starts with your chosen target. Missed days add no extra verses.</p>
    {ready && <>
      <div className="my-4 flex flex-wrap gap-3">
        <label className="text-sm">Surah <select className="rounded border bg-white p-2" value={surah}
          onChange={e=>configure(Number(e.target.value),target)}>
          {SURAH_NAMES.map((name,i)=><option key={name} value={i+1}>{i+1}. {name}</option>)}
        </select></label>
        <label className="text-sm">New ayahs per day <select className="rounded border bg-white p-2" value={target}
          onChange={e=>configure(surah,Number(e.target.value))}>
          {Array.from({length:10},(_,i)=><option key={i} value={i+1}>{i+1}</option>)}
        </select></label>
      </div>
      {groups.map(group=><div key={group.name} className="border-t border-[#A9B8A9] py-3">
        <h3 className="font-semibold">{group.name}</h3>
        {group.verses.length===0?<p className="text-sm">Nothing due today.</p>:group.verses.map(a=>
          <div key={a} className="flex flex-wrap items-center justify-between gap-2 py-1">
            <Link className="min-h-11 py-2 underline" href={`/?surah=${surah}&ayah=${a}`}>Open ayah {surah}:{a}</Link>
            <button type="button" className="min-h-11 rounded border border-[#607965] px-3" onClick={()=>mark(a)}>I practised {surah}:{a}</button>
          </div>)}
      </div>)}
      <p className="text-xs">Your own practice record. Only a learner action advances this plan.</p>
    </>}
    <p role="status" className="mt-2 text-sm">{notice}</p>
  </section>;
}
