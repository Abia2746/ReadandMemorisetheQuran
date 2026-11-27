import type { QuranWord, WordStatus } from "./verseApi";
/** Orthographic matching only. It cannot establish vowel or Tajweed accuracy. */
export function normalizeArabic(value:string):string {
  return value.normalize("NFKD")
    .replace(/[\u064B-\u065F\u0670\u06D6-\u06ED\u0640]/g,"")
    .replace(/[إأآٱ]/g,"ا").replace(/ى/g,"ي").replace(/ؤ/g,"و")
    .replace(/ئ/g,"ي").replace(/ة/g,"ه")
    .replace(/[^\u0621-\u064A]+/g," ").trim();
}
// A reversible position cue for complete transcript words, independent of grades.
export function previewPosition(expected:QuranWord[], transcript:string, start:number):number|null {
  const tokens=normalizeArabic(transcript).split(/\s+/).filter(Boolean);
  if(!tokens.length || start<0 || start+tokens.length>expected.length)return null;
  if(!tokens.every((token,i)=>token===normalizeArabic(expected[start+i].arabic)))return null;
  return start+tokens.length-1;
}

export type AlignmentUpdate = {
  matched:number[];
  reviewCandidates:number[];
  nextExpected:number;
  trustworthy:boolean;
};
/**
 * A partial word / single word / interim ASR result is NOT a verified phrase.
 * Confirm only whole ordered phrases of up to four words, ending at the ayah
 * boundary. No skipping, Levenshtein, phoneme-prefix or low-confidence green.
 *
 * This is still just textual recognition, not a Tajweed assessment.
 */
export function alignObservation(
  expected:QuranWord[],observed:string,
  lastConfirmed:number, final:boolean, confidence:number|null
): AlignmentUpdate {
  const cursor=Math.max(0,lastConfirmed+1);
  const none:AlignmentUpdate={matched:[],reviewCandidates:[],
    nextExpected:cursor,trustworthy:false};
  if(!final||cursor>=expected.length)return none;
  const tokens=normalizeArabic(observed).split(/\s+/).filter(Boolean);
  if(!tokens.length)return none;
  const forms=expected.map(w=>normalizeArabic(w.arabic));
  let i=cursor,j=0;
  const matched:number[]=[];
  while(i<expected.length){
    // This API supplies one ayah at a time. Do not assume QuranWord has an ayah field.
    const end=Math.min(expected.length,i+4);
    const size=end-i;
    if(tokens.length-j<size)break;
    const phrase=forms.slice(i,end);
    const heard=tokens.slice(j,j+size);
    if(phrase.some((w,index)=>w!==heard[index]))break;
    for(let n=i;n<end;n++)matched.push(n);
    i=end;j+=size;
  }
  // Confidence does not prove Tajweed. It only affects whether a completed
  // text observation may be trusted; never invent a red "wrong" label.
  const trustworthy=typeof confidence==="number"&&confidence>=0.88;
  return {matched:trustworthy?matched:[],reviewCandidates:[],
    nextExpected:trustworthy?i:cursor,trustworthy};
}
export function statusMapAfter(
  previous:Record<string,WordStatus>,
  expected:QuranWord[],update:AlignmentUpdate
):Record<string,WordStatus>{
  const statuses={...previous};
  for(const idx of update.matched){
    if(expected[idx])statuses[expected[idx].id]="confirmed";
  }
  return statuses;
}
