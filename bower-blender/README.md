# Bower V1

A procedural model of a Bower: rooms, bays and crowns are edited as a small plan
graph, and the architectural envelope and the primary timber are regenerated
from it. The brief is in
`Bower_Claude_Blender_Handoff/Bower_Blender_Claude_Handoff/BOWER_V1_CLAUDE_HANDOFF.md`.

Status: Gate 4. `design.json` is one room, eight bays as it stands, with its
primary timber and every joint milled, and it can be worked on from a panel in
Blender with sliders and live handles (`scripts/panel.py`). The same code also builds a long hall, a
room whose crown is a line instead of a point (`views/gate2_hall.jpg`), and
rooms joined to each other through a shared arch: `design/two_rooms.json` is
the first pair (`views/gate3_rooms.jpg`). The earlier six-bay model is frozen
as the snapshot `../releases/six-bay-v1`. No planting. Dimensions, sections and clearances are provisional concept
values; nothing here is a structural, fabrication or horticultural check.

## Working on the model in Blender

The panel is how the model is played with. Open it once per Blender session:

```python
import runpy
runpy.run_path(r"C:\BOWER\Auxin\bower-blender\scripts\panel.py")["main"]()
```

then press N in the 3D viewport and choose the **Bower** tab
(`views/gate4_panel.png`).

| In the panel | What it does |
|---|---|
| Crown | sliders for the crown ring's height and radius, the lantern's radius and base height, the slope the crown arrives at its ring with, and the spine's length (0 is a round room; drag it out and the room becomes a hall) |
| Room | sliders for the room's radius, its number of bays, the height of all its arches together and the height of its piers |
| Lattice | sliders for ribs per hand, the ribs' lean and the number of hoops |
| Handles | drag the empties in the viewport: a pier (cube), an apex (small sphere) or a crown (large sphere, up and down for its height). Select an apex handle to split or remove its bay, or to grow a new room out of it |
| Room chooser | with more than one room, which room the sliders act on |
| Undo, Save, Revert | undo steps back through changes made in the panel; Save writes the working design to the design file; Revert reads the file again |

It runs at three speeds. While a slider or a handle is moving, the room's
boundary curves (arches, crown ring, ridges) follow at once. A moment after it
stops, all the timber is rebuilt as a draft: swept from its centrelines, with
no joints cut and nothing checked, in about three seconds for one room. **Mill
joints** builds it in full, every joint cut and every check run, in about a
minute, and reports what it found.

