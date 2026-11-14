// Training lines: thin cable on the outside of the structure, laid out by the structure itself.
//
// The building carries its roof to the ground in three steps: the lattice of ribs on to the hoops and arches at
// its edge, those down on to the piers, the piers to the ground. The lines lead plants up the way the loads come
// down. From a bed at the foot of a pier a line climbs the pier, follows the hoop that runs inside the arch round
// the edge of the roof, and from that hoop lines branch off straight up the slope to the crown.
//
// Nothing is placed by eye. Wherever two members cross there is a lap joint, and the joints are the only places
// a line is fixed:
//   boughs    one along each hoop named, from its foot at one pier, over the bay, to its foot at the next. It runs
//             from joint to joint along the hoop, proud of the ribs that cross it.
//   branches  from a joint on a bough, on to the nearest joint that lies up the slope and is on neither of the
//             same two members, and so on to the crown. In a lattice of two leaning families of ribs that is the
//             third direction, the one the timber does not have: a branch runs across the open cells from corner
//             to corner, so plants trained on it cover the openings as well as the wood. Branches that meet go on
//             as one.
// Branches leave a bough no closer together than the spacing asked for. Nothing is strung across an opening: the
// boughs go over the arches, as the hoops do.
//
// Nothing here is engineered: how a cable is fixed and tensioned and what it does to the timber are for the
// building model and an engineer. This says where the lines would run, and it is one rule among those possible.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { add, against, dot, gridOf, len, lerp, mul, reject, segmentsOf, sub, unit } from './solids.mjs';

export const LINE_DEFAULTS = {
  /** The cable, and how far its centre stands off the outermost timber at a fixing. */
  diameterMm: 3,
  standOffM: 0.03,
  /** The members a bough follows: by default the first hoop inside each arch. */
  boughs: 'hoop0$',
  /** Branches leave a bough about this far apart. */
  spacingM: 0.9,
  /** How near and how far the next fixing up a branch may be, and how far off straight up the slope, in degrees. */
  stepM: [0.3, 1.7],
  coneDeg: 38,
  /** A branch shorter than this is not worth stringing. */
  shortestM: 1.2,
  /** Beds at the foot of each bough, and how far apart they stand. */
  bedsPerFoot: 3,
  bedGapM: 0.42,
};

const UP = [0, 0, 1];

function readJoints(file) {
  const [head, ...rows] = readFileSync(file, 'utf8').split(/\r?\n/).filter((l) => l.length);
  const keys = head.split(',');
  return rows.map((r) => Object.fromEntries(r.split(',').map((v, i) => [keys[i], v])));
}

/**
 * The training lines of one snapshot.
 * Returns the cables (polylines, metres, z up), the beds at their feet, and counts.
 */
