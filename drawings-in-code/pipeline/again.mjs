// The same view on the same day from several grown runs of one planting, to turn between: the timber holds
// still and the plants do not.
//   node pipeline/again.mjs [name]        (deck/<name>/piece.json; "grown-again" if none is named)
//     --frames=keep     lay out again from the pictures already made, drawing nothing
// Reads  deck/<name>/piece.json and the page beside it (index.html)
// Writes exports/deck/<as>/   one picture for each run, piece.js, the page, and still.png for print
//
// The runs are of one building, one planting and one care, and differ only in the simulator's chance (its seed).
// One run is ten years of growth, so one studio is open at a time and it is stopped between runs. It is on a
// port of its own, so that it does not meet a plate or another piece being made.
import { execFileSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
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
// the full pictures are kept beside the exports, and are not in git: the page reads smaller ones
const made = resolve(root, 'exports/deck/.again', piece.as ?? name);
rmSync(resolve(out, 'frames'), { recursive: true, force: true });
mkdirSync(resolve(out, 'frames'), { recursive: true });
mkdirSync(made, { recursive: true });

const scale = piece.scale ?? 2;
const [w, h] = piece.size;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const png = (i) => resolve(made, `run-${i}.png`);

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
        writeFileSync(png(i), await page.shot());
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

// ---- for the page ---------------------------------------------------------------------------------------------------
for (const [i] of piece.runs.entries()) {
  if (!existsSync(png(i))) throw new Error(`no picture of run ${i}: make them first, without --frames=keep`);
  execFileSync(ffmpeg, ['-y', '-loglevel', 'error', '-i', png(i), '-c:v', 'libwebp', '-quality', '88', resolve(out, 'frames', `run-${i}.webp`)]);
}
const data = {
  name: piece.as ?? name,
  for: piece.for,
  statement: piece.statement ?? '',
  words: piece.words ?? {},
  paper: `#${piece.paper}`,
  ink: `#${piece.ink}`,
  slot: piece.slot,
  size: piece.size,
  hold: piece.hold ?? 1500,
  band: piece.band ?? 0.3,
  runs: piece.runs.map((_, i) => `frames/run-${i}.webp`),
};
for (const old of ['measures.json', 'measures.js']) rmSync(resolve(out, old), { force: true });
writeFileSync(resolve(out, 'piece.json'), `${JSON.stringify(data, null, 2)}\n`);
// and as a script, so that the page opens from a folder with no server
writeFileSync(resolve(out, 'piece.js'), `window.GROWN_AGAIN = ${JSON.stringify(data)};\n`);
copyFileSync(resolve(source, 'index.html'), resolve(out, 'index.html'));

// ---- the still, for print -----------------------------------------------------------------------------------------
const browser = process.env.BROWSER_EXE ?? ['C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', 'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium'].find((p) => existsSync(p));
if (browser && options.still !== 'no') {
  const [sw, sh] = piece.slot;
  execFileSync(browser, ['--headless=new', '--hide-scrollbars', '--no-first-run', '--disable-extensions', `--window-size=${sw},${sh}`, `--force-device-scale-factor=${scale}`, '--virtual-time-budget=4000', `--screenshot=${resolve(out, 'still.png')}`, `${pathToFileURL(resolve(out, 'index.html')).href}?print&embed`], { stdio: 'ignore' });
}
console.log(`${piece.as ?? name}: ${piece.runs.length} runs in ${out}`);
process.exit(0);
