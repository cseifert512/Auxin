// Focused verification of the isolated comparison; run after its local server.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
const here=dirname(fileURLToPath(import.meta.url)),out=resolve(here,'.qa');
const require=createRequire(import.meta.url);
const {chromium}=require('C:/BOWER/Bower_Web/node_modules/playwright');
const base=process.env.TEST_URL||'http://127.0.0.1:5340/designx/v8/tests/room-time-hybrid/';
await mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--enable-gpu','--ignore-gpu-blocklist','--use-angle=d3d11']});
const page=await browser.newPage({viewport:{width:1600,height:1100},deviceScaleFactor:1});
const errors=[],checks=[];
page.on('pageerror',e=>errors.push(e.message));
const ready=()=>page.waitForFunction(()=>window.__roomTimeTest?.ready,null,{timeout:45000});
const state=()=>page.evaluate(()=>window.__roomTimeTest.snapshot());
try{
  await page.goto(base+'?variant=hybrid&time=49',{waitUntil:'domcontentloaded'});await ready();
  assert.ok(Math.abs((await state()).currentTime-49)<.01);checks.push('Direct hybrid link preserves requested time');
  await page.screenshot({path:resolve(out,'comparison-desktop.png'),fullPage:true});
  for(const id of ['original','compressed','hybrid']){
    await page.locator(`[data-variant="${id}"]`).click();await ready();
    const value=await state();assert.equal(value.currentVersion,id);assert.ok(Math.abs(value.currentTime-49)<.05);
  }
  checks.push('Switching all versions preserves the moment');
  await page.evaluate(()=>window.__roomTimeTest.seek(42));
  await page.locator('#play').click();await page.waitForTimeout(600);await page.locator('#play').click();
  const paused=await state();assert.ok(paused.currentTime>42);assert.equal(paused.playing,false);
  await page.waitForTimeout(200);assert.ok(Math.abs((await state()).currentTime-paused.currentTime)<.1);
  checks.push('Play, pause and scrub work and remain paused');
  await page.evaluate(async()=>{const pending=window.__roomTimeTest.select('original');await pending;const loading=window.__roomTimeTest.select('hybrid');const replacing=window.__roomTimeTest.select('compressed');await Promise.allSettled([loading,replacing]);});
  await ready();assert.equal((await state()).currentVersion,'compressed');
  checks.push('Rapid replacement cancels stale hybrid loading');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:resolve(out,'comparison-mobile.png'),fullPage:true});checks.push('Mobile layout has no page overflow');
  const manifest=JSON.parse(await readFile(resolve(here,'manifest.json'),'utf8'));
  const original=await readFile(resolve(here,manifest.original.src));
  assert.equal(createHash('sha256').update(original).digest('hex'),manifest.original.sha256);checks.push('Existing source film hash unchanged');
  assert.deepEqual(errors,[]);
  await writeFile(resolve(out,'ui-check.json'),JSON.stringify({checks,errors},null,2)+'\n');console.log(JSON.stringify({checks,errors}));
}finally{await browser.close();}
