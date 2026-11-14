// The same view of the same room growing, from several grown runs of one planting: the timber is the same every
// time and the plants are not.
//   node pipeline/again.mjs [name]        (deck/<name>/piece.json; "grown-again" if none is named)
//     --frames=keep     lay out again from the pictures already made, drawing nothing
// Reads  deck/<name>/piece.json and the page beside it (index.html)
// Writes exports/deck/<as>/   for each run, the view from bare timber through each summer to the last;
//                             piece.js; the page; and still.png for print
//
// The runs are of one building, one planting and one care, and differ only in the simulator's chance (its seed).
// One run is ten years of growth, so one studio is open at a time and it is stopped between runs. It is on a
// port of its own, so that it does not meet a plate or another piece being made.
import { execFileSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
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
const scale = piece.scale ?? 2;
const [w, h] = piece.size;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const two = (k) => String(k).padStart(2, '0');

if (options.frames !== 'keep') {
  rmSync(made, { recursive: true, force: true });
  mkdirSync(made, { recursive: true });
  // A run is drawn in under a minute. One that takes three has met something that will not end by itself: the
  // studio's source not compiling while another session edits it, or a page that stopped answering. Such a page
  // waits for ever and says nothing, so the run is given up and tried again in a fresh studio.
  const within = (promise, ms, what) => {
    promise.catch(() => {});
    return Promise.race([promise, sleep(ms).then(() => Promise.reject(new Error(`${what} did not finish in ${ms / 1000} s`)))]);
  };
  async function drawRun(studio, i, grown) {
    const page = await studio.open({ plate: '', paper: piece.paper, ink: piece.ink, timber: piece.timber ?? 'ink', build: '1', run: grown }, { width: w, height: h, scale });
    const drawn = await page.js('window.studio.state().run');
    if (drawn !== grown) throw new Error(`the studio drew ${drawn}, not ${grown}: is that run grown for ${piece.snapshot ?? 'this building'}?`);
    // the moments: the timber standing with nothing planted, then every midsummer from the first to the last,
    // so that the room is in full leaf in each and what changes from one to the next is growth, not season
    const line = await page.js('window.studio.line()');
    const days = [line.planted - 1];
    for (let k = Math.floor((line.lastSummer - line.planted) / 365.25); k >= 0; k--) days.push(Math.round(line.lastSummer - k * 365.25));
    for (const [k, day] of days.entries()) {
      await page.js(`window.studio.plate(${JSON.stringify({ view: piece.view, lookAt: piece.lookAt, zoom: piece.zoom, sun: piece.sun, at: day })})`);
      writeFileSync(resolve(made, `run-${i}-${two(k)}.png`), await page.shot());
    }
    return days.length;
  }
  for (const [i, grown] of piece.runs.entries()) {
    for (let attempt = 1; ; attempt++) {
      const began = performance.now();
      console.log(`  ${grown}${attempt > 1 ? `, try ${attempt}` : ''} ...`);
      const studio = await startStudio(5328, piece.snapshot ?? null);
      try {
        const moments = await within(drawRun(studio, i, grown), 180000, grown);
        console.log(`  ${grown}: ${moments} moments in ${((performance.now() - began) / 1000).toFixed(0)} s`);
        break;
      } catch (problem) {
        if (attempt === 3 || !/did not finish/.test(problem.message)) throw problem;
        console.log(`  ${problem.message}; trying again`);
      } finally {
        studio.stop();
        await sleep(3000);
      }
    }
  }
}

// ---- for the page ---------------------------------------------------------------------------------------------------
rmSync(resolve(out, 'frames'), { recursive: true, force: true });
mkdirSync(resolve(out, 'frames'), { recursive: true });
const runs = piece.runs.map((_, i) => {
  const pictures = existsSync(made) ? readdirSync(made).filter((f) => f.startsWith(`run-${i}-`) && f.endsWith('.png')).sort() : [];
  if (!pictures.length) throw new Error(`no pictures of run ${i}: make them first, without --frames=keep`);
  return pictures.map((f) => {
    const src = `frames/${f.replace('.png', '.webp')}`;
    execFileSync(ffmpeg, ['-y', '-loglevel', 'error', '-i', resolve(made, f), '-c:v', 'libwebp', '-quality', String(piece.quality ?? 82), resolve(out, src)]);
    return src;
  });
});
const data = {
  name: piece.as ?? name,
  for: piece.for,
  statement: piece.statement ?? '',
  words: piece.words ?? {},
  paper: `#${piece.paper}`,
  ink: `#${piece.ink}`,
  slot: piece.slot,
  size: piece.size,
  timing: piece.timing ?? {},
  band: piece.band ?? 0.3,
  runs,
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
  execFileSync(browser, ['--headless=new', '--hide-scrollbars', '--no-first-run', '--disable-extensions', `--window-size=${sw},${sh}`, '--force-device-scale-factor=2', '--virtual-time-budget=4000', `--screenshot=${resolve(out, 'still.png')}`, `${pathToFileURL(resolve(out, 'index.html')).href}?print&embed`], { stdio: 'ignore' });
}
console.log(`${piece.as ?? name}: ${runs.length} runs of ${runs[0].length} moments in ${out}`);
process.exit(0);
