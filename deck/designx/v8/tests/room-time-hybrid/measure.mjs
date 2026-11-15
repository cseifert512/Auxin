// Repeatable, isolated delivery comparison. This script changes no deck/source assets.
// node measure.mjs [--variants=original,hybrid,compressed] [--profiles=local,slow]
//                  [--screenshots=0] [--budget=180] [--port=0] [--url=http://.../]
// Measurements and screenshots are written only to this test's ignored .qa/ folder.
import { createServer } from 'node:http';
import { createReadStream, existsSync } from 'node:fs';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
import { performance } from 'node:perf_hooks';

const here = dirname(fileURLToPath(import.meta.url));
const deckRoot = resolve(here, '../../../..');
const out = resolve(here, '.qa');
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/BOWER/Bower_Web/node_modules/playwright');
const options = Object.fromEntries(process.argv.slice(2).map(value => value.replace(/^--/, '').split('=')));
const variants = (options.variants || 'original,hybrid,compressed').split(',');
const profiles = (options.profiles || 'local,slow').split(',');
const screenshotTimes = options.screenshots === '0' ? [] : [6, 13, 28, 42, 49];
const budgetSeconds = Number(options.budget || 180);
const started = performance.now();
const remaining = () => Math.max(0, budgetSeconds * 1000 - (performance.now() - started));
const limits = {
  local: { label: 'Unthrottled localhost', latencyMs: 0, downloadBytesPerSecond: -1 },
  slow: { label: '5 Mbps download / 80 ms added latency', latencyMs: 80, downloadBytesPerSecond: 5_000_000 / 8 },
};
for (const id of profiles) if (!limits[id]) throw new Error(`Unknown profile ${id}`);
for (const id of variants) if (!['original', 'hybrid', 'compressed'].includes(id)) throw new Error(`Unknown variant ${id}`);
await mkdir(out, { recursive: true });
const manifest = JSON.parse(await readFile(resolve(here, 'manifest.json'), 'utf8'));
const expected = variants.filter(id => manifest[id]);
const report = {
  schema: 'bower.room-time-delivery-measurement/1',
  measuredAt: new Date().toISOString(),
  protocol: {
    viewport: { width: 1600, height: 1100 }, deviceScaleFactor: 1,
    browserCache: 'Disabled through CDP; fresh browser context for every trial',
    profiles: profiles.map(id => ({ id, ...limits[id] })),
    playback: options['slow-playback']==='1'?'Unthrottled: seven seconds from t42; throttled: complete sequence from t0':'On unthrottled trials only: seek to 42 seconds, play for 7 wall-clock seconds, pause',
    screenshots: screenshotTimes,
    note: 'The added latency is the CDP latency parameter. This local test does not measure public hosting, DNS, TLS or real-world mobile graphics.',
  },
  trials: [], imageComparisons: [], errors: [],
  declaredAssets: Object.fromEntries(expected.map(id => [id, { src: manifest[id].src, mediaBytes: manifest[id].bytes, totalBytes: manifest[id].totalBytes ?? manifest[id].payloadBytes ?? null }])),
  limitations: [
    'One trial per variant/profile by default; results are exploratory, not statistically stable benchmarks.',
    'CPU render-submission times and display callbacks are not GPU execution times.',
    'Initial transferred bytes include HTML, CSS, scripts, manifest, poster and media/model traffic received up to readiness; the complete media file need not be downloaded.',
    options['slow-playback']==='1'?'The slow profile includes full playback; detailed screenshots and seven-second decoder samples use the local profile.':'The slow profile measures startup only. Playback and visual captures use the unthrottled local profile.',
    'A new browser context clears page/media caches, but operating-system file caches and GPU driver shader caches can remain warm.',
    'Pixel differences between variants include compression, foliage resolution and any scene-rendering differences. They are not a perceptual quality verdict.',
    'The new bake and the original film can have different wind phase after the material transition. Bare-timber source/client comparisons isolate camera/material alignment.',
  ],
};

const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.mp4': 'video/mp4', '.glb': 'model/gltf-binary', '.woff2': 'font/woff2' };
const textTypes = new Set(['.html', '.js', '.mjs', '.json', '.css', '.svg']);
const compressed = new Map();
let server, browser, budgetTimer;

