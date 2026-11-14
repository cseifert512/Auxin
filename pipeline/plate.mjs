// Plates for a page that is not ours: a drawing made to fit a space in the presentation, on that page's paper.
//   node pipeline/plate.mjs [name ...]          (every plate in plates/, if none is named)
// Reads  plates/<name>.json
// Writes exports/deck/<name>.png and .webp
//
// A plate is described, not drawn by hand, so that it can be made again when the building changes: the same
// description, a new snapshot, the same command. Like a film, it is the studio's own drawing, with nothing on it
// but the drawing.
//
// A description says which space it is for (`slot`, in the page's pixels; the plate is made at `scale` times
// that), the page's `paper` and `ink`, and one of:
//   row     panels side by side, each a view at a moment:  { view, at, sun, timber, shade, run }
//   Panels may add `lines: "marked"` (training lines in green), and in the drawing view `lookAt` and `zoom`.
//   round   the whole room unrolled, as seen turning on the spot in the middle of it: `slices` upright strips, each
//           what is seen in one direction. Every strip can be drawn at its own moment, so that a turn of the room
//           is also a passage of time: `at` for one moment, or `sectors`, a list of moments shared out round the turn.
// A moment is "build:0.5" (a share of the assembly), "day:3399" (a day of the run) or "date:2031-06-20".
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { root, startStudio } from './headless.mjs';

const ffmpeg = createRequire(import.meta.url)('ffmpeg-static');
const names = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const all = readdirSync(resolve(root, 'plates')).filter((f) => f.endsWith('.json')).map((f) => f.slice(0, -5));
const wanted = names.length ? names : all;
const out = resolve(root, 'exports/deck');
const work = resolve(out, '.work');
mkdirSync(work, { recursive: true });

const studio = await startStudio();
/** Pages are kept open and used again: reading ten years of growth is the slow part. */
const pages = new Map();
async function pageFor(spec, panel, size) {
  const query = { plate: '', paper: spec.paper ?? 'FDFCF9', ink: spec.ink ?? '1D1D1B', timber: panel.timber ?? spec.timber ?? 'ink', build: '1', ...(panel.run ?? spec.run ? { run: panel.run ?? spec.run } : {}), ...(panel.lines ? { lines: panel.lines } : {}) };
  const key = JSON.stringify(query);
  if (!pages.has(key)) pages.set(key, await studio.open(query, { ...size, scale: spec.scale ?? 2 }));
  const page = pages.get(key);
  await page.size(size.width, size.height, spec.scale ?? 2);
  return page;
}
const ask = (panel, extra = {}) => {
  const p = { view: panel.view, timber: panel.timber, sun: panel.sun, shade: panel.shade, lookAt: panel.lookAt, zoom: panel.zoom, ...extra };
  return `window.studio.plate({ ...${JSON.stringify(p)}, at: window.studio.moment(${JSON.stringify(panel.at ?? 'build:1')}) })`;
};
const run = (args) => execFileSync(ffmpeg, ['-y', '-loglevel', 'error', ...args]);

