"""Set out the ground of the room in each configuration of the study, for the scene to draw and the drawing to quote.

    python set_out_ground.py            writes ground/<configuration>.json for every configuration in site.json. No Blender.

A configuration names a snapshot, a footing, where the climbers are rooted, the floor and how they are tended
(site.json, "configurations"). Three are set out:

    found       the room as the existing work has it. The footing is the ground draft's (bower/ground.py: a steel cap on
                screw piles under each pier). The climbers are where drawings-in-code's grown planting starts them: at the
                feet of the training lines. The two were made apart and do not agree.
    baseline    the same pier, corrected so that nothing stands on steel: bower/ground.py run as it is, with a root zone
                outside each arch leg, a feeder up the leg and a hand-over to the lines.
    proposal    the pier opened (the frozen study six-bay-radial-open-pier) and stood on a frame in place of a plate, with
                the climbers back at the feet of their own lines, now in open ground.

What comes from where:
    generated   members, feet, training lines (bower/timber.py, bower/lines.py on the snapshot's frozen design); in found
                and baseline also caps, piles, root zones, feeders and hand-overs (bower/ground.py, unchanged).
    carried     where the climbers stand and which taxon each is: drawings-in-code/scenes/<snapshot>/bower.json, planting.json.
    proposal    the frame footing of the proposal and its root zones: `frame_footing` below, authored for this study.
    measured    every quantity under "quantities", worked out here from that geometry. None is engineered, and none says
                anything about how a plant will grow.

Snapshots carry neither root zones nor training lines, so both are worked out again from the snapshot's design, and
nothing is written back to a release.
"""
from __future__ import annotations

import json
import math
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

SITE = json.loads((HERE / "site.json").read_text(encoding="utf-8"))
FOUND = "found: the existing work, as it stands"
GENERATED = "generated: the building model's own code on the snapshot's design"
PROPOSAL = "proposal: authored for this study"
CARRIED = "carried: from drawings-in-code's planting on this snapshot"
MEASURED = "measured: from this configuration's geometry, before the drawing is shown"


def _r(values, places: int = 3):
    return [round(float(v), places) for v in values]


_built: dict = {}


def built(snapshot: str) -> dict:
    """A snapshot's one room: its design, members, joints, training lines under the default settings, and feet."""
    if snapshot not in _built:
        design = T.load(REPO / "releases" / snapshot / "design.json")
        group = build_design_timber(design)[0]
        joints = find_joints(group["members"], design["timber"])[0]
        timber = {**design["timber"], "training_lines": design["timber"].get("training_lines") or {}}
        lines = training_lines(group["members"], timber, joints)
        planted = {**design, "timber": timber}
        _built[snapshot] = {"design": planted, "group": group, "joints": joints, "lines": lines, "at": G.feet_at_piers(planted, group)}
    return _built[snapshot]


def stations(snapshot: str) -> list:
    """Where the grown planting of drawings-in-code roots its climbers on this snapshot, and what each is."""
    scene = REPO / "drawings-in-code" / "scenes" / snapshot
    taxa = {p["stationId"]: p["taxonId"] for p in json.loads((scene / "planting.json").read_text(encoding="utf-8"))["plants"]}
    out = []
    for s in json.loads((scene / "bower.json").read_text(encoding="utf-8"))["stations"]:
        out.append({"id": s["id"], "pier": ".".join(s["id"].split(".")[1:3]), "position_m": _r(s["position"][:2]), "taxon": taxa.get(s["id"], ""), "member": s.get("note", "").split(" on ")[-1]})
    return out


def line_from(lines: list, member: str, at) -> dict | None:
    """The training line of a member, taken from the end nearest a place on the ground: its id and its points in that order."""
    best = None
    for line in lines:
        if line.member != member:
            continue
        for points in (list(line.points), list(reversed(line.points))):
            away = math.dist(points[0], at)
            if best is None or away < best[0]:
                best = (away, line.id, points)
    return None if best is None else {"line": best[1], "to_line_m": round(best[0], 3), "points_m": [_r(p, 4) for p in best[2]]}


