// A vignette: one finding from growing a planting on the building, and the change to the building it led to,
// as a drawing that plays by itself. This makes its pictures from the studio and puts its page beside them.
//   node pipeline/vignette.mjs <name>            (deck/<name>/piece.json, data.mjs and index.html)
//     --only=<set>[,<set>]   make only those sets of pictures again, keeping the rest
// Reads  deck/<name>/piece.json   which pictures: views (the room, a place close to), and sets of moments, each
//                                 from one snapshot and one grown run
//        deck/<name>/data.mjs     the numbers and places the page needs, worked out from the runs
//        deck/<name>/index.html   the page: it plays the pictures and draws the annotation over them
// Writes exports/deck/<name>/     frames/, manifest.js (which pictures, and where each named place falls in each
//                                 view), data.js, and the page
//
// The pictures are the studio's own drawing on a clear ground, as a plate's are. A view is the same for every set,
// so a place in the building falls at the same spot in every picture of that view, and the page can mark it.
// One studio runs at a time, on a port of its own, so that it does not meet a plate or another piece being made.
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { root, startStudio } from './headless.mjs';

const PORT = 5338;
const name = process.argv.slice(2).find((a) => !a.startsWith('--'));
if (!name) throw new Error('usage: node pipeline/vignette.mjs <name>');
const options = Object.fromEntries(process.argv.slice(2).filter((a) => a.startsWith('--')).map((a) => a.slice(2).split('=')));
const source = resolve(root, 'deck', name);
const piece = JSON.parse(readFileSync(resolve(source, 'piece.json'), 'utf8'));
const out = resolve(root, 'exports/deck', piece.as ?? name);
mkdirSync(resolve(out, 'frames'), { recursive: true });
const only = options.only ? options.only.split(',') : null;
const scale = piece.scale ?? 2;

const { default: gather } = await import(pathToFileURL(resolve(source, 'data.mjs')).href);
const data = await gather(root);
const points = { ...(piece.points ?? {}), ...(data.points ?? {}) };   // named places: one [x, y, z], or a list of them

/** The moments of a set: given one by one ("build:1", "day:3579"), or as days spread evenly between two. */
const momentsOf = (set) => (Array.isArray(set.moments) ? set.moments : Array.from({ length: set.moments.count }, (_, i) => `day:${Math.round(set.moments.days[0] + (set.moments.days[1] - set.moments.days[0]) * i / (set.moments.count - 1))}`));
const ask = (view, at) => `window.studio.plate({ ...${JSON.stringify({ view: view.view ?? 'drawing', lookAt: view.lookAt, zoom: view.zoom, from: view.from })}, at: window.studio.moment(${JSON.stringify(at)}) })`;

const manifestFile = resolve(out, 'manifest.js');
const before = only && existsSync(manifestFile) ? JSON.parse(readFileSync(manifestFile, 'utf8').replace(/^window\.VIGNETTE = /, '').replace(/;\s*$/, '')) : null;
const manifest = { name, statement: piece.statement, paper: piece.paper, ink: piece.ink, views: before?.views ?? {}, sets: before?.sets ?? {} };

const bySnapshot = new Map();
for (const set of piece.sets) if (!only || only.includes(set.id)) bySnapshot.set(set.snapshot, [...(bySnapshot.get(set.snapshot) ?? []), set]);
const started = performance.now();
for (const [snapshot, sets] of bySnapshot) {
  const studio = await startStudio(PORT, snapshot);
  try {
    for (const file of ['src/paper.ts', 'src/main.ts']) {   // a studio that does not compile opens no page and says nothing
      const answer = await fetch(`http://localhost:${PORT}/${file}`);
      if (!answer.ok) throw new Error(`the studio does not compile (${file}):\n${(await answer.text()).match(/"message":"(.*?)","stack"/)?.[1]?.replaceAll('\\n', '\n') ?? answer.status}`);
    }
    const pages = new Map();   // one page for each grown run: reading ten years of growth is the slow part
    for (const set of sets) {
      const query = { plate: '', paper: piece.paper ?? 'EEF3EA', ink: piece.ink ?? '102820', timber: set.timber ?? piece.timber ?? 'ink', build: '1', run: set.run };
      const key = JSON.stringify(query);
      if (!pages.has(key)) pages.set(key, await studio.open(query, { width: 800, height: 600, scale }));
      const page = pages.get(key);
      const moments = momentsOf(set);
      manifest.sets[set.id] = { snapshot, run: set.run, moments, days: moments.map((m) => (m.startsWith('day:') ? Number(m.slice(4)) : null)), views: {} };
      for (const id of set.views) {
        const view = piece.views[id];
        await page.size(view.size[0], view.size[1], scale);
        const files = [];
        for (const [i, at] of moments.entries()) {
          await page.js(ask(view, at));
          const file = `frames/${set.id}-${id}-${String(i).padStart(2, '0')}.webp`;
          writeFileSync(resolve(out, file), await page.shot('webp'));
          files.push(file);
        }
        manifest.sets[set.id].views[id] = files;
        // where each named place falls in this view; the same for every set, since the view is
        const placed = {};
        for (const [label, at] of Object.entries(points)) {
          const list = Array.isArray(at[0]) ? at : [at];
          const where = await page.js(`${JSON.stringify(list)}.map((p) => window.studio.paper.project(p))`);
          placed[label] = Array.isArray(at[0]) ? where : where[0];
        }
        manifest.views[id] = { size: view.size, points: placed };
        console.log(`  ${set.id} / ${id}: ${files.length} pictures at ${view.size[0] * scale} x ${view.size[1] * scale}`);
      }
      if (page.problems.length) throw new Error(`the studio complained:\n  ${page.problems.join('\n  ')}`);
    }
  } finally {
    studio.stop();
  }
}
writeFileSync(manifestFile, `window.VIGNETTE = ${JSON.stringify(manifest)};\n`);
const { points: _places, ...rest } = data;
writeFileSync(resolve(out, 'data.js'), `window.VIGNETTE_DATA = ${JSON.stringify(rest)};\n`);
copyFileSync(resolve(source, 'index.html'), resolve(out, 'index.html'));
console.log(`${name}: written to ${out} in ${((performance.now() - started) / 1000).toFixed(0)} s`);
process.exit(0);
