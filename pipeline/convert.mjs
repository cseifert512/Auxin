// A frozen snapshot of the building -> the file the plant simulator reads.
//   node pipeline/convert.mjs [snapshot]
// Reads  releases/<snapshot>/centrelines.json and design.json
// Writes scenes/<snapshot>/bower.json
//
// The snapshot says what is built. This adds the two things a planting needs
// that the building model does not hold yet: where plants go into the ground,
// and where a visitor stands. Both are this project's assumptions.
//
// Plants go in where the timber meets the ground, and nowhere else: the
// structure is what they grow on. On this building that is the six piers, each
// a sheaf of members gathered to the ground like a trunk, so the beds are a
// ring round each pier. The simulator will not take a bed more than 1.5 m from
// something to climb, and nothing is added for plants to climb.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const snapshot = process.argv.slice(2).find((a) => !a.startsWith('--')) ?? 'six-bay-v1';
const from = resolve(root, 'releases', snapshot);
const to = resolve(root, 'scenes', snapshot);
const read = (name) => JSON.parse(readFileSync(resolve(from, name), 'utf8'));

const centrelines = read('centrelines.json');
const design = read('design.json');
if (centrelines.units !== 'm' || centrelines.axes?.up !== '+Z' || centrelines.axes?.north !== '+Y') {
  throw new Error(`${snapshot}: centrelines.json is not in metres with Z up and Y north`);
}

/** Beds in the ring round each pier, and how far the ring stands from the middle of the pier's feet. */
const BEDS_PER_PIER = 6;
const RING_M = 0.85;
const COMPASS = ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west'];
const compass = (dx, dy) => COMPASS[Math.round(((Math.atan2(dx, dy) * 180) / Math.PI + 360) / 45) % 8];

const round = (v, places = 4) => Number(v.toFixed(places));
const members = centrelines.members.map((m) => ({
  id: m.id,
  tier: 'primary',
  role: m.family,
  section: { shape: 'rect', widthMm: round(m.width_m * 1000, 1), depthMm: round(m.depth_m * 1000, 1) },
  points: m.points_m.map((p) => p.map((c) => round(c))),
}));

// every place a member comes to the ground
const feet = centrelines.members.flatMap((m) => [m.points_m[0], m.points_m[m.points_m.length - 1]].filter((p) => p[2] < 0.06).map((p) => ({ member: m.id, at: p })));

const stations = [];
for (const room of design.rooms) {
  const [cx, cy] = room.crown.centre_m;
  for (const pier of room.piers) {
    const [px, py] = pier.position_m;
    const own = feet.filter((f) => Math.hypot(f.at[0] - px, f.at[1] - py) < 1.3);
    if (!own.length) throw new Error(`${snapshot}: no member comes to the ground at pier ${pier.id}`);
    const mx = own.reduce((s, f) => s + f.at[0], 0) / own.length;
    const my = own.reduce((s, f) => s + f.at[1], 0) / own.length;
    // the first bed stands on the side away from the room, the rest follow round
    const out = Math.atan2(my - cy, mx - cx);
    for (let k = 0; k < BEDS_PER_PIER; k++) {
      const a = out + (k * 2 * Math.PI) / BEDS_PER_PIER;
      const x = mx + RING_M * Math.cos(a);
      const y = my + RING_M * Math.sin(a);
      stations.push({
        id: `bed.${pier.id}.${k + 1}`,
        position: [round(x, 3), round(y, 3), room.floor_z_m ?? 0],
        note: `in the ring round pier ${pier.id} (${own.length} members come to the ground here), on its ${compass(x - mx, y - my)} side; the pier stands to the ${compass(px - cx, py - cy)} of the room`,
      });
    }
  }
}

// a full-frame lens of this focal length sees this far across, top to bottom
const fovOf = (lensMm) => round((2 * Math.atan(12 / lensMm) * 180) / Math.PI, 1);
const VIEW_LABELS = { interior: 'Standing inside, looking up to the crown', exterior: 'Approaching from the south', overhead: 'From above, to the south-east' };
const viewpoints = design.views
  .filter((v) => v.projection === 'persp' && VIEW_LABELS[v.id])
  .map((v) => ({ id: v.id, label: VIEW_LABELS[v.id], eye: v.location_m, target: v.target_m, fovDeg: fovOf(v.lens_mm) }));
// the approach again from the other side
const south = viewpoints.find((v) => v.id === 'exterior');
if (south) viewpoints.push({ id: 'north', label: 'Approaching from the north', eye: [-south.eye[0], -south.eye[1], south.eye[2]], target: [-south.target[0], -south.target[1], south.target[2]], fovDeg: south.fovDeg });

const bower = {
  schemaVersion: 1,
  id: snapshot,
  name: `the ${design.rooms.map((r) => `${r.bays.length}-bay`).join(' and ')} room, snapshot ${snapshot}`,
  frame: 'x east, y north, z up, metres',
  members,
  stations,
  viewpoints,
};

mkdirSync(to, { recursive: true });
writeFileSync(resolve(to, 'bower.json'), `${JSON.stringify(bower)}\n`);
console.log(`${snapshot}: ${members.length} members, ${feet.length} of their ends on the ground at ${design.rooms.reduce((n, r) => n + r.piers.length, 0)} piers, ${stations.length} beds, ${viewpoints.length} viewpoints`);
console.log(`written: ${resolve(to, 'bower.json')}`);
