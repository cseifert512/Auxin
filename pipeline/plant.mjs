// The planting, written from a rule instead of by hand, so that it follows the building when the building changes.
//   node pipeline/plant.mjs [snapshot]
// Reads  releases/<snapshot>/design.json and scenes/<snapshot>/bower.json
// Writes scenes/<snapshot>/planting.json
//
// The rule: every bed in the ring round a pier takes a plant, and which plants a pier takes depends on the side
// of the room it stands on. The sides and what suits them are from the plant library's own profiles, as gathered
// in "Plants and the shape of a Bower": warmth and sun for the tender and the free-flowering to the south and
// west, the plants that take shade and cool to the north and east, and the adaptable ones anywhere.
//
// Within a ring the first plant named goes in on the side away from the room, where the light is, and the rest
// follow round. Which member of the pier each plant then takes is the simulator's choice, not this file's: it has
// no way to be told, and where the members of a pier meet at the ground it reads them as one joint.
//
// This is a trial arrangement to see what the structure can carry. It is not a planting design.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const snapshot = process.argv.slice(2).find((a) => !a.startsWith('--')) ?? 'six-bay-v1';
const design = JSON.parse(readFileSync(resolve(root, 'releases', snapshot, 'design.json'), 'utf8'));
const bower = JSON.parse(readFileSync(resolve(root, 'scenes', snapshot, 'bower.json'), 'utf8'));

/** By the side of the room a pier stands on: taxon folders in the plant library, outermost bed first. */
const PALETTES = {
  south: ['wisteria-sinensis', 'rosa-the-generous-gardener', 'trachelospermum-jasminoides', 'clematis-cirrhosa-freckles', 'lonicera-periclymenum-graham-thomas', 'clematis-viticella-etoile-violette'],
  west: ['wisteria-floribunda-macrobotrys', 'clematis-armandi', 'campsis-x-tagliabueana-madame-galen', 'vitis-coignetiae', 'lonicera-periclymenum-graham-thomas', 'clematis-princess-diana'],
  east: ['akebia-quinata', 'lonicera-periclymenum-graham-thomas', 'clematis-viticella-etoile-violette', 'lonicera-henryi', 'rosa-the-generous-gardener', 'clematis-princess-diana'],
  north: ['hydrangea-anomala-subsp-petiolaris', 'lonicera-henryi', 'hedera-helix', 'akebia-quinata', 'lonicera-henryi', 'clematis-viticella-etoile-violette'],
};
const NAMES = {
  'wisteria-sinensis': 'wisteria',
  'wisteria-floribunda-macrobotrys': 'japanese-wisteria',
  'rosa-the-generous-gardener': 'rose',
  'trachelospermum-jasminoides': 'star-jasmine',
  'clematis-cirrhosa-freckles': 'winter-clematis',
  'clematis-armandi': 'spring-clematis',
  'clematis-viticella-etoile-violette': 'summer-clematis',
  'clematis-princess-diana': 'late-clematis',
  'lonicera-periclymenum-graham-thomas': 'honeysuckle',
  'lonicera-henryi': 'evergreen-honeysuckle',
  'campsis-x-tagliabueana-madame-galen': 'trumpet-vine',
  'vitis-coignetiae': 'vine',
  'akebia-quinata': 'akebia',
  'hydrangea-anomala-subsp-petiolaris': 'hydrangea',
  'hedera-helix': 'ivy',
};

const plants = [];
const seen = {};
for (const room of design.rooms) {
  const [cx, cy] = room.crown.centre_m;
  for (const pier of room.piers) {
    // the bearing of the pier from the middle of the room, clockwise from north
    const bearing = ((Math.atan2(pier.position_m[0] - cx, pier.position_m[1] - cy) * 180) / Math.PI + 360) % 360;
    const side = bearing >= 315 || bearing < 45 ? 'north' : bearing < 135 ? 'east' : bearing < 225 ? 'south' : 'west';
    // a second pier on the same side takes the same plants one place round, so that no two rings are alike
    const turn = (seen[side] = (seen[side] ?? -1) + 1);
    const beds = bower.stations.filter((s) => s.id.startsWith(`bed.${pier.id}.`));
    beds.forEach((bed, k) => {
      const taxonId = PALETTES[side][(k + turn) % PALETTES[side].length];
      const short = pier.id.split('.').pop();
      const twin = plants.filter((p) => p.plantId.startsWith(`${short}.${NAMES[taxonId]}`)).length;
      plants.push({ plantId: `${short}.${NAMES[taxonId]}${twin ? `.${twin + 1}` : ''}`, taxonId, stationId: bed.id });
    });
  }
}

const plan = { schemaVersion: 1, name: `Trial planting: a ring of climbers round each pier, chosen by the side of the room it stands on (${plants.length} plants)`, plants };
writeFileSync(resolve(root, 'scenes', snapshot, 'planting.json'), `{\n  "schemaVersion": 1,\n  "name": ${JSON.stringify(plan.name)},\n  "plants": [\n${plants.map((p) => `    ${JSON.stringify(p)}`).join(',\n')}\n  ]\n}\n`);
console.log(`${snapshot}: ${plants.length} plants of ${new Set(plants.map((p) => p.taxonId)).size} kinds in ${new Set(plants.map((p) => p.stationId.split('.').slice(0, 3).join('.'))).size} rings`);
