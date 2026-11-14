// The sheet the drawing is made on: paper, light, and the places to look from.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { Sky } from 'three/addons/objects/Sky.js';

export const PAPER = 0xfdfcf9;
export const INK = 0x1d1d1b;
export const MUTED = 0x6b7178;

/** A point in the building's frame (x east, y north, z up) as three.js has it. */
export const toThree = (p: readonly number[]): THREE.Vector3 => new THREE.Vector3(p[0]!, p[2]!, -p[1]!);

export type ViewId = 'drawing' | 'approach' | 'inside';

/** A place a visitor stands, as the building model's design file gives it. */
export interface Standpoint {
  eye: readonly number[];
  target: readonly number[];
  lensMm: number;
}

/**
 * The factory drawings' projection (bower-factory, engine/projection.js): the plan turned 0.575 radians, depth
 * drawn at half scale and heights at full scale. As a camera that is a parallel view looking down at atan(1/2),
 * with the picture stretched upright by one over the cosine of that angle.
 */
const TURN = 0.575;
const DIP = Math.atan(0.5);
const STRETCH = 1 / Math.cos(DIP);
/** The proportion of the sheet the standpoints' lenses are given for: a presentation slide. */
const WIDE_SHEET = 16 / 9;
/** The field of view the plant models' levels of detail were tuned at. */
const DETAIL_FOV = THREE.MathUtils.degToRad(40);

/** The sky of three.js with the response curve the plants were coloured under (see the viewer's scene/stage.ts). */
function makeSky(): Sky {
  const sky = new Sky();
  const m = sky.material;
  const linear = 'gl_FragColor = vec4( texColor, 1.0 );';
  if (m.fragmentShader.includes(linear) && m.vertexShader.includes('varying float vSunfade;')) {
    m.fragmentShader = m.fragmentShader
      .replace(linear, 'gl_FragColor = vec4( pow( texColor, vec3( 1.0 / ( 1.2 + ( 1.2 * vSunfade ) ) ) ), 1.0 );')
      .replace('varying vec3 vSunDirection;', 'varying vec3 vSunDirection; varying float vSunfade;');
  }
  const u = m.uniforms;
  u['turbidity']!.value = 4.2;
  u['rayleigh']!.value = 1.5;
  u['mieCoefficient']!.value = 0.004;
  u['mieDirectionalG']!.value = 0.82;
  if (u['cloudCoverage']) u['cloudCoverage'].value = 0;
  sky.scale.setScalar(450);
  return sky;
}

