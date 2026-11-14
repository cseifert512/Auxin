// The timber, drawn two ways.
//
//   ink     every member filled with paper, so that it hides what is behind it, and every edge of it (its four
//           long arrises, its ends and each milled joint) drawn in ink: the factory drawings' way
//   wood    the same edges over timber in its own colour, lit by the sun the plants are lit by and taking their
//           shade; its colour held by a finish that is kept up, deepening with the years
//   bare    the same, left unfinished to go silver
//
// Coloured timber is drawn as what it is: glue-laminated. Each member is a stack of boards through its depth, the
// glue lines between them showing on its sides, each board a length of its own shade with its own growth rings.
// The rings are drawn as a draughtsman would draw grain: a few lines along the piece at any distance, more of the
// real ones as the eye comes close.
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
  /** How strongly the grain and glue lines are drawn on coloured timber: 0 none, 1 as designed. */
  setGrain(strength: number): void;
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

/** A member's centre line as the snapshot records it: a point every tenth of a metre, and which way its depth is turned there. */
export interface Centreline {
  id: string;
  family?: string;
  width_m: number;
  depth_m: number;
  closed?: boolean;
  points_m: number[][];
  depth_axes: number[][];
}

/** About how thick one board of a glue-laminated member is. */
const LAMINATION_M = 0.044;
const laminationsOf = (line: Centreline): number => Math.max(1, Math.round(line.depth_m / LAMINATION_M));

/**
 * Where each corner of a member's mesh lies in its own timber: metres along it, metres across its width, and
 * boards through its depth (0 at one face, the number of boards at the other). The mesh is in the drawing's
 * axes (y up), the centre line in the building's (z up, y north).
 */
function grainOf(geometry: THREE.BufferGeometry, world: THREE.Matrix4, line: Centreline): Float32Array {
  const pts = line.points_m;
  const n = pts.length;
  const boards = laminationsOf(line);
  const arc = new Float64Array(n);
  for (let i = 1; i < n; i++) arc[i] = arc[i - 1]! + Math.hypot(pts[i]![0]! - pts[i - 1]![0]!, pts[i]![1]! - pts[i - 1]![1]!, pts[i]![2]! - pts[i - 1]![2]!);
  // at each sample: along the member, through its depth, across its width
  const frames = new Float64Array(n * 9);
  for (let i = 0; i < n; i++) {
    const a = pts[line.closed ? (i - 1 + n) % n : Math.max(0, i - 1)]!;
    const b = pts[line.closed ? (i + 1) % n : Math.min(n - 1, i + 1)]!;
    let [tx, ty, tz] = [b[0]! - a[0]!, b[1]! - a[1]!, b[2]! - a[2]!];
    const tl = Math.hypot(tx, ty, tz) || 1;
    [tx, ty, tz] = [tx / tl, ty / tl, tz / tl];
    let [dx, dy, dz] = line.depth_axes[i] as [number, number, number];
    const along = dx * tx + dy * ty + dz * tz;
    [dx, dy, dz] = [dx - along * tx, dy - along * ty, dz - along * tz];
    const dl = Math.hypot(dx, dy, dz) || 1;
    [dx, dy, dz] = [dx / dl, dy / dl, dz / dl];
    frames.set([tx, ty, tz, dx, dy, dz, ty * dz - tz * dy, tz * dx - tx * dz, tx * dy - ty * dx], i * 9);
  }
  const position = geometry.getAttribute('position');
  const out = new Float32Array(position.count * 3);
  const v = new THREE.Vector3();
  for (let k = 0; k < position.count; k++) {
    v.fromBufferAttribute(position, k).applyMatrix4(world);
    const [x, y, z] = [v.x, -v.z, v.y];
    let best = 0;
    let least = Infinity;
    for (let i = 0; i < n; i++) {
      const p = pts[i]!;
      const d2 = (x - p[0]!) ** 2 + (y - p[1]!) ** 2 + (z - p[2]!) ** 2;
      if (d2 < least) {
        least = d2;
        best = i;
      }
    }
    const p = pts[best]!;
    const f = best * 9;
    const [ox, oy, oz] = [x - p[0]!, y - p[1]!, z - p[2]!];
    out[k * 3] = arc[best]! + ox * frames[f]! + oy * frames[f + 1]! + oz * frames[f + 2]!;
    out[k * 3 + 1] = ox * frames[f + 6]! + oy * frames[f + 7]! + oz * frames[f + 8]!;
    out[k * 3 + 2] = (ox * frames[f + 3]! + oy * frames[f + 4]! + oz * frames[f + 5]!) / (line.depth_m / boards) + boards / 2;
  }
  // a ring comes round to where it began: the triangles across that seam are measured on from its end, not back to 0
  if (line.closed) {
    const length = arc[n - 1]!;
    for (let k = 0; k + 2 < position.count; k += 3) {
      const s = [out[k * 3]!, out[k * 3 + 3]!, out[k * 3 + 6]!];
      if (Math.max(...s) - Math.min(...s) > length / 2) for (let j = 0; j < 3; j++) if (s[j]! < length / 2) out[(k + j) * 3] = s[j]! + length;
    }
  }
  return out;
}

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

