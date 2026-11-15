// What "Opening the pier" is drawn from: the same pier and the same four climbers, grown twice, side by side.
//   Right, legs apart (the design): scenes/six-bay-meadow-v2/light/place-10y.growth, one grown run of the plant
//     simulator (contract 2, gzipped JSON), and in bower-blender/studies/inhabited-room/ground/openings.json the
//     opening marked is_the_design (ring radius 1.2 m) for the timber, cables and soil level at R1.P1.
//   Left, legs together: scenes/trial-meadow-pier-034/light/place-10y.growth, the run on the tightest opening (ring
//     radius 0.34 m), and that opening in openings.json. Until that light copy exists the left side is gathered from
//     the design run and marked `placeholder`, and the page says so across the left picture; gathering again once
//     the file is there clears it.
// From each run: the four climbers of pier R1.P1 and everything of theirs alive at any time in the ten years (stem
// points, leaves, flowers) and every season. What is on a plant on a day is decided on the page by the simulator's
// own rules (presence.ts, as ported in bower-blender/studies/inhabited-room/grown.py); this only cuts the run down.
// One run is read at a time and let go before the next: the laptop is short of memory.
// Each side is turned into the same fixed orthographic elevation as "A year of care": u across (to the right as you
// face the room's centre from outside the pier, about that side's own ring of feet), z up, depth away from the eye;
// millimetres. Days are the run's own (day 0 is its start, 2027-03-01).
// The study strip's figures are given by the study (one run and one seed per opening), written in below as they were
// handed over; the feet in plan are each opening's own, from openings.json.
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { gunzipSync } from 'node:zlib';

const PIER = 'R1.P1', PREFIX = 'P1.';
const SIDES = [
  { id: 'together', title: 'Legs together', ring: 0.34, run: 'scenes/trial-meadow-pier-034/light/place-10y.growth', inLight: 2 },
  { id: 'apart', title: 'Legs apart', ring: 1.2, run: 'scenes/six-bay-meadow-v2/light/place-10y.growth', inLight: 4 },
];
const DESIGN_RUN = SIDES[1].run;
const IDS = ['P1.wisteria', 'P1.rose', 'P1.star-jasmine', 'P1.winter-clematis'];
// the six openings, as the study gives them: climbers of 24 getting the light their species asks for, the way in
// between the piers, and whether the footing draft's rules are met (with the word pair for those that are not)
const STUDY = [
  { ring: 0.34, light: 12, wayIn: 4.92, ok: false, why: 'piles too close' },
  { ring: 0.6, light: 13, wayIn: 4.83, ok: false, why: 'piles too close' },
  { ring: 0.8, light: 13, wayIn: 4.41, ok: false, why: 'piles too close' },
  { ring: 1.0, light: 18, wayIn: 4.0, ok: true },
  { ring: 1.2, light: 19, wayIn: 3.6, ok: true },
  { ring: 1.4, light: 21, wayIn: 3.19, ok: false, why: 'foot too far from its pile' },
];
// leaf kind and colours per species: grown.py LOOKS (the viewer's own colours, the rose's flower a stand-in from its bud)
const LOOKS = {
  'wisteria-sinensis': { leaf: 'pinnate', green: ['#588737', '#6a9742'], autumn: ['#e6c336', '#d0a02c'], flower: ['#d0bdf0', '#a285d6'], bloom: 'raceme' },
  'rosa-the-generous-gardener': { leaf: 'pinnate', green: ['#66803e', '#6c8a3a'], autumn: ['#66803e', '#8a7448'], flower: ['#f6d5da', '#f3a6b6'], bloom: 'head' },
  'trachelospermum-jasminoides': { leaf: 'simple', green: ['#27431f', '#365a29'], autumn: ['#5a3a22', '#7c2a22'], flower: ['#fbfbf3', '#eef0e2'], bloom: 'single' },
  'clematis-cirrhosa-freckles': { leaf: 'three', green: ['#1f3a1a', '#7f9468'], autumn: ['#1f3a1a', '#7f9468'], flower: ['#f8f2dc', '#c46a8e'], bloom: 'single' },
};
const BUDGET = 3.4e6;   // bytes of data.js, about; over it, leaves are thinned evenly, the same on both sides

