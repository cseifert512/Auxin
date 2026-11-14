// Seat a grown planting on the timber faces that are really there.
//
// The simulator reads a member as a centre line and a section, with nothing to
// say which way the section is turned, and works out a frame of its own for
// each stretch (sim/stem-path.ts `frames`). The snapshot records the true
// direction of the depth at every sample. Where the two differ, a stem wound
// round the member in the simulator's frame cuts through the real timber or
// stands off it.
//
// Here every supported stem point keeps its direction out from the member's
// centre line and is moved along that direction on to the outline of the real
// section: the simulator's own rounded outline through the section's corners,
// turned the way the timber is. What grows on a stem point moves with it.
// Lengths, routes and dates are untouched: this moves geometry by centimetres.
//
// Unsupported stretches of stem (a shoot hanging free, the lead from a bed to
// the first timber) keep their shape, and so their relation to gravity; they
// are shifted to stay joined to the supported points beside them.

const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const mul = (a, k) => [a[0] * k, a[1] * k, a[2] * k];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const len = (a) => Math.hypot(a[0], a[1], a[2]);
const unit = (a) => {
  const l = len(a);
  return l > 1e-12 ? mul(a, 1 / l) : [0, 0, 0];
};
const reject = (v, t) => sub(v, mul(t, dot(v, t)));
const lerp = (a, b, u) => [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u];
/** `v` turned by the smallest turn that takes unit vector `from` to unit vector `to`. */
function carry(v, from, to) {
  const axis = cross(from, to);
  const s = len(axis);
  const c = dot(from, to);
  if (s < 1e-9) return v;
  const k = mul(axis, 1 / s);
  return add(add(mul(v, c), mul(cross(k, v), s)), mul(k, dot(k, v) * (1 - c)));
}

const CELL = 0.5;
/** The simulator's rounded outline through the corners of a section (stem-path.ts `outline`): a superellipse of power 5. */
const POWER = 5;
const SWELL = 2 ** (1 / POWER);
/** How far off the outline's range a contact point may be and still be taken to lie on a member, in metres. */
const SLACK = 0.015;

function segmentsOf(centrelines) {
  const segments = [];
  centrelines.members.forEach((m, member) => {
    for (let i = 0; i + 1 < m.points_m.length; i++) {
      const a = m.points_m[i];
      const ab = sub(m.points_m[i + 1], a);
      const l = len(ab);
      if (l < 1e-9) continue;
      segments.push({ member, a, ab, l, t: mul(ab, 1 / l), axis0: m.depth_axes[i], axis1: m.depth_axes[i + 1], halfW: m.width_m / 2, halfD: m.depth_m / 2 });
    }
  });
  return segments;
}

function gridOf(segments) {
  const grid = new Map();
  const key = (x, y, z) => `${x},${y},${z}`;
  segments.forEach((s, index) => {
    const b = add(s.a, s.ab);
    const reach = Math.hypot(s.halfW, s.halfD) + 0.05;
    const lo = [0, 1, 2].map((k) => Math.floor((Math.min(s.a[k], b[k]) - reach) / CELL));
    const hi = [0, 1, 2].map((k) => Math.floor((Math.max(s.a[k], b[k]) + reach) / CELL));
    for (let x = lo[0]; x <= hi[0]; x++) for (let y = lo[1]; y <= hi[1]; y++) for (let z = lo[2]; z <= hi[2]; z++) {
      const k = key(x, y, z);
      if (!grid.has(k)) grid.set(k, []);
      grid.get(k).push(index);
    }
  });
  return (p) => grid.get(key(Math.floor(p[0] / CELL), Math.floor(p[1] / CELL), Math.floor(p[2] / CELL))) ?? [];
}

/**
 * The member a contact point lies on. A point on a member's outline stands off its centre line by between half
 * its width and half its diagonal, and its "away" direction points out from that centre line. Where two members
 * cross, both may pass: the one the stem was already on is kept, so that a stem changes member once at a joint.
 */
function seatOf(p, away, segments, near, last) {
  const byMember = new Map();
  for (const index of near(p)) {
    const s = segments[index];
    const along = dot(sub(p, s.a), s.t);
    if (along < -0.02 || along > s.l + 0.02) continue;
    const u = Math.min(1, Math.max(0, along / s.l));
    const c = add(s.a, mul(s.ab, u));
    const r = reject(sub(p, c), s.t);
    const d = len(r);
    if (d < s.halfW * SWELL - SLACK || d > Math.hypot(s.halfW, s.halfD) + SLACK) continue;
    const facing = dot(away, mul(r, 1 / d));
    if (facing < 0.3) continue;
    const had = byMember.get(s.member);
    if (!had || facing > had.facing) byMember.set(s.member, { s, u, c, r, facing });
  }
  if (!byMember.size) return null;
  let best = byMember.get(last);
  if (!best) for (const found of byMember.values()) if (!best || found.facing > best.facing) best = found;
  const { s, u, c, r } = best;
  const deep = unit(reject(lerp(s.axis0, s.axis1, u), s.t));
  const wide = cross(deep, s.t);
  const x = dot(r, wide);
  const y = dot(r, deep);
  // outside the real section by this much (negative: inside the timber) as the simulator left it
  const ox = Math.abs(x) - s.halfW;
  const oy = Math.abs(y) - s.halfD;
  const clear = ox > 0 || oy > 0 ? Math.hypot(Math.max(ox, 0), Math.max(oy, 0)) : Math.max(ox, oy);
  // the same direction out from the centre line, on the outline as it really lies
  const phi = Math.atan2(y, x);
  const a = s.halfW * SWELL;
  const b = s.halfD * SWELL;
  const cp = Math.cos(phi);
  const sp = Math.sin(phi);
  const rho = (Math.abs(cp / a) ** POWER + Math.abs(sp / b) ** POWER) ** (-1 / POWER);
  const qx = rho * cp;
  const qy = rho * sp;
  const nx = (Math.sign(qx) * Math.abs(qx / a) ** (POWER - 1)) / a;
  const ny = (Math.sign(qy) * Math.abs(qy / b) ** (POWER - 1)) / b;
  return {
    member: s.member,
    clear,
    contact: add(c, add(mul(wide, qx), mul(deep, qy))),
    away: unit(add(mul(wide, nx), mul(deep, ny))),
  };
}

