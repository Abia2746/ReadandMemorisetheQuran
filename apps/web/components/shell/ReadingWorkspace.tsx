"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { BookOpen, BookText, Brain, CloudRain, Mic, MicOff, Pause, Play,
  RotateCcw, Volume2, CheckCircle2 } from "lucide-react";
import { StickyReaderBar } from "@/components/shell/StickyReaderBar";
import { MushafReader } from "@/components/mushaf/MushafReader";
import { MeaningQuiz } from "@/components/memorise/MeaningQuiz";
import { MeaningTileGrid } from "@/components/memorise/MeaningTileGrid";
import { WordActionPopover } from "@/components/mushaf/WordActionPopover";
import { RecitationProvider, useRecitation } from "@/components/audio/RecitationProvider";
import { AcousticPractice } from "@/components/audio/AcousticPractice";
import { GuidedRecitationCoach } from "@/components/audio/GuidedRecitationCoach";
import { AYAHS_PER_SURAH, type ReciterId } from "@/lib/quranMetadata";
import { fetchJSON, fetchVerse, postJSON, apiPath, type QuranVerse, type QuranWord, type WordStatus, type DifficultWord } from "@/lib/verseApi";
import { useStudyAuth, accessToken } from "@/lib/auth";
import { alignObservation, previewPosition, statusMapAfter } from "@/lib/arabicAlignment";
import { flagDifficultWord, loadDifficultWords, removeDifficultWord,
  reviewDifficultWord } from "@/lib/difficultWords";

type TimingPayload={available:boolean;segments:{index:number;start_ms:number;end_ms:number}[];
  source:string;caution:string};
type Mode="read"|"memorise"|"live"|"quiz";
type Selection={word:QuranWord;rect:DOMRect};