const mm = (v) => Math.round(v * 1000);
const dayOfDate = (start, date) => Math.round((Date.parse(`${date}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86400000);
const jitter = (x, y, z) => { const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453; return s - Math.floor(s); };   // grown.py / presence.ts

/** One side: one run read, cut down to the pier, turned into the elevation, and let go. */
function side(root, spec, opening, runFile) {
  let R = JSON.parse(gunzipSync(readFileSync(runFile)).toString());
  if (R.contract !== 2) throw new Error(`${runFile} is contract ${R.contract}; this reads contract 2`);
  const plants = IDS.map((id) => R.plants.find((p) => p.id === id));
  if (plants.some((p) => !p)) throw new Error(`${runFile}: not all of ${IDS.join(', ')} are in the run`);
  const pi = Object.fromEntries(plants.map((p, i) => [p.id, i]));
  const mine = (id) => id in pi;

  // the view: from outside the pier, looking at the room's centre, about this opening's own ring of feet
  const corners = opening.feet[PIER].flatMap((f) => f.corners);
  const pier = [corners.reduce((s, c) => s + c[0], 0) / corners.length, corners.reduce((s, c) => s + c[1], 0) / corners.length];
  const L = Math.hypot(pier[0], pier[1]), f = [-pier[0] / L, -pier[1] / L], r = [f[1], -f[0]];
  const ground = opening.levels_m[PIER];
  const view = (x, y, z) => [mm((x - pier[0]) * r[0] + (y - pier[1]) * r[1]), mm(z), mm((x - pier[0]) * f[0] + (y - pier[1]) * f[1])];

  // stems: every point of every stem of these climbers (all are alive at some time in the ten years)
  const stems = [], byId = new Map(R.stems.map((s) => [s.id, s]));
  const P = (s, i) => [s.contact[3 * i], s.contact[3 * i + 1], s.contact[3 * i + 2]];
  const attach = (s) => {   // where a stem leaves its parent: the parent's nearest point, if it is close
    const parent = s.parentId && byId.get(s.parentId);
    if (!parent) return null;
    const p0 = P(s, 0); let best = Infinity, at = null;
    for (let i = 0; i < parent.bornDay.length; i++) { const q = P(parent, i), d = Math.hypot(q[0] - p0[0], q[1] - p0[1], q[2] - p0[2]); if (d < best) { best = d; at = q; } }
    return best > 0.3 ? null : at;
  };
  const reach = [];   // [born day, height above the soil] of every stem point, for "reached so far"
  for (const s of R.stems) {
    if (!mine(s.plantId) || !s.bornDay.length) continue;
    const n = s.bornDay.length, from = attach(s);
    stems.push({
      p: pi[s.plantId],
      from: from ? view(...from) : null,
      pts: Array.from({ length: n }, (_, i) => view(...P(s, i))).flat(),
      born: s.bornDay.slice(),
      gone: s.removedDay.slice(),
      rad: s.radiusMm.map((v) => Math.round(v * 10)),   // tenths of a millimetre, the radius at the end of the run
    });
    for (let i = 0; i < n; i++) reach.push([s.bornDay[i], s.contact[3 * i + 2] - ground]);
  }
  // the highest any of the four has reached by each day: a step wherever it rises (in centimetres)
  reach.sort((a, b) => a[0] - b[0]);
  const reached = [];
  let top = -Infinity;
  for (const [d, z] of reach) if (z > top + 0.005) { top = z; if (reached.length && reached.at(-1)[0] === d) reached.at(-1)[1] = Math.round(z * 100); else reached.push([d, Math.round(z * 100)]); }

  // leaves and flowers: all of these climbers' (each is on the plant at some time in the run)
  const leaves = [];
  for (const l of R.leaves) {
    if (!mine(l.plantId)) continue;
    const at = view(...l.position), tip = view(l.position[0] + l.direction[0], l.position[1] + l.direction[1], l.position[2] + l.direction[2]);
    const du = tip[0] - at[0], dz = tip[1] - at[1], dl = Math.hypot(du, dz) || 1;
    leaves.push([pi[l.plantId], at[0], at[1], Math.round(at[2] / 10), Math.round(du / dl * 100), Math.round(dz / dl * 100), Math.round(dl / 10), mm(l.lengthM), l.firstYear - 2027, l.lastYear == null ? -1 : l.lastYear - 2027, l.evergreen ? 1 : 0, l.bornDay, l.removedDay, Math.round(jitter(...l.position) * 1000)]);
  }
  leaves.sort((a, b) => a[11] - b[11]);
  const flowers = [];
  for (const fl of R.flowers) {
    if (!mine(fl.plantId)) continue;
    const at = view(...fl.position);
    flowers.push([pi[fl.plantId], at[0], at[1], Math.round(at[2] / 10), mm(fl.lengthM), fl.openDay, fl.spentDay, Math.round(jitter(...fl.position) * 1000)]);
  }
  flowers.sort((a, b) => a[5] - b[5]);

  // seasons: per climber, per calendar year, in the run's days
  const seasons = plants.map((p) => {
    const out = {};
    for (const s of R.seasons.filter((x) => x.plantId === p.id)) {
      const o = { year: s.year };
      for (const k of ['budburstDay', 'growthEndDay', 'leafFlush', 'autumnColour', 'leafFall', 'leafFallBefore', 'autumnColourBefore', 'leafFlushAfter']) if (s[k] != null) o[k] = s[k];
      out[s.year] = o;
    }
    return out;
  });

  // the timber at this pier: the members standing on its feet, and whatever else the climbers grow on
  const alivePts = [];
  for (const s of stems) for (let i = 0; i < s.born.length; i++) alivePts.push([s.pts[3 * i] / 1000, s.pts[3 * i + 1] / 1000, s.pts[3 * i + 2] / 1000]);
  const onFeet = new Set(opening.feet[PIER].map((x) => x.member));
  const touched = (pts) => { const vp = pts.map((p) => view(...p).map((v) => v / 1000)); let n = 0; for (const q of alivePts) { for (let i = 1; i < vp.length; i++) { const a = vp[i - 1], b = vp[i], ab = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], l2 = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2 || 1, t = Math.max(0, Math.min(1, ((q[0] - a[0]) * ab[0] + (q[1] - a[1]) * ab[1] + (q[2] - a[2]) * ab[2]) / l2)); if (Math.hypot(a[0] + ab[0] * t - q[0], a[1] + ab[1] * t - q[1], a[2] + ab[2] * t - q[2]) < 0.12) { n++; break; } } if (n >= 6) return true; } return false; };
  const members = opening.members.filter((m) => onFeet.has(m.id) || touched(m.pts)).map((m) => ({ id: m.id, w: mm(m.w), pts: m.pts.flatMap((p) => view(...p)) }));
  const cables = opening.cables.filter((c) => touched(c)).map((c) => c.flatMap((p) => view(...p)));

  const zs = alivePts.map((q) => q[1]).sort((a, b) => a - b), us = alivePts.map((q) => q[0]).sort((a, b) => a - b);
  const qq = (a, k) => a[Math.floor(k * (a.length - 1))];
  const totalStem = (() => { let m = 0; for (const s of R.stems) for (let i = 1; i < s.bornDay.length; i++) { const a = P(s, i - 1), b = P(s, i); m += Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]); } return Math.round(m); })();
  const out = {
    id: spec.id, title: spec.title, ring: opening.ring_radius_m, inLight: spec.inLight,
    run: runFile === resolve(root, spec.run) ? spec.run : DESIGN_RUN, placeholder: runFile !== resolve(root, spec.run),
    start: R.start, lastDay: R.lastDay, thickening: R.thickening, statement: R.statement,
    plants: plants.map((p) => ({ id: p.id, label: p.label, taxon: p.taxonId, habit: p.leafHabit, look: LOOKS[p.taxonId] })),
    seasons, stems, leaves, flowers, reached, members, cables,
    ground: mm(ground),
    frame: { top: mm(zs.at(-1)), u: [mm(qq(us, 0.01)), mm(qq(us, 0.99))], z98: mm(qq(zs, 0.98)) },
    totalStemRoomM: totalStem,   // every stem point to point, the whole room, at the end of the run (for the note)
  };
  R = null;   // let the run go before the next is read
  return out;
}

export default function gather(root) {
  const openFile = resolve(root, '../bower-blender/studies/inhabited-room/ground/openings.json');
  if (!existsSync(openFile)) throw new Error(`${openFile} is not there`);
  const O = JSON.parse(readFileSync(openFile, 'utf8'));
  const sides = SIDES.map((spec) => {
    const opening = O.openings.find((o) => Math.abs(o.ring_radius_m - spec.ring) < 1e-6);
    if (!opening) throw new Error(`openings.json has no opening of ring radius ${spec.ring} m`);
    if (spec.id === 'apart' && !opening.is_the_design) throw new Error('the 1.2 m opening is no longer the design');
    let runFile = resolve(root, spec.run);
    if (!existsSync(runFile)) {
      if (spec.id === 'apart') throw new Error(`${runFile} is not there`);
      console.warn(`  ${spec.run} is not there yet: the left side is gathered from the design run, marked as a placeholder`);
      runFile = resolve(root, DESIGN_RUN);
    }
    const s = side(root, spec, opening, runFile);
    global.gc?.();
    return s;
  });
  if (sides[0].start !== sides[1].start) throw new Error('the two runs do not start on the same day');

  // the study: each opening's feet at this pier in plan, about its own ring, turned as the elevations are
  const study = STUDY.map((x) => {
    const o = O.openings.find((q) => Math.abs(q.ring_radius_m - x.ring) < 1e-6);
    if (!o) throw new Error(`openings.json has no opening of ring radius ${x.ring} m`);
    const c = o.feet[PIER].flatMap((ft) => ft.corners), cx = c.reduce((s, q) => s + q[0], 0) / c.length, cy = c.reduce((s, q) => s + q[1], 0) / c.length;
    const L = Math.hypot(cx, cy), f = [-cx / L, -cy / L], r = [f[1], -f[0]];
    const feet = o.feet[PIER].map((ft) => { const q = ft.corners.map(([x0, y0]) => [mm((x0 - cx) * r[0] + (y0 - cy) * r[1]), mm((x0 - cx) * f[0] + (y0 - cy) * f[1])]); return [q[0], q[1], q[3], q[2]].flat(); });   // corners round the quad
    return { ...x, design: !!o.is_the_design, across: Math.round(x.ring * 2 * 10) / 10, feet };
  });

  // thin the leaves evenly if data.js would be too large: every k-th by a fixed hash, the same rule on both sides
  const size = () => JSON.stringify({ sides, study }).length;
  let kept = 1;
  const full = size();
  if (full > BUDGET) {
    const leafBytes = sides.reduce((s, x) => s + JSON.stringify(x.leaves).length, 0);
    kept = Math.max(0.2, 1 - (full - BUDGET) / leafBytes);
    // every leaf whose place in the born-day order crosses a whole step of `kept`: evenly through time and over the
    // plant, and not by the jitter, which also sets when a leaf falls
    for (const s of sides) s.leaves = s.leaves.filter((_, i) => Math.floor((i + 1) * kept) > Math.floor(i * kept));
  }
  const yearStart = Object.fromEntries(Array.from({ length: 12 }, (_, k) => [2027 + k, dayOfDate(sides[1].start, `${2027 + k}-01-01`)]));
  console.log(`  data: ${(size() / 1e6).toFixed(2)} MB (${(full / 1e6).toFixed(2)} MB before thinning; leaves kept ${(kept * 100).toFixed(0)}%), leaves ${sides.map((s) => s.leaves.length).join(' / ')}, top ${sides.map((s) => s.frame.top).join(' / ')} mm`);
  return { pier: PIER, start: sides[1].start, yearStart, planted: Math.min(...sides.flatMap((s) => s.stems.map((x) => x.born[0]))), kept, sides, study };
}
