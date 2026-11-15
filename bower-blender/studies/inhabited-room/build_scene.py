"""Build the inhabited-room study: the six-bay Bower as a place, in one editable Blender scene.

    blender-launcher.exe --background --factory-startup --disable-autoexec --python build_scene.py -- [--render arrival,section,plan] [--samples 96]

or, in a Blender with a window, from the Python console:

    import runpy; runpy.run_path(r"<this folder>\\build_scene.py")["main"](["--render", "arrival,section"])

It starts from an empty file every time and writes inhabited_room.blend beside itself, so the scene
can be thrown away and made again. What goes into it, and where each part comes from:

    linked      the timber and the source cameras, from ../../../releases/<snapshot>/bower.blend. The
                snapshot's own collection BOWER_V1 is linked whole; its timber objects are shown through
                S05_BOWER_TIMBER, local objects of the same names on the same linked meshes, because the
                snapshot's materials carry no colour a path tracer can use and a linked material cannot
                be given one.
    generated   footings, piles, root zones, training lines, feeders and hand-overs, from ground.json
                (set_out_ground.py: the building model's own bower/ground.py and bower/lines.py).
    proposal    the site: levels, floor, paths, beds, care path, water. Authored for this study in
                site.json; every size provisional.
    borrowed    people, surrounding vegetation, ground textures and the sky (assets.json, fetch_assets.py).

Every object carries `study_status` (one of those four) and `study_note` (what it is for).

One switch draws the section. The node group STUDY_section_switch holds two numbers, `section_on` and
`section_y`. With section_on at 1 every study material hides what lies south of section_y and paints
the inside of each solid it has cut with a flat colour; CAM_section clips everything else at the same
plane. `render()` sets the switch for each view and puts it back to 0, so the file is saved inhabited.

A windowless Blender prints nothing back: progress and errors go to build.log.
"""
from __future__ import annotations

import json
import random
import sys
import time
import traceback
from math import atan2, cos, degrees, exp, hypot, pi, radians, sin, sqrt
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
SITE = json.loads((HERE / "site.json").read_text(encoding="utf-8"))
GROUND = json.loads((HERE / "ground.json").read_text(encoding="utf-8"))
BLEND = HERE / "inhabited_room.blend"
SNAPSHOT = SITE["baseline"]["snapshot"]
LOG = HERE / "build.log"

LINKED = "linked: snapshot geometry, unchanged"
GENERATED = "generated: bower/ground.py and bower/lines.py on the snapshot's design (set_out_ground.py)"
PROPOSAL = "proposal: authored for this study, provisional"
BORROWED = "borrowed asset: not Bower geometry or planting (assets.json)"

FLOOR = GROUND["floor_z_m"]  # the underside of the timber feet
SOIL = FLOOR - GROUND["piles"]["feet_above_soil_m"]  # the soil level bower/ground.py sets
RING = hypot(*next(iter(GROUND["piers"].values())))  # the piers' circle
RC = SITE["room"]["floor_corner_radius_m"]
EDGE = RC * cos(pi / 6)  # from the crown to the middle of a floor edge
HW = SITE["paths"]["width_m"] / 2.0
YL = RING * cos(pi / 6) + SITE["paths"]["landing_m"]  # where the level landing ends and the ramp begins
RB = SITE["beds"]["outer_radius_m"]
MULCH = SITE["beds"]["mulch_m"]
CUT_Y = SITE["cameras"]["section"]["cut_y_m"]
BEYOND_M = 2.0  # how far behind the cut buried things are still drawn in the section

_lines: list = []


def log(message: str) -> None:
    _lines.append(f"{time.strftime('%H:%M:%S')} {message}")
    LOG.write_text("\n".join(_lines) + "\n", encoding="utf-8")


# --- the lie of the land ----------------------------------------------------------------------------


def ground_z(x: float, y: float) -> float:
    """The garden's surface: level round the room, falling to a hollow beyond it."""
    w = SITE["water"]
    g = max(0.0, min(hypot(x, y), 26.0) - w["level_radius_m"])
    lift = -cos(atan2(y, x) - radians(w["fall_towards_deg"])) * w["fall"] * g * g / (g + 2.5)
    d = hypot(x - w["hollow_m"][0], y - w["hollow_m"][1])
    return SOIL + lift - w["hollow_depth_m"] * exp(-2.2 * (d / w["hollow_radius_m"]) ** 2)


def floor_z(x: float, y: float) -> float:
    """The room's floor: highest at the middle, falling to the beds."""
    return SITE["levels"]["floor_centre_m"] - SITE["levels"]["floor_fall"] * hypot(x, y)


def hex_norm(x: float, y: float) -> float:
    """How far out a point is, measured as the floor's hexagon is: EDGE on the floor's edge."""
    return max(x * cos(pi / 6 + k * pi / 3) + y * sin(pi / 6 + k * pi / 3) for k in range(6))


def path_top(y: float) -> float:
    """The approach path's surface: level with the floor's edge to the end of the landing, then a ramp down to the garden."""
    level = floor_z(0.0, EDGE)
    lawn = ground_z(0.0, y) + 0.012
    return level if abs(y) <= YL else max(level - SITE["paths"]["ramp_gradient"] * (abs(y) - YL), lawn)


def surface_z(x: float, y: float) -> float:
    """What someone stands on at a point."""
    if hex_norm(x, y) <= EDGE:
        return floor_z(x, y)
    if abs(x) <= HW:
        return path_top(y)
    return ground_z(x, y)


# --- collections, objects, tags ---------------------------------------------------------------------

COLLECTIONS = [
    ("S05_BOWER_TIMBER", "the snapshot's timber, on its linked meshes, with materials that render"),
    ("S10_TERRAIN", "the garden's soil and its surface"),
    ("S20_ROOM_GROUND", "the room's floor, the approach and its edges"),
    ("S30_BEDS", "the planting beds, their root zones and the low planting on them"),
    ("S40_FOUNDATIONS", "pile caps and screw piles, as bower/ground.py sets them out"),
    ("S45_SUPPORTS", "training lines, feeders and hand-overs, as bower/lines.py and bower/ground.py set them out"),
    ("S50_BOWER_PLANTING", "the climbers at installation, as diagrams"),
    ("S60_WATER", "the standpipe, the drip line and the damp hollow"),
    ("S65_CARE", "the care path, stepping pads and standing pads"),
    ("S70_GARDEN", "trees, border, unmown strip, log: borrowed vegetation"),
    ("S80_PEOPLE", "borrowed figures"),
    ("S90_CAMERAS", "the study's cameras"),
    ("S95_SECTION_NOTES", "labels for the section: hidden in every other view"),
    ("S99_ASSET_SOURCES", "linked asset collections the scatters draw on: not shown"),
]


def make_collections(scene) -> dict:
    top = bpy.data.collections.new("STUDY_inhabited_room")
    scene.collection.children.link(top)
    made = {}
    for name, note in COLLECTIONS:
        c = bpy.data.collections.new(name)
        c["study_note"] = note
        top.children.link(c)
        made[name] = c
    return made


def layer_of(layer, name: str):
    if layer.name == name:
        return layer
    for child in layer.children:
        found = layer_of(child, name)
        if found:
            return found
    return None


def tag(obj, status: str, note: str):
    obj["study_status"] = status
    obj["study_note"] = note
    return obj


def add_mesh(name, verts, faces, coll, material=None, status=PROPOSAL, note="", smooth=False):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    if smooth:
        mesh.shade_smooth()
    obj = bpy.data.objects.new(name, mesh)
    if material is not None:
        for m in material if isinstance(material, (list, tuple)) else [material]:
            mesh.materials.append(m)
    coll.objects.link(obj)
    return tag(obj, status, note)


def _ccw(outline):
    area = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(outline, outline[1:] + outline[:1]))
    return list(outline) if area > 0 else list(reversed(outline))


def prism(outline, z0, z1):
    """A closed upright prism on a plan outline; z0 and z1 may be numbers or functions of (x, y)."""
    outline = _ccw([tuple(p[:2]) for p in outline])
    lo = z0 if callable(z0) else (lambda x, y: z0)
    hi = z1 if callable(z1) else (lambda x, y: z1)
    n = len(outline)
    verts = [(x, y, lo(x, y)) for x, y in outline] + [(x, y, hi(x, y)) for x, y in outline]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return verts, faces


def merge(parts):
    verts, faces = [], []
    for v, f in parts:
        base = len(verts)
        verts += v
        faces += [tuple(base + i for i in face) for face in f]
    return verts, faces


def circle(cx, cy, r, sides=32):
    return [(cx + r * cos(2 * pi * k / sides), cy + r * sin(2 * pi * k / sides)) for k in range(sides)]


def arc(r, a0, a1, step_deg=3.0):
    n = max(2, int(abs(a1 - a0) / radians(step_deg)) + 1)
    return [(r * cos(a0 + (a1 - a0) * k / (n - 1)), r * sin(a0 + (a1 - a0) * k / (n - 1))) for k in range(n)]