def entrances(design: dict, at: dict) -> list:
    """The way through each bay: between its arch legs, and between the innermost legs of any kind that stand in its threshold."""
    room = design["rooms"][0]
    position = {p["id"]: tuple(p["position_m"]) for p in room["piers"]}
    out = []
    for bay in room["bays"]:
        a, b = position[bay["from"]], position[bay["to"]]
        span = math.dist(a, b)
        u = ((b[0] - a[0]) / span, (b[1] - a[1]) / span)
        arch, lo, hi = [0.0, span], (0.0, a), (span, b)
        for pier in (bay["from"], bay["to"]):
            for m, _, corners in at["feet"][pier]:
                for c in corners:
                    t = (c[0] - a[0]) * u[0] + (c[1] - a[1]) * u[1]
                    off = abs((c[0] - a[0]) * u[1] - (c[1] - a[1]) * u[0])
                    if off > 1.0 or not 0.0 <= t <= span:
                        continue  # not in this bay's threshold
                    if m.id.startswith(bay["id"] + ".arch"):
                        arch = [max(arch[0], t), arch[1]] if pier == bay["from"] else [arch[0], min(arch[1], t)]
                    if pier == bay["from"] and t > lo[0]:
                        lo = (t, c, m.id)
                    if pier == bay["to"] and t < hi[0]:
                        hi = (t, c, m.id)
        out.append({"bay": bay["id"], "between_arch_legs_m": round(arch[1] - arch[0], 2), "between_innermost_legs_m": round(hi[0] - lo[0], 2), "innermost_legs": [lo[2] if len(lo) > 2 else "", hi[2] if len(hi) > 2 else ""], "innermost_points_m": [_r(lo[1]), _r(hi[1])]})
    return out


def _area(plates: list, step: float = 0.01) -> float:
    """The plan area that a set of convex plates covers together."""
    xs, ys = [p[0] for plate in plates for p in plate], [p[1] for plate in plates for p in plate]
    count, x = 0, min(xs)
    while x < max(xs):
        y = min(ys)
        while y < max(ys):
            count += any(G._within(plate, (x + step / 2, y + step / 2)) > 0.0 for plate in plates)
            y += step
        x += step
    return count * step * step


def _bar(a, b, width: float) -> list:
    """A flat bar from one plan point to another, as a convex outline."""
    length = math.dist(a, b)
    n = (-(b[1] - a[1]) / length * width / 2.0, (b[0] - a[0]) / length * width / 2.0)
    return G._hull([(a[0] + n[0], a[1] + n[1]), (b[0] + n[0], b[1] + n[1]), (b[0] - n[0], b[1] - n[1]), (a[0] - n[0], a[1] - n[1])])


