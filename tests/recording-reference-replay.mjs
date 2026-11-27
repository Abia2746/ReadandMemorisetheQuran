// Offline integration runner: supply a locally installed @tilawa/core Node entry,
// pinned reference JSON, unpacked lite model directory and a mono WAV of 1:1.
// No learner audio leaves this process.
import {readFile} from "node:fs/promises";
import {createHash} from "node:crypto";
import path from "node:path";
import {pathToFileURL} from "node:url";
import assert from "node:assert/strict";
import {passageAudit} from "../recording_audit.mjs";

import {continuousTracker,playbackBounds} from "../recording_tracker.mjs";

const [sdkPath,refPath,modelDir,wavPath]=process.argv.slice(2);
if(!wavPath)throw Error("Supply SDK entry, ref-v2.json, model directory and Al-Fatihah 1:1 WAV paths.");
async function pinned(file,expected){
  const bytes=await readFile(file);
  assert.equal(createHash("sha256").update(bytes).digest("hex"),expected);
  return bytes;
}
const reference=JSON.parse(await pinned(refPath,"f236384ea91e81ad554ba2777bc4073c3ff41e34120343a8a474571c577b7727"));
await pinned(path.join(modelDir,"model.onnx"),"4974de78d3c35d2542e7a24d99b747e1160d6e31e366fb68492b74a789890f1b");
const sdk=await import(pathToFileURL(path.resolve(sdkPath)));
const engine=await sdk.createTilawa({modelDir,reference,recordEvidence:true,threads:1});
try{
  const session=engine.startFreeRecitation();
  const wav=await sdk.readWav(wavPath);
  await session.pushAudio(wav.samples,wav.sampleRate);await session.end();
  const evidence=session.evidence();
  for(const [ayah,chunks,expected] of [[1,evidence,4],[2,evidence,0],[1,evidence.slice(0,8),0]]){
    const report=passageAudit(reference,{surah:1,first:ayah,end:ayah},chunks);
    assert.equal(report.matched,expected);
    console.log("1:"+ayah,chunks.length+" chunks",report.matched+" supported word windows");
  }
  const selection={surah:1,first:1,end:1};
  const tracker=continuousTracker(reference,selection);
  let state,targets=new Set();
  for(let i=1;i<=evidence.length;i++){
    const end=Math.min(wav.samples.length,((evidence[i-1].decodedTo||0)+1)*evidence[i-1].frameMs*16);
    state=tracker.ingest(evidence.slice(0,i),wav.samples.subarray(0,end));
    if(state.active)targets.add(state.active.site.label);
  }
  assert.ok(state.beat>=30&&state.beat<=500);
  assert.ok(targets.has("Tabi‘i"));
  const words=passageAudit(reference,selection,evidence).words;
  const last=words.at(-1).interval;
  const trimmed=playbackBounds(wav.samples,last,(words.at(-2).interval.end+last.start)/2,wav.samples.length/16);
  assert.ok(trimmed.end>last.end && trimmed.end<=wav.samples.length/16);
  console.log("Automatic beat estimate",state.beat,"ms; target candidates",[...targets],
    "last word original and refined windows",last,trimmed);
  session.dispose();
}finally{await engine.dispose()}