for (const name of wanted) {
  const spec = JSON.parse(readFileSync(resolve(root, 'plates', `${name}.json`), 'utf8'));
  const scale = spec.scale ?? 2;
  const [slotW, slotH] = spec.slot;
  const paper = `0x${spec.paper ?? 'FDFCF9'}`;
  const began = performance.now();
  const rows = [];

  for (const [r, row] of (spec.rows ?? [spec]).entries()) {
    const rowH = Math.round((slotH - (spec.gutter ?? 0) * ((spec.rows?.length ?? 1) - 1)) / (spec.rows?.length ?? 1));
    const file = resolve(work, `${name}-row${r}.png`);
    if (row.row) {
      // ---- panels side by side -----------------------------------------------------------------------------------
      const n = row.row.length;
      const gutter = spec.gutter ?? 12;
      const width = Math.floor((slotW - gutter * (n - 1)) / n);
      const files = [];
      for (const [i, panel] of row.row.entries()) {
        const page = await pageFor(spec, panel, { width, height: rowH });
        await page.js(ask(panel));
        files.push(resolve(work, `${name}-${r}-${i}.png`));
        writeFileSync(files[i], await page.shot());
      }
      const pads = files.map((_, i) => (i ? `[${i}]pad=iw+${gutter * scale}:ih:${gutter * scale}:0:color=${paper}[p${i}]` : `[0]null[p0]`)).join(';');
      run([...files.flatMap((f) => ['-i', f]), '-filter_complex', `${pads};${files.map((_, i) => `[p${i}]`).join('')}hstack=inputs=${n}`, file]);
    } else if (row.round) {
      // ---- the room unrolled ---------------------------------------------------------------------------------------
      const o = { slices: 72, from: 0, raise: 0.2, ...row.round };
      const slicePx = Math.floor((slotW * scale) / o.slices);
      // each strip is cut from the middle of a wider, taller picture taken with the lens a strip that narrow needs
      const focalPx = slicePx / 2 / Math.tan(Math.PI / o.slices);
      const tall = Math.round(rowH * 1.7);
      const up = (2 * Math.atan((tall * scale) / 2 / focalPx) * 180) / Math.PI;
      const page = await pageFor(spec, row.round, { width: 200, height: tall });
      const top = Math.round((tall * scale - rowH * scale) / 2 - o.raise * rowH * scale);
      const files = [];
      for (let i = 0; i < o.slices; i++) {
        // which moment this direction belongs to: sectors end where they say, or share the turn equally
        const deg = ((i + 0.5) * 360) / o.slices;
        const sector = o.sectors ? (o.sectors.find((s, k) => deg < (s.until ?? ((k + 1) * 360) / o.sectors.length)) ?? o.sectors[o.sectors.length - 1]) : o;
        await page.js(ask({ ...o, ...sector, view: 'round' }, { yaw: o.from + ((i + 0.5) * 360) / o.slices, up }));
        const strip = resolve(work, `${name}-${r}-s${String(i).padStart(3, '0')}.png`);
        writeFileSync(strip, await page.shot());
        files.push(strip);
      }
      // the middle of each, and all of them side by side
      const crops = files.map((_, i) => `[${i}]crop=${slicePx}:${rowH * scale}:${200 * scale / 2 - slicePx / 2}:${top}[c${i}]`).join(';');
      run([...files.flatMap((f) => ['-i', f]), '-filter_complex', `${crops};${files.map((_, i) => `[c${i}]`).join('')}hstack=inputs=${o.slices},scale=${slotW * scale}:${rowH * scale}:flags=lanczos${(o.sectors ?? []).slice(0, -1).map((s) => `,drawbox=x=${Math.round((s.until / 360) * slotW * scale) - 3}:y=0:w=6:h=ih:color=${paper}:t=fill`).join('')}`, file]);
    } else throw new Error(`plates/${name}.json: a plate is a "row" of panels or the room "round"`);
    rows.push(file);
  }

  // rows one above another, and the whole to exactly the space asked for
  const gutter = (spec.gutter ?? 0) * scale;
  const stack = rows.length > 1 ? `${rows.map((_, i) => (i ? `[${i}]pad=iw:ih+${gutter}:0:${gutter}:color=${paper}[r${i}]` : `[0]null[r0]`)).join(';')};${rows.map((_, i) => `[r${i}]`).join('')}vstack=inputs=${rows.length},` : '';
  const fit = `scale=${slotW * scale}:${slotH * scale}:force_original_aspect_ratio=decrease:flags=lanczos,pad=${slotW * scale}:${slotH * scale}:(ow-iw)/2:(oh-ih)/2:color=${paper}`;
  run([...rows.flatMap((f) => ['-i', f]), '-filter_complex', `${stack}${fit}`, resolve(out, `${name}.png`)]);
  run(['-i', resolve(out, `${name}.png`), '-c:v', 'libwebp', '-quality', '90', resolve(out, `${name}.webp`)]);
  console.log(`${name}: ${slotW * scale} x ${slotH * scale} in ${((performance.now() - began) / 1000).toFixed(0)} s`);
}
rmSync(work, { recursive: true, force: true });
studio.stop();
process.exit(0);
