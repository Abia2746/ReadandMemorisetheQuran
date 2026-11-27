// Values are PCM sample counts at the SDK audio tap's specified rate, 16 kHz.
export function paceMeter(){
  const taps=[];
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
  add("p","Tap four steady beats at your recitation pace. Practise one sustained vowel at a time. The meter follows periodic sound, including humming. Choose the exercise length yourself.");
  const tap=add("button","Tap one beat");
  const pace=add("span","Waiting for taps");
  const meter=paceMeter();
  tap.onclick=()=>{meter.tap(performance.now());const beat=meter.beat();pace.textContent=beat?Math.round(beat)+" ms / beat":"Keep tapping"};
  const label=add("label","Target ");
  const target=add("select","",label);
  for(const n of [2,4,6]){const opt=add("option",n+" beats",target);opt.value=String(n)}
  const bar=add("progress","");bar.max=2;bar.value=0;bar.setAttribute("aria-label","Elapsed beats");
  const elapsed=add("output","0.0 beats");elapsed.setAttribute("aria-live","off");
  const start=add("button","Prepare local recorder"), stop=add("button","Stop");
  stop.disabled=true;
  const status=add("p","Audio stays in this browser. Maximum session length is 90 seconds.");
  status.setAttribute("role","status");
  const player=add("audio","");player.controls=true;player.hidden=true;
  const save=add("a","Download session WAV");save.download="recitation.wav";save.hidden=true;
  let sdk,engine,session,mic,prepared,interval,url,dead=false,opening=false,closing=false;
  const abort=new AbortController();
  let samples,count=0,analysed=0;
  function clearRecording(){
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
      url=URL.createObjectURL(pcmWave(samples.subarray(0,count)));
      player.src=save.href=url;player.hidden=save.hidden=false;
      status.textContent="Recording ready for playback.";
    }catch{if(!dead)status.textContent="Recording interrupted. Please try again."}
    finally{session?.dispose();session=null;prepared?.release();prepared=null;closing=false;start.disabled=dead;}
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
        engine=await sdk.createTilawa({tier:"lite",threads:1,providers:["wasm"],recordEvidence:true,signal:abort.signal});
        if(dead){await engine.dispose();return}
        start.textContent="Start recording";status.textContent="Ready. Tap Start recording when you want to begin.";return;
      }
      prepared=sdk.prepareMicrophone();
      clearRecording();samples=new Float32Array(16000*90);count=analysed=0;
      meter.frame(new Float32Array(640));
      session=engine.startFreeRecitation();
      session.onAudio((pcm,ms)=>{
        if(dead)return;
        const at=Math.round(ms*16);
        if(at!==count||at>=samples.length)return;
        const part=pcm.subarray(0,samples.length-at);samples.set(part,at);count+=part.length;
        let duration;
        while(analysed+320<=count){duration=meter.frame(samples.subarray(analysed,analysed+320));analysed+=320}
        if(duration!==undefined){
          const beat=meter.beat();bar.max=Number(target.value);
          bar.value=beat?Math.min(bar.max,duration/beat):0;
          elapsed.textContent=beat?(duration/beat).toFixed(1)+" beats":Math.round(duration)+" ms";
        }
      });
      mic=await engine.listen(session,{prepared,vad:false,onError:()=>{if(mic)void finish()}});
      if(dead){await finish();return}
      interval=setTimeout(()=>void finish(),90000);stop.disabled=false;
      status.textContent="Recording · tap Stop to keep the session.";
    }catch{session?.dispose();session=null;prepared?.release();prepared=null;
      if(!dead)status.textContent="Recorder unavailable. Check microphone access and the model download, then retry."}
    finally{opening=false;start.disabled=dead||!!mic||closing;}
  };
  return ()=>{
    dead=true;abort.abort();clearTimeout(interval);clearRecording();prepared?.release();
    if(mic)void finish().finally(()=>engine?.dispose());
    else if(!opening){session?.dispose();void engine?.dispose()}
  };
}
