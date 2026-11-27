// Values are PCM sample counts at the SDK audio tap's specified rate, 16 kHz.
export function paceMeter(){
  const taps=[];
  const isolated=[];
  let lastTap=null, run=0, quiet=0;
  return {
    tap(ms){
      const gap=ms-lastTap;
      if(lastTap!==null && gap>=100 && gap<=1200){
        taps.push(gap);
        if(taps.length>7)taps.shift();
      }else taps.length=0;
      lastTap=ms;
    },
    beat(){
      if(taps.length<3)return null;
      const sorted=[...taps].sort((a,b)=>a-b);
      const mid=Math.floor(sorted.length/2);
      return (sorted[mid]+sorted[Math.floor((sorted.length-1)/2)])/2;
    },
    calibrate(duration){
      if(duration>=60 && duration<=600){
        isolated.push(duration);
        if(isolated.length>7)isolated.shift();
      }
    },
    acousticBeat(){
      if(isolated.length<4)return null;
      const sorted=[...isolated].sort((a,b)=>a-b);
      const mid=Math.floor(sorted.length/2);
      return (sorted[mid]+sorted[Math.floor((sorted.length-1)/2)])/2;
    },
    frame(pcm){
      // A periodic-sound gate in 20 ms windows. It also responds to humming.
      let energy=0;
      for(const x of pcm)energy+=x*x;
      let periodic=false;
      if(energy/pcm.length>.00012){
        for(let lag=32;lag<=192;lag+=2){
          let cross=0,a=0,b=0;
          for(let i=lag;i<pcm.length;i+=2){
            cross+=pcm[i]*pcm[i-lag];a+=pcm[i]**2;b+=pcm[i-lag]**2;
          }
          if(cross>0 && cross*cross>.65*a*b){periodic=true;break}
        }
      }
      if(periodic){run+=pcm.length+quiet;quiet=0}
      else {quiet+=pcm.length;if(quiet>=640){run=0;quiet=0}}
      return run/16;
    }
  };
}

export function pcmWave(samples){
  const buffer=new ArrayBuffer(44+samples.length*2);
  const d=new DataView(buffer);
  const tag=(offset,word)=>[...word].forEach((c,i)=>d.setUint8(offset+i,c.charCodeAt(0)));
  tag(0,"RIFF");d.setUint32(4,buffer.byteLength-8,true);tag(8,"WAVE");tag(12,"fmt ");
  d.setUint32(16,16,true);d.setUint16(20,1,true);d.setUint16(22,1,true);
  d.setUint32(24,16000,true);d.setUint32(28,32000,true);d.setUint16(32,2,true);
  d.setUint16(34,16,true);tag(36,"data");d.setUint32(40,samples.length*2,true);
  samples.forEach((x,i)=>d.setInt16(44+2*i,Math.round(Math.max(-1,Math.min(1,x))*(x<0?32768:32767)),true));
  return new Blob([buffer],{type:"audio/wav"});
}

// Release resources that arrive after the browser has timed out or the
// learner has left the tab. Timers and abort listeners belong to one wait.
export function awaitRecorderStep(task,ms,signal,message,releaseLate){
  return new Promise((resolve,reject)=>{
    let done=false;
    function settle(callback,value){
      if(done)return false;
      done=true;clearTimeout(timer);signal.removeEventListener("abort",cancel);
      callback(value);return true;
    }
    const cancel=()=>settle(reject,new DOMException("Recording closed","AbortError"));
    const timer=setTimeout(()=>settle(reject,new Error(message)),ms);
    signal.addEventListener("abort",cancel,{once:true});
    if(signal.aborted)cancel();
    Promise.resolve(task).then(value=>{
      if(!settle(resolve,value) && releaseLate)Promise.resolve(releaseLate(value)).catch(()=>{});
    },error=>settle(reject,error));
  });
}

