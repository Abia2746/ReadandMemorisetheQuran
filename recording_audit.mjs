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
  let band=0,total=0,lowerBand=0,upperBand=0;
  for(let k=1;k<=240;k++){
    let re=0,im=0;
    for(let i=0;i<480;i++){
      const v=samples[i]*(.5-.5*Math.cos(2*Math.PI*i/479)),w=2*Math.PI*k*i/480;
      re+=v*Math.cos(w);im+=v*Math.sin(w);
    }
    const power=re*re+im*im;total+=power;
    const hz=k*16000/480;
    if(hz>=500 && hz<1500)lowerBand+=power;
    if(hz>=1500 && hz<2500)upperBand+=power;
    if(k*16000/480>=250&&k*16000/480<=300)band+=power;
  }
  return {peaks:peaks.slice(0,2),nasalBandFraction:total?band/total:0,
    bandBalanceDb:10*Math.log10((upperBand+1e-12)/(lowerBand+1e-12)),
    releaseChangeDb:10*Math.log10((high+1e-12)/(low+1e-12))};
}

export function referenceTags(text,phones,nextText){
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

export function passageAudit(reference,selection,evidence){
  const ayahs=reference.ayahs.filter(a=>a.s===selection.surah && a.a>=selection.first && a.a<=selection.end);
  const words=[];let expected="";
  for(const a of ayahs){
    for(let i=0;i<a.w.length;i++){
      const phones=a.p.slice(a.o[i],a.o[i+1]??a.p.length);
      words.push({ayah:a.a,ref:a.s+":"+a.a,index:i,count:a.w.length,arabic:a.w[i],phones,
        start:expected.length,pause:a.iso[i],tags:referenceTags(a.w[i],phones,a.w[i+1])});
      expected+=phones;
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

function renderAudit(panel,result,pcm,selection,add,signal,timing){
  panel.replaceChildren();
  add("h4","Recording evidence",panel);
  add("p","Hifz · "+result.matched+" of "+result.words.length+" word sequences supported by the free phoneme decoder and forced path. Madd, ghunnah and articulation grades require independent calibration.",panel);
  const source=add("a","Reference · Tanzil Uthmani text",panel);
  source.href="https://tanzil.net";source.target="_blank";source.rel="noopener";
  add("p","Hafs reference phones from quran-transcript via Tilawa ref-v2. Times indicate model frames. A weak match or a different permissible reading may leave a word unresolved.",panel);
  let clipUrl,active;
  const chapter=fetch("https://api.quran.com/api/v4/chapter_recitations/6/"+selection.surah+"?segments=true",{signal})
    .then(r=>r.ok?r.json():null).catch(()=>null);
  function clear(){
    active?.pause();if(active){active.removeAttribute("src");active.load();active=null}
    if(clipUrl){URL.revokeObjectURL(clipUrl);clipUrl=null}
  }
  signal.addEventListener("abort",clear,{once:true});
  for(const [wi,w] of result.words.entries()){
    const row=add("details","",panel);
    add("summary",w.ref+" · "+(w.index+1)+" · "+w.arabic,row);
    add("p","Connected phones: "+w.phones+" · Isolated form: "+w.pause,row);
    if(w.tags.length)add("p",w.tags.join(" · "),row);
    if(!w.interval){
      add("p","Word or vowel identity (lahn jali review): Listen for the same letters and vowels in sequence. This recording did not resolve the word clearly enough to identify an error.",row);
      continue;
    }
    // Split the gap only between adjacent supported words. Do not take time
    // from an unresolved neighbour. The last word can extend into its decay.
    const prev=result.words[wi-1]?.interval,next=result.words[wi+1]?.interval;
    const left=prev?(prev.end+w.interval.start)/2:wi===0?0:w.interval.start;
    const right=next?(next.start+w.interval.end)/2:wi===result.words.length-1?pcm.length/16:w.interval.end;
    const {start,end}=playbackBounds(pcm,w.interval,left,right);
    add("p","Estimated learner window "+start+"–"+end+" ms.",row);
    const yours=add("button","Hear my word",row);
    const master=add("button","Hear Al-Husary",row);master.disabled=true;
    const note=add("p","",row);
    function play(url){
      const audio=new Audio(url);active=audio;
      void audio.play().catch(()=>{if(!signal.aborted)note.textContent="Playback unavailable."});
    }
    yours.onclick=()=>{
      clear();clipUrl=URL.createObjectURL(pcmWave(pcm.subarray(start*16,end*16)));play(clipUrl);
    };
    void chapter.then(payload=>{
      if(signal.aborted)return;
      const ref=husaryClip(payload,w.ref,w.index,w.count);
      if(!ref){note.textContent="Source-matched Al-Husary timing unavailable.";return}
      note.textContent="Al-Husary · source timing "+ref.start+"–"+ref.end+" ms in chapter audio.";
      master.disabled=false;
      master.onclick=()=>{clear();play(ref.url+"#t="+ref.start/1000+","+ref.end/1000)};
    });
    row.ontoggle=()=>{
      if(!row.open||!row.ontoggle)return;
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
      for(const [i,phone] of [...w.phones].entries()){
        const s=w.phoneSpans[i],mid=Math.round((s.start+s.end)*8);
        if(mid-240<0||mid+240>pcm.length)continue;
        const feature=acousticWindow(pcm.subarray(mid-240,mid+240));
        if(!feature)continue;
        const numbers=[];
        if("َُِاۥۦ".includes(phone)&&feature.peaks.length===2)numbers.push("LPC peaks "+feature.peaks.join(" / ")+" Hz");
        const preceding=w.phones[i-1];
        if(preceding && "صسطتقكضد".includes(preceding) && "َُِ".includes(phone) && feature.peaks.length===2){
          numbers.push("upper/lower vowel-band balance "+feature.bandBalanceDb.toFixed(1)+" dB");
          add("p","Listen to "+preceding+" and the vowel immediately after it in both recordings. Keep the same vowel while comparing its resonance.",row);
        }
        if("نمں۾".includes(phone))numbers.push("250–300 Hz energy "+(100*feature.nasalBandFraction).toFixed(1)+"%");
        if("قطبجد".includes(phone))numbers.push("high-frequency energy change "+feature.releaseChangeDb.toFixed(1)+" dB");
        if(numbers.length)add("p",phone+" · "+s.start+" ms · "+numbers.join(" · "),row);
      }
    };
  }
  return ()=>{signal.removeEventListener("abort",clear);clear();panel.replaceChildren()};
}
