// Equivalent Vite build with esbuild's official WASM implementation, for Windows
// environments where native subprocess pipe creation is unavailable.
import {createRequire,syncBuiltinESMExports} from 'node:module';
import fs from 'node:fs';
import './prepare-vision.mjs';
const require=createRequire(import.meta.url);
// Vite probes mapped network drives with `net use`. Local workspace paths do not
// need that optional optimization; preserve the normal realpath fallback.
const childProcess=require('node:child_process');
const originalExec=childProcess.exec;
childProcess.exec=function(command,...args){
  if(command==='net use'){const callback=args.at(-1);queueMicrotask(()=>callback(new Error('Mapped drive optimization unavailable'),''));return;}
  return originalExec.call(this,command,...args);
};
syncBuiltinESMExports();
globalThis.self=globalThis;
const esbuild=require('esbuild-wasm/lib/browser.js');
await esbuild.initialize({wasmModule:await WebAssembly.compile(fs.readFileSync(require.resolve('esbuild-wasm/esbuild.wasm'))),worker:false});
const native=require.resolve('esbuild');
require.cache[native]={id:native,filename:native,loaded:true,exports:esbuild};
const command=process.argv[2]||'build';
const {default:react}=await import('@vitejs/plugin-react');
const config={configFile:false,plugins:[react()],worker:{format:'es'},build:{chunkSizeWarningLimit:2500,rollupOptions:{input:{main:'index.html',detector:'detector-check.html'}}},server:{host:'127.0.0.1',proxy:{'/api':'http://127.0.0.1:8000'}}};
if(command==='test'){
  const {startVitest}=await import('vitest/node');
  const ctx=await startVitest('test',['src/detection.test.ts','src/groundedDetections.test.ts','src/routes.test.ts','src/fullscreen.test.ts','src/gaze.test.ts','src/Applications.test.tsx'],{watch:false,pool:'threads',maxWorkers:1,minWorkers:1},config);
  await ctx?.close();
}else{
  const {build,createServer}=await import('vite');
  if(command==='dev'){const server=await createServer(config);await server.listen();server.printUrls();}
  else{await build(config);esbuild.stop();}
}

