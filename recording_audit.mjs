// Reference phones and offsets are from the pinned Hafs ref-v2 asset.
// The Viterbi path estimates CTC emission locations, not articulator motion.
export function alignPhones(expected, evidence, inventory) {
  const ids=[...expected].map(p=>inventory.tokens.indexOf(p)+1);
  if(!ids.length || ids.includes(0) || ids.length>1400)return null;
  const rows=[];
  const ms=evidence[0]?.frameMs;
  for(const chunk of evidence){
    const p=chunk.posteriors;
    if(chunk.inventory!==inventory.id || chunk.frameMs!==ms || !p || p.startFrame!==rows.length)return null;
    for(let t=0;t<p.nFrames;t++){
      const row=new Map();
      for(let i=0;i<p.k;i++)row.set(p.ids[t*p.k+i],p.probs[t*p.k+i]);
      rows.push(row);
    }
  }
  const states=ids.length*2+1;
  if(!ms||!rows.length||rows.length*states>7000000)return null;
  const path=new Uint8Array(rows.length*states);
  let prev=new Float64Array(states).fill(-Infinity);prev[0]=0;
  for(let t=0;t<rows.length;t++){
    const row=rows[t],curr=new Float64Array(states).fill(-Infinity);
    for(let s=0;s<Math.min(states,2*t+3);s++){
      const phone=s%2?ids[(s-1)/2]:0;
      const prob=row.get(phone);
      if(!(prob>0))continue;
      let best=prev[s],step=0;
      if(s && prev[s-1]>best){best=prev[s-1];step=1}
      if(s>1 && phone && phone!==ids[(s-3)/2] && prev[s-2]>best){best=prev[s-2];step=2}
      curr[s]=best+Math.log(prob);path[t*states+s]=step;
    }
    prev=curr;
  }
  let state=prev[states-1]>prev[states-2]?states-1:states-2;
  if(!Number.isFinite(prev[state]))return null;
  const spans=ids.map(()=>({start:Infinity,end:0,peak:0}));
  for(let t=rows.length-1;t>=0;t--){
    if(state%2){
      const i=(state-1)/2,span=spans[i];
      span.start=t*ms;span.end=Math.max(span.end,(t+1)*ms);
      span.peak=Math.max(span.peak,rows[t].get(ids[i]));
    }
    state-=path[t*states+state];
  }
  return spans;
}

export function acousticWindow(samples){
  // 30 ms pre-emphasized Hamming frame; autocorrelation LPC envelope peaks.
  if(samples.length!==480)return null;
  const x=new Float64Array(480);let energy=0, low=0,high=0;
  for(let i=0;i<x.length;i++){
    energy+=samples[i]**2;
    x[i]=(samples[i]-.97*(samples[i-1]||0))*(.54-.46*Math.cos(2*Math.PI*i/479));
    if(i>0){const diff=(samples[i]-samples[i-1])**2;if(i<240)low+=diff;else high+=diff}
  }
  if(energy/480<.0001)return null;
  const order=16,r=new Float64Array(order+1);
  for(let k=0;k<=order;k++)for(let i=k;i<x.length;i++)r[k]+=x[i]*x[i-k];
  let a=[1],err=r[0];
  for(let k=1;k<=order;k++){
    let sum=r[k];for(let j=1;j<k;j++)sum+=a[j]*r[k-j];
    const reflection=-sum/err;if(!Number.isFinite(reflection)||Math.abs(reflection)>=1)return null;
    const b=[1];for(let j=1;j<k;j++)b[j]=a[j]+reflection*a[k-j];
    b.push(reflection);a=b;err*=1-reflection**2;
  }
  const peaks=[];let prev=0,before=0;
  for(let f=100;f<=4000;f+=25){
    let re=0,im=0;for(let k=0;k<a.length;k++){
      const w=2*Math.PI*f*k/16000;re+=a[k]*Math.cos(w);im+=a[k]*Math.sin(w);
    }
    const v=1/(re*re+im*im);
    if(prev>before&&prev>v&&f>=250)peaks.push(f-25);
    before=prev;prev=v;
  }
  // DFT band energy uses un-pre-emphasized samples and the same window.
  // Estimate a local harmonic spacing across adult and higher pitched voices.
  // A harmonic energy fraction is descriptive and does not prove nasal airflow.
  let best=0,lag=0;
  for(let k=27;k<=228;k++){
    let cross=0,a=0,b=0;
    for(let i=k;i<480;i++){cross+=samples[i]*samples[i-k];a+=samples[i]**2;b+=samples[i-k]**2}
    const corr=cross/Math.sqrt(a*b||1);
    if(corr>best+.015){best=corr;lag=k}
  }
  const f0=best>.75?16000/lag:null;
  let band=0,total=0,lowerBand=0,upperBand=0,harmonic=0;
  for(let k=1;k<=240;k++){
    let re=0,im=0;
    for(let i=0;i<480;i++){
      const v=samples[i]*(.5-.5*Math.cos(2*Math.PI*i/479)),w=2*Math.PI*k*i/480;
      re+=v*Math.cos(w);im+=v*Math.sin(w);
    }
    const power=re*re+im*im;total+=power;
    const hz=k*16000/480;
    if(f0 && Math.abs(hz-f0)<=Math.max(40,.15*f0))harmonic+=power;
    if(hz>=500 && hz<1500)lowerBand+=power;
    if(hz>=1500 && hz<2500)upperBand+=power;
    if(k*16000/480>=250&&k*16000/480<=300)band+=power;
  }
  return {f0,harmonicFraction:f0&&total?harmonic/total:null,peaks:peaks.slice(0,2),nasalBandFraction:total?band/total:0,
    bandBalanceDb:10*Math.log10((upperBand+1e-12)/(lowerBand+1e-12)),
    releaseChangeDb:10*Math.log10((high+1e-12)/(low+1e-12))};
}

