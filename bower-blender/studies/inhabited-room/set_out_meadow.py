"""Set out the pier designed for the plant, on the designed site: ground/meadow.json.

Called by set_out_ground.py for a configuration whose footing is "sole". What it writes, and where each part comes from:

    generated   the members' feet and each pier's own level, the training lines (trunk cables) with their wider gap at
                the foot, the joints: the building model's own code on the snapshot's design
    carried     which climber goes with which leg: drawings-in-code's planting on the level open-pier room
    proposal    the steel sole and its piles, where each climber is planted, the mesh round the joints: authored here,
                not engineered, every size provisional
    measured    the quantities, from this geometry and from the level room it is compared with

Pure Python (no bpy).
"""
from __future__ import annotations

import copy
import math

from bower import ground as G
from bower.joints import find_joints
from bower.timber import build_design_timber
from bower.floor import Floor
from bower.lines import on_floor

import set_out_ground as S

LATTICE_JOINTS = ("cross_lap", "housing", "base", "pier_mitre", "alongside", "scarf", "mitre", "crown_seat", "paired_heads")


def _centre(corners):
    return (sum(c[0] for c in corners) / len(corners), sum(c[1] for c in corners) / len(corners))


def sole_footing(pier_xy, feet: list, cfg: dict, piles: dict) -> dict:
    """A proposal, authored here and not engineered: a steel sole under an opened pier, buried under its feet.

    The two arch legs stand on a small plate at the pier. The six lattice legs stand on one curved beam, on the arc
    they already stand on. Two ties run from the plate to the beam's ends, clear of the places the climbers are
    planted, so the whole is one closed shape. It stands on three screw piles: one under the plate, two under the beam,
    set a little outside it so that they keep away from the climbers. The feet run a little way into the soil; the sole
    lies under the bed, and a slender stub comes up from it to a shoe under each foot, so none of it is seen and the
    bed's soil is whole but for the stubs. The checks are the ground draft's own three rules for piles; what fails is
    said.
    """
    hub = [corners for m, _, corners in feet if m.family == "arch"]
    legs = sorted((_centre(corners) for m, _, corners in feet if m.family != "arch"), key=lambda c: math.atan2(c[1] - pier_xy[1], c[0] - pier_xy[0]))
    turn = [math.atan2(c[1] - pier_xy[1], c[0] - pier_xy[0]) for c in legs]
    gaps = [((turn[(i + 1) % len(legs)] - turn[i]) % (2 * math.pi), i) for i in range(len(legs))]
    first = (max(gaps)[1] + 1) % len(legs)  # the arc runs the short way round: it starts after the widest gap
    legs = legs[first:] + legs[:first]
    radius = sum(math.dist(c, pier_xy) for c in legs) / len(legs)
    a0 = math.atan2(legs[0][1] - pier_xy[1], legs[0][0] - pier_xy[0])
    a1 = a0 + (math.atan2(legs[-1][1] - pier_xy[1], legs[-1][0] - pier_xy[0]) - a0) % (2 * math.pi)
    over = 0.14 / radius  # the beam runs on a little past its end legs
    on_arc = lambda a, r=radius: (pier_xy[0] + r * math.cos(a), pier_xy[1] + r * math.sin(a))  # noqa: E731
    steps = 16
    spine = [on_arc(a0 - over + (a1 - a0 + 2 * over) * k / steps) for k in range(steps + 1)]
    hub_plate = G._grow(G._hull([c for corners in hub for c in corners]), cfg["hub_margin_m"])
    hub_at = _centre(hub_plate)
    mid, swing = (a0 + a1) / 2.0, math.radians(cfg["pile_at_deg"])
    pile_at = [hub_at, on_arc(mid - swing, radius + cfg["pile_out_m"]), on_arc(mid + swing, radius + cfg["pile_out_m"])]
    plates = [hub_plate]
    plates += [S._bar(p, q, cfg["beam_width_m"]) for p, q in zip(spine, spine[1:])]
    plates += [S._bar(hub_at, spine[0], cfg["tie_width_m"]), S._bar(hub_at, spine[-1], cfg["tie_width_m"])]
    plates += [G._grow(G._hull([q]), cfg["pile_head_m"] / 2.0, 12) for q in pile_at[1:]]  # a head plate on each pile under the beam
    return {
        "kind": "sole",
        "plates_m": [[S._r(p) for p in plate] for plate in plates],
        "beam_m": [S._r(p) for p in spine],
        "hub_m": S._r(hub_at),
        "arc_radius_m": round(radius, 3),
        "steel_area_m2": round(S._area(plates), 2),
        "hull_area_m2": round(G._area(G._hull([c for _, _, corners in feet for c in corners] + pile_at)), 2),
        "cap_depth_m": piles["cap_depth_m"],
        "piles_m": [S._r(p) for p in pile_at],
        "stubs_m": [{"member": m.id, "at": S._r(_centre(corners)), "size_m": cfg["arch_stub_m"] if m.family == "arch" else cfg["stub_m"]} for m, _, corners in feet],
        "shoes_m": [[S._r(c) for c in corners] for _, _, corners in feet],
        "_feet": [_centre(corners) for _, _, corners in feet],
    }


