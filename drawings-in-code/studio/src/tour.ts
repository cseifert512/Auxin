// A turn through the forms the room can take, with a planting on it: the timber moved from state to state, and the
// plants of one grown planting carried on it.
//
// Three things are true of what this draws, and they go under any picture made from it.
//   The timber between two forms is the generator's own: every state is built by bower-blender, and a timber is
//   moved point by point between one state and the next. The meshes moved are the snapshot's milled ones, so a
//   joint cut for one form is drawn on all of them; only the snapshot's own form is as the mill would cut it.
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
  loop: boolean;
  between: number;
  /** Each is one timber followed through the tour by where it stands; `mesh` is the snapshot's member it is, if it stands in the snapshot. */
  members: { id: string; kind: string; family: string; width_m: number; depth_m: number; closed: boolean; from_head: boolean; mesh: string | null }[];
  /** Round a loop, which timber each has become by the first state again, where that is not itself (-1: none). */
  wrap?: number[];
  forms: { id: string; title: string; state: number; grown_on: string }[];
  states: { values: Record<string, number>; has: number[]; mm: number[]; axes: number[] }[];
}

const DAY_MS = 86_400_000;
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
/** A timber missing from this many states in a row or fewer is taken to be there throughout, and drawn between its neighbours. */
const BRIEF_GAP = 2;
/** The points of a rib nearest its foot that are drawn out with it when it runs on further than the snapshot's did. */
const FOOT_POINTS = 2.5;

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
}

