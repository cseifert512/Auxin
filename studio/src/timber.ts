// The timber, drawn two ways.
//
//   ink     every member filled with paper, so that it hides what is behind it, and every edge of it (its four
//           long arrises, its ends and each milled joint) drawn in ink: the factory drawings' way
//   wood    the same edges over timber in its own colour, lit by the sun the plants are lit by and taking their
//           shade; its colour held by a finish that is kept up, deepening with the years
//   bare    the same, left unfinished to go silver
//
// Both are pictures of how softwood is said to age, not models of it, and the first takes for granted a pigmented
// finish that someone goes on renewing. The species and finish of the real timber are not decided.
import * as THREE from 'three';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { INK, MUTED, PAPER } from './paper.ts';

export type TimberLook = 'wood' | 'bare' | 'ink';

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
  setLook(look: TimberLook): void;
  /** Years the timber has stood in the weather. */
  setAge(years: number): void;
}

/** Two faces meeting at more than this are an edge to draw; less, and they are one curved face. */
const CREASE_DEG = 28;
/** Freshly planed softwood glulam, and the same wood weathered. */
const FRESH = 0xcf9f66;
const SILVERED = 0xb3aa9a;
/** The training lines when they are marked for looking at: the factory drawings' green for what is Bower's own. */
const MARKED = 0x2a6a50;
/** The line that edges coloured timber: the ink, warmed. */
const WOOD_LINE = 0x33261b;
/** Years for a face turned full to the sky to go about two thirds of the way to silver. */
const WEATHERING_YEARS = 1.1;

/** A number between 0 and 1 from a name: the same member always gets the same shade. */
function shadeOf(id: string): number {
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) h = Math.imul(h ^ id.charCodeAt(i), 16777619);
  return ((h >>> 0) % 1000) / 999;
}

/**
 * How the colour goes with the years, two ways.
 *   kept   under a pigmented finish that is kept up, the colour holds: it deepens over the first few years, and
 *          only the faces most open to the weather grey a little, slowly
 *   bare   left unfinished, faces turned up go silver within a year or two, upright faces follow, undersides last
 */
const AGEING = {
  kept: { greyMost: 0.32, greyYears: 6, deepens: 0.7 },
  bare: { greyMost: 1, greyYears: WEATHERING_YEARS, deepens: 0.15 },
};

function makeWood(years: { value: number }) {
  const ageing = { greyMost: { value: 0 }, greyYears: { value: 1 }, deepens: { value: 0 } };
  const wood = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.84, metalness: 0, polygonOffset: true, polygonOffsetFactor: 1.5, polygonOffsetUnits: 2 });
  wood.onBeforeCompile = (shader) => {
    shader.uniforms['uYears'] = years;
    shader.uniforms['uSilvered'] = { value: new THREE.Color(SILVERED) };
    shader.uniforms['uGreyMost'] = ageing.greyMost;
    shader.uniforms['uGreyYears'] = ageing.greyYears;
    shader.uniforms['uDeepens'] = ageing.deepens;
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform float uYears, uGreyMost, uGreyYears, uDeepens;\nuniform vec3 uSilvered;')
      .replace(
        '#include <color_fragment>',
        /* glsl */ `#include <color_fragment>
        {
          // which way the face is turned, in the world: up to the weather, upright, or down and sheltered
          vec3 faceW = normalize( ( vec4( normalize( vNormal ), 0.0 ) * viewMatrix ).xyz );
          float open = 0.12 + 0.88 * smoothstep( -0.6, 0.9, faceW.y );
          // new timber is pale: light deepens it towards amber over its first years
          vec3 deep = diffuseColor.rgb * vec3( 0.86, 0.74, 0.6 );
          diffuseColor.rgb = mix( diffuseColor.rgb, deep, uDeepens * ( 1.0 - exp( - uYears / 2.5 ) ) );
          float weathered = uGreyMost * ( 1.0 - exp( - uYears * open / uGreyYears ) );
          // each piece keeps a little of its own shade as it greys
          vec3 grey = uSilvered * ( 0.9 + 0.2 * dot( diffuseColor.rgb, vec3( 0.6, 0.9, 0.5 ) ) );
          diffuseColor.rgb = mix( diffuseColor.rgb, grey, weathered );
        }`,
      );
  };
  return {
    wood,
    age(as: keyof typeof AGEING): void {
      ageing.greyMost.value = AGEING[as].greyMost;
      ageing.greyYears.value = AGEING[as].greyYears;
      ageing.deepens.value = AGEING[as].deepens;
    },
  };
}

