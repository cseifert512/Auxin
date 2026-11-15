"""The ground at a pier: where a plant is rooted, what the legs stand on, and how the plant gets up.

A pier is where the building comes to the ground and where its plants do too. The roots, the
footing and the plant's way up all want the same square metre, so they are set out together:

    root zones   authored, as piers are. design["ground"]["root_zones"] is a list of
                 {id, position_m, radius_m, depth_m, plant, needs_soil_m3}: a cylinder of soil kept
                 for one plant's roots. `plant` is a label, and `needs_soil_m3` what that plant is
                 said to need: both are the plant side's to say and are only carried here.
    footings     generated, one under each pier, of the type the design names:
                 piles  screw piles under a steel cap that the feet stand on. The cap is lifted
                        clear of the soil, so the ground stays open beneath the whole pier and a
                        root zone loses only a sleeve of soil round each shaft. Piles cannot
                        stand as close as the feet do, so there are few of them: enough that no
                        foot is further than reach_m from one, never fewer than `least`, kept
                        spacing_m apart in a ring and plant_clear_m from where a plant stands.
                        Where a pile has to stand outside the feet the cap reaches out to it.
                 pad    the earlier model, kept as an option: a solid pad, the outline of the
                        feet grown by margin_m. Beside a root zone it is cut back, to leave the
                        zone its ground and root_clear_m more, but never to less than least_m
                        beyond a foot; where that stops it the zone loses ground, and says so.
    feeders      generated: the plant's way from its root zone up to the training lines, as two
                 cables on the arch leg nearest the zone, set out as training lines are
                 (bower/lines.py). One stands off the leg's exterior face from the floor. The
                 other stands off the arch's back, which is free only once the two arches of
                 the pier have parted; the first runs on beside it for overlap_m, so that a
                 shoot is led round one corner of the arch from the one to the other.
    hand-overs   measured: from the feeder on the arch's back, the nearest point of each training
                 line that starts at this pier that a straight tie can reach clear of the
                 timber. They are where a gardener leads a shoot across; nothing is built there.
    entrances    measured: the clear way through each open bay, between its arch legs and between
                 the root zones beside them.

design["ground"]:
    root_zones   the list above
    footings     type (piles | pad), and the settings of each under its own name:
                 piles  cap_margin_m, cap_depth_m, feet_above_soil_m (how far below the feet the
                        soil lies: the cap's depth and the air beneath it), shaft_m, helix_m,
                        length_m, spacing_m, reach_m, least, edge_m (a pile's centre from the
                        cap's edge), plant_clear_m, root_clear_m (the sleeve round a shaft)
                 pad    margin_m, least_m, root_clear_m, depth_m
    feeders      reach_m (the longest tie a hand-over may be), overlap_m, beyond_m (how far the
                 feeder runs on past its last hand-over), tie_clear_m, plant_reach_m (the furthest
                 a root zone may be from the foot of its feeder)
    entrances    least_m: a way through narrower than this is marked for review

A design without that block has no ground set out. Nothing here changes a member: where the
ground cannot be shared, the conflict is reported, for the piers to be changed or the plant moved.

Lifting the cap clear of the soil means the soil at a pier lies feet_above_soil_m below the
feet. This module only records that level and puts the root zones at it: whether the feet are
raised above the ground all round, or each pier stands in a sunken bed, is not decided here.

Pure Python (no bpy). No foundation has been designed or sized. How many piles a pier has is
set by where its feet stand, not by any load; nothing is known of the soil; and the outward
push of the arches on slender piles in soft planting soil is not looked at.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import lines as L
from .centreline import add, mul, norm, sub
from .spine import crown_spine
from .topology import DesignError

FOOTINGS = {
    "piles": {"cap_margin_m": 0.1, "cap_depth_m": 0.12, "feet_above_soil_m": 0.3, "shaft_m": 0.09, "helix_m": 0.3, "length_m": 2.5, "spacing_m": 0.9, "reach_m": 0.6, "least": 3, "edge_m": 0.12, "plant_clear_m": 0.3, "root_clear_m": 0.05},
    "pad": {"margin_m": 0.25, "least_m": 0.08, "root_clear_m": 0.1, "depth_m": 0.5},
}
DEFAULTS = {
    "footings": {"type": "piles", **FOOTINGS},
    "feeders": {"reach_m": 0.6, "overlap_m": 0.5, "beyond_m": 0.3, "tie_clear_m": 0.02, "plant_reach_m": 1.0},
    "entrances": {"least_m": 2.0},
}
ZONE = {"radius_m": 0.5, "depth_m": 0.6, "plant": "", "needs_soil_m3": None}
FEEDER_REACH_M = 3.0  # how far up an arch, past where its back comes free, a hand-over is looked for


@dataclass(frozen=True)
class RootZone:
    id: str
    position: tuple  # plan
    radius_m: float
    depth_m: float
    plant: str
    needs_soil_m3: float | None
    pier: str
    outside: bool  # whether it lies outside its room's ring of piers
    soil_m3: float  # the soil it has: its cylinder, less what a footing takes, shared where zones overlap
    taken: float  # the share of its ground a footing takes: a pad, or the sleeves round pile shafts
    covered: float  # the share of its ground that lies under a cap: open soil, but out of the rain and the light
    top_m: float  # how far below the feet its soil lies
    feeder: str  # the arch its feeder is on, or ""
    to_feeder_m: float | None  # from its centre to the foot of that feeder
    review: str = ""


@dataclass(frozen=True)
class Footing:
    pier: str
    kind: str  # "piles" or "pad"
    outline: tuple  # plan polygon, counter-clockwise: the cap, or the pad
    area_m2: float
    plain_area_m2: float  # a pad with no root zone beside it; a cap as small as the feet allow
    depth_m: float  # of the cap, or of the pad
    feet: tuple  # the members that stand on it
    cut_for: tuple = ()  # a pad: the root zones it was cut back for
    piles: tuple = ()  # the plan positions of its piles
    review: str = ""


@dataclass(frozen=True)
class Handover:
    line: str  # the training line reached
    feeder: str  # from this feeder line
    pier: str
    gap_m: float  # the length of the tie
    at_m: float  # station along the feeder's arch
    start: tuple  # on the feeder's cable
    end: tuple  # on the training line's cable
    below_m: float  # the length of that training line below the hand-over: what a plant from this zone cannot use


def settings(design: dict) -> dict | None:
    """A design's ground settings with every default filled in, or None if it sets none out."""
    own = design.get("ground")
    if own is None:
        return None
    unknown = sorted(set(own) - set(DEFAULTS) - {"note", "root_zones"})
    if unknown:
        raise DesignError(f"ground has no setting called {', '.join(unknown)}")
    cfg = {}
    for part, defaults in DEFAULTS.items():
        given = own.get(part, {})
        odd = sorted(set(given) - set(defaults))
        if odd:
            raise DesignError(f"ground.{part} has no setting called {', '.join(odd)}")
        cfg[part] = {**defaults, **given}
    if cfg["footings"]["type"] not in FOOTINGS:
        raise DesignError(f"ground.footings.type {cfg['footings']['type']!r} is not one of {', '.join(FOOTINGS)}")
    for kind, defaults in FOOTINGS.items():
        given = own.get("footings", {}).get(kind, {})
        odd = sorted(set(given) - set(defaults))
        if odd:
            raise DesignError(f"ground.footings.{kind} has no setting called {', '.join(odd)}")
        cfg["footings"][kind] = {**defaults, **given}
    zones, seen = [], set()
    for zone in own.get("root_zones", []):
        odd = sorted(set(zone) - set(ZONE) - {"id", "position_m"})
        if "id" not in zone or "position_m" not in zone or odd:
            raise DesignError(f"a root zone needs an id and a position_m, and may give {', '.join(ZONE)}: {zone}")
        if zone["id"] in seen:
            raise DesignError(f"two root zones are called {zone['id']}")
        seen.add(zone["id"])
        merged = {**ZONE, **zone}
        if not merged["radius_m"] > 0.0 or not merged["depth_m"] > 0.0:
            raise DesignError(f"root zone {zone['id']}: radius_m and depth_m must be more than 0")
        zones.append(merged)
    cfg["root_zones"] = zones
    if cfg["footings"]["pad"]["least_m"] > cfg["footings"]["pad"]["margin_m"]:
        raise DesignError("ground.footings.pad.least_m cannot be more than margin_m")
    piles = cfg["footings"]["piles"]
    if piles["least"] < 1 or not piles["spacing_m"] > 0.0 or not piles["reach_m"] > 0.0 or piles["cap_depth_m"] >= piles["feet_above_soil_m"]:
        raise DesignError("ground.footings.piles: least must be 1 or more, spacing_m and reach_m more than 0, and feet_above_soil_m more than cap_depth_m, or the cap would sit in the soil")
    return cfg


