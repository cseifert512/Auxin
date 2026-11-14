// The planting, written from a rule instead of by hand, so that it follows the building when the building changes.
//   node pipeline/plant.mjs [snapshot] [--scheme=piers|woven|cover|even] [--out=planting-x.json]
// Reads  releases/<snapshot>/design.json and scenes/<snapshot>/bower.json
// Writes scenes/<snapshot>/planting.json
//
// A plant can go in only at the foot of a training line, and the lines start at the piers. Each pier has two kinds
// of place: at the feet of the lines that run in over the roof (on the second ribs), and at the feet of the lines
// that go over one bay, beside its doorway (on the hoops). A scheme says what goes where.
//
// Two schemes are designs, and the choice between them is the designer's:
//
//   piers   Divided. Each pier is one character, and the characters alternate round the room, so that every one
//           of them is met on every side and no plant is on one side only.
//             the wisteria pier   two wisterias over the roof, the Chinese and the Japanese: they flower one after
//                                 the other through May, the second with the longest racemes, and twine opposite
//                                 ways. Beside the doorways, where scent and flower are met at the height of a face,
//                                 the woodbine, which carries on from June to September and takes the shade under
//                                 the wisterias, and an evergreen so that no pier is bare in winter: the spring
//                                 clematis (flower in March, before anything else) where the pier is warm enough
//                                 for it, the evergreen honeysuckle where it is not.
//             the vine pier       the vine and the akebia over the roof: the largest leaf and the densest cover,
//                                 and the autumn. Evergreen honeysuckle and ivy on the legs, held below the spring
//                                 of the roof, so that in winter the piers are clothed and the roof lets the light in.
//           The warmer piers go to the wisterias, which flower by the sun they get. Read plainly: each plant has
//           its place, each bay runs from one character to the other, and a visitor can name what they are under.
//   woven   Integrated. Every pier carries the same company (a wisteria, an akebia or the vine, a woodbine, an
//           evergreen), and nothing is held back: the plants meet over the roof and grow through one another, and
//           the building is one texture all round. It is the fuller and the less legible of the two, and asks more
//           of the gardener, who has to keep four habits of growth apart on every pier instead of two.
//
// Two are the earlier trials, kept to compare with:
//   cover   by the side of the room: three of that side's vigorous climbers and one accent to a pier
//   even    by the side of the room: the next plant of that side's list to each bed, small and vigorous alike
//
// Which climber suits which aspect is the plant library's own statement (species/<id>/taxon.json, site.aspect).
// The designed schemes set wisterias on the cooler piers as well as the warmer: the library says "preferably south
// or west facing", and this is an open room, not a wall, where the simulator's light model gives a north pier most
// of an open site's light. A run's report says where a plant has less sun than its profile asks.
//
// Which member of the pier each plant then takes is the simulator's choice, not this file's. All of these are
// arrangements to see what the structure can carry and how it reads. None is a planting plan for a site.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const options = Object.fromEntries(process.argv.slice(2).filter((a) => a.startsWith('--')).map((a) => a.slice(2).split('=')));
const snapshot = process.argv.slice(2).find((a) => !a.startsWith('--')) ?? JSON.parse(readFileSync(new URL('../snapshot.json', import.meta.url), 'utf8')).snapshot;
const scheme = options.scheme ?? options.palette ?? 'piers';
const design = JSON.parse(readFileSync(resolve(root, 'releases', snapshot, 'design.json'), 'utf8'));
const bower = JSON.parse(readFileSync(resolve(root, 'scenes', snapshot, 'bower.json'), 'utf8'));

const WISTERIAS = ['wisteria-sinensis', 'wisteria-floribunda-macrobotrys'];
/**
 * The designed schemes: characters that alternate round the ring of piers. Each place is a list of plants taken in
 * turn by the piers of that character, so that two piers alike in kind differ in cultivar; or two lists, one for a
 * pier on the south and west of the room (`warm`) and one for any other (`cool`), where a plant asks for warmth.
 * `held` are the plants not taken above the spring of the roof.
 */
