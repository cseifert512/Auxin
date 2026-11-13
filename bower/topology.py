"""Level A: the plan graph that everything else is generated from.

A room is a counter-clockwise ring of piers. Each bay spans two consecutive
piers and names them by ID, so the ring order and the bay endpoints check each
other. IDs come from per-room counters that only count up: an ID is never
reused, and no edit renumbers anything else.

Operations are pure. Each returns a new, validated design and a record of what
it added, removed and modified; the design passed in is left untouched, so a
rejected edit costs nothing.

Pure Python (no bpy). Lengths are metres; plan positions are [x, y] with Y north.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

BAY_TYPES_GENERATED = ("open",)  # lattice / partly_closed / portal arrive with the wall face
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
    """A plan point `fraction` of the way along a bay, pushed out to the radius its two piers
    suggest, measured from the crown centre."""
    a = get_pier(room, bay["from"])["position_m"]
    b = get_pier(room, bay["to"])["position_m"]
    cx, cy = room["crown"]["centre_m"]
    x, y = a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction
    ra, rb = math.hypot(a[0] - cx, a[1] - cy), math.hypot(b[0] - cx, b[1] - cy)
    scale = (ra + (rb - ra) * fraction) / math.hypot(x - cx, y - cy)
    return [round(cx + (x - cx) * scale, 4), round(cy + (y - cy) * scale, 4)]


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
        if bay["apex_height_m"] < room["shape"]["eave_height_m"] + 0.3 or abs(bay["apex_shift"]) >= 0.9:
            problems.append(f"{bay['id']}: apex must stand at least 0.3 m above the eave, with |apex_shift| below 0.9")
    if problems:
        return problems

    crown = room["crown"]
    cx, cy = crown["centre_m"]
    if crown["radius_m"] <= 0 or crown["height_m"] < room["shape"]["eave_height_m"] + 0.5:
        problems.append(f"{rid}: crown needs a positive radius and must stand at least 0.5 m above the eave")
    if room["shape"]["eave_height_m"] < room["shape"]["pier_height_m"] + 0.3:
        problems.append(f"{rid}: the eave must stand at least 0.3 m above the springs")
    # Going round the ring pier, apex, pier, apex ... the bearing from the crown centre must keep
    # turning counter-clockwise and close after exactly one turn. That makes the footprint simple
    # and keeps groins and ridges from crossing on their way to the crown.
    stops = []
    for pier, bay in zip(piers, bays):
        stops.append((pier["id"], pier["position_m"]))
        stops.append((bay["id"] + " apex", apex_point(room, bay)))
    bearings = []
    for name, p in stops:
        if math.hypot(p[0] - cx, p[1] - cy) < crown["radius_m"] + 0.1:
            problems.append(f"{name}: lies inside or on the crown ring")
        bearings.append(math.atan2(p[1] - cy, p[0] - cx))
    total = 0.0
    for k, (name, _) in enumerate(stops):
        step = (bearings[(k + 1) % len(stops)] - bearings[k]) % TWO_PI
        if not 1e-3 < step < math.pi:
            problems.append(f"{name}: out of counter-clockwise order around the crown centre")
        total += step
    if not problems and abs(total - TWO_PI) > 1e-6:
        problems.append(f"{rid}: the pier ring does not wind once around the crown centre")
    return problems


def validate(design: dict) -> None:
    problems = [p for room in design["rooms"] for p in _room_problems(room)]
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
    """Move one pier in plan. The two bays that meet at it follow; nothing else changes."""
    new = copy.deepcopy(design)
    room, pier = find(new, "piers", pier_id)
    pier["position_m"] = [float(position_m[0]), float(position_m[1])]
    validate(new)
    touched = [b["id"] for b in room["bays"] if pier_id in (b["from"], b["to"])]
    return new, _change("move_pier", modified=[pier_id, *touched])


def set_apex(design: dict, bay_id: str, *, height_m=None, shift=None, out_m=None) -> tuple[dict, dict]:
    """Set any of a bay's apex parameters."""
    new = copy.deepcopy(design)
    _, bay = find(new, "bays", bay_id)
    for key, value in (("apex_height_m", height_m), ("apex_shift", shift), ("apex_out_m", out_m)):
        if value is not None:
            bay[key] = float(value)
    validate(new)
    return new, _change("set_apex", modified=[bay_id])


def set_crown(design: dict, room_id: str, *, height_m=None, radius_m=None, centre_m=None) -> tuple[dict, dict]:
    """Set any of a room's crown parameters. Every groin and ridge of the room follows."""
    new = copy.deepcopy(design)
    crown = get_room(new, room_id)["crown"]
    if height_m is not None:
        crown["height_m"] = float(height_m)
    if radius_m is not None:
        crown["radius_m"] = float(radius_m)
    if centre_m is not None:
        crown["centre_m"] = [float(centre_m[0]), float(centre_m[1])]
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
    pier = {"id": f"{rid}.P{room['next_pier']}", "position_m": _ring_point(room, bay, fraction)}
    twin = {**copy.deepcopy(bay), "id": f"{rid}.B{room['next_bay']}", "from": pier["id"]}
    bay["to"] = pier["id"]
    room["next_pier"] += 1
    room["next_bay"] += 1
    at = room["bays"].index(bay) + 1
    room["piers"].insert(at, pier)
    room["bays"].insert(at, twin)
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
    validate(new)
    return new, _change("remove_bay", removed=[bay_id, gone["id"]], modified=modified)
