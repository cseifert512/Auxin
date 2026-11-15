"""Set out the ground of the six-bay room with the building model's own code, for the study to draw.

    python set_out_ground.py            writes ground.json beside this file. No Blender needed.

`bower/ground.py` was drafted at one pier of the eight-bay design. Here it is run, unchanged, on the
frozen design of the snapshot the study links (releases/<snapshot>/design.json): a root zone outside
each arch leg of every pier (`ground.beside_pier`), footings on screw piles, the feeders up the arch
legs and the hand-overs to the training lines. Snapshots carry neither root zones nor training
lines, so both are worked out again here from the snapshot's design, and nothing is written back.

Two things are added to what that code reports, both measured from the same geometry:
    stations    where the drawings' grown planting roots its plants (drawings-in-code/scenes/<snapshot>/
                bower.json and planting.json), each tested against the cap of its pier's footing
    open_pier   the way through an entrance bay in releases/six-bay-radial-open-pier, for comparison

Everything in ground.json is generated or measured. Nothing in it is engineered: see bower/ground.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLENDER = HERE.parents[1]  # bower-blender
REPO = BLENDER.parent
sys.path.insert(0, str(BLENDER))

from bower import ground as G  # noqa: E402
from bower import topology as T  # noqa: E402
from bower.joints import find_joints  # noqa: E402
from bower.lines import training_lines  # noqa: E402
from bower.timber import build_design_timber  # noqa: E402

SNAPSHOT = json.loads((HERE / "site.json").read_text(encoding="utf-8"))["baseline"]["snapshot"]


def _r(values, places: int = 3):
    return [round(float(v), places) for v in values]


def lay(design: dict, zones=None) -> tuple:
    """A design's one room with its joints, its training lines under the default settings, and its ground."""
    group = build_design_timber(design)[0]
    joints = find_joints(group["members"], design["timber"])[0]
    timber = {**design["timber"], "training_lines": design["timber"].get("training_lines") or {}}
    lines = training_lines(group["members"], timber, joints)
    planted = {**design, "timber": timber}
    if zones is None:
        zones = [zone for room in design["rooms"] for pier in room["piers"] for zone in G.beside_pier(planted, group, pier["id"])]
    planted["ground"] = {"root_zones": zones}
    return group, lines, G.lay(planted, group, joints, lines), planted


