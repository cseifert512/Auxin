// A room through time: the timber as an ink drawing, the plants in colour, and one line of time to draw along.
// The line runs from the design (centre lines), through the building going together, into ten years of growth.
//
// What is drawn comes from frozen things: a snapshot of the building (releases/, at the top of the repository), the order its joints let it go
// together in, and a run of the plant simulator on it (scenes/<snapshot>/). The plants are drawn by the
// simulator's own viewer code, read in place; nothing here decides when a leaf opens or a flower falls.
import * as THREE from 'three';
import type { RenderData } from '@horti/core';
import { clock } from '@horti/viewer/plant/adapter.ts';
import { loadLooks } from '@horti/viewer/plant/registry.ts';
import { shared } from '@horti/viewer/plant/shaders.ts';
import { PlantView, makePlantMaterials } from '@horti/viewer/plant/view.ts';
import { makeBarkTextures, makeLeafTexture, makeOwnLeafTexture } from '@horti/viewer/textures.ts';
import design from '@snapshot/design.json';
import timberUrl from '@snapshot/bower.glb?url';
import centrelinesUrl from '@snapshot/centrelines.json?url';
import plan from '@scene/assembly.json';
import { type AssemblyPlan, type AssemblyState, DESIGN_SHARE, makeAssembly } from './assembly.ts';
import { PAPER, type Standpoint, type ViewId, makePaper } from './paper.ts';
import { type Centreline, type TimberLook, drawBeds, drawCables, drawOverhead, loadTimber } from './timber.ts';

const $ = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T;
const url = new URL(location.href).searchParams;
const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

// the deck's own face, where its files are beside this repository; otherwise the stack in style.css
const faces = import.meta.glob('../../../../Bower_Web/public/designx/4/assets/fonts/safiro-{regular,semibold}-webfont.woff2', { query: '?url', import: 'default', eager: true }) as Record<string, string>;
for (const [file, href] of Object.entries(faces)) {
  void new FontFace('Safiro', `url(${href})`, { weight: file.includes('semibold') ? '600' : '400' }).load().then((f) => document.fonts.add(f));
}

// ---- which planting ------------------------------------------------------------------------------------------------
// Every run of the simulator that has been grown on this machine (scenes/<snapshot>/runs/<name>/growth.json).
const grown = import.meta.glob('@scene/runs/*/growth.json', { query: '?url', import: 'default', eager: true }) as Record<string, string>;
const runs = new Map(Object.entries(grown).map(([file, href]) => [file.split('/').at(-2)!, href]));
const RUN_NAMES: Record<string, string> = { 'trained-10y': 'Tended, ten years', 'untended-10y': 'Untended, ten years' };
const run = runs.has(url.get('run') ?? '') ? url.get('run')! : runs.has('trained-10y') ? 'trained-10y' : [...runs.keys()][0];
if (!run) throw new Error('no planting has been grown yet: npm run grow');
const growthUrl = runs.get(run)!;
// each run was grown on one version of the building: the snapshot as it is, or with cables added to try
const setups = import.meta.glob('@scene/runs/*/run.json', { import: 'default', eager: true }) as Record<string, { bower?: string }>;
const builtAs = Object.entries(setups).find(([file]) => file.split('/').at(-2) === run)?.[1].bower ?? 'bower.json';
const buildings = import.meta.glob('@scene/bower*.json', { query: '?url', import: 'default', eager: true }) as Record<string, string>;
const bowerUrl = Object.entries(buildings).find(([file]) => file.endsWith(`/${builtAs}`))?.[1];
if (!bowerUrl) throw new Error(`${run} was grown on ${builtAs}, which is not in the scene: npm run convert`);

