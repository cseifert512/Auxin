// A turn through the forms the room can take, with a planting on it: the timber of every state drawn with that
// state's own joints, and the plants of one grown planting carried on it.
//
// Three things are true of what this draws, and they go under any picture made from it.
//   The timber is the generator's at every state: bower-blender builds each state and sets out its joints, and
//   between two states a timber is moved point by point. Each timber is drawn as the generator's own simpler
//   model of a milled member (bower/member.py, `sweep`): its section swept along its centre line, its ends cut to
//   their planes, and a flat-walled lap stepped in wherever the joints code says another member crosses it. It is
//   not the milled mesh of a snapshot: laps only, with no housings, seats or splayed walls, and a lap too oblique
//   or too near an end to step in is left uncut, as that model leaves it.
//   The lattice does not change smoothly, and that is the generator's too. A rib that passes near a pier is drawn
//   into it and stands on the floor; one that passes wider lands on an arch. Between two states that differ in
//   this the rib is drawn running out to its new foot, or drawing back from its old one.
//   A planting is grown on one form. Away from that form it is CARRIED, not grown: each stem point that lies on a
//   timber keeps its place along that timber and its side of it, and what stands on it goes with it. Shoots that
//   hang free keep their shape and go with the wood they spring from. Nothing here decides how a plant would
//   have grown on the form in between.
//
// Read with ?tour=<states.json>&growth=<growth.json>&form=<id>: see pipeline/tour.mjs, which asks for the frames.
import * as THREE from 'three';
import type { RenderData } from '@horti/core';
import { clock } from '@horti/viewer/plant/adapter.ts';
import { shared } from '@horti/viewer/plant/shaders.ts';
import { type PlantMaterials, PlantView } from '@horti/viewer/plant/view.ts';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import type { Paper } from './paper.ts';
import type { Timber } from './timber.ts';

interface TourFile {
  tour: string;
  snapshot: string;
  samples: number;
  /** A member marked `from_head` has its points this far apart, counted back from its last; the rest are spread evenly along it. */
  spacing_m: number;
  /** The gap the joints code leaves between a member and the wall of the lap it sits in. */
  lap_clearance_m?: number;
  loop: boolean;
  between: number;
  /** Each is one timber followed through the tour by where it stands; `mesh` is the snapshot's member it is, if it stands in the snapshot. */
  members: { id: string; kind: string; family: string; width_m: number; depth_m: number; closed: boolean; from_head: boolean; mesh: string | null }[];
  /** Round a loop, which timber each has become by the first state again, where that is not itself (-1: none). */
  wrap?: number[];
  forms: { id: string; title: string; state: number; grown_on: string }[];
  /**
   * `len`: each member's length in millimetres. `ends`: six numbers a member, the unit normals (in ten-thousandths) of
   * the planes its start and its end are cut to, or noughts. `laps`: six numbers a lap: the timber cut on its outer
   * face, the timber cut on its inner face, millimetres along each from its start, and how deep each is cut.
   */
  states: { values: Record<string, number>; has: number[]; mm: number[]; axes: number[]; len: number[]; ends: number[]; laps: number[] }[];
}

const DAY_MS = 86_400_000;
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
/** A timber missing from this many states in a row or fewer is taken to be there throughout, and drawn between its neighbours. */
const BRIEF_GAP = 2;
/** As bower/member.py: how far a ring of a member's section may be slid along it to reach a plane it is cut to. */
const CUT_SLIDE_LIMIT_M = 0.5;
/** Two members set out as lapped are still lapped while their centre lines pass this near; further apart, the lap is not cut. */
const LAP_REACH_M = 0.15;

// ---- a planting kept to the days a film shows ------------------------------------------------------------------------
/**
 * The planting with only what is on the plants at some time between two days: `days` is "from,to". A film of one
 * year has no use for the leaves of the nine others, and every state of the tour is drawn by making the plants
 * again from this.
 */
export function inSeason(data: RenderData, days: string | null): RenderData {
  const [from, to] = (days ?? '').split(',').map(Number);
  if (from === undefined || to === undefined || !Number.isFinite(from) || !Number.isFinite(to)) return data;
  const start = Date.parse(`${data.start}T00:00:00Z`);
  const year = (day: number) => new Date(start + day * DAY_MS).getUTCFullYear();
  const [y0, y1] = [year(from), year(to)];
  const here = (born: number, removed: number) => born <= to && (removed < 0 || removed >= from);
  const stems = data.stems.filter((s) => s.bornDay.length >= 2 && here(s.bornDay[0]!, s.removedDay[0]!));
  const kept = new Set(stems.map((s) => s.id));
  return {
    ...data,
    stems,
    leaves: data.leaves.filter((l) => kept.has(l.stemId) && l.firstYear <= y1 && (l.lastYear === null || l.lastYear >= y0) && here(l.bornDay, l.removedDay)),
    flowers: data.flowers.filter((f) => kept.has(f.stemId) && f.developDay <= to && (f.spentDay < 0 || f.spentDay >= from - 30)),
    fruits: data.fruits.filter((f) => kept.has(f.stemId) && f.swell[0] <= to && (f.removedDay < 0 || f.removedDay >= from)),
    appendages: data.appendages.filter((a) => kept.has(a.stemId) && here(a.bornDay, a.removedDay)),
  };
}

// ---- the building at one state: where each timber's centre line is, and how it is turned ------------------------------
/** Every timber as N points, each with its frame: along it, through its depth, across its width (building axes, z up). */
interface Stand {
  C: Float32Array; // timbers * N * 3
  F: Float32Array; // timbers * N * 9
  /** How much of each timber is there: 1 standing, 0 not in this state, between while it comes or goes. */
  there: Float32Array;
  /** For a rib, whose points are counted from its head: the first of them that is not its foot over again. 0 for anything else. */
  foot: Float32Array;
  /** Metres of each timber to one of its points. */
  pitch: Float32Array;
  /** The unit normals of the planes each timber's start and end are cut to: six numbers a timber, noughts where it is cut square. */
  ends: Float32Array;
  /** The laps set out in the nearer state, six numbers each: the timber cut on its outer face, the one cut on its inner, points along each, depth of each cut. */
  laps: Float32Array;
  lapCount: number;
}

