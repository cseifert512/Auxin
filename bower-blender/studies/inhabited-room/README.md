# Inhabited room: the six-bay Bower at a threshold, on the day it is planted

One editable Blender scene of the six-bay Bower as a place, and a worked decision made in it: **what
the plant needs at a pier, and what that changes in the ground, the structure, the making and the
experience of the room.**

The site is designed, not surveyed. Nothing here is engineered, no growth is simulated, and every
size is provisional. What is generated, what is proposed and what is borrowed are kept apart all the
way through; see "Four kinds of thing".

## What to open

| Open | To see |
|---|---|
| `views/arrival.png` | Arriving: the Bower across the bend of the path, through planting |
| `views/lookout.png` | From just inside: through the room and out to the meadow |
| `views/section.png` | The whole place cut through its uphill and downhill piers |
| `views/plant.png` | The plant's view: one pier from under its roots to its first joints |
| `views/whole.png`, `views/plan.png` | The whole place, raised and from above |
| `inhabited_room.blend` | The scene itself: named collections, six cameras, a note on every object |
| `site.json` | The site, as authored |
| `ground/meadow.json` | The pier as set out, with every quantity quoted below and where it comes from |

## The site

**Intention: a threshold between garden and landscape. A place to pause, look out and feel
sheltered.**

A cultivated garden opens into a meadow, with woodland along one edge. The Bower stands where the
mown grass stops.

- **Arrival.** A path from a gate in the garden wall makes one gentle bend to the left, 17 m long.
  The Bower is first seen across the inside of the bend, through planting, and comes straight ahead
  only at the end, with the meadow visible through it. The path steps over the swale on a stone slab.
- **The room.** You come in through one bay and look out through the one opposite. The other four
  bays are planted across: shrubs and ferns on the woodland side for shelter, low planting on the
  sunny side so the light and the view come in. A mown path goes on from the look-out into the
  meadow.
- **Light.** Woodland to the north and east, open sky to the south and west, and one afternoon: the
  sun in the south-west, 27 degrees up. The sky is a photograph; no date or latitude is modelled.
- **Ground.** One even fall of 1 in 25, 0.48 m across the room. Nothing is levelled: the floor is
  bound gravel that follows the ground, and each pier's legs are cut to that pier's own level. The
  timber runs 75 mm (about 3 in) into the soil and comes straight out of it: no footing is seen.
  The soil is continuous round every pier.
- **Water.** A swale round the uphill side takes the garden's run-off round the room, not through
  it. It and a line of pebbles from the floor's low edge end in a planted hollow below. A standpipe
  and a drip line are for the establishment years only.
- **Life.** Two people arriving, three pausing (two at the look-out, one looking up), one tending a
  climber from the floor. No furniture.

North lies toward 135 degrees in the building's axes (`site.json`, `setting`), so that the section,
which looks along +Y, has the woodland behind it.

## The worked decision: a pier designed for the plant

The first pass of this study ran the building model's own ground draft on the level six-bay room
and found that **all 24 climbers the grown planting starts from stand on a steel pile cap**. The
draft's answer keeps the cap and moves the plants out, to twelve root zones, handing each to its
lines 2.7 to 3.1 m up. (`first-pass/README.md`, "One pier, three ways".)

This pass starts from the plant instead. A woody climber needs soil where it is planted, something
to climb from the ground up, and room for its stem to thicken for decades without bearing on the
building. From that:

| | What changes | In numbers (`ground/meadow.json`) |
|---|---|---|
| **Ground** | No platform and no plate. The room stands on the slope as it is. Each pier has a buried steel sole on three screw piles: a plate under the two arch legs, one curved beam under the six lattice legs, two ties. The timber feet stand on it 75 mm under the soil, so nobody sees a footing. Its bars are narrow, with soil over, under and between them, and no climber's root ball has steel under it. The two beds are the garden's own soil, loosened and mulched in place, not boxed in. | 24 of 24 climbers rooted in soil. 0.96 m² of steel within 1.81 m² at each pier, its top 75 mm under the soil. 18 piles. 139 m² of bed loosened 0.6 m deep. |
| **Structure** | Each pier's legs run on down to that pier's ground; nothing above the feet moves. Each leg that takes a climber carries a cable for the trunk, held 200 mm off the timber at the foot and coming in to 75 mm over 2.5 m, so a thickening stem cannot bear on a member or work into a joint. Each climber is planted 0.12 m from the foot of its own cable. Thin growth is tied to the timber by hand. | Six lengths of leg: 0, 0.064, 0.175, 0.304, 0.415 and 0.479 m longer than on level ground. 232 m of cable in 48 stretches on 500 standoffs, 75 to 195 mm long. |
| **Making** | The roof is the level room's. Only the members that stand on the ground are made longer, each by its pier's amount. Some pass the longest piece that can be made and gain a scarf. Every joint is wrapped in fine mesh to keep growth out. | 32 of 111 members change length, by up to 0.89 m (a hoop that stands at two piers); 79 are unchanged. 7 more scarfs: 620 joints, not 613. 620 joints to wrap, 56 of them within 3.2 m of the ground. |
| **Experience** | No step and no ramp: you walk down a gentle slope into the room and out to the meadow. The way in is between planted legs. The climbers are tended from the floor and from the two thresholds, standing, with the cable at hand. | 3.61 m between the legs at the way in, for a 1.8 m path. 65 m² of floor. |