export function referenceTags(text,phones,nextText,previousText="",pause="",previousPhones=""){
  const tags=[];
  for(const m of phones.matchAll(/(ا+|ۦ+|ۥ+)/gu))tags.push("Reference long-vowel units: "+m[0].length);
  if(phones.match(/(ا|ۦ|ۥ){4,}ء/u))tags.push("Madd muttaṣil candidate · reference profile 4 beats");
  if(/(ا|ۦ|ۥ){4}$/u.test(phones) && /^[أإءآ]/u.test(nextText||""))tags.push("Madd munfaṣil candidate · reference profile 4 beats");
  if(/(ا{6}|ۦ{6}|ۥ{6})/u.test(phones))tags.push("Six-unit madd in reference");
  if(/[نم][\u064b-\u0652]*ّ/u.test(text))tags.push("Doubled nūn/mīm · ghunnah target 2 beats");
  if(/[قطبجد][ْۡ]/u.test(text))tags.push("Written sukūn · qalqalah site");
  if(/[خصضغطقظ]/u.test(text))tags.push("Contains a letter of istiʿlāʾ");
  const next=(nextText||"").replace(/^[^ء-يٱ]+/u,"")[0];
  if(next && /(?:ن[ْۡ]?|[ًٌٍ]ا?)[\sۖ-ۜ]*$/u.test(text)){
    if(next==="ب")tags.push("Connected reading · iqlāb");
    else if("يرملون".includes(next))tags.push("Connected reading · idghām");
    else if("ءأإهعحغخ".includes(next))tags.push("Connected reading · iẓhār");
    else if("صذثكجشقسدطزفتضظ".includes(next))tags.push("Connected reading · ikhfāʾ");
  }
  const letters=word=>[...(word||"").replace(/ـ/gu,"").matchAll(/([ء-غف-يٱ])([\p{M}]*)/gu)].map(m=>({base:m[1],marks:m[2]}));
  const chars=letters(text),following=letters(nextText);
  const final=chars.at(-1);
  for(let i=0;i<chars.length;i++){
    const {base,marks}=chars[i],nextLetter=chars[i+1]?.base||following[0]?.base;
    if(base==="م"&&!/[ً-ِّٰۥ]/u.test(marks)&&nextLetter && nextLetter!=="ٱ"){
      tags.push(nextLetter==="ب"?"Mīm sākinah · ikhfāʾ shafawī":nextLetter==="م"?
        "Mīm sākinah · idghām shafawī":"Mīm sākinah · iẓhār shafawī");
    }
    if(base==="ر"){
      if(/[ٍِ]/u.test(marks))tags.push("Connected rāʾ · light");
      else if(/[ًٌَُ]/u.test(marks))tags.push("Connected rāʾ · heavy");
      else if(i>0){
        const before=chars[i-1];
        if(/[َُ]/u.test(before.marks))tags.push("Sākin rāʾ · heavy");
        else if(/ِ/u.test(before.marks) && before.base!=="ٱ"){
          if(nextLetter==="ق"&&/[ٍِ]/u.test(chars[i+1]?.marks||""))tags.push("Sākin rāʾ · review permitted variants");
          else tags.push(chars[i+1]&&"خصضغطقظ".includes(nextLetter)?"Sākin rāʾ · heavy":"Sākin rāʾ · light");
        }
      }
    }
  }
  const skeleton=chars.map(c=>c.base).join("");
  const allah=skeleton.match(/(?:[اٱ]لله|لله)$/u);
  if(allah){
    const contracted=allah[0]==="لله";
    const prior=contracted?chars[allah.index]:chars.slice(0,allah.index).at(-1)||letters(previousText).at(-1);
    const precedingPhone=!contracted && !allah.index?previousPhones.at(-1):null;
    if(!prior||/[ًٌَُ]/u.test(prior.marks)||precedingPhone&&"اۥَُ".includes(precedingPhone))tags.push("Lām in Allāh · heavy");
    else if(/[ٍِ]/u.test(prior.marks)||precedingPhone&&"ۦِ".includes(precedingPhone))tags.push("Lām in Allāh · light");
  }else{
    const article=skeleton.match(/^(?:[وف])?(?:[بك])?[ٱا]ل(.)/u);
    if(article)tags.push("تثدذرزسشصضطظلن".includes(article[1])?"Solar lām · assimilate":"Lunar lām · pronounce clearly");
  }
  if(final?.base==="ة")tags.push("Stopping · tāʾ marbūṭah becomes hāʾ");
  else if(/ً/u.test(chars.slice(-2).map(c=>c.marks).join("")) && /اا$/u.test(pause))tags.push("Stopping · madd ʿiwaḍ · 2 beats");
  else if(/(?:اا|ۥۥ|ۦۦ)[^َُِاۦۥ]$/u.test(pause) && /[ٌٍَُِ]/u.test(final?.marks||""))
    tags.push("Stopping · madd ʿāriḍ li-s-sukūn · 2, 4 or 6 beats");
  else if(/[ٌٍَُِ]/u.test(final?.marks||"") && !/[اوىي]/u.test(final.base))tags.push("Stopping · final sukūn");
  return tags;
}