// ---- the sheet ---------------------------------------------------------------------------------------------------
const view = (id: string): Standpoint => {
  const v = design.views.find((x) => x.id === id);
  if (!v || v.lens_mm === undefined) throw new Error(`the design has no "${id}" view to stand at`);
  return { eye: v.location_m, target: v.target_m, lensMm: v.lens_mm };
};
// On an upright sheet the approach is walked on: to stand square before the bay nearest the approach, far enough
// off to see it from pier to pier, looking a little up.
const approachTall = (() => {
  const room = design.rooms[0]!;
  const from = view('exterior').eye;
  const pier = (id: string) => room.piers.find((p) => p.id === id)!.position_m;
  const bays = room.bays.map((b) => ({ a: pier(b.from), b: pier(b.to) })).map(({ a, b }) => ({ mid: [(a[0]! + b[0]!) / 2, (a[1]! + b[1]!) / 2], width: Math.hypot(b[0]! - a[0]!, b[1]! - a[1]!) }));
  const bay = bays.reduce((near, x) => (Math.hypot(x.mid[0]! - from[0]!, x.mid[1]! - from[1]!) < Math.hypot(near.mid[0]! - from[0]!, near.mid[1]! - from[1]!) ? x : near));
  const acrossDeg = 44;
  const out = [bay.mid[0]! - room.crown.centre_m[0]!, bay.mid[1]! - room.crown.centre_m[1]!];
  const far = (bay.width / 2 + 0.35) / Math.tan((acrossDeg * Math.PI) / 360) / Math.hypot(out[0]!, out[1]!);
  return { eye: [bay.mid[0]! + out[0]! * far, bay.mid[1]! + out[1]! * far, from[2]!], target: [bay.mid[0]!, bay.mid[1]!, 2.0], acrossDeg };
})();
const paper = makePaper($<HTMLCanvasElement>('sheet'), { approach: view('exterior'), inside: view('interior'), approachTall, middle: design.rooms[0]!.crown.centre_m });
// mid-afternoon in early summer, from the south-west: towards the sun, as (east, up, south)
/**
 * Towards the sun on a day of the year and at an hour by the sun, in southern England (51.5 N), as (east, up,
 * south). Good enough to put shade on the right side of things; it is not an almanac.
 */
function sunAt(dayOfYear: number, hour: number): THREE.Vector3 {
  const lat = (51.5 * Math.PI) / 180;
  const lean = ((-23.44 * Math.PI) / 180) * Math.cos((2 * Math.PI * (dayOfYear + 10)) / 365);
  const turn = ((hour - 12) * 15 * Math.PI) / 180;
  const up = Math.asin(Math.sin(lat) * Math.sin(lean) + Math.cos(lat) * Math.cos(lean) * Math.cos(turn));
  const round = Math.atan2(Math.sin(turn), Math.cos(turn) * Math.sin(lat) - Math.tan(lean) * Math.cos(lat)) + Math.PI;
  return new THREE.Vector3(Math.cos(up) * Math.sin(round), Math.sin(up), -Math.cos(up) * Math.cos(round));
}
const sunAsked = (url.get('sun') ?? '').split(',').map(Number);
paper.setSun(sunAsked.length === 2 && sunAsked.every(Number.isFinite) ? sunAt(sunAsked[0]!, sunAsked[1]!) : new THREE.Vector3(-0.609, 0.669, 0.426));
paper.resize();

const centrelines = (await (await fetch(centrelinesUrl)).json()).members as Centreline[];
const timber = await loadTimber(timberUrl, centrelines);
// in plan, the arches, the rings and the crown overhead, so that the shade has something to be read against
paper.planOnly.add(drawOverhead(centrelines, ['arch', 'ring', 'crown']));
if (url.has('grain')) timber.setGrain(Number(url.get('grain')));
paper.scene.add(timber.group);
paper.frame(timber.bounds);
const assembly = makeAssembly(timber, plan as AssemblyPlan);
paper.scene.add(assembly.group);


