/// <reference lib="webworker" />
import {pipeline, RawImage, env} from '@huggingface/transformers';
import {groundedDetections} from '../groundedDetections';
env.allowLocalModels=true;
env.allowRemoteModels=false;
env.localModelPath='/models/';
if(env.backends.onnx.wasm){env.backends.onnx.wasm.numThreads=1;env.backends.onnx.wasm.proxy=false;}
let detector:any;
let threshold=.35;
let backend='wasm';
let diagnostic=false;
self.onmessage=async({data})=>{
  const {type,frame,timestamp}=data;
  try{
    if(type==='init'){
      threshold=data.threshold??.35;
      diagnostic=!!data.diagnostic;
      const options={local_files_only:true,progress_callback:(progress:unknown)=>self.postMessage({type:'progress',progress})};
      // CPU/WASM only: video frames and model results never leave this browser.
      detector=await pipeline('zero-shot-object-detection','grounding-dino',{...options,device:'wasm',dtype:'q8'});
      self.postMessage({type:'ready',device:'CPU (local quantized model)'});
    } else if(type==='frame'){
      const start=performance.now(),canvas=new OffscreenCanvas(frame.width,frame.height);
      const ctx=canvas.getContext('2d')!;ctx.drawImage(frame,0,0);
      const pixels=ctx.getImageData(0,0,frame.width,frame.height);
      const image=new RawImage(new Uint8ClampedArray(pixels.data),frame.width,frame.height,4);
      const labels=['mobile phone','tablet computer','laptop computer','monitor'];
      // Batch size is fixed to one. Pass the complete processor output,
      // including pixel_mask, which the generic pipeline currently omits.
      const inputs=await detector.processor(image,labels.join('. ')+'.');
      const ids=inputs.input_ids.tolist()[0].map(Number);
      const groups=labels.map(label=>{
        const noun=({'mobile phone':'phone','tablet computer':'tablet','laptop computer':'laptop','monitor':'monitor'} as Record<string,string>)[label];
        const tokens=detector.tokenizer(noun,{add_special_tokens:false}).input_ids.tolist()[0].map(Number);
        const start=ids.findIndex((_:number,i:number)=>tokens.every((id:number,j:number)=>ids[i+j]===id));
        return {label:label==='monitor'?'second monitor':label,positions:start<0?[]:tokens.map((_:number,i:number)=>start+i)};
      });
      const outputs=await detector.model(inputs);
      const probabilities=outputs.logits.sigmoid().tolist()[0];
      if(!probabilities.flat().every(Number.isFinite))throw new Error('Invalid model output on this graphics adapter. Monitoring cannot continue.');
      if(diagnostic)self.postMessage({type:'diagnostic',groups,maxima:groups.map(g=>Math.max(...probabilities.map((r:number[])=>Math.min(...g.positions.map((j:number)=>r[j])))))});
      const detections=groundedDetections(probabilities,outputs.pred_boxes.tolist()[0],groups,frame.width,frame.height,threshold);
      self.postMessage({type:'result',timestamp,latency:performance.now()-start,backend,detections});
    }
  }catch(error){self.postMessage({type:'error',message:String(error)});}finally{frame?.close();}
};
