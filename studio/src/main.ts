// A room through time: the timber as an ink drawing, the plants in colour, and one line of time to draw along.
// The line runs from the design (centre lines), through the building going together, into ten years of growth.
//
// What is drawn comes from frozen things: a snapshot of the building (releases/), the order its joints let it go
// together in, and a run of the plant simulator on it (scenes/<snapshot>/). The plants are drawn by the
// simulator's own viewer code, read in place; nothing here decides when a leaf opens or a flower falls.
import * as THREE from 'three';
import type { RenderData } from '@horti/core';
import { clock } from '@horti/viewer/plant/adapter.ts';
import { loadLooks } from '@horti/viewer/plant/registry.ts';
import { shared } from '@horti/viewer/plant/shaders.ts';
import { PlantView, makePlantMaterials } from '@horti/viewer/plant/view.ts';
import { makeBarkTextures, makeLeafTexture, makeOwnLeafTexture } from '@horti/viewer/textures.ts';
import design from '../../releases/six-bay-v1/design.json';
import timberUrl from '../../releases/six-bay-v1/bower.glb?url';
import plan from '../../scenes/six-bay-v1/assembly.json';
import bowerUrl from '../../scenes/six-bay-v1/bower.json?url';
import growthUrl from '../../scenes/six-bay-v1/runs/trained-10y/growth.json?url';
import { type AssemblyPlan, type AssemblyState, DESIGN_SHARE, makeAssembly } from './assembly.ts';
import { type Standpoint, type ViewId, makePaper } from './paper.ts';
import { drawBeds, loadTimber } from './timber.ts';

const $ = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T;
const url = new URL(location.href).searchParams;
const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

// the deck's own face, where its files are beside this repository; otherwise the stack in style.css
const faces = import.meta.glob('../../../Bower_Web/public/designx/4/assets/fonts/safiro-{regular,semibold}-webfont.woff2', { query: '?url', import: 'default', eager: true }) as Record<string, string>;
for (const [file, href] of Object.entries(faces)) {
  void new FontFace('Safiro', `url(${href})`, { weight: file.includes('semibold') ? '600' : '400' }).load().then((f) => document.fonts.add(f));
}

// ---- the sheet ---------------------------------------------------------------------------------------------------
const view = (id: string): Standpoint => {
  const v = design.views.find((x) => x.id === id);
  if (!v || v.lens_mm === undefined) throw new Error(`the design has no "${id}" view to stand at`);
  return { eye: v.location_m, target: v.target_m, lensMm: v.lens_mm };
};
const paper = makePaper($<HTMLCanvasElement>('sheet'), { approach: view('exterior'), inside: view('interior') });
// mid-afternoon in early summer, from the south-west: towards the sun, as (east, up, south)
paper.setSun(new THREE.Vector3(-0.609, 0.669, 0.426));
paper.resize();

const timber = await loadTimber(timberUrl);
paper.scene.add(timber.group);
paper.frame(timber.bounds);
const assembly = makeAssembly(timber, plan as AssemblyPlan);
paper.scene.add(assembly.group);

const bower = (await (await fetch(bowerUrl)).json()) as { stations: { id: string; position: number[] }[] };
paper.scene.add(drawBeds(bower.stations));

// ---- the plants --------------------------------------------------------------------------------------------------
const growth = (await (await fetch(growthUrl)).json()) as RenderData;
await loadLooks([...new Set(growth.plants.map((p) => p.taxonId))]);
const plants = new PlantView(growth, makePlantMaterials({ bark: (grain) => makeBarkTextures(grain), leafTex: makeLeafTexture(), ownLeafTex: makeOwnLeafTexture }));
paper.scene.add(plants.group);

// ---- the line of time --------------------------------------------------------------------------------------------
// One line carries two things that are not measured alike. From planting on it is days, and the simulator's. Before
// planting it is the assembly, which has an order but no dates: it is given a stretch of the line at its start.
const DAY_MS = 86_400_000;
const start = Date.parse(`${growth.start}T00:00:00Z`);
const planted = plants.timeline.firstDay;
const lastDay = plants.timeline.lastDay;
const BUILD_SPAN = Math.round(0.17 * (lastDay - planted));
const lineStart = planted - BUILD_SPAN;
/** How long each part plays for, in seconds, and the pause between them as the plants go in. */
const BUILD_SECONDS = 26;
const GROW_SECONDS = 80;
const PLANTING_PAUSE_MS = 1100;
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const SEASONS = ['winter', 'winter', 'spring', 'spring', 'spring', 'summer', 'summer', 'summer', 'autumn', 'autumn', 'autumn', 'winter'];
const FAMILIES: Record<string, string> = { arch: 'arches', hoop: 'hoops', ring: 'rings', rib: 'ribs', fill: 'second ribs', fine: 'third ribs', crown: 'the crown' };