async function localServer() {
  server = createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      if (pathname === '/favicon.ico') { response.writeHead(204).end(); return; }
      let file = resolve(deckRoot, `.${pathname}`);
      if (file !== deckRoot && !file.startsWith(deckRoot + sep)) { response.writeHead(403).end(); return; }
      let info = await stat(file);
      if (info.isDirectory()) { file = resolve(file, 'index.html'); info = await stat(file); }
      const extension = extname(file).toLowerCase();
      const headers = { 'Content-Type': types[extension] || 'application/octet-stream', 'Cache-Control': 'no-store', 'Accept-Ranges': 'bytes' };
      const match = /^bytes=(\d*)-(\d*)$/.exec(request.headers.range || '');
      if (match && (match[1] || match[2])) {
        const start = match[1] ? Number(match[1]) : Math.max(0, info.size - Number(match[2]));
        const end = match[1] && match[2] ? Math.min(Number(match[2]), info.size - 1) : info.size - 1;
        if (start > end || start >= info.size) { response.writeHead(416, { 'Content-Range': `bytes */${info.size}` }).end(); return; }
        response.writeHead(206, { ...headers, 'Content-Range': `bytes ${start}-${end}/${info.size}`, 'Content-Length': end - start + 1 });
        if (request.method === 'HEAD') response.end();
        else { const stream = createReadStream(file, { start, end }); response.on('close', () => stream.destroy()); stream.pipe(response); }
      } else if (textTypes.has(extension) && /\bgzip\b/.test(request.headers['accept-encoding'] || '')) {
        let body = compressed.get(file);
        if (!body) { body = gzipSync(await readFile(file), { level: 6 }); compressed.set(file, body); }
        response.writeHead(200, { ...headers, Vary: 'Accept-Encoding', 'Content-Encoding': 'gzip', 'Content-Length': body.length });
        response.end(request.method === 'HEAD' ? undefined : body);
      } else {
        response.writeHead(200, { ...headers, 'Content-Length': info.size });
        if (request.method === 'HEAD') response.end();
        else { const stream = createReadStream(file); response.on('close', () => stream.destroy()); stream.pipe(response); }
      }
    } catch (error) {
      if (!response.headersSent) response.writeHead(error.code === 'ENOENT' ? 404 : 500, { 'Content-Type': 'text/plain' });
      response.end('Asset unavailable');
    }
  });
  await new Promise((yes, no) => { server.once('error', no); server.listen(Number(options.port || 0), '127.0.0.1', yes); });
  const port = server.address().port;
  report.protocol.server = 'Isolated local static HTTP server, no-store, byte ranges, gzip text; binary media/models unchanged';
  return `http://127.0.0.1:${port}/designx/v8/tests/room-time-hybrid/`;
}

function trackNetwork(session) {
  const records = new Map();
  session.on('Network.requestWillBeSent', event => records.set(event.requestId, { url: event.request.url, method: event.request.method, range: event.request.headers.Range || event.request.headers.range || null, receivedEncodedBytes: 0, receivedDecodedBytes: 0 }));
  session.on('Network.responseReceived', event => {
    const item = records.get(event.requestId); if (item) Object.assign(item, { status: event.response.status, mimeType: event.response.mimeType, cache: Boolean(event.response.fromDiskCache || event.response.fromServiceWorker) });
  });
  session.on('Network.dataReceived', event => {
    const item = records.get(event.requestId); if (item) { item.receivedEncodedBytes += event.encodedDataLength || 0; item.receivedDecodedBytes += event.dataLength || 0; }
  });
  session.on('Network.loadingFinished', event => { const item = records.get(event.requestId); if (item) item.finishedEncodedBytes = event.encodedDataLength; });
  session.on('Network.loadingFailed', event => { const item = records.get(event.requestId); if (item) item.failure = event.errorText; });
  const snapshot = () => {
    const requests = [...records.values()].map(item => ({ ...item, encodedBytes: item.finishedEncodedBytes ?? item.receivedEncodedBytes }));
    return { encodedBytes: requests.reduce((n, item) => n + item.encodedBytes, 0), decodedBytes: requests.reduce((n, item) => n + item.receivedDecodedBytes, 0), requests };
  };
  return { snapshot };
}

async function browserSnapshot(page) {
  return page.evaluate(() => {
    const data = window.__roomTimeTest.snapshot();
    const record = data.measurements.find(item => item.id === data.currentVersion);
    return { currentTime: data.currentTime, ready: data.ready, currentVersion: data.currentVersion, playing: data.playing, record, navigationToNowMs: performance.now() };
  });
}

