// Set runs of one scene side by side: how much of the timber the plants hold, how they hold it, what it costs
// in steel and in the gardener's ties, and what a visitor sees.
//   node pipeline/compare.mjs [snapshot] [run ...]        (every run of the scene, if none is named)
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const [snapshot = JSON.parse(readFileSync(new URL('../snapshot.json', import.meta.url), 'utf8')).snapshot, ...named] = process.argv.slice(2);
const runsDir = resolve(root, 'scenes', snapshot, 'runs');
const runs = (named.length ? named : readdirSync(runsDir)).filter((r) => existsSync(resolve(runsDir, r, 'report.json')));
const pct = (x) => `${Math.round(100 * x)}%`.padStart(4);
const sum = (list, f) => list.reduce((n, x) => n + f(x), 0);

for (const run of runs) {
  const r = JSON.parse(readFileSync(resolve(runsDir, run, 'report.json'), 'utf8'));
  const setup = JSON.parse(readFileSync(resolve(runsDir, run, 'run.json'), 'utf8'));
  const s = r.structure;
  console.log(`\n${run}: ${r.plants.length} plants${setup.specimenM ? `, planted standing ${setup.specimenM} m` : ', planted as young canes'}, on ${setup.bower ?? 'bower.json'}; simulator ${setup.simulator?.branch ?? 'main'} at ${String(setup.simulator?.commit).slice(0, 7)}${setup.band ? `, every plant at the ${setup.band} end of its published range` : ''}${setup.stemsTimes ? `, ${setup.stemsTimes} times the stems to a member` : ''}`);
  console.log(`  routes        ${s.routeM.toFixed(0)} m, of which steel cable ${s.steelCableM.toFixed(0)} m (${pct(s.steelShareOfRoute).trim()})`);
  console.log(`  held          ${pct(r.routes.heldShare).trim()} of the routes carry a plant in ${r.year}; ${r.routes.freeM.toFixed(0)} m carry nothing`);
  const self = sum(r.plants, (p) => p.heldUnaided);
  const tied = sum(r.plants, (p) => p.tiedIn);
  console.log(`  how           ${self} stretches held by the plant itself, ${tied} tied in by the gardener (${pct(self / Math.max(1, self + tied)).trim()} unaided); ${sum(r.gardening, (g) => g.tieIns)} tie-ins over the run`);
  const years = [...new Set(r.milestones.map((m) => m.yearsAfterPlanting))].sort((a, b) => a - b);
  console.log(`  framework     ${years.map((y) => `year ${y}: ${sum(r.milestones.filter((m) => m.yearsAfterPlanting === y), (m) => m.frameworkM).toFixed(0)} m`).join('   ')}`);
  for (const month of [0, 5]) {
    const m = r.months[month];
    console.log(`  ${month === 0 ? 'January' : 'June   '} ${r.year}  ${m.views.map((v) => `${v.viewpointId}: timber seen ${pct(v.timberVisible)}, leaf fills ${pct(v.foliage)}`).join('   ')}`);
  }
  console.log(`  winter        evergreens hold ${pct(r.winter.routeHeldByEvergreens).trim()} of the routes (target 25% to 40%)`);
}
