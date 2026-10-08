import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {describe,it,expect} from 'vitest';

describe('CPU device worker classification',()=>{
  it('discards persons and weak phone detections, retaining only supported devices',async()=>{
    const messages:any[]=[];
    const detection=(categoryName:string,score:number)=>({categories:[{categoryName,score}],boundingBox:{originX:0,originY:0,width:20,height:20}});
    const worker:any={postMessage:(message:any)=>messages.push(message)};
    const detector={detect:()=>({detections:[detection('person',.99),detection('cell phone',.1),detection('cell phone',.9),detection('laptop',.8),detection('chair',.9)]})};
    const context={self:worker,performance:{now:()=>0},importScripts:()=>Object.assign(worker.exports,{FilesetResolver:{forVisionTasks:async()=>({})},ObjectDetector:{createFromOptions:async()=>detector}}),OffscreenCanvas:class {getContext(){return {drawImage(){}};}}};
    runInNewContext(readFileSync(new URL('../public/device-monitor.js',import.meta.url),'utf8'),context);
    await worker.onmessage({data:{type:'init',threshold:.35}});
    await worker.onmessage({data:{type:'frame',frame:{width:100,height:100,close(){}},timestamp:1}});
    const result=messages.find(x=>x.type==='result');
    expect(result.detections.map((x:any)=>x.label)).toEqual(['mobile phone','laptop computer']);
    expect(messages.some(x=>x.type==='error')).toBe(false);
  });
});
