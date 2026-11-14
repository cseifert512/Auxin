// How far a scenario's readings move when numbers nobody has measured are changed.
//   npm run sensitivity -- [wisteria|mixed|dome|palette] [trained|untended] [years] [seed]
//       leaf and shoot densities multiplied: winter cover, summer leaf, timber legibility, flowers
//   npm run sensitivity -- growth [wisteria|mixed|dome|palette] [trained|untended] [years] [seed]
//       one growth parameter at a time, ranked by how far it moves height by year, route held, tie-ins and timber seen
//   npm run sensitivity -- band [wisteria|mixed|dome|palette] [trained|untended] [years] [seed]
//       the low end, as modelled, and the high end of the ranges the growth models give for extension
// A designed structure in place of a reference scenario, in any of the three:
//   npm run sensitivity -- [growth|band] design <bower.json> <planting.json> [trained|untended] [years] [seed]
// Options:
//   --specimen=<m>   every plant goes in as a nursery specimen standing that many metres, all its main stems under way
//   --only=<a,b>     growth only: just the runs whose parameter or id contains one of these (and the run as modelled)
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { readBower } from '../src/bower/description.ts';
import { loadGrowable } from '../src/node/load-taxa.ts';
import { GROWTH_VARIATIONS, formatGrowthBand, formatGrowthSensitivity, growthBand, growthSensitivity } from '../src/sim/growth-sensitivity.ts';
import { withParam } from '../src/sim/model.ts';
import { parsePlantingPlan, plantingOn } from '../src/sim/planting.ts';
import { type Growable, mixedOnVault, referencePalette, wisteriaOnHemisphere, wisteriaOnVault } from '../src/sim/scenarios.ts';
import { formatSensitivity, sensitivity } from '../src/sim/sensitivity.ts';

const options = Object.fromEntries(process.argv.slice(2).filter((a) => a.startsWith('--')).map((a) => a.slice(2).split('='))) as Record<string, string | undefined>;
const args = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const mode = ['growth', 'band'].includes(args[0] ?? '') ? (args.shift() as 'growth' | 'band') : 'densities';
const which = ['mixed', 'wisteria', 'dome', 'palette', 'design'].includes(args[0] ?? '') ? args.shift()! : 'palette';
const files = which === 'design' ? args.splice(0, 2) : [];
if (which === 'design' && files.length < 2) throw new Error('usage: npm run sensitivity -- [growth|band] design <bower.json> <planting.json> [trained|untended] [years] [seed]');
const care = args[0] === 'untended' ? 'untended' : 'trained';
const years = Number(args[1] ?? 12);
const seed = Number(args[2] ?? 7);
const root = fileURLToPath(new URL('../../../', import.meta.url));
const read = (file: string): unknown => JSON.parse(readFileSync(file, 'utf8'));

// A specimen is the same plant with a longer stem on the day it goes in and all its main stems under way; how fast
// it then grows, and the slow years after planting, are left as its model has them. It is applied to whatever library
// a run is made with, so that a variation of the cane or of the stems' starting years would still be overridden.
const specimenM = options.specimen ? Number(options.specimen) : null;
const specimen = (taxa: Growable): Growable => {
  if (specimenM === null) return taxa;
  const why = `planted as a nursery specimen standing ${specimenM} m, not a young plant`;
  return new Map(
    [...taxa].map(([id, t]) => {
      const tall = withParam(t.model, 'architecture.nurseryCaneM', specimenM, why);
      return [id, { profile: t.profile, model: withParam(tall, 'architecture.trunkStemStartYears', t.model.params['architecture.trunkStemStartYears'].value!.map(() => 0), `${why}: every main stem already growing`) }];
    }),
  );
};

const design = which === 'design' ? readBower(read(files[0]!), files[0]!) : null;
const plan = design ? parsePlantingPlan(read(files[1]!), files[1]!) : null;
const make = (taxa: Growable) =>
  design && plan
    ? plantingOn(design.bower, plan, { taxa: specimen(taxa), care, years, seed, viewpoints: design.viewpoints })
    : (which === 'mixed' ? mixedOnVault : which === 'dome' ? wisteriaOnHemisphere : which === 'wisteria' ? wisteriaOnVault : referencePalette)({ taxa: specimen(taxa), care, years, seed });

const library = loadGrowable(`${root}species`);
const until = `${2027 + years - 1}-12-31`;
const t0 = performance.now();
const lap = () => `${((performance.now() - t0) / 1000).toFixed(0)} s`;
let text: string;
let result: unknown;
let runs: number;
let kind: string;
if (mode === 'growth') {
  const only = options.only?.split(',').filter(Boolean);
  const variations = only ? GROWTH_VARIATIONS.filter((v) => v.id === 'as_modelled' || only.some((o) => v.parameter.includes(o) || v.id.includes(o))) : GROWTH_VARIATIONS;
  const r = growthSensitivity(make, library, until, variations, (row) => console.error(`  ${lap()}  ${row.label}`));
  text = formatGrowthSensitivity(r);
  result = r;
  runs = r.rows.length;
  kind = `growth${only ? `-${only.join('+').replace(/[^a-zA-Z0-9+]+/g, '_')}` : ''}`;
} else if (mode === 'band') {
  const r = growthBand(make, library, until, (end) => console.error(`  ${lap()}  ${end === 'mid' ? 'as modelled' : `${end} end`}`));
  text = formatGrowthBand(r);
  result = r;
  runs = 3;
  kind = 'band';
} else {
  const r = sensitivity(make, library, until);
  text = formatSensitivity(r);
  result = r;
  runs = r.rows.length;
  kind = 'sensitivity';
}
console.log(text);
console.log(`\n${runs} runs in ${lap()}`);

mkdirSync(`${root}out`, { recursive: true });
const file = `${root}out/${design ? design.bower.id : which}-${care}-${years}y${specimenM === null ? '' : `-specimen${specimenM}`}.${kind}`;
writeFileSync(`${file}.txt`, `${text}\n`);
writeFileSync(`${file}.json`, JSON.stringify(result, null, 2));
console.log(`written: ${file}.txt and .json`);
