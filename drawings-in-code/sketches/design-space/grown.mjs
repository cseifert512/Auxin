// Thin the grown runs at the two ends of a change, for the design-space sketch: the stems of each with the day
// every point was laid down, and a few lines of each run's report.
//   node sketches/design-space/grown.mjs pier-opens six-bay-radial-v1/trained-10y-new-growth trial-pier-120/trained-10y
// The first run is the start of the sweep and the second its end. Each is scenes/<scene>/runs/<run>/.
// Writes sketches/design-space/grown-<sweep>.js, which the page loads if it is there.
// Stems only: no leaves, flowers or fruit, and nothing shorter than SHORTEST_M.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..', '..');
const [sweep, ...ends] = process.argv.slice(2);
if (!sweep || ends.length !== 2) throw new Error('usage: grown.mjs <sweep id> <scene>/<run at the start> <scene>/<run at the end>');

const SPACING_M = 0.15;   // a drawn stem keeps one point about this often
const SHORTEST_M = 0.4;   // spurs and short side shoots are left out
const AT_CROWN_M = 0.1;   // a plant within this of the crown's height has reached it
const read = (file) => JSON.parse(readFileSync(file, 'utf8'));
const sum = (list, f) => list.reduce((n, x) => n + f(x), 0);

function end(path) {
  const [scene, run] = path.split('/');
  const dir = resolve(root, 'scenes', scene, 'runs', run);
  const report = read(resolve(dir, 'report.json'));
  const setup = read(resolve(dir, 'run.json'));
  const growth = read(resolve(dir, 'growth.json'));
  const index = new Map(growth.plants.map((p, i) => [p.id, i]));
  const stems = [];
  let kept = 0;
  for (const s of growth.stems) {
    const n = s.bornDay.length;
    if (n < 2 || s.contact.length !== n * 3) continue;
    const mm = [], born = [], gone = [];
    let last = null, length = 0;
    for (let i = 0; i < n; i++) {
      const p = [s.contact[i * 3], s.contact[i * 3 + 1], s.contact[i * 3 + 2]];
      const step = last ? Math.hypot(p[0] - last[0], p[1] - last[1], p[2] - last[2]) : 0;
      if (last && i < n - 1 && step < SPACING_M) continue;
      length += step;
      mm.push(Math.round(p[0] * 1000), Math.round(p[1] * 1000), Math.round(p[2] * 1000));
      born.push(s.bornDay[i]);
      gone.push(s.removedDay[i]);
      last = p;
    }
    if (born.length < 2 || length < SHORTEST_M) continue;
    kept += born.length;
    stems.push({ plant: index.get(s.plantId), frame: s.role === 'leader' || s.role === 'lateral' ? 1 : 0, mm, born, gone });
  }
  const crown = report.structure.crownHeightM;
  const years = [...new Set(report.milestones.map((m) => m.yearsAfterPlanting))].sort((a, b) => a - b);
  const views = (month) => report.months[month].views.map((v) => ({ id: v.viewpointId, timberSeen: v.timberVisible, leafFills: v.foliage }));
  console.log(`${path}: ${growth.stems.length} stems, ${stems.length} drawn with ${kept} points; ${report.plants.length} plants; simulator ${setup.simulator?.commit?.slice(0, 7)}`);
  return {
    scene, run,
    setup: { care: setup.care, years: setup.years, seed: setup.seed, specimenM: setup.specimenM, simulator: setup.simulator?.commit?.slice(0, 7) ?? null },
    start: growth.start, lastDay: growth.lastDay, statement: growth.statement,
    plants: growth.plants.map((p) => ({ id: p.id, label: p.label, taxon: p.taxonId })),
    stems,
    report: {
      plants: report.plants.length,
      routeM: report.structure.routeM,
      cableM: report.structure.steelCableM,
      heldShare: report.routes.heldShare,
      freeM: report.routes.freeM,
      tieIns: sum(report.gardening, (g) => g.tieIns),
      cutM: sum(report.gardening, (g) => g.stemRemovedM),
      heldUnaided: sum(report.plants, (p) => p.heldUnaided),
      tiedIn: sum(report.plants, (p) => p.tiedIn),
      evergreenWinterShare: report.winter.routeHeldByEvergreens,
      // What the light model gives each plant where it stands: hours of direct sun on a clear midsummer day,
      // and the share of its growth the model lets it have for that light (1 is all of it).
      sunHours: sum(report.light.plants, (p) => p.midsummerHours) / report.light.plants.length,
      lightGrowth: sum(report.light.plants, (p) => p.growthFactor ?? 1) / report.light.plants.length,
      fullSun: report.light.plants.filter((p) => p.sunClass === 'full_sun').length,
      byYear: years.map((y) => {
        const at = report.milestones.filter((m) => m.yearsAfterPlanting === y);
        return { year: y, frameworkM: sum(at, (m) => m.frameworkM), atCrown: at.filter((m) => m.highestM >= crown - AT_CROWN_M).length, flowersOpened: sum(at, (m) => m.flowersOpened) };
      }),
      january: views(0), june: views(5),
    },
  };
}

const out = { start: end(ends[0]), end: end(ends[1]) };
const file = resolve(here, `grown-${sweep}.js`);
writeFileSync(file, `(window.GROWN ??= {})[${JSON.stringify(sweep)}] = ${JSON.stringify(out)};\n`);
console.log(`wrote ${file} (${Math.round(Buffer.byteLength(JSON.stringify(out)) / 1024)} KB)`);
