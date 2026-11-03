/* Real-backend Excel activation E2E. All workbooks/accounts/DBs are synthetic and temporary. */
const {chromium} = require('playwright');
const {spawn, spawnSync} = require('node:child_process');
const {once} = require('node:events');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const net = require('node:net');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '..');
const python = path.join(root, '.venv/bin/python');
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'sua-import-browser-'));
const sourceDatabase = path.join(temporary, 'source.sqlite3');
const url = 'http://127.0.0.1:8021';
const environment = {...process.env, SUA_DB:sourceDatabase, PORT:'8021',
  HOST:'127.0.0.1', SUA_SECURE_COOKIE:'0', CODESPACES:'false'};
const bootstrap = "import server,json; server.init(seed=json.loads((server.BASE/'data/demo.json').read_text(encoding='utf-8')),demo=True); server.ThreadingHTTPServer(('127.0.0.1',8021),server.Handler).serve_forever()";
let service, browser, logs = '';

function pythonResult(code, args=[]) {
  const result = spawnSync(python, ['-c', code, ...args], {
    cwd:root, env:environment, encoding:'utf8', maxBuffer:5*1024*1024,
  });
  if(result.status !== 0) throw new Error('Synthetic test helper failed: ' + (result.stderr || result.error || 'unknown error'));
  return result.stdout;
}

async function availablePort() {
  const probe = net.createServer();
  probe.listen(8021, '127.0.0.1');
  await once(probe, 'listening');
  await new Promise(resolve=>probe.close(resolve));
}

