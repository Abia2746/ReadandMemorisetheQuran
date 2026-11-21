"use client";
import { Flame, Globe2, ChevronDown, BookOpenText } from "lucide-react";
import Link from "next/link";
import { AYAHS_PER_SURAH, SURAH_NAMES, RECITERS, type ReciterId } from "@/lib/quranMetadata";
export type NavProps = {
  surah:number;ayah:number;reciter:ReciterId;language:string;
  xp:number;streak:number;
  onSurah:(value:number)=>void;onAyah:(value:number)=>void;
  onReciter:(value:ReciterId)=>void;onLanguage:(value:string)=>void;
};
export function StickyReaderBar(props:NavProps) {
  return <header className="am-sticky-nav" aria-label="Qur'an reader navigation">
    <Link href="/" className="flex shrink-0 items-center gap-2 text-[#D4AF37] no-underline" aria-label="Al-Mu'allim reader">
      <span className="grid h-10 w-10 place-items-center rounded-xl border border-[#C8A96E]/40 bg-[#2A1F18] font-quran text-2xl">۞</span>
      <span className="hidden font-editorial text-lg font-semibold tracking-tight sm:block">Al-Mu&apos;allim</span>
    </Link>
    <div className="am-nav-pills flex-1" aria-label="Passage and settings">
      <label className="am-nav-select" title="Choose surah">
        <span className="sr-only">Surah</span>
        <BookOpenText size={15} aria-hidden="true" />
        <select aria-label="Select surah" value={props.surah}
          onChange={e=>props.onSurah(Number(e.target.value))}
          className="min-w-0 max-w-[140px] appearance-none bg-transparent text-sm text-[#F5EBE0] outline-none sm:max-w-[240px]">
          {SURAH_NAMES.map((name,i)=><option key={name} value={i+1}>{i+1}. {name}</option>)}
        </select>
        <ChevronDown size={13} aria-hidden="true"/>
      </label>
      <label className="am-nav-select" title="Choose ayah">
        <span className="sr-only">Ayah</span>
        <span className="shrink-0 text-xs text-[#C8A96E]">Ayah</span>
        <select value={props.ayah} aria-label="Select ayah"
          onChange={e=>props.onAyah(Number(e.target.value))}
          className="max-w-[62px] appearance-none bg-transparent text-sm text-[#F5EBE0] outline-none">
          {Array.from({length:AYAHS_PER_SURAH[props.surah]},(_,i)=><option key={i+1}>{i+1}</option>)}
        </select>
      </label>
      <label className="am-nav-select" title="Choose reciter">
        <span className="sr-only">Reciter</span>
        <select aria-label="Choose Qari reciter" value={props.reciter}
          onChange={e=>props.onReciter(e.target.value as ReciterId)}
          className="max-w-[138px] appearance-none bg-transparent text-sm text-[#F5EBE0] outline-none">
          {Object.entries(RECITERS).map(([id,item])=><option key={id} value={id}>{item.label}</option>)}
        </select>
      </label>
      <label className="am-nav-select" title="Study language">
        <Globe2 size={15} aria-hidden="true"/>
        <span className="sr-only">Study language</span>
        <select value={props.language} aria-label="Study language"
          onChange={e=>props.onLanguage(e.target.value)}
          className="appearance-none bg-transparent text-sm text-[#F5EBE0] outline-none">
          <option value="en">EN</option>
        </select>
      </label>
      <span className="am-nav-select border-[#D4AF37]/25 text-xs" aria-label={`${props.xp} experience points, ${props.streak} day streak`}>
        <Flame size={15} className="text-[#D4AF37]" aria-hidden="true"/>
        <span>{props.xp} XP</span><span className="text-[#C8A96E]">· {props.streak}d</span>
      </span>
    </div>
    <Link href="/pricing/" className="am-small-action shrink-0 border border-[#D4AF37]/50 text-[#EDD39F]" aria-label="View plans and pricing">Pricing</Link>
  </header>;
}
