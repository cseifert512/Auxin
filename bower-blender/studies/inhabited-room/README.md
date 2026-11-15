# Inhabited room: the six-bay Bower at a threshold, growing over ten years

One editable Blender scene of the six-bay Bower as a place, a worked decision made in it, and time
running through it: **what the plant needs at a pier, what that changes in the ground, the
structure, the making and the experience of the room, and what the room becomes as the climbers
grow.**

The site is designed, not surveyed. Nothing here is engineered. The climbers are grown by the plant
simulator, whose species numbers are provisional assumptions. What is generated, simulated,
proposed and borrowed is kept apart all the way through; see "Five kinds of thing".

## What to open

Every picture exists at five moments: `planted` (March 2027), `year-1`, `year-3`, `year-6` and
`year-10` (June 2036). The moment is written in the corner of each.

| Open | To see |
|---|---|
| `views/<moment>/arrival.jpg` | Arriving: the Bower across the bend of the path, through planting |
| `views/<moment>/lookout.jpg` | From just inside: through the room and out to the meadow |
| `views/<moment>/plant.jpg` | The plant's view: one pier from under its roots to its first joints |
| `views/planted/section.jpg`, `views/year-10/section.jpg` | The whole place cut through its uphill and downhill piers |
| `views/year-10/whole.jpg`, `plan.jpg` | The whole place, raised and from above |
| `inhabited_room.blend` | The scene: named collections, six cameras, one collection of climbers per moment, a note on every object |
| `site.json` | The site and the moments, as authored |
| `ground/meadow.json` | The pier as set out, with every quantity quoted below and where it comes from |
| `ground/meadow.growth.json` | What the grown run has on the plants at each moment |

## The site

**Intention: a threshold between garden and landscape. A place to pause, look out and feel
sheltered.**

A cultivated garden opens into a meadow, with woodland along one edge. The Bower stands where the
mown grass stops.

- **Arrival.** A path from a gate in the garden wall makes one gentle bend to the left, 17 m long.
  The Bower is first seen across the inside of the bend, through planting, and comes straight ahead
  only at the end, with the meadow visible through it. The path steps over the swale on a stone slab.
- **The room.** You come in through one bay and look out through the one opposite. The other four
  bays are planted across. A mown path goes on from the look-out into the meadow.
- **Light.** Woodland to the north and east, open sky to the south and west, and one afternoon: the
  sun in the south-west, 27 degrees up. The sky is a photograph; no date or latitude is modelled.
- **Ground.** One even fall of 1 in 25, 0.48 m across the room. Nothing is levelled: the floor is
  bound gravel that follows the ground, and each pier's legs are cut to that pier's own level. The
  timber runs 75 mm (about 3 in) into the soil and comes straight out of it. No footing is seen.
- **Water.** A swale round the uphill side takes the garden's run-off round the room, not through
  it. It and a line of pebbles from the floor's low edge end in a planted hollow below. A standpipe
  and a drip line are for the establishment years only.
- **Beds.** Two beds, massed in layers: carpet at the floor's edge, perennials and ferns behind,
  and on the woodland side shrubs to head height for shelter. The sunny bed stays low so that light
  and the view come in. Borrowed models stand in for a planting nobody has designed.
- **Life.** Two people arriving, three pausing (two at the look-out, one looking up), one tending a
  climber from the floor. No furniture.

North lies toward 135 degrees in the building's axes (`site.json`, `setting`), so that the section,
which looks along +Y, has the woodland behind it.

## The worked decision: a pier designed for the plant

The first pass of this study ran the building model's own ground draft on the level six-bay room
and found that **all 24 climbers the grown planting starts from stand on a steel pile cap**. The
draft's answer keeps the cap and moves the plants out, handing each to its lines 2.7 to 3.1 m up.
(`first-pass/README.md`, "One pier, three ways".)

This pass starts from the plant. A woody climber needs soil where it is planted, something to climb
from the ground up, and room for its stem to thicken for decades without bearing on the building.

