import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { loadGrowable } from '../src/node/load-taxa.ts';
import { Simulation } from '../src/sim/engine.ts';
import { FORMER_STEM_CAPS_M } from '../src/sim/growth-sensitivity.ts';
import { withParam } from '../src/sim/model.ts';
import { designReport, formatDesignReport } from '../src/sim/report.ts';
import { type Growable, wisteriaOnHemisphere } from '../src/sim/scenarios.ts';

const speciesDir = fileURLToPath(new URL('../../../species', import.meta.url));
const taxa = loadGrowable(speciesDir);
const END = '2038-12-31';
const grow = (t: Growable) => new Simulation(wisteriaOnHemisphere({ taxa: t, care: 'trained', years: 12 })).runUntil(END);

const sim = grow(taxa);
const report = designReport(sim);

// KEY.md section 4: "Height is not enough". DEVELOPMENT_GUIDE.md stage 5 exit check.
//
// Until 14 November 2026 these three never reached the crown, and the test said that route length had run out. What
// had run out was a planned length of 7 to 8.6 m that every main stem carried, which was the route of the Wisteria
// prototype's structure and no fact about the plant (docs/GROWTH_WITHOUT_STEM_CAPS.md). A main stem now goes on while
// it has support ahead and the gardener leads it; the last block of this file puts the old length back and finds the
// old result. What the clause asks still holds, and is what is tested here: the crown is 11.78 m of route away, not
// 7.5 m, so the plants are years longer getting there than their height in the early years would suggest.
describe('three wisterias on the 15 m hemisphere, twelve years on', () => {
  const firstAt = (plantId: string, heightM: number) => Math.min(...sim.summaries.filter((s) => s.plantId === plantId && s.highestM >= heightM).map((s) => s.year - 2026));

  it('have been led to the crown, 7.5 m up and 11.78 m of route away, and took years over it', () => {
    expect(report.structure.crownHeightM).toBeCloseTo(7.5, 6);
    for (const p of report.plants) {
      expect(p.highestM, p.plantId).toBeGreaterThan(7.5 * 0.985);
      expect(report.alerts.some((a) => a.kind === 'crown_not_reached' && a.plantId === p.plantId), p.plantId).toBe(false);
      // half the height in three years; the whole of it not in six, as height alone would have it, but later:
      // the dome flattens, and the last metres of height are the longest of route
      expect(firstAt(p.plantId, 3.75), p.plantId).toBeLessThanOrEqual(4);
      expect(firstAt(p.plantId, 7.5 * 0.985), p.plantId).toBeGreaterThan(2 * firstAt(p.plantId, 3.75) - 1);
      expect(firstAt(p.plantId, 7.5 * 0.985), p.plantId).toBeGreaterThanOrEqual(6);
      expect(firstAt(p.plantId, 7.5 * 0.985), p.plantId).toBeLessThanOrEqual(10);
    }
  });

  it('hold most of the routes by then, and still leave some bare', () => {
    expect(report.routes.heldShare).toBeGreaterThan(0.7);
    expect(report.routes.heldShare).toBeLessThan(0.97);
    expect(report.routes.freeM).toBeGreaterThan(15);
  });

  it('twine the glulam meridians and the cables unaided, and are tied along the timber rings', () => {
    const { graph } = sim.scenario.bower;
    const seen = { meridian: 0, ring: 0, cable: 0 };
    for (const a of sim.axes.values()) {
      for (const r of a.runs) {
        const edge = graph.edges.get(r.edgeId)!;
        if (edge.kind === 'cable') {
          expect(r.mode).toBe('twine');
          seen.cable++;
        } else if (edge.host.id.startsWith('rib.')) {
          expect(r.mode).toBe('twine');
          expect(r.by).toBe('plant');
          seen.meridian++;
        } else if (a.role !== 'leader' && a.role !== 'lateral') {
          // a shoot of the year that took hold of a ring from the air is not framework, and nobody ties it in:
          // it twines by itself (SIMULATION_KEY.md section 4.3, "Unsupported shoots")
          expect(r.mode).toBe('twine');
          expect(r.by).toBe('plant');
        } else {
          expect(r.mode).toBe('along');
          expect(r.by).not.toBe('plant');
          seen.ring++;
        }
      }
    }
    expect(seen.meridian).toBeGreaterThan(20);
    expect(seen.ring).toBeGreaterThan(5);
    expect(seen.cable).toBeGreaterThan(20);
  });

  it('show their progress at one, three, five and ten years', () => {
    for (const p of report.plants) {
      const mine = report.milestones.filter((m) => m.plantId === p.plantId);
      expect(mine.map((m) => m.yearsAfterPlanting)).toEqual([1, 3, 5, 10, 12]);
      for (let i = 1; i < mine.length; i++) expect(mine[i]!.frameworkM).toBeGreaterThanOrEqual(mine[i - 1]!.frameworkM);
      // a plant that will end at the crown is under 3 m after its first year: route takes time as well as length
      expect(mine[0]!.highestM).toBeLessThan(3);
      expect(mine[1]!.highestM).toBeLessThan(mine[4]!.highestM);
      expect(mine[0]!.flowersOpened).toBe(0);
      expect(mine[4]!.flowersOpened).toBeGreaterThan(100);
    }
    expect(formatDesignReport(report)).toContain('OVER THE YEARS');
  });

  it('leave the timber of the dome almost wholly legible from inside, even in leaf', () => {
    for (const m of report.months) expect(m.views.find((v) => v.viewpointId === 'inside')!.timberVisible).toBeGreaterThan(0.6);
  });
});

// PROJECT_CONTEXT.md section 10: unknowns are explored by varying them, in the open.
describe('asking what the planned length of a leader did, by putting it back', () => {
  const w = taxa.get('wisteria-sinensis')!;
  const former = [...FORMER_STEM_CAPS_M['wisteria-sinensis']!] as [number, number];
  const capped = withParam(w.model, 'architecture.maxStemLengthM', former, 'what did the planned length carried until 14 November 2026 do to this run?');
  const variedSim = grow(new Map([['wisteria-sinensis', { profile: w.profile, model: capped }]]));
  const varied = designReport(variedSim);

  it('stops every plant short of the crown, on a structure that goes on above it', () => {
    for (const p of varied.plants) {
      expect(p.highestM, p.plantId).toBeLessThan(7);
      expect(p.highestM, p.plantId).toBeGreaterThan(5);
      const alert = varied.alerts.find((a) => a.kind === 'crown_not_reached' && a.plantId === p.plantId);
      expect(alert, p.plantId).toBeDefined();
      // and the report says what ran out: a length given to the stems, not the support and not time
      expect(alert!.text).toContain('came to the length given for a stem of this plant, 7 to 8.6 m');
    }
    expect(varied.routes.heldShare).toBeLessThan(report.routes.heldShare);
  });

  it('says in the report that an assumption was varied, and why', () => {
    expect(varied.variations).toEqual([{ taxonId: 'wisteria-sinensis', parameter: 'architecture.maxStemLengthM', value: former, basis: expect.stringContaining('what did the planned length') }]);
    expect(report.variations).toEqual([]);
    expect(formatDesignReport(varied)).toContain('varied: wisteria-sinensis architecture.maxStemLengthM');
    expect(capped.params['architecture.maxStemLengthM'].status).toBe('provisional_design_assumption');
    expect(capped.params['architecture.maxStemLengthM'].basis).toContain('was null');
    // the library's own model is untouched: it gives no length
    expect(w.model.params['architecture.maxStemLengthM'].value).toBeNull();
  });
});
