import test from 'node:test';
import assert from 'node:assert/strict';
import {alignPhones,acousticWindow,referenceTags,husaryClip,passageAudit} from '../recording_audit.mjs';
const inventory={id:'sample',tokens:'اب'};
function evidence(ids){
 return [{inventory:'sample',frameMs:40,phonemes:ids.flatMap((id,i)=>id?[{p:inventory.tokens[id-1],start:i,end:i}]:[]),
 posteriors:{startFrame:0,nFrames:ids.length,k:1,ids,probs:ids.map(()=>.97)}}];
}
test('CTC permits separated duplicates, rejects unsupported targets and missing frames',()=>{
 const ev=evidence([0,1,0,1,2,0]);assert.deepEqual(alignPhones('ااب',ev,inventory).map(s=>s.start),[40,120,160]);
 assert.equal(alignPhones('ااب',evidence([1,1,2]),inventory),null);
 assert.equal(alignPhones('اب',evidence([1,0]),inventory),null);
 ev[0].posteriors.startFrame=2;assert.equal(alignPhones('اب',ev,inventory),null);
});
test('forced path alone cannot verify a word',()=>{
 const ev=evidence([1,2]);ev[0].phonemes.pop();
 const ref={inventory,ayahs:[{s:1,a:1,w:['اب'],o:[0],p:'اب',iso:['اب']}]};
 const report=passageAudit(ref,{surah:1,first:1,end:1},ev);
 assert.equal(report.aligned,true);assert.equal(report.matched,0);assert.equal(report.words[0].interval,undefined);
});
test('band-energy measurement rejects silence and separates tones',()=>{
 const tone=f=>Float32Array.from({length:480},(_,i)=>.1*Math.sin(2*Math.PI*f*i/16000));
 assert.equal(acousticWindow(tone(0)),null);
 assert.ok(acousticWindow(tone(280)).nasalBandFraction>.5);
 assert.ok(acousticWindow(tone(1000)).nasalBandFraction<.01);
});
test('reference tags and audio identity',()=>{
 assert.ok(referenceTags('مِنْ','مِن','بَعْد').some(t=>t.includes('iqlāb')));
 const payload={audio_file:{chapter_id:1,audio_url:'https://download.quranicaudio.com/qdc/khalil_al_husary/murattal/1.mp3',timestamps:[{verse_key:'1:1',timestamp_from:0,timestamp_to:5220,segments:[[1,0,540]]}]}};
 assert.equal(husaryClip(payload,'1:1',0,1).end,540);
 assert.equal(husaryClip(payload,'1:1',0,2),null);
 payload.audio_file.audio_url+='x';assert.equal(husaryClip(payload,'1:1',0,1),null);
});
