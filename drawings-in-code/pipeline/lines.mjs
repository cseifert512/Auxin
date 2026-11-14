// Training lines: thin cable that rides the timber.
//
// A line belongs to a member. It is held a hand's breadth off the member's outer face on standoffs screwed into
// it, and it goes where the member goes: up the leg, through the curve of the pier, out over the roof. Nothing is
// drawn here that the building does not already draw; the lines are the structure's own lines, moved outwards by
// the gap. Where two members cross, their lines cross above the joint, and a plant can pass from one to the other.
//
// This works on this building because its lattice is flush on the outside: at every lap the two members' outer
// faces meet within a couple of centimetres, so a line held off one clears all that cross it.
//
// Which members carry a line is the design decision, and the one setting that matters:
//   ground        every member with a foot on the ground: each is a way up from the soil          (the default)
//   ground+ribs   those, and every rib of the first tier
//   all           every member
//   or a pattern  matched against member IDs
// and, for the first three, only members of `families`: the lattice's, not the arches. An arch frames a doorway,
// and a line on its back hangs planting in the opening. This is the building model's own rule (bower-blender,
// bower/lines.py: carry grounded, families rib, fill, fine, hoop), which these lines are kept in step with until
// a snapshot carries the generator's own.
//
// A plant goes in at the foot of a line. Each pier takes up to `bedsPerPier`, and the lines that go furthest in
// over the room are planted first: the roof is what the planting is for, and the lines that only go over a bay,
// just behind its arch, are left to be reached from the others where they cross. At a pier the feet of the lines
// stand a hand apart in the pocket behind the arch legs, which is not where anything can be planted: the building
// model's answer (a root zone outside the pier and a feeder up the arch leg) is a draft at one pier, and until a
// snapshot carries it the plants here start at the line feet.
//
// Nothing here is engineered: the standoff, its fixing and the cable's tension are for the building model and an
// engineer. This says where the lines would run. It belongs in the building's own generator once it is settled.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { add, against, dot, gridOf, len, mul, segmentsOf, sub, unit } from './solids.mjs';

export const LINE_DEFAULTS = {
  diameterMm: 4,
  /** Clear gap between the member's outer face and the cable: about 3 inches. */
  gapM: 0.075,
  carry: 'ground',
  families: ['rib', 'fill', 'fine', 'hoop'],
  /** The cable is recorded at about this spacing along the member; a standoff every other point or so. */
  stationM: 0.3,
  standoffEveryM: 0.6,
  bedsPerPier: 4,
};

/**
 * The training lines of one snapshot.
 * Returns the cables (polylines, metres, z up), the beds at their feet, and counts.
 */