The ground draft's three rules for piles could not all be met on the level room's frame (a pile
stood 0.24 m from a climber, under the 0.3 m asked). Here they are: piles 1.26 m apart at the least,
no foot more than 0.56 m from one, none nearer than 0.55 m to a climber.

### What we would need to learn from building it

Each of these is a number or a choice in this design that nothing yet stands behind.

1. **How thick each stem gets at its foot, and how fast.** The 200 mm gap is an allowance. The
   species library holds no girth figure. Measure it every year on a built pier.
2. **Whether a stem takes the cable.** A twiner 200 mm from a timber leg may take the leg. How much
   of the gardener's time does it take to keep thick growth on the cable and thin growth on the
   timber, per pier, per year?
3. **Whether mesh protects a joint or harms it.** It may keep shoots out and hold wet leaves against
   end grain. What mesh, how fixed, and how is a joint inspected behind it?
4. **Whether timber can stand in the ground.** The feet run 75 mm into the soil so that no footing
   shows. The soil line is where timber rots. Which timber, treatment or detail (a drained collar, a
   sleeve, a foot that can be replaced) makes it last, and how is a foot looked at once it is buried
   and planted round?
5. **Whether the sole stands up.** No load, no thrust from the arches and no soil has been looked
   at. The piles pass through 0.6 m of loosened bed, and the steel sits in wet, cultivated soil.
6. **What roots do at steel.** Do they thicken round a pile shaft or lift a beam? Is 0.55 m enough?
7. **What limits the climbers in open ground.** Soil volume is no longer the limit; water, the bed
   planting and the woodland's roots on the sheltered side may be.
8. **Where the water goes.** Whether the floor sheds to the look-out as drawn, whether the swale is
   needed, whether the hollow holds water or drains.
9. **Whether people are comfortable on 1 in 25.** Standing and talking for a while, with a pram or
   a chair; whether bound gravel stays put on it.
10. **How accurately the ground must be known before milling.** Six leg lengths are free to a robot,
   but they fix the building to one survey. What tolerance, and what adjustment at the shoe?
11. **Which climber suits which pier.** The planting was carried from the level room without regard
    to slope, shade or the woodland. The planting itself is still to be designed.
12. **What else lives here.** The hollow, the log, the meadow and the woodland edge are intentions
    for other life. What to watch for, and when, is not yet written down.

### What is not in this pass: time

Nothing grows here. The picture is the day of planting, which is honest and is also the least
interesting day in the life of the building. Growing the planting on this pier in the simulator
(`drawings-in-code`: convert, plant, grow) would show whether the stems take their cables, where
growth reaches joints and what the room is like in year three and year ten. Those results would
then change the pier again. That return trip, from grown result back to the building's parameters,
is what "closing the loop" means; this pass makes the first half of one turn.

## Four kinds of thing

Every object in the scene carries `study_status` and `study_note`.

| Status | What | From |
|---|---|---|
| **linked** | The timber: 111 milled members | `releases/six-bay-meadow-v1/bower.blend`, unchanged |
| **generated** | Each pier's level, the trunk cables and standoffs, the joints | The building model's own code on the snapshot's design (`bower/floor.py`, `bower/lines.py`, `bower/joints.py`), run by `set_out_ground.py` |
| **carried** | Which climber goes with which leg | `drawings-in-code/scenes/six-bay-radial-open-pier/planting.json` |
| **proposal** | The site; the sole and piles; where each climber is planted; the mesh; the climbers as drawn | `site.json`, `set_out_meadow.py`. Authored here, provisional, not engineered |
| **borrowed** | People, vegetation, ground textures, sky | `assets.json` |

Nothing is **simulated** and nothing is **measured from a real thing**. The quantities above are
measured from this geometry.

## What changed in the building model

