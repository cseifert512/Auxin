"""Gate 3: a second room joined to the first through one bay.

Grows a smaller room out of one bay of the room in design.json. The two rooms
share that bay's arch and its two piers; each keeps its own ring, crown, roof
and IDs. The two-room design is written to design/two_rooms.json, which
scripts/generate.py can rebuild on its own:

    runpy.run_path(r"<repo>/scripts/generate.py")["main"](design_path=r"<repo>/design/two_rooms.json")

Then the second room is resized, its crown is moved and a pier the rooms share
is moved, each on its own; the scene is rebuilt each time and the first room is
compared, member by member, with what it was. Last, the pair is built with
every joint milled and checked. design.json is not modified. The scene is left
as design/two_rooms.json describes it; scripts/generate.py puts it back to
design.json.

Outputs: design/two_rooms.json, views/gate3_*.png, output/gate3_rooms.json.

Run inside Blender:
    runpy.run_path(r"<repo>/scripts/gate3_rooms.py")["main"]()
"""
import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "design.json"
PAIR = REPO / "design" / "two_rooms.json"

# The second room: grown out of the first room's east bay, six bays, lower and lighter than the first.
SECOND_ROOM = {
    "bay": "R1.B3",
    "bays": 6,
    "shape": {"lantern_base_height_m": 4.5},
    "timber": {
        "lattice": {
            "ribs_per_family": 8,
            "tiers": [
                {"family": "rib", "phases": [0.0], "from": "top"},
                {"family": "fill", "phases": [0.5], "from": {"lantern": 0.22}},
                {"family": "fine", "phases": [0.25, 0.75], "from": {"radius_m": 2.7}, "gathers": False},
            ],
        },
        "arches": {"hoops_m": [0.5]},
    },
}

# Cameras for two rooms side by side, and for the way through between them.
VIEWS = [
    {"id": "plan", "projection": "ortho", "location_m": [3.7, -0.3, 30.0], "target_m": [3.7, -0.3, 0.0], "ortho_scale_m": 31.0},
    {"id": "overhead", "projection": "persp", "location_m": [15.0, -22.0, 17.0], "target_m": [3.9, -0.6, 2.4], "lens_mm": 35.0},
    {"id": "exterior", "projection": "persp", "location_m": [4.2, -28.0, 1.7], "target_m": [3.8, 0.0, 3.0], "lens_mm": 40.0},
    {"id": "through", "projection": "persp", "location_m": [-2.6, 0.9, 1.65], "target_m": [9.4, -2.2, 3.3], "lens_mm": 20.0},
    {"id": "back", "projection": "persp", "location_m": [11.4, -2.7, 1.65], "target_m": [0.0, 0.0, 3.8], "lens_mm": 18.0},
    {"id": "shared_pier", "projection": "persp", "location_m": [7.2, -10.2, 3.0], "target_m": [5.3, -3.6, 2.9], "lens_mm": 32.0},
]


def joined(design: dict, second: dict | None = None) -> dict:
    """The design with the second room joined on, and cameras that take in both rooms."""
    from bower import topology

    second = dict(second or SECOND_ROOM)
    new, _ = topology.add_room_from_bay(design, second.pop("bay"), **copy.deepcopy(second))
    new["views"] = copy.deepcopy(VIEWS)
    new["note"] = "Two rooms joined through one bay: made from design.json by scripts/gate3_rooms.py. Edit freely; scripts/generate.py rebuilds it."
    return new


def edits(pair: dict) -> list:
    """The edits that show the second room can change without the first being lost: name, description, edit."""
    from bower import topology

    second = pair["rooms"][1]
    (cx, cy), height = second["crown"]["centre_m"], second["crown"]["height_m"]
    radius, connection = second["layout"]["outline"]["radius_m"], second["layout"]["outline"]["through"]
    shared = topology.portals(pair)[topology.get_room(pair, second["id"])["bays"][0]["id"]][1]  # the first room's side of the portal
    pier = topology.get_pier(pair["rooms"][0], topology.get_bay(pair["rooms"][0], shared)["to"])
    px, py = pier["position_m"]
    return [
        ("1_resize", f"set_layout({second['id']}, outline radius {radius} -> 5.2 m): the second room made larger", lambda d: topology.set_layout(d, second["id"], outline={"radius_m": 5.2, "through": connection})),
        ("2_move_crown", f"set_crown({second['id']}): its crown moved 0.6 m and raised 0.5 m", lambda d: topology.set_crown(d, second["id"], centre_m=[round(cx + 0.5, 3), round(cy - 0.35, 3)], height_m=height + 0.5)),
        ("3_shared_pier", f"move_pier({pier['id']}): a pier the two rooms share moved 0.5 m", lambda d: topology.move_pier(d, pier["id"], [round(px + 0.35, 3), round(py + 0.35, 3)])),
    ]