Every change goes through the same operations and checks as a hand edit of the
design file. One that would give an invalid design is refused: the panel says
why, the slider goes back, and a handle dragged too far is put back where it
was. The panel works on a copy of the design kept in the scene; nothing is
written to the design file until Save. A slider that cannot be used on a room
(a joined room's bay count, for one) is greyed out with the reason under it.

Use the panel's Undo rather than Ctrl+Z, which does not know about the design.
If the scene ever looks out of step with the sliders, Rebuild draft puts it
right.

## Source of truth

`design.json` holds the authored design: rooms, piers, bays, crown, shape
parameters, timber sections and rules, sampling densities, view cameras.
Everything in Blender is generated from it and can be deleted and rebuilt.
Units are metres, Z up, Y north.

Three levels, each generated from the one before:

| Level | Module | What it holds |
|---|---|---|
| A, topology | `bower/topology.py` | piers, bays, crown (a point or a spine), the number of bays, persistent IDs, edit operations |
| B, envelope | `bower/envelope.py` | the roof as one smooth surface: pointed arches at the rim, a canopy that gathers onto each pier, a lantern at the centre (a guide surface, hidden by default) |
| C, members | `bower/timber.py` | arches that are the roof's edge, hoops inside them, a flush lattice of spiralling ribs in tiers, a crown ring, and piers that are bundles of the legs of those members |
| C, joints | `bower/joints.py` | every joint between those members, the cut it makes in each, and the volume to mill out: laps, housings, mitres, seats, splices, bases |

## Round rooms and long rooms

Everything in a roof is placed by two coordinates: its bearing round the crown
and its distance from the crown. `bower/spine.py` supplies them. Round a crown
that is a point they are an angle and a radius. Give the crown a `spine_m` (two
plan points) and they wrap round that line instead: distance is measured to the
nearest point of the spine, and bearing runs once round it, as an angle round
each end and as a length along each side. The roof, the lattice, the crown ring
and the joints are written in those two coordinates only, so the same code
makes a round room or a hall with two straight sides and two round ends. Ribs
that spiral round a point run straight, as a diagonal grid, beside a spine.

A point crown is the special case of a spine with no length: a spine a micron
long gives the round room back to within five microns
(`tests/test_spine.py`).

## Joined rooms

Rooms are joined through a bay. `design["connections"]` pairs a bay of one room
with a bay of another, and the two are then the same opening seen from either
side, a portal: they stand on the same two piers and have one apex and one
arch. Each room keeps its own ring, crown, roof and IDs, so each is edited as
before; a shared pier has an ID in each room and moves in both.

`topology.add_room_from_bay(design, bay_id, bays=6, radius_m=...)` grows a new
room out of an open bay: its ring runs through the bay's two piers and round a
circle on the bay's outer side. `topology.remove_room` takes one away again and
leaves the other exactly as it was.

| What | How it is resolved |
|---|---|
| The shared arch | built once, by the room whose bay the connection names first; the lattice of both rooms is housed into it, one room into each face; each room keeps its own hoops inside it |
| A shared pier | three arch legs meet there and are mitred into one trunk, each leg keeping what lies nearer its own arch; each room's legs stand in its own angle between them |
| The two roofs | meet on the shared arch, in a fold along it, as two vaults meet at the arch between them. They are not smoothed into one surface; `envelope.check_connections` reports the fold |
| Joints and checks | found, milled and checked for the two rooms together, since they share members |
| The first room | its members are unchanged by the join, by resizing the second room and by moving its crown: only the shared arch gains joints |

A room joined to another cannot have its whole ring laid out afresh (its bay
count is changed with `add_bay` / `remove_bay`), except a room made by
`add_room_from_bay`, whose layout is a circle through its portal and can be
resized or recounted. Two rooms that overlap, or meet anywhere but on one
shared bay, are not handled.

## The timber generator

`bower/timber.py` is a small engine: one generator builds the arches, one builds
the lattice, and they share the piers. Each is chosen by name in `design.json`
and takes its own parameters, so the timber can be shifted a long way without
touching code. A new arrangement is a new generator class added to the
registry.

| `design.json` | Options | What it changes |
|---|---|---|
| `rooms[].layout.bays` | whole number, 3 or more | how many bays the room has. Change it and the next `generate.py` lays the ring out afresh on the room's present outline (same size, outline and apex heights; narrower or wider bays), keeps IDs where it can, and writes the new ring back to `design.json`. `layout.bay_weights` are the bays' relative widths. |
| `rooms[].layout.outline` | `radius_m`, `stretch`, `stretch_bearing_deg`, `taper`, `lobes`, `lobe_depth`, `centre_m` | the plan outline the piers stand on: round, oval, egg-shaped or lobed. Without it the ring keeps the outline it has. A pier moved by hand afterwards stays where it is put, and the layout then keeps only the bay count. Round a spine the outline is set off from the spine by `radius_m` (two straight sides, two round ends), the bays share out its length, and `first_pier_turn` (0 to 1) says how far round the first pier stands. |
| `connections` | list of `{id, bays: [bay, bay]}` | the bays through which rooms are joined: see Joined rooms. Made by `add_room_from_bay`; the two bays have the type `portal`. |
| `rooms[].layout.outline` in a joined room | `radius_m`, `through` (a connection ID) | the ring of a room grown out of a bay: a circle of that radius through the two piers of its portal. Change the radius (or `layout.bays`) and the next `generate.py` lays the room out afresh; the portal stays where it is and the crown moves with the circle's centre. |
| `rooms[].timber` | `lattice`, `arches`, `piers` | a room's own values for its lattice, hoops and piers, laid over the design's (a smaller room wants fewer ribs). Sections, joints and the arch type belong to the whole design. |
| `rooms[].crown.spine_m` | two plan points | draws the crown out into a straight line between them, for a long room; `centre_m` is its middle. Leave it out for a round room. The ring has to be laid out to suit (`layout.outline`), since every pier must stand clear of the lantern all the way along. |
| `rooms[].layout.apex_heights_m` | one height, or a list used in turn | the bays' apex heights, set from the layout instead of bay by bay |
| `rooms[].crown.section` | `base_slope_deg`, `top_slope_deg`, `fullness` | the shape of the crown between its base ring and its top ring. With the crown's `radius_m` and `height_m` this makes a lantern (the default), a flared basket (top slope over 90), a dome (steep base, level top), a flat ring round an open oculus (height equal to the lantern base height), or a trunk that comes down to the floor (height 0, top slope -90). |
| `timber.arches.type` | `edge`, `paired`, `none` | `edge`: one arch per bay on the roof's edge, the lattice housed into it. `paired`: the earlier light arch on the edge with a heavier one standing proud. |
| `timber.arches.hoops_m`, `hoop_nudge_m` | list of distances | hoops following each arch inside it, lying in the roof, each one member from pier to pier; empty for none |
| `timber.lattice.type` | `spiral`, `none` | the lattice generator |
| `timber.lattice.lean_deg`, `lean_top_deg`, `lean_rim_deg` | degrees | the angle ribs hold to the roof's meridians, and optionally the angle they straighten to at the crown and turn to by the arches |
| `timber.lattice.land_square_m`, `land_gap_m` | metres | within this distance of an arch a rib turns to meet it squarely (0 lets it hold its course), and neighbouring feet are kept this far apart along the arch |
| `timber.lattice.pair_gap_m` | metres | the two ribs that reach one point of the crown ring arrive side by side this far apart |
| `timber.lattice.ribs_per_family` | count | ribs of each hand per tier, evenly spaced along the crown ring (a long room has a longer ring and wants more) |
| `timber.lattice.tiers` | list | each tier is a family with its own section, starting at the top ring, part-way up the lantern or at a ring on the canopy |
| `timber.lattice.gather_m` | metres | ribs passing nearer than this to a pier are drawn into it and stand on the floor as legs |
| `timber.piers` | `legs`, `gap_m`, `ring_radius_m` | whether gathered ribs become legs, and how tightly the legs of a pier are packed |
| `timber.crown` | `seat_m` | how far the heads of the ribs are let into the crown ring |
| `timber.joints` | `lap_order`, `lap_clearance_m`, `housing_depth_m`, `max_piece_length_m`, `cut_meshes`, `solver` | which member of a lap is notched on which face, clearances and depths, where long members are spliced, and how joints are cut into the meshes: `milled` (every joint, by boolean), `notches` (laps only, stepped into the sweep) or `none` |
| `timber.sections_m` | width, depth per family | every family's section; the lattice families share one depth so that they lie flush |

Shape parameters under each room's `shape` (arch profile, canopy, pier funnel,
lantern) reshape the roof surface that all of the above lies in.