def inside(outline, x, y) -> bool:
    hit = False
    for (x0, y0), (x1, y1) in zip(outline, outline[1:] + outline[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (x1 - x0) * (y - y0) / (y1 - y0):
            hit = not hit
    return hit


def poly_curve(name, runs, radius, coll, material, status, note, cyclic=False):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions, curve.bevel_depth, curve.bevel_resolution = "3D", radius, 2
    curve.use_fill_caps = True
    for run in runs:
        spline = curve.splines.new("POLY")
        spline.points.add(len(run) - 1)
        for point, co in zip(spline.points, run):
            point.co = (*co, 1.0)
        spline.use_cyclic_u = cyclic
    curve.materials.append(material)
    obj = bpy.data.objects.new(name, curve)
    coll.objects.link(obj)
    return tag(obj, status, note)


# --- materials: every one of the study's goes through the section switch -----------------------------


def switch_group():
    ng = bpy.data.node_groups.get("STUDY_section_switch")
    if ng:
        return ng
    ng = bpy.data.node_groups.new("STUDY_section_switch", "ShaderNodeTree")
    ng.interface.new_socket("On", in_out="OUTPUT", socket_type="NodeSocketFloat")
    ng.interface.new_socket("Cut y", in_out="OUTPUT", socket_type="NodeSocketFloat")
    out = ng.nodes.new("NodeGroupOutput")
    on, cut = ng.nodes.new("ShaderNodeValue"), ng.nodes.new("ShaderNodeValue")
    on.name = on.label = "section_on"
    cut.name = cut.label = "section_y"
    on.outputs[0].default_value, cut.outputs[0].default_value = 0.0, CUT_Y
    ng.links.new(on.outputs[0], out.inputs["On"])
    ng.links.new(cut.outputs[0], out.inputs["Cut y"])
    return ng


def cut_group(solid):
    """Shader in, shader out: hidden south of the cut when the section is on; a solid's inside painted flat.

    `solid` False only hides. "buried" is for what lies in the ground: painted flat all over when the
    section is on, and hidden below the soil more than BEYOND_M behind the cut, so that the far piers'
    piles and root zones do not show through the soil as if they were under the floor."""
    name = {True: "STUDY_section_cut", False: "STUDY_section_hide", "buried": "STUDY_section_buried"}[solid]
    ng = bpy.data.node_groups.get(name)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(name, "ShaderNodeTree")
    ng.interface.new_socket("Shader", in_out="INPUT", socket_type="NodeSocketShader")
    ng.interface.new_socket("Cut colour", in_out="INPUT", socket_type="NodeSocketColor")
    ng.interface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
    n, link = ng.nodes, ng.links.new
    gin, gout = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    sw = n.new("ShaderNodeGroup")
    sw.node_tree = switch_group()
    geo, sep = n.new("ShaderNodeNewGeometry"), n.new("ShaderNodeSeparateXYZ")
    south, hide = n.new("ShaderNodeMath"), n.new("ShaderNodeMath")
    south.operation, hide.operation = "LESS_THAN", "MULTIPLY"
    link(geo.outputs["Position"], sep.inputs[0])
    link(sep.outputs["Y"], south.inputs[0])
    link(sw.outputs["Cut y"], south.inputs[1])
    link(south.outputs[0], hide.inputs[0])
    link(sw.outputs["On"], hide.inputs[1])
    clear, gone = n.new("ShaderNodeBsdfTransparent"), n.new("ShaderNodeMixShader")
    shown = gin.outputs["Shader"]
    if solid:
        back, face = n.new("ShaderNodeMath"), n.new("ShaderNodeMixShader")
        back.operation = "MULTIPLY"
        flat = n.new("ShaderNodeEmission")
        if solid == "buried":
            back.inputs[0].default_value = 1.0
        else:
            link(geo.outputs["Backfacing"], back.inputs[0])
        link(sw.outputs["On"], back.inputs[1])
        link(gin.outputs["Cut colour"], flat.inputs["Color"])
        link(back.outputs[0], face.inputs[0])
        link(gin.outputs["Shader"], face.inputs[1])
        link(flat.outputs[0], face.inputs[2])
        shown = face.outputs[0]
    hidden = hide.outputs[0]
    if solid == "buried":
        far, north, below, both, either, when = (n.new("ShaderNodeMath") for _ in range(6))
        far.operation, north.operation, below.operation, both.operation, either.operation, when.operation = "ADD", "GREATER_THAN", "LESS_THAN", "MULTIPLY", "MAXIMUM", "MULTIPLY"
        link(sw.outputs["Cut y"], far.inputs[0])
        far.inputs[1].default_value = BEYOND_M
        link(sep.outputs["Y"], north.inputs[0])
        link(far.outputs[0], north.inputs[1])
        link(sep.outputs["Z"], below.inputs[0])
        below.inputs[1].default_value = SOIL + 0.02
        link(north.outputs[0], both.inputs[0])
        link(below.outputs[0], both.inputs[1])
        link(south.outputs[0], either.inputs[0])
        link(both.outputs[0], either.inputs[1])
        link(either.outputs[0], when.inputs[0])
        link(sw.outputs["On"], when.inputs[1])
        hidden = when.outputs[0]
    link(hidden, gone.inputs[0])
    link(shown, gone.inputs[1])
    link(clear.outputs[0], gone.inputs[2])
    link(gone.outputs[0], gout.inputs["Shader"])
    return ng


def _begin(name, viewport):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    m.diffuse_color = (*viewport, 1.0)
    return m, m.node_tree


def _finish(m, shader, cut, solid=True):
    nt = m.node_tree
    out, g = nt.nodes.new("ShaderNodeOutputMaterial"), nt.nodes.new("ShaderNodeGroup")
    g.node_tree = cut_group(solid)
    g.inputs["Cut colour"].default_value = (*cut, 1.0)
    nt.links.new(shader, g.inputs["Shader"])
    nt.links.new(g.outputs["Shader"], out.inputs["Surface"])
    return m


def flat(name, colour, cut=None, rough=0.8, metallic=0.0, solid=True, vary=0.0):
    m, nt = _begin(name, colour)
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (*colour, 1.0)
    p.inputs["Roughness"].default_value, p.inputs["Metallic"].default_value = rough, metallic
    if vary:  # each object a little lighter or darker than its neighbour, so that members read apart
        info, hsv = nt.nodes.new("ShaderNodeObjectInfo"), nt.nodes.new("ShaderNodeHueSaturation")
        ramp = nt.nodes.new("ShaderNodeMapRange")
        ramp.inputs["To Min"].default_value, ramp.inputs["To Max"].default_value = 1.0 - vary, 1.0 + vary
        hsv.inputs["Color"].default_value = (*colour, 1.0)
        nt.links.new(info.outputs["Random"], ramp.inputs["Value"])
        nt.links.new(ramp.outputs["Result"], hsv.inputs["Value"])
        nt.links.new(hsv.outputs["Color"], p.inputs["Base Color"])
    return _finish(m, p.outputs["BSDF"], cut or colour, solid)


def textured(name, tex, size_m, cut, tint=(1.0, 1.0, 1.0), patch=0.0, viewport=(0.5, 0.5, 0.5)):
    """A Poly Haven ground texture laid flat on the world's X and Y, `size_m` across."""
    m, nt = _begin(name, viewport)
    n, link = nt.nodes, nt.links.new
    folder = f"//assets/polyhaven/textures/{tex}/"
    geo, mapping = n.new("ShaderNodeNewGeometry"), n.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0 / size_m, 1.0 / size_m, 1.0)
    mapping.inputs["Rotation"].default_value = (0.0, 0.0, 0.31)
    link(geo.outputs["Position"], mapping.inputs["Vector"])
    diff, rough = n.new("ShaderNodeTexImage"), n.new("ShaderNodeTexImage")
    diff.image = bpy.data.images.load(folder + f"{tex}_diff_1k.jpg", check_existing=True)
    rough.image = bpy.data.images.load(folder + f"{tex}_rough_1k.jpg", check_existing=True)
    rough.image.colorspace_settings.name = "Non-Color"
    link(mapping.outputs[0], diff.inputs[0])
    link(mapping.outputs[0], rough.inputs[0])
    mix = n.new("ShaderNodeMix")
    mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    mix.inputs[7].default_value = (*tint, 1.0)
    link(diff.outputs["Color"], mix.inputs[6])
    colour = mix.outputs[2]
    if patch:  # broad lighter and darker patches, so that the tiling does not show at a distance
        noise, ramp, mix2 = n.new("ShaderNodeTexNoise"), n.new("ShaderNodeMapRange"), n.new("ShaderNodeMix")
        noise.inputs["Scale"].default_value = 0.22
        noise.inputs["Detail"].default_value = 3.0
        ramp.inputs["To Min"].default_value, ramp.inputs["To Max"].default_value = 1.0 - patch, 1.0 + patch
        link(geo.outputs["Position"], noise.inputs["Vector"])
        link(noise.outputs["Fac"], ramp.inputs["Value"])
        mix2.data_type, mix2.blend_type = "RGBA", "MULTIPLY"
        mix2.inputs[0].default_value = 1.0
        link(colour, mix2.inputs[6])
        link(ramp.outputs["Result"], mix2.inputs[7])
        colour = mix2.outputs[2]
    p = n.new("ShaderNodeBsdfPrincipled")
    link(colour, p.inputs["Base Color"])
    link(rough.outputs["Color"], p.inputs["Roughness"])
    return _finish(m, p.outputs["BSDF"], cut, True)


def diagram(name, real, drawn, metallic=1.0, rough=0.4, only_in_section=False):
    """Its true colour in the inhabited views; a diagram's flat colour when the section is on."""
    m, nt = _begin(name, drawn)
    n, link = nt.nodes, nt.links.new
    sw = n.new("ShaderNodeGroup")
    sw.node_tree = switch_group()
    emit, mix = n.new("ShaderNodeEmission"), n.new("ShaderNodeMixShader")
    emit.inputs["Color"].default_value = (*drawn, 1.0)
    if only_in_section:
        true = n.new("ShaderNodeBsdfTransparent").outputs[0]
    else:
        p = n.new("ShaderNodeBsdfPrincipled")
        p.inputs["Base Color"].default_value = (*real, 1.0)
        p.inputs["Metallic"].default_value, p.inputs["Roughness"].default_value = metallic, rough
        true = p.outputs["BSDF"]
    link(sw.outputs["On"], mix.inputs[0])
    link(true, mix.inputs[1])
    link(emit.outputs[0], mix.inputs[2])
    return _finish(m, mix.outputs[0], drawn, False)


CUTS = {"soil": (0.36, 0.26, 0.17), "subsoil": (0.55, 0.47, 0.38), "root": (0.08, 0.05, 0.03), "floor": (0.46, 0.44, 0.41), "mulch": (0.22, 0.15, 0.1), "steel": (0.2, 0.22, 0.26), "timber": (0.33, 0.21, 0.11), "chips": (0.5, 0.36, 0.2)}


def materials() -> dict:
    return {
        "lawn": textured("STUDY_lawn", "leafy_grass", 2.2, CUTS["soil"], tint=(0.5, 0.86, 0.4), patch=0.22, viewport=(0.28, 0.42, 0.16)),
        "soil": flat("STUDY_soil", (0.2, 0.14, 0.09), CUTS["soil"], rough=0.95),
        "subsoil": flat("STUDY_subsoil", (0.38, 0.31, 0.24), CUTS["subsoil"], rough=0.95),
        "floor": textured("STUDY_floor_gravel", "pebble_ground_01", 1.5, CUTS["floor"], tint=(1.0, 0.95, 0.86), patch=0.06, viewport=(0.62, 0.58, 0.5)),
        "mulch": textured("STUDY_bed_mulch", "brown_mud_leaves_01", 1.3, CUTS["mulch"], tint=(0.6, 0.52, 0.45), patch=0.1, viewport=(0.2, 0.14, 0.09)),
        "chips": textured("STUDY_wood_chip", "wood_chip_path", 2.1, CUTS["chips"], tint=(0.55, 0.5, 0.45), viewport=(0.5, 0.36, 0.2)),
        "root": flat("STUDY_root_zone", (0.11, 0.07, 0.045), CUTS["root"], rough=0.95, solid="buried"),
        "steel": flat("STUDY_steel", (0.33, 0.36, 0.4), CUTS["steel"], rough=0.45, metallic=0.9, solid="buried"),
        "edge": flat("STUDY_steel_edge", (0.3, 0.19, 0.12), (0.2, 0.12, 0.08), rough=0.7, metallic=0.6),
        "pad": flat("STUDY_standing_pad", (0.2, 0.18, 0.15), (0.45, 0.43, 0.4), rough=1.0),
        "post": flat("STUDY_post", (0.36, 0.26, 0.16), (0.3, 0.2, 0.12), rough=0.8),
        "brass": flat("STUDY_tap", (0.7, 0.55, 0.2), (0.7, 0.55, 0.2), rough=0.35, metallic=1.0),
        "damp": flat("STUDY_damp_ground", (0.075, 0.062, 0.04), CUTS["soil"], rough=0.95),
        "line": diagram("STUDY_training_line", (0.33, 0.34, 0.35), (0.05, 0.3, 0.85), metallic=0.5, rough=0.6),
        "feeder": diagram("STUDY_feeder", (0.33, 0.34, 0.35), (0.85, 0.12, 0.08), metallic=0.5, rough=0.6),
        "tie": diagram("STUDY_handover", (0, 0, 0), (0.1, 0.6, 0.2), only_in_section=True),
        "back_soil": diagram("STUDY_cut_backing_soil", (0, 0, 0), CUTS["soil"], only_in_section=True),
        "back_subsoil": diagram("STUDY_cut_backing_subsoil", (0, 0, 0), CUTS["subsoil"], only_in_section=True),
        "drip": diagram("STUDY_drip_line", (0.05, 0.045, 0.04), (0.0, 0.5, 0.75), metallic=0.0, rough=0.6),
        "stem": flat("STUDY_climber_stem", (0.3, 0.24, 0.12), solid=False, rough=0.8),
        "leaf": flat("STUDY_climber_leaf", (0.2, 0.42, 0.1), solid=False, rough=0.6),
    }


# --- the Bower, linked -------------------------------------------------------------------------------


def link_bower(scene, colls) -> None:
    with bpy.data.libraries.load(f"//../../../releases/{SNAPSHOT}/bower.blend", link=True, relative=True) as (_, dst):
        dst.collections = ["BOWER_V1"]
    bower = dst.collections[0]
    scene.collection.children.link(bower)
    bpy.context.view_layer.update()
    for name in [c.name for c in bower.children if c.name != "70_CAMERAS"]:  # the source cameras stay in the scene; the rest is linked but not shown
        layer_of(bpy.context.view_layer.layer_collection, name).exclude = True
    timber = {}
    source = next(c for c in bower.children if c.name == "21_PRIMARY_MESHES")
    for src in source.objects:
        if src.type != "MESH":
            continue
        obj = bpy.data.objects.new(src.name, src.data)  # the same name, on the same linked mesh
        obj.matrix_world = src.matrix_world.copy()
        for key in src.keys():
            obj[key] = src[key]
        colls["S05_BOWER_TIMBER"].objects.link(obj)
        family = src.get("bower_family", "timber")
        for slot in obj.material_slots:
            if family not in timber:
                colour = tuple(0.82 * c for c in (slot.material.diffuse_color[:3] if slot.material else (0.72, 0.52, 0.3)))  # the snapshot's own colour for the family, a little deeper for sunlight
                timber[family] = flat(f"STUDY_timber_{family}", colour, CUTS["timber"], rough=0.55, vary=0.07)
            slot.link = "OBJECT"
            slot.material = timber[family]
        tag(obj, LINKED, f"member {src.get('bower_id', src.name)}: the snapshot's own milled mesh, shown with a study material")
    log(f"linked {SNAPSHOT}: {len(colls['S05_BOWER_TIMBER'].objects)} members shown, families {sorted(timber)}")


# --- the ground --------------------------------------------------------------------------------------

AXIS = [-150.0, -100.0, -70.0, -50.0, -40.0, -34.0, -29.0, -25.0, -22.0] + [k * 0.5 for k in range(-40, 41)] + [22.0, 25.0, 29.0, 34.0, 40.0, 50.0, 70.0, 100.0, 150.0]


def terrain(colls, mats) -> None:
    n = len(AXIS)
    depth = SOIL - SITE["beds"]["soil_depth_m"]
    top = [(x, y, ground_z(x, y)) for y in AXIS for x in AXIS]
    bottom = [(x, y, depth) for y in AXIS for x in AXIS]
    faces, slots = [], []
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i
            faces.append((a, a + 1, a + n + 1, a + n))
            slots.append(0)
            b = n * n + a
            faces.append((b, b + n, b + n + 1, b + 1))
            slots.append(1)
    rim = [j * n for j in range(n)] + [(n - 1) * n + i for i in range(1, n)] + [j * n + n - 1 for j in range(n - 2, -1, -1)] + [i for i in range(n - 2, 0, -1)]
    for a, b in zip(rim, rim[1:] + rim[:1]):
        faces.append((a, b, n * n + b, n * n + a))  # the rim, facing out
        slots.append(1)
    soil = add_mesh("GR_garden_soil", top + bottom, faces, colls["S10_TERRAIN"], [mats["lawn"], mats["soil"]], PROPOSAL, f"The garden's own soil, {SITE['beds']['soil_depth_m']} m of it drawn, with the lawn on top. Its level under the room, {SOIL} m, is feet_above_soil_m from bower/ground.py; the fall and the hollow are illustrative. No soil is known.")
    soil.data.polygons.foreach_set("material_index", slots)
    soil.data.update()
    block = [(-150, -150), (150, -150), (150, 150), (-150, 150)]
    add_mesh("GR_subsoil", *prism(block, SOIL - 3.4, depth), colls["S10_TERRAIN"], mats["subsoil"], PROPOSAL, "The ground below the cultivated soil, drawn so that the piles have something to stand in. Nothing is known of it.")
    # Behind the cut the drawn soil is closed off. Without this the section looks straight through it at whatever
    # stands in the ground further north: a tree's foot, a fern on the hollow's slope. Seen only when the section is on.
    y, xs = CUT_Y + BEYOND_M + 0.5, [k * 0.5 for k in range(-60, 61)]
    m = len(xs)
    wall = [(x, y, ground_z(x, y) - 0.004) for x in xs] + [(x, y, depth) for x in xs] + [(x, y, SOIL - 3.4) for x in xs]
    faces = [(i, i + 1, m + i + 1, m + i) for i in range(m - 1)] + [(m + i, m + i + 1, 2 * m + i + 1, 2 * m + i) for i in range(m - 1)]
    back = add_mesh("GR_cut_backing", wall, faces, colls["S10_TERRAIN"], [mats["back_soil"], mats["back_subsoil"]], PROPOSAL, f"A drawing device, not a thing: the soil's cut colour on a plane {BEYOND_M + 0.5} m behind the section, so that the cut ground reads as solid. Invisible unless the section is on.")
    back.data.polygons.foreach_set("material_index", [0] * (m - 1) + [1] * (m - 1))
    back.data.update()


def floor_outline():
    corners = [(RC * cos(radians(a)), RC * sin(radians(a))) for a in (-120, -60, 0, 60, 120, 180)]
    out = []
    for p, q in zip(corners, corners[1:] + corners[:1]):
        out += [(p[0] + (q[0] - p[0]) * k / 10.0, p[1] + (q[1] - p[1]) * k / 10.0) for k in range(10)]
    return out


def room_ground(colls, mats) -> None:
    rim = floor_outline()
    n = len(rim)
    rings = [0.25, 0.5, 0.75, 1.0]
    verts = [(0.0, 0.0, floor_z(0, 0))]
    for f in rings:
        verts += [(x * f, y * f, floor_z(x * f, y * f)) for x, y in rim]
    faces = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
    for r in range(len(rings) - 1):
        a, b = 1 + r * n, 1 + (r + 1) * n
        faces += [(a + i, b + i, b + (i + 1) % n, a + (i + 1) % n) for i in range(n)]
    last, low = 1 + (len(rings) - 1) * n, len(verts)
    verts += [(x, y, SOIL) for x, y in rim]
    faces += [(last + i, low + i, low + (i + 1) % n, last + (i + 1) % n) for i in range(n)]
    faces.append(tuple(low + i for i in reversed(range(n))))
    add_mesh("RG_floor", verts, faces, colls["S20_ROOM_GROUND"], mats["floor"], PROPOSAL, f"The room's floor: a bound gravel surface built up {round(floor_z(0, 0) - SOIL, 2)} m on the stripped ground, not dug into it, falling 1 in {round(1 / SITE['levels']['floor_fall'])} from the middle to the beds. It stops {round(RING - RC, 2)} m short of the piers' circle, so every pier stands in a bed.")
    for sign, name in ((-1, "south"), (1, "north")):
        ys = [EDGE + 0.002 + k * 0.4 for k in range(int((SITE["paths"]["length_m"] - EDGE) / 0.4) + 1)]
        v, f = [], []
        for y in ys:
            yy = sign * y
            for x in (-HW, HW):
                v.append((x, yy, path_top(yy)))
            for x in (-HW, HW):
                v.append((x, yy, ground_z(x, yy) + 0.003))
        for k in range(len(ys) - 1):
            a = 4 * k
            quads = [(a, a + 1, a + 5, a + 4), (a + 2, a + 6, a + 7, a + 3), (a, a + 4, a + 6, a + 2), (a + 1, a + 3, a + 7, a + 5)]
            f += quads if sign > 0 else [tuple(reversed(q)) for q in quads]
        end = 4 * (len(ys) - 1)
        caps = [(0, 2, 3, 1), (end, end + 1, end + 3, end + 2)]
        f += caps if sign > 0 else [tuple(reversed(q)) for q in caps]
        add_mesh(f"RG_path_{name}", v, f, colls["S20_ROOM_GROUND"], mats["floor"], PROPOSAL, f"The way {'in from' if sign < 0 else 'on to'} the {name}: {SITE['paths']['width_m']} m wide through an arch that is {GROUND['entrances'][0]['between_arch_legs_m']} m between its legs, level for {SITE['paths']['landing_m']} m outside the piers, then a ramp of 1 in {round(1 / SITE['paths']['ramp_gradient'])} down to the lawn.")
    # a steel edge holds the built-up floor and the landings above the beds
    parts, t = [], 0.012
    corners = [(RC * cos(radians(a)), RC * sin(radians(a))) for a in (-120, -60, 0, 60, 120, 180)]
    runs = []
    for p, q in zip(corners, corners[1:] + corners[:1]):
        if abs(p[1] - q[1]) < 1e-6 and abs(abs(p[1]) - EDGE) < 1e-6:  # a through bay: the edge stops at the path
            lo, hi = sorted((p, q))
            runs += [(lo, (-HW, lo[1])), ((HW, hi[1]), hi)]
        else:
            runs.append((p, q))
    for sign in (-1, 1):
        for x in (-HW, HW):
            runs.append(((x, sign * EDGE), (x, sign * (YL + (floor_z(0, EDGE) - SOIL) / SITE["paths"]["ramp_gradient"]))))
    for p, q in runs:
        d = Vector((q[0] - p[0], q[1] - p[1]))
        mid = Vector(((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0))
        nrm = Vector((-d.y, d.x)).normalized() * t
        beside_path = abs(abs(mid.x) - HW) < 0.01 and abs(mid.y) > EDGE + 0.01
        if (beside_path and abs(mid.x + nrm.x) < HW) or (not beside_path and (mid + nrm).length < mid.length):
            nrm = -nrm  # outside the path, or outside the floor: in the bed, not in what it holds
        gap = nrm.normalized() * 0.002
        p, q = (p[0] + gap.x, p[1] + gap.y), (q[0] + gap.x, q[1] + gap.y)
        quad = [(p[0], p[1]), (q[0], q[1]), (q[0] + nrm.x, q[1] + nrm.y), (p[0] + nrm.x, p[1] + nrm.y)]
        parts.append(prism(quad, SOIL, lambda x, y: (floor_z(x, y) if hex_norm(x, y) <= EDGE + 0.05 else path_top(y)) + 0.004))
    add_mesh("RG_edge", *merge(parts), colls["S20_ROOM_GROUND"], mats["edge"], PROPOSAL, "A steel edge holding the built-up floor and landings above the beds. Water leaves the floor over it.")


def bed_outline(side: int):
    """One crescent of bed: side +1 east, -1 west."""
    ys = sqrt(RB * RB - HW * HW)
    pts = arc(RB, atan2(-ys, HW), atan2(ys, HW)) + [(HW, EDGE)] + [(RC * cos(radians(a)), RC * sin(radians(a))) for a in (60, 0, -60)] + [(HW, -EDGE)]
    return [(side * x, y) for x, y in pts]


def stations() -> list:
    """Each pier's standing pad and the stepping pad in to it: (pier, centre, bearing, stepping pad centre)."""
    out = []
    for pier, (px, py) in GROUND["piers"].items():
        b, r = atan2(py, px), RING + SITE["care"]["station_out_m"]
        out.append((pier, (r * cos(b), r * sin(b)), b, ((RB - 0.3) * cos(b), (RB - 0.3) * sin(b))))
    return out


def beds(colls, mats, assets) -> None:
    rng = random.Random(11)
    zones = GROUND["root_zones"]
    keep_clear = [(z["position_m"], z["radius_m"] + 0.12) for z in zones] + [(p, 0.78) for p in GROUND["piers"].values()]
    keep_clear += [(c, 0.62) for _, c, _, _ in stations()] + [(s, 0.36) for _, _, _, s in stations()]
    points = {"periwinkle_plant": [], "fern_02": [], "shrub_01": [], "shrub_04": []}
    for side, name in ((1, "east"), (-1, "west")):
        outline = bed_outline(side)
        add_mesh(f"BD_{name}_surface", *prism(outline, SOIL, SOIL + MULCH), colls["S30_BEDS"], mats["mulch"], PROPOSAL, f"The {name} bed, round three piers: the garden's own soil loosened in place and mulched, {round(RB - RING, 1)} m deep beyond the piers and reaching {round(RING * cos(pi / 6) - EDGE, 2)} m into the room under each planted arch. Not a container: its soil is GR_garden_soil.")
        tries = 0
        want = {"periwinkle_plant": 80, "fern_02": 26, "shrub_01": 60, "shrub_04": 60}
        got = {k: 0 for k in want}
        while tries < 40000 and any(got[k] < want[k] for k in want):
            tries += 1
            x, y = side * rng.uniform(HW, RB), rng.uniform(-RB, RB)
            if not inside(outline, x, y) or any(hypot(x - c[0], y - c[1]) < r for c, r in keep_clear):
                continue
            h = hex_norm(x, y)
            kind = rng.choice(["periwinkle_plant", "periwinkle_plant", "fern_02"]) if h < EDGE + 1.5 else rng.choice(["shrub_01", "shrub_04", "fern_02", "shrub_01", "shrub_04"])
            if got[kind] < want[kind]:
                got[kind] += 1
                points[kind].append((x, y, SOIL + MULCH))
    scales = {"periwinkle_plant": (0.9, 1.5), "fern_02": (0.8, 1.3), "shrub_01": (1.2, 2.1), "shrub_04": (1.3, 2.2)}
    for kind, pts in points.items():
        scatter(f"BD_low_planting_{kind}", pts, assets[kind], colls["S30_BEDS"], scales[kind], BORROWED, seed=len(kind), note=f"Low planting on the beds, as newly planted: sparse, with the mulch showing. A borrowed model ({kind}, Poly Haven, CC0) standing in for a planting nobody has designed; not a species choice.")
    parts, tops = [], []
    for z in zones:
        (x, y), r = z["position_m"], z["radius_m"]
        parts.append(prism(circle(x, y, r, 40), SOIL - z["depth_m"], SOIL))
        tops.append(prism(circle(x, y, r, 40), SOIL + MULCH, SOIL + MULCH + 0.006))
    add_mesh("RZ_root_zones", *merge(parts), colls["S30_BEDS"], mats["root"], GENERATED, f"Twelve root zones, one outside each arch leg (ground.beside_pier): {zones[0]['radius_m']} m radius, {zones[0]['depth_m']} m deep, about {zones[0]['soil_m3']} m3 of kept soil each, {round(FLOOR - SOIL, 2)} m below the feet. The sizes are that code's provisional defaults, not what any plant is known to need.")
    add_mesh("RZ_root_zone_tops", *merge(tops), colls["S30_BEDS"], mats["root"], GENERATED, "The same root zones marked on the bed: ground kept for one climber each, with nothing else planted on it.")
    for z in zones:
        e = bpy.data.objects.new(f"RS_{z['id']}", None)
        e.empty_display_type, e.empty_display_size = "PLAIN_AXES", 0.3
        e.location = (*z["position_m"], SOIL)
        e["bower_id"], e["taxon_from_drawings"], e["soil_m3"], e["feeder_on"] = z["id"], z["taxon_from_drawings"], z["soil_m3"], z["feeder_on"]
        colls["S50_BOWER_PLANTING"].objects.link(e)
        tag(e, GENERATED, "A planting point at a root zone. The taxon is carried from drawings-in-code's planting for this pier; it is a label, not a check that the plant suits the place.")


def cylinder(x, y, r, z0, z1, sides=14):
    return prism(circle(x, y, r, sides), z0, z1)


def foundations(colls, mats) -> None:
    p = GROUND["piles"]
    caps, piles = [], []
    for pier, f in GROUND["footings"].items():
        caps.append(prism(f["cap_outline_m"], FLOOR - f["cap_depth_m"], FLOOR))
        for x, y in f["piles_m"]:
            piles.append(cylinder(x, y, p["shaft_m"] / 2.0, FLOOR - p["length_m"], FLOOR - f["cap_depth_m"]))
            piles.append(cylinder(x, y, p["helix_m"] / 2.0, FLOOR - p["length_m"] + 0.15, FLOOR - p["length_m"] + 0.165, 20))
    note = "Set out by bower/ground.py, which says of itself that no foundation has been designed or sized: the number of piles follows from where the feet stand, not from any load."
    add_mesh("FT_pile_caps", *merge(caps), colls["S40_FOUNDATIONS"], mats["steel"], GENERATED, f"A steel cap under each pier, {GROUND['footings']['R1.P1']['cap_area_m2']} m2, its top at the feet and its underside {round(FLOOR - SOIL - p['cap_depth_m'], 2)} m clear of the soil. {note}")
    add_mesh("PL_screw_piles", *merge(piles), colls["S40_FOUNDATIONS"], mats["steel"], GENERATED, f"Three screw piles under each cap, {p['length_m']} m long, {p['spacing_m']} m apart. {note}")


def supports(colls, mats) -> None:
    r = 0.004
    thick = "Drawn 8 mm thick so that it can be seen; the cable is 4 mm."
    poly_curve("LN_training_lines", [l["points_m"] for l in GROUND["training_lines"]], r, colls["S45_SUPPORTS"], mats["line"], GENERATED, f"The 24 training lines bower/lines.py strings on the members that stand on the floor: {round(sum(l['length_m'] for l in GROUND['training_lines']), 1)} m of cable, standing off the timber's outer face. They are not in the snapshot; they are worked out again from its design. {thick}")
    poly_curve("LN_feeders", [l["points_m"] for l in GROUND["feeders"]], r, colls["S45_SUPPORTS"], mats["feeder"], GENERATED, f"The feeders: a plant's way from its root zone up the outside of an arch leg and round to the arch's back. {thick}")
    h = GROUND["handovers"]
    poly_curve("HO_handovers", [[x["start_m"], x["end_m"]] for x in h], 0.008, colls["S45_SUPPORTS"], mats["tie"], GENERATED, f"Where a gardener leads a shoot from a feeder across to a training line: {len(h)} places, between {min(x['height_m'] for x in h)} and {max(x['height_m'] for x in h)} m above the floor. Nothing is built there. Shown only when the section is on.")


def climbers(colls, mats) -> None:
    """One climber at each root zone as it might go in: a tied stem on its feeder, with a few leaves. A diagram."""
    rng = random.Random(5)
    feeders = {l["id"]: l["points_m"] for l in GROUND["feeders"]}
    top = SOIL + SITE["planting_at_installation"]["cane_height_m"]
    stems, leaf_v, leaf_f = [], [], []
    for z in GROUND["root_zones"]:
        line = feeders.get(z["feeder_on"] + ".feeder")
        if not line:
            continue
        x, y = z["position_m"]
        foot = Vector(line[0])
        run = [Vector((x, y, SOIL + MULCH)), Vector((x, y, SOIL + MULCH + 0.12)).lerp(foot, 0.35), Vector((x, y, SOIL + 0.3)).lerp(foot, 0.8), foot]
        for a, b in zip(line, line[1:]):
            a, b = Vector(a), Vector(b)
            if b.z >= top:
                run.append(a.lerp(b, (top - a.z) / (b.z - a.z)))
                break
            run.append(b)
        stems.append([tuple(p) for p in run])
        # leaves every hand's breadth up the stem, turned at random
        fine = []
        for a, b in zip(run, run[1:]):
            steps = max(1, int((b - a).length / 0.1))
            fine += [a.lerp(b, k / steps) for k in range(steps)]
        for p in fine[3:]:
            turn, size = rng.uniform(0, 2 * pi), rng.uniform(0.06, 0.11)
            out = Vector((cos(turn), sin(turn), -0.45)).normalized()
            side = Vector((-sin(turn), cos(turn), 0.0)) * size * 0.32
            base = p + out * 0.015
            k = len(leaf_v)
            leaf_v += [tuple(base), tuple(base + out * size * 0.5 + side), tuple(base + out * size), tuple(base + out * size * 0.5 - side)]
            leaf_f.append((k, k + 1, k + 2, k + 3))
    poly_curve("BP_climber_stems", stems, 0.007, colls["S50_BOWER_PLANTING"], mats["stem"], PROPOSAL, f"Twelve climbers as they might go in, {SITE['planting_at_installation']['cane_height_m']} m long, each tied to the feeder nearest its root zone. A diagram of an installed plant: not grown, not simulated, and no shade.")
    add_mesh("BP_climber_leaves", leaf_v, leaf_f, colls["S50_BOWER_PLANTING"], mats["leaf"], PROPOSAL, "Leaves on those stems, to show how little a new plant covers.")


def care(colls, mats) -> None:
    c = SITE["care"]
    r0, r1 = c["path_radius_m"] - c["path_width_m"] / 2.0, c["path_radius_m"] + c["path_width_m"] / 2.0
    a = atan2(sqrt(c["path_radius_m"] ** 2 - HW * HW), HW)
    for side, name in ((1, "east"), (-1, "west")):
        ring = [(side * x, y) for x, y in arc(r1, -a, a) + list(reversed(arc(r0, -a, a)))]
        add_mesh(f"CP_care_path_{name}", *prism(ring, SOIL, SOIL + 0.08), colls["S65_CARE"], mats["chips"], PROPOSAL, f"A woodchip path round the back of the {name} bed, {c['path_width_m']} m wide, leaving the approach on the ramp {round(sqrt(c['path_radius_m'] ** 2 - HW * HW) - RING * cos(pi / 6), 1)} m short of the entrance: the way to every pier's outer side that crosses neither the entrance nor a bed.")
    slabs, steps = [], []
    w, d = c["station_size_m"]
    for pier, (cx, cy), b, (sx, sy) in stations():
        u, t = Vector((cos(b), sin(b))), Vector((-sin(b), cos(b)))
        quad = [(cx + sa * u.x * d / 2 + sb * t.x * w / 2, cy + sa * u.y * d / 2 + sb * t.y * w / 2) for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        slabs.append(prism(quad, SOIL + MULCH - 0.01, SOIL + MULCH + 0.05))
        steps.append(prism(circle(sx, sy, c["pad_m"] / 2.0, 20), SOIL + MULCH - 0.01, SOIL + MULCH + 0.04))
    add_mesh("CP_standing_pads", *merge(slabs), colls["S65_CARE"], mats["pad"], PROPOSAL, f"A standing pad outside each pier, {w} by {d} m, between its two root zones: firm ground for a pair of steps, since the hand-overs are {GROUND['report']['handover_height_m'][0]} to {GROUND['report']['handover_height_m'][1]} m up. It is also {round(c['station_out_m'] - 0.52, 2)} m from the root zones' middles, on ground their roots would otherwise have.")
    add_mesh("CP_stepping_pads", *merge(steps), colls["S65_CARE"], mats["pad"], PROPOSAL, "A stepping pad from the care path in to each standing pad, so that the bed is crossed in one place.")


def water(colls, mats, assets) -> None:
    w = SITE["water"]
    sx, sy = w["standpipe_m"]
    g = ground_z(sx, sy)
    post = [(sx - 0.045, sy - 0.045), (sx + 0.045, sy - 0.045), (sx + 0.045, sy + 0.045), (sx - 0.045, sy + 0.045)]
    add_mesh("WA_standpipe", *prism(post, g - 0.05, g + 1.05), colls["S60_WATER"], mats["post"], PROPOSAL, "A standpipe where the care path leaves the approach: the proposed source of water for the establishment years. Where its supply comes from is not known: there is no site.")
    tap = [(sx + 0.045, sy - 0.02), (sx + 0.16, sy - 0.02), (sx + 0.16, sy + 0.02), (sx + 0.045, sy + 0.02)]
    add_mesh("WA_tap", *prism(tap, g + 0.86, g + 0.9), colls["S60_WATER"], mats["brass"], PROPOSAL, "The tap.")
    z = SOIL + MULCH + 0.012
    r = w["drip_radius_m"]
    a = atan2(sqrt(r * r - (HW + 0.15) ** 2), HW + 0.15)
    east = [(x, y, z) for x, y in arc(r, -a, a, 2.0)]
    west = [(-x, y, z) for x, y, _ in east]
    under = [(west[0][0], west[0][1], SOIL + 0.02), (east[0][0], east[0][1], SOIL + 0.02)]
    feed = [(sx, sy, g + 0.2), (sx, sy, g + 0.02), (sx + 0.5, sy + 0.9, SOIL + 0.02), west[0]]
    rings = [[(zx + 0.36 * cos(2 * pi * k / 28), zy + 0.36 * sin(2 * pi * k / 28), z) for k in range(29)] for zx, zy in (q["position_m"] for q in GROUND["root_zones"])]
    spurs = []
    for q in GROUND["root_zones"]:
        zx, zy = q["position_m"]
        b = atan2(zy, zx)
        spurs.append([(r * cos(b), r * sin(b), z), (zx + 0.36 * cos(b), zy + 0.36 * sin(b), z)])
    poly_curve("WA_drip_line", [east, west, under, feed] + rings + spurs, 0.009, colls["S60_WATER"], mats["drip"], PROPOSAL, f"A drip line from the standpipe round the back of both beds, {round(r - RING, 2)} m outside the piers, with a ring at each root zone and a sleeve under the approach: water put where the new roots are, for the establishment years. How much, how often and for how long are the plant side's to say.")
    hx, hy = w["hollow_m"]
    wobble = [1.0 + 0.1 * sin(2 * pi * k / 28 * 2 + 0.7) + 0.06 * sin(2 * pi * k / 28 * 3) for k in range(28)]
    damp = [(hx + (x - hx) * f, hy + (y - hy) * f) for f, (x, y) in zip(wobble, circle(hx, hy, w["hollow_radius_m"] * 0.4, 28))]
    damp = [(x, y, ground_z(x, y) + 0.015) for x, y in damp]
    add_mesh("WA_damp_hollow", [(hx, hy, ground_z(hx, hy) + 0.015)] + damp, [(0, 1 + k, 1 + (k + 1) % 28) for k in range(28)], colls["S60_WATER"], mats["damp"], PROPOSAL, f"The low point of the garden, {w['hollow_depth_m']} m down, north-east of the room: where water that the floor sheds and the beds do not hold is meant to go. Its use to other life is an intention, not a finding.")
    rng = random.Random(3)
    pts = []
    while len(pts) < 34:
        t, d = rng.uniform(0, 2 * pi), w["hollow_radius_m"] * rng.uniform(0.35, 1.05)
        x, y = hx + d * cos(t), hy + d * sin(t)
        pts.append((x, y, ground_z(x, y) + 0.06))
    scatter("WA_hollow_ferns", pts, assets["fern_02"], colls["S60_WATER"], (1.0, 1.8), BORROWED, "Ferns round the damp hollow: a borrowed model (fern_02, Poly Haven, CC0) marking ground that is meant to stay wet.")


# --- borrowed things ---------------------------------------------------------------------------------


def asset(colls, name: str, prefer=("_LOD1", "_LOD2", "_LOD0", "_geometry")):
    """A Poly Haven model's collection, linked: the lightest of the levels of detail that still reads."""
    path = f"//assets/polyhaven/models/{name}/{name}_1k.blend"
    with bpy.data.libraries.load(path, link=True, relative=True) as (src, dst):
        pick = next((c for p in prefer for c in src.collections if c == name + p), None) or name
        dst.collections = [pick]
    c = dst.collections[0]
    colls["S99_ASSET_SOURCES"].children.link(c)
    log(f"asset {name}: collection {c.name}, {len(c.objects)} objects, {sum(len(o.data.polygons) for o in c.objects if o.type == 'MESH')} faces")
    return c


def scatter(name, points, source, coll, scale, status, note, seed=0):
    """Instances of the objects of `source`, one picked for each point, turned and sized at random."""
    ng = bpy.data.node_groups.new(f"STUDY_scatter_{name}", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, link = ng.nodes, ng.links.new
    gin, gout = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    info, place = n.new("GeometryNodeCollectionInfo"), n.new("GeometryNodeInstanceOnPoints")
    info.inputs[0].default_value = source
    info.inputs["Separate Children"].default_value = True
    info.inputs["Reset Children"].default_value = True
    place.inputs["Pick Instance"].default_value = True
    turn, size = n.new("FunctionNodeRandomValue"), n.new("FunctionNodeRandomValue")
    turn.data_type, size.data_type = "FLOAT_VECTOR", "FLOAT"

    def socket(sockets, kind, called=None):  # this node keeps a Min, a Max and a Value for every type it can make
        return next(s for s in sockets if s.type == kind and (called is None or s.name == called))

    socket(turn.inputs, "VECTOR", "Min").default_value, socket(turn.inputs, "VECTOR", "Max").default_value = (0.0, 0.0, 0.0), (0.0, 0.0, 2 * pi)
    socket(size.inputs, "VALUE", "Min").default_value, socket(size.inputs, "VALUE", "Max").default_value = scale
    turn.inputs["Seed"].default_value, size.inputs["Seed"].default_value = seed, seed + 1
    link(gin.outputs[0], place.inputs["Points"])
    link(info.outputs[0], place.inputs["Instance"])
    link(socket(turn.outputs, "VECTOR"), place.inputs["Rotation"])
    link(socket(size.outputs, "VALUE"), place.inputs["Scale"])
    link(place.outputs[0], gout.inputs[0])
    obj = add_mesh(name, [tuple(p) for p in points], [], coll, None, status, note)
    obj.modifiers.new("scatter", "NODES").node_group = ng
    obj["study_instances"] = len(points)
    return obj


def instance(name, source, coll, at, scale, turn_deg, status, note):
    e = bpy.data.objects.new(name, None)
    e.instance_type, e.instance_collection = "COLLECTION", source
    e.empty_display_size = 0.5
    e.location, e.scale, e.rotation_euler = at, (scale,) * 3, (0.0, 0.0, radians(turn_deg))
    coll.objects.link(e)
    return tag(e, status, note)


def garden(colls, assets) -> None:
    g = SITE["garden"]
    for k, (x, y, s, t) in enumerate(g["trees"]):
        instance(f"GD_tree_{k + 1}", assets["tree_small_02"], colls["S70_GARDEN"], (x, y, ground_z(x, y) + 0.04), s * 1.35, t, BORROWED, "A garden tree north or north-east of the room, behind it as you arrive, leaving the south and west open to the sun. A borrowed model (tree_small_02, Poly Haven, CC0) for a small deciduous tree; no species is meant.")
    b = g["border"]
    rng = random.Random(8)
    for k in range(b["count"]):
        a = radians(b["from_deg"] + (b["to_deg"] - b["from_deg"]) * k / (b["count"] - 1))
        r = b["radius_m"] + rng.uniform(-0.7, 0.9)
        x, y = r * cos(a), r * sin(a)
        instance(f"GD_border_{k + 1}", assets["tree_small_02"], colls["S70_GARDEN"], (x, y, ground_z(x, y) + 0.02), rng.uniform(*b["scale"]) * 1.35, rng.uniform(0, 360), BORROWED, "The border north-west of the room: a back to the care path and cover at the garden's edge, placed so that it does not stand between the beds and the afternoon sun. The same borrowed tree at shrub size; its use to birds and insects is an intention, not a finding.")
    lx, ly, lt = g["log_m"]
    instance("GD_log", assets["dead_tree_trunk"], colls["S70_GARDEN"], (lx, ly, ground_z(lx, ly) + 0.02), 1.0, lt, BORROWED, "A log left by the border: dead wood kept on purpose. A borrowed model (dead_tree_trunk, Poly Haven, CC0); what lives in it is not claimed.")
    c = SITE["care"]
    r0, r1 = c["path_radius_m"] + c["path_width_m"] / 2.0 + 0.05, SITE["water"]["level_radius_m"]
    tufts, flowers = [], []
    while len(tufts) < 420:
        t, r = rng.uniform(0, 2 * pi), rng.uniform(r0, r1)
        x, y = r * cos(t), r * sin(t)
        if abs(x) < HW + 0.5:
            continue
        tufts.append((x, y, ground_z(x, y) + 0.02))
        if len(tufts) % 6 == 0:
            flowers.append((x + 0.12, y + 0.08, ground_z(x, y) + 0.01))
    scatter("GD_unmown_strip", tufts, assets["grass_medium_02"], colls["S70_GARDEN"], (1.3, 2.4), BORROWED, f"A strip left unmown outside the care path, {round(r1 - r0, 1)} m wide: longer grass between the beds and the lawn. A borrowed model (grass_medium_02, Poly Haven, CC0); its use to insects is an intention.")
    scatter("GD_unmown_flowers", flowers, assets["dandelion_01"], colls["S70_GARDEN"], (1.2, 1.9), BORROWED, "Flowers in the unmown strip (dandelion_01, Poly Haven, CC0).")


# --- people ------------------------------------------------------------------------------------------

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
ARMS = [("L UpperArm", Y, 42), ("R UpperArm", Y, -42), ("L Forearm", X, -10), ("R Forearm", X, -12)]
# a figure as imported faces -Y with its left to +X. A turn is about an axis of that frame, through the joint:
# about X, a hanging limb swings forward for a negative angle; about Y, the left arm drops for a positive one.
POSES = {
    "stand": ARMS + [("L Thigh", X, -5), ("Head", X, 10), ("Head", Z, 14)],
    "walk": ARMS + [("L Thigh", X, -22), ("L Calf", X, 10), ("R Thigh", X, 14), ("R Calf", X, 26), ("L UpperArm", X, 20), ("R UpperArm", X, -20), ("L Forearm", X, -12), ("R Forearm", X, -24), ("Spine1", X, 3)],
    "walk_b": ARMS + [("R Thigh", X, -22), ("R Calf", X, 10), ("L Thigh", X, 14), ("L Calf", X, 26), ("R UpperArm", X, 20), ("L UpperArm", X, -20), ("R Forearm", X, -12), ("L Forearm", X, -24), ("Head", Z, -20)],
    "talk": ARMS + [("R UpperArm", X, -24), ("R Forearm", X, -68), ("R Thigh", X, -4), ("Head", Z, -12)],
    "look_up": ARMS + [("Spine2", X, -5), ("Neck", X, -14), ("Head", X, -24), ("L Thigh", X, -4)],
    "tend": [("L UpperArm", Z, -62), ("R UpperArm", Z, 62), ("L UpperArm", X, -62), ("R UpperArm", X, -70), ("L Forearm", X, -26), ("R Forearm", X, -32), ("Neck", X, -8), ("Head", X, -14), ("R Thigh", X, -8)],
}


def figure(colls, avatar: str, pose: str, at, facing_deg: float, does: str, name: str):
    folder = HERE / "assets" / "rocketbox" / avatar
    before = set(bpy.data.objects)
    images = set(bpy.data.images)
    bpy.ops.wm.fbx_import(filepath=str(folder / f"{avatar}.fbx"))
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == "ARMATURE")
    body = [o for o in new if o.type == "MESH"]
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        if o.type in ("ARMATURE", "MESH"):
            colls["S80_PEOPLE"].objects.link(o)
        else:
            bpy.data.objects.remove(o)
    for image in set(bpy.data.images) - images:  # the file names 2048 px TGAs on its author's disk; the study has its own reduced copies
        bpy.data.images.remove(image)
    textures = {p.stem.split("_")[1]: p for p in (folder / "textures").iterdir()}
    for o in body:
        for slot in o.material_slots:
            m = slot.material
            key = next((k for k in ("head", "opacity", "body") if k in m.name.lower()), "body")
            m.use_nodes = True
            nt = m.node_tree
            nt.nodes.clear()
            out, p, t = nt.nodes.new("ShaderNodeOutputMaterial"), nt.nodes.new("ShaderNodeBsdfPrincipled"), nt.nodes.new("ShaderNodeTexImage")
            p.inputs["Roughness"].default_value = 0.75
            t.image = bpy.data.images.load(f"//assets/rocketbox/{avatar}/textures/{textures[key].name}", check_existing=True)
            nt.links.new(t.outputs["Color"], p.inputs["Base Color"])
            if key == "opacity":
                nt.links.new(t.outputs["Alpha"], p.inputs["Alpha"])
            nt.links.new(p.outputs["BSDF"], out.inputs["Surface"])
    bpy.context.view_layer.update()
    bones = {b.name.split(" ", 1)[1]: b for b in arm.pose.bones if " " in b.name}
    for bone, axis, deg in POSES[pose]:
        pb, mw = bones[bone], arm.matrix_world
        m = mw @ pb.matrix
        h = m.translation.copy()
        pb.matrix = mw.inverted() @ (Matrix.Translation(h) @ Matrix.Rotation(radians(deg), 4, axis) @ Matrix.Translation(-h) @ m)
        bpy.context.view_layer.update()
    # stand the posed figure on the ground: its lowest point to zero
    dg = bpy.context.evaluated_depsgraph_get()
    low = min((o.evaluated_get(dg).matrix_world @ v.co).z for o in body for v in o.evaluated_get(dg).data.vertices)
    root = bpy.data.objects.new(name, None)
    root.empty_display_type, root.empty_display_size = "ARROWS", 0.4
    colls["S80_PEOPLE"].objects.link(root)
    arm.location.z -= low
    arm.parent = root
    arm.name, arm.data.name = f"{name}_rig", f"{name}_rig"
    for o in body:
        o.name = f"{name}_body"
        tag(o, BORROWED, f"{avatar}, Microsoft Rocketbox (MIT).")
    tag(arm, BORROWED, f"{avatar}'s rig, posed '{pose}' by turning its joints (POSES in build_scene.py).")
    root.location = (at[0], at[1], surface_z(at[0], at[1]) if len(at) < 3 else at[2])
    root.rotation_euler = (0.0, 0.0, radians(facing_deg + 90.0))
    tag(root, BORROWED, f"Someone {does}. A borrowed figure ({avatar}, Microsoft Rocketbox, MIT), here for scale and to show the room in use.")
    return root


def people(colls) -> None:
    pads = {pier: c for pier, c, _, _ in stations()}
    for k, p in enumerate(SITE["people"]):
        at = list(p["at_m"])
        if any(hypot(at[0] - c[0], at[1] - c[1]) < 0.5 for c in pads.values()):
            at.append(SOIL + MULCH + 0.05)  # on a standing pad
        figure(colls, p["avatar"], p["pose"], at, p["facing_deg"], p["does"], f"PP_{k + 1}_{p['does'].split(',')[0].split(' ')[0]}")
    log(f"people: {len(SITE['people'])} figures")


# --- sky, cameras, rendering -------------------------------------------------------------------------

SUN_UV = (0.6005, 0.6499)  # where the sun is in meadow_2_2k.hdr, measured from its brightest pixels


def sky(scene) -> None:
    world = bpy.data.worlds.new("STUDY_sky")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    n, link = nt.nodes, nt.links.new
    coord, mapping, env = n.new("ShaderNodeTexCoord"), n.new("ShaderNodeMapping"), n.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load("//assets/polyhaven/hdris/meadow_2_2k.hdr", check_existing=True)
    phi = (SUN_UV[0] - 0.5) * 2 * pi
    # A direction at angle a (anticlockwise from east) reads the photograph at u = 0.5 - a / 360, so its sun stands at
    # -phi; turning the mapping by r moves everything by -r. Both were checked against the shadows in two renders.
    # Mirrored, the photograph is read at r - a instead: the same sky with left and right exchanged.
    want = radians(90.0 - SITE["setting"]["sun_azimuth_deg"])
    if SITE["setting"]["sky_mirrored"]:
        mapping.inputs["Scale"].default_value = (1.0, -1.0, 1.0)
        mapping.inputs["Rotation"].default_value = (0.0, 0.0, want - phi)
    else:
        mapping.inputs["Rotation"].default_value = (0.0, 0.0, -phi - want)
    link(coord.outputs["Generated"], mapping.inputs["Vector"])
    link(mapping.outputs[0], env.inputs[0])
    photo, paper, mix, out = n.new("ShaderNodeBackground"), n.new("ShaderNodeBackground"), n.new("ShaderNodeMixShader"), n.new("ShaderNodeOutputWorld")
    paper.inputs["Color"].default_value = (0.9, 0.89, 0.86, 1.0)
    paper.inputs["Strength"].default_value = 1.5
    link(env.outputs[0], photo.inputs["Color"])
    sw, path, both = n.new("ShaderNodeGroup"), n.new("ShaderNodeLightPath"), n.new("ShaderNodeMath")
    sw.node_tree = switch_group()
    both.operation = "MULTIPLY"
    link(sw.outputs["On"], both.inputs[0])
    link(path.outputs["Is Camera Ray"], both.inputs[1])
    link(both.outputs[0], mix.inputs[0])
    link(photo.outputs[0], mix.inputs[1])
    link(paper.outputs[0], mix.inputs[2])
    link(mix.outputs[0], out.inputs["Surface"])
    world["study_status"] = BORROWED
    world["study_note"] = f"meadow_2 (Poly Haven, CC0), {'mirrored and ' if SITE['setting']['sky_mirrored'] else ''}turned so that its sun stands at {SITE['setting']['sun_azimuth_deg']} degrees: its light, its height ({round((SUN_UV[1] - 0.5) * 180)} degrees) and its distant trees are the photograph's. Behind the section it gives way to plain paper."


def cameras(scene, colls) -> dict:
    made = {}
    c = SITE["cameras"]
    a = c["arrival"]
    data = bpy.data.cameras.new("CAM_arrival")
    data.lens, data.clip_start, data.clip_end = a["lens_mm"], 0.1, 600.0
    cam = bpy.data.objects.new("CAM_arrival", data)
    x, y, eye = a["location_m"]
    cam.location = (x, y, surface_z(x, y) + eye)
    cam.rotation_euler = (Vector(a["target_m"]) - cam.location).to_track_quat("-Z", "Y").to_euler()
    made["arrival"] = tag(cam, PROPOSAL, f"{a['note']} {eye} m above the path.")
    s = c["section"]
    data = bpy.data.cameras.new("CAM_section")
    data.type, data.ortho_scale = "ORTHO", s["width_m"]
    data.clip_start, data.clip_end = 30.0, 400.0  # the near plane is the cut
    cam = bpy.data.objects.new("CAM_section", data)
    cam.location = (s["centre_m"][0], CUT_Y - 30.0, s["centre_m"][1])
    cam.rotation_euler = (radians(90.0), 0.0, 0.0)
    made["section"] = tag(cam, PROPOSAL, f"{s['note']} Looking north. Its near clipping plane is the cut; turn the section switch on with it (see `render` in build_scene.py).")
    data = bpy.data.cameras.new("CAM_site_plan")
    data.type, data.ortho_scale, data.clip_end = "ORTHO", c["site_plan"]["width_m"], 400.0
    cam = bpy.data.objects.new("CAM_site_plan", data)
    cam.location = (0.0, 0.0, 60.0)
    made["plan"] = tag(cam, PROPOSAL, "The site from above, north up: for checking the two views against one layout.")
    for cam in made.values():
        colls["S90_CAMERAS"].objects.link(cam)
    scene.camera = made["arrival"]
    return made


def render_settings(scene, samples: int) -> None:
    scene.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for device in prefs.devices:
            device.use = device.type == "OPTIX"
        scene.cycles.device = "GPU" if any(d.use for d in prefs.devices) else "CPU"
    except Exception as error:  # no such card: the processor will do
        scene.cycles.device = "CPU"
        log(f"render on the processor: {error}")
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.transparent_max_bounces = 24
    scene.cycles.max_bounces = 6
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = -0.35
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            scene.view_settings.look = look
            break
        except TypeError:
            continue
    scene.render.image_settings.file_format = "PNG"


SIZES = {"arrival": (1920, 1200), "section": (3000, 1350), "plan": (1500, 1500)}


def render(scene, cams: dict, colls: dict, views: list, samples: int, out_dir: Path) -> None:
    switch = bpy.data.node_groups["STUDY_section_switch"].nodes
    notes = colls["S95_SECTION_NOTES"]
    out_dir.mkdir(parents=True, exist_ok=True)
    for view in views:
        scene.camera = cams[view]
        on = view == "section"
        switch["section_on"].outputs[0].default_value = 1.0 if on else 0.0
        notes.hide_render = not on
        scene.cycles.samples = samples if view == "arrival" else max(32, samples // 2)
        scene.render.resolution_x, scene.render.resolution_y = SIZES[view]
        scene.render.filepath = str(out_dir / f"{view}.png")
        started = time.time()
        bpy.ops.render.render(write_still=True)
        log(f"rendered {view} at {SIZES[view]} in {round(time.time() - started)} s")
    switch["section_on"].outputs[0].default_value = 0.0
    notes.hide_render = True
    scene.camera = cams["arrival"]


# --- the whole ---------------------------------------------------------------------------------------


def build(samples: int = 96):
    here = Path(bpy.data.filepath) if bpy.data.filepath else None
    if here and here.resolve() != BLEND.resolve():
        raise RuntimeError(f"build_scene.py starts from an empty file and would discard {here.name}. Run it in a new, unsaved Blender file, or with {BLEND.name} open.")
    bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
    scene = bpy.context.scene
    scene.unit_settings.system, scene.unit_settings.scale_length = "METRIC", 1.0
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))  # first, so that the relative links have somewhere to be relative to
    colls = make_collections(scene)
    mats = materials()
    link_bower(scene, colls)
    assets = {name: asset(colls, name) for name in ("tree_small_02", "shrub_01", "shrub_04", "fern_02", "periwinkle_plant", "dandelion_01", "grass_medium_02", "dead_tree_trunk")}
    terrain(colls, mats)
    room_ground(colls, mats)
    beds(colls, mats, assets)
    foundations(colls, mats)
    supports(colls, mats)
    climbers(colls, mats)
    care(colls, mats)
    water(colls, mats, assets)
    garden(colls, assets)
    people(colls)
    sky(scene)
    cams = cameras(scene, colls)
    render_settings(scene, samples)
    view = bpy.context.view_layer
    for name in ("S99_ASSET_SOURCES",):
        layer_of(view.layer_collection, name).exclude = True
    sys.path.insert(0, str(HERE))
    import section_notes

    section_notes.add(colls["S95_SECTION_NOTES"], SITE, GROUND, CUT_Y, tag, PROPOSAL)
    colls["S95_SECTION_NOTES"].hide_render = True
    scene["study"] = "inhabited-room: the six-bay Bower as a place, at installation"
    scene["study_baseline"] = f"releases/{SNAPSHOT}, linked"
    scene["study_section"] = "Set node group STUDY_section_switch > section_on to 1 and look through CAM_section; show S95_SECTION_NOTES."
    scene["study_statuses"] = " | ".join((LINKED, GENERATED, PROPOSAL, BORROWED))
    bpy.ops.wm.save_mainfile()
    log(f"saved {BLEND.name}: {len(bpy.data.objects)} objects")
    return scene, colls, cams


def pose_sheet(out_dir: Path) -> None:
    """Every figure in its pose, in a row: for checking the poses before they go into the scene."""
    bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
    scene = bpy.context.scene
    sheet = HERE / "_poses.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(sheet))
    colls = make_collections(scene)
    for k, p in enumerate(SITE["people"]):
        figure(colls, p["avatar"], p["pose"], (k * 1.5, 0.0, 0.0), -90.0 + (35.0 if k % 2 else -35.0), p["does"], f"PP_{k + 1}")
        figure(colls, p["avatar"], p["pose"], (k * 1.5, 6.0, 3.2), -90.0 + 90.0, p["does"], f"PPs_{k + 1}")
    add_mesh("ground", [(-30, -30, 0), (30, -30, 0), (30, 30, 0), (-30, 30, 0)], [(0, 1, 2, 3)], colls["S10_TERRAIN"], flat("ground", (0.5, 0.5, 0.48)))
    sky(scene)
    data = bpy.data.cameras.new("poses")
    data.type, data.ortho_scale = "ORTHO", 1.5 * len(SITE["people"]) + 0.6
    cam = bpy.data.objects.new("poses", data)
    cam.location, cam.rotation_euler = (0.75 * (len(SITE["people"]) - 1), -20.0, 2.55), (radians(90.0), 0.0, 0.0)
    scene.collection.objects.link(cam)
    scene.camera = cam
    render_settings(scene, 24)
    scene.render.resolution_x, scene.render.resolution_y = 1800, 1080
    scene.render.filepath = str(out_dir / "poses.png")
    bpy.ops.render.render(write_still=True)
    sheet.unlink(missing_ok=True)
    log("pose sheet rendered")


def main(argv=None) -> None:
    argv = list(argv or [])
    try:
        samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 96
        views = argv[argv.index("--render") + 1].split(",") if "--render" in argv else []
        out_dir = Path(argv[argv.index("--out") + 1]) if "--out" in argv else HERE / "views"
        if "--poses" in argv:
            pose_sheet(out_dir)
            return
        scene, colls, cams = build(samples)
        render(scene, cams, colls, views, samples, out_dir)
        bpy.ops.wm.save_mainfile()
        log("done")
    except Exception:
        log("FAILED\n" + traceback.format_exc())


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
