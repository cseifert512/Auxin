// Grow a planting on a converted snapshot and keep the record.
//   node pipeline/grow.mjs [snapshot] [trained|untended] [years] [seed]
// Reads  scenes/<snapshot>/bower.json and planting.json
// Writes scenes/<snapshot>/runs/<care>-<years>y/growth.json  (every stem, leaf and flower with its days)
//                                              report.json, report.txt, run.json
//
// The simulator is the one in the Horti-code-ture checkout beside this
// repository (or at HORTI_DIR). It is read in place and nothing is written there.
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { clear } from './clear.mjs';
import { reseat } from './reseat.mjs';
import { thin } from './thin.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const horti = resolve(process.env.HORTI_DIR ?? resolve(root, '../Horti-code-ture'));
const core = (file) => import(pathToFileURL(resolve(horti, 'packages/core/src', file)).href);

// options: --bower=<file in the scene folder>  --plan=<file in the scene folder>  --specimen=<metres each plant stands when it goes in>  --name=<run folder>
const options = Object.fromEntries(process.argv.slice(2).filter((a) => a.startsWith('--')).map((a) => a.slice(2).split('=')));
const [snapshot = JSON.parse(readFileSync(new URL('../snapshot.json', import.meta.url), 'utf8')).snapshot, careArg = 'trained', yearsArg = '10', seedArg = '7'] = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const care = careArg === 'untended' ? 'untended' : 'trained';
const years = Number(yearsArg);
const seed = Number(seedArg);
const scene = resolve(root, 'scenes', snapshot);
const read = (file) => JSON.parse(readFileSync(file, 'utf8'));

const { readBower } = await core('bower/description.ts');
const { loadGrowable } = await core('node/load-taxa.ts');
const { Simulation } = await core('sim/engine.ts');
const { withParam } = await core('sim/model.ts');
const { toRenderData } = await core('sim/render-data.ts');
const { parsePlantingPlan, plantingOn } = await core('sim/planting.ts');
const { designReport, formatDesignReport } = await core('sim/report.ts');

const bowerFile = resolve(scene, options.bower ?? 'bower.json');
const plantingFile = resolve(scene, options.plan ?? 'planting.json');
let t0 = performance.now();
const design = readBower(read(bowerFile), bowerFile);
console.log(`read ${snapshot} in ${(performance.now() - t0).toFixed(0)} ms: ${Object.entries(design.bower.facts).filter(([k]) => k !== 'source').map(([k, v]) => `${k} ${v}`).join(', ')}`);
for (const w of design.warnings) console.log(`  to check: ${w}`);

// The simulator plants each climber as a young nursery cane, 0.15 to 1.2 m long by taxon. A specimen is the same
// plant with a longer stem on the day it goes in; how fast it then grows, and the slow years after planting, are
// left as the model has them.
const specimenM = options.specimen ? Number(options.specimen) : null;
const stock = loadGrowable(resolve(horti, 'species'));
// A specimen also has all its main stems under way: the model starts some of a young plant's in later seasons.
const specimen = (model) => {
  const why = `planted as a nursery specimen standing ${specimenM} m, not a young plant`;
  const tall = withParam(model, 'architecture.nurseryCaneM', specimenM, why);
  const starts = model.params['architecture.trunkStemStartYears']?.value;
  return Array.isArray(starts) ? withParam(tall, 'architecture.trunkStemStartYears', starts.map(() => 0), `${why}: every main stem already growing`) : tall;
};
const taxa = specimenM ? new Map([...stock].map(([id, t]) => [id, { ...t, model: specimen(t.model) }])) : stock;
const scenario = plantingOn(design.bower, parsePlantingPlan(read(plantingFile), plantingFile), { taxa, care, years, seed, viewpoints: design.viewpoints });
t0 = performance.now();
const sim = new Simulation(scenario).runUntil(`${2027 + years - 1}-12-31`);
console.log(`\n${scenario.name}\n${sim.day + 1} days simulated in ${((performance.now() - t0) / 1000).toFixed(1)} s`);

const notes = sim.decisions.filter((d) => ['not_modelled', 'part_not_modelled', 'assumed', 'generic_shoot'].includes(d.kind)).map((d) => `${d.plantId}: ${d.text}`);
const report = designReport(sim);
const text = formatDesignReport(report);

// The simulator's input has no way to say which way a timber section is turned, and takes its deep side to face up.
// The snapshot knows. Each stem and what grows on it is turned about its member on to the faces that are really there.
const growth = toRenderData(sim);
const seated = reseat(growth, read(resolve(root, 'releases', snapshot, 'centrelines.json')));
console.log(`\nre-seated on the real timber faces: ${seated.summary}`);
const thinned = thin(growth);
console.log(`thinned for drawing at the scale of a room: ${thinned.summary}`);
// The simulator takes no account of the members that cross the one a stem is on. Nothing grows through wood.
const cleared = clear(growth, read(resolve(root, 'releases', snapshot, 'centrelines.json')));
console.log(`kept out of the timber: ${cleared.summary}`);

const out = resolve(scene, 'runs', options.name ?? `${care}-${years}y`);
mkdirSync(out, { recursive: true });
const commit = (() => {
  try {
    return execFileSync('git', ['-C', horti, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
  } catch {
    return 'unknown';
  }
})();
// a tenth of a millimetre is as fine as anything here is known: it also halves the file
writeFileSync(resolve(out, 'growth.json'), JSON.stringify(growth, (_, v) => (typeof v === 'number' && !Number.isInteger(v) ? Math.round(v * 1e4) / 1e4 : v)));
writeFileSync(resolve(out, 'report.json'), JSON.stringify(report, null, 2));
writeFileSync(resolve(out, 'report.txt'), `${text}\n`);
writeFileSync(
  resolve(out, 'run.json'),
  `${JSON.stringify({ snapshot, bower: options.bower ?? 'bower.json', plan: options.plan ?? 'planting.json', specimenM, care, years, seed, simulator: { repository: 'horti-code-ture', commit }, toCheck: design.warnings, notModelledOrAssumed: notes, reseated: seated.summary, thinned: thinned.summary, cleared: cleared.summary }, null, 2)}\n`,
);
console.log(`\n${text}`);
console.log(`\nwritten: ${out}`);
