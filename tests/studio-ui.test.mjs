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
assert.match(source,/Window Lounge · R7/);
assert.match(source,/@tilawa\/core@1\.0\.0-rc\.0\/web/);
assert.match(source,/prepareMicrophone\(\)/);
assert.doesNotMatch(source,/const micTest=btn/);

const importExpression=/const tilawaSdkModule=import\(\s*"https:\/\/esm\.sh\/@tilawa\/core@1\.0\.0-rc\.0\/web\?bundle&deps=onnxruntime-web@1\.30\.0"\s*\)\.then/;
assert.match(source,importExpression);
source=source.replace(importExpression,"const tilawaSdkModule=Promise.resolve(mockSdk).then");

class Element{
  constructor(tag,text=""){
    this.tag=tag;this.textContent=text;this.children=[];this.className="";
    this.style={};this.dataset={};this.attributes={};this.hidden=false;
    this.disabled=false;this.paused=true;this.value="";
  }
  appendChild(node){this.children.push(node);return node}
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
async function fixture(mode,overrides={},startListening=true){
  let callback,prepared=0,listenCount=0,stopCount=0;
  const mockSdk={
    prepareMicrophone(){
      prepared++;
      return {release(){}}
    },
    async createTilawa(){
      return {
        startMemorization(){
          return {subscribe(fn){callback=fn},dispose(){}}
        },
        async listen(){listenCount++;return {stop:async()=>{stopCount++}}},
        async dispose(){}
      };
    }
  };
  const combined = roomUiSource+"\n"+
    source.replace(/^export default function\(component\)/,"function Studio(component)")+
    "\nreturn Studio;";
  const factory=new Function("mockSdk","document","window","navigator","sessionStorage",
     "localStorage","AbortController","createPrayerRoomScene", combined);
  const create=factory(mockSdk,document,{},{
    userAgent:"iPad",platform:"iPad",maxTouchPoints:5
  },{getItem:()=>null,setItem(){}},{getItem:()=>null,setItem(){}},abortCtor,
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
  assert.equal(select.value,"local","Quran listener selected rather than browser dictation");
  if(startListening){
    await start.onclick();
    assert.equal(prepared,1,"Safari microphone prepared on the real tap");
    assert.equal(listenCount,1,"SDK listen() invoked");
    assert.ok(callback,"received SDK position subscription");
  }
  return {mount,callback,dispose,getStopCount:()=>stopCount};
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
  x.callback({type:"position",state:"locked",observed:[{word:{surah:2,ayah:60,word:2}}]});
  reveal=nodes(x.mount).filter(n=>n.className.split(" ").includes("am-revealed-ar"));
  assert.deepEqual(reveal.map(n=>n.textContent),["فَقُلْنَا"],"first word only reveals after moving to the second");
  x.callback({type:"position",state:"locked",observed:[{word:{surah:2,ayah:60,word:3}}]});
  reveal=nodes(x.mount).filter(n=>n.className.split(" ").includes("am-revealed-ar"));
  assert.deepEqual(reveal.map(n=>n.textContent),["فَقُلْنَا","اضْرِبْ"]);
  x.callback({type:"position",state:"locked",observed:[{word:{surah:99,ayah:60,word:3}}]});
  reveal=nodes(x.mount).filter(n=>n.className.split(" ").includes("am-revealed-ar"));
  assert.equal(reveal.length,2,"unrelated Surah does not advance memorisation");
  x.dispose();
}
{
  const x=await fixture("full");
  x.callback({type:"position",state:"locked",observed:[{word:{surah:2,ayah:60,word:2}}]});
  const wordNodes=nodes(x.mount).filter(n=>n.className.split(/\s+/).includes("am-word"));
  assert.equal(wordNodes.filter(n=>n.className.includes("am-active")).length,1);
  assert.match(wordNodes[1].className,/am-active/,"reading highlight follows the SDK");
  assert.equal(nodes(x.mount).filter(n=>n.className.includes("am-revealed-ar")).length,0,
    "reading mode does not insert duplicate Arabic text");
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
  a.duration=3;a.currentTime=1.5;
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
  audio.duration=3;audio.currentTime=1.6;audio.ontimeupdate();
  const words=nodes(x.mount).filter(n=>n.className.split(" ").includes("am-word"));
  assert.equal(words.filter(n=>n.className.includes("am-active")).length,0,
    "missing timings must NOT produce a guessed active word");
  assert.equal(words.filter(n=>n.className.includes("am-ayah-playing")).length,3,
    "without word data, highlight only the actual ayah");
  x.dispose();
}
console.log("PASS: R7 SDK events, delayed memorisation reveal, and source-matched reciter timing without guesswork.");
