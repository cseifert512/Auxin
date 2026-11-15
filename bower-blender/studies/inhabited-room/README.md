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
| `ground/openings.json` | The pier opened by degrees: what each opening does to sun, the way in and the footing |
| `drawings-in-code/exports/deck/opening-the-pier/index.html` | That study as a drawing in code, for the deck |
| `views/timelapse/<view>/` | Each view on 41 days across the ten years (made by `--timelapse`; not in git) |

## The site

**Intention: a threshold between garden and landscape. A place to pause, look out and feel
sheltered.**

A cultivated garden opens into a meadow, with woodland along one edge. The Bower stands where the
mown grass stops.

- **Arrival.** A path from a gate in the garden wall makes one gentle bend to the left, 17 m long.
  The Bower is first seen across the inside of the bend, through planting, and comes straight ahead
  only at the end, with the meadow visible through it. The path is not a built thing: it is the
  same grass as the garden, kept clear of taller plants.
- **The room.** You come in through one bay and look out through the one opposite. The other four
  bays are planted across. A mown path goes on from the look-out into the meadow.
- **Light.** Woodland to the north and east, open sky to the south and west. The pictures are lit by
  one afternoon: the sun in the south-west, 27 degrees up, from a photograph of a sky. The plant
  simulator is told more: an assumed latitude of 51.5 degrees, which way the building is turned,
  and what stands near enough to shade it (the woodland's front rows, the trees on the bend of the
  path, the garden wall). `grow_inputs.py` writes that from `site.json`.
- **Ground.** One even fall of 1 in 25, 0.48 m across the room. Nothing is levelled: the floor is
  bound gravel that follows the ground, and each pier's legs are cut to that pier's own level. The
  timber runs 75 mm (about 3 in) into the soil and comes straight out of it. No footing is seen.
- **Water.** A swale round the uphill side takes the garden's run-off round the room, not through
  it. It and the floor's own water end in a planted hollow below. Neither is a built thing to look
  at: each is a line of different planting. A standpipe is for the establishment years only.
- **Planting.** One planting, with no beds and no lawn, in the manner of a naturalistic perennial
  garden. It runs from the garden wall through the piers into the meadow and under the woodland's
  edge. Grasses run all through it and other kinds stand in drifts. It is low at every path, at the
  floor's edge and out through the look-out, and taller away from them. The swale reads as a line of
  taller, wetter planting. Shrubs to head height shelter the woodland side of the room. Borrowed
  models stand in for a planting nobody has designed.
- **Floor.** A clearing of rolled gravel whose edge wanders and is grown over, with stones at it to
  perch on.
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
| **Ground** | No platform and no plate. The room stands on the slope as it is. The steel sole of each pier lies under the bed, 0.6 m down, on three screw piles. A slender steel stub comes up from it to a shoe under each foot, and the timber stands on that shoe 75 mm under the soil. So nobody sees a footing, and the soil is whole but for eight stubs. Round the piers the ground is loosened before planting and nothing is raised or edged: the planting runs over it without a break. | 24 of 24 climbers rooted in soil. Through the bed, 8 stubs at each pier: 0.034 m² in plan. 0.86 m² of steel under each pier, under the bed. 18 piles. 139 m² of bed loosened 0.6 m deep. |
| **Structure** | Each pier's legs run on down to that pier's ground; nothing above the feet moves. The arches are slimmer, 180 by 300 mm, kin to the lattice they carry. Each leg that takes a climber carries a cable for the trunk, held 200 mm off the timber at the foot and coming in to 75 mm over 2.5 m, so a thickening stem cannot bear on a member or work into a joint. Each climber is planted 0.12 m from the foot of its own cable. Thin growth is tied to the timber by the gardener. | Six lengths of leg: 0, 0.064, 0.175, 0.304, 0.415 and 0.479 m longer than on level ground. 232 m of cable in 48 stretches on 497 standoffs, 75 to 195 mm long. Arches 30% of the timber, from 45%. |
| **Making** | The roof is the level room's. Only the members that stand on the ground are made longer, each by its pier's amount. Some pass the longest piece that can be made and gain a scarf. Every joint is wrapped in fine mesh to keep growth out; it is too fine to see and is not drawn. | 32 of 111 members change length, by up to 0.89 m (a hoop that stands at two piers); 79 are unchanged. 7 more scarfs. 620 joints to wrap. |
| **Experience** | No step and no ramp: you walk down a gentle slope into the room and out to the meadow. The way in is between planted legs. The climbers are tended from the floor and from the two thresholds, standing, with the cable at hand. | 3.6 m between the legs at the way in, for a 1.8 m path. 65 m² of floor. |

