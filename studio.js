export default function(component) {
  "use strict";
  const D=component.data || {};
  const words=Array.isArray(D.words)?D.words:[];
  const meta=D.meta || {};
  const root=component.parentElement.querySelector(".am-mount");
  if(!root)return;
  root.replaceChildren();
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
    ["read","☷","Read"],
    ["cover","◉","Memorise"],
    ["listen","♫","Listen"],
    ["journey","✦","My journey"]
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
  const controls=CE("div","am-control-row");
  const toggleHint=btn("✧ Show hints");
  const toggleColour=btn("◈ Tajweed signs");
  const resetBtn=btn("↺ Start over");
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
  let playingIndex=0;
  if(playlist.length)audio.src=playlist[0];
  audioPanel.appendChild(audio);
  const playCaption=CE("div","am-note","Follow the teacher's recitation at your own pace.");
  playCaption.style.marginTop="8px";
  audioPanel.appendChild(playCaption);
  readerPanel.appendChild(audioPanel);
  const micPanel=CE("div","am-panel");
  micPanel.style.marginTop="14px";
  const micTop=CE("div","am-section-top");
  append(micTop,CE("h2","", "Live recitation"),CE("span","am-badge","Beta · word following"));
  micPanel.appendChild(micTop);
  const micBody=CE("div","am-scaffold");
  const micDescription=CE("p","am-note",
     "Your voice should move the gold highlight across words. Browser speech recognition is approximate and cannot verify every Tajweed rule.");
  const micControls=CE("div","am-control-row");
  const micButton=btn("🎙 Start listening","am-button am-primary");
  const micTest=btn("◌ Test mic");
  const engineSelect=CE("select","am-input");
  engineSelect.setAttribute("aria-label","Speech recognition method");
  [["browser","Browser recognition"],["local","On-device AI · experimental"]].forEach(([value,label])=>{
    const op=CE("option","",label);op.value=value;engineSelect.appendChild(op);
  });
  append(micControls,micButton,micTest,engineSelect);
  const meter=CE("div","am-meter"),meterFill=CE("div","");
  meter.appendChild(meterFill);
  const micText=CE("div","am-note","No audio test has been performed.");
  const micMessage=CE("div","am-note","");
  append(micBody,micDescription,micControls,meter,micText,micMessage);
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
    ["Progress",String(D.reviewed||0)+" words reviewed"]
  ];
  statRows.forEach(([label,value])=>{
    const line=CE("div","am-mini-row");
    append(line,CE("span","",label),CE("b","",value));stats.appendChild(line);
  });
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
  const footer=CE("footer","am-footer","");
  footer.appendChild(CE("strong","", "Al-Mu'allim"));
  footer.appendChild(document.createTextNode(" · Original Qur'an study workspace · AI feedback is a learning aid, not an ijazah or a qualified teacher's assessment."));
  app.appendChild(footer);

  let currentTab=D.mode==="blind"?"cover":"read";
  let showHints=false,showTajweed=false;
  let currentWord=-1,confirmedWord=-1;
  let wordNodes=[];
  let live=false,starting=false,cleanupLive=null,recognition=null;
  let meterAnimation=0,micStream=null,micContext=null;
  let audioSegments=Array.isArray(D.segments)?D.segments:[];
  let currentAudioIdx=-1;
  let repetitions=0;
  const sessionKey="amuallim:practice:"+String(meta.s||0)+":"+String(meta.a||0)+":"+String(meta.end||0);
  try{repetitions=Math.max(0,Math.min(1000,Number(localStorage.getItem(sessionKey)||0)||0))}catch(_){}
  function setStatus(message,state="idle"){
    status.dataset.state=state;
    statusText.textContent=message;
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
  function match(text,cursor){
    const heard=normalized(text).split(" ").filter(Boolean);
    let idx=Math.max(0,cursor),found=-1;
    for(const token of heard){
      for(let i=idx;i<Math.min(expected.length,idx+8);i++){
        const target=expected[i];
        if(target && (token===target || (token.length>=5&&target.length>=5&&distance(token,target)<=1))){
          found=i;idx=i+1;break;
        }
      }
    }
    return found;
  }
  function mark(index,confirm){
    if(index<0||index>=words.length)return;
    currentWord=index;
    if(confirm)confirmedWord=Math.max(confirmedWord,index);
    wordNodes.forEach((el,i)=>{
      el.classList.toggle("am-active",i===index);
      el.classList.toggle("am-confirmed",i<=confirmedWord&&i!==index);
    });
    progressFill.style.width=Math.round(100*(index+1)/Math.max(1,words.length))+"%";
    wordNodes[index]?.scrollIntoView({behavior:"smooth",block:"nearest",inline:"nearest"});
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
      playingIndex=idx;audio.src=playlist[idx];
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
    textArea.setAttribute("lang",cover?"en":"ar");
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
      const view=()=>{if(cover)showIndividualHint(i);else openWord(i)};
      el.addEventListener("click",view);
      el.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();view()}});
      if(i===currentWord)el.classList.add("am-active");
      else if(i<=confirmedWord)el.classList.add("am-confirmed");
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
    if(live && (tab==="journey"||tab==="listen"))void stopLive();
    currentTab=tab;showHints=false;detail.hidden=true;
    Object.entries(tabBtns).forEach(([id,b])=>b.setAttribute("aria-selected",String(id===tab)));
    const journey=tab==="journey";
    layout.hidden=journey;
    journeyPanel.hidden=!journey;
    hero.hidden=journey;
    if(journey){return}
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
  resetBtn.onclick=()=>{currentWord=-1;confirmedWord=-1;progressFill.style.width="0%";setStatus("Ready to practise from the beginning.");transcript.textContent="";renderWords()};
  recordHint.onclick=()=>{
    micPanel.scrollIntoView({behavior:"smooth",block:"center"});
    if(!live)micButton.focus();
  };
  repeatCount.textContent=String(repetitions)+" repetitions";
  repeatButton.onclick=()=>{
    repetitions++;repeatCount.textContent=String(repetitions)+" repetitions";
    repeatMessage.textContent="Alhamdulillah · "+String(repetitions)+" repetitions in this passage.";
    try{localStorage.setItem(sessionKey,String(repetitions))}catch(_){}
  };
  audio.onended=()=>{
    playingIndex++;
    if(playingIndex<playlist.length){
      audio.src=playlist[playingIndex];audio.play().catch(()=>{});
    } else {
      playingIndex=0;currentAudioIdx=-1;playCaption.textContent="Playback finished.";
      if(!live)wordNodes.forEach(el=>el.classList.remove("am-active"));
    }
  };
  audio.ontimeupdate=()=>{
    if(live)return;
    const ayah=Number(meta.a)+playingIndex;
    const pos=audio.currentTime*1000;
    const timed=audioSegments.find(s=>Number(s.ayah)===ayah&&pos>=s.start&&pos<s.end);
    if(timed && Number.isInteger(timed.word_idx)){
      const i=timed.word_idx;
      if(i>=0&&i<wordNodes.length&&i!==currentAudioIdx){
        currentAudioIdx=i;
        wordNodes.forEach((el,j)=>el.classList.toggle("am-active",j===i));
      }
    }
    playCaption.textContent="Playing ayah "+ayah+" of "+meta.end+
      (timed?" · audio word timing":" · timing unavailable");
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
  let micTesting=false;
  micTest.onclick=async()=>{
    if(micTesting||live){micText.textContent="Stop live tracking before checking the microphone.";return}
    micTesting=true;micTest.disabled=true;
    micText.textContent="Requesting microphone permission...";
    let ctx,stream;
    try{
      if(!navigator.mediaDevices?.getUserMedia)throw new Error("Microphone access is not available on this page.");
      stream=await navigator.mediaDevices.getUserMedia({audio:true});
      ctx=new (window.AudioContext||window.webkitAudioContext)();
      await ctx.resume();
      const source=ctx.createMediaStreamSource(stream);
      const analyser=ctx.createAnalyser();analyser.fftSize=1024;source.connect(analyser);
      let running=true;updateMeter(analyser,()=>running);
      micText.textContent="Microphone access granted. Speak to check the level meter.";
      await new Promise(resolve=>setTimeout(resolve,3200));
      running=false;cancelAnimationFrame(meterAnimation);
      micText.textContent="Microphone test finished. If the meter moved, audio capture works; recognition is tested separately.";
    }catch(e){micText.textContent="Microphone unavailable: "+String(e?.message||e)}
    finally{
      meterFill.style.width="0%";
      stream?.getTracks().forEach(t=>t.stop());
      try{await ctx?.close()}catch(_){}
      micTesting=false;micTest.disabled=false;
    }
  };
  let watchdog=null,restartHandle=null;
  function clearTimers(){
    if(watchdog!==null)clearTimeout(watchdog);
    if(restartHandle!==null)clearTimeout(restartHandle);
    watchdog=restartHandle=null;
  }
  async function stopLive(){
    live=false;starting=false;clearTimers();
    try{if(cleanupLive)await cleanupLive()}catch(_){}
    cleanupLive=null;
    micButton.disabled=false;
    micButton.textContent="🎙 Start listening";
    micButton.classList.remove("am-danger");
    micButton.classList.add("am-primary");
    setStatus("Listening stopped.");
  }
  async function browserLive(){
    const BrowserSpeech=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!BrowserSpeech)throw new Error("This browser does not support Arabic speech recognition. Use the recorded audio review below instead.");
    const apple=/iPad|iPhone|iPod/.test(navigator.userAgent)||
      (navigator.platform==="MacIntel"&&navigator.maxTouchPoints>1);
    const r=new BrowserSpeech();
    r.lang="ar-SA";r.continuous=!apple;r.interimResults=true;r.maxAlternatives=1;
    let closed=false,received=false,started=0,cursor=Math.max(0,confirmedWord+1),lastInterim=-1;
    function armWatchdog(){
      if(watchdog!==null)clearTimeout(watchdog);
      watchdog=setTimeout(()=>{
        if(!closed&&!received){
          setStatus("Microphone opened, but Safari returned no speech results. Try the mic test or recorded review.","error");
          transcript.textContent="No words recognised. This is a browser limitation, not evidence of a recitation mistake.";
        }
      },11500);
    }
    r.onstart=()=>{
      started++;setStatus("Microphone connected · waiting for Arabic speech...","active");armWatchdog();
    };
    r.onspeechstart=()=>setStatus("Speech detected · matching Qur'an words...","active");
    r.onresult=e=>{
      received=true;
      if(watchdog!==null){clearTimeout(watchdog);watchdog=null}
      let final="",interim="";
      for(let i=e.resultIndex;i<e.results.length;i++){
        const item=e.results[i],v=item?.[0]?.transcript||"";
        if(item.isFinal)final+=" "+v;else interim+=" "+v;
      }
      let idx=-1;
      if(final.trim()){
        idx=match(final,cursor);
        if(idx>=0){mark(idx,true);cursor=Math.max(cursor,idx+1)}
      }
      if(interim.trim()){
        const guess=match(interim,cursor);
        if(guess>=0){lastInterim=guess;mark(guess,false);idx=guess}
      }
      const heard=(final+" "+interim).trim();
      if(heard)transcript.textContent="Recognised Arabic (approximate): "+heard.slice(0,180);
      setStatus(idx>=0?"Following your recitation · "+Math.round(100*(idx+1)/Math.max(1,words.length))+"% of passage":
        "Arabic heard, but no match yet. Check the selected ayahs.","active");
    };
    r.onerror=e=>{
      const err=e.error||"unknown";
      if(closed)return;
      setStatus(err==="no-speech"?"No clear speech heard. Try a short ayah.":
        "Speech recognition error: "+err+". Try the microphone test.", "error");
      if(["not-allowed","audio-capture","service-not-allowed","language-not-supported"].includes(err)){
        closed=true;
      }
    };
    r.onend=()=>{
      clearTimers();
      if(closed){void stopLive();return}
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
  async function localLive(){
    // Experimental, only selected explicitly. Browser speech remains the default.
    const [core,runtime]=await Promise.all([
      import("https://esm.sh/@tilawa/core@next/web"),
      import("https://esm.sh/onnxruntime-web@1.30.0/wasm")
    ]);
    const ort=runtime;
    if(ort.env?.wasm){
      ort.env.wasm.wasmPaths="https://cdn.jsdelivr.net/npm/onnxruntime-web@1.30.0/dist/";
      ort.env.wasm.numThreads=1;ort.env.wasm.proxy=false;
    }
    if(typeof core.createTilawa!=="function")throw new Error("The experimental engine is unavailable.");
    setStatus("Loading the optional on-device Quran tracking model...","active");
    const model=await core.createTilawa({ort,onProgress:p=>setStatus("Loading model · "+String(p.stage||"")+
      " "+Math.round((p.fraction||0)*100)+"%","active")});
    let mic;
    try{
      const session=model.startMemorization({surah:Number(meta.s),fromAyah:Number(meta.a),toAyah:Number(meta.end)},
        {confirm:{after:"next-word"}});
      const offsets=[];let current=0;
      (D.trackWordCounts||[]).forEach(n=>{offsets.push(current);current+=n});
      const locate=o=>{
        const verse=(o.ayah??o.verse??meta.a)-meta.a;
        const word=o.word-1;
        if(verse<0||verse>=offsets.length||word<0||word>=D.trackWordCounts[verse])return -1;
        return offsets[verse]+word;
      };
      session.subscribe(event=>{
        if(!live)return;
        if(event.type==="position"&&event.state==="locked"&&event.observed?.[0]){
          const idx=locate(event.observed[0]);
          if(idx>=0){mark(idx,false);setStatus("Local model following · "+Math.round(100*(idx+1)/Math.max(1,words.length))+"%","active")}
        }
        if(event.type==="checker"&&event.state==="confirmed"){
          const idx=locate(event.location);
          if(idx>=0){mark(idx,event.errorClass==="correct")}
        }
      });
      mic=await model.listen(session);
    }catch(e){await model.dispose();throw e}
    cleanupLive=async()=>{try{await mic?.stop()}finally{await model.dispose()}};
    setStatus("Local model listening. Word tracking is experimental.","active");
  }
  micButton.onclick=async()=>{
    if(live){await stopLive();return}
    if(starting||micTesting)return;
    starting=true;micButton.disabled=true;
    setStatus("Preparing microphone...","idle");
    try{
      if(!audio.paused)audio.pause();
      live=true;
      if(engineSelect.value==="local")await localLive();
      else await browserLive();
      micButton.textContent="■ Stop listening";
      micButton.classList.remove("am-primary");
      micButton.classList.add("am-danger");
      micButton.disabled=false;
    }catch(e){
      live=false;
      setStatus("Live tracking unavailable: "+String(e?.message||e),"error");
      micButton.textContent="🎙 Retry listening";
      micButton.disabled=false;
      micButton.classList.add("am-primary");
    }finally{starting=false}
  };
  selectTab(currentTab);
  return ()=>{
    live=false;clearTimers();
    try{if(cleanupLive)void cleanupLive()}catch(_){}
    try{audio.pause()}catch(_){}
    try{micStream?.getTracks().forEach(t=>t.stop())}catch(_){}
    try{void micContext?.close()}catch(_){}
    if(meterAnimation)cancelAnimationFrame(meterAnimation);
  };
}
