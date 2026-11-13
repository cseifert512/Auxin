# Bower V1

A procedural model of a Bower: rooms, bays and crowns are edited as a small plan
graph, and the architectural envelope and the primary timber are regenerated
from it. The brief is in
`Bower_Claude_Blender_Handoff/Bower_Blender_Claude_Handoff/BOWER_V1_CLAUDE_HANDOFF.md`.

Status: Gate 2 (one six-bay room with its primary glulam members). No secondary
lattice, no connected rooms, no planting. Dimensions, sections and clearances
are provisional concept values; nothing here is a structural, fabrication or
horticultural check.

## Source of truth

`design.json` holds the authored design: rooms, piers, bays, crown, shape
parameters, timber sections and rules, sampling densities, view cameras.
Everything in Blender is generated from it and can be deleted and rebuilt.
Units are metres, Z up, Y north.

Three levels, each generated from the one before:

| Level | Module | What it holds |
|---|---|---|
| A, topology | `bower/topology.py` | piers, bays, crown, persistent IDs, edit operations |
| B, envelope | `bower/envelope.py` | named boundary curves, fans and roof panels (a guide surface, hidden by default) |
| C, members | `bower/timber.py` | arches, groins, ridges, sweeps, liernes, crown ring, each a planar centreline with a section |

## Regenerate the scene

In Blender (5.1 or later), from the Python console, the Text Editor or the MCP connector:

```python
import runpy
runpy.run_path(r"C:\BOWER\bower-blender\scripts\generate.py")["main"]()
```

| Script | What it does |
|---|---|
| `scripts/generate.py` | Rebuilds handles, envelope, timber, context and cameras from `design.json`, and writes `output/member_schedule.csv`. Pass `views_dir=` to render the views as well. |
| `scripts/apply_handles.py` | Reads handles you have dragged in `00_CONTROLS` back into `design.json`, then rebuilds. |
| `scripts/gate2_demo.py` | Regenerates the timber after four topology edits and checks each result. |
| `scripts/gate1_demo.py` | The same four edits, reported at envelope level. |
| `scripts/gate0.py` | Rebuilds the Gate 0 test member from `design/gate0_member.json`. |

Every member is two objects: `CL_<id>`, its Bezier centreline in
`20_PRIMARY_CENTERLINES`, and `TM_<id>`, the swept solid in `21_PRIMARY_MESHES`.
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
bower/timber.py                 Level C: member grammar, clearances, schedule
bower/centreline.py             Bezier paths, sampling, frames
bower/member.py                 member data and section sweep
bower/blender_scene.py          the only module that touches Blender
scripts/                        entry points run inside Blender
tests/                          geometry, topology and timber tests
output/bower_v1.blend           the scene as last saved
output/member_schedule.csv      one row per primary member
output/gate2_regeneration.json  record of the Gate 2 edit checks
views/                          renders and viewport captures
```

The construction of each level is described at the top of its module.
