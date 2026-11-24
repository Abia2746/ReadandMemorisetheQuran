import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const js=readFileSync(new URL("../studio.js",import.meta.url),"utf8");
const source=js.slice(js.indexOf("  const PHRASE_WORDS"),js.indexOf("  function updateMatchCount"));
const tokens=s=>s.split(" ");
const phrases=["وإذ استسقى موسى لقومه","فادع لنا ربك يخرج لنا مما تنبت الأرض"];
const words=phrases.flatMap((phrase,i)=>tokens(phrase).map(ar=>({ar,ayah:60+i})));
function fixture(passage=words){
  const matched=new Set(),pending=[];
  const matcher=new Function("words","expected","markMatched","updateMatchCount","wordNodes","coach",
    source+";return matchFinalTokens")(passage,passage.map(w=>w.ar),i=>matched.add(i),()=>{},[],()=>{});
  let cursor=0;
  return {matched,hear(text){pending.push(...tokens(text));cursor=matcher(pending,cursor).cursor}};
}
const x=fixture();
x.hear("فادع لنا");
assert.equal(x.matched.size,0);
x.hear("ربك يخرج لنا ثم");
assert.deepEqual([...x.matched],[4,5,6,7]);
x.hear("فادع لنا ربك يخرج");
assert.deepEqual([...x.matched],[4,5,6,7]);
for(const heard of ["ف","فادع لنا يخرج ربك","بسم الله الرحمن الرحيم","موسى لقومه فادع لنا"]){
  const miss=fixture();miss.hear(heard);assert.equal(miss.matched.size,0);
}
const ambiguous=fixture([...words,...words.slice(4)]);
ambiguous.hear("فادع لنا ربك يخرج");assert.equal(ambiguous.matched.size,0);
const full=fixture();full.hear(phrases.join(" "));assert.equal(full.matched.size,12);
console.log("PASS: final phrase matching, mid-passage recovery, repeats, ambiguity and exclusions");
