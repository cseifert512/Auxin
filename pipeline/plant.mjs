// The planting, written from a rule instead of by hand, so that it follows the building when the building changes.
//   node pipeline/plant.mjs [snapshot] [--palette=even|cover] [--out=planting-x.json]
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
// Two palettes:
//   even    every bed of a pier takes the next plant of its side's list. Half the plants in it are small or slow
//           (the clematis, the star jasmine, the hydrangea, the trumpet vine, the roses), and ten years on, six of
//           twenty-four carry two thirds of all the growth.
//   cover   weighted to the plants that take a structure. Each pier takes three of its side's vigorous climbers and
//           one of its smaller ones as an accent; the two most vigorous go in at the feet of the lines that run
//           furthest in over the roof. Which climber suits which side is the plant library's own statement of
//           aspect (species/<id>/taxon.json, site.aspect): wisterias and the vine to the south and west, the
//           evergreen honeysuckle and the hydrangea to the north and east, the akebia, the woodbine and ivy anywhere.
//
// Either is a trial arrangement to see what the structure can carry. It is not a planting design.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const options = Object.fromEntries(process.argv.slice(2).filter((a) => a.startsWith('--')).map((a) => a.slice(2).split('=')));
const snapshot = process.argv.slice(2).find((a) => !a.startsWith('--')) ?? JSON.parse(readFileSync(new URL('../snapshot.json', import.meta.url), 'utf8')).snapshot;
const palette = options.palette === 'cover' ? 'cover' : 'even';
const design = JSON.parse(readFileSync(resolve(root, 'releases', snapshot, 'design.json'), 'utf8'));
const bower = JSON.parse(readFileSync(resolve(root, 'scenes', snapshot, 'bower.json'), 'utf8'));

/** By the side of the room a pier stands on: taxon folders in the plant library, outermost bed first. */
const PALETTES = {
  south: ['wisteria-sinensis', 'rosa-the-generous-gardener', 'trachelospermum-jasminoides', 'clematis-cirrhosa-freckles', 'lonicera-periclymenum-graham-thomas', 'clematis-viticella-etoile-violette'],
  west: ['wisteria-floribunda-macrobotrys', 'clematis-armandi', 'campsis-x-tagliabueana-madame-galen', 'vitis-coignetiae', 'lonicera-periclymenum-graham-thomas', 'clematis-princess-diana'],
  east: ['akebia-quinata', 'lonicera-periclymenum-graham-thomas', 'clematis-viticella-etoile-violette', 'lonicera-henryi', 'rosa-the-generous-gardener', 'clematis-princess-diana'],
  north: ['hydrangea-anomala-subsp-petiolaris', 'lonicera-henryi', 'hedera-helix', 'akebia-quinata', 'lonicera-henryi', 'clematis-viticella-etoile-violette'],
};
/** By side: the climbers that take a structure, most vigorous first, and the smaller ones kept as accents. */
const COVER = {
  south: { cover: ['wisteria-sinensis', 'vitis-coignetiae', 'akebia-quinata', 'lonicera-periclymenum-graham-thomas'], accent: ['rosa-the-generous-gardener', 'trachelospermum-jasminoides', 'clematis-cirrhosa-freckles', 'clematis-viticella-etoile-violette'] },
  west: { cover: ['wisteria-floribunda-macrobotrys', 'vitis-coignetiae', 'akebia-quinata', 'lonicera-periclymenum-graham-thomas'], accent: ['clematis-armandi', 'campsis-x-tagliabueana-madame-galen', 'clematis-princess-diana'] },
  east: { cover: ['akebia-quinata', 'lonicera-periclymenum-graham-thomas', 'lonicera-henryi', 'hedera-helix'], accent: ['rosa-the-generous-gardener', 'clematis-viticella-etoile-violette', 'clematis-princess-diana'] },
  north: { cover: ['akebia-quinata', 'hedera-helix', 'lonicera-henryi', 'lonicera-periclymenum-graham-thomas'], accent: ['hydrangea-anomala-subsp-petiolaris', 'clematis-viticella-etoile-violette'] },
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
    // cover: three vigorous climbers and an accent. The beds at the feet of the lines that go in over the roof (on
    // the second ribs) take the first two; the beds on the hoops, beside the doorways, the third and the accent.
    const { cover, accent } = COVER[side];
    const inOverRoof = (bed) => (/\.fill\./.test(bed.note ?? '') ? 0 : 1);
    const chosen = [cover[turn % cover.length], cover[(turn + 1) % cover.length], cover[(turn + 2) % cover.length], accent[turn % accent.length]];
    const order = palette === 'cover' ? [...beds].sort((a, b) => inOverRoof(a) - inOverRoof(b)) : beds;
    order.forEach((bed, k) => {
      const taxonId = palette === 'cover' ? chosen[k % chosen.length] : PALETTES[side][(k + turn) % PALETTES[side].length];
      const short = pier.id.split('.').pop();
      const twin = plants.filter((p) => p.plantId.startsWith(`${short}.${NAMES[taxonId]}`)).length;
      plants.push({ plantId: `${short}.${NAMES[taxonId]}${twin ? `.${twin + 1}` : ''}`, taxonId, stationId: bed.id });
    });
  }
}

const plan = { schemaVersion: 1, name: palette === 'cover' ? `Trial planting for cover: three vigorous climbers and an accent at each pier, chosen by the side of the room it stands on (${plants.length} plants)` : `Trial planting: a ring of climbers round each pier, chosen by the side of the room it stands on (${plants.length} plants)`, plants };
const counts = {};
for (const p of plants) counts[NAMES[p.taxonId]] = (counts[NAMES[p.taxonId]] ?? 0) + 1;
console.log(`  ${palette}: ${Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([name, n]) => `${n} ${name}`).join(', ')}`);
writeFileSync(resolve(root, 'scenes', snapshot, options.out ?? 'planting.json'), `{\n  "schemaVersion": 1,\n  "name": ${JSON.stringify(plan.name)},\n  "plants": [\n${plants.map((p) => `    ${JSON.stringify(p)}`).join(',\n')}\n  ]\n}\n`);
console.log(`${snapshot}: ${plants.length} plants of ${new Set(plants.map((p) => p.taxonId)).size} kinds in ${new Set(plants.map((p) => p.stationId.split('.').slice(0, 3).join('.'))).size} rings`);
