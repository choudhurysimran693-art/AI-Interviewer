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
let modelName='grounding-dino-tiny-q8';
async function loadCPU(){backend='wasm';modelName='grounding-dino-tiny-q8';return pipeline('zero-shot-object-detection','grounding-dino',{local_files_only:true,device:'wasm',dtype:'q8'});}
let diagnostic=false;
self.onmessage=async({data})=>{
  const {type,frame,timestamp}=data;
  try{
    if(type==='init'){
      threshold=data.threshold??.35;
      diagnostic=!!data.diagnostic;
      const options={local_files_only:true,progress_callback:(progress:unknown)=>self.postMessage({type:'progress',progress})};
      // Only advisory scans use the accelerated variant until separately validated.
      const gpu=(self.navigator as WorkerNavigator&{gpu?:{requestAdapter:()=>Promise<{features:Set<string>}|null>}}).gpu;
      const adapter=data.advisory!==false&&gpu?await gpu.requestAdapter().catch(()=>null):null;
      if(adapter?.features.has('shader-f16')){
        try{detector=await pipeline('zero-shot-object-detection','grounding-dino',{...options,device:'webgpu',dtype:'fp16'});backend='webgpu';modelName='grounding-dino-tiny-fp16';}
        catch{detector=await loadCPU();}
      }else detector=await loadCPU();
      self.postMessage({type:'ready',device:backend==='webgpu'?'GPU (local model)':'CPU (local quantized model)'});
    } else if(type==='frame'){
      const start=performance.now(),canvas=new OffscreenCanvas(frame.width,frame.height);
      const ctx=canvas.getContext('2d')!;ctx.drawImage(frame,0,0);
      const pixels=ctx.getImageData(0,0,frame.width,frame.height);
      const image=new RawImage(new Uint8ClampedArray(pixels.data),frame.width,frame.height,4);
      const labels=['mobile phone','tablet computer','laptop computer'];
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
      let outputs;
      try{outputs=await detector.model(inputs);if(!outputs.logits.sigmoid().tolist()[0].flat().every(Number.isFinite))throw new Error('GPU output invalid');}catch(error){
        if(backend!=='webgpu')throw error;
        await detector.dispose().catch(()=>{});detector=await loadCPU();
        const cpuInputs=await detector.processor(image,labels.join('. ')+'.');
        outputs=await detector.model(cpuInputs);
      }
      const probabilities=outputs.logits.sigmoid().tolist()[0];
      if(!probabilities.flat().every(Number.isFinite))throw new Error('Invalid model output on this graphics adapter. Monitoring cannot continue.');
      if(diagnostic)self.postMessage({type:'diagnostic',groups,maxima:groups.map(g=>Math.max(...probabilities.map((r:number[])=>Math.min(...g.positions.map((j:number)=>r[j])))))});
      const detections=groundedDetections(probabilities,outputs.pred_boxes.tolist()[0],groups,frame.width,frame.height,threshold);
      self.postMessage({type:'result',timestamp,latency:performance.now()-start,backend,model:modelName,model_revision:'ff690b0a8050566c290287545bd059350f3e9096',detections});
    }
  }catch(error){self.postMessage({type:'error',message:String(error)});}finally{frame?.close();}
};
