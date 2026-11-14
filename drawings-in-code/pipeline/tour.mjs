// A film of a turn through the forms a room can take: the timber moved from form to form with a planting on it,
// the seasons going by, seen from a camera that goes round.
//   node pipeline/tour.mjs [name] [grow | film]      (tours/<name>/tour.json; "first" if none is named)
//     grow                 grow the planting on every form that has none yet, one after another (--again: on every form)
//     film                 the film (the default)
//       --still=12.5       one picture, at that many seconds into the film, and no film
//       --fps=24 --scale=2 --size=960x540
//       --back=0.5 --lift=2 --turn=40   the camera nearer, higher, or further round than the tour says: to look at a joint
//       --frames=keep      put the film together again from the pictures already made
// Reads  tours/<name>/tour.json, and beside it states.json (bower-blender/scripts/tour_states.py)
// Writes exports/tour-<name>/tour-<name>.mp4 and a still beside it
//
// What the film is, and is not. Every state of the timber is one the generator builds. A planting is grown on each
// form of the tour and on no state between: between two forms the plants are those of the nearer form, carried on
// the moving timber (studio/src/tour.ts), and across the middle of the way one planting is dissolved into the next,
// picture into picture. So a film is taken once for each form, one studio open at a time, and the takes are laid
// over each other afterwards. It is a picture of the forms a room can take with a planting on each: no building
// moves, and nothing grew on the states in between.
import { execFileSync } from 'node:child_process';
import { closeSync, copyFileSync, existsSync, mkdirSync, openSync, readFileSync, readSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { root, startStudio } from './headless.mjs';

const args = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const options = Object.fromEntries(process.argv.slice(2).filter((a) => a.startsWith('--')).map((a) => a.slice(2).split('=')));
const what = args.find((a) => a === 'grow' || a === 'film') ?? 'film';
const name = args.find((a) => a !== 'grow' && a !== 'film') ?? 'first';
const folder = resolve(root, 'tours', name);
const tour = JSON.parse(readFileSync(resolve(folder, 'tour.json'), 'utf8'));
if (!existsSync(resolve(folder, 'states.json'))) throw new Error(`no states yet: cd ../bower-blender && python scripts/tour_states.py ${resolve(folder, 'tour.json')}`);
// only what says which state each form is, and where it was grown: the states themselves are for the studio
const { forms, between, loop, states: allStates } = JSON.parse(readFileSync(resolve(folder, 'states.json'), 'utf8'));
const stateCount = allStates.length;
// The planting is the one the other drawings are made from (README, "Run it"): the scheme `npm run plant` writes
// unless told another, ten tended years, specimens standing 3 m and the wisterias 4 m. A tour may say otherwise.
const PLANTING = { care: 'trained', years: 10, seed: 7, specimen: 3, tall: 'wisteria:4', scheme: null, ...(tour.planting ?? {}) };
const runOf = (form) => resolve(root, 'scenes', form.grown_on, 'runs', `${PLANTING.care}-${PLANTING.years}y`);

// ---- the plantings ---------------------------------------------------------------------------------------------------
if (what === 'grow') {
  const node = (script, ...rest) => execFileSync(process.execPath, [resolve(root, 'pipeline', script), ...rest], { cwd: root, stdio: 'inherit' });
  for (const form of forms) {
    // --again: grow them all afresh, as after the planting's rule or the simulator has changed
    if (existsSync(resolve(runOf(form), 'growth.json')) && !('again' in options)) continue;
    console.log(`growing on ${form.grown_on}`);
    node('convert.mjs', form.grown_on);
    node('plant.mjs', form.grown_on, ...(PLANTING.scheme ? [`--scheme=${PLANTING.scheme}`] : []));
    node('grow.mjs', form.grown_on, PLANTING.care, String(PLANTING.years), String(PLANTING.seed), `--specimen=${PLANTING.specimen}`, ...(PLANTING.tall ? [`--tall=${PLANTING.tall}`] : []));
  }
  process.exit(0);
}
for (const form of forms) if (!existsSync(resolve(runOf(form), 'growth.json'))) throw new Error(`no planting grown on ${form.grown_on}: node pipeline/tour.mjs ${name} grow`);

// ---- the score: where the film is at each moment ----------------------------------------------------------------------
const film = { seconds: 36, fps: 24, turns: 1, yaw: 0, hold: 1.5, dissolve: [0.35, 0.65], calendar: { from: '2035-01-10', to: '2036-01-10' }, timber: 'wood', view: 'approach', back: 1.15, lift: 1, ...(tour.film ?? {}) };
const fps = Number(options.fps ?? film.fps);
const [w, h] = (options.size ?? '960x540').split('x').map(Number);
const scale = Number(options.scale ?? 2);
const legs = loop ? forms.length : forms.length - 1;
const legSeconds = film.seconds / legs;
const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};
/** Day 0 of a planting, read from the head of its record without reading the hundred megabytes after it. */
function startOf(form) {
  const file = openSync(resolve(runOf(form), 'growth.json'), 'r');
  const head = Buffer.alloc(4096);
  readSync(file, head, 0, 4096, 0);
  closeSync(file);
  const found = head.toString('utf8').match(/"start":"(\d{4}-\d\d-\d\d)"/);
  if (!found) throw new Error(`${form.grown_on}: the planting's record does not say when it starts`);
  return Date.parse(`${found[1]}T00:00:00Z`);
}
const start = startOf(forms[0]);
const dayOf = (date) => (Date.parse(`${date}T00:00:00Z`) - start) / 86_400_000;
const days = [dayOf(film.calendar.from), dayOf(film.calendar.to)];