function tourOf(file: TourFile) {
  const N = file.samples;
  const M = file.members.length;
  const S = file.states.length;
  const closed = file.members.map((m) => m.closed);
  const pos: Float32Array[] = [];
  const axis: Float32Array[] = [];
  const has: Uint8Array[] = [];
  const cutTo: Float32Array[] = [];
  const lapsOf: Float32Array[] = [];
  for (const state of file.states) {
    const p = new Float32Array(M * N * 3);
    const a = new Float32Array(M * N * 3);
    const h = new Uint8Array(M);
    const e = new Float32Array(M * 6);
    const lengthOf = new Float32Array(M);
    state.has.forEach((m, k) => {
      h[m] = 1;
      for (let i = 0; i < N * 3; i++) {
        p[m * N * 3 + i] = state.mm[k * N * 3 + i]! / 1000;
        a[m * N * 3 + i] = state.axes[k * N * 3 + i]! / 10000;
      }
      for (let i = 0; i < 6; i++) e[m * 6 + i] = (state.ends?.[k * 6 + i] ?? 0) / 10000;
      lengthOf[m] = (state.len?.[k] ?? 0) / 1000;
    });
    // a station in metres from a member's start, as a count of its points
    const pointAt = (m: number, mm: number) => {
      const [s, L] = [mm / 1000, lengthOf[m]! || 1];
      return closed[m] ? (s / L) * N : file.members[m]!.from_head ? N - 1 - (L - s) / file.spacing_m : (s / L) * (N - 1);
    };
    const set = state.laps ?? [];
    const l = new Float32Array(set.length);
    for (let k = 0; k + 5 < set.length; k += 6) l.set([set[k]!, set[k + 1]!, pointAt(set[k]!, set[k + 2]!), pointAt(set[k + 1]!, set[k + 3]!), set[k + 4]! / 1000, set[k + 5]! / 1000], k);
    pos.push(p);
    axis.push(a);
    has.push(h);
    cutTo.push(e);
    lapsOf.push(l);
  }
  // Round a loop the timbers may come back shifted: a rib that began in one place ends in the next one's. A state
  // is then counted on past the last (or back before the first), and `turned` says which timber is meant there.
  const onward = file.wrap ?? file.members.map((_, m) => m);
  const backward = new Int32Array(M).fill(-1);
  onward.forEach((to, m) => {
    if (to >= 0) backward[to] = m;
  });
  const turned = (m: number, times: number): number => {
    for (let k = 0; k < Math.abs(times) && m >= 0; k++) m = times > 0 ? onward[m]! : backward[m]!;
    return m;
  };
  // A timber not in a state still needs somewhere to be drawn from while it comes and goes: across a brief gap it
  // is carried between the states either side and counted as there; across a long one it waits where it last stood.
  // (Not across the seam of a loop whose timbers come round shifted: there it waits.)
  const round = file.loop && !file.wrap;
  const step = (s: number, by: number) => (round ? (((s + by) % S) + S) % S : Math.min(S - 1, Math.max(0, s + by)));
  const stood = has.map((h) => Uint8Array.from(h));
  for (let m = 0; m < M; m++) {
    for (let s = 0; s < S; s++) {
      if (stood[s]![m]) continue;
      let before = 1;
      let after = 1;
      while (before < S && !stood[step(s, -before)]![m] && (round || s - before > 0)) before++;
      while (after < S && !stood[step(s, after)]![m] && (round || s + after < S - 1)) after++;
      const [a, b] = [step(s, -before), step(s, after)];
      const [isA, isB] = [stood[a]![m] === 1, stood[b]![m] === 1];
      if (!isA && !isB) continue; // never anywhere
      const brief = isA && isB && before + after - 1 <= BRIEF_GAP;
      const t = brief ? before / (before + after) : !isB || (isA && before <= after) ? 0 : 1;
      for (let i = m * N * 3; i < (m + 1) * N * 3; i++) {
        pos[s]![i] = pos[a]![i]! + (pos[b]![i]! - pos[a]![i]!) * t;
        axis[s]![i] = axis[a]![i]! + (axis[b]![i]! - axis[a]![i]!) * t;
      }
      if (brief) has[s]![m] = 1;
    }
  }
  /** Where a rib's own points begin, in one state: before that they are its foot over again. */
  const footOf = (C: Float32Array, m: number, from: number): number => {
    if (!file.members[m]!.from_head) return 0;
    let n = 0;
    const at = from * N * 3;
    while (n < N - 2 && C[at + n * 3] === C[at + n * 3 + 3] && C[at + n * 3 + 1] === C[at + n * 3 + 4] && C[at + n * 3 + 2] === C[at + n * 3 + 5]) n++;
    return n;
  };

  /**
   * The building at a place on the tour: a state by its number, or part-way from one to the next. Round a loop the
   * number may run on past the last state or back before the first, and each timber keeps the number it has at
   * the states inside the tour.
   */
  function stand(at: number, out?: Stand): Stand {
    const o = out ?? { C: new Float32Array(M * N * 3), F: new Float32Array(M * N * 9), there: new Float32Array(M), foot: new Float32Array(M), pitch: new Float32Array(M), ends: new Float32Array(M * 6), laps: new Float32Array(6 * 1024), lapCount: 0 };
    const sigma = file.loop ? at : Math.min(S - 1, Math.max(0, at));
    const n0 = file.loop ? Math.floor(sigma) : Math.min(S - 2, Math.floor(sigma));
    const t = sigma - n0;
    const [i, j] = [((n0 % S) + S) % S, (((n0 + 1) % S) + S) % S];
    const [wi, wj] = [Math.floor(n0 / S), Math.floor((n0 + 1) / S)];
    const [pa, pb, aa, ab] = [pos[i]!, pos[j]!, axis[i]!, axis[j]!];
    const C = o.C;
    for (let m = 0; m < M; m++) {
      const [mi, mj] = [turned(m, wi), turned(m, wj)];
      o.there[m] = (mi >= 0 ? has[i]![mi]! : 0) * (1 - t) + (mj >= 0 ? has[j]![mj]! : 0) * t;
      // a timber with no place on one side is drawn where it is on the other, and comes or goes
      const [ma, mb] = [mi >= 0 ? mi : mj, mj >= 0 ? mj : mi];
      if (ma < 0 || mb < 0) continue;
      const [a, b] = [ma * N * 3, mb * N * 3];
      const c = m * N * 3;
      for (let k = 0; k < N * 3; k++) C[c + k] = pa[a + k]! + (pb[b + k]! - pa[a + k]!) * t;
      o.foot[m] = footOf(C, m, m);
      let length = 0;
      for (let n = 0; n < (closed[m] ? N : N - 1); n++) {
        const [p, q] = [c + n * 3, c + ((n + 1) % N) * 3];
        length += Math.hypot(C[q]! - C[p]!, C[q + 1]! - C[p + 1]!, C[q + 2]! - C[p + 2]!);
      }
      o.pitch[m] = file.members[m]!.from_head ? file.spacing_m : length / (closed[m] ? N : N - 1);
      for (let e = 0; e < 6; e += 3) {
        const [x, y, z] = [0, 1, 2].map((k) => cutTo[i]![ma * 6 + e + k]! * (1 - t) + cutTo[j]![mb * 6 + e + k]! * t) as [number, number, number];
        const size = Math.hypot(x, y, z);
        o.ends.set(size > 1e-6 ? [x / size, y / size, z / size] : [0, 0, 0], m * 6 + e);
      }
      // from the head down, so that the points of a foot take the frame of the last point above them
      for (let n = N - 1; n >= 0; n--) {
        const prev = c + (closed[m] ? (n - 1 + N) % N : Math.max(0, n - 1)) * 3;
        const next = c + (closed[m] ? (n + 1) % N : Math.min(N - 1, n + 1)) * 3;
        let [tx, ty, tz] = [C[next]! - C[prev]!, C[next + 1]! - C[prev + 1]!, C[next + 2]! - C[prev + 2]!];
        const tl = Math.hypot(tx, ty, tz);
        if (tl < 1e-9 && n < N - 1) {
          o.F.copyWithin((m * N + n) * 9, (m * N + n + 1) * 9, (m * N + n + 2) * 9);
          continue;
        }
        [tx, ty, tz] = [tx / (tl || 1), ty / (tl || 1), tz / (tl || 1)];
        let dx = aa[a + n * 3]! + (ab[b + n * 3]! - aa[a + n * 3]!) * t;
        let dy = aa[a + n * 3 + 1]! + (ab[b + n * 3 + 1]! - aa[a + n * 3 + 1]!) * t;
        let dz = aa[a + n * 3 + 2]! + (ab[b + n * 3 + 2]! - aa[a + n * 3 + 2]!) * t;
        const along = dx * tx + dy * ty + dz * tz;
        [dx, dy, dz] = [dx - along * tx, dy - along * ty, dz - along * tz];
        const dl = Math.hypot(dx, dy, dz) || 1;
        [dx, dy, dz] = [dx / dl, dy / dl, dz / dl];
        o.F.set([tx, ty, tz, dx, dy, dz, ty * dz - tz * dy, tz * dx - tx * dz, tx * dy - ty * dx], (m * N + n) * 9);
      }
    }
    // the laps of whichever state is nearer, under the numbers the timbers have here
    const [near, w] = t < 0.5 ? [i, wi] : [j, wj];
    const set = lapsOf[near]!;
    if (o.laps.length < set.length) o.laps = new Float32Array(set.length);
    o.lapCount = 0;
    for (let k = 0; k + 5 < set.length; k += 6) {
      const [a, b] = [turned(set[k]!, -w), turned(set[k + 1]!, -w)];
      if (a < 0 || b < 0) continue;
      o.laps.set([a, b, set[k + 2]!, set[k + 3]!, set[k + 4]!, set[k + 5]!], o.lapCount * 6);
      o.lapCount++;
    }
    return o;
  }

  /** The place and frame at `f` points along timber `m`, written into `out` (3 for the place, then along, depth, across). */
  function at(s: Stand, m: number, f: number, out: Float32Array | Float64Array, to = 0): void {
    const last = closed[m] ? N : N - 1;
    const g = closed[m] ? ((f % N) + N) % N : Math.min(last, Math.max(0, f));
    const i = Math.min(closed[m] ? N - 1 : N - 2, Math.floor(g));
    const j = closed[m] ? (i + 1) % N : i + 1;
    const t = g - i;
    const [ci, cj, fi, fj] = [(m * N + i) * 3, (m * N + j) * 3, (m * N + i) * 9, (m * N + j) * 9];
    for (let k = 0; k < 3; k++) out[to + k] = s.C[ci + k]! + (s.C[cj + k]! - s.C[ci + k]!) * t;
    let [tx, ty, tz] = [s.F[fi]! + (s.F[fj]! - s.F[fi]!) * t, s.F[fi + 1]! + (s.F[fj + 1]! - s.F[fi + 1]!) * t, s.F[fi + 2]! + (s.F[fj + 2]! - s.F[fi + 2]!) * t];
    const tl = Math.hypot(tx, ty, tz) || 1;
    [tx, ty, tz] = [tx / tl, ty / tl, tz / tl];
    let [dx, dy, dz] = [s.F[fi + 3]! + (s.F[fj + 3]! - s.F[fi + 3]!) * t, s.F[fi + 4]! + (s.F[fj + 4]! - s.F[fi + 4]!) * t, s.F[fi + 5]! + (s.F[fj + 5]! - s.F[fi + 5]!) * t];
    const along = dx * tx + dy * ty + dz * tz;
    [dx, dy, dz] = [dx - along * tx, dy - along * ty, dz - along * tz];
    const dl = Math.hypot(dx, dy, dz) || 1;
    [dx, dy, dz] = [dx / dl, dy / dl, dz / dl];
    out[to + 3] = tx;
    out[to + 4] = ty;
    out[to + 5] = tz;
    out[to + 6] = dx;
    out[to + 7] = dy;
    out[to + 8] = dz;
    out[to + 9] = ty * dz - tz * dy;
    out[to + 10] = tz * dx - tx * dz;
    out[to + 11] = tx * dy - ty * dx;
  }

  /**
   * How far along timber `m` the point of its centre line nearest (x, y, z) is, in points, and the square of how
   * far off. Only the part of it from `from` to `to` is looked at: by default, all that is not a rib's foot over
   * again. Round a ring the two may run past its seam.
   */
  function nearestOn(s: Stand, m: number, x: number, y: number, z: number, from = s.foot[m]!, to = Infinity): [number, number] {
    let best = from;
    let least = Infinity;
    const segments = closed[m] ? N : N - 1;
    const first = closed[m] ? Math.floor(from) : Math.max(0, Math.min(segments - 1, Math.floor(from)));
    const last = closed[m] ? Math.min(first + N, Math.ceil(to)) : Math.min(segments, Math.ceil(to));
    for (let k = first; k < last; k++) {
      const i = ((k % N) + N) % N;
      const a = (m * N + i) * 3;
      const b = (m * N + ((i + 1) % N)) * 3;
      const [ax, ay, az] = [s.C[a]!, s.C[a + 1]!, s.C[a + 2]!];
      const [ux, uy, uz] = [s.C[b]! - ax, s.C[b + 1]! - ay, s.C[b + 2]! - az];
      const uu = ux * ux + uy * uy + uz * uz;
      const t = uu > 0 ? Math.min(1, Math.max(0, ((x - ax) * ux + (y - ay) * uy + (z - az) * uz) / uu)) : 0;
      const d2 = (x - ax - ux * t) ** 2 + (y - ay - uy * t) ** 2 + (z - az - uz * t) ** 2;
      if (d2 < least) {
        least = d2;
        best = k + t;
      }
    }
    return [best, least];
  }

  /**
   * What stands in every whole state from `from` to `to` along the tour (which may run on past its ends, round a
   * loop): for each timber, whether it does, and for a rib the point from which it is there in all of them.
   */
  function throughout(from: number, to: number): { stands: Uint8Array; from: Float32Array } {
    const stands = new Uint8Array(M).fill(1);
    const begins = new Float32Array(M);
    for (let n = Math.ceil(from); n <= Math.floor(to); n++) {
      if (!file.loop && (n < 0 || n >= S)) continue;
      const [i, w] = [((n % S) + S) % S, Math.floor(n / S)];
      for (let m = 0; m < M; m++) {
        const mi = turned(m, w);
        if (mi < 0 || !has[i]![mi]) stands[m] = 0;
        else begins[m] = Math.max(begins[m]!, footOf(pos[i]!, m, mi));
      }
    }
    return { stands, from: begins };
  }

  return { N, M, S, closed, stand, at, nearestOn, throughout };
}
type Tour = ReturnType<typeof tourOf>;