# --- plan geometry ----------------------------------------------------------------------------------


def _hull(points: list) -> list:
    """The convex outline of plan points, counter-clockwise."""
    pts = sorted(set((round(p[0], 6), round(p[1], 6)) for p in points))
    if len(pts) < 3:
        return pts

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and (out[-1][0] - out[-2][0]) * (p[1] - out[-2][1]) - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0]) <= 0:
                out.pop()
            out.append(p)
        return out[:-1]

    return half(pts) + half(pts[::-1])


def _grow(outline: list, by: float, sides: int = 16) -> list:
    """A convex outline moved out by `by` all round, its corners rounded."""
    return _hull([(x + by * math.cos(2 * math.pi * k / sides), y + by * math.sin(2 * math.pi * k / sides)) for x, y in outline for k in range(sides)])


def _cut(outline: list, c, u, t: float) -> list:
    """The part of a convex outline at least `t` from the point `c`, measured along the unit direction `u`."""
    def side(p):
        return (p[0] - c[0]) * u[0] + (p[1] - c[1]) * u[1] - t

    out = []
    for p, q in zip(outline, outline[1:] + outline[:1]):
        a, b = side(p), side(q)
        if a >= 0.0:
            out.append(p)
        if (a >= 0.0) != (b >= 0.0):
            k = a / (a - b)
            out.append((p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k))
    return out


