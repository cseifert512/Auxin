// Drop stem points that add nothing at the scale of a building.
//
// The simulator records a shoot that hangs free every few millimetres, which
// is right for a portrait of one plant and far more than a drawing of a whole
// room can show: most of the points in a run are of this kind. Supported
// stems, which wind round the timber, are left exactly as they are. Along an
// unsupported stretch a point is kept when it stands at least `spacingM` from
// the last one kept, and at every place where something changes: where support
// begins or ends, and where a cut was made.

const dist = (a, i, j) => Math.hypot(a[3 * i] - a[3 * j], a[3 * i + 1] - a[3 * j + 1], a[3 * i + 2] - a[3 * j + 2]);

/** Mutates `growth` (the simulator's render data). Returns what was done, for the run's record. */
export function thin(growth, spacingM = 0.025) {
  /** Per stem: the new index of each old point. */
  const moved = new Map();
  let before = 0;
  let after = 0;
  for (const stem of growth.stems) {
    const n = stem.bornDay.length;
    before += n;
    const supported = (i) => Math.abs(stem.away[3 * i]) + Math.abs(stem.away[3 * i + 1]) + Math.abs(stem.away[3 * i + 2]) > 1e-6;
    const keep = [];
    const to = new Int32Array(n);
    let last = 0;
    for (let i = 0; i < n; i++) {
      const end = i === 0 || i === n - 1;
      const change = !end && (supported(i) !== supported(i - 1) || supported(i) !== supported(i + 1) || stem.removedDay[i] !== stem.removedDay[i - 1] || stem.removedDay[i] !== stem.removedDay[i + 1]);
      if (end || change || supported(i) || dist(stem.contact, i, last) >= spacingM) {
        last = i;
        keep.push(i);
      }
      to[i] = keep.length - 1;
    }
    after += keep.length;
    moved.set(stem.id, to);
    if (keep.length === n) continue;
    const triples = (arr) => keep.flatMap((i) => [arr[3 * i], arr[3 * i + 1], arr[3 * i + 2]]);
    stem.contact = triples(stem.contact);
    stem.away = triples(stem.away);
    stem.bornDay = keep.map((i) => stem.bornDay[i]);
    stem.removedDay = keep.map((i) => stem.removedDay[i]);
    stem.radiusMm = keep.map((i) => stem.radiusMm[i]);
  }
  for (const organ of [...growth.leaves, ...growth.flowers, ...(growth.fruits ?? []), ...(growth.appendages ?? [])]) {
    if (organ.stemPoint === undefined) continue;
    const to = moved.get(organ.stemId);
    if (to && organ.stemPoint >= 0 && organ.stemPoint < to.length) organ.stemPoint = to[organ.stemPoint];
  }
  return { summary: `${before} stem points recorded, ${after} kept: unsupported shoots thinned to one point every ${Math.round(spacingM * 1000)} mm` };
}
