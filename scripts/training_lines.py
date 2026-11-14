"""Build the design with its training lines, measure every cable against the timber as milled, and render them.

Run inside Blender as generate.py is, or on its own without a window:
    blender --background --factory-startup --python scripts/training_lines.py

It rebuilds the scene from the design file (so it takes over whatever scene it is run in),
then writes:
    views/lines_*.png            close views at the cables' true size: the pier where most lines start,
                                 from outside, from inside the room and down at its foot, and a
                                 stretch of roof
    views/lines_ground_*.png     where the design sets out its ground (bower/ground.py): a plan of a
                                 planted pier cut at knee height, its feeder from outside, a section
                                 through the ground from outside, and where the feeder hands over to
                                 the training lines (the ties drawn green). The scene's ground disc
                                 is left out of these, since the soil and the piles lie below it
    views/lines_diagram_*.png    diagrams of where the cables run, not of how they look: each cable a
                                 plain line thick enough to follow, its standoffs left out. Training
                                 lines blue, feeders red, hand-overs green
    output/training_lines.json   what was set out, and what was measured in the scene
    output/line_schedule.csv     one row per line (generate.py writes it)
"""
import copy
import json
import math
import runpy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "design.json"
DIAGRAM_RADIUS_M = {"far": 0.014, "near": 0.006}  # how thick a cable is drawn in a diagram of the whole building, and of one pier
DIAGRAM_COLOURS = {"training": (0.04, 0.22, 0.70, 1.0), "feeder": (0.85, 0.08, 0.12, 1.0)}


def _unit(v):
    length = math.sqrt(sum(c * c for c in v))
    return tuple(c / length for c in v)


def close_views(design: dict, groups: list) -> list[dict]:
    """Cameras for the close views, placed from the lines themselves so that they follow the design."""
    lines = [line for group in groups for line in group["lines"]]
    piers = {p["id"]: (p["position_m"], room) for room in design["rooms"] for p in room["piers"]}
    feet = {}
    for line in lines:
        for end in (line.standoffs[0], line.standoffs[-1]):
            if end.head[2] - piers[next(iter(piers))][1]["floor_z_m"] < 0.5:
                pid = min(piers, key=lambda k: math.hypot(piers[k][0][0] - end.head[0], piers[k][0][1] - end.head[1]))
                feet.setdefault(pid, []).append(end.head)
    planted = [zone.pier for group in groups if group.get("ground") for zone in group["ground"]["root_zones"]]
    pid = planted[0] if planted else max(sorted(feet), key=lambda k: len(feet[k]))  # a pier with a plant at it, or the one where most lines start
    (px, py), room = piers[pid]
    cx, cy = room["crown"]["centre_m"]
    out = _unit((px - cx, py - cy, 0.0))
    side = (-out[1], out[0], 0.0)
    floor = room["floor_z_m"]
    views = [
        {"id": "pier_outside", "projection": "persp", "location_m": [px + 3.6 * out[0] + 2.6 * side[0], py + 3.6 * out[1] + 2.6 * side[1], floor + 1.7], "target_m": [px, py, floor + 2.1], "lens_mm": 26.0},
        {"id": "pier_inside", "projection": "persp", "location_m": [px - 4.4 * out[0] - 1.4 * side[0], py - 4.4 * out[1] - 1.4 * side[1], floor + 1.6], "target_m": [px, py, floor + 2.3], "lens_mm": 24.0},
        {"id": "pier_foot", "projection": "persp", "location_m": [px + 0.9 * out[0] + 1.5 * side[0], py + 0.9 * out[1] + 1.5 * side[1], floor + 1.7], "target_m": [px - 0.35 * out[0], py - 0.35 * out[1], floor + 0.3], "lens_mm": 28.0},
    ]
    if planted:  # the ground at that pier: a plan cut at knee height, the feeder from outside, and where it hands over
        views += [
            {"id": "ground_plan", "projection": "ortho", "location_m": [px + 0.35 * out[0], py + 0.35 * out[1], floor + 0.6], "target_m": [px + 0.35 * out[0], py + 0.35 * out[1], floor], "ortho_scale_m": 4.2},
            {"id": "ground_outside", "projection": "persp", "location_m": [px + 5.2 * out[0] - 2.1 * side[0], py + 5.2 * out[1] - 2.1 * side[1], floor + 1.6], "target_m": [px, py, floor + 1.45], "lens_mm": 24.0},
            # a section from outside: nothing more than 1.2 m beyond the pier's axis is drawn, so the piers behind stay out of it
            {"id": "ground_section", "projection": "ortho", "location_m": [px + 9.0 * out[0], py + 9.0 * out[1], floor - 1.0], "target_m": [px, py, floor - 1.0], "ortho_scale_m": 5.6, "clip_end_m": 10.2},
            {"id": "ground_handover", "projection": "persp", "location_m": [px + 2.4 * out[0] + 0.5 * side[0], py + 2.4 * out[1] + 0.5 * side[1], floor + 4.3], "target_m": [px - 0.35 * out[0], py - 0.35 * out[1], floor + 3.05], "lens_mm": 26.0},
        ]
    # a stretch of roof: beside a rib's line two thirds of the way up it, looking along the cable
    line = next((l for l in lines if l.kind == "training" and ".rib." in l.id), lines[0])
    k = (2 * len(line.standoffs)) // 3
    here, onward = line.standoffs[k], line.standoffs[min(k + 1, len(line.standoffs) - 1)]
    normal = _unit(tuple(h - f for h, f in zip(here.head, here.foot)))
    along = _unit(tuple(b - a for a, b in zip(here.head, onward.head)))
    across = _unit((along[1] * normal[2] - along[2] * normal[1], along[2] * normal[0] - along[0] * normal[2], along[0] * normal[1] - along[1] * normal[0]))
    eye = [here.head[i] + 0.75 * normal[i] - 1.25 * along[i] + 0.7 * across[i] for i in range(3)]
    views.append({"id": "roof", "projection": "persp", "location_m": eye, "target_m": [here.head[i] + 0.4 * along[i] for i in range(3)], "lens_mm": 30.0})
    return views