def _area(outline: list) -> float:
    return 0.5 * sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(outline, outline[1:] + outline[:1]))


def _within(outline: list, p) -> float:
    """How far inside a convex counter-clockwise outline a point is: negative outside it."""
    least = math.inf
    for a, b in zip(outline, outline[1:] + outline[:1]):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length > 1e-12:
            least = min(least, ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) / length)
    return least


def _along(points: list, step: float) -> list:
    """Points every `step` or less along a run of straight pieces, each with how far along the run it is."""
    out, run = [], 0.0
    for a, b in zip(points, points[1:]):
        length = norm(sub(b, a))
        count = max(1, math.ceil(length / step))
        out += [(add(a, mul(sub(b, a), i / count)), run + length * i / count) for i in range(count)]
        run += length
    return out + [(points[-1], run)]


# --- the parts ------------------------------------------------------------------------------------


def feet_at_piers(design: dict, group: dict) -> dict:
    """Every foot that stands on the floor, by the pier it stands at: pier ID -> [(member, its station there, its plan corners)]."""
    members, floor = group["members"], L._floor(group["members"])
    piers = {}
    for room in design["rooms"]:
        if room["id"] in group["rooms"]:
            for pier in room["piers"]:
                at = tuple(pier["position_m"])
                piers.setdefault(next((k for k, v in piers.items() if math.dist(v, at) < 1e-6), pier["id"]), at)  # a pier two rooms share is one pier
    feet = {pier_id: [] for pier_id in piers}
    for m in members:
        for station, grounded in zip((0.0, m.path.length), L.on_floor(m, floor)):
            if grounded:
                st = m.path.station_at(station)
                pier_id = min(piers, key=lambda k: math.hypot(piers[k][0] - st.point[0], piers[k][1] - st.point[1]))
                corners = [(st.point[0] + sx * st.width_axis[0] * m.width / 2.0 + sy * st.depth_axis[0] * m.depth / 2.0, st.point[1] + sx * st.width_axis[1] * m.width / 2.0 + sy * st.depth_axis[1] * m.depth / 2.0) for sx in (-1, 1) for sy in (-1, 1)]
                feet[pier_id].append((m, station, corners))
    return {"piers": piers, "feet": {k: v for k, v in feet.items() if v}}