const toB = (v: THREE.Vector3): [number, number, number] => [v.x, -v.z, v.y];

// ---- the timber, cut ------------------------------------------------------------------------------------------------
/** A plane: a point on it and its unit normal, six numbers. */
type Plane = [number, number, number, number, number, number];
/** A lap in one member, as bower/member.py has it: between two walls, one face is cut back to a floor. Stations are metres along the member. */
interface Notch {
  lo: number;
  hi: number;
  /** +1 cuts the face on the +depth side of the section (the room's side), -1 the other (the roof's upper side). */
  face: number;
  floor: Plane;
  loWall: Plane;
  hiWall: Plane;
}

/**
 * Every timber of a state as one mesh and one set of edges, made again whenever the state changes: a port of
 * `sweep` and `fit_notches` in bower-blender/bower/member.py, with the laps set out by bower/joints.py.
 */
function cutTimber(tour: Tour, file: TourFile, timber: Timber) {
  const { N, M } = tour;
  const clearance = file.lap_clearance_m ?? 0.001;
  const here = new Float64Array(12);
  const there = new Float64Array(12);
  const frame = new Float64Array(12);

  // each timber's own shade and how many boards it is laid up from: the snapshot's, or those of the nearest of its kind
  const numberOf = (id: string) => Number(id.split('@')[0]!.match(/\d+$/)?.[0] ?? 0);
  const shades = new Float32Array(M * 5);
  file.members.forEach((member, m) => {
    const like = member.mesh
      ? member
      : file.members.filter((x) => x.mesh && x.kind === member.kind).sort((a, b) => Math.abs(numberOf(a.id) - numberOf(member.id)) - Math.abs(numberOf(b.id) - numberOf(member.id)))[0];
    const from = like?.mesh ? timber.members.get(like.mesh)?.mesh.geometry : undefined;
    const [colour, piece] = [from?.getAttribute('color'), from?.getAttribute('piece')];
    shades.set([colour?.getX(0) ?? 0.62, colour?.getY(0) ?? 0.35, colour?.getZ(0) ?? 0.13, piece?.getX(0) ?? 0.5, piece?.getY(0) ?? Math.max(1, Math.round(member.depth_m / 0.044))], m * 5);
  });
  const anyOne = [...timber.members.values()][0]!;
  for (const one of timber.members.values()) one.mesh.visible = false;
  timber.lines.visible = false;

  let room = 700_000; // corners of triangles there is room for
  const geometry = new THREE.BufferGeometry();
  let position = new Float32Array(room * 3);
  let normal = new Float32Array(room * 3);
  let colour = new Float32Array(room * 3);
  let grain = new Float32Array(room * 3);
  let piece = new Float32Array(room * 2);
  const hold = () => {
    for (const [name, array, size] of [['position', position, 3], ['normal', normal, 3], ['color', colour, 3], ['grain', grain, 3], ['piece', piece, 2]] as const) {
      const attribute = new THREE.BufferAttribute(array, size);
      attribute.setUsage(THREE.DynamicDrawUsage);
      geometry.setAttribute(name, attribute);
    }
  };
  hold();
  const mesh = new THREE.Mesh(geometry, anyOne.mesh.material);
  mesh.castShadow = true;
  mesh.frustumCulled = false;
  mesh.name = 'timber, cut';
  const EDGES = 400_000;
  const edges = new Float32Array(EDGES * 6);
  const edgeGeometry = new LineSegmentsGeometry().setPositions(edges);
  const lines = new LineSegments2(edgeGeometry, timber.ink);
  lines.frustumCulled = false;
  lines.name = 'timber ink, cut';
  timber.group.add(mesh, lines);
  const drawn = (edgeGeometry.getAttribute('instanceStart') as THREE.InterleavedBufferAttribute).data;

  let used = 0;
  let edged = 0;
  let cut = 0;
  let uncut = 0;
  /** One edge, between two places in the building's axes. */
  const edge = (a: Float64Array, i: number, b: Float64Array, j: number) => {
    if (edged >= EDGES) return;
    edges.set([a[i]!, a[i + 2]!, -a[i + 1]!, b[j]!, b[j + 2]!, -b[j + 1]!], edged * 6);
    edged++;
  };
  /** A ring of a member's section: four corners (12 numbers), then for each corner metres along, across and through its timber (12 more). */
  type Ring = Float64Array;
  /** One face between corners of two rings, flat: two triangles, with where each corner lies in the timber for its grain. */
  const face = (m: number, a: Ring, i: number, b: Ring, j: number, c: Ring, k: number, d: Ring, l: number) => {
    const [ux, uy, uz] = [b[j * 3]! - a[i * 3]!, b[j * 3 + 1]! - a[i * 3 + 1]!, b[j * 3 + 2]! - a[i * 3 + 2]!];
    const [vx, vy, vz] = [d[l * 3]! - a[i * 3]!, d[l * 3 + 1]! - a[i * 3 + 1]!, d[l * 3 + 2]! - a[i * 3 + 2]!];
    let [nx, ny, nz] = [uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx];
    let size = Math.hypot(nx, ny, nz);
    if (size < 1e-12) {
      // a face that comes to a point at its first corner: its normal is found from the corner opposite
      const [px, py, pz] = [b[j * 3]! - c[k * 3]!, b[j * 3 + 1]! - c[k * 3 + 1]!, b[j * 3 + 2]! - c[k * 3 + 2]!];
      const [qx, qy, qz] = [d[l * 3]! - c[k * 3]!, d[l * 3 + 1]! - c[k * 3 + 1]!, d[l * 3 + 2]! - c[k * 3 + 2]!];
      [nx, ny, nz] = [qy * pz - qz * py, qz * px - qx * pz, qx * py - qy * px];
      size = Math.hypot(nx, ny, nz);
      if (size < 1e-12) return;
    }
    [nx, ny, nz] = [nx / size, ny / size, nz / size];
    if (used + 6 > room) {
      room *= 2;
      const grown = (old: Float32Array, per: number) => {
        const next = new Float32Array(room * per);
        next.set(old);
        return next;
      };
      [position, normal, colour, grain, piece] = [grown(position, 3), grown(normal, 3), grown(colour, 3), grown(grain, 3), grown(piece, 2)];
      hold();
    }
    const corners: [Ring, number][] = [[a, i], [b, j], [c, k], [a, i], [c, k], [d, l]];
    for (const [ring, n] of corners) {
      position.set([ring[n * 3]!, ring[n * 3 + 2]!, -ring[n * 3 + 1]!], used * 3);
      normal.set([nx, nz, -ny], used * 3);
      colour.set([shades[m * 5]!, shades[m * 5 + 1]!, shades[m * 5 + 2]!], used * 3);
      grain.set([ring[12 + n * 3]!, ring[12 + n * 3 + 1]!, ring[12 + n * 3 + 2]!], used * 3);
      piece.set([shades[m * 5 + 3]!, shades[m * 5 + 4]!], used * 2);
      used++;
    }
  };

  /** How squarely a wall crosses member `m` at a station, and how far along the member the skewed wall runs from its centre line to its edge. */
  const wallAt = (now: Stand, m: number, s: number, wall: Plane, halfWidth: number): [number, number] => {
    tour.at(now, m, s / now.pitch[m]!, frame);
    const sine = Math.abs(frame[3]! * wall[3] + frame[4]! * wall[4] + frame[5]! * wall[5]);
    return sine < 1e-6 ? [sine, Infinity] : [sine, (halfWidth * Math.sqrt(Math.max(0, 1 - sine * sine))) / sine];
  };

  function set(now: Stand): void {
    used = 0;
    edged = 0;
    cut = 0;
    uncut = 0;
    // ---- the laps asked of each timber -----------------------------------------------------------------------------
    const asked: { notch: Notch; lap: number }[][] = Array.from({ length: M }, () => []);
    for (let r = 0; r < now.lapCount; r++) {
      const [a, b] = [now.laps[r * 6]!, now.laps[r * 6 + 1]!];
      if (now.there[a]! < 0.999 || now.there[b]! < 0.999) continue;
      // The two were set out as crossing at these points in the nearer state. Where they cross now is looked for
      // close by: between two states both have moved.
      let [fa, fb] = [now.laps[r * 6 + 2]!, now.laps[r * 6 + 3]!];
      let apart = Infinity;
      for (let turn = 0; turn < 4; turn++) {
        tour.at(now, a, fa, here);
        [fb] = tour.nearestOn(now, b, here[0]!, here[1]!, here[2]!, Math.max(now.foot[b]!, fb - 6), fb + 6);
        tour.at(now, b, fb, there);
        const found = tour.nearestOn(now, a, there[0]!, there[1]!, there[2]!, Math.max(now.foot[a]!, fa - 6), fa + 6);
        fa = found[0];
        apart = Math.sqrt(found[1]);
      }
      if (apart > LAP_REACH_M) {
        uncut++;
        continue;
      }
      for (const [m, f, other, g, sign, depth] of [[a, fa, b, fb, -1, now.laps[r * 6 + 4]!], [b, fb, a, fa, 1, now.laps[r * 6 + 5]!]] as const) {
        tour.at(now, m, f, here);
        tour.at(now, other, g, there);
        const mine = file.members[m]!;
        // the plane the two parts meet on is square to both their depths
        let [qx, qy, qz] = [here[6]! + there[6]!, here[7]! + there[7]!, here[8]! + there[8]!];
        const ql = Math.hypot(qx, qy, qz);
        [qx, qy, qz] = ql > 1e-6 ? [qx / ql, qy / ql, qz / ql] : [here[6]!, here[7]!, here[8]!];
        const level = sign * (mine.depth_m / 2 - depth);
        const floor: Plane = [here[0]! + here[6]! * level, here[1]! + here[7]! * level, here[2]! + here[8]! * level, qx, qy, qz];
        // its walls are the other member's sides, a clearance off
        const across = here[3]! * there[9]! + here[4]! * there[10]! + here[5]! * there[11]!;
        const sine = Math.max(Math.abs(across), 0.2);
        const way = across > 0 ? 1 : -1;
        const halfGap = file.members[other]!.width_m / 2 + clearance;
        const middle = [(here[0]! + there[0]!) / 2, (here[1]! + there[1]!) / 2, (here[2]! + there[2]!) / 2];
        const wall = (side: number): Plane => [middle[0]! + side * way * halfGap * there[9]!, middle[1]! + side * way * halfGap * there[10]!, middle[2]! + side * way * halfGap * there[11]!, there[9]!, there[10]!, there[11]!];
        const s = f * now.pitch[m]!;
        asked[m]!.push({ notch: { lo: s - halfGap / sine, hi: s + halfGap / sine, face: sign, floor, loWall: wall(-1), hiWall: wall(1) }, lap: r });
      }
    }

    // ---- how much of each timber is drawn ------------------------------------------------------------------------
    const shapes = file.members.map((member, m) => {
      const present = now.there[m]!;
      if (present < 0.002) return null;
      const ring = tour.closed[m]!;
      const pitch = now.pitch[m]!;
      // a ring that comes or goes thins; a rib is drawn out from, or back to, its head
      const [hw, hd] = [(member.width_m / 2) * (ring ? present : 1), (member.depth_m / 2) * (ring ? present : 1)];
      const whole = present > 0.999;
      const f0 = ring ? 0 : member.from_head ? Math.max(now.foot[m]!, N - 1 - present * (N - 1 - now.foot[m]!)) : 0;
      const f1 = ring ? N : N - 1;
      const startCut = !ring && whole && Math.hypot(now.ends[m * 6]!, now.ends[m * 6 + 1]!, now.ends[m * 6 + 2]!) > 0.5;
      const endCut = !ring && Math.hypot(now.ends[m * 6 + 3]!, now.ends[m * 6 + 4]!, now.ends[m * 6 + 5]!) > 0.5;
      return { member, ring, pitch, hw, hd, f0, f1, s0: f0 * pitch, s1: f1 * pitch, startCut, endCut };
    });

    // ---- the laps that can be cut: bower/member.py, fit_notches ---------------------------------------------------
    // A lap that cannot be stepped into one of its two members is left uncut in both, and every member's laps are
    // fitted again without it, until all that remain can be cut in both: as bower/joints.py does for this model.
    const left = new Set<number>();
    let fits: { notch: Notch; lo: number; hi: number }[][] = [];
    for (let again = true; again; ) {
      again = false;
      fits = shapes.map((shape, m) => {
        const fitted: { notch: Notch; lo: number; hi: number }[] = [];
        if (!shape) return fitted;
        const { ring, hw, s0, s1, startCut, endCut } = shape;
        for (const want of asked[m]!.filter((w) => !left.has(w.lap)).sort((p, q) => p.notch.lo - q.notch.lo)) {
          let notch = want.notch;
          const [sineLo, runLo] = wallAt(now, m, notch.lo, notch.loWall, hw);
          const [sineHi, runHi] = wallAt(now, m, notch.hi, notch.hiWall, hw);
          let [lo, hi] = [notch.lo - runLo - 0.003, notch.hi + runHi + 0.003];
          const clashing = fitted.filter((f) => lo < f.hi + 0.004 && f.lo - 0.004 < hi);
          // too oblique to have walls, too near an end, or opposite a lap on the other face, which would cut the member through
          if (Math.min(sineLo, sineHi) < 0.25 || (!ring && (lo < s0 + (startCut ? 0.15 : 0.03) || hi > s1 - (endCut ? 0.15 : 0.03))) || clashing.some((f) => f.notch.face !== notch.face)) {
            left.add(want.lap);
            again = true;
            continue;
          }
          for (const f of clashing) {
            // the same face: one wider lap
            const first = f.notch.lo <= notch.lo ? f.notch : notch;
            const far = notch.hi >= f.notch.hi ? notch : f.notch;
            notch = { lo: first.lo, hi: far.hi, face: notch.face, floor: first.floor, loWall: first.loWall, hiWall: far.hiWall };
            [lo, hi] = [Math.min(lo, f.lo), Math.max(hi, f.hi)];
            fitted.splice(fitted.indexOf(f), 1);
          }
          fitted.push({ notch, lo, hi });
        }
        return fitted;
      });
    }
    uncut += left.size;

    for (let m = 0; m < M; m++) {
      const shape = shapes[m];
      if (!shape) continue;
      const { member, ring, pitch, hw, hd, f0, f1, s0, s1, startCut, endCut } = shape;
      const fitted = fits[m]!;
      cut += fitted.length;

      // ---- its section swept through its rings: bower/member.py, sweep ------------------------------------------
      const rings: { s: number; plane: Plane | null; step: Notch | null; wall: boolean }[] = [];
      const plain = (s: number) => {
        if (!fitted.some((f) => f.lo < s && s < f.hi)) rings.push({ s, plane: null, step: null, wall: false });
      };
      if (!ring) plain(s0);
      for (let n = Math.floor(f0) + 1; n < f1; n++) plain(n * pitch);
      if (ring) plain(0);
      else plain(s1);
      for (const { notch } of fitted) {
        // a wall is two rings half a millimetre apart on the wall's plane: the full section, then the stepped one
        const sets: [number, Plane, number, Notch | null][] = [[notch.lo, notch.loWall, -1, null], [notch.lo, notch.loWall, 1, notch], [notch.hi, notch.hiWall, -1, notch], [notch.hi, notch.hiWall, 1, null]];
        sets.forEach(([s, wall, nudge, step], order) => {
          tour.at(now, m, s / pitch, frame);
          rings.push({ s: s + order * 1e-9, plane: [wall[0] + frame[3]! * nudge * 0.00025, wall[1] + frame[4]! * nudge * 0.00025, wall[2] + frame[5]! * nudge * 0.00025, wall[3], wall[4], wall[5]], step, wall: true });
        });
      }
      rings.sort((p, q) => p.s - q.s);
      if (rings.length < 2) continue;
      if (startCut) rings[0]!.plane = [0, 0, 0, now.ends[m * 6]!, now.ends[m * 6 + 1]!, now.ends[m * 6 + 2]!];
      if (endCut) rings.at(-1)!.plane = [0, 0, 0, now.ends[m * 6 + 3]!, now.ends[m * 6 + 4]!, now.ends[m * 6 + 5]!];
      const built: Ring[] = [];
      const slid: [number, number][] = []; // the least and the most any corner of a ring was slid along the member
      rings.forEach((at, k) => {
        tour.at(now, m, at.s / pitch, frame);
        const out = new Float64Array(24);
        let [least, most] = [0, 0];
        // an end is cut to a plane through the end of the centre line
        const plane = at.plane && !at.wall ? ([frame[0]!, frame[1]!, frame[2]!, at.plane[3], at.plane[4], at.plane[5]] as Plane) : at.plane;
        // the section's width runs the way the generator has it: width x depth = along
        const corners: [number, number][] = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
        corners.forEach(([sx, sy], c) => {
          const [ex, ey, ez] = [frame[0]! - frame[9]! * sx * hw, frame[1]! - frame[10]! * sx * hw, frame[2]! - frame[11]! * sx * hw];
          let off = sy * hd;
          if (at.step && at.step.face === sy) {
            const fl = at.step.floor;
            off = ((fl[0] - ex) * fl[3] + (fl[1] - ey) * fl[4] + (fl[2] - ez) * fl[5]) / (frame[6]! * fl[3] + frame[7]! * fl[4] + frame[8]! * fl[5]);
          }
          let [x, y, z] = [ex + frame[6]! * off, ey + frame[7]! * off, ez + frame[8]! * off];
          let slide = 0;
          if (plane) {
            const across = frame[3]! * plane[3] + frame[4]! * plane[4] + frame[5]! * plane[5];
            if (Math.abs(across) > 1e-6) {
              slide = Math.max(-CUT_SLIDE_LIMIT_M, Math.min(CUT_SLIDE_LIMIT_M, ((plane[0] - x) * plane[3] + (plane[1] - y) * plane[4] + (plane[2] - z) * plane[5]) / across));
              [x, y, z] = [x + frame[3]! * slide, y + frame[4]! * slide, z + frame[5]! * slide];
            }
          }
          [least, most] = [Math.min(least, slide), Math.max(most, slide)];
          out.set([x, y, z], c * 3);
          // where it lies in its own timber, for the grain: a rib is measured from its head, so its boards stay put as its foot moves
          out.set([(member.from_head ? s1 - at.s : at.s) + slide, sx * hw, off / (member.depth_m / shades[m * 5 + 4]!) + shades[m * 5 + 4]! / 2], 12 + c * 3);
        });
        built[k] = out;
        slid[k] = [least, most];
      });
      // plain rings that a cut end has been slid past are left out, so the mesh does not fold back on itself
      const last = rings.length - 1;
      const [pastStart, pastEnd] = [Math.max(0, slid[0]![1]), Math.max(0, -slid[last]![0])];
      const kept = rings.map((_, k) => k).filter((k) => k === 0 || k === last || rings[k]!.plane || (rings[k]!.s - rings[0]!.s > pastStart + 1e-3 && rings[last]!.s - rings[k]!.s > pastEnd + 1e-3));
      const count = kept.length;
      for (let j = 0; j < (ring ? count : count - 1); j++) {
        const [p, q] = [built[kept[j]!]!, built[kept[(j + 1) % count]!]!];
        for (let k = 0; k < 4; k++) {
          const k2 = (k + 1) % 4;
          face(m, p, k, p, k2, q, k2, q, k);
          edge(p, k * 3, q, k * 3);
        }
        // where the section steps, the edge across the face that is cut
        const [stepP, stepQ] = [rings[kept[j]!]!, rings[kept[(j + 1) % count]!]!];
        if (stepP.wall && stepQ.wall && stepP.step !== stepQ.step) {
          const on = (stepP.step ?? stepQ.step)!.face > 0 ? 2 : 0;
          edge(p, on * 3, p, (on + 1) * 3);
          edge(q, on * 3, q, (on + 1) * 3);
        }
      }
      if (!ring) {
        const [p, q] = [built[kept[0]!]!, built[kept[count - 1]!]!];
        face(m, p, 3, p, 2, p, 1, p, 0);
        face(m, q, 0, q, 1, q, 2, q, 3);
        for (let k = 0; k < 4; k++) {
          edge(p, k * 3, p, ((k + 1) % 4) * 3);
          edge(q, k * 3, q, ((k + 1) % 4) * 3);
        }
      }
    }

    for (const name of ['position', 'normal', 'color', 'grain', 'piece']) (geometry.getAttribute(name) as THREE.BufferAttribute).needsUpdate = true;
    geometry.setDrawRange(0, used);
    drawn.needsUpdate = true;
    edgeGeometry.instanceCount = edged;
    // drawn as the snapshot's timber is: in its own colour, or as paper
    mesh.material = anyOne.mesh.material;
    mesh.receiveShadow = anyOne.mesh.receiveShadow;
  }
  return { set, counts: () => ({ triangles: used / 3, edges: edged, lapsCut: cut, lapsNotCut: uncut }) };
}

