"""Write a design's ground into the open Blender scene (the ground itself: bower/ground.py).

    RS_<zone>       an empty at each root zone's planting point, in 50_PLANTING_POINTS
    RZ_<zone>       the zone's soil as a drum, its top at the level of the soil
    FT_<pier>       each pier's footing, its top at the level of the feet, in 45_FOOTINGS: the
                    steel cap of a footing on piles, or a pad
    PL_<pier>       the screw piles of a footing on piles: each a shaft from the cap down, a
                    helix at its foot, and a head plate that shows where it stands in plan
    HO_<pier>       the hand-overs at a planted pier, as thin green ties from the feeder to each
                    training line: where a gardener leads a shoot across. Nothing is built there.

Under a cap on piles the soil lies below the feet (ground.footings.piles.feet_above_soil_m),
so a root zone's drum and the piles are below the scene's ground disc: hide `CTX_ground` to
see them, as scripts/training_lines.py does for its views of the ground.

The feeders are lines, and are written with the other lines by bower/blender_lines.py.
Everything here is flagged `bower_generated` and tagged with its room, as the lines are, so
`blender_scene.build_design` clears it and `build_ground` is run after it.
"""
from __future__ import annotations

from math import cos, pi, sin

import bpy

from .blender_scene import _collection, _place, _remove_stale
from .floor import Floor
from .ground import settings
from .lines import design_lines

PLANTING, FOOTINGS = "50_PLANTING_POINTS", "45_FOOTINGS"
COLOURS = {"soil": (0.24, 0.16, 0.10, 1.0), "footing": (0.62, 0.62, 0.60, 1.0), "steel": (0.33, 0.36, 0.40, 1.0), "handover": (0.20, 0.55, 0.25, 1.0)}
TIE_RADIUS_M = 0.003
KINDS = ("footing", "piles", "root_zone", "root_station", "handover")


def _material(key: str):
    material = bpy.data.materials.get(f"BOWER_{key}") or bpy.data.materials.new(f"BOWER_{key}")
    material.diffuse_color = COLOURS[key]
    return material


def _ring(centre, radius: float, sides: int = 24) -> list:
    return [(centre[0] + radius * cos(2 * pi * k / sides), centre[1] + radius * sin(2 * pi * k / sides)) for k in range(sides)]


def _prisms(name: str, parts: list, material: str):
    """One mesh of closed upright prisms: each of `parts` is (plan outline, counter-clockwise; bottom; top)."""
    verts, faces = [], []
    for outline, z0, z1 in parts:
        base, n = len(verts), len(outline)
        verts += [(x, y, z0) for x, y in outline] + [(x, y, z1) for x, y in outline]
        faces += [tuple(base + i for i in reversed(range(n))), tuple(base + n + i for i in range(n))] + [(base + i, base + (i + 1) % n, base + n + (i + 1) % n, base + n + i) for i in range(n)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.materials.append(_material(material))
    return mesh


def build_ground(scene, design: dict, groups=None) -> dict:
    """Rebuild the ground of the design in the scene and return its reports, one per group of joined rooms.

    Ground the design no longer has is removed, so a design that sets none out leaves none.
    `groups` is `lines.design_lines(design)` if it has been worked out already.
    """
    groups = design_lines(design) if groups is None else groups
    cfg = settings(design)
    built, reports = [], []
    for group in groups:
        laid = group.get("ground")
        if not laid:
            continue
        levels = Floor(group["members"])  # each pier's feet stand at their own level on sloping ground
        room = group["rooms"][0]
        room_of_pier = {p["id"]: r["id"] for r in design["rooms"] for p in r["piers"]}
        planting, footings = _collection(scene, PLANTING), _collection(scene, FOOTINGS)
        piles = cfg["footings"]["piles"]
        for pier_id, footing in laid["footings"].items():
            floor = levels.at(footing.outline[0])
            tags = {"bower_room": room_of_pier.get(pier_id, room), "bower_id": pier_id, "bower_footing": footing.kind}
            props = {**tags, "bower_kind": "footing", "bower_area_m2": footing.area_m2, "bower_piles": len(footing.piles), "bower_review": footing.review}
            cap = _prisms(f"{pier_id}.footing", [(footing.outline, floor - footing.depth_m, floor)], "steel" if footing.kind == "piles" else "footing")
            built.append(_place(f"FT_{pier_id}", cap, footings, props))
            if footing.piles:
                parts = []
                for at in footing.piles:
                    foot = floor - piles["length_m"]
                    parts += [
                        (_ring(at, piles["shaft_m"] / 2.0, 12), foot, floor - footing.depth_m),  # the shaft, from the underside of the cap down
                        (_ring(at, piles["helix_m"] / 2.0), foot + 0.15, foot + 0.165),  # its helix, shown as a plate
                        (_ring(at, piles["shaft_m"]), floor, floor + 0.006),  # its head, proud of the cap so that it shows in plan
                    ]
                built.append(_place(f"PL_{pier_id}", _prisms(f"{pier_id}.piles", parts, "steel"), footings, {**tags, "bower_kind": "piles", "bower_length_m": piles["length_m"]}))
        for zone in laid["root_zones"]:
            tags = {"bower_room": room_of_pier.get(zone.pier, room), "bower_id": zone.id, "bower_pier": zone.pier, "bower_plant": zone.plant, "bower_soil_m3": zone.soil_m3, "bower_review": zone.review}
            floor = levels.at(zone.position)
            top = floor - zone.top_m if zone.top_m else floor + 0.03  # beside a pad the soil is at the feet's level: drawn just proud of the ground
            drum = _prisms(f"{zone.id}.soil", [(_ring(zone.position, zone.radius_m, 48), top - zone.depth_m, top)], "soil")
            built.append(_place(f"RZ_{zone.id}", drum, planting, {**tags, "bower_kind": "root_zone"}))
            station = _place(f"RS_{zone.id}", None, planting, {**tags, "bower_kind": "root_station"})
            station.empty_display_type, station.empty_display_size = "PLAIN_AXES", 0.3
            station.location = (zone.position[0], zone.position[1], top)
            built.append(station)
        by_pier = {}
        for handover in laid["handovers"]:
            by_pier.setdefault(handover.pier, []).append(handover)
        for pier_id, ties in by_pier.items():
            curve = bpy.data.curves.new(f"{pier_id}.handovers", "CURVE")
            curve.dimensions, curve.bevel_depth, curve.bevel_resolution = "3D", TIE_RADIUS_M, 1
            for tie in ties:
                spline = curve.splines.new("POLY")
                spline.points.add(1)
                spline.points[0].co, spline.points[1].co = (*tie.start, 1.0), (*tie.end, 1.0)
            curve.materials.append(_material("handover"))
            built.append(_place(f"HO_{pier_id}", curve, planting, {"bower_room": room_of_pier.get(pier_id, room), "bower_kind": "handover", "bower_id": pier_id, "bower_ties": len(ties)}))
        reports.append({"rooms": list(group["rooms"]), **laid["report"]})
    keep = {o.name for o in built}
    removed = sum(_remove_stale(keep, bower_kind=kind) for kind in KINDS)
    bpy.context.view_layer.update()
    return {"objects": len(built), "stale_objects_removed": removed, "groups": reports}
