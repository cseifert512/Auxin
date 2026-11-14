// What the pier drawing says in numbers and places, worked out from the two grown runs and the two buildings.
// Reads two files made beside the sketches (see README, sketches): states.js (bower-blender/scripts/sweep_states.py)
// for what is measured off the centre lines, and grown-pier-opens.js (grown.mjs) for the two runs' reports.
// The places come from the snapshot's own design. Nothing here is typed in by hand.
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const made = (file, start) => {
  if (!existsSync(file)) throw new Error(`${file} is not there: make it first (drawings-in-code/README.md, under sketches)`);
  return JSON.parse(readFileSync(file, 'utf8').replace(start, '').replace(/;\s*$/, ''));
};

export default function gather(root) {
  const sweep = made(resolve(root, 'sketches/design-space/states.js'), /^window\.DESIGN_SPACE = /).sweeps.find((s) => s.id === 'pier-opens');
  const grown = made(resolve(root, 'sketches/design-space/grown-pier-opens.js'), /^\(window\.GROWN \?\?= \{\}\)\["pier-opens"\] = /);
  const design = JSON.parse(readFileSync(resolve(root, '../releases/six-bay-radial-v1/design.json'), 'utf8'));
  const piers = design.rooms[0].piers.map((p) => [p.position_m[0], p.position_m[1], 0]);
  const last = sweep.measures.length - 1, YEARS = 5;   // the years of growth the drawing shows on each room
  const report = (end) => ({
    sunHours: end.report.sunHours, fullSun: end.report.fullSun, plants: end.report.plants, lightGrowth: end.report.lightGrowth,
    tieIns: end.report.tieIns, frameworkM: end.report.byYear.find((y) => y.year === YEARS)?.frameworkM ?? null,
  });
  return {
    points: { piers },
    years: YEARS,
    ring: [sweep.values[0], sweep.values[last]],
    feetApart: [sweep.measures[0].feet_apart_m, sweep.measures[last].feet_apart_m],
    wayThrough: [sweep.measures[0].way_through_m, sweep.measures[last].way_through_m],
    was: report(grown.start),
    now: report(grown.end),
    setup: grown.end.setup,
    statement: grown.start.statement,
  };
}
