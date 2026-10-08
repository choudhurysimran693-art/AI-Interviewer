import {chromium} from '@playwright/test';
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve('..');
const profile=path.resolve('../../../work/browser-test-profile');
const chrome=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=9337',`--user-data-dir=${profile}`,'about:blank'],{stdio:'ignore',windowsHide:true});
let browser;
for(let i=0;i<30;i++){try{browser=await chromium.connectOverCDP('http://127.0.0.1:9337');break;}catch{await new Promise(r=>setTimeout(r,500));}}
if(!browser)throw new Error('Could not start isolated test browser.');
const context=await browser.newContext({viewport:{width:1440,height:1100}});
const page=await context.newPage();
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
fs.mkdirSync(path.join(root,'docs'),{recursive:true});
try{
  await page.goto('http://127.0.0.1:8000');
  await page.getByRole('heading',{name:/Make your next interview/}).waitFor();
  await page.screenshot({path:path.join(root,'docs/home-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(root,'docs/home-mobile.png'),fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  if(overflow)throw new Error('Mobile horizontal overflow');
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Start a practice interview'}).click();
  await page.getByLabel('First name *',{exact:true}).fill('Test');
  await page.getByLabel('Last name *',{exact:true}).fill('Candidate');
  await page.getByRole('button',{name:'Try a sample profile'}).click();
  await page.getByRole('checkbox').check();
  await page.getByRole('button',{name:'Create interview'}).click();
  await page.getByRole('button',{name:'Begin interview'}).click();
  for(let i=0;i<5;i++){
    await page.getByPlaceholder('Take a breath. Walk us through your thinking…').fill(`For example ${i+1}, I used Python validation, database transactions, and automated tests. I tested both the success path and malformed inputs. A limitation was the extra complexity, so I documented the trade-off.`);
    await page.getByRole('button',{name:'Review answer'}).click();
    await page.getByRole('button',{name:'Approve & evaluate'}).click();
    await page.getByRole('heading',{name:'Answer processed.'}).waitFor();
    await page.getByRole('button',{name:i===4?'Finish interview':'Next question'}).click();
  }
  await page.getByRole('button',{name:'Open my report'}).click();
  await page.getByRole('heading',{name:'A clearer next step.'}).waitFor();
  if(!await page.getByText('0 of 5 answers scored',{exact:false}).count())throw new Error('Unavailable scoring not disclosed');
  await page.screenshot({path:path.join(root,'docs/sample-report.png'),fullPage:true});
  await page.emulateMedia({media:'print'});
  await page.pdf({path:path.join(root,'docs/sample-assessment.pdf'),format:'A4',printBackground:true});
  await page.emulateMedia({media:'screen'});
  await page.getByRole('button',{name:'Camera observations',exact:true}).click();
  if(await page.getByText('No camera observation recorded',{exact:true}).count()!==5)throw new Error('Unexpected camera observations');
  await page.emulateMedia({media:'print'});
  await page.pdf({path:path.join(root,'docs/sample-observations.pdf'),format:'A4',printBackground:true});
  await page.emulateMedia({media:'screen'});
  if(errors.length)throw new Error(errors.join('\n'));
  fs.writeFileSync(path.join(root,'docs/browser-test-results.json'),JSON.stringify({passed:true,checks:['desktop layout','mobile no overflow','full five-answer practice UI','approved transcript evaluation attempts','separate observations report','assessment PDF','observations PDF'],consoleErrors:errors},null,2));
  console.log('PASS: desktop/mobile layouts, five-answer practice, observations, report and PDF exports.');
}finally{await context.close();await browser.close();chrome.kill();}
