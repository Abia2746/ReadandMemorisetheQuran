/* AudioWorklet: capture mono Float32 PCM without a Streamlit rerun.
   Analyser and worker processing remain local to the browser. */
class AlMuallimPCM extends AudioWorkletProcessor {
  constructor(){
    super();
    this.buffer=new Float32Array(4096);
    this.count=0;
  }
  process(inputs){
    const input=inputs[0]?.[0];
    if(input){
      for(let i=0;i<input.length;i++){
        this.buffer[this.count++]=input[i];
        if(this.count===this.buffer.length){
          const full=this.buffer;
          this.port.postMessage({pcm:full,sourceRate:sampleRate},[full.buffer]);
          this.buffer=new Float32Array(4096);
          this.count=0;
        }
      }
    }
    return true;
  }
}
registerProcessor("almuallim-pcm",AlMuallimPCM);
