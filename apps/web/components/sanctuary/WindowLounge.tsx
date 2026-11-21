"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { CloudRain, Moon, Sun, Volume2, VolumeX, ZoomIn, Sparkles, Settings2 } from "lucide-react";
import type { RoomLighting, RoomTheme } from "./WindowLoungeScene";
import { CITY_OPTIONS, sceneLightingFromPrayerPeriods, type CityId } from "./prayerLighting";
import { useStudyAuth, accessToken } from "@/lib/auth";
import { fetchJSON, postJSON, apiPath } from "@/lib/verseApi";
import { makeBillingApi } from "@/lib/billingApi";
import { AlMuallimPaywall, type StorePrice } from "@/components/billing/Paywall";
import { ScholarshipRequest } from "@/components/billing/ScholarshipRequest";

const Scene=dynamic(()=>import("./WindowLoungeScene"),{
  ssr:false,loading:()=> <div className="grid h-full place-items-center text-sm text-[#EDD39F]">
    Preparing your 3D sanctuary…
  </div>,
});
const THEMES: {id:RoomTheme;name:string;description:string;premium:boolean}[]=[
  {id:"walnut",name:"The Window Lounge",description:"Walnut, warm parchment and a tranquil riverside arch. Free forever.",premium:false},
  {id:"midnight",name:"Midnight Celestial",description:"Deep sapphire walls and gentle lantern glow.",premium:true},
  {id:"fajr_mist",name:"Fajr Mist",description:"Soft sage tones and the calm of early light.",premium:true},
  {id:"andalusian",name:"Andalusian Courtyard",description:"Earthy stone, ornamental symmetry and warmth.",premium:true},
];
type RoomSettings={lighting:RoomLighting;theme:RoomTheme;rain_enabled:boolean;audio_enabled:boolean};
function supportsWebGL(){
  if(typeof document==="undefined")return false;
  try{const canvas=document.createElement("canvas");return Boolean(canvas.getContext("webgl2")||canvas.getContext("webgl"));}catch{return false}
}
function useRainAudio(){
  const context=useRef<AudioContext|null>(null);
  const source=useRef<AudioBufferSourceNode|null>(null);
  const [enabled,setEnabled]=useState(false);
  const stop=()=>{
    try{source.current?.stop()}catch{}
    source.current=null;void context.current?.close().catch(()=>{});context.current=null;setEnabled(false);
  };
  useEffect(()=>()=>{try{source.current?.stop()}catch{}void context.current?.close().catch(()=>{})},[]);
  const toggle=async()=>{
    if(context.current){stop();return}
    const ctx=new AudioContext();
    const buffer=ctx.createBuffer(1,ctx.sampleRate*2,ctx.sampleRate);
    const samples=buffer.getChannelData(0);
    // Gentle filtered noise generated on-device, not copyrighted recordings.
    for(let i=0;i<samples.length;i++)samples[i]=(Math.random()*2-1)*.28;
    const node=ctx.createBufferSource();node.buffer=buffer;node.loop=true;
    const filter=ctx.createBiquadFilter();filter.type="lowpass";filter.frequency.value=1150;
    const gain=ctx.createGain();gain.gain.value=.08;
    node.connect(filter);filter.connect(gain);gain.connect(ctx.destination);
    await ctx.resume();node.start();
    context.current=ctx;source.current=node;setEnabled(true);
  };
  return {enabled,toggle,stop};
}