## Joints

`bower/joints.py` derives the joints from the members, so they regenerate with
them. Each joint names its two members, where it is, the angle they meet at and
one cut per member, set out along that member's own centreline: station, face,
length, depth and skew. Where two lattice members cross, both are notched to
half their depth; `lap_order` fixes which goes in first and is notched on its
outer face. Where a member is crossed on both faces at one place it keeps the
middle third of its depth, and those two laps are a third deep.

Members are milled by robot, so each joint is cut as the true shape of what it
receives. With `cut_meshes` set to `milled`, every lap, housing, seat and pier
mitre comes with a cutter: the mating member's own volume, a clearance larger,
on the cut side of the plane the two meet on. Lap walls follow the other
member's sides as they turn, a pocket is the shape of the end it takes, and a
shallow crossing becomes a long lap. Blender subtracts the cutters from each
member, so `TM_<id>` shows the piece as it would be machined, and the build
then measures how deeply any two members still overlap. `notches` is the
earlier, simpler model, kept as an option: flat-walled lap notches only.

A joint that still needs a detail of its own is not hidden: its `review` column
says why (two members running alongside each other, or four meeting at one
place). Depths and clearances are provisional concept values. This sets joints
out and cuts them; it does not prove them structurally.

### Joints the plants reach

A grown planting says which joints a plant that clings to the timber gets to
unaided, by the joints' own IDs, in how many of the runs and how soon. The
drawings write that list (`../drawings-in-code/scenes/<snapshot>/joints-reached.json`)
and one command copies it into the design, with where it came from:

```bash
python scripts/take_findings.py        # six-bay-radial-v1 into design/six_bay_radial.json
```

It lands in `timber.joints.reached_by_plants`. The design is the source, so a
snapshot made from it says what it was told. Each joint named is then noted in
the schedule's `review` column ("a clinging plant reaches this joint in 3 of 3
grown runs, first in year 5"), and the summary counts them as
`reached_by_plants`. A design that has changed so that a named joint is gone is
refused: the planting is to be grown again on it.