async function startServer() {
  service = spawn(python, ['-c', bootstrap], {cwd:root, env:environment, stdio:['ignore','pipe','pipe']});
  service.stdout.on('data', value=>{logs += value});
  service.stderr.on('data', value=>{logs += value});
  for(let attempt=0;attempt<100;attempt++) {
    if(service.exitCode !== null) throw new Error('Isolated import server exited: ' + logs.slice(-2500));
    try {
      const response = await fetch(url + '/api/health', {signal:AbortSignal.timeout(1000)});
      if(response.ok && (await response.json()).status === 'ok') return;
    } catch {}
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  throw new Error('Isolated import server was not ready: ' + logs.slice(-2500));
}

async function stopServer() {
  const child=service;
  service=null;
  if(!child || child.exitCode !== null || child.signalCode !== null) return;
  const stopped=once(child,'exit');
  child.kill('SIGTERM');
  const timeout=setTimeout(()=>child.kill('SIGKILL'),5000);
  try {await stopped} finally {clearTimeout(timeout)}
}

async function state(page) {
  return page.evaluate(async()=>{
    const response=await fetch('/api/state');
    if(!response.ok) throw new Error('Cannot read browser test state: '+response.status);
    return response.json();
  });
}

async function downloadTo(page, click, filename) {
  const event=page.waitForEvent('download');
  await click();
  const file=await event;
  const target=path.join(temporary, filename);
  await file.saveAs(target);
  return target;
}

async function main() {
  try {
    await availablePort();
    const uploads=JSON.parse(pythonResult("import sys,json; sys.path.insert(0,'tests'); from test_live_import import sample_uploads; print(json.dumps(sample_uploads()))"));
    for(const type of ['inventory','cost']) fs.writeFileSync(path.join(temporary,type+'.xlsx'),Buffer.from(uploads[type].base64,'base64'));
    await startServer();
    browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
    const context=await browser.newContext({viewport:{width:1440,height:1000}});
    const page=await context.newPage();
    const errors=[];
    page.on('pageerror', error=>errors.push(error.message));
    await page.goto(url);
    const password=crypto.randomBytes(18).toString('hex');
    await page.locator('[name="display_name"]').fill('Chủ quán nhập thử');
    await page.locator('[name="username"]').fill('live_browser_owner');
    await page.locator('[name="password"]').fill(password);
    await page.locator('#login-form button').click();
    await page.waitForSelector('.hero');
    let current=await state(page);
    assert.equal(current.demo,true);
    assert.equal(current.menu.length,3,'Test must start from bundled synthetic data, never a private seed.');
    const demoDataset=current.dataset_id;
    const ownerId=current.user.id;

    // Keep a paid demo transaction to verify it is archived and never counted as live revenue.
    await page.click('[data-tab="sale"]');
    await page.locator('[data-product="CF01_M"]').click();await page.click('#add-custom-drink');
    await page.click('#checkout');
    await page.waitForFunction(()=>!document.querySelector('[data-minus]'));
    current=await state(page);
    assert.equal(current.orders.length,1);

    // This tab intentionally remains on the old dataset with an unsent cart.
    const stale=await context.newPage();
    stale.on('pageerror', error=>errors.push(error.message));
    await stale.goto(url);
    await stale.waitForSelector('.hero');
    await stale.click('[data-tab="sale"]');
    await stale.locator('[data-product="CF01_M"]').click();await stale.click('#add-custom-drink');
    assert.equal(await stale.locator('[data-minus]').count(),1);

    await page.click('#open-live-import');
    await page.waitForSelector('#import-files-form');
    await page.locator('#import-inventory').setInputFiles(path.join(temporary,'inventory.xlsx'));
    await page.locator('#import-cost').setInputFiles(path.join(temporary,'cost.xlsx'));
    await page.click('#preview-import');
    await page.waitForSelector('#apply-import');
    assert(await page.locator('#apply-import').isDisabled());
    await page.getByText('Live coffee',{exact:true}).waitFor();
    await page.locator('[data-import-stock="1"]').fill('900');
    const inventoryDate=await page.evaluate(()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()));
    await page.locator('#import-inventory-date').fill(inventoryDate);
    assert(await page.locator('#apply-import').isDisabled());
    await page.check('#import-reviewed');
    assert(!(await page.locator('#apply-import').isDisabled()));
    await page.setViewportSize({width:390,height:844});
    assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),'Import review overflows mobile viewport');
    await page.screenshot({path:'/tmp/sua-import-preview.png',fullPage:true});
    await page.setViewportSize({width:1440,height:1000});

    // The first response is lost after the real backend commits activation.
    let firstResponse=true;
    const applyPayloads=[];
    await page.route('**/api/import/apply',async route=>{
      applyPayloads.push(route.request().postDataJSON());
      const response=await route.fetch();
      assert.equal(response.status(),201,await response.text());
      if(firstResponse) {
        firstResponse=false;
        await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Mất phản hồi mô phỏng; thử lại cùng lần áp dụng.'})});
      } else await route.fulfill({response});
    });
    await page.click('#apply-import');
    await page.locator('dialog button[type="submit"]').click();
    await page.locator('dialog .error').filter({hasText:'Mất phản hồi mô phỏng'}).waitFor();
    current=await state(page);
    assert.equal(current.demo,false,'The simulated lost response must happen after activation commits.');
    await page.locator('dialog button[type="submit"]').click();
    await page.waitForSelector('#live-backup');
    assert.equal(applyPayloads.length,2);
    assert.deepEqual(applyPayloads[0],applyPayloads[1],'Activation retries must reuse the reviewed job and quantities.');
    current=await state(page);
    assert.equal(current.user.id,ownerId);
    assert.equal(current.user.username,'live_browser_owner');
    assert.notEqual(current.dataset_id,demoDataset);
    assert.deepEqual(current.menu.map(p=>p.id),['LIVE_M']);
    assert.equal(current.stock[0].qty,900);
    assert.equal(current.inventory_date,inventoryDate);
    assert.deepEqual(current.orders,[]);
    assert(await page.locator('#demo-banner').isHidden());
    assert.equal(await page.locator('#apply-import').count(),0);

    const demoBackup=await downloadTo(page,()=>page.click('#demo-archive-backup'),'archived-demo.sqlite3');
    assert.equal(fs.readFileSync(demoBackup).subarray(0,15).toString(),'SQLite format 3');
    const archive=JSON.parse(pythonResult("import sqlite3,sys,json; c=sqlite3.connect(sys.argv[1]); print(json.dumps({'integrity':c.execute('PRAGMA integrity_check').fetchone()[0],'orders':c.execute('SELECT COUNT(*) FROM orders').fetchone()[0]})); c.close()",[demoBackup]));
    assert.equal(archive.integrity,'ok');
    assert.equal(archive.orders,1);

    // The old tab must not submit its demo cart into the new business dataset.
    const rejected=stale.waitForResponse(response=>response.url().endsWith('/api/orders')&&response.status()===409);
    await stale.click('#checkout');
    assert.equal((await (await rejected).json()).code,'DATASET_CHANGED');
    await stale.waitForFunction(()=>!document.querySelector('[data-minus]'));
    assert.equal((await state(page)).orders.length,0);

    await page.click('[data-tab="sale"]');
    await page.locator('[data-product="LIVE_M"]').click();await page.click('#add-custom-drink');
    await page.click('#checkout');
    await page.waitForFunction(()=>!document.querySelector('[data-minus]'));
    current=await state(page);
    assert.equal(current.orders.length,1);
    assert.equal(current.orders[0].total,26000);
    assert.equal(current.stock[0].qty,900,'Inventory stays manual until recipe mappings are confirmed.');
    const liveDataset=current.dataset_id;
    const marker=JSON.parse(fs.readFileSync(path.join(temporary,'source.active.json'),'utf8'));
    assert(fs.existsSync(path.join(temporary,marker.database)));
    assert(fs.existsSync(sourceDatabase),'The original demo database must remain intact.');

    // Restart using exactly the original configured path. The persisted pointer must select live data.
    await stopServer();
    await startServer();
    await page.reload();
    await page.waitForSelector('.hero');
    current=await state(page);
    assert.equal(current.demo,false);
    assert.equal(current.dataset_id,liveDataset);
    assert.equal(current.user.id,ownerId);
    assert.deepEqual(current.menu.map(p=>p.id),['LIVE_M']);
    assert.equal(current.stock[0].qty,900);
    assert.equal(current.orders.length,1);
    assert(await page.locator('#demo-banner').isHidden());
    assert.equal(await page.locator('#login-form').count(),0,'Session must survive the dataset transition and restart.');
    assert.deepEqual(errors,[]);
    console.log('PASS real-backend import: synthetic XLSX upload/review, stock/date confirmation, lost-response replay, owner/session preservation, demo archive, stale-tab rejection, first live sale/PDF, mobile and restart persistence.');
  } finally {
    if(browser)await browser.close();
    await stopServer();
    fs.rmSync(temporary,{recursive:true,force:true});
  }
}

main().catch(error=>{console.error(error.message);process.exitCode=1});
