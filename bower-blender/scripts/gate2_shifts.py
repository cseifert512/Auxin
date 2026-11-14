"""Gate 2: the same room under shifts of the timber parameters.

Not alternative proposals: a demonstration that the generator's options
regenerate a checked model. Each shift changes a few values under
design["timber"], rebuilds the scene, checks the timber and renders the overhead
view. design.json is not modified and the scene is left as it describes.

Outputs: views/gate2_shift_*.png and output/gate2_shifts.json.

Run inside Blender:
    runpy.run_path(r"<repo>/scripts/gate2_shifts.py")["main"]()
"""
import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "design.json"

SHIFTS = [
    (
        "1_sweeping_ribs",
        "ribs lean 32 degrees at the lantern and sweep round to 62 degrees at the arches",
        {"lattice": {"lean_deg": 32.0, "lean_rim_deg": 62.0}},
    ),
    (
        "2_upright_fine_weave",
        "ribs lean 25 degrees, 16 to a family instead of 12, one hoop 0.7 m inside each arch",
        {"lattice": {"lean_deg": 25.0, "ribs_per_family": 16}, "arches": {"hoops_m": [0.7]}},
    ),
]


def main() -> dict:
    import bpy

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    for name in [m for m in sys.modules if m == "bower" or m.startswith("bower.")]:
        del sys.modules[name]
    from bower import topology
    from bower.blender_scene import build_design, render_views

    scene = bpy.context.scene
    base = topology.load(DESIGN)
    record = {"design": str(DESIGN), "shifts": []}
    for name, description, changes in SHIFTS:
        shifted = copy.deepcopy(base)
        for section, values in changes.items():
            shifted["timber"][section].update(values)
        timber = build_design(scene, shifted)["rooms"][0]["timber"]
        image = render_views(scene, shifted, REPO / "views", f"gate2_shift_{name}_", only={"overhead"})[0]
        record["shifts"].append(
            {
                "shift": description,
                "timber": changes,
                "members": timber["members"],
                "families": timber["families"],
                "joints": timber["joints"],
                "lap_notches_cut": timber["lap_notches_cut"],
                "collisions_estimated": timber["collisions_estimated"],
                "mesh_intersections_in_scene": timber["mesh_intersections_in_scene"],
                "meshes_closed": timber["meshes_closed"],
                "image": Path(image).name,
            }
        )
    build_design(scene, base)  # leave the scene as design.json describes it
    (REPO / "output").mkdir(exist_ok=True)
    (REPO / "output" / "gate2_shifts.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