Nothing is cut differently for these joints yet. They need a detail that keeps
a stem out, and that detail is not designed; a lap is milled with the same
`lap_clearance_m` as every other. The note is the hand-off, not the answer.
`design/six_bay_radial.json` carries the 22 joints found on `six-bay-radial-v1`.

## Training lines

`bower/lines.py` strings thin steel cables on the timber for plants to climb. A
line belongs to one member: it runs along that member's centreline, a set gap
off one face of its section, on standoffs fixed into the member. So it has the
member's curve and no direction the timber does not have. Lines are derived
from the members and their joints and regenerate with them. A design without
`timber.training_lines` has none.

| `timber.training_lines` | Options | What it changes |
|---|---|---|
| `carry` | `grounded`, `all`, `none` | which members carry a line. `grounded`: every member of `families` that stands on the floor, so that a plant has one timber from the soil upward |
| `families`, `members`, `without` | families; member IDs | the families that may carry a line (the lattice's, by default: not the arches); members that carry one whatever `carry` says; members that carry none |
| `face` | `outer`, `inner` | the face the line stands off: the roof's upper side, or the room's |
| `gap_m`, `cable_diameter_m` | metres | from that face to the middle of the cable, and the cable |
| `standoff_spacing_m`, `standoff_sag_m` | metres | the furthest apart two standoffs stand, and how far the cable, which is straight between two, may stray from the member's curve: on a bend they stand closer |
| `clear_m` | metres | a line keeps this far from every other member; where it cannot, it is cut back and the schedule says why |
| `foot_clear_m`, `end_clear_m` | metres | how far above the floor a line starts, and how far short of any other end of its member it stops |

What is written: one curve per line, `LN_<member>.line`, in `40_CABLES`, with
the cable and its standoffs at their true size; `output/line_schedule.csv`, one
row per line (where it starts and ends, at which pier, its length, its
standoffs, the nearest other member); and one `standoff` row per hole in
`output/joint_schedule.csv`, set out like any other cut: station along the
member, face, diameter, depth.

The lattice is flush, so a line passes over every member that crosses its own
by the gap. `lines.check_lines` measures every cable against every member, and
`scripts/training_lines.py` measures them again in Blender against the meshes
as milled.

Known limits, none of them hidden:

- At a pier the legs stand in a tight arc behind the two arch legs, and a leg's
  outer face looks at those arch legs. A line on the outer face therefore
  starts inside the pier, in the pocket between the legs and the arches
  (`views/lines_pier_foot.png`): clear of the timber, but not where a plant can
  be put. `foot_clear_m` starts the lines higher; `face: inner` puts them on
  the room's side all the way up. Running a line up the room's side of a leg
  and over to the outer face above the pier is not built.
- Two lines whose members cross are strung at one height and touch where they
  cross. Which goes over is left to the site.
- A standoff is kept out of a lap cut in the face it is fixed to, where that
  face belongs to the crossing member. On a bend that leaves no other place a
  few stand in one; their rows in the joint schedule say so.
- End fittings and tensioners are not modelled.
- Lines are not in snapshots: `bower/snapshot.py` is unchanged.
- `build_design` on its own (the panel's rebuilds, the gate scripts) does not
  string lines, and clears those of the rooms it rebuilds. `scripts/generate.py`
  strings them.

## The ground at a pier

A draft, at one pier (`R1.P6`). `bower/ground.py` sets out what shares the
ground where the building comes down: a plant's roots, the footing the legs
stand on, and the plant's way up to its training lines. Nothing in it moves a
member; where the ground cannot be shared it says so, for the pier to be
changed or the plant moved. A design without a `ground` block has none.

| `ground` | What it is |
|---|---|
| `root_zones` | authored, as piers are: `{id, position_m, radius_m, depth_m, plant, needs_soil_m3}`, a cylinder of soil kept for one plant. `plant` and `needs_soil_m3` are the plant side's to say and are only carried here: a zone with less soil than it is said to need is marked for review. `ground.beside_pier(...)` gives the zones to author outside a pier's arch legs. |
| `footings` | generated, one under every pier, of the `type` named. `piles`: screw piles under a steel cap the feet stand on. The cap is lifted clear of the soil, so the ground stays open under the whole pier and a root zone loses only a sleeve of soil round each shaft. Piles cannot stand as close as the feet do, so they stand in a ring, `spacing_m` apart: as few as leave no foot further than `reach_m` from one, never fewer than `least`, and `plant_clear_m` from any plant; the cap reaches out to a pile that stands outside the feet. `pad`: the earlier model, kept as an option: a solid pad, the outline of the feet grown by `margin_m`, cut back beside a root zone but never to less than `least_m` beyond a foot; where that stops it, the zone loses ground and both say so. |
| `feeders` | generated: two cables on the arch leg nearest each zone, set out as training lines are. One stands off the leg's exterior face from the floor; the other stands off the arch's back, which is free only where the pier's two arches have parted (about 2.4 m up). They run side by side for `overlap_m`, so a shoot is led round one corner of the arch. |
| hand-overs | measured: from the feeder on the arch's back to each training line that starts at that pier, the shortest straight tie that passes clear of the timber, no longer than `feeders.reach_m`. Where a gardener leads a shoot across; nothing is built there. |
| entrances | measured: the clear way through each open bay, between its arch legs and between the root zones beside them; narrower than `entrances.least_m` is marked for review. |

What is written: `RS_<zone>` empties and `RZ_<zone>` soil drums in
`50_PLANTING_POINTS`, `FT_<pier>` caps (or pads) and `PL_<pier>` piles in
`45_FOOTINGS`, `HO_<pier>` ties (green) at a planted pier, the feeders with
the other lines in `40_CABLES` and in the line and joint schedules, and
`output/root_schedule.csv`. Under a cap on piles the soil lies below the feet,
so the soil drums and the piles are under the scene's ground disc: hide
`CTX_ground` to see them.

What the draft shows at `R1.P6`, and what it leaves open:

- A plant rooted outside reaches every training line that starts at the pier,
  but only above head height: the hand-overs fall between 2.8 and 3.6 m up.
  Below that the training lines are behind the arch legs, so about 3 m of each
  of them is cable no plant from outside can use.
- On screw piles the ground is no longer tight. Three piles 0.9 m apart carry
  each pier under a cap hardly larger than the feet, and a root zone 0.4 m
  from its feeder keeps 97% of its ground. A pad at that distance takes 9% and
  cannot be cut back far enough; it needs the zone 0.65 m away.
- Lifting the cap clear of the soil puts the soil at a pier 0.3 m below the
  feet (`feet_above_soil_m`). Whether that means the feet are raised above the
  ground all round, or each pier stands in a sunken bed, is not decided: the
  model only puts the root zones at that level.
- Two zones beside a pier take 0.3 m off the way through each bay beside it.
- No foundation has been designed or sized. The number of piles follows from
  where the feet stand, not from any load; the outward push of the arches on
  slender piles in soft planting soil is not looked at; nothing is known of
  the soil; and root zones are not in snapshots.

## Regenerate the scene

In Blender (5.1 or later), from the Python console, the Text Editor or the MCP connector:

```python
import runpy
runpy.run_path(r"C:\BOWER\Auxin\bower-blender\scripts\generate.py")["main"]()
```

| Script | What it does |
|---|---|
| `scripts/panel.py` | Opens the Bower panel in the 3D viewport's sidebar: sliders, live handles, draft and milled rebuilds. See Working on the model in Blender. |
| `scripts/generate.py` | Rebuilds handles, envelope, timber, context and cameras from `design.json`, strings the training lines, and writes `output/member_schedule.csv`, `output/joint_schedule.csv` and `output/line_schedule.csv`. Pass `views_dir=` to render the views as well, and `design_path=` to build another design file (`design/two_rooms.json`). |
| `scripts/apply_handles.py` | Reads handles you have dragged in `00_CONTROLS` back into `design.json`, then rebuilds. |
| `scripts/gate2_demo.py` | Regenerates the timber after four topology edits and checks each result. |
| `scripts/gate2_shifts.py` | Regenerates the timber under two shifts of its parameters and checks each result. |
| `scripts/gate2_forms.py` | Builds and renders seven different structures from the same code by changing the crown's section, the plan's outline and the crown's spine (`views/form_*.png`; the sheets `views/gate2_forms.jpg` and `views/gate2_hall.jpg` are put together from those). `main(only={...}, milled=True)` also mills a form's joints and records how cleanly. |
| `scripts/gate3_rooms.py` | Joins a second, smaller room to the first through one bay, writes the pair to `design/two_rooms.json`, then resizes the second room, moves its crown and moves a shared pier, checking the first room each time; last it builds the pair with every joint milled (`views/gate3_*.png`, `output/gate3_rooms.json`). Leaves the scene as the pair. |
| `scripts/gate2_notches_view.py` | Renders a close view with the ribs of one hand left out, so the lap notches can be seen. |
| `scripts/training_lines.py` | Builds the design with its training lines, measures every cable against the timber meshes as milled, and renders them: close views at true size (`views/lines_*.png`), and diagrams of where the cables run, each drawn as a plain line thick enough to follow with its standoffs left out: training lines blue, feeders red, hand-overs green (`views/lines_diagram_*.png`). Writes `output/training_lines.json`. Runs without a window too: `blender --background --factory-startup --python scripts/training_lines.py`. |
| `scripts/export_snapshot.py` | Writes a named, frozen copy of the model to `../releases/<name>/` for other work to link or read. See `../releases/README.md`. |
| `scripts/gate1_demo.py` | The same four edits, reported at envelope level. |
| `scripts/gate0.py` | Rebuilds the Gate 0 test member from `design/gate0_member.json`. |

Every member is two objects: `CL_<id>`, its Bezier centreline in
`20_PRIMARY_CENTERLINES`, and `TM_<id>`, the swept solid with its joints milled, in
`21_PRIMARY_MESHES`. `JT_<room>` in `80_DIAGNOSTICS` holds one point per joint.
A build with milled joints takes about a minute.
Set `"display": {"envelope": true}` in `design.json` to show the guide surface.

Generated objects carry a `bower_generated` flag and are replaced in place.
Objects without it are never touched. Start from an empty scene (delete or hide
the default cube, which sits inside the room).

## Tests

No Blender needed:

```
python tests/test_gate0_geometry.py
python tests/test_gate1_room.py
python tests/test_gate2_timber.py
python tests/test_snapshot.py
python tests/test_bay_count.py
python tests/test_forms.py
python tests/test_spine.py
python tests/test_rooms.py
python tests/test_controls.py
python tests/test_lines.py
python tests/test_ground.py
python tests/survey_envelope_validity.py     # slower: random walks of edits
```

The room and timber tests name particular piers and bays, so they run on the
frozen design in `../releases/six-bay-v1`: they also show that an old snapshot
still builds. `test_bay_count.py` and `test_snapshot.py` run on `design.json`
as it stands.

## Layout

```
design.json                     authored topology and parameters
design/two_rooms.json           the same room with a second joined to it (made by scripts/gate3_rooms.py)
bower/topology.py               Level A
bower/spine.py                  bearing and distance round a crown that is a point or a line
bower/envelope.py               Level B
bower/timber.py                 Level C: member generators, clearances, schedule
bower/joints.py                 Level C: joints and the cuts they make
bower/lines.py                  training lines for plants: cables held off the members on standoffs
bower/ground.py                 the ground at a pier: root zones, footings, feeders, hand-overs
bower/blender_lines.py          writes the lines into Blender and measures them against the timber there
bower/blender_ground.py         writes root zones, footings and hand-overs into Blender
bower/snapshot.py               what a snapshot carries: centrelines, schedules, manifest
../releases/                    named snapshots of the model, at the top of the repository
bower/centreline.py             Bezier paths, sampling, frames
bower/member.py                 member data and section sweep
bower/controls.py               what each slider reads from a design and changes in it
bower/blender_scene.py          writes the design into Blender, at outline, draft or full detail
bower/blender_ui.py             the panel: sliders, live handles, rebuild buttons
scripts/                        entry points run inside Blender
tests/                          geometry, topology and timber tests
output/bower_v1.blend           the scene as last saved
output/member_schedule.csv      one row per primary member
output/joint_schedule.csv       one row per joint, and one per standoff hole where the design has training lines
output/line_schedule.csv        one row per training line and feeder
output/root_schedule.csv        one row per root zone
output/training_lines.json      record of the lines and the ground as set out, and of the cables as measured in the scene
output/gate2_regeneration.json  record of the Gate 2 edit checks
output/gate2_shifts.json        record of the Gate 2 parameter-shift checks
output/gate2_forms.json         record of the forms, with the long hall's milled check
output/gate3_rooms.json         record of the joined rooms: the edits, the milled check, how the roofs meet
views/                          renders and viewport captures
```

The construction of each level is described at the top of its module.