/** Mutates `growth` (the simulator's render data). Returns what was done, for the run's record. */
export function reseat(growth, centrelines) {
  const segments = segmentsOf(centrelines);
  const near = gridOf(segments);
  const stems = new Map(growth.stems.map((s) => [s.id, s]));
  /** Per stem, per point: where it was, how far it moved, and the turn its "away" took (supported points only). */
  const done = new Map();
  const count = { supported: 0, unseated: 0, buried: 0, moved: 0, furthest: 0 };

  const at = (arr, i) => [arr[3 * i], arr[3 * i + 1], arr[3 * i + 2]];
  const put = (arr, i, v) => {
    arr[3 * i] = v[0];
    arr[3 * i + 1] = v[1];
    arr[3 * i + 2] = v[2];
  };

  function seatStem(stem) {
    if (done.has(stem.id)) return done.get(stem.id);
    const n = stem.bornDay.length;
    const was = Array.from({ length: n }, (_, i) => at(stem.contact, i));
    const shifts = new Array(n).fill(null);
    const turns = new Array(n).fill(null);
    const record = { was, shifts, turns };
    done.set(stem.id, record); // set first: a malformed loop of parents must not recurse for ever
    let last = -1;
    for (let i = 0; i < n; i++) {
      const away = at(stem.away, i);
      if (len(away) < 1e-6) continue;
      count.supported++;
      const seat = seatOf(was[i], away, segments, near, last);
      if (!seat) {
        count.unseated++;
        continue;
      }
      last = seat.member;
      if (seat.clear < -0.01) count.buried++;
      const shift = sub(seat.contact, was[i]);
      const far = len(shift);
      if (far > 0.005) count.moved++;
      count.furthest = Math.max(count.furthest, far);
      put(stem.contact, i, seat.contact);
      put(stem.away, i, seat.away);
      shifts[i] = shift;
      turns[i] = { from: away, to: seat.away };
    }
    // everything else keeps its shape and follows the seated points at either end
    const parent = stem.parentId ? stems.get(stem.parentId) : null;
    let base = [0, 0, 0];
    if (parent && shifts[0] === null) {
      const from = seatStem(parent);
      let nearest = -1;
      let dMin = Infinity;
      for (let j = 0; j < from.was.length; j++) {
        const d = len(sub(from.was[j], was[0]));
        if (d < dMin) {
          dMin = d;
          nearest = j;
        }
      }
      if (nearest >= 0 && dMin < 0.25) base = from.shifts[nearest];
    }
    for (let i = 0; i < n; ) {
      if (shifts[i] !== null) {
        i++;
        continue;
      }
      let j = i;
      while (j < n && shifts[j] === null) j++;
      const left = i > 0 ? shifts[i - 1] : base;
      const right = j < n ? shifts[j] : left;
      for (let k = i; k < j; k++) {
        shifts[k] = lerp(left, right, (k - i + 1) / (j - i + 1));
        put(stem.contact, k, add(was[k], shifts[k]));
      }
      i = j;
    }
    return record;
  }
  for (const stem of growth.stems) seatStem(stem);

  // what grows on a stem goes with the point it stands on
  for (const organ of [...growth.leaves, ...growth.flowers, ...(growth.fruits ?? []), ...(growth.appendages ?? [])]) {
    const record = done.get(organ.stemId);
    if (!record) continue;
    const { was, shifts, turns } = record;
    let i = organ.stemPoint;
    if (i === undefined || i < 0 || i >= was.length) {
      let dMin = Infinity;
      for (let j = 0; j < was.length; j++) {
        const d = len(sub(was[j], organ.position));
        if (d < dMin) {
          dMin = d;
          i = j;
        }
      }
    }
    const turn = turns[i];
    if (turn) {
      organ.position = add(add(was[i], shifts[i]), carry(sub(organ.position, was[i]), turn.from, turn.to));
      if (organ.direction) organ.direction = carry(organ.direction, turn.from, turn.to);
    } else {
      organ.position = add(organ.position, shifts[i]);
    }
  }

  const pct = (n) => `${((100 * n) / Math.max(1, count.supported)).toFixed(1)}%`;
  return {
    summary: `${count.supported} supported stem points: ${pct(count.buried)} stood more than 10 mm inside the real timber and ${pct(count.moved)} were moved by more than 5 mm (the furthest ${(count.furthest * 1000).toFixed(0)} mm); ${pct(count.unseated)} could not be placed on a member and follow their neighbours`,
  };
}
