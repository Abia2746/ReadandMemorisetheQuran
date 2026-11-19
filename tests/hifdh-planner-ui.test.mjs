/** Noor planner R8 DOM regression: editing, focus, completion and reminders. */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {dirname,resolve} from "node:path";
import {fileURLToPath} from "node:url";
const src=readFileSync(resolve(dirname(fileURLToPath(import.meta.url)),"../hifdh_planner_ui.js"),"utf8");
class Node{
  constructor(tag,text=""){
    this.tag=tag;this.textContent=text;this.children=[];this.className="";
    this.style={};this.attrs={};this.value="";this.hidden=false;
    this.checked=false;this.disabled=false;
  }
  appendChild(x){this.children.push(x);return x}
  replaceChildren(...xs){this.children=xs}
  setAttribute(k,v){this.attrs[k]=v}
  get childNodes(){return this.children}
}
const all=n=>[n,...n.children.flatMap(all)];
const CE=(tag,cl,text="")=>{const x=new Node(tag,text);x.className=cl||"";return x};
const btn=(text,cl="am-button")=>{const x=CE("button",cl,text);return x};
const append=(p,...xs)=>{xs.forEach(x=>p.appendChild(x));return p};
let activeTab="journey",gateOpened=false;
const stage=CE("div"),panel=CE("div");
const roomTab=btn("Prayer Room");
let roomLaunches=0;roomTab.onclick=()=>{roomLaunches++};
const buttons={room:roomTab};
const events=[];
const component={setTriggerValue:(key,value)=>events.push({key,value})};
const ui={panel,stage,CE,btn,append,tabBtns:buttons,
  navigate:tab=>{activeTab=tab}};
const state={
  configured:true,goal_total:6236,done:50,left:6186,
  progress_pct:.8,required_ayahs_per_day:11,recommended_ayahs:11,
  overload:false,deadline:"2028-11-19",days_left:522,
  study_today:true,finished_today:false,today:"2026-11-19",
  teacher_message:"Noor's daily advice",
  config:{
    goal:"whole",surah:2,months:24,weekdays:[0,1,2,3,4,5],
    minutes:35,review_minutes:15,time:"18:30",remind_before:10,focus:true
  },
  today_ranges:[{surah:2,from:20,to:30,label:"Al-Baqarah 2:20–30"}],
  surahs:[
    {n:1,name:"Al-Fatihah",count:7},
    {n:2,name:"Al-Baqarah",count:286},
    {n:112,name:"Al-Ikhlas",count:4}
  ]
};
const make=new Function("setInterval","clearInterval",src+"\nreturn attachHifdhJourney;")(
  ()=>1,()=>{});
const app=make(component,{
  hifdhPlan:state,
  hifdhCalendar:"BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nEND:VEVENT\r\nEND:VCALENDAR",
  avatar:""
},ui);
assert.ok(all(panel).some(n=>n.textContent==="Noor's Hifdh Journey"),"Noor heading visible");
assert.ok(all(panel).some(n=>n.textContent==="Noor's daily advice"),"personal Noor advice shown");
const save=all(panel).find(n=>n.tag==="button"&&n.textContent==="Save my updated plan");
assert.ok(save);
save.onclick();
assert.equal(events.at(-1).key,"plan_action");
assert.equal(events.at(-1).value.action,"save");
assert.equal(events.at(-1).value.settings.months,24);
assert.equal(events.at(-1).value.settings.goal,"whole");
const complete=all(panel).find(n=>n.tag==="button"&&n.textContent.includes("completed today's"));
assert.ok(complete);
complete.onclick();
assert.equal(events.at(-1).value.action,"done");
roomTab.onclick();
const gate=all(stage).find(n=>n.className==="am-hifdh-gate");
assert.ok(gate);
assert.equal(gate.hidden,false,"opt-in focus prompt appears");
assert.equal(roomLaunches,0,"focus prompt intercepts room tab temporarily");
const bypass=all(gate).find(n=>n.tag==="button"&&n.textContent==="Continue anyway");
assert.ok(bypass);
bypass.onclick();
assert.equal(activeTab,"room","user can always exit Focus Companion");
app.setVisible(true);
app.setVisible(false);
app.dispose();
assert.equal(buttons.room.onclick===roomTab.onclick,true);
console.log("PASS: Noor plan editor, saved goal options, completion events, gentle optional Focus prompt and bypass.");