def _check(footing: dict, planted: list, piles: dict) -> None:
    """The ground draft's three rules for piles, on a sole and the climbers planted at it."""
    pile_at = [tuple(p) for p in footing["piles_m"]]
    notes = []
    gap = min(math.dist(p, q) for i, p in enumerate(pile_at) for q in pile_at[i + 1 :])
    if gap < piles["spacing_m"] - 1e-6:
        notes.append(f"two piles stand {gap:.2f} m apart, under the {piles['spacing_m']} m the ground draft asks")
    reach = max(min(math.dist(c, q) for q in pile_at) for c in footing.pop("_feet"))
    if reach > piles["reach_m"] + 1e-6:
        notes.append(f"a foot stands {reach:.2f} m from the nearest pile, over the {piles['reach_m']} m the ground draft allows")
    clear = min((math.dist(p["root_m"], q) for p in planted for q in pile_at), default=9.0)
    if clear < piles["plant_clear_m"] - 1e-6:
        notes.append(f"a pile stands {clear:.2f} m from a climber, under the {piles['plant_clear_m']} m the ground draft asks")
    footing.update({"pile_spacing_m": round(gap, 2), "furthest_foot_from_a_pile_m": round(reach, 2), "nearest_pile_to_a_climber_m": round(clear, 2), "review": "; ".join(notes)})


def _sleeves(members: list, joints: list, floor: Floor, cfg: dict) -> tuple[list, dict]:
    """A mesh sleeve round each member at each joint within reach of the ground: where, which way it lies, how big."""
    by_id = {m.id: m for m in members}
    sampled = {}
    out, kinds = [], {}
    for j in joints:
        kinds[j.kind] = kinds.get(j.kind, 0) + 1
        at = tuple(j.at_m)
        if at[2] - floor.at(at) > cfg["below_m"]:
            continue
        for mid in sorted({m for m in j.members if m}):
            m = by_id.get(mid)
            if m is None:
                continue
            if mid not in sampled:
                sampled[mid] = m.path.stations(0.05)
            st = min(sampled[mid], key=lambda s: math.dist(s.point, at))
            if math.dist(st.point, at) > 0.45:
                continue
            out.append({"joint": j.id, "kind": j.kind, "member": mid, "at_m": S._r(st.point, 4), "along": S._r(st.tangent, 4), "across": S._r(st.width_axis, 4), "up": S._r(st.depth_axis, 4), "size_m": [round(m.width + 2 * cfg["proud_m"], 3), round(m.depth + 2 * cfg["proud_m"], 3), cfg["length_m"]]})
    return out, kinds


