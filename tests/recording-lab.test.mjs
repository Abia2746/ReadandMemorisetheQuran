import test from 'node:test';
import assert from 'node:assert/strict';
import {paceMeter,pcmWave} from '../recording_lab.js';
test('meter requires calibration and measures actual samples',()=>{
 const m=paceMeter();[0,250,500].forEach(t=>m.tap(t));assert.equal(m.beat(),null);
 m.tap(750);assert.equal(m.beat(),250);
 const tone=Float32Array.from({length:320},(_,i)=>.1*Math.sin(2*Math.PI*i/80));
 let ms;for(let i=0;i<25;i++)ms=m.frame(tone);
 assert.equal(ms/m.beat(),2);m.frame(new Float32Array(320));assert.equal(m.frame(new Float32Array(320)),0);
 [1000,1200,1400,1600,1800].forEach(t=>m.tap(t));assert.equal(m.beat(),200);
});
test('PCM WAV preserves signed sample extremes and frame duration',async()=>{
 const wav=new DataView(await pcmWave([-1,0,1]).arrayBuffer());
 assert.equal(wav.getUint32(24,true),16000);assert.equal(wav.getUint32(40,true),6);
 assert.equal(wav.getInt16(44,true),-32768);assert.equal(wav.getInt16(48,true),32767);
});
