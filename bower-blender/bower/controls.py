"""What can be adjusted about a room with a slider: one entry per control.

Each control reads a value from a design and returns a new design with that value changed,
always through the operations in bower/topology.py, so an adjustment is checked exactly as a
hand edit of the design file is. A control that cannot be used on a room as it stands says why.

No bpy here: bower/blender_ui.py draws these as sliders, tests/test_controls.py checks them.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable

from . import topology as T
from .spine import crown_spine

HOOP_DISTANCES_M = (0.5, 1.0, 1.5)  # how far inside its arch each hoop runs, nearest first


@dataclass(frozen=True)
class Control:
    key: str
    label: str
    group: str
    kind: str  # "length" (metres), "angle" (degrees) or "count"
    lo: float
    hi: float
    step: float
    get: Callable  # (design, room) -> value
    set: Callable  # (design, room ID, value) -> design
    tip: str = ""
    blocked: Callable = lambda design, room: ""  # why it cannot be used on this room, or ""


def _joined(room: dict) -> bool:
    return any(bay["type"] == "portal" for bay in room["bays"])


def _outline(room: dict) -> dict:
    return (room.get("layout") or {}).get("outline") or {}


def _reach(room: dict) -> float:
    """How far from its crown a room's piers stand: its outline's radius, or their mean distance."""
    if "radius_m" in _outline(room):
        return _outline(room)["radius_m"]
    spine = crown_spine(room["crown"])
    return sum(spine.locate(p["position_m"])[1] for p in room["piers"]) / len(room["piers"])


def _resize(design: dict, room_id: str, radius: float) -> dict:
    return T.scale_room(design, room_id, radius / _reach(T.get_room(design, room_id)))[0]


def _count_bays(design: dict, room_id: str, count: int) -> dict:
    if _outline(T.get_room(design, room_id)).get("through"):
        return T.set_layout(design, room_id, bays=int(count), bay_weights=None)[0]
    return T.set_bay_count(design, room_id, int(count))[0]


def _raise_arches(design: dict, room_id: str, height: float) -> dict:
    """Move every arch of the room up or down together, keeping the differences between them."""
    room = T.get_room(design, room_id)
    by = height - sum(bay["apex_height_m"] for bay in room["bays"]) / len(room["bays"])
    for bay in room["bays"]:
        design = T.set_apex(design, bay["id"], height_m=round(bay["apex_height_m"] + by, 3))[0]
    return design


def _timber_value(design: dict, room: dict, part: str, key: str):
    return (room.get("timber") or {}).get(part, {}).get(key, design["timber"][part][key])


def _set_timber(design: dict, room_id: str, part: str, key: str, value) -> dict:
    """Set one timber value: in the room's own settings if it has any, otherwise for the whole design."""
    new = copy.deepcopy(design)
    room = T.get_room(new, room_id)
    if room.get("timber"):
        room["timber"].setdefault(part, {})[key] = value
    else:
        new["timber"][part][key] = value
    return new


def _fixed_ring(design: dict, room: dict) -> str:
    if _joined(room) and not _outline(room).get("through"):
        return "joined to another room: change its ring bay by bay"
    return ""


def _fixed_size(design: dict, room: dict) -> str:
    if _joined(room) and "radius_m" not in _outline(room):
        return "joined to another room: it cannot be resized without moving its neighbour"
    return ""


