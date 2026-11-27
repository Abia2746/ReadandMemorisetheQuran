// All time values are milliseconds on the 16 kHz audio tap's sample clock.
const SHORT_VOWELS="َُِ";
const LONG_VOWELS="اۦۥ";
function medianValue(xs){
  const a=[...xs].sort((x,y)=>x-y),i=Math.floor(a.length/2);
  return a.length?(a[i]+a[Math.floor((a.length-1)/2)])/2:null;
}

export function maddSites(ayah){
  const sites=new Map();
  for(let w=0;w<ayah.w.length;w++){
    const offset=ayah.o[w],phones=ayah.p.slice(offset,ayah.o[w+1]);
    for(const m of phones.matchAll(/(ا+|ۦ+|ۥ+)/gu)){
      const length=m[0].length,i=m.index,end=i+length,after=phones[end];
      let label,range;
      if(length===4&&after==="ء"){label="Muttasil";range=[4,5]}
      else if(length===4&&end===phones.length&&/^[أإءآ]/u.test(ayah.w[w+1]||"")){label="Munfasil";range=[4,5]}
      else if(length===6){label="Lazim";range=[6,6]}
      else if(length===2){
        if(w===ayah.w.length-1 && end===phones.length-1){
          label="Pause-dependent madd";range=[2,6];
        }else{
          // Exclude hamzah-preceded badal and pronominal silah from the tabi'i label.
          label=phones.slice(Math.max(0,i-2),i).includes("ء")||/[ۥۦ]/u.test(ayah.w[w])?"Two-unit reference madd":"Tabi‘i";
          range=[2,2];
        }
      }
      if(label)for(let j=i;j<end;j++)sites.set(offset+j,{label,range,word:w+1,arabic:ayah.w[w],onset:offset+i});
    }
  }
  return sites;
}

function frameRms(pcm,ms){
  const i=Math.round(ms*16),end=Math.min(pcm.length,i+160);
  if(i<0||end<=i)return 0;
  let sum=0;for(let j=i;j<end;j++)sum+=pcm[j]*pcm[j];
  return Math.sqrt(sum/(end-i));
}

// Expand an emission towards neighbouring sound, within hard word limits.
// Preserve a short decay tail and never cross the next supported emission.
export function playbackBounds(pcm,span,left,right){
  const floor=Math.max(0,Math.ceil(left/10)*10);
  const cap=Math.min(pcm.length/16,right);
  let start=Math.max(floor,span.start),end=Math.min(cap,span.end);
  const anchor=Math.max(frameRms(pcm,start),frameRms(pcm,Math.max(start,end-10)));
  const cutoff=Math.max(.0008,anchor*.04);
  while(start-10>=floor && start>span.start-160 && frameRms(pcm,start-10)>cutoff)start-=10;
  let last=end,quiet=0;
  for(let t=end;t+10<=Math.min(cap,span.end+450);t+=10){
    if(frameRms(pcm,t)>cutoff){last=t+10;quiet=0}
    else if(++quiet>=3)break;
  }
  end=Math.min(cap,last+10);
  return {start:Math.round(start),end:Math.round(end)};
}

function bandShape(pcm,ms){
  const i=Math.round(ms*16);
  if(i<0||i+160>pcm.length||frameRms(pcm,ms)<.004)return null;
  const bands=[0,0,0,0];const filters=[.09,.23,.48];
  let a=0,b=0,c=0;
  for(let j=i;j<i+160;j++){
    const v=pcm[j];a+=filters[0]*(v-a);b+=filters[1]*(v-b);c+=filters[2]*(v-c);
    bands[0]+=a*a;bands[1]+=(b-a)**2;bands[2]+=(c-b)**2;bands[3]+=(v-c)**2;
  }
  const total=bands.reduce((x,y)=>x+y,0);
  return bands.map(v=>Math.sqrt(v/total));
}

export function vowelNucleus(pcm,previous,vowel,next){
  // Bracket the vowel by independent decoded neighbours. Measure the acoustic
  // region similar to its anchor; the CTC spike width is not a vowel duration.
  const lo=previous.end,hi=next.start;
  const mid=Math.floor((vowel.start+vowel.end)/20)*10;
  const shape=bandShape(pcm,mid);
  if(!shape || mid<lo || mid+10>hi || hi-lo>600)return null;
  const close=t=>{
    const s=bandShape(pcm,t);
    return s && s.reduce((sum,v,i)=>sum+v*shape[i],0)>.982;
  };
  let a=mid,b=mid+10;
  while(a-10>=lo&&close(a-10))a-=10;
  while(b+10<=hi&&close(b))b+=10;
  const duration=b-a;
  return duration>=30 && duration<=500?{start:a,end:b,duration}:null;
}

