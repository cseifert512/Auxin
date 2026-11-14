// Copies the dynamic drawings beside the deck, for when the deck has to stand without this repository's server
// (put on the website, or opened from a folder).
//   node deck/pieces.mjs
// Reads  drawings-in-code/exports/deck/   (made there by `npm run plate`, `pipeline/vignette.mjs`, `pipeline/again.mjs`)
// Writes deck/designx/pieces/             (not in git: about 80 MB, and a copy of what is already kept there)
//
// Day to day this is not needed: deck/serve.mjs answers /designx/pieces/ straight from where the drawings are made,
// so the deck always shows the latest. A copy made here is used in preference, so delete it when it is stale.
import { cpSync, existsSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const top = fileURLToPath(new URL('..', import.meta.url));
const from = resolve(top, 'drawings-in-code/exports/deck');
const to = resolve(top, 'deck/designx/pieces');

// what edition 08 sets into its slides
const pieces = [
  'a-room-through-time', // a slide of its own: the one piece drawn live
  '04-plants-make-space-timber', // Plants make space: the room unrolled, the light on its floor, and through time
  '05-shaded-room-timber.webp', // Growth changes the geometry: the plate for Shaded room
  'shaded-at-the-pier', // a slide of its own: the plants were shading each other
  '06-grown-again', // a slide of its own: the same pier grown three times
];

mkdirSync(to, { recursive: true });
for (const name of pieces) {
  if (!existsSync(resolve(from, name))) {
    console.log(`not made yet: ${name}`);
    continue;
  }
  cpSync(resolve(from, name), resolve(to, name), { recursive: true });
  console.log(`copied ${name}`);
}