def frame_footing(pier_xy, feet: list, planted: list, cfg: dict, piles: dict) -> dict:
    """A proposal, authored here and not engineered: an opened pier on a frame instead of a plate.

    The open pier stands its six lattice legs apart on an arc, with the two arch legs at its middle, and the grown
    planting starts its climbers on that arc, in the gaps between the legs. So no steel runs along the arc. The two arch
    legs keep a small plate of their own on one pile. Two more piles stand inside the arc, the ground draft's least
    distance from the first and from each other, and the three are tied in a triangle. Each lattice leg stands on a
    finger that reaches in to that triangle. Everything is lifted clear of the soil, as the ground draft's cap is, so
    the ground between is open to rain and light. The widths are settings in site.json; the three checks are the ground
    draft's own rules for piles, and what fails is said.
    """
    centre = lambda corners: (sum(c[0] for c in corners) / len(corners), sum(c[1] for c in corners) / len(corners))  # noqa: E731
    hub = [corners for m, _, corners in feet if m.family == "arch"]
    arc = sorted((centre(corners) for m, _, corners in feet if m.family != "arch"), key=lambda c: math.atan2(c[1] - pier_xy[1], c[0] - pier_xy[0]))
    # the arc runs the short way round: start it after the widest gap between neighbours
    turn = [math.atan2(c[1] - pier_xy[1], c[0] - pier_xy[0]) for c in arc]
    gaps = [((turn[(i + 1) % len(arc)] - turn[i]) % (2 * math.pi), i) for i in range(len(arc))]
    first = (max(gaps)[1] + 1) % len(arc)
    arc = arc[first:] + arc[:first]
    hub_plate = G._grow(G._hull([c for corners in hub for c in corners]), cfg["hub_margin_m"])
    hub_at = centre(hub_plate)
    a0 = math.atan2(arc[0][1] - hub_at[1], arc[0][0] - hub_at[0])
    a1 = a0 + (math.atan2(arc[-1][1] - hub_at[1], arc[-1][0] - hub_at[0]) - a0) % (2 * math.pi)
    side = piles["spacing_m"]  # the three piles stand in a triangle of the least spacing the ground draft allows
    pile_at = [hub_at] + [(hub_at[0] + side * math.cos((a0 + a1) / 2.0 + k * math.pi / 6.0), hub_at[1] + side * math.sin((a0 + a1) / 2.0 + k * math.pi / 6.0)) for k in (-1, 1)]
    _, a, b = pile_at

    def onto_tie(c):  # the nearest place on the tie between the two inner piles
        t = max(0.0, min(1.0, ((c[0] - a[0]) * (b[0] - a[0]) + (c[1] - a[1]) * (b[1] - a[1])) / math.dist(a, b) ** 2))
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    plates = [hub_plate, _bar(hub_at, a, cfg["tie_width_m"]), _bar(hub_at, b, cfg["tie_width_m"]), _bar(a, b, cfg["tie_width_m"])]
    plates += [G._grow(G._hull([q]), cfg["pile_head_m"] / 2.0, 12) for q in (a, b)]  # a head plate on each inner pile
    plates += [_bar(c, onto_tie(c), cfg["finger_width_m"]) for c in arc]  # a finger under each lattice leg
    plates += [G._grow(G._hull([c]), cfg["finger_width_m"] / 2.0 + 0.03, 12) for c in arc]  # and a shoe where the leg stands
    notes = []
    gap = min(math.dist(p, q) for i, p in enumerate(pile_at) for q in pile_at[i + 1 :])
    if gap < piles["spacing_m"] - 1e-6:
        notes.append(f"two piles stand {gap:.2f} m apart, under the {piles['spacing_m']} m the ground draft asks")
    reach = max(min(math.dist(centre(corners), q) for q in pile_at) for _, _, corners in feet)
    if reach > piles["reach_m"]:
        notes.append(f"a foot stands {reach:.2f} m from the nearest pile, over the {piles['reach_m']} m the ground draft allows")
    clear = min((math.dist(p["position_m"], q) for p in planted for q in pile_at), default=9.0)
    if clear < piles["plant_clear_m"]:
        notes.append(f"a pile stands {clear:.2f} m from a climber, under the {piles['plant_clear_m']} m the ground draft asks")
    hull = G._hull([c for _, _, corners in feet for c in corners] + pile_at)
    return {
        "kind": "frame",
        "plates_m": [[_r(p) for p in plate] for plate in plates],
        "steel_area_m2": round(_area(plates), 2),
        "hull_area_m2": round(G._area(hull), 2),
        "cap_depth_m": piles["cap_depth_m"],
        "piles_m": [_r(p) for p in pile_at],
        "pile_spacing_m": round(gap, 2),
        "furthest_foot_from_a_pile_m": round(reach, 2),
        "nearest_pile_to_a_climber_m": round(clear, 2),
        "review": "; ".join(notes),
    }


