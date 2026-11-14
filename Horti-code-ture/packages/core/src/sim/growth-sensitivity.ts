/**
 * Which of the numbers behind growth move what a building is designed around, and how far a result moves between
 * the low and the high end of what is published for how fast a plant grows.
 * DEVELOPMENT_GUIDE.md stage 7: "Add credible intervals and scenario uncertainty".
 *
 * Two tools, both of which run one scenario several times and set the runs side by side:
 *
 *   growthSensitivity  one parameter at a time, taken to half and to one and a half times its value (a capacity one
 *                      stem fewer and one more), ranked by how far four readings move: the height each plant's
 *                      lasting framework has reached by year, the share of route held, the gardener's tie-ins, and
 *                      the timber still seen from the viewpoints. It says which numbers to go and source or measure
 *                      first. The variations are multiples, not estimates: nothing here says a plant grows half as
 *                      fast as its model gives it, only what would follow if it did.
 *
 *   growthBand         the scenario at the low end, as modelled, and at the high end of the ranges its growth models
 *                      give for extension (`atBandEnd` in model.ts), so that a result is reported as a band ("reaches
 *                      the top in year four to seven") and not as one date. These are the sources' ends, not multiples.
 */
import { Simulation } from './engine.ts';
import { type BandEnd, type GrowthModel, type RequiredParamKey, atBandEnd, hasBand, param, shootParam, withParam, withUnknown } from './model.ts';
import { designReport } from './report.ts';
import type { Growable } from './scenarios.ts';
import type { Scenario } from './types.ts';

/**
 * The caps on the length of a main stem that the growth models carried until 14 November 2026, for the taxa whose
 * cap was then taken away or changed: the planned length of the Wisteria prototype's leaders, or an RHS height band
 * used as a length. Six were taken away because no length of stem is published for the plant; four gave way to a
 * length that is published, or to the published size itself. Kept so that what those caps did to a run can still
 * be measured (`former_caps` below). They are not facts about the plants and are used nowhere else.
 */
export const FORMER_STEM_CAPS_M: Readonly<Record<string, readonly [number, number]>> = {
  'wisteria-sinensis': [7, 8.6],
  'wisteria-floribunda-macrobotrys': [7, 8.6],
  'campsis-x-tagliabueana-madame-galen': [8, 12],
  'hedera-helix': [8, 12],
  'lonicera-periclymenum-graham-thomas': [4, 8],
  'vitis-coignetiae': [12, 15],
  'hydrangea-anomala-subsp-petiolaris': [12, 15],
  'trachelospermum-jasminoides': [4, 9],
  'lonicera-henryi': [4, 10],
  'clematis-viticella-etoile-violette': [2.8, 4],
};

export interface GrowthVariation {
  id: string;
  /** The parameter, or the rule, that this run varies: runs of the same one are ranked together. */
  parameter: string;
  label: string;
  apply: (taxa: Growable) => Growable;
  /** For what is not a number in a growth model: a change to the scenario itself. */
  scenario?: (s: Scenario) => Scenario;
}

const each = (taxa: Growable, change: (model: GrowthModel, taxonId: string) => GrowthModel): Growable => new Map([...taxa].map(([id, t]) => [id, { profile: t.profile, model: change(t.model, id) }]));

/** One number of every model multiplied by `factor`; `cap` holds a share or a chance at or under 1. */
function scaled(key: RequiredParamKey, factor: number, cap?: number): (taxa: Growable) => Growable {
  const fit = (v: number) => (cap === undefined ? v * factor : Math.min(cap, v * factor));
  return (taxa) =>
    each(taxa, (model) => {
      const was = param(model, key) as number | number[];
      const why = `sensitivity: ${factor} times ${key}`;
      return withParam(model, key, (Array.isArray(was) ? was.map(fit) : fit(was)) as never, why);
    });
}

/** A count of stems one fewer or one more, and never under one. */
function stepped(key: 'architecture.maxStemsPerRoute' | 'architecture.maxStemsPerPrimaryMember', by: number): (taxa: Growable) => Growable {
  return (taxa) => each(taxa, (model) => withParam(model, key, Math.max(1, param(model, key) + by), `sensitivity: ${by > 0 ? 'one more stem' : 'one stem fewer'} to a member (${key})`));
}

/** A number of the shoot in the air, the taxon's own or the generic one it is drawn with, multiplied. */
function scaledShoot(key: 'mechanics.searcherReachM' | 'attachment.graspReachM', factor: number): (taxa: Growable) => Growable {
  return (taxa) => each(taxa, (model) => withParam(model, key, shootParam(model, key) * factor, `sensitivity: ${factor} times ${key}`));
}