Two optional settings, both in `bower-blender/README.md`. Every existing design and release builds
exactly as before.

- `rooms[].piers[].foot_z_m`: a pier's own foot level. Legs are lengthened to it ("A room on sloping
  ground").
- `timber.training_lines.foot_gap_m`, `foot_taper_m`: a cable stands further off at a foot.

`design/six_bay_meadow.json` uses both. Its snapshot is `releases/six-bay-meadow-v1`. The design's
foot levels and the site's ground must agree: `set_out_meadow.py` stops if they are more than 4 mm
apart at any pier.

## The scene

`build_scene.py` makes `inhabited_room.blend` from an empty file every time.

| Collection | Holds |
|---|---|
| `S05_BOWER_TIMBER` | the linked timber, with materials that render |
| `S10_TERRAIN` | the ground, 0.6 m of its soil, the subsoil |
| `S20_ROOM_GROUND` | floor, arrival path, slab over the swale, mown path |
| `S30_BEDS` | the two beds, their loosened soil, their planting |
| `S40_FOUNDATIONS` | soles and screw piles |
| `S45_SUPPORTS` | trunk cables, standoffs, joint mesh |
| `S50_BOWER_PLANTING` | the climbers as planted, their root balls |
| `S60_WATER` | standpipe, drip line, swale bed, rill, hollow |
| `S70_GARDEN` | woodland, wall, planting on the bend, meadow |
| `S80_PEOPLE` | six figures |
| `S90_CAMERAS` | `CAM_arrival`, `CAM_lookout`, `CAM_whole`, `CAM_section`, `CAM_plant`, `CAM_plan` |
| `S95_SECTION_NOTES`, `S96_PLANT_NOTES` | labels, each hidden outside its own view |

The section and the plant's view are the same scene with one switch on: node group
`STUDY_section_switch`, `section_on` to 1, looking through `CAM_section` or `CAM_plant`.

## Opening, changing, rendering

```powershell
python fetch_assets.py                                  # once: the borrowed assets, 152 MB, not in git
python set_out_ground.py                                # ground/meadow.json from the snapshot and site.json
.\run_headless.ps1 --render arrival,lookout,section,plant,whole,plan --samples 64
.\run_headless.ps1 --render arrival --samples 24 --scale 0.45 --out _preview    # a cheap look
```

Change the site in `site.json` and run the last two again. Change the building in
`bower-blender/design/six_bay_meadow.json`, export a snapshot under a new name, point
`configurations.meadow.snapshot` at it, and run all three.

## Assets borrowed

`assets.lock.json` records every file, its source address, size and MD5.

| Source | Licence | Used for |
|---|---|---|
| [Poly Haven](https://polyhaven.com): `meadow_2` (HDRI, 2k) | CC0 | sky, sunlight, the distant trees |
| Poly Haven: `pebble_ground_01`, `leafy_grass`, `brown_mud_leaves_01` (1k) | CC0 | floor, path, swale and rill; mown grass and meadow; beds and woodland floor |
| Poly Haven: `tree_small_02`, `shrub_01`, `shrub_04`, `fern_02`, `periwinkle_plant`, `dandelion_01`, `grass_medium_02`, `dead_tree_trunk` (1k) | CC0 | woodland and the trees on the bend; bed planting; hollow and swale; meadow; the log |
| [Microsoft Rocketbox](https://github.com/microsoft/Microsoft-Rocketbox): six avatars | MIT | the people |

One small deciduous tree stands for every tree, at several sizes. No model is a species choice. The
figures are game-quality; they show scale and use. What was looked for and not used is in
`first-pass/README.md`.

## The first pass

The study began on an illustrative level garden, with three configurations of one pier (as found,
the ground draft's correction, a first open-pier proposal) and an explorable drawing made from them.
All of it is kept: `first-pass/README.md` says where each file is now. The explorable drawing
(`explore/`, `drawings-in-code/exports/deck/inhabited-room/`) still shows the first pass. It has not
been re-made on this site, and `build_scene.py --export` says so.

## Not known, not done

- No site exists. Soil, water table, rainfall, aspect and the trees are all authored.
- Nothing is engineered: not the sole, the piles, the longer legs, the scarfs or timber standing in soil.
- No growth, shade, season or year. See "What is not in this pass: time".
- No claim about other life is a finding.
- The planting on the beds, the meadow and the woodland are borrowed models, not designs.
- Manufacturing is counted (members, scarfs, standoffs, joints), not planned: nothing here says
  what a longer leg or a mesh sleeve costs at a station.
- Daniel has not reviewed the sole.
- The explorable drawing has not been re-made on this site.
