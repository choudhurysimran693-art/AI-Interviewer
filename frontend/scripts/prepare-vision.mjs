import fs from 'node:fs';
import path from 'node:path';
// Classic worker: MediaPipe's WASM loader needs importScripts. Its installed
// CommonJS bundle exports through `exports`, not a global called `vision`.
const root=path.resolve(import.meta.dirname,'..');
const dest=path.join(root,'public','vision');
fs.mkdirSync(dest,{recursive:true});
fs.copyFileSync(path.join(root,'node_modules/@mediapipe/tasks-vision/vision_bundle.cjs'),path.join(dest,'vision_bundle.js'));
fs.cpSync(path.join(root,'node_modules/@mediapipe/tasks-vision/wasm'),path.join(dest,'wasm'),{recursive:true});
