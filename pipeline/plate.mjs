// Drawings for a page that is not ours: made to fit a space in the presentation, on that page's paper.
//   node pipeline/plate.mjs [name ...]          (every description in plates/, if none is named)
// Reads  plates/<name>.json
// Writes exports/deck/<name>.png and .webp                  for a plate: one still picture
//        exports/deck/<name>/ (index.html, frames, posters)  for a piece: a drawing to turn, scrub and play
//
// Pictures are made on a clear ground, with only the drawing on it, so they can be laid on a page of any colour.
//
// Either is described, not drawn by hand, so that it can be made again when the building changes: the same
// description, a new snapshot, the same command. Like a film, it is the studio's own drawing.
//
// A description says which space it is for (`slot`, in the page's pixels; pictures are made at `scale` times
// that), the page's `paper` and `ink`, and how the space is filled:
//   row     panels side by side, each a view at a moment:  { view, at, sun, timber, shade, run, lines, lookAt, zoom }
//   round   the whole room unrolled, as seen turning on the spot in the middle of it: `slices` upright strips, each
//           what is seen in one direction. Every strip can be drawn at its own moment, so that a turn of the room
//           is also a passage of time: `at` for one moment, or `sectors`, a list of moments shared out round the turn.
//   rows    several of those, one above another
// A moment is "build:0.5" (a share of the assembly), "day:3399" (a day of the run) or "date:2031-06-20".
//
// A piece has `modes`, each filled in one of those ways and drawn at a list of `moments`: the frames it is
// scrubbed and played through. The player (deck/player) is copied in beside them. A piece carries no heavy
// machinery to the page it goes to: pictures, and a few hundred lines of script.
import { execFileSync } from 'node:child_process';
import { copyFileSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
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

/** Panels side by side. */
async function drawRow(spec, panels, rowH, file, tag) {
  const scale = spec.scale ?? 2;
  const paper = 'black@0.0';
  const n = panels.length;
  const gutter = spec.gutter ?? 12;
  const width = Math.floor((spec.slot[0] - gutter * (n - 1)) / n);
  const files = [];
  for (const [i, panel] of panels.entries()) {
    const page = await pageFor(spec, panel, { width, height: rowH });
    await page.js(ask(panel));
    files.push(resolve(work, `${tag}-${i}.png`));
    writeFileSync(files[i], await page.shot());
  }
  const pads = files.map((_, i) => (i ? `[${i}]pad=iw+${gutter * scale}:ih:${gutter * scale}:0:color=${paper}[p${i}]` : `[0]null[p0]`)).join(';');
  run([...files.flatMap((f) => ['-i', f]), '-filter_complex', `${pads};${files.map((_, i) => `[p${i}]`).join('')}hstack=inputs=${n}`, file]);
}

/** The room unrolled. */
async function drawRound(spec, round, rowH, file, tag) {
  const scale = spec.scale ?? 2;
  const paper = 'black@0.0';
  const slotW = spec.slot[0];
  const o = { slices: 72, from: 0, raise: 0.2, ...round };
  const slicePx = Math.floor((slotW * scale) / o.slices);
  // each strip is cut from the middle of a wider, taller picture taken with the lens a strip that narrow needs
  const focalPx = slicePx / 2 / Math.tan(Math.PI / o.slices);
  const tall = Math.round(rowH * 1.7);
  const up = (2 * Math.atan((tall * scale) / 2 / focalPx) * 180) / Math.PI;
  const page = await pageFor(spec, o, { width: 200, height: tall });
  const top = Math.round((tall * scale - rowH * scale) / 2 - o.raise * rowH * scale);
  const files = [];
  for (let i = 0; i < o.slices; i++) {
    // which moment this direction belongs to: sectors end where they say, or share the turn equally
    const deg = ((i + 0.5) * 360) / o.slices;
    const sector = o.sectors ? (o.sectors.find((s, k) => deg < (s.until ?? ((k + 1) * 360) / o.sectors.length)) ?? o.sectors[o.sectors.length - 1]) : o;
    await page.js(ask({ ...o, ...sector, view: 'round' }, { yaw: o.from + deg, up }));
    const strip = resolve(work, `${tag}-s${String(i).padStart(3, '0')}.png`);
    writeFileSync(strip, await page.shot());
    files.push(strip);
  }
  // the middle of each, and all of them side by side; a sliver of paper where one moment gives way to the next
  const crops = files.map((_, i) => `[${i}]crop=${slicePx}:${rowH * scale}:${(200 * scale) / 2 - slicePx / 2}:${top}[c${i}]`).join(';');
  const seams = (o.sectors ?? []).slice(0, -1).map((s) => `,drawbox=x=${Math.round((s.until / 360) * slotW * scale) - 3}:y=0:w=6:h=ih:color=${paper}:t=fill:replace=1`).join('');
  run([...files.flatMap((f) => ['-i', f]), '-filter_complex', `${crops};${files.map((_, i) => `[c${i}]`).join('')}hstack=inputs=${o.slices},scale=${slotW * scale}:${rowH * scale}:flags=lanczos${seams}`, file]);
  for (const f of files) rmSync(f, { force: true });
}

/** One picture filling the space, from a description that has `row`, `round` or `rows`. */
async function drawSlot(spec, what, file, tag) {
  const scale = spec.scale ?? 2;
  const [slotW, slotH] = spec.slot;
  const paper = 'black@0.0';
  const list = what.rows ?? [what];
  const between = list.length > 1 ? (spec.gutter ?? 0) : 0;
  const rowH = Math.round((slotH - between * (list.length - 1)) / list.length);
  const rows = [];
  for (const [r, row] of list.entries()) {
    rows.push(resolve(work, `${tag}-row${r}.png`));
    if (row.row) await drawRow(spec, row.row, rowH, rows[r], `${tag}-${r}`);
    else if (row.round) await drawRound(spec, row.round, rowH, rows[r], `${tag}-${r}`);
    else throw new Error(`${tag}: a space is filled by a "row" of panels, the room "round", or "rows" of those`);
  }
  // rows one above another, and the whole to exactly the space asked for
  const gap = between * scale;
  const stack = rows.length > 1 ? `${rows.map((_, i) => (i ? `[${i}]pad=iw:ih+${gap}:0:${gap}:color=${paper}[r${i}]` : `[0]null[r0]`)).join(';')};${rows.map((_, i) => `[r${i}]`).join('')}vstack=inputs=${rows.length},` : '';
  const fit = `scale=${slotW * scale}:${slotH * scale}:force_original_aspect_ratio=decrease:flags=lanczos,pad=${slotW * scale}:${slotH * scale}:(ow-iw)/2:(oh-ih)/2:color=${paper}`;
  run([...rows.flatMap((f) => ['-i', f]), '-filter_complex', `${stack}${fit}`, file]);
}

/** A mode's way of filling the space, at one of its moments. What a panel says for itself stands; the moment fills in the rest. */
function atMoment(mode, moment) {
  const { stage, poster, ...when } = moment;
  if (mode.round) return { round: { ...mode.round, ...when } };
  if (mode.row) return { row: mode.row.map((panel) => ({ ...when, ...panel })) };
  throw new Error('a mode is filled by a "row" of panels or the room "round"');
}

for (const name of wanted) {
  const spec = JSON.parse(readFileSync(resolve(root, 'plates', `${name}.json`), 'utf8'));
  const began = performance.now();

  if (!spec.piece) {
    await drawSlot(spec, spec, resolve(out, `${name}.png`), name);
    run(['-i', resolve(out, `${name}.png`), '-c:v', 'libwebp', '-quality', '90', resolve(out, `${name}.webp`)]);
    console.log(`${name}: ${spec.slot[0] * (spec.scale ?? 2)} x ${spec.slot[1] * (spec.scale ?? 2)} in ${((performance.now() - began) / 1000).toFixed(0)} s`);
    continue;
  }

  // ---- a piece: frames for each mode, a poster for print, and the player beside them ---------------------------------
  const dir = resolve(out, name);
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(resolve(dir, 'frames'), { recursive: true });
  const manifest = { name, for: spec.for, slot: spec.slot, paper: `#${spec.paper ?? 'FDFCF9'}`, ink: `#${spec.ink ?? '1D1D1B'}`, statement: spec.statement ?? '', modes: [] };
  for (const [id, mode] of Object.entries(spec.piece.modes)) {
    const frames = [];
    for (const [i, moment] of mode.moments.entries()) {
      const png = resolve(work, `${name}-${id}-${i}.png`);
      await drawSlot(spec, atMoment(mode, moment), png, `${name}-${id}-${i}`);
      const src = `frames/${id}-${String(i).padStart(2, '0')}.webp`;
      run(['-i', png, '-c:v', 'libwebp', '-quality', '84', resolve(dir, src)]);
      if (moment.poster || mode.moments.length === 1) copyFileSync(png, resolve(dir, `poster-${id}.png`));
      frames.push({ src, stage: moment.stage ?? '' });
      console.log(`  ${name} ${id} ${i + 1}/${mode.moments.length} (${((performance.now() - began) / 60000).toFixed(1)} min)`);
    }
    manifest.modes.push({ id, label: mode.label ?? id, line: mode.line ?? '', turns: Boolean(mode.round), seconds: mode.seconds ?? 24, frames });
  }
  writeFileSync(resolve(dir, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);
  // and as a script, so that the piece opens from a folder with no server
  writeFileSync(resolve(dir, 'manifest.js'), `window.BOWER_PIECE = ${JSON.stringify(manifest)};\n`);
  for (const file of readdirSync(resolve(root, 'deck/player'))) copyFileSync(resolve(root, 'deck/player', file), resolve(dir, file));
  console.log(`${name}: a piece of ${manifest.modes.map((m) => `${m.frames.length} ${m.id}`).join(', ')} frames in ${((performance.now() - began) / 60000).toFixed(1)} min`);
}
rmSync(work, { recursive: true, force: true });
studio.stop();
process.exit(0);
