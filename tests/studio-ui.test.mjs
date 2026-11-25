/**
 * Offline front-end regression test. Uses a mock of the SDK events, rather than
 * pretending an iPad microphone or hosted ONNX model can be tested in CI.
 * Run with: node tests/studio-ui.test.mjs
 */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {resolve,dirname} from "node:path";

const root=resolve(dirname(fileURLToPath(import.meta.url)),"..");
let source=readFileSync(resolve(root,"studio.js"),"utf8");
const roomUiSource=readFileSync(resolve(root,"prayer_room_ui.js"),"utf8");
const hifdhUiSource=readFileSync(resolve(root,"hifdh_planner_ui.js"),"utf8");
assert.doesNotMatch(source,/Noor Hifdh · R8/);
assert.doesNotMatch(source,/Live reader ·/);
assert.match(source,/@tilawa\/core@1\.0\.0-rc\.0\/web/);
assert.match(source,/prepareMicrophone\(\)/);
assert.doesNotMatch(source,/const micTest=btn/);

const importExpression=/sdkPromise=import\(\s*"https:\/\/esm\.sh\/@tilawa\/core@1\.0\.0-rc\.0\/web\?bundle&deps=onnxruntime-web@1\.30\.0"\s*\)\.then/;
assert.match(source,importExpression);
source=source.replace(importExpression,"sdkPromise=Promise.resolve(mockSdk).then");

class Element{
  constructor(tag,text=""){
    this.tag=tag;this.textContent=text;this.children=[];this.className="";
    this.style={};this.dataset={};this.attributes={};this.hidden=false;
    this.disabled=false;this.paused=true;this.value="";
  }
  appendChild(node){this.children.push(node);return node}
  insertBefore(node,reference){
    const at=this.children.indexOf(reference);
    this.children.splice(at<0?this.children.length:at,0,node);
    return node;
  }
  replaceChildren(...nodes){this.children=nodes}
  setAttribute(name,value){this.attributes[name]=value}
  addEventListener(){}
  scrollIntoView(){}
  pause(){this.paused=true}
  get childNodes(){return this.children}
  get classList(){
    return {
      add:n=>{const s=new Set(this.className.split(/\s+/).filter(Boolean));s.add(n);this.className=[...s].join(" ")},
      remove:n=>{this.className=this.className.split(/\s+/).filter(x=>x&&x!==n).join(" ")},
      toggle:(n,flag)=>{
        const s=new Set(this.className.split(/\s+/).filter(Boolean));
        const on=flag===undefined?!s.has(n):flag;
        if(on)s.add(n);else s.delete(n);
        this.className=[...s].join(" ");
      }
    }
  }
  querySelector(selector){
    if(selector.startsWith(".")&&this.className.split(/\s+/).includes(selector.slice(1)))return this;
    for(const child of this.children){
      const found=child.querySelector?.(selector);
      if(found)return found;
    }
    return null;
  }
}
const nodes=root=>[root,...root.children.flatMap(nodes)];
const document={
  createElement:tag=>new Element(tag),
  createTextNode:text=>new Element("text",text)
};
const abortCtor=class{signal={};abort(){}};
const testWords=[
  {ar:"فَقُلْنَا",en:"And We said",tr:"faqulna",ayah:60,letters:[]},
  {ar:"اضْرِبْ",en:"Strike",tr:"idrib",ayah:60,letters:[]},
  {ar:"الْحَجَرَ",en:"The stone",tr:"al-hajara",ayah:60,letters:[]}
];
async function fixture(mode,overrides={},startListening=true,browserWindow={},deviceStore={getItem:()=>null,setItem(){}}){
  let callback,prepared=0,listenCount=0,stopCount=0;
  const mockSdk={
    prepareMicrophone(){
      prepared++;
      return {release(){}}
    },
    async createTilawa(options){
      return {
        startFreeRecitation(){
          assert.equal(options.recordEvidence,true);
          assert.equal(options.tier,"lite");
          return {onAudio(fn){fn(Float32Array.from({length:192000},(_,i)=>(i%32)/32),0)},evidence:()=>overrides.testEvidence,dispose(){}};
        },
        startMemorization(){
          return {subscribe(fn){callback=fn},dispose(){}}
        },
        async listen(){listenCount++;return {stop:async()=>{stopCount++}}},
        async dispose(){}
      };
    }
  };
  const combined = roomUiSource+"\n"+hifdhUiSource+"\n"+
    source.replace(/^export default function\(component\)/,"function Studio(component)")+
    "\nreturn Studio;";
  const factory=new Function("mockSdk","document","window","navigator","sessionStorage",
     "localStorage","AbortController","createPrayerRoomScene", combined);
  const create=factory(mockSdk,document,browserWindow,{
    userAgent:"iPad",platform:"iPad",maxTouchPoints:5
  },{getItem:()=>null,setItem(){}},deviceStore,abortCtor,
    async()=>({start(){},stop(){},dispose(){}}));
  const mount=new Element("div");
  mount.className="am-mount";
  const data={
    mode,cloudAvailable:true,meta:{s:2,a:60,end:60,xp:0,streak:0},
    words:testWords,trackWordCounts:[3],audio:[],segments:[],
    surahEnglish:"Al-Baqarah",reciter:"Yasser",
    ...overrides
  };
  const dispose=create({parentElement:mount,data,setTriggerValue(){}});
  for(let i=0;i<12;i++)await Promise.resolve();
  const start=nodes(mount).find(x=>x.tag==="button"&&x.textContent==="🎙 Start listening");
  assert.ok(start,"direct microphone start exists");
  const select=nodes(mount).find(x=>x.tag==="select");
  assert.equal(select.value,"local","on-device audio is the default even with cloud available");
  // Test the local SDK path explicitly: it must remain positioning-only.
  select.value="local";
  select.onchange();
  for(let i=0;i<6;i++)await Promise.resolve();
  if(startListening){
    await start.onclick();
    assert.equal(prepared,1,"Safari microphone prepared on the real tap");
    assert.equal(listenCount,1,"SDK listen() invoked");
    assert.ok(callback,"received SDK position subscription");
  }
  return {mount,callback,dispose,getStopCount:()=>stopCount};
}

