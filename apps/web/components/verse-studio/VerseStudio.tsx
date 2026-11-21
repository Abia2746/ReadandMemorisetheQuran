"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, BookText, GraduationCap, Layers3, LoaderCircle, LockKeyhole,
  RotateCcw, ShieldCheck } from "lucide-react";
import { AYAHS_PER_SURAH, SURAH_NAMES, validVerse } from "@/lib/quranMetadata";
import { accessToken, useStudyAuth } from "@/lib/auth";
import { fetchJSON, fetchVerse, postJSON, type QuranVerse } from "@/lib/verseApi";
import { SourcePills, type TafsirSource } from "./SourcePills";
import { RootFlashcards, type VocabItem } from "./RootFlashcards";
import { MasteryDrills, type StudyDrill } from "./MasteryDrills";
import { AlMuallimPaywall, type StorePrice } from "@/components/billing/Paywall";
import { ScholarshipRequest } from "@/components/billing/ScholarshipRequest";
import { makeBillingApi } from "@/lib/billingApi";

type Claim = {
 claim_id:string;section:string;text:string;speaker:string|null;
 kind:string;evidence_state:"source_supported"|"needs_review"|"unavailable";
 source_ids:string[];is_verbatim:boolean;quote_arabic:string|null;
};
type TafsirPayload={
 sections:{section:string;heading:string;claims:Claim[]}[];
 sources:TafsirSource[];completion:string;public_quality_notes:string[];
};
type QuranVocabulary={
 word_id:string;index:number;arabic_uthmani:string;literal_gloss:string;
 root:string|null;root_state:string;grammar:string|null;
};
type TafsirVocabulary={
 arabic:string;root:string|null;root_state:string;
 literal_gloss:string;source_ids:string[];
};
type DrillsPayload={
 quran_vocabulary:QuranVocabulary[];tafsir_vocabulary:TafsirVocabulary[];
 drills:StudyDrill[];completion:string;public_quality_notes:string[];
 sources:TafsirSource[];
};
const names=["Meaning & Context","Word & Fiqh Insights","Root Flashcards","Arabic Mastery Drills"] as const;
const symbols=[BookOpen,BookText,Layers3,GraduationCap] as const;