| | What changes | In numbers (`ground/meadow.json`) |
|---|---|---|
| **Ground** | No platform and no plate. The room stands on the slope as it is. The steel sole of each pier lies under the bed, 0.6 m down, on three screw piles. A slender steel stub comes up from it to a shoe under each foot, and the timber stands on that shoe 75 mm under the soil. So nobody sees a footing, and the bed's soil is whole but for eight stubs. The beds are the garden's own soil, loosened and mulched in place, not boxed in. | 24 of 24 climbers rooted in soil. Through the bed, 8 stubs at each pier: 0.034 m² in plan. 0.86 m² of steel under each pier, under the bed. 18 piles. 139 m² of bed loosened 0.6 m deep. |
| **Structure** | Each pier's legs run on down to that pier's ground; nothing above the feet moves. The arches are slimmer, 180 by 300 mm, kin to the lattice they carry. Each leg that takes a climber carries a cable for the trunk, held 200 mm off the timber at the foot and coming in to 75 mm over 2.5 m, so a thickening stem cannot bear on a member or work into a joint. Each climber is planted 0.12 m from the foot of its own cable. Thin growth is tied to the timber by the gardener. | Six lengths of leg: 0, 0.064, 0.175, 0.304, 0.415 and 0.479 m longer than on level ground. 232 m of cable in 48 stretches on 497 standoffs, 75 to 195 mm long. Arches 30% of the timber, from 45%. |
| **Making** | The roof is the level room's. Only the members that stand on the ground are made longer, each by its pier's amount. Some pass the longest piece that can be made and gain a scarf. Every joint is wrapped in fine mesh to keep growth out; it is too fine to see and is not drawn. | 32 of 111 members change length, by up to 0.89 m (a hoop that stands at two piers); 79 are unchanged. 7 more scarfs. 620 joints to wrap. |
| **Experience** | No step and no ramp: you walk down a gentle slope into the room and out to the meadow. The way in is between planted legs. The climbers are tended from the floor and from the two thresholds, standing, with the cable at hand. | 3.6 m between the legs at the way in, for a 1.8 m path. 65 m² of floor. |

The ground draft's three rules for piles are all met: piles 1.26 m apart at the least, no foot more
than 0.56 m from one in plan, none nearer than 0.55 m to a climber.

## Time

The climbers in the scene are not drawn by hand. They are one run of the plant simulator
(`Horti-code-ture`, through `drawings-in-code`) on this snapshot, with this scene's own cables and
planting places: 24 climbers of 14 kinds, planted as 3 m specimens on 12 March 2027, then trained
and pruned by the simulator's gardener for ten years. The scene holds them on five days.

| Moment | Stem | Thickest stem | Leaves | Flowers |
|---|---|---|---|---|
| The day after planting, March 2027 | 62 m | 5 mm | 65 | 0 |
| First summer, July 2027 | 93 m | 6 mm | 1,241 | 14 |
| Year 3, June 2029 | 577 m | 15 mm | 9,252 | 284 |
| Year 6, June 2032 | 2,627 m | 38 mm | 32,530 | 1,370 |
| Year 10, June 2036 | 6,687 m | 77 mm | 67,721 | 3,074 |

(Counted from the light copy of the run that is drawn, which leaves out twigs and thins crowded
leaves. In ten years the gardener cut off 8.8 km of growth.)

**What comes back from the run.** This is the return trip from a grown result to the building:

- The cable's 200 mm gap at a foot was an allowance with no number behind it. In this run the
  thickest stem is 77 mm across after ten years; the gap would take a stem of about 390 mm. So the
  allowance is generous for the first decade. What a forty-year wisteria needs, the run does not say.
- The growth reaches the crown by year 6 (7 m) and covers the roof by year 10. The room is in full
  sun for its first three summers.

**What is the simulator's and what is not.** Where and when there is a stem, a leaf or a flower is
the run's, decided by the same rules as the simulator's own viewer (`grown.py` follows
`presence.ts` line for line). Their shapes and colours are not: each species has a plain leaf of
the right kind and a plain flower, in the viewer's colours for it. A picture is a true record of
where the run put growth and a sketch of what each plant looks like.

**What the simulator gets wrong on this site.** It takes the ground to be level, at the feet of the
highest pier.

- At the downhill piers, shoots that leave their support below that level stop at once, and nothing
  hangs below it: the lowest 0.4 m there is barer than it should be.
- Wisteria's clear stem is measured from that level, so it is up to 0.48 m taller downhill.
- Where a cable passes close to another member, the run's tidying moves that stretch of stem on to
  the timber.