const LOW = 0.5;
const HIGH = 1.5;
const pair = (parameter: string, what: string, make: (factor: number) => (taxa: Growable) => Growable): GrowthVariation[] => [
  { id: `${parameter}_x${LOW}`, parameter, label: `half ${what}`, apply: make(LOW) },
  { id: `${parameter}_x${HIGH}`, parameter, label: `one and a half times ${what}`, apply: make(HIGH) },
];

/**
 * The runs of the triage. The first is the scenario as modelled; every other changes one thing in every plant's
 * model, or one rule of the scenario.
 */
export const GROWTH_VARIATIONS: readonly GrowthVariation[] = [
  { id: 'as_modelled', parameter: 'as modelled', label: 'as modelled', apply: (t) => t },
  {
    id: 'former_caps',
    parameter: 'architecture.maxStemLengthM',
    label: 'the caps on stem length taken away on 14 November 2026, put back',
    apply: (taxa) => each(taxa, (model, id) => (FORMER_STEM_CAPS_M[id] ? withParam(model, 'architecture.maxStemLengthM', [...FORMER_STEM_CAPS_M[id]] as [number, number], 'sensitivity: the cap this model carried until 14 November 2026, put back') : model)),
  },
  {
    id: 'no_stem_length',
    parameter: 'architecture.maxStemLengthM',
    label: 'no stem length at all, published or not',
    apply: (taxa) => each(taxa, (model) => withUnknown(model, 'architecture.maxStemLengthM')),
  },
  ...pair('extension.leaderMPerSeason', "the leader's extension a season", (f) => scaled('extension.leaderMPerSeason', f)),
  ...pair('extension.establishmentFactorByYear', 'the growth of the first seasons', (f) => scaled('extension.establishmentFactorByYear', f, 1)),
  ...pair('architecture.lateralLengthMByOrder', 'the planned length of laterals', (f) => scaled('architecture.lateralLengthMByOrder', f)),
  ...pair('architecture.lateralChanceByParentOrder', 'the chance of a lateral at a node', (f) => scaled('architecture.lateralChanceByParentOrder', f, 1)),
  { id: 'architecture.maxStemsPerRoute_-1', parameter: 'architecture.maxStemsPerRoute', label: 'one stem fewer to a member or cable', apply: stepped('architecture.maxStemsPerRoute', -1) },
  { id: 'architecture.maxStemsPerRoute_+1', parameter: 'architecture.maxStemsPerRoute', label: 'one more stem to a member or cable', apply: stepped('architecture.maxStemsPerRoute', 1) },
  { id: 'architecture.maxStemsPerPrimaryMember_-1', parameter: 'architecture.maxStemsPerPrimaryMember', label: 'one stem fewer to a glulam member', apply: stepped('architecture.maxStemsPerPrimaryMember', -1) },
  { id: 'architecture.maxStemsPerPrimaryMember_+1', parameter: 'architecture.maxStemsPerPrimaryMember', label: 'one more stem to a glulam member', apply: stepped('architecture.maxStemsPerPrimaryMember', 1) },
  ...pair('routing.roleDropChance', 'the chance at a node that a shoot drops its heading', (f) => scaled('routing.roleDropChance', f, 1)),
  ...pair('attachment.maxGraspDiameterMm', 'the thickest support grasped', (f) => scaled('attachment.maxGraspDiameterMm', f)),
  ...pair('mechanics.searcherReachM', 'how far a shoot holds itself out', (f) => scaledShoot('mechanics.searcherReachM', f)),
  ...pair('attachment.graspReachM', 'how near a support a shoot takes hold', (f) => scaledShoot('attachment.graspReachM', f)),
  {
    id: 'every_stem_led_up',
    parameter: 'training: which main stems are led up',
    label: 'every main stem led up, not the first alone',
    apply: (t) => t,
    scenario: (s) => ({ ...s, plantings: s.plantings.map((p) => ({ ...p, train: { ...p.train, stemsLedUp: 'all' as const } })) }),
  },
];

/** The years after planting at which a plant's height is read, as the design report's milestones are. */
export const HEIGHT_YEARS = [1, 3, 5, 10] as const;

