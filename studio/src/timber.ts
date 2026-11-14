// The timber, as a drawing: every member filled with paper, so that it hides what is behind it, and every edge
// of it (its four long arrises, its ends and each milled joint) drawn in ink.
import * as THREE from 'three';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { INK, MUTED, PAPER } from './paper.ts';

export interface Member {
  id: string;
  family: string;
  mesh: THREE.Mesh;
  /** This member's edges, as pairs of points where it stands in the building. */
  edges: number[];
}

export interface Timber {
  group: THREE.Group;
  bounds: THREE.Box3;
  members: Map<string, Member>;
  ink: LineMaterial;
  /** Every member's edges as one object: what is drawn once the building stands. */
  lines: LineSegments2;
}

/** Two faces meeting at more than this are an edge to draw; less, and they are one curved face. */
const CREASE_DEG = 28;

export async function loadTimber(url: string): Promise<Timber> {
  const gltf = await new GLTFLoader().loadAsync(url);
  gltf.scene.updateMatrixWorld(true);
  const fill = new THREE.MeshBasicMaterial({ color: PAPER, toneMapped: false, polygonOffset: true, polygonOffsetFactor: 1.5, polygonOffsetUnits: 2 });

  const members = new Map<string, Member>();
  const all: number[] = [];
  const v = new THREE.Vector3();
  gltf.scene.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.material = fill;
    mesh.castShadow = true;
    const creases = new THREE.EdgesGeometry(mesh.geometry, CREASE_DEG);
    const p = creases.getAttribute('position');
    const edges: number[] = [];
    for (let i = 0; i < p.count; i++) {
      v.fromBufferAttribute(p, i).applyMatrix4(mesh.matrixWorld);
      edges.push(v.x, v.y, v.z);
    }
    creases.dispose();
    for (const c of edges) all.push(c);
    const id = String(mesh.userData['bower_id'] ?? mesh.name);
    members.set(id, { id, family: String(mesh.userData['bower_family'] ?? ''), mesh, edges });
  });

  const ink = new LineMaterial({ color: INK, linewidth: 1, toneMapped: false });
  const lines = new LineSegments2(new LineSegmentsGeometry().setPositions(all), ink);
  lines.frustumCulled = false;
  lines.name = 'timber ink';

  const group = new THREE.Group();
  group.name = 'timber';
  group.add(gltf.scene, lines);
  return { group, bounds: new THREE.Box3().setFromObject(gltf.scene), members, ink, lines };
}

/** Where plants go into the ground: a ring of thin line at each bed. */
export function drawBeds(stations: readonly { position: readonly number[] }[], radiusM = 0.34): THREE.Object3D {
  const positions: number[] = [];
  const steps = 40;
  for (const s of stations) {
    const [x, y, z] = s.position as [number, number, number];
    for (let i = 0; i < steps; i++) {
      const a0 = (i / steps) * Math.PI * 2;
      const a1 = ((i + 1) / steps) * Math.PI * 2;
      positions.push(x + radiusM * Math.cos(a0), z + 0.004, -(y + radiusM * Math.sin(a0)), x + radiusM * Math.cos(a1), z + 0.004, -(y + radiusM * Math.sin(a1)));
    }
  }
  const object = new LineSegments2(new LineSegmentsGeometry().setPositions(positions), new LineMaterial({ color: MUTED, linewidth: 0.8, toneMapped: false }));
  object.frustumCulled = false;
  object.name = 'beds';
  return object;
}