The ground draft's three rules for piles are all met: piles 1.26 m apart at the least, no foot more
than 0.56 m from one in plan, none nearer than 0.55 m to a climber.

## How far to open the pier

The design opens each pier: its legs stand in a ring 1.2 m in radius, not bunched at 0.34 m. How
far to open it was a judgement. `study_openings.py` puts numbers beside it. For six openings it
makes the building, sets its pier out as above, hands the simulator that building on this site, and
grows it for ten years. No Blender is needed. `ground/openings.json` holds what came back.

| Ring of legs, radius | Feet apart | Way in | June sun on a climber, mean of 24 | In full sun | Stem by year 10 | Footing draft's rules |
|---|---|---|---|---|---|---|
| 0.34 m | 0.15 m | 4.92 m | 1.25 h | 0 | 2,182 m | not met: piles 0.62 m apart; a pile 0.06 m from a climber |
| 0.6 m | 0.17 m | 4.83 m | 1.51 h | 0 | 2,153 m | not met |
| 0.8 m | 0.26 m | 4.41 m | 3.14 h | 2 | 2,031 m | not met: piles 0.86 m apart |
| 1.0 m | 0.34 m | 4.00 m | 3.58 h | 2 | 2,112 m | met |
| **1.2 m, the design** | 0.43 m | 3.60 m | 4.05 h | 5 | 2,081 m | met |
| 1.4 m | 0.51 m | 3.19 m | 4.50 h | 6 | 2,088 m | not met: a foot 0.63 m from its nearest pile |

- **What it supports.** Opening the pier from 0.34 m to 1.2 m about triples the direct sun that
  reaches a climber's planting place in June, in the simulator's light model. Each step wider gives
  more sun and a narrower way in. 1.2 m is the widest opening at which this study's sole still
  meets the ground draft's rules.
- **What it does not support.** More growth. Stem by year 10 is about the same at every opening:
  in this simulator, on these provisional numbers, light is not what limits these climbers.
- **What stands behind it.** One run and one seed for each opening. The light model is provisional
  and the latitude assumed. The footing rules are the ground draft's, not an engineer's.

```powershell
python study_openings.py            # about ten minutes; --keep reads runs that are already there
```

The trial buildings are written to `releases/trial-meadow-pier-*`, which git ignores: they are not
snapshots.

## Time

The climbers in the scene are not drawn by hand. They are one run of the plant simulator
(`Horti-code-ture`, through `drawings-in-code`) on this snapshot, with this scene's own cables and
planting places: 24 climbers of 14 kinds, planted as 3 m specimens on 12 March 2027, then trained
and pruned by the simulator's gardener for ten years. The scene holds them on five days.

| Moment | Stem | Thickest stem | Leaves | Flowers |
|---|---|---|---|---|
| The day after planting, March 2027 | 62 m | 5 mm | 65 | 0 |
| First summer, July 2027 | 86 m | 6 mm | 1,232 | 14 |
| Year 3, June 2029 | 507 m | 15 mm | 8,451 | 254 |
| Year 6, June 2032 | 2,289 m | 36 mm | 29,463 | 1,233 |
| Year 10, June 2036 | 6,349 m | 73 mm | 65,188 | 2,900 |

(Counted from the light copy of the run that is drawn, which leaves out twigs and thins crowded
leaves. In ten years the gardener cut off 7.6 km of growth.)

**What comes back from the run.** This is the return trip from a grown result to the building:

