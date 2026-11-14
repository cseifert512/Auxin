// The same view on the same day from several grown runs of one planting: what is the same every time, and what is not.
//   node pipeline/again.mjs [name]        (deck/<name>/piece.json; "grown-again" if none is named)
//     --frames=keep     measure and lay out again from the pictures already made, drawing nothing
// Reads  deck/<name>/piece.json and the page beside it (index.html)
// Writes exports/deck/<as>/   one picture for each run, what stayed and what differs between them, the room,
//                             measures.js, the page, and still.png for print
//
// The runs are of one building, one planting and one care, and differ only in the simulator's chance (its seed).
// A place in the picture is "the same" where every run draws the same thing there, to within `tolerance` of 255.
// For each region marked in the description, the measure is: of the timber and plants any run draws there (shade
// is not counted), the share that differs.
// That is a measure of these pictures, not of plants: it says how far three runs of a scenario agree.
//
// One run is ten years of growth, so one studio is open at a time and it is stopped between runs. It is on a
// port of its own, so that it does not meet a plate being made.
import { execFileSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { root, startStudio } from './headless.mjs';

const ffmpeg = createRequire(import.meta.url)('ffmpeg-static');
const name = process.argv.slice(2).find((a) => !a.startsWith('--')) ?? 'grown-again';
const options = Object.fromEntries(process.argv.slice(2).filter((a) => a.startsWith('--')).map((a) => a.slice(2).split('=')));
const source = resolve(root, 'deck', name);
const piece = JSON.parse(readFileSync(resolve(source, 'piece.json'), 'utf8'));
const out = resolve(root, 'exports/deck', piece.as ?? name);
// the full pictures are kept beside the exports for measuring again, and are not in git: the page reads smaller ones
const made = resolve(root, 'exports/deck/.again', piece.as ?? name);
mkdirSync(resolve(out, 'frames'), { recursive: true });
mkdirSync(made, { recursive: true });

const scale = piece.scale ?? 2;
const [w, h] = piece.size;
const [pw, ph] = [w * scale, h * scale];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const png = (id) => resolve(made, `${id}.png`);
const hex = (s) => [0, 2, 4].map((i) => Number.parseInt(s.slice(i, i + 2), 16));
const run = (args, more = {}) => execFileSync(ffmpeg, ['-y', '-loglevel', 'error', ...args], { maxBuffer: 1 << 28, ...more });

// ---- the pictures: one studio, one run, then the next -------------------------------------------------------------
if (options.frames !== 'keep') {
  const ask = (p) => `window.studio.plate({ ...${JSON.stringify(p)}, at: window.studio.moment(${JSON.stringify(piece.at)}) })`;
  // A page that meets the studio's source while it does not compile (another session may be editing it) waits
  // for ever and says nothing. A run opens in a quarter of a minute, so one that has not in 90 s is tried again.
  const within = (promise, ms, what) => {
    promise.catch(() => {});
    return Promise.race([promise, sleep(ms).then(() => Promise.reject(new Error(`${what} did not open in ${ms / 1000} s`)))]);
  };
  for (const [i, grown] of piece.runs.entries()) {
    for (let attempt = 1; ; attempt++) {
      const began = performance.now();
      const studio = await startStudio(5328, piece.snapshot ?? null);
      try {
        const page = await within(studio.open({ plate: '', paper: piece.paper, ink: piece.ink, timber: piece.timber ?? 'ink', build: '1', run: grown }, { width: w, height: h, scale }), 90000, grown);
        const drawn = await page.js('window.studio.state().run');
        if (drawn !== grown) throw new Error(`the studio drew ${drawn}, not ${grown}: is that run grown for ${piece.snapshot ?? 'this building'}?`);
        await page.js(ask({ view: piece.view, lookAt: piece.lookAt, zoom: piece.zoom, sun: piece.sun }));
        writeFileSync(png(`run-${i}`), await page.shot());
        if (i === 0 && piece.room) {
          await page.size(piece.room.size[0], piece.room.size[1], scale);
          await page.js(ask({ view: piece.view, sun: piece.sun }));
          writeFileSync(png('room'), await page.shot());
        }
        console.log(`  ${grown} in ${((performance.now() - began) / 1000).toFixed(0)} s`);
        break;
      } catch (problem) {
        if (attempt === 3 || !/did not open/.test(problem.message)) throw problem;
        console.log(`  ${grown}: ${problem.message}; trying again`);
      } finally {
        studio.stop();
        await sleep(3000);
      }
    }
  }
}

// ---- what stayed, what differs --------------------------------------------------------------------------------------
const raw = piece.runs.map((_, i) => {
  if (!existsSync(png(`run-${i}`))) throw new Error(`no picture of run ${i}: make them first, without --frames=keep`);
  return run(['-i', png(`run-${i}`), '-f', 'rawvideo', '-pix_fmt', 'rgba', '-']);
});
const n = pw * ph;
if (raw.some((b) => b.length !== n * 4)) throw new Error(`the pictures are not ${pw} x ${ph}: was "size" changed since they were made?`);
const paper = hex(piece.paper);
const red = hex(piece.red ?? 'B4492F');
const tolerance = piece.tolerance ?? 28;
// each picture as it lies on the page's paper, so that a clear place and a place drawn in paper colour are the same
const onPaper = (b, p, c) => (b[p * 4 + c] * b[p * 4 + 3] + paper[c] * (255 - b[p * 4 + 3])) / 255;
const differs = new Uint8Array(n);
const drawn = new Uint8Array(n);
for (let p = 0; p < n; p++) {
  let far = 0;
  let ink = 0;
  for (let a = 0; a < raw.length; a++) {
    // timber and plants are drawn solid; shade is a thin wash over the floor, shown but not counted
    if (raw[a][p * 4 + 3] > 128) ink = 1;
    for (let b = a + 1; b < raw.length; b++) for (let c = 0; c < 3; c++) far = Math.max(far, Math.abs(onPaper(raw[a], p, c) - onPaper(raw[b], p, c)));
  }
  drawn[p] = ink;
  differs[p] = far > tolerance ? 1 : 0;
}
// stayed: the first run's picture wherever all agree. differs: every run's picture at once, in the one red.
const stayed = Buffer.alloc(n * 4);
const unlike = Buffer.alloc(n * 4);
for (let p = 0; p < n; p++) {
  if (!differs[p]) raw[0].copy(stayed, p * 4, p * 4, p * 4 + 4);
  else {
    let alpha = 0;
    let dark = 0;
    for (const b of raw) {
      alpha = Math.max(alpha, b[p * 4 + 3]);
      // how dark each run draws this place, so that leaf and stem still read inside the red
      dark += (1 - (0.3 * onPaper(b, p, 0) + 0.59 * onPaper(b, p, 1) + 0.11 * onPaper(b, p, 2)) / 255) / raw.length;
    }
    const k = 0.55 + 0.45 * Math.min(1, dark * 1.6);
    for (let c = 0; c < 3; c++) unlike[p * 4 + c] = Math.round(red[c] * k + paper[c] * (1 - k));
    unlike[p * 4 + 3] = alpha;
  }
}
const write = (buffer, id) => run(['-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${pw}x${ph}`, '-i', '-', png(id)], { input: buffer });
write(stayed, 'stayed');
write(unlike, 'differs');

// ---- the measure in each marked place -----------------------------------------------------------------------------
const regions = (piece.regions ?? []).map((region) => {
  const [x0, y0, x1, y1] = [region.box[0] * pw, region.box[1] * ph, (region.box[0] + region.box[2]) * pw, (region.box[1] + region.box[3]) * ph].map(Math.round);
  let any = 0;
  let unlikeHere = 0;
  for (let y = y0; y < y1; y++) {
    for (let x = x0; x < x1; x++) {
      any += drawn[y * pw + x];
      unlikeHere += drawn[y * pw + x] & differs[y * pw + x];
    }
  }
  return { ...region, share: any ? Number((unlikeHere / any).toFixed(3)) : 0 };
});
let all = 0;
let allUnlike = 0;
for (let p = 0; p < n; p++) {
  all += drawn[p];
  allUnlike += drawn[p] & differs[p];
}

// ---- for the page ---------------------------------------------------------------------------------------------------
const pictures = [...piece.runs.map((_, i) => `run-${i}`), 'stayed', 'differs', ...(piece.room ? ['room'] : [])];
for (const id of pictures) run(['-i', png(id), '-c:v', 'libwebp', '-quality', '88', resolve(out, 'frames', `${id}.webp`)]);
const measures = {
  name: piece.as ?? name,
  for: piece.for,
  statement: piece.statement ?? '',
  paper: `#${piece.paper}`,
  ink: `#${piece.ink}`,
  red: `#${piece.red ?? 'B4492F'}`,
  slot: piece.slot,
  size: piece.size,
  runs: piece.runs.map((_, i) => `frames/run-${i}.webp`),
  stayed: 'frames/stayed.webp',
  differs: 'frames/differs.webp',
  room: piece.room ? { src: 'frames/room.webp', size: piece.room.size, ring: piece.room.ring } : null,
  regions,
  whole: Number((allUnlike / all).toFixed(3)),
  scale: piece.scale_of_control ?? [],
};
writeFileSync(resolve(out, 'measures.json'), `${JSON.stringify(measures, null, 2)}\n`);
// and as a script, so that the page opens from a folder with no server
writeFileSync(resolve(out, 'measures.js'), `window.GROWN_AGAIN = ${JSON.stringify(measures)};\n`);
copyFileSync(resolve(source, 'index.html'), resolve(out, 'index.html'));
for (const r of regions) console.log(`  ${r.id.padEnd(8)} ${(r.share * 100).toFixed(0).padStart(3)}% of what is drawn there differs`);
console.log(`  the whole picture: ${(measures.whole * 100).toFixed(0)}%`);

// ---- the still, for print -----------------------------------------------------------------------------------------
const browser = process.env.BROWSER_EXE ?? ['C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', 'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium'].find((p) => existsSync(p));
if (browser && options.still !== 'no') {
  const [sw, sh] = piece.slot;
  execFileSync(browser, ['--headless=new', '--hide-scrollbars', '--no-first-run', '--disable-extensions', `--window-size=${sw},${sh}`, `--force-device-scale-factor=${scale}`, '--virtual-time-budget=4000', `--screenshot=${resolve(out, 'still.png')}`, `${pathToFileURL(resolve(out, 'index.html')).href}?print&embed`], { stdio: 'ignore' });
  console.log(`  still.png, ${sw * scale} x ${sh * scale}`);
}
console.log(`${piece.as ?? name}: ${piece.runs.length} runs in ${out}`);
process.exit(0);
