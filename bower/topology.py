"""Level A: the plan graph that everything else is generated from.

A room is a counter-clockwise ring of piers. Each bay spans two consecutive
piers and names them by ID, so the ring order and the bay endpoints check each
other. IDs come from per-room counters that only count up: an ID is never
reused, and no edit renumbers anything else.

Operations are pure. Each returns a new, validated design and a record of what
it added, removed and modified; the design passed in is left untouched, so a
rejected edit costs nothing.

The ring can also be laid out from parameters: room["layout"] holds the number
of bays and, optionally, the plan outline the piers stand on and the apex
heights. Change it and `reconcile` (which scripts/generate.py runs) lays the
ring out afresh, keeping IDs where it can. Single bays and piers can still be
added, removed and moved by hand afterwards; the layout then keeps only the
count, since its outline no longer describes the ring.

Rooms can be joined: design["connections"] pairs a bay of one room with a bay
of another, and the two then share that bay's two piers and its arch (a
portal). Each room still has its own ring, crown and IDs. `add_room_from_bay`
grows a new room out of an open bay.

A room's crown is a point (`centre_m`) or, for a long room, a straight line
(`spine_m`, two plan points). Bearings round the crown and distances from it
are measured the same way for both: see bower/spine.py.

Pure Python (no bpy). Lengths are metres; plan positions are [x, y] with Y north.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

from .spine import crown_spine

BAY_TYPES_GENERATED = ("open", "portal")  # portal: shared with another room. lattice / partly_closed arrive with the wall face
TWO_PI = 2.0 * math.pi


class DesignError(ValueError):
    """The design is not a valid plan graph, or an edit would make it invalid."""


# --- lookup -----------------------------------------------------------------


def get_room(design: dict, room_id: str) -> dict:
    for room in design["rooms"]:
        if room["id"] == room_id:
            return room
    raise DesignError(f"no room {room_id!r}")


def get_pier(room: dict, pier_id: str) -> dict:
    for pier in room["piers"]:
        if pier["id"] == pier_id:
            return pier
    raise DesignError(f"no pier {pier_id!r} in room {room['id']!r}")


def get_bay(room: dict, bay_id: str) -> dict:
    for bay in room["bays"]:
        if bay["id"] == bay_id:
            return bay
    raise DesignError(f"no bay {bay_id!r} in room {room['id']!r}")


def find(design: dict, kind: str, element_id: str) -> tuple[dict, dict]:
    for room in design["rooms"]:
        for element in room[kind]:
            if element["id"] == element_id:
                return room, element
    raise DesignError(f"no {kind[:-1]} {element_id!r} in the design")


# --- plan geometry of a bay ---------------------------------------------------


def chord_frame(room: dict, bay: dict):
    """A bay's chord in plan: midpoint, unit direction, outward unit normal and half-length."""
    a = get_pier(room, bay["from"])["position_m"]
    b = get_pier(room, bay["to"])["position_m"]
    dx, dy = b[0] - a[0], b[1] - a[1]
    half = math.hypot(dx, dy) / 2.0
    along = (dx / (2.0 * half), dy / (2.0 * half))
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0), along, (along[1], -along[0]), half


def apex_point(room: dict, bay: dict) -> tuple[float, float, float]:
    """World position of a bay's apex handle.

    The apex is stored relative to its chord (a shift along it as a fraction of
    the half-chord, an outward offset and a height), so it follows its piers.
    """
    mid, along, outward, half = chord_frame(room, bay)
    s, o = bay["apex_shift"] * half, bay["apex_out_m"]
    return (
        mid[0] + s * along[0] + o * outward[0],
        mid[1] + s * along[1] + o * outward[1],
        room["floor_z_m"] + bay["apex_height_m"],
    )


def apex_params(room: dict, bay: dict, point) -> dict:
    """The inverse of `apex_point`: chord-relative parameters for a dragged apex handle."""
    mid, along, outward, half = chord_frame(room, bay)
    dx, dy = point[0] - mid[0], point[1] - mid[1]
    return {
        "apex_shift": (dx * along[0] + dy * along[1]) / half,
        "apex_out_m": dx * outward[0] + dy * outward[1],
        "apex_height_m": point[2] - room["floor_z_m"],
    }


def _ring_point(room: dict, bay: dict, fraction: float) -> list[float]:
    """A plan point `fraction` of the way along a bay, pushed out to the distance from the crown
    its two piers suggest."""
    a = get_pier(room, bay["from"])["position_m"]
    b = get_pier(room, bay["to"])["position_m"]
    spine = crown_spine(room["crown"])
    x, y = a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction
    ra, rb = spine.locate(a)[1], spine.locate(b)[1]
    (fx, fy), (ux, uy) = spine.frame(spine.locate((x, y))[0])
    distance = ra + (rb - ra) * fraction
    return [round(fx + ux * distance, 4), round(fy + uy * distance, 4)]


# --- connections: two rooms that share a bay's arch ------------------------------------------
#
# design["connections"] is a list of {"id": "C1", "bays": [bay of one room, bay of another]}.
# The two bays are the same opening seen from either side: they stand on the same two piers,
# have the same apex, and both have the type "portal". Each room keeps its own ring, crown and
# roof, and its own IDs: the piers the two rings share are two IDs for one pier. The first bay a
# connection names owns the arch: its room builds the one arch the two rooms share.

ARCH_KEYS = ("pier_height_m", "pier_radius_m", "arch_shoulder", "arch_point_deg", "arch_reach")  # what gives an arch its curve


def portals(design: dict) -> dict:
    """The bays that are joined to a bay of another room: bay ID -> (connection, the other bay's ID, whether this bay owns the shared arch)."""
    found = {}
    for connection in design.get("connections", []):
        one, other = connection["bays"]
        found[one], found[other] = (connection, other, True), (connection, one, False)
    return found


