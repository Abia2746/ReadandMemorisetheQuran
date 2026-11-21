import type { DifficultWord, QuranWord } from "./verseApi";
const KEY="almuallim:difficult-words:v1";
export function loadDifficultWords():DifficultWord[]{
  if(typeof window==="undefined")return [];
  try{
    const data=JSON.parse(localStorage.getItem(KEY)||"[]");
    return Array.isArray(data)?data.filter((x)=>x&&typeof x.word_id==="string").slice(0,500):[];
  }catch{return []}
}
function save(items:DifficultWord[]){
  if(typeof window!=="undefined"){
    try{localStorage.setItem(KEY,JSON.stringify(items.slice(0,500)))}catch{}
  }
}
export function flagDifficultWord(
  surah:number,ayah:number,word:QuranWord,reason="Needs review",
):DifficultWord[]{
  const old=loadDifficultWords();
  const replacement:DifficultWord={
    word_id:word.id,arabic:word.arabic,meaning:word.meaning,
    surah,ayah,index:word.index,reason,strength:0,
    due:new Date().toISOString().slice(0,10),
  };
  const next=[replacement,...old.filter(w=>w.word_id!==word.id)];
  save(next);
  window.dispatchEvent(new CustomEvent("almuallim:difficult-updated"));
  return next;
}
export function reviewDifficultWord(wordId:string, correct:boolean){
  const items=loadDifficultWords().map(word=>{
    if(word.word_id!==wordId)return word;
    // Simple, capped interval ladder, not a medical/scientific learning claim.
    const strength=correct?Math.min(5,word.strength+1):0;
    const intervals=[1,2,4,8,16,30];
    const date=new Date();
    date.setDate(date.getDate()+intervals[strength]);
    return {...word,strength,due:date.toISOString().slice(0,10)};
  });
  save(items);
  window.dispatchEvent(new CustomEvent("almuallim:difficult-updated"));
}

export function removeDifficultWord(wordId:string){
  save(loadDifficultWords().filter(item=>item.word_id!==wordId));
  if(typeof window!=="undefined")window.dispatchEvent(new CustomEvent("almuallim:difficult-updated"));
}