export function WindowLounge(){
 const auth=useStudyAuth();
 const [lighting,setLighting]=useState<RoomLighting>("auto");
 const [theme,setTheme]=useState<RoomTheme>("walnut");
 const [city,setCity]=useState<CityId>("london");
 const [now,setNow]=useState(()=>new Date());
 const [rain,setRain]=useState(false);
 const [motionReduced,setMotionReduced]=useState(false);
 const [webgl,setWebgl]=useState(true);
 const [xp,setXp]=useState(0);
 const [coins,setCoins]=useState(0);
 const [proAnnual,setProAnnual]=useState(false);
 const [notice,setNotice]=useState("");
 const [error,setError]=useState("");
 const [previewTheme,setPreviewTheme]=useState<RoomTheme|null>(null);
 const previewTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
 const [paywall,setPaywall]=useState(false);
 const [scholarship,setScholarship]=useState(false);
 const [prices,setPrices]=useState<StorePrice[]>([]);
 const audio=useRainAudio();
 const billing=makeBillingApi(process.env.NEXT_PUBLIC_API_ORIGIN||
   (typeof window!=="undefined"?window.location.origin:"https://invalid.example"),accessToken);

 useEffect(()=>{
   setWebgl(supportsWebGL());
   const q=window.matchMedia("(prefers-reduced-motion: reduce)");
   setMotionReduced(q.matches);
   const update=()=>setMotionReduced(q.matches);
   q.addEventListener("change",update);
   const timer=window.setInterval(()=>setNow(new Date()),60000);
   return()=>{q.removeEventListener("change",update);window.clearInterval(timer);
     if(previewTimer.current)window.clearTimeout(previewTimer.current)};
 },[]);
 useEffect(()=>{
   if(!auth.isSignedIn)return;
   let alive=true;
   void accessToken().then(token=>Promise.all([
     fetchJSON<{settings:RoomSettings;xp:number;coins:number}>("/api/learning/sanctuary",undefined,token),
     billing.me(),billing.prices(),
   ])).then(([room,account,priceData])=>{
     if(!alive)return;
     setTheme(room.settings.theme);setLighting(room.settings.lighting);
     setRain(room.settings.rain_enabled);setXp(room.xp);setCoins(room.coins);
     setProAnnual(account.features.includes("premium_sanctuaries"));
     setPrices(priceData.plans);
   }).catch(()=>{});
   return()=>{alive=false};
 // Auth-state boundary only.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[auth.isSignedIn]);
 const effective=useMemo(()=>{
   if(lighting!=="auto")return lighting;
   return sceneLightingFromPrayerPeriods(city,now);
 },[lighting,city,now]);
 const shownTheme=previewTheme||theme;
 const persist=async(settings:RoomSettings)=>{
   if(!auth.isSignedIn){setNotice("Sign in to save your personal sanctuary across devices.");return}
   try{
     const token=await accessToken();
     const res=await fetch(apiPath("/api/learning/sanctuary"),{
       method:"PUT",headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},
       body:JSON.stringify(settings),
     });
     if(!res.ok)throw Error("Room settings could not be saved.");
     setNotice("Your personal sanctuary settings are saved.");
   }catch(e){setError(e instanceof Error?e.message:"Unable to save room settings")}
 };
 const chooseTheme=(target:RoomTheme)=>{
   setError("");setNotice("");
   if(previewTimer.current)clearTimeout(previewTimer.current);
   if(target!=="walnut"&&!proAnnual){
     setPreviewTheme(target);
     setNotice("You are previewing an optional premium room finish for 30 seconds. Your free room stays available.");
     previewTimer.current=setTimeout(()=>{
       setPreviewTheme(null);
       setNotice("Your preview has ended. The original Window Lounge remains free.");
     },30000);
     return;
   }
   setPreviewTheme(null);setTheme(target);
   void persist({lighting,theme:target,rain_enabled:rain,audio_enabled:audio.enabled});
 };
 const updateLighting=(value:RoomLighting)=>{
   setLighting(value);
   void persist({lighting:value,theme,rain_enabled:rain,audio_enabled:audio.enabled});
 };
 const updateRain=(value:boolean)=>{
   setRain(value);void persist({lighting,theme,rain_enabled:value,audio_enabled:audio.enabled});
 };
 const toggleSound=async()=>{
   setError("");
   if(!proAnnual){
     setNotice("Rain soundscapes are an optional Annual Pro feature. You can still enjoy the free visual room.");
     return;
   }
   try{
     await audio.toggle();
     void persist({lighting,theme,rain_enabled:rain,audio_enabled:!audio.enabled});
   }catch{setError("Your browser could not start rain audio. The 3D room is still available.")}
 };
 return <main className="am-page mx-auto pb-20">
   <header className="flex min-h-16 flex-wrap items-center justify-between gap-2 border-b border-[#4A3828]">
     <Link href="/" className="font-editorial text-xl text-[#D4AF37]">۞ Al-Mu&apos;allim</Link>
     <Link href="/" className="am-small-action">Return to the Mushaf</Link>
   </header>
   <section className="py-5">
     <p className="text-xs font-semibold uppercase tracking-[.2em] text-[#C8A96E]">The Window Lounge</p>
     <h1 className="mt-1 font-editorial text-3xl text-[#EDD39F]">A peaceful space for Qur&apos;an study</h1>
     <p className="mt-3 max-w-3xl text-sm leading-relaxed text-[#E6D5B8]">
       An original interactive prayer room with an arched riverside window,
       a prayer rug, Mushaf stand and gentle light. Use a finger or trackpad to
       orbit and pinch to zoom. Learning milestones unlock decorative details.
     </p>
   </section>
   <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(270px,320px)]">
     <section className="min-w-0 overflow-hidden rounded-[24px] border border-[#C8A96E]/30 bg-[#241913]">
       <div className="flex flex-wrap items-center justify-between gap-3 p-4">
         <p className="text-sm font-semibold text-[#EDD39F]">{THEMES.find(x=>x.id===shownTheme)?.name}</p>
         <span className="flex items-center gap-2 text-xs text-[#E6D5B8]">
           <ZoomIn size={14}/> Pinch, scroll or drag to explore
         </span>
       </div>
       <div className="relative h-[min(66vw,640px)] min-h-[360px] w-full bg-[radial-gradient(circle_at_50%_20%,#755a45,#241913_78%)] sm:min-h-[500px]">
         {webgl?<Scene lighting={effective} theme={shownTheme} rain={rain&&!motionReduced} xp={xp}/>:
           <div className="grid h-full place-items-center px-5 text-center">
             <div>
               <p className="font-quran text-6xl text-[#D4AF37]">۞</p>
               <p className="mt-4 font-editorial text-xl text-[#F5EBE0]">Window Lounge</p>
               <p className="mt-2 text-sm text-[#E6D5B8]">
                 WebGL is unavailable on this device. Your Qur&apos;an reading and planner still work.
               </p>
             </div>
           </div>}
         <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#1A120D]/85 to-transparent p-4 text-center text-xs text-[#F5EBE0]">
           {effective==="fajr"?"Fajr · a gentle dawn":effective==="asr"?"Asr · warm afternoon light":"Isha · quiet lantern glow"}
           {rain&&!motionReduced?" · rain on the window":""}
         </div>
       </div>
       <div className="grid gap-3 border-t border-[#4A3828] p-4 sm:grid-cols-2">
         <label className="block text-xs text-[#E6D5B8]">Atmosphere
           <select className="am-field mt-1" value={lighting} onChange={e=>updateLighting(e.target.value as RoomLighting)}>
             <option value="auto">Automatically follow selected-city prayer periods</option>
             <option value="fajr">Fajr · dawn</option>
             <option value="asr">Asr · golden hour</option>
             <option value="isha">Isha · lantern glow</option>
           </select>
         </label>
         <label className="block text-xs text-[#E6D5B8]">City for atmosphere
           <select className="am-field mt-1" value={city} onChange={e=>setCity(e.target.value as CityId)}>
             {Object.entries(CITY_OPTIONS).map(([id,c])=><option key={id} value={id}>{c.label}</option>)}
           </select>
         </label>
       </div>
       <div className="flex flex-wrap items-center gap-2 p-4 pt-0">
         <button type="button" className="am-small-action" aria-pressed={rain}
           onClick={()=>updateRain(!rain)}><CloudRain size={16}/>{rain?"Stop animated rain":"Rain on the window"}</button>
         <button type="button" className="am-small-action" aria-pressed={audio.enabled}
           onClick={()=>{void toggleSound()}}>{audio.enabled?<VolumeX size={16}/>:<Volume2 size={16}/>}
           {audio.enabled?"Stop rain sound":"Play rain sound"}
         </button>
         {motionReduced&&<span className="text-xs text-[#C0AB90]">Animations reduced according to your device preference.</span>}
       </div>
       <p className="px-4 pb-4 text-xs leading-relaxed text-[#C0AB90]">
         Prayer-time lighting uses astronomical estimates for your chosen city.
         Always follow your local mosque&apos;s prayer timetable for worship.
       </p>
     </section>

     <aside className="min-w-0 rounded-[24px] border border-[#4A3828] bg-[#241913] p-4">
       <p className="text-xs uppercase tracking-[.18em] text-[#C8A96E]">Your sanctuary</p>
       <h2 className="mt-1 font-editorial text-xl text-[#EDD39F]">Curated Collection</h2>
       <p className="mt-2 text-xs leading-relaxed text-[#E6D5B8]">
         A peaceful collection without adverts or pressure to purchase.
         Preview any premium finish first.
       </p>
       <p className="my-3 rounded-lg border border-[#C8A96E]/25 px-3 py-2 text-xs text-[#EDD39F]">
         {xp} XP · {coins} study coins
       </p>
       <div className="space-y-3">
         {THEMES.map(item=><div key={item.id} className="am-curated-card">
           <div className={`grid h-[68px] w-[64px] place-items-center rounded-xl border border-[#C8A96E]/35 text-2xl
             ${item.id==="midnight"?"bg-[#344057]":item.id==="fajr_mist"?"bg-[#A3ADAB]":item.id==="andalusian"?"bg-[#A8896C]":"bg-[#71523C]"}`}>
             ۞
           </div>
           <div className="min-w-0">
             <h3 className="break-words text-sm font-semibold text-[#F5EBE0]">{item.name}</h3>
             <p className="mt-1 break-words text-[11px] leading-relaxed text-[#C0AB90]">{item.description}</p>
             <div className="mt-3 flex flex-wrap items-center gap-2">
               <button type="button" className="am-small-action" onClick={()=>chooseTheme(item.id)}>
                 {item.premium&&!proAnnual?"Try in your room":
                  item.id===theme?"Selected":"Use this theme"}
               </button>
               {item.premium&&!proAnnual&&<span className="text-[10px] text-[#D4AF37]">Annual Pro</span>}
             </div>
           </div>
         </div>)}
       </div>
       {!proAnnual&&previewTheme&&<button type="button" className="am-small-action mt-4 w-full"
         onClick={()=>setPaywall(true)}>
         Explore optional Annual Pro room themes
       </button>}
       <p className="mt-4 text-xs leading-relaxed text-[#C0AB90]">
         Books and plants appear through learning XP. XP is earned from real study milestones, not purchased.
       </p>
     </aside>
   </div>
   {notice&&<p role="status" className="mt-4 rounded-xl border border-[#C8A96E]/25 p-3 text-xs text-[#E6D5B8]">{notice}</p>}
   {error&&<p role="alert" className="mt-4 rounded-xl border border-[#C62828] p-3 text-sm">{error}</p>}
   <AlMuallimPaywall open={paywall} reason={{kind:"sanctuary_preview",theme:THEMES.find(x=>x.id===previewTheme)?.name||"this sanctuary"}}
     prices={prices} platform="web" onClose={()=>setPaywall(false)}
     onCheckout={tier=>billing.subscribe(tier)}
     onScholarship={()=>{setPaywall(false);setScholarship(true)}}/>
   {scholarship&&<div className="fixed inset-0 z-[135] grid place-items-center bg-black/75 p-3">
     <div className="w-full max-w-lg"><ScholarshipRequest onClose={()=>setScholarship(false)}
       submitRequest={(months,note)=>billing.requestScholarship(months,note).then(()=>undefined)}/></div>
   </div>}
 </main>;
}
