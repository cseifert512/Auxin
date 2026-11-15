// Focused edition 08 integration QA. HTTP assets come from disk; no downloads required.
// Set DECK_FS_ROUTE=0 to exercise an already-running local server instead.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, extname, resolve, sep } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/BOWER/Bower_Web/node_modules/playwright');
const href = process.env.DECK_URL || 'http://localhost:5312/designx/v8/';
const origin = new URL(href).origin;
const expectedThemes = ['cover', 'buyers-slide', 'v7-growth-slide', 'v8-ground-slide', 'v7-anatomy-slide', 'v7-computation-slide', 'variability-slide', 'factory-slide', 'factory-focus-slide', 'v7-commercial-model-slide', 'v8-care-slide', 'v7-learning-slide', 'learning-slide', 'v7-learning-flow-slide', 'commercial-loop-slide', 'coupled-slide', 'team-slide', 'material-problem-slide', 'v7-future-slide', 'closing'];
const result = { passed: [], failures: [], errors: [], missingAssets: [], failedRequests: [], externalRequests: [], slides: [] };
const dependencies = new Set();
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || 'C:/Users/cseif/AppData/Local/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-win64/chrome-headless-shell.exe' });
const context = await browser.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1, reducedMotion: 'no-preference' });
context.setDefaultTimeout(20000); context.setDefaultNavigationTimeout(20000);
const deckRoot = resolve(root, '../..'), piecesRoot = resolve(deckRoot, '../drawings-in-code/exports/deck');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.png': 'image/png', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.mp4': 'video/mp4' };
const inside = (file, directory) => file === directory || file.startsWith(directory + sep);
await context.route('**/*', async route => {
  const url = new URL(route.request().url()); dependencies.add(url.href);
  if (url.origin !== origin) { result.externalRequests.push(url.href); await route.abort('blockedbyclient'); return; }
  if (process.env.DECK_FS_ROUTE === '0') { await route.continue(); return; }
  const pathname = decodeURIComponent(url.pathname);
  if (pathname === '/favicon.ico') { await route.fulfill({ status: 204, body: '' }); return; }
  let file = resolve(deckRoot, `.${pathname}`);
  try {
    if (!inside(file, deckRoot)) throw new Error('Path outside deck');
    let info;
    try { info = await stat(file); }
    catch {
      if (!pathname.startsWith('/designx/pieces/')) throw new Error('Missing deck asset');
      file = resolve(piecesRoot, pathname.slice('/designx/pieces/'.length));
      if (!inside(file, piecesRoot)) throw new Error('Path outside drawing exports');
      info = await stat(file);
    }
    if (info.isDirectory()) file = resolve(file, 'index.html');
    await route.fulfill({ status: 200, contentType: types[extname(file)] || 'application/octet-stream', body: await readFile(file) });
  } catch (error) { await route.fulfill({ status: 404, contentType: 'text/plain', body: `${pathname}: ${error.message}` }); }
});
const page = await context.newPage();
page.on('pageerror', error => result.errors.push(error.message));
page.on('response', response => { if (response.status() >= 400) result.missingAssets.push({ status: response.status(), url: response.url() }); });
page.on('requestfailed', request => { const error = request.failure()?.errorText || ''; if (!/ERR_ABORTED|NS_BINDING_ABORTED/.test(error)) result.failedRequests.push({ url: request.url(), error }); });
const host = kind => page.locator(`[data-v8-study="${kind}"]`);
const frames = (count = 12) => page.evaluate(n => new Promise(done => { const step = () => --n <= 0 ? done() : requestAnimationFrame(step); requestAnimationFrame(step); }), count);
async function test(name, fn) {
  console.log(`[v8 QA] START ${name}`);
  try { await fn(); result.passed.push(name); console.log(`[v8 QA] PASS ${name}`); }
  catch (error) { result.failures.push({ name, message: error.stack || error.message }); console.log(`[v8 QA] FAIL ${name}: ${error.message}`); }
  finally { await page.evaluate(() => document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close())).catch(() => {}); }
}
async function activate(theme) {
  const number = await page.evaluate(theme => {
    const index = window.DESIGNX_SLIDES.findIndex(slide => slide.theme.split(' ').includes(theme));
    if (index < 0) throw new Error(`Missing slide theme: ${theme}`);
    window.DESIGNX.goTo(index + 1); return index + 1;
  }, theme);
  const slide = page.locator(`#slide-${String(number).padStart(2, '0')}.is-active`); await slide.waitFor(); return slide;
}
async function ready(kind) {
  await page.waitForFunction(kind => { const el = document.querySelector(`[data-v8-study="${kind}"]`); return el?.querySelector('.v8-study')?.dataset.ready === 'true' && el.querySelector('iframe')?.contentWindow.__ready && el.querySelector('.v8-study-loading')?.hidden; }, kind);
}
async function snapshot(kind) {
  return host(kind).evaluate((el, kind) => {
    const doc = el.querySelector('iframe')?.contentDocument;
    return { mode: el.querySelector('.v8-study')?.dataset.mode, range: Number(el.querySelector('input')?.value), play: el.querySelector('[data-v8-study-play]')?.textContent, caption: el.querySelector('output')?.textContent,
      childPosition: kind === 'growth' ? Number(doc?.getElementById('scrub')?.value) : parseFloat(doc?.getElementById('fill')?.style.width || 'NaN') * 10 };
  }, kind);
}
async function pausedStable(kind) {
  const before = await snapshot(kind); assert.equal(before.play, 'Play', `${kind} should be paused`); await frames();
  const after = await snapshot(kind); assert.equal(after.range, before.range, 'Parent timeline moved while paused'); assert.equal(after.childPosition, before.childPosition, 'Child drawing moved while paused'); return after;
}
async function setRange(kind, value) {
  await host(kind).locator('input').evaluate((el, value) => { el.value = String(value); el.dispatchEvent(new Event('input', { bubbles: true })); }, value);
  await frames(2); const state = await pausedStable(kind); assert.equal(state.range, value); assert.ok(Math.abs(state.childPosition - value) <= 1, `Child seek ${state.childPosition} differs from ${value}`); return state;
}
async function screenshot(name, locator = page.locator('.slide.is-active')) {
  await page.evaluate(() => document.fonts.ready); await locator.evaluate(el => Promise.all([...el.querySelectorAll('img')].map(img => img.decode().catch(() => {}))));
  await frames(2); await locator.screenshot({ path: resolve(root, `.qa/${name}.png`) });
}
async function openStudy(kind) { await page.locator(`.slide.is-active [data-v8-open="${kind}"]`).click(); await page.locator('.v8-study-dialog[open]').waitFor(); await ready(kind); }
async function closeStudy() { await page.locator('.v8-study-dialog[open]').getByRole('button', { name: 'Return to slide ×', exact: true }).click(); await page.waitForFunction(() => !document.querySelector('.v8-study-dialog')?.open); }
async function factoryReady(viewer, id) { await page.waitForFunction(({ viewer, id }) => { const state = window.DESIGNX_FACTORY?.getStates().find(item => item.viewer === viewer); return state?.id === id && state.duration > 0; }, { viewer, id }); }