def _set_piles(plain: list, corners: list, zones: list, p: dict):
    """Where the piles of one pier stand, or None if no arrangement serves.

    They stand in a ring, spacing_m from one to the next: a triangle of three, a square of four.
    Of the places and turns such a ring can take about the middle of the feet, the one is taken
    that keeps plant_clear_m from every plant, leaves no foot further than reach_m from a pile,
    and stands least outside the outline of the feet; a ring of more piles only if none of
    fewer will do.
    """
    cx, cy = sum(c[0] for c in corners) / len(corners), sum(c[1] for c in corners) / len(corners)
    for count in range(p["least"], 7):
        radius = p["spacing_m"] / (2.0 * math.sin(math.pi / count)) if count > 1 else 0.0
        best = None
        for i in range(-4, 5):
            for j in range(-4, 5):
                for k in range(12 if count > 1 else 1):
                    turn = 2.0 * math.pi / count * k / 12.0
                    piles = [(cx + 0.1 * i + radius * math.cos(turn + 2.0 * math.pi * m / count), cy + 0.1 * j + radius * math.sin(turn + 2.0 * math.pi * m / count)) for m in range(count)]
                    if any(math.dist(q, z["position_m"]) < p["plant_clear_m"] for q in piles for z in zones):
                        continue
                    far = max(min(math.dist(c, q) for q in piles) for c in corners)
                    if far > p["reach_m"]:
                        continue
                    outside = sum(max(0.0, p["edge_m"] - _within(plain, q)) ** 2 for q in piles)
                    key = (round(outside, 6), round(far, 4))
                    if best is None or key < best[0]:
                        best = (key, piles)
        if best:
            return [(round(x, 3), round(y, 3)) for x, y in best[1]]
    return None


def _caps(cfg: dict, at: dict) -> dict:
    """One cap on screw piles per pier: the outline of its feet grown by cap_margin_m, reaching
    further only where a pile stands outside that."""
    p, footings = cfg["footings"]["piles"], {}
    for pier_id, feet in at["feet"].items():
        corners = [c for _, _, cs in feet for c in cs]
        plain = _grow(_hull(corners), p["cap_margin_m"])
        near = [z for z in cfg["root_zones"] if min(math.dist(z["position_m"], c) for c in corners) < 3.0]
        piles = _set_piles(plain, corners, near, p)
        notes = []
        if piles is None:
            piles, cap = [], plain
            notes.append(f"no ring of up to 6 piles {p['spacing_m']} m apart stands within {p['reach_m']} m of every foot and {p['plant_clear_m']} m clear of every plant")
        else:
            cap = _hull(list(plain) + [(x + p["edge_m"] * math.cos(2 * math.pi * k / 16), y + p["edge_m"] * math.sin(2 * math.pi * k / 16)) for x, y in piles for k in range(16)])
            if _area(cap) > 1.25 * _area(plain):
                notes.append(f"the cap is {_area(cap):.2f} m2, against {_area(plain):.2f} for the feet alone, to reach its {len(piles)} piles {p['spacing_m']} m apart")
        footings[pier_id] = Footing(pier_id, "piles", tuple(cap), round(_area(cap), 3), round(_area(plain), 3), p["cap_depth_m"], tuple(m.id for m, _, _ in feet), (), tuple(piles), "; ".join(notes))
    return footings


def _footings(cfg: dict, at: dict) -> dict:
    """One footing per pier, of the type the design names."""
    return _caps(cfg, at) if cfg["footings"]["type"] == "piles" else _pads(cfg, at)


def _pads(cfg: dict, at: dict) -> dict:
    """One pad per pier, each cut back for the root zones beside it."""
    f, held = cfg["footings"]["pad"], {}
    footings = {}
    for pier_id, feet in at["feet"].items():
        corners = [c for _, _, cs in feet for c in cs]
        core = _hull(corners)
        plain = _grow(core, f["margin_m"])
        middle = (sum(p[0] for p in core) / len(core), sum(p[1] for p in core) / len(core))
        outline, cut_for = plain, []
        for zone in cfg["root_zones"]:
            c, reach = zone["position_m"], zone["radius_m"] + f["root_clear_m"]
            away = math.hypot(middle[0] - c[0], middle[1] - c[1])
            if away < 1e-9 or min(math.hypot(p[0] - c[0], p[1] - c[1]) for p in plain) > reach + 2.0:
                continue
            u = ((middle[0] - c[0]) / away, (middle[1] - c[1]) / away)
            if min((p[0] - c[0]) * u[0] + (p[1] - c[1]) * u[1] for p in plain) >= reach:
                continue  # the zone does not come near this footing
            least = min((p[0] - c[0]) * u[0] + (p[1] - c[1]) * u[1] for p in corners) - f["least_m"]
            outline = _cut(outline, c, u, min(reach, least))
            cut_for.append(zone["id"])
            if least < reach:
                held.setdefault(zone["id"], []).append(pier_id)
        review = "; ".join(f"it could not be cut back far enough to leave {z} its ground: a foot stands in the way" for z in cut_for if pier_id in held.get(z, []))
        footings[pier_id] = Footing(pier_id, "pad", tuple(outline), round(_area(outline), 3), round(_area(plain), 3), f["depth_m"], tuple(m.id for m, _, _ in feet), tuple(cut_for), (), review)
    return footings