**What does not change with the date.** The sky, the beds, the meadow and the woodland are one
summer afternoon at every moment, including the March one. Roots are not modelled: the section
draws each root ball as planted. The planting was carried from the level room without regard to
slope, shade or the woodland.

## What we would need to learn from building it

1. **How thick each stem gets at its foot, and how fast.** The run gives 77 mm in ten years on
   provisional numbers. Measure it every year on a built pier.
2. **Whether a stem takes the cable.** A twiner 200 mm from a timber leg may take the leg. How much
   of the gardener's time does it take to keep thick growth on the cable and thin growth on the
   timber, per pier, per year?
3. **Whether mesh protects a joint or harms it.** It may keep shoots out and hold wet leaves against
   end grain. What mesh, how fixed, and how is a joint inspected behind it?
4. **Whether timber can stand in the ground.** The feet run 75 mm into the soil. The soil line is
   where timber rots. Set aside for later, by decision; not designed round here.
5. **Whether the sole stands up.** No load, no thrust from the arches and no soil has been looked
   at. Each foot stands on a stub 0.53 m long; the piles start under 0.6 m of loosened bed.
6. **What roots do at steel.** Do they thicken round a stub or a pile shaft? Is 0.55 m enough?
7. **What limits the climbers in open ground.** Soil volume is no longer the limit; water, the bed
   planting and the woodland's roots on the sheltered side may be.
8. **Where the water goes.** Whether the floor sheds to the look-out as drawn, whether the swale is
   needed, whether the hollow holds water or drains.
9. **Whether people are comfortable on 1 in 25.** Standing and talking for a while, with a pram or
   a chair; whether bound gravel stays put on it.
10. **How accurately the ground must be known before milling.** Six leg lengths are free to a
    robot, but they fix the building to one survey. What tolerance, and what adjustment at the shoe?
11. **Which climber suits which pier.** The planting itself is still to be designed.
12. **What else lives here.** The hollow, the log, the meadow and the woodland edge are intentions
    for other life. What to watch for, and when, is not yet written down.

## Five kinds of thing

Every object in the scene carries `study_status` and `study_note`.

| Status | What | From |
|---|---|---|
| **linked** | The timber: 111 milled members | `releases/six-bay-meadow-v2/bower.blend`, unchanged |
| **generated** | Each pier's level, the trunk cables and standoffs, the joints | The building model's own code on the snapshot's design, run by `set_out_ground.py` |
| **simulated** | The climbers at each moment | `drawings-in-code/scenes/six-bay-meadow-v2/runs/place-10y`, read by `grown.py` |
| **carried** | Which climber goes with which leg | `drawings-in-code/scenes/six-bay-radial-open-pier/planting.json` |
| **proposal** | The site; the sole, stubs and piles; where each climber is planted; the mesh | `site.json`, `set_out_meadow.py`. Authored here, provisional, not engineered |
| **borrowed** | People, bed and garden planting, ground textures, sky | `assets.json` |

Nothing is **measured from a real thing**. The quantities above are measured from this geometry.

## What changed in the building model

Two optional settings, both in `bower-blender/README.md`. Every existing design and release builds
exactly as before.

- `rooms[].piers[].foot_z_m`: a pier's own foot level. Legs are lengthened to it.
- `timber.training_lines.foot_gap_m`, `foot_taper_m`: a cable stands further off at a foot.

`design/six_bay_meadow.json` uses both, with slimmer arches. Its snapshots are
`releases/six-bay-meadow-v1` (arches 260 by 400) and `-v2` (180 by 300). The design's foot levels
and the site's ground must agree: `set_out_meadow.py` stops if they are more than 4 mm apart.

## The scene

`build_scene.py` makes `inhabited_room.blend` from an empty file every time.

