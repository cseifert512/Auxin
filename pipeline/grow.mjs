// Grow a planting on a converted snapshot and keep the record.
//   node pipeline/grow.mjs [snapshot] [trained|untended] [years] [seed]
// Reads  scenes/<snapshot>/bower.json and planting.json
// Writes scenes/<snapshot>/runs/<care>-<years>y/growth.json  (every stem, leaf and flower with its days)
//                                              report.json, report.txt, run.json
//
// The simulator is the one in the Horti-code-ture checkout beside this
// repository, or the folder snapshot.json names as `simulator` (a branch of it
// checked out somewhere else), or HORTI_DIR. It is read in place and nothing
// is written there. Which it was, and at which commit, goes into run.json.
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { clear } from './clear.mjs';
import { reseat } from './reseat.mjs';
import { thin } from './thin.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const settings = JSON.parse(readFileSync(new URL('../snapshot.json', import.meta.url), 'utf8'));
const horti = resolve(root, process.env.HORTI_DIR ?? settings.simulator ?? '../Horti-code-ture');
if (!existsSync(resolve(horti, 'packages/core/src/sim/engine.ts'))) {
  throw new Error(`no plant simulator at ${horti}${settings.simulator && !process.env.HORTI_DIR ? ': snapshot.json names it as `simulator`; take that line out to use the checkout beside this repository' : ''}`);
}
const core = (file) => import(pathToFileURL(resolve(horti, 'packages/core/src', file)).href);

// options: --bower=<file in the scene folder>  --plan=<file in the scene folder>  --specimen=<metres each plant stands when it goes in>  --name=<run folder>
//          --band=low|high   every plant at the low or the high end of what is published for a year's growth, where a range is given
//          --stems=<times>   how many stems the gardener lets share one member, as a multiple of what each plant's model
//                            assumes (2 to a member, 3 to a main one: a training decision the models carry as a number)
// The gardener's hand, which is a decision about this building and not a fact about a plant:
//          --free=vine,akebia   plants (by the name in their plant ID) that are not cut back to keep them in: their yearly
//                            shortening of side shoots and trimming to bounds are left out. Pruning a plant needs in order
//                            to flower (a wisteria's spurs, a late clematis cut down in February) is kept.
//          --loose=<metres>  growth that stands off the timber is let stand this far before it is trimmed, where the
//                            routine trims nearer
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
// the simulator takes the end of the range from the environment (it has to, for callers that load its plants for it)
if (options.band) process.env.HORTI_GROWTH_BAND = options.band;
const band = process.env.HORTI_GROWTH_BAND ?? null;
const stock = loadGrowable(resolve(horti, 'species'));
// A specimen also has all its main stems under way: the model starts some of a young plant's in later seasons.
const specimen = (model) => {
  const why = `planted as a nursery specimen standing ${specimenM} m, not a young plant`;
  const tall = withParam(model, 'architecture.nurseryCaneM', specimenM, why);
  const starts = model.params['architecture.trunkStemStartYears']?.value;
  return Array.isArray(starts) ? withParam(tall, 'architecture.trunkStemStartYears', starts.map(() => 0), `${why}: every main stem already growing`) : tall;
};
const stemsTimes = options.stems ? Number(options.stems) : null;
const fuller = (model) => {
  let m = model;
  for (const key of ['architecture.maxStemsPerRoute', 'architecture.maxStemsPerPrimaryMember']) {
    const now = m.params[key]?.value;
    if (typeof now === 'number') m = withParam(m, key, Math.round(now * stemsTimes), `the gardener lets ${stemsTimes} times as many stems share a member as the model assumes: a training decision, not a fact about the plant`);
  }
  return m;
};
const asGrown = (model) => (stemsTimes ? fuller(specimenM ? specimen(model) : model) : specimenM ? specimen(model) : model);
const taxa = specimenM || stemsTimes ? new Map([...stock].map(([id, t]) => [id, { ...t, model: asGrown(t.model) }])) : stock;
const scenario = plantingOn(design.bower, parsePlantingPlan(read(plantingFile), plantingFile), { taxa, care, years, seed, viewpoints: design.viewpoints });
// The gardener's hand. The routines the simulator writes for each plant are the RHS's for a plant kept within
// bounds. How closely this building's plants are kept is a matter of design, so the plan of visits can be loosened
// here before it is carried out; what was changed goes into run.json.
const free = (options.free ?? '').split(',').filter(Boolean);
const looseM = options.loose ? Number(options.loose) : null;
const kindOf = (plantId) => plantId.split('.').slice(1).join('.').replace(/\.\d+$/, '');
let visits = scenario.events;
if (free.length) visits = visits.filter((e) => !(free.includes(kindOf(e.plantId)) && (e.type === 'shorten_side_shoots' || e.type === 'trim_to_bounds')));
if (looseM) visits = visits.map((e) => (e.type === 'trim_to_bounds' && e.freeBeyondM < looseM ? { ...e, freeBeyondM: looseM } : e));
const gardener = free.length || looseM ? { notKeptIn: free, letStandOffM: looseM, visitsLeftOut: scenario.events.length - visits.length } : null;
if (gardener) console.log(`the gardener's hand: ${free.length ? `${free.join(', ')} not cut back to keep them in (${gardener.visitsLeftOut} visits left out)` : ''}${free.length && looseM ? '; ' : ''}${looseM ? `growth let stand ${looseM} m off the timber before it is trimmed` : ''}`);
t0 = performance.now();
const sim = new Simulation(gardener ? { ...scenario, events: visits } : scenario).runUntil(`${2027 + years - 1}-12-31`);
console.log(`\n${scenario.name}\n${sim.day + 1} days simulated in ${((performance.now() - t0) / 1000).toFixed(1)} s`);