def _soil(cfg: dict, footings: dict) -> dict:
    """The soil each root zone has, the share of its ground a footing takes, and the share that
    lies under a cap: zone ID -> (m3, share taken, share covered).

    A pad takes all the ground it covers. A cap on piles takes none: only the sleeve of
    root_clear_m round each shaft is lost, and the rest of what it covers stays open soil.
    """
    zones, out = cfg["root_zones"], {}
    sleeve = cfg["footings"]["piles"]["shaft_m"] / 2.0 + cfg["footings"]["piles"]["root_clear_m"]

    def lost(p) -> bool:
        return any(_within(f.outline, p) > 0.0 if f.kind == "pad" else any(math.dist(p, q) <= sleeve for q in f.piles) for f in footings.values())

    for zone in zones:
        (cx, cy), r = zone["position_m"], zone["radius_m"]
        h, n = r / 20.0, 20
        every = free = taken = covered = 0.0
        for i in range(-n, n):
            for j in range(-n, n):
                p = (cx + (i + 0.5) * h, cy + (j + 0.5) * h)
                if math.hypot(p[0] - cx, p[1] - cy) > r:
                    continue
                every += 1.0
                covered += any(f.kind == "piles" and _within(f.outline, p) > 0.0 for f in footings.values())
                if lost(p):
                    taken += 1.0
                else:
                    free += 1.0 / sum(1 for other in zones if math.hypot(p[0] - other["position_m"][0], p[1] - other["position_m"][1]) <= other["radius_m"])
        out[zone["id"]] = (free * h * h * zone["depth_m"], taken / every if every else 0.0, covered / every if every else 0.0)
    return out


def _tie(feeder: list, target: list, bodies, reach: float, clear: float):
    """The shortest straight tie from a feeder's cable to another cable that passes clear of all the
    timber: (its length, how far along the feeder it leaves, its start, its end, how far along the
    other cable it lands), or None. `feeder` and `target` are points with how far along they are."""
    found = None
    for p, run in feeder:
        q, along = min(target, key=lambda item: norm(sub(item[0], p)))
        gap = norm(sub(q, p))
        if gap > reach or (found and gap >= found[0]):
            continue
        if all(bodies.clearance(add(p, mul(sub(q, p), k / 10.0)))[0] >= clear for k in range(1, 10)):
            found = (gap, run, p, q, along)
    return found


def beside_pier(design: dict, group: dict, pier_id: str, out_m: float = 0.45, **zone) -> list[dict]:
    """Root zones to author beside one pier: one outside each of its arch legs, `out_m` beyond where
    that leg's feeder cable would stand. Returns them as design["ground"]["root_zones"] holds them."""
    line_cfg = L.settings(design["timber"]) or L.DEFAULTS
    at = feet_at_piers(design, group)
    zones = []
    for m, station, _ in sorted(at["feet"].get(pier_id, []), key=lambda foot: foot[0].id):
        if m.family != "arch" or _bay(design, m.parent)["type"] == "portal":
            continue
        st = m.path.station_at(station)
        axis, half = L._off(m, st, L.EXTERIOR, _centre(design, group["room_of"][m.id]))
        p = add(st.point, mul(axis, half + line_cfg["gap_m"] + out_m))
        zones.append({"id": f"{pier_id}.root.{len(zones) + 1}", "position_m": [round(p[0], 3), round(p[1], 3)], **zone})
    return zones


def _bay(design: dict, bay_id: str) -> dict:
    return next(bay for room in design["rooms"] for bay in room["bays"] if bay["id"] == bay_id)


def _centre(design: dict, room_id: str) -> tuple:
    return tuple(next(room for room in design["rooms"] if room["id"] == room_id)["crown"]["centre_m"])


