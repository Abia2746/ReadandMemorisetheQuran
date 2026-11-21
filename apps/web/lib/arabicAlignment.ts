import type { QuranWord, WordStatus } from "./verseApi";
/** Orthographic matching only. It does not grade vowels, makharij or Tajweed. */
export function normalizeArabic(value:string):string {
  return value.normalize("NFKD")
    .replace(/[\u064B-\u065F\u0670\u06D6-\u06ED\u0640]/g,"")
    .replace(/[إأآٱ]/g,"ا").replace(/ى/g,"ي").replace(/ؤ/g,"و")
    .replace(/ئ/g,"ي").replace(/ة/g,"ه")
    .replace(/[^\u0621-\u064A]+/g," ").trim();
}
export type AlignmentUpdate = {
  matched:number[];
  reviewCandidates:number[];
  nextExpected:number;
  trustworthy:boolean;
};
export function alignObservation(
  expected:QuranWord[],observed:string,
  lastConfirmed:number, final:boolean, confidence:number|null
): AlignmentUpdate {
  const tokens=normalizeArabic(observed).split(/\s+/).filter(Boolean);
  const expectedForms=expected.map(w=>normalizeArabic(w.arabic));
  const matched:number[]=[];const gaps:number[]=[];
  let cursor=Math.max(0,lastConfirmed+1);
  for(const word of tokens){
    if(!word)continue;
    const end=Math.min(expected.length,cursor+5);
    let idx=-1;
    // Avoid falsely asserting very short common Arabic words unless directly next.
    for(let i=cursor;i<end;i++){
      if(expectedForms[i]===word && (word.length>2||i===cursor)){
        idx=i;break;
      }
    }
    if(idx<0)continue;
    if(idx>cursor)for(let n=cursor;n<idx;n++)gaps.push(n);
    matched.push(idx);cursor=idx+1;
  }
  const trustworthy=final && typeof confidence==="number" && confidence>=0.88;
  // Red means 'needs review', NOT proof of mispronunciation. Never turn
  // a low-confidence ASR omission into a claimed error.
  return {
    matched:final?matched:[],
    reviewCandidates:trustworthy?gaps:[],
    nextExpected:matched.length?matched[matched.length-1]+1:lastConfirmed+1,
    trustworthy,
  };
}
export function statusMapAfter(
  previous:Record<string,WordStatus>,
  expected:QuranWord[], update:AlignmentUpdate
):Record<string,WordStatus>{
  const statuses={...previous};
  for(const idx of update.matched){
    if(expected[idx])statuses[expected[idx].id]="confirmed";
  }
  for(const idx of update.reviewCandidates){
    const item=expected[idx];
    if(item && statuses[item.id]!=="confirmed")statuses[item.id]="review";
  }
  return statuses;
}