def same_piers(design: dict) -> dict:
    """The piers that two or more rooms share: pier ID -> the ID that stands for all of them (the first in the design)."""
    rank = {pier["id"]: k for k, pier in enumerate(p for room in design["rooms"] for p in room["piers"])}
    stands_for = {}

    def first(pier_id: str) -> str:
        while stands_for.get(pier_id, pier_id) != pier_id:
            pier_id = stands_for[pier_id]
        return pier_id

    for connection in design.get("connections", []):
        (_, a), (_, b) = (find(design, "bays", bay_id) for bay_id in connection["bays"])
        for one, other in ((a["from"], b["to"]), (a["to"], b["from"])):  # the two rings run opposite ways along the arch
            one, other = sorted((first(one), first(other)), key=rank.__getitem__)
            stands_for.setdefault(one, one)
            if other != one:
                stands_for[other] = one
    return {pier_id: first(pier_id) for pier_id in stands_for}


def joined_rooms(design: dict) -> list[list[str]]:
    """The rooms, in groups that are joined to each other: each group, and the list of groups, in design order."""
    group = {room["id"]: room["id"] for room in design["rooms"]}

    def first(room_id: str) -> str:
        while group[room_id] != room_id:
            room_id = group[room_id]
        return room_id

    for connection in design.get("connections", []):
        a, b = (first(find(design, "bays", bay_id)[0]["id"]) for bay_id in connection["bays"])
        if a != b:
            group[b] = a
    groups = {}
    for room in design["rooms"]:
        groups.setdefault(first(room["id"]), []).append(room["id"])
    return list(groups.values())


def _connection_problems(design: dict) -> list[str]:
    problems, joined = [], set()
    rooms, connections = design["rooms"], design.get("connections", [])
    for kind, elements, key in (("room", rooms, "next_room"), ("connection", connections, "next_connection")):
        ids = [e["id"] for e in elements]
        if len(set(ids)) != len(ids):
            problems.append(f"duplicate {kind} IDs")
        if key in design and any(int(i[1:]) >= design[key] for i in ids):
            problems.append(f"{key} would reissue an existing ID")
    for connection in connections:
        cid = connection["id"]
        try:
            (room_a, a), (room_b, b) = (find(design, "bays", bay_id) for bay_id in connection["bays"])
        except (DesignError, ValueError):
            problems.append(f"{cid}: joins a bay that is not in the design")
            continue
        if room_a is room_b:
            problems.append(f"{cid}: joins two bays of the same room")
            continue
        for bay in (a, b):
            if bay["id"] in joined:
                problems.append(f"{bay['id']}: is joined to more than one room")
            joined.add(bay["id"])
            if bay["type"] != "portal":
                problems.append(f"{bay['id']}: a bay that is joined to another room has the type 'portal'")
        ends_a = [get_pier(room_a, a[k])["position_m"] for k in ("from", "to")]
        ends_b = [get_pier(room_b, b[k])["position_m"] for k in ("to", "from")]
        if max(math.dist(p, q) for p, q in zip(ends_a, ends_b)) > 1e-3:
            problems.append(f"{cid}: {a['id']} and {b['id']} do not stand on the same two piers")
            continue
        if math.dist(apex_point(room_a, a), apex_point(room_b, b)) > 1e-3:
            problems.append(f"{cid}: {a['id']} and {b['id']} do not share one apex")
        if room_a["floor_z_m"] != room_b["floor_z_m"] or any(room_a["shape"][k] != room_b["shape"][k] for k in ARCH_KEYS):
            problems.append(f"{cid}: {room_a['id']} and {room_b['id']} need the same floor and the same {', '.join(ARCH_KEYS)}, so that the arch they share is one arch")
        # each room keeps to its own side of the arch
        mid, _, outward, _ = chord_frame(room_a, a)

        def beyond(p) -> float:
            return (p[0] - mid[0]) * outward[0] + (p[1] - mid[1]) * outward[1]

        free = [p["position_m"] for p in room_b["piers"] if p["id"] not in (b["from"], b["to"])]
        if min(beyond(p) for p in free + [room_b["crown"]["centre_m"]]) < 0.5 or beyond(room_a["crown"]["centre_m"]) > -0.5:
            problems.append(f"{cid}: {room_b['id']} must lie outside {a['id']}, the bay it is joined through")
        # and the three arches that meet at each shared pier have room to stand
        ring_a, ring_b = [p["id"] for p in room_a["piers"]], [p["id"] for p in room_b["piers"]]
        for here, there, other, step_a, step_b in ((a["from"], b["to"], a["to"], -1, 1), (a["to"], b["from"], a["from"], 1, -1)):
            at = get_pier(room_a, here)["position_m"]
            onward = [
                get_pier(room_a, other)["position_m"],
                room_a["piers"][(ring_a.index(here) + step_a) % len(ring_a)]["position_m"],
                room_b["piers"][(ring_b.index(there) + step_b) % len(ring_b)]["position_m"],
            ]
            ways = [math.atan2(q[1] - at[1], q[0] - at[0]) for q in onward]
            apart = min(abs((ways[i] - ways[j] + math.pi) % TWO_PI - math.pi) for i, j in ((0, 1), (0, 2), (1, 2)))
            if apart < math.radians(40.0):
                problems.append(f"{here}: the arches that meet at this pier need at least 40 degrees between them, and two are {math.degrees(apart):.0f} apart")
    for room in rooms:
        for bay in room["bays"]:
            if bay["type"] == "portal" and bay["id"] not in joined:
                problems.append(f"{bay['id']}: has the type 'portal' but is joined to nothing")
    return problems


# --- validation ---------------------------------------------------------------


def _id_number(element_id: str) -> int:
    return int(element_id.rsplit(".", 1)[1][1:])