def main() -> None:
    design = T.load(REPO / "releases" / SNAPSHOT / "design.json")
    group, lines, laid, planted = lay(design)
    cfg = G.settings(planted)
    at = G.feet_at_piers(planted, group)
    floor = design["rooms"][0]["floor_z_m"]

    # the plants the drawings grow, carried here: which taxon the planting puts at each station, and where that station is
    scene = REPO / "drawings-in-code" / "scenes" / SNAPSHOT
    stations, taxa = [], {}
    if (scene / "bower.json").exists():
        planting = json.loads((scene / "planting.json").read_text(encoding="utf-8"))
        taxa = {p["stationId"]: p["taxonId"] for p in planting["plants"]}
        for s in json.loads((scene / "bower.json").read_text(encoding="utf-8"))["stations"]:
            pier = ".".join(s["id"].split(".")[1:3])
            cap = laid["footings"][pier]
            inside = G._within(list(cap.outline), s["position"][:2])
            nearest = min(laid["root_zones"], key=lambda z: (z.position[0] - s["position"][0]) ** 2 + (z.position[1] - s["position"][1]) ** 2)
            stations.append({"id": s["id"], "pier": pier, "position_m": _r(s["position"][:2]), "taxon": taxa.get(s["id"], ""), "note": s.get("note", ""), "inside_cap_m": round(inside, 3), "on_the_cap": inside > 0.0, "to_nearest_root_zone_m": round(((nearest.position[0] - s["position"][0]) ** 2 + (nearest.position[1] - s["position"][1]) ** 2) ** 0.5, 3)})

    # each root zone is given the two taxa the drawings' planting sends over the roof from its pier (the stations on the lattice legs), one each
    over_roof = {}
    for s in stations:
        if ".fill." in s["note"]:
            over_roof.setdefault(s["pier"], []).append(s["taxon"])
    zone_plant = {}
    for pier, names in over_roof.items():
        for k, zone in enumerate(sorted((z for z in laid["root_zones"] if z.pier == pier), key=lambda z: z.id)):
            zone_plant[zone.id] = names[k % len(names)] if names else ""

    piles = cfg["footings"]["piles"]
    out = {
        "note": "Written by set_out_ground.py: bower/ground.py and bower/lines.py run on the snapshot's frozen design. Generated and measured, not engineered; sizes are the provisional defaults of that code.",
        "snapshot": SNAPSHOT,
        "floor_z_m": floor,
        "piers": {pid: _r(p) for pid, p in at["piers"].items()},
        "feet": {pid: [{"member": m.id, "family": m.family, "corners_m": [_r(c) for c in corners]} for m, _, corners in feet] for pid, feet in at["feet"].items()},
        "root_zones": [{"id": z.id, "pier": z.pier, "position_m": _r(z.position), "radius_m": z.radius_m, "depth_m": z.depth_m, "soil_below_feet_m": z.top_m, "soil_m3": z.soil_m3, "taken_by_footing": z.taken, "under_a_cap": z.covered, "feeder_on": z.feeder, "to_feeder_m": z.to_feeder_m, "taxon_from_drawings": zone_plant.get(z.id, ""), "review": z.review} for z in laid["root_zones"]],
        "footings": {pid: {"kind": f.kind, "cap_outline_m": [_r(p) for p in f.outline], "cap_area_m2": f.area_m2, "cap_depth_m": f.depth_m, "piles_m": [_r(p) for p in f.piles], "feet": list(f.feet), "review": f.review} for pid, f in laid["footings"].items()},
        "piles": {k: piles[k] for k in ("shaft_m", "helix_m", "length_m", "spacing_m", "feet_above_soil_m", "cap_depth_m")},
        "training_lines": [{"id": line.id, "member": line.member, "length_m": round(line.length_m, 2), "points_m": [_r(p, 4) for p in line.points]} for line in lines],
        "feeders": [{"id": line.id, "member": line.member, "length_m": round(line.length_m, 2), "points_m": [_r(p, 4) for p in line.points]} for line in laid["feeders"]],
        "cable_diameter_m": 0.004,
        "handovers": [{"line": h.line, "feeder": h.feeder, "pier": h.pier, "tie_m": h.gap_m, "start_m": _r(h.start, 4), "end_m": _r(h.end, 4), "height_m": round(h.end[2] - floor, 2), "line_below_m": h.below_m} for h in laid["handovers"]],
        "entrances": laid["entrances"],
        "report": laid["report"],
        "stations_of_the_grown_planting": stations,
    }

    other = REPO / "releases" / "six-bay-radial-open-pier" / "design.json"
    if other.exists():
        _, _, opened, _ = lay(T.load(other))
        out["open_pier"] = {"snapshot": "six-bay-radial-open-pier", "entrances": opened["entrances"], "handover_height_m": opened["report"]["handover_height_m"], "piles_at_each_pier": opened["report"]["piles_at_each_pier"], "footing_area_m2": sorted({tuple(v) for v in opened["report"]["footing_area_m2"].values()}), "to_review": opened["report"]["to_review"]}

    (HERE / "ground.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    on_cap = sum(s["on_the_cap"] for s in stations)
    print(f"{SNAPSHOT}: {len(out['root_zones'])} root zones, {laid['report']['piles']} piles, {len(lines)} training lines, {len(out['feeders'])} feeders, {len(out['handovers'])} hand-overs {laid['report']['handover_height_m']} m up")
    print(f"entrances: {out['entrances'][0]}")
    print(f"stations of the grown planting on a pile cap: {on_cap} of {len(stations)}")
    if "open_pier" in out:
        print(f"open pier: {out['open_pier']['entrances'][0]}, hand-overs {out['open_pier']['handover_height_m']}, piles {out['open_pier']['piles_at_each_pier']}, caps {out['open_pier']['footing_area_m2']}")
        print(f"open pier to review: {out['open_pier']['to_review']}")


if __name__ == "__main__":
    main()
