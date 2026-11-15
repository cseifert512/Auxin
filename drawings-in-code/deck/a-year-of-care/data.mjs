// What "A year of care" is drawn from.
//   scenes/six-bay-meadow-v2/light/place-10y.growth: one grown run of the plant simulator (contract 2, gzipped JSON).
//     From it, the four climbers of pier R1.P1 and everything of theirs alive at any time in 2032: stem points,
//     leaves, flowers, the fruit the gardener took, each climber's 2032 season, and the simulated gardener's 2032
//     record for them (events[]). What is on a plant on a given day is decided on the page by the simulator's own
//     rules (presence.ts, as ported in bower-blender/studies/inhabited-room/grown.py); this only cuts the run down.
//   bower-blender/studies/inhabited-room/ground/openings.json, the opening marked is_the_design: the timber and
//     cables standing at R1.P1, and the soil level there.
// Everything is turned into one fixed orthographic elevation at gather time: u across (metres, to the right as you
// face the room's centre from outside the pier), z up, and depth (metres away from the eye), stored in millimetres.
// What was cut on a visit is what the run marks removed on that event's own day (removedDay === day).
// The sentences for the visits are written from each event's outcome text; a check below fails if a number in a
// sentence is not in that text.
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { gunzipSync } from 'node:zlib';

const RUN = 'scenes/six-bay-meadow-v2/light/place-10y.growth';
const PIER = 'R1.P1', PREFIX = 'P1.', YEAR = 2032;
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const NAMES = { 'P1.wisteria': 'wisteria', 'P1.rose': 'rose', 'P1.star-jasmine': 'star jasmine', 'P1.winter-clematis': 'winter clematis' };
// leaf kind and colours per species: grown.py LOOKS (the viewer's own colours, the rose's flower a stand-in from its bud)
const LOOKS = {
  'wisteria-sinensis': { leaf: 'pinnate', green: ['#588737', '#6a9742'], autumn: ['#e6c336', '#d0a02c'], flower: ['#d0bdf0', '#a285d6'], bloom: 'raceme' },
  'rosa-the-generous-gardener': { leaf: 'pinnate', green: ['#66803e', '#6c8a3a'], autumn: ['#66803e', '#8a7448'], flower: ['#f6d5da', '#f3a6b6'], bloom: 'head' },
  'trachelospermum-jasminoides': { leaf: 'simple', green: ['#27431f', '#365a29'], autumn: ['#5a3a22', '#7c2a22'], flower: ['#fbfbf3', '#eef0e2'], bloom: 'single' },
  'clematis-cirrhosa-freckles': { leaf: 'three', green: ['#1f3a1a', '#7f9468'], autumn: ['#1f3a1a', '#7f9468'], flower: ['#f8f2dc', '#c46a8e'], bloom: 'single' },
};
// One plain sentence per visit, from its outcome text. `needs`: words or numbers the outcome must contain.
const SAY = [
  { date: '2032-01-08', type: 'shorten_side_shoots', needs: ['30 flowered side shoots cut back'], say: 'January. The rose’s flowered side shoots are cut back.' },
  { date: '2032-01-20', type: 'spur_prune', needs: ['4 shoots cut back to two or three buds'], say: 'January. Wisteria shoots cut back to two or three buds.' },
  { date: '2032-03-25', type: 'trim_to_bounds', needs: ['9 free shoots standing out', 'from the timber cut off'], say: 'March. Winter clematis shoots standing out from the timber cut off.' },
  { date: '2032-04-15', type: 'trim_to_bounds', needs: ['1 free shoot standing out', 'from the timber cut off'], say: 'April. One star jasmine shoot standing out from the timber cut off.' },
  { date: '2032-05-15', type: 'monitor', needs: ['observed', '46 live flower buds'], say: 'May. The wisteria looked over: 46 flower buds.' },
  { date: '2032-06-28', type: 'deadhead_or_select_flowers', needs: ['nothing to take off', 'no spent flowers'], say: 'June. The rose looked over: no spent flowers to take off.' },
  { date: '2032-07-12', type: 'deadhead_or_select_flowers', needs: ['20 spent flowers taken off'], say: 'July. Twenty spent rose flowers taken off.' },
  { date: '2032-07-26', type: 'deadhead_or_select_flowers', needs: ['10 spent flowers taken off'], say: 'July. Ten spent rose flowers taken off.' },
  { date: '2032-08-01', type: 'spur_prune', needs: ['7 whippy shoots cut back to five or six leaves'], say: 'August. Wisteria’s whippy shoots cut back to five or six leaves.' },
  { date: '2032-08-09', type: 'deadhead_or_select_flowers', needs: ['nothing to take off', 'no spent flowers'], say: 'August. The rose looked over: no spent flowers to take off.' },
  { date: '2032-08-23', type: 'deadhead_or_select_flowers', needs: ['5 spent flowers taken off'], say: 'August. Five spent rose flowers taken off.' },
];