export function husaryClip(payload,ref,index,count){
  const audio=payload?.audio_file;
  const [surah]=ref.split(":");
  const expected="https://download.quranicaudio.com/qdc/khalil_al_husary/murattal/"+surah+".mp3";
  if(audio?.audio_url!==expected||String(audio.chapter_id)!==surah)return null;
  const verse=audio.timestamps?.find(v=>v.verse_key===ref);
  const rows=verse?.segments;
  if(!Array.isArray(rows)||rows.length!==count)return null;
  let last=verse.timestamp_from;
  for(const [i,r] of rows.entries()){
    if(!Array.isArray(r)||r[0]!==i+1||!Number.isFinite(r[1])||!Number.isFinite(r[2])||
       r[1]<last||r[2]<=r[1]||r[2]>verse.timestamp_to)return null;
    last=r[2];
  }
  const row=rows[index];return row?{url:expected,start:row[1],end:row[2]}:null;
}

export function passageAudit(reference,selection,evidence,pcm){
  const ayahs=reference.ayahs.filter(a=>a.s===selection.surah && a.a>=selection.first && a.a<=selection.end);
  const words=[];let expected="";
  for(const a of ayahs){
    for(let i=0;i<a.w.length;i++){
      const phones=a.p.slice(a.o[i],a.o[i+1]??a.p.length);
      words.push({ayah:a.a,ref:a.s+":"+a.a,index:i,count:a.w.length,arabic:a.w[i],phones,
        start:expected.length,pause:a.iso[i],tags:referenceTags(a.w[i],phones,a.w[i+1],a.w[i-1],a.iso[i],i?a.p.slice(a.o[i-1],a.o[i]):"")});
      expected+=phones;
    }
  }
  // For a whole selection ending at a pause, require a free-decoded phone
  // suffix AND measured quiet after it. Never award a duration or waqf grade.
  const finalWord=words.at(-1);
  if(pcm && finalWord?.pause){
    const decoded=evidence.flatMap(e=>e.phonemes.map(p=>({...p,endMs:(p.end+1)*e.frameMs})));
    const tail=decoded.slice(-finalWord.pause.length);
    const last=tail.at(-1);
    if(last && tail.map(p=>p.p).join("")===finalWord.pause && tail.every(p=>p.conf>=.55)){
      const begin=Math.ceil(last.endMs/10)*10,limit=Math.min(begin+650,pcm.length/16);
      let quiet=0;
      for(let t=begin;t+10<=limit;t+=10){
        let energy=0;for(let j=t*16;j<(t+10)*16;j++)energy+=pcm[j]**2;
        quiet=energy/160<.000016?quiet+10:0;
        if(quiet>=150){
          expected=expected.slice(0,finalWord.start)+finalWord.pause;
          finalWord.connected=finalWord.phones;finalWord.phones=finalWord.pause;
          finalWord.stopCandidate=true;break;
        }
      }
    }
  }
  const spans=alignPhones(expected,evidence,reference.inventory);
  if(!spans)return {words,matched:0,aligned:false};
  const decoded=evidence.flatMap(e=>e.phonemes.map(p=>({p:p.p,ms:p.start*e.frameMs,end:(p.end+1)*e.frameMs})));
  let matched=0;
  for(const w of words){
    const phones=spans.slice(w.start,w.start+w.phones.length);
    if(!phones.length)continue;
    const start=phones[0].start,end=phones.at(-1).end;
    const observed=decoded.filter(p=>p.end>start&&p.ms<end).map(p=>p.p).join("");
    if(observed!==w.phones || phones.some(p=>p.peak<.5))continue;
    w.interval={start,end};w.phoneSpans=phones;matched++;
    if(w.stopCandidate)w.pauseSupported=true;
  }
  return {words,matched,aligned:true};
}