| Collection | Holds |
|---|---|
| `S05_BOWER_TIMBER` | the linked timber, with materials that render |
| `S10_TERRAIN` | the ground, 0.6 m of its soil, the subsoil |
| `S20_ROOM_GROUND` | floor, arrival path, slab over the swale, mown path |
| `S30_BEDS` | the two beds, their loosened soil, their massed planting |
| `S40_FOUNDATIONS` | soles, stubs and screw piles |
| `S45_SUPPORTS` | trunk cables and standoffs |
| `S50_BOWER_PLANTING` | root balls, and one collection of climbers per moment: `S50_planted` ... `S50_year-10` |
| `S60_WATER` | standpipe, drip line, swale bed, rill, hollow |
| `S70_GARDEN` | woodland, wall, planting on the bend, meadow |
| `S80_PEOPLE` | six figures |
| `S90_CAMERAS` | `CAM_arrival`, `CAM_lookout`, `CAM_whole`, `CAM_section`, `CAM_plant`, `CAM_plan` |
| `S95_SECTION_NOTES`, `S96_PLANT_NOTES` | labels, each hidden outside its own view |

The file opens on year 10. To see another moment, show its `S50_` collection and hide the rest.

The section and the plant's view are the same scene with one switch on: node group
`STUDY_section_switch`, `section_on` to 1, looking through `CAM_section` or `CAM_plant`. A section
draws as steel only the steel it cuts; what lies behind the cut is drawn faintly. The bed's loosened
soil fades into the ground round it, because it has no edge.

## Opening, changing, rendering

```powershell
python fetch_assets.py                                  # once: the borrowed assets, 177 MB, not in git
python set_out_ground.py                                # ground/meadow.json from the snapshot and site.json
.\run_headless.ps1 --render arrival,lookout,plant --samples 48 --scale 0.75      # every moment
.\run_headless.ps1 --render section,whole,plan --moments planted,year-10
.\run_headless.ps1 --render arrival --moments year-3 --samples 24 --scale 0.5 --out _preview    # a cheap look
```

To grow the climbers again, after a change to the building, the cables or the planting places:

```powershell
cd ..\..\..\drawings-in-code
npm run convert -- six-bay-meadow-v2
python ..\bower-blender\studies\inhabited-room\grow_inputs.py
npm run grow -- six-bay-meadow-v2 trained 10 7 --specimen=3 --bower=bower-place.json --name=place-10y
npm run lighten -- six-bay-meadow-v2 place-10y
```

The run takes about two minutes and writes 127 MB, which is not in git; its reports are. Without a
run the scene draws the climbers as a diagram of the day of planting and says so in `build.log`.
The moments are in `site.json`, `growth.moments`: any date from 2027-03-12 to 2036-12-31.

## Assets borrowed

`assets.json` lists them and what each is used for.

| Source | Licence | Used for |
|---|---|---|
| [Poly Haven](https://polyhaven.com): `meadow_2` (HDRI, 2k) | CC0 | sky, sunlight, the distant trees |
| Poly Haven: `pebble_ground_01`, `leafy_grass`, `brown_mud_leaves_01` (1k) | CC0 | floor, path, swale and rill; mown grass and meadow; beds and woodland floor |
| Poly Haven: 14 plant models (1k) | CC0 | woodland and the trees on the bend; the beds' massed planting; hollow and swale; meadow; the log |
| [Microsoft Rocketbox](https://github.com/microsoft/Microsoft-Rocketbox): six avatars | MIT | the people |

The plant models are small plants, measured, and set out at 1 to 8 times their size as clumps
(`SCALES` in `build_scene.py`). One small deciduous tree stands for every tree. No model is a
species choice, and none changes with the season. The figures are game-quality; they show scale and
use. What was looked for and not used is in `first-pass/README.md`.

## The first pass

The study began on an illustrative level garden, with three configurations of one pier and an
explorable drawing made from them. All of it is kept: `first-pass/README.md` says where each file is
now. The explorable drawing (`explore/`, `drawings-in-code/exports/deck/inhabited-room/`) still
shows the first pass. It has not been re-made on this site, and `build_scene.py --export` says so.

## Not known, not done

- No site exists. Soil, water table, rainfall, aspect and the trees are all authored.
- Nothing is engineered: not the sole, the stubs, the piles, the longer legs, the scarfs, the
  slimmer arches or timber standing in soil.
- One run, one seed. The species numbers behind it are provisional assumptions.
- The site does not change with the date; only the climbers do.
- No claim about other life is a finding.
- The beds, the meadow and the woodland are borrowed models, not designs.
- Manufacturing is counted (members, scarfs, standoffs, joints), not planned.
- Daniel has not reviewed the sole.
- The explorable drawing has not been re-made on this site.
