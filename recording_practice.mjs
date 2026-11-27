// Device-local summaries contain verse coordinates and practice counts only.
// Use the app's canonical surah counts for imports and drill navigation.
export function parseHistory(text,counts){
  if(typeof text!=="string"||text.length>1_000_000)throw Error("History file is too large.");
  const data=JSON.parse(text);
  if(data?.version!==1||!Array.isArray(data.sessions)||data.sessions.length>500)throw Error("Unsupported history file.");
  return data.sessions.map(s=>{
    if(!/^[a-f0-9-]{36}$/i.test(s.id)||!Number.isSafeInteger(s.time)||s.time<0||!Array.isArray(s.verses)||s.verses.length<1||s.verses.length>10)throw Error("Invalid practice session.");
    const verses=s.verses.map(v=>{
      if(!Number.isInteger(v.s)||!Number.isInteger(v.a)||v.s<1||v.s>114||v.a<1||v.a>counts[v.s-1])throw Error("Unknown verse.");
      const row={s:v.s,a:v.a};
      for(const k of ["supported","unresolved","timing"]){
        if(!Number.isInteger(v[k])||v[k]<0||v[k]>1000)throw Error("Invalid practice counts.");
        row[k]=v[k];
      }
      const flags=v.flags??[];
      if(!Array.isArray(flags)||flags.length>300||flags.some(f=>!Number.isInteger(f.word)||f.word<1||f.word>300||
          !["recall","timing","ghunnah","qalqalah","madd","articulation","waqf"].includes(f.skill)))throw Error("Invalid review flag.");
      row.flags=flags.map(f=>({word:f.word,skill:f.skill}));
      return row;
    });
    return {id:s.id,time:s.time,verses};
  });
}

export function practiceHistory(storage,profile,counts){
  const key="am:recording-history:v1:"+profile;
  const read=()=>parseHistory(storage.getItem(key)||'{"version":1,"sessions":[]}',counts);
  function merge(incoming){
    const rows=new Map(read().map(s=>[s.id,s]));
    for(const s of parseHistory(incoming,counts))if(!rows.has(s.id))rows.set(s.id,s);
    const sessions=[...rows.values()].sort((a,b)=>b.time-a.time||a.id.localeCompare(b.id)).slice(0,500);
    storage.setItem(key,JSON.stringify({version:1,sessions}));
  }
  function flag(id,s,a,word,skill){
    const sessions=read(),verse=sessions.find(x=>x.id===id)?.verses.find(v=>v.s===s&&v.a===a);
    if(!verse)return;
    if(!verse.flags.some(f=>f.word===word&&f.skill===skill))verse.flags.push({word,skill});
    const text=JSON.stringify({version:1,sessions});
    parseHistory(text,counts);storage.setItem(key,text);
  }
  function queue(){
    const scores=new Map();
    for(const session of read())for(const v of session.verses){
      const key=v.s+":"+v.a;
      const entry=scores.get(key)||{s:v.s,a:v.a,unresolved:0,timing:0,flags:{}};
      entry.unresolved+=Number(v.unresolved>0);entry.timing+=Number(v.timing>0);
      for(const f of v.flags){
        const label="word "+f.word+" · "+f.skill;
        entry.flags[label]=(entry.flags[label]||0)+1;
      }
      scores.set(key,entry);
    }
    const priority=v=>v.unresolved+v.timing+Object.values(v.flags).reduce((sum,count)=>sum+count,0);
    return [...scores.values()].filter(priority).sort((a,b)=>priority(b)-priority(a));
  }
  return {read,merge,queue,flag};
}

export function microphoneConditioner(){
  let floor=.0001,gain=1,total=0;
  const history=[];
  return function apply(pcm){
    const out=new Float32Array(pcm.length);
    for(let i=0;i<pcm.length;i+=160){
      const end=Math.min(i+160,pcm.length);
      let power=0,peak=0;
      for(let j=i;j<end;j++){power+=pcm[j]**2;peak=Math.max(peak,Math.abs(pcm[j]))}
      const rms=Math.sqrt(power/(end-i));
      history.push(rms);if(history.length>120)history.shift();
      if(history.length>=3){
        const sorted=[...history].sort((a,b)=>a-b);
        // Cap initial ambient estimate so speech starting on the first frame survives.
        const candidate=Math.min(.009,sorted[Math.floor(sorted.length*.15)]);
        floor=Math.max(.00006,Math.min(total<4800?.001:.009,candidate));
      }
      const snr=rms/floor;
      const targetGain=Math.max(.35,Math.min(8,.075/Math.max(.001,rms)));
      gain+=.12*(targetGain-gain);
      const gate=total<4800?1:Math.min(1,Math.max(.18,(snr-.8)/1.5));
      const scale=Math.min(gain*gate,.98/Math.max(.001,peak));
      for(let j=i;j<end;j++)out[j]=pcm[j]*scale;
      total+=end-i;
    }
    return out;
  };
}

export function startBufferSegment(ctx,buffer,startMs,endMs){
  const begin=startMs/1000,end=endMs/1000;
  if(!Number.isFinite(begin)||!Number.isFinite(end)||begin<0||end<=begin||end>buffer.duration+.025)throw Error("Invalid reference interval");
  const source=ctx.createBufferSource();source.buffer=buffer;source.connect(ctx.destination);
  source.start(0,begin,Math.min(end,buffer.duration)-begin);return source;
}