function makeWood(years: { value: number }, grain: { value: number }) {
  const ageing = { greyMost: { value: 0 }, greyYears: { value: 1 }, deepens: { value: 0 } };
  const wood = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.84, metalness: 0, polygonOffset: true, polygonOffsetFactor: 1.5, polygonOffsetUnits: 2 });
  wood.onBeforeCompile = (shader) => {
    shader.uniforms['uYears'] = years;
    shader.uniforms['uSilvered'] = { value: new THREE.Color(SILVERED) };
    shader.uniforms['uGreyMost'] = ageing.greyMost;
    shader.uniforms['uGreyYears'] = ageing.greyYears;
    shader.uniforms['uDeepens'] = ageing.deepens;
    shader.uniforms['uGrain'] = grain;
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nattribute vec3 grain;\nattribute vec2 piece;\nvarying vec3 vGrain;\nvarying vec2 vPiece;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvGrain = grain;\nvPiece = piece;');
    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        /* glsl */ `#include <common>
        uniform float uYears, uGreyMost, uGreyYears, uDeepens, uGrain;
        uniform vec3 uSilvered;
        varying vec3 vGrain;
        varying vec2 vPiece;
        float chance1( float n ) { return fract( sin( n * 127.1 ) * 43758.5453 ); }
        float chance2( vec2 p ) { return fract( sin( dot( p, vec2( 127.1, 311.7 ) ) ) * 43758.5453 ); }
        float drift( vec2 p ) {
          vec2 i = floor( p ), f = fract( p );
          f = f * f * ( 3.0 - 2.0 * f );
          return mix( mix( chance2( i ), chance2( i + vec2( 1.0, 0.0 ) ), f.x ), mix( chance2( i + vec2( 0.0, 1.0 ) ), chance2( i + vec2( 1.0, 1.0 ) ), f.x ), f.y );
        }`,
      )
      .replace(
        '#include <color_fragment>',
        /* glsl */ `#include <color_fragment>
        if ( uGrain > 0.0 ) {
          float boards = vPiece.y;
          float along = vGrain.x;
          float through = clamp( vGrain.z, 0.001, boards - 0.001 );
          float lam = floor( through );
          // a lamination is boards end to end, each a few metres long and from its own tree
          float board = floor( along / 3.4 + chance1( lam + vPiece.x * 91.0 ) );
          float id = lam * 17.0 + board * 3.0 + vPiece.x * 257.0;
          // laminations to a pixel: under two pixels deep, they are not drawn apart
          float perPixel = fwidth( vGrain.z );
          float seen = 1.0 - smoothstep( 0.3, 0.6, perPixel );
          float shade = ( chance1( id ) - 0.5 ) * 0.15 * seen;
          // the glue line between one lamination and the next (the two outer faces are not lines)
          float inner = clamp( vGrain.z, 0.5, boards - 0.5 );
          float off = abs( fract( inner + 0.5 ) - 0.5 );
          float glue = ( 1.0 - smoothstep( 0.4 * perPixel, 1.2 * perPixel + 0.012, off ) ) * seen;
          // growth rings: the heart of the tree lies below the board and wanders a little along it
          vec2 q = vec2( vGrain.y, ( through - lam - 0.5 ) * 0.044 );
          vec2 heart = vec2( ( chance1( id + 1.3 ) - 0.5 ) * 0.16, - 0.03 - 0.1 * chance1( id + 2.7 ) );
          heart += 0.014 * ( vec2( drift( vec2( along * 0.35, id ) ), drift( vec2( along * 0.22, id + 9.0 ) ) ) - 0.5 );
          float r = length( q - heart );
          // drawn at a spacing the eye can take: the real rings close to, every second, fourth, eighth further off
          float metres = length( fwidth( vec3( vGrain.xy, vGrain.z * 0.044 ) ) ) * 0.7 + 1e-6;
          float level = max( 0.0, log2( metres * 5.0 / 0.004 ) );
          float spacing = 0.004 * exp2( floor( level ) );
          float x = r / spacing;
          float ring = floor( x + 0.5 );
          float wide = clamp( fwidth( x ), 1e-4, 0.5 );
          float keep = 1.0 - mod( ring, 2.0 ) * fract( level );
          float name = ring * spacing * 250.0;
          float weight = 0.3 + 0.7 * drift( vec2( along * 1.3 + name * 7.1, name * 1.7 + id ) );
          float stroke = ( 1.0 - smoothstep( 0.35 * wide, 1.1 * wide, abs( x - ring ) ) ) * keep * weight;
          vec3 drawn = diffuseColor.rgb * ( 1.0 + shade );
          drawn = mix( drawn, drawn * vec3( 0.78, 0.66, 0.54 ), stroke * 0.6 );
          drawn = mix( drawn, drawn * vec3( 0.6, 0.5, 0.42 ), glue * 0.65 );
          diffuseColor.rgb = mix( diffuseColor.rgb, drawn, uGrain );
        }
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

export async function loadTimber(url: string, centrelines: readonly Centreline[] = []): Promise<Timber> {
  const lineOf = new Map(centrelines.map((c) => [c.id, c]));
  const gltf = await new GLTFLoader().loadAsync(url);
  gltf.scene.updateMatrixWorld(true);
  const paper = new THREE.MeshBasicMaterial({ color: PAPER, toneMapped: false, polygonOffset: true, polygonOffsetFactor: 1.5, polygonOffsetUnits: 2 });
  const years = { value: 0 };
  const grain = { value: 1 };
  const { wood, age } = makeWood(years, grain);

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
    // where each corner lies in the member's own timber, for its grain
    const line = lineOf.get(id);
    if (line?.closed && mesh.geometry.index) mesh.geometry = mesh.geometry.toNonIndexed();
    const count = mesh.geometry.getAttribute('position').count;
    const colours = new Float32Array(count * 3);
    const piece = new Float32Array(count * 2);
    for (let i = 0; i < count; i++) {
      colours.set([tone.r, tone.g, tone.b], i * 3);
      piece.set([shade, line ? laminationsOf(line) : 1], i * 2);
    }
    mesh.geometry.setAttribute('color', new THREE.BufferAttribute(colours, 3));
    mesh.geometry.setAttribute('piece', new THREE.BufferAttribute(piece, 2));
    mesh.geometry.setAttribute('grain', new THREE.BufferAttribute(line ? grainOf(mesh.geometry, mesh.matrixWorld, line) : new Float32Array(count * 3), 3));

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
    setGrain(strength) {
      grain.value = Math.max(0, Math.min(1, strength));
    },
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

/** In plan, what is overhead: the centre lines of the members of the families named, as broken lines on the floor below them. */
export function drawOverhead(lines: readonly Centreline[], families: readonly string[]): THREE.Object3D {
  const positions: number[] = [];
  for (const line of lines) {
    if (!families.includes(line.family ?? '')) continue;
    for (let i = 0; i + 1 < line.points_m.length; i++) {
      const a = line.points_m[i]!;
      const b = line.points_m[i + 1]!;
      positions.push(a[0]!, 0.015, -a[1]!, b[0]!, 0.015, -b[1]!);
    }
  }
  const object = new LineSegments2(new LineSegmentsGeometry().setPositions(positions.length ? positions : [0, 0, 0, 0, 0, 0]), new LineMaterial({ color: INK, linewidth: 0.7, dashed: true, dashSize: 0.2, gapSize: 0.14, toneMapped: false }));
  object.computeLineDistances();
  object.frustumCulled = false;
  object.name = 'overhead';
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