def lay(design: dict, group: dict, joints, lines: list) -> dict:
    """Set out the ground of one group of joined rooms, given its joints and its training lines.

    Returns {"root_zones", "footings", "feeders", "handovers", "entrances", "report"}: the
    feeders are lines (bower/lines.py) of kind "feeder", to be strung and scheduled with the rest.
    """
    cfg = settings(design)
    line_cfg = L.settings(design["timber"]) or dict(L.DEFAULTS)
    members, room_of = group["members"], group["room_of"]
    by_id, floor = {m.id: m for m in members}, L._floor(members)
    at = feet_at_piers(design, group)
    piers = at["piers"]
    rooms = {room["id"]: room for room in design["rooms"] if room["id"] in group["rooms"]}
    pier_room = {p["id"]: room for room in rooms.values() for p in room["piers"]}
    mine = [z for z in cfg["root_zones"] if piers and min(math.dist(z["position_m"], p) for p in piers.values()) < 6.0] if piers else []
    cfg = {**cfg, "root_zones": mine}  # the zones that are this group's to deal with
    footings = _footings(cfg, at)
    soil = _soil(cfg, footings)
    bodies = L.Bodies(members, max(L.REACH_M, line_cfg["gap_m"] + line_cfg["standoff_sag_m"] + 0.02))
    cuts = {}
    for joint in joints:
        for cut in joint.cuts:
            cuts.setdefault(cut.member, []).append((cut, next((m for m in joint.members if m and m != cut.member), "")))

    # each zone's feeder: on the arch leg of its pier whose exterior face it stands nearest
    f = cfg["feeders"]
    zone_pier = {z["id"]: min(piers, key=lambda k: math.dist(piers[k], z["position_m"])) for z in mine}
    chosen = {}  # zone ID -> (arch, distance from the zone to the foot of its feeder)
    for zone in mine:
        best = None
        for m, station, _ in at["feet"].get(zone_pier[zone["id"]], []):
            if m.family != "arch" or _bay(design, m.parent)["type"] == "portal" or station != 0.0:
                continue
            st = m.path.station_at(line_cfg["foot_clear_m"])
            axis, half = L._off(m, st, L.EXTERIOR, _centre(design, room_of[m.id]))
            foot = add(st.point, mul(axis, half + line_cfg["gap_m"]))
            away = math.hypot(foot[0] - zone["position_m"][0], foot[1] - zone["position_m"][1])
            if best is None or away < best[1]:
                best = (m, away)
        if best and best[1] <= f["plant_reach_m"]:
            chosen[zone["id"]] = best

    feeders, handovers, notes = [], [], {z["id"]: [] for z in mine}
    for pier_id in sorted({zone_pier[z] for z in chosen}):
        arches = sorted({chosen[z][0].id for z in chosen if zone_pier[z] == pier_id})
        here = {m.id: station for m, station, _ in at["feet"][pier_id]}  # each member that stands here, and which of its ends does
        legs = [line for line in lines if line.kind == "training" and line.member in here]
        targets = {line.id: _along(list(line.points), 0.1) for line in legs}
        backs = {}
        for arch_id in arches:
            arch = by_id[arch_id]
            trial = L._line(arch, line_cfg, bodies, cuts.get(arch_id, []), floor, face="outer", tag="feeder.back", kind="feeder")
            if trial:  # the back is free from where the first stretch starts
                first = trial[0]
                trimmed = [(p, run) for p, run in _along(list(first.points), 0.1) if run <= FEEDER_REACH_M]
                backs[arch_id] = (first, trimmed)
        # every training line that starts here is handed over from the feeder that reaches it with the shortest tie
        reached = {}
        for line in legs:
            for arch_id, (first, cable) in backs.items():
                tie = _tie(cable, targets[line.id], bodies, f["reach_m"], f["tie_clear_m"])
                if tie and (line.id not in reached or tie[0] < reached[line.id][1][0]):
                    reached[line.id] = (arch_id, tie)
        for arch_id in arches:
            arch, centre = by_id[arch_id], _centre(design, room_of[arch_id])
            if arch_id not in backs:
                for z in chosen:
                    if chosen[z][0].id == arch_id:
                        notes[z].append(f"the back of {arch_id} never comes free of the timber beside it, so its feeder has nowhere to hand over")
                continue
            first = backs[arch_id][0]
            ties = [tie for a, tie in reached.values() if a == arch_id]
            run = max((tie[1] for tie in ties), default=0.0) + f["beyond_m"]
            # the station on the arch where the cable has run that far: its standoffs are stations along the arch
            far = first.from_m
            travelled = 0.0
            for a, b in zip(first.standoffs, first.standoffs[1:]):
                step = norm(sub(b.head, a.head))
                if travelled + step >= run:
                    far = a.at_m + (b.at_m - a.at_m) * (run - travelled) / step
                    break
                travelled, far = travelled + step, b.at_m
            far = max(far, first.from_m + line_cfg["min_length_m"])
            # The far end may fall in a housing cut for another member, where no standoff can stand. The cable then stops short of it,
            # and a stretch left shorter than the least length is no line at all: two piers of a regular six-bay room lost theirs that way.
            # So it runs on, a little at a time, to the next place a standoff can stand.
            back, reach = [], far
            while not back and reach <= far + 0.6:
                back = L._line(arch, line_cfg, bodies, cuts.get(arch_id, []), floor, face="outer", span=(first.from_m, reach), tag="feeder.back", kind="feeder")
                reach += 0.1
            front = L._line(arch, line_cfg, bodies, cuts.get(arch_id, []), floor, face=L.EXTERIOR, span=(line_cfg["foot_clear_m"], first.from_m + f["overlap_m"]), centre=centre, tag="feeder", kind="feeder")
            feeders += front[:1] + back[:1]
            for z in chosen:
                if chosen[z][0].id == arch_id and (not front or front[0].from_m > line_cfg["foot_clear_m"] + 0.3):
                    notes[z].append(f"the feeder on the outside of {arch_id} does not start at the floor: something stands too close to that face")
            for line_id, (a, tie) in sorted(reached.items()):
                if a == arch_id:
                    gap, _, start, end, along = tie
                    reached_line = next(line for line in legs if line.id == line_id)
                    below = along if here[reached_line.member] == 0.0 else reached_line.length_m - along  # a hoop's line ends at its second pier
                    handovers.append(Handover(line_id, back[0].id if back else first.id, pier_id, round(gap, 3), round(first.from_m + tie[1], 2), start, end, round(below, 2)))
        missed = sorted(line.id for line in legs if line.id not in reached)
        if missed:
            for z in chosen:
                if zone_pier[z] == pier_id:
                    notes[z].append(f"no hand-over within {f['reach_m']} m to {', '.join(missed)}")

    zones = []
    for zone in mine:
        zid, pier_id = zone["id"], zone_pier[zone["id"]]
        room = pier_room.get(pier_id) or next(iter(rooms.values()))
        spine = crown_spine(room["crown"])
        outside = spine.locate(zone["position_m"])[1] > spine.locate(piers[pier_id])[1]
        m3, taken, covered = soil[zid]
        review = list(notes[zid])
        if zid not in chosen:
            review.append(f"no arch leg stands within {f['plant_reach_m']} m of it to carry a feeder")
        if not outside:
            review.append("it lies inside the room's ring of piers")
        if taken > 0.02 and cfg["footings"]["type"] == "pad":
            review.append(f"a footing takes {100 * taken:.0f}% of its ground")
        if covered > 0.5:
            review.append(f"{100 * covered:.0f}% of its ground lies under a cap, out of the rain")
        if zone["needs_soil_m3"] is not None and m3 < zone["needs_soil_m3"] - 1e-9:
            review.append(f"it has {m3:.2f} m3 of soil and is said to need {zone['needs_soil_m3']}")
        arch, away = chosen.get(zid, (None, None))
        top = cfg["footings"]["piles"]["feet_above_soil_m"] if cfg["footings"]["type"] == "piles" else 0.0
        zones.append(RootZone(zid, tuple(zone["position_m"]), zone["radius_m"], zone["depth_m"], zone["plant"], zone["needs_soil_m3"], pier_id, outside, round(m3, 3), round(taken, 3), round(covered, 3), top, arch.id if arch else "", round(away, 3) if away is not None else None, "; ".join(review)))

    entrances = _entrances(design, rooms, at, mine, cfg["entrances"]["least_m"])
    planted = sorted({z.pier for z in zones})
    report = {
        "root_zones": len(zones),
        "piers_with_root_zones": planted,
        "soil_m3": {z.id: z.soil_m3 for z in zones},
        "footings": len(footings),
        "footing_type": cfg["footings"]["type"],
        "piles": sum(len(ft.piles) for ft in footings.values()),
        "piles_at_each_pier": sorted({len(ft.piles) for ft in footings.values()}),
        "footing_area_m2": {p: [footings[p].area_m2, footings[p].plain_area_m2] for p in planted if p in footings},
        "soil_below_feet_m": cfg["footings"]["piles"]["feet_above_soil_m"] if cfg["footings"]["type"] == "piles" else 0.0,
        "feeders": [line.id for line in feeders],
        "feeder_length_m": round(sum(line.length_m for line in feeders), 2),
        "handovers": len(handovers),
        "handover_gap_m": [min(h.gap_m for h in handovers), max(h.gap_m for h in handovers)] if handovers else None,
        "handover_height_m": [round(min(h.end[2] for h in handovers) - floor, 2), round(max(h.end[2] for h in handovers) - floor, 2)] if handovers else None,
        "training_line_below_handovers_m": round(sum(h.below_m for h in handovers), 1),
        "narrowest_entrance_m": min((e["between_root_zones_m"] for e in entrances), default=None),
        "to_review": {**{z.id: z.review for z in zones if z.review}, **{f"footing at {p}": ft.review for p, ft in footings.items() if ft.review}, **{f"entrance {e['bay']}": e["review"] for e in entrances if e["review"]}},
    }
    return {"root_zones": zones, "footings": footings, "feeders": feeders, "handovers": handovers, "entrances": entrances, "report": report}