// ---- a planting, carried ---------------------------------------------------------------------------------------------
type Organ = { position: [number, number, number]; direction?: [number, number, number]; stemId: string; stemPoint?: number };

/**
 * `steady` is the timber that is there the whole while this planting is drawn: which timbers, and from which point
 * of each rib. A stem point is tied to the nearest of it, so nothing a plant rides comes or goes under it.
 */
function carriedPlanting(tour: Tour, data: RenderData, home: Stand, steady: { stands: Uint8Array; from: Float32Array }) {
  const { N, M } = tour;
  const frame = new Float64Array(12);
  // where each timber is, roughly, so that most need not be looked at for a given point
  const middle = new Float32Array(M * 4);
  for (let m = 0; m < M; m++) {
    let [x, y, z] = [0, 0, 0];
    for (let i = 0; i < N; i++) {
      x += home.C[(m * N + i) * 3]! / N;
      y += home.C[(m * N + i) * 3 + 1]! / N;
      z += home.C[(m * N + i) * 3 + 2]! / N;
    }
    let reach = 0;
    for (let i = 0; i < N; i++) reach = Math.max(reach, Math.hypot(home.C[(m * N + i) * 3]! - x, home.C[(m * N + i) * 3 + 1]! - y, home.C[(m * N + i) * 3 + 2]! - z));
    middle.set([x, y, z, reach], m * 4);
  }
  const memberOf = (x: number, y: number, z: number): [number, number] => {
    let [best, where, least] = [-1, 0, Infinity];
    for (let m = 0; m < M; m++) {
      if (!steady.stands[m] || home.there[m]! < 1) continue;
      const off = Math.hypot(x - middle[m * 4]!, y - middle[m * 4 + 1]!, z - middle[m * 4 + 2]!) - middle[m * 4 + 3]!;
      if (off > 0 && off * off > least) continue;
      const [f, d2] = tour.nearestOn(home, m, x, y, z, Math.max(home.foot[m]!, steady.from[m]!));
      if (d2 < least) [best, where, least] = [m, f, d2];
    }
    return [best, where];
  };

  // every point of every stem, in one run: where it is at home, and what it rides
  const first = new Int32Array(data.stems.length + 1);
  data.stems.forEach((s, i) => (first[i + 1] = first[i]! + s.bornDay.length));
  const points = first[data.stems.length]!;
  const at = new Float32Array(points * 3);
  const member = new Int32Array(points).fill(-1);
  const along = new Float32Array(points);
  const lies = new Float32Array(points * 3);
  const leans = new Float32Array(points * 3);
  /** For a point on no timber: the points before and after it on its own stem that are, or -1. */
  const before = new Int32Array(points).fill(-1);
  const after = new Int32Array(points).fill(-1);
  const local = (x: number, y: number, z: number, out: Float32Array, k: number) => {
    out[k] = x * frame[3]! + y * frame[4]! + z * frame[5]!;
    out[k + 1] = x * frame[6]! + y * frame[7]! + z * frame[8]!;
    out[k + 2] = x * frame[9]! + y * frame[10]! + z * frame[11]!;
  };
  const tie = (g: number) => {
    const [m, f] = memberOf(at[g * 3]!, at[g * 3 + 1]!, at[g * 3 + 2]!);
    member[g] = m;
    along[g] = f;
    tour.at(home, m, f, frame);
    local(at[g * 3]! - frame[0]!, at[g * 3 + 1]! - frame[1]!, at[g * 3 + 2]! - frame[2]!, lies, g * 3);
  };
  const byId = new Map(data.stems.map((s, i) => [s.id, i]));
  /** For a stem with no point on a timber: the point of its parent it springs from, or -1. */
  const springs = new Int32Array(data.stems.length).fill(-1);
  let held = 0;
  data.stems.forEach((s, i) => {
    const n = s.bornDay.length;
    const g0 = first[i]!;
    let any = false;
    for (let k = 0; k < n; k++) {
      const g = g0 + k;
      at.set([s.contact[k * 3]!, s.contact[k * 3 + 1]!, s.contact[k * 3 + 2]!], g * 3);
      const [ax, ay, az] = [s.away[k * 3]!, s.away[k * 3 + 1]!, s.away[k * 3 + 2]!];
      if (ax === 0 && ay === 0 && az === 0) continue;
      tie(g);
      local(ax, ay, az, leans, g * 3);
      any = true;
      held++;
    }
    let last = -1;
    for (let k = 0; k < n; k++) {
      if (member[g0 + k]! >= 0) last = g0 + k;
      else before[g0 + k] = last;
    }
    last = -1;
    for (let k = n - 1; k >= 0; k--) {
      if (member[g0 + k]! >= 0) last = g0 + k;
      else after[g0 + k] = last;
    }
    if (any) return;
    const parent = s.parentId === null ? undefined : byId.get(s.parentId);
    if (parent === undefined) {
      // a stem with nothing to go with goes with the timber its foot is nearest
      tie(g0);
      for (let k = 1; k < n; k++) before[g0 + k] = g0;
      return;
    }
    const p = data.stems[parent]!;
    let [nearest, least] = [0, Infinity];
    for (let k = 0; k < p.bornDay.length; k++) {
      const d2 = (p.contact[k * 3]! - at[g0 * 3]!) ** 2 + (p.contact[k * 3 + 1]! - at[g0 * 3 + 1]!) ** 2 + (p.contact[k * 3 + 2]! - at[g0 * 3 + 2]!) ** 2;
      if (d2 < least) [nearest, least] = [k, d2];
    }
    springs[i] = first[parent]! + nearest;
  });
  // parents before what springs from them
  const depth = new Int32Array(data.stems.length).fill(-1);
  const depthOf = (i: number): number => {
    if (depth[i]! >= 0) return depth[i]!;
    depth[i] = 0; // a stem named as its own ancestor stops here
    const parent = data.stems[i]!.parentId === null ? undefined : byId.get(data.stems[i]!.parentId!);
    return (depth[i] = parent === undefined ? 0 : depthOf(parent) + 1);
  };
  const order = data.stems.map((_, i) => i).sort((a, b) => depthOf(a) - depthOf(b));

  // what stands on a stem: on a point that lies on a timber it keeps its place in that timber's frame; otherwise it goes with its point
  const organs: { of: Organ; point: number; lies: Float32Array; faces: Float32Array | null }[] = [];
  for (const list of [data.leaves, data.flowers, data.fruits, data.appendages] as Organ[][]) {
    for (const organ of list) {
      const i = byId.get(organ.stemId);
      if (i === undefined) continue;
      const s = data.stems[i]!;
      let k = organ.stemPoint ?? -1;
      if (k < 0 || k >= s.bornDay.length) {
        let least = Infinity;
        for (let j = 0; j < s.bornDay.length; j++) {
          const d2 = (s.contact[j * 3]! - organ.position[0]) ** 2 + (s.contact[j * 3 + 1]! - organ.position[1]) ** 2 + (s.contact[j * 3 + 2]! - organ.position[2]) ** 2;
          if (d2 < least) [k, least] = [j, d2];
        }
      }
      const g = first[i]! + k;
      const place = new Float32Array(3);
      let faces: Float32Array | null = null;
      if (member[g]! >= 0) {
        tour.at(home, member[g]!, along[g]!, frame);
        local(organ.position[0] - frame[0]!, organ.position[1] - frame[1]!, organ.position[2] - frame[2]!, place, 0);
        if (organ.direction) local(organ.direction[0], organ.direction[1], organ.direction[2], (faces = new Float32Array(3)), 0);
      } else place.set([organ.position[0] - at[g * 3]!, organ.position[1] - at[g * 3 + 1]!, organ.position[2] - at[g * 3 + 2]!]);
      organs.push({ of: organ, point: g, lies: place, faces });
    }
  }

  const now = new Float32Array(points * 3);
  const frames = new Float32Array(points * 12);
  /** Put every stem and what stands on it where the building now is. Changes `data` in place. */
  function set(stand: Stand): void {
    for (const i of order) {
      const s = data.stems[i]!;
      const g0 = first[i]!;
      const n = s.bornDay.length;
      for (let k = 0; k < n; k++) {
        const g = g0 + k;
        if (member[g]! < 0) continue;
        tour.at(stand, member[g]!, along[g]!, frames, g * 12);
        const f = g * 12;
        for (let c = 0; c < 3; c++) now[g * 3 + c] = frames[f + c]! + lies[g * 3]! * frames[f + 3 + c]! + lies[g * 3 + 1]! * frames[f + 6 + c]! + lies[g * 3 + 2]! * frames[f + 9 + c]!;
        // the way it leans off the timber turns with the timber (nothing, for a point that only goes with one)
        for (let c = 0; c < 3; c++) s.away[k * 3 + c] = leans[g * 3]! * frames[f + 3 + c]! + leans[g * 3 + 1]! * frames[f + 6 + c]! + leans[g * 3 + 2]! * frames[f + 9 + c]!;
      }
      for (let k = 0; k < n; k++) {
        const g = g0 + k;
        if (member[g]! >= 0) continue;
        const [a, b] = [before[g]!, after[g]!];
        const from = a >= 0 ? a : b >= 0 ? b : springs[i]!;
        const t = a >= 0 && b >= 0 ? (g - a) / (b - a) : 0;
        const to = a >= 0 && b >= 0 ? b : from;
        for (let c = 0; c < 3; c++) {
          const moved = from < 0 ? 0 : now[from * 3 + c]! - at[from * 3 + c]! + (now[to * 3 + c]! - at[to * 3 + c]! - (now[from * 3 + c]! - at[from * 3 + c]!)) * t;
          now[g * 3 + c] = at[g * 3 + c]! + moved;
        }
      }
      for (let k = 0; k < n * 3; k++) s.contact[k] = now[g0 * 3 + k]!;
    }
    for (const organ of organs) {
      const g = organ.point;
      const f = g * 12;
      if (member[g]! >= 0) {
        for (let c = 0; c < 3; c++) organ.of.position[c] = frames[f + c]! + organ.lies[0]! * frames[f + 3 + c]! + organ.lies[1]! * frames[f + 6 + c]! + organ.lies[2]! * frames[f + 9 + c]!;
        if (organ.faces && organ.of.direction) for (let c = 0; c < 3; c++) organ.of.direction[c] = organ.faces[0]! * frames[f + 3 + c]! + organ.faces[1]! * frames[f + 6 + c]! + organ.faces[2]! * frames[f + 9 + c]!;
      } else for (let c = 0; c < 3; c++) organ.of.position[c] = now[g * 3 + c]! + organ.lies[c]!;
    }
  }
  return { set, points, held, organs: organs.length };
}