{
  const cases=[["one vowel",[{frameMs:40,phonemes:[{p:"ب",start:0},{p:"َ",start:3,conf:.92}]}],1],["ambiguous",[{frameMs:40,phonemes:[{p:"ُ",start:12,conf:.56},{p:"ِ",start:14}]}],2],["consonant only",[{frameMs:40,phonemes:[{p:"ب",start:0}]}],0]];
  if(process.env.QURAN_VOWEL_TRACES){
    for(const [name,count] of [["phrase",36],["prefix",0],["quiet",0]]){
      cases.push([name,JSON.parse(readFileSync(resolve(process.env.QURAN_VOWEL_TRACES,name+"-vowels.json"),"utf8")),count]);
    }
  }
  for(const [name,testEvidence,expected] of cases){
    let buffer;
    const AudioContext=class{
      async resume(){}
      async close(){}
      createBuffer(channels,size,rate){assert.equal(rate,16000);buffer=new Float32Array(size);return {getChannelData:()=>buffer}}
      createBufferSource(){return {connect(){},start(){}}}
    };
    const x=await fixture("blind",{testEvidence},false,{AudioContext});
    const select=nodes(x.mount).find(n=>n.tag==="select");
    select.value="vowels";
    select.onchange();
    const mic=nodes(x.mount).find(n=>n.textContent==="🎙 Start listening");
    await mic.onclick();
    await mic.onclick();
    assert.equal(x.getStopCount(),1);
    const rows=nodes(x.mount).filter(n=>n.tag==="li"&&n.textContent.match(/ · [0-9.]+ s$/));
    assert.equal(rows.length,expected,name);
    if(name==="one vowel")assert.equal(rows[0].textContent,"Fatḥah /a/ · 0.12 s");
    if(name==="ambiguous")assert.ok(rows.every(n=>n.textContent.startsWith("Vowel unclear")));
    if(name==="phrase")assert.equal(rows.filter(n=>n.textContent.startsWith("Vowel unclear")).length,1);
    if(expected){
      const button=rows[0].children[0];
      await button.onclick();
      assert.ok(buffer.length<=12801&&buffer.some(sample=>sample!==0),"replay uses captured PCM around the detection");
    }
    if(!expected)assert.ok(nodes(x.mount).some(n=>n.textContent==="No short vowel resolved in this recording."));
    assert.ok(nodes(x.mount).every(n=>!n.className.split(" ").includes("am-acoustic-cursor")&&!n.className.split(" ").includes("am-confirmed")));
    x.dispose();
  }
}
{
  const x=await fixture("blind");
  let reveal=nodes(x.mount).filter(n=>n.className.split(" ").includes("am-revealed-ar"));
  assert.equal(reveal.length,0,"memory test starts English-only");
  x.callback({type:"position",state:"acquiring",observed:[{word:{surah:2,ayah:60,word:1}}]});
  reveal=nodes(x.mount).filter(n=>n.className.split(" ").includes("am-revealed-ar"));
  assert.equal(reveal.length,0,"uncertain audio cannot reveal answers");
  // The first vowel/word position must NOT count as completed.
  x.callback({type:"position",state:"locked",observed:[{word:{surah:2,ayah:60,word:1}}]});
  reveal=nodes(x.mount).filter(n=>n.className.split(" ").includes("am-revealed-ar"));
  assert.equal(reveal.length,0,"first locked word only highlights current position");
  // Position-lock means the SDK estimates where audio is, not that the
  // full word/phrase was spoken. Neither movement nor repeated confidence
  // may reveal the Arabic answer during blind memorisation.
  x.callback({type:"position",state:"locked",observed:[{word:{surah:2,ayah:60,word:2},confidence:.99}]});
  x.callback({type:"position",state:"locked",observed:[{word:{surah:2,ayah:60,word:3},confidence:.99}]});
  x.callback({type:"position",state:"locked",observed:[{word:{surah:2,ayah:60,word:3},confidence:.99}]});
  reveal=nodes(x.mount).filter(n=>n.className.split(" ").includes("am-revealed-ar"));
  assert.equal(reveal.length,0,"even high-confidence position movement cannot reveal unverified phrases");
  const confirmed=nodes(x.mount).filter(n=>n.className.split(/\s+/).includes("am-confirmed"));
  assert.equal(confirmed.length,0,"position predictions must never mark Quran words green");
  x.callback({type:"position",state:"locked",observed:[{word:{surah:99,ayah:60,word:3}}]});
  reveal=nodes(x.mount).filter(n=>n.className.split(" ").includes("am-revealed-ar"));
  assert.equal(reveal.length,0,"unrelated Surah cannot reveal anything");
  x.dispose();
}
{
  const x=await fixture("full");
  x.callback({type:"position",state:"locked",observed:[{word:{surah:2,ayah:60,word:2}}]});
  const wordNodes=nodes(x.mount).filter(n=>n.className.split(/\s+/).includes("am-word"));
  assert.equal(wordNodes.filter(n=>n.className.includes("am-active")).length,0,
    "SDK-only position must never display as verified active highlighting");
  assert.match(wordNodes[1].className,/am-acoustic-cursor/,
    "tentative location should be visually distinguishable from verified recitation");
  assert.equal(nodes(x.mount).filter(n=>n.className.includes("am-revealed-ar")).length,0,
    "reading mode does not insert duplicate Arabic text");
  const word=n=>({word:{surah:2,ayah:60,word:n}});
  x.callback({type:"position",state:"locked",observed:[word(1),word(3)]});
  assert.match(wordNodes[0].className,/am-acoustic-cursor/);
  assert.doesNotMatch(wordNodes[2].className,/am-acoustic-cursor/);
  x.callback({type:"position",state:"locked",observed:[{word:{surah:2,ayah:61,word:1}},word(2)]});
  assert.ok(wordNodes.every(n=>!n.className.includes("am-acoustic-cursor")));
  for(const event of [{state:"ambiguous"},{state:"lost"},{state:"locked",spanHold:true},{state:"locked",hold:"start"}]){
    x.callback({type:"position",state:"locked",observed:[word(2)]});
    x.callback({type:"position",observed:[word(2)],...event});
    assert.ok(wordNodes.every(n=>!n.className.includes("am-acoustic-cursor")));
  }
  x.dispose();
}
{
  const x=await fixture("blind");
  const panel=x.mount.querySelector(".am-audio-cues");
  const location={surah:2,ayah:60,word:2};
  const cue={type:"checker",id:"w2",state:"confirmed",errorClass:"omitted_word",confidence:.9,location};
  x.callback(cue);
  assert.equal(panel.hidden,true);
  x.callback({type:"position",state:"locked",observed:[{word:location}]});
  for(const changes of [{state:"suspected"},{confidence:.2},{errorClass:"short_vowel"},{location:{...location,surah:1}}]){
    x.callback({...cue,...changes});
    assert.equal(panel.hidden,true);
  }
  x.callback(cue);
  x.callback(cue);
  const buttons=nodes(panel).filter(n=>n.tag==="button");
  assert.equal(buttons.length,1);
  assert.match(buttons[0].textContent,/Possible missed word · Ayah 60, word 2/);
  assert.equal(nodes(x.mount).some(n=>n.className.split(" ").includes("am-confirmed")),false);
  buttons[0].onclick();
  assert.ok(nodes(x.mount).some(n=>n.textContent.includes("Selected · Ayah 60, word 2")));
  x.callback({type:"position",state:"lost"});
  x.callback({...cue,state:"resolved"});
  assert.equal(panel.hidden,true);
  x.dispose();
}
{
  const segments = [
    {ayah:60,word_idx:0,start:0,end:1000},
    {ayah:60,word_idx:1,start:1000,end:2000},
    {ayah:60,word_idx:2,start:2000,end:3000},
  ];
  const x=await fixture("full",{audio:["https://everyayah.com/data/test/002060.mp3"],segments},false);
  const a=nodes(x.mount).find(node=>node.tag==="audio");
  assert.ok(a,"audio player exists");
  a.duration=3;a.currentTime=1.5;a.paused=false;
  a.ontimeupdate();
  const words=nodes(x.mount).filter(n=>n.className.split(" ").includes("am-word"));
  assert.match(words[1].className,/am-active/,"aligned reciter highlight follows true second-word timestamp");
  assert.equal(words.filter(n=>n.className.includes("am-active")).length,1);
  a.currentTime=2.5;a.ontimeupdate();
  assert.match(words[2].className,/am-active/,"aligned reciter highlight advances with audio time");
  x.dispose();
}
{
  const x=await fixture("full",{audio:["https://everyayah.com/data/test/002060.mp3"],segments:[]},false);
  const audio=nodes(x.mount).find(node=>node.tag==="audio");
  audio.duration=3;audio.currentTime=1.6;audio.paused=false;audio.ontimeupdate();
  const words=nodes(x.mount).filter(n=>n.className.split(" ").includes("am-word"));
  assert.equal(words.filter(n=>n.className.includes("am-active")).length,0,
    "missing timings must NOT produce a guessed active word");
  assert.equal(words.filter(n=>n.className.includes("am-ayah-playing")).length,0,
    "without word timing, never highlight all ayah words");
  x.dispose();
}
console.log("PASS: SDK position estimates never validate phrases; reader timings remain source-matched.");