export interface GrowthReadings {
  /** For each of `HEIGHT_YEARS` the run reaches: the height of the lasting framework, averaged over the plants. */
  meanHeightM: { yearsAfterPlanting: number; value: number }[];
  /** Plants whose lasting framework has come to the top of the structure by the end of the run. */
  plantsAtTop: number;
  /** Share of all route held by any plant at the end of the run. */
  routeHeldShare: number;
  /** Stretches of stem a gardener tied in, over the whole run. */
  tieIns: number;
  /** Share of the bare structure's timber still seen in mid July of the last year, averaged over the viewpoints; null with no viewpoints. */
  timberSeenJuly: number | null;
}

export interface GrowthRow extends GrowthReadings {
  id: string;
  parameter: string;
  label: string;
  /** Height of each plant's lasting framework at each of `HEIGHT_YEARS` the run reaches. */
  heights: { plantId: string; taxonId: string; yearsAfterPlanting: number; highestM: number }[];
}

/**
 * The top of the structure, for saying a plant has arrived: the engine's own mark, at which a stem set on making
 * height turns to run level (`chooseNext`).
 */
const ARRIVED_SHARE = 0.985;

function read(sim: Simulation): GrowthReadings & { heights: GrowthRow['heights']; scenario: string; topM: number } {
  const report = designReport(sim);
  const heights: GrowthRow['heights'] = [];
  for (const plant of sim.plants.values()) {
    for (const s of sim.summaries) {
      if (s.plantId !== plant.id) continue;
      const n = s.year - plant.firstPlantedYear + 1;
      if ((HEIGHT_YEARS as readonly number[]).includes(n)) heights.push({ plantId: plant.id, taxonId: plant.taxonId, yearsAfterPlanting: n, highestM: s.highestM });
    }
  }
  const meanHeightM = HEIGHT_YEARS.map((n) => {
    const at = heights.filter((h) => h.yearsAfterPlanting === n);
    return { yearsAfterPlanting: n, value: at.length ? at.reduce((sum, h) => sum + h.highestM, 0) / at.length : NaN };
  }).filter((h) => !Number.isNaN(h.value));
  const topM = report.structure.crownHeightM;
  const july = report.months.find((m) => m.month === 7);
  return {
    scenario: report.scenario,
    topM,
    heights,
    meanHeightM,
    plantsAtTop: report.plants.filter((p) => p.highestM >= topM * ARRIVED_SHARE).length,
    routeHeldShare: report.routes.heldShare,
    tieIns: report.gardening.reduce((sum, g) => sum + g.tieIns, 0),
    timberSeenJuly: july && july.views.length ? july.views.reduce((sum, v) => sum + v.timberVisible, 0) / july.views.length : null,
  };
}

export interface GrowthSensitivity {
  scenario: string;
  until: string;
  /** Height of the top of the structure. */
  topM: number;
  rows: GrowthRow[];
  ranking: GrowthRank[];
}

export interface GrowthRank {
  parameter: string;
  /**
   * How far each reading moves across the parameter's runs and the run as modelled, highest less lowest, as a share
   * of the reading as modelled. Heights: the largest such swing among the years read.
   */
  swing: { height: number; routeHeld: number; tieIns: number; timberSeen: number | null };
  /** The largest of the four: what the parameters are ranked by. */
  largest: number;
}

/** Highest less lowest of a reading over some runs, as a share of the reading as modelled. */
function swing(base: number, values: number[]): number {
  const all = [base, ...values];
  const spread = Math.max(...all) - Math.min(...all);
  return base !== 0 ? spread / Math.abs(base) : spread === 0 ? 0 : Infinity;
}

export function rankGrowth(rows: readonly GrowthRow[]): GrowthRank[] {
  const base = rows.find((r) => r.id === 'as_modelled');
  if (!base) throw new Error('a growth sensitivity is ranked against the run as modelled, which is not among the rows');
  const parameters = [...new Set(rows.filter((r) => r !== base).map((r) => r.parameter))];
  return parameters
    .map((parameter) => {
      const mine = rows.filter((r) => r.parameter === parameter);
      const height = Math.max(0, ...base.meanHeightM.map((h) => swing(h.value, mine.flatMap((r) => r.meanHeightM.filter((x) => x.yearsAfterPlanting === h.yearsAfterPlanting).map((x) => x.value)))));
      const routeHeld = swing(base.routeHeldShare, mine.map((r) => r.routeHeldShare));
      const tieIns = swing(base.tieIns, mine.map((r) => r.tieIns));
      const timberSeen = base.timberSeenJuly === null ? null : swing(base.timberSeenJuly, mine.flatMap((r) => (r.timberSeenJuly === null ? [] : [r.timberSeenJuly])));
      return { parameter, swing: { height, routeHeld, tieIns, timberSeen }, largest: Math.max(height, routeHeld, tieIns, timberSeen ?? 0) };
    })
    .sort((a, b) => b.largest - a.largest);
}