async function verifiedReference(signal){
  const response=await fetch("https://tilawa.dev/v1/reference/ref-v2.json",{signal});
  if(!response.ok)throw Error("Reference unavailable");
  const data=await response.arrayBuffer();
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",data)),v=>v.toString(16).padStart(2,"0")).join("");
  if(hash!=="f236384ea91e81ad554ba2777bc4073c3ff41e34120343a8a474571c577b7727")throw Error("Reference integrity check failed");
  return JSON.parse(new TextDecoder().decode(data));
}

export function relativeFeature(value,values){
  if(!Number.isFinite(value)||values.length<3)return null;
  const sorted=values.filter(Number.isFinite).sort((a,b)=>a-b);
  if(sorted.length<3)return null;
  return value-sorted[Math.floor(sorted.length/2)];
}

function speakerReferences(words,pcm){
  const groups=new Map();
  for(const w of words){
    if(!w.interval)continue;
    for(const [i,p] of [...w.phones].entries()){
      if(!"َُِ".includes(p)||!w.phones[i-1]||!"ستكدبف".includes(w.phones[i-1]))continue;
      const group=groups.get(p)||[];if(group.length>=7)continue;
      const span=w.phoneSpans[i],mid=Math.round((span.start+span.end)*8);
      if(mid<240||mid+240>pcm.length)continue;
      const feature=acousticWindow(pcm.subarray(mid-240,mid+240));
      if(feature && feature.peaks.length===2){group.push(feature);groups.set(p,group)}
    }
  }
  return groups;
}

