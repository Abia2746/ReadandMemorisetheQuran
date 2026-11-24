"use client";
import { useCallback, useEffect, useState } from "react";
import { DevicePractice } from "./DevicePractice";
import Link from "next/link";
import { CalendarDays, Check, Clock3, Sparkles, SunMoon, RotateCcw } from "lucide-react";
import { useStudyAuth, accessToken } from "@/lib/auth";
import { fetchJSON, postJSON, apiPath } from "@/lib/verseApi";
import { SURAH_NAMES } from "@/lib/quranMetadata";

type Goal="surah"|"whole";
type Config={
 title:string;goal:Goal;surah:number;months:number;
 weekdays:number[];sabq_minutes:number;review_minutes:number;
 study_time:string;reminder_minutes:number;
};
type VerseKey={surah:number;ayah:number};
type PlanState={
 configured:boolean;plan_id?:string;title?:string;goal?:Goal;surah?:number;
 deadline?:string;today?:string;progress_pct?:number;memorised?:number;
 goal_total?:number;remaining?:number;recommended_sabq?:number;
 sabq?:VerseKey[];sabqi?:VerseKey[];manzil?:VerseKey[];
 difficult_words?:{surah:number;ayah:number;word_index:number;arabic:string;gloss:string;}[];
 study_today?:boolean;completed_today?:boolean;overload?:boolean;
 noor_message?:string;settings?:{
  months:number;weekdays:number[];sabq_minutes:number;review_minutes:number;
  study_time:string;reminder_minutes:number;timezone_name:string;
 };
};
const defaults:Config={
 title:"A Plan with Noor",goal:"surah",surah:2,months:24,
 weekdays:[0,1,2,3,4,5],sabq_minutes:35,review_minutes:15,
 study_time:"18:30",reminder_minutes:10,
};
const week=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];

function VerseBadge({verse}:{verse:VerseKey}){
 return <Link href={`/?surah=${verse.surah}&ayah=${verse.ayah}`}
   className="inline-flex min-h-10 items-center rounded-full border border-[#C8A96E]/30 bg-[#2A1F18] px-3 text-xs text-[#F5EBE0] hover:border-[#D4AF37]">
   {verse.surah}:{verse.ayah}
 </Link>;
}
function StudyGroup({title,subtitle,items,accent}:{
 title:string;subtitle:string;items:VerseKey[];accent:string;
}){
 return <section className="rounded-2xl border border-[#4A3828] bg-[#241913] p-5">
   <div className="flex items-center justify-between gap-2">
     <h3 className="font-editorial text-lg text-[#EDD39F]">{title}</h3>
     <span className="rounded-full border border-[#4A3828] px-2 text-xs text-[#C0AB90]">{items.length}</span>
   </div>
   <p className="my-2 text-xs leading-relaxed text-[#E6D5B8]">{subtitle}</p>
   <div className="flex flex-wrap gap-2">
     {items.length?items.map((verse,i)=><VerseBadge key={`${verse.surah}:${verse.ayah}:${i}`} verse={verse}/>):
       <p className="text-xs text-[#C0AB90]">Nothing due in this group today.</p>}
   </div>
 </section>;
}

