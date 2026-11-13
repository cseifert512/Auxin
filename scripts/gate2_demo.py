"""Gate 2 validation: regenerate the primary timber after representative topology edits.

Each edit is applied to the room in design.json on its own, the whole scene is
rebuilt in the open Blender session, and the timber is checked twice: by the
source-side clearance estimate and by intersecting the member meshes in Blender.
design.json is not modified and the scene is left as design.json describes it.

Outputs: views/gate2_edit_*.png and output/gate2_regeneration.json.

Run inside Blender:
    runpy.run_path(r"<repo>/scripts/gate2_demo.py")["main"]()
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "design.json"


def main() -> dict:
    import bpy

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    for name in [m for m in sys.modules if m == "bower" or m.startswith("bower.")]:
        del sys.modules[name]
    from bower import topology
    from bower.blender_scene import build_design, render_views
    from bower.timber import build_timber

    scene = bpy.context.scene
    base = topology.load(DESIGN)

    def shapes(design):
        return {m.id: tuple((a.co, a.handle_left, a.handle_right) for a in m.path.anchors) for m in build_timber(design["rooms"][0], design["timber"])}

    before = shapes(base)
    edits = [
        ("1_move_pier", "move_pier(R1.P3, [7.0, 0.3])", lambda d: topology.move_pier(d, "R1.P3", [7.0, 0.3])),
        ("2_crown_height", "set_crown(R1, height_m=7.0), up from 6.3", lambda d: topology.set_crown(d, "R1", height_m=7.0)),
        ("3_add_bay", "add_bay(R1.B1): split the front bay", lambda d: topology.add_bay(d, "R1.B1")),
        ("4_remove_bay", "remove_bay(R1.B2): collapse the south-east bay", lambda d: topology.remove_bay(d, "R1.B2")),
    ]
    record = {"design": str(DESIGN), "base_members": len(before), "edits": []}
    for name, description, edit in edits:
        edited, change = edit(base)
        timber = build_design(scene, edited)["rooms"][0]["timber"]
        after = shapes(edited)
        image = render_views(scene, edited, REPO / "views", f"gate2_edit_{name}_", only={"overhead"})[0]
        record["edits"].append(
            {
                "edit": description,
                "change": change,
                "members": timber["members"],
                "members_added": sorted(set(after) - set(before)),
                "members_removed": sorted(set(before) - set(after)),
                "members_reshaped": sum(1 for k in after if k in before and after[k] != before[k]),
                "members_identical": sum(1 for k in after if k in before and after[k] == before[k]),
                "families": timber["families"],
                "joints": timber["joints"],
                "lap_notches_cut": timber["lap_notches_cut"],
                "collisions_estimated": timber["collisions_estimated"],
                "mesh_intersections_in_scene": timber["mesh_intersections_in_scene"],
                "meshes_closed": timber["meshes_closed"],
                "max_centreline_deviation_m": timber["max_centreline_deviation_m"],
                "image": Path(image).name,
            }
        )
    build_design(scene, base)  # leave the scene as design.json describes it
    (REPO / "output").mkdir(exist_ok=True)
    (REPO / "output" / "gate2_regeneration.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