/**
 * Run the scenario once for each variation and rank the parameters. `make` builds the scenario from a taxon
 * library, so that each run differs only in what is varied. `onRun` is told as each run ends: a sweep is slow.
 */
export function growthSensitivity(make: (taxa: Growable) => Scenario, taxa: Growable, until: string, variations: readonly GrowthVariation[] = GROWTH_VARIATIONS, onRun?: (row: GrowthRow) => void): GrowthSensitivity {
  let scenario = '';
  let topM = 0;
  const rows: GrowthRow[] = variations.map((v) => {
    const built = make(v.apply(taxa));
    const r = read(new Simulation(v.scenario ? v.scenario(built) : built).runUntil(until));
    if (v.id === 'as_modelled' || !scenario) scenario = r.scenario;
    topM = r.topM;
    const row: GrowthRow = { id: v.id, parameter: v.parameter, label: v.label, heights: r.heights, meanHeightM: r.meanHeightM, plantsAtTop: r.plantsAtTop, routeHeldShare: r.routeHeldShare, tieIns: r.tieIns, timberSeenJuly: r.timberSeenJuly };
    onRun?.(row);
    return row;
  });
  return { scenario, until, topM, rows, ranking: rankGrowth(rows) };
}

const pct = (x: number | null) => (x === null ? '-' : !Number.isFinite(x) ? 'from 0' : `${(100 * x).toFixed(x < 0.1 ? 1 : 0)}%`);

export function formatGrowthSensitivity(s: GrowthSensitivity): string {
  const out: string[] = [];
  out.push(`GROWTH SENSITIVITY of ${s.scenario}, to ${s.until}`);
  out.push('What the readings a building is designed around would be if one number in every plant model were other than it is.');
  out.push('Half and one and a half times are multiples, not estimates: most of these numbers have never been measured.');
  out.push('');
  const years = s.rows[0]?.meanHeightM.map((h) => h.yearsAfterPlanting) ?? [];
  const w = Math.max(...s.rows.map((r) => r.label.length)) + 2;
  out.push(`  ${''.padEnd(w)}${years.map((n) => `height y${n}`.padStart(11)).join('')}${'at the top'.padStart(12)}${'route held'.padStart(12)}${'tie-ins'.padStart(9)}${'timber seen, Jul'.padStart(18)}`);
  let last = '';
  for (const r of s.rows) {
    if (r.parameter !== last && r.id !== 'as_modelled') out.push(`  ${r.parameter}`);
    last = r.parameter;
    out.push(`  ${r.label.padEnd(w)}${years.map((n) => `${(r.meanHeightM.find((h) => h.yearsAfterPlanting === n)?.value ?? NaN).toFixed(2)} m`.padStart(11)).join('')}${String(r.plantsAtTop).padStart(12)}${pct(r.routeHeldShare).padStart(12)}${String(r.tieIns).padStart(9)}${pct(r.timberSeenJuly).padStart(18)}`);
  }
  out.push('');
  out.push(`  Heights are of the lasting framework, averaged over the plants; "at the top" counts the plants within ${(100 * (1 - ARRIVED_SHARE)).toFixed(1)}% of the top of the structure (${s.topM.toFixed(2)} m) at the end.`);
  out.push('');
  out.push('RANKING: how far each reading moves across a parameter\'s runs, highest less lowest, as a share of the reading as modelled');
  const pw = Math.max(...s.ranking.map((r) => r.parameter.length)) + 2;
  out.push(`  ${''.padEnd(4)}${''.padEnd(pw)}${'height'.padStart(9)}${'route held'.padStart(12)}${'tie-ins'.padStart(9)}${'timber seen'.padStart(13)}`);
  s.ranking.forEach((r, i) => out.push(`  ${`${i + 1}.`.padEnd(4)}${r.parameter.padEnd(pw)}${pct(r.swing.height).padStart(9)}${pct(r.swing.routeHeld).padStart(12)}${pct(r.swing.tieIns).padStart(9)}${pct(r.swing.timberSeen).padStart(13)}`));
  return out.join('\n');
}

// ---------------------------------------------------------------------------
// The band: low end, as modelled, high end
// ---------------------------------------------------------------------------
export interface GrowthBandRow {
  plantId: string;
  taxonId: string;
  /** False where the plant's model gives no range for its extension: it was run at its one value at both ends. */
  hasBand: boolean;
  /** Height of the lasting framework at the low end, as modelled, and at the high end, for each year read. */
  heights: { yearsAfterPlanting: number; low: number; mid: number; high: number }[];
  /** The first year after planting in which the lasting framework had come to the top of the structure; null: not within the run. */
  topReached: { low: number | null; mid: number | null; high: number | null };
}

