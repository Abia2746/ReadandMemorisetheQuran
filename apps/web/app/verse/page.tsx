"use client";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { VerseStudio } from "@/components/verse-studio/VerseStudio";
import { validVerse } from "@/lib/quranMetadata";

function VerseFromQuery(){
  const search=useSearchParams();
  const surah=Number(search.get("surah")||"2");
  const ayah=Number(search.get("ayah")||"60");
  const s=validVerse(surah,ayah)?surah:2;
  const a=validVerse(surah,ayah)?ayah:60;
  return <VerseStudio initialSurah={s} initialAyah={a}/>;
}
export default function VersePage(){
  return <Suspense fallback={<div className="am-page p-8 text-[#E6D5B8]">Preparing Verse Studio…</div>}>
    <VerseFromQuery/>
  </Suspense>;
}