def set_out(name: str, cfg: dict) -> dict:
    b = built(cfg["snapshot"])
    design, group, joints, lines, at = b["design"], b["group"], b["joints"], b["lines"], b["at"]
    floor = design["rooms"][0]["floor_z_m"]
    piers = [p["id"] for p in design["rooms"][0]["piers"]]
    zones = [zone for pier in piers for zone in G.beside_pier(design, group, pier)]
    drafted = G.lay({**design, "ground": {"root_zones": zones}}, group, joints, lines)  # the ground draft, unchanged, on this snapshot
    pile_cfg = G.settings({**design, "ground": {}})["footings"]["piles"]
    grown = stations(cfg["snapshot"])
    out = {
        "note": "Written by set_out_ground.py. Generated, carried and measured as its header says; nothing here is engineered, and sizes are provisional.",
        "configuration": name,
        "label": cfg["label"],
        "what": cfg["what"],
        "snapshot": cfg["snapshot"],
        "floor_z_m": floor,
        "piers": {pid: _r(p) for pid, p in at["piers"].items()},
        "feet": {pid: [{"member": m.id, "family": m.family, "corners_m": [_r(c) for c in corners]} for m, _, corners in feet] for pid, feet in at["feet"].items()},
        "piles": {k: pile_cfg[k] for k in ("shaft_m", "helix_m", "length_m", "spacing_m", "reach_m", "plant_clear_m", "feet_above_soil_m", "cap_depth_m")},
        "training_lines": [{"id": line.id, "member": line.member, "length_m": round(line.length_m, 2), "points_m": [_r(p, 4) for p in line.points]} for line in lines],
        "cable_diameter_m": 0.004,
        "entrances": entrances(design, at),
        "root_zones": [],
        "feeders": [],
        "handovers": [],
        "plants": [],
    }
    soil_level = floor - pile_cfg["feet_above_soil_m"]

    if cfg["footing"] == "cap":
        out["footings"] = {pid: {"kind": "cap", "plates_m": [[_r(p) for p in f.outline]], "cap_outline_m": [_r(p) for p in f.outline], "steel_area_m2": f.area_m2, "cap_area_m2": f.area_m2, "hull_area_m2": f.area_m2, "cap_depth_m": f.depth_m, "piles_m": [_r(p) for p in f.piles], "review": f.review} for pid, f in drafted["footings"].items()}
        out["footing_status"] = GENERATED
    if cfg["planting"] == "root-zones-outside":
        out["root_zones"] = [{"id": z.id, "pier": z.pier, "position_m": _r(z.position), "radius_m": z.radius_m, "depth_m": z.depth_m, "soil_below_feet_m": z.top_m, "soil_m3": z.soil_m3, "taken_by_footing": z.taken, "under_steel": z.covered, "feeder_on": z.feeder, "to_feeder_m": z.to_feeder_m, "review": z.review} for z in drafted["root_zones"]]
        out["root_zone_status"] = GENERATED
        out["feeders"] = [{"id": line.id, "member": line.member, "length_m": round(line.length_m, 2), "points_m": [_r(p, 4) for p in line.points]} for line in drafted["feeders"]]
        out["handovers"] = [{"line": h.line, "feeder": h.feeder, "pier": h.pier, "tie_m": h.gap_m, "start_m": _r(h.start, 4), "end_m": _r(h.end, 4), "height_m": round(h.end[2] - floor, 2), "line_below_m": h.below_m} for h in drafted["handovers"]]
        # one climber to a root zone: the two taxa the grown planting sends over the roof from that pier, one each
        over_roof = {}
        for s in grown:
            if ".fill." in s["member"]:
                over_roof.setdefault(s["pier"], []).append(s["taxon"])
        feeders = {f["id"]: f for f in out["feeders"]}
        for pier in piers:
            for k, z in enumerate(sorted((z for z in out["root_zones"] if z["pier"] == pier), key=lambda z: z["id"])):
                feeder = feeders.get(z["feeder_on"] + ".feeder")
                reached = [h for h in out["handovers"] if h["feeder"].startswith(z["feeder_on"])]
                out["plants"].append({"id": z["id"].replace(".root.", ".climber."), "pier": pier, "taxon": over_roof.get(pier, [""])[k % max(1, len(over_roof.get(pier, [])))], "root_m": z["position_m"], "root_level_m": soil_level, "rooted_in": z["id"], "on_steel": False, "climbs": feeder["id"] if feeder else "", "route_m": feeder["points_m"] if feeder else [], "meets_its_lines_at_m": [min(h["height_m"] for h in reached), max(h["height_m"] for h in reached)] if reached else None})
        out["planting_status"] = "the root zones are " + GENERATED + "; one climber to a zone is this study's reading of it"
        out["report"] = drafted["report"]
        out["stations_of_the_grown_planting"] = []
        for s in grown:
            cap = drafted["footings"][s["pier"]]
            nearest = min(math.dist(z.position, s["position_m"]) for z in drafted["root_zones"])
            out["stations_of_the_grown_planting"].append({**s, "inside_cap_m": round(G._within(list(cap.outline), s["position_m"]), 3), "on_the_cap": G._within(list(cap.outline), s["position_m"]) > 0.0, "to_nearest_root_zone_m": round(nearest, 3)})

    if cfg["footing"] == "frame":
        out["footings"] = {pid: frame_footing(at["piers"][pid], at["feet"][pid], [s for s in grown if s["pier"] == pid], cfg["frame"], pile_cfg) for pid in piers}
        out["footing_status"] = PROPOSAL

    if cfg["planting"] == "at-the-lines":
        plates = {pid: [[tuple(p) for p in plate] for plate in f["plates_m"]] for pid, f in out["footings"].items()}
        for s in grown:
            # A climber stands on steel when its whole root ball does: no open ground anywhere under a disc of that width.
            ball = SITE["planting_at_installation"]["root_ball_m"] / 2.0
            under = [(s["position_m"][0] + ball * f * math.cos(t * math.pi / 8.0), s["position_m"][1] + ball * f * math.sin(t * math.pi / 8.0)) for f in (0.0, 0.5, 1.0) for t in range(16)]
            covered = sum(any(G._within(plate, q) > 0.0 for plate in plates[s["pier"]]) for q in under) / len(under)
            on_steel = covered > 0.999
            climbs = line_from(lines, s["member"], (*s["position_m"], floor))
            out["plants"].append({"id": s["id"].replace("bed.", "climber."), "pier": s["pier"], "taxon": s["taxon"], "root_m": s["position_m"], "root_level_m": floor if on_steel else soil_level, "rooted_in": "", "on_steel": on_steel, "root_ball_on_steel": round(covered, 2), "climbs": climbs["line"] if climbs else "", "to_line_m": climbs["to_line_m"] if climbs else None, "route_m": climbs["points_m"] if climbs else [], "meets_its_lines_at_m": [round(climbs["points_m"][0][2] - floor, 2)] * 2 if climbs else None})
        out["planting_status"] = CARRIED
        if cfg["footing"] == "frame":
            # a root zone for each climber, where it stands: the ground draft's own size of zone, and its own count of the soil
            default = dict(G.ZONE)
            rz = [{"id": p["id"].replace("climber.", "root."), "position_m": p["root_m"], **default} for p in out["plants"]]
            pseudo = {}  # each plate of a frame, to the ground draft's soil count, is a cap that covers ground; the piles go with the first
            for pid, f in out["footings"].items():
                for i, plate in enumerate(f["plates_m"]):
                    pseudo[f"{pid}.{i}"] = G.Footing(pid, "piles", tuple(tuple(p) for p in plate), 0.0, 0.0, f["cap_depth_m"], (), (), tuple(tuple(p) for p in f["piles_m"]) if i == 0 else (), "")
            soil = G._soil({"root_zones": rz, "footings": {"piles": pile_cfg}}, pseudo)
            for p, z in zip(out["plants"], rz):
                m3, taken, covered = soil[z["id"]]
                p["rooted_in"] = z["id"]
                out["root_zones"].append({"id": z["id"], "pier": p["pier"], "position_m": z["position_m"], "radius_m": z["radius_m"], "depth_m": z["depth_m"], "soil_below_feet_m": pile_cfg["feet_above_soil_m"], "soil_m3": round(m3, 3), "taken_by_footing": round(taken, 3), "under_steel": round(covered, 3), "feeder_on": "", "to_feeder_m": None, "review": ""})
            out["root_zone_status"] = PROPOSAL + " (a zone of the ground draft's default size at each place the grown planting starts a climber; neighbours share what overlaps)"

    # what the drawing quotes: each a number or a few words, with where it comes from
    plants, zones_out = out["plants"], out["root_zones"]
    in_soil = sum(1 for p in plants if not p["on_steel"])
    meets = [v for p in plants if p["meets_its_lines_at_m"] for v in p["meets_its_lines_at_m"]]
    steel = sorted({f["steel_area_m2"] for f in out["footings"].values()})
    hull = sorted({f["hull_area_m2"] for f in out["footings"].values()})
    soil_each = sorted({z["soil_m3"] for z in zones_out})
    way = out["entrances"][0]
    quantities = {
        "climbers": {"value": len(plants), "unit": "", "says": f"{len(plants)} climbers", "from": CARRIED if cfg["planting"] == "at-the-lines" else PROPOSAL},
        "climbers_in_soil": {"value": in_soil, "of": len(plants), "says": f"{in_soil} of {len(plants)} rooted in soil", "from": MEASURED},
        "meets_its_lines_m": {"value": [min(meets), max(meets)] if meets else None, "unit": "m above the floor", "says": ("at its foot" if max(meets) < 0.5 else f"{min(meets)} to {max(meets)} m up") if meets else "", "from": MEASURED},
        "cable_on_the_arches_m": {"value": round(sum(f["length_m"] for f in out["feeders"]), 1), "unit": "m", "says": f"{round(sum(f['length_m'] for f in out['feeders']))} m of cable on the arch legs" if out["feeders"] else "no cable on the arch legs", "from": MEASURED},
        "steel_over_the_ground_m2": {"value": steel, "within_m2": hull, "unit": "m2 at each pier", "says": (f"{round(steel[0], 2)} m2 of plate" if cfg["footing"] == "cap" else f"{steel[0]} m2 of bars in {hull[0]} m2 of open ground"), "from": MEASURED},
        "soil_per_climber_m3": {"value": [soil_each[0], soil_each[-1]] if soil_each else 0.0, "unit": "m3", "says": (f"{soil_each[0]} m3 each" if soil_each and soil_each[0] == soil_each[-1] else f"{soil_each[0]} to {soil_each[-1]} m3 each") if soil_each else "none: they stand on steel", "from": MEASURED},
        "soil_all_m3": {"value": round(sum(z["soil_m3"] for z in zones_out), 1), "unit": "m3", "says": f"{round(sum(z['soil_m3'] for z in zones_out), 1)} m3 kept in all", "from": MEASURED},
        "way_in_m": {"value": way["between_innermost_legs_m"], "between_arch_legs_m": way["between_arch_legs_m"], "path_m": SITE["paths"]["width_m"], "unit": "m", "says": f"{way['between_innermost_legs_m']} m between the legs", "from": MEASURED},
        "piles": {"value": sum(len(f["piles_m"]) for f in out["footings"].values()), "unit": "", "says": f"{sum(len(f['piles_m']) for f in out['footings'].values())} screw piles", "from": MEASURED},
        "training_line_m": {"value": round(sum(line.length_m for line in lines), 1), "unit": "m", "says": f"{round(sum(line.length_m for line in lines))} m of training line", "from": MEASURED},
    }
    if cfg["planting"] == "root-zones-outside":
        below = drafted["report"]["training_line_below_handovers_m"]
        quantities["line_out_of_reach_m"] = {"value": below, "of": quantities["training_line_m"]["value"], "unit": "m", "says": f"{round(below)} m of line below the hand-overs", "from": MEASURED}
    shape = cfg["floor"]
    area = 1.5 * math.sqrt(3) * shape["corner_radius_m"] ** 2 if shape["shape"] == "hexagon" else math.pi * shape["radius_m"] ** 2
    quantities["floor_m2"] = {"value": round(area), "unit": "m2", "says": f"{round(area)} m2 of floor", "from": PROPOSAL}
    quantities["tended"] = {"value": cfg["care"] if name != "found" else None, "says": "not set out" if name == "found" else {"outside": "from a pad outside, on steps", "from-the-floor": "from the floor, standing"}[cfg["care"]], "from": PROPOSAL}
    out["quantities"] = quantities
    return out


def main() -> None:
    folder = HERE / "ground"
    folder.mkdir(exist_ok=True)
    for name, cfg in SITE["configurations"].items():
        out = set_out(name, cfg)
        (folder / f"{name}.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        q = out["quantities"]
        print(f"{name} ({out['snapshot']}): " + "; ".join(q[k]["says"] for k in ("climbers_in_soil", "meets_its_lines_m", "cable_on_the_arches_m", "steel_over_the_ground_m2", "soil_per_climber_m3", "way_in_m", "piles", "floor_m2", "tended")))
        notes = sorted({f["review"] for f in out["footings"].values() if f["review"]})
        if notes:
            print("   footings to review:", notes)


if __name__ == "__main__":
    main()
