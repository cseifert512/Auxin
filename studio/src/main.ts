// A room through time: the timber as an ink drawing, the plants in colour, and one line of time to draw along.
//
// What is drawn comes from two frozen things: a snapshot of the building (releases/) and a run of the plant
// simulator on it (scenes/<snapshot>/runs/). The plants are drawn by the simulator's own viewer code, read in
// place; nothing here decides when a leaf opens or a flower falls.
import * as THREE from 'three';
import type { RenderData } from '@horti/core';
import { clock } from '@horti/viewer/plant/adapter.ts';
import { loadLooks } from '@horti/viewer/plant/registry.ts';
import { shared } from '@horti/viewer/plant/shaders.ts';
import { PlantView, makePlantMaterials } from '@horti/viewer/plant/view.ts';
import { makeBarkTextures, makeLeafTexture, makeOwnLeafTexture } from '@horti/viewer/textures.ts';
import design from '../../releases/six-bay-v1/design.json';
import timberUrl from '../../releases/six-bay-v1/bower.glb?url';
import bowerUrl from '../../scenes/six-bay-v1/bower.json?url';
import growthUrl from '../../scenes/six-bay-v1/runs/trained-10y/growth.json?url';
import { type Standpoint, type ViewId, makePaper } from './paper.ts';
import { drawBeds, loadTimber } from './timber.ts';

const $ = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T;
const url = new URL(location.href).searchParams;

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
const inks = [...timber.inks];
const sizeInks = () => {
  for (const ink of inks) ink.resolution.set(paper.size.width, paper.size.height);
};
sizeInks();
paper.render();

const bower = (await (await fetch(bowerUrl)).json()) as { stations: { id: string; position: number[] }[] };
const beds = drawBeds(bower.stations);
paper.scene.add(beds.object);
inks.push(beds.ink);
sizeInks();

// ---- the plants --------------------------------------------------------------------------------------------------
const growth = (await (await fetch(growthUrl)).json()) as RenderData;
await loadLooks([...new Set(growth.plants.map((p) => p.taxonId))]);
const plants = new PlantView(growth, makePlantMaterials({ bark: (grain) => makeBarkTextures(grain), leafTex: makeLeafTexture(), ownLeafTex: makeOwnLeafTexture }));
paper.scene.add(plants.group);

// ---- time --------------------------------------------------------------------------------------------------------
const DAY_MS = 86_400_000;
const start = Date.parse(`${growth.start}T00:00:00Z`);
const firstDay = plants.timeline.firstDay;
const lastDay = plants.timeline.lastDay;
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const SEASONS = ['winter', 'winter', 'spring', 'spring', 'spring', 'summer', 'summer', 'summer', 'autumn', 'autumn', 'autumn', 'winter'];
/** The whole run plays in this many seconds. */
const PLAY_SECONDS = 80;

const state = { day: Number(url.get('day') ?? firstDay), playing: url.has('play'), drawn: -1 };
const el = { play: $<HTMLButtonElement>('play'), scrub: $<HTMLInputElement>('scrub'), date: $('date'), age: $('age'), leaves: $('leaves'), flowers: $('flowers'), years: $('years') };

el.scrub.min = String(firstDay);
el.scrub.max = String(lastDay);
for (let year = new Date(start).getUTCFullYear() + 1; ; year++) {
  const day = (Date.UTC(year, 0, 1) - start) / DAY_MS;
  if (day >= lastDay) break;
  const tick = document.createElement('span');
  tick.textContent = String(year);
  tick.style.left = `${(100 * (day - firstDay)) / (lastDay - firstDay)}%`;
  el.years.append(tick);
}

