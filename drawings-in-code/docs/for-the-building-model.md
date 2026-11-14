# For whoever is working on the building model

Written 14 November 2026 from the `drawings-in-code` side, after growing plants on snapshot `six-bay-v1` and
drawing the result. It says what was learned, what the planting needs from the building, and where each decision
should live. Numbers about plants are the plant simulator's running assumptions, not measurements.

## Who owns what

| Repository | Owns | Should not |
|---|---|---|
| `bower-blender` | Everything that is physically part of the building, including what is bolted to it for plants: training lines, their fixings, the beds at the feet, zones to keep clear. | Hold plant biology (growth rates, what a species can grasp). |
| `Horti-code-ture` | How plants behave: how each holds on, how fast it grows, how it is pruned. | Know anything about one particular building. |
| `drawings-in-code` | Joining the two: converting a snapshot, growing a planting on it, scoring it, drawing and filming it. | Invent parts of the building. It currently does (beds and training lines), as stand-ins. |

The snapshot is the contract between them. One direction of authority (building → snapshot → plants → drawings)
and one way back: scores from a grown planting, which inform the building's parameters.

## What the six-bay room is like for plants

1. **Plants can only start at the six piers.** 52 member ends reach the ground (6 ribs, 10 second-tier ribs, 12
   arches, 12 hoops with two feet each), all in six sheaves. The simulator refuses a bed more than 1.5 m from
   something to climb.
2. **The feet of a pier stand about 0.15 m apart** (`timber.piers.ring_radius_m` 0.34, `gap_m` 0.03). There is no
   soil between them, and the simulator reads a whole pier as one joint, so a plant cannot be given one leg.
3. **Most plants cannot hold these members.** A twiner has to get round the section: perimeter / pi. Ribs,
   second and third tiers and hoops come to 178-197 mm; arches to 420 mm. The simulator's limits are 200 mm for
   wisteria, 114 mm for honeysuckle 'Graham Thomas', 60 mm for akebia, 55 mm for evergreen honeysuckle, 40 mm for
   star jasmine, and about 10 mm for clematis and the vine. Ivy and climbing hydrangea cling to a textured face of
   any size. So only wisteria and the two clingers hold on unaided; the rest are tied by a gardener or need
   something slender beside the timber.
4. **The lattice is flush on the outside.** At all 410 lap joints the two notches add up to the member depth
   within 17 mm. A line held at a constant gap off the outer face of any member clears every member that crosses
   it.
5. **Routes are long.** In every run plants stopped short of the crown because they ran out of route, not height.
   `timber.lattice.lean_deg` (40) sets how long the way up is.
6. **The lattice is densest at the rim**, because the second and third tiers start part-way down. That is where
   the short plants live (the summer clematis top out near 2.5 m).

## What growing on it showed

Thirty-six climbers, planted standing 3 m at the piers, tended, ten years:

- 93% of the timber routes carry a plant by year ten; from the approach in June 64% of the timber is still seen.
  The building stays legible. Evergreens hold 40% of the routes in winter.
- What moves the cover is the number of plants and where they can go in. Planting at 2 m in place of young canes
  gave height in year one and almost nothing by year ten.
- With thin lines added for plants to hold, tie-ins by the gardener over ten years fell from 4,587 to 1,634 and
  the share of routes held unaided rose from 15% to 40%.
- The simulator gives the beds 36-62% of an open site's light in June. Light at the piers is not the limit.

## What Clay has decided about the planting

- The structure is what the plants grow on. Nothing is strung across an entrance.
- Training lines are thin steel cable fixed ON the structure: a gap of about 3 inches (75 mm) off the member,
  on standoffs screwed into it, the cable following the member's own curve. A net laid over the building in
  directions the timber does not have reads as superficial and was rejected.
- Structure and planting should be designed in dialogue: the building may change for the plants.
- Plants go in as nursery specimens of 2-3 m.

## What the building model could take on

These are parts of the building, so they belong in the generator and the snapshot, regenerated with every edit:

1. **Training lines as a property of a member.** Say which members carry one, the gap and the face. Generate the
   line from the member's centre line and depth axis, with a standoff at each station. Put the standoff holes in
   the schedule with the joints: they are one more operation where the laps are milled.
