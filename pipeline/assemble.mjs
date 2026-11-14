// The order the timber can go together in, read from the joint schedule.
//   node pipeline/assemble.mjs [snapshot]
// Reads  releases/<snapshot>/joints.csv, centrelines.json and design.json
// Writes scenes/<snapshot>/assembly.json
//
// Three kinds of joint say that one member has to be in place before another:
//   cross lap   the member notched on its outer face lies under the one notched on its inner face, so it goes in first
//   housing     a member whose end is shouldered into another needs that other standing to receive it
//   crown seat  the top ring is housed on its underside over the level ends of the ribs, so it is lowered on last
// Everything else (feet on the ground, mitres between arches, scarfs within one member, ribs meeting head to
// head) fixes no order. Among members that are free to go in, the order is a choice made here to read clearly:
// by family from the heaviest to the lightest, and round the room from the first pier.
//
// This is the order the joints allow, not a method statement: lifting, propping and scaffold are not worked out.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const snapshot = process.argv[2] ?? 'six-bay-v1';
const from = resolve(root, 'releases', snapshot);
const to = resolve(root, 'scenes', snapshot);

const centrelines = JSON.parse(readFileSync(resolve(from, 'centrelines.json'), 'utf8'));
const design = JSON.parse(readFileSync(resolve(from, 'design.json'), 'utf8'));

function readCsv(file) {
  const [head, ...lines] = readFileSync(file, 'utf8').split(/\r?\n/).filter((l) => l.length);
  const cells = (line) => {
    const out = [];
    let cell = '';
    let quoted = false;
    for (const ch of line) {
      if (ch === '"') quoted = !quoted;
      else if (ch === ',' && !quoted) {
        out.push(cell);
        cell = '';
      } else cell += ch;
    }
    out.push(cell);
    return out;
  };
  const keys = cells(head);
  return lines.map((l) => Object.fromEntries(cells(l).map((v, i) => [keys[i], v])));
}
const joints = readCsv(resolve(from, 'joints.csv'));

/** Heaviest first; the ring that caps the ribs comes out last by the joints themselves. */
const FAMILY_ORDER = ['arch', 'hoop', 'ring', 'rib', 'fill', 'fine', 'crown'];
/** How far out a member starts from where it ends up, in metres: a little further for a longer one. */
const startAway = (lengthM) => Math.min(2.6, 1.3 + 0.1 * lengthM);
/** A centre line is drawn from one point in this many of the snapshot's. */
const LINE_EVERY = 3;

const [cx, cy] = design.rooms[0].crown.centre_m;
const firstPier = design.rooms[0].piers[0].position_m;
const turnFrom = Math.atan2(firstPier[1] - cy, firstPier[0] - cx);
const round = (v, places = 3) => Number(v.toFixed(places));

const members = new Map(
  centrelines.members.map((m) => {
    const mid = m.points_m[Math.floor(m.points_m.length / 2)];
    // round the room from the first pier, anticlockwise seen from above
    const turn = (Math.atan2(mid[1] - cy, mid[0] - cx) - turnFrom + 4 * Math.PI) % (2 * Math.PI);
    // out from the room and up: the side every later member is brought on from, since each lies over the ones before it
    const out = [0, 1, 2].map((k) => m.depth_axes.reduce((sum, a) => sum + a[k], 0) / m.depth_axes.length);
    const outward = [mid[0] - cx, mid[1] - cy, mid[2] - 1];
    if (out[0] * outward[0] + out[1] * outward[1] + out[2] * outward[2] < 0) for (let k = 0; k < 3; k++) out[k] = -out[k];
    const way = m.family === 'arch' ? [0, 0, 1] : [out[0], out[1], out[2] + 0.6];
    const l = Math.hypot(...way) || 1;
    const away = startAway(m.length_m);
    const stage = FAMILY_ORDER.indexOf(m.family);
    return [
      m.id,
      {
        id: m.id,
        family: m.family,
        lengthM: round(m.length_m),
        key: [stage < 0 ? FAMILY_ORDER.length : stage, m.id.includes('.ccw.') ? 1 : 0, turn],
        from: way.map((c) => round((c / l) * away)),
        line: m.points_m.filter((_, i) => i % LINE_EVERY === 0 || i === m.points_m.length - 1).map((p) => p.map((c) => round(c))),
        after: new Set(),
      },
    ];
  }),
);