export function makePaper(canvas: HTMLCanvasElement, standpoints: { approach: Standpoint; inside: Standpoint; approachTall: { eye: readonly number[]; target: readonly number[]; acrossDeg: number } }) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance', preserveDrawingBuffer: true });
  renderer.setClearColor(PAPER, 1);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.shadowMap.autoUpdate = false;
  renderer.toneMapping = THREE.NeutralToneMapping;
  const scene = new THREE.Scene();

  // ---- light: the plants are lit as the viewer lights them, so their colours are the ones they were made with ----
  const sun = new THREE.DirectionalLight(0xfff0dc, 3.4);
  sun.castShadow = true;
  sun.shadow.mapSize.set(4096, 4096);
  sun.shadow.bias = -0.0003;
  sun.shadow.normalBias = 0.012;
  sun.shadow.radius = 2.5;
  const skyLight = new THREE.HemisphereLight(0xcfe0ff, 0xe6e0d2, 0.35);
  scene.add(sun, sun.target, skyLight);

  const pmrem = new THREE.PMREMGenerator(renderer);
  const skyScene = new THREE.Scene();
  const sky = makeSky();
  skyScene.add(sky);
  let skyTarget: THREE.WebGLRenderTarget | null = null;
  const sunDir = new THREE.Vector3(0, 1, 0);
  let shadowHalf = 12;

  /** `direction`: unit vector towards the sun, in three.js axes. */
  function setSun(direction: THREE.Vector3): void {
    sunDir.copy(direction).normalize();
    const elevation = THREE.MathUtils.radToDeg(Math.asin(THREE.MathUtils.clamp(sunDir.y, -1, 1)));
    const low = THREE.MathUtils.smoothstep(elevation, 2, 30);
    sun.color.setRGB(1, 0.72 + 0.22 * low, 0.5 + 0.36 * low);
    sun.intensity = 0.6 + 2.8 * low;
    sun.position.copy(sunDir).multiplyScalar(60).add(sun.target.position);
    renderer.toneMappingExposure = 0.62 * (1.3 - 0.3 * low);
    sky.material.uniforms['sunPosition']!.value.copy(sunDir);
    skyTarget?.dispose();
    skyTarget = pmrem.fromScene(skyScene, 0.02);
    scene.environment = skyTarget.texture;
    scene.environmentIntensity = 0.9;
    renderer.shadowMap.needsUpdate = true;
  }

  // the ground is paper: all it shows is where shade falls
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), new THREE.ShadowMaterial({ color: 0x4a463e, opacity: 0.2 }));
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  // ---- the places to look from ---------------------------------------------------------------------------------
  const drawing = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.5, 400);
  const lensFov = (lensMm: number) => THREE.MathUtils.radToDeg(2 * Math.atan(12 / lensMm));
  const approach = new THREE.PerspectiveCamera(lensFov(standpoints.approach.lensMm), 1, 0.05, 600);
  const inside = new THREE.PerspectiveCamera(lensFov(standpoints.inside.lensMm), 1, 0.03, 600);
  const cameras: Record<ViewId, THREE.Camera> = { drawing, approach, inside };

  const controls: Record<ViewId, OrbitControls> = {
    drawing: new OrbitControls(drawing, canvas),
    approach: new OrbitControls(approach, canvas),
    inside: new OrbitControls(inside, canvas),
  };
  let moved = true;
  for (const c of Object.values(controls)) {
    c.enableDamping = true;
    c.dampingFactor = 0.08;
    c.addEventListener('change', () => (moved = true));
  }
  // the drawing turns like a model on a turntable: its projection never changes
  controls.drawing.minPolarAngle = controls.drawing.maxPolarAngle = Math.PI / 2 - DIP;
  controls.drawing.minZoom = 0.6;
  controls.drawing.maxZoom = 14;
  controls.drawing.zoomToCursor = true;
  controls.approach.maxPolarAngle = Math.PI * 0.53;
  controls.approach.minDistance = 3;
  controls.approach.maxDistance = 70;
  // standing inside, a drag turns the head
  controls.inside.enableZoom = false;
  controls.inside.enablePan = false;
  controls.inside.rotateSpeed = -0.35;

  approach.position.copy(toThree(standpoints.approach.eye));
  controls.approach.target.copy(toThree(standpoints.approach.target));
  inside.position.copy(toThree(standpoints.inside.eye));
  controls.inside.target.copy(inside.position).addScaledVector(toThree(standpoints.inside.target).sub(inside.position).normalize(), 0.2);

  /** Half the width and height the subject takes up in the drawing, in metres across the sheet. */
  const need = { halfW: 10, halfH: 6 };
  const size = { width: 1, height: 1 };
  let wasTall = false;

  function fitDrawing(): void {
    const aspect = size.width / size.height;
    const margin = 1.08;
    // room is left below for the time line
    const above = 1.0;
    const below = 1.3;
    let halfH = need.halfH * margin;
    const halfW = ((halfH * (above + below)) / 2) * STRETCH * aspect;
    if (halfW < need.halfW * margin) halfH *= (need.halfW * margin) / halfW;
    drawing.top = halfH * above;
    drawing.bottom = -halfH * below;
    const w = ((drawing.top - drawing.bottom) / 2) * STRETCH * aspect;
    drawing.left = -w;
    drawing.right = w;
    drawing.updateProjectionMatrix();
  }

  /** Set the sheet up round what is drawn. */
  function frame(bounds: THREE.Box3): void {
    const centre = bounds.getCenter(new THREE.Vector3());
    const forward = new THREE.Vector3(Math.sin(TURN) * Math.cos(DIP), -Math.sin(DIP), -Math.cos(TURN) * Math.cos(DIP));
    drawing.position.copy(centre).addScaledVector(forward, -120);
    drawing.lookAt(centre);
    drawing.updateMatrixWorld(true);
    controls.drawing.target.copy(centre);
    let halfW = 0;
    let halfH = 0;
    const corner = new THREE.Vector3();
    for (let i = 0; i < 8; i++) {
      corner.set(i & 1 ? bounds.max.x : bounds.min.x, i & 2 ? bounds.max.y : bounds.min.y, i & 4 ? bounds.max.z : bounds.min.z).applyMatrix4(drawing.matrixWorldInverse);
      halfW = Math.max(halfW, Math.abs(corner.x));
      halfH = Math.max(halfH, Math.abs(corner.y));
    }
    need.halfW = halfW;
    need.halfH = halfH;
    fitDrawing();

    const radius = bounds.getBoundingSphere(new THREE.Sphere()).radius;
    shadowHalf = radius * 1.35;
    const cam = sun.shadow.camera;
    cam.left = cam.bottom = -shadowHalf;
    cam.right = cam.top = shadowHalf;
    cam.near = 1;
    cam.far = 60 + shadowHalf * 2.2;
    cam.updateProjectionMatrix();
    sun.target.position.set(centre.x, 1.4, centre.z);
    sun.target.updateMatrixWorld();
    setSun(sunDir.clone());
    for (const c of Object.values(controls)) c.update();
  }

  let active: ViewId = 'drawing';
  function setView(id: ViewId): void {
    active = id;
    for (const [key, c] of Object.entries(controls)) c.enabled = key === id;
    moved = true;
  }
  setView('drawing');

  function resize(): boolean {
    const width = Math.max(1, canvas.clientWidth);
    const height = Math.max(1, canvas.clientHeight);
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    if (width === size.width && height === size.height && pixelRatio === renderer.getPixelRatio()) return false;
    size.width = width;
    size.height = height;
    renderer.setPixelRatio(pixelRatio);
    renderer.setSize(width, height, false);
    approach.aspect = inside.aspect = width / height;
    // The standpoints were set up for a wide sheet. On an upright one each keeps what it sees from side to side,
    // and sees further up and down instead, so the whole building is still in the picture.
    for (const [camera, standpoint] of [[approach, standpoints.approach], [inside, standpoints.inside]] as const) {
      const half = Math.tan(THREE.MathUtils.degToRad(lensFov(standpoint.lensMm)) / 2) * Math.max(1, WIDE_SHEET / camera.aspect);
      camera.fov = Math.min(100, THREE.MathUtils.radToDeg(2 * Math.atan(half)));
    }
    // On a sheet taller than it is wide, a phone's, a building this broad seen whole is a small thing in the
    // middle. The approach is walked on instead, to stand before the bay in front (standpoints.approachTall).
    const tall = width < height;
    if (tall !== wasTall) {
      wasTall = tall;
      approach.position.copy(toThree(tall ? standpoints.approachTall.eye : standpoints.approach.eye));
      controls.approach.target.copy(toThree(tall ? standpoints.approachTall.target : standpoints.approach.target));
      controls.approach.update();
    }
    if (tall) approach.fov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(standpoints.approachTall.acrossDeg) / 2) / approach.aspect));
    approach.updateProjectionMatrix();
    inside.updateProjectionMatrix();
    fitDrawing();
    moved = true;
    return true;
  }

  // The plants choose how finely to draw each leaf by its distance from the camera. A parallel camera has no
  // distance that means anything, so it is given one: where a camera with an ordinary lens would stand to see
  // as much of the building as the drawing shows.
  const detailCamera = new THREE.PerspectiveCamera();
  function detailFrom(): THREE.Camera {
    if (active !== 'drawing') return cameras[active];
    const seen = (drawing.top - drawing.bottom) / drawing.zoom;
    const away = drawing.position.clone().sub(controls.drawing.target).normalize();
    detailCamera.position.copy(controls.drawing.target).addScaledVector(away, seen / (2 * Math.tan(DETAIL_FOV / 2)));
    return detailCamera;
  }

  return {
    renderer,
    scene,
    sun,
    sunDir,
    size,
    setSun,
    frame,
    setView,
    view: () => active,
    camera: () => cameras[active],
    detailFrom,
    resize,
    /** Let the camera settle; true if it has moved since last asked. */
    step(): boolean {
      controls[active].update();
      const was = moved;
      moved = false;
      return was;
    },
    shadeChanged(): void {
      renderer.shadowMap.needsUpdate = true;
    },
    render(): void {
      renderer.render(scene, cameras[active]);
    },
  };
}

export type Paper = ReturnType<typeof makePaper>;
