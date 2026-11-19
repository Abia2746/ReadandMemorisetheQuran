/* Noor's Hifdh journey — original, editable, client UI.
 * Rewards and completion state remain server-authoritative.
 * Reminders are calendar exports; no false background push promises.
 */
function attachHifdhJourney(component,D,ui){
  const {panel,CE,btn,append,tabBtns,navigate}=ui;
  const state=D.hifdhPlan||{},config=state.config||{};
  const saved=Boolean(state.configured);
  const days=new Set(config.weekdays||[0,1,2,3,4,5]);
  let alertTimer=null,focusBypassed=false;
  const root=CE("section","am-hifdh");
  panel.appendChild(root);
  const header=CE("div","am-hifdh-heading");
  append(header,CE("div","am-hifdh-overline","Your Qur'an · your pace"),
    CE("h2","","Noor's Hifdh Journey"),
    CE("p","","A gentle, adaptive plan for memorisation, revision and consistency. Shape it around school, family and your daily routine."));
  root.appendChild(header);
  const status=CE("div","am-hifdh-toast",String(D.planMessage||""));
  status.hidden=!D.planMessage;root.appendChild(status);
  const columns=CE("div","am-hifdh-grid"),left=CE("div","am-hifdh-column"),right=CE("div","am-hifdh-column");
  append(columns,left,right);root.appendChild(columns);
  const noor=CE("div","am-hifdh-card am-hifdh-noor");
  const noorHeader=CE("div","am-hifdh-noor-heading");
  const avatar=CE("img","am-hifdh-noor-photo");
  if(D.avatar){avatar.src=D.avatar;avatar.alt="Ustadha Noor, study companion";noorHeader.appendChild(avatar)}
  const noorTitle=CE("div","");
  append(noorTitle,CE("span","am-hifdh-overline","Your learning companion"),
    CE("h3","","A plan with Noor"),CE("span","am-hifdh-pill","Adaptive · Editable"));
  noorHeader.appendChild(noorTitle);noor.appendChild(noorHeader);
  noor.appendChild(CE("p","am-hifdh-noor-message",state.teacher_message||"Assalamu alaikum. Let's plan your next step."));
  noor.appendChild(CE("p","am-hifdh-note","This guidance is calculated from your goals and completed verses, not a certified Hifdh or Tajweed assessment. Some ayahs take much longer than others."));
  left.appendChild(noor);
  const editor=CE("div","am-hifdh-card");
  append(editor,CE("h3","","Build your personal plan"),
    CE("p","am-hifdh-note","Update your goal or routine at any time. Saved memorisation progress stays intact."));
  const form=CE("div","am-hifdh-form");
  const field=(label,control)=>{
    const wrapper=CE("label","am-hifdh-field");
    append(wrapper,CE("span","",label),control);form.appendChild(wrapper);return wrapper;
  };
  const option=(select,value,label)=>{
    const opt=CE("option","",label);opt.value=String(value);select.appendChild(opt);
  };
  const goal=CE("select","");
  option(goal,"surah","One surah");option(goal,"whole","The whole Qur'an");
  goal.value=config.goal||"surah";field("What would you like to memorise?",goal);
  const surah=CE("select","");
  for(const chapter of state.surahs||[])option(surah,chapter.n,chapter.n+" · "+chapter.name+" ("+chapter.count+" ayahs)");
  surah.value=String(config.surah||2);
  const surahLabel=field("Choose your surah",surah);
  const showSurah=()=>{surahLabel.hidden=goal.value==="whole"};
  goal.onchange=showSurah;showSurah();
  const months=CE("select","");
  for(const m of [1,2,3,6,9,12,18,24,30,36,48,60,72,120])
    option(months,m,m<12?m+" months":m%12===0?m/12+" years":m+" months");
  months.value=String(config.months||24);field("When would you like to finish?",months);
  const time=CE("input","");time.type="time";time.value=config.time||"18:30";
  field("Best time for your session",time);
  const newMins=CE("select","");
  for(const m of [10,15,20,25,30,35,40,45,60,75,90,120])option(newMins,m,m+" min");
  newMins.value=String(config.minutes||35);field("New memorisation time",newMins);
  const reviewMins=CE("select","");
  for(const m of [0,5,10,15,20,25,30,40,45,60,75,90])option(reviewMins,m,m+" min");
  reviewMins.value=String(config.review_minutes??15);field("Revision time",reviewMins);
  const lead=CE("select","");
  for(const m of [0,5,10,15,20,30,45,60])option(lead,m,m===0?"At the start":m+" min beforehand");
  lead.value=String(config.remind_before??10);field("Reminder before study",lead);
  const week=CE("div","am-hifdh-days");
  week.appendChild(CE("span","am-hifdh-form-label","Which days are free?"));
  const weekButtons=CE("div","am-hifdh-weekdays");
  ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].forEach((label,i)=>{
    const button=btn(label,"am-hifdh-day");
    button.setAttribute("aria-pressed",String(days.has(i)));
    button.onclick=()=>{
      if(days.has(i)&&days.size===1){notify("Choose at least one study day.");return}
      days.has(i)?days.delete(i):days.add(i);
      button.setAttribute("aria-pressed",String(days.has(i)));
    };
    weekButtons.appendChild(button);
  });
  week.appendChild(weekButtons);form.appendChild(week);
  const focus=CE("label","am-hifdh-focus-toggle");
  const check=CE("input","");check.type="checkbox";check.checked=Boolean(config.focus);
  append(focus,check,CE("span","","Focus Companion · gently encourage study before visiting the Prayer Room"));
  form.appendChild(focus);
  form.appendChild(CE("p","am-hifdh-note","Optional, reversible and within Al-Mu'allim only. It cannot lock other iPad apps."));
  const saveBtn=btn(saved?"Save my updated plan":"Create my plan","am-button am-primary am-hifdh-save");
  saveBtn.onclick=()=>send("save",{settings:{
    goal:goal.value,surah:Number(surah.value)||2,months:Number(months.value)||24,
    weekdays:[...days].sort((a,b)=>a-b),time:time.value||"18:30",
    minutes:Number(newMins.value)||35,review_minutes:Number(reviewMins.value),
    remind_before:Number(lead.value),focus:Boolean(check.checked)
  }});
  form.appendChild(saveBtn);editor.appendChild(form);left.appendChild(editor);

  const today=CE("div","am-hifdh-card am-hifdh-today");
  append(today,CE("div","am-hifdh-overline","Every day is a fresh beginning"),
    CE("h3","","Today's study plan"));
  const metrics=CE("div","am-hifdh-metrics");
  for(const [label,value] of [
    ["Memorised",(state.done||0)+" / "+(state.goal_total||0)],
    ["Progress",(state.progress_pct||0)+"%"],
    ["Suggested",String(state.required_ayahs_per_day||0)+" ayahs / day"]
  ]){
    const cell=CE("div","am-hifdh-metric");
    append(cell,CE("strong","",value),CE("span","",label));metrics.appendChild(cell);
  }
  today.appendChild(metrics);
  const track=CE("div","am-hifdh-progress"),bar=CE("div","am-hifdh-progress-fill");
  bar.style.width=Math.max(0,Math.min(100,Number(state.progress_pct)||0))+"%";
  track.appendChild(bar);today.appendChild(track);
  today.appendChild(CE("p","am-hifdh-note","Target: "+(state.deadline||"not set")+" · "+(state.days_left||0)+" planned study days remaining."));
  if(state.overload)today.appendChild(CE("p","am-hifdh-warning",
    "This deadline may require too much per study day, especially for long ayahs. Consider extending your timeline rather than rushing."));
  const steps=CE("div","am-hifdh-steps");
  function step(num,description){
    const row=CE("div","am-hifdh-step");
    append(row,CE("span","am-hifdh-step-num",num),CE("span","",description));
    steps.appendChild(row);
  }
  if(!saved){
    step("✧","Save your plan to see tomorrow's and today's personal ayah targets.");
  }else if(state.finished_today){
    step("✓","Alhamdulillah. Today's plan has been marked complete. Feel free to revise or rest.");
  }else if(!state.study_today){
    step("☾","Today is a rest or catch-up day. You can listen or review without pressure.");
  }else{
    step("01","Revision · "+(config.review_minutes??15)+" min: yesterday's verses and a selection from last week.");
    step("02","Listen once to a trusted reciter, then work through a few words at a time.");
    for(const r of state.today_ranges||[])step("✦",r.label);
    step("03","Recite without hints and review difficult sounds with a qualified teacher.");
  }
  today.appendChild(steps);
  const done=btn("✓ I completed today's planned passage","am-button am-primary am-hifdh-done");
  done.disabled=!saved||state.finished_today||!state.study_today||!(state.today_ranges||[]).length;
  done.onclick=()=>send("done");today.appendChild(done);
  today.appendChild(CE("p","am-hifdh-note","Completion is self-reported. Missed days are recalculated without penalties, and finishing a plan never certifies Tajweed accuracy."));
  right.appendChild(today);

  const calendar=CE("div","am-hifdh-card");
  append(calendar,CE("h3","","Gentle device reminders"),
    CE("p","am-hifdh-note","Import a 90-day schedule into Apple Calendar and enable its alerts for device notifications. You control all reminders."));
  const actions=CE("div","am-hifdh-actions");
  const exportBtn=btn("◷ Download Calendar reminders","am-button am-primary");
  exportBtn.disabled=!saved||!D.hifdhCalendar;
  exportBtn.onclick=()=>{
    try{
      const blob=new Blob([D.hifdhCalendar],{type:"text/calendar;charset=utf-8"});
      const uri=URL.createObjectURL(blob);
      const anchor=document.createElement("a");
      anchor.href=uri;anchor.download="al-muallim-hifdh-calendar.ics";
      document.body.appendChild(anchor);anchor.click();anchor.remove();
      setTimeout(()=>URL.revokeObjectURL(uri),30000);
      notify("Calendar file prepared. Import it and enable Apple Calendar alerts. Re-importing can duplicate events.");
    }catch(e){notify("Calendar download unavailable: "+String(e?.message||e))}
  };
  const notifyBtn=btn("Allow alerts while open","am-button");
  notifyBtn.onclick=async()=>{
    if(typeof Notification==="undefined"){
      notify("Notifications aren't supported in this browser view. Use the Calendar export.");
      return;
    }
    try{
      const p=await Notification.requestPermission();
      notify(p==="granted"
        ?"Enabled while the app is open. Use Calendar for reminders after closing Safari."
        :"Permission not enabled. Apple Calendar remains available.");
    }catch(e){notify("Browser notifications unavailable; use Apple Calendar.")}
  };
  append(actions,exportBtn,notifyBtn);calendar.appendChild(actions);
  calendar.appendChild(CE("p","am-hifdh-note",
    "This Streamlit app has no background push server. iPad Safari tabs cannot guarantee notifications while closed."));
  const screenTime=CE("div","am-hifdh-device-explain");
  append(screenTime,CE("strong","","Want genuine app limits?"),
    CE("p","","A website cannot block other apps on iPad. If you want limits, configure Settings → Screen Time → App Limits on your own device. Focus Companion only adds a gentle prompt inside Al-Mu'allim."));
  calendar.appendChild(screenTime);right.appendChild(calendar);

  const gate=CE("div","am-hifdh-gate");gate.hidden=true;
  const gateCard=CE("div","am-hifdh-gate-panel");
  append(gateCard,CE("div","am-hifdh-overline","Focus Companion"),
    CE("h3","","A quiet invitation to practise"),
    CE("p","","You enabled Focus Companion and today's plan isn't yet marked complete. Would you like to return to it first?"));
  const gateActions=CE("div","am-hifdh-actions");
  const goBack=btn("Return to My Journey","am-button am-primary");
  goBack.onclick=()=>{gate.hidden=true;navigate("journey")};
  const continueBtn=btn("Continue anyway","am-button");
  continueBtn.onclick=()=>{gate.hidden=true;focusBypassed=true;navigate("room")};
  append(gateActions,goBack,continueBtn);
  gateCard.appendChild(gateActions);gate.appendChild(gateCard);panel.appendChild(gate);
  const priorRoomClick=tabBtns.room?.onclick;
  if(tabBtns.room && typeof priorRoomClick==="function"){
    tabBtns.room.onclick=()=>{
      if(saved&&config.focus&&state.study_today&&!state.finished_today&&!focusBypassed){
        gate.hidden=false;
      }else priorRoomClick();
    };
  }
  function notify(s){status.hidden=false;status.textContent=String(s||"")}
  function send(action,more={}){
    if(typeof component.setTriggerValue!=="function"){
      notify("This app build cannot save changes.");return;
    }
    notify("Updating Noor's plan…");
    component.setTriggerValue("plan_action",{
      id:String(Date.now())+"-"+Math.random().toString(36).slice(2,8),
      action,tab:"journey",...more
    });
  }
  function checkOpenReminder(){
    if(!saved||!state.study_today||state.finished_today||
       typeof Notification==="undefined"||Notification.permission!=="granted")return;
    try{
      const hm=new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/London",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date());
      const [h,m]=hm.split(":").map(Number);
      const [hour,minute]=String(config.time||"18:30").split(":").map(Number);
      const start=hour*60+minute-(Number(config.remind_before)||0);
      if(h*60+m<start||h*60+m>start+1)return;
      const key="am:hifdh-notification:"+state.today+":"+config.time;
      if(sessionStorage.getItem(key))return;
      sessionStorage.setItem(key,"sent");
      new Notification("A quiet moment with the Qur'an",{
        body:"Your Noor revision and memorisation session is ready."
      });
    }catch(_){}
  }
  function setVisible(visible){
    root.hidden=!visible;
    if(visible){
      if(alertTimer===null)alertTimer=setInterval(checkOpenReminder,45000);
    }else if(alertTimer!==null){clearInterval(alertTimer);alertTimer=null}
  }
  return {setVisible,dispose(){
    if(alertTimer!==null)clearInterval(alertTimer);
    if(priorRoomClick&&tabBtns.room)tabBtns.room.onclick=priorRoomClick;
  }};
}
