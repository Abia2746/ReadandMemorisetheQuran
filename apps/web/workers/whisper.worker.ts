/** Optional multilingual Whisper Tiny ASR worker.
 * Model and transformers runtime are Apache 2.0, not the
 * non-commercial Zipformer corpus. Downloads on opt-in first use only.
 * Not calibrated as a Tajweed grader. Processing stays local after download.
 */
import { pipeline } from "@huggingface/transformers";
type Message={type:"init";session:number}|{type:"transcribe";session:number;audio:Float32Array;sampleRate:number};
let loader:Promise<any>|null=null;
let transcribing=false;
async function loadModel(){
  if(!loader){
    loader=pipeline("automatic-speech-recognition","onnx-community/whisper-tiny",{
      device:"wasm",dtype:"q8",
    }).catch(error=>{
      loader=null;
      throw error;
    });
  }
  return loader;
}
self.onmessage=async (event:MessageEvent<Message>)=>{
  if(event.data.type==="init"){
    try{
      await loadModel();
      self.postMessage({type:"ready",session:event.data.session});
    }catch{
      self.postMessage({type:"error",session:event.data.session,message:"Model download unavailable"});
    }
    return;
  }
  if(event.data.type!=="transcribe")return;
  if(transcribing){
    self.postMessage({type:"busy",session:event.data.session});
    return;
  }
  transcribing=true;
  try{
    const model=await loadModel();
    const pcm=event.data.audio;
    if(!(pcm instanceof Float32Array)||pcm.length<16000)throw Error("Insufficient microphone audio");
    const output=await model(pcm,{language:"arabic",task:"transcribe",return_timestamps:false});
    const text=typeof output?.text==="string"?output.text:
      Array.isArray(output)&&typeof output[0]?.text==="string"?output[0].text:"";
    self.postMessage({type:"transcript",session:event.data.session,text});
  }catch(e){
    self.postMessage({type:"error",session:event.data.session,message:e instanceof Error?e.message:"On-device model unavailable"});
  }finally{transcribing=false}
};
export {};
