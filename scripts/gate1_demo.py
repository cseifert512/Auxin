"""Gate 1 demonstration: move a pier, raise the crown, add a bay, delete a bay.

Each edit is applied to the room in design.json on its own, rebuilt in the open
Blender scene, checked and rendered; then all four are applied in sequence.
design.json is not modified and the scene is left as design.json describes it.

Outputs: views/gate1_demo_*.png and output/gate1_demo.json.

Run inside Blender:
    runpy.run_path(r"<repo>/scripts/gate1_demo.py")["main"]()
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
    from bower.blender_scene import build_design, read_dragged_handles, render_views
    from bower.envelope import bay_signature, build_envelope

    scene = bpy.context.scene
    base = topology.load(DESIGN)

    def drag_pier_handle(design):
        """The direct-manipulation path: move the handle empty, then read handles back into the design."""
        bpy.data.objects["H_R1.P3"].location.xy = (5.9, 0.3)
        after, changes = read_dragged_handles(design)
        return after, changes[0]

    steps = [
        ("1_move_pier", "drag handle H_R1.P3 to (5.90, 0.30) and apply handles", drag_pier_handle, lambda d: topology.move_pier(d, "R1.P3", [5.9, 0.3])),
        ("2_crown_height", "set_crown(R1, height_m=7.2), up from 6.0", None, lambda d: topology.set_crown(d, "R1", height_m=7.2)),
        ("3_add_bay", "add_bay(R1.B1): split the front bay with a new pier", None, lambda d: topology.add_bay(d, "R1.B1")),
        ("4_remove_bay", "remove_bay(R1.B2): collapse the south-east bay", None, lambda d: topology.remove_bay(d, "R1.B2")),
    ]

    def ids(design):
        room = design["rooms"][0]
        return {"piers": [p["id"] for p in room["piers"]], "bays": [b["id"] for b in room["bays"]]}

    def compare(before, after):
        """Which surviving bays are vertex-for-vertex identical, and which changed."""
        env_a = build_envelope(before["rooms"][0], before["sampling"])
        env_b = build_envelope(after["rooms"][0], after["sampling"])
        kept = [b for b in ids(before)["bays"] if b in ids(after)["bays"]]
        same = [b for b in kept if bay_signature(env_a, b) == bay_signature(env_b, b)]
        return {"identical_bays": same, "reshaped_bays": [b for b in kept if b not in same]}

    def build_and_render(design, name):
        room = build_design(scene, design)["rooms"][0]
        image = render_views(scene, design, REPO / "views", f"gate1_demo_{name}_", only={"overhead"})[0]
        return {"envelope": room["envelope"], "scene_check": room["scene_check"], "stale_objects_removed": room["stale_objects_removed"], "image": Path(image).name}

    record = {"design": str(DESIGN), "base": ids(base), "steps": []}
    for name, description, in_scene, operation in steps:
        build_design(scene, base)  # every step starts from the room in design.json
        after, change = (in_scene or operation)(base)
        record["steps"].append({"step": name, "edit": description, "change": change, "ids_after": ids(after), **compare(base, after), **build_and_render(after, name)})

    chained = base
    for _, _, _, operation in steps:
        chained, _ = operation(chained)
    record["all_four_in_sequence"] = {"ids_after": ids(chained), **compare(base, chained), **build_and_render(chained, "5_all_four")}

    build_design(scene, base)  # leave the scene as design.json describes it
    (REPO / "output").mkdir(exist_ok=True)
    (REPO / "output" / "gate1_demo.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
