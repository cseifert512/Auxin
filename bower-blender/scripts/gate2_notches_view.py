"""Gate 2: show the lap notches, by rendering one view with the ribs of one hand left out.

With the counter-clockwise ribs hidden, the notches they drop into are open to
view in the hoops, the rings and the clockwise ribs. Nothing in the scene is
changed: the hidden members are shown again afterwards.

Output: views/gate2_notches_<view>.png

Run inside Blender, after scripts/generate.py:
    runpy.run_path(r"<repo>/scripts/gate2_notches_view.py")["main"]()
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "design.json"


def main(hide: str = "ccw", view: str = "detail_notches") -> dict:
    import bpy

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from bower import topology
    from bower.blender_scene import render_views

    design = topology.load(DESIGN)
    hidden = [o for o in bpy.data.objects if o.get("bower_kind") == "timber_preview" and f".{hide}." in o.get("bower_id", "")]
    for obj in hidden:
        obj.hide_render = True
    try:
        paths = render_views(bpy.context.scene, design, REPO / "views", "gate2_notches_", only={view})
    finally:
        for obj in hidden:
            obj.hide_render = False
    return {"hidden_members": len(hidden), "image": paths[0]}


if __name__ == "__main__":
    print(main())