export function NoorPlanner(){
 const auth=useStudyAuth();
 const [config,setConfig]=useState<Config>(defaults);
 const [state,setState]=useState<PlanState|null>(null);
 const [loading,setLoading]=useState(false);
 const [saving,setSaving]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const [expanded,setExpanded]=useState(true);
 const [coins,setCoins]=useState(0);
 const [xp,setXp]=useState(0);
 const fetchPlan=useCallback(async()=>{
   const token=await accessToken();
   const [p,profile]=await Promise.all([
     fetchJSON<PlanState>("/api/learning/plan/today",undefined,token),
     fetchJSON<{xp:number;coins:number}>("/api/learning/profile",undefined,token)
   ]);
   setState(p);setXp(profile.xp);setCoins(profile.coins);
   if(p.configured&&p.settings){
     setConfig({
       title:p.title||defaults.title,goal:p.goal||"surah",surah:p.surah||2,
       months:p.settings.months,weekdays:p.settings.weekdays,
       sabq_minutes:p.settings.sabq_minutes,
       review_minutes:p.settings.review_minutes,
       study_time:p.settings.study_time,
       reminder_minutes:p.settings.reminder_minutes,
     });
     setExpanded(false);
   }
 },[]);
 useEffect(()=>{
   if(!auth.isSignedIn)return;
   let cancelled=false;setLoading(true);
   void fetchPlan().catch(e=>{if(!cancelled)setError(e instanceof Error?e.message:"Planner unavailable")})
     .finally(()=>{if(!cancelled)setLoading(false)});
   return()=>{cancelled=true};
 },[auth.isSignedIn,fetchPlan]);

 const modify=<K extends keyof Config>(field:K,value:Config[K])=>
   setConfig(p=>({...p,[field]:value}));
 const save=async()=>{
   setSaving(true);setError("");setNotice("");
   try{
     const token=await accessToken();
     const url=state?.configured&&state.plan_id?
       `/api/learning/plans/${state.plan_id}`:"/api/learning/plans";
     const response=await fetch(apiPath(url),{
       method:state?.configured?"PUT":"POST",
       headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},
       body:JSON.stringify(config),
     });
     if(!response.ok){
       const body=await response.json().catch(()=>null);
       throw Error(body?.detail?.message||"Your plan could not be saved.");
     }
     await fetchPlan();setNotice("Your plan is saved. Existing memorisation is preserved.");setExpanded(false);
   }catch(e){setError(e instanceof Error?e.message:"Unable to save plan")}
   finally{setSaving(false)}
 };
 const markToday=async()=>{
   if(!state?.plan_id)return;
   setError("");setNotice("");
   try{
     const token=await accessToken();
     await postJSON("/api/learning/plan/complete-day",token,{plan_id:state.plan_id});
     await fetchPlan();setNotice("Alhamdulillah — today's effort is saved, with no penalties.");
   }catch(e){setError(e instanceof Error?e.message:"Could not save today's work")}
 };
 const exportCalendar=async()=>{
   if(!state?.plan_id)return;
   try{
     const token=await accessToken();
     const res=await fetch(apiPath(`/api/learning/calendar.ics?plan_id=${state.plan_id}`),
       {headers:{Authorization:`Bearer ${token}`},cache:"no-store"});
     if(!res.ok)throw Error("Calendar export unavailable");
     const file=new Blob([await res.text()],{type:"text/calendar;charset=utf-8"});
     const url=URL.createObjectURL(file);
     const link=document.createElement("a");link.href=url;link.download="almuallim-noor-90-days.ics";
     document.body.appendChild(link);link.click();link.remove();
     window.setTimeout(()=>URL.revokeObjectURL(url),1000);
     setNotice("Your 90-day calendar was exported. Import it and enable alerts in your device's Calendar settings.");
   }catch(e){setError(e instanceof Error?e.message:"Calendar export failed")}
 };

 return <main className="am-page mx-auto pb-20">
   <header className="flex min-h-16 flex-wrap items-center justify-between gap-2 border-b border-[#4A3828]">
     <Link href="/" className="font-editorial text-xl text-[#D4AF37]">۞ Al-Mu&apos;allim</Link>
     <Link href="/" className="am-small-action">Return to the Qur&apos;an</Link>
   </header>
   <section className="py-6">
     <p className="text-xs font-semibold tracking-[.2em] text-[#C8A96E] uppercase">My Journey</p>
     <h1 className="mt-1 font-editorial text-3xl text-[#EDD39F]">A Plan with Noor</h1>
     <p className="mt-3 max-w-2xl text-sm leading-relaxed text-[#E6D5B8]">
       A calm, editable Hifz companion. Missed days are recalculated without penalties.
       Revise what you know, study a little new Qur&apos;an, and progress at your own pace.
     </p>
   </section>
   {!auth.loading&&!auth.isSignedIn&&<DevicePractice/>}
   {!auth.loading&&!auth.isSignedIn&&<section className="rounded-2xl border border-[#4A3828] bg-[#241913] p-6">
     <h2 className="font-editorial text-xl text-[#EDD39F]">Your first plan is free forever</h2>
     <p className="mt-2 text-sm text-[#E6D5B8]">Sign in to keep your saved progress across devices. Reading and Qari listening remain free without a login.</p>
     {auth.configured&&<button type="button" onClick={()=>{void auth.signIn()}} className="am-gold-action mt-4">Sign in to begin</button>}
     {!auth.configured&&<p className="mt-4 text-sm text-[#C0AB90]">Secure study accounts are not configured on this deployment yet.</p>}
   </section>}
   {loading&&<p role="status" className="text-[#E6D5B8]">Loading your saved plan…</p>}
   {auth.isSignedIn&&<div className="space-y-5">
     {error&&<p role="alert" className="rounded-xl border border-[#C62828] p-3 text-sm">{error}</p>}
     {notice&&<p role="status" className="rounded-xl border border-[#2E7D32] p-3 text-sm">{notice}</p>}
     {state?.configured&&<>
       <div className="grid grid-cols-3 gap-2">
         {[
           ["Memorised",`${state.memorised||0} / ${state.goal_total||0}`],
           ["Progress",`${state.progress_pct??0}%`],
           ["Study rewards",`${xp} XP · ${coins} coins`],
         ].map(([key,value])=><div key={key} className="rounded-xl border border-[#4A3828] bg-[#241913] p-3 text-center">
           <p className="text-[11px] text-[#C0AB90]">{key}</p>
           <p className="mt-1 text-sm font-semibold text-[#EDD39F] sm:text-lg">{value}</p>
         </div>)}
       </div>
       <div className="rounded-2xl border border-[#C8A96E]/25 bg-[#2A1F18] p-5">
         <p className="flex items-center gap-2 text-xs font-semibold text-[#D4AF37]">
           <Sparkles size={15}/> Noor&apos;s guidance
         </p>
         <p className="mt-2 text-sm leading-relaxed text-[#F5EBE0]">{state.noor_message}</p>
         {state.overload&&<p className="mt-2 text-xs text-[#E6D5B8]">
           Your current deadline may be too demanding. Extend the plan or choose more study days; never rush Tajweed.
         </p>}
         {state.completed_today&&<p className="mt-3 text-xs text-[#2FA76B]">Today&apos;s new memorisation is recorded. You can rest.</p>}
       </div>
       <div className="grid gap-3 lg:grid-cols-3">
         <StudyGroup title="Sabq · New" subtitle={state.completed_today?"You have finished today’s new passage. Your next study day will bring the next verses.":"Your recommended new verses, in gentle groups."} items={state.sabq||[]} accent="#D4AF37"/>
         <StudyGroup title="Sabqi · Recent" subtitle="Recently memorised verses and red-flagged passages." items={state.sabqi||[]} accent="#2E7D32"/>
         <StudyGroup title="Manzil · Older" subtitle="Older memorisation to revisit before it fades." items={state.manzil||[]} accent="#C8A96E"/>
       </div>
       {(state.difficult_words?.length||0)>0&&<div className="rounded-xl border border-[#4A3828] bg-[#241913] p-4">
         <h3 className="font-editorial text-lg text-[#EDD39F]">Priority: Difficult Words</h3>
         <div className="mt-3 flex flex-wrap gap-2">{state.difficult_words?.slice(0,10).map(w=>
           <span key={`${w.surah}:${w.ayah}:${w.word_index}`}
             className="rounded-lg border border-[#C62828]/35 bg-[#C62828]/10 px-3 py-2">
             <span lang="ar" dir="rtl" className="font-quran text-2xl">{w.arabic}</span>
             <span className="ml-2 text-xs text-[#E6D5B8]">{w.surah}:{w.ayah}</span>
           </span>)}</div>
       </div>}
       <div className="flex flex-wrap gap-3">
         <button type="button" className="am-gold-action" disabled={state.completed_today||!state.study_today}
           onClick={()=>{void markToday()}}><Check size={16}/>
           {state.completed_today?"Today's plan completed":"Mark today's Sabq complete"}</button>
         <button type="button" className="am-small-action" onClick={()=>{void exportCalendar()}}>
           <CalendarDays size={16}/> Export 90-day calendar (.ics)
         </button>
         <button type="button" className="am-small-action" onClick={()=>setExpanded(v=>!v)}>
           <RotateCcw size={16}/> {expanded?"Close settings":"Edit my plan"}
         </button>
       </div>
     </>}
     {(!state?.configured||expanded)&&<form onSubmit={e=>{e.preventDefault();void save()}}
       className="rounded-2xl border border-[#4A3828] bg-[#241913] p-5">
       <h2 className="mb-4 font-editorial text-xl text-[#EDD39F]">Shape your study routine</h2>
       <div className="grid gap-4 sm:grid-cols-2">
         <label className="block text-xs font-semibold text-[#E6D5B8]">
           Memorisation goal
           <select className="am-field mt-2" value={config.goal} onChange={e=>modify("goal",e.target.value as Goal)}>
             <option value="surah">One surah</option><option value="whole">The whole Qur&apos;an</option>
           </select>
         </label>
         {config.goal==="surah"&&<label className="block text-xs font-semibold text-[#E6D5B8]">
           Choose a surah
           <select className="am-field mt-2" value={config.surah} onChange={e=>modify("surah",Number(e.target.value))}>
             {SURAH_NAMES.map((name,i)=><option key={name} value={i+1}>{i+1}. {name}</option>)}
           </select>
         </label>}
         <label className="block text-xs font-semibold text-[#E6D5B8]">
           Target duration (months)
           <input className="am-field mt-2" type="number" min={1} max={120} value={config.months}
             onChange={e=>modify("months",Math.max(1,Math.min(120,Number(e.target.value)||1)))}/>
         </label>
         <label className="block text-xs font-semibold text-[#E6D5B8]">
           New memorisation (minutes)
           <input className="am-field mt-2" type="number" min={10} max={120} value={config.sabq_minutes}
             onChange={e=>modify("sabq_minutes",Number(e.target.value))}/>
         </label>
         <label className="block text-xs font-semibold text-[#E6D5B8]">
           Revision (minutes)
           <input className="am-field mt-2" type="number" min={0} max={90} value={config.review_minutes}
             onChange={e=>modify("review_minutes",Number(e.target.value))}/>
         </label>
         <label className="block text-xs font-semibold text-[#E6D5B8]">
           Preferred study time
           <input className="am-field mt-2" type="time" value={config.study_time}
             onChange={e=>modify("study_time",e.target.value)}/>
         </label>
         <label className="block text-xs font-semibold text-[#E6D5B8]">
           Calendar reminder (minutes before)
           <select className="am-field mt-2" value={config.reminder_minutes}
             onChange={e=>modify("reminder_minutes",Number(e.target.value))}>
             {[0,5,10,15,30,45,60].map(n=><option key={n} value={n}>{n} minutes</option>)}
           </select>
         </label>
       </div>
       <fieldset className="mt-5">
         <legend className="mb-2 text-xs font-semibold text-[#E6D5B8]">My study days</legend>
         <div className="flex flex-wrap gap-2">{week.map((label,i)=><button key={label}
           type="button" aria-pressed={config.weekdays.includes(i)}
           onClick={()=>modify("weekdays",
             config.weekdays.includes(i)?config.weekdays.filter(d=>d!==i):
             [...config.weekdays,i].sort((a,b)=>a-b))}
           className={`min-h-10 rounded-full border px-3 text-xs ${config.weekdays.includes(i)?
             "border-[#D4AF37] bg-[#4A3828] text-[#F5EBE0]":
             "border-[#4A3828] text-[#E6D5B8]"}`}>{label}</button>)}</div>
       </fieldset>
       <button className="am-gold-action mt-5" disabled={saving||config.weekdays.length===0} type="submit">
         {saving?"Saving plan…":state?.configured?"Save changes without losing progress":"Create my free plan"}</button>
     </form>}
     <p className="text-xs leading-relaxed text-[#C0AB90]">
       Web browsers cannot send background alerts while closed—export your 90-day schedule
       to Apple or Google Calendar for reliable device notifications. After importing,
       enable alerts in your device settings.
     </p>
   </div>}
 </main>;
}