- The cable's 200 mm gap at a foot was an allowance with no number behind it. In this run the
  thickest stem is 73 mm across after ten years; the gap would take a stem of about 390 mm. So the
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
summer afternoon at every moment, including the March one. Which climber goes where was carried
from the level room without regard to slope, shade or the woodland.

**Roots.** The simulator does not model roots. The section draws them from a sketch with stated
rules (`roots.py`, checked by `check_roots.py`): a few far-running shallow laterals, branches,
feeders near the surface and one to three sinkers, growing outward over the ten years and steered
clear of the stubs, piles and sole. How far a climber's roots reach is set from the thickest stem
the run gave it, by an authored rule (`site.json`, `growth.roots`). Nothing stands behind it: it is
there so that the picture shows the plant below ground too, not as evidence about any plant. The
root ball it was planted with is drawn for the first 60 days only.

**The time-lapse.** `--timelapse` renders the views on 41 days: the day of planting, then four days
in each year (late April, mid June, early August, late October). The arrival and look-out cameras
travel a little as the years pass. Each day's climbers are drawn, rendered and thrown away, so the
scene file stays small. `views/timelapse/frames.json` lists what was made and where the named
places fall in every frame.

## What we would need to learn from building it

1. **How thick each stem gets at its foot, and how fast.** The run gives 73 mm in ten years on
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
| `S30_BEDS` | the planting, and under it the ground loosened for the climbers |
| `S40_FOUNDATIONS` | soles, stubs and screw piles |
| `S45_SUPPORTS` | trunk cables and standoffs |
| `S50_BOWER_PLANTING` | root balls, and one collection per moment of climbers and their sketched roots: `S50_planted` ... `S50_year-10` |
| `S60_WATER` | standpipe, the planted hollow |
| `S70_GARDEN` | woodland, wall, planting on the bend, meadow |
| `S80_PEOPLE` | six figures |
| `S90_CAMERAS` | `CAM_arrival`, `CAM_lookout`, `CAM_whole`, `CAM_section`, `CAM_plant`, `CAM_plan` |
| `S95_SECTION_NOTES`, `S96_PLANT_NOTES` | labels, each hidden outside its own view |

The file opens on year 10. To see another moment, show its `S50_` collection and hide the rest.

The section and the plant's view are the same scene with one switch on: node group
`STUDY_section_switch`, `section_on` to 1, looking through `CAM_section` or `CAM_plant`. A section
draws as steel only the steel it cuts; what lies behind the cut is drawn faintly. The loosened soil
fades into the ground round it, because it has no edge. Cables are drawn as quiet steel lines.

## Opening, changing, rendering

```powershell
python fetch_assets.py                                  # once: the borrowed assets, about 215 MB, not in git
python set_out_ground.py                                # ground/meadow.json from the snapshot and site.json
.\run_headless.ps1 --render arrival,lookout,plant --samples 48 --scale 0.75      # every moment
.\run_headless.ps1 --render section,whole,plan --moments planted,year-10
.\run_headless.ps1 --render arrival --moments year-3 --samples 24 --scale 0.5 --out _preview    # a cheap look
.\run_headless.ps1 --timelapse arrival,lookout,plant,whole,section                              # 41 days; about two and a half hours
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
| Poly Haven: `gravel_ground_01`, `leafy_grass`, `brown_mud_leaves_01` (1k) | CC0 | floor and path; the ground under the planting, the meadow and the woodland |
| Poly Haven: 17 plant models and 2 sets of stones (1k) | CC0 | woodland and the trees on the bend; the planting; hollow; the stones at the floor's edge; the log |
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
- The planting, the meadow and the woodland are borrowed models in a manner of planting, not a
  planting design.
- The pictures are lit by a photograph of a sky, the simulator by a sun worked out for an assumed
  latitude. The two are not the same afternoon.
- Manufacturing is counted (members, scarfs, standoffs, joints), not planned.
- Daniel has not reviewed the sole.
- The explorable page of this site (`place/`, packed to `drawings-in-code/exports/deck/the-place/`)
  is parked: pictures with targets on them did not make a drawing to explore.