export function mountRecitation(root,data){
  root.replaceChildren();
  const add=(tag,text,parent=root)=>{
    const el=document.createElement(tag);el.textContent=text;parent.appendChild(el);return el;
  };
  const filters=add("div","");filters.className="recite-filters";filters.setAttribute("aria-label","Highlight Tajwid rules");
  const progress=add("progress","");progress.className="recite-position";progress.hidden=true;
  progress.setAttribute("aria-label","Current word in the passage");
  const canvas=add("div","");canvas.className="recite-canvas";canvas.dir="rtl";canvas.lang="ar";
  const controls=add("div","");controls.className="recite-controls";
  const blindLabel=add("label","Recite from memory ",controls);
  const blind=add("input","",blindLabel);blind.type="checkbox";blind.checked=!!data.blind;
  const start=add("button","Bismillah, I recite",controls),stop=add("button","Stop recording",controls);

  const bar=add("progress","");bar.hidden=true;bar.setAttribute("aria-label","Madd counts");
  const elapsed=add("output","");stop.hidden=true;start.disabled=true;
  stop.disabled=true;
  const status=add("p","Audio stays in this browser. Maximum session length is 90 seconds.");
  status.setAttribute("role","status");
  const busy=add("progress","");busy.hidden=true;busy.setAttribute("aria-label","Preparing recorder");
  const micHelp="Open this app directly in Safari, allow Microphone in Website Settings, then tap to retry.";
  const modelHelp="The speech model did not load. Check your connection and tap to retry.";
  function loading(message){status.textContent=message;busy.hidden=false}

  const player=add("audio","");player.controls=true;player.hidden=true;
  const save=add("a","Download session WAV");save.download="recitation.wav";save.hidden=true;
  let selection=data;
  const historyPanel=add("details","");add("summary","Device practice history",historyPanel);
  const summary=add("p","",historyPanel),drill=add("button","Practice weak verses");
  const tech=add("details","");add("summary","Technical Acoustic Lab",tech);
  const exportBtn=add("button","Export history",tech);
  const importLabel=add("label","Import history ",tech),file=add("input","",importLabel);
  file.type="file";file.accept=".json,application/json";
  let history,queue=[],drillIndex=0,exportUrl;
  function refresh(){
    try{
      queue=history.queue();
      summary.textContent=history.read().length+" saved sessions on this browser. "+queue.slice(0,3).map(v=>
        v.s+":"+v.a+" · "+v.unresolved+" recall reviews · "+v.timing+" timing reviews "+
        Object.entries(v.flags).map(([label,n])=>label+" ×"+n).join(", ")).join(" | ");
      drill.hidden=!queue.length;drill.disabled=!reference||!queue.length||!!mic||opening||closing;
    }catch{summary.textContent="Practice history unavailable in this browser.";drill.disabled=true}
  }
  drill.onclick=()=>{
    if(!reference||!queue.length||mic||opening||closing)return;
    clearRecording();
    const v=queue[drillIndex++%queue.length];
    selection={...data,surah:v.s,first:v.a,end:v.a};blind.checked=true;drawPassage();
    status.textContent="Blind drill · "+v.s+":"+v.a+". Start when ready.";
  };
  exportBtn.onclick=()=>{
    try{
      const text=JSON.stringify({version:1,sessions:history.read()});
      if(exportUrl)URL.revokeObjectURL(exportUrl);
      exportUrl=URL.createObjectURL(new Blob([text],{type:"application/json"}));
      const a=document.createElement("a");a.href=exportUrl;a.download="al-muallim-practice.json";a.click();
    }catch{summary.textContent="Export unavailable."}
  };
  file.onchange=async()=>{
    try{
      const f=file.files[0];if(!f)return;
      if(f.size>1000000)throw Error();
      history.merge(await f.text());refresh();
    }catch{summary.textContent="Import failed. Choose an Al-Mu’allim practice history file."}
    file.value="";
  };
  const report=add("section","");root.append(report,drill,historyPanel,tech);tech.append(save);
  const metrics=add("section","",tech);
  let reference,clearAudit,tracker,autoState;
  let sdk,engine,session,mic,prepared,interval,url,dead=false,opening=false,closing=false;
  const abort=new AbortController();
  try{history=practiceHistory(localStorage,data.profile,data.countsCsv.split(",").map(Number))}catch{}
  let wordNodes=new Map(),lit=null,filter="all";
  const hintsByWord=new Map();
  function applyFilter(){
    for(const button of filters.children)button.setAttribute("aria-pressed",String(button.dataset.kind===filter));
    for(const [key,node] of wordNodes){
      node.classList.toggle("filtered",filter!=="all"&&hintsByWord.get(key).some(h=>h.kind===filter));
    }
    for(const item of canvas.querySelectorAll("[data-rule]")){
      const selected=filter==="all"||item.dataset.rule===filter;
      if(item.tagName==="SMALL")item.hidden=!selected;
      else item.classList.toggle("ink",selected);
    }
  }
  function drawPassage(){
    canvas.replaceChildren();wordNodes.clear();lit=null;
    const verses=reference?.ayahs.filter(a=>a.s===selection.surah&&a.a>=selection.first&&a.a<=selection.end);
    const rows=verses||[{s:data.surah,a:data.first,w:data.preview||[]}];
    hintsByWord.clear();
    let ordinal=0;
    const counts=Object.fromEntries(Object.keys(ruleNames).map(k=>[k,0]));
    for(const row of rows){
      const line=add("div","",canvas);line.className="recite-line";
      const sites=row.p?[...new Map([...maddSites(row).values()].map(site=>[site.onset,site])).values()]:[];
      row.w.forEach((word,i)=>{
        const node=add("span","",line);node.className="recite-word";node.dataset.ordinal=++ordinal;
        const key=row.s+":"+row.a+":"+(i+1);wordNodes.set(key,node);
        const tags=row.p?referenceTags(word,row.p.slice(row.o[i],row.o[i+1]),row.w[i+1],row.w[i-1],row.iso[i]):[];
        const hints=wordRuleHints(word,tags,sites.filter(site=>site.word===i+1));
        hintsByWord.set(key,hints);
        const script=add("span","",node);
        for(const part of word.matchAll(/.\p{M}*/gu)){
          const hint=hints.find(h=>h.index===part.index);
          if(hint)add("span",part[0],script).dataset.rule=hint.kind;
          else script.append(document.createTextNode(part[0]));
        }
        const labels=add("span","",node);labels.className="recite-labels";labels.dir="ltr";labels.lang="en";
        for(const h of hints){counts[h.kind]++;counts.all++}
        for(const h of new Map(hints.map(item=>[item.label,item])).values())add("small",h.label,labels).dataset.rule=h.kind;
      });
      if(verses){const marker=add("span",String(row.a),line);marker.className="recite-ayah";marker.setAttribute("aria-label","Ayah "+row.a)}
    }
    filters.replaceChildren();filters.hidden=!verses;
    for(const [kind,title] of Object.entries(ruleNames)){
      const button=add("button",title+" · "+counts[kind],filters);button.dataset.kind=kind;
      button.onclick=()=>{filter=kind;applyFilter()};
    }
    applyFilter();progress.max=Math.max(1,ordinal);progress.value=0;
  }
  function spotlight(position){
    const next=position&&wordNodes.get(position.ref+":"+position.word);
    if(lit===next)return;
    if(lit && canvas.classList.contains("memory"))lit.setAttribute("aria-hidden","true");
    lit?.classList.remove("current");lit?.removeAttribute("aria-current");lit=next;
    if(lit){lit.removeAttribute("aria-hidden");lit.classList.add("current");lit.setAttribute("aria-current","location");progress.value=Number(lit.dataset.ordinal)}
  }
  drawPassage();
  const loadReference=()=>awaitRecorderStep(verifiedReference(abort.signal),60000,abort.signal,modelHelp).then(value=>{
    if(!dead){reference=value;drawPassage();refresh()}return value;
  });
  const ruleNotice=add("p","Loading rule labels…");root.insertBefore(ruleNotice,filters);
  function fetchRules(){
    ruleNotice.hidden=false;
    return loadReference().then(value=>{ruleNotice.hidden=true;return value}).catch(()=>{
      if(!dead)ruleNotice.textContent="Rule labels could not load. Check your connection and retry recording.";
      return null;
    });
  }
  let referenceTask=fetchRules();
  function prepare(){
    start.disabled=true;
    loading("Preparing the recorder…");
    const moduleTask=import("https://esm.sh/@tilawa/core@1.0.0-rc.0/web?bundle&deps=onnxruntime-web@1.30.0");
    return awaitRecorderStep(moduleTask,45000,abort.signal,modelHelp).then(module=>{
      if(dead)return;sdk=module;status.textContent="Ready to recite. Audio stays on this device.";
    }).catch(()=>{if(!dead)status.textContent="The recorder could not load. Check your connection and tap to retry."})
      .finally(()=>{if(!dead){busy.hidden=true;start.disabled=false}});

  }
  void prepare();
  refresh();
  let wake,raw,rawCount,interrupted=false;
  let samples,count=0;
  function clearRecording(){
    clearAudit?.();clearAudit=null;report.replaceChildren();metrics.replaceChildren();spotlight(null);
    canvas.classList.remove("memory","blind-review");progress.value=0;for(const n of wordNodes.values()){n.classList.remove("review");n.onclick=null;n.removeAttribute("role");n.removeAttribute("tabindex");n.onkeydown=null}
    if(url){player.pause();player.removeAttribute("src");player.load();URL.revokeObjectURL(url);url=null}
    save.hidden=player.hidden=true;
  }
  async function finish(){
    if(!mic||closing)return;
    closing=true;stop.disabled=true;clearTimeout(interval);
    canvas.classList.remove("memory");for(const node of wordNodes.values())node.removeAttribute("aria-hidden");
    const current=mic;mic=null;
    try{
      await current.stop();
      if(dead)return;
      if(!count){status.textContent="No audio was captured. Try again when you are ready.";return}
      autoState=tracker.ingest(session.evidence(),samples.subarray(0,count));
      url=URL.createObjectURL(pcmWave(raw.subarray(0,Math.min(rawCount,count))));
      player.src=save.href=url;player.hidden=save.hidden=false;
      status.textContent=interrupted?"Recording interrupted. The captured portion is ready for playback.":"Recording ready for playback.";

      const evidence=session.evidence();
      const result=passageAudit(reference,selection,evidence,samples.subarray(0,count));
      const sessionId=crypto.randomUUID();
      if(!interrupted && result.matched){
        const verses=new Map();
        for(const w of result.words){
          const v=verses.get(w.ayah)||{s:selection.surah,a:w.ayah,supported:0,unresolved:0,timing:0,flags:[]};
          if(w.interval)v.supported++;else v.unresolved++;
          verses.set(w.ayah,v);
        }
        for(const n of autoState.notes.values()){
          const v=verses.get(Number(n.ref.split(":")[1]));if(v)v.timing++;
        }
        try{history.merge(JSON.stringify({version:1,sessions:[{id:sessionId,time:Date.now(),verses:[...verses.values()]}]}));refresh()}catch{summary.textContent="Session could not be saved on this device."}
      }
      const saveFlag=(!interrupted&&result.matched&&history)?(w,skill)=>{
        history.flag(sessionId,selection.surah,w.ayah,w.index+1,skill);refresh();
      }:null;
      const drawWord=renderAudit(report,result,samples.subarray(0,count),selection,add,abort.signal,autoState,false,saveFlag,raw.subarray(0,rawCount),metrics,hintsByWord);
      clearAudit=drawWord;
      if(result.matched>0 && result.matched<result.words.length && !interrupted)status.textContent="Underlined words are worth another listen.";
      spotlight(null);
      for(const w of result.words){
        const node=wordNodes.get(w.ref+":"+(w.index+1));
        if(!node)continue;
        if(result.aligned && result.matched>0 && (!w.interval||[...autoState.notes.values()].some(n=>n.ref===w.ref&&n.word===w.index+1)))node.classList.add("review");
        node.setAttribute("role","button");node.tabIndex=0;
        node.onclick=()=>drawWord.show(w);
        node.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();node.click()}};
      }
      canvas.classList.toggle("blind-review",blind.checked && result.matched>0);
    }catch{if(!dead)status.textContent="Recording interrupted. Please try again."}
    finally{await wake?.release().catch(()=>{});wake=null;blind.disabled=false;session?.dispose();session=null;prepared?.release();prepared=null;closing=false;stop.hidden=true;start.hidden=false;progress.hidden=true;bar.hidden=true;elapsed.textContent="";canvas.classList.remove("memory");start.disabled=dead;refresh();if(dead)await engine?.dispose();}
  }
  blind.onchange=()=>{if(!blind.checked)canvas.classList.remove("blind-review")};
  stop.onclick=()=>void finish();
  start.onclick=async()=>{
    if(opening||closing||dead)return;
    opening=true;start.disabled=true;
    try{
      if(!sdk){await prepare();return}
      // iPad requires AudioContext.resume and getUserMedia in the tap itself.
      loading("1 of 2 · Requesting microphone. Allow access when prompted.");
      const policy=document.permissionsPolicy||document.featurePolicy;
      if(policy?.allowsFeature && !policy.allowsFeature("microphone"))throw Error(micHelp);
      if(!navigator.mediaDevices?.getUserMedia)throw Error(micHelp);
      prepared=sdk.prepareMicrophone();
      await awaitRecorderStep(prepared.stream,15000,abort.signal,"Microphone did not respond within 15 seconds. "+micHelp);
      loading("2 of 2 · Loading the speech model. The first download can take a minute.");
      if(!reference && !(await referenceTask)){
        referenceTask=fetchRules();
        if(!(await referenceTask))throw Error(modelHelp);
      }
      if(dead)return;
      if(!engine){
        engine=await awaitRecorderStep(sdk.createTilawa({reference,tier:"lite",threads:1,providers:["wasm"],recordEvidence:true,signal:abort.signal}),
          90000,abort.signal,modelHelp,lateEngine=>lateEngine.dispose());
      }
      if(dead)return;
      tracker=continuousTracker(reference,selection);autoState=null;
      interrupted=false;blind.disabled=true;drill.disabled=true;
      const capture=prepared;
      void navigator.wakeLock?.request("screen").then(lock=>{
        if(dead||closing||prepared!==capture)void lock.release();else wake=lock;
      }).catch(()=>{});
      clearRecording();samples=new Float32Array(16000*90);count=rawCount=0;raw=new Float32Array(samples.length);

      const take=engine.startFreeRecitation();
      session=take;
      take.onAudio((pcm,ms)=>{
        if(dead||session!==take)return;
        const at=Math.round(ms*16);
        if(at!==count||at>=samples.length)return;
        const part=pcm.subarray(0,samples.length-at);samples.set(part,at);count+=part.length;
        const now=count/16;
        autoState=tracker.ingest(session.evidence(),samples.subarray(0,count));
        const {beat,active,position}=autoState;
        spotlight(position && now-position.end<450?position:null);
        const fresh=active && now-active.last<=Math.max(240,(beat||100)*2);
        bar.hidden=!fresh||!beat;
        elapsed.textContent=fresh?"Hold Madd · "+(active.site.label==="Pause-dependent madd"?"2, 4 or 6":[...new Set(active.site.range)].join("–"))+" counts":"";
        if(fresh&&beat){bar.max=active.site.range[0];bar.value=Math.min(bar.max,(now-active.start)/beat)}
      });
      const condition=microphoneConditioner();
      const input={
        get state(){return take.state},
        end:()=>take.end(),
        pushAudio:(pcm,rate)=>{
          if(dead||session!==take)return Promise.resolve([]);
          const n=Math.min(pcm.length,raw.length-rawCount);
          if(n<=0)return Promise.resolve([]);
          const chunk=pcm.subarray(0,n);
          raw.set(chunk,rawCount);rawCount+=n;
          return take.pushAudio(condition(chunk),rate);
        }
      };
      loading("Starting audio capture…");
      mic=await awaitRecorderStep(engine.listen(input,{prepared,vad:false,onError:()=>{
        if(session===take){interrupted=true;if(mic)void finish()}
      }}),15000,abort.signal,"Audio capture did not start. "+micHelp,lateMic=>lateMic.stop());
      const stream=await prepared.stream;
      const lost=()=>{interrupted=true;if(mic)void finish()};
      stream.getAudioTracks().forEach(track=>track.addEventListener("ended",lost,{once:true}));
      if(dead){await finish();return}
      interval=setTimeout(()=>void finish(),90000);stop.disabled=false;
      start.hidden=true;stop.hidden=false;progress.hidden=false;canvas.classList.toggle("memory",blind.checked);
      if(blind.checked)for(const node of wordNodes.values())node.setAttribute("aria-hidden","true");
      status.textContent="Recording…";
    }catch(error){blind.disabled=false;await wake?.release().catch(()=>{});wake=null;session?.dispose();session=null;prepared?.release();prepared=null;
      if(!dead){
        if(["NotAllowedError","SecurityError"].includes(error?.name))status.textContent="Microphone access was blocked. "+micHelp;
        else if(error?.name==="NotFoundError")status.textContent="No microphone is available. Connect one and try again.";
        else if(error?.message===modelHelp||error?.message?.endsWith(micHelp))status.textContent=error.message;
        else status.textContent="Recording could not start. Check microphone access and your connection, then retry.";
      }}
    finally{busy.hidden=true;opening=false;start.disabled=dead||!!mic||closing;if(dead && !closing)await engine?.dispose();}
  };
  const hidden=()=>{if(document.hidden && mic){interrupted=true;void finish()}};
  document.addEventListener("visibilitychange",hidden);
  return ()=>{
    document.removeEventListener("visibilitychange",hidden);
    if(exportUrl)URL.revokeObjectURL(exportUrl);
    dead=true;abort.abort();clearTimeout(interval);clearRecording();prepared?.release();
    if(mic)void finish();
    else if(!opening && !closing){session?.dispose();void engine?.dispose()}
  };
}