function Workspace(){
  const [surah,setSurah]=useState(2);
  const [ayah,setAyah]=useState(60);
  const [reciter,setReciter]=useState<ReciterId>("dosari");
  const [lang,setLang]=useState("en");
  const [mode,setMode]=useState<Mode>("read");
  const [verse,setVerse]=useState<QuranVerse|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [timings,setTimings]=useState<TimingPayload|null>(null);
  const [statuses,setStatuses]=useState<Record<string,WordStatus>>({});
  const [revealed,setRevealed]=useState<Set<string>>(()=>new Set());
  const [selection,setSelection]=useState<Selection|null>(null);
  const [queue,setQueue]=useState(()=>[] as ReturnType<typeof loadDifficultWords>);
  const [recitationMessage,setRecitationMessage]=useState("");
  const [speed,setSpeedState]=useState(1);
  const [xp,setXp]=useState(0);
  const [streak,setStreak]=useState(0);
  const auth=useStudyAuth();
  const [micEngine,setMicEngine]=useState<"browser"|"whisper">("browser");
  const [preview,setPreview]=useState<number|null>(null);
  const lastConfirmed=useRef(-1);
  const recitation=useRecitation();
  const {stop,stopMicrophone}=recitation;

  useEffect(()=>{
    const params=new URLSearchParams(window.location.search);
    const s=Number(params.get("surah"));
    const a=Number(params.get("ayah"));
    if(Number.isInteger(s)&&s>=1&&s<=114&&Number.isInteger(a)&&a>=1&&a<=AYAHS_PER_SURAH[s]){
      setSurah(s);setAyah(a);
    }
    setQueue(loadDifficultWords());
    const update=()=>setQueue(loadDifficultWords());
    window.addEventListener("almuallim:difficult-updated",update);
    return ()=>window.removeEventListener("almuallim:difficult-updated",update);
  },[]);

  useEffect(()=>{
    if(!auth.isSignedIn)return;
    let mounted=true;
    void accessToken().then(token=>Promise.all([
      fetchJSON<{xp:number;streak:number}>("/api/learning/profile",undefined,token),
      fetchJSON<{words:{surah:number;ayah:number;word_index:number;arabic:string;gloss:string;reason:string;strength:number;due_on:string}[]}>("/api/learning/difficult",undefined,token),
    ])).then(([profile,remote])=>{
      if(!mounted)return;
      setXp(profile.xp);setStreak(profile.streak);
      const fromRemote:DifficultWord[]=remote.words.map(w=>({
        word_id:`${w.surah}:${w.ayah}:${w.word_index}`,
        surah:w.surah,ayah:w.ayah,index:w.word_index,
        arabic:w.arabic,meaning:w.gloss,reason:w.reason,
        due:w.due_on,strength:w.strength,
      }));
      const local=loadDifficultWords();
      const seen=new Set(fromRemote.map(w=>w.word_id));
      setQueue([...fromRemote,...local.filter(w=>!seen.has(w.word_id))]);
    }).catch(()=>{});
    return()=>{mounted=false};
  },[auth.isSignedIn]);

  const syncFlag=useCallback((word:QuranWord,reason:string)=>{
    if(!auth.isSignedIn)return;
    void accessToken().then(token=>postJSON("/api/learning/difficult/flag",token,{
      surah,ayah,index:word.index,arabic:word.arabic,meaning:word.meaning,reason
    })).catch(()=>{});
  },[auth.isSignedIn,surah,ayah]);

  const syncRemove=useCallback((word:QuranWord)=>{
    if(!auth.isSignedIn)return;
    void accessToken().then(token=>fetch(apiPath(
      `/api/learning/difficult/${surah}/${ayah}/${word.index}`),{
      method:"DELETE",headers:{Authorization:`Bearer ${token}`},
    })).catch(()=>{});
  },[auth.isSignedIn,surah,ayah]);

  useEffect(()=>{
    const ctrl=new AbortController();
    setLoading(true);setError("");setVerse(null);setTimings(null);
    setStatuses({});setRevealed(new Set());setSelection(null);
    setPreview(null);lastConfirmed.current=-1;
    stop();stopMicrophone();
    fetchVerse(surah,ayah,reciter,lang,ctrl.signal)
      .then(value=>{if(!ctrl.signal.aborted)setVerse(value)})
      .catch(e=>{if(!ctrl.signal.aborted)setError(e instanceof Error?e.message:"Qur'an service unavailable")})
      .finally(()=>{if(!ctrl.signal.aborted)setLoading(false)});
    return ()=>ctrl.abort();
  },[surah,ayah,reciter,lang,stop,stopMicrophone]);

  useEffect(()=>{
    if(!verse)return;
    const ctrl=new AbortController();
    fetchJSON<TimingPayload>(`/api/quran/timings/${surah}/${ayah}?reciter=${reciter}`,ctrl.signal)
      .then(item=>{if(!ctrl.signal.aborted)setTimings(item)})
      .catch(()=>{if(!ctrl.signal.aborted)setTimings(null)});
    return ()=>ctrl.abort();
  },[verse,surah,ayah,reciter]);

  const navigateSurah=(n:number)=>{setSurah(n);setAyah(1)};
  const navigateAyah=(n:number)=>{setAyah(Math.min(AYAHS_PER_SURAH[surah],Math.max(1,n)))};
  const onSelect=useCallback((word:QuranWord,rect:DOMRect)=>setSelection({word,rect}),[]);
  const quit=useCallback(()=>setSelection(null),[]);

  const timedPhrase=useCallback((word:QuranWord)=>{
    const items=timings?.segments||[];
    const segment=items.find(item=>item.index===word.index);
    if(!segment)return null;
    const last=items.find(item=>item.index===Math.min(verse?.words.length||word.index,word.index+3));
    return {start:segment.start_ms,end:last?.end_ms||segment.end_ms};
  },[timings,verse]);

  const hearSelected=async()=>{
    if(!verse||!selection)return;
    const segment=timedPhrase(selection.word);
    try{
      if(segment)await recitation.playRange(verse.audio_url,`${surah}:${ayah}`,segment.start,segment.end,1);
      else await recitation.playVerse(verse.audio_url,`${surah}:${ayah}`);
    }catch{setRecitationMessage("Playback unavailable. Try the full Qari recitation.")}
    quit();
  };
  const loopSelected=async()=>{
    if(!verse||!selection)return;
    const segment=timedPhrase(selection.word);
    if(!segment)return;
    try{await recitation.playRange(verse.audio_url,`${surah}:${ayah}`,segment.start,segment.end,3)}
    catch{setRecitationMessage("Exact phrase playback could not start.")}
    quit();
  };
  const revealSelected=()=>{
    if(!verse||!selection)return;
    setRevealed(previous=>{
      const next=new Set(previous);
      const start=selection.word.index-1;
      verse.words.slice(start,start+4).forEach(w=>next.add(w.id));
      return next;
    });
    quit();
  };
  const flagSelected=()=>{
    if(!verse||!selection)return;
    flagDifficultWord(surah,ayah,selection.word,"Manually flagged for focused revision");
    syncFlag(selection.word,"Manually flagged for focused revision");
    setStatuses(p=>({...p,[selection.word.id]:"review"}));
    quit();
  };
  const correctSelected=()=>{
    if(!selection)return;
    removeDifficultWord(selection.word.id);
    syncRemove(selection.word);
    setStatuses(p=>({...p,[selection.word.id]:"unknown"}));
    quit();
  };

  const startListening=async()=>{
    if(!verse)return;
    if(recitation.state.listening){recitation.stopMicrophone();return}
    setRecitationMessage("");
    setPreview(null);
    let provisionalStart=lastConfirmed.current+1;
    try{
      await recitation.startMicrophone(observation=>{
        const index=previewPosition(verse.words,observation.transcript,provisionalStart);
        setPreview(index);
        if(observation.final && index!==null)provisionalStart=index+1;
        const update=alignObservation(verse.words,observation.transcript,
          lastConfirmed.current,observation.final,observation.confidence);
        if(update.matched.length===0 && update.reviewCandidates.length===0)return;
        lastConfirmed.current=Math.max(lastConfirmed.current,update.nextExpected-1);
        setStatuses(p=>statusMapAfter(p,verse.words,update));
        // These are review candidates, NEVER definitive Tajweed grades.
        for(const index of update.reviewCandidates){
          const word=verse.words[index];
          if(word){
            flagDifficultWord(surah,ayah,word,"Possible recall/sequence mismatch — please verify");
            syncFlag(word,"Possible recall/sequence mismatch — please verify");
          }
        }
        if(update.matched.length){
          setRecitationMessage(`${update.nextExpected} of ${verse.words.length} words followed. Listen back to check pronunciation.`);
        }
      },micEngine);
    }catch(e){
      setRecitationMessage(e instanceof Error?e.message:"Unable to open microphone");
    }
  };

  return <div className="min-h-screen">
    <StickyReaderBar surah={surah} ayah={ayah} reciter={reciter} language={lang}
      xp={xp} streak={streak} onSurah={navigateSurah} onAyah={navigateAyah}
      onReciter={setReciter} onLanguage={setLang}/>
    <main className="am-page mx-auto">
      <nav className="flex min-h-12 flex-wrap items-center justify-between gap-2 border-b border-[#4A3828]/60 py-1" aria-label="Learning modes">
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Qur'an practice">
          {([["read","Read"],["memorise","Memorise"],["live","Live recitation"],["quiz","Word quiz"]] as const).map(([id,label])=>
            <button key={id} type="button" role="tab" aria-selected={mode===id}
              onClick={()=>{if(id==="quiz"){stopMicrophone();stop();quit()}setMode(id)}} className="am-mode-tab"
              data-current={mode===id}>{label}</button>)}
        </div>
        <div className="flex gap-2 text-xs">
          <Link href={`/verse/?surah=${surah}&ayah=${ayah}`} className="am-nav-text-link"><BookOpen size={14}/> Verse Studio</Link>
          <Link href="/journey/" className="am-nav-text-link"><Brain size={14}/> Journey</Link>
          <Link href="/sanctuary/" className="am-nav-text-link"><CloudRain size={14}/> Sanctuary</Link>
          <Link href="/account/" className="am-nav-text-link">Account</Link>
        </div>
      </nav>

      {loading&&<div role="status" className="am-ayah-panel animate-pulse p-8 text-center text-[#E6D5B8]">
        Loading the Uthmani Qur'an passage from its canonical source…
      </div>}
      {error&&<div role="alert" className="am-ayah-panel p-6 text-[#F5EBE0]">
        <h2 className="font-editorial text-lg text-[#D4AF37]">Qur'an source temporarily unavailable</h2>
        <p className="mt-2 text-sm">{error}</p>
        <p className="mt-2 text-xs text-[#C0AB90]">No Arabic verse or translation will be invented. Check the backend Qur'an API credentials and connection.</p>
      </div>}
      {verse && mode==="quiz" && <MeaningQuiz key={verse.surah+":"+verse.ayah} verse={verse} reciter={reciter} language={lang}/>}
      {verse && mode!=="quiz" && <section className="mt-1">
        {verse.text_source==="Tanzil" && <p className="px-4 py-2 text-xs text-[#E6D5B8]">
          Arabic text from the <a className="underline" href="https://tanzil.net">Tanzil Project</a>. Word details are temporarily unavailable.
        </p>}
        {mode==="memorise"?
          <div className="am-ayah-panel p-4 sm:p-6">
            <div className="mb-3 flex justify-between text-xs text-[#C8A96E]">
              <span>MEMORISE WITH MEANING</span><span>{surah}:{ayah}</span>
            </div>
            <MeaningTileGrid preview={recitation.state.listening?preview:null} words={verse.words} statuses={statuses} revealed={revealed} onSelect={onSelect}/>
            <details className="mt-4 border-t border-[#4A3828] pt-3">
              <summary className="cursor-pointer text-xs text-[#E6D5B8]">Read complete Arabic ayah and English meaning</summary>
              <div dir="rtl" lang="ar" className="py-4 font-quran text-3xl leading-[2.2]">{verse.arabic_uthmani}</div>
              <p className="text-sm leading-relaxed">{verse.translation}</p>
            </details>
          </div>:
          <MushafReader verse={verse} statuses={statuses} onSelect={onSelect}/>
        }
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-[#4A3828] bg-[#241913] p-3">
          <button type="button" onClick={()=>{void recitation.playVerse(verse.audio_url,`${surah}:${ayah}`).catch(()=>setRecitationMessage("Qari audio unavailable right now."))}}
            className="am-small-action"><Play size={16}/> Hear recitation</button>
          <button type="button" onClick={recitation.pause} className="am-small-action"><Pause size={16}/> Pause</button>
          <button type="button" onClick={recitation.stop} className="am-small-action"><RotateCcw size={16}/> Restart</button>
          <label className="ml-auto flex items-center gap-2 text-xs text-[#E6D5B8]">
            Speed
            <select className="am-field max-w-[90px]" value={speed}
              onChange={e=>{const n=Number(e.target.value);setSpeedState(n);recitation.setSpeed(n)}}>
              <option value="0.75">0.75×</option><option value="1">1×</option><option value="1.25">1.25×</option>
            </select>
          </label>
          <span className="w-full text-xs text-[#C0AB90]">
            <Volume2 className="mr-1 inline" size={13}/>
            {recitation.state.playing?
              `${Math.floor(recitation.state.time)}s of ${Math.floor(recitation.state.duration)}s`:
              "Tap any word to hear it in context or loop its phrase."}
          </span>
        </div>
        <div className="mt-3 rounded-2xl border border-[#4A3828] bg-[#241913] p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-editorial text-lg text-[#EDD39F]">Live recitation practice</h2>
              <p className="mt-1 text-xs text-[#C0AB90]">Green = word recognised in sequence · Red = possible mismatch to review</p>
            </div>
            <button type="button" onClick={()=>{void startListening()}}
              aria-pressed={recitation.state.listening}
              className="am-gold-action">{recitation.state.listening?<MicOff size={17}/>:<Mic size={17}/>}
              {recitation.state.listening?"Stop listening":"Start listening"}</button>
          </div>
          <label className="mt-3 flex flex-wrap items-center gap-2 text-xs text-[#E6D5B8]">
            Speech engine
            <select className="am-field max-w-[280px]" value={micEngine}
              disabled={recitation.state.listening}
              onChange={e=>setMicEngine(e.target.value as "browser"|"whisper")}>
              <option value="browser">Browser Arabic recognition (may use cloud speech services)</option>
              <option value="whisper">On-device Whisper Tiny (first download, experimental)</option>
            </select>
          </label>
          <div aria-label="Microphone activity" className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#4A3828]">
            <div className="h-full rounded-full bg-[#2E7D32] transition-[width] duration-150"
              style={{width:`${recitation.state.micLevel*100}%`}}/>
          </div>
          <p role="status" aria-live="polite" className="mt-3 text-xs text-[#E6D5B8]">
            {recitationMessage||recitation.state.note}
          </p>
          <p className="mt-2 text-xs leading-relaxed text-[#C0AB90]">
            Browser recognition may process speech using your browser provider; optional Whisper processes local microphone audio on device. Word following
            checks approximate recall and sequence, not ghunnah, madd, makharij or correct vowels.
            Compare with Qari recitation or a qualified Tajweed teacher.
          </p>
        </div>
        <GuidedRecitationCoach key={`coach:${surah}:${ayah}`} verseRef={`${surah}:${ayah}`}
          onListen={()=>{void recitation.playVerse(verse.audio_url,`${surah}:${ayah}`).catch(()=>setRecitationMessage("Qari audio unavailable right now."))}}
          onStartReciting={()=>{setMode("live");void startListening()}}/>
        <AcousticPractice key={`${surah}:${ayah}`} verseRef={`${surah}:${ayah}`}/>
        {queue.length>0&&<section className="mb-8 mt-4 rounded-2xl border border-[#4A3828] bg-[#241913] p-4">
          <h2 className="font-editorial text-lg text-[#EDD39F]">Difficult Words · gentle revision</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {queue.filter(item=>item.due<=new Date().toISOString().slice(0,10)).slice(0,8).map(word=>
              <div key={word.word_id} className="rounded-xl border border-[#4A3828] bg-[#2A1F18] px-3 py-2">
                <div dir="rtl" lang="ar" className="font-quran text-2xl">{word.arabic}</div>
                <div className="text-xs text-[#E6D5B8]">{word.meaning}</div>
                <button type="button" onClick={()=>{
                    reviewDifficultWord(word.word_id,true);
                    if(auth.isSignedIn){void accessToken().then(token=>postJSON(
                      `/api/learning/difficult/${word.surah}/${word.ayah}/${word.index}/review`,token,{correct:true}
                    )).catch(()=>{});}
                  }}
                  className="mt-1 flex items-center gap-1 text-xs text-[#D4AF37]">
                  <CheckCircle2 size={13}/> Practised accurately
                </button>
              </div>)}
          </div>
          <p className="mt-3 text-xs text-[#C0AB90]">Suggestions can be corrected at any time. Revisions reschedule gently; no missed-day penalties.</p>
        </section>}
      </section>}
      {selection&&<WordActionPopover word={selection.word} anchor={selection.rect}
        canLoop={Boolean(timedPhrase(selection.word))}
        isReview={statuses[selection.word.id]==="review"}
        onHear={()=>{void hearSelected()}} onLoop={()=>{void loopSelected()}}
        onReveal={revealSelected} onFlag={flagSelected}
        onCorrect={correctSelected} onClose={quit}/>}
    </main>
  </div>;
}
export function ReadingWorkspace(){
  return <RecitationProvider><Workspace/></RecitationProvider>;
}
