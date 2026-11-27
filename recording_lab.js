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

export default function(component){
  const root=component.parentElement.querySelector(".timing-lab");
  root.replaceChildren();
  const add=(tag,text,parent=root)=>{
    const el=document.createElement(tag);el.textContent=text;parent.appendChild(el);return el;
  };
  add("h3","Madd timing practice");
  add("p","Recite the selected ayahs. Automatic pace uses short-vowel estimates and displays a madd target when the listener finds its place.");
  const tap=add("button","Tap one beat");
  const pace=add("span","Waiting for recitation");
  const meter=paceMeter();
  tap.onclick=()=>{meter.tap(performance.now());const beat=meter.beat();pace.textContent=beat?Math.round(beat)+" ms / beat":"Keep tapping"};
  const modeLabel=add("label","Pace source ");
  const mode=add("select","",modeLabel);
  for(const [id,title] of [["auto","Continuous recitation"],["tap","Tapped beat"],["cal","Calibrate with isolated short vowels"],["voice","Use calibrated vowels"]]){
    const option=add("option",title,mode);option.value=id;
  }
  mode.onchange=()=>{
    tap.hidden=mode.value!=="tap";label.hidden=mode.value==="auto";
    pace.textContent=mode.value==="auto"?"Listening for short vowels":mode.value==="cal"?"While recording, say four separate short vowels at your pace, with silence between them.":
      mode.value==="voice"?(meter.acousticBeat()?meter.acousticBeat()+" ms / beat":"Calibrate four vowels first"):"Tap four steady beats";
  };
  const label=add("label","Target ");
  const target=add("select","",label);
  for(const n of [1,2,4,6]){const opt=add("option",n+" beats",target);opt.value=String(n)}
  target.value="2";mode.onchange();
  const guard=add("p","");
  const bar=add("progress","");bar.max=2;bar.value=0;bar.setAttribute("aria-label","Elapsed beats");
  const elapsed=add("output","0.0 beats");elapsed.setAttribute("aria-live","off");
  const start=add("button","Prepare local recorder"), stop=add("button","Stop");
  stop.disabled=true;
  const status=add("p","Audio stays in this browser. Maximum session length is 90 seconds.");
  status.setAttribute("role","status");
  const player=add("audio","");player.controls=true;player.hidden=true;
  const save=add("a","Download session WAV");save.download="recitation.wav";save.hidden=true;
  const blindLabel=add("label","Blind Hifz test ");
  const blind=add("input","",blindLabel);blind.type="checkbox";
  let selection=component.data;
  const historyPanel=add("details","");add("summary","Device practice history",historyPanel);
  const summary=add("p","",historyPanel),drill=add("button","Drill my weakest verses",historyPanel);
  const exportBtn=add("button","Export history",historyPanel);
  const importLabel=add("label","Import history ",historyPanel),file=add("input","",importLabel);
  file.type="file";file.accept=".json,application/json";
  let history,queue=[],drillIndex=0,exportUrl;
  function refresh(){
    try{
      queue=history.queue();
      summary.textContent=history.read().length+" saved sessions on this browser. "+queue.slice(0,3).map(v=>
        v.s+":"+v.a+" · "+v.unresolved+" recall reviews · "+v.timing+" timing reviews "+
        Object.entries(v.flags).map(([label,n])=>label+" ×"+n).join(", ")).join(" | ");
      drill.disabled=!queue.length||!!mic||opening||closing;
    }catch{summary.textContent="Practice history unavailable in this browser.";drill.disabled=true}
  }
  drill.onclick=()=>{
    if(!queue.length||mic||opening||closing)return;
    clearRecording();
    const v=queue[drillIndex++%queue.length];
    selection={...component.data,surah:v.s,first:v.a,end:v.a};blind.checked=true;
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
  const report=add("section","");
  let reference,clearAudit,tracker,autoState;
  let sdk,engine,session,mic,prepared,interval,url,dead=false,opening=false,closing=false;
  const abort=new AbortController();
  try{history=practiceHistory(localStorage,component.data.profile,component.data.countsCsv.split(",").map(Number))}catch{}
  refresh();
  let wake,raw,rawCount,interrupted=false;
  let samples,count=0,analysed=0,previousRun=0;
  function clearRecording(){
    clearAudit?.();clearAudit=null;report.replaceChildren();
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
      const inspect=add("button","Inspect word timing and compare reciters",report);
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
      const wasBlind=blind.checked;
      inspect.onclick=()=>{
        clearAudit=renderAudit(report,result,samples.subarray(0,count),selection,add,abort.signal,autoState,wasBlind,saveFlag,raw.subarray(0,rawCount));
      };
    }catch{if(!dead)status.textContent="Recording interrupted. Please try again."}
    finally{await wake?.release().catch(()=>{});wake=null;blind.disabled=false;session?.dispose();session=null;prepared?.release();prepared=null;closing=false;start.disabled=dead;refresh();if(dead)await engine?.dispose();}
  }
  stop.onclick=()=>void finish();
  start.onclick=async()=>{
    if(opening||closing||dead)return;
    opening=true;start.disabled=true;
    try{
      if(!engine){
        status.textContent="Preparing the on-device phoneme listener…";
        sdk=await import("https://esm.sh/@tilawa/core@1.0.0-rc.0/web?bundle&deps=onnxruntime-web@1.30.0");
        if(dead)return;
        reference=await verifiedReference(abort.signal);
        engine=await sdk.createTilawa({reference,tier:"lite",threads:1,providers:["wasm"],recordEvidence:true,signal:abort.signal});
        if(dead)return;
        start.textContent="Start recording";status.textContent="Ready. Tap Start recording when you want to begin.";return;
      }
      tracker=continuousTracker(reference,selection);autoState=null;
      prepared=sdk.prepareMicrophone();
      interrupted=false;blind.disabled=true;drill.disabled=true;
      const capture=prepared;
      void navigator.wakeLock?.request("screen").then(lock=>{
        if(dead||closing||prepared!==capture)void lock.release();else wake=lock;
      }).catch(()=>{});
      clearRecording();samples=new Float32Array(16000*90);count=analysed=rawCount=0;raw=new Float32Array(samples.length);
      meter.frame(new Float32Array(640));previousRun=0;
      session=engine.startFreeRecitation();
      session.onAudio((pcm,ms)=>{
        if(dead)return;
        const at=Math.round(ms*16);
        if(at!==count||at>=samples.length)return;
        const part=pcm.subarray(0,samples.length-at);samples.set(part,at);count+=part.length;
        let duration;
        while(analysed+320<=count){
          duration=meter.frame(samples.subarray(analysed,analysed+320));analysed+=320;
          if(mode.value==="cal" && duration===0 && previousRun>0){
            meter.calibrate(previousRun);
            if(meter.acousticBeat())pace.textContent=meter.acousticBeat()+" ms / beat · choose Use calibrated vowels";
          }
          previousRun=duration;
        }
        if(mode.value==="auto"){
          const now=count/16;
          autoState=tracker.ingest(session.evidence(),samples.subarray(0,count));
          const {beat,active}=autoState;
          pace.textContent=beat?" Estimated beat: "+Math.round(beat)+" ms":" Learning your pace…";
          const fresh=active && now-active.last<=Math.max(240,(beat||100)*2) && duration>0;
          bar.max=fresh?active.site.range[1]:1;
          bar.value=fresh && beat?Math.min(bar.max,(now-active.start)/beat):0;
          const range=fresh?active.site.label==="Pause-dependent madd"?"2, 4 or 6":
            [...new Set(active.site.range)].join("–"):"";
          elapsed.textContent=fresh?active.site.ref+" · "+(blind.checked?"":active.site.arabic+" · ")+active.site.label+
            " · target "+range+(beat?" · about "+((now-active.start)/beat).toFixed(1)+" beats":""):
            "Waiting for a supported madd";
          const note=autoState.latest;
          guard.textContent=note && now-note.end<1800?(blind.checked?"":note.arabic+" · ")+timingAdvice(note):"";
          return;
        }
        if(duration!==undefined){
          const beat=mode.value==="tap"?meter.beat():meter.acousticBeat();bar.max=Number(target.value);
          bar.value=beat?Math.min(bar.max,duration/beat):0;
          guard.textContent=beat && target.value==="1" && duration>1.4*beat
            ?"This periodic sound exceeds 1.4 tapped beats. Repeat the isolated vowel and compare.":"";
          elapsed.textContent=beat?(duration/beat).toFixed(1)+" beats":Math.round(duration)+" ms";
        }
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
      status.textContent="Recording · tap Stop to keep the session.";
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