/** The film at `t` seconds: where on the tour, which day, where the camera is, and how much of each planting shows. */
function at(t) {
  const leg = Math.min(legs - 1, Math.floor(t / legSeconds));
  const into = t - leg * legSeconds;
  // it rests on a form, then goes on to the next
  const x = into <= film.hold ? 0 : smooth(0, 1, (into - film.hold) / (legSeconds - film.hold));
  const next = (leg + 1) % forms.length;
  const more = smooth(film.dissolve[0], film.dissolve[1], x);
  return {
    at: (leg + x) * (between + 1),
    day: days[0] + ((days[1] - days[0]) * t) / film.seconds,
    yaw: film.yaw + (360 * film.turns * t) / film.seconds,
    shows: more <= 0 ? [[leg, 1]] : more >= 1 ? [[next, 1]] : [[leg, 1 - more], [next, more]],
    title: forms[more < 0.5 ? leg : next].title,
  };
}
const total = Math.round(film.seconds * fps);
const wanted = 'still' in options ? [Math.round(Number(options.still) * fps)] : Array.from({ length: total }, (_, i) => i);
const moments = new Map(wanted.map((i) => [i, at(i / fps)]));

const out = resolve(root, 'exports', `tour-${name}`);
const takes = resolve(out, 'frames');
const ffmpeg = createRequire(import.meta.url)('ffmpeg-static');
const run = (list) => execFileSync(ffmpeg, ['-y', '-loglevel', 'error', ...list], { maxBuffer: 1 << 28 });
const shot = (form, i) => resolve(takes, forms[form].id, `${String(i).padStart(5, '0')}.jpg`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fromDisk = (file) => `/@fs/${file.replaceAll('\\', '/')}`;
mkdirSync(out, { recursive: true });

// ---- the takes: one studio, one planting, then the next ---------------------------------------------------------------
if (options.frames !== 'keep') {
  if (!('still' in options)) rmSync(takes, { recursive: true, force: true });
  for (const [q, form] of forms.entries()) {
    const mine = wanted.filter((i) => moments.get(i).shows.some(([f]) => f === q));
    if (!mine.length) continue;
    mkdirSync(resolve(takes, form.id), { recursive: true });
    const began = performance.now();
    // this planting is drawn from the middle of the way from the form before to the middle of the way to the next
    const span = [(q - 1 + film.dissolve[0]) * (between + 1), (q + film.dissolve[1]) * (between + 1)].map((s) => (loop ? s : Math.min(stateCount - 1, Math.max(0, s))));
    const studio = await startStudio(5334, tour.snapshot);
    const page = await studio.open(
      { film: '', view: film.view, timber: film.timber, day: String(Math.round(days[0])), tour: fromDisk(resolve(folder, 'states.json')), growth: fromDisk(resolve(runOf(form), 'growth.json')), form: form.id, span: span.join(','), days: days.map(Math.round).join(','), ...(film.title ? { title: film.title } : {}), ...(film.subtitle ? { subtitle: film.subtitle } : {}) },
      { width: w, height: h, scale },
    );
    for (let i = 0; i < 600; i++) {
      if (await page.js('typeof window.studio.tour === "object"')) break;
      if (page.problems.length) throw new Error(`the studio failed to set the tour up:\n  ${page.problems.join('\n  ')}`);
      await sleep(500);
    }
    const tied = await page.js('window.studio.tour.tied');
    console.log(`${form.id}: ${mine.length} pictures; ${tied.onTimber} of ${tied.points} stem points lie on timber, ${tied.organs} leaves, flowers and the rest go with them (tied in ${tied.seconds.toFixed(1)} s)`);
    for (const [n, i] of mine.entries()) {
      const m = moments.get(i);
      await page.js(`window.studio.tour.frame(${JSON.stringify({ at: m.at, day: m.day, yaw: m.yaw + Number(options.turn ?? 0), back: Number(options.back ?? film.back), lift: Number(options.lift ?? film.lift), title: m.title, seconds: 1 / fps, view: film.view })})`);
      writeFileSync(shot(q, i), await page.shot('jpeg'));
      if (page.problems.length) throw new Error(`the studio failed while filming:\n  ${page.problems.join('\n  ')}`);
      if (n % 60 === 59) console.log(`  ${n + 1} of ${mine.length}: ${((performance.now() - began) / 1000 / (n + 1)).toFixed(1)} s a picture`);
    }
    const made = await page.js('window.studio.tour.made()');
    const cut = await page.js('window.studio.tour.timber()');
    studio.stop();
    console.log(`  ${form.id} in ${((performance.now() - began) / 1000).toFixed(0)} s; the plants were placed afresh ${made} times; in the last picture ${cut.lapsCut} lap notches are cut and ${cut.lapsNotCut} could not be`);
    await sleep(3000);
  }
}

// ---- the takes laid over each other ----------------------------------------------------------------------------------
const laid = resolve(takes, 'laid');
mkdirSync(laid, { recursive: true });
for (const [n, i] of wanted.entries()) {
  const { shows } = moments.get(i);
  const to = resolve(laid, `${String(n).padStart(5, '0')}.jpg`);
  if (shows.length === 1) copyFileSync(shot(shows[0][0], i), to);
  else run(['-i', shot(shows[0][0], i), '-i', shot(shows[1][0], i), '-filter_complex', `[0:v][1:v]blend=all_expr='A*${shows[0][1].toFixed(4)}+B*${shows[1][1].toFixed(4)}'`, '-q:v', '2', to]);
}
if ('still' in options) {
  const file = resolve(out, `still-${String(options.still).replace('.', '_')}s.jpg`);
  copyFileSync(resolve(laid, '00000.jpg'), file);
  console.log(`written: ${file}`);
  process.exit(0);
}
const file = resolve(out, `tour-${name}.mp4`);
run(['-framerate', String(fps), '-i', resolve(laid, '%05d.jpg'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', file]);
copyFileSync(resolve(laid, `${String(Math.round(total * 0.45)).padStart(5, '0')}.jpg`), resolve(out, `tour-${name}.jpg`));
console.log(`written: ${file}, ${total} pictures at ${fps} a second`);
process.exit(0);
