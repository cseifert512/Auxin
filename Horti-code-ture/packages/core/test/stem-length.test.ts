import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { afterEach, describe, expect, it } from 'vitest';
import { loadGrowable } from '../src/node/load-taxa.ts';
import { isEvidence } from '../src/provenance.ts';
import { Simulation } from '../src/sim/engine.ts';
import { FORMER_STEM_CAPS_M, GROWTH_VARIATIONS, formatGrowthBand, formatGrowthSensitivity, growthBand, growthSensitivity, taxaAtBandEnd } from '../src/sim/growth-sensitivity.ts';
import { atBandEnd, hasBand, known, param, parseGrowthModel, withParam } from '../src/sim/model.ts';
import { parsePlantingPlan, plantingOn } from '../src/sim/planting.ts';
import { designReport, formatDesignReport } from '../src/sim/report.ts';
import { type Growable, wisteriaOnHemisphere } from '../src/sim/scenarios.ts';
import { DEFAULT_TRAINING, type Axis, type GardenerEvent, type Scenario, type TrainingPlan } from '../src/sim/types.ts';
import { STEMS_LED_UP, TRAINING_EXTENT } from '../src/vocab.ts';

// What ends a main stem, and who decides how far a plant is taken (owner's decision, 14 November 2026: a plant known
// to grow further is not to be capped by an assumed length). CLAUDE.md: "No bare numbers about plants", "Height is not
// route length". KEY.md section 4: "Height is not enough". PROJECT_CONTEXT.md section 3.4: the gardened plant is the
// baseline, and section 5 C: gardeners choose leaders and train shoots. HORTICULTURAL_INTERVENTIONS.md section 2,
// `train_leader`. DEVELOPMENT_GUIDE.md stage 7: "Add credible intervals and scenario uncertainty".
// docs/GROWTH_WITHOUT_STEM_CAPS.md says what was changed and what it did to earlier runs.

const speciesDir = fileURLToPath(new URL('../../../species', import.meta.url));
// as written, whatever the environment says: these tests set the band themselves
const taxa = loadGrowable(speciesDir, { band: null });
const W = 'wisteria-sinensis';
const end = (years: number) => `${2027 + years - 1}-12-31`;
const dome = (t: Growable, years: number, change?: (s: Scenario) => Scenario) => {
  const s = wisteriaOnHemisphere({ taxa: t, care: 'trained', years });
  return new Simulation(change ? change(s) : s).runUntil(end(years));
};
const trainAll = (train: Partial<TrainingPlan>) => (s: Scenario): Scenario => ({ ...s, plantings: s.plantings.map((p) => ({ ...p, train })) });
const lengthOf = (a: Axis) => (a.alive > 0 ? a.lengthAt[a.alive - 1]! : 0);
const leaders = (sim: Simulation, plantId: string) => [...sim.axes.values()].filter((a) => a.plantId === plantId && a.role === 'leader' && a.removedDay === null);
const framework = (sim: Simulation) => [...sim.axes.values()].filter((a) => (a.role === 'leader' || a.role === 'lateral') && a.removedDay === null);
const CROWN = 7.5;
const ARRIVED = CROWN * 0.985;
const firstYearAtTop = (sim: Simulation, plantId: string) => {
  const hit = sim.summaries.filter((s) => s.plantId === plantId && s.highestM >= ARRIVED).map((s) => s.year - 2026);
  return hit.length ? Math.min(...hit) : null;
};

describe('the words for how far a plant is taken', () => {
  it('are in the vocabulary before they are used (CLAUDE.md: vocabulary first)', () => {
    expect(TRAINING_EXTENT).toEqual(['top_of_support', 'height']);
    expect(STEMS_LED_UP).toEqual(['first', 'all']);
    expect(DEFAULT_TRAINING).toEqual({ extent: { to: 'top_of_support' }, stemsLedUp: 'first' });
  });
});