const atBuild = (share: number) => lineStart + clamp01(share) * BUILD_SPAN;
// it opens on the finished design: every centre line drawn, and the first member about to move
const opening = url.has('day') ? Number(url.get('day')) : url.has('build') ? atBuild(Number(url.get('build'))) : atBuild(DESIGN_SHARE) - 0.5;
const state = { at: opening, playing: url.has('play'), drawnAt: Number.NaN, drawnDay: -1, pausedUntil: 0 };
let built: AssemblyState = assembly.set(clamp01((state.at - lineStart) / BUILD_SPAN));

const el = {
  play: $<HTMLButtonElement>('play'),
  scrub: $<HTMLInputElement>('scrub'),
  date: $('date'),
  age: $('age'),
  years: $('years'),
  key1: $('key1'),
  value1: $('value1'),
  key2: $('key2'),
  value2: $('value2'),
  statement: $('statement'),
};

el.scrub.min = String(lineStart);
el.scrub.max = String(lastDay);
const tick = (at: number, text: string) => {
  const mark = document.createElement('span');
  mark.textContent = text;
  mark.style.left = `${(100 * (at - lineStart)) / (lastDay - lineStart)}%`;
  el.years.append(mark);
};
tick(lineStart, 'assembly');
tick(planted, 'planted');
for (let year = new Date(start).getUTCFullYear() + 1; ; year++) {
  const day = (Date.UTC(year, 0, 1) - start) / DAY_MS;
  if (day >= lastDay) break;
  tick(day, String(year));
}

const growing = () => state.at >= planted;
function setPlaying(on: boolean): void {
  state.playing = on;
  el.play.textContent = on ? 'Pause' : 'Play';
  el.play.setAttribute('aria-label', on ? 'Pause' : 'Play');
}
function setAt(at: number): void {
  state.at = Math.min(lastDay, Math.max(lineStart, at));
  el.scrub.value = String(Math.round(state.at));
}

/** What the words beside the drawing say for the moment shown. */
function describe(): void {
  if (growing()) {
    const when = new Date(start + Math.floor(state.at) * DAY_MS);
    el.date.textContent = `${when.getUTCDate()} ${MONTHS[when.getUTCMonth()]} ${when.getUTCFullYear()}`;
    el.age.textContent = `year ${Math.floor((state.at - planted) / 365.25) + 1} · ${SEASONS[when.getUTCMonth()]}`;
    el.key1.textContent = 'in leaf';
    el.key2.textContent = 'in flower';
    el.statement.textContent = `${growth.statement} The timber is concept geometry.`;
    return;
  }
  el.key1.textContent = 'members';
  el.key2.textContent = 'joints made';
  el.value1.textContent = `${built.placed} / ${built.of}`;
  el.value2.textContent = `${built.jointsMade} / ${built.joints}`;
  el.statement.textContent = `${assembly.note} The timber is concept geometry.`;
  el.date.textContent = built.phase === 'design' ? 'The design' : 'Assembly';
  el.age.textContent = built.phase === 'design' ? `${built.of} centre lines` : (FAMILIES[built.family] ?? built.family);
}

el.play.addEventListener('click', () => {
  if (!state.playing && state.at >= lastDay - 1) setAt(lineStart);
  setPlaying(!state.playing);
});
el.scrub.addEventListener('input', () => {
  setPlaying(false);
  setAt(Number(el.scrub.value));
});
addEventListener('keydown', (e) => {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLButtonElement) return;
  const step = growing() ? (e.shiftKey ? 365 : 30) : BUILD_SPAN / (e.shiftKey ? 4 : 24);
  if (e.code === 'Space') el.play.click();
  else if (e.code === 'ArrowRight') setAt(state.at + step);
  else if (e.code === 'ArrowLeft') setAt(state.at - step);
  else return;
  e.preventDefault();
});

// ---- views -------------------------------------------------------------------------------------------------------
const viewButtons = [...document.querySelectorAll<HTMLButtonElement>('button[data-view]')];
function setView(id: ViewId): void {
  paper.setView(id);
  for (const b of viewButtons) b.setAttribute('aria-pressed', String(b.dataset['view'] === id));
}
for (const b of viewButtons) b.addEventListener('click', () => setView(b.dataset['view'] as ViewId));
if (['drawing', 'approach', 'inside'].includes(url.get('view') ?? '')) setView(url.get('view') as ViewId);

