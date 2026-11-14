// A film of the line of time: the studio's own drawing, taken frame by frame and put together.
//   node pipeline/film.mjs [--name=approach-ink] [--view=approach|drawing|inside] [--timber=ink|wood|bare]
//                          [--format=both|landscape|portrait] [--run=trained-10y]
//                          [--fps=30] [--build=12] [--grow=36] [--hold=2] [--to-the-end] [--keep-frames]
//                          [--crf=17]        how hard the film is packed: lower is finer and larger (a moving camera
//                                            changes every pixel of every frame, and is packed at 21 unless told)
//                          [--camera=tour]   a camera that moves: once round the building as it goes up and grows,
//                                            in under the arch in front, and up into the crown from underneath
// Writes exports/<name>/<name>-16x9.mp4 (1920 x 1080, for a presentation) and <name>-9x16.mp4 (1080 x 1920, for
// a phone), each with a still of its last frame beside it.
//
// Nothing is drawn differently for a film. The script starts the studio, opens it in a headless Edge or Chrome,
// and asks it for each frame in turn (window.studio.film): the same page, the same timber and plants, with the
// buttons hidden. Each frame is worked out in full however long that takes, so a film plays smoothly on any
// machine although the studio itself may not.
//
// --build and --grow are how many seconds the assembly and the ten years take; the building stands for a second
// between them as the plants go in, and the last frame is held for --hold seconds.
import { execFileSync, spawn } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const options = Object.fromEntries(process.argv.slice(2).filter((a) => a.startsWith('--')).map((a) => a.slice(2).split('=')));
const touring = options.camera === 'tour';
const view = touring ? 'approach' : (options.view ?? 'approach');
const timber = options.timber ?? 'ink';
const name = options.name ?? `${touring ? 'tour' : view}-${timber}`;
const fps = Number(options.fps ?? 30);
const seconds = { build: Number(options.build ?? 12), planting: 1, grow: Number(options.grow ?? 36), hold: Number(options.hold ?? 2) };
/** The sheet in the page's own units, drawn at twice that, so that type and line keep the weight they have on a good screen. */
const FORMATS = {
  landscape: { tag: '16x9', width: 960, height: 540 },
  portrait: { tag: '9x16', width: 540, height: 960 },
};
const SCALE = 2;
const formats = (options.format ?? 'both') === 'both' ? ['landscape', 'portrait'] : [options.format];
const out = resolve(root, 'exports', name);
const PORT = 5317;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const horti = resolve(process.env.HORTI_DIR ?? resolve(root, '../Horti-code-ture'));
const ffmpeg = createRequire(import.meta.url)('ffmpeg-static');
if (!ffmpeg || !existsSync(ffmpeg)) throw new Error('ffmpeg is not here: run npm install in this repository');

const BROWSERS = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
];
const exe = process.env.BROWSER_EXE ?? BROWSERS.find((p) => existsSync(p));
if (!exe) throw new Error('no Chrome or Edge found: set BROWSER_EXE to a Chromium browser');

// ---- the studio, on a port of its own ---------------------------------------------------------------------------
const server = spawn(process.execPath, [resolve(horti, 'node_modules/vite/bin/vite.js'), '--config', resolve(root, 'studio/vite.config.js'), '--port', String(PORT), '--strictPort'], {
  cwd: root,
  stdio: 'ignore',
  env: { ...process.env, STUDIO_CACHE: '.vite-film' },
});
const profile = mkdtempSync(join(tmpdir(), 'bower-film-'));
const debugPort = 9400 + Math.floor(Math.random() * 300);
let browser = null;
const close = () => {
  browser?.kill();
  server.kill();
  try {
    rmSync(profile, { recursive: true, force: true });
  } catch {
    // the browser may still hold its profile for a moment: it is in the temporary folder either way
  }
};
process.on('exit', close);
process.on('SIGINT', () => process.exit(130));

for (let i = 0; ; i++) {
  try {
    if ((await fetch(`http://localhost:${PORT}/`)).ok) break;
  } catch {
    if (i > 120) throw new Error('the studio did not start');
  }
  await sleep(250);
}

// ---- the browser, spoken to over the DevTools protocol (no dependencies: Node's own fetch and WebSocket) --------
browser = spawn(
  exe,
  ['--headless=new', `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--hide-scrollbars', '--ignore-gpu-blocklist', '--enable-gpu', '--use-angle=d3d11', '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows', 'about:blank'],
  { stdio: 'ignore' },
);

async function openPage() {
  let target;
  for (let i = 0; i < 80 && !target; i++) {
    try {
      target = await (await fetch(`http://127.0.0.1:${debugPort}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
    } catch {
      await sleep(250);
    }
  }
  if (!target) throw new Error('the browser did not start');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  const pending = new Map();
  const problems = [];
  let nextId = 1;
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) {
      const { ok, fail } = pending.get(m.id);
      pending.delete(m.id);
      if (m.error) fail(new Error(JSON.stringify(m.error)));
      else ok(m.result);
    } else if (m.method === 'Runtime.exceptionThrown') problems.push(m.params.exceptionDetails.exception?.description ?? m.params.exceptionDetails.text);
  };
  const send = (method, params = {}) =>
    new Promise((ok, fail) => {
      const id = nextId++;
      pending.set(id, { ok, fail });
      ws.send(JSON.stringify({ id, method, params }));
    });
  const js = async (expression) => {
    const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? r.exceptionDetails.text);
    return r.result.value;
  };
  await send('Runtime.enable');
  await send('Page.enable');
  return { send, js, problems, close: () => ws.close() };
}

