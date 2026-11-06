/* Isolated browser acceptance test: never writes to the live shop database. */
const {chromium} = require('playwright');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'sua-browser-'));
const service=spawn(path.join(root,'.venv/bin/python'),['server.py'],{cwd:root,env:{...process.env,SUA_DB:path.join(tmp,'test.sqlite3'),PORT:'8019'},stdio:['ignore','pipe','pipe']});
let logs='';service.stderr.on('data',b=>logs+=b);service.stdout.on('data',b=>logs+=b);
async function main(){
  let browser;
  try{
    let ready=false;
    for(let i=0;i<50;i++){try{if((await fetch('http://127.0.0.1:8019/api/health')).ok){ready=true;break}}catch{}await new Promise(r=>setTimeout(r,100))}
    assert(ready,'Test server failed to start');
    browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:8019');
    const password=crypto.randomBytes(18).toString('hex');
    await page.locator('[name="display_name"]').fill('Chủ quán thử nghiệm');
    await page.locator('[name="username"]').fill('browser_owner');
    await page.locator('[name="password"]').fill(password);
    await page.locator('#login-form button').click();await page.waitForSelector('.hero');
    await page.click('[data-tab="recipes"]');await page.click('#add-product');
    for(const [key,value] of Object.entries({id:'BROWSER_TEST',name:'Món thử giao diện',category:'Test',size:'M',price:'32000',cost:'10000'}))await page.locator(`dialog [name="${key}"]`).fill(value);
    await page.locator('dialog button[type="submit"]').click();await page.waitForSelector('dialog',{state:'detached'});
    await page.click('[data-tab="sale"]');await page.locator('#search').fill('Món thử');await page.locator('[data-product="BROWSER_TEST"]').click();await page.click('#add-custom-drink');
    assert((await page.locator('#cart').innerText()).includes('32.000'));
    // Lose the response AFTER the server commits. Retrying must return that same sale.
    let lose=true;
    await page.route('**/api/orders',async route=>{if(lose){lose=false;await route.fetch();await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Mất xác nhận mô phỏng'})})}else await route.continue()});
    await page.click('#checkout');await page.getByRole('button',{name:'Thử lại thanh toán'}).waitFor();
    await page.reload();await page.waitForSelector('.hero');await page.click('[data-tab="sale"]');
    await page.getByRole('button',{name:'Thử lại thanh toán'}).click();
    await page.waitForFunction(()=>!document.querySelector('[data-minus]'));
    const orderState=await page.evaluate(()=>fetch('/api/state').then(r=>r.json()));
    const pdfResponse=await page.request.get('http://127.0.0.1:8019/api/invoice/'+orderState.orders[0].id+'?dataset='+orderState.dataset_id);
    assert((await pdfResponse.body()).subarray(0,4).toString()==='%PDF');
    const state=await page.evaluate(()=>fetch('/api/state').then(r=>r.json()));assert.equal(state.orders.length,1);assert.equal(state.orders[0].total,32000);
    await page.click('[data-tab="stock"]');await page.locator('[data-stock]').first().click();await page.locator('dialog [name="qty"]').fill('2');await page.locator('dialog [name="note"]').fill('Nhập thử giao diện');await page.locator('dialog button[type="submit"]').click();await page.waitForSelector('dialog',{state:'detached'});await page.getByText('Nhập thử giao diện',{exact:true}).waitFor();
    await page.click('[data-tab="cakes"]');for(const [key,value] of Object.entries({name:'Bánh thử',received:'10',sold:'4',waste:'1',price:'15000',cost:'6000'}))await page.locator(`#cake-form [name="${key}"]`).fill(value);await page.locator('#cake-form button').click();await page.getByText('Bánh thử',{exact:true}).waitFor();
    await page.click('[data-tab="reports"]');await page.waitForSelector('#report-cards .card');assert((await page.locator('#report-cards').innerText()).includes('92.000'));
    await page.locator('#report-period').selectOption('month');await page.waitForSelector('#report-cards .card');
    const csvEvent=page.waitForEvent('download');await page.click('#export-report');assert((await csvEvent).suggestedFilename().endsWith('.csv'));
    await page.click('[data-tab="orders"]');await page.locator('[data-refund]').first().click();await page.locator('dialog [name="reason"]').fill('Hoàn thử');await page.locator('dialog button[type="submit"]').click();await page.waitForSelector('dialog',{state:'detached'});await page.getByText('Đã hoàn',{exact:true}).waitFor();
    await page.click('[data-tab="settings"]');await page.locator('#settings-form [name="address"]').fill('Địa chỉ quán thử nghiệm');await page.locator('#settings-form button').click();await page.getByText('settings.save',{exact:true}).waitFor();
    await page.click('#add-user');for(const [key,value] of Object.entries({username:'cashier_ui',display_name:'Thu ngân thử',password}))await page.locator(`dialog [name="${key}"]`).fill(value);await page.locator('dialog button[type="submit"]').click();await page.waitForSelector('dialog',{state:'detached'});
    const backupEvent=page.waitForEvent('download');await page.click('#backup');const backup=await backupEvent;await backup.saveAs(path.join(tmp,'backup.sqlite3'));assert(fs.readFileSync(path.join(tmp,'backup.sqlite3')).subarray(0,15).toString()==='SQLite format 3');
    await page.click('[data-tab="overview"]');await page.screenshot({path:'/tmp/sua-v2-desktop.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});for(const tab of ['overview','sale','orders','stock','cakes','reports','recipes','settings']){await page.click(`[data-tab="${tab}"]`);assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),`Mobile overflow: ${tab}: ${JSON.stringify(await page.evaluate(()=>[...document.querySelectorAll("body *")].filter(e=>e.getBoundingClientRect().right>innerWidth).slice(0,12).map(e=>({tag:e.tagName,id:e.id,cls:e.className,w:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right}))))}`)}
    await page.screenshot({path:'/tmp/sua-v2-mobile.png',fullPage:true});
    await page.click('#logout');await page.waitForSelector('#login-form');await page.locator('[name="username"]').fill('cashier_ui');await page.locator('[name="password"]').fill(password);await page.locator('#login-form button').click();await page.waitForSelector('#checkout');assert.equal(await page.locator('[data-tab="settings"]').count(),1);assert.equal(await page.locator('[data-tab="reports"]').count(),0);
    const cashierState=await page.evaluate(()=>fetch('/api/state').then(r=>r.json()));assert(cashierState.menu.every(p=>!('cost' in p)));assert.equal(cashierState.orders.length,0);
    assert.deepEqual(errors,[]);console.log('PASS browser: setup, 8 screens, menu, lost-response retry, PDF, inventory, cakes, reports/CSV, refund, settings/users, backup, mobile, cashier permissions.');
  }finally{if(browser)await browser.close();service.kill('SIGTERM');await new Promise(resolve=>service.once('exit',resolve));fs.rmSync(tmp,{recursive:true,force:true})}
}
main().catch(e=>{console.error(e.message);process.exitCode=1});