export async function loadTimber(url: string): Promise<Timber> {
  const gltf = await new GLTFLoader().loadAsync(url);
  gltf.scene.updateMatrixWorld(true);
  const paper = new THREE.MeshBasicMaterial({ color: PAPER, toneMapped: false, polygonOffset: true, polygonOffsetFactor: 1.5, polygonOffsetUnits: 2 });
  const years = { value: 0 };
  const { wood, age } = makeWood(years);

  const members = new Map<string, Member>();
  const all: number[] = [];
  const v = new THREE.Vector3();
  const tone = new THREE.Color();
  gltf.scene.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.castShadow = true;
    const id = String(mesh.userData['bower_id'] ?? mesh.name);

    const creases = new THREE.EdgesGeometry(mesh.geometry, CREASE_DEG);
    const p = creases.getAttribute('position');
    const edges: number[] = [];
    for (let i = 0; i < p.count; i++) {
      v.fromBufferAttribute(p, i).applyMatrix4(mesh.matrixWorld);
      edges.push(v.x, v.y, v.z);
    }
    creases.dispose();
    for (const c of edges) all.push(c);

    // no two pieces of timber are one colour: each member a little lighter or darker, a little redder or yellower
    const shade = shadeOf(id);
    tone.setHex(FRESH).offsetHSL((shadeOf(`${id}:hue`) - 0.5) * 0.02, 0, (shade - 0.5) * 0.09);
    const count = mesh.geometry.getAttribute('position').count;
    const colours = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) colours.set([tone.r, tone.g, tone.b], i * 3);
    mesh.geometry.setAttribute('color', new THREE.BufferAttribute(colours, 3));

    members.set(id, { id, family: String(mesh.userData['bower_family'] ?? ''), mesh, edges });
  });

  const ink = new LineMaterial({ color: INK, linewidth: 1, toneMapped: false });
  const lines = new LineSegments2(new LineSegmentsGeometry().setPositions(all), ink);
  lines.frustumCulled = false;
  lines.name = 'timber ink';

  const group = new THREE.Group();
  group.name = 'timber';
  group.add(gltf.scene, lines);

  function setLook(look: TimberLook): void {
    const coloured = look !== 'ink';
    for (const m of members.values()) {
      m.mesh.material = coloured ? wood : paper;
      m.mesh.receiveShadow = coloured;
    }
    if (coloured) age(look === 'bare' ? 'bare' : 'kept');
    ink.color.setHex(coloured ? WOOD_LINE : INK);
    ink.linewidth = coloured ? 0.85 : 1;
  }
  setLook('wood');

  return {
    group,
    bounds: new THREE.Box3().setFromObject(gltf.scene),
    members,
    ink,
    lines,
    setLook,
    setAge(y) {
      years.value = Math.max(0, y);
    },
  };
}

/** Slender steel for plants to hold: each cable a thin line, in the grey of the factory drawings' labels. */
export function drawCables(cables: readonly { points: readonly number[][] }[], marked = false): THREE.Object3D {
  const positions: number[] = [];
  for (const c of cables) {
    for (let i = 0; i + 1 < c.points.length; i++) {
      const a = c.points[i]!;
      const b = c.points[i + 1]!;
      positions.push(a[0]!, a[2]!, -a[1]!, b[0]!, b[2]!, -b[1]!);
    }
  }
  const object = new LineSegments2(new LineSegmentsGeometry().setPositions(positions.length ? positions : [0, 0, 0, 0, 0, 0]), new LineMaterial(marked ? { color: MARKED, linewidth: 1.7, toneMapped: false } : { color: MUTED, linewidth: 0.55, toneMapped: false }));
  object.frustumCulled = false;
  object.visible = positions.length > 0;
  object.name = 'cables';
  return object;
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