{
  let recogniser;
  class Speech {
    constructor(){recogniser=this}
    start(){}
    abort(){}
  }
  const x=await fixture("blind",{},false,{SpeechRecognition:Speech});
  const all=()=>nodes(x.mount);
  const select=all().find(n=>n.tag==="select");
  select.value="browser";
  await all().find(n=>n.textContent==="🎙 Start listening").onclick();
  const deliver=recogniser.onresult;
  const result=isFinal=>({resultIndex:0,results:[{isFinal,0:{transcript:"فقلنا اضرب الحجر"}}]});
  deliver(result(false));
  assert.equal(all().filter(n=>n.className.includes("am-confirmed")).length,0);
  deliver(result(true));
  assert.equal(all().filter(n=>n.className.includes("am-confirmed")).length,3);
  await all().find(n=>n.textContent.includes("Start over")&&n.tag==="button").onclick();
  deliver(result(true));
  assert.equal(all().filter(n=>n.className.includes("am-confirmed")).length,0);
  assert.equal(recogniser.onresult,null);
  x.dispose();
}

{
  const values=new Map();
  const device={getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};
  const open=profile=>fixture("blind",{reviewProfile:profile},false,{},device);
  const click=(x,label)=>nodes(x.mount).find(n=>n.tag==="button"&&n.textContent.includes(label)).onclick();
  const flagged=x=>nodes(x.mount).filter(n=>n.className.split(" ").includes("am-practice-flag")).length;
  const first=await open("learner-a");click(first,"Flag selected phrase");first.dispose();
  const other=await open("learner-b");assert.equal(flagged(other),0);other.dispose();
  const second=await open("learner-a");assert.equal(flagged(second),1);
  click(second,"Clear selected review flag");second.dispose();
  const last=await open("learner-a");assert.equal(flagged(last),0);last.dispose();
}

