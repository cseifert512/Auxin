"""Direct manipulation, explicit form: drag handles in Blender, then run this.

Every handle in 00_CONTROLS that has moved since it was placed is turned into
the matching topology operation (move_pier, set_crown, set_apex). If the result
is a valid design it is written to design.json and the scene is rebuilt from
it; if not, nothing is written and the error says which handle went too far.

Run inside Blender:
    runpy.run_path(r"<repo>/scripts/apply_handles.py")["main"]()
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "design.json"


def main(design_path=DESIGN) -> dict:
    import bpy

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    for name in [m for m in sys.modules if m == "bower" or m.startswith("bower.")]:
        del sys.modules[name]
    from bower import topology
    from bower.blender_scene import build_design, read_dragged_handles

    design, changes = read_dragged_handles(topology.load(design_path))
    if changes:
        topology.save(design_path, design)
    return {"changes": changes, **build_design(bpy.context.scene, design)}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
