// A frozen snapshot of the building -> the file the plant simulator reads.
//   node pipeline/convert.mjs [snapshot]
// Reads  releases/<snapshot>/centrelines.json and design.json
// Writes scenes/<snapshot>/bower.json
//
// The snapshot says what is built. This adds the two things a planting needs
// that the building model does not hold yet: where plants go into the ground
// (four beds at the foot of each pier, two towards each neighbouring bay) and
// where a visitor stands. Both are this project's assumptions, not the model's.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const snapshot = process.argv[2] ?? 'six-bay-v1';
const from = resolve(root, 'releases', snapshot);
const to = resolve(root, 'scenes', snapshot);
const read = (name) => JSON.parse(readFileSync(resolve(from, name), 'utf8'));

const centrelines = read('centrelines.json');
const design = read('design.json');
if (centrelines.units !== 'm' || centrelines.axes?.up !== '+Z' || centrelines.axes?.north !== '+Y') {
  throw new Error(`${snapshot}: centrelines.json is not in metres with Z up and Y north`);
}

/** Beds stand this far inside the line of the arches, and this far to either side of the pier: a near one and a far one. */
const BED_INSIDE_M = 0.5;
const BEDS_ASIDE_M = [
  ['', 0.8],
  ['.far', 1.35],
];

const round = (v, places = 4) => Number(v.toFixed(places));
const members = centrelines.members.map((m) => ({
  id: m.id,
  tier: 'primary',
  role: m.family,
  section: { shape: 'rect', widthMm: round(m.width_m * 1000, 1), depthMm: round(m.depth_m * 1000, 1) },
  points: m.points_m.map((p) => p.map((c) => round(c))),
}));

const stations = [];
for (const room of design.rooms) {
  const [cx, cy] = room.crown.centre_m;
  for (const pier of room.piers) {
    const [px, py] = pier.position_m;
    const l = Math.hypot(px - cx, py - cy);
    const out = [(px - cx) / l, (py - cy) / l];
    const along = [-out[1], out[0]];
    // the bay that starts at this pier lies on its +along side; the one that ends at it on the other
    const starts = room.bays.find((b) => b.from === pier.id);
    const ends = room.bays.find((b) => b.to === pier.id);
    for (const [bay, side] of [[starts, 1], [ends, -1]]) {
      if (!bay) continue;
      for (const [suffix, aside] of BEDS_ASIDE_M) {
        stations.push({
          id: `bed.${pier.id}.${bay.id.split('.').pop()}${suffix}`,
          position: [round(px - out[0] * BED_INSIDE_M + along[0] * aside * side, 3), round(py - out[1] * BED_INSIDE_M + along[1] * aside * side, 3), room.floor_z_m ?? 0],
          note: `${aside} m from pier ${pier.id}, on the side of bay ${bay.id}`,
        });
      }
    }
  }
}

// a full-frame lens of this focal length sees this far across, top to bottom
const fovOf = (lensMm) => round((2 * Math.atan(12 / lensMm) * 180) / Math.PI, 1);
const VIEW_LABELS = { interior: 'Standing inside, looking up to the crown', exterior: 'Approaching from the south', overhead: 'From above, to the south-east' };
const viewpoints = design.views
  .filter((v) => v.projection === 'persp' && VIEW_LABELS[v.id])
  .map((v) => ({ id: v.id, label: VIEW_LABELS[v.id], eye: v.location_m, target: v.target_m, fovDeg: fovOf(v.lens_mm) }));

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
console.log(`${snapshot}: ${members.length} members, ${members.reduce((n, m) => n + m.points.length, 0)} points, ${stations.length} beds, ${viewpoints.length} viewpoints`);
console.log(`written: ${resolve(to, 'bower.json')}`);
