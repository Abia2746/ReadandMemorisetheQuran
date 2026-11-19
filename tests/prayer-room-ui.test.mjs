/** Run the actual room UI with a lightweight DOM and mocked 3D scene. */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {resolve,dirname} from "node:path";
import {fileURLToPath} from "node:url";
const src=readFileSync(resolve(dirname(fileURLToPath(import.meta.url)),"../prayer_room_ui.js"),"utf8");
class Element{
  constructor(tag,text=""){
    this.tag=tag;this.textContent=text;this.children=[];this.className="";
    this.attrs={};this.style={};this.hidden=false;this.disabled=false;this.value="";
  }
  appendChild(n){this.children.push(n);return n}
  replaceChildren(...items){this.children=items}
  setAttribute(k,v){this.attrs[k]=v}
  addEventListener(){}
  get childNodes(){return this.children}
  get classList(){
    return {toggle:(c,v)=>{const s=new Set(this.className.split(" ").filter(Boolean));
      (v??!s.has(c))?s.add(c):s.delete(c);this.className=[...s].join(" ")},
      add:c=>{const s=new Set(this.className.split(" ").filter(Boolean));
        s.add(c);this.className=[...s].join(" ")},
      remove:c=>{this.className=this.className.split(" ").filter(x=>x&&x!==c).join(" ")}};
  }
  querySelector(selector){
    if(selector==="p"&&this.tag==="p")return this;
    if(selector.startsWith(".")&&this.className.split(" ").includes(selector.slice(1)))return this;
    for(const child of this.children){const found=child.querySelector?.(selector);if(found)return found}
    return null;
  }
}
const all=node=>[node,...node.children.flatMap(all)];
const CE=(tag,cl,text)=>{const n=new Element(tag,text);n.className=cl||"";return n};
const btn=(text,cls="am-button")=>{const n=CE("button",cls,text);n.type="button";return n};
const append=(parent,...kids)=>{kids.forEach(n=>n&&parent.appendChild(n));return parent};
let sceneCalls=0,sceneStopped=0,sceneDisposed=0,lastScene=null;
const recordedMoods=[];
const recordedRain=[];
const createPrayerRoomScene=async(canvas,options)=>{
  sceneCalls++;lastScene=options;
  return {start(){},stop(){sceneStopped++},dispose(){sceneDisposed++},
    setMood(m){recordedMoods.push(m)},setRain(level){recordedRain.push(level)},resetCamera(){} };
};
const make=new Function("createPrayerRoomScene",src+"\nreturn attachPrayerRoom;")(createPrayerRoomScene);
const ui={
  stage:new Element("div"),
  main:new Element("div"),tabs:new Element("div"),tabBtns:{},CE,btn,append,
  onNavigate:page=>{activeTab=page;room.setVisible(page==="room")},
  getCurrentTab:()=>activeTab,
};
let activeTab="read";
const events=[];
const component={setTriggerValue:(key,val)=>events.push({key,val})};
const room=make(component,{
  meta:{s:2,a:60,end:61},
  prayerClock:{
    city:"London",cities:["London","Birmingham"],timezone:"Europe/London",
    available:true,times:{
      Fajr:"05:30",Sunrise:"07:10",Dhuhr:"12:10",
      Asr:"14:35",Maghrib:"16:18",Isha:"18:03"
    }
  },
  room:{
    xp:150,coins:175,owned:["plant_olive"],
    equipped:{plant:"plant_olive"},
    items:[
      {id:"plant_olive",name:"Olive Tree",category:"plant",price:110,unlock_xp:0,description:"Organic foliage"},
      {id:"rug_emerald",name:"Emerald Rug",category:"rug",price:200,unlock_xp:100,description:"Handwoven"}]
  }
},ui);
assert.ok(ui.tabBtns.room,"Prayer Room tab added");
assert.ok(ui.main.children.some(c=>c.className==="am-room-claim"),"Study rewards visible");
room.setPracticeMode("read");
const readButton=all(ui.main).find(n=>n.tag==="button"&&n.textContent.includes("Mark read"));
readButton.onclick();
assert.equal(events[0].key,"room_action");
assert.equal(events[0].val.action,"read");
assert.equal(events[0].val.ayah,60);
assert.equal(events[0].val.tab,"read");
room.setPracticeMode("cover");
const memorize=all(ui.main).find(n=>n.tag==="button"&&n.textContent.includes("Mark memorised"));
memorize.onclick();
assert.equal(events[1].val.action,"memorise");
assert.equal(events[1].val.tab,"cover");

ui.tabBtns.room.onclick();
for(let i=0;i<4;i++)await Promise.resolve();
assert.equal(sceneCalls,1,"3D scene initialized when prayer room opened");
assert.equal(ui.stage.children.length,1);
assert.equal(ui.stage.children[0].hidden,false);
const mood=all(ui.stage).find(n=>n.tag==="select"&&n.attrs["aria-label"]==="Room lighting and time of day");
assert.ok(mood,"Auto / Fajr / day / sunset / night selector exists");
mood.value="night";mood.onchange();
assert.equal(recordedMoods.at(-1),"night","manual moonlit mood applies without 3D rebuild");
mood.value="day";mood.onchange();
assert.equal(recordedMoods.at(-1),"day","manual daylight applies without 3D rebuild");
assert.equal(sceneCalls,1,"lighting changes do not re-initialise the 3D scene");
const rain=all(ui.stage).find(n=>n.tag==="select"&&n.attrs["aria-label"]==="Animated falling rain intensity");
assert.ok(rain,"immersive rain intensity selector exists");
rain.value="storm";rain.onchange();
assert.equal(recordedRain.at(-1),"storm","storm starts without rebuilding room");
rain.value="off";rain.onchange();
assert.equal(recordedRain.at(-1),"off","rain can be turned off instantly");
assert.equal(sceneCalls,1,"weather intensity does not recreate 3D scene");
const city=all(ui.stage).find(n=>n.tag==="select"&&n.attrs["aria-label"]==="City for prayer-time ambience");
assert.ok(city,"City selector exists without GPS");
city.value="Birmingham";city.onchange();
assert.equal(events.at(-1).val.action,"set_prayer_city");
assert.equal(events.at(-1).val.city,"Birmingham");
const shopItems=all(ui.stage).filter(n=>n.className==="am-room-item");
assert.equal(shopItems.length,2);
const place=all(ui.stage).find(n=>n.tag==="button"&&n.textContent==="Remove");
assert.ok(place,"Owned item can be unequipped");
place.onclick();
assert.equal(events.at(-1).val.action,"unequip");
assert.equal(events.at(-1).val.category,"plant");
const preview=all(ui.stage).find(n=>n.tag==="button"&&n.textContent==="Preview");
preview.onclick();
for(let i=0;i<5;i++)await Promise.resolve();
assert.equal(sceneCalls,2,"Preview rebuilds the room with the new decor");
assert.ok(sceneDisposed>0,"Previous 3D instance disposed after preview");
room.setVisible(false);
assert.ok(sceneStopped>0,"3D loop stops outside this tab");
room.dispose();
console.log("PASS: Prayer Room tab, XP claims, shop/equipment events, 3D preview and scene cleanup.");
