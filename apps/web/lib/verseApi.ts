import { validVerse, type ReciterId } from "./quranMetadata";
export type QuranWord = {
  id: string; index: number; arabic: string;
  meaning: string; transliteration: string | null;
};
export type QuranVerse = {
  surah:number; ayah:number; arabic_uthmani:string;
  translation:string; translation_attribution:string;
  words:QuranWord[]; audio_url:string; reciter:string; free:true;
};
export type WordStatus = "pending"|"confirmed"|"review"|"unknown";
export type DifficultWord = {word_id:string;arabic:string;meaning:string;
  surah:number;ayah:number;index:number;due:string;strength:number;reason:string};
const origin = process.env.NEXT_PUBLIC_API_ORIGIN?.replace(/\/$/, "") ?? "";
const inFlight = new Map<string,Promise<unknown>>();
export function apiPath(path:string) {return origin+path;}
export async function fetchJSON<T>(url:string,signal?:AbortSignal,token?:string):Promise<T> {
  const response=await fetch(apiPath(url),{signal,headers:token?{Authorization:`Bearer ${token}`}:{},cache:"no-store"});
  if(!response.ok){let info:any=null;try{info=await response.json()}catch{}
    const error=new Error(typeof info?.detail==="string"?info.detail:
      info?.detail?.message||`Service unavailable (${response.status})`) as Error & {status:number;code?:string};
    error.status=response.status;error.code=info?.detail?.code;throw error;
  }
  return response.json() as Promise<T>;
}
export async function fetchVerse(surah:number,ayah:number,reciter:ReciterId="dosari",lang="en",signal?:AbortSignal) {
  if(!validVerse(surah,ayah))throw Error("Invalid verse reference");
  const key=`${surah}:${ayah}:${lang}:${reciter}`;
  // De-duplicate simultaneous un-aborted calls across reader components.
  if(signal)return fetchJSON<QuranVerse>(`/api/quran/verse/${surah}/${ayah}?lang=${lang}&reciter=${reciter}`,signal);
  const hit=inFlight.get(key) as Promise<QuranVerse>|undefined;
  if(hit)return hit;
  const promise=fetchJSON<QuranVerse>(`/api/quran/verse/${surah}/${ayah}?lang=${lang}&reciter=${reciter}`);
  inFlight.set(key,promise);void promise.finally(()=>inFlight.delete(key)).catch(()=>{});
  return promise;
}
export async function postJSON<T>(url:string,token:string,payload:unknown,signal?:AbortSignal):Promise<T>{
  const response=await fetch(apiPath(url),{method:"POST",signal,cache:"no-store",
    headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},
    body:JSON.stringify(payload)});
  if(!response.ok){let data:any=null;try{data=await response.json()}catch{}
    const error=new Error(data?.detail?.message||data?.detail||"Request could not be completed") as Error & {status:number;code?:string};
    error.status=response.status;error.code=data?.detail?.code;throw error;
  }
  return response.json() as Promise<T>;
}