def first_room(design: dict) -> dict:
    """Each member of the first room as its curve and its nodes, for comparing one build with another."""
    from bower.timber import build_design_timber

    group = build_design_timber(design)[0]
    first = group["rooms"][0]
    return {m.id: (tuple((a.co, a.handle_left, a.handle_right) for a in m.path.anchors), m.nodes) for m in group["members"] if group["room_of"][m.id] == first}


def compared(before: dict, after: dict) -> dict:
    return {
        "members_identical": sum(1 for k in after if k in before and after[k][0] == before[k][0]),
        "members_reshaped": sorted(k for k in after if k in before and after[k][0] != before[k][0]),
        "members_with_other_joints": sorted(k for k in after if k in before and after[k][0] == before[k][0] and after[k][1] != before[k][1]),
        "members_added": sorted(set(after) - set(before)),
        "members_removed": sorted(set(before) - set(after)),
    }


def main(milled: bool = True, only=None) -> dict:
    import bpy

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    for name in [m for m in sys.modules if m == "bower" or m.startswith("bower.")]:
        del sys.modules[name]
    from bower import topology
    from bower.blender_scene import build_design, render_views
    from bower.envelope import check_connections

    scene = bpy.context.scene
    base = topology.load(DESIGN)
    pair = joined(base)
    PAIR.parent.mkdir(exist_ok=True)
    topology.save(PAIR, pair)

    def summed(timber: dict) -> dict:
        found = timber.get("mesh_intersections_in_scene") or {}
        overlaps = sorted(found.get("laps_not_clean", []) + found.get("clashes", []), key=lambda p: -p[-1])
        return {
            "rooms": timber["rooms"],
            "members": timber["members"],
            "members_by_room": timber["members_by_room"],
            "total_length_m": timber["total_length_m"],
            "joints": timber["joints"],
            "collisions_estimated": timber["collisions_estimated"],
            "meshes_closed": timber["meshes_closed"],
            "milled": timber["milled"],
            **({"laps_not_clean": len(found.get("laps_not_clean", [])), "clashes": len(found.get("clashes", [])), "deepest_overlaps_mm": overlaps[:8]} if timber["milled"] else {}),
        }

    alone, together = first_room(base), first_room(pair)
    record = {
        "design": str(DESIGN),
        "pair": str(PAIR),
        "second_room": SECOND_ROOM,
        "connections": check_connections(pair),
        "first_room_once_joined": compared(alone, together),
        "edits": [],
    }
    for name, description, edit in edits(pair):
        if only and name not in only:
            continue
        edited, change = edit(pair)
        edited["timber"] = {**edited["timber"], "joints": {**edited["timber"].get("joints", {}), "cut_meshes": "none"}}  # a quick build: joints set out, not milled
        timber = build_design(scene, edited)["rooms"][0]["timber"]
        image = render_views(scene, edited, REPO / "views", f"gate3_edit_{name}_", only={"overhead"})[0]
        record["edits"].append({"edit": description, "change": change, "first_room": compared(together, first_room(edited)), "connections": check_connections(edited), "timber": summed(timber), "image": Path(image).name})

    # the second room taken away again: the first room is the room it was
    undone, change = topology.remove_room(pair, pair["rooms"][1]["id"])
    back = first_room(undone)
    record["second_room_removed"] = {"change": change, "first_room_as_it_was_alone": back == alone}

    # last, the pair itself, with every joint milled: this is what the scene is left as
    built = copy.deepcopy(pair)
    if not milled:
        built["timber"] = {**built["timber"], "joints": {**built["timber"].get("joints", {}), "cut_meshes": "none"}}
    report = build_design(scene, built)
    record["built"] = summed(report["rooms"][0]["timber"])
    record["images"] = [Path(image).name for image in render_views(scene, built, REPO / "views", "gate3_")]
    (REPO / "output").mkdir(exist_ok=True)
    (REPO / "output" / "gate3_rooms.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