def main(design_path=DESIGN, views_dir=REPO / "views", record=REPO / "output" / "training_lines.json") -> dict:
    import bpy

    if bpy.app.background:  # a fresh scene of our own: clear away the default cube, lamp and camera
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
    built = runpy.run_path(str(REPO / "scripts" / "generate.py"))["main"](design_path)
    from bower import topology
    from bower.blender_lines import measure_lines
    from bower.blender_scene import build_views, render_views
    from bower.lines import design_lines, line_rows, settings

    scene = bpy.context.scene
    design = topology.load(design_path)
    groups = design_lines(design)
    lines = [line for group in groups for line in group["lines"]]
    report = {
        "blender": bpy.app.version_string,
        "design": str(design_path),
        "settings": settings(design["timber"]),
        "set_out": built.get("training_lines"),
        "ground": built.get("ground"),
        "measured_in_scene": measure_lines(scene),
        "timber": [{k: room["timber"].get(k) for k in ("members", "milled", "meshes_closed", "mesh_intersections_in_scene")} for room in built["rooms"] if "timber" in room],
    }
    if lines:
        piers = {p["id"]: p["position_m"] for room in design["rooms"] for p in room["piers"]}
        rows = [row for group in groups for row in line_rows(group["lines"], group["members"], piers)]
        at_pier = {}
        for row in rows:
            for end in ("start", "end"):
                if row[f"{end}_pier"]:
                    at_pier.setdefault(row[f"{end}_pier"], []).append((row[f"{end}_x_m"], row[f"{end}_y_m"]))
        report["line_feet_at_each_pier"] = {
            pid: {
                "lines": len(feet),
                "from_pier_axis_m": [round(min(math.hypot(x - piers[pid][0], y - piers[pid][1]) for x, y in feet), 3), round(max(math.hypot(x - piers[pid][0], y - piers[pid][1]) for x, y in feet), 3)],
                "closest_two_m": round(min(math.hypot(a[0] - b[0], a[1] - b[1]) for i, a in enumerate(feet) for b in feet[i + 1 :]), 3) if len(feet) > 1 else None,
            }
            for pid, feet in sorted(at_pier.items())
        }
        report["to_review"] = {row["id"]: row["review"] for row in rows if row["review"]}
        if views_dir is not None:
            shown = copy.deepcopy(design)
            shown["views"] = design["views"] + close_views(design, groups)
            build_views(scene, shown)
            for view in shown["views"]:
                if "clip_end_m" in view:
                    bpy.data.objects[f"CAM_{view['id']}"].data.clip_end = view["clip_end_m"]
            close ={view["id"] for view in shown["views"]} - {view["id"] for view in design["views"]}
            below = {name for name in close if name.startswith("ground_")}  # the soil and the piles lie below the scene's ground disc

            def render(prefix: str, only: set, **how) -> list:
                """Render some views, those of the ground with the scene's ground disc out of the way."""
                done = render_views(scene, shown, views_dir, prefix, only=only - below, **how) if only - below else []
                disc = bpy.data.objects.get("CTX_ground")
                if only & below:
                    hidden = disc.hide_render if disc else None
                    try:
                        if disc:
                            disc.hide_render = True
                        done += render_views(scene, shown, views_dir, prefix, only=only & below, **how)
                    finally:
                        if disc:
                            disc.hide_render = hidden
                return done

            report["views"] = render("lines_", close, size=(2000, 1250))
            # The diagrams: the same cables drawn as plain coloured lines, thick enough to follow, with
            # their standoffs left out. Training lines in blue, feeders in red, hand-overs in green.
            cables = [o for o in bpy.data.objects if o.get("bower_kind") == "training_line"]
            ties = [o for o in bpy.data.objects if o.get("bower_kind") == "handover"]
            material = bpy.data.materials["BOWER_cable"]
            feeder = bpy.data.materials.new("BOWER_diagram_feeder")
            feeder.diffuse_color = DIAGRAM_COLOURS["feeder"]
            true = (material.diffuse_color[:], [o.data.bevel_depth for o in cables + ties], [[p.radius for spline in o.data.splines[1:] for p in spline.points] for o in cables])
            try:
                material.diffuse_color = DIAGRAM_COLOURS["training"]
                for obj in cables:
                    for spline in obj.data.splines[1:]:  # every spline after the cable is a standoff
                        for point in spline.points:
                            point.radius = 0.0
                    if obj.get("bower_line") == "feeder":
                        obj.data.materials[0] = feeder
                for radius, only in ((DIAGRAM_RADIUS_M["far"], {"overhead", "plan", "exterior"}), (DIAGRAM_RADIUS_M["near"], {"ground_outside", "ground_handover"})):
                    for obj in cables + ties:
                        obj.data.bevel_depth = radius
                    report["views"] += render("lines_diagram_", only, size=(2000, 1250))
            finally:
                material.diffuse_color = true[0]
                for obj, depth in zip(cables + ties, true[1]):
                    obj.data.bevel_depth = depth
                for obj, radii in zip(cables, true[2]):
                    obj.data.materials[0] = material
                    for point, radius in zip((p for spline in obj.data.splines[1:] for p in spline.points), radii):
                        point.radius = radius
                bpy.data.materials.remove(feeder)
            build_views(scene, design)  # leave the scene's cameras as the design has them
    if record is not None:
        Path(record).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
