import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import ts from 'typescript';
const source=readFileSync(new URL('../src/workers/device.worker.ts',import.meta.url),'utf8').replace(/^import .*;$/gm,'');
const js=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText.replace(/^export {};$/gm,'');
for(const scenario of ['cpu','gpu','load-failure','inference-failure','invalid-output']){
  const calls=[],messages=[];
  const self={navigator:scenario==='cpu'?{}:{gpu:{requestAdapter:async()=>({features:new Set(['shader-f16'])})}},postMessage:m=>messages.push(m)};
  const processor=async()=>({input_ids:{tolist:()=>[[1]]}});
  const pipeline=async(_task,_name,options)=>{
    calls.push(options.device);
    if(scenario==='load-failure'&&options.device==='webgpu')throw Error('GPU unsupported');
    return {processor,tokenizer:()=>({input_ids:{tolist:()=>[[1]]}}),dispose:async()=>{},model:async()=>{
      if(scenario==='inference-failure'&&options.device==='webgpu')throw Error('GPU unsupported operator');
      const value=scenario==='invalid-output'&&options.device==='webgpu'?NaN:.5;
      return {logits:{sigmoid:()=>({tolist:()=>[[[value]]]})},pred_boxes:{tolist:()=>[[[.5,.5,.2,.2]]]}};
    }};
  };
  vm.runInNewContext(js,{self,pipeline,RawImage:class{},env:{backends:{onnx:{wasm:{}}}},groundedDetections:()=>[],performance,OffscreenCanvas:class{getContext(){return {drawImage(){},getImageData(){return {data:new Uint8ClampedArray(16)}}}}}});
  await self.onmessage({data:{type:'init',advisory:true}});
  await self.onmessage({data:{type:'frame',timestamp:1,frame:{width:2,height:2,close(){}}}});
  assert.equal(messages.at(-1).type,'result',scenario);
  assert.equal(messages.at(-1).backend,scenario==='gpu'?'webgpu':'wasm',scenario);
  assert.equal(calls.at(-1),scenario==='gpu'?'webgpu':'wasm',scenario);
}
console.log('Device worker checks passed: CPU, GPU, initialization fallback, inference fallback, invalid-output fallback.');