// ---- the plants --------------------------------------------------------------------------------------------------
const growth = (await (await fetch(growthUrl)).json()) as RenderData;
// a ring on the ground where each plant of this planting goes in
const bower = (await (await fetch(bowerUrl)).json()) as { stations: { id: string; position: number[] }[]; cables?: { id: string; points: number[][] }[] };
const bedsUsed = new Set(growth.plants.map((p) => p.stationId));
paper.scene.add(drawBeds(bower.stations.filter((s) => bedsUsed.has(s.id))));
// and any cables this version of the building has, strung once the timber stands
// as thin as they are, or marked in green to be looked at (?lines=marked)
const steel = drawCables(bower.cables ?? [], url.get('lines') === 'marked');
const steelM = (bower.cables ?? []).reduce((sum, c) => sum + c.points.slice(1).reduce((d, p, i) => d + Math.hypot(p[0]! - c.points[i]![0]!, p[1]! - c.points[i]![1]!, p[2]! - c.points[i]![2]!), 0), 0);
paper.scene.add(steel);
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
const BUILD_SECONDS = 20;
const GROW_SECONDS = 56;
const PLANTING_PAUSE_MS = 1100;
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const SEASONS = ['winter', 'winter', 'spring', 'spring', 'spring', 'summer', 'summer', 'summer', 'autumn', 'autumn', 'autumn', 'winter'];
/** What has to be said under the picture about the timber's colour, by how it is drawn. */
const TIMBER_NOTES: Record<TimberLook, string> = {
  wood: '; its colour is illustrative, and takes for granted a pigmented finish that is kept up',
  bare: '; its colour and weathering are illustrative, for timber left unfinished',
  ink: '',
};
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
// planting is the first mark of the years: the plants go in in the spring of the first
tick(planted, String(new Date(start).getUTCFullYear()));
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
    // the month, not the day: at this speed a day is gone in a fortieth of a second
    el.date.textContent = `${MONTHS[when.getUTCMonth()]} ${when.getUTCFullYear()}`;
    el.age.textContent = `year ${Math.floor((state.at - planted) / 365.25) + 1} · ${SEASONS[when.getUTCMonth()]}`;
    el.key1.textContent = 'in leaf';
    el.key2.textContent = 'in flower';
    el.statement.textContent = `${growth.statement} The timber is concept geometry${TIMBER_NOTES[look]}.`;
    return;
  }
  el.key1.textContent = 'members';
  el.key2.textContent = 'joints made';
  el.value1.textContent = `${built.placed} / ${built.of}`;
  el.value2.textContent = `${built.jointsMade} / ${built.joints}`;
  el.statement.textContent = `${assembly.note} The timber is concept geometry${look === 'ink' ? '' : '; its colour is illustrative'}.`;
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
if (['drawing', 'approach', 'inside', 'plan', 'round'].includes(url.get('view') ?? '')) setView(url.get('view') as ViewId);

// ---- timber, and which planting ----------------------------------------------------------------------------------
let look: TimberLook = url.get('timber') === 'ink' ? 'ink' : url.get('timber') === 'bare' ? 'bare' : 'wood';
const lookButtons = [...document.querySelectorAll<HTMLButtonElement>('button[data-timber]')];
function setLook(next: TimberLook): void {
  look = next;
  timber.setLook(look);
  for (const b of lookButtons) b.setAttribute('aria-pressed', String(b.dataset['timber'] === look));
  state.drawnAt = Number.NaN;
}
for (const b of lookButtons) b.addEventListener('click', () => setLook(b.dataset['timber'] as TimberLook));

const chooser = $<HTMLSelectElement>('run');
for (const name of runs.keys()) chooser.add(new Option(RUN_NAMES[name] ?? name, name, false, name === run));
chooser.hidden = runs.size < 2;
chooser.addEventListener('change', () => {
  const next = new URL(location.href);
  next.searchParams.set('run', chooser.value);
  next.searchParams.set(growing() ? 'day' : 'build', growing() ? String(Math.round(state.at)) : String(clamp01((state.at - lineStart) / BUILD_SPAN)));
  next.searchParams.delete(growing() ? 'build' : 'day');
  next.searchParams.set('view', paper.view());
  next.searchParams.set('timber', look);
  location.href = next.href;
});

// ---- what goes with the picture ----------------------------------------------------------------------------------
$('subtitle').textContent = `${design.rooms[0]!.bays.length}-bay room · ${plan.members.length} timber members · trial planting of ${growth.plants.length} climbers, tended${steelM > 0 ? ` · ${Math.round(steelM)} m of training line` : ''}`;
setLook(look);
$('loading').hidden = true;
document.querySelector<HTMLElement>('.time')!.hidden = false;
if (url.has('bare')) document.body.classList.add('bare');
// a film is the same sheet with nothing to press: the script that makes it asks for each frame in turn
const filming = url.has('film') || url.has('plate');
if (url.has('film')) document.body.classList.add('film');
// a plate is the drawing alone, on the paper of the page it is going to: no title, no line of time, no words
if (url.has('plate')) document.body.classList.add('plate');
document.body.style.background = url.has('plate') ? 'transparent' : `#${PAPER.toString(16).padStart(6, '0')}`;
if (url.has('plate')) document.documentElement.style.background = 'transparent';
setPlaying(state.playing);
setAt(state.at);
describe();