for (const j of joints) {
  const a = members.get(j.member_a);
  const b = members.get(j.member_b);
  if (!a || !b || a === b) continue;
  if (j.kind === 'cross_lap') (j.a_face === 'outer' ? b : a).after.add((j.a_face === 'outer' ? a : b).id);
  else if (j.kind === 'housing') a.after.add(b.id);
  else if (j.kind === 'crown_seat') b.after.add(a.id);
}

// each time, the member that is free to go in and comes first by family and by place round the room
const before = (p, q) => {
  for (let k = 0; k < p.key.length; k++) if (p.key[k] !== q.key[k]) return p.key[k] - q.key[k];
  return p.id < q.id ? -1 : 1;
};
const order = [];
const placed = new Set();
const waiting = new Set(members.values());
let forced = 0;
while (waiting.size) {
  let next = null;
  for (const m of waiting) if ([...m.after].every((id) => placed.has(id)) && (!next || before(m, next) < 0)) next = m;
  if (!next) {
    // the joints ask for a circle: put in the one with fewest still to wait for, and say so
    for (const m of waiting) {
      const owing = [...m.after].filter((id) => !placed.has(id)).length;
      if (!next || owing < next.owing) next = Object.assign(m, { owing });
    }
    forced++;
  }
  waiting.delete(next);
  placed.add(next.id);
  order.push(next);
}

// a joint is made when the last member it joins is in
const index = new Map(order.map((m, i) => [m.id, i]));
const madeAfter = new Array(order.length).fill(0);
for (const j of joints) {
  const at = Math.max(index.get(j.member_a) ?? -1, index.get(j.member_b) ?? -1);
  if (at >= 0) madeAfter[at]++;
}
for (let i = 1; i < madeAfter.length; i++) madeAfter[i] += madeAfter[i - 1];

const assembly = {
  schema: 'drawings.assembly/1',
  snapshot,
  frame: 'x east, y north, z up, metres',
  note: 'The order the joints allow: a member lapped under another goes in first, and a member housed into another waits for it. Lifting, propping and scaffold are not worked out or drawn.',
  joints: joints.length,
  members: order.map((m, i) => ({ id: m.id, family: m.family, lengthM: m.lengthM, after: [...m.after].sort(), jointsMade: madeAfter[i], from: m.from, line: m.line })),
};
mkdirSync(to, { recursive: true });
writeFileSync(resolve(to, 'assembly.json'), `${JSON.stringify(assembly)}\n`);

const runs = [];
for (const m of order) {
  const last = runs[runs.length - 1];
  if (last && last.family === m.family) last.n++;
  else runs.push({ family: m.family, n: 1 });
}
const broken = order.filter((m, i) => [...m.after].some((id) => index.get(id) > i)).length;
console.log(`${snapshot}: ${order.length} members in order, from ${joints.length} joints that fix ${order.reduce((n, m) => n + m.after.size, 0)} "this before that"`);
console.log(`  ${runs.map((r) => `${r.n} ${r.family}`).join(', ')}`);
console.log(`  members that had to go in before something they wait for: ${broken}${forced ? ` (the joints ask for a circle ${forced} times)` : ''}`);
console.log(`  first ${order.slice(0, 4).map((m) => m.id).join(', ')}; last ${order.slice(-3).map((m) => m.id).join(', ')}`);
console.log(`written: ${resolve(to, 'assembly.json')}`);
