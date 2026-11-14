// The drawing that is drawn live, made ready to go into the presentation.
//   node pipeline/live.mjs [--runs=trained-10y,woven-10y] [--also=high-10y,...]
//     --runs   the plantings that go to the presentation with it (the first is the one it opens on): trained-10y
//     --also   plantings made light as well, for looking at in the studio, and not sent: woven-10y and high-10y
// Writes exports/deck/a-room-through-time/   (index.html and what it needs: plain files)
//
// Three things, in order:
//   1. a light copy of every run of the scene (lighten.mjs): what can be seen of ten years of growth, a twentieth
//      of the size
//   2. a still of the room, established, in summer: the page shows it at once, draws over it when it is ready, and
//      keeps it if the machine it is on cannot draw at all
//   3. the studio built as plain files (vite build --mode deck), with the light copies and nothing else
//
// What comes out needs a web server and nothing more: no installing, nothing to run first. Set into a slide:
//   <iframe src=".../a-room-through-time/index.html?embed&paper=EEF3EA&ink=102820&view=approach"></iframe>
// and add &play for it to start by itself.
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { root, startStudio } from './headless.mjs';

const snapshot = JSON.parse(readFileSync(resolve(root, 'snapshot.json'), 'utf8')).snapshot;
const options = Object.fromEntries(process.argv.slice(2).filter((a) => a.startsWith('--')).map((a) => a.slice(2).split('=')));
const grown = (r) => existsSync(resolve(root, 'scenes', snapshot, 'runs', r, 'growth.json'));
const runs = (options.runs ?? 'trained-10y').split(',').filter(grown);
const also = (options.also ?? 'woven-10y,high-10y').split(',').filter((r) => grown(r) && !runs.includes(r));
rmSync(resolve(root, 'scenes', snapshot, 'light'), { recursive: true, force: true });
if (!runs.length) throw new Error(`no planting has been grown on ${snapshot}: npm run grow`);
const node = (args, env = {}) => execFileSync(process.execPath, args, { cwd: root, stdio: 'inherit', env: { ...process.env, ...env } });

// 1
for (const run of runs) node(['--max-old-space-size=6000', 'pipeline/lighten.mjs', snapshot, run]);

// 2
const ffmpeg = createRequire(import.meta.url)('ffmpeg-static');
const publicDir = resolve(root, 'studio/public');
mkdirSync(publicDir, { recursive: true });
const studio = await startStudio();
try {
  const page = await studio.open({ plate: '', timber: 'wood', build: '1', ...(runs.includes('trained-10y') ? { run: 'trained-10y' } : {}) }, { width: 1280, height: 720, scale: 1.5 });
  await page.js(`window.studio.plate({ view: 'approach', sun: [191, 14], at: window.studio.line().lastSummer })`);
  const png = resolve(publicDir, 'poster.png');
  writeFileSync(png, await page.shot());
  execFileSync(ffmpeg, ['-y', '-loglevel', 'error', '-i', png, '-c:v', 'libwebp', '-quality', '86', resolve(publicDir, 'poster.webp')]);
  rmSync(png);
} finally {
  await studio.stop();
}

// 3
const horti = resolve(process.env.HORTI_DIR ?? resolve(root, '../Horti-code-ture'));
node([resolve(horti, 'node_modules/vite/bin/vite.js'), 'build', '--mode', 'deck', '--config', 'studio/vite.config.js', '--logLevel', 'warn']);

// and, now that what is sent is made, the others to look at in the studio
for (const run of also) node(['--max-old-space-size=6000', 'pipeline/lighten.mjs', snapshot, run]);

const out = resolve(root, 'exports/deck/a-room-through-time');
const sizeOf = (dir) => readdirSync(dir, { withFileTypes: true }).reduce((n, f) => n + (f.isDirectory() ? sizeOf(resolve(dir, f.name)) : statSync(resolve(dir, f.name)).size), 0);
console.log(`\nwritten: ${out} (${(sizeOf(out) / 1e6).toFixed(1)} MB)`);
process.exit(0);