export function trainingLines(snapshotDir, design, options = {}) {
  const o = { ...LINE_DEFAULTS, ...options };
  const centrelines = JSON.parse(readFileSync(resolve(snapshotDir, 'centrelines.json'), 'utf8'));
  const room = design.rooms[0];
  const [cx, cy] = room.crown.centre_m;
  const segments = segmentsOf(centrelines);
  const near = gridOf(segments, 0.3);
  const grounded = (p) => p[2] < 0.06;
  const reachesGround = (m) => grounded(m.points_m[0]) || grounded(m.points_m[m.points_m.length - 1]);

  const ofFamilies = (m) => o.families.includes(m.family);
  const carries =
    o.carry === 'all'
      ? ofFamilies
      : o.carry === 'ground'
        ? (m) => ofFamilies(m) && reachesGround(m)
        : o.carry === 'ground+ribs'
          ? (m) => ofFamilies(m) && (reachesGround(m) || m.family === 'rib')
          : (m) => new RegExp(o.carry).test(m.id);

  const feet = centrelines.members.flatMap((m) => [m.points_m[0], m.points_m[m.points_m.length - 1]].filter(grounded));
  const piers = room.piers.map((pier) => {
    const own = feet.filter((f) => Math.hypot(f[0] - pier.position_m[0], f[1] - pier.position_m[1]) < 1.3);
    return { id: pier.id, mid: [own.reduce((s, f) => s + f[0], 0) / own.length, own.reduce((s, f) => s + f[1], 0) / own.length], feet: [] };
  });
  const pierOf = (p) => piers.map((pier) => ({ pier, d: Math.hypot(p[0] - pier.mid[0], p[1] - pier.mid[1]) })).sort((a, b) => a.d - b.d)[0];

  const cables = [];
  let insideTimber = 0;
  let points = 0;
  for (const m of centrelines.members) {
    if (!carries(m)) continue;
    const n = m.points_m.length;
    // Which way is out. On the roof that is up and away from the middle of the room. The same face is then
    // followed along the member, so that down a pier the line stays on the outside of the sheaf with its member.
    const top = m.points_m.reduce((best, p, i) => (p[2] > m.points_m[best][2] ? i : best), 0);
    const out = new Array(n);
    const at = m.points_m[top];
    const roof = unit([at[0] - cx, at[1] - cy, at[2] - 1 + 2]);
    out[top] = mul(unit(m.depth_axes[top]), dot(m.depth_axes[top], roof) < 0 ? -1 : 1);
    for (let i = top + 1; i < n; i++) out[i] = mul(unit(m.depth_axes[i]), dot(m.depth_axes[i], out[i - 1]) < 0 ? -1 : 1);
    for (let i = top - 1; i >= 0; i--) out[i] = mul(unit(m.depth_axes[i]), dot(m.depth_axes[i], out[i + 1]) < 0 ? -1 : 1);

    const every = Math.max(1, Math.round(o.stationM / (centrelines.sample_spacing_m ?? 0.1)));
    const line = [];
    for (let i = 0; i < n; i++) {
      if (i % every !== 0 && i !== n - 1) continue;
      const p = add(m.points_m[i], mul(out[i], m.depth_m / 2 + o.gapM));
      // a foot on the ground stays just above it
      if (grounded(m.points_m[i])) p[2] = Math.max(p[2], 0.05);
      line.push(p);
      points++;
      if (near(p).some((k) => segments[k].member !== centrelines.members.indexOf(m) && (against(p, segments[k])?.inside ?? -1) > 0.005)) insideTimber++;
    }
    for (const end of [0, n - 1]) {
      if (!grounded(m.points_m[end])) continue;
      const foot = end === 0 ? line[0] : line[line.length - 1];
      // how near the middle of the room the member comes: the smaller, the further in over the roof it goes
      const inM = Math.min(...m.points_m.map((p) => Math.hypot(p[0] - cx, p[1] - cy)));
      pierOf(foot).pier.feet.push({ member: m.id, family: m.family, at: foot, lengthM: m.length_m, inM });
    }
    cables.push({ id: `line.${m.id}`, member: m.id, family: m.family, points: line });
  }

  // ---- beds: at the feet of lines, up to so many a pier, the ways furthest in over the room first -------------------------
  const beds = [];
  for (const pier of piers) {
    const angle = (f) => (Math.atan2(f.at[1] - pier.mid[1], f.at[0] - pier.mid[0]) - Math.atan2(pier.mid[1] - cy, pier.mid[0] - cx) + 4 * Math.PI) % (2 * Math.PI);
    const chosen = [];
    for (const foot of [...pier.feet].sort((a, b) => a.inM - b.inM || b.lengthM - a.lengthM)) {
      if (chosen.length >= o.bedsPerPier) break;
      // not two beds on top of one another
      if (chosen.some((c) => Math.hypot(c.at[0] - foot.at[0], c.at[1] - foot.at[1]) < 0.09)) continue;
      chosen.push(foot);
    }
    chosen
      .sort((a, b) => angle(a) - angle(b))
      .forEach((foot, k) => {
        const away = unit([foot.at[0] - pier.mid[0], foot.at[1] - pier.mid[1], 0]);
        beds.push({ id: `bed.${pier.id}.${k + 1}`, position: [Number((foot.at[0] + away[0] * 0.18).toFixed(3)), Number((foot.at[1] + away[1] * 0.18).toFixed(3)), room.floor_z_m ?? 0], climbs: foot.member });
      });
  }

  const round = (v) => Number(v.toFixed(4));
  const lengthOf = (c) => c.points.slice(1).reduce((d, p, i) => d + len(sub(p, c.points[i])), 0);
  const byFamily = {};
  for (const c of cables) byFamily[c.family] = Math.round((byFamily[c.family] ?? 0) + lengthOf(c));
  const lengthM = cables.reduce((s, c) => s + lengthOf(c), 0);
  return {
    cables: cables.map((c) => ({ id: c.id, diameterMm: o.diameterMm, points: c.points.map((p) => p.map(round)) })),
    beds,
    gapM: o.gapM,
    summary: { carry: o.carry, lines: cables.length, lengthM: Math.round(lengthM), byFamily, standoffs: Math.round(lengthM / o.standoffEveryM), beds: beds.length, pointsInsideOtherTimber: `${insideTimber} of ${points}` },
  };
}