CONTROLS = (
    Control("crown_height", "Height", "Crown", "length", 0.0, 14.0, 0.05, lambda d, r: r["crown"]["height_m"], lambda d, rid, v: T.set_crown(d, rid, height_m=v)[0], "Height of the crown ring above the floor"),
    Control("crown_radius", "Ring radius", "Crown", "length", 0.2, 5.0, 0.02, lambda d, r: r["crown"]["radius_m"], lambda d, rid, v: T.set_crown(d, rid, radius_m=v)[0], "Radius of the crown ring"),
    Control("lantern_radius", "Lantern radius", "Crown", "length", 0.6, 8.0, 0.02, lambda d, r: r["shape"]["lantern_radius_m"], lambda d, rid, v: T.set_shape(d, rid, lantern_radius_m=v)[0], "Radius of the ring where the canopy turns up into the lantern"),
    Control("lantern_base", "Lantern base", "Crown", "length", 1.0, 12.0, 0.05, lambda d, r: r["shape"]["lantern_base_height_m"], lambda d, rid, v: T.set_shape(d, rid, lantern_base_height_m=v)[0], "Height at which the canopy turns up into the lantern"),
    Control("top_slope", "Top slope", "Crown", "angle", -90.0, 150.0, 1.0, lambda d, r: r["crown"].get("section", {}).get("top_slope_deg", 90.0), lambda d, rid, v: T.set_crown(d, rid, section={"top_slope_deg": v})[0], "How the crown arrives at its ring: 90 upright, 0 level, over 90 flared, -90 straight down"),
    Control("spine_length", "Spine length", "Crown", "length", 0.0, 20.0, 0.1, lambda d, r: crown_spine(r["crown"]).length, lambda d, rid, v: T.set_spine(d, rid, v)[0], "Draws the crown out into a line: a round room becomes a long hall"),
    Control("room_radius", "Radius", "Room", "length", 2.5, 15.0, 0.05, lambda d, r: _reach(r), _resize, "How far from the crown the piers stand", _fixed_size),
    Control("bays", "Bays", "Room", "count", 3, 24, 1, lambda d, r: len(r["bays"]), _count_bays, "How many bays the room has", _fixed_ring),
    Control("arch_height", "Arch height", "Room", "length", 2.6, 10.0, 0.05, lambda d, r: sum(b["apex_height_m"] for b in r["bays"]) / len(r["bays"]), _raise_arches, "Raises or lowers every arch together; drag one apex handle to move one arch"),
    Control("pier_height", "Pier height", "Room", "length", 0.5, 4.0, 0.05, lambda d, r: r["shape"]["pier_height_m"], lambda d, rid, v: T.set_shape(d, rid, pier_height_m=v)[0], "Height at which the arches spring from the piers (the same in every room joined to this one)"),
    Control("ribs", "Ribs per hand", "Lattice", "count", 4, 40, 1, lambda d, r: _timber_value(d, r, "lattice", "ribs_per_family"), lambda d, rid, v: _set_timber(d, rid, "lattice", "ribs_per_family", int(v)), "Ribs of each hand in each tier of the lattice"),
    Control("lean", "Rib lean", "Lattice", "angle", 10.0, 70.0, 1.0, lambda d, r: _timber_value(d, r, "lattice", "lean_deg"), lambda d, rid, v: _set_timber(d, rid, "lattice", "lean_deg", float(v)), "The angle the ribs hold to the straight way down the roof"),
    Control(
        "hoops", "Hoops", "Lattice", "count", 0, len(HOOP_DISTANCES_M), 1,
        lambda d, r: len(_timber_value(d, r, "arches", "hoops_m")),
        lambda d, rid, v: _set_timber(d, rid, "arches", "hoops_m", list(HOOP_DISTANCES_M[: int(v)])),
        "Hoops following each arch inside it",
    ),
)
BY_KEY = {control.key: control for control in CONTROLS}
GROUPS = tuple(dict.fromkeys(control.group for control in CONTROLS))


def values(design: dict, room_id: str) -> dict:
    """The present value of every control for one room."""
    room = T.get_room(design, room_id)
    return {control.key: control.get(design, room) for control in CONTROLS}


def blocked(design: dict, room_id: str) -> dict:
    """The controls that cannot be used on this room as it stands, with the reason for each."""
    room = T.get_room(design, room_id)
    return {control.key: reason for control in CONTROLS if (reason := control.blocked(design, room))}


def adjust(design: dict, room_id: str, key: str, value) -> dict:
    """The design with one control of one room set to a value. Raises DesignError if that is not a valid design."""
    control = BY_KEY[key]
    reason = control.blocked(design, T.get_room(design, room_id))
    if reason:
        raise T.DesignError(f"{room_id}: {reason}")
    new = control.set(design, room_id, value)
    T.validate(new)
    return new


def grow_room(design: dict, bay_id: str, bays: int = 6) -> dict:
    """The design with a smaller room grown out of a bay, given a lattice and hoops that suit its size."""
    host = T.find(design, "bays", bay_id)[0]
    new, change = T.add_room_from_bay(design, bay_id, bays=bays, shape={"lantern_base_height_m": round(host["shape"]["lantern_base_height_m"] - 0.3, 2)})
    room = T.get_room(new, change["added"][0])
    scale = _reach(room) / _reach(host)
    lattice = new["timber"]["lattice"]
    tiers = copy.deepcopy(lattice["tiers"])
    for tier in tiers:  # a tier that starts on the canopy starts as far beyond the smaller lantern as it does in the host
        if isinstance(tier.get("from"), dict) and "radius_m" in tier["from"]:
            tier["from"]["radius_m"] = round(room["shape"]["lantern_radius_m"] + (tier["from"]["radius_m"] - host["shape"]["lantern_radius_m"]) * scale * 0.65, 2)
    room["timber"] = {"lattice": {"ribs_per_family": max(6, round(lattice["ribs_per_family"] * scale)), "tiers": tiers}, "arches": {"hoops_m": list(new["timber"]["arches"].get("hoops_m", []))[:1]}}
    T.validate(new)
    return new