await mkdir(resolve(root, '.qa'), { recursive: true });
try {
  console.log('[v8 QA] Loading edition 08'); await page.goto(href); await page.waitForFunction(() => Boolean(window.DESIGNX && window.DESIGNX_V8_STORY));
  result.slides = await page.evaluate(() => window.DESIGNX_SLIDES.map((slide, i) => ({ number: i + 1, title: slide.title, theme: slide.theme })));
  await test('Twenty-slide narrative preserves original material and interleaves two new drawings', async () => {
    assert.deepEqual(result.slides.map(slide => slide.theme.split(' ')[0]), expectedThemes); assert.equal(await page.evaluate(() => window.DESIGNX_V8_STORY.length), 20);
    assert.match(await page.locator('body').getAttribute('class'), /designx-v7/); assert.match(await page.locator('body').getAttribute('class'), /designx-v8/);
  });
  await test('Customer discussions and proposed commercial terms remain intact', async () => {
    const buyers = await activate('buyers-slide');
    for (const label of ['Private gardens', 'Cultural destinations', 'Hospitality', 'In discussion']) assert.match(await buyers.innerText(), new RegExp(label, 'i'));
    for (const name of ['Eden Project', 'The Newt', '25hours']) assert.equal(await buyers.getByRole('img', { name, exact: true }).count(), 1);
    assert.match(await buyers.innerText(), /not signed commissions/i); await screenshot('slide-02-customers', buyers);
    const offer = await activate('v7-commercial-model-slide');
    for (const pattern of [/£65,000/, /Deducted from total build cost/i, /Fixed\s+build price/i, /Annual\s+care/i]) assert.match(await offer.innerText(), pattern);
    await screenshot('slide-10-commercial', offer);
  });
  await test('Growth tabs, paused seeking, playback and enlargement retain the chosen view', async () => {
    const slide = await activate('v7-growth-slide'); await ready('growth');
    for (const [index, mode] of ['space', 'light', 'time'].entries()) { await slide.locator(`[data-v7-growth="${index}"]`).click(); assert.equal((await snapshot('growth')).mode, mode); assert.equal(await slide.locator(`[data-v7-growth="${index}"]`).getAttribute('aria-pressed'), 'true'); await setRange('growth', 437); }
    await host('growth').getByRole('button', { name: 'Winter', exact: true }).click(); assert.match((await pausedStable('growth')).caption, /winter/i);
    await host('growth').getByRole('button', { name: 'Summer', exact: true }).click(); assert.match((await pausedStable('growth')).caption, /summer/i); await screenshot('slide-03-growth', slide);
    await slide.locator('[data-v7-growth="1"]').click(); assert.equal(await host('growth').getByRole('button', { name: 'Winter', exact: true }).count(), 0);
    await host('growth').getByRole('button', { name: 'Noon', exact: true }).click(); assert.match((await pausedStable('growth')).caption, /noon/i);
    const before = await setRange('growth', 555); await openStudy('growth'); assert.deepEqual(await pausedStable('growth'), before, 'Enlarging must preserve mode, position and pause');
    await screenshot('growth-enlarged', page.locator('.v8-study-dialog[open]')); await closeStudy(); await ready('growth'); assert.deepEqual(await pausedStable('growth'), before, 'Returning must preserve the same drawing');
    assert.equal(await page.evaluate(() => document.activeElement?.dataset.v8Open), 'growth');
    await host('growth').locator('[data-v8-study-play]').click(); await page.waitForFunction(() => Number(document.querySelector('[data-v8-study="growth"] input').value) > 555);
    await host('growth').locator('[data-v8-study-play]').click(); const paused = await pausedStable('growth');
    await activate('v7-anatomy-slide'); assert.equal(await host('growth').locator('iframe').count(), 0);
    await activate('v7-growth-slide'); await ready('growth'); assert.deepEqual(await pausedStable('growth'), paused);
  });
  await test('Pier exploration preserves time and other intentions remain placeholders', async () => {
    const slide = await activate('v7-anatomy-slide'); await slide.locator('[data-v7-intent="1"]').click();
    assert.equal(await slide.locator('.v7-drawing-note').isVisible(), true); assert.equal(await slide.locator('.v8-pier-example').isVisible(), false);
    await slide.locator('[data-v7-intent="0"]').click(); assert.equal(await slide.locator('.v8-pier-example').isVisible(), true); await screenshot('slide-05-pier', slide); await openStudy('pier');
    for (const name of ['Planted', 'Shaded', 'Piers open', 'Grown again']) { await host('pier').getByRole('button', { name, exact: true }).click(); assert.ok((await pausedStable('pier')).caption.length); }
    await setRange('pier', 555); await host('pier').locator('[data-v8-study-play]').click(); await page.waitForFunction(() => Number(document.querySelector('[data-v8-study="pier"] input').value) > 555);
    await host('pier').locator('[data-v8-study-play]').click(); const before = await pausedStable('pier'); await screenshot('pier-enlarged', page.locator('.v8-study-dialog[open]'));
    await closeStudy(); await openStudy('pier'); assert.deepEqual(await pausedStable('pier'), before, 'Reopening must retain the paused pier'); await closeStudy();
  });
  await test('Original factory overview and Form / Measure / Machine controls work', async () => {
    const overview = await activate('factory-slide'); await factoryReady('overview', 'overview'); await screenshot('slide-08-factory', overview);
    assert.equal(await overview.locator('[data-factory-focus]').count(), 1); await overview.locator('[data-factory-notes]').click(); await page.locator('#factory-notes[open]').waitFor();
    await page.locator('#factory-notes').getByRole('button', { name: 'Close drawing dialog', exact: true }).click();
    await page.frameLocator('.slide.is-active [data-factory-surface] iframe').locator('[data-factory-station="05-press"]').press('Enter');
    await page.waitForFunction(() => document.querySelector('#factory-enlarged[open] iframe')?.contentWindow.BOWER_FACTORY?.getState().id === '05-press');
    assert.equal(await page.locator('#factory-enlarged [data-factory-next]').count(), 1);
    await page.locator('#factory-enlarged').getByRole('button', { name: 'Back to the whole factory', exact: true }).click();
    await page.waitForFunction(() => !document.querySelector('#factory-enlarged'));
    const focus = await activate('factory-focus-slide'); await factoryReady('focus', '05-press');
    for (const id of ['07-scan', '11-cut', '05-press']) { await focus.locator(`[data-factory-id="${id}"]`).click(); await factoryReady('focus', id); assert.equal(await focus.locator(`[data-factory-id="${id}"]`).getAttribute('aria-pressed'), 'true'); }
    if (await focus.locator('[data-factory-play]').innerText() === 'Pause') await focus.locator('[data-factory-play]').click();
    await focus.locator('[data-factory-seek]').evaluate(el => { el.value = '42'; el.dispatchEvent(new Event('input', { bubbles: true })); });
    await page.waitForFunction(() => { const state = window.DESIGNX_FACTORY.getStates().find(item => item.viewer === 'focus'); return Math.abs(state.time / state.duration - .42) < .001 && !state.playing; });
    const before = await page.evaluate(() => window.DESIGNX_FACTORY.getStates().find(item => item.viewer === 'focus').time); await frames();
    assert.equal(await page.evaluate(() => window.DESIGNX_FACTORY.getStates().find(item => item.viewer === 'focus').time), before); await screenshot('slide-09-factory-focus', focus);
  });
  await test('Index, notes, new drawing slots and print link remain usable', async () => {
    await screenshot('slide-04-ground', await activate('v8-ground-slide')); await screenshot('slide-11-care', await activate('v8-care-slide'));
    await page.locator('#open-index').click(); assert.equal(await page.locator('#slide-index[open] [data-go]').count(), 20);
    await page.locator('#slide-index [data-go]').last().click(); assert.equal(await page.evaluate(() => window.DESIGNX.current), 20);
    await page.locator('#show-notes').click(); assert.match(await page.locator('#notes-content').innerText(), /Story connection|Continue to the next slide|Drawing plan/); await page.locator('[data-close-dialog="speaker-notes"]').click();
    const print = new URL(await page.locator('#pdf-link').getAttribute('href'), href); assert.equal(print.searchParams.get('print'), '1'); assert.ok(print.pathname.includes('/v8'));
  });
  await test('Static reading view has twenty scenes, complete factory diagrams and no broken images', async () => {
    const print = new URL(href); print.search = '?print=1'; await page.goto(print.href); await page.waitForFunction(() => Boolean(window.DESIGNX));
    await page.evaluate(() => Promise.race([Promise.all([window.DESIGNX_READY, window.DESIGNX_FACTORY_READY]), new Promise((_, reject) => setTimeout(() => reject(new Error('Static factory preparation exceeded 20 seconds')), 20000))]));
    assert.equal(await page.locator('.slide.is-active').count(), 20); assert.equal(await page.locator('[data-v8-study] iframe').count(), 0); assert.equal(await page.locator('[data-factory-poster] svg').count(), 4);
    const images = await page.locator('.slide img').evaluateAll(images => images.map(img => ({ src: img.currentSrc || img.src, complete: img.complete, width: img.naturalWidth })));
    assert.ok(images.length); assert.deepEqual(images.filter(img => !img.complete || !img.width), []);
  });
  await test('Story map loads and no edition 09 dependencies remain', async () => {
    await page.goto(new URL('story-map.html', href).href); await page.waitForLoadState('domcontentloaded'); assert.match(await page.locator('body').innerText(), /story|presentation|drawing/i);
    await page.screenshot({ path: resolve(root, '.qa/story-map.png'), fullPage: true }); assert.deepEqual([...dependencies].filter(url => /\/v9(?:\/|$)/.test(new URL(url).pathname)), []);
  });
} catch (error) { result.failures.push({ name: 'Setup or navigation', message: error.stack || error.message }); }
finally {
  await browser.close(); await writeFile(resolve(root, '.qa/check-result.json'), JSON.stringify(result, null, 2)); console.log(JSON.stringify(result, null, 2));
  if (result.failures.length || result.errors.length || result.missingAssets.length || result.failedRequests.length || result.externalRequests.length) process.exitCode = 1;
}