// ---- the drawing ---------------------------------------------------------------------------------------------------
export async function startTour(o: {
  url: URLSearchParams;
  paper: Paper;
  timber: Timber;
  growth: RenderData;
  materials: PlantMaterials;
  plants: PlantView;
  /** Where the approach is seen from and what it looks at, in the building's axes. */
  stand: { eye: readonly number[]; target: readonly number[] };
  planted: number;
}) {
  const file = (await (await fetch(o.url.get('tour')!)).json()) as TourFile;
  const tour = tourOf(file);
  const form = file.forms.find((f) => f.id === o.url.get('form')) ?? file.forms[0]!;
  // how far either side of its own form this planting is drawn, in states (which may run past the ends of a loop)
  const span = (o.url.get('span') ?? '').split(',').map(Number);
  const [from, to] = span.length === 2 && span.every(Number.isFinite) ? (span as [number, number]) : [form.state, form.state];
  const home = tour.stand(form.state);
  const timber = cutTimber(tour, file, o.timber);
  const began = performance.now();
  const planting = carriedPlanting(tour, o.growth, home, tour.throughout(from, to));
  const tiedIn = (performance.now() - began) / 1000;

  for (const name of ['beds', 'cables']) {
    const object = o.paper.scene.getObjectByName(name);
    if (object) object.visible = false;
  }
  const $ = (id: string) => document.getElementById(id)!;
  // no line of time to drag, and no counts: two plantings are laid over each other on the way from form to form
  for (const part of ['.track', '.reading']) {
    const element = document.querySelector<HTMLElement>(part);
    if (element) element.style.visibility = 'hidden';
  }
  if (o.url.get('title')) document.querySelector('.title h1')!.textContent = o.url.get('title');
  if (o.url.get('subtitle')) $('subtitle').textContent = o.url.get('subtitle');
  $('statement').textContent = `${o.growth.statement} The timber is concept geometry, lapped as the generator sets out for each form; its colour is illustrative. A planting was grown on each form named; between forms the plants are carried, not grown.`;

  const start = Date.parse(`${o.growth.start}T00:00:00Z`);
  const now = tour.stand(form.state);
  const under = tour.stand(form.state);
  let plants = o.plants;
  let drawnAt = form.state;
  let made = 0;
  const offset = new THREE.Vector3(o.stand.eye[0]! - o.stand.target[0]!, o.stand.eye[2]! - o.stand.target[2]!, -(o.stand.eye[1]! - o.stand.target[1]!));
  const target = new THREE.Vector3(o.stand.target[0]!, o.stand.target[2]!, -o.stand.target[1]!);
  const sunInView = new THREE.Vector3();
  timber.set(now);

  return {
    forms: file.forms,
    states: tour.S,
    loop: file.loop,
    tied: { points: planting.points, onTimber: planting.held, organs: planting.organs, seconds: tiedIn },
    made: () => made,
    timber: () => timber.counts(),
    /**
     * One picture: the building at `at` on the tour (a state by number, or between two), on `day` of the planting,
     * seen from `yaw` degrees round from where the approach stands, `back` times as far off and `lift` metres higher.
     * `title` is what is said of the form; `seconds` is how long since the picture before, for what sways.
     */
    async frame(p: { at: number; day: number; yaw?: number; back?: number; lift?: number; title?: string; seconds?: number; view?: 'approach' | 'drawing'; zoom?: number }) {
      if (p.at !== drawnAt) {
        tour.stand(p.at, now);
        timber.set(now);
        // the planting counts states from its own form: round a loop, the same place may be past the last state for it
        const mine = file.loop ? p.at + tour.S * Math.round((form.state - p.at) / tour.S) : p.at;
        planting.set(mine === p.at ? now : tour.stand(mine, under));
        o.paper.scene.remove(plants.group);
        plants.dispose();
        plants = new PlantView(o.growth, o.materials);
        o.paper.scene.add(plants.group);
        drawnAt = p.at;
        made++;
      }
      const view = p.view ?? 'approach';
      if (o.paper.view() !== view) o.paper.setView(view);
      const yaw = THREE.MathUtils.degToRad(p.yaw ?? 0);
      if (view === 'approach') {
        const camera = o.paper.camera();
        camera.position.copy(offset).multiplyScalar(p.back ?? 1).applyAxisAngle(new THREE.Vector3(0, 1, 0), yaw).add(target);
        camera.position.y += p.lift ?? 0;
      } else {
        const side = toB(offset.clone().applyAxisAngle(new THREE.Vector3(0, 1, 0), yaw));
        o.paper.focus(null, p.zoom ?? 1, side);
      }
      o.paper.step();
      const camera = o.paper.camera();
      camera.updateMatrixWorld(true);
      shared.uTime.value += p.seconds ?? 0;
      shared.uSunColor.value.copy(o.paper.sun.color).multiplyScalar(o.paper.sun.intensity * 0.32);
      shared.uSunDirWorld.value.copy(o.paper.sunDir);
      shared.uSunDirView.value.copy(sunInView.copy(o.paper.sunDir).transformDirection(camera.matrixWorldInverse));
      clock.uDay.value = p.day;
      plants.group.visible = true;
      plants.update(o.paper.detailFrom(), p.day, 1);
      o.timber.setAge((p.day - o.planted) / 365.25);
      const when = new Date(start + Math.floor(p.day) * DAY_MS);
      $('date').textContent = `${MONTHS[when.getUTCMonth()]} ${when.getUTCFullYear()}`;
      $('age').textContent = p.title ?? form.title;
      o.paper.resize();
      o.paper.shadeChanged();
      o.paper.render();
      await new Promise((shown) => requestAnimationFrame(() => requestAnimationFrame(shown)));
    },
  };
}
