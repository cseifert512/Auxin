"""Mill the two members of one joint, as every lap is cut and as the design now cuts this one, and write what is left of each near the joint.

Run inside Blender, without a window:
    blender-launcher.exe --background --factory-startup --python scripts/joint_detail.py -- "lap:R1.fine.cw.03:R1.fill.ccw.06"

Writes ../drawings-in-code/sketches/design-space/joint-detail.js for the joints vignette, and
output/joint_detail.log (what was milled, or the error: a windowless Blender prints nothing back).

Only the two members of the joint are built, each with every cutter it has, so this takes seconds
and leaves no scene behind. "as_drawn" is the design with timber.joints.plant_detail and
reached_by_plants taken out; "now" is the design as it stands.
"""
import json
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOG = REPO / "output" / "joint_detail.log"
OUT = REPO.parent / "drawings-in-code" / "sketches" / "design-space" / "joint-detail.js"
NEAR_M = 0.5  # how much of each member is kept, either side of the joint
DESIGN = "design/six_bay_radial.json"


def main(joint_id: str) -> dict:
    import bpy

    sys.path.insert(0, str(REPO))
    from bower import topology
    from bower.blender_scene import _mill, build_member
    from bower.joints import find_joints
    from bower.timber import build_design_timber

    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene = bpy.context.scene
    design = topology.load(REPO / DESIGN)
    joints_cfg = design["timber"]["joints"]
    variants = {
        "as_drawn": {**design["timber"], "joints": {k: v for k, v in joints_cfg.items() if k not in ("plant_detail", "reached_by_plants")}},
        "now": design["timber"],
    }
    group = build_design_timber(design)[0]
    by_id = {m.id: m for m in group["members"]}
    out = {"joint": joint_id, "design": DESIGN, "variants": {}}
    for name, timber in variants.items():
        joints, _, cutters = find_joints(group["members"], timber)
        joint = next(j for j in joints if j.id == joint_id)
        at = joint.at_m
        pieces, objects = {}, []
        for member_id in joint.members:
            built = build_member(scene, by_id[member_id], design["timber"]["sampling"], {"bower_room": "R1"}, (), checks=False)
            objects.append(bpy.data.objects[built["objects"]["timber"]])
        milled = _mill(scene, objects, {m: cutters[m] for m in joint.members}, timber["joints"].get("solver", "EXACT"))
        for obj in objects:
            mesh = obj.data
            keep, index, verts, faces = set(), {}, [], []
            for poly in mesh.polygons:
                if any(sum((mesh.vertices[v].co[k] - at[k]) ** 2 for k in range(3)) <= NEAR_M ** 2 for v in poly.vertices):
                    keep.add(poly.index)
            for poly in mesh.polygons:
                if poly.index not in keep:
                    continue
                face = []
                for v in poly.vertices:
                    if v not in index:
                        index[v] = len(verts)
                        verts.append([round(c, 4) for c in mesh.vertices[v].co])  # to a tenth of a millimetre: the gap of a lap is three
                    face.append(index[v])
                faces.append(face)
            pieces[obj["bower_id"]] = {"verts_m": verts, "faces": faces, "cutters": len(cutters[obj["bower_id"]])}
        out["variants"][name] = {
            "at_m": list(at),
            "review": joint.review,
            "cuts": [{"member": c.member, "operation": c.operation, "face": c.face, "depth_m": c.depth_m, "length_m": c.length_m} for c in joint.cuts],
            "clearance_m": (timber["joints"].get("plant_detail") or {}).get("clearance_m") if "cut as a splayed lap" in joint.review else timber["joints"].get("lap_clearance_m"),
            "detail": timber["joints"].get("plant_detail") if "cut as a splayed lap" in joint.review else None,
            "milled": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in milled.items()},
            "pieces": pieces,
        }
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
    OUT.write_text("window.JOINT_DETAIL = " + json.dumps(out, separators=(",", ":")) + ";\n", encoding="utf-8")
    return {name: {"milled": v["milled"], "faces": {k: len(p["faces"]) for k, p in v["pieces"].items()}} for name, v in out["variants"].items()}


if __name__ == "__main__":
    LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
        LOG.write_text("ok " + json.dumps(main(args[0] if args else "lap:R1.fine.cw.03:R1.fill.ccw.06"), indent=1) + "\n", encoding="utf-8")
    except Exception:
        LOG.write_text("failed\n" + traceback.format_exc(), encoding="utf-8")