// ---- what goes with the picture ----------------------------------------------------------------------------------
$('subtitle').textContent = `${design.rooms[0]!.bays.length}-bay room · ${plan.members.length} timber members · trial planting of ${growth.plants.length} climbers, tended`;
$('loading').hidden = true;
document.querySelector<HTMLElement>('.time')!.hidden = false;
if (url.has('bare')) document.body.classList.add('bare');
setPlaying(state.playing);
setAt(state.at);
describe();

// ---- drawing -----------------------------------------------------------------------------------------------------
// Stems lengthen and thicken on the graphics card, from the day alone, so they are right in every frame. Leaves,
// flowers and fruit are worked out one by one, which for ten years of twelve plants takes about a tenth of a
// second: while time is moving that is done a few times a second, and once more, with the shade, when it rests.
const ORGANS_EVERY_MS = 220;
const SHADE_EVERY_MS = 700;
const sunInView = new THREE.Vector3();
let before = performance.now();
let organsAt = 0;
let organsFrom: { x: number; y: number; z: number; view: ViewId } | null = null;
let readAt = 0;
let shadeAt = 0;
let shadeOwed = true;

function draw(now: number): void {
  const dt = Math.min(0.1, (now - before) / 1000);
  before = now;
  paper.resize();
  if (state.playing && now >= state.pausedUntil) {
    const was = state.at;
    setAt(state.at + dt * (growing() ? (lastDay - planted) / GROW_SECONDS : BUILD_SPAN / BUILD_SECONDS));
    // the building stands for a moment before the plants go in
    if (was < planted && state.at >= planted) {
      setAt(planted);
      state.pausedUntil = now + PLANTING_PAUSE_MS;
    }
    if (state.at >= lastDay) setPlaying(false);
  }
  paper.step();
  const camera = paper.camera();

  if (state.at !== state.drawnAt) {
    const share = clamp01((state.at - lineStart) / BUILD_SPAN);
    if (share < 1 || built.phase !== 'built') {
      built = assembly.set(share);
      paper.shadeChanged();
    }
    plants.group.visible = growing();
    describe();
    state.drawnAt = state.at;
  }

  if (growing()) {
    shared.uTime.value += dt;
    shared.uSunColor.value.copy(paper.sun.color).multiplyScalar(paper.sun.intensity * 0.32);
    shared.uSunDirWorld.value.copy(paper.sunDir);
    shared.uSunDirView.value.copy(sunInView.copy(paper.sunDir).transformDirection(camera.matrixWorldInverse));
    clock.uDay.value = state.at;

    // how finely each leaf is drawn follows where it is seen from: worth working out again only after a real move
    const from = paper.detailFrom().position;
    const reach = organsFrom ? Math.hypot(from.x - organsFrom.x, from.y - organsFrom.y, from.z - organsFrom.z) : Infinity;
    const viewChanged = !organsFrom || organsFrom.view !== paper.view() || reach > 0.12 * Math.max(1, from.length());
    const dayChanged = state.at !== state.drawnDay;
    if ((dayChanged || viewChanged) && (now - organsAt > ORGANS_EVERY_MS || (!state.playing && now - organsAt > 60))) {
      plants.update(paper.detailFrom(), state.at, 1);
      organsAt = now;
      organsFrom = { x: from.x, y: from.y, z: from.z, view: paper.view() };
      if (dayChanged) shadeOwed = true;
      state.drawnDay = state.at;
    }
    if (shadeOwed && (now - shadeAt > SHADE_EVERY_MS || !state.playing)) {
      paper.shadeChanged();
      shadeAt = now;
      shadeOwed = false;
    }
    if (now - readAt > 200) {
      const s = plants.stats();
      el.value1.textContent = s.leaves.toLocaleString('en-GB');
      el.value2.textContent = s.flowers.toLocaleString('en-GB');
      readAt = now;
    }
  }
  paper.render();
  requestAnimationFrame(draw);
}
requestAnimationFrame(draw);

// for stills and checks: put the picture at a moment and a view
Object.assign(window, {
  studio: {
    growth,
    plants,
    paper,
    timber,
    /** A day of growth, counted from the start of the run. */
    set(day: number, id?: ViewId) {
      setPlaying(false);
      setAt(day);
      if (id) setView(id);
    },
    /** A share of the assembly: 0 nothing drawn, 1 standing. */
    build(share: number, id?: ViewId) {
      setPlaying(false);
      setAt(atBuild(share));
      if (id) setView(id);
    },
    state: () => ({ at: state.at, built }),
  },
});
