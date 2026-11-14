"""Rebuild the Bower scene from design.json: handles, boundary curves, envelope, context, cameras.

Run inside Blender, any of:
    runpy.run_path(r"<repo>/scripts/generate.py")["main"]()      (MCP or the Python console)
    Text Editor > Open > Run Script
    blender --python scripts/generate.py

Pass views_dir to also render the design's views there. Re-running rebuilds the
same objects in place; change design.json (or drag handles and run
apply_handles.py), not the generated objects.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "design.json"


def write_schedule(design: dict, path, joints_path=None, lines_path=None, roots_path=None) -> str:
    """Write one row per primary member (section, length, tightest bend, volume, cuts, neighbours)
    and, to `joints_path`, one row per joint (its members, place, angle and the cut in each).

    Where the design has training lines (bower/lines.py) or sets out its ground (bower/ground.py),
    each standoff of each line and feeder is added to the joint schedule as a hole to drill in
    its member, `lines_path` gets one row per line, and `roots_path` one row per root zone."""
    import csv

    from bower.ground import zone_rows
    from bower.joints import joint_rows
    from bower.lines import design_lines, line_rows, standoff_joints
    from bower.timber import build_design_timber, clearances, schedule

    rows, joints, lines, roots = [], [], [], []
    piers = {pier["id"]: pier["position_m"] for room in design["rooms"] for pier in room["piers"]}
    groups = build_design_timber(design)  # rooms joined to each other share members and joints
    strung = {tuple(group["rooms"]): group for group in design_lines(design, groups)}
    for group in groups:
        members = group["members"]
        mine = strung.get(tuple(group["rooms"]))
        found = mine["joints"] if mine else __import__("bower.joints", fromlist=["find_joints"]).find_joints(members, design["timber"])[0]
        rows += schedule(members, design["timber"], clearances(members), found)
        joints += joint_rows(found)
        if mine and mine["lines"]:
            joints += joint_rows(standoff_joints(mine["lines"], design["timber"]))
            lines += line_rows(mine["lines"], members, piers)
        if mine and mine["ground"]:
            roots += zone_rows(mine["ground"])
    Path(path).parent.mkdir(exist_ok=True)
    for target, table in ((path, rows), (joints_path, joints), (lines_path, lines), (roots_path, roots)):
        if target is not None and table:
            with open(target, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(table[0]))
                writer.writeheader()
                writer.writerows(table)
    for target, table in ((lines_path, lines), (roots_path, roots)):
        if target is not None and not table and Path(target).exists():
            Path(target).unlink()  # a design with no lines, or no root zones, leaves no schedule of them behind
    return str(path)


def main(design_path=DESIGN, views_dir=None, view_prefix="") -> dict:
    import bpy

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    for name in [m for m in sys.modules if m == "bower" or m.startswith("bower.")]:
        del sys.modules[name]  # pick up source edits in a long-lived Blender session
    from bower import topology
    from bower.blender_scene import build_design, render_views

    scene = bpy.context.scene
    units = scene.unit_settings
    if units.system != "METRIC" or abs(units.scale_length - 1.0) > 1e-9:
        raise RuntimeError(f"scene units are {units.system} x {units.scale_length}; bower geometry is in metres at scale 1.0")
    design = topology.load(design_path)
    # A room whose layout asks for a different number of bays than its ring has is laid out afresh,
    # and the new ring is written back to the design file.
    design, relaid = topology.reconcile(design)
    if relaid:
        topology.save(design_path, design)
    report = {"blender": bpy.app.version_string, "design": str(design_path), "relaid": relaid, **build_design(scene, design)}
    if "timber" in design:
        from bower.blender_ground import build_ground
        from bower.blender_lines import build_lines
        from bower.lines import design_lines

        strung = design_lines(design)  # the lines, and the ground with its feeders, worked out once for both
        report["training_lines"] = build_lines(scene, design, groups=strung)  # after build_design, which clears a room's objects it did not build
        report["ground"] = build_ground(scene, design, groups=strung)
        report["member_schedule"] = write_schedule(design, REPO / "output" / "member_schedule.csv", REPO / "output" / "joint_schedule.csv", REPO / "output" / "line_schedule.csv", REPO / "output" / "root_schedule.csv")
    if views_dir is not None:
        report["views"] = render_views(scene, design, views_dir, view_prefix)
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
