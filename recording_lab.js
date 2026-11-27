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

export function mountRecitation(root,data){
  root.replaceChildren();
  const add=(tag,text,parent=root)=>{
    const el=document.createElement(tag);el.textContent=text;parent.appendChild(el);return el;
  };
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
      drill.hidden=!queue.length;drill.disabled=!queue.length||!!mic||opening||closing;
    }catch{summary.textContent="Practice history unavailable in this browser.";drill.disabled=true}
  }
  drill.onclick=()=>{
    if(!queue.length||mic||opening||closing)return;
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
  const report=add("section","");root.append(drill,report,historyPanel,tech);tech.append(save);
  const metrics=add("section","",tech);
  let reference,clearAudit,tracker,autoState;
  let sdk,engine,session,mic,prepared,interval,url,dead=false,opening=false,closing=false;
  const abort=new AbortController();
  try{history=practiceHistory(localStorage,data.profile,data.countsCsv.split(",").map(Number))}catch{}
  let wordNodes=new Map(),lit=null;
  function drawPassage(){
    canvas.replaceChildren();wordNodes.clear();lit=null;
    const verses=reference?.ayahs.filter(a=>a.s===selection.surah&&a.a>=selection.first&&a.a<=selection.end);
    const rows=verses||[{s:data.surah,a:data.first,w:data.preview||[]}];
    for(const row of rows){
      const line=add("div","",canvas);
      row.w.forEach((word,i)=>{
        const node=add("span",word,line);node.className="recite-word";
        wordNodes.set(row.s+":"+row.a+":"+(i+1),node);
      });
    }
  }
  function spotlight(position){
    const next=position&&wordNodes.get(position.ref+":"+position.word);
    if(lit===next)return;
    lit?.classList.remove("current");lit=next;lit?.classList.add("current");
  }
  drawPassage();
  const loadReference=()=>verifiedReference(abort.signal).then(value=>{
    if(!dead){reference=value;drawPassage()}return value;
  });
  let referenceTask=loadReference().catch(()=>null);
  function prepare(){
    start.disabled=true;
    return import("https://esm.sh/@tilawa/core@1.0.0-rc.0/web?bundle&deps=onnxruntime-web@1.30.0").then(module=>{
      if(dead)return;sdk=module;start.disabled=false;
    }).catch(()=>{if(!dead){start.disabled=false;status.textContent="The listener could not load. Tap to retry."}});
  }
  void prepare();
  refresh();
  let wake,raw,rawCount,interrupted=false;
  let samples,count=0;
  function clearRecording(){
    clearAudit?.();clearAudit=null;report.replaceChildren();metrics.replaceChildren();spotlight(null);
    canvas.classList.remove("memory");for(const n of wordNodes.values()){n.classList.remove("review");n.onclick=null;n.removeAttribute("role");n.removeAttribute("tabindex");n.onkeydown=null}
    if(url){player.pause();player.removeAttribute("src");player.load();URL.revokeObjectURL(url);url=null}
    save.hidden=player.hidden=true;
  }
  async function finish(){
    if(!mic||closing)return;
    closing=true;stop.disabled=true;clearTimeout(interval);
    const current=mic;mic=null;
    try{
      await current.stop();
      if(dead||!count)return;
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
      const drawWord=renderAudit(report,result,samples.subarray(0,count),selection,add,abort.signal,autoState,false,saveFlag,raw.subarray(0,rawCount),metrics);
      clearAudit=drawWord;
      spotlight(null);
      for(const w of result.words){
        const node=wordNodes.get(w.ref+":"+(w.index+1));
        if(!node)continue;
        if(result.aligned && (!w.interval||[...autoState.notes.values()].some(n=>n.ref===w.ref&&n.word===w.index+1)))node.classList.add("review");
        node.setAttribute("role","button");node.tabIndex=0;
        node.onclick=()=>drawWord.show(w);
        node.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();node.click()}};
      }
      canvas.classList.remove("memory");
    }catch{if(!dead)status.textContent="Recording interrupted. Please try again."}
    finally{await wake?.release().catch(()=>{});wake=null;blind.disabled=false;session?.dispose();session=null;prepared?.release();prepared=null;closing=false;stop.hidden=true;start.hidden=false;bar.hidden=true;elapsed.textContent="";canvas.classList.remove("memory");start.disabled=dead;refresh();if(dead)await engine?.dispose();}
  }
  stop.onclick=()=>void finish();
  start.onclick=async()=>{
    if(opening||closing||dead)return;
    opening=true;start.disabled=true;
    try{
      if(!sdk){await prepare();return}
      prepared=sdk.prepareMicrophone();
      prepared.stream.catch(()=>{});
      status.textContent="Getting ready. Start reciting when the Stop button appears.";
      if(!reference && !(await referenceTask))referenceTask=loadReference();
      await referenceTask;
      if(dead)return;
      if(!engine)engine=await sdk.createTilawa({reference,tier:"lite",threads:1,providers:["wasm"],recordEvidence:true,signal:abort.signal});
      if(dead)return;
      tracker=continuousTracker(reference,selection);autoState=null;
      interrupted=false;blind.disabled=true;drill.disabled=true;
      const capture=prepared;
      void navigator.wakeLock?.request("screen").then(lock=>{
        if(dead||closing||prepared!==capture)void lock.release();else wake=lock;
      }).catch(()=>{});
      clearRecording();samples=new Float32Array(16000*90);count=rawCount=0;raw=new Float32Array(samples.length);

      session=engine.startFreeRecitation();
      session.onAudio((pcm,ms)=>{
        if(dead)return;
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
        get state(){return session.state},
        end:()=>session.end(),
        pushAudio:(pcm,rate)=>{
          const n=Math.min(pcm.length,raw.length-rawCount);
          if(n<=0)return Promise.resolve([]);
          const chunk=pcm.subarray(0,n);
          raw.set(chunk,rawCount);rawCount+=n;
          return session.pushAudio(condition(chunk),rate);
        }
      };
      mic=await engine.listen(input,{prepared,vad:false,onError:()=>{interrupted=true;if(mic)void finish()}});
      const stream=await prepared.stream;
      const lost=()=>{interrupted=true;if(mic)void finish()};
      stream.getAudioTracks().forEach(track=>track.addEventListener("ended",lost,{once:true}));
      if(dead){await finish();return}
      interval=setTimeout(()=>void finish(),90000);stop.disabled=false;
      start.hidden=true;stop.hidden=false;canvas.classList.toggle("memory",blind.checked);status.textContent="Recording…";
    }catch{blind.disabled=false;await wake?.release().catch(()=>{});wake=null;session?.dispose();session=null;prepared?.release();prepared=null;
      if(!dead)status.textContent="Recorder unavailable. Check microphone access and the model download, then retry."}
    finally{opening=false;start.disabled=dead||!!mic||closing;if(dead && !closing)await engine?.dispose();}
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