async function samplePlayback(page, trial) {
  const seekBegan = performance.now();
  await page.evaluate(() => window.__roomTimeTest.seek(42));
  trial.seekToDenseMs = performance.now() - seekBegan;
  trial.beforePlayback = await browserSnapshot(page);
  await page.evaluate(() => {
    const video = document.querySelector('#drawing-surface video') || document.querySelector('video');
    const sample = { supported: Boolean(video?.requestVideoFrameCallback), frames: 0, firstMediaTime: null, lastMediaTime: null, maxCallbackGapMs: 0, lastWallTime: null };
    window.__deliveryVideoSample = sample;
    if (sample.supported) {
      const next = (now, metadata) => {
        if (!window.__deliveryVideoSample) return;
        sample.frames++; sample.firstMediaTime ??= metadata.mediaTime; sample.lastMediaTime = metadata.mediaTime;
        if (sample.lastWallTime !== null) sample.maxCallbackGapMs = Math.max(sample.maxCallbackGapMs, now - sample.lastWallTime);
        sample.lastWallTime = now;
        sample.callbackId = video.requestVideoFrameCallback(next);
      };
      sample.callbackId = video.requestVideoFrameCallback(next);
    }
  });
  await page.evaluate(() => window.__roomTimeTest.play());
  const began = performance.now();
  await page.waitForTimeout(7000);
  await page.evaluate(() => window.__roomTimeTest.pause());
  const after = await browserSnapshot(page);
  const callbacks = await page.evaluate(() => {
    const sample = window.__deliveryVideoSample;
    const video = document.querySelector('#drawing-surface video') || document.querySelector('video');
    if (sample?.callbackId && video?.cancelVideoFrameCallback) video.cancelVideoFrameCallback(sample.callbackId);
    window.__deliveryVideoSample = null;
    return sample;
  });
  const before = trial.beforePlayback;
  trial.playback = {
    observedWallMs: performance.now() - began,
    mediaAdvancedSeconds: after.currentTime - before.currentTime,
    droppedFrames: Number.isFinite(after.record.droppedFrames) && Number.isFinite(before.record.droppedFrames) ? after.record.droppedFrames - before.record.droppedFrames : null,
    decodedFrames: Number.isFinite(after.record.decodedFrames) && Number.isFinite(before.record.decodedFrames) ? after.record.decodedFrames - before.record.decodedFrames : null,
    stalls: after.record.stalls - before.record.stalls,
    videoCallbacks: callbacks,
    rendererBefore: before.record.renderer,
    rendererAfter: after.record.renderer,
    displayCallbackRate: after.record.meanCallbackRate,
    note: 'Video callbacks count presented video frames. Display callback rate is the UI requestAnimationFrame cadence. Renderer timings, if supplied, measure CPU submission rather than GPU completion.',
  };
}

