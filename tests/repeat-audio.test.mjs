/**
 * Regression harness for reciter repetition: 1,2,3,1,2.
 * This tests the real player/controller code with a mock SDK, not speech
 * inference or Safari/ONNX audio accuracy.
 */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {dirname,resolve} from "node:path";
import {fileURLToPath} from "node:url";

let js=readFileSync(resolve(dirname(fileURLToPath(import.meta.url)),"../studio.js"),"utf8");
const sdkImport=/const tilawaSdkModule=import\(\s*"https:\/\/esm\.sh\/@tilawa\/core@1\.0\.0-rc\.0\/web\?bundle&deps=onnxruntime-web@1\.30\.0"\s*\)\.then/;
assert.match(js,sdkImport);
js=js.replace(sdkImport,"const tilawaSdkModule=Promise.resolve(mockSdk).then");

class Node{
  constructor(tag,text=""){
    this.tag=tag;this.textContent=text;this.className="";this.children=[];
    this.style={};this.attrs={};this.dataset={};this.paused=true;
    this.ended=false;this.hidden=false;this.disabled=false;this.value="";
  }
  appendChild(n){this.children.push(n);return n}
  replaceChildren(...n){this.children=n}
  setAttribute(k,v){this.attrs[k]=v}
  addEventListener(){}
  pause(){this.paused=true}
  scrollIntoView(){}
  get childNodes(){return this.children}
  get classList(){
    return {
      add:k=>{const s=new Set(this.className.split(" ").filter(Boolean));s.add(k);this.className=[...s].join(" ")},
      remove:k=>{this.className=this.className.split(" ").filter(x=>x!==k).join(" ")},
      toggle:(k,on)=>{
        const s=new Set(this.className.split(" ").filter(Boolean));
        (on??!s.has(k))?s.add(k):s.delete(k);
        this.className=[...s].join(" ");
      }
    };
  }
  querySelector(query){
    if(query.startsWith(".")&&this.className.split(" ").includes(query.slice(1)))return this;
    for(const c of this.children){const found=c.querySelector?.(query);if(found)return found}
    return null;
  }
}
const nodes=n=>[n,...n.children.flatMap(nodes)];
const document={createElement:tag=>new Node(tag),createTextNode:text=>new Node("text",text)};
class FakeAudioContext{
  async decodeAudioData(){
    return {duration:3,sampleRate:10000,numberOfChannels:1,
      getChannelData(){return new Float32Array(35000)}};
  }
  async close(){}
}
let loads=0,pushCount=0,sessionCallback=null;
const sequence=[
  {timeMs:100,word:1},
  {timeMs:400,word:2},
  {timeMs:700,word:3},
  {timeMs:1100,word:1},
  {timeMs:1400,word:2},
];
const mockSdk={
  prepareMicrophone(){return {release(){}}},
  async createTilawa(){
    loads++;
    return {
      startFreeRecitation(){
        return {
          subscribe(fn){sessionCallback=fn},
          async pushAudio(){
            const event=sequence[pushCount++];
            if(event)sessionCallback({
              type:"position",state:"locked",timeMs:event.timeMs,
              observed:[{word:{surah:2,ayah:60,word:event.word},confidence:0.96}]
            });
            return [];
          },
          async end(){return []},dispose(){}
        };
      },
      startMemorization(){
        return {subscribe(){},dispose(){}};
      },
      async listen(){return {stop:async()=>{}}},
      async dispose(){}
    };
  }
};
const factory=new Function("mockSdk","document","window","navigator","sessionStorage",
  "localStorage","AbortController","return ("+js.replace(/^export default\s*/,"")+")");
const create=factory(mockSdk,document,{AudioContext:FakeAudioContext},
  {userAgent:"iPad",platform:"iPad",maxTouchPoints:5},
  {getItem:()=>null,setItem(){},removeItem(){}},
  {getItem:()=>null,setItem(){}},AbortController);

const root=new Node("div");root.className="am-mount";
const data={
  meta:{s:2,a:60,end:60,xp:0,streak:0},
  mode:"full",cloudAvailable:false,trackWordCounts:[3],reciter:"Yasser Al-Dosari",
  words:[
    {ayah:60,ar:"فَقُلْنَا",en:"We said",letters:[]},
    {ayah:60,ar:"اضْرِبْ",en:"Strike",letters:[]},
    {ayah:60,ar:"الْحَجَرَ",en:"Stone",letters:[]}
  ],
  audio:["https://everyayah.com/data/Yasser_Ad-Dussary_128kbps/002060.mp3"],
  inlineAudio:["QUFB".repeat(200)],
  segments:[
    {ayah:60,word_idx:0,start:0,end:1000},
    {ayah:60,word_idx:1,start:1000,end:2000},
    {ayah:60,word_idx:2,start:2000,end:3000}
  ]
};
const dispose=create({data,parentElement:root,setTriggerValue(){}});
for(let i=0;i<20;i++)await Promise.resolve();
const prep=nodes(root).find(n=>n.tag==="button"&&n.textContent.includes("Analyse repeats"));
assert.ok(prep,"repeat analysis button is available");
await prep.onclick();
assert.equal(loads,1,"on-device model initialised once");
assert.ok(pushCount>=sequence.length,"prerecorded PCM fed to SDK");
const repeats=nodes(root).filter(n=>n.className==="am-note"&&n.textContent.includes("backwards"));
assert.ok(repeats.length>0,"model noticed a backwards phrase movement");
const audio=nodes(root).find(n=>n.tag==="audio");
audio.duration=3;
audio.currentTime=1.19; // word 1 was repeated at 1.1 seconds
audio.ontimeupdate();
const arabic=nodes(root).filter(n=>n.className.split(" ").includes("am-word"));
assert.match(arabic[0].className,/am-active/,"repeat returns to the first word");
assert.doesNotMatch(arabic[1].className,/am-active/,
  "static position for word 2 must not override a detected repeat");

const start=nodes(root).find(n=>n.tag==="button"&&n.textContent==="🎙 Start listening");
assert.ok(start,"microphone mode remains available");
await start.onclick();
assert.equal(loads,1,"same Quran model re-used for mic and prerecorded audio");
dispose();

console.log("PASS: Quran-recognition model detects a simulated reciter repeat, jumps back, and is re-used efficiently.");
