import {chromium} from '@playwright/test';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
for(const role of ['candidate','hr']){
 const context=await browser.newContext();const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{const url=new URL(route.request().url());const body=url.pathname==='/api/auth/me'?{id:'test',name:'Browser test',email:'test@example.test',role}:url.pathname==='/api/portal/candidates'?[]:{assignments:[],notifications:[],practice_history:[]};await route.fulfill({json:body});});
 await page.goto('http://127.0.0.1:8000/');await page.waitForURL(`**/${role}/dashboard`);await page.getByRole('navigation',{name:'Workspace navigation'}).waitFor();
 await page.reload();await page.getByRole('navigation',{name:'Workspace navigation'}).waitFor();
 await page.goto(`http://127.0.0.1:8000/${role==='hr'?'candidate/practice':'hr/reports'}`);await page.waitForURL(`**/${role}/dashboard`);
 await page.setViewportSize({width:390,height:844});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error(role+' overflow');
 if(errors.length)throw new Error(errors.join(';'));console.log(role+': dashboard, refresh, role guard and mobile layout passed');await context.close();
}
const page=await browser.newPage();await page.goto('http://127.0.0.1:8000/hr/dashboard');await page.waitForURL('**/login');console.log('Anonymous protected route redirects to login');
}finally{await browser.close();}