export function trainingLines(snapshotDir, design, options = {}) {
  const o = { ...LINE_DEFAULTS, ...options };
  const centrelines = JSON.parse(readFileSync(resolve(snapshotDir, 'centrelines.json'), 'utf8'));
  const joints = readJoints(resolve(snapshotDir, 'joints.csv'));
  const members = new Map(centrelines.members.map((m) => [m.id, m]));
  const room = design.rooms[0];
  const [cx, cy] = room.crown.centre_m;
  const segments = segmentsOf(centrelines);
  const near = gridOf(segments, 0.3);
  const inTimber = (p) => near(p).some((k) => (against(p, segments[k])?.inside ?? -1) > 0);

  // where on a member a joint is: the nearest sample of its centre line, and the way its depth points out there
  const seat = (id, at) => {
    const m = members.get(id);
    if (!m) return null;
    let best = 0;
    let dMin = Infinity;
    m.points_m.forEach((p, i) => {
      const d = len(sub(p, at));
      if (d < dMin) {
        dMin = d;
        best = i;
      }
    });
    let out = unit(m.depth_axes[best]);
    if (dot(out, [at[0] - cx, at[1] - cy, at[2] - 1]) < 0) out = mul(out, -1);
    return { sample: best, centre: m.points_m[best], out, halfD: m.depth_m / 2 };
  };

  // ---- the fixings: every lap joint, as a point just proud of the outermost timber there -----------------------------
  const fixings = [];
  for (const j of joints) {
    if (j.kind !== 'cross_lap') continue;
    const at = [Number(j.x_m), Number(j.y_m), Number(j.z_m)];
    const a = seat(j.member_a, at);
    const b = seat(j.member_b, at);
    if (!a || !b) continue;
    const out = unit(add(a.out, b.out));
    const proud = Math.max(dot(sub(a.centre, at), out) + a.halfD, dot(sub(b.centre, at), out) + b.halfD) + o.standOffM;
    const slope = reject(UP, out);
    // on a face that is nearly level there is no slope to follow: head for the crown
    const uphill = len(slope) > 0.15 ? unit(slope) : unit(reject([cx - at[0], cy - at[1], 0.2], out));
    fixings.push({ index: fixings.length, members: [j.member_a, j.member_b], samples: { [j.member_a]: a.sample, [j.member_b]: b.sample }, at: add(at, mul(out, proud)), uphill, next: -1 });
  }

  // each goes on to the next one up the slope that is on neither of its own two members
  const cone = Math.cos((o.coneDeg * Math.PI) / 180);
  for (const p of fixings) {
    let best = null;
    for (const q of fixings) {
      if (q === p || q.members.includes(p.members[0]) || q.members.includes(p.members[1])) continue;
      const v = sub(q.at, p.at);
      const d = len(v);
      if (d < o.stepM[0] || d > o.stepM[1] || q.at[2] <= p.at[2]) continue;
      const climb = dot(v, p.uphill) / d;
      if (climb < cone) continue;
      // nearest first, and of two as near, the straighter
      const cost = d * (1.7 - climb);
      if (!best || cost < best.cost) best = { q, cost };
    }
    if (best) p.next = best.q.index;
  }

  // ---- boughs ---------------------------------------------------------------------------------------------------------
  const feet = centrelines.members.flatMap((m) => [m.points_m[0], m.points_m[m.points_m.length - 1]].filter((p) => p[2] < 0.06));
  const piers = room.piers.map((pier) => {
    const own = feet.filter((f) => Math.hypot(f[0] - pier.position_m[0], f[1] - pier.position_m[1]) < 1.3);
    return { id: pier.id, at: pier.position_m, mid: [own.reduce((s, f) => s + f[0], 0) / own.length, own.reduce((s, f) => s + f[1], 0) / own.length], feet: [] };
  });
  const pierOf = (p) => piers.map((pier) => ({ pier, d: Math.hypot(p[0] - pier.at[0], p[1] - pier.at[1]) })).sort((a, b) => a.d - b.d)[0].pier;

  /** A place on the ground beside a member's foot, out from the pier, that a straight cable to `first` reaches without passing through timber. */
  const footOf = (end, first) => {
    const pier = pierOf(end);
    const away = unit([end[0] - pier.mid[0], end[1] - pier.mid[1], 0]);
    for (const out of [0.3, 0.5, 0.75, 1.0]) {
      const ground = [end[0] + away[0] * out, end[1] + away[1] * out, 0.05];
      if (Array.from({ length: 16 }, (_, i) => lerp(ground, first, (i + 1) / 17)).every((p) => !inTimber(p)) || out === 1.0) return { pier, ground };
    }
    return null;
  };

  const boughPattern = new RegExp(o.boughs);
  const cables = [];
  const used = new Set();
  const branchFeet = [];
  for (const m of centrelines.members) {
    if (!boughPattern.test(m.id)) continue;
    const on = fixings.filter((f) => f.members.includes(m.id)).sort((p, q) => p.samples[m.id] - q.samples[m.id]);
    if (on.length < 2) continue;
    const points = on.map((f) => f.at);
    // down to the ground at whichever ends of the member reach it
    for (const [end, first, put] of [[m.points_m[0], on[0].at, 'unshift'], [m.points_m[m.points_m.length - 1], on[on.length - 1].at, 'push']]) {
      if (end[2] > 0.06) continue;
      const foot = footOf(end, first);
      points[put](foot.ground);
      foot.pier.feet.push(foot.ground);
    }
    cables.push({ kind: 'bough', along: m.id, points });
    // branches leave it no closer together than asked
    let since = Infinity;
    on.forEach((f, i) => {
      used.add(f.index);
      if (i > 0) since += len(sub(f.at, on[i - 1].at));
      if (since >= o.spacingM && f.next >= 0) {
        branchFeet.push(f);
        since = 0;
      }
    });
  }

  // ---- branches: up the slope from a bough until the crown, or until another branch is met -----------------------------
  for (const foot of branchFeet) {
    const points = [foot.at];
    let f = fixings[foot.next];
    let guard = 0;
    while (f && guard++ < 200) {
      points.push(f.at);
      if (used.has(f.index)) break;
      used.add(f.index);
      f = f.next >= 0 ? fixings[f.next] : null;
    }
    const length = points.slice(1).reduce((d, p, i) => d + len(sub(p, points[i])), 0);
    if (length >= o.shortestM) cables.push({ kind: 'branch', points });
  }

  // ---- beds: a few at the foot of each bough, side by side round the pier ------------------------------------------------
  const beds = [];
  for (const pier of piers) {
    const spots = [];
    for (const ground of pier.feet) {
      const out = unit([ground[0] - pier.mid[0], ground[1] - pier.mid[1], 0]);
      const round = [-out[1], out[0], 0];
      for (let k = 0; k < o.bedsPerFoot; k++) {
        const aside = (k - (o.bedsPerFoot - 1) / 2) * o.bedGapM;
        spots.push([ground[0] + round[0] * aside + out[0] * 0.12, ground[1] + round[1] * aside + out[1] * 0.12]);
      }
    }
    // round the pier in order, the first on the side away from the room
    const turn = (s) => (Math.atan2(s[1] - pier.mid[1], s[0] - pier.mid[0]) - Math.atan2(pier.mid[1] - cy, pier.mid[0] - cx) + 4 * Math.PI) % (2 * Math.PI);
    spots.sort((a, b) => turn(a) - turn(b)).forEach((s, k) => beds.push({ id: `bed.${pier.id}.${k + 1}`, position: [Number(s[0].toFixed(3)), Number(s[1].toFixed(3)), room.floor_z_m ?? 0] }));
  }

  const round = (v) => Number(v.toFixed(4));
  const lengthOf = (kind) => cables.filter((c) => c.kind === kind).reduce((sum, c) => sum + c.points.slice(1).reduce((d, p, i) => d + len(sub(p, c.points[i])), 0), 0);
  let b = 0;
  let r = 0;
  return {
    cables: cables.map((c) => ({ id: c.kind === 'bough' ? `bough.${String(++b).padStart(2, '0')}` : `branch.${String(++r).padStart(3, '0')}`, diameterMm: o.diameterMm, points: c.points.map((p) => p.map(round)) })),
    beds,
    summary: { fixings: fixings.length, fixingsUsed: used.size, boughs: b, boughM: Math.round(lengthOf('bough')), branches: r, branchM: Math.round(lengthOf('branch')), beds: beds.length },
  };
}