function renderAudit(panel,result,pcm,selection,add,signal,timing,blind=false,saveFlag=null,original=pcm,technical=panel,hintsByWord=new Map()){
  let baseline;
  panel.replaceChildren();
  add("h3","Recitation summary",panel);
  const strip=add("div","",panel);strip.className="recite-summary";
  add("span","Words matched · "+result.matched+"/"+result.words.length,strip);
  add("span",timing?.beat?"Reading pace · "+Math.round(timing.beat)+" ms/count":"Reading pace · still learning",strip);
  const card=add("section","",panel);card.className="recite-card";card.hidden=true;
  const cards=new Map();
  add("p",result.matched?"Tap a word to listen and practise.":"The recording was unclear. Try one ayah in a quieter spot.",panel);
  add("p","Hafs reference phones from quran-transcript via Tilawa ref-v2. Timing and resonance are practice cues.",technical);
  const source=add("a","Reference · Tanzil Uthmani text",technical);
  source.href="https://tanzil.net";source.target="_blank";source.rel="noopener";
  let clipUrl,active,context,sourceNode,generation=0;
  const chapter=fetch("https://api.quran.com/api/v4/chapter_recitations/6/"+selection.surah+"?segments=true",{signal})
    .then(r=>r.ok?r.json():null).catch(()=>null);
  function clear(){
    generation++;
    if(sourceNode){try{sourceNode.stop()}catch{}sourceNode=null}
    active?.pause();if(active){active.removeAttribute("src");active.load();active=null}
    if(clipUrl){URL.revokeObjectURL(clipUrl);clipUrl=null}
  }
  signal.addEventListener("abort",clear,{once:true});
  for(const [wi,w] of result.words.entries()){
    const timingCue=[...(timing?.notes.values()||[])].some(n=>n.ref===w.ref&&n.word===w.index+1);
    if(blind && (w.interval&&!timingCue || !result.aligned))continue;
    const row=add("details","",technical);
    add("summary",w.ref+" · "+(w.index+1)+" · "+w.arabic,row);
    add("p","Connected phones: "+(w.connected??w.phones)+" · Isolated form: "+w.pause,row);
    if(w.pauseSupported)add("p","The final phone sequence supports the isolated form, followed by quiet audio.",row);
    if(w.tags.length)add("p",w.tags.join(" · "),row);
    if(saveFlag){
      const choose=add("select","",row);choose.setAttribute("aria-label","Practice focus");
      for(const skill of ["recall","timing","madd","ghunnah","qalqalah","articulation","waqf"])add("option",skill,choose);
      const flag=add("button","Save practice focus",row);
      flag.onclick=()=>{try{saveFlag(w,choose.value);flag.textContent="Saved practice focus"}catch{flag.textContent="Device storage unavailable"}};
    }
    const face=add("div","",card);face.hidden=true;cards.set(w,face);
    add("h4",w.arabic,face);
    const hints=hintsByWord.get(w.ref+":"+(w.index+1))||[];
    const tips=[...new Set(hints.map(h=>h.tip))];
    for(const tip of tips.length?tips:["Listen once, then repeat the word at a comfortable pace."])add("p",tip,face);
    if(!w.interval)add("p","This word could not be matched clearly.",face);
    if(timingCue)add("p","Listen again to the length of the short vowel.",face);
    const yours=add("button","▶ Your Voice",face);yours.disabled=!w.interval;
    const master=add("button","▶ Sheikh Al-Husary",face);master.disabled=true;
    const note=add("p","",face);
    let start,end;
    if(w.interval){
      const prev=result.words[wi-1]?.interval,next=result.words[wi+1]?.interval;
      const left=prev?(prev.end+w.interval.start)/2:wi===0?0:w.interval.start;
      const right=next?(next.start+w.interval.end)/2:wi===result.words.length-1?pcm.length/16:w.interval.end;
      ({start,end}=playbackBounds(pcm,w.interval,left,right));
      add("p","Estimated learner window "+start+"–"+end+" ms.",row);
    }
    function play(url){
      const audio=new Audio(url);active=audio;
      void audio.play().catch(()=>{if(!signal.aborted)note.textContent="Playback unavailable."});
    }
    yours.onclick=()=>{
      clear();clipUrl=URL.createObjectURL(pcmWave(original.subarray(start*16,end*16)));play(clipUrl);
    };
    void chapter.then(payload=>{
      if(signal.aborted)return;
      const ref=husaryClip(payload,w.ref,w.index,w.count);
      if(!ref){note.textContent="Source-matched Al-Husary timing unavailable.";return}
      add("p","Al-Husary · "+ref.start+"–"+ref.end+" ms",row);
      master.disabled=false;
      master.onclick=async()=>{
        clear();const ticket=generation;
        try{
          // Bound chapter decoding on phones. Longer chapters use explicit
          // seeking plus an end guard, independent of media fragment support.
          const length=payload.audio_file.timestamps.at(-1)?.timestamp_to;
          if(length>0 && length<=90000){
            const Ctx=window.AudioContext||window.webkitAudioContext;
            context??=new Ctx();await context.resume();
            const response=await fetch(ref.url,{signal});
            const size=Number(response.headers.get("content-length"));
            if(!response.ok||!(size>0&&size<=4000000))throw Error("Use streaming playback");
            const buffer=await context.decodeAudioData(await response.arrayBuffer());
            if(signal.aborted||generation!==ticket)return;
            sourceNode=startBufferSegment(context,buffer,ref.start,ref.end);return;
          }
        }catch{if(signal.aborted||generation!==ticket)return}
        const audio=new Audio(ref.url);active=audio;
        audio.onloadedmetadata=()=>{if(active===audio)audio.currentTime=ref.start/1000};
        audio.ontimeupdate=()=>{if(audio.currentTime>=ref.end/1000)audio.pause()};
        audio.onseeked=()=>{if(active===audio)void audio.play().catch(()=>{note.textContent="Tap the player to hear this segment.";audio.controls=true;face.appendChild(audio)})};
        if(!ref.start){void audio.play().catch(()=>{audio.controls=true;face.appendChild(audio)})}
      };
    });
    row.ontoggle=()=>{
      if(!w.interval||!row.open||!row.ontoggle)return;
      row.ontoggle=null;
      // Calculate only on expansion, and only inside the aligned word.
      for(const note of timing?.notes.values()||[]){
        if(note.ref===w.ref && note.word===w.index+1)add("p","Timing practice (lahn khafi review): "+timingAdvice(note),row);
      }
      if(w.tags.some(t=>t.includes("ghunnah")||t.includes("ikhfā")||t.includes("iqlāb")))
        add("p","Ghunnah practice: listen to the nasal resonance in the reference, then repeat at your own pace. Low-band energy alone cannot identify ghunnah.",row);
      if(w.tags.some(t=>t.includes("qalqalah")))
        add("p","Qalqalah practice: compare the consonant release, listening for an extra vowel after it. A burst can also come from microphone noise.",row);
      if(w.tags.some(t=>t.includes("istiʿlāʾ")))
        add("p","Heavy-letter practice: compare the letter and its following vowel with Al-Husary. The displayed vowel resonance peaks depend on your voice and neighbouring sounds.",row);
      baseline??=speakerReferences(result.words,pcm);
      for(const [i,phone] of [...w.phones].entries()){
        const s=w.phoneSpans[i],mid=Math.round((s.start+s.end)*8);
        if(mid-240<0||mid+240>pcm.length)continue;
        const feature=acousticWindow(pcm.subarray(mid-240,mid+240));
        if(!feature)continue;
        const numbers=[];
        if("َُِاۥۦ".includes(phone)&&feature.peaks.length===2)numbers.push("LPC peaks "+feature.peaks.join(" / ")+" Hz");
        const preceding=w.phones[i-1];
        if(preceding && "صسطتقكضد".includes(preceding) && "َُِ".includes(phone) && feature.peaks.length===2){
          const group=baseline.get(phone)||[];
          const delta=relativeFeature(feature.peaks[1],group.map(f=>f.peaks[1]));
          if(delta!==null)numbers.push("F2 candidate "+Math.round(delta)+" Hz relative to your light-context "+phone+" vowel median");
          numbers.push("upper/lower vowel-band balance "+feature.bandBalanceDb.toFixed(1)+" dB");
          add("p","Listen to "+preceding+" and the vowel immediately after it in both recordings. Keep the same vowel while comparing its resonance.",row);
        }
        if("نمں۾".includes(phone)){
          const ordinary=[...baseline.values()].flat().filter(f=>f.f0&&feature.f0&&Math.abs(Math.log2(f.f0/feature.f0))<.5).map(f=>f.harmonicFraction);
          const delta=relativeFeature(feature.harmonicFraction,ordinary);
          numbers.push(delta===null?"Insufficient same-speaker baseline for low-band comparison":
            "Pitch-centred low harmonic energy "+(100*delta).toFixed(1)+" percentage points relative to your oral vowels");
        }
        if("قطبجد".includes(phone))numbers.push("high-frequency energy change "+feature.releaseChangeDb.toFixed(1)+" dB");
        if(numbers.length)add("p",phone+" · "+s.start+" ms · "+numbers.join(" · "),row);
      }
    };
  }
  const dispose=()=>{signal.removeEventListener("abort",clear);clear();if(context)void context.close().catch(()=>{});panel.replaceChildren()};
  let shown;
  dispose.show=w=>{
    clear();if(shown)shown.hidden=true;shown=cards.get(w);
    if(shown){card.hidden=false;shown.hidden=false;card.scrollIntoView({block:"nearest"})}
  };
  return dispose;
}
