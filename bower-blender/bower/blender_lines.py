"""Write a design's training lines into the open Blender scene (the lines themselves: bower/lines.py).

Each line is one curve object, `LN_<line id>`, in 40_CABLES: its cable as straight runs through
the standoff heads, at the cable's true diameter, and each standoff as a short thicker run from
the member's face to the cable.

Like everything else that is generated, a line object is flagged `bower_generated` and tagged
with its room, and is replaced in place on the next run. `blender_scene.build_design` clears
away whatever it did not itself build for a room, lines included, so `build_lines` is run
after it: a scene rebuilt without it has no lines, never stale ones.
"""
from __future__ import annotations

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .blender_scene import CENTRELINE_COLLECTION, _collection, _place, _remove_stale
from .lines import DEFAULTS, check_lines, design_lines, settings

CABLE_COLOUR = (0.14, 0.15, 0.17, 1.0)  # a flat viewport colour for steel, as blender_scene's are for timber


def _material():
    material = bpy.data.materials.get("BOWER_cable") or bpy.data.materials.new("BOWER_cable")
    material.diffuse_color = CABLE_COLOUR
    return material


def _line_curve(line, cfg: dict):
    """One curve data-block for a line: the cable, then one two-point run per standoff."""
    curve = bpy.data.curves.new(line.id, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = cfg["cable_diameter_m"] / 2.0
    curve.bevel_resolution = 2
    curve.use_fill_caps = True
    cable = curve.splines.new("POLY")
    cable.points.add(len(line.points) - 1)
    for point, co in zip(cable.points, line.points):
        point.co = (*co, 1.0)
    cable.use_cyclic_u = line.closed
    thicker = cfg["standoff_diameter_m"] / cfg["cable_diameter_m"]  # a point's radius scales the bevel
    for standoff in line.standoffs:
        post = curve.splines.new("POLY")
        post.points.add(1)
        for point, co in zip(post.points, (standoff.foot, standoff.head)):
            point.co = (*co, 1.0)
            point.radius = thicker
    curve.materials.append(_material())
    return curve


def build_lines(scene, design: dict, check: bool = True, groups=None) -> dict:
    """Rebuild the lines of the design in the scene and return what was built: its training lines,
    and the feeders of its ground (bower/ground.py) with them.

    Lines the design no longer has are removed, so a design that asks for none leaves none.
    With `check`, each group of joined rooms also carries what `lines.check_lines` measured.
    `groups` is `lines.design_lines(design)` if it has been worked out already.
    """
    cfg = settings(design.get("timber", {})) or DEFAULTS
    strung = design_lines(design) if groups is None else groups
    built, groups = [], []
    if strung:
        collection = _collection(scene, CENTRELINE_COLLECTION["cable"])
        for group in strung:
            for line in group["lines"]:
                props = {
                    "bower_room": group["room_of"][line.member],
                    "bower_kind": "training_line",
                    "bower_line": line.kind,
                    "bower_role": "cable",
                    "bower_id": line.id,
                    "bower_member": line.member,
                    "bower_face": line.face,
                    "bower_gap_m": line.gap_m,
                    "bower_length_m": round(line.length_m, 3),
                    "bower_standoffs": len(line.standoffs),
                    "bower_review": line.review,
                }
                built.append(_place(f"LN_{line.id}", _line_curve(line, cfg), collection, props))
            summary = {"rooms": list(group["rooms"]), "lines": len(group["lines"])}
            groups.append({**summary, **check_lines(group["lines"], group["members"], design["timber"])} if check and group["lines"] else summary)
    removed = _remove_stale({o.name for o in built}, bower_kind="training_line")
    bpy.context.view_layer.update()
    return {"lines": len(built), "stale_lines_removed": removed, "groups": groups}


def _inside(tree, point) -> bool:
    """Whether a point lies inside a closed mesh: a ray from it leaves through an odd number of faces."""
    direction, origin, hits = Vector((0.3713, 0.5571, 0.7427)), point, 0  # square to no face of a member
    while hits < 64:
        location = tree.ray_cast(origin, direction)[0]
        if location is None:
            break
        hits += 1
        origin = location + direction * 1e-5
    return hits % 2 == 1


def measure_lines(scene, step: float = 0.03, reach: float = 0.3) -> dict:
    """Measure the cables in the scene against the timber in the scene, as it has been milled.

    This uses nothing of how the lines were set out: only the `LN_` curves and the `TM_` meshes
    as they stand. Every cable is sampled along its straight runs, and each sample measured
    to the surface of every member's mesh within `reach` and tested for lying inside one.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    trees = {o["bower_id"]: BVHTree.FromObject(o, depsgraph) for o in bpy.data.objects if o.get("bower_kind") == "timber_preview"}
    cables = sorted((o for o in bpy.data.objects if o.get("bower_kind") == "training_line"), key=lambda o: o.name)
    samples = inside = 0
    other, own_lo, own_hi = (reach, "", ""), reach, 0.0
    for obj in cables:
        cable = obj.data.splines[0]
        points = [Vector(p.co[:3]) for p in cable.points]
        if cable.use_cyclic_u:
            points.append(points[0])
        for a, b in zip(points, points[1:]):
            count = max(1, int((b - a).length / step) + 1)
            for i in range(count + 1):
                p = a.lerp(b, i / count)
                samples += 1
                for member_id, tree in trees.items():
                    distance = tree.find_nearest(p, reach)[3]
                    if distance is None:
                        continue
                    if _inside(tree, p):
                        inside += 1
                        distance = -distance
                    if member_id == obj["bower_member"]:
                        own_lo, own_hi = min(own_lo, distance), max(own_hi, distance)
                    elif distance < other[0]:
                        other = (distance, obj["bower_id"], member_id)
    return {
        "measured_against": f"the {len(trees)} timber meshes in the scene, as they stand",
        "cables": len(cables),
        "samples": samples,
        "samples_inside_timber": inside,
        "nearest_other_member_m": {"clear_m": round(other[0], 4), "line": other[1], "member": other[2]} if other[1] else None,
        "gap_to_own_member_m": [round(own_lo, 4), round(own_hi, 4)] if cables else None,
    }