def _room_problems(room: dict) -> list[str]:
    rid, piers, bays = room["id"], room["piers"], room["bays"]
    problems = []
    for kind, elements in (("pier", piers), ("bay", bays)):
        ids = [e["id"] for e in elements]
        if len(set(ids)) != len(ids):
            problems.append(f"{rid}: duplicate {kind} IDs")
        if any(_id_number(i) >= room[f"next_{kind}"] for i in ids):
            problems.append(f"{rid}: next_{kind} would reissue an existing ID")
    if len(piers) < 3 or len(bays) != len(piers):
        return problems + [f"{rid}: a room needs at least three piers and one bay per pier"]
    n = len(piers)
    for i, bay in enumerate(bays):
        if (bay["from"], bay["to"]) != (piers[i]["id"], piers[(i + 1) % n]["id"]):
            problems.append(f"{bay['id']}: does not span consecutive piers of the ring")
        if bay["type"] not in BAY_TYPES_GENERATED:
            problems.append(f"{bay['id']}: bay type {bay['type']!r} is not generated yet")
        if bay["apex_height_m"] < room["shape"]["pier_height_m"] + 1.0 or abs(bay["apex_shift"]) >= 0.9:
            problems.append(f"{bay['id']}: apex must stand at least 1 m above the springs, with |apex_shift| below 0.9")
    if problems:
        return problems

    crown = room["crown"]
    shape = room["shape"]
    line = crown.get("spine_m")
    if line is not None:
        if len(line) != 2 or math.dist(line[0], line[1]) < 0.1:
            return problems + [f"{rid}: a crown's spine_m is two plan points at least 0.1 m apart"]
        if math.dist(crown["centre_m"], ((line[0][0] + line[1][0]) / 2.0, (line[0][1] + line[1][1]) / 2.0)) > 1e-3:
            problems.append(f"{rid}: the crown's centre_m must be the middle of its spine_m")
    spine = crown_spine(crown)
    about = "the crown's spine" if spine.length else "the crown centre"
    if crown["radius_m"] <= 0 or crown["radius_m"] > shape["lantern_radius_m"] - 0.3:
        problems.append(f"{rid}: the crown ring needs a positive radius at least 0.3 m inside the lantern's base ring")
    if crown["height_m"] < 0.0:
        problems.append(f"{rid}: the crown cannot go below the floor")
    # Going round the ring pier, apex, pier, apex ... the bearing round the crown must keep
    # turning counter-clockwise and close after exactly one turn. That makes the footprint simple
    # and keeps groins and ridges from crossing on their way to the crown.
    stops = []
    for pier, bay in zip(piers, bays):
        stops.append((pier["id"], pier["position_m"]))
        stops.append((bay["id"] + " apex", apex_point(room, bay)))
    bearings = []
    for name, p in stops:
        bearing, distance = spine.locate(p)
        if distance < shape["lantern_radius_m"] + 0.8:
            problems.append(f"{name}: lies inside the lantern or within 0.8 m of it")
        bearings.append(bearing)
    total = 0.0
    for k, (name, _) in enumerate(stops):
        step = (bearings[(k + 1) % len(stops)] - bearings[k]) % spine.period
        if not 1e-3 < step < spine.period / 2.0:
            problems.append(f"{name}: out of counter-clockwise order around {about}")
        total += step
    if not problems and abs(total - spine.period) > 1e-6:
        problems.append(f"{rid}: the pier ring does not wind once around {about}")
    return problems


def validate(design: dict) -> None:
    problems = [p for room in design["rooms"] for p in _room_problems(room)]
    if not problems:  # the rooms are sound: now how they are joined
        problems = _connection_problems(design)
    if problems:
        raise DesignError("; ".join(problems))


def load(path) -> dict:
    design = json.loads(Path(path).read_text(encoding="utf-8"))
    validate(design)
    return design


def save(path, design: dict) -> None:
    validate(design)
    Path(path).write_text(json.dumps(design, indent=2) + "\n", encoding="utf-8")


# --- operations -----------------------------------------------------------------


def _change(op: str, added=(), removed=(), modified=()) -> dict:
    return {"op": op, "added": list(added), "removed": list(removed), "modified": list(modified)}


def move_pier(design: dict, pier_id: str, position_m) -> tuple[dict, dict]:
    """Move one pier in plan. The two bays that meet at it follow; nothing else changes.

    A pier that two rooms share moves in both: it is one pier.
    """
    new = copy.deepcopy(design)
    find(new, "piers", pier_id)
    stands_for = same_piers(new)
    moved = [pier_id] + [other for other in stands_for if other != pier_id and stands_for[other] == stands_for.get(pier_id)]
    touched = []
    for one in moved:
        room, pier = find(new, "piers", one)
        pier["position_m"] = [float(position_m[0]), float(position_m[1])]
        _layout_follows(room)
        touched += [b["id"] for b in room["bays"] if one in (b["from"], b["to"])]
    validate(new)
    return new, _change("move_pier", modified=[*moved, *touched])


def set_apex(design: dict, bay_id: str, *, height_m=None, shift=None, out_m=None) -> tuple[dict, dict]:
    """Set any of a bay's apex parameters."""
    new = copy.deepcopy(design)
    room, bay = find(new, "bays", bay_id)
    for key, value in (("apex_height_m", height_m), ("apex_shift", shift), ("apex_out_m", out_m)):
        if value is not None:
            bay[key] = float(value)
    room.get("layout", {}).pop("apex_heights_m", None)  # this apex is now set by hand
    modified = [bay_id]
    if bay_id in portals(new):  # the arch is shared: the other room's bay has the same apex, seen from its own side
        other_room, other = find(new, "bays", portals(new)[bay_id][1])
        other.update({"apex_height_m": bay["apex_height_m"], "apex_shift": -bay["apex_shift"], "apex_out_m": -bay["apex_out_m"]})
        other_room.get("layout", {}).pop("apex_heights_m", None)
        modified.append(other["id"])
    validate(new)
    return new, _change("set_apex", modified=modified)


