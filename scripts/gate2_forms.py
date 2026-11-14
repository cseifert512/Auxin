"""Gate 2: different structures from the same code, by changing the crown's section, the plan's outline and the crown's spine.

Each form changes a few values of the room in design.json (its crown, its
shape, its layout, and where needed the timber's counts), rebuilds the scene
and renders two views. The timber and joinery code is the same for all of
them. design.json is not modified and the scene is left as it describes.

For speed the forms are built without milling the joints into the meshes; the
joints are still set out and counted. With milled=True they are milled as well
and the record says how cleanly: slower, and worth doing for one form at a time.

Outputs: views/form_*.png and output/gate2_forms.json.

Run inside Blender:
    runpy.run_path(r"<repo>/scripts/gate2_forms.py")["main"]()
    runpy.run_path(r"<repo>/scripts/gate2_forms.py")["main"](only={"7_long_hall"}, milled=True, views=("plan", "interior", "exterior", "overhead"))
"""
import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "design.json"

# name, what it is, and the changes: to the room's crown and shape, to its layout, and to the timber
FORMS = [
    (
        "1_flared_basket",
        "the crown leans back out at the top, as a flared basket: nearest the reference",
        {"crown": {"height_m": 7.4, "radius_m": 1.5, "section": {"top_slope_deg": 118.0}}},
    ),
    (
        "2_dome",
        "the crown rises steeply from the canopy and levels off at a small oculus: a dome",
        {"crown": {"height_m": 7.4, "radius_m": 0.9, "section": {"base_slope_deg": 38.0, "top_slope_deg": 8.0}}},
    ),
    (
        "3_open_oculus",
        "no lantern: the canopy runs level to a ring round an open oculus",
        {"crown": {"height_m": 4.8, "radius_m": 1.7, "section": {"top_slope_deg": 0.0}}},
    ),
    (
        "4_trunk",
        "the crown comes down to the floor at the centre: the ribs gather into a trunk",
        {"crown": {"height_m": 0.0, "radius_m": 0.6, "section": {"top_slope_deg": -90.0}}},
    ),
    (
        "5_oval",
        "ten bays on an oval outline, 1.4 times as long as it is wide",
        {"layout": {"bays": 10, "bay_weights": None, "outline": {"radius_m": 5.5, "stretch": 1.4, "stretch_bearing_deg": 15.0}}},
    ),
    (
        "6_lobed_egg",
        "seven bays on an egg-shaped outline with four shallow lobes",
        {"layout": {"bays": 7, "bay_weights": None, "outline": {"radius_m": 6.1, "taper": 0.12, "lobes": 4, "lobe_depth": 0.05}}},
    ),
    (
        "7_long_hall",
        "the crown drawn out into a spine 6 m long: a hall with two straight sides and two round ends",
        {
            "crown": {"spine_m": [[-2.95, 0.1], [3.05, 0.1]]},
            "layout": {"bays": 10, "bay_weights": None, "outline": {"radius_m": 5.6, "first_pier_turn": 0.947}},  # an arch on the axis at each end
            "timber": {"lattice": {"ribs_per_family": 20}},
            "views": {  # a longer building: the cameras stand further back
                "exterior": {"location_m": [1.6, -28.0, 1.7]},
                "overhead": {"location_m": [15.0, -20.0, 17.5]},
                "plan": {"ortho_scale_m": 30.0},
                "elevation": {"ortho_scale_m": 24.0},
            },
        },
    ),
]


def _merge(into: dict, changes: dict) -> None:
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(into.get(key), dict):
            _merge(into[key], value)
        else:
            into[key] = copy.deepcopy(value)


def formed(design: dict, changes: dict, room_id: str | None = None) -> dict:
    """The design with a form's changes applied to one room (the first by default)."""
    from bower import topology

    new = copy.deepcopy(design)
    room = new["rooms"][0] if room_id is None else topology.get_room(new, room_id)
    for part in ("crown", "shape"):
        room[part].update(copy.deepcopy(changes.get(part, {})))
    if room["crown"].get("spine_m"):  # a crown drawn out into a line has its centre at the line's middle
        (ax, ay), (bx, by) = room["crown"]["spine_m"]
        room["crown"]["centre_m"] = [round((ax + bx) / 2.0, 6), round((ay + by) / 2.0, 6)]
    _merge(new["timber"], changes.get("timber", {}))
    for view in new.get("views", []):
        _merge(view, changes.get("views", {}).get(view["id"], {}))
    if "layout" in changes:  # the ring is laid out afresh, and checked, on the crown as it now is
        new, _ = topology.set_layout(new, room["id"], **changes["layout"])
    else:
        topology.validate(new)
    return new


def main(only=None, milled: bool = False, views=("exterior", "overhead")) -> dict:
    import bpy

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    for name in [m for m in sys.modules if m == "bower" or m.startswith("bower.")]:
        del sys.modules[name]
    from bower import topology
    from bower.blender_scene import build_design, render_views

    scene = bpy.context.scene
    base = topology.load(DESIGN)
    record = {"design": str(DESIGN), "forms": []}
    kept = {}
    if only and (REPO / "output" / "gate2_forms.json").exists():  # forms not rebuilt this time keep their record
        kept = {f.get("name", f["images"][0][len("form_") : -len("_exterior.png")]): f for f in json.loads((REPO / "output" / "gate2_forms.json").read_text(encoding="utf-8"))["forms"]}
    for name, description, changes in FORMS:
        if only and name not in only:
            if name in kept:
                record["forms"].append({"name": name, **kept[name]})
            continue
        design = formed(base, changes)
        if not milled:
            design["timber"].setdefault("joints", {})["cut_meshes"] = "none"  # a quick build: joints set out, not milled
        timber = build_design(scene, design)["rooms"][0]["timber"]
        images = render_views(scene, design, REPO / "views", f"form_{name}_", only=set(views))
        check = {}
        if milled:  # how the milled meshes came out: any left open, and how deeply any two still overlap
            found = timber.get("mesh_intersections_in_scene") or {}
            overlaps = sorted(found.get("laps_not_clean", []) + found.get("clashes", []), key=lambda pair: -pair[-1])
            check = {
                "milled": timber.get("milled"),
                "meshes_closed": timber.get("meshes_closed"),
                "laps_not_clean": len(found.get("laps_not_clean", [])),
                "clashes": len(found.get("clashes", [])),
                "deepest_overlaps_mm": overlaps[:8],
            }
        record["forms"].append(
            {
                "name": name,
                "form": description,
                "changes": changes,
                "bays": len(design["rooms"][0]["bays"]),
                "members": timber["members"],
                "families": timber["families"],
                "total_length_m": timber["total_length_m"],
                "joints": timber["joints"],
                "collisions_estimated": timber["collisions_estimated"],
                **({"milled_check": check} if milled else {}),
                "images": [Path(image).name for image in images],
            }
        )
    build_design(scene, base)  # leave the scene as design.json describes it
    (REPO / "output").mkdir(exist_ok=True)
    (REPO / "output" / "gate2_forms.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
