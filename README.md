# Bower V1

A procedural model of a Bower: rooms, bays and crowns are edited as a small plan
graph, and the architectural envelope (and, later, the timber members) is
regenerated from it. The brief is in
`Bower_Claude_Blender_Handoff/Bower_Blender_Claude_Handoff/BOWER_V1_CLAUDE_HANDOFF.md`.

Status: Gate 1 (one six-bay room, control topology and light envelope). No
timber, no planting. Dimensions are provisional design values; nothing here is
a structural, fabrication or horticultural check.

## Source of truth

`design.json` holds the authored design: rooms, piers, bays, crown, shape
parameters, sampling densities, view cameras. Everything in Blender is
generated from it and can be deleted and rebuilt. Units are metres, Z up, Y north.

## Regenerate the scene

In Blender (5.1 or later), from the Python console, the Text Editor or the MCP connector:

```python
import runpy
runpy.run_path(r"C:\BOWER\bower-blender\scripts\generate.py")["main"]()
```

| Script | What it does |
|---|---|
| `scripts/generate.py` | Rebuilds handles, boundary curves, envelope, context and cameras from `design.json`. Pass `views_dir=` to render the views as well. |
| `scripts/apply_handles.py` | Reads handles you have dragged in `00_CONTROLS` back into `design.json`, then rebuilds. |
| `scripts/gate1_demo.py` | Runs the four Gate 1 edits (move pier, crown height, add bay, delete bay), checks and renders each. |
| `scripts/gate0.py` | Rebuilds the Gate 0 test member from `design/gate0_member.json`. |

Generated objects carry a `bower_generated` flag and are replaced in place.
Objects without it are never touched. Start from an empty scene (delete or hide
the default cube, which sits inside the room).

## Tests

No Blender needed:

```
python tests/test_gate0_geometry.py
python tests/test_gate1_room.py
python tests/survey_envelope_validity.py     # slower: random walks of edits
```

## Layout

```
design.json               authored topology and parameters
bower/topology.py         Level A: plan graph, validation, edit operations
bower/envelope.py         Level B: boundary curves, fans and roof panels, validity checks
bower/centreline.py       Bezier paths, sampling, frames
bower/member.py           Level C: members (Gate 0 only so far)
bower/blender_scene.py    the only module that touches Blender
scripts/                  entry points run inside Blender
tests/                    geometry and topology tests
output/bower_v1.blend     the scene as last saved
output/gate1_demo.json    record of the Gate 1 edit demonstrations
views/                    renders and viewport captures
```

How the envelope is constructed is described at the top of `bower/envelope.py`;
how IDs and edits work, at the top of `bower/topology.py`.
