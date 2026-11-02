// Built-app UI checks with mocked APIs; never sends candidate email or uploads media.
import {chromium,expect} from '@playwright/test';
import {createServer} from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../dist');
const server=createServer(async(req,res)=>{try{let file=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));if(!file.startsWith(root+path.sep))file=path.join(root,'index.html');let data;try{data=await readFile(file);}catch{file=path.join(root,'index.html');data=await readFile(file);}res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html','.wasm':'application/wasm'})[path.extname(file)]||'application/octet-stream');res.end(data);}catch{res.statusCode=500;res.end();}});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin='http://127.0.0.1:'+server.address().port;
await mkdir('test-results',{recursive:true});
const executablePath=process.env.CHROME_PATH||(process.platform==='win32'?'C:/Program Files/Google/Chrome/Application/chrome.exe':undefined);
const browser=await chromium.launch({headless:true,...(executablePath?{executablePath}:{})});
try{
 const context=await browser.newContext();const page=await context.newPage();let read=false,reads=0;const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{
  const url=new URL(route.request().url());let data={items:[]};
  if(url.pathname==='/api/auth/me')data={id:'candidate',name:'Test Candidate',role:'candidate'};
  if(url.pathname==='/api/candidate/notifications')data={items:[{id:'notice',title:'Next round: Aptitude',message:'You passed Resume Screening.',href:'/candidate/interview?assignment=test',type:'next_round',created_at:1,read,window_end_at:Date.now()/1000+3600}],unread_count:read?0:1};
  if(url.pathname.endsWith('/notice/read')){read=true;reads++;data={saved:true};}
  if(url.pathname==='/api/portal/dashboard')data={assignments:[]};
  await route.fulfill({json:data});
 });
 await page.goto(origin+'/candidate/interview');
 await expect(page.getByRole('region',{name:'New round unlocked'})).toBeVisible();
 await page.getByRole('link',{name:'Read your invitation and deadline'}).click();
 await expect(page.getByRole('heading',{name:'Messages',exact:true})).toBeVisible();
 await expect(page.getByLabel('Notifications, 1 unread')).toBeVisible();
 await page.getByRole('button',{name:'New · Next round: Aptitude'}).click();
 await expect(page.getByText('You passed Resume Screening.',{exact:true}).last()).toBeVisible();
 await expect(page.getByLabel('Notifications, 0 unread')).toBeVisible();
 if(reads!==1)throw Error('Read was not persisted exactly once');
 await page.goto(origin+'/candidate/interview');
 await expect(page.getByRole('region',{name:'New round unlocked'})).toHaveCount(0);
 await page.setViewportSize({width:390,height:844});await page.goto(origin+'/candidate/messages');
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Messages overflow on mobile');
 await page.screenshot({path:'test-results/workflow-messages.png',fullPage:true});
 if(errors.length)throw Error(errors.join(';'));
 console.log('Passed: unlocked banner, Messages navigation, mark-read persistence, unread bell refresh, read banner removal, mobile layout. APIs mocked.');
 await context.close();
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