// What the gardener's visits took off, act by act and plant by plant: the care plan's own account of itself.
const cut = { byAct: {}, byPlant: {} };
for (const e of sim.events) {
  const kind = e.plantId.split('.').slice(1).join('.').replace(/\.\d+$/, '');
  for (const [table, key] of [[cut.byAct, e.type], [cut.byPlant, `${kind}: ${e.type}`]]) {
    table[key] ??= { visits: 0, stemRemovedM: 0 };
    table[key].visits++;
    table[key].stemRemovedM += e.effects.stemRemovedM;
  }
}
for (const table of [cut.byAct, cut.byPlant]) for (const row of Object.values(table)) row.stemRemovedM = Math.round(row.stemRemovedM);
const most = (table, n) => Object.entries(table).filter(([, r]) => r.stemRemovedM > 0).sort((a, b) => b[1].stemRemovedM - a[1].stemRemovedM).slice(0, n);
console.log(`
what the gardener cut off in ${years} years:`);
for (const [act, r] of most(cut.byAct, 8)) console.log(`  ${act.padEnd(22)} ${String(r.stemRemovedM).padStart(6)} m in ${r.visits} visits`);
console.log('  of which, most:');
for (const [what, r] of most(cut.byPlant, 10)) console.log(`    ${what.padEnd(44)} ${String(r.stemRemovedM).padStart(6)} m`);

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
const git = (...args) => {
  try {
    return execFileSync('git', ['-C', horti, ...args], { encoding: 'utf8' }).trim();
  } catch {
    return 'unknown';
  }
};
const commit = git('rev-parse', 'HEAD');
const branch = git('rev-parse', '--abbrev-ref', 'HEAD');
// a tenth of a millimetre is as fine as anything here is known: it also halves the file
writeFileSync(resolve(out, 'growth.json'), JSON.stringify(growth, (_, v) => (typeof v === 'number' && !Number.isInteger(v) ? Math.round(v * 1e4) / 1e4 : v)));
writeFileSync(resolve(out, 'report.json'), JSON.stringify(report, null, 2));
writeFileSync(resolve(out, 'report.txt'), `${text}\n`);
writeFileSync(
  resolve(out, 'run.json'),
  `${JSON.stringify({ snapshot, bower: options.bower ?? 'bower.json', plan: options.plan ?? 'planting.json', specimenM, band, stemsTimes, gardener, care, years, seed, gardenerCut: cut, simulator: { repository: 'horti-code-ture', branch, commit }, toCheck: design.warnings, notModelledOrAssumed: notes, reseated: seated.summary, thinned: thinned.summary, cleared: cleared.summary }, null, 2)}\n`,
);
console.log(`\n${text}`);
console.log(`\nwritten: ${out}`);