function tourOf(file: TourFile) {
  const N = file.samples;
  const M = file.members.length;
  const S = file.states.length;
  const closed = file.members.map((m) => m.closed);
  const pos: Float32Array[] = [];
  const axis: Float32Array[] = [];
  const has: Uint8Array[] = [];
  for (const state of file.states) {
    const p = new Float32Array(M * N * 3);
    const a = new Float32Array(M * N * 3);
    const h = new Uint8Array(M);
    state.has.forEach((m, k) => {
      h[m] = 1;
      for (let i = 0; i < N * 3; i++) {
        p[m * N * 3 + i] = state.mm[k * N * 3 + i]! / 1000;
        a[m * N * 3 + i] = state.axes[k * N * 3 + i]! / 10000;
      }
    });
    pos.push(p);
    axis.push(a);
    has.push(h);
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
    const o = out ?? { C: new Float32Array(M * N * 3), F: new Float32Array(M * N * 9), there: new Float32Array(M), foot: new Float32Array(M) };
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
      const [a, b] = [(mi >= 0 ? mi : mj) * N * 3, (mj >= 0 ? mj : mi) * N * 3];
      if (a < 0 || b < 0) continue;
      const c = m * N * 3;
      for (let k = 0; k < N * 3; k++) C[c + k] = pa[a + k]! + (pb[b + k]! - pa[a + k]!) * t;
      o.foot[m] = footOf(C, m, m);
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
    return o;
  }

  /** The place and frame at `f` samples along timber `m`, written into `out` (3 for the place, then 9). */
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
   * How far along timber `m` the point of its centre line nearest (x, y, z) is, in samples, and the square of how
   * far off. Only the part of it from `from` on is looked at: by default, all that is not a rib's foot over again.
   */
  function nearestOn(s: Stand, m: number, x: number, y: number, z: number, from = s.foot[m]!): [number, number] {
    let best = from;
    let least = Infinity;
    const segments = closed[m] ? N : N - 1;
    for (let i = Math.min(segments - 1, Math.floor(from)); i < segments; i++) {
      const a = (m * N + i) * 3;
      const b = (m * N + ((i + 1) % N)) * 3;
      const [ax, ay, az] = [s.C[a]!, s.C[a + 1]!, s.C[a + 2]!];
      const [ux, uy, uz] = [s.C[b]! - ax, s.C[b + 1]! - ay, s.C[b + 2]! - az];
      const uu = ux * ux + uy * uy + uz * uz;
      const t = uu > 0 ? Math.min(1, Math.max(0, ((x - ax) * ux + (y - ay) * uy + (z - az) * uz) / uu)) : 0;
      const d2 = (x - ax - ux * t) ** 2 + (y - ay - uy * t) ** 2 + (z - az - uz * t) ** 2;
      if (d2 < least) {
        least = d2;
        best = i + t;
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

// ---- the timber, moved --------------------------------------------------------------------------------------------
function movedTimber(tour: Tour, file: TourFile, timber: Timber, home: Stand) {
  const { N } = tour;
  const frame = new Float64Array(12);
  const v = new THREE.Vector3();
  const n = new THREE.Vector3();
  /** A point in the drawing's axes, as where it lies in timber `m`: samples along, then its place in the frame there. */
  const lay = (m: number, p: THREE.Vector3, out: Float32Array, k: number): number => {
    const [x, y, z] = toB(p);
    const [f] = tour.nearestOn(home, m, x, y, z);
    tour.at(home, m, f, frame);
    const [ox, oy, oz] = [x - frame[0]!, y - frame[1]!, z - frame[2]!];
    out[k] = ox * frame[3]! + oy * frame[4]! + oz * frame[5]!;
    out[k + 1] = ox * frame[6]! + oy * frame[7]! + oz * frame[8]!;
    out[k + 2] = ox * frame[9]! + oy * frame[10]! + oz * frame[11]!;
    return f;
  };

  // which of the tour's timbers each of the snapshot's meshes is
  const owner = new Map<string, number>();
  file.members.forEach((member, m) => {
    if (member.mesh) owner.set(member.mesh, m);
  });
  const numberOf = (id: string) => Number(id.split('@')[0]!.match(/\d+$/)?.[0] ?? 0);
  const pieces: { m: number; like: number; mesh: THREE.Mesh; along: Float32Array; lies: Float32Array; faces: Float32Array; back: THREE.Matrix4; turnBack: THREE.Matrix3; edgeAlong: Float32Array; edgeLies: Float32Array; edgeAt: number; keepFirst: boolean }[] = [];
  let edgeCount = 0;
  file.members.forEach((member, m) => {
    let from = member.mesh ? timber.members.get(member.mesh) : undefined;
    let like = m;
    if (!from) {
      // a timber the snapshot does not have is drawn with the milled mesh of the nearest one of its kind
      const near = file.members
        .filter((x) => x.mesh && x.kind === member.kind && timber.members.has(x.mesh))
        .sort((a, b) => Math.abs(numberOf(a.id) - numberOf(member.id)) - Math.abs(numberOf(b.id) - numberOf(member.id)))[0];
      if (!near) return;
      const source = timber.members.get(near.mesh!)!;
      const mesh = new THREE.Mesh(source.mesh.geometry.clone(), source.mesh.material);
      mesh.castShadow = true;
      mesh.receiveShadow = source.mesh.receiveShadow;
      source.mesh.parent!.add(mesh);
      mesh.matrix.copy(source.mesh.matrix);
      mesh.matrix.decompose(mesh.position, mesh.quaternion, mesh.scale);
      mesh.updateMatrixWorld(true);
      from = { id: member.id, family: source.family, mesh, edges: [...source.edges] };
      timber.members.set(member.id, from);
      like = owner.get(near.mesh!)!;
    }
    const mesh = from.mesh;
    mesh.frustumCulled = false;
    const position = mesh.geometry.getAttribute('position');
    const normal = mesh.geometry.getAttribute('normal');
    const along = new Float32Array(position.count);
    const lies = new Float32Array(position.count * 3);
    const faces = new Float32Array(position.count * 3);
    const turn = new THREE.Matrix3().getNormalMatrix(mesh.matrixWorld);
    for (let k = 0; k < position.count; k++) {
      along[k] = lay(like, v.fromBufferAttribute(position, k).applyMatrix4(mesh.matrixWorld), lies, k * 3);
      if (normal) {
        const [x, y, z] = toB(n.fromBufferAttribute(normal, k).applyMatrix3(turn).normalize());
        tour.at(home, like, along[k]!, frame);
        faces.set([x * frame[3]! + y * frame[4]! + z * frame[5]!, x * frame[6]! + y * frame[7]! + z * frame[8]!, x * frame[9]! + y * frame[10]! + z * frame[11]!], k * 3);
      }
    }
    const ends = from.edges.length / 3;
    const edgeAlong = new Float32Array(ends);
    const edgeLies = new Float32Array(ends * 3);
    for (let k = 0; k < ends; k++) edgeAlong[k] = lay(like, v.set(from.edges[k * 3]!, from.edges[k * 3 + 1]!, from.edges[k * 3 + 2]!), edgeLies, k * 3);
    // a timber that comes or goes is drawn out from, or back to, its upper end
    const keepFirst = home.C[like * N * 3 + 2]! >= home.C[(like * N + N - 1) * 3 + 2]!;
    pieces.push({ m, like, mesh, along, lies, faces, back: new THREE.Matrix4().copy(mesh.matrixWorld).invert(), turnBack: new THREE.Matrix3().setFromMatrix4(mesh.matrixWorld).invert(), edgeAlong, edgeLies, edgeAt: edgeCount, keepFirst });
    edgeCount += ends;
  });

  const segments = new Float32Array(edgeCount * 3);
  const geometry = new LineSegmentsGeometry().setPositions(segments);
  const lines = new LineSegments2(geometry, timber.ink);
  lines.frustumCulled = false;
  lines.name = 'timber ink, moved';
  timber.lines.visible = false;
  timber.group.add(lines);
  const drawn = (geometry.getAttribute('instanceStart') as THREE.InterleavedBufferAttribute).data;

  function set(now: Stand): void {
    for (const piece of pieces) {
      const there = now.there[piece.m]!;
      piece.mesh.visible = there > 0.002;
      const ring = tour.closed[piece.m]!;
      const rib = file.members[piece.m]!.from_head;
      // a ring cannot be drawn out or back, so it thins instead
      const thin = ring ? there : 1;
      const [footNow, footHome] = [now.foot[piece.m]!, home.foot[piece.like]!];
      const place = (f: number, lies: Float32Array, k: number, out: Float32Array, to: number, back: THREE.Matrix4 | null) => {
        let g = f;
        let flat = false;
        if (rib) {
          // Counted from its head, a rib is where it was as far down as the snapshot's ran. Where it now runs on
          // further, the last of the snapshot's mesh is drawn out to its new foot; where it stops short, or is only
          // part there, what would lie beyond is gathered at its end.
          if (f < footHome + FOOT_POINTS) g = footNow + ((f - footHome) * Math.max(0, footHome + FOOT_POINTS - footNow)) / FOOT_POINTS;
          const end = Math.max(footNow, N - 1 - there * (N - 1 - footNow));
          if (g < end) {
            g = end;
            flat = true;
          }
        } else if (!ring && there < 1) {
          const cut = there * (N - 1);
          if ((piece.keepFirst ? f : N - 1 - f) > cut) {
            g = piece.keepFirst ? cut : N - 1 - cut;
            flat = true;
          }
        }
        tour.at(now, piece.m, g, frame);
        const [a, b, c] = [flat ? 0 : lies[k]!, lies[k + 1]! * thin, lies[k + 2]! * thin];
        const x = frame[0]! + a * frame[3]! + b * frame[6]! + c * frame[9]!;
        const y = frame[1]! + a * frame[4]! + b * frame[7]! + c * frame[10]!;
        const z = frame[2]! + a * frame[5]! + b * frame[8]! + c * frame[11]!;
        v.set(x, z, -y);
        if (back) v.applyMatrix4(back);
        out[to] = v.x;
        out[to + 1] = v.y;
        out[to + 2] = v.z;
      };
      if (piece.mesh.visible) {
        const position = piece.mesh.geometry.getAttribute('position') as THREE.BufferAttribute;
        const normal = piece.mesh.geometry.getAttribute('normal') as THREE.BufferAttribute | undefined;
        const p = position.array as Float32Array;
        for (let k = 0; k < position.count; k++) {
          place(piece.along[k]!, piece.lies, k * 3, p, k * 3, piece.back);
          if (normal) {
            // `frame` is still the one this corner was placed in
            const [a, b, c] = [piece.faces[k * 3]!, piece.faces[k * 3 + 1]!, piece.faces[k * 3 + 2]!];
            n.set(a * frame[3]! + b * frame[6]! + c * frame[9]!, a * frame[5]! + b * frame[8]! + c * frame[11]!, -(a * frame[4]! + b * frame[7]! + c * frame[10]!)).applyMatrix3(piece.turnBack).normalize();
            (normal.array as Float32Array).set([n.x, n.y, n.z], k * 3);
          }
        }
        position.needsUpdate = true;
        if (normal) normal.needsUpdate = true;
      }
      const ends = piece.edgeAlong.length;
      for (let k = 0; k < ends; k++) {
        if (piece.mesh.visible) place(piece.edgeAlong[k]!, piece.edgeLies, k * 3, drawn.array as Float32Array, (piece.edgeAt + k) * 3, null);
        else (drawn.array as Float32Array).fill(0, (piece.edgeAt + k) * 3, (piece.edgeAt + k) * 3 + 3);
      }
    }
    drawn.needsUpdate = true;
  }
  return { set, pieces: pieces.length };
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
  // the milled meshes are the snapshot's: they are tied to the form that is the snapshot
  const timber = movedTimber(tour, file, o.timber, tour.stand(file.forms.find((f) => f.grown_on === file.snapshot)?.state ?? 0));
  const began = performance.now();
  const planting = carriedPlanting(tour, o.growth, home, tour.throughout(from, to));
  const tiedIn = (performance.now() - began) / 1000;

  for (const name of ['beds', 'cables']) {
    const object = o.paper.scene.getObjectByName(name);
    if (object) object.visible = false;
  }
  const $ = (id: string) => document.getElementById(id)!;
  // no line of time to drag, and no counts: two plantings are laid over each other on the way from form to form
  for (const part of ['.track', '.reading']) document.querySelector<HTMLElement>(part)!.style.visibility = 'hidden';
  if (o.url.get('title')) document.querySelector('.title h1')!.textContent = o.url.get('title');
  if (o.url.get('subtitle')) $('subtitle').textContent = o.url.get('subtitle');
  $('statement').textContent = `${o.growth.statement} The timber is concept geometry, moved between forms the generator builds; its colour is illustrative. A planting was grown on each form named; between two forms the plants are carried on the timber, not grown.`;

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
    tied: { points: planting.points, onTimber: planting.held, organs: planting.organs, seconds: tiedIn, timberPieces: timber.pieces },
    made: () => made,
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
