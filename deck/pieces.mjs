// Copies the pictures a version of ours uses out of the drawings, so that the version's folder stands by itself.
//   node deck/pieces.mjs
// Reads  drawings-in-code/exports/deck/   (made there by `npm run plate`)
// Writes deck/designx/v8/frames/
// Run it again after a plate is remade. The copies are kept in git: the site must open with nothing else beside it.
import { copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const top = fileURLToPath(new URL('..', import.meta.url));
const from = resolve(top, 'drawings-in-code/exports/deck');
const to = resolve(top, 'deck/designx/v8/frames');
const numbered = (n) => Array.from({ length: n }, (_, i) => String(i).padStart(2, '0'));

const pieces = [
  // the room through time, timber in its colour: from above, on the approach, inside
  ...numbered(34).map((i) => [`04-plants-make-space-timber/frames/time-${i}.webp`, `time-${i}.webp`]),
  // one midsummer day on the floor of the room, at three ages
  ...numbered(37).map((i) => [`04-plants-make-space/frames/light-${i}.webp`, `light-${i}.webp`]),
  // the room unrolled, established, in summer
  ['04-plants-make-space-timber/frames/space-07.webp', 'space.webp'],
  // one lap as every lap is cut, cut splayed, grown; and the room
  ['found-the-joints.webp', 'joints.webp'],
];

mkdirSync(to, { recursive: true });
let missing = 0;
for (const [source, name] of pieces) {
  if (!existsSync(resolve(from, source))) {
    console.log(`not made yet: ${source}`);
    missing++;
    continue;
  }
  copyFileSync(resolve(from, source), resolve(to, name));
}
console.log(`${pieces.length - missing} pictures in deck/designx/v8/frames${missing ? `, ${missing} missing` : ''}`);