2. **Beds.** Where a plant goes into the ground, tied to the foot of the member or line it is to climb.
3. **Zones to keep clear.** The crown opening (in one run a vine closed over it); headroom in the entrances, and
   0.2-1.1 m of hanging room under any member that carries wisteria.
4. **The site.** Latitude, and anything near enough to cast shade. Y is already north.

Open questions for the design, each of which the plant side can score:

- Which members carry a line: all 108 (639 m), or the 40 that reach the ground, so that each plant is given one
  timber from soil upward?
- Should the legs of a pier stand apart at the ground, with soil between, so each has its own plant?
- Rib lean against years to reach the crown.
- Where the tiers begin, against where the short plants live.
- How a gardener reaches what has to be pruned two to four times a year.

## What would help in a snapshot

Already right, please keep: persistent member IDs; `centrelines.json` with `depth_axes` at every sample; one mesh
per member in `bower.glb` carrying its ID; `joints.csv` with faces and depths (the assembly order was derived
from it: 556 orderings, none in conflict).

Worth adding:

- `depth_axes` always pointing outward. The sign is currently worked out downstream by guessing from the room's
  centre.
- Lines, beds and zones, once the generator makes them: as `lines.json` (per line: member ID, gap, points,
  fixings) or as fields on the members.
- The outer surface of the roof as a mesh, if the envelope is still to hand.
- For each member end on the ground, which pier it belongs to.

## Things in the plant simulator that will catch you out

- Its input cannot say which way a section is turned; it assumes its own frame. `drawings-in-code` turns the
  stems on to the real faces afterwards (`pipeline/reseat.mjs`).
- It winds a stem round a member straight through the members crossing it. About a tenth of the recorded stem
  stood inside wood; `pipeline/clear.mjs` takes it out.
- It joins elements whose centre lines pass within half the larger section dimension of each, plus 20 mm. A line
  75 mm off a face needs `joinToleranceM` raised in the converted file.
- Fixings closer than about 0.15 m along one member are merged into a single joint. Thirty lines landing on the
  crown ring turned the whole ring into one.
- A plant cannot be told which member to take. It can be given a line of its own: a bed at the foot of a cable
  is led on to that cable.

## How to score a snapshot

From `C:\BOWER\drawings-in-code`, with a snapshot copied into `releases/<name>/`:

```bash
npm run convert -- <name>
npm run plant -- <name>
npm run grow -- <name> trained 10 7 --specimen=3
npm run compare -- <name>
```

`compare` prints the routes held, how (unaided or tied), the gardener's tie-ins, and what is seen from each
viewpoint in January and June. `pipeline/lines.mjs` is a first rule for laying out lines from the joints. Its
layout was rejected, but how it reads the joints and tests a line against the timber may be worth reading.

## Added later the same day: the lines need to come across in the snapshot

The generator now sets out training lines itself (`bower/lines.py`), with root zones and feeders at a pier
(`bower/ground.py`). None of that reaches the drawings: a snapshot carries no lines, so `drawings-in-code` still
sets out its own (`pipeline/lines.mjs`). The two rules have been brought into step by hand (lattice members that
stand on the floor, 75 mm off the outer face, 4 mm cable, no line on an arch), but they are two rules, and the
feeders, the root zones and the cut-backs exist only in the generator.

What would close the gap: one more file in the snapshot, `lines.json`, in the snapshot's axes and metres:

- `lines`: for each cable, its `id`, `kind` (`training` or `feeder`), the `member` it belongs to, and `points_m`,
  the cable as strung (standoff head to standoff head);
- `root_zones`: for each, its `id`, `pier`, and `position_m` on the ground, and which line or feeder a plant put
  there starts on;
- the settings they were made with.

`pipeline/convert.mjs` would then take cables and planting places from that file and set out none of its own.

One finding to pass on, which the generator's README already half says: at a pier of `six-bay-radial-v1` the feet of
the six lattice lines stand 0.10 m apart in the pocket behind the arch legs. Planting there (as the drawings do,
for want of root zones) puts four plants in a space no one could dig. The root zone outside the pier with a feeder
up the arch leg is the right answer, and the drawings will show it as soon as a snapshot carries it.
