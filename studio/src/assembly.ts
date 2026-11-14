// The building going together: first its centre lines, which are the design, drawn on in thin broken line;
// then each member brought on to its line, in the order the joints allow (pipeline/assemble.mjs).
//
// The factory drawings keep one red for what is moving. A member is drawn in it while it travels and turns to
// ink as it seats.
import * as THREE from 'three';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { MUTED } from './paper.ts';
import type { Timber } from './timber.ts';

export interface AssemblyPlan {
  note: string;
  joints: number;
  members: { id: string; family: string; lengthM: number; jointsMade: number; from: number[]; line: number[][] }[];
}

export interface AssemblyState {
  phase: 'design' | 'assembly' | 'built';
  placed: number;
  of: number;
  jointsMade: number;
  joints: number;
  /** The family of the member most lately brought on. */
  family: string;
}

const MOVING = 0xb4492f;
/** The share of the whole sequence in which the centre lines are drawn, before any timber arrives. */
export const DESIGN_SHARE = 0.12;
/** How many centre lines are being drawn at any moment. */
const LINES_AT_ONCE = 7;
/** How long one member takes to arrive, as a share of the whole sequence. */
const ARRIVAL_SHARE = 0.06;
/** More members than are ever in the air together. */
const IN_THE_AIR = 16;

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

export function makeAssembly(timber: Timber, plan: AssemblyPlan) {
  const group = new THREE.Group();
  group.name = 'assembly';
  const centreLine = new LineMaterial({ color: MUTED, linewidth: 0.75, dashed: true, dashSize: 0.2, gapSize: 0.11, toneMapped: false });
  const moving = Array.from({ length: IN_THE_AIR }, () => new LineMaterial({ color: MOVING, linewidth: 1.2, transparent: true, toneMapped: false }));

  const parts = plan.members.map((p) => {
    const member = timber.members.get(p.id);
    if (!member) throw new Error(`the assembly names "${p.id}", which the timber does not have`);
    const edges = new LineSegments2(new LineSegmentsGeometry().setPositions(member.edges), timber.ink);
    edges.frustumCulled = false;
    const pairs: number[] = [];
    for (let i = 0; i + 1 < p.line.length; i++) {
      const a = p.line[i]!;
      const b = p.line[i + 1]!;
      pairs.push(a[0]!, a[2]!, -a[1]!, b[0]!, b[2]!, -b[1]!);
    }
    const line = new LineSegments2(new LineSegmentsGeometry().setPositions(pairs), centreLine);
    line.computeLineDistances();
    line.frustumCulled = false;
    group.add(edges, line);
    return { family: p.family, jointsMade: p.jointsMade, mesh: member.mesh, edges, line, segments: p.line.length - 1, away: new THREE.Vector3(p.from[0]!, p.from[2]!, -p.from[1]!) };
  });
  const n = parts.length;

  /** Put the building at `progress` through its assembly: 0 nothing drawn, DESIGN_SHARE every centre line, 1 standing. */
  function set(progress: number): AssemblyState {
    const p = clamp01(progress);
    const built = p >= 1;
    timber.lines.visible = built;
    group.visible = !built;
    let placed = 0;
    let latest = -1;
    let inTheAir = 0;
    for (let i = 0; i < n; i++) {
      const part = parts[i]!;
      const start = DESIGN_SHARE + (1 - DESIGN_SHARE - ARRIVAL_SHARE) * (i / Math.max(1, n - 1));
      const t = built ? 1 : clamp01((p - start) / ARRIVAL_SHARE);
      if (t >= 1) {
        part.mesh.visible = true;
        part.mesh.position.set(0, 0, 0);
        part.edges.visible = !built;
        part.edges.position.set(0, 0, 0);
        part.edges.material = timber.ink;
        part.line.visible = false;
        placed++;
        latest = i;
        continue;
      }
      // its centre line, drawn from one end to the other
      const drawn = clamp01(((p / DESIGN_SHARE) * (n + LINES_AT_ONCE - 1) - i) / LINES_AT_ONCE);
      part.line.visible = drawn > 0;
      part.line.geometry.instanceCount = Math.ceil(drawn * part.segments);
      if (t <= 0) {
        part.mesh.visible = false;
        part.edges.visible = false;
        continue;
      }
      // on its way in: quick at first, settling on to its line
      const settle = 1 - (1 - t) ** 3;
      part.mesh.visible = t > 0.18;
      part.mesh.position.copy(part.away).multiplyScalar(1 - settle);
      part.edges.visible = true;
      part.edges.position.copy(part.mesh.position);
      const red = moving[inTheAir++ % IN_THE_AIR]!;
      red.opacity = clamp01(t / 0.3);
      part.edges.material = red;
      latest = i;
    }
    return {
      // it is the design until the first member is on its way
      phase: built ? 'built' : latest < 0 ? 'design' : 'assembly',
      placed,
      of: n,
      jointsMade: placed ? parts[placed - 1]!.jointsMade : 0,
      joints: plan.joints,
      family: latest >= 0 ? parts[latest]!.family : (parts[0]?.family ?? ''),
    };
  }

  return { group, set, note: plan.note };
}
