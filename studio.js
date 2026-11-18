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
     "Cloud Live sends your recitation audio to Gemini after you press Start. It can return Arabic words while you speak, but it does not certify vowels or Tajweed. It may use your Gemini API quota.");
  const micControls=CE("div","am-control-row");
  const micButton=btn("🎙 Start listening","am-button am-primary");

  const engineSelect=CE("select","am-input");
  engineSelect.setAttribute("aria-label","Speech recognition method");
  [
    ["cloud",D.cloudAvailable?"Cloud Live · recommended":"Cloud Live · requires API key"],
    ["browser","Safari/browser recogniser · fallback"],
    ["local","On-device AI · experimental"]
  ].forEach(([value,label])=>{
    const op=CE("option","",label);op.value=value;engineSelect.appendChild(op);
  });
  // iPad Safari often blocks the browser's speech recognition service even
  // when microphone audio capture succeeds. Never silently select it.
  const isAppleWebKit=/iPad|iPhone|iPod/.test(navigator.userAgent||"")||
    (navigator.platform==="MacIntel"&&navigator.maxTouchPoints>1);
  engineSelect.value=(D.cloudAvailable||isAppleWebKit)?"cloud":"browser";
  append(micControls,micButton,engineSelect);
  const meter=CE("div","am-meter"),meterFill=CE("div","");
  meter.appendChild(meterFill);
  const micText=CE("div","am-note","No audio test has been performed.");
  const micMessage=CE("div","am-note",D.cloudError || (
    D.cloudAvailable
      ? "Cloud Live is ready to request a short-lived session token. Audio is sent to Google only after you press Start."
      : isAppleWebKit
        ? "Safari blocks speech recognition on some iPads (service-not-allowed). Microphone access is working; live highlighting needs Cloud Live, which requires GEMINI_API_KEY in Streamlit secrets. You can still use Record and review below."
        : "Cloud Live needs GEMINI_API_KEY in Streamlit secrets. Browser recognition may be unavailable even if the mic test succeeds."
  ));
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

  let currentTab=["read","cover"].includes(D.resumeTab)?D.resumeTab:(D.mode==="blind"?"cover":"read");
  let showHints=false,showTajweed=false;
  let currentWord=-1,confirmedWord=Number.isInteger(D.resumeWord)?Math.max(-1,Math.min(words.length-1,D.resumeWord)):-1;
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
        "Speech recognition error: "+err+". Try Cloud Live or recorded review.", "error");
      if(err==="service-not-allowed"){
        closed=true;
        setStatus("Safari blocked its speech-recognition service. Your microphone works; choose Cloud Live (requires a configured Gemini API key).","error");
        micMessage.textContent="Safari service-not-allowed is not a Tajweed error. Select Cloud Live or use the recorded-audio review.";
        engineSelect.value="cloud";
      } else if(["not-allowed","audio-capture","language-not-supported"].includes(err)){
        closed=true;
      }
    };
    r.onend=()=>{
      clearTimers();
      if(closed){
        // Keep the actual Safari error visible instead of overwriting it
        // with the generic "Listening stopped" message.
        live=false;starting=false;clearTimers();
        cleanupLive=null;
        micButton.disabled=false;
        micButton.textContent="🎙 Try Cloud Live";
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
    let watchdogId=null;
    const cleanup=async()=>{
      closed=true;
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
      if(!phrase)return;
      gotTranscript=true;
      if(watchdogId!==null){clearTimeout(watchdogId);watchdogId=null}
      transcript.textContent=(final?"Recognised: ":"Listening: ")+phrase.slice(0,230);
      const idx=match(phrase,cursor);
      if(idx>=0){
        mark(idx,final);
        if(final)cursor=Math.max(cursor,idx+1);
        setStatus("Cloud recognition active · "+Math.round((idx+1)*100/Math.max(1,words.length))+
          "% of the selected passage","active");
      } else {
        setStatus("Cloud recognised Arabic audio, but couldn't match these words to the selected ayahs.","active");
      }
    };
    setStatus("Connecting to Gemini's live transcription service...","active");
    const url="wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained?access_token="+encodeURIComponent(token);
    socket=new WebSocket(url);
    await new Promise((resolve,reject)=>{
      let setupStarted=false,settled=false;
      const handshakeTimeout=setTimeout(()=>{
        if(!settled){settled=true;reject(Error("Cloud connection timed out. Check network access."))}
      },18000);
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
            inputAudioTranscription:{languageCodes:[]}
          }
        }));
      };
      socket.onmessage=async event=>{
        if(closed)return;
        let payload;
        try{payload=JSON.parse(typeof event.data==="string"?event.data:await event.data.text())}
        catch(_){return}
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
            audioContext=new (window.AudioContext||window.webkitAudioContext)();
            await audioContext.resume();
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
          live=false;
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
    if(starting)return;
    starting=true;micButton.disabled=true;
    setStatus("Preparing microphone...","idle");
    try{
      if(!audio.paused)audio.pause();
      if(engineSelect.value==="cloud" && (!cloudSession?.token || tokenConsumed())){
        await requestCloudToken();
        return;
      }
      live=true;
      if(engineSelect.value==="cloud")await cloudLive();
      else if(engineSelect.value==="local")await localLive();
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
  if(cloudSession?.token && !tokenConsumed()){
    // Streamlit supplied a token after the user's explicit Start request.
    engineSelect.value="cloud";
    Promise.resolve().then(()=>{if(!live&&!starting)void micButton.onclick()});
  }
  return ()=>{
    live=false;clearTimers();
    try{if(cleanupLive)void cleanupLive()}catch(_){}
    try{audio.pause()}catch(_){}
    try{micStream?.getTracks().forEach(t=>t.stop())}catch(_){}
    try{void micContext?.close()}catch(_){}
    if(meterAnimation)cancelAnimationFrame(meterAnimation);
  };
}
