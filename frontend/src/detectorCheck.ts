import {createDeviceWorker} from './createDeviceWorker';
const worker=createDeviceWorker();
const output=document.querySelector<HTMLPreElement>('#output')!;
let file:File|undefined,ready=false,busy=false;
async function run(){
  if(!file||busy)return;
  busy=true;output.textContent='Running local inference…';
  const frame=await createImageBitmap(file);
  worker.postMessage({type:'frame',frame,timestamp:performance.now()},[frame]);
}
worker.onmessage=({data})=>{
  output.textContent=JSON.stringify(data,null,2);
  if(data.type==='ready'){ready=true;if(file)void run();}
  if(data.type==='result'||data.type==='error')busy=false;
};
worker.onerror=e=>{busy=false;output.textContent=e.message;};
document.querySelector<HTMLInputElement>('input')!.onchange=e=>{
  file=(e.target as HTMLInputElement).files?.[0];if(ready&&file)void run();
};
worker.postMessage({type:'init',threshold:.35});
