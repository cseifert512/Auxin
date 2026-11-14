// Set runs of one scene side by side: how much of the timber the plants hold, and what a visitor sees.
//   node pipeline/compare.mjs [snapshot] [run ...]        (every run of the scene, if none is named)
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const [snapshot = 'six-bay-v1', ...named] = process.argv.slice(2);
const runsDir = resolve(root, 'scenes', snapshot, 'runs');
const runs = (named.length ? named : readdirSync(runsDir)).filter((r) => existsSync(resolve(runsDir, r, 'report.json')));
const pct = (x) => `${Math.round(100 * x)}%`.padStart(5);

for (const run of runs) {
  const r = JSON.parse(readFileSync(resolve(runsDir, run, 'report.json'), 'utf8'));
  const setup = JSON.parse(readFileSync(resolve(runsDir, run, 'run.json'), 'utf8'));
  console.log(`\n${run}: ${r.plants.length} plants${setup.specimenM ? `, planted standing ${setup.specimenM} m` : ', planted as young canes'}`);
  // routes held: the plants' shares added, year by year (a stretch two plants share is counted twice)
  const years = [...new Set(r.milestones.map((m) => m.yearsAfterPlanting))].sort((a, b) => a - b);
  console.log(`  timber route held, plants added together   ${years.map((y) => `year ${y}: ${pct(r.milestones.filter((m) => m.yearsAfterPlanting === y).reduce((s, m) => s + m.routeShare, 0))}`).join('   ')}`);
  console.log(`  highest any plant stands                    ${years.map((y) => `year ${y}: ${Math.max(...r.milestones.filter((m) => m.yearsAfterPlanting === y).map((m) => m.highestM)).toFixed(1)} m`).join('   ')}`);
  for (const month of [0, 5]) {
    const m = r.months[month];
    console.log(`  ${r.year} ${month === 0 ? 'January' : 'June   '}  ${m.views.map((v) => `${v.viewpointId}: timber seen ${pct(v.timberVisible)}, leaf ${pct(v.foliage)} of the view`).join('   ')}`);
  }
}