// ---- drawing -----------------------------------------------------------------------------------------------------
// Stems lengthen and thicken on the graphics card, from the day alone, so they are right in every frame. Leaves,
// flowers and fruit are worked out one by one, which for ten years of twelve plants takes about a tenth of a
// second and for twenty-four about two: while time is moving that is done as often as leaves a good four fifths
// of the time for drawing, and once more, with the shade, when it rests.
let organsEveryMs = 220;
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
    steel.visible = growing() && steelM > 0;
    timber.setAge((state.at - planted) / 365.25);
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
    if ((dayChanged || viewChanged) && (now - organsAt > organsEveryMs || (!state.playing && now - organsAt > 60))) {
      const began = performance.now();
      plants.update(paper.detailFrom(), state.at, 1);
      organsEveryMs = Math.min(900, Math.max(220, (performance.now() - began) * 4));
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
  if (!filming) requestAnimationFrame(draw);
}
let filmClock = performance.now();
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
    look: setLook,
    state: () => ({ at: state.at, built, run, look }),
    /** A place on the line of time from its name: "build:0.5", "day:3399" or "date:2031-06-20". */
    moment(name: string): number {
      const [what, value = ''] = name.split(':');
      if (what === 'build') return atBuild(Number(value));
      if (what === 'date') return (Date.parse(`${value}T00:00:00Z`) - start) / DAY_MS;
      return Number(value);
    },
    /** The line of time, for a script that will draw along it. */
    line: () => {
      // the last midsummer of the run: a film ends there, in full leaf, and not in the December the run stops in
      let summer = lastDay;
      for (let year = new Date(start + lastDay * DAY_MS).getUTCFullYear(); summer >= lastDay && year > 0; year--) summer = (Date.UTC(year, 5, 20) - start) / DAY_MS;
      return { start: lineStart, planted, last: lastDay, lastSummer: Math.max(planted, summer) };
    },
    /**
     * One frame of a film: the picture at `at` on the line of time, `seconds` after the frame before it, worked out
     * in full and drawn before this returns.
     */
    /**
     * One plate: the picture set up as asked, then drawn. `at` is a place on the line of time; `sun` a day of the
     * year and an hour; `yaw` and `up` turn the view from the middle of the room; `shade` is how dark shade is drawn;
     * `lookAt` and `zoom` bring one place close, and `from` is the side it is looked at from, in the building's axes.
     */
    async plate(p: { view?: ViewId; at?: number; timber?: TimberLook; sun?: [number, number]; yaw?: number; up?: number; shade?: number; lookAt?: number[]; zoom?: number; from?: number[] }) {
      if (p.timber) setLook(p.timber);
      if (p.sun) paper.setSun(sunAt(p.sun[0], p.sun[1]));
      if (p.shade !== undefined) paper.setShade(p.shade);
      if (p.view) setView(p.view);
      if (p.yaw !== undefined) paper.turnTo(p.yaw, p.up ?? 80);
      if (p.view === 'drawing') paper.focus(p.lookAt ?? null, p.zoom ?? 1, p.from ?? null);
      else if (p.view && p.view !== 'round') paper.zoom(p.view, p.zoom ?? 1);
      organsFrom = null;
      state.drawnAt = Number.NaN;
      await this.film(p.at ?? state.at, 0);
      await this.film(p.at ?? state.at, 0);
    },
    async film(at: number, seconds: number) {
      setPlaying(false);
      setAt(at);
      organsAt = Number.NEGATIVE_INFINITY;
      filmClock += seconds * 1000;
      draw(filmClock);
      await new Promise((shown) => requestAnimationFrame(() => requestAnimationFrame(shown)));
    },
  },
});