export function VerseStudio({initialSurah,initialAyah}:{initialSurah:number;initialAyah:number}){
 const [surah,setSurah]=useState(validVerse(initialSurah,initialAyah)?initialSurah:2);
 const [ayah,setAyah]=useState(validVerse(initialSurah,initialAyah)?initialAyah:60);
 const [verse,setVerse]=useState<QuranVerse|null>(null);
 const [tab,setTab]=useState(0);
 const [tafsir,setTafsir]=useState<TafsirPayload|null>(null);
 const [drills,setDrills]=useState<DrillsPayload|null>(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [verseError,setVerseError]=useState("");
 const [paywall,setPaywall]=useState(false);
 const [scholarship,setScholarship]=useState(false);
 const [prices,setPrices]=useState<StorePrice[]>([]);
 const [drillsComplete,setDrillsComplete]=useState(false);
 const auth=useStudyAuth();
 const billing=makeBillingApi(process.env.NEXT_PUBLIC_API_ORIGIN??windowSafeOrigin(),accessToken);
 function windowSafeOrigin(){return typeof window!=="undefined"?window.location.origin:"https://invalid.example";}

 useEffect(()=>{
   const controller=new AbortController();
   setVerse(null);setVerseError("");setTafsir(null);setDrills(null);setDrillsComplete(false);
   fetchVerse(surah,ayah,"dosari","en",controller.signal)
     .then(data=>{if(!controller.signal.aborted)setVerse(data)})
     .catch(e=>{if(!controller.signal.aborted)setVerseError(e instanceof Error?e.message:"Source unavailable")});
   return()=>controller.abort();
 },[surah,ayah]);

 useEffect(()=>{
   if(!auth.isSignedIn)return;
   let alive=true;
   void billing.prices().then(r=>{if(alive)setPrices(r.plans)})
     .catch(()=>{});
   return()=>{alive=false};
 // Auth is the trigger; avoid re-fetching on each UI render.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[auth.isSignedIn]);

 useEffect(()=>{
   if(!auth.isSignedIn)return;
   if(tab<=1&&tafsir)return;
   if(tab>=2&&drills)return;
   const controller=new AbortController();
   setBusy(true);setError("");
   const route=tab<=1?"tafsir":"study-drills";
   void accessToken()
     .then(token=>fetchJSON<TafsirPayload|DrillsPayload>(
       `/api/verse/${surah}/${ayah}/${route}?lang=en`,controller.signal,token))
     .then(body=>{
       if(controller.signal.aborted)return;
       if(route==="tafsir")setTafsir(body as TafsirPayload);
       else setDrills(body as DrillsPayload);
     })
     .catch(e=>{
       if(controller.signal.aborted)return;
       if(e?.status===403&&e?.code==="verse_limit_reached")setPaywall(true);
       else setError(e instanceof Error?e.message:"Deep study unavailable");
     })
     .finally(()=>{if(!controller.signal.aborted)setBusy(false)});
   return()=>controller.abort();
 },[tab,surah,ayah,auth.isSignedIn,tafsir,drills]);

 const changeSurah=(n:number)=>{setSurah(n);setAyah(1);setTab(0)};
 const claimList=(id:string)=>tafsir?.sections.filter(s=>s.section===id)
   .flatMap(s=>s.claims)||[];
 const section=(id:string)=><div className="space-y-4">
   {claimList(id).length===0?<p className="text-sm text-[#C0AB90]">
     Nothing source-supported is available for this section yet.
   </p>:claimList(id).map((item)=>{
     const sourceLabels=item.source_ids.map(id=>tafsir?.sources.find(s=>s.source_id===id)?.author)
       .filter(Boolean).join(" • ");
     return <article key={item.claim_id} className="rounded-xl border border-[#4A3828] bg-[#241913] p-4">
       {item.speaker&&<p className="mb-2 text-xs font-semibold text-[#C8A96E]">{item.speaker}</p>}
       <p className="whitespace-pre-wrap text-sm leading-[1.9] text-[#F5EBE0]">{item.text}</p>
       {item.is_verbatim&&item.quote_arabic&&<p dir="rtl" lang="ar" className="mt-3 font-quran text-2xl leading-[2.1]">{item.quote_arabic}</p>}
       {sourceLabels&&<p className="mt-3 text-xs text-[#C8A96E]">Commentary: {sourceLabels}</p>}
       {item.evidence_state!=="source_supported"&&
         <p className="mt-2 text-xs text-[#C0AB90]">Scholarly attribution requires further review.</p>}
     </article>;
   })}
 </div>;

 const quranVocab:VocabItem[]=(drills?.quran_vocabulary||[]).map(w=>({
   id:w.word_id,arabic:w.arabic_uthmani,root:w.root,root_state:w.root_state,
   meaning:w.literal_gloss,grammar:w.grammar,
 }));
 const commentaryVocab:VocabItem[]=(drills?.tafsir_vocabulary||[]).map((w,i)=>({
   id:`commentary-${i}`,arabic:w.arabic,root:w.root,root_state:w.root_state,
   meaning:w.literal_gloss,
 }));
 const onMastered=useCallback(()=>{
   setDrillsComplete(true);
   // Rewards must be confirmed by authenticated server, never browser-only XP.
   void accessToken().then(token=>postJSON(
     "/api/learning/drills/complete",token,{surah,ayah}
   )).catch(()=>{});
 },[surah,ayah]);

 return <main className="am-page mx-auto pb-16">
   <header className="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b border-[#4A3828]">
     <Link href="/" className="font-editorial text-xl text-[#D4AF37]">۞ Al-Mu&apos;allim</Link>
     <Link href="/" className="am-small-action">Return to the free Mushaf</Link>
   </header>
   <section className="mt-4">
     <div className="flex flex-wrap items-center gap-3">
       <h1 className="font-editorial text-2xl text-[#EDD39F]">Verse Studio</h1>
       <label className="ml-auto text-xs text-[#E6D5B8]">Surah
         <select className="am-field mt-1 max-w-52" value={surah} onChange={e=>changeSurah(Number(e.target.value))}>
           {SURAH_NAMES.map((name,i)=><option key={name} value={i+1}>{i+1}. {name}</option>)}
         </select>
       </label>
       <label className="text-xs text-[#E6D5B8]">Ayah
         <select className="am-field mt-1" value={ayah} onChange={e=>{setAyah(Number(e.target.value));setTab(0)}}>
           {Array.from({length:AYAHS_PER_SURAH[surah]},(_,i)=><option key={i+1} value={i+1}>{i+1}</option>)}
         </select>
       </label>
     </div>
     <p className="mt-2 text-xs text-[#C0AB90]">
       Classical sources · Arabic vocabulary · self-paced practice · no invented quotations
     </p>
     {verse?<div className="am-ayah-panel mt-4">
       <p className="border-b border-[#4A3828] px-5 py-2 text-xs text-[#C8A96E]">
         {SURAH_NAMES[surah-1]} · {surah}:{ayah}
       </p>
       <div dir="rtl" lang="ar" className="am-quran">{verse.arabic_uthmani}</div>
       <p className="border-t border-[#4A3828] px-5 py-3 text-sm leading-7">{verse.translation}</p>
       <p className="px-5 pb-3 text-[11px] text-[#C0AB90]">English translation: {verse.translation_attribution}</p>
     </div>:<p role="status" className="am-ayah-panel mt-4 p-5 text-sm text-[#E6D5B8]">
       {verseError||"Loading the verse from the canonical Qur'an source…"}
     </p>}
   </section>
   <section className="mt-5 overflow-hidden rounded-2xl border border-[#4A3828] bg-[#1A120D]">
     <div role="tablist" aria-label="Verse Studio learning sections"
       className="am-verse-tabs" style={{scrollbarWidth:"thin"}}>
       {names.map((name,i)=>{
         const Icon=symbols[i];
         return <button key={name} type="button" role="tab"
           aria-selected={tab===i}
           className="am-verse-tab flex items-center gap-2"
           onClick={()=>setTab(i)}><Icon size={15}/>{name}</button>;
       })}
     </div>
     <div role="tabpanel" className="min-h-[220px] p-4 sm:p-6">
       {!auth.loading&&!auth.isSignedIn&&
         <section className="py-7 text-center">
           <LockKeyhole className="mx-auto mb-3 text-[#D4AF37]" size={30}/>
           <h2 className="font-editorial text-xl">Study with your free account</h2>
           <p className="mx-auto mt-2 max-w-lg text-sm leading-relaxed text-[#E6D5B8]">
             The Qur&apos;an remains free without signing in. A free account gives
             three Verse Studio lessons and five AI teacher questions each day.
           </p>
           {auth.configured?
             <button type="button" className="am-gold-action mt-4" onClick={()=>{void auth.signIn()}}>Sign in to study</button>:
             <p className="mt-4 text-xs text-[#C0AB90]">Account sign-in has not yet been configured by the app administrator.</p>}
         </section>}
       {auth.loading&&<p>Checking your study account…</p>}
       {auth.isSignedIn&&<>
         {busy&&<p role="status" className="flex items-center gap-2 text-sm text-[#E6D5B8]">
           <LoaderCircle className="animate-spin" size={16}/> Preparing the lesson from classical sources…
         </p>}
         {error&&<div role="alert" className="rounded-lg border border-[#C8A96E]/40 p-4 text-sm">
           <p>{error}</p>
           <button type="button" className="am-small-action mt-3" onClick={()=>{setTafsir(null);setDrills(null);setTab(v=>v===0?1:0)}}>
             <RotateCcw size={14}/> Retry
           </button>
         </div>}
         {!busy&&!error&&<>
           {tab===0&&tafsir&&<>
             <h2 className="mb-4 font-editorial text-xl text-[#EDD39F]">Meaning &amp; Context</h2>
             {section("meaning_context")}
           </>}
           {tab===1&&tafsir&&<>
             <h2 className="mb-4 font-editorial text-xl text-[#EDD39F]">Words, Fiqh &amp; Reflections</h2>
             {section("word_fiqh")}
             <h3 className="mb-3 mt-7 font-editorial text-lg text-[#C8A96E]">Purpose and reflection</h3>
             {section("reflection")}
           </>}
           {tab===2&&drills&&<RootFlashcards quran={quranVocab} commentary={commentaryVocab}/>}
           {tab===3&&drills&&<MasteryDrills drills={drills.drills}
             verseKey={`${surah}:${ayah}`} onComplete={onMastered}/>}
           {((tab<=1&&tafsir)||(tab>=2&&drills))&&
             <SourcePills sources={tab<=1?tafsir?.sources||[]:drills?.sources||[]}
               needsReview={Boolean(tafsir?.sections?.some(s=>s.claims.some(c=>c.evidence_state==="needs_review")))}/>}
           {((tab<=1&&tafsir?.completion==="partial")||(tab>=2&&drills?.completion==="partial"))&&
             <p className="mt-4 text-xs text-[#C0AB90]">This lesson is incomplete; only available validated material is shown.</p>}
         </>}
       </>}
     </div>
   </section>
   <AlMuallimPaywall open={paywall} reason={{kind:"verse_limit"}} prices={prices}
     platform="web" onClose={()=>setPaywall(false)}
     onCheckout={async(tier)=>{await billing.subscribe(tier)}}
     onScholarship={()=>{setPaywall(false);setScholarship(true)}}/>
   {scholarship&&<div className="fixed inset-0 z-[130] grid place-items-center bg-black/75 p-4">
     <div className="w-full max-w-lg"><ScholarshipRequest onClose={()=>setScholarship(false)}
       submitRequest={(months,note)=>billing.requestScholarship(months,note).then(()=>undefined)}/></div>
   </div>}
 </main>;
}
