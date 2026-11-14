// Which of the building's milled joints the planting reaches by clinging, and when, for the joints vignette.
//   node sketches/design-space/joints.mjs six-bay-radial-v1 trained-10y-new-growth trained-10y-new-growth-seed8 trained-10y-new-growth-seed9
// The runs are of one scene and one planting and differ only in seed. The first is the one drawn.
// Reads   scenes/<snapshot>/bower.json and runs/<run>/report.json (and growth.json of the first run)
//         ../releases/<snapshot>/joints.csv and centrelines.json
// Writes  sketches/design-space/reached-joints.js
//
// The simulator names the places where members meet (j188) and reports the ones a clinging plant has reached
// unaided. Each is matched here to the rows of the snapshot's joint schedule that are milled at that place,
// so that the list a run gives is a list of joints the mill cuts.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..', '..');
const horti = resolve(process.env.HORTI_DIR ?? resolve(root, '../Horti-code-ture'));
const [snapshot, ...runs] = process.argv.slice(2);
if (!snapshot || !runs.length) throw new Error('usage: joints.mjs <snapshot> <run to draw> [more runs of the same planting ...]');

const AT_NODE_M = 0.3;      // a milled joint this near a named place, between members that meet there, is at it
const ARRIVED_M = 0.15;     // a stem point this near the place has reached it
const CLOSE_M = 0.75;       // how much of each member is drawn either side of the joint drawn close to
const NEAR_M = 1.0;         // stems this near that joint are drawn with it
const LATTICE = ['rib', 'fill', 'fine', 'hoop'];
const read = (file) => JSON.parse(readFileSync(file, 'utf8'));
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const mm = (p) => p.map((v) => Math.round(v * 1000));

const { readBower } = await import(pathToFileURL(resolve(horti, 'packages/core/src/bower/description.ts')).href);
const bowerFile = resolve(root, 'scenes', snapshot, 'bower.json');
const graph = readBower(read(bowerFile), bowerFile).bower.graph;
const placeOf = (node) => { const p = graph.nodes.get(node)?.position; return p ? [p.x, p.y, p.z] : null; };
const membersAt = (node) => [...new Set((graph.adjacency.get(node) ?? []).map((edge) => edge.replace(/:\d+$/, '')))].filter((id) => member.has(id));   // timber members only, not the lines

const from = resolve(root, '..', 'releases', snapshot);
const [head, ...rows] = readFileSync(resolve(from, 'joints.csv'), 'utf8').trim().split(/\r?\n/).map((line) => line.split(','));
const schedule = rows.map((cells) => Object.fromEntries(head.map((name, i) => [name, cells[i]])));
const centrelines = read(resolve(from, 'centrelines.json'));
const member = new Map(centrelines.members.map((m) => [m.id, m]));

// The rows of the joint schedule that are milled at a named place.
function milledAt(node) {
  const place = placeOf(node), meeting = new Set(membersAt(node));
  const near = schedule.map((row) => ({ row, d: dist(place, [+row.x_m, +row.y_m, +row.z_m]) })).filter((x) => x.d <= AT_NODE_M);
  const between = near.filter((x) => meeting.has(x.row.member_a) && meeting.has(x.row.member_b));
  return (between.length ? between : near.sort((a, b) => a.d - b.d).slice(0, 1)).map((x) => x.row);
}