function showDay(): void {
  const when = new Date(start + Math.floor(state.day) * DAY_MS);
  el.date.textContent = `${when.getUTCDate()} ${MONTHS[when.getUTCMonth()]} ${when.getUTCFullYear()}`;
  el.age.textContent = `year ${Math.floor((state.day - firstDay) / 365.25) + 1} · ${SEASONS[when.getUTCMonth()]}`;
  el.scrub.value = String(Math.round(state.day));
}
function setPlaying(on: boolean): void {
  state.playing = on;
  el.play.textContent = on ? 'Pause' : 'Play';
  el.play.setAttribute('aria-label', on ? 'Pause' : 'Play');
}
function setDay(day: number): void {
  state.day = Math.min(lastDay, Math.max(firstDay, day));
  showDay();
}

el.play.addEventListener('click', () => {
  if (!state.playing && state.day >= lastDay - 1) setDay(firstDay);
  setPlaying(!state.playing);
});
el.scrub.addEventListener('input', () => {
  setPlaying(false);
  setDay(Number(el.scrub.value));
});
addEventListener('keydown', (e) => {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLButtonElement) return;
  if (e.code === 'Space') el.play.click();
  else if (e.code === 'ArrowRight') setDay(state.day + (e.shiftKey ? 365 : 30));
  else if (e.code === 'ArrowLeft') setDay(state.day - (e.shiftKey ? 365 : 30));
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
$('subtitle').textContent = `${design.rooms[0]!.bays.length}-bay room · trial planting of ${growth.plants.length} climbers, tended · planted ${MONTHS[new Date(start).getUTCMonth()]} ${new Date(start).getUTCFullYear()}`;
$('statement').textContent = `${growth.statement} The timber is concept geometry.`;
$('loading').hidden = true;
document.querySelector<HTMLElement>('.time')!.hidden = false;
if (url.has('bare')) document.body.classList.add('bare');
setPlaying(state.playing);
setDay(state.day);

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
  if (paper.resize()) sizeInks();
  if (state.playing) {
    setDay(state.day + (dt * (lastDay - firstDay)) / PLAY_SECONDS);
    if (state.day >= lastDay) setPlaying(false);
  }
  paper.step();
  const camera = paper.camera();

  shared.uTime.value += dt;
  shared.uSunColor.value.copy(paper.sun.color).multiplyScalar(paper.sun.intensity * 0.32);
  shared.uSunDirWorld.value.copy(paper.sunDir);
  shared.uSunDirView.value.copy(sunInView.copy(paper.sunDir).transformDirection(camera.matrixWorldInverse));
  clock.uDay.value = state.day;

  // how finely each leaf is drawn follows where it is seen from: worth working out again only after a real move
  const from = paper.detailFrom().position;
  const reach = organsFrom ? Math.hypot(from.x - organsFrom.x, from.y - organsFrom.y, from.z - organsFrom.z) : Infinity;
  const viewChanged = !organsFrom || organsFrom.view !== paper.view() || reach > 0.12 * Math.max(1, from.length());
  const dayChanged = state.day !== state.drawn;
  if ((dayChanged || viewChanged) && (now - organsAt > ORGANS_EVERY_MS || (!state.playing && now - organsAt > 60))) {
    plants.update(paper.detailFrom(), state.day, 1);
    organsAt = now;
    organsFrom = { x: from.x, y: from.y, z: from.z, view: paper.view() };
    if (dayChanged) shadeOwed = true;
    state.drawn = state.day;
  }
  if (shadeOwed && (now - shadeAt > SHADE_EVERY_MS || !state.playing)) {
    paper.shadeChanged();
    shadeAt = now;
    shadeOwed = false;
  }
  if (now - readAt > 200) {
    const s = plants.stats();
    el.leaves.textContent = s.leaves.toLocaleString('en-GB');
    el.flowers.textContent = s.flowers.toLocaleString('en-GB');
    readAt = now;
  }
  paper.render();
  requestAnimationFrame(draw);
}
requestAnimationFrame(draw);

// for stills and checks: put the picture at a day and a view, and draw it now
Object.assign(window, {
  studio: {
    growth,
    plants,
    paper,
    timber,
    set(day: number, id?: ViewId) {
      setPlaying(false);
      setDay(day);
      if (id) setView(id);
    },
  },
});