def _entrances(design: dict, rooms: dict, at: dict, zones: list, least: float) -> list[dict]:
    """The clear way through each open bay: between its two arch legs, and between the root zones beside them."""
    out = []
    corners = {m.id: cs for feet in at["feet"].values() for m, _, cs in feet if m.family == "arch"}
    for room in rooms.values():
        position = {p["id"]: tuple(p["position_m"]) for p in room["piers"]}
        for bay in room["bays"]:
            if bay["type"] != "open":
                continue
            a, b = position[bay["from"]], position[bay["to"]]
            span = math.dist(a, b)
            u = ((b[0] - a[0]) / span, (b[1] - a[1]) / span)
            lo, hi = 0.0, span
            for side in ("L", "R"):
                for c in corners.get(f"{bay['id']}.arch.{side}", []):
                    t = (c[0] - a[0]) * u[0] + (c[1] - a[1]) * u[1]
                    lo, hi = (max(lo, t), hi) if math.dist(c, a) < math.dist(c, b) else (lo, min(hi, t))
            taken = [(lo - 9.0, lo), (hi, hi + 9.0)]
            for zone in zones:
                c, r = zone["position_m"], zone["radius_m"]
                t = (c[0] - a[0]) * u[0] + (c[1] - a[1]) * u[1]
                off = abs((c[0] - a[0]) * u[1] - (c[1] - a[1]) * u[0])
                if off < r + 1.5 and -r < t < span + r:  # beside this bay's threshold, within a stride or two of it
                    taken.append((t - r, t + r))
            taken.sort()
            free, edge = 0.0, taken[0][1]
            for start, end in taken[1:]:
                free, edge = max(free, start - edge), max(edge, end)
            review = f"the way through is {free:.2f} m between root zones, under the {least} m asked for" if free < least else ""
            out.append({"bay": bay["id"], "between_arch_legs_m": round(hi - lo, 2), "between_root_zones_m": round(free, 2), "review": review})
    return out


def zone_rows(laid: dict) -> list[dict]:
    """One row per root zone, for a schedule."""
    reached = {}
    for h in laid["handovers"]:
        reached.setdefault(h.feeder.split(".feeder")[0], []).append(h)
    rows = []
    for z in laid["root_zones"]:
        ties = reached.get(z.feeder, [])
        rows.append(
            {
                "id": z.id,
                "pier": z.pier,
                "plant": z.plant,
                "x_m": z.position[0],
                "y_m": z.position[1],
                "radius_m": z.radius_m,
                "depth_m": z.depth_m,
                "outside_the_room": "yes" if z.outside else "no",
                "soil_m3": z.soil_m3,
                "needs_soil_m3": "" if z.needs_soil_m3 is None else z.needs_soil_m3,
                "ground_taken_by_footing": z.taken,
                "ground_under_a_cap": z.covered,
                "soil_below_feet_m": z.top_m,
                "feeder_on": z.feeder,
                "to_feeder_m": "" if z.to_feeder_m is None else z.to_feeder_m,
                "lines_handed_to": len(ties),
                "longest_tie_m": max((h.gap_m for h in ties), default=""),
                "review": z.review,
            }
        )
    return rows
