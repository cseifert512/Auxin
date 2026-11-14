// A lighter copy of a run, for the drawing that is drawn live.
//   node pipeline/lighten.mjs [snapshot] [run]
// Reads  scenes/<snapshot>/runs/<run>/growth.json     (every stem, leaf and flower with its days)
// Writes scenes/<snapshot>/light/<run>.growth       (the same record, lighter, and packed: gzip of its JSON)
//
// The whole record is what pictures are made from beforehand, where a frame may take as long as it takes. Drawn
// live, on a laptop, most of it cannot be seen and all of it has to be drawn: on this building, eight and a half
// million triangles a frame. What goes, in the order of what it saves:
//
//   points along a stem   A stem is recorded every few centimetres. A point is kept only where the stem bends: where
//                         leaving it out would move the line by more than `bendMm`, or leave a stretch longer than
//                         `stretchM` with nothing on it, and wherever something changes (support begins or ends, a cut).
//   twigs                 A stem thinner than `twigMm` and shorter than `twigM` that carries no other stem is a
//                         hair's breadth at the scale of a room. Its leaves stay where they were.
//   what it holds on by   Prickles, aerial roots, tendrils: millimetres long, and tens of thousands of them.
//   leaves in a crowd     Where one plant carries more than `crowd` leaves in a year, some are left out, never more
//                         than the share `leastKept` leaves, and those that stay are drawn a little larger, so the
//                         plant covers nearly what it did. A young plant keeps every leaf.
//
// Nothing is moved and no day is changed: what is drawn grows when and where the simulator said. This is a drawing
// decision, not a finding, and the whole record stays beside it.
import { mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const options = Object.fromEntries(process.argv.slice(2).filter((a) => a.startsWith('--')).map((a) => a.slice(2).split('=')));
const [snapshot = JSON.parse(readFileSync(new URL('../snapshot.json', import.meta.url), 'utf8')).snapshot, run = 'trained-10y'] = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const o = { bendMm: 10, stretchM: 0.5, twigMm: 3, twigM: 0.35, crowd: 2500, leastKept: 0.45, ...Object.fromEntries(Object.entries(options).map(([k, v]) => [k, Number(v)])) };

const from = resolve(root, 'scenes', snapshot, 'runs', run, 'growth.json');
const growth = JSON.parse(readFileSync(from, 'utf8'));
const was = { stems: growth.stems.length, points: growth.stems.reduce((n, s) => n + s.bornDay.length, 0), leaves: growth.leaves.length, appendages: growth.appendages?.length ?? 0, bytes: statSync(from).size };

// ---- twigs ---------------------------------------------------------------------------------------------------------
const at = (c, i) => [c[3 * i], c[3 * i + 1], c[3 * i + 2]];
const gap = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const lengthOf = (s) => {
  let d = 0;
  for (let i = 1; i < s.bornDay.length; i++) d += gap(at(s.contact, i), at(s.contact, i - 1));
  return d;
};
const bearing = new Set(growth.stems.map((s) => s.parentId).filter(Boolean));
growth.stems = growth.stems.filter((s) => bearing.has(s.id) || Math.max(...s.radiusMm) >= o.twigMm || lengthOf(s) >= o.twigM);

// ---- points along a stem ---------------------------------------------------------------------------------------------
/** How far `p` stands from the straight line from `a` to `b`. */
function off(p, a, b) {
  const ab = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
  const ap = [p[0] - a[0], p[1] - a[1], p[2] - a[2]];
  const l2 = ab[0] * ab[0] + ab[1] * ab[1] + ab[2] * ab[2];
  const t = l2 > 0 ? Math.min(1, Math.max(0, (ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / l2)) : 0;
  return Math.hypot(ap[0] - t * ab[0], ap[1] - t * ab[1], ap[2] - t * ab[2]);
}
const moved = new Map();
for (const stem of growth.stems) {
  const n = stem.bornDay.length;
  const supported = (i) => Math.abs(stem.away[3 * i]) + Math.abs(stem.away[3 * i + 1]) + Math.abs(stem.away[3 * i + 2]) > 1e-6;
  const keep = [0];
  const to = new Int32Array(n);
  let last = 0;
  for (let i = 1; i < n; i++) {
    let needed = i === n - 1;
    if (!needed) needed = supported(i) !== supported(i - 1) || supported(i) !== supported(i + 1) || stem.removedDay[i] !== stem.removedDay[i - 1] || stem.removedDay[i] !== stem.removedDay[i + 1];
    if (!needed) {
      // without this point the stem would run straight from the last one kept to the next: is that still the stem?
      const a = at(stem.contact, last);
      const b = at(stem.contact, i + 1);
      needed = gap(a, b) > o.stretchM;
      for (let k = last + 1; k <= i && !needed; k++) needed = off(at(stem.contact, k), a, b) > o.bendMm / 1000;
    }
    if (needed) {
      keep.push(i);
      last = i;
    }
    to[i] = keep.length - 1;
  }
  moved.set(stem.id, to);
  if (keep.length === n) continue;
  const triples = (arr) => keep.flatMap((i) => [arr[3 * i], arr[3 * i + 1], arr[3 * i + 2]]);
  stem.contact = triples(stem.contact);
  stem.away = triples(stem.away);
  stem.bornDay = keep.map((i) => stem.bornDay[i]);
  stem.removedDay = keep.map((i) => stem.removedDay[i]);
  stem.radiusMm = keep.map((i) => stem.radiusMm[i]);
}

// ---- what it holds on by, and leaves in a crowd ------------------------------------------------------------------------
growth.appendages = [];
/** A number from 0 to 1 that is the same for the same leaf every time. */
const chance = (n) => {
  let h = (n + 0x9e3779b9) | 0;
  h = Math.imul(h ^ (h >>> 16), 0x85ebca6b);
  h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
};
// how many leaves each plant carries at midsummer of each year (a leaf's place is kept from year to year)
const crowds = new Map();
const firstMidsummer = Math.round((Date.parse(`${growth.start.slice(0, 4)}-07-10T00:00:00Z`) - Date.parse(`${growth.start}T00:00:00Z`)) / 86_400_000);
for (const leaf of growth.leaves) {
  let years = crowds.get(leaf.plantId);
  if (!years) crowds.set(leaf.plantId, (years = new Map()));
  for (let day = firstMidsummer; day <= growth.lastDay; day += 365.25) {
    if (leaf.bornDay <= day && (leaf.removedDay < 0 || leaf.removedDay > day)) years.set(day, (years.get(day) ?? 0) + 1);
  }
}
const kept = new Map([...crowds].map(([plant, years]) => [plant, Math.min(1, Math.max(o.leastKept, o.crowd / Math.max(1, ...years.values())))]));
growth.leaves = growth.leaves.filter((leaf, n) => {
  const share = kept.get(leaf.plantId) ?? 1;
  if (chance(n) >= share) return false;
  // fewer leaves, each a little larger: most of the cover the plant had, not all of it
  leaf.lengthM *= share ** -0.4;
  return true;
});

const present = new Set(growth.stems.map((s) => s.id));
for (const organ of [...growth.leaves, ...growth.flowers, ...(growth.fruits ?? [])]) {
  if (organ.stemPoint === undefined || !present.has(organ.stemId)) continue;
  const to = moved.get(organ.stemId);
  if (to && organ.stemPoint >= 0 && organ.stemPoint < to.length) organ.stemPoint = to[organ.stemPoint];
}

const out = resolve(root, 'scenes', snapshot, 'light', `${run}.growth`);
mkdirSync(dirname(out), { recursive: true });
// a millimetre is finer than anything here is drawn
const written = JSON.stringify(growth, (_, v) => (typeof v === 'number' && !Number.isInteger(v) ? Math.round(v * 1e3) / 1e3 : v));
writeFileSync(out, gzipSync(written, { level: 9 }));
const now = { stems: growth.stems.length, points: growth.stems.reduce((n, s) => n + s.bornDay.length, 0), leaves: growth.leaves.length, bytes: statSync(out).size };
const thinned = [...kept].filter(([, share]) => share < 1);
console.log(`${snapshot} ${run}: for drawing live`);
console.log(`  stems            ${was.stems} -> ${now.stems}   (twigs under ${o.twigMm} mm thick and ${o.twigM} m long left out)`);
console.log(`  points on them   ${was.points} -> ${now.points}   (kept where a stem bends by more than ${o.bendMm} mm, and every ${o.stretchM} m at least)`);
console.log(`  leaves           ${was.leaves} -> ${now.leaves}   (${thinned.length} of ${kept.size} plants carry more than ${o.crowd} at a midsummer: ${thinned.map(([p, s]) => `${p} ${Math.round(s * 100)}%`).join(', ') || 'none'})`);
console.log(`  holdfasts        ${was.appendages} -> 0`);
console.log(`  file             ${(was.bytes / 1e6).toFixed(0)} MB -> ${(written.length / 1e6).toFixed(0)} MB, ${(now.bytes / 1e6).toFixed(1)} MB packed`);
console.log(`written: ${out}`);