async function runTrial(base, id, profile) {
  const trial = { variant: id, profile, errors: [] };
  report.trials.push(trial);
  const context = await browser.newContext({ viewport: report.protocol.viewport, deviceScaleFactor: 1, reducedMotion: 'no-preference', serviceWorkers: 'block' });
  const page = await context.newPage();
  const session = await context.newCDPSession(page);
  const network = trackNetwork(session);
  await session.send('Network.enable');
  await session.send('Network.setCacheDisabled', { cacheDisabled: true });
  const config = limits[profile];
  await session.send('Network.emulateNetworkConditions', { offline: false, latency: config.latencyMs, downloadThroughput: config.downloadBytesPerSecond, uploadThroughput: config.downloadBytesPerSecond, connectionType: profile === 'slow' ? 'cellular4g' : 'ethernet' });
  page.on('pageerror', error => trial.errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') trial.errors.push(message.text()); });
  const url = new URL(base); url.searchParams.set('variant', id);
  const navigationBegan = performance.now();
  try {
    const timeout = Math.min(45000, remaining());
    if (timeout < 1000) throw new Error('Measurement budget exhausted');
    page.setDefaultTimeout(timeout);
    page.setDefaultNavigationTimeout(timeout);
    await page.goto(url.href, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => window.__roomTimeTest?.ready || !document.querySelector('#error-note')?.hidden, null, { timeout: Math.min(45000, remaining()) });
    if (!await page.evaluate(() => window.__roomTimeTest?.ready)) throw new Error(await page.locator('#error-note').textContent());
    trial.navigationToReadyMs = performance.now() - navigationBegan;
    trial.firstFrame = await browserSnapshot(page);
    trial.startupNetwork = network.snapshot();
    console.log(`${profile}/${id}: first drawing ${(trial.navigationToReadyMs / 1000).toFixed(2)} s; ${(trial.startupNetwork.encodedBytes / 1e6).toFixed(2)} MB received`);
    if (profile === 'local' && remaining() > 18000) {
      await samplePlayback(page, trial);
      trial.screenshots = [];
      for (const seconds of screenshotTimes) {
        if (remaining() < 5000) break;
        await page.evaluate(value => window.__roomTimeTest.seek(value), seconds);
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        const file = `${id}-${String(seconds).padStart(2, '0')}.png`;
        // Captures just the scene, excluding the version label/status overlay.
        await page.locator('#drawing-surface').screenshot({ path: resolve(out, file) });
        trial.screenshots.push({ time: seconds, file });
        if(id==='hybrid'){
          await page.evaluate(()=>window.__roomTimeTest.setLayerEnabled(false));
          const raw=await page.locator('#drawing-surface canvas').evaluate(canvas=>canvas.toDataURL('image/png').split(',')[1]);
          await writeFile(resolve(out,`client-base-${seconds}.png`),Buffer.from(raw,'base64'));
          await page.evaluate(()=>window.__roomTimeTest.setLayerEnabled(true));
        }
      }
    }
    if(profile==='slow'&&options['slow-playback']==='1'&&remaining()>75000){
      const before=await browserSnapshot(page),began=performance.now();
      await page.evaluate(()=>window.__roomTimeTest.play());
      let completed=true;
      try{await page.waitForFunction(()=>window.__roomTimeTest.snapshot().currentTime>=50.95,null,{timeout:Math.min(100000,remaining()-5000),polling:250});}
      catch{completed=false;}
      await page.evaluate(()=>window.__roomTimeTest.pause());
      const after=await browserSnapshot(page);
      trial.slowPlayback={completed,wallSeconds:(performance.now()-began)/1000,mediaSeconds:after.currentTime-before.currentTime,
        stalls:after.record.stalls-before.record.stalls,
        droppedFrames:after.record.droppedFrames-before.record.droppedFrames,
        decodedFrames:after.record.decodedFrames-before.record.decodedFrames};
      console.log(`${profile}/${id}: whole playback ${trial.slowPlayback.wallSeconds.toFixed(1)} s, ${trial.slowPlayback.stalls} stalls, completed=${completed}`);
    }
    trial.finalNetwork = network.snapshot();
    trial.final = await browserSnapshot(page);
  } catch (error) {
    trial.error = error.stack || error.message;
    trial.finalNetwork = network.snapshot();
    console.log(`${profile}/${id}: ${error.message}`);
  } finally {
    await context.close().catch(() => {});
    await writeFile(resolve(out, 'measurement-latest.json'), JSON.stringify(report, null, 2) + '\n');
  }
}

async function compareImages() {
  let sharp;
  try { sharp = require('C:/BOWER/Bower_Web/node_modules/sharp'); } catch { return; }
  report.baseAlignment=[];
  for(const time of screenshotTimes){
    if(!report.trials.some(t=>t.variant==='hybrid'&&t.screenshots?.some(s=>s.time===time)))continue;
    const source=resolve(out,`probe-${time}-base.png`),client=resolve(out,`client-base-${time}.png`);
    if(!existsSync(source)||!existsSync(client))continue;
    const a=await sharp(source).removeAlpha().raw().toBuffer(),b=await sharp(client).removeAlpha().raw().toBuffer();
    if(a.length!==b.length){report.baseAlignment.push({time,error:'Source/client dimensions differ'});continue;}
    let abs=0,changed=0;for(let i=0;i<a.length;i++){const d=Math.abs(a[i]-b[i]);abs+=d;if(d>16)changed++;}
    report.baseAlignment.push({time,meanAbsoluteChannelDifference:abs/a.length,fractionChannelsOver16:changed/a.length});
  }
  for (const id of ['hybrid', 'compressed']) for (const time of screenshotTimes) {
    // Do not compare against screenshots left by an earlier partial/filtered run.
    const captured = variant => report.trials.some(trial => trial.profile === 'local' && trial.variant === variant && trial.screenshots?.some(shot => shot.time === time));
    if (!captured('original') || !captured(id)) continue;
    const stem = String(time).padStart(2, '0');
    const aFile = resolve(out, `original-${stem}.png`), bFile = resolve(out, `${id}-${stem}.png`);
    if (!existsSync(aFile) || !existsSync(bFile)) continue;
    const a = await sharp(aFile).removeAlpha().raw().toBuffer({ resolveWithObject: true });
    const b = await sharp(bFile).removeAlpha().raw().toBuffer({ resolveWithObject: true });
    if (a.data.length !== b.data.length) { report.imageComparisons.push({ variant: id, time, error: 'Screenshot dimensions differ' }); continue; }
    let absolute = 0, squares = 0, changedPixels = 0;
    for (let i = 0; i < a.data.length; i += 3) {
      let changed = false;
      for (let channel = 0; channel < 3; channel++) { const delta = Math.abs(a.data[i + channel] - b.data[i + channel]); absolute += delta; squares += delta * delta; changed ||= delta > 16; }
      if (changed) changedPixels++;
    }
    const mse = squares / a.data.length;
    report.imageComparisons.push({ variant: id, time, width: a.info.width, height: a.info.height, meanAbsoluteChannelDifference: absolute / a.data.length, rmse: Math.sqrt(mse), psnrDb: mse ? 10 * Math.log10(255 * 255 / mse) : null, fractionPixelsWithChannelDifferenceOver16: changedPixels / (a.data.length / 3) });
  }
}

function summary() {
  const seconds = value => Number.isFinite(value) ? `${(value / 1000).toFixed(2)} s` : '—';
  const mb = value => Number.isFinite(value) ? `${(value / 1e6).toFixed(2)} MB` : '—';
  const rows = report.trials.map(trial => `| ${trial.profile} | ${trial.variant} | ${seconds(trial.navigationToReadyMs)} | ${mb(trial.startupNetwork?.encodedBytes)} | ${trial.playback ? `${trial.playback.droppedFrames ?? '—'} / ${trial.playback.decodedFrames ?? '—'}` : '—'} | ${trial.playback?.stalls ?? '—'} | ${trial.error ? 'Failed; see JSON' : 'Completed'} |`);
  return `# Room through time: delivery measurements\n\nMeasured ${report.measuredAt}. Browser: ${report.browser?.version || 'unknown'}.\n\n| Profile | Version | Navigation to first drawing | Bytes received by first drawing | Dropped / decoded during sample | Stalls | Status |\n|---|---|---:|---:|---:|---:|---|\n${rows.join('\n')}\n\n${report.limitations.map(item => `- ${item}`).join('\n')}\n\nHardware/renderer information, request accounting, submission timings and screenshot comparison data are in measurement-latest.json. No perceptual quality pass is inferred from pixel metrics.\n`;
}

try {
  const base = options.url || await localServer();
  const executablePath = process.env.CHROMIUM_PATH || [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Users/cseif/AppData/Local/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-win64/chrome-headless-shell.exe',
  ].find(existsSync);
  browser = await chromium.launch({ headless: true, executablePath, args: ['--enable-gpu', '--ignore-gpu-blocklist', '--disable-background-timer-throttling', '--disable-renderer-backgrounding', ...(process.platform === 'win32' ? ['--use-angle=d3d11'] : [])] });
  report.browser = { executablePath, version: browser.version() };
  try { const system = await browser.newBrowserCDPSession(); const info = await system.send('SystemInfo.getInfo'); report.browser.gpu = info.gpu; await system.detach(); } catch (error) { report.browser.gpuReadError = error.message; }
  budgetTimer = setTimeout(() => { report.errors.push(`Stopped at ${budgetSeconds} second measurement budget`); browser.close().catch(() => {}); }, Math.max(1000, remaining()));
  for (const profile of profiles) for (const id of expected) {
    if (remaining() < 5000) { report.errors.push(`Budget prevented ${profile}/${id}`); continue; }
    await runTrial(base, id, profile);
  }
  await compareImages();
} catch (error) { report.errors.push(error.stack || error.message); }
finally {
  clearTimeout(budgetTimer);
  await browser?.close().catch(() => {});
  if (server) { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
  report.elapsedSeconds = (performance.now() - started) / 1000;
  await writeFile(resolve(out, 'measurement-latest.json'), JSON.stringify(report, null, 2) + '\n');
  await writeFile(resolve(out, 'measurement-summary.md'), summary());
  console.log(`Saved ${resolve(out, 'measurement-latest.json')}`);
}
if (report.errors.length || report.trials.some(trial => trial.error || trial.errors.length)) process.exitCode = 1;