// Optional integration replay: unmodified position events captured from PCM
// by the pinned SDK. A trace contains hypotheses, never correctness labels.
// Replay real SDK events captured from the same clip with different inputs.
if(process.env.QURAN_CUE_TRACES){
  for(const [name,surah,counts,expected] of [
    ["clean",1,[4,4,2,3,4,3,9],0],["cut",1,[4,4,2,3,4,3,9],2],
    ["other",2,[1,7,8,12,8],0],["silence",1,[4,4,2,3,4,3,9],0]
  ]){
    const x=await fixture("blind",{meta:{s:surah,a:1,end:counts.length},
      trackWordCounts:counts,words:counts.flatMap((count,i)=>Array.from({length:count},()=>({...testWords[0],ayah:i+1})))});
    const events=JSON.parse(readFileSync(resolve(process.env.QURAN_CUE_TRACES,name+".json"),"utf8"));
    for(const event of events)x.callback(event);
    const cues=nodes(x.mount.querySelector(".am-audio-cues")).filter(n=>n.tag==="button");
    assert.equal(cues.length,expected,name);
    if(name==="cut")assert.deepEqual(cues.map(n=>n.textContent),[
      "Possible skipped passage · Ayah 3, word 2","Possible skipped passage · Ayah 4, word 1"
    ]);
    x.dispose();
  }
}
if(process.env.QURAN_POSITION_REPLAY){
  const events=JSON.parse(readFileSync(process.env.QURAN_POSITION_REPLAY,"utf8"));
  const ayah=Number(process.env.QURAN_REPLAY_AYAH);
  const count=Number(process.env.QURAN_REPLAY_WORDS);
  const f=await fixture("blind",{meta:{s:2,a:ayah,end:ayah},trackWordCounts:[count],
    words:Array.from({length:count},()=>({ayah,ar:"",en:"",letters:[]}))});
  const positions=new Set();
  for(const event of events){
    f.callback(event);
    const rows=nodes(f.mount).filter(n=>n.className.split(" ").includes("am-word"));
    const active=rows.flatMap((n,i)=>n.className.split(" ").includes("am-acoustic-cursor")?[i+1]:[]);
    assert.ok(active.length<=1);
    active.forEach(i=>positions.add(i));
    assert.ok(rows.every(n=>!n.className.includes("am-confirmed")));
  }
  assert.deepEqual([...positions],JSON.parse(process.env.QURAN_EXPECT_POSITIONS));
  console.log("Positions followed from real engine events:",[...positions]);
  f.dispose();
}
