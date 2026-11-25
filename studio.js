export default function(component) {
  "use strict";
  const D=component.data || {};
  const words=Array.isArray(D.words)?D.words:[];
  const meta=D.meta || {};
  const language=String(D.language||"en");
  const labels=D.uiStrings||{};
  const T=(key,fallback)=>String(labels[key]||fallback);
  const verseTranslations=D.verseTranslations||{};
  const root=component.parentElement.querySelector(".am-mount");
  if(!root)return;
  root.replaceChildren();
  if(typeof localizeStudioShell==="function")queueMicrotask(()=>localizeStudioShell(root,String(D.language||"en"),D.uiCatalogue||{}));
  const CE=(tag,cls,text)=>{
    const n=document.createElement(tag);
    if(cls)n.className=cls;
    if(text!==undefined&&text!==null)n.textContent=String(text);
    return n;
  };
  const append=(parent,...items)=>{items.forEach(x=>{if(x)parent.appendChild(x)});return parent};
  const btn=(label,cls="am-button")=>{const b=CE("button",cls,label);b.type="button";return b};
  const header=CE("div","am-top");
  const brand=CE("div","am-logo");
  const seal=CE("div","am-seal","۞");
  const brandText=CE("div","am-brand");
  append(brandText,CE("strong","", "Al-Mu'allim"),CE("small","", "Your Qur'an companion"));
  append(brand,seal,brandText);
  const headRight=CE("div","am-head-right");
  append(headRight,
    CE("span","am-chip","✧ "+String(meta.xp||0)+" XP"),
    CE("span","am-chip","✺ "+String(meta.streak||0)+" day streak"));
  append(header,brand,headRight);
  const app=CE("section","am-app");
  app.appendChild(header);
  root.appendChild(app);
  const tabs=CE("div","am-tabs");
  tabs.setAttribute("role","tablist");
  const pages=[
    ["read","☷",T("read","Read")],
    ["cover","◉",T("cover","Memorise")],
    ["listen","♫",T("listen","Listen")],
    ["journey","✦",T("journey","My journey")]
  ];
  const tabBtns={};
  pages.forEach(([id,icon,title])=>{
    const b=btn(icon+" "+title,"am-tab");
    b.setAttribute("role","tab");
    b.setAttribute("aria-selected","false");
    b.onclick=()=>selectTab(id);
    tabBtns[id]=b;
    tabs.appendChild(b);
  });
  app.appendChild(tabs);
  const hero=CE("div","am-hero");
  hero.appendChild(CE("div","am-eyebrow","A moment with the Qur'an"));
  const titleAr=CE("div","am-ar-title",String(D.surahArabic||"القرآن الكريم"));
  const titleEn=CE("h1","",String(D.surahEnglish||"Surah "+meta.s));
  hero.appendChild(titleAr);
  hero.appendChild(titleEn);
  const subtitle=CE("p","", "Ayahs "+meta.a+"–"+meta.end+" · "+words.length+" words · "+String(D.reciter||"Recitation practice"));
  hero.appendChild(subtitle);
  hero.appendChild(CE("div","am-ornament","✦ ── ✦"));
  app.appendChild(hero);
  const stage=CE("div","am-stage");
  app.appendChild(stage);
  const layout=CE("div","am-layout");
  const main=CE("div","am-main");
  const side=CE("div","am-side");
  append(layout,main,side);stage.appendChild(layout);
  const readerPanel=CE("section","am-panel");
  main.appendChild(readerPanel);
  const sectionTop=CE("div","am-section-top");
  const sectionHeading=CE("h2","", "The Noble Qur'an");
  const range=CE("span","am-verse-range","Surah "+meta.s+" · "+meta.a+"–"+meta.end);
  append(sectionTop,sectionHeading,range);
  readerPanel.appendChild(sectionTop);
  const basmalah=CE("div","am-basmala","بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ");
  if(meta.a!==1 || meta.s===9)basmalah.hidden=true;
  readerPanel.appendChild(basmalah);
  const textArea=CE("div","am-mushaf");
  textArea.setAttribute("aria-label","Uthmani Qur'an text");
  readerPanel.appendChild(textArea);
  // Published verse meanings follow the selected locale; never replace Arabic.
  const translatedEntries=Object.entries(verseTranslations)
    .filter(([ayah,text])=>Number(ayah)>=Number(meta.a)&&Number(ayah)<=Number(meta.end)&&String(text).trim());
  if(translatedEntries.length){
    const translations=CE("section","am-panel am-translations");
    translations.style.marginTop="14px";
    translations.setAttribute("lang",language);
    const heading=CE("h3","am-smallhead",T("translation","Translation")+" · "+language.toUpperCase());
    translations.appendChild(heading);
    translatedEntries.sort((a,b)=>Number(a[0])-Number(b[0])).forEach(([ayah,meaning])=>{
      const row=CE("div","am-translation-ayah");
      row.style.padding="10px 0";
      row.style.borderBottom="1px solid rgba(155,135,99,.2)";
      append(row,CE("strong","",String(meta.s)+":"+ayah),CE("p","",meaning));
      translations.appendChild(row);
    });
    readerPanel.appendChild(translations);
  }
  const controls=CE("div","am-control-row");
  const toggleHint=btn("✧ "+T("hints","Show hints"));
  const toggleColour=btn("◈ Tajweed signs");
  const resetBtn=btn("↺ "+T("reset","Start over"));
  const recordHint=btn("🎙 Live recitation","am-button am-primary");
  append(controls,toggleHint,toggleColour,resetBtn,recordHint);
  readerPanel.appendChild(controls);
  const status=CE("div","am-status");
  status.dataset.state="idle";
  const stateLine=CE("div","am-status-line");
  const dot=CE("span","am-pulse");
  const statusText=CE("span","", "Ready to practise. Tap the microphone to start.");
  append(stateLine,dot,statusText);
  const progress=CE("div","am-track");const progressFill=CE("div","");
  progress.appendChild(progressFill);
  const transcript=CE("div","am-note","");
  transcript.style.marginTop="10px";
  append(status,stateLine,progress,transcript);
  readerPanel.appendChild(status);
  const detail=CE("div","am-detail");detail.hidden=true;readerPanel.appendChild(detail);
  const audioPanel=CE("div","am-audio");
  audioPanel.appendChild(CE("small","", "LISTEN TO THE RECITER · "+String(D.reciter||"")));
  const audio=CE("audio");
  audio.controls=true;audio.preload="none";
  const playlist=Array.isArray(D.audio)?D.audio:[];
  const inlineAudio=Array.isArray(D.inlineAudio)?D.inlineAudio:[];
  let playingIndex=0;
  if(playlist.length)audio.src=playlist[0];
  audioPanel.appendChild(audio);
  const playCaption=CE("div","am-note","Follow the teacher's recitation at your own pace.");
  playCaption.style.marginTop="8px";
  audioPanel.appendChild(playCaption);
  const repeatControls=CE("div","am-control-row");
  const repeatBtn=btn("⟲ Follow repeated phrases","am-button am-on");
  repeatBtn.setAttribute("aria-pressed","true");
  const analyseRepeatBtn=btn("✧ Analyse repeats");
  const repeatHelp=CE("div","am-note","Repeat-aware following uses local Qur'an speech recognition when supported. Source-matched word timings remain the fallback.");
  repeatHelp.style.margin="0 12px 10px";
  repeatControls.appendChild(repeatBtn);
  repeatControls.appendChild(analyseRepeatBtn);
  repeatControls.hidden=!inlineAudio.some(Boolean);
  repeatHelp.hidden=repeatControls.hidden;
  audioPanel.appendChild(repeatControls);
  audioPanel.appendChild(repeatHelp);
  readerPanel.appendChild(audioPanel);
  const micPanel=CE("div","am-panel");
  micPanel.style.marginTop="14px";
  const micTop=CE("div","am-section-top");
  append(micTop,CE("h2","", "Live recitation"),CE("span","am-badge","Word-following practice"));
  micPanel.appendChild(micTop);
  const micBody=CE("div","am-scaffold");
  const micDescription=CE("p","am-note",
     "The Qur’an listener follows the sounds in your microphone on this device. A dashed gold outline shows your estimated place. Pronunciation and Tajweed remain ungraded.");
  const micControls=CE("div","am-control-row");
  const micButton=btn("🎙 Start listening","am-button am-primary");

  const engineSelect=CE("select","am-input");
  engineSelect.setAttribute("aria-label","Speech recognition method");
  [
    ["local","On-device Qur’an listener"],
    ["vowels","Short-vowel review · 12 seconds on device"],
    ["browser","Optional · browser Arabic transcription"],
    ["cloud",D.cloudAvailable?"Optional · cloud Arabic transcription":"Cloud transcription · requires API key"]
  ].forEach(([value,label])=>{
    const op=CE("option","",label);op.value=value;engineSelect.appendChild(op);
  });
  engineSelect.value="local";
  append(micControls,micButton,engineSelect);
  const meter=CE("div","am-meter"),meterFill=CE("div","");
  meter.appendChild(meterFill);
  const micText=CE("div","am-note","Choose a listener, then tap Start listening.");
  const micMessage=CE("div","am-note","Audio stays on this device while using the Qur’an listener.");
  append(micBody,micDescription,micControls,meter,micText,micMessage);
  let vowelPlayback=null;
  const vowelReport=CE("div","am-note");
  vowelReport.setAttribute("role","status");
  micBody.appendChild(vowelReport);
  micPanel.appendChild(micBody);
  main.appendChild(micPanel);
  const teacher=CE("section","am-panel am-teacher");
  const portrait=D.avatar ? CE("img","am-portrait") : CE("div","am-portrait","✧");
  if(D.avatar){portrait.src=D.avatar;portrait.alt="Illustrated AI tutor avatar";}
  append(teacher,portrait,CE("div","am-eyebrow","Your learning companion"));
  teacher.appendChild(CE("h3","",String(D.teacherName||"AI Teacher")));
  teacher.appendChild(CE("p","", "Listen · Repeat · Reflect"));
  const teacherQuote=CE("div","am-quote",
    "Begin with a little, recite steadily, and review what needs attention. I can guide your practice, but detailed pronunciation should be checked against clear audio.");
  teacher.appendChild(teacherQuote);
  side.appendChild(teacher);
  const stats=CE("section","am-panel am-mini");
  stats.appendChild(CE("h3","am-smallhead","Your selected passage"));
  const statRows=[
    ["Verses",String((meta.end||meta.a)-(meta.a||0)+1)],
    ["Words",String(words.length)],
    ["Reciter",String(D.reciter||"Selected reciter")],
    ["Reviewed previously",String(D.reviewed||0)+" words"]
  ];
  statRows.forEach(([label,value])=>{
    const line=CE("div","am-mini-row");
    append(line,CE("span","",label),CE("b","",value));stats.appendChild(line);
  });
  const liveCount=CE("b","","Waiting for recitation");
  const liveCountLabel=CE("span","","Current listening position");
  const matchedRow=CE("div","am-mini-row");
  append(matchedRow,liveCountLabel,liveCount);
  stats.appendChild(matchedRow);
  side.appendChild(stats);
  const reviewPanel=CE("section","am-panel am-mini");
  reviewPanel.appendChild(CE("h3","am-smallhead","How practice works"));
  [
    ["01","Listen","Hear the ayah from your selected reciter"],
    ["02","Recall","Use English clues in Memorise mode"],
    ["03","Recite","Follow the live speech indicator when supported"],
    ["04","Review","Record a passage below for AI-assisted feedback"]
  ].forEach(([n,title,desc])=>{
    const line=CE("div","am-mini-row");
    const left=CE("div","");
    append(left,CE("b","",n+" · "+title),CE("div","am-note",desc));
    line.appendChild(left);reviewPanel.appendChild(line);
  });
  side.appendChild(reviewPanel);
  const journeyPanel=CE("section","am-subpage");
  journeyPanel.hidden=true;
  stage.appendChild(journeyPanel);
  const journeyGrid=CE("div","am-guide");
  [
    ["✦","Begin with presence","Listen once and notice where each verse begins and ends."],
    ["☾","Strengthen your Hifz","Recite from English clues. Reveal hints only when you need them."],
    ["✧","Review with evidence","Use the recording review to identify possible mistakes; verify subtle Tajweed with a qualified teacher."]
  ].forEach(([icon,title,desc])=>{
    const c=CE("div","am-guide-card");
    append(c,CE("div","am-guide-icon",icon),CE("b","",title),CE("p","",desc));
    journeyGrid.appendChild(c);
  });
  journeyPanel.appendChild(journeyGrid);
  const history=CE("div","am-panel am-history");
  history.style.marginTop="14px";
  history.appendChild(CE("h3","", "Your practice session"));
  const repeatLine=CE("div","am-mini-row");
  const repeatCount=CE("b","", "0 repetitions");
  const repeatButton=btn("✓ I repeated this passage");
  append(repeatLine,repeatCount,repeatButton);
  history.appendChild(repeatLine);
  const repeatMessage=CE("div","am-note","Small, consistent repetition is more useful than rushing through verses.");
  history.appendChild(repeatMessage);
  journeyPanel.appendChild(history);
  const prayerRoom=attachPrayerRoom(component,D,{
    stage,main,tabs,tabBtns,CE,btn,append,
    onNavigate:(page)=>selectTab(page),
    getCurrentTab:()=>currentTab,
  });
  const journeyPlanner=attachHifdhJourney(component,D,{
    panel:journeyPanel,stage,CE,btn,append,tabBtns,
    navigate:(page)=>selectTab(page),
  });
  const footer=CE("footer","am-footer","");
  footer.appendChild(CE("strong","", "Al-Mu'allim"));
  footer.appendChild(document.createTextNode(" · Recitation tracking is practice guidance, not a certified Tajweed assessment."));
  app.appendChild(footer);

  let currentTab=["read","cover","room","listen","journey"].includes(D.resumeTab)
    ?D.resumeTab:(D.mode==="blind"?"cover":"read");
  let showHints=false,showTajweed=false;
  let acousticCursor=-1;
  let currentWord=-1,confirmedWord=-1; // A fresh live session must establish its own word evidence.
  // A locked position only establishes that individual word. Never reveal
  // all intervening Arabic words after a skip, seek or erroneous match.
  const confirmedIndices=new Set();
  const practiceReview=new Set();
  const reviewLocations=[];
  const reviewByAyah=new Map();
  function readFlags(key){
    const stored=JSON.parse(localStorage.getItem(key)||"[]");
    return new Set(Array.isArray(stored)?stored.filter(Number.isInteger):[]);
  }
  for(const [i,w] of words.entries()){
    const key="amuallim:flags:"+D.reviewProfile+":"+meta.s+":"+w.ayah;
    let group=reviewByAyah.get(key);
    if(!group){
      group={count:0,saved:new Set()};
      if(D.reviewProfile){try{group.saved=readFlags(key)}catch(_){}}
      reviewByAyah.set(key,group);
    }
    const position=++group.count;
    reviewLocations.push({key,position});
    if(group.saved.has(position))practiceReview.add(i);
  }
  function saveReviewFlag(i,flag){
    const location=reviewLocations[i];
    if(!location)return false;
    if(flag)practiceReview.add(i);else practiceReview.delete(i);
    wordNodes[i]?.classList.toggle("am-practice-flag",flag);
    if(!D.reviewProfile)return false;
    try{
      const saved=readFlags(location.key);
      if(flag)saved.add(location.position);else saved.delete(location.position);
      if(saved.size)localStorage.setItem(location.key,JSON.stringify([...saved]));
      else localStorage.removeItem(location.key);
      return true;
    }catch(_){return false}
  }
  let lastReviewIndex=-1;
  let revealIndex=-1;
  let selectedPracticeWord=-1;
  let revealTimer=null;

  let wordNodes=[];
  let live=false,starting=false,cleanupLive=null,recognition=null;
  let meterAnimation=0,micStream=null,micContext=null;
  let audioSegments=Array.isArray(D.segments)?D.segments:[];
  let currentAudioIdx=-1;
  let repeatAwareEnabled=!repeatControls.hidden;
  const smartAudioTracks=new Map();
  const smartAudioErrors=new Map();
  let audioAnalysisQueue=Promise.resolve();
  const audioAnalysisPending=new Map();
  let repetitions=0;
  const sessionKey="amuallim:practice:"+String(meta.s||0)+":"+String(meta.a||0)+":"+String(meta.end||0);
  try{repetitions=Math.max(0,Math.min(1000,Number(localStorage.getItem(sessionKey)||0)||0))}catch(_){}
  // Gentle, accessible live coaching: status remains visible for screen readers.
  // Gentle rescue controls: the user can reveal and hear the difficult
  // phrase without treating recognition uncertainty as a recitation error.
  const rescuePanel=CE("div","am-rescue-panel");
  rescuePanel.style.cssText="margin-top:12px;padding:12px;border:1px solid #c9d6c5;border-radius:14px;background:rgba(231,239,226,.6)";
  const rescueHeading=CE("div","am-note","✦ Stuck on a phrase? Practice it, then return to recitation.");
  const rescueControls=CE("div","am-control-row");
  const revealButton=btn("✦ Reveal phrase","am-button");
  const hearButton=btn("▶ Hear recitation","am-button");
  const correctButton=btn("Clear selected review flag","am-button");
  const flagButton=btn("⚑ Flag selected phrase","am-button");
  const roundButton=btn("↻ Review difficult words","am-button");
  const rescueText=CE("div","am-note","");
  rescueText.style.marginTop="8px";
  append(rescueControls,revealButton,hearButton,flagButton,correctButton,roundButton);
  append(rescuePanel,rescueHeading,rescueControls,rescueText);
  micPanel.appendChild(rescuePanel);
  function rescueTarget(){
    if(selectedPracticeWord>=0&&selectedPracticeWord<words.length)return selectedPracticeWord;
    if(currentWord>=0&&currentWord<words.length)return currentWord;
    return Math.min(words.length-1,Math.max(0,confirmedWord+1));
  }
  function rescuePhrase(index){
    const w=words[index];if(!w)return [];
    const first=Math.max(0,index-1),last=Math.min(words.length-1,index+2);
    return words.slice(first,last+1).filter(x=>x.ayah===w.ayah);
  }
  function showRescue(index){
    const phrase=rescuePhrase(index);
    if(!phrase.length)return;
    revealIndex=index;
    rescueText.replaceChildren();
    const ar=CE("div","am-detail-ar",phrase.map(w=>w.ar).join(" "));
    ar.dir="rtl";ar.style.cssText="font-size:1.55rem;line-height:2.3;margin:8px 0";
    rescueText.appendChild(ar);
    rescueText.appendChild(CE("div","", "Repeat this short phrase, then continue. A reveal is a learning aid, not a mistake."));
    clearTimeout(revealTimer);
    revealTimer=setTimeout(()=>{revealIndex=-1;rescueText.textContent="✦ Phrase hidden again. Try reciting from memory.";},16000);
  }
  const selectedLabel=CE("div","am-note","Tap any Qur'an word above to select the exact phrase you want to practise.");
  selectedLabel.style.margin="8px 0";
  rescuePanel.insertBefore(selectedLabel,rescueControls);
  function selectPracticeWord(i){
    if(i<0||i>=words.length)return;
    selectedPracticeWord=i;
    selectedLabel.textContent="Selected · Ayah "+words[i].ayah+", word "+reviewLocations[i].position+": "+words[i].ar;
    wordNodes.forEach((el,j)=>el.classList.toggle("am-practice-selected",j===i));
    rescueText.textContent="Choose Flag, Reveal or Hear for this selected phrase.";
  }
  const audioCues=new Map();
  const cuePanel=CE("div","am-audio-cues");
  const cueLabels=new Map([
    ["wrong_word","Possible word change"],["omitted_word","Possible missed word"],
    ["added_word","Possible extra word"],["skipped_passage","Possible skipped passage"]
  ]);
  rescuePanel.appendChild(cuePanel);
  function renderAudioCues(){
    cuePanel.replaceChildren();
    cuePanel.hidden=audioCues.size===0;
    if(cuePanel.hidden)return;
    cuePanel.appendChild(CE("div","am-note","From this recording · select a suggestion to review it."));
    for(const {index,label} of audioCues.values()){
      const control=btn(label+" · Ayah "+words[index].ayah+", word "+reviewLocations[index].position,"am-button");
      control.onclick=()=>selectPracticeWord(index);
      cuePanel.appendChild(control);
    }
  }
  function clearAudioCues(){
    audioCues.clear();
    renderAudioCues();
  }
  renderAudioCues();
  flagButton.onclick=()=>{
    const i=rescueTarget();
    if(i<0)return;
    selectedPracticeWord=i;
    const persisted=saveReviewFlag(i,true);
    selectedLabel.textContent="⚑ Flagged · Ayah "+words[i].ayah+", word "+reviewLocations[i].position;
    rescueText.textContent=persisted?"Saved on this device for difficult-phrase review.":"Flagged for this session.";
  };
  revealButton.onclick=()=>{const i=rescueTarget();practiceReview.add(i);showRescue(i)};
  hearButton.onclick=()=>{
    const i=rescueTarget(),w=words[i];if(!w)return;
    practiceReview.add(i);showRescue(i);
    const verseIndex=Math.max(0,Number(w.ayah)-Number(meta.a));
    const url=playlist[verseIndex]||playlist[0];
    if(!url){rescueText.appendChild(CE("div","am-note","No reciter audio available for this verse."));return}
    audio.pause();audio.src=url;playingIndex=verseIndex;
    audio.play().catch(()=>{rescueText.appendChild(CE("div","am-note","Tap the audio player to hear this ayah."))});
    rescueText.appendChild(CE("div","am-note","Playing the selected ayah; repeat the displayed phrase."));
  };
  correctButton.onclick=()=>{
    const i=rescueTarget();if(i<0)return;
    saveReviewFlag(i,false);
    wordNodes[i]?.classList.remove("am-review","am-uncertain","am-practice-flag");
    
    rescueText.textContent="Review flag cleared by you.";
  };
  roundButton.onclick=()=>{
    const indices=[...practiceReview].sort((a,b)=>a-b);
    if(!indices.length){rescueText.textContent="No difficult words saved yet. Reveal or flag a phrase to add it.";return}
    const first=indices.find(i=>i>lastReviewIndex)??indices[0];
    lastReviewIndex=selectedPracticeWord=first;
    selectPracticeWord(first);
    showRescue(first);
    rescueText.appendChild(CE("div","am-note","Review "+(indices.indexOf(first)+1)+" of "+indices.length+". Tap Review difficult words for the next phrase."));
    wordNodes[first]?.scrollIntoView({behavior:"instant",block:"nearest"});
  };
  const coaching=CE("div","am-live-coaching");
  coaching.setAttribute("role","status");
  coaching.setAttribute("aria-live","polite");
  coaching.hidden=true;
  micPanel.appendChild(coaching);
  let lastCoachingText="",lastCoachingAt=0;
  function coach(message,tone="neutral"){
    const now=Date.now();
    if(message===lastCoachingText&&now-lastCoachingAt<6500)return;
    lastCoachingText=message;lastCoachingAt=now;
    coaching.textContent=message;
    coaching.dataset.tone=tone;
    coaching.hidden=false;
  }
  function setStatus(message,state="idle"){
    if(status.dataset.state!==state)status.dataset.state=state;
    if(statusText.textContent!==message)statusText.textContent=message;
  }
  function normalized(text) {
    return String(text||"").normalize("NFKD")
      .replace(/[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]/g,"")
      .replace(/[ٱأإآ]/g,"ا").replace(/[ؤ]/g,"و")
      .replace(/[ئ]/g,"ي").replace(/[ى]/g,"ي")
      .replace(/[ة]/g,"ه")
      .replace(/[^\u0621-\u064A\s]/g,"").replace(/\s+/g," ").trim();
  }
  const expected=words.map(w=>normalized(w.ar));
  function distance(a,b) {
    if(a===b)return 0;
    if(Math.abs(a.length-b.length)>1)return 2;
    let row=Array.from({length:b.length+1},(_,i)=>i);
    for(let i=1;i<=a.length;i++){
      let previous=row[0];row[0]=i;
      for(let j=1;j<=b.length;j++){
        const old=row[j];
        row[j]=Math.min(row[j]+1,row[j-1]+1,previous+(a[i-1]===b[j-1]?0:1));
        previous=old;
      }
    }
    return row[b.length];
  }
  // Only a complete run of exact Arabic word tokens verifies a phrase.
  // Position predictions and interim ASR may be displayed, never confirmed.
  const PHRASE_WORDS=4;
  function phraseEnd(start){
    if(start>=words.length)return words.length;
    const ayah=words[start].ayah;
    let end=start;
    while(end<words.length&&end-start<PHRASE_WORDS&&words[end].ayah===ayah)end++;
    return end;
  }
  function phraseMatches(tokens,start){
    const count=phraseEnd(start)-start;
    return count>0&&tokens.length>=count&&
      tokens.slice(0,count).every((token,i)=>token===expected[start+i]);
  }
  // Accept a new starting position only when four consecutive final tokens
  // identify exactly one location within an ayah of the selected passage.
  function uniquePhrase(tokens){
    if(tokens.length<PHRASE_WORDS)return -1;
    let found=-1;
    for(let i=0;i+PHRASE_WORDS<=words.length;i++){
      if(phraseEnd(i)-i!==PHRASE_WORDS||!phraseMatches(tokens,i))continue;
      if(found>=0)return -1;
      found=i;
    }
    return found;
  }
  function matchFinalTokens(pending,cursor){
    let matched=false;
    while(pending.length){
      let start=cursor;
      if(!phraseMatches(pending,start)){
        start=uniquePhrase(pending);
        if(start<0){
          if(pending.length<PHRASE_WORDS)break;
          pending.shift();
          continue;
        }
      }
      const end=phraseEnd(start);
      for(let i=start;i<end;i++)markMatched(i);
      pending.splice(0,end-start);
      cursor=end;
      matched=true;
    }
    if(matched){
      updateMatchCount();
      wordNodes[cursor-1]?.scrollIntoView({behavior:"instant",block:"nearest",inline:"nearest"});
      coach("Phrase matched in the Arabic transcript. Keep going.","success");
    }
    return {cursor,matched};
  }
  function updateMatchCount(){
    if(engineSelect.value==="vowels"){
      liveCountLabel.textContent="Short-vowel review";
      liveCount.textContent="Ungraded";
      progressFill.style.width="0%";
      return;
    }
    if(engineSelect.value==="local"){
      liveCountLabel.textContent="Current listening position";
      liveCount.textContent=acousticCursor<0?"Waiting for recitation":String(words[acousticCursor].ayah)+", word "+reviewLocations[acousticCursor].position;
      progressFill.style.width="0%";
      return;
    }
    liveCountLabel.textContent="Words matched in transcript";
    liveCount.textContent=confirmedIndices.size+" / "+words.length;
    progressFill.style.width=Math.round(100*confirmedIndices.size/Math.max(1,words.length))+"%";
  }
  function markMatched(index){
    wordNodes[currentWord]?.classList.remove("am-active");
    currentWord=confirmedWord=index;
    confirmedIndices.add(index);
    const el=wordNodes[index];
    if(!el)return;
    el.classList.remove("am-review","am-uncertain","am-ayah-playing");
    el.classList.add("am-confirmed");
    if(currentTab==="cover"&&!el.querySelector(".am-revealed-ar")){
      el.appendChild(CE("span","am-revealed-ar",words[index].ar||""));
    }
  }
  const digits="٠١٢٣٤٥٦٧٨٩";
  function arabicDigits(n){return String(n).replace(/[0-9]/g,d=>digits[Number(d)])}
  function wordMarks(w) {
    const out=[];
    const graphemes=Array.isArray(w.letters)?w.letters:[];
    graphemes.forEach(g=> (g.marks||[]).forEach(mark=>out.push([mark,g.text])));
    return out;
  }
  function classification(w){
    const all=wordMarks(w).map(x=>x[0]);
    if(all.some(s=>/Maddah|Superscript alif/.test(s)))return "am-madd";
    if(all.some(s=>/Shaddah/.test(s)))return "am-shaddah";
    if(all.some(s=>/Sukoon/.test(s)))return "am-sukun";
    return "";
  }
  function openWord(index){
    const w=words[index];if(!w)return;
    detail.replaceChildren();
    detail.appendChild(CE("h3","", "Word study · Ayah "+w.ayah));
    detail.appendChild(CE("div","am-detail-ar",w.ar));
    if(w.tr)detail.appendChild(CE("div","am-detail-meta",w.tr));
    if(w.en)detail.appendChild(CE("div","am-detail-meta",w.en));
    const marks=wordMarks(w);
    if(marks.length){
      const marksRow=CE("div","");
      marks.forEach(([mark,letter])=>{
        marksRow.appendChild(CE("span","am-detail-mark",letter+" · "+mark));
      });
      detail.appendChild(marksRow);
    }
    const actions=CE("div","am-control-row");
    const hear=btn("♫ Play this ayah");
    hear.onclick=()=>{
      const idx=Number(w.ayah)-Number(meta.a);
      if(idx<0||idx>=playlist.length)return;
      playingIndex=idx;currentAudioIdx=-1;audio.src=playlist[idx];
      showPlaybackPosition();
      audio.play().catch(()=>setStatus("Audio playback did not start. Use the player controls.","error"));
    };
    const close=btn("Close");close.onclick=()=>{detail.hidden=true};
    append(actions,hear,close);detail.appendChild(actions);
    detail.hidden=false;
    detail.scrollIntoView({behavior:"smooth",block:"nearest"});
  }
  function renderWords(){
    textArea.replaceChildren();wordNodes=[];
    const cover=currentTab==="cover",showArabic=currentTab!=="cover";
    textArea.className=cover?"am-mushaf am-cover":"am-mushaf";
    textArea.dir=cover?"ltr":"rtl";
    textArea.setAttribute("lang",cover?language:"ar");
    textArea.setAttribute("aria-label",cover?"English clues for memorising the selected verses":"Arabic Qur'an passage");
    if(currentTab==="journey")return;
    words.forEach((w,i)=>{
      const el=CE("span","am-word"+(showTajweed&&showArabic?" "+classification(w):""));
      el.tabIndex=0;el.setAttribute("role","button");
      if(cover){
        el.appendChild(CE("span","am-covered",w.en||"Meaning unavailable"));
        if(showHints){
          if(w.tr)el.appendChild(CE("span","am-sub-hint",w.tr));
          const names=[...new Set(wordMarks(w).map(x=>x[0]))];
          if(names.length)el.appendChild(CE("span","am-marks",names.join(" · ")));
        }
        el.setAttribute("aria-label","English clue "+(i+1)+". Tap for pronunciation hints.");
      } else {
        el.textContent=w.ar||"";
        el.setAttribute("aria-label","Study Arabic word "+(w.tr||String(i+1)));
      }
      const view=()=>{selectPracticeWord(i);if(cover)showIndividualHint(i);else openWord(i)};
      el.addEventListener("click",view);
      el.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();view()}});
      // Only the single actively followed word is visually highlighted.
      // Completed words can reveal Arabic in Cover, but are not all gold.
      if(i===acousticCursor&&live)el.classList.add("am-acoustic-cursor");
      else if(i===currentWord&&live&&engineSelect.value!=="local")el.classList.add("am-active");
      if(confirmedIndices.has(i))el.classList.add("am-confirmed");
      if(practiceReview.has(i))el.classList.add("am-practice-flag");
      if(selectedPracticeWord===i)el.classList.add("am-practice-selected");
      if(cover && confirmedIndices.has(i)){
        el.appendChild(CE("span","am-revealed-ar",w.ar||""));
      }
      textArea.appendChild(el);
      wordNodes.push(el);
      if(i===words.length-1 || Number(words[i+1].ayah)!==Number(w.ayah)){
        if(!cover)textArea.appendChild(CE("span","am-ayah-end","۝"+arabicDigits(w.ayah)));
      }else{
        textArea.appendChild(document.createTextNode(" "));
      }
    });
    toggleHint.textContent=showHints?"✧ Hide hints":"✧ Show hints";
    toggleHint.classList.toggle("am-on",showHints);
    toggleColour.classList.toggle("am-on",showTajweed);
    toggleColour.hidden=cover;
    detail.hidden=true;
    basmalah.hidden=cover||Number(meta.a)!==1||Number(meta.s)===9;
  }
  function showIndividualHint(index){
    const el=wordNodes[index],w=words[index];if(!el||!w)return;
    // Hint only reveals pronunciation, not Arabic, during the cover test.
    let block=el.querySelector(".am-extra");
    if(block){block.remove();return}
    block=CE("span","am-extra");
    if(w.tr)block.appendChild(CE("span","am-sub-hint",w.tr));
    const names=[...new Set(wordMarks(w).map(x=>x[0]))];
    if(names.length)block.appendChild(CE("span","am-marks",names.join(" · ")));
    if(!block.childNodes.length)block.appendChild(CE("span","am-marks","No pronunciation hints available"));
    el.appendChild(block);
  }
  function selectTab(tab){
    if(live && (tab==="journey"||tab==="listen"||tab==="room"))void stopLive();
    if(tab==="room" && !audio.paused)audio.pause();
    currentTab=tab;showHints=false;detail.hidden=true;
    Object.entries(tabBtns).forEach(([id,b])=>b.setAttribute("aria-selected",String(id===tab)));
    const journey=tab==="journey",room=tab==="room";
    prayerRoom.setVisible(room);
    prayerRoom.setPracticeMode(tab);
    journeyPlanner.setVisible(journey);
    layout.hidden=journey||room;
    journeyPanel.hidden=!journey;
    hero.hidden=journey||room;
    if(journey||room){return}
    // Switching between Read, Memorise and Listen resets stale playback
    // highlights. Only an actively playing reciter or mic can mark a word.
    lastPlaybackUiKey="";
    if(!live)currentWord=-1;
    sectionHeading.textContent=tab==="cover"?"Memorise with meaning":tab==="listen"?"Listen and follow":"The Noble Qur'an";
    micPanel.hidden=tab==="listen";
    toggleHint.hidden=tab==="listen";
    toggleColour.hidden=tab==="cover";
    resetBtn.hidden=tab==="listen";
    recordHint.hidden=tab==="listen";
    audioPanel.hidden=tab==="cover";
    readerPanel.style.borderColor=tab==="cover"?"#d9aa5960":"";
    renderWords();
    if(tab==="listen"){
      audio.scrollIntoView({behavior:"smooth",block:"nearest"});
    }
  }
  toggleHint.onclick=()=>{showHints=!showHints;renderWords()};
  toggleColour.onclick=()=>{showTajweed=!showTajweed;renderWords()};
  resetBtn.onclick=async()=>{if(live)await stopLive();clearAudioCues();clearVowelReview();currentWord=-1;confirmedWord=-1;confirmedIndices.clear();updateMatchCount();lastPlaybackUiKey="";progressFill.style.width="0%";setStatus("Ready to practise from the beginning.");transcript.textContent="";renderWords()};
  recordHint.onclick=()=>{
    micPanel.scrollIntoView({behavior:"smooth",block:"center"});
    // Start capture from the original tap, preserving the iPad user gesture.
    if(!live)void micButton.onclick();
    else micButton.focus();
  };
  repeatCount.textContent=String(repetitions)+" repetitions";
  repeatButton.onclick=()=>{
    repetitions++;repeatCount.textContent=String(repetitions)+" repetitions";
    repeatMessage.textContent="Alhamdulillah · "+String(repetitions)+" repetitions in this passage.";
    try{localStorage.setItem(sessionKey,String(repetitions))}catch(_){}
  };
  // The audio files are the source-matched EveryAyah recordings. Word times
  // originate from QuranLife's automatically generated alignments for each
  // *same* reciter and audio file. Never invent word positions by text length.
  let playbackFrame=null;
  let playbackTimingWarning="";
  let lastPlaybackUiKey="";
  // Analyse the *actual MP3 samples* using the Quran-specific speech model.
  // A 1-time mapping from recording milliseconds to observed Quran words can
  // contain 4,5,6,4,5 when the sheikh repeats a phrase. Static word timings
  // cannot represent this because each expected word appears only once.
  async function buildAudioAwareTrack(verseIndex){
    const encoded=inlineAudio[verseIndex];
    const ayah=Number(meta.a)+verseIndex;
    if(typeof encoded!=="string"||encoded.length<512){
      const reason="This reciter clip could not be downloaded within the size limit; following the published word timings instead.";
      smartAudioErrors.set(verseIndex,reason);
      repeatHelp.textContent=reason;
      return;
    }
    if(live){
      repeatHelp.textContent="Stop live recitation before analysing the sheikh recording; the microphone has priority.";
      return;
    }  // microphone should have priority on limited iPad CPU
    let ctx=null,session=null;
    try{
      repeatHelp.textContent="Preparing Quran-aware listening for "+meta.s+":"+ayah+
        " · reciter playback still uses verified-source timings.";
      const engine=await ensureQuranEngine("reciter");
      if(live)return;
      const AudioContextClass=window.AudioContext||window.webkitAudioContext;
      if(!AudioContextClass)throw Error("This browser cannot decode recitation for analysis.");
      ctx=new AudioContextClass();
      const bytes=Uint8Array.from(atob(encoded),ch=>ch.charCodeAt(0));
      const buffer=await ctx.decodeAudioData(bytes.buffer.slice(0));
      const duration=buffer.duration;
      if(!Number.isFinite(duration)||duration>120||duration<0.4)
        throw Error("The clip exceeds the analysis duration limit.");
      const left=buffer.getChannelData(0);
      let mono=left;
      if(buffer.numberOfChannels>1){
        const right=buffer.getChannelData(1);
        mono=new Float32Array(left.length);
        for(let i=0;i<left.length;i++)mono[i]=(left[i]+right[i])*0.5;
      }
      const sourceRate=buffer.sampleRate;
      session=engine.startFreeRecitation({minConfidence:0.60});
      const locations=[];
      const countForAyah=words.reduce((sum,w)=>sum+(Number(w.ayah)===ayah?1:0),0);
      let base=words.findIndex(w=>Number(w.ayah)===ayah);
      const validLocation=location=>{
        if(Number(location?.surah)!==Number(meta.s)||Number(location?.ayah)!==ayah)return -1;
        const wi=Number(location?.word);
        return Number.isInteger(wi)&&wi>=1&&wi<=countForAyah?base+wi-1:-1;
      };
      session.subscribe(event=>{
        if(event?.type!=="position"||event.state!=="locked")return;
        const possible=(Array.isArray(event.observed)?event.observed:[])
          .filter(candidate=>validLocation(candidate.word)>=0);
        if(!possible.length)return;
        const candidate=possible[0];
        const word=validLocation(candidate.word);
        const confidence=Number(candidate.confidence);
        if(Number.isFinite(confidence)&&confidence<0.48)return;
        const timeMs=Number(event.timeMs);
        if(!Number.isFinite(timeMs)||timeMs<0||timeMs>duration*1000+800)return;
        const previous=locations[locations.length-1];
        if(previous?.word===word && timeMs-previous.timeMs<800)return;
        const repeated=Boolean(previous&&word<previous.word);
        locations.push({word,timeMs:Math.round(timeMs),repeat:repeated});
      });
      const chunkSamples=Math.max(2048,Math.floor(sourceRate*.32));
      for(let start=0;start<mono.length;start+=chunkSamples){
        if(engineAbort.signal.aborted||live||!repeatAwareEnabled)return;
        const part=mono.subarray(start,Math.min(start+chunkSamples,mono.length));
        await session.pushAudio(part,sourceRate);
        if((Math.floor(start/chunkSamples)%12)===0){
          repeatHelp.textContent="Analysing "+meta.s+":"+ayah+" for repeated words · "+
            Math.round(start/mono.length*100)+"% · normal playback remains available";
          await new Promise(resolve=>setTimeout(resolve,0));
        }
      }
      await session.end();
      if(!locations.length){
        throw Error("The recogniser did not locate enough Quran words to build an audio-aware timeline.");
      }
      locations.sort((a,b)=>a.timeMs-b.timeMs);
      const backwardCount=locations.filter(x=>x.repeat).length;
      const distinct=new Set(locations.map(x=>x.word)).size;
      if(distinct<2)throw Error("Too few distinct words were recognised.");
      smartAudioTracks.set(verseIndex,locations);
      repeatHelp.textContent=backwardCount
        ? "Repeat-aware alignment ready for "+meta.s+":"+ayah+
          " · "+backwardCount+" backwards phrase movement(s) detected"
        : "Quran model did not confirm a repeat in "+meta.s+":"+ayah+
          " · source-matched word timing stays active";
      showPlaybackPosition();
    }catch(e){
      const message=String(e?.message||e).slice(0,190);
      smartAudioErrors.set(verseIndex,message);
      repeatHelp.textContent="Repeat-aware analysis unavailable ("+message+
        "). Existing reciter playback remains available.";
    }finally{
      try{session?.dispose()}catch(_){}
      try{await ctx?.close()}catch(_){}
    }
  }
  function requestAudioAwareFollowing(verseIndex){
    if(!repeatAwareEnabled||live||smartAudioTracks.has(verseIndex)||
       smartAudioErrors.has(verseIndex))return Promise.resolve();
    if(audioAnalysisPending.has(verseIndex))return audioAnalysisPending.get(verseIndex);
    const job=audioAnalysisQueue.then(()=>buildAudioAwareTrack(verseIndex));
    audioAnalysisPending.set(verseIndex,job);
    audioAnalysisQueue=job.catch(()=>{});
    job.finally(()=>{audioAnalysisPending.delete(verseIndex)}).catch(()=>{});
    return job;
  }
  analyseRepeatBtn.onclick=async()=>{
    if(audioAnalysisPending.has(playingIndex))return;
    const idx=playingIndex;
    // A user-triggered retry should be possible after a temporary network
    // or model download error; never trap the interface in a failed state.
    smartAudioErrors.delete(idx);
    analyseRepeatBtn.disabled=true;
    analyseRepeatBtn.textContent="Analysing "+meta.s+":"+(Number(meta.a)+idx)+"...";
    try{await requestAudioAwareFollowing(idx)}
    finally{
      analyseRepeatBtn.disabled=false;
      analyseRepeatBtn.textContent=smartAudioTracks.has(idx)
        ?"✓ Audio analysis ready":"✧ Analyse repeats";
    }
  };
  repeatBtn.onclick=()=>{
    repeatAwareEnabled=!repeatAwareEnabled;
    repeatBtn.classList.toggle("am-on",repeatAwareEnabled);
    repeatBtn.setAttribute("aria-pressed",String(repeatAwareEnabled));
    repeatBtn.textContent=repeatAwareEnabled?"⟲ Follow repeated phrases":"⟲ Repeat-following off";
    analyseRepeatBtn.hidden=!repeatAwareEnabled;
    showPlaybackPosition();
    if(repeatAwareEnabled && !audio.paused)void requestAudioAwareFollowing(playingIndex);
  };
  const audioTimings=new Map();
  for(const seg of audioSegments){
    const ayah=Number(seg.ayah),word=Number(seg.word_idx);
    const start=Number(seg.start),end=Number(seg.end);
    if(!Number.isInteger(ayah)||!Number.isInteger(word)||!Number.isFinite(start)||
       !Number.isFinite(end)||start<0||end<=start||word<0||word>=words.length)continue;
    const list=audioTimings.get(ayah)||[];
    list.push({word,start,end});
    audioTimings.set(ayah,list);
  }
  for(const list of audioTimings.values())list.sort((a,b)=>a.start-b.start);
  const selectCurrentAyah=()=>Number(meta.a)+playingIndex;
  function timingForCurrentRecording(){
    const ayah=selectCurrentAyah();
    const segments=audioTimings.get(ayah)||[];
    const expected=words.filter(w=>Number(w.ayah)===ayah).length;
    if(!segments.length || segments.length!==expected){
      return {segments:null,reason:"No source-matched word timing for this ayah"};
    }
    if(!Number.isFinite(audio.duration)||audio.duration<=0){
      return {segments:null,reason:"Waiting for audio metadata"};
    }
    const lastEnd=segments[segments.length-1].end;
    // The last aligned word often ends well before the MP3 does: a reciter
    // may leave a long trailing pause. Reject only impossible timings extending
    // materially past the recording, not legitimate trailing silence.
    if(lastEnd/1000>audio.duration+0.75){
      return {segments:null,reason:"Word timing extends beyond this audio recording"};
    }
    return {segments,reason:"Source-matched automated word timing (approximate)"};
  }
  function showPlaybackPosition(){
    if(live)return;
    const ayah=selectCurrentAyah();
    const {segments,reason}=timingForCurrentRecording();
    const smart=repeatAwareEnabled?smartAudioTracks.get(playingIndex):null;
    let index=-1;
    let playbackReason=reason;
    const smartHasRepeat=Boolean(smart?.some(item=>item.repeat));
    if(smart?.length && (smartHasRepeat || !segments)){
      const now=Math.max(0,Number(audio.currentTime)||0)*1000;
      // Preserve deliberate backward movements when the sheikh repeats words.
      let lo=0,hi=smart.length;
      while(lo<hi){const m=(lo+hi)>>1;if(smart[m].timeMs<=now)lo=m+1;else hi=m}
      const event=smart[Math.max(0,lo-1)];
      if(event?.timeMs<=now){
        index=event.word;
        playbackReason=event.repeat
          ?"Repeated phrase recognised · following the earlier word"
          :"Audio-aware Qur'an word following";
      }
    }
    if(index<0 && segments){
      const now=Math.max(0,Number(audio.currentTime)||0)*1000;
      // Keep a word highlighted during pauses *only inside the same ayah*.
      for(let i=0;i<segments.length;i++){
        if(now>=segments[i].start && now<segments[i].end){index=segments[i].word;break;}
      }
    }
    // Do not pretend alignment is precise when source-matched timings are absent.\n    // Avoid repainting every Arabic word 60 times per second on iPad.
    const displayKey=ayah+":"+index+":"+(smartHasRepeat?"repeat":"timed")+
      ":"+Boolean(segments);
    if(displayKey+":"+((currentTab==="read"||currentTab==="listen"||currentTab==="cover")&&!audio.paused)===lastPlaybackUiKey
       && playbackTimingWarning===playbackReason)return;
    lastPlaybackUiKey=displayKey+":"+((currentTab==="read"||currentTab==="listen")&&!audio.paused);
    // Critical: never colour an entire ayah as though every word is active.
    // Only show audio-following while playback is actually active in Listen.
    // Reader/Memorise words must not change merely because metadata loaded.
    const followAudio=(currentTab==="read"||currentTab==="listen"||currentTab==="cover")
      &&!audio.paused&&!audio.ended;
    wordNodes.forEach((el,i)=>{
      el.classList.toggle("am-active",followAudio&&index>=0&&i===index);
      el.classList.remove("am-ayah-playing","am-confirmed");
    });
    if(index!==currentAudioIdx && followAudio){
      currentAudioIdx=index;
      if(index>=0)wordNodes[index]?.scrollIntoView({
        behavior:"auto",block:"nearest",inline:"nearest"
      });
    }
    playCaption.textContent="Playing "+String(D.reciter||"reciter")+" · "+
      meta.s+":"+ayah+" · "+playbackReason;
    playbackTimingWarning=playbackReason;
  }
  function stopPlaybackFollow(){
    if(playbackFrame!==null){cancelAnimationFrame(playbackFrame);playbackFrame=null}
  }
  let lastPlaybackPaint=0;
  function playbackFollowFrame(timestamp){
    playbackFrame=null;
    // 15 Hz is enough for word-following; 60 Hz needlessly forces DOM work.
    if(timestamp-lastPlaybackPaint>=65){
      lastPlaybackPaint=timestamp;
      if(!document.hidden)showPlaybackPosition();
    }
    if(!audio.paused&&!audio.ended&&!live){
      playbackFrame=requestAnimationFrame(playbackFollowFrame);
    }
  }
  function startPlaybackFollow(){
    stopPlaybackFollow();
    if(!live){
      playbackFrame=requestAnimationFrame(playbackFollowFrame);
      if(repeatAwareEnabled)void requestAudioAwareFollowing(playingIndex);
    }
  }
  audio.onloadedmetadata=showPlaybackPosition;
  audio.onseeked=showPlaybackPosition;
  audio.ontimeupdate=showPlaybackPosition;
  audio.onplay=async()=>{
    stopVowelPlayback();
    if(live)await stopLive();
    if(!audio.paused)startPlaybackFollow();
  };
  audio.onpause=()=>{
    stopPlaybackFollow();
    if(currentTab==="listen"||currentTab==="read"||currentTab==="cover"){
      wordNodes.forEach(el=>el.classList.remove("am-active","am-ayah-playing"));
      lastPlaybackUiKey="";
    }
  };
  audio.onended=()=>{
    stopPlaybackFollow();
    playingIndex++;
    currentAudioIdx=-1;
    lastPlaybackUiKey="";
    if(playingIndex<playlist.length){
      audio.src=playlist[playingIndex];
      analyseRepeatBtn.textContent=smartAudioTracks.has(playingIndex)
        ?"✓ Audio analysis ready":"✧ Analyse repeats";
      if(repeatAwareEnabled)void requestAudioAwareFollowing(playingIndex);
      audio.play().catch(()=>{playCaption.textContent="Tap Play to continue to the next ayah."});
    }else{
      playingIndex=0;
      playCaption.textContent="Reciter passage finished.";
      wordNodes.forEach(el=>{
        el.classList.remove("am-active");
        el.classList.remove("am-ayah-playing");
      });
      if(playlist.length)audio.src=playlist[0];
    }
  };
  function updateMeter(analyser,stopAt) {
    const buffer=new Uint8Array(analyser.fftSize);
    const measure=()=>{
      if(!stopAt())return;
      analyser.getByteTimeDomainData(buffer);
      let power=0;
      for(let i=0;i<buffer.length;i++){
        const x=(buffer[i]-128)/128;power+=x*x;
      }
      const rms=Math.sqrt(power/buffer.length);
      meterFill.style.width=Math.min(100,Math.floor(rms*800))+"%";
      meterAnimation=requestAnimationFrame(measure);
    };
    measure();
  }
  let watchdog=null,restartHandle=null;
  function clearTimers(){
    if(watchdog!==null)clearTimeout(watchdog);
    if(restartHandle!==null)clearTimeout(restartHandle);
    watchdog=restartHandle=null;
  }
  async function stopLive(){
    live=false;starting=false;micButton.disabled=true;clearTimers();
    try{if(cleanupLive)await cleanupLive()}catch(_){}
    cleanupLive=null;
    micButton.disabled=false;
    micButton.textContent="🎙 Start listening";
    micButton.classList.remove("am-danger");
    micButton.classList.add("am-primary");
    wordNodes[acousticCursor]?.classList.remove("am-acoustic-cursor");
    acousticCursor=-1;
    updateMatchCount();
    wordNodes.forEach(el=>el.classList.remove("am-active"));
    engineSelect.disabled=false;
    setStatus("Listening stopped.");
    coaching.hidden=true;
  }
  async function browserLive(){
    const BrowserSpeech=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!BrowserSpeech)throw new Error("This browser does not support Arabic speech recognition. Use the recorded audio review below instead.");
    const apple=/iPad|iPhone|iPod/.test(navigator.userAgent)||
      (navigator.platform==="MacIntel"&&navigator.maxTouchPoints>1);
    const r=new BrowserSpeech();
    r.lang="ar-SA";r.continuous=!apple;r.interimResults=true;r.maxAlternatives=1;
    let closed=false,received=false,started=0,cursor=Math.max(0,confirmedWord+1);
    let phraseBuffer=[];
    function armWatchdog(){
      if(watchdog!==null)clearTimeout(watchdog);
      watchdog=setTimeout(()=>{
        if(!closed&&!received){
          setStatus("Safari returned no speech results. Select Cloud Live or use recorded review.","error");
          transcript.textContent="No words recognised. This is a browser limitation, not evidence of a recitation mistake.";
        }
      },11500);
    }
    r.onstart=()=>{
      started++;setStatus("Microphone connected · waiting for Arabic speech...","active");armWatchdog();
    };
    r.onspeechstart=()=>setStatus("Speech detected · matching Qur'an words...","active");
    r.onresult=e=>{
      if(closed||!live||!audio.paused)return;
      received=true;
      if(watchdog!==null){clearTimeout(watchdog);watchdog=null}
      let final="",interim="";
      for(let i=e.resultIndex;i<e.results.length;i++){
        const item=e.results[i],v=item?.[0]?.transcript||"";
        if(item.isFinal)final+=" "+v;else interim+=" "+v;
      }
      let idx=-1;
      if(final.trim()){
        phraseBuffer.push(...normalized(final).split(" ").filter(Boolean));
        const result=matchFinalTokens(phraseBuffer,cursor);
        cursor=result.cursor;
        if(result.matched)idx=cursor-1;
      }
      if(interim.trim()){
        setStatus("Listening · full phrase awaiting verification","active");
      }
      const heard=(final+" "+interim).trim();
      if(heard)transcript.textContent="Recognised Arabic (approximate): "+heard.slice(0,180);
      setStatus(idx>=0?"Following your recitation · "+Math.round(100*confirmedIndices.size/Math.max(1,words.length))+"% of passage":
        "Arabic heard, but no match yet. Check the selected ayahs.","active");
    };
    r.onerror=e=>{
      const err=e.error||"unknown";
      if(closed)return;
      setStatus(err==="no-speech"?"No clear speech heard. Try a short ayah.":
        "Speech recognition error: "+err+". Try Cloud Live or recorded review.", "error");
      if(err==="service-not-allowed"){
        closed=true;
        setStatus("Safari blocked its speech-recognition service. Your microphone works; choose Cloud Live (requires a configured Gemini API key).","error");
        micMessage.textContent="Safari service-not-allowed is not a Tajweed error. Select Cloud Live or use the recorded-audio review.";

      } else if(["not-allowed","audio-capture","language-not-supported"].includes(err)){
        closed=true;
      }
    };
    r.onend=()=>{
      clearTimers();
      if(closed){
        // Keep the actual Safari error visible instead of overwriting it
        // with the generic "Listening stopped" message.
        live=false;starting=false;engineSelect.disabled=false;clearTimers();
        cleanupLive=null;
        micButton.disabled=false;
        micButton.textContent="🎙 Restart listener";
        micButton.classList.remove("am-danger");
        micButton.classList.add("am-primary");
        return;
      }
      if(started>=4&&!received){
        closed=true;
        setStatus("Safari ended recognition repeatedly without returning words. Use recorded review.","error");
        void stopLive();return;
      }
      restartHandle=setTimeout(()=>{
        if(closed||!live)return;
        try{r.start()}catch(e){setStatus("Could not restart speech recognition: "+String(e.message),"error");closed=true;void stopLive()}
      },520);
    };
    r.start();
    cleanupLive=async()=>{
      closed=true;clearTimers();
      try{r.abort()}catch(_){}
      r.onstart=r.onresult=r.onerror=r.onend=null;
    };
  }

  // Gemini Live transcription. Unlike WebKit SpeechRecognition this captures
  // real microphone samples and streams 16 kHz PCM to a dedicated STT model.
  // Permanent API keys never reach this component. A token lasts one session.
  const cloudSession=D.cloudSession||null;
  function tokenConsumed(){
    if(!cloudSession?.id)return true;
    try{return sessionStorage.getItem("amuallim:used-live:"+cloudSession.id)==="yes"}catch(_){return false}
  }
  async function requestCloudToken(){
    if(!D.cloudAvailable)throw Error("GEMINI_API_KEY is not configured in Streamlit secrets.");
    if(typeof component.setTriggerValue!=="function")throw Error("Streamlit live connection bridge is unavailable.");
    // Ask the device for microphone access while handling the actual button click.
    // This is necessary on iPads where permission may require a direct gesture.
    if(!navigator.mediaDevices?.getUserMedia)throw Error("Microphone capture is unavailable. Open the app via HTTPS in Safari.");
    setStatus("Requesting microphone permission...","active");
    const testStream=await navigator.mediaDevices.getUserMedia({audio:true});
    testStream.getTracks().forEach(t=>t.stop());
    const id=String(Date.now())+"-"+Math.random().toString(36).slice(2,8);
    micButton.textContent="Connecting securely...";
    setStatus("Requesting a one-session cloud transcription token...","active");
    try{sessionStorage.setItem("amuallim:pendingCloudRequest",id)}catch(_){}
    component.setTriggerValue("request_cloud",{
      id, tab:currentTab==="cover"?"cover":"read",
      cursor:confirmedWord
    });
  }
  function floatToPcm16Base64(input,originalRate){
    // Resample mono floats to 16,000 Hz using linear interpolation.
    // AudioContext sampleRate commonly differs from 16 kHz on iPad.
    const ratio=originalRate/16000;
    const outLen=Math.max(1,Math.floor(input.length/ratio));
    const bytes=new Uint8Array(outLen*2);
    for(let i=0;i<outLen;i++){
      const position=i*ratio;
      const a=Math.min(input.length-1,Math.floor(position));
      const b=Math.min(input.length-1,a+1);
      const f=position-a;
      const sample=Math.max(-1,Math.min(1,input[a]*(1-f)+input[b]*f));
      const value=sample<0?Math.round(sample*32768):Math.round(sample*32767);
      bytes[i*2]=value&255;
      bytes[i*2+1]=(value>>8)&255;
    }
    let binary="";
    for(let i=0;i<bytes.length;i++)binary+=String.fromCharCode(bytes[i]);
    return btoa(binary);
  }
  async function cloudLive(){
    if(!cloudSession?.token || tokenConsumed()){
      throw Error("The session token is missing or already used. Press Start to request a new one.");
    }
    if(!navigator.mediaDevices?.getUserMedia){
      throw Error("Microphone capture is unavailable on this browser.");
    }
    const token=cloudSession.token;
    try{sessionStorage.setItem("amuallim:used-live:"+cloudSession.id,"yes")}catch(_){}
    let socket=null,stream=null,audioContext=null,source=null,processor=null,mute=null;
    let closed=false,gotTranscript=false,maxRms=0;
    let cursor=Math.max(0,confirmedWord+1);
    let cloudAccum=[];
    let lastCloudFinal=[];
    let watchdogId=null;
    let cancelSetup=null;
    const cleanup=async()=>{
      closed=true;
      cancelSetup?.();
      if(watchdogId!==null)clearTimeout(watchdogId);
      try{if(socket?.readyState===WebSocket.OPEN)socket.send(JSON.stringify({realtimeInput:{audioStreamEnd:true}}))}catch(_){}
      try{processor && (processor.onaudioprocess=null)}catch(_){}
      try{source?.disconnect()}catch(_){}
      try{processor?.disconnect()}catch(_){}
      try{mute?.disconnect()}catch(_){}
      try{stream?.getTracks().forEach(t=>t.stop())}catch(_){}
      try{await audioContext?.close()}catch(_){}
      try{socket?.close(1000,"User stopped recording")}catch(_){}
      meterFill.style.width="0%";
    };
    cleanupLive=cleanup;
    const parseSpeech=(spoken,final)=>{
      const phrase=String(spoken||"").trim();
      if(closed||!live||!audio.paused||!phrase)return;
      // Arabic script check: Gemini may occasionally hallucinate a Hindi,
      // Japanese or other-language transcript despite Arabic recitation.
      const arabicLetters=(phrase.match(/[\u0621-\u064A]/g)||[]).length;
      const scriptLetters=(phrase.match(/[^\s\d\p{P}\p{S}]/gu)||[]).length;
      if(scriptLetters>0 && arabicLetters/Math.max(1,scriptLetters)<0.55){
        transcript.textContent="Incorrect transcription language: "+phrase.slice(0,160);
        setStatus("Cloud returned non-Arabic text. Waiting for Arabic Qur'an recognition; no words marked.","error");
        return;
      }
      gotTranscript=true;
      if(watchdogId!==null){clearTimeout(watchdogId);watchdogId=null}
      transcript.textContent=(final?"Recognised: ":"Listening: ")+phrase.slice(0,230);
      // Cloud responses often contain a full phrase. Never confirm only its
      // final word: process each consecutive word and preserve intermediate
      // progress. Partial transcripts may overlap previously heard words.
      const tokens=normalized(phrase).split(" ").filter(Boolean);
      if(!final){
        setStatus("Cloud listening · waiting to verify full phrase","active");
        return;
      }
      // Some transcription services resend their cumulative final words.
      // Strip *only* exact, already-received overlaps before buffering the
      // next phrase; repeated identical events must not manufacture progress.
      let overlap=0;
      const max=Math.min(lastCloudFinal.length,tokens.length);
      for(let n=max;n>0;n--){
        if(lastCloudFinal.slice(-n).every((token,i)=>token===tokens[i])){
          overlap=n;break;
        }
      }
      let fresh=tokens.slice(overlap);
      if(lastCloudFinal.length>=tokens.length &&
         tokens.every((token,i)=>token===lastCloudFinal[i]))fresh=[];
      lastCloudFinal=tokens;
      if(!fresh.length)return;
      cloudAccum.push(...fresh);
      const result=matchFinalTokens(cloudAccum,cursor);
      cursor=result.cursor;
      setStatus(result.matched?"Phrase matched · "+liveCount.textContent+" words":
        "Arabic heard · waiting for a complete phrase","active");
    };
    setStatus("Connecting to Gemini's live transcription service...","active");
    const url="wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained?access_token="+encodeURIComponent(token);
    socket=new WebSocket(url);
    await new Promise((resolve,reject)=>{
      let setupStarted=false,settled=false;
      const handshakeTimeout=setTimeout(()=>{
        if(!settled){settled=true;reject(Error("Cloud connection timed out. Check network access."))}
      },18000);
      cancelSetup=()=>{
        clearTimeout(handshakeTimeout);
        if(!settled){settled=true;resolve()}
      };
      const fail=e=>{
        if(!settled){
          settled=true;
          clearTimeout(handshakeTimeout);
          reject(e instanceof Error?e:Error(String(e)));
        }
      };
      socket.onopen=()=>{
        socket.send(JSON.stringify({
          setup:{
            model:"models/gemini-3.5-transcribe-live",
            generationConfig:{responseModalities:["TEXT"]},
            // Force Arabic recognition instead of automatic multilingual detection.
            inputAudioTranscription:{languageCodes:["ar"]}
          }
        }));
      };
      socket.onmessage=async event=>{
        if(closed)return;
        let payload;
        try{payload=JSON.parse(typeof event.data==="string"?event.data:await event.data.text())}
        catch(_){return}
        if(closed)return;
        if(payload.error){
          fail(Error("Gemini Live response: "+String(payload.error.message||"Invalid session")));
          setStatus("Live transcription error: "+String(payload.error.message||"Invalid session"),"error");
          return;
        }
        if(payload.setupComplete || payload.setup_complete){
          if(setupStarted)return;
          setupStarted=true;clearTimeout(handshakeTimeout);
          try{
            stream=await navigator.mediaDevices.getUserMedia({
              audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},
              video:false
            });
            if(closed){
              stream.getTracks().forEach(track=>track.stop());
              return;
            }
            audioContext=new (window.AudioContext||window.webkitAudioContext)();
            await audioContext.resume();
            if(closed)return;
            source=audioContext.createMediaStreamSource(stream);
            processor=audioContext.createScriptProcessor(4096,1,1);
            mute=audioContext.createGain();
            mute.gain.value=0;
            source.connect(processor);processor.connect(mute);mute.connect(audioContext.destination);
            processor.onaudioprocess=evt=>{
              if(closed || socket.readyState!==WebSocket.OPEN)return;
              const samples=evt.inputBuffer.getChannelData(0);
              evt.outputBuffer.getChannelData(0).fill(0);
              let energy=0;
              for(let i=0;i<samples.length;i++)energy+=samples[i]*samples[i];
              const rms=Math.sqrt(energy/samples.length);
              maxRms=Math.max(maxRms,rms);
              meterFill.style.width=Math.min(100,Math.floor(rms*850))+"%";
              if(socket.bufferedAmount>512000) {
                micText.textContent="Network is catching up with the audio stream.";
                return;
              }
              socket.send(JSON.stringify({
                realtimeInput:{audio:{
                  mimeType:"audio/pcm;rate=16000",
                  data:floatToPcm16Base64(samples,audioContext.sampleRate)
                }}
              }));
            };
            micText.textContent="Cloud microphone is streaming. Recite a short passage clearly.";
            setStatus("Live microphone streaming · waiting for Arabic transcript...","active");
            watchdogId=setTimeout(()=>{
              if(closed||gotTranscript)return;
              setStatus(maxRms>0.012
                ? "Voice audio is being captured, but Gemini has not returned a transcript yet. Try a short pause or restart."
                : "The microphone connection is open but little sound is reaching it. Check Safari microphone permission.","error");
            },14000);
            settled=true;
            resolve();
          }catch(e){fail(Error("Microphone access after cloud connection failed: "+String(e?.message||e)))}
          return;
        }
        const content=payload.serverContent || payload.server_content;
        if(content){
          const interim=content.interimInputTranscription||content.interim_input_transcription;
          const finalized=content.inputTranscription||content.input_transcription;
          if(interim?.text)parseSpeech(interim.text,false);
          if(finalized?.text)parseSpeech(finalized.text,true);
        }
      };
      socket.onerror=()=>{
        if(!closed){
          fail(Error("Gemini Live WebSocket could not connect."));
          setStatus("Cloud connection failed. Check your API access and internet connection.","error");
        }
      };
      socket.onclose=event=>{
        if(!closed){
          fail(Error("Gemini Live closed: "+event.code+" "+(event.reason||"")));
          setStatus("Cloud transcription session ended ("+event.code+"). Start a new session to continue.","error");
          live=false;engineSelect.disabled=false;
          micButton.disabled=false;
          micButton.textContent="🎙 Start new session";
          micButton.classList.add("am-primary");
          micButton.classList.remove("am-danger");
          void cleanup();
        }
      };
    }).catch(async error=>{
      await cleanup();cleanupLive=null;
      throw error;
    });
  }

  // The current @tilawa/core 1.0 preview uses createTilawa(), not
  // the legacy createTilawaSession() SDK. Import once on page mount so
  // prepareMicrophone() can be called synchronously in the iPad tap handler.
  let sdkPromise=null,tilawaSdkReady=null;
  function loadSdk(){
    if(!sdkPromise){
      sdkPromise=import(
        "https://esm.sh/@tilawa/core@1.0.0-rc.0/web?bundle&deps=onnxruntime-web@1.30.0"
      ).then(mod=>{
        if(typeof mod.createTilawa!=="function"||typeof mod.prepareMicrophone!=="function")
          throw Error("Quran recognition SDK unavailable");
        tilawaSdkReady=mod;
        return mod;
      }).catch(error=>{sdkPromise=null;throw error});
    }
    return sdkPromise;
  }
  let sharedQuranEngine=null, sharedQuranEnginePromise=null;
  const engineAbort=new AbortController();
  async function ensureQuranEngine(purpose){
    if(sharedQuranEngine)return sharedQuranEngine;
    if(sharedQuranEnginePromise)return sharedQuranEnginePromise;
    sharedQuranEnginePromise=(async()=>{
      const sdk=tilawaSdkReady||await loadSdk();
      const created=await sdk.createTilawa({
        tier:"auto",
        providers:["wasm"],threads:1,signal:engineAbort.signal,
        onProgress:p=>{
          const stage=p.stage==="model"?"speech model":
            p.stage==="reference"?"Quran reference":"warm-up";
          const fraction=Number.isFinite(p.fraction)?Math.round(p.fraction*100):0;
          if(purpose==="live"){
            setStatus("Loading on-device Quran "+stage+" · "+fraction+"%","active");
          }else if(!live){
            repeatHelp.textContent="Preparing audio-aware reciter following · "+
              stage+" "+fraction+"% (playback remains available)";
          }
        }
      });
      if(engineAbort.signal.aborted){
        await created.dispose();
        throw Error("The component was closed");
      }
      sharedQuranEngine=created;
      return created;
    })().catch(e=>{
      sharedQuranEnginePromise=null;
      throw e;
    });
    return sharedQuranEnginePromise;
  }
  function onDevice(){return engineSelect.value==="local"||engineSelect.value==="vowels"}
  function prepareSelectedListener(){
    if(!onDevice())return;
    micText.textContent="Loading the on-device listener…";
    loadSdk().then(()=>{
      if(!live&&onDevice())micText.textContent="On-device listener ready. Tap Start listening.";
    }).catch(()=>{
      if(!live&&onDevice())micText.textContent="On-device listener unavailable. Tap Start to retry.";
    });
  }
  engineSelect.onchange=()=>{
    updateMatchCount();
    clearVowelReview();
    if(onDevice()){
      micMessage.textContent=engineSelect.value==="vowels"?"Recite one word or a short phrase. Stop to see possible vowel sounds. Audio stays on this device.":"Audio stays on this device while using the Qur’an listener.";
      prepareSelectedListener();
    }else{
      micText.textContent="Tap Start listening to use the selected transcription service.";
      micMessage.textContent=engineSelect.value==="cloud"?"Cloud transcription streams your microphone audio to Gemini.":
        "Your browser provides Arabic transcription and may use its speech service.";
    }
  };
  prepareSelectedListener();
  function stopVowelPlayback(){
    if(vowelPlayback){
      const context=vowelPlayback;
      vowelPlayback=null;
      void context.close().catch(()=>{});
    }
  }
  function clearVowelReview(){
    stopVowelPlayback();
    vowelReport.replaceChildren();
  }
  async function replayVowel(pcm,time,button){
    stopVowelPlayback();
    if(!audio.paused)audio.pause();
    const first=Math.max(0,Math.floor((time-0.35)*16000));
    const last=Math.min(pcm.length,Math.ceil((time+0.45)*16000));
    if(first>=last)return;
    let context;
    try{
      context=new (window.AudioContext||window.webkitAudioContext)();
      vowelPlayback=context;
      await context.resume();
      if(vowelPlayback!==context)return;
      const buffer=context.createBuffer(1,last-first,16000);
      buffer.getChannelData(0).set(pcm.subarray(first,last));
      const player=context.createBufferSource();
      player.buffer=buffer;
      player.connect(context.destination);
      player.onended=()=>{if(vowelPlayback===context)stopVowelPlayback()};
      player.start();
    }catch(_){
      if(context&&vowelPlayback!==context)return;
      stopVowelPlayback();
      button.textContent="Playback unavailable";
    }
  }
  function showVowels(evidence,pcm){
    const names=new Map([["َ","Fatḥah /a/"],["ِ","Kasrah /i/"],["ُ","Ḍammah /u/"]]);
    const list=CE("ol","");
    for(const chunk of evidence){
      for(const phone of chunk.phonemes){
        const name=names.get(phone.p);
        if(!name)continue;
        const time=phone.start*chunk.frameMs/1000;
        if(!Number.isFinite(time)||time<0||time>=pcm.length/16000)continue;
        // A display threshold only; decoder scores are not calibrated correctness probabilities.
        const supported=Number.isFinite(phone.conf)&&phone.conf>=0.80&&phone.conf<=1;
        const label=supported?name:"Vowel unclear";
        const row=CE("li","",label+" · "+time.toFixed(2)+" s");
        const replay=btn("Hear clip","am-button");
        replay.setAttribute("aria-label","Hear your recitation around "+time.toFixed(2)+" seconds");
        replay.onclick=()=>replayVowel(pcm,time,replay);
        row.appendChild(replay);
        list.appendChild(row);
      }
    }
    clearVowelReview();
    if(!list.childNodes.length){
      vowelReport.textContent="No short vowel resolved in this recording.";
      return;
    }
    append(vowelReport,CE("p","","Possible short vowels in recording order. Tap Hear clip to hear the surrounding sounds in your recording. Weak predictions appear as “Vowel unclear”. The listener can miss vowels or misidentify even a strong prediction."),list);
  }
  async function vowelLive(prepared){
    let engine,session,mic,timer,closed=false,failed=false;
    const pcm=new Float32Array(12*16000);
    let recorded=0;
    const cleanup=async()=>{
      if(closed)return;
      closed=true;
      clearTimeout(timer);
      try{
        if(mic){
          await mic.stop();
          if(!failed&&!engineAbort.signal.aborted)showVowels(session.evidence(),pcm.subarray(0,recorded));
        }
      }catch(_){vowelReport.textContent="Vowel review could not finish. Try another short recording."}
      finally{
        prepared.release();
        session?.dispose();
        await engine?.dispose();
      }
    };
    cleanupLive=cleanup;
    try{
      setStatus("Loading the on-device vowel listener…","active");
      engine=await tilawaSdkReady.createTilawa({tier:"lite",providers:["wasm"],threads:1,
        recordEvidence:true,signal:engineAbort.signal});
      if(closed){await engine.dispose();return}
      session=engine.startFreeRecitation();
      session.onAudio((samples,startMs)=>{
        const offset=Math.round(startMs*16);
        if(offset<0||offset>=pcm.length)return;
        const part=samples.subarray(0,pcm.length-offset);
        pcm.set(part,offset);
        recorded=Math.max(recorded,offset+part.length);
      });
      mic=await engine.listen(session,{prepared,vad:false,onError:()=>{
        failed=true;
        vowelReport.textContent="Audio analysis was interrupted. Try recording again.";
        if(!closed)void stopLive();
      }});
      if(closed){await mic.stop();return}
      setStatus("Recite now · vowel review stops after 12 seconds.","active");
      timer=setTimeout(()=>{if(!closed)void stopLive()},12000);
    }catch(error){failed=true;await cleanup();throw error}
  }
  async function localLive(prepared){
    // prepareMicrophone() is invoked synchronously in the button event, before
    // asynchronous model downloads, to preserve Safari's user gesture.
    if(!prepared)throw Error("The Quran microphone was not prepared. Tap Start again.");
    setStatus("Loading Quran-specific model · first download may be 25 MB on iPad...","active");
    let engine=null,session=null,mic=null,disposed=false;
    const cleanup=async()=>{
      if(disposed)return;
      disposed=true;
      try{prepared.release()}catch(_){}
      try{
        const finalEvents=mic?await mic.stop():[];
        // A final decoder pass may withdraw a previously displayed cue.
        let changed=false;
        for(const event of finalEvents||[]){
          if(event.type==="checker"&&(event.state==="resolved"||event.state==="uncertain")){
            if(audioCues.delete(event.id))changed=true;
          }
        }
        if(changed)renderAudioCues();
      }catch(_){}
      try{session?.dispose()}catch(_){}
      meterFill.style.width="0%";
    };
    cleanupLive=cleanup;
    try{
      engine=await ensureQuranEngine("live");
      if(disposed)return;
      session=engine.startMemorization(
        {surah:Number(meta.s),fromAyah:Number(meta.a),toAyah:Number(meta.end)},
        // Preserve SDK-default confidence: lowering it would increase false
        // pronunciation warnings without teaching the model subtle vowels.
        {confirm:{after:"next-word"},minConfidence:0.60}
      );
      const counts=Array.isArray(D.trackWordCounts)?D.trackWordCounts:[];
      // Precompute verse offsets once; recognition events can arrive rapidly.
      const verseOffsets=[0];
      for(const count of counts)verseOffsets.push(verseOffsets[verseOffsets.length-1]+Number(count||0));
      const globalIndex=location=>{
        const surah=Number(location?.surah),ayah=Number(location?.ayah);
        const word=Number(location?.word);
        const verseIndex=ayah-Number(meta.a);
        if(!Number.isInteger(ayah)||surah!==Number(meta.s)||verseIndex<0||verseIndex>=counts.length)return -1;
        if(!Number.isInteger(word)||word<1||word>Number(counts[verseIndex]))return -1;
        return verseOffsets[verseIndex]+word-1;
      };
      // Fast-recitation tracking is independent of the memorisation cursor:
      // a recogniser may emit one locked event for several spoken words.
      // Skipped positions are UNKNOWN, never silently marked correct or wrong.
      function clearCursor(){
        wordNodes[acousticCursor]?.classList.remove("am-acoustic-cursor");
        acousticCursor=-1;
        currentWord=-1;
      }
      session.subscribe(event=>{
        if(!live||disposed||!event)return;
        if(event.type==="checker"){
          if(typeof event.id!=="string"||!event.id)return;
          if(event.state==="resolved"||event.state==="uncertain"){
            if(audioCues.delete(event.id))renderAudioCues();
            return;
          }
          const index=globalIndex(event.location);
          const label=cueLabels.get(event.errorClass);
          if(event.state!=="confirmed"||!label||!Number.isFinite(event.confidence)||event.confidence<0.60||
             !words[index]||!words[acousticCursor])return;
          // Confirmation may arrive several ayahs after the affected word.
          const previous=audioCues.get(event.id);
          if(previous?.index===index&&previous.label===label)return;
          audioCues.set(event.id,{index,label});
          renderAudioCues();
          return;
        }
        if(event.type==="position"){
          // The SDK ranks alternatives best first, including out-of-passage
          // matches. Never substitute a weaker candidate inside the selection.
          const best=event.observed?.[0];
          const idx=globalIndex(best?.word);
          if(event.state!=="locked"||idx<0||event.hold||event.spanHold){
            clearCursor();
            updateMatchCount();
            setStatus(event.state==="locked"&&idx<0?"Heard a different passage · check your selection":
              "Listening for a clear location…","active");
            return;
          }
          if(acousticCursor!==idx){
            clearCursor();
            acousticCursor=currentWord=idx;
            updateMatchCount();
            wordNodes[idx]?.classList.add("am-acoustic-cursor");
            wordNodes[idx]?.scrollIntoView({behavior:"instant",block:"nearest",inline:"nearest"});
          }
          setStatus("Following ayah "+best.word.ayah+" · word "+best.word.word,"active");
        }
      });
      let lastMeterUpdate=0;
      mic=await engine.listen(session,{
        prepared,
        onLevel:db=>{
          if(disposed)return;
          const now=Date.now();
          if(now-lastMeterUpdate<70)return; // at most ~14 paint updates/sec
          lastMeterUpdate=now;
          const level=Number.isFinite(db)?Math.min(100,Math.max(0,(db+65)*1.8)):0;
          meterFill.style.width=level+"%";
          if(level<4 && now-lastCoachingAt>8500)coach("🎙 I can’t hear you clearly. Move a little closer to the microphone.","guide");
        },
        onError:error=>{
          if(disposed)return;
          setStatus("Quran model inference failed: "+String(error?.message||error),"error");
          void stopLive();
        }
      });
      if(disposed){await mic.stop();return}
      micText.textContent="On-device Quran recognition active · no recitation audio sent to Gemini.";
      setStatus("Quran model listening. Begin reciting the displayed ayahs...","active");
      coach("Recite naturally. The dashed gold outline follows the word the listener locates.","guide");
    }catch(error){
      await cleanup();
      cleanupLive=null;
      throw error;
    }
  }
  micButton.onclick=async()=>{
    if(live){await stopLive();return}
    if(starting)return;
    starting=true;micButton.disabled=true;
    setStatus("Preparing microphone...","idle");
    let preparedLocalMic=null;
    try{
      if(!audio.paused)audio.pause();
      if(onDevice()){
        if(!tilawaSdkReady){
          await loadSdk();
          micText.textContent="On-device listener ready.";
          setStatus("Tap Start listening to open the microphone.");
          micButton.disabled=false;
          return;
        }
        // MUST precede every await in this click handler for iPad Safari.
        preparedLocalMic=tilawaSdkReady.prepareMicrophone();
      }
      if(engineSelect.value==="cloud" && (!cloudSession?.token || tokenConsumed())){
        await requestCloudToken();
        return;
      }
      transcript.textContent="";
      engineSelect.disabled=true;
      clearAudioCues();
      clearVowelReview();
      live=true;
      if(engineSelect.value==="cloud")await cloudLive();
      else if(engineSelect.value==="vowels")await vowelLive(preparedLocalMic);
      else if(engineSelect.value==="local")await localLive(preparedLocalMic);
      else await browserLive();
      if(!live)return;
      micButton.textContent="■ Stop listening";
      micButton.classList.remove("am-primary");
      micButton.classList.add("am-danger");
      micButton.disabled=false;
    }catch(e){
      try{preparedLocalMic?.release()}catch(_){}
      live=false;engineSelect.disabled=false;
      setStatus("Live tracking unavailable: "+String(e?.message||e),"error");
      micButton.textContent="🎙 Retry listening";
      micButton.disabled=false;
      micButton.classList.add("am-primary");
    }finally{starting=false}
  };
  selectTab(currentTab);
  let pendingCloudRequest=null;
  try{pendingCloudRequest=sessionStorage.getItem("amuallim:pendingCloudRequest")}catch(_){}
  if(cloudSession?.token && !tokenConsumed() &&
      pendingCloudRequest===cloudSession.id){
    // Only a freshly requested Cloud session may override the Quran listener.
    // An old token retained by Streamlit must never silently start Gemini.
    try{sessionStorage.removeItem("amuallim:pendingCloudRequest")}catch(_){}
    engineSelect.value="cloud";
    engineSelect.onchange();
    Promise.resolve().then(()=>{if(!live&&!starting)void micButton.onclick()});
  }
  return ()=>{
    clearTimeout(revealTimer);
    prayerRoom.dispose();
    journeyPlanner.dispose();
    clearVowelReview();
    live=false;clearTimers();
    try{if(cleanupLive)void cleanupLive()}catch(_){}
    try{audio.pause()}catch(_){}
    stopPlaybackFollow();
    engineAbort.abort();
    if(sharedQuranEngine)void sharedQuranEngine.dispose();
    try{micStream?.getTracks().forEach(t=>t.stop())}catch(_){}
    try{void micContext?.close()}catch(_){}
    if(meterAnimation)cancelAnimationFrame(meterAnimation);
  };
}
