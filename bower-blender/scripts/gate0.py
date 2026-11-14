"""Gate 0: build the test member in design/gate0_member.json into the open Blender scene.

Run inside Blender, any of:
    runpy.run_path(r"<repo>/scripts/gate0.py")["main"]()     (MCP or the Python console)
    Text Editor > Open > Run Script
    blender --python scripts/gate0.py

Re-running rebuilds the same objects in place; edit the JSON, not the objects.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "design" / "gate0_member.json"


def main(design_path=DESIGN) -> dict:
    import bpy

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    for name in [m for m in sys.modules if m == "bower" or m.startswith("bower.")]:
        del sys.modules[name]  # pick up source edits in a long-lived Blender session
    from bower.blender_scene import build_member
    from bower.member import member_from_spec

    scene = bpy.context.scene
    units = scene.unit_settings
    if units.system != "METRIC" or abs(units.scale_length - 1.0) > 1e-9:
        raise RuntimeError(
            f"scene units are {units.system} x {units.scale_length}; bower geometry is in metres at scale 1.0"
        )
    design = json.loads(Path(design_path).read_text(encoding="utf-8"))
    return {
        "blender": bpy.app.version_string,
        "design": str(design_path),
        "members": [build_member(scene, member_from_spec(spec), design["sampling"]) for spec in design["members"]],
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