export function continuousTracker(reference,selection){
  let expected="";const sites=new Map(),positions=new Map();
  for(const a of reference.ayahs.filter(a=>a.s===selection.surah&&a.a>=selection.first&&a.a<=selection.end)){
    for(const [i,site] of maddSites(a))sites.set(expected.length+i,{...site,ref:a.s+":"+a.a,onset:expected.length+site.onset});
    a.w.forEach((word,i)=>{
      for(let j=a.o[i];j<(a.o[i+1]??a.p.length);j++)positions.set(expected.length+j,{ref:a.s+":"+a.a,word:i+1,arabic:word});
    });
    expected+=a.p;
  }
  const recent=[],durations=[],notes=new Map(),pending=[];
  let cursor=-1,read=0,active=null,latest=null;
  function ingest(evidence,pcm){
    for(;read<evidence.length;read++){
      const chunk=evidence[read];
      for(const phone of chunk.phonemes){
        const event={p:phone.p,start:phone.start*chunk.frameMs,end:(phone.end+1)*chunk.frameMs,conf:phone.conf,index:-1};
        recent.push(event);if(recent.length>10)recent.shift();
        if(phone.conf>=.55 && cursor>=0 && expected[cursor+1]===phone.p)event.index=++cursor;
        else{
          cursor=-1;
          const tail=recent.slice(-5);
          if(tail.length>=3 && tail.every(e=>e.conf>=.55)){
            const pattern=tail.map(e=>e.p).join(""),at=expected.indexOf(pattern);
            if(at>=0 && at===expected.lastIndexOf(pattern)){
              cursor=at+pattern.length-1;
              tail.forEach((e,i)=>e.index=at+i);
            }
          }
        }
        const site=sites.get(cursor);
        if(site){
          if(!active || active.site.onset!==site.onset)active={site,start:event.start};
          active.last=event.end;
        }else active=null;
        if(recent.length<3)continue;
        const [prev,v,next]=recent.slice(-3);
        if(v.index<0||next.index!==v.index+1||prev.index!==v.index-1||
          !SHORT_VOWELS.includes(v.p)||LONG_VOWELS.includes(next.p)||Math.min(v.conf,next.conf,prev.conf)<.6)continue;
        const window=vowelNucleus(pcm,prev,v,next);if(!window)continue;
        const baseline=durations.length>=4?medianValue(durations):null;
        const ratio=baseline?window.duration/baseline:null;
        if(ratio && (ratio>1.4 || ratio<.55)){
          const pos=positions.get(v.index);
          // A short nucleus alone does not distinguish a stop from clipped capture.
          const pauseStart=next.end;
          const note={...pos,ratio,end:window.end,short:ratio<.55};
          if(note.short)pending.push({note,pauseStart,index:v.index});
          else {latest=note;notes.set(v.index,note)}
        }
        if(!baseline || (ratio>=.55&&ratio<=1.8)){
          durations.push(window.duration);if(durations.length>11)durations.shift();
        }
      }
    }
    while(pending.length && pcm.length/16>=pending[0].pauseStart+200){
      const item=pending.shift();
      let quiet=true;
      for(let i=2;i<20;i++)if(frameRms(pcm,item.pauseStart+i*10)>=.003){quiet=false;break}
      if(quiet){
        notes.set(item.index,item.note);
        if(!latest||latest.end<=item.note.end)latest=item.note;
      }
    }
    const last=recent.at(-1),pos=positions.get(cursor);
    return {position:pos && last?{...pos,end:last.end}:null,beat:durations.length>=4?medianValue(durations):null,active,notes,latest};
  }
  return {ingest};
}

function timingAdvice(note){
  return "Estimated short vowel "+note.ratio.toFixed(1)+"× your recent beat. "+
    (note.short?"Replay the ending. Check whether you completed the vowel before the stop.":
     "Repeat the word slowly, keeping the short vowel distinct from a madd.");
}