def set_crown(design: dict, room_id: str, *, height_m=None, radius_m=None, centre_m=None, spine_m=None, section=None) -> tuple[dict, dict]:
    """Set any of a room's crown parameters. Every groin and ridge of the room follows.

    `spine_m` (two plan points) draws the crown out into a line and puts `centre_m` at its middle;
    an empty `spine_m` makes the crown a point again. Moving `centre_m` carries a spine with it.
    `section` sets values of the crown's section (see envelope.lantern_profile), leaving the rest.
    """
    new = copy.deepcopy(design)
    crown = get_room(new, room_id)["crown"]
    if height_m is not None:
        crown["height_m"] = float(height_m)
    if radius_m is not None:
        crown["radius_m"] = float(radius_m)
    if section:
        crown["section"] = {**crown.get("section", {}), **{key: float(value) for key, value in section.items()}}
    if spine_m is not None:
        crown.pop("spine_m", None)
        if len(spine_m):
            (ax, ay), (bx, by) = spine_m
            crown["spine_m"] = [[float(ax), float(ay)], [float(bx), float(by)]]
            crown["centre_m"] = [round((ax + bx) / 2.0, 6), round((ay + by) / 2.0, 6)]
    if centre_m is not None:
        dx, dy = centre_m[0] - crown["centre_m"][0], centre_m[1] - crown["centre_m"][1]
        crown["centre_m"] = [float(centre_m[0]), float(centre_m[1])]
        if "spine_m" in crown:
            crown["spine_m"] = [[round(x + dx, 6), round(y + dy, 6)] for x, y in crown["spine_m"]]
    validate(new)
    return new, _change("set_crown", modified=[room_id + ".crown"])


def add_bay(design: dict, bay_id: str, fraction: float = 0.5) -> tuple[dict, dict]:
    """Split a bay in two by inserting a pier `fraction` of the way along it.

    The split bay keeps its ID and its `from` pier; a new bay with the next free
    ID takes over the `to` pier and inherits the apex parameters.
    """
    new = copy.deepcopy(design)
    room, bay = find(new, "bays", bay_id)
    rid = room["id"]
    if bay["type"] == "portal":
        raise DesignError(f"{bay_id}: is the portal to another room and cannot be split")
    pier = {"id": f"{rid}.P{room['next_pier']}", "position_m": _ring_point(room, bay, fraction)}
    twin = {**copy.deepcopy(bay), "id": f"{rid}.B{room['next_bay']}", "from": pier["id"]}
    bay["to"] = pier["id"]
    room["next_pier"] += 1
    room["next_bay"] += 1
    at = room["bays"].index(bay) + 1
    room["piers"].insert(at, pier)
    room["bays"].insert(at, twin)
    _layout_follows(room)
    validate(new)
    return new, _change("add_bay", added=[pier["id"], twin["id"]], modified=[bay_id])


def remove_bay(design: dict, bay_id: str, merge_at: float = 0.5) -> tuple[dict, dict]:
    """Collapse a bay so that its two piers become one.

    The `from` pier survives under its own ID and moves `merge_at` of the way
    along the removed bay (0 leaves it where it is). The `to` pier is removed and
    the following bay re-attaches to the survivor.
    """
    new = copy.deepcopy(design)
    room, bay = find(new, "bays", bay_id)
    bays = room["bays"]
    if len(bays) <= 3:
        raise DesignError(f"{room['id']}: a room needs at least three bays")
    if bay["type"] == "portal":
        raise DesignError(f"{bay_id}: is the portal to another room; remove that room first")
    i = bays.index(bay)
    before, after = bays[i - 1], bays[(i + 1) % len(bays)]
    survivor, gone = get_pier(room, bay["from"]), get_pier(room, bay["to"])
    modified = [after["id"]]
    if merge_at > 0:
        survivor["position_m"] = list(gone["position_m"]) if merge_at >= 1 else _ring_point(room, bay, merge_at)
        modified = [survivor["id"], before["id"], after["id"]]
    after["from"] = survivor["id"]
    room["piers"].remove(gone)
    bays.remove(bay)
    room["piers"] = [get_pier(room, b["from"]) for b in bays]  # keep pier i at the start of bay i
    _layout_follows(room)
    validate(new)
    return new, _change("remove_bay", removed=[bay_id, gone["id"]], modified=modified)


# --- the layout of the ring: how many bays, on what outline ----------------------------


def _layout_follows(room: dict) -> None:
    """After the ring is changed by hand, the room's layout keeps only the count it now has."""
    if "layout" in room:
        room["layout"] = {"bays": len(room["bays"])}  # its outline and widths no longer describe the ring


def bay_weights(count: int, variation: float = 0.1) -> list[float]:
    """Relative widths for `count` bays: close to equal, never two the same, with no pattern that repeats round the ring."""
    return [round(1.0 + variation * math.cos(TWO_PI * 0.6180339887 * k + 0.9), 3) for k in range(count)]


def outline_radius(outline: dict, bearing: float) -> float:
    """How far the outline lies from its centre at a bearing.

        radius_m              the outline's radius where nothing else acts on it
        stretch               over 1 lengthens it into an oval along `stretch_bearing_deg` (default 1, bearing 0 = east)
        taper                 widens one end of that axis and narrows the other, toward an egg (default 0)
        lobes, lobe_depth     scallops: how many round the ring and how deep, as a fraction of the radius
        lobe_bearing_deg      the bearing of one lobe's crest
    """
    phi = bearing - math.radians(outline.get("stretch_bearing_deg", 0.0))
    b = float(outline["radius_m"])
    a = b * outline.get("stretch", 1.0)
    radius = a * b / math.hypot(b * math.cos(phi), a * math.sin(phi))
    radius *= 1.0 + outline.get("taper", 0.0) * math.cos(phi)
    if outline.get("lobes"):
        radius *= 1.0 + outline.get("lobe_depth", 0.0) * math.cos(outline["lobes"] * (bearing - math.radians(outline.get("lobe_bearing_deg", 0.0))))
    return radius


def _round_the_ring(samples: list, bearing: float, period: float = TWO_PI) -> float:
    """A value read off (bearing, value) samples round the crown, between the two samples either side of `bearing`."""
    ordered = sorted((b % period, v) for b, v in samples)
    ordered = [(ordered[-1][0] - period, ordered[-1][1]), *ordered, (ordered[0][0] + period, ordered[0][1])]
    bearing %= period
    for (b0, v0), (b1, v1) in zip(ordered, ordered[1:]):
        if b0 <= bearing <= b1:
            return v0 + (v1 - v0) * (bearing - b0) / max(b1 - b0, 1e-12)
    return ordered[0][1]


LAYOUT_KEYS = ("bays", "bay_weights", "outline", "apex_heights_m")


