import test from "node:test";
import assert from "node:assert/strict";
import {referenceTags,relativeFeature} from "../recording_audit.mjs";
import {startBufferSegment,microphoneConditioner,practiceHistory} from "../recording_practice.mjs";

test("mīm sākinah uses the next letter and excludes a vowelled mīm",()=>{
 for(const [next,tag] of [["بِهِ","ikhfāʾ"],["مَّا","idghām"],["فِيهَا","iẓhār"]])
   assert.ok(referenceTags("عَلَيْهِمْ","",next).some(t=>t.includes("Mīm")&&t.includes(tag)));
 assert.ok(!referenceTags("عَلِمَ","","بِهِ").some(t=>t.includes("Mīm")));
});
test("connected rāʾ, Divine Name and article rules use vowel context",()=>{
 for(const [word,next,prev,tag] of [
   ["رِزْقٌ","","","rāʾ · light"],["رَبِّ","","","rāʾ · heavy"],
   ["فِرْقٍ","","","permitted variants"],["قِرْطَاسٍ","","","rāʾ · heavy"],
   ["ٱللَّهِ","","بِسْمِ","Allāh · light"],["ٱللَّهُ","","قَالَ","Allāh · heavy"],["لِلَّهِ","","","Allāh · light"],
   ["ٱلشَّمْسِ","","","Solar"],["وَٱلْقَمَرِ","","","Lunar"]])
   assert.ok(referenceTags(word,"",next,prev).some(t=>t.includes(tag)),word);
});
test("stopping transformations honour the word’s isolated reference",()=>{
 for(const [text,pause,label] of [["رَحْمَةً","رَحمَه","marbūṭah"],["عَلِيمًا","عَلِۦۦمَاا","ʿiwaḍ"],
 ["ٱلرَّحِيمِ","ءَررَحِۦۦم","ʿāriḍ"],["نَعْبُدُ","نَعبُد","final sukūn"]])
   assert.ok(referenceTags(text,"","","",pause).some(t=>t.includes(label)),text);
 assert.ok(!referenceTags("رَحْمَةً","","","","رَحمَه").some(t=>t.includes("ʿiwaḍ")));
});
test("noise conditioning preserves sample count and raw PCM; lifts quiet harmonic signals",()=>{
 for(const pitch of [110,250,410]){
   const apply=microphoneConditioner(),noise=new Float32Array(4800).fill(.0005);apply(noise);
   const raw=Float32Array.from({length:16000},(_,i)=>.006*Math.sin(2*Math.PI*pitch*i/16000));
   const original=raw.slice(),out=apply(raw);
   assert.deepEqual(original,raw);assert.equal(out.length,raw.length);
   assert.ok(Math.max(...out)>.02);assert.ok(Math.max(...out)<1);
 }
 assert.equal(relativeFeature(1800,[1700,1600,1900]),100);
 assert.equal(relativeFeature(1800,[1700]),null);
});
test("Web Audio reference playback uses nonzero offset and a hard stop duration",()=>{
 const calls=[],source={connect(){},start(...args){calls.push(args)}};
 const ctx={createBufferSource:()=>source,destination:{}};
 startBufferSegment(ctx,{duration:5.3},540,1350);assert.deepEqual(calls,[[0,.54,.81]]);
 assert.throws(()=>startBufferSegment(ctx,{duration:1},500,2000));
});
test("device history merges imports idempotently and isolates accounts and invalid files",()=>{
 const values=new Map(),store={getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v)};
 const counts=[7,286],h=practiceHistory(store,"a",counts);
 const s={id:"00000000-0000-4000-8000-000000000001",time:1,verses:[{s:2,a:57,timing:1,unresolved:1,supported:3}]};
 const serial=o=>JSON.stringify({version:1,sessions:[o]});
 h.merge(serial(s));h.flag(s.id,2,57,2,"madd");h.merge(serial(s));
 assert.equal(h.read().length,1);assert.equal(h.queue()[0].flags["word 2 · madd"],1);
 assert.deepEqual(practiceHistory(store,"b",counts).read(),[]);
 assert.throws(()=>h.merge(serial({...s,verses:[{s:2,a:287}]})));assert.equal(h.read().length,1);
});

test("an isolated ending needs independent phone evidence and subsequent quiet",async()=>{
  const {passageAudit}=await import("../recording_audit.mjs");
  const reference={inventory:{id:"t",tokens:"ته"},ayahs:[{a:1,s:1,p:"ت",o:[0],w:["ة"],iso:["ه"]}]};
  const selection={surah:1,first:1,end:1};
  const ev=[{inventory:"t",frameMs:40,phonemes:[{p:"ه",start:0,end:0,conf:.95}],
    posteriors:{startFrame:0,nFrames:1,k:1,ids:[2],probs:[.95]}}];
  const pcm=new Float32Array(8000);pcm.fill(.2,0,640);
  assert.equal(passageAudit(reference,selection,ev,pcm).words[0].pauseSupported,true);
  pcm.fill(.2);assert.equal(passageAudit(reference,selection,ev,pcm).words[0].pauseSupported,undefined);
});
