import test from "node:test";
import assert from "node:assert/strict";
import {continuousTracker,maddSites,playbackBounds,vowelNucleus} from "../recording_tracker.mjs";

test("Hafs targets depend on the connected phones and following word",()=>{
  const get=(p,w,o)=>[...maddSites({p,w,o}).values()][0];
  assert.deepEqual(get("مَاا","مَا".split(" "),[0]).range,[2,2]);
  assert.equal(get("جَااااء",["جَاءَ"],[0]).label,"Muttasil");
  assert.equal(get("بِمَااااءُ",["بِمَآ","أُنزِلَ"],[0,8]).label,"Munfasil");
  assert.equal(get("ضَاااااالل",["ٱلضَّآلِّينَ"],[0]).label,"Lazim");
  assert.equal(get("حِۦۦم",["ٱلرَّحِيمِ"],[0]).label,"Pause-dependent madd");
  assert.equal(get("مِن",["مِنْ"],[0]),undefined);
});
test("bounded replay windows recover audible decay and stay inside neighbouring words",()=>{
  const pcm=Float32Array.from({length:16000},(_,i)=>i>=3200&&i<12000?.08*Math.sin(i/12):0);
  const span={start:250,end:650};
  assert.deepEqual(playbackBounds(pcm,span,0,1000),{start:200,end:760});
  assert.ok(playbackBounds(pcm,span,220,700).end<=700);
});
test("strong model emissions on silent PCM cannot create a short-vowel baseline",()=>{
  const samples=new Float32Array(16000);
  assert.equal(vowelNucleus(samples,{end:100},{start:130,end:150},{start:200}),null);
});
test("an ambiguous repeated phrase cannot lock the adaptive gauge",()=>{
  const p="سَمَااسَمَاا",ref={ayahs:[{a:1,s:1,p,o:[0,6],w:["سما","سما"]}]};
  const tracker=continuousTracker(ref,{surah:1,first:1,end:1});
  const ev=[{frameMs:40,phonemes:[..."سَمَا"].map((p,i)=>({p,start:i,end:i,conf:.98}))}];
  assert.equal(tracker.ingest(ev,new Float32Array(16000)).active,null);
});

test("delayed short-vowel measurements use the preceding pace and wait for silence before a clipping cue",()=>{
  const p="بَتِجُدَسِقُكَضِط";
  const ref={ayahs:[{a:1,s:1,p,o:[0],w:["تدريب"]}]};
  const pcm=new Float32Array(64000),phones=[];
  let ms=0;
  for(const [i,symbol] of [...p].entries()){
    const vowel="َُِ".includes(symbol);
    const duration=vowel?(i===11?180:i===15?40:100):40;
    if(vowel)for(let j=ms*16;j<(ms+duration)*16;j++)pcm[j]=.12*Math.sin(j*.087);
    const anchor=vowel?ms+Math.floor(duration/2)-10:ms;
    phones.push({p:symbol,start:anchor,end:vowel?anchor+20:ms+40,conf:.99});
    ms+=duration;
  }
  const evidence=[{frameMs:1,phonemes:phones}];
  const tracker=continuousTracker(ref,{surah:1,first:1,end:1});
  const first=tracker.ingest(evidence,pcm.subarray(0,ms*16));
  assert.ok(Math.abs(first.beat-100)<=10);
  assert.ok(first.notes.get(11).ratio>1.4);
  assert.equal(first.notes.has(15),false);
  const after=tracker.ingest(evidence,pcm);
  assert.equal(after.notes.get(15).short,true);
});