describe('the length at which a main stem stops', () => {
  const file = `${speciesDir}/${W}/model.json`;
  const raw = () => JSON.parse(readFileSync(file, 'utf8')) as { params: Record<string, unknown> };

  it('may be left out of a growth model: it is then unknown, and nothing of the plant sets it', () => {
    const json = raw();
    delete json.params['architecture.maxStemLengthM'];
    const model = parseGrowthModel(json, file);
    expect(known(model, 'architecture.maxStemLengthM')).toBeNull();
    expect(model.params['architecture.maxStemLengthM'].status).toBe('unknown');
  });

  it('cannot come in under its old name: a planned length that was never a fact about the plant is refused, not read', () => {
    const json = raw();
    json.params['architecture.leaderLengthM'] = { value: [7, 8.6], unit: 'm', status: 'provisional_design_assumption', basis: 'carried over from the prototype' };
    expect(() => parseGrowthModel(json, file)).toThrow(/architecture\.leaderLengthM|Unrecognized key/);
  });

  // The brief of 14 November 2026: "A maximum stem length applies only where a published STEM LENGTH exists for that
  // plant, and is labelled as such"; "Plants that really are short stay short where published sizes say so ... with the source".
  it('is given in the library only with its source, and never from the prototype or from a height band taken as a length', () => {
    const given: string[] = [];
    for (const [id, t] of taxa) {
      const p = t.model.params['architecture.maxStemLengthM'];
      if (p.value === null) {
        // an unknown says why there is none
        if (t.profile.attachment.mechanism !== 'none') expect(p.basis, id).toBeTruthy();
        continue;
      }
      given.push(id);
      expect(p.source, `${id} names where its stem length is published`).toMatch(/^https?:\/\//);
      expect(p.basis ?? '', id).not.toMatch(/prototype/i);
      expect(p.unit, id).toBe('m');
      // a height read as a length is not evidence of a length, and says that it is a reading
      if (!isEvidence(p)) expect(p.basis ?? '', id).toMatch(/read as|do not agree|reading/);
    }
    // the plants whose stems are published as so long, and the short ones whose published size is that of their stems
    expect(given.sort()).toEqual(
      [
        'akebia-quinata',
        'clematis-armandi',
        'clematis-cirrhosa-freckles',
        'clematis-princess-diana',
        'clematis-viticella-etoile-violette',
        'hydrangea-anomala-subsp-petiolaris',
        'lonicera-henryi',
        'rosa-the-generous-gardener',
        'thunbergia-alata',
        'trachelospermum-jasminoides',
      ].sort(),
    );
    // the vigorous ones the owner named, and those whose cap was a height
    for (const id of [W, 'wisteria-floribunda-macrobotrys', 'vitis-coignetiae', 'hedera-helix', 'campsis-x-tagliabueana-madame-galen', 'lonicera-periclymenum-graham-thomas']) {
      expect(known(taxa.get(id)!.model, 'architecture.maxStemLengthM'), id).toBeNull();
    }
  });

  it('keeps the short plants short: a Group 3 clematis stops at its published size, whatever it is given to climb', () => {
    const id = 'clematis-viticella-etoile-violette';
    const p = taxa.get(id)!.model.params['architecture.maxStemLengthM'];
    expect(p.value).toEqual([2.5, 4]);
    // the RHS ultimate-height band of the cultivar, and nothing added to it
    expect(p.value).toEqual(taxa.get(id)!.profile.size.rhsUltimateHeightM.value);
  });
});

describe('a wisteria on the 15 m hemisphere, with no length of its own to stop at', () => {
  const YEARS = 12;
  const sim = dome(taxa, YEARS);
  const model = taxa.get(W)!.model;
  const capped = dome(new Map([[W, { profile: taxa.get(W)!.profile, model: withParam(model, 'architecture.maxStemLengthM', [...FORMER_STEM_CAPS_M[W]!] as [number, number], 'the cap this model carried until 14 November 2026') }]]), YEARS);

  it('is led to the crown, 11.78 m of route away, and takes years over it (KEY.md section 4: height is not enough)', () => {
    for (const plant of sim.plants.values()) {
      const year = firstYearAtTop(sim, plant.id);
      expect(year, plant.id).not.toBeNull();
      // a stem that made its height at the pace it makes its length would be there far sooner: 7.5 m is not 11.78 m
      expect(year!, plant.id).toBeGreaterThanOrEqual(4);
      expect(year!, plant.id).toBeLessThanOrEqual(9);
    }
  });

  it('has main stems that no length ended: each stopped, if it did, for want of a way on', () => {
    for (const plant of sim.plants.values()) {
      for (const a of leaders(sim, plant.id)) {
        expect(a.targetLengthM, a.id).toBe(Infinity);
        if (a.tip.state === 'stopped') expect(a.tip.reason, a.id).toMatch(/no way on/);
      }
    }
    expect(sim.decisions.some((d) => /stems of this plant are given as/.test(d.text))).toBe(false);
  });

  it('with the cap it carried until 14 November 2026 never arrives, and the run says that a length and not the support stopped it', () => {
    for (const plant of capped.plants.values()) {
      expect(firstYearAtTop(capped, plant.id), plant.id).toBeNull();
      const stopped = leaders(capped, plant.id).filter((a) => a.tip.state === 'stopped' && /length given for a stem/.test(a.tip.reason));
      expect(stopped.length, plant.id).toBeGreaterThan(0);
      for (const a of stopped) {
        // (to a millimetre: the last point of a coil is laid a hair past the length)
        expect(lengthOf(a), a.id).toBeLessThanOrEqual(8.6 + 1e-3);
        expect(capped.decisions.some((d) => d.axisId === a.id && d.kind === 'stopped' && /Whether there was support ahead of it did not decide this/.test(d.text)), a.id).toBe(true);
      }
    }
    // the report of the capped run says an assumption was varied
    expect(designReport(capped, { viewpoints: [] }).variations.map((v) => v.parameter)).toContain('architecture.maxStemLengthM');
  });

  it('is the same plant as the capped one until a stem passes the length it would have stopped at', () => {
    // the planned length used to be drawn from the plant's stream; a number is still drawn there, so nothing else moves
    const at = (s: Simulation, year: number) => s.summaries.filter((x) => x.year === year).map((x) => x.frameworkM);
    expect(at(sim, 2027)).toEqual(at(capped, 2027));
    expect(at(sim, 2028)).toEqual(at(capped, 2028));
    expect(at(sim, 2038)).not.toEqual(at(capped, 2038));
  });
});

describe('how far a plant is taken is the training plan\'s to say', () => {
  const YEARS = 7;
  const HOLD = 3;
  const held = dome(taxa, YEARS, trainAll({ extent: { to: 'height', heightM: HOLD } }));
  const free = dome(taxa, YEARS);

  it('holds the whole framework below a height, on a structure that goes on above it', () => {
    for (const a of framework(held)) for (let i = 0; i < a.alive; i++) expect(a.contact[i]!.z, a.id).toBeLessThanOrEqual(HOLD + 1e-6);
    for (const s of held.summaries) expect(s.highestM, `${s.plantId} ${s.year}`).toBeLessThanOrEqual(HOLD + 1e-6);
    // the same plants, taken to the top, are well above it by then
    for (const s of free.summaries.filter((x) => x.year === 2033)) expect(s.highestM, s.plantId).toBeGreaterThan(HOLD + 2);
  });

  it('says of each stem it stopped that the gardener stopped it and that there was support ahead', () => {
    const stops = held.decisions.filter((d) => d.kind === 'stopped' && /the gardener holds this plant's framework below 3\.0 m/.test(d.text));
    expect(stops.length).toBeGreaterThanOrEqual(held.plants.size);
    for (const d of stops) expect(d.text).toMatch(/There was support ahead of it/);
    for (const plant of held.plants.values()) expect(leaders(held, plant.id).some((a) => a.tip.state === 'stopped' && /held below 3\.0 m by the gardener/.test(a.tip.reason)), plant.id).toBe(true);
  });

  it('fills what it is given below the hold: the framework goes on growing sideways', () => {
    const y3 = held.summaries.filter((s) => s.year === 2029).reduce((sum, s) => sum + s.frameworkM, 0);
    const y7 = held.summaries.filter((s) => s.year === 2033).reduce((sum, s) => sum + s.frameworkM, 0);
    expect(y7).toBeGreaterThan(y3 * 1.5);
  });

  it('lets a later visit take the plant higher: the stems stopped under the hold go on from where they stand', () => {
    const lift: GardenerEvent[] = [...held.plants.keys()].map((plantId) => ({ id: `lift-${plantId}`, date: '2031-03-01', type: 'train_leader', plantId, tieToTimber: true, train: { extent: { to: 'top_of_support' } }, author: 'gardener', reason: 'the room below is furnished: take it to the crown' }));
    const lifted = dome(taxa, YEARS + 4, (s) => ({ ...trainAll({ extent: { to: 'height', heightM: HOLD } })(s), events: [...s.events, ...lift] }));
    for (const s of lifted.summaries.filter((x) => x.year === 2030)) expect(s.highestM, s.plantId).toBeLessThanOrEqual(HOLD + 1e-6);
    for (const s of lifted.summaries.filter((x) => x.year === 2037)) expect(s.highestM, s.plantId).toBeGreaterThan(HOLD + 1.5);
    const records = lifted.events.filter((e) => e.eventId.startsWith('lift-'));
    expect(records.length).toBe(lifted.plants.size);
    for (const r of records) expect(r.outcome).toMatch(/taken as far as the support goes, and \d+ stems? that had been stopped lower go(es)? on/);
  });

  it('leads up the first main stem alone unless the plan says every one', () => {
    const all = dome(taxa, 4, trainAll({ stemsLedUp: 'all' }));
    const first = dome(taxa, 4);
    const led = (sim: Simulation, a: Axis) => sim.decisions.some((d) => d.axisId === a.id && /led by the gardener the shortest way up/.test(d.text));
    for (const plant of first.plants.values()) expect(leaders(first, plant.id).filter((a) => led(first, a)).length, plant.id).toBe(1);
    for (const plant of all.plants.values()) {
      const mine = leaders(all, plant.id);
      expect(mine.length, plant.id).toBeGreaterThan(1);
      expect(mine.filter((a) => led(all, a)).length, plant.id).toBe(mine.length);
    }
  });
});

describe('a main stem that a gardener leads up', () => {
  const sim = dome(taxa, 8);
  const { graph } = sim.scenario.bower;

  it('is taken the shortest way to the top: on the hemisphere, straight up its own meridian (CLAUDE.md: reach is computed on the support graph)', () => {
    for (const plant of sim.plants.values()) {
      const stem = leaders(sim, plant.id).find((a) => sim.decisions.some((d) => d.axisId === a.id && /led by the gardener/.test(d.text)))!;
      expect(stem, plant.id).toBeDefined();
      const arrived = stem.runs.findIndex((r) => graph.nodes.get(r.toNode)!.position.z > ARRIVED);
      expect(arrived, plant.id).toBeGreaterThan(3);
      const way = stem.runs.slice(0, arrived + 1);
      // every stretch of it a rib, and every one rising
      for (const r of way) {
        expect(graph.edges.get(r.edgeId)!.host.id, r.edgeId).toMatch(/^rib\./);
        expect(graph.nodes.get(r.toNode)!.position.z, r.edgeId).toBeGreaterThan(graph.nodes.get(r.fromNode)!.position.z);
      }
      // 11.78 m of meridian and no more
      expect(way.reduce((sum, r) => sum + graph.edges.get(r.edgeId)!.curve.length, 0)).toBeLessThan(11.9);
    }
  });

  it('is not led where nobody gardens: an untended plant finds its own way, as before', () => {
    const untended = new Simulation(wisteriaOnHemisphere({ taxa, care: 'untended', years: 4 })).runUntil(end(4));
    expect(untended.decisions.some((d) => /led by the gardener/.test(d.text))).toBe(false);
  });
});

describe('a result as a band, between the low and the high end of what is published for a year\'s growth', () => {
  const model = taxa.get(W)!.model;

  it('takes a model to the end of its range, laterals and long shoots with the leader, and says that it did', () => {
    const rate = model.params['extension.leaderMPerSeason'];
    expect(rate.range, 'Wisteria sinensis gives a range for a year\'s extension').toBeDefined();
    expect(rate.range![0]).toBeLessThanOrEqual(rate.value!);
    expect(rate.range![1]).toBeGreaterThanOrEqual(rate.value!);
    for (const which of ['low', 'high'] as const) {
      const at = which === 'low' ? 0 : 1;
      const varied = atBandEnd(model, which);
      const p = varied.params['extension.leaderMPerSeason'];
      expect(p.value).toBe(rate.range![at]);
      // the end of a sourced range is as well sourced as the range
      expect(p.status).toBe(rate.status);
      expect(p.source).toBe(rate.source);
      expect(p.basis).toMatch(new RegExp(`^Varied for this scenario .*the ${which} end of the range`));
      const ratio = rate.range![at] / rate.value!;
      if (ratio !== 1) {
        param(varied, 'extension.lateralMPerSeasonByOrder').forEach((v, i) => expect(v).toBeCloseTo(param(model, 'extension.lateralMPerSeasonByOrder')[i]! * ratio, 9));
        expect(param(varied, 'extension.whipMPerSeason')).toBeCloseTo(param(model, 'extension.whipMPerSeason') * ratio, 9);
      }
    }
    // the library's own model is untouched
    expect(taxa.get(W)!.model.params['extension.leaderMPerSeason'].value).toBe(rate.value);
  });

  it('leaves alone a model that gives no range: nothing says how far out it might be', () => {
    const plain = [...taxa.values()].find((t) => !hasBand(t.model))!;
    expect(plain).toBeDefined();
    expect(atBandEnd(plain.model, 'low')).toBe(plain.model);
    expect(atBandEnd(plain.model, 'high')).toBe(plain.model);
  });

  const YEARS = 10;
  const band = growthBand((t) => wisteriaOnHemisphere({ taxa: t, care: 'trained', years: YEARS }), taxa, end(YEARS));

  it('reports the year a plant comes to the top as a span of years, the high end first', () => {
    expect(band.topM).toBeCloseTo(CROWN, 6);
    for (const r of band.rows) {
      expect(r.hasBand, r.plantId).toBe(true);
      expect(r.heights.map((h) => h.yearsAfterPlanting)).toEqual([1, 3, 5, 10]);
      const y3 = r.heights.find((h) => h.yearsAfterPlanting === 3)!;
      expect(y3.low, r.plantId).toBeLessThan(y3.high);
      expect(y3.low, r.plantId).toBeLessThanOrEqual(y3.mid + 1e-9);
      expect(y3.mid, r.plantId).toBeLessThanOrEqual(y3.high + 1e-9);
      expect(r.topReached.high, r.plantId).not.toBeNull();
      if (r.topReached.low !== null) expect(r.topReached.high!, r.plantId).toBeLessThan(r.topReached.low);
    }
    const text = formatGrowthBand(band);
    expect(text).toContain('comes to the top');
    expect(text).toContain('comes to the top: high end / as modelled / low end');
    expect(text).toMatch(/year \d+ \/ year \d+ \/ (year \d+|not in this run)/);
  });

  it('labels a run made at one end, so that its own report says so', () => {
    const low = taxaAtBandEnd(taxa, 'low');
    const report = designReport(dome(low, 2), { viewpoints: [] });
    const varied = report.variations.filter((v) => v.taxonId === W).map((v) => v.parameter);
    expect(varied).toContain('extension.leaderMPerSeason');
    expect(formatDesignReport(report)).toMatch(/varied: wisteria-sinensis extension\.leaderMPerSeason = [\d.]+\. Varied for this scenario .*the low end of the range/);
  });
});

describe('the library at one end of its ranges, for a caller that cannot be given an option', () => {
  afterEach(() => {
    delete process.env.HORTI_GROWTH_BAND;
  });

  it('is loaded by option', () => {
    const low = loadGrowable(speciesDir, { band: 'low' });
    expect(low.get(W)!.model.params['extension.leaderMPerSeason'].value).toBe(taxa.get(W)!.model.params['extension.leaderMPerSeason'].range![0]);
  });

  it('or by HORTI_GROWTH_BAND, which an option overrides and a misspelling stops', () => {
    process.env.HORTI_GROWTH_BAND = 'high';
    expect(loadGrowable(speciesDir).get(W)!.model.params['extension.leaderMPerSeason'].value).toBe(taxa.get(W)!.model.params['extension.leaderMPerSeason'].range![1]);
    expect(loadGrowable(speciesDir, { band: null }).get(W)!.model.params['extension.leaderMPerSeason'].value).toBe(taxa.get(W)!.model.params['extension.leaderMPerSeason'].value);
    process.env.HORTI_GROWTH_BAND = 'hi';
    expect(() => loadGrowable(speciesDir)).toThrow(/HORTI_GROWTH_BAND is "hi"/);
  });
});

describe('a planting plan', () => {
  const bower = wisteriaOnHemisphere({ taxa, care: 'trained', years: 1 }).bower;
  const stationId = bower.rootStations[0]!.id;
  const plan = (train: unknown) => ({ schemaVersion: 1, name: 'One wisteria', plants: [{ plantId: 'w', taxonId: W, stationId, ...(train === undefined ? {} : { train }) }] });

  it('says how far each plant is taken, where the designer has decided', () => {
    const scenario = plantingOn(bower, parsePlantingPlan(plan({ extent: { to: 'height', heightM: 2.5 }, stemsLedUp: 'all' })), { taxa, years: 2 });
    expect(scenario.plantings[0]!.train).toEqual({ extent: { to: 'height', heightM: 2.5 }, stemsLedUp: 'all' });
    const sim = new Simulation(scenario).runUntil(end(2));
    expect(sim.plants.get('w')!.training).toMatchObject({ tieToTimber: true, extent: { to: 'height', heightM: 2.5 }, stemsLedUp: 'all' });
  });

  it('and leaves it to the top of the support where it says nothing', () => {
    const scenario = plantingOn(bower, parsePlantingPlan(plan(undefined)), { taxa, years: 1 });
    expect(scenario.plantings[0]!.train).toBeUndefined();
    const sim = new Simulation(scenario).runUntil(end(1));
    expect(sim.plants.get('w')!.training).toMatchObject(DEFAULT_TRAINING);
  });

  it('refuses a height with no number, and a word that is not in the vocabulary', () => {
    expect(() => parsePlantingPlan(plan({ extent: { to: 'height' } }))).toThrow(/not a valid planting plan/);
    expect(() => parsePlantingPlan(plan({ extent: { to: 'the_eaves' } }))).toThrow(/not a valid planting plan/);
    expect(() => parsePlantingPlan(plan({ stemsLedUp: 'some' }))).toThrow(/not a valid planting plan/);
  });
});

describe('which numbers move what a building is designed around', () => {
  it('sets out one run for each change, the run as modelled first, and names a model for every former cap', () => {
    expect(GROWTH_VARIATIONS[0]!.id).toBe('as_modelled');
    expect(new Set(GROWTH_VARIATIONS.map((v) => v.id)).size).toBe(GROWTH_VARIATIONS.length);
    for (const id of Object.keys(FORMER_STEM_CAPS_M)) expect(taxa.has(id), id).toBe(true);
    // every candidate of the brief of 14 November 2026 is among them
    const parameters = new Set(GROWTH_VARIATIONS.map((v) => v.parameter));
    for (const p of ['architecture.maxStemLengthM', 'extension.leaderMPerSeason', 'extension.establishmentFactorByYear', 'architecture.lateralLengthMByOrder', 'architecture.lateralChanceByParentOrder', 'architecture.maxStemsPerRoute', 'architecture.maxStemsPerPrimaryMember', 'attachment.maxGraspDiameterMm', 'mechanics.searcherReachM', 'attachment.graspReachM', 'training: which main stems are led up']) {
      expect(parameters.has(p), p).toBe(true);
    }
  });

  const YEARS = 7;
  const some = GROWTH_VARIATIONS.filter((v) => ['as_modelled', 'former_caps', 'extension.leaderMPerSeason_x0.5', 'extension.leaderMPerSeason_x1.5', 'attachment.graspReachM_x0.5', 'attachment.graspReachM_x1.5'].includes(v.id));
  const sweep = growthSensitivity((t) => wisteriaOnHemisphere({ taxa: t, care: 'trained', years: YEARS }), taxa, end(YEARS), some);
  const row = (id: string) => sweep.rows.find((r) => r.id === id)!;

  it('starts from the run as it is modelled', () => {
    const plain = dome(taxa, YEARS);
    expect(row('as_modelled').routeHeldShare).toBe(designReport(plain).routes.heldShare);
    expect(row('as_modelled').heights.filter((h) => h.yearsAfterPlanting === 5).map((h) => h.highestM)).toEqual(plain.summaries.filter((s) => s.year === 2031).map((s) => s.highestM));
  });

  it('shows the former cap holding the plants under the crown, and a slower leader arriving later', () => {
    expect(row('as_modelled').plantsAtTop).toBe(3);
    expect(row('former_caps').plantsAtTop).toBe(0);
    const y3 = (id: string) => row(id).meanHeightM.find((h) => h.yearsAfterPlanting === 3)!.value;
    expect(y3('extension.leaderMPerSeason_x0.5')).toBeLessThan(y3('as_modelled'));
    expect(y3('extension.leaderMPerSeason_x1.5')).toBeGreaterThan(y3('as_modelled'));
  });

  it('ranks the parameters by how far they move the readings, and how fast the leader grows comes before how near a shoot takes hold', () => {
    expect(sweep.ranking.map((r) => r.parameter).sort()).toEqual(['architecture.maxStemLengthM', 'attachment.graspReachM', 'extension.leaderMPerSeason'].sort());
    const rank = (p: string) => sweep.ranking.findIndex((r) => r.parameter === p);
    expect(rank('extension.leaderMPerSeason')).toBeLessThan(rank('attachment.graspReachM'));
    for (let i = 1; i < sweep.ranking.length; i++) expect(sweep.ranking[i]!.largest).toBeLessThanOrEqual(sweep.ranking[i - 1]!.largest);
    const text = formatGrowthSensitivity(sweep);
    expect(text).toContain('RANKING');
    expect(text).toContain('multiples, not estimates');
  });
});
