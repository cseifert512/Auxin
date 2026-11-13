"""Rebuild the Bower scene from design.json: handles, boundary curves, envelope, context, cameras.

Run inside Blender, any of:
    runpy.run_path(r"<repo>/scripts/generate.py")["main"]()      (MCP or the Python console)
    Text Editor > Open > Run Script
    blender --python scripts/generate.py

Pass views_dir to also render the design's views there. Re-running rebuilds the
same objects in place; change design.json (or drag handles and run
apply_handles.py), not the generated objects.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "design.json"


def main(design_path=DESIGN, views_dir=None, view_prefix="") -> dict:
    import bpy

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    for name in [m for m in sys.modules if m == "bower" or m.startswith("bower.")]:
        del sys.modules[name]  # pick up source edits in a long-lived Blender session
    from bower import topology
    from bower.blender_scene import build_design, render_views

    scene = bpy.context.scene
    units = scene.unit_settings
    if units.system != "METRIC" or abs(units.scale_length - 1.0) > 1e-9:
        raise RuntimeError(f"scene units are {units.system} x {units.scale_length}; bower geometry is in metres at scale 1.0")
    design = topology.load(design_path)
    report = {"blender": bpy.app.version_string, "design": str(design_path), **build_design(scene, design)}
    if views_dir is not None:
        report["views"] = render_views(scene, design, views_dir, view_prefix)
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
