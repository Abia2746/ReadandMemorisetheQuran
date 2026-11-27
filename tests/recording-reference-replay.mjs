// Offline integration runner: supply a locally installed @tilawa/core Node entry,
// pinned reference JSON, unpacked lite model directory and a mono WAV of 1:1.
// No learner audio leaves this process.
import {readFile} from "node:fs/promises";
import {createHash} from "node:crypto";
import path from "node:path";
import {pathToFileURL} from "node:url";
import assert from "node:assert/strict";
import {passageAudit} from "../recording_audit.mjs";

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
  session.dispose();
}finally{await engine.dispose()}