/** Where on the line of time the frame at `t` seconds stands. */
function momentAt(t, line) {
  if (t < seconds.build) return line.start + (t / seconds.build) * (line.planted - line.start);
  if (t < seconds.build + seconds.planting) return line.planted;
  const grown = (t - seconds.build - seconds.planting) / seconds.grow;
  // it ends on the last midsummer of the run, in full leaf, unless the whole run is asked for
  const end = 'to-the-end' in options ? line.last : line.lastSummer;
  return grown >= 1 ? end : line.planted + grown * (end - line.planted);
}

mkdirSync(out, { recursive: true });
const total = Math.round((seconds.build + seconds.planting + seconds.grow + seconds.hold) * fps);

for (const key of formats) {
  const format = FORMATS[key];
  if (!format) throw new Error(`--format is landscape, portrait or both, not "${key}"`);
  const file = `${name}-${format.tag}`;
  const frames = resolve(out, 'frames', format.tag);
  rmSync(frames, { recursive: true, force: true });
  mkdirSync(frames, { recursive: true });

  const page = await openPage();
  await page.send('Emulation.setDeviceMetricsOverride', { width: format.width, height: format.height, deviceScaleFactor: SCALE, mobile: false });
  const query = new URLSearchParams({ film: '', ...(touring ? { tour: '' } : {}), view, timber, build: '0', ...(options.run ? { run: options.run } : {}), ...(options.lines ? { lines: options.lines } : {}) });
  await page.send('Page.navigate', { url: `http://localhost:${PORT}/?${query}` });
  // reading ten years of growth takes a while
  let ready = false;
  for (let i = 0; i < 1200 && !ready; i++) {
    await sleep(500);
    ready = await page.js('typeof window.studio === "object"').catch(() => false);
    if (page.problems.length) throw new Error(`the studio failed to open:\n  ${page.problems.join('\n  ')}`);
  }
  if (!ready) throw new Error('the studio did not open in ten minutes');
  const line = await page.js('window.studio.line()');
  const gpu = await page.js(`(() => { const gl = window.studio.paper.renderer.getContext(); const e = gl.getExtension('WEBGL_debug_renderer_info'); return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : 'unknown'; })()`);
  console.log(`${file}: ${format.width * SCALE} x ${format.height * SCALE}, ${total} frames at ${fps} a second, drawn by ${gpu}`);

  // one picture and no film: --still=day:3399 (a day of growth) or --still=build:0.5 (a share of the assembly)
  if (options.still) {
    const [what, value] = options.still.split(':');
    const at = what === 'build' ? line.start + Number(value) * (line.planted - line.start) : Number(value);
    await page.js(`window.studio.film(${at}, 0)`);
    await page.js(`window.studio.film(${at}, 0)`);
    const shot = await page.send('Page.captureScreenshot', { format: 'jpeg', quality: 95 });
    writeFileSync(resolve(out, `${file}.jpg`), Buffer.from(shot.data, 'base64'));
    console.log(`  written: ${resolve(out, `${file}.jpg`)}`);
    page.close();
    continue;
  }

  const began = performance.now();
  for (let i = 0; i < total; i++) {
    await page.js(`window.studio.film(${momentAt(i / fps, line)}, ${1 / fps}${touring ? `, [${i / fps}, ${total / fps}]` : ''})`);
    const shot = await page.send('Page.captureScreenshot', { format: 'jpeg', quality: 94 });
    writeFileSync(resolve(frames, `${String(i).padStart(5, '0')}.jpg`), Buffer.from(shot.data, 'base64'));
    if (i % 150 === 149) {
      const each = (performance.now() - began) / (i + 1);
      console.log(`  ${i + 1} of ${total}: ${(each / 1000).toFixed(2)} s a frame, about ${Math.ceil(((total - i - 1) * each) / 60000)} min to go`);
    }
    if (page.problems.length) throw new Error(`the studio failed while filming:\n  ${page.problems.join('\n  ')}`);
  }
  page.close();

  execFileSync(ffmpeg, ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', resolve(frames, '%05d.jpg'), '-c:v', 'libx264', '-preset', 'slow', '-crf', String(options.crf ?? (touring ? 21 : 17)), '-pix_fmt', 'yuv420p', '-movflags', '+faststart', resolve(out, `${file}.mp4`)]);
  copyFileSync(resolve(frames, `${String(total - 1).padStart(5, '0')}.jpg`), resolve(out, `${file}.jpg`));
  if (!('keep-frames' in options)) rmSync(frames, { recursive: true, force: true });
  console.log(`  written: ${resolve(out, `${file}.mp4`)} in ${((performance.now() - began) / 60000).toFixed(1)} min`);
}
if (!('keep-frames' in options)) rmSync(resolve(out, 'frames'), { recursive: true, force: true });
process.exit(0);