def set_layout(design: dict, room_id: str, _op: str = "set_layout", **changes) -> tuple[dict, dict]:
    """Change a room's layout and lay its ring out afresh from it.

    The layout is room["layout"]; `changes` sets any of its keys (None removes one):

        bays              how many bays
        bay_weights       their relative widths, in ring order (default: close to equal, never two the same)
        outline           for a room joined to another: {"radius_m": r, "through": connection ID}, a circle
                          of that radius through the two piers of its portal. The portal stays where
                          it is, the other bays share out the rest of the circle (`bay_weights` then
                          has one weight fewer than there are bays), and when the radius changes the
                          crown moves with the circle's centre. Otherwise:
                          the plan outline the piers stand on, as `outline_radius` reads it, with an
                          optional `centre_m` (default: the crown's centre). Without an outline the
                          piers stand on the outline the room has now. Round a spine the outline
                          is set off from the spine: at each bearing it stands as far from the
                          spine as the outline's radius in the direction that bearing faces, so a
                          plain `radius_m` gives two straight sides and two round ends.
        apex_heights_m    one apex height for every bay, or a list used in turn round the ring.
                          Without it each bay takes the height the present bays have at its bearing.

    The first pier stands where the room's first pier stands now (as a bearing from the centre),
    the rest are spaced round by the bay weights: by angle round a point crown, by distance along
    the outline round a spine. The first piers and bays keep their IDs, in ring order; extra ones
    get new IDs; with fewer bays the surplus IDs are retired.
    """
    unknown = set(changes) - set(LAYOUT_KEYS)
    if unknown:
        raise DesignError(f"{room_id}: unknown layout keys {sorted(unknown)}")
    new = copy.deepcopy(design)
    room = get_room(new, room_id)
    rid, spine = room["id"], crown_spine(room["crown"])
    cx, cy = room["crown"]["centre_m"]
    layout = {**room.get("layout", {})}
    for key, value in changes.items():
        if value is None:
            layout.pop(key, None)
        else:
            layout[key] = copy.deepcopy(value)
    if (layout.get("outline") or {}).get("through"):
        return _lay_through(new, room, layout, changes, _op)
    if any(bay["type"] == "portal" for bay in room["bays"]):
        raise DesignError(f"{rid}: is joined to another room, so its ring cannot be laid out afresh: edit it bay by bay, or give it layout.outline with `through`")
    count = layout.get("bays", len(room["bays"]))
    if int(count) != count or count < 3:
        raise DesignError(f"{rid}: a room needs a whole number of bays, three or more")
    count = int(count)
    weights = layout.get("bay_weights")
    weights = [float(w) for w in weights] if weights and (len(weights) == count or "bay_weights" in changes) else bay_weights(count)
    if len(weights) != count or min(weights) <= 0.0:
        raise DesignError(f"{rid}: {count} bays need {count} positive bay weights")

    old_piers, old_bays = [p["id"] for p in room["piers"]], [b["id"] for b in room["bays"]]
    outline = layout.get("outline")
    first = room["piers"][0]["position_m"]
    if outline and outline.get("radius_m", 0.0) <= 0.0:
        raise DesignError(f"{rid}: an outline needs a positive radius_m")
    if spine.length:
        if outline:
            if "centre_m" in outline:
                raise DesignError(f"{rid}: round a spine the outline is measured from the spine, and takes no centre_m")
            reach = float(outline["radius_m"])  # piers are spaced by distance along the plain curve this far from the spine
            if "first_pier_turn" not in outline:  # fixed once, as a share of the way round from bearing 0
                outline["first_pier_turn"] = round(spine.arc(0.0, spine.locate(first)[0], reach) / spine.perimeter(reach), 4)
            at = spine.along(outline["first_pier_turn"] * spine.perimeter(reach), reach)

            def radius_at(bearing: float) -> float:
                away = spine.frame(bearing)[1]
                return outline_radius(outline, math.atan2(away[1], away[0]))

        else:
            present = [spine.locate(p["position_m"]) for p in room["piers"]]
            reach, at = sum(distance for _, distance in present) / len(present), present[0][0]

            def radius_at(bearing: float) -> float:
                return _round_the_ring(present, bearing, spine.period)

        def place(bearing: float) -> list:
            (fx, fy), (ux, uy) = spine.frame(bearing)
            radius = radius_at(bearing)
            return [round(fx + ux * radius, 3), round(fy + uy * radius, 3)]

        def onward(bearing: float, weight: float, total: float) -> float:
            return spine.shift(bearing, spine.perimeter(reach) * weight / total, reach)

    elif outline:
        ox, oy = outline.get("centre_m", (cx, cy))
        if "first_pier_bearing_deg" not in outline:  # fixed once, so the same layout always gives the same ring
            outline["first_pier_bearing_deg"] = round(math.degrees(math.atan2(first[1] - oy, first[0] - ox)), 3)
        at = math.radians(outline["first_pier_bearing_deg"])

        def radius_at(bearing: float) -> float:
            return outline_radius(outline, bearing)

    else:
        ox, oy = cx, cy
        present = [(math.atan2(p["position_m"][1] - cy, p["position_m"][0] - cx), math.hypot(p["position_m"][0] - cx, p["position_m"][1] - cy)) for p in room["piers"]]
        at = present[0][0]

        def radius_at(bearing: float) -> float:
            return _round_the_ring(present, bearing)

    if not spine.length:

        def place(bearing: float) -> list:
            radius = radius_at(bearing)
            return [round(ox + radius * math.cos(bearing), 3), round(oy + radius * math.sin(bearing), 3)]

        def onward(bearing: float, weight: float, total: float) -> float:
            return bearing + TWO_PI * weight / total

    heights = [(spine.locate(apex_point(room, b))[0], b["apex_height_m"]) for b in room["bays"]]
    given = layout.get("apex_heights_m")
    given = [float(given)] if isinstance(given, (int, float)) else ([float(h) for h in given] if given else None)

    def issue(kind: str, letter: str, old: list, k: int) -> str:
        if k < len(old):
            return old[k]
        room[f"next_{kind}"] += 1
        return f"{rid}.{letter}{room[f'next_{kind}'] - 1}"

    total = sum(weights)
    piers = []
    for k, weight in enumerate(weights):
        piers.append({"id": issue("pier", "P", old_piers, k), "position_m": place(at)})
        at = onward(at, weight, total)
    bays = []
    for k in range(count):
        a, b = piers[k]["position_m"], piers[(k + 1) % count]["position_m"]
        middle = spine.locate(((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0))[0]
        height = given[k % len(given)] if given else round(_round_the_ring(heights, middle, spine.period), 2)
        bays.append({"id": issue("bay", "B", old_bays, k), "from": piers[k]["id"], "to": piers[(k + 1) % count]["id"], "type": "open", "apex_height_m": height, "apex_shift": 0.0, "apex_out_m": 0.0})
    room["piers"], room["bays"] = piers, bays
    room["layout"] = {**layout, "bays": count, "bay_weights": weights}
    validate(new)
    return new, _change(
        _op,
        added=[p["id"] for p in piers[len(old_piers) :]] + [b["id"] for b in bays[len(old_bays) :]],
        removed=old_piers[count:] + old_bays[count:],
        modified=old_piers[:count] + old_bays[:count],
    )


def set_bay_count(design: dict, room_id: str, count: int, weights=None) -> tuple[dict, dict]:
    """Lay a room's ring out afresh with `count` bays, keeping its outline and apex heights. See `set_layout`."""
    return set_layout(design, room_id, "set_bay_count", bays=count, bay_weights=weights)


def reconcile(design: dict) -> tuple[dict, list]:
    """Bring each room's ring into line with its layout.

    room["layout"] is edited by hand: the number of bays, and optionally an outline and apex
    heights. Where the ring no longer matches (a different count, or piers and heights that are
    not what the outline and heights give), it is laid out afresh with `set_layout`. Returns
    the design and the change records (empty when nothing had to move).
    """
    changes = []
    for room in list(design["rooms"]):
        layout = room.get("layout")
        if not layout:
            continue
        stale = layout.get("bays", len(room["bays"])) != len(room["bays"])
        if not stale and ("outline" in layout or "apex_heights_m" in layout):
            laid = get_room(set_layout(design, room["id"])[0], room["id"])
            stale = [p["position_m"] for p in laid["piers"]] != [p["position_m"] for p in room["piers"]] if "outline" in layout else False
            stale = stale or ("apex_heights_m" in layout and [b["apex_height_m"] for b in laid["bays"]] != [b["apex_height_m"] for b in room["bays"]])
        if stale:
            design, change = set_layout(design, room["id"])
            changes.append(change)
    return design, changes


# --- rooms joined to rooms ------------------------------------------------------------------


def _ring_through(p0, p1, radius: float, weights: list) -> tuple:
    """A ring on a circle through two piers: the circle's centre, and the plan positions of the piers after them.

    The ring runs counter-clockwise from p0 to p1 (the short way, along the portal) and on round
    the rest of the circle, which `weights` shares out between the remaining bays.
    """
    chord = math.dist(p0, p1)
    dx, dy = (p1[0] - p0[0]) / chord, (p1[1] - p0[1]) / chord
    rise = math.sqrt(max(radius * radius - chord * chord / 4.0, 0.0))
    cx, cy = (p0[0] + p1[0]) / 2.0 - dy * rise, (p0[1] + p1[1]) / 2.0 + dx * rise  # to the left of p0 -> p1
    start = math.atan2(p1[1] - cy, p1[0] - cx)
    span = TWO_PI - 2.0 * math.asin(min(1.0, chord / (2.0 * radius)))
    places, gone, total = [], 0.0, sum(weights)
    for weight in weights[:-1]:
        gone += weight
        at = start + span * gone / total
        places.append([round(cx + radius * math.cos(at), 3), round(cy + radius * math.sin(at), 3)])
    return (cx, cy), places


def _lay_through(new: dict, room: dict, layout: dict, changes: dict, op: str) -> tuple[dict, dict]:
    """Lay a joined room's ring out on a circle through the two piers of its portal (see `set_layout`)."""
    rid, outline = room["id"], layout["outline"]
    connection = next((c for c in new.get("connections", []) if c["id"] == outline["through"]), None)
    portal = next((bay for bay in room["bays"] if connection and bay["id"] in connection["bays"]), None)
    if portal is None:
        raise DesignError(f"{rid}: layout.outline.through names {outline['through']!r}, which is not a connection of this room")
    if sum(bay["type"] == "portal" for bay in room["bays"]) != 1:
        raise DesignError(f"{rid}: a ring laid out through one portal cannot have a second portal")
    count = layout.get("bays", len(room["bays"]))
    if int(count) != count or count < 3:
        raise DesignError(f"{rid}: a room needs a whole number of bays, three or more")
    count = int(count)
    weights = layout.get("bay_weights")
    weights = [float(w) for w in weights] if weights and (len(weights) == count - 1 or "bay_weights" in changes) else bay_weights(count - 1)
    if len(weights) != count - 1 or min(weights) <= 0.0:
        raise DesignError(f"{rid}: {count} bays, one of them the portal, need {count - 1} positive bay weights")

    k = room["bays"].index(portal)  # the ring, read from the portal round
    old_bays = room["bays"][k:] + room["bays"][:k]
    old_piers = [get_pier(room, bay["from"]) for bay in old_bays]
    p0, p1 = old_piers[0]["position_m"], old_piers[1]["position_m"]
    radius, chord = float(outline["radius_m"]), math.dist(p0, p1)
    if radius < chord / 2.0 + 0.05:
        raise DesignError(f"{rid}: a circle through its portal needs a radius over {chord / 2.0 + 0.05:.2f} m")
    centre, places = _ring_through(p0, p1, radius, weights)
    was = (room.get("layout", {}).get("outline") or {})
    if was.get("through") == outline["through"] and was.get("radius_m", radius) != radius:  # resized: the crown goes with the circle's centre
        before = _ring_through(p0, p1, float(was["radius_m"]), [1.0, 1.0])[0]
        crown = room["crown"]
        dx, dy = centre[0] - before[0], centre[1] - before[1]
        crown["centre_m"] = [round(crown["centre_m"][0] + dx, 3), round(crown["centre_m"][1] + dy, 3)]
        if "spine_m" in crown:
            crown["spine_m"] = [[round(x + dx, 6), round(y + dy, 6)] for x, y in crown["spine_m"]]

    given = layout.get("apex_heights_m")
    given = [float(given)] if isinstance(given, (int, float)) else ([float(h) for h in given] if given else None)
    kept = [bay["apex_height_m"] for bay in old_bays[1:]]

    def issue(kind: str, letter: str, old: list, n: int) -> str:
        if n < len(old):
            return old[n]["id"]
        room[f"next_{kind}"] += 1
        return f"{rid}.{letter}{room[f'next_{kind}'] - 1}"

    piers = old_piers[:2] + [{"id": issue("pier", "P", old_piers, n + 2), "position_m": place} for n, place in enumerate(places)]
    bays = [portal]
    for n in range(1, count):
        height = given[(n - 1) % len(given)] if given else kept[min(n - 1, len(kept) - 1)]
        bays.append({"id": issue("bay", "B", old_bays, n), "from": piers[n]["id"], "to": piers[(n + 1) % count]["id"], "type": "open", "apex_height_m": height, "apex_shift": 0.0, "apex_out_m": 0.0})
    room["piers"], room["bays"] = piers, bays
    room["layout"] = {**layout, "bays": count, "bay_weights": weights}
    validate(new)
    old_pier_ids, old_bay_ids = [p["id"] for p in old_piers], [b["id"] for b in old_bays]
    return new, _change(
        op,
        added=[p["id"] for p in piers[len(old_piers) :]] + [b["id"] for b in bays[len(old_bays) :]],
        removed=old_pier_ids[count:] + old_bay_ids[count:],
        modified=old_pier_ids[2:count] + old_bay_ids[1:count] + [rid + ".crown"],
    )


def add_room_from_bay(design: dict, bay_id: str, *, bays: int = 6, radius_m=None, weights=None, apex_height_m=None, crown=None, shape=None, timber=None) -> tuple[dict, dict]:
    """Add a room on the outside of an open bay, joined to it: the bay becomes the portal between the two.

    The new room's ring passes through the bay's two piers and runs round a circle on the bay's
    outer side. `radius_m` is that circle's radius (default: the one that makes the portal one of
    `bays` equal bays). The new room has its own ID, piers, bays and crown, and can be edited on
    its own; its size is room["layout"]["outline"]["radius_m"], so `set_layout` (or the file,
    then `reconcile`) resizes it.

    Its shape and crown start as the host room's, scaled to its size; `shape`, `crown` and
    `apex_height_m` (one height, or a list for its free bays) override them. The values that give
    an arch its curve (ARCH_KEYS) stay the host's, so that the shared arch is one arch. `timber`
    sets the room's own lattice, hoop and pier settings (see bower/timber.py).
    """
    new = copy.deepcopy(design)
    host, bay = find(new, "bays", bay_id)
    if bay["type"] != "open":
        raise DesignError(f"{bay_id}: only an open bay can become the portal to a new room")
    count = int(bays)
    if count != bays or count < 3:
        raise DesignError("a room needs a whole number of bays, three or more")
    numbers = {}
    for key, letter, elements in (("next_room", "R", new["rooms"]), ("next_connection", "C", new.get("connections", []))):
        numbers[letter] = new.get(key, 1 + max((int(e["id"][1:]) for e in elements), default=0))
        new[key] = numbers[letter] + 1
    rid, cid = f"R{numbers['R']}", f"C{numbers['C']}"

    # the new room's ring runs the other way along the shared arch
    p0, p1 = list(get_pier(host, bay["to"])["position_m"]), list(get_pier(host, bay["from"])["position_m"])
    chord = math.dist(p0, p1)
    radius = float(radius_m) if radius_m is not None else round(chord / (2.0 * math.sin(math.pi / count)), 3)
    if radius < chord / 2.0 + 0.05:
        raise DesignError(f"{rid}: a circle through {bay_id} needs a radius over {chord / 2.0 + 0.05:.2f} m")
    weights = [float(w) for w in weights] if weights else bay_weights(count - 1)
    if len(weights) != count - 1 or min(weights) <= 0.0:
        raise DesignError(f"{rid}: {count} bays, one of them the portal, need {count - 1} positive bay weights")
    centre, places = _ring_through(p0, p1, radius, weights)

    spine = crown_spine(host["crown"])
    scale = radius * len(host["piers"]) / sum(spine.locate(p["position_m"])[1] for p in host["piers"])  # its size beside the host's
    host_shape, host_crown = host["shape"], host["crown"]
    room_shape = copy.deepcopy(host_shape)
    for key in ("lantern_radius_m", "fan_radius_m", "pier_funnel_m"):
        room_shape[key] = round(host_shape[key] * scale, 2)
    room_shape.update(copy.deepcopy(shape or {}))
    room_crown = {
        "centre_m": [round(centre[0], 3), round(centre[1], 3)],
        "height_m": round(room_shape["lantern_base_height_m"] + (host_crown["height_m"] - host_shape["lantern_base_height_m"]) * scale, 2),
        "radius_m": round(host_crown["radius_m"] * scale, 2),
    }
    if "section" in host_crown:
        room_crown["section"] = copy.deepcopy(host_crown["section"])
    room_crown.update(copy.deepcopy(crown or {}))

    heights = apex_height_m if apex_height_m is not None else round(bay["apex_height_m"] - 0.3, 2)
    heights = [float(heights)] if isinstance(heights, (int, float)) else [float(h) for h in heights]
    piers = [{"id": f"{rid}.P1", "position_m": p0}, {"id": f"{rid}.P2", "position_m": p1}] + [{"id": f"{rid}.P{n + 3}", "position_m": place} for n, place in enumerate(places)]
    ring = [{"id": f"{rid}.B1", "from": piers[0]["id"], "to": piers[1]["id"], "type": "portal", "apex_height_m": bay["apex_height_m"], "apex_shift": -bay["apex_shift"], "apex_out_m": -bay["apex_out_m"]}]
    for n in range(1, count):
        ring.append({"id": f"{rid}.B{n + 1}", "from": piers[n]["id"], "to": piers[(n + 1) % count]["id"], "type": "open", "apex_height_m": heights[(n - 1) % len(heights)], "apex_shift": 0.0, "apex_out_m": 0.0})
    room = {
        "id": rid,
        "floor_z_m": host["floor_z_m"],
        "crown": room_crown,
        "shape": room_shape,
        "piers": piers,
        "bays": ring,
        "next_pier": count + 1,
        "next_bay": count + 1,
        "layout": {"bays": count, "bay_weights": weights, "outline": {"radius_m": radius, "through": cid}},
    }
    if timber:
        room["timber"] = copy.deepcopy(timber)
    bay["type"] = "portal"
    _layout_follows(host)  # the host's ring is now tied to its neighbour: it is edited bay by bay
    new["rooms"].append(room)
    new.setdefault("connections", []).append({"id": cid, "bays": [bay_id, ring[0]["id"]]})
    validate(new)
    return new, _change("add_room_from_bay", added=[rid, cid, *(p["id"] for p in piers), *(b["id"] for b in ring)], modified=[bay_id])


def remove_room(design: dict, room_id: str) -> tuple[dict, dict]:
    """Take a room out of the design. The bays of other rooms that were portals to it are open bays again."""
    new = copy.deepcopy(design)
    room = get_room(new, room_id)
    if len(new["rooms"]) == 1:
        raise DesignError("a design needs at least one room")
    mine = {bay["id"] for bay in room["bays"]}
    gone = [c for c in new.get("connections", []) if mine & set(c["bays"])]
    opened = []
    for connection in gone:
        for bay_id in set(connection["bays"]) - mine:
            find(new, "bays", bay_id)[1]["type"] = "open"
            opened.append(bay_id)
    new["connections"] = [c for c in new.get("connections", []) if c not in gone]
    new["rooms"].remove(room)
    validate(new)
    return new, _change("remove_room", removed=[room_id, *(c["id"] for c in gone)], modified=sorted(opened))


# --- whole-room adjustments: the operations behind the sliders ----------------------------------


def set_shape(design: dict, room_id: str, **values) -> tuple[dict, dict]:
    """Set any of a room's shape parameters (room["shape"]).

    The values that give an arch its curve (ARCH_KEYS) are set in every room joined to this one
    as well, so that the arches they share stay one arch.
    """
    new = copy.deepcopy(design)
    room = get_room(new, room_id)
    unknown = sorted(set(values) - set(room["shape"]) - {"ridge_soften"})
    if unknown:
        raise DesignError(f"{room_id}: no shape parameters called {', '.join(unknown)}")
    together = next(group for group in joined_rooms(new) if room_id in group) if set(values) & set(ARCH_KEYS) else [room_id]
    for other_id in together:
        other = get_room(new, other_id)
        for key, value in values.items():
            if other_id == room_id or key in ARCH_KEYS:
                other["shape"][key] = float(value)
    validate(new)
    return new, _change("set_shape", modified=[other_id + ".shape" for other_id in together])


def scale_room(design: dict, room_id: str, factor: float) -> tuple[dict, dict]:
    """Make a room larger or smaller about its crown: every pier `factor` times as far from it.

    A ring laid out on an outline is resized through the outline (its radius is scaled and the
    ring laid out afresh), which is also how a room grown out of a bay is resized. Any other
    ring has its piers moved. A room that is joined to another and has no outline of its own
    cannot be resized without moving its neighbour, and is refused.
    """
    room = get_room(design, room_id)
    if factor <= 0.0:
        raise DesignError(f"{room_id}: a room is scaled by a positive factor")
    outline = (room.get("layout") or {}).get("outline")
    if outline and "radius_m" in outline:
        return set_layout(design, room_id, "scale_room", outline={**outline, "radius_m": round(outline["radius_m"] * factor, 3)})
    if any(bay["type"] == "portal" for bay in room["bays"]):
        raise DesignError(f"{room_id}: is joined to another room and has no outline of its own, so it cannot be resized without moving its neighbour")
    new = copy.deepcopy(design)
    room = get_room(new, room_id)
    spine = crown_spine(room["crown"])
    for pier in room["piers"]:
        bearing, distance = spine.locate(pier["position_m"])
        (fx, fy), (ux, uy) = spine.frame(bearing)
        pier["position_m"] = [round(fx + ux * distance * factor, 3), round(fy + uy * distance * factor, 3)]
    validate(new)
    return new, _change("scale_room", modified=[p["id"] for p in room["piers"]] + [b["id"] for b in room["bays"]])


def set_spine(design: dict, room_id: str, length_m: float, heading_deg=None) -> tuple[dict, dict]:
    """Draw a room's crown out into a spine of this length (under 0.1 m: a point again), and lay its ring out round it.

    The spine keeps the crown's centre and runs along `heading_deg` (default: the way it runs
    now, or east-west). A room that is joined to nothing has its ring laid out afresh on the
    outline at its present distance from the crown, so a round room becomes a hall with two
    straight sides and back again. A joined room keeps its ring, which must already suit the
    spine.
    """
    new = copy.deepcopy(design)
    room = get_room(new, room_id)
    crown = room["crown"]
    before = crown_spine(crown)
    reach = sum(before.locate(p["position_m"])[1] for p in room["piers"]) / len(room["piers"])
    if heading_deg is None:
        heading = math.atan2(before.u[1], before.u[0]) if before.length else 0.0
    else:
        heading = math.radians(heading_deg)
    cx, cy = crown["centre_m"]
    crown.pop("spine_m", None)
    if length_m >= 0.1:
        ux, uy = math.cos(heading) * length_m / 2.0, math.sin(heading) * length_m / 2.0
        crown["spine_m"] = [[round(cx - ux, 4), round(cy - uy, 4)], [round(cx + ux, 4), round(cy + uy, 4)]]
    if any(bay["type"] == "portal" for bay in room["bays"]):
        validate(new)
        return new, _change("set_spine", modified=[room_id + ".crown"])
    outline = dict((room.get("layout") or {}).get("outline") or {"radius_m": round(reach, 2)})
    laid, change = set_layout(new, room_id, "set_spine", outline=outline)
    return laid, {**change, "modified": [room_id + ".crown", *change["modified"]]}