const out = { snapshot, joints: schedule.length, kinds: {}, runs: [], places: {} };
for (const row of schedule) out.kinds[row.kind] = (out.kinds[row.kind] ?? 0) + 1;
let drawn = null;
for (const [index, run] of runs.entries()) {
  const dir = resolve(root, 'scenes', snapshot, 'runs', run);
  const report = read(resolve(dir, 'report.json')), setup = read(resolve(dir, 'run.json'));
  const reached = new Map();   // place -> the plants that reached it
  for (const plant of report.jointsReached) for (const node of plant.nodeIds) reached.set(node, [...(reached.get(node) ?? []), plant.plantId]);
  for (const node of reached.keys()) {
    out.places[node] ??= { at: mm(placeOf(node)), members: membersAt(node), milled: milledAt(node).map((row) => ({ id: row.id, kind: row.kind, a: row.member_a, b: row.member_b, aDepthMm: Math.round(+row.a_depth_m * 1000) || null, bDepthMm: Math.round(+row.b_depth_m * 1000) || null })) };
  }
  const entry = { run, seed: setup.seed, simulator: setup.simulator?.commit?.slice(0, 7) ?? null, care: setup.care, years: setup.years, specimenM: setup.specimenM, reached: [...reached].map(([node, plants]) => ({ node, plants })) };
  if (index === 0) {   // the run that is drawn: when each place was reached, from the stems themselves
    const growth = read(resolve(dir, 'growth.json'));
    const byPlant = new Map();
    for (const stem of growth.stems) byPlant.set(stem.plantId, [...(byPlant.get(stem.plantId) ?? []), stem]);
    for (const item of entry.reached) {
      const place = placeOf(item.node);
      let day = Infinity;
      for (const plantId of item.plants) for (const stem of byPlant.get(plantId) ?? []) {
        for (let i = 0; i < stem.bornDay.length; i++) {
          if (stem.bornDay[i] < day && dist(place, [stem.contact[i * 3], stem.contact[i * 3 + 1], stem.contact[i * 3 + 2]]) <= ARRIVED_M) day = stem.bornDay[i];
        }
      }
      item.day = Number.isFinite(day) ? day : null;
    }
    entry.lastDay = growth.lastDay; entry.statement = growth.statement;
    entry.labels = Object.fromEntries(growth.plants.map((p) => [p.id, p.label]));
    drawn = { growth, entry };
  }
  out.runs.push(entry);
  console.log(`${run} (seed ${entry.seed}): ${entry.reached.length} places reached by ${report.jointsReached.map((p) => p.plantId).join(', ')}`);
}
const every = Object.keys(out.places).filter((node) => out.runs.every((r) => r.reached.some((x) => x.node === node)));
out.always = every;
out.sometimes = Object.keys(out.places).filter((node) => !every.includes(node));
out.milledAlways = new Set(every.flatMap((node) => out.places[node].milled.map((j) => j.id))).size;
out.milledEver = new Set(Object.values(out.places).flatMap((p) => p.milled.map((j) => j.id))).size;

// One joint drawn close to: the first reached in the drawn run that every run reaches, lapped between two lattice members.
const lapped = (node) => out.places[node].milled.find((j) => j.kind === 'cross_lap' && LATTICE.includes(member.get(j.a)?.family) && LATTICE.includes(member.get(j.b)?.family));
const pick = drawn.entry.reached.filter((x) => x.day != null && lapped(x.node)).sort((a, b) => (every.includes(b.node) - every.includes(a.node)) || a.day - b.day)[0];
if (pick) {
  const joint = lapped(pick.node), row = schedule.find((r) => r.id === joint.id), at = [+row.x_m, +row.y_m, +row.z_m];
  const piece = (id) => {
    const m = member.get(id);
    let nearest = 0;
    m.points_m.forEach((p, i) => { if (dist(p, at) < dist(m.points_m[nearest], at)) nearest = i; });
    const frames = [];
    m.points_m.forEach((p, i) => { if (dist(p, m.points_m[nearest]) <= CLOSE_M) frames.push({ p: mm(p), d: m.depth_axes[i].map((v) => Math.round(v * 1000) / 1000) }); });
    return { id, family: m.family, widthM: m.width_m, depthM: m.depth_m, frames };
  };
  const stems = [];
  const plantIndex = new Map(drawn.growth.plants.map((p, i) => [p.id, i]));
  for (const stem of drawn.growth.stems) {
    const points = [], born = [], gone = [];
    for (let i = 0; i < stem.bornDay.length; i++) {
      const p = [stem.contact[i * 3], stem.contact[i * 3 + 1], stem.contact[i * 3 + 2]];
      if (dist(p, at) > NEAR_M) { if (points.length > 3) stems.push({ plant: plantIndex.get(stem.plantId), mm: points.splice(0), born: born.splice(0), gone: gone.splice(0) }); else { points.length = born.length = gone.length = 0; } continue; }
      points.push(...mm(p)); born.push(stem.bornDay[i]); gone.push(stem.removedDay[i]);
    }
    if (points.length > 3) stems.push({ plant: plantIndex.get(stem.plantId), mm: points, born, gone });
  }
  out.close = { node: pick.node, day: pick.day, plants: pick.plants, joint, at: mm(at), angleDeg: +row.angle_deg, a: piece(joint.a), b: piece(joint.b), stems };
  console.log(`drawn close to: ${joint.id} at ${pick.node}, reached on day ${pick.day} by ${pick.plants.join(', ')}; ${stems.length} stretches of stem near it`);
}
console.log(`${Object.keys(out.places).length} places in all: ${every.length} reached in every run, ${out.sometimes.length} in some. Milled joints at them: ${out.milledAlways} always, ${out.milledEver} ever, of ${schedule.length}.`);
const file = resolve(here, 'reached-joints.js');
writeFileSync(file, `window.REACHED = ${JSON.stringify(out)};\n`);
console.log(`wrote ${file} (${Math.round(Buffer.byteLength(JSON.stringify(out)) / 1024)} KB)`);
