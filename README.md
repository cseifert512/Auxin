# Bower V1

A procedural model of a Bower: rooms, bays and crowns are edited as a small plan
graph, and the architectural envelope and the primary timber are regenerated
from it. The brief is in
`Bower_Claude_Blender_Handoff/Bower_Blender_Claude_Handoff/BOWER_V1_CLAUDE_HANDOFF.md`.

Status: Gate 2 (one six-bay room with its primary timber). No connected rooms,
no planting. Dimensions, sections and clearances are provisional concept
values; nothing here is a structural, fabrication or horticultural check.

## Source of truth

`design.json` holds the authored design: rooms, piers, bays, crown, shape
parameters, timber sections and rules, sampling densities, view cameras.
Everything in Blender is generated from it and can be deleted and rebuilt.
Units are metres, Z up, Y north.

Three levels, each generated from the one before:

| Level | Module | What it holds |
|---|---|---|
| A, topology | `bower/topology.py` | piers, bays, crown, persistent IDs, edit operations |
| B, envelope | `bower/envelope.py` | the roof as one smooth surface: pointed arches at the rim, a canopy that gathers onto each pier, a lantern at the centre (a guide surface, hidden by default) |
| C, members | `bower/timber.py` | arches that are the roof's edge, hoops inside them, a flush lattice of spiralling ribs in tiers, a crown ring, and piers that are bundles of the legs of those members |
| C, joints | `bower/joints.py` | every joint between those members, the cut it makes in each, and the volume to mill out: laps, housings, mitres, seats, splices, bases |

## The timber generator

`bower/timber.py` is a small engine: one generator builds the arches, one builds
the lattice, and they share the piers. Each is chosen by name in `design.json`
and takes its own parameters, so the timber can be shifted a long way without
touching code. A new arrangement is a new generator class added to the
registry.

| `design.json` | Options | What it changes |
|---|---|---|
| `timber.arches.type` | `edge`, `paired`, `none` | `edge`: one arch per bay on the roof's edge, the lattice housed into it. `paired`: the earlier light arch on the edge with a heavier one standing proud. |
| `timber.arches.hoops_m`, `hoop_nudge_m` | list of distances | hoops following each arch inside it, lying in the roof, each one member from pier to pier; empty for none |
| `timber.lattice.type` | `spiral`, `none` | the lattice generator |
| `timber.lattice.lean_deg`, `lean_top_deg`, `lean_rim_deg` | degrees | the angle ribs hold to the roof's meridians, and optionally the angle they straighten to at the crown and turn to by the arches |
| `timber.lattice.land_square_m`, `land_gap_m` | metres | within this distance of an arch a rib turns to meet it squarely (0 lets it hold its course), and neighbouring feet are kept this far apart along the arch |
| `timber.lattice.pair_gap_m` | metres | the two ribs that reach one point of the crown ring arrive side by side this far apart |
| `timber.lattice.ribs_per_family` | count | ribs of each hand per tier |
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

## Regenerate the scene

In Blender (5.1 or later), from the Python console, the Text Editor or the MCP connector:

```python
import runpy
runpy.run_path(r"C:\BOWER\bower-blender\scripts\generate.py")["main"]()
```

| Script | What it does |
|---|---|
| `scripts/generate.py` | Rebuilds handles, envelope, timber, context and cameras from `design.json`, and writes `output/member_schedule.csv` and `output/joint_schedule.csv`. Pass `views_dir=` to render the views as well. |
| `scripts/apply_handles.py` | Reads handles you have dragged in `00_CONTROLS` back into `design.json`, then rebuilds. |
| `scripts/gate2_demo.py` | Regenerates the timber after four topology edits and checks each result. |
| `scripts/gate2_shifts.py` | Regenerates the timber under two shifts of its parameters and checks each result. |
| `scripts/gate2_notches_view.py` | Renders a close view with the ribs of one hand left out, so the lap notches can be seen. |
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
python tests/survey_envelope_validity.py     # slower: random walks of edits
```

## Layout

```
design.json                     authored topology and parameters
bower/topology.py               Level A
bower/envelope.py               Level B
bower/timber.py                 Level C: member generators, clearances, schedule
bower/joints.py                 Level C: joints and the cuts they make
bower/centreline.py             Bezier paths, sampling, frames
bower/member.py                 member data and section sweep
bower/blender_scene.py          the only module that touches Blender
scripts/                        entry points run inside Blender
tests/                          geometry, topology and timber tests
output/bower_v1.blend           the scene as last saved
output/member_schedule.csv      one row per primary member
output/joint_schedule.csv       one row per joint
output/gate2_regeneration.json  record of the Gate 2 edit checks
output/gate2_shifts.json        record of the Gate 2 parameter-shift checks
views/                          renders and viewport captures
```

The construction of each level is described at the top of its module.
