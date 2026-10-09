import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import {resolve,extname,sep} from 'node:path';
import {chromium} from '@playwright/test';
const root=resolve('dist');
const server=createServer(async(req,res)=>{
  const path=resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
  if(!path.startsWith(root+sep)){res.writeHead(403).end();return;}
  try{await stat(path);res.setHeader('Content-Type',({'.js':'text/javascript','.html':'text/html','.json':'application/json','.wasm':'application/wasm'})[extname(path)]||'application/octet-stream');createReadStream(path).pipe(res);}catch{res.writeHead(404).end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
let browser;
try{
  browser=await chromium.launch({channel:'msedge',headless:true});
  const page=await browser.newPage();
  await page.goto(`http://127.0.0.1:${server.address().port}/detector-check.html`);
  await page.waitForFunction(()=>/"type": "(ready|error)"/.test(document.querySelector('#output').textContent),{},{timeout:120000});
  console.log(await page.locator('#output').innerText());
  if((await page.locator('#output').innerText()).includes('"error"'))process.exitCode=1;
  else{
    await page.locator('input').setInputFiles(process.argv[2]);
    await page.waitForFunction(()=>/"type": "(result|error)"/.test(document.querySelector('#output').textContent),{},{timeout:120000});
    console.log(await page.locator('#output').innerText());
  }
}finally{await browser?.close();server.close();}