export interface GrowthBand {
  scenario: string;
  until: string;
  topM: number;
  rows: GrowthBandRow[];
}

/** Every model of a library taken to one end of its extension ranges. */
export function taxaAtBandEnd(taxa: Growable, end: BandEnd): Growable {
  return each(taxa, (model) => atBandEnd(model, end));
}

/** The scenario at the low end, as modelled and at the high end of what its growth models give for extension. */
export function growthBand(make: (taxa: Growable) => Scenario, taxa: Growable, until: string, onRun?: (end: BandEnd | 'mid') => void): GrowthBand {
  const run = (end: BandEnd | 'mid') => {
    const sim = new Simulation(make(end === 'mid' ? taxa : taxaAtBandEnd(taxa, end))).runUntil(until);
    onRun?.(end);
    return sim;
  };
  const sims = { low: run('low'), mid: run('mid'), high: run('high') };
  // the highest point of any route, as the design report gives it
  const topM = Math.max(0, ...[...sims.mid.scenario.bower.graph.nodes.values()].map((n) => n.position.z));
  const firstAtTop = (sim: Simulation, plantId: string, firstYear: number): number | null => {
    const hit = sim.summaries.filter((s) => s.plantId === plantId && s.highestM >= topM * ARRIVED_SHARE).map((s) => s.year - firstYear + 1);
    return hit.length ? Math.min(...hit) : null;
  };
  const rows: GrowthBandRow[] = [...sims.mid.plants.values()].map((plant) => {
    const at = (sim: Simulation, n: number) => sim.summaries.find((s) => s.plantId === plant.id && s.year - plant.firstPlantedYear + 1 === n)?.highestM;
    const heights = HEIGHT_YEARS.flatMap((n) => {
      const mid = at(sims.mid, n);
      return mid === undefined ? [] : [{ yearsAfterPlanting: n, low: at(sims.low, n) ?? NaN, mid, high: at(sims.high, n) ?? NaN }];
    });
    return {
      plantId: plant.id,
      taxonId: plant.taxonId,
      hasBand: hasBand(taxa.get(plant.taxonId)!.model),
      heights,
      topReached: { low: firstAtTop(sims.low, plant.id, plant.firstPlantedYear), mid: firstAtTop(sims.mid, plant.id, plant.firstPlantedYear), high: firstAtTop(sims.high, plant.id, plant.firstPlantedYear) },
    };
  });
  return { scenario: sims.mid.scenario.name, until, topM, rows };
}

export function formatGrowthBand(b: GrowthBand): string {
  const out: string[] = [];
  out.push(`GROWTH BAND of ${b.scenario}, to ${b.until}`);
  out.push('The height of each plant\'s lasting framework, at the low end and at the high end of the range its growth model gives for a year\'s extension and for the slow first seasons.');
  out.push(`A plant has come to the top when its framework stands within ${(100 * (1 - ARRIVED_SHARE)).toFixed(1)}% of the top of the structure, ${b.topM.toFixed(2)} m.`);
  out.push('');
  const years = b.rows[0]?.heights.map((h) => h.yearsAfterPlanting) ?? [];
  const w = Math.max(...b.rows.map((r) => r.plantId.length)) + 2;
  out.push(`  ${''.padEnd(w)}${years.map((n) => `year ${n}`.padStart(16)).join('')}   comes to the top: high end / as modelled / low end`);
  const span = (lo: number, hi: number) => (Math.abs(hi - lo) < 0.05 ? `${lo.toFixed(1)} m` : `${Math.min(lo, hi).toFixed(1)} to ${Math.max(lo, hi).toFixed(1)} m`);
  for (const r of b.rows) {
    const t = r.topReached;
    // the high end arrives first; "never" is within this run, which says nothing of the years after it
    const when = (year: number | null) => (year === null ? 'not in this run' : `year ${year}`);
    const top = t.high === null && t.mid === null && t.low === null ? 'not in this run' : `${when(t.high)} / ${when(t.mid)} / ${when(t.low)}`;
    out.push(`  ${r.plantId.padEnd(w)}${years.map((n) => { const h = r.heights.find((x) => x.yearsAfterPlanting === n); return (h ? span(h.low, h.high) : '-').padStart(16); }).join('')}   ${top}${r.hasBand ? '' : '  (no range given: one value)'}`);
  }
  return out.join('\n');
}
