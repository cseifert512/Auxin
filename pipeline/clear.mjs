// Keep every stem outside the timber.
//
// The simulator winds a stem round the member it climbs and takes no account of the members that cross that one:
// where another is lapped over or under it, the stem as recorded runs straight through the second. Shoots that
// hang free are likewise recorded with no timber in their way. Nothing grows through wood, so here every stretch
// of stem that stands inside a member is moved out of it.
//
// A stretch inside one member leaves it by one face, the same for the whole stretch: the face that moves the
// stretch least. So a stem that meets a crossing member goes over it, or under, or round one side, in one piece,
// and does not jump from face to face through the wood. A point moved on to a face rests on it from then on: it
// thickens outwards from that face. What grows on a stem point moves with it.
import { add, against, dot, gridOf, mul, segmentsOf, sub } from './solids.mjs';

/** A point this far inside a face still counts as on it, and a moved point is left this far outside. */
const SKIN_M = 0.003;
const FACES = ['wide+', 'wide-', 'deep+', 'deep-'];

/** The member a point stands deepest inside, if any, with the stretch of it concerned. */
function holder(p, segments, near) {
  let found = null;
  for (const k of near(p)) {
    const at = against(p, segments[k]);
    if (at && at.inside > SKIN_M && (!found || at.inside > found.inside)) found = { segment: segments[k], inside: at.inside };
  }
  return found;
}

/** How far a point has to go to leave a stretch of timber by one face, and the way out through it. */
function leaveBy(p, s, face) {
  const r = sub(p, s.a);
  const sign = face.endsWith('+') ? 1 : -1;
  const axis = face.startsWith('wide') ? s.wide : s.deep;
  const half = face.startsWith('wide') ? s.halfW : s.halfD;
  return { far: half - sign * dot(r, axis), out: mul(axis, sign) };
}

/** The share of stem points standing more than `depthM` inside any member. */
export function shareInside(growth, centrelines, depthM = 0.005) {
  const segments = segmentsOf(centrelines);
  const near = gridOf(segments);
  let points = 0;
  let inside = 0;
  for (const stem of growth.stems) {
    for (let i = 0; i < stem.bornDay.length; i++) {
      points++;
      const p = [stem.contact[3 * i], stem.contact[3 * i + 1], stem.contact[3 * i + 2]];
      for (const k of near(p)) {
        const at = against(p, segments[k]);
        if (at && at.inside > depthM) {
          inside++;
          break;
        }
      }
    }
  }
  return inside / Math.max(1, points);
}

/** Mutates `growth` (the simulator's render data). Returns what was done, for the run's record. */
export function clear(growth, centrelines) {
  const segments = segmentsOf(centrelines);
  const near = gridOf(segments);
  const before = shareInside(growth, centrelines);
  const moved = new Map();
  let stretches = 0;
  let furthest = 0;

  for (const stem of growth.stems) {
    const n = stem.bornDay.length;
    const at = (i) => [stem.contact[3 * i], stem.contact[3 * i + 1], stem.contact[3 * i + 2]];
    const was = Array.from({ length: n }, (_, i) => at(i));
    let touched = false;
    // a stretch taken out of one member may land in the next: a few rounds settle it
    for (let round = 0; round < 4; round++) {
      const holders = Array.from({ length: n }, (_, i) => holder(at(i), segments, near));
      let any = false;
      for (let i = 0; i < n; ) {
        if (!holders[i]) {
          i++;
          continue;
        }
        const member = holders[i].segment.member;
        let j = i;
        while (j < n && holders[j] && holders[j].segment.member === member) j++;
        // the one face that moves this stretch least
        let best = null;
        for (const face of FACES) {
          let cost = 0;
          for (let k = i; k < j; k++) cost += Math.max(0, leaveBy(at(k), holders[k].segment, face).far);
          if (!best || cost < best.cost) best = { face, cost };
        }
        for (let k = i; k < j; k++) {
          const exit = leaveBy(at(k), holders[k].segment, best.face);
          const to = add(at(k), mul(exit.out, exit.far + SKIN_M));
          stem.contact[3 * k] = to[0];
          stem.contact[3 * k + 1] = to[1];
          stem.contact[3 * k + 2] = to[2];
          stem.away[3 * k] = exit.out[0];
          stem.away[3 * k + 1] = exit.out[1];
          stem.away[3 * k + 2] = exit.out[2];
        }
        stretches++;
        any = touched = true;
        i = j;
      }
      if (!any) break;
    }
    if (!touched) continue;
    const shifts = was.map((p, i) => sub(at(i), p));
    for (const s of shifts) furthest = Math.max(furthest, Math.hypot(s[0], s[1], s[2]));
    moved.set(stem.id, { was, shifts });
  }

  // what grows on a stem goes with the point it stands on
  for (const organ of [...growth.leaves, ...growth.flowers, ...(growth.fruits ?? []), ...(growth.appendages ?? [])]) {
    const m = moved.get(organ.stemId);
    if (!m) continue;
    let i = organ.stemPoint;
    if (i === undefined || i < 0 || i >= m.was.length) {
      let dMin = Infinity;
      for (let j = 0; j < m.was.length; j++) {
        const d = Math.hypot(m.was[j][0] - organ.position[0], m.was[j][1] - organ.position[1], m.was[j][2] - organ.position[2]);
        if (d < dMin) {
          dMin = d;
          i = j;
        }
      }
    }
    organ.position = add(organ.position, m.shifts[i]);
  }

  const after = shareInside(growth, centrelines);
  const pct = (x) => `${(100 * x).toFixed(1)}%`;
  return {
    summary: `${pct(before)} of stem points stood more than 5 mm inside the timber; ${stretches} stretches of stem were taken out of it (the furthest moved ${(furthest * 1000).toFixed(0)} mm), leaving ${pct(after)}`,
  };
}