const mm = (v) => Math.round(v * 1000);
const dayOfDate = (start, date) => Math.round((Date.parse(`${date}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86400000);
const jitter = (x, y, z) => { const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453; return s - Math.floor(s); };   // grown.py / presence.ts

export default function gather(root) {
  const runFile = resolve(root, RUN), openFile = resolve(root, '../bower-blender/studies/inhabited-room/ground/openings.json');
  for (const f of [runFile, openFile]) if (!existsSync(f)) throw new Error(`${f} is not there`);
  const R = JSON.parse(gunzipSync(readFileSync(runFile)).toString());
  if (R.contract !== 2) throw new Error(`the run is contract ${R.contract}; this reads contract 2`);
  const O = JSON.parse(readFileSync(openFile, 'utf8'));
  const design = O.openings.find((o) => o.is_the_design);
  if (!design) throw new Error('openings.json has no opening marked is_the_design');

  const Y0 = dayOfDate(R.start, `${YEAR}-01-01`), Y1 = dayOfDate(R.start, `${YEAR + 1}-01-01`);   // the year: Y0 <= day < Y1
  const plants = R.plants.filter((p) => p.id.startsWith(PREFIX));
  if (plants.length !== 4) throw new Error(`expected four climbers at ${PIER}, found ${plants.length}`);
  const pi = Object.fromEntries(plants.map((p, i) => [p.id, i]));
  const mine = (id) => id in pi;

  // ---- the view: from outside the pier, looking at the room's centre ----
  const corners = design.feet[PIER].flatMap((f) => f.corners);
  const pier = [corners.reduce((s, c) => s + c[0], 0) / corners.length, corners.reduce((s, c) => s + c[1], 0) / corners.length];
  const L = Math.hypot(pier[0], pier[1]), f = [-pier[0] / L, -pier[1] / L], r = [f[1], -f[0]];
  const ground = design.levels_m[PIER];
  const view = (x, y, z) => [mm((x - pier[0]) * r[0] + (y - pier[1]) * r[1]), mm(z), mm((x - pier[0]) * f[0] + (y - pier[1]) * f[1])];

  // ---- stems: the points alive at some time in the year, which are one unbroken stretch of each stem ----
  const stems = [], byId = new Map(R.stems.map((s) => [s.id, s]));
  const P = (s, i) => [s.contact[3 * i], s.contact[3 * i + 1], s.contact[3 * i + 2]];
  const attach = (s) => {   // where a stem leaves its parent: the parent's nearest point, if it is close
    const parent = s.parentId && byId.get(s.parentId);
    if (!parent) return null;
    const p0 = P(s, 0); let best = Infinity, at = null;
    for (let i = 0; i < parent.bornDay.length; i++) { const q = P(parent, i), d = Math.hypot(q[0] - p0[0], q[1] - p0[1], q[2] - p0[2]); if (d < best) { best = d; at = q; } }
    return best > 0.3 ? null : at;
  };
  for (const s of R.stems) {
    if (!mine(s.plantId)) continue;
    const idx = [];
    for (let i = 0; i < s.bornDay.length; i++) if (s.bornDay[i] < Y1 && (s.removedDay[i] < 0 || s.removedDay[i] >= Y0)) idx.push(i);
    if (!idx.length) continue;
    if (idx.at(-1) - idx[0] + 1 !== idx.length) throw new Error(`stem ${s.id}: its points alive in ${YEAR} are not one stretch`);
    // where it leaves its parent, so the first stretch of a side shoot is drawn (the parent's nearest point)
    const from = idx[0] === 0 ? attach(s) : null;
    stems.push({
      p: pi[s.plantId],
      from: from ? view(...from) : null,
      pts: idx.flatMap((i) => view(...P(s, i))),
      born: idx.map((i) => s.bornDay[i] - Y0),
      gone: idx.map((i) => (s.removedDay[i] < 0 ? -1 : s.removedDay[i] - Y0)),
      rad: idx.map((i) => Math.round(s.radiusMm[i] * 10)),   // tenths of a millimetre, the radius at the end of the run
      first: idx[0],
    });
  }

  // ---- leaves, flowers: those that could be on the plant at some time in the year ----
  const leaves = [];
  for (const l of R.leaves) {
    if (!mine(l.plantId) || l.bornDay >= Y1 || (l.removedDay >= 0 && l.removedDay < Y0)) continue;
    if (l.firstYear > YEAR || (l.lastYear !== null && l.lastYear < YEAR - 1)) continue;
    const at = view(...l.position), tip = view(l.position[0] + l.direction[0], l.position[1] + l.direction[1], l.position[2] + l.direction[2]);
    const du = tip[0] - at[0], dz = tip[1] - at[1], dl = Math.hypot(du, dz) || 1;
    leaves.push([pi[l.plantId], at[0], at[1], at[2], Math.round(du / dl * 100), Math.round(dz / dl * 100), Math.round(dl / 10), mm(l.lengthM), l.firstYear, l.lastYear ?? 0, l.evergreen ? 1 : 0, l.bornDay - Y0, l.removedDay < 0 ? -1 : l.removedDay - Y0, Math.round(jitter(...l.position) * 1000)]);
  }
  const flowers = [];
  for (const fl of R.flowers) {
    if (!mine(fl.plantId) || fl.openDay >= Y1 || (fl.spentDay >= 0 && fl.spentDay < Y0)) continue;
    const at = view(...fl.position);
    flowers.push([pi[fl.plantId], at[0], at[1], at[2], mm(fl.lengthM), fl.openDay - Y0, fl.spentDay < 0 ? -1 : fl.spentDay - Y0, Math.round(jitter(...fl.position) * 1000)]);
  }

  // ---- seasons, rebased to the year ----
  const rebase = (v) => (Array.isArray(v) ? v.map((d) => d - Y0) : typeof v === 'number' ? v - Y0 : v);
  const seasons = plants.map((p) => {
    const s = R.seasons.find((x) => x.plantId === p.id && x.year === YEAR);
    if (!s) throw new Error(`no ${YEAR} season for ${p.id}`);
    const out = { year: s.year };
    for (const k of ['budburstDay', 'growthEndDay', 'leafFlush', 'autumnColour', 'leafFall', 'leafFallBefore', 'autumnColourBefore', 'leafFlushAfter']) if (s[k] != null) out[k] = rebase(s[k]);
    return out;
  });

  // ---- the visits, and what each took ----
  // metres of stem that went on this day: each stretch between two of a stem's points that ends at a point removed
  // that day. It leaves out the short stretch from a parent to a shoot taken whole, and counts a shortened shoot from
  // its last kept point. It comes within 0.4 m of each figure in the record but the rose's January cut (6.2 m here, 7.2 m there)
  const removedLength = (s, day) => {
    let m = 0;
    for (let i = 0; i < s.bornDay.length; i++) {
      if (s.removedDay[i] !== day) continue;
      if (i > 0) { const a = P(s, i - 1), b = P(s, i); m += Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]); }
    }
    return m;
  };
  const events = R.events.filter((e) => mine(e.plantId) && e.day >= Y0 && e.day < Y1).sort((a, b) => a.day - b.day);
  if (events.length !== SAY.length) throw new Error(`${events.length} visits at ${PIER} in ${YEAR}; the sentences are written for ${SAY.length}`);
  const check = [];
  const visits = events.map((e, k) => {
    const w = SAY[k];
    if (w.date !== e.date || w.type !== e.type) throw new Error(`visit ${k}: the run has ${e.date} ${e.type}, the sentence is for ${w.date} ${w.type}`);
    for (const n of w.needs) if (!e.outcome.includes(n)) throw new Error(`visit ${e.date}: "${n}" is not in its outcome: ${e.outcome}`);
    const near = {};   // what this plant lost a few days either side, to see that the record and the removals agree
    for (let d = -3; d <= 3; d++) {
      let pts = 0, lv = 0, fr = 0;
      for (const s of R.stems) if (s.plantId === e.plantId) for (const g of s.removedDay) if (g === e.day + d) pts++;
      for (const l of R.leaves) if (l.plantId === e.plantId && l.removedDay === e.day + d) lv++;
      for (const x of R.fruits) if (x.plantId === e.plantId && x.removedDay === e.day + d) fr++;
      if (pts || lv || fr) near[d] = { points: pts, leaves: lv, fruits: fr };
    }
    let metres = 0, points = 0;
    for (const s of R.stems) if (s.plantId === e.plantId) { metres += removedLength(s, e.day); for (const g of s.removedDay) if (g === e.day) points++; }
    const fruits = R.fruits.filter((x) => x.plantId === e.plantId && x.removedDay === e.day).map((x) => { const at = view(...x.position); return [at[0], at[1], at[2], mm(x.lengthM)]; });
    const lv = R.leaves.filter((l) => l.plantId === e.plantId && l.removedDay === e.day).length;
    check.push({ date: e.date, plant: e.plantId, type: e.type, points, leaves: lv, fruits: fruits.length, metres: Math.round(metres * 100) / 100, near, outcome: e.outcome });
    return { day: e.day - Y0, date: e.date, p: pi[e.plantId], type: e.type, say: w.say, metres: Math.round(metres * 100) / 100, fruits, cuts: points + lv + fruits.length > 0 };
  });

  // ---- what the plants are doing, for the sentence between visits: one per half month, from the seasons and flowers ----
  const name = (i) => NAMES[plants[i].id];
  const and = (xs) => (xs.length < 2 ? xs[0] : `${xs.slice(0, -1).join(', ')} and ${xs.at(-1)}`);
  const cap = (s) => s[0].toUpperCase() + s.slice(1);
  const shed = [];   // side shoots a plant sheds at budburst (not a cut: engine.ts, 'shed'): days with removals and no visit
  for (const [i, p] of plants.entries()) {
    const days = new Map();
    for (const s of R.stems) if (s.plantId === p.id) for (const g of s.removedDay) if (g >= Y0 && g < Y1 && !events.some((e) => e.plantId === p.id && e.day === g)) days.set(g, (days.get(g) ?? 0) + 1);
    for (const [d, n] of days) if (n >= 10) shed.push({ p: i, day: d - Y0, points: n, budburst: d - Y0 === seasons[i].budburstDay });
  }
  const daysIn = (m) => [dayOfDate(R.start, `${YEAR}-${String(m + 1).padStart(2, '0')}-01`) - Y0, m === 11 ? Y1 - Y0 : dayOfDate(R.start, `${YEAR}-${String(m + 2).padStart(2, '0')}-01`) - Y0];
  const slots = [];
  for (let m = 0; m < 12; m++) {
    const [a, b] = daysIn(m), mid = a + 15;
    for (const [s0, s1] of [[a, mid], [mid, b]]) {
      const touches = (lo, hi) => lo < s1 && hi >= s0;
      const open = plants.map((_, i) => flowers.filter((x) => x[0] === i && x[5] < s1 && (x[6] < 0 || x[6] > s0)).length);
      const inFlower = plants.map((_, i) => i).filter((i) => open[i] >= 3);
      const sheds = shed.filter((x) => x.day >= s0 && x.day < s1);
      const bursting = plants.map((_, i) => i).filter((i) => seasons[i].budburstDay >= s0 && seasons[i].budburstDay < s1);
      const deciduous = plants.map((_, i) => i).filter((i) => plants[i].leafHabit === 'deciduous');
      const falling = deciduous.filter((i) => touches(seasons[i].leafFall[0], seasons[i].leafFall[1]));
      const turning = deciduous.filter((i) => touches(seasons[i].autumnColour[0], seasons[i].autumnColour[1]) && !falling.includes(i));
      const flushing = plants.map((_, i) => i).filter((i) => touches(seasons[i].leafFlush[0], seasons[i].leafFlush[1]));
      const growing = plants.map((_, i) => i).filter((i) => s0 >= seasons[i].budburstDay && s0 < seasons[i].growthEndDay);
      const bare = deciduous.every((i) => s1 <= seasons[i].leafFlush[0] || s0 >= seasons[i].leafFall[1]);
      let t;
      const shedAtBurst = sheds.length === 1 && sheds[0].budburst;
      if (shedAtBurst) t = `The ${name(sheds[0].p)} breaks bud and sheds old flowering shoots.`;
      else if (sheds.length) t = `The ${and(sheds.map((x) => name(x.p)))} ${sheds.length > 1 ? 'shed' : 'sheds'} side shoots that have lived out their time.`;
      else if (bursting.length) t = `The ${and(bursting.map(name))} ${bursting.length > 1 ? 'are' : 'is'} breaking bud.`;
      else if (falling.length) t = `The ${and(falling.map(name))} ${falling.length > 1 ? 'are' : 'is'} losing ${falling.length > 1 ? 'their' : 'its'} leaves.`;
      else if (turning.length) t = `The ${and(turning.map(name))} ${turning.length > 1 ? 'turn' : 'turns'} to autumn colour.`;
      else if (inFlower.length) t = `The ${and(inFlower.map(name))} ${inFlower.length > 1 ? 'are' : 'is'} in flower.`;
      else if (flushing.length) t = `The ${and(flushing.map(name))} ${flushing.length > 1 ? 'are' : 'is'} coming into leaf.`;
      else if (growing.length) t = 'The climbers are growing.';
      else if (bare) t = 'Bare stems, and the evergreens in leaf.';
      else t = 'The climbers rest.';
      slots.push({ from: s0, say: `${MONTHS[m]}. ${cap(t)}` });
    }
  }

  // ---- the timber at this pier: the members standing on its feet, and whatever else the climbers grow on ----
  const alivePts = [];
  for (const s of stems) for (let i = 0; i < s.born.length; i++) alivePts.push([s.pts[3 * i] / 1000, s.pts[3 * i + 1] / 1000, s.pts[3 * i + 2] / 1000]);
  const onFeet = new Set(design.feet[PIER].map((x) => x.member));
  const touched = (pts) => { const vp = pts.map((p) => view(...p).map((v) => v / 1000)); let n = 0; for (const q of alivePts) { for (let i = 1; i < vp.length; i++) { const a = vp[i - 1], b = vp[i], ab = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], l2 = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2 || 1, t = Math.max(0, Math.min(1, ((q[0] - a[0]) * ab[0] + (q[1] - a[1]) * ab[1] + (q[2] - a[2]) * ab[2]) / l2)); if (Math.hypot(a[0] + ab[0] * t - q[0], a[1] + ab[1] * t - q[1], a[2] + ab[2] * t - q[2]) < 0.12) { n++; break; } } if (n >= 6) return true; } return false; };
  const members = design.members.filter((m) => onFeet.has(m.id) || touched(m.pts)).map((m) => ({ id: m.id, w: mm(m.w), pts: m.pts.flatMap((p) => view(...p)) }));
  const cables = design.cables.filter((c) => touched(c)).map((c) => c.flatMap((p) => view(...p)));

  // ---- the frame: the height the climbers reach this year ----
  const zs = alivePts.map((q) => q[1]).sort((a, b) => a - b), us = alivePts.map((q) => q[0]).sort((a, b) => a - b);
  const top = zs.at(-1), q = (a, k) => a[Math.floor(k * (a.length - 1))];

  return {
    run: RUN, start: R.start, year: YEAR, pier: PIER, yearDays: Y1 - Y0, lastDay: R.lastDay - Y0,
    thickening: R.thickening,
    statement: R.statement,
    plants: plants.map((p) => ({ id: p.id, name: NAMES[p.id], label: p.label, taxon: p.taxonId, habit: p.leafHabit, look: LOOKS[p.taxonId] })),
    seasons, stems, leaves, flowers, visits, slots, shed, members, cables,
    ground: mm(ground),
    frame: { top: mm(top), u: [mm(q(us, 0.01)), mm(q(us, 0.99))], z98: mm(q(zs, 0.98)) },
    check,
  };
}