const DESIGNED = {
  piers: {
    says: 'each pier one character, wisteria piers and vine piers alternating round the room',
    characters: [
      { roof: [WISTERIAS, [...WISTERIAS].reverse()], door: [['lonicera-periclymenum-graham-thomas'], { warm: ['clematis-armandi'], cool: ['lonicera-henryi'] }], held: [] },
      { roof: [['vitis-coignetiae'], ['akebia-quinata']], door: [['lonicera-henryi'], ['hedera-helix']], held: ['lonicera-henryi', 'hedera-helix'] },
    ],
  },
  woven: {
    says: 'every pier the same company, grown through one another',
    characters: [{ roof: [WISTERIAS, ['akebia-quinata', 'vitis-coignetiae']], door: [['lonicera-periclymenum-graham-thomas'], ['lonicera-henryi', 'hedera-helix']], held: [] }],
  },
};
/** How far up a held plant is taken, as a share of the building's height: about where the legs turn into the roof. */
const HELD_SHARE = 0.55;

/** By the side of the room a pier stands on: taxon folders in the plant library, outermost bed first. */
const BY_SIDE = {
  south: ['wisteria-sinensis', 'rosa-the-generous-gardener', 'trachelospermum-jasminoides', 'clematis-cirrhosa-freckles', 'lonicera-periclymenum-graham-thomas', 'clematis-viticella-etoile-violette'],
  west: ['wisteria-floribunda-macrobotrys', 'clematis-armandi', 'campsis-x-tagliabueana-madame-galen', 'vitis-coignetiae', 'lonicera-periclymenum-graham-thomas', 'clematis-princess-diana'],
  east: ['akebia-quinata', 'lonicera-periclymenum-graham-thomas', 'clematis-viticella-etoile-violette', 'lonicera-henryi', 'rosa-the-generous-gardener', 'clematis-princess-diana'],
  north: ['hydrangea-anomala-subsp-petiolaris', 'lonicera-henryi', 'hedera-helix', 'akebia-quinata', 'lonicera-henryi', 'clematis-viticella-etoile-violette'],
};
/** By side: the climbers that take a structure, most vigorous first, and the smaller ones kept as accents. */
const COVER_BY_SIDE = {
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
if (!DESIGNED[scheme] && scheme !== 'cover' && scheme !== 'even') throw new Error(`no planting scheme "${scheme}": piers, woven, cover or even`);

const plants = [];
const put = (pier, bed, taxonId, train) => {
  const short = pier.id.split('.').pop();
  const twin = plants.filter((p) => p.plantId.startsWith(`${short}.${NAMES[taxonId]}`)).length;
  plants.push({ plantId: `${short}.${NAMES[taxonId]}${twin ? `.${twin + 1}` : ''}`, taxonId, stationId: bed.id, ...(train ? { train } : {}) });
};
/** The beds of a pier: those at the feet of the lines that go in over the roof first, then those beside the doorways. */
const overRoof = (bed) => /\.fill\./.test(bed.note ?? '');
const bedsOf = (pier) => bower.stations.filter((s) => s.id.startsWith(`bed.${pier.id}.`));
const top = Math.max(...bower.members.flatMap((m) => m.points.map((p) => p[2])));
const seen = {};

for (const room of design.rooms) {
  const [cx, cy] = room.crown.centre_m;
  /** The bearing of a pier from the middle of the room, clockwise from north. */
  const bearingOf = (pier) => ((Math.atan2(pier.position_m[0] - cx, pier.position_m[1] - cy) * 180) / Math.PI + 360) % 360;

  if (DESIGNED[scheme]) {
    const { characters } = DESIGNED[scheme];
    // Round the ring the characters alternate. Which pier the round starts at is chosen so that the first
    // character, the one that flowers by the sun it gets, has the most piers it can on the south and west of the
    // room (the library's "south or west facing": from south-east round to north-west), and of those the warmest.
    const warm = (pier) => bearingOf(pier) > 112.5 && bearingOf(pier) < 292.5;
    const warmth = (pier) => (warm(pier) ? 1 : 0) + 0.01 * Math.cos(((bearingOf(pier) - 202.5) * Math.PI) / 180);
    let start = 0;
    let best = -Infinity;
    for (let s = 0; s < characters.length; s++) {
      const sum = room.piers.reduce((n, pier, k) => n + ((k + s) % characters.length === 0 ? warmth(pier) : 0), 0);
      if (sum > best) {
        best = sum;
        start = s;
      }
    }
    const met = characters.map(() => 0);
    room.piers.forEach((pier, k) => {
      const which = (k + start) % characters.length;
      const character = characters[which];
      const nth = met[which]++;
      const beds = bedsOf(pier);
      const places = [
        [beds.filter(overRoof), character.roof],
        [beds.filter((b) => !overRoof(b)), character.door],
      ];
      for (const [at, lists] of places) {
        at.forEach((bed, i) => {
          const given = lists[i % lists.length];
          const list = Array.isArray(given) ? given : warm(pier) ? given.warm : given.cool;
          const taxonId = list[nth % list.length];
          put(pier, bed, taxonId, character.held.includes(taxonId) ? { extent: { to: 'height', heightM: Number((top * HELD_SHARE).toFixed(1)) } } : null);
        });
      }
    });
    continue;
  }

  for (const pier of room.piers) {
    const bearing = bearingOf(pier);
    const side = bearing >= 315 || bearing < 45 ? 'north' : bearing < 135 ? 'east' : bearing < 225 ? 'south' : 'west';
    // a second pier on the same side takes the same plants one place round, so that no two rings are alike
    const turn = (seen[side] = (seen[side] ?? -1) + 1);
    const beds = bedsOf(pier);
    // cover: three vigorous climbers and an accent. The beds over the roof take the first two; the beds beside the
    // doorways, the third and the accent.
    const { cover, accent } = COVER_BY_SIDE[side];
    const chosen = [cover[turn % cover.length], cover[(turn + 1) % cover.length], cover[(turn + 2) % cover.length], accent[turn % accent.length]];
    const order = scheme === 'cover' ? [...beds].sort((a, b) => Number(overRoof(b)) - Number(overRoof(a))) : beds;
    order.forEach((bed, k) => put(pier, bed, scheme === 'cover' ? chosen[k % chosen.length] : BY_SIDE[side][(k + turn) % BY_SIDE[side].length], null));
  }
}

const NAME = {
  piers: `Planting divided by pier: ${DESIGNED.piers.says}`,
  woven: `Planting woven: ${DESIGNED.woven.says}`,
  cover: 'Trial planting for cover: three vigorous climbers and an accent at each pier, chosen by the side of the room it stands on',
  even: 'Trial planting: a ring of climbers round each pier, chosen by the side of the room it stands on',
};
const name = `${NAME[scheme]} (${plants.length} plants)`;
const counts = {};
for (const p of plants) counts[NAMES[p.taxonId]] = (counts[NAMES[p.taxonId]] ?? 0) + 1;
console.log(`  ${scheme}: ${Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([kind, n]) => `${n} ${kind}`).join(', ')}`);
const held = plants.filter((p) => p.train);
if (held.length) console.log(`  held below ${held[0].train.extent.heightM} m (the building stands ${top.toFixed(1)} m): ${held.map((p) => p.plantId).join(', ')}`);
writeFileSync(resolve(root, 'scenes', snapshot, options.out ?? 'planting.json'), `{\n  "schemaVersion": 1,\n  "name": ${JSON.stringify(name)},\n  "plants": [\n${plants.map((p) => `    ${JSON.stringify(p)}`).join(',\n')}\n  ]\n}\n`);
console.log(`${snapshot}: ${plants.length} plants of ${new Set(plants.map((p) => p.taxonId)).size} kinds in ${new Set(plants.map((p) => p.stationId.split('.').slice(0, 3).join('.'))).size} rings`);