def set_out(name: str, cfg: dict, site: dict) -> dict:
    b = S.built(cfg["snapshot"])
    design, group, joints, lines, at = b["design"], b["group"], b["joints"], b["lines"], b["at"]
    members = group["members"]
    by_id = {m.id: m for m in members}
    floor = Floor(members)
    room = design["rooms"][0]
    piers = [p["id"] for p in room["piers"]]
    pile_cfg = G.settings({**design, "ground": {}})["footings"]["piles"]
    level = {pid: round(floor.at(at["piers"][pid]), 4) for pid in piers}
    line_cfg = design["timber"]["training_lines"]

    # the site and the building must agree: each pier's feet are feet_below_soil_m under the site's ground there
    g = site["ground"]
    gx, gy = -g["fall"] * math.cos(math.radians(g["fall_towards_deg"])), -g["fall"] * math.sin(math.radians(g["fall_towards_deg"]))
    top = max(level, key=level.get)
    sunk = g["feet_below_soil_m"]  # the timber runs this far into the soil, and the sole under it is buried
    z0 = level[top] + sunk - (gx * at["piers"][top][0] + gy * at["piers"][top][1])
    soil = {pid: round(z0 + gx * at["piers"][pid][0] + gy * at["piers"][pid][1], 4) for pid in piers}
    apart = max(abs(level[pid] + sunk - soil[pid]) for pid in piers)
    if apart > 0.004:
        raise SystemExit(f"the design's foot levels and the site's ground are {apart:.3f} m apart at a pier: change one to match the other")

    out = {
        "note": "Written by set_out_meadow.py. Generated, carried, proposed and measured as its header says; nothing here is engineered, and sizes are provisional.",
        "configuration": name,
        "label": cfg["label"],
        "what": cfg["what"],
        "snapshot": cfg["snapshot"],
        "floor_z_m": max(level.values()),
        "pier_levels_m": level,
        "soil_at_pier_m": soil,
        "piers": {pid: S._r(p) for pid, p in at["piers"].items()},
        "feet": {pid: [{"member": m.id, "family": m.family, "corners_m": [S._r(c) for c in corners]} for m, _, corners in feet] for pid, feet in at["feet"].items()},
        "piles": {k: pile_cfg[k] for k in ("shaft_m", "helix_m", "length_m", "spacing_m", "reach_m", "plant_clear_m", "feet_above_soil_m", "cap_depth_m")},
        "training_lines": [{"id": line.id, "member": line.member, "length_m": round(line.length_m, 2), "points_m": [S._r(p, 4) for p in line.points], "standoffs_m": [[S._r(s.foot, 4), S._r(s.head, 4)] for s in line.standoffs], "review": line.review} for line in lines],
        "cable": {"diameter_m": 0.004, "gap_m": 0.075, "foot_gap_m": line_cfg.get("foot_gap_m"), "foot_taper_m": line_cfg.get("foot_taper_m"), "status": S.GENERATED + " (bower/lines.py, with the design's own foot_gap_m; the gap itself is a provisional allowance, not a measured girth)"},
        "entrances": S.entrances(design, at),
        "root_zones": [],
        "feeders": [],
        "handovers": [],
        "plants": [],
    }

    # the climbers: each of the level room's, on the same leg, planted beside the foot of that leg's cable
    footings = {pid: sole_footing(at["piers"][pid], at["feet"][pid], cfg["sole"], pile_cfg) for pid in piers}
    ball = site["planting_at_installation"]["root_ball_m"] / 2.0
    for s in S.stations(cfg["planting_from"]):
        m = by_id[s["member"]]
        ends = [m.path.station_at(e).point for e, stands in zip((0.0, m.path.length), on_floor(m, floor)) if stands]
        foot = min(ends, key=lambda q: math.dist(q[:2], at["piers"][s["pier"]]))  # a hoop stands at two piers: the foot at this climber's
        climbs = S.line_from(lines, s["member"], foot)
        if not climbs:
            continue
        cable = climbs["points_m"][0]
        away = (cable[0] - foot[0], cable[1] - foot[1])
        span = math.hypot(*away) or 1.0
        root = [round(cable[0] + away[0] / span * cfg["plant_in_m"], 3), round(cable[1] + away[1] / span * cfg["plant_in_m"], 3)]
        plates = [[tuple(p) for p in plate] for plate in footings[s["pier"]]["plates_m"]]
        under = [(root[0] + ball * f * math.cos(t * math.pi / 8.0), root[1] + ball * f * math.sin(t * math.pi / 8.0)) for f in (0.0, 0.5, 1.0) for t in range(16)]
        covered = sum(any(G._within(plate, q) > 0.0 for plate in plates) for q in under) / len(under)
        ground = round(z0 + gx * root[0] + gy * root[1], 3)
        out["plants"].append({"id": s["id"].replace("bed.", "climber."), "pier": s["pier"], "taxon": s["taxon"], "root_m": root, "root_level_m": ground, "rooted_in": "the bed's own soil", "on_steel": covered > 0.999, "root_ball_under_steel": round(covered, 2), "climbs": climbs["line"], "leg": s["member"], "cable_foot_m": cable, "cable_from_leg_m": round(span, 3), "route_m": climbs["points_m"], "meets_its_lines_at_m": [round(cable[2] - ground, 2)] * 2})
    for pid in piers:
        _check(footings[pid], [p for p in out["plants"] if p["pier"] == pid], pile_cfg)
    out["footings"] = footings
    out["footing_status"] = S.PROPOSAL
    out["planting_status"] = "which climber goes with which leg is " + S.CARRIED + f" (the level room {cfg['planting_from']}); where each is planted is a " + S.PROPOSAL

    # mesh round the joints the climbers can reach from the ground
    out["mesh_sleeves"], kinds = _sleeves(members, joints, floor, cfg["mesh"])
    out["mesh_status"] = S.PROPOSAL + " (a fine mesh round each joint, to keep growth out of it: its make, its fixing and whether it holds water against the timber are not known)"

    # what the level room would have been: the same design without its foot levels
    flat = copy.deepcopy({k: v for k, v in design.items()})
    for pier in flat["rooms"][0]["piers"]:
        pier.pop("foot_z_m", None)
    flat_members = build_design_timber(flat)[0]["members"]
    level_room = {"group": {"members": flat_members}, "joints": find_joints(flat_members, flat["timber"])[0]}
    was = {m.id: m.path.length for m in level_room["group"]["members"]}
    longer = {m.id: round(m.path.length - was[m.id], 3) for m in members if m.id in was and m.path.length - was[m.id] > 1e-4}
    scarfs = sum(1 for j in joints if j.kind == "scarf") - sum(1 for j in level_room["joints"] if j.kind == "scarf")
    drops = sorted({round(max(level.values()) - z, 3) for z in level.values()})

    plants = out["plants"]
    in_soil = sum(1 for p in plants if not p["on_steel"])
    steel = sorted({f["steel_area_m2"] for f in footings.values()})
    hull = sorted({f["hull_area_m2"] for f in footings.values()})
    standoffs = [math.dist(a, c) for line in out["training_lines"] for a, c in line["standoffs_m"]]
    way = next(e for e in out["entrances"] if e["bay"] == site["room"]["entry_bay"])
    deep = g["sole_below_soil_m"]  # the sole lies this far down, under the loosened bed
    first = next(iter(footings.values()))
    stub_m2 = round(sum(s["size_m"] ** 2 for s in first["stubs_m"]), 3)
    rf, beds = site["floor"]["radius_m"], site["beds"]
    arc = math.radians(180.0 - 2.0 * beds["opening_half_deg"])
    bed_m2 = 0.5 * arc * ((beds["outer_radius_m"] ** 2 - rf**2) + (beds["sheltered_outer_radius_m"] ** 2 - rf**2))
    reached = len({s["joint"] for s in out["mesh_sleeves"]})
    q = {
        "climbers": {"value": len(plants), "says": f"{len(plants)} climbers", "from": S.CARRIED},
        "climbers_in_soil": {"value": in_soil, "of": len(plants), "says": f"{in_soil} of {len(plants)} rooted in soil", "from": S.MEASURED},
        "planted_from_its_cable_m": {"value": cfg["plant_in_m"], "says": f"each planted {cfg['plant_in_m']} m from the foot of its own cable", "from": S.PROPOSAL},
        "steel_over_the_ground_m2": {"value": steel, "within_m2": hull, "buried_m": [deep, round(deep + pile_cfg["cap_depth_m"], 3)], "says": f"{steel[0]} m2 of steel under each pier, {deep} m down: under the bed, not in it", "from": S.MEASURED},
        "steel_through_the_bed": {"value": len(first["stubs_m"]), "plan_m2": stub_m2, "sizes_m": sorted({s["size_m"] for s in first["stubs_m"]}), "long_m": round(deep - sunk, 3), "says": f"through the bed, {len(first['stubs_m'])} slender stubs at each pier and nothing else: {stub_m2} m2 in plan", "from": S.PROPOSAL},
        "timber_in_the_ground_m": {"value": sunk, "says": f"every foot runs {round(sunk * 1000)} mm into the soil", "from": S.PROPOSAL},
        "loosened_soil_m3": {"value": round(bed_m2 * g["soil_depth_m"], 1), "bed_m2": round(bed_m2, 1), "says": f"{round(bed_m2)} m2 of bed, loosened {g['soil_depth_m']} m deep, open to the ground beyond", "from": S.PROPOSAL},
        "piles": {"value": sum(len(f["piles_m"]) for f in footings.values()), "says": f"{sum(len(f['piles_m']) for f in footings.values())} screw piles", "from": S.PROPOSAL},
        "fall_across_the_room_m": {"value": drops[-1], "says": f"the ground falls {drops[-1]} m across the room, and nothing is levelled", "from": S.MEASURED},
        "leg_lengths": {"value": drops, "says": f"{len(drops)} lengths of leg: {', '.join(str(d) for d in drops)} m longer than on level ground", "from": S.MEASURED},
        "members_made_longer": {"value": len(longer), "of": len(members), "most_m": max(longer.values()), "says": f"{len(longer)} of {len(members)} members are made longer, by up to {max(longer.values())} m (a hoop that stands at two piers); the other {len(members) - len(longer)} are the level room's", "from": S.MEASURED},
        "extra_scarfs": {"value": scarfs, "says": f"{scarfs} members pass the longest piece that can be made and gain a scarf", "from": S.MEASURED},
        "cable_m": {"value": round(sum(line.length_m for line in lines), 1), "stretches": len(lines), "says": f"{round(sum(line.length_m for line in lines))} m of cable in {len(lines)} stretches", "from": S.MEASURED},
        "standoffs": {"value": len(standoffs), "longest_m": round(max(standoffs), 3), "shortest_m": round(min(standoffs), 3), "says": f"{len(standoffs)} standoffs, from {round(min(standoffs) * 1000)} mm long up the roof to {round(max(standoffs) * 1000)} mm at a foot", "from": S.MEASURED},
        "joints": {"value": len(joints), "by_kind": kinds, "within_reach": reached, "reach_m": cfg["mesh"]["below_m"], "says": f"{len(joints)} joints to wrap in mesh, {sum(1 for j in joints if j.at_m[2] - floor.at(j.at_m) <= 3.2)} of them within 3.2 m of the ground", "from": S.MEASURED},
        "way_in_m": {"value": way["between_innermost_legs_m"], "path_m": site["paths"]["arrival"]["width_m"], "says": f"{way['between_innermost_legs_m']} m between the legs at the way in", "from": S.MEASURED},
        "floor_m2": {"value": round(math.pi * rf**2), "says": f"{round(math.pi * rf**2)} m2 of floor, following the ground", "from": S.PROPOSAL},
        "tended": {"value": "from-the-floor", "says": "tended from the floor and from the two thresholds, standing", "from": S.PROPOSAL},
    }
    out["quantities"] = q
    out["members_made_longer"] = longer
    return out
