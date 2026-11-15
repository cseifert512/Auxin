"""Build the inhabited-room study: the six-bay Bower as a place, in one editable Blender scene.

    blender-launcher.exe --background --factory-startup --disable-autoexec --python build_scene.py -- [--render arrival,lookout,section,plant,whole,plan] [--samples 96] [--scale 0.5]

or, in a Blender with a window, from the Python console:

    import runpy; runpy.run_path(r"<this folder>\\build_scene.py")["main"](["--render", "arrival,section"])

It starts from an empty file every time and writes inhabited_room.blend beside itself, so the scene
can be thrown away and made again. What goes into it, and where each part comes from:

    linked      the timber and the source cameras, from ../../../releases/<snapshot>/bower.blend. The
                snapshot's own collection BOWER_V1 is linked whole; its timber objects are shown through
                S05_BOWER_TIMBER, local objects of the same names on the same linked meshes, because the
                snapshot's materials carry no colour a path tracer can use and a linked material cannot
                be given one.
    generated   each pier's own level, the trunk cables and their standoffs, the joints: the building
                model's own code on the snapshot's design (set_out_ground.py, ground/<configuration>.json).
    proposal    the site (site.json: the lie of the land, floor, paths, beds, swale, hollow, wall), the
                steel sole and piles under each pier, where each climber is planted, the mesh round the
                joints. Authored for this study; every size provisional.
    carried     which climber goes with which leg, from drawings-in-code's planting.
    borrowed    people, surrounding vegetation, ground textures and the sky (assets.json, fetch_assets.py).

Every object carries `study_status` (one of those) and `study_note` (what it is for).

One switch draws a section. The node group STUDY_section_switch holds two numbers, `section_on` and
`section_y`. With section_on at 1 every study material hides what lies on the camera's side of
section_y and paints the inside of each solid it has cut with a flat colour; CAM_section and CAM_plant
clip everything else at the same plane. `render()` sets the switch for each view and puts it back to
0, so the file is saved inhabited.

A windowless Blender prints nothing back: progress and errors go to build.log.
"""
from __future__ import annotations

import json
import random
import sys
import time
import traceback
from math import atan2, cos, degrees, exp, hypot, pi, radians, sin, sqrt  # noqa: F401
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
SITE = json.loads((HERE / "site.json").read_text(encoding="utf-8"))
_ARGS = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
CONFIG = _ARGS[_ARGS.index("--config") + 1] if "--config" in _ARGS else SITE["default_configuration"]
CFG = SITE["configurations"][CONFIG]  # which snapshot, footing and planting: see site.json
GROUND = json.loads((HERE / "ground" / f"{CONFIG}.json").read_text(encoding="utf-8"))
BLEND = HERE / ("inhabited_room.blend" if CONFIG == SITE["default_configuration"] else f"inhabited_room.{CONFIG}.blend")
SNAPSHOT = CFG["snapshot"]
LOG = HERE / "build.log"

LINKED = "linked: snapshot geometry, unchanged"
GENERATED = "generated: the building model's own code on the snapshot's design (set_out_ground.py)"
PROPOSAL = "proposal: authored for this study, provisional"
BORROWED = "borrowed asset: not Bower geometry or planting (assets.json)"
CARRIED = "carried: which climber goes with which leg, from drawings-in-code's planting"

LAND = SITE["ground"]
LEVEL = GROUND["pier_levels_m"]  # the underside of each pier's timber feet
FLOOR = GROUND["floor_z_m"]  # the feet of the highest pier
SUNK = LAND["feet_below_soil_m"]  # how far the timber feet run into the soil: no footing is seen
GX, GY = -LAND["fall"] * cos(radians(LAND["fall_towards_deg"])), -LAND["fall"] * sin(radians(LAND["fall_towards_deg"]))
_TOP = max(LEVEL, key=LEVEL.get)
Z0 = LEVEL[_TOP] + SUNK - (GX * GROUND["piers"][_TOP][0] + GY * GROUND["piers"][_TOP][1])  # the ground's level under the crown
RING = hypot(*next(iter(GROUND["piers"].values())))  # the piers' circle
RF = SITE["floor"]["radius_m"]
BUILDUP = SITE["floor"]["buildup_m"]
RB_SHELTER, RB_SUN = SITE["beds"]["sheltered_outer_radius_m"], SITE["beds"]["outer_radius_m"]
MULCH = SITE["beds"]["mulch_m"]
DEPTH = LAND["soil_depth_m"]
ENTRY, LOOKOUT = radians(SITE["room"]["entry_deg"]), radians(SITE["room"]["lookout_deg"])
OPENING = radians(SITE["beds"]["opening_half_deg"])
CUT_Y = SITE["cameras"]["section"]["cut_y_m"]
BEYOND_M = 2.0  # how far behind the cut buried things are still drawn in a section

_lines: list = []


def log(message: str) -> None:
    _lines.append(f"{time.strftime('%H:%M:%S')} {message}")
    LOG.write_text("\n".join(_lines) + "\n", encoding="utf-8")


# --- the lie of the land ----------------------------------------------------------------------------

def plane(x: float, y: float) -> float:
    """The lie of the land before anything is cut into it: one even fall, which stops `even_to_m` out."""
    r = hypot(x, y)
    k = min(1.0, LAND["even_to_m"] / r) if r else 1.0
    return Z0 + (GX * x + GY * y) * k


def _to_run(x, y, a, b) -> float:
    """How far a plan point is from the straight run a-b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / ((dx * dx + dy * dy) or 1.0)))
    return hypot(x - a[0] - dx * t, y - a[1] - dy * t)


def _to_line(x, y, points) -> float:
    return min(_to_run(x, y, a, b) for a, b in zip(points, points[1:]))


def _swale() -> list:
    """The swale's line: round the uphill side of the room from its high point both ways, then down to the hollow."""
    s = LAND["swale"]
    n = int(abs(s["to_deg"] - s["from_deg"]) / 3.0)
    line = [(s["radius_m"] * cos(radians(s["from_deg"] + (s["to_deg"] - s["from_deg"]) * k / n)), s["radius_m"] * sin(radians(s["from_deg"] + (s["to_deg"] - s["from_deg"]) * k / n))) for k in range(n + 1)]
    return line + [tuple(LAND["hollow"]["at_m"])]


def _arrival() -> list:
    """The arrival path's line, from just outside the gate to the floor's edge: one bend, then straight in through the entry bay."""
    p = SITE["paths"]["arrival"]
    (cx, cy), r = p["centre_m"], p["radius_m"]
    n = 40
    line = [(cx + r * cos(radians(p["from_deg"] + (p["to_deg"] - p["from_deg"]) * k / n)), cy + r * sin(radians(p["from_deg"] + (p["to_deg"] - p["from_deg"]) * k / n))) for k in range(n + 1)]
    heading = radians(p["from_deg"] + 90.0)
    line.insert(0, (line[0][0] - 1.6 * cos(heading), line[0][1] - 1.6 * sin(heading)))
    last, end = line[-1], ((RF - 0.05) * cos(ENTRY), (RF - 0.05) * sin(ENTRY))
    return line + [(last[0] + (end[0] - last[0]) * k / 12, last[1] + (end[1] - last[1]) * k / 12) for k in range(1, 13)]


def _mown() -> list:
    """The mown path's line, on from the look-out into the meadow, turning a little as it goes."""
    p = SITE["paths"]["mown"]
    x, y, heading = RF * cos(LOOKOUT), RF * sin(LOOKOUT), LOOKOUT
    line, n = [(x, y)], int(p["length_m"])
    for _ in range(n):
        heading += radians(p["bend_deg"]) / n
        x, y = x + cos(heading), y + sin(heading)
        line.append((x, y))
    return line


SWALE, ARRIVAL, MOWN = _swale(), _arrival(), _mown()
RILL = [(RF * cos(radians(LAND["rill_from_deg"])), RF * sin(radians(LAND["rill_from_deg"]))), tuple(LAND["hollow"]["at_m"])]


def ground_z(x: float, y: float) -> float:
    """The ground's surface: the even fall, with the swale and the hollow cut into it."""
    s, h = LAND["swale"], LAND["hollow"]
    cut = s["depth_m"] * exp(-((_to_line(x, y, SWALE) / s["half_width_m"]) ** 2)) if hypot(x, y) < 24.0 else 0.0
    dip = h["depth_m"] * exp(-2.2 * (hypot(x - h["at_m"][0], y - h["at_m"][1]) / h["radius_m"]) ** 2)
    return plane(x, y) - max(cut, dip)


def on_arrival(x, y, margin=0.0) -> bool:
    return _to_line(x, y, ARRIVAL) <= SITE["paths"]["arrival"]["width_m"] / 2.0 + margin


def surface_z(x: float, y: float) -> float:
    """What someone stands on at a point: the floor and the arrival path follow the even fall, a little proud of it."""
    if hypot(x, y) <= RF or on_arrival(x, y):
        return plane(x, y) + BUILDUP
    return ground_z(x, y)


def kind_of_ground(x: float, y: float) -> int:
    """0 the garden's mown grass, 1 meadow, 2 the woodland's floor."""
    if y > SITE["woodland"]["edge_y_m"] + 1.3 * sin(0.3 * x) - 0.6:
        return 2
    along, across = x * cos(ENTRY) + y * sin(ENTRY), -x * sin(ENTRY) + y * cos(ENTRY)
    return 1 if along + 0.9 * sin(0.35 * across) < -SITE["meadow"]["begins_m"] else 0
# --- collections, objects, tags ---------------------------------------------------------------------

COLLECTIONS = [
    ("S05_BOWER_TIMBER", "the snapshot's timber, on its linked meshes, with materials that render"),
    ("S10_TERRAIN", "the garden's soil and its surface"),
    ("S20_ROOM_GROUND", "the room's floor, the arrival path and the mown path"),
    ("S30_BEDS", "the two beds, their loosened soil and the planting on them"),
    ("S40_FOUNDATIONS", "the steel sole and screw piles under each pier"),
    ("S45_SUPPORTS", "the trunk cables and their standoffs, as bower/lines.py sets them out, and the mesh round the joints"),
    ("S50_BOWER_PLANTING", "the climbers at installation, as diagrams"),
    ("S60_WATER", "the standpipe and drip line; the swale, the rill and the planted hollow"),
    ("S70_GARDEN", "the woodland, the garden wall, the planting on the bend of the path, the meadow: borrowed vegetation"),
    ("S80_PEOPLE", "borrowed figures"),
    ("S90_CAMERAS", "the study's cameras"),
    ("S95_SECTION_NOTES", "labels for the section: hidden in every other view"),
    ("S96_PLANT_NOTES", "labels for the plant's view: hidden in every other view"),
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
        level = n.new("ShaderNodeVectorMath")  # how high a point is above the even fall of the ground
        level.operation = "DOT_PRODUCT"
        link(geo.outputs["Position"], level.inputs[0])
        level.inputs[1].default_value = (-GX, -GY, 1.0)
        link(level.outputs["Value"], below.inputs[0])
        below.inputs[1].default_value = Z0 + 0.02
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


def textured(name, tex, size_m, cut, tint=(1.0, 1.0, 1.0), patch=0.0, viewport=(0.5, 0.5, 0.5), matte=False):
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
    if matte:  # grass seen at a distance: without this a flat field mirrors the sky at a glancing angle
        p.inputs["Roughness"].default_value = 1.0
        p.inputs["Specular IOR Level"].default_value = 0.0
    else:
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
        "lawn": textured("STUDY_lawn", "leafy_grass", 2.2, CUTS["soil"], tint=(0.5, 0.86, 0.4), patch=0.22, viewport=(0.28, 0.42, 0.16), matte=True),
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
        "meadow": textured("STUDY_meadow", "leafy_grass", 3.1, CUTS["soil"], tint=(0.36, 0.58, 0.22), patch=0.32, viewport=(0.3, 0.4, 0.16), matte=True),
        "mown": textured("STUDY_mown_path", "leafy_grass", 1.6, CUTS["soil"], tint=(0.46, 0.9, 0.42), patch=0.1, viewport=(0.3, 0.48, 0.2), matte=True),
        "litter": textured("STUDY_woodland_floor", "brown_mud_leaves_01", 2.4, CUTS["soil"], tint=(0.75, 0.68, 0.55), patch=0.2, viewport=(0.3, 0.22, 0.14)),
        "pebble": textured("STUDY_pebbles", "pebble_ground_01", 0.9, CUTS["floor"], tint=(0.8, 0.8, 0.82), viewport=(0.55, 0.55, 0.56)),
        "wall": flat("STUDY_garden_wall", (0.3, 0.19, 0.14), (0.45, 0.3, 0.22), rough=0.95),
        "loam": flat("STUDY_loosened_soil", (0.15, 0.1, 0.065), (0.27, 0.18, 0.11), rough=0.95, solid="buried"),
        "mesh": flat("STUDY_joint_mesh", (0.55, 0.42, 0.2), solid=False, rough=0.5, metallic=0.8),
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



def cylinder(x, y, r, z0, z1, sides=14):
    return prism(circle(x, y, r, sides), z0, z1)



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
    "tend_low": [("Spine", X, 16), ("Spine1", X, 16), ("Spine2", X, 12), ("L UpperArm", Y, 30), ("R UpperArm", Y, -30), ("L UpperArm", X, -48), ("R UpperArm", X, -58), ("L Forearm", X, -22), ("R Forearm", X, -30), ("L Thigh", X, -24), ("L Calf", X, 30), ("R Thigh", X, -8), ("R Calf", X, 18), ("Head", X, -12)],
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
    want = radians(SITE["setting"]["sun_stands_deg"])  # where the sun stands, anticlockwise from +X
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
    world["study_note"] = f"meadow_2 (Poly Haven, CC0), {'mirrored and ' if SITE['setting']['sky_mirrored'] else ''}turned so that its sun stands toward {SITE['setting']['sun_stands_deg']} degrees in the building's axes: its light, its height ({round((SUN_UV[1] - 0.5) * 180)} degrees) and its distant trees are the photograph's. Behind the section it gives way to plain paper."



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


# What follows made the coordinated layers of the first pass's explorable drawing (explore/, package_explorer.py), on the
# level site. It has NOT been re-made for the designed site: its places and views are the first pass's. `--export` says so.
LAYERS = {  # what a viewer can pick out, and which objects of the scene each is
    "timber": ("the timber", lambda n: n.startswith("TM_")),
    "footings": ("what it stands on", lambda n: n.startswith(("FT_", "PL_"))),
    "root-zones": ("the ground kept for roots, as it shows on the bed", lambda n: n.startswith("RZ_root_zone_tops")),
    "plant-routes": ("each climber and its way up", lambda n: n.startswith(("BP_", "LN_feeders", "HO_"))),
    "support-lines": ("the training lines", lambda n: n.startswith("LN_training")),
    "walking-route": ("where people walk", lambda n: n.startswith(("RG_floor", "RG_path"))),
    "care-area": ("where the plants are tended from, and the way round to them", lambda n: n.startswith("CP_")),
    "water": ("the standpipe and the drip line", lambda n: n.startswith(("WA_standpipe", "WA_tap", "WA_drip"))),
}
EXPORT_VIEWS = ("arrival", "whole", "pier")
CABLE_SHOWN_M = {"arrival": 0.012, "whole": 0.03, "pier": 0.012}  # a 4 mm cable would not show in a picture of the whole room


def anchors(scene) -> dict:
    """Named places of this configuration, in metres: what the drawing's labels and marks are pinned to."""
    a = {}
    middle = lambda pts: (sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts))  # noqa: E731
    for pid, (x, y) in GROUND["piers"].items():
        a[f"pier.{pid}"] = (x, y, 1.5)
        a[f"pier.{pid}.foot"] = (x, y, FLOOR)
    for pid, f in GROUND["footings"].items():
        a[f"footing.{pid}"] = (*middle([q for plate in f["plates_m"] for q in plate]), FLOOR)
        for k, (x, y) in enumerate(f["piles_m"]):
            a[f"pile.{pid}.{k + 1}"] = (x, y, FLOOR - f["cap_depth_m"])
            a[f"pile.{pid}.{k + 1}.tip"] = (x, y, FLOOR - GROUND["piles"]["length_m"])
    for z in GROUND["root_zones"]:
        a[z["id"]] = (*z["position_m"], SOIL + MULCH)
    lowest = {}
    for h in GROUND["handovers"]:
        key = h["feeder"].split(".feeder")[0]
        if key not in lowest or h["height_m"] < lowest[key]["height_m"]:
            lowest[key] = h
    zone_feeder = {z["id"]: z["feeder_on"] for z in GROUND["root_zones"]}
    for q in GROUND["plants"]:
        a[q["id"]] = (*q["root_m"], q["root_level_m"])
        hand = lowest.get(zone_feeder.get(q["rooted_in"], ""))
        if hand:
            a[q["id"] + ".meets"] = tuple(hand["end_m"])  # the lowest place a gardener can hand it across to a training line
        elif q["route_m"]:
            a[q["id"] + ".meets"] = tuple(q["route_m"][0])  # the foot of its own line
    way = GROUND["entrances"][0]
    (x0, y0), (x1, y1) = way["innermost_points_m"]
    a["way-in.west"], a["way-in.east"], a["way-in.middle"] = (x0, y0, 0.05), (x1, y1, 0.05), ((x0 + x1) / 2, (y0 + y1) / 2, 0.05)
    edge = -RING * cos(pi / 6)
    a["path.west"], a["path.east"] = (-HW, edge, path_top(edge)), (HW, edge, path_top(edge))
    a["floor.middle"] = (0.0, 0.0, floor_z(0, 0))
    for pid, (x, y) in GROUND["piers"].items():
        k = (RC if ROUND else RC) / hypot(x, y)
        a[f"floor.edge.{pid}"] = (x * k, y * k, floor_z(x * k, y * k))
    pads = {pier: c for pier, c, _, _ in stations()}
    for pid in GROUND["piers"]:
        a[f"tended.{pid}"] = (*pads[pid], SOIL + MULCH + 0.05) if pid in pads else (a[f"floor.edge.{pid}"][0] * 0.94, a[f"floor.edge.{pid}"][1] * 0.94, a[f"floor.edge.{pid}"][2])
    c = SITE["care"]
    a["care-path.west"], a["care-path.east"] = (-c["path_radius_m"], 0.0, SOIL + 0.08), (c["path_radius_m"], 0.0, SOIL + 0.08)
    sx, sy = SITE["water"]["standpipe_m"]
    a["standpipe"] = (sx, sy, ground_z(sx, sy) + 1.0)
    hx, hy = SITE["water"]["hollow_m"]
    a["hollow"] = (hx, hy, ground_z(hx, hy))
    top = max((o.matrix_world @ Vector(corner)).z for o in scene.objects if o.name.startswith("TM_") and o.library is None for corner in o.bound_box)
    a["crown"] = (0.0, 0.0, top)
    for o in scene.objects:
        if o.name.startswith("PP_") and o.type == "EMPTY":
            a["person." + o.name[3:]] = (o.location.x, o.location.y, o.location.z + 1.0)
    return a


def export_views(scene, cams: dict, out_dir: Path, samples: int, size=(1280, 800)) -> None:
    """This configuration as the drawing needs it: a picture from each camera state, a mask of each layer in the same
    frame, and where every named place falls in each picture. Written to <out_dir>/<configuration>/."""
    from bpy_extras.object_utils import world_to_camera_view

    out = out_dir / CONFIG
    out.mkdir(parents=True, exist_ok=True)
    scene.render.resolution_x, scene.render.resolution_y = size
    views = {}
    places = anchors(scene)
    for view in EXPORT_VIEWS:
        cam = scene.camera = cams[view]
        scene.cycles.samples = samples
        scene.render.filepath = str(out / f"{view}.png")
        started = time.time()
        bpy.ops.render.render(write_still=True)
        log(f"exported {CONFIG} {view} in {round(time.time() - started)} s")
        bpy.context.view_layer.update()
        points = {}
        for name, at in places.items():
            u, v, depth = world_to_camera_view(scene, cam, Vector(at))
            points[name] = [round(u, 4), round(1.0 - v, 4), round(depth, 2)]  # from the picture's left and top, as fractions; metres in front of the camera
        views[view] = {"camera": {"name": cam.name, "location_m": [round(v, 3) for v in cam.location], "rotation_euler_rad": [round(v, 5) for v in cam.rotation_euler], "lens_mm": cam.data.lens, "sensor_mm": cam.data.sensor_width, "note": cam.get("study_note", "")}, "points": points}

    # the layers: each alone, white on nothing, in the same frames; the timber hides what stands behind it
    local = [o for o in scene.objects if o.library is None and o.type in ("MESH", "CURVE", "EMPTY", "ARMATURE")]
    before = {o.name: (o.hide_render, o.is_holdout) for o in local}
    white = bpy.data.materials.new("STUDY_layer_mask")
    white.use_nodes = True
    white.node_tree.nodes.clear()
    emit, shown = white.node_tree.nodes.new("ShaderNodeEmission"), white.node_tree.nodes.new("ShaderNodeOutputMaterial")
    white.node_tree.links.new(emit.outputs[0], shown.inputs["Surface"])
    layer = bpy.context.view_layer
    transform, denoise = scene.view_settings.view_transform, scene.cycles.use_denoising
    layer.material_override, scene.render.film_transparent, scene.view_settings.view_transform, scene.cycles.use_denoising, scene.cycles.samples = white, True, "Standard", False, 12
    timber = [o for o in local if o.name.startswith("TM_")]
    figures = [o for o in local if o.name.startswith("PP_") and o.type == "MESH"]  # people stand in front of what they stand on
    reach = {view: cams[view].data.clip_end for view in EXPORT_VIEWS}
    layers = {}
    for name, (what, belongs) in LAYERS.items():
        members = [o for o in local if belongs(o.name)]
        layers[name] = {"what": what, "objects": sorted(o.name for o in members if not o.name.startswith("TM_")) or (["S05_BOWER_TIMBER: every member, TM_<id>"] if members else [])}
        if not members:
            continue
        for o in local:
            o.hide_render = True
        for o in timber:
            o.hide_render, o.is_holdout = False, name != "timber"
        for o in figures:
            o.hide_render, o.is_holdout = False, True
        for o in members:
            o.hide_render, o.is_holdout = False, False
        cables = [o for o in members if o.type == "CURVE" and o.name.startswith(("LN_", "HO_", "WA_drip"))]
        true = {o.name: o.data.bevel_depth for o in cables}
        for view in EXPORT_VIEWS:
            for o in cables:
                o.data.bevel_depth = CABLE_SHOWN_M[view]
            scene.camera = cams[view]
            cams[view].data.clip_end = SITE["cameras"].get(view, {}).get("layers_reach_m", reach[view])  # close to, the layers stop behind the thing looked at
            scene.render.filepath = str(out / f"{view}.{name}.png")
            bpy.ops.render.render(write_still=True)
            cams[view].data.clip_end = reach[view]
        for o in cables:
            o.data.bevel_depth = true[o.name]
    for o in local:
        o.hide_render, o.is_holdout = before[o.name]
    layer.material_override, scene.render.film_transparent, scene.view_settings.view_transform, scene.cycles.use_denoising = None, False, transform, denoise
    bpy.data.materials.remove(white)
    scene.camera = cams["arrival"]
    record = {"configuration": CONFIG, "label": CFG["label"], "what": CFG["what"], "snapshot": SNAPSHOT, "size": list(size), "views": views, "layers": layers, "cable_shown_m": CABLE_SHOWN_M, "places_m": {k: [round(v, 3) for v in at] for k, at in places.items()}}
    (out / "export.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    log(f"exported {CONFIG}: {len(EXPORT_VIEWS)} views, {sum(1 for v in layers.values() if v['objects'])} layers, {len(places)} places")


# --- the ground --------------------------------------------------------------------------------------

AXIS = [-150.0, -120.0, -95.0, -75.0, -62.0, -52.0, -45.0, -39.0, -34.0] + [k * 0.4 for k in range(-76, 77)] + [34.0, 39.0, 45.0, 52.0, 62.0, 75.0, 95.0, 120.0, 150.0]


def outward(obj):
    """Turn every face of a closed mesh to face out, so that a section paints its inside and not its outside."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def strip(left, right, top, bottom):
    """A closed solid between two plan lines of the same length; top and bottom are functions of (x, y)."""
    n = len(left)
    verts = [(x, y, top(x, y)) for x, y in left] + [(x, y, top(x, y)) for x, y in right] + [(x, y, bottom(x, y)) for x, y in left] + [(x, y, bottom(x, y)) for x, y in right]
    faces = [(0, n, 3 * n, 2 * n), (n - 1, 2 * n - 1, 4 * n - 1, 3 * n - 1)]
    for k in range(n - 1):
        faces += [(k, k + 1, n + k + 1, n + k), (2 * n + k, 3 * n + k, 3 * n + k + 1, 2 * n + k + 1), (k, 2 * n + k, 2 * n + k + 1, k + 1), (n + k, n + k + 1, 3 * n + k + 1, 3 * n + k)]
    return verts, faces


def ribbon(points, half, top, bottom):
    """A closed strip along a plan line, `half` wide each side."""
    left, right = [], []
    for k, (x, y) in enumerate(points):
        ax, ay = points[max(k - 1, 0)]
        bx, by = points[min(k + 1, len(points) - 1)]
        d = hypot(bx - ax, by - ay) or 1.0
        nx, ny = -(by - ay) / d * half, (bx - ax) / d * half
        left.append((x + nx, y + ny))
        right.append((x - nx, y - ny))
    return strip(left, right, top, bottom)


def band(a0, a1, r_in, r_out, top, bottom, step_deg=3.0):
    """A closed solid on part of a ring about the crown; either radius may be a function of the angle."""
    n = max(2, int(abs(a1 - a0) / radians(step_deg)) + 1)
    angles = [a0 + (a1 - a0) * k / (n - 1) for k in range(n)]
    ri = r_in if callable(r_in) else (lambda a: r_in)
    ro = r_out if callable(r_out) else (lambda a: r_out)
    return strip([(ro(a) * cos(a), ro(a) * sin(a)) for a in angles], [(ri(a) * cos(a), ri(a) * sin(a)) for a in angles], top, bottom)


def slab(name, top, bottom, coll, materials, slot_of, status, note):
    """A solid on the terrain's grid between two surfaces; `slot_of(x, y)` picks the material of each top face."""
    n = len(AXIS)
    verts = [(x, y, top(x, y)) for y in AXIS for x in AXIS] + [(x, y, bottom(x, y)) for y in AXIS for x in AXIS]
    faces, slots = [], []
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i
            faces.append((a, a + 1, a + n + 1, a + n))
            slots.append(slot_of((AXIS[i] + AXIS[i + 1]) / 2.0, (AXIS[j] + AXIS[j + 1]) / 2.0))
            b = n * n + a
            faces.append((b, b + n, b + n + 1, b + 1))
            slots.append(1)
    rim = [j * n for j in range(n)] + [(n - 1) * n + i for i in range(1, n)] + [j * n + n - 1 for j in range(n - 2, -1, -1)] + [i for i in range(n - 2, 0, -1)]
    for a, b in zip(rim, rim[1:] + rim[:1]):
        faces.append((a, b, n * n + b, n * n + a))  # the rim, facing out
        slots.append(1)
    obj = add_mesh(name, verts, faces, coll, materials, status, note)
    obj.data.polygons.foreach_set("material_index", slots)
    obj.data.update()
    return obj


def terrain(colls, mats) -> None:
    fall = round(1.0 / LAND["fall"])
    slab("GR_soil", ground_z, lambda x, y: plane(x, y) - DEPTH, colls["S10_TERRAIN"], [mats["lawn"], mats["soil"], mats["meadow"], mats["litter"]], lambda x, y: (0, 2, 3)[kind_of_ground(x, y)], PROPOSAL, f"The ground of the designed site, {DEPTH} m of its soil drawn: an even fall of 1 in {fall} with a swale and a hollow cut into it, mown grass on the garden side, meadow on the other and leaf litter under the woodland. At each pier it is feet_below_soil_m (site.json) above the pier's feet, so the timber comes straight out of the soil. Nothing is known of a real soil.")
    slab("GR_subsoil", lambda x, y: plane(x, y) - DEPTH, lambda x, y: Z0 - 8.0, colls["S10_TERRAIN"], [mats["subsoil"], mats["subsoil"]], lambda x, y: 0, PROPOSAL, "The ground below the cultivated soil, drawn so that the piles have something to stand in. Nothing is known of it.")
    # Behind a cut the drawn soil is closed off, so that a section does not look through it at what stands in the ground beyond.
    y, xs = CUT_Y + BEYOND_M + 0.5, [k * 0.4 for k in range(-90, 91)]
    m = len(xs)
    wall = [(x, y, ground_z(x, y) - 0.004) for x in xs] + [(x, y, plane(x, y) - DEPTH) for x in xs] + [(x, y, Z0 - 8.0) for x in xs]
    faces = [(i, i + 1, m + i + 1, m + i) for i in range(m - 1)] + [(m + i, m + i + 1, 2 * m + i + 1, 2 * m + i) for i in range(m - 1)]
    back = add_mesh("GR_cut_backing", wall, faces, colls["S10_TERRAIN"], [mats["back_soil"], mats["back_subsoil"]], PROPOSAL, f"A drawing device, not a thing: the soil's cut colour on a plane {BEYOND_M + 0.5} m behind the section, so that the cut ground reads as solid. Invisible unless a section is on.")
    back.data.polygons.foreach_set("material_index", [0] * (m - 1) + [1] * (m - 1))
    back.data.update()


def room_ground(colls, mats) -> None:
    fall = round(1.0 / LAND["fall"])
    top = lambda x, y: plane(x, y) + BUILDUP  # noqa: E731
    add_mesh("RG_floor", *prism(circle(0.0, 0.0, RF, 96), lambda x, y: plane(x, y) - 0.15, top), colls["S20_ROOM_GROUND"], mats["floor"], PROPOSAL, f"The room's floor: a round of bound gravel {2 * RF} m across that follows the ground, 1 in {fall}, with no step at its edge and no platform under it. Whether 1 in {fall} is comfortable to stand and talk on for long is to be found out. No furniture.")
    path = SITE["paths"]["arrival"]
    outward(add_mesh("RG_arrival_path", *ribbon(ARRIVAL, path["width_m"] / 2.0, lambda x, y: plane(x, y) + BUILDUP - 0.004, lambda x, y: plane(x, y) - 0.12), colls["S20_ROOM_GROUND"], mats["floor"], PROPOSAL, path["note"] + f" Bound gravel, {path['width_m']} m wide, falling with the ground."))
    reach = LAND["swale"]["radius_m"]
    over = [p for p in ARRIVAL if abs(hypot(*p) - reach) < 1.5]
    outward(add_mesh("RG_swale_crossing", *ribbon(over, path["width_m"] / 2.0 + 0.18, lambda x, y: plane(x, y) + BUILDUP + 0.02, lambda x, y: plane(x, y) - 0.1), colls["S20_ROOM_GROUND"], mats["pad"], PROPOSAL, "A stone slab where the arrival path crosses the swale: you step over the water's way on the way in."))
    mown = SITE["paths"]["mown"]
    outward(add_mesh("RG_mown_path", *ribbon(MOWN, mown["width_m"] / 2.0, lambda x, y: ground_z(x, y) + 0.02, lambda x, y: ground_z(x, y) - 0.03), colls["S20_ROOM_GROUND"], mats["mown"], PROPOSAL, mown["note"]))
    w = SITE["wall"]
    (wx, wy), a = w["through_m"], radians(w["along_deg"])
    for name, s0, s1 in (("south", w["from_m"], -w["gate_m"] / 2.0), ("north", w["gate_m"] / 2.0, w["to_m"])):
        n = max(2, int(abs(s1 - s0)))
        line = [(wx + (s0 + (s1 - s0) * k / n) * cos(a), wy + (s0 + (s1 - s0) * k / n) * sin(a)) for k in range(n + 1)]
        outward(add_mesh(f"GD_wall_{name}", *ribbon(line, w["thickness_m"] / 2.0, lambda x, y: ground_z(x, y) + w["height_m"], lambda x, y: ground_z(x, y) - 0.4), colls["S70_GARDEN"], mats["wall"], PROPOSAL, w["note"] + f" {w['height_m']} m high, with a gate {w['gate_m']} m wide where the path comes through."))


def bed_edges():
    """The two beds: (name, from, to, outer radius as a function of the angle)."""
    return (
        ("sheltered", ENTRY + OPENING, LOOKOUT - OPENING, lambda a: RB_SHELTER + 0.35 * sin(3.0 * a)),
        ("sunny", LOOKOUT + OPENING, ENTRY + 2 * pi - OPENING, lambda a: RB_SUN + 0.25 * sin(4.0 * a)),
    )


def in_bed(x, y) -> str:
    r, a = hypot(x, y), atan2(y, x)
    for name, a0, a1, outer in bed_edges():
        t = a
        while t < a0:
            t += 2 * pi
        if t <= a1 and RF < r < outer(t):
            return name
    return ""


def beds(colls, mats, assets) -> None:
    rng = random.Random(11)
    roots = [p["root_m"] for p in GROUND["plants"]]
    feet = [c for pier in GROUND["feet"].values() for f in pier for c in f["corners_m"]]
    for name, a0, a1, outer in bed_edges():
        outward(add_mesh(f"BD_bed_{name}", *band(a0, a1, RF, outer, lambda x, y: plane(x, y) + MULCH, lambda x, y: plane(x, y) - 0.01), colls["S30_BEDS"], mats["mulch"], PROPOSAL, SITE["beds"]["note"] + f" Mulched {MULCH} m deep."))
        outward(add_mesh(f"BD_loosened_soil_{name}", *band(a0, a1, RF, outer, lambda x, y: plane(x, y) - 0.012, lambda x, y: plane(x, y) - DEPTH + 0.01), colls["S30_BEDS"], mats["loam"], PROPOSAL, f"The bed's soil, loosened {DEPTH} m deep and not boxed in: it is the same ground as the lawn and the meadow beside it, and runs on over, under and between the bars of every pier's buried sole. {GROUND['quantities']['loosened_soil_m3']['says']}. Seen only in a section."))
        want = {"sheltered": {"shrub_01": 16, "shrub_04": 14, "fern_02": 70, "periwinkle_plant": 60}, "sunny": {"periwinkle_plant": 90, "dandelion_01": 30, "fern_02": 10}}[name]
        scales = {"periwinkle_plant": (0.9, 1.5), "fern_02": (0.8, 1.4), "shrub_01": (1.5, 2.6), "shrub_04": (1.6, 2.7), "dandelion_01": (1.2, 1.9)}
        for kind, count in want.items():
            points = []
            while len(points) < count:
                a = rng.uniform(a0, a1)
                tall = kind.startswith("shrub")
                r = rng.uniform(RING + 1.1, outer(a) - 0.4) if tall else rng.uniform(RF + 0.25, outer(a) - 0.2)
                x, y = r * cos(a), r * sin(a)
                if any(hypot(x - q[0], y - q[1]) < 0.45 for q in roots) or any(hypot(x - q[0], y - q[1]) < 0.3 for q in feet):
                    continue  # the climbers' own ground, and the feet, are left clear
                points.append((x, y, plane(x, y) + MULCH))
            scatter(f"BD_{name}_{kind}", points, assets[kind], colls["S30_BEDS"], scales[kind], BORROWED, seed=len(kind) + len(name), note=f"Planting on the {name} bed as newly planted: {'shrubs and ferns for shelter on the woodland side' if name == 'sheltered' else 'low planting, so the sun and the view come in'}. A borrowed model ({kind}, Poly Haven, CC0) standing in for a planting nobody has designed; not a species choice.")
    balls = [cylinder(p["root_m"][0], p["root_m"][1], SITE["planting_at_installation"]["root_ball_m"] / 2.0, plane(*p["root_m"]) + MULCH - 0.32, plane(*p["root_m"]) + MULCH - 0.02) for p in GROUND["plants"]]
    add_mesh("BP_root_balls", *merge(balls), colls["S50_BOWER_PLANTING"], mats["root"], PROPOSAL, f"Each climber's root ball as it goes in, {SITE['planting_at_installation']['root_ball_m']} m across: a drawing assumption, not a horticultural requirement. All it has on the day it is planted; the soil round it is what it grows into. Seen only in a section.")


def foundations(colls, mats) -> None:
    p = GROUND["piles"]
    plates, piles = [], []
    for pid, f in GROUND["footings"].items():
        top = LEVEL[pid]
        plates += [prism(plate, top - f["cap_depth_m"], top) for plate in f["plates_m"]]
        for x, y in f["piles_m"]:
            tip = plane(x, y) - p["length_m"]
            piles.append(cylinder(x, y, p["shaft_m"] / 2.0, tip, top - f["cap_depth_m"]))
            piles.append(cylinder(x, y, p["helix_m"] / 2.0, tip + 0.15, tip + 0.165, 20))
    first = next(iter(GROUND["footings"].values()))
    note = "A proposal authored for this study (set_out_meadow.py, sole_footing); not engineered: no load, no soil and no thrust from the arches has been looked at."
    add_mesh("FT_soles", *merge(plates), colls["S40_FOUNDATIONS"], mats["steel"], PROPOSAL, f"A steel sole under each pier, at that pier's own level and buried: a plate under the two arch legs, one curved beam under the six lattice legs and two ties. The timber feet stand on it {round(SUNK * 1000)} mm under the soil, so no footing is seen. {GROUND['quantities']['steel_over_the_ground_m2']['says']}. Timber in the ground is a durability question this study does not answer. Seen only in a section. {note}")
    add_mesh("PL_screw_piles", *merge(piles), colls["S40_FOUNDATIONS"], mats["steel"], PROPOSAL, f"Three screw piles under each sole, {p['length_m']} m into the ground: {first['pile_spacing_m']} m apart at the least, no foot more than {first['furthest_foot_from_a_pile_m']} m from one and none nearer than {first['nearest_pile_to_a_climber_m']} m to a climber, which meets the ground draft's three rules. {note}")


def supports(colls, mats) -> None:
    lines, c = GROUND["training_lines"], GROUND["cable"]
    q = GROUND["quantities"]
    poly_curve("LN_trunk_cables", [l["points_m"] for l in lines], 0.004, colls["S45_SUPPORTS"], mats["line"], GENERATED, f"The cables for the stems that grow thick, strung by bower/lines.py on the legs: {q['cable_m']['says']}. Each stands {c['foot_gap_m']} m off the timber at a foot and comes in to {c['gap_m']} m over {c['foot_taper_m']} m of the leg, so that a trunk cannot bear on a member or work into a joint. That gap is a provisional allowance: no girth figure stands behind it. Thin growth is tied to the timber itself, by hand, and is not drawn. Drawn 8 mm thick so that it can be seen; the cable is 4 mm.")
    poly_curve("LN_standoffs", [pair for l in lines for pair in l["standoffs_m"]], 0.005, colls["S45_SUPPORTS"], mats["line"], GENERATED, f"The standoffs that hold the cables off the timber: {q['standoffs']['says']}.")
    verts, faces = [], []
    for s in GROUND["mesh_sleeves"]:
        at, u, v, w = Vector(s["at_m"]), Vector(s["across"]), Vector(s["up"]), Vector(s["along"])
        a, b, c2 = s["size_m"][0] / 2.0, s["size_m"][1] / 2.0, s["size_m"][2] / 2.0
        k = len(verts)
        verts += [tuple(at + u * (a * i) + v * (b * j) + w * (c2 * m)) for m in (-1, 1) for j in (-1, 1) for i in (-1, 1)]
        faces += [(k, k + 1, k + 5, k + 4), (k + 2, k + 6, k + 7, k + 3), (k, k + 4, k + 6, k + 2), (k + 1, k + 3, k + 7, k + 5)]  # a sleeve: four sides, open at both ends
    add_mesh("MS_joint_mesh", verts, faces, colls["S45_SUPPORTS"], mats["mesh"], PROPOSAL, f"A sleeve of fine mesh round each member at each joint, to keep growth out of it: {q['joints']['says']}. A proposal. What it is made of, how it is fixed and whether it holds water against the timber are not known.")


def climbers(colls, mats) -> None:
    """One climber at each place one is planted, as it might go in: a tied stem on its cable, with a few leaves. A diagram."""
    rng = random.Random(5)
    length = SITE["planting_at_installation"]["cane_height_m"]
    stems, leaf_v, leaf_f = [], [], []
    for q in GROUND["plants"]:
        line = q["route_m"]
        x, y = q["root_m"]
        base = plane(x, y) + MULCH
        foot = Vector(line[0])
        run = [Vector((x, y, base)), Vector((x, y, base + 0.12)).lerp(foot, 0.35), Vector((x, y, base + 0.3)).lerp(foot, 0.8), foot]
        gone = sum((b - a).length for a, b in zip(run, run[1:]))
        for a, b in zip(line, line[1:]):
            a, b = Vector(a), Vector(b)
            step = (b - a).length
            if gone + step >= length:
                run.append(a.lerp(b, (length - gone) / step))
                break
            run.append(b)
            gone += step
        stems.append([tuple(v) for v in run])
        fine = []
        for a, b in zip(run, run[1:]):
            steps = max(1, int((b - a).length / 0.1))
            fine += [a.lerp(b, k / steps) for k in range(steps)]
        for v in fine[3:]:  # leaves every hand's breadth up the stem, turned at random
            turn, size = rng.uniform(0, 2 * pi), rng.uniform(0.06, 0.11)
            out = Vector((cos(turn), sin(turn), -0.45)).normalized()
            side = Vector((-sin(turn), cos(turn), 0.0)) * size * 0.32
            base_v = v + out * 0.015
            k = len(leaf_v)
            leaf_v += [tuple(base_v), tuple(base_v + out * size * 0.5 + side), tuple(base_v + out * size), tuple(base_v + out * size * 0.5 - side)]
            leaf_f.append((k, k + 1, k + 2, k + 3))
    poly_curve("BP_climber_stems", stems, 0.007, colls["S50_BOWER_PLANTING"], mats["stem"], PROPOSAL, f"{len(stems)} climbers as they might go in, {length} m long, each planted {CFG['plant_in_m']} m from the foot of its own cable, in the bed's soil, and tied up it. A diagram of an installed plant: not grown, not simulated, and no shade.")
    add_mesh("BP_climber_leaves", leaf_v, leaf_f, colls["S50_BOWER_PLANTING"], mats["leaf"], PROPOSAL, "Leaves on those stems, to show how little a new plant covers.")


def water(colls, mats, assets) -> None:
    w, h, s = SITE["water"], LAND["hollow"], LAND["swale"]
    sx, sy = w["standpipe_m"]
    g = ground_z(sx, sy)
    post = [(sx - 0.045, sy - 0.045), (sx + 0.045, sy - 0.045), (sx + 0.045, sy + 0.045), (sx - 0.045, sy + 0.045)]
    add_mesh("WA_standpipe", *prism(post, g - 0.05, g + 1.05), colls["S60_WATER"], mats["post"], PROPOSAL, "A standpipe beside the way in: the proposed source of water for the establishment years, and where a can is filled. Where its supply comes from is not known.")
    tap = [(sx + 0.045, sy - 0.02), (sx + 0.16, sy - 0.02), (sx + 0.16, sy + 0.02), (sx + 0.045, sy + 0.02)]
    add_mesh("WA_tap", *prism(tap, g + 0.86, g + 0.9), colls["S60_WATER"], mats["brass"], PROPOSAL, "The tap.")
    r = w["drip_radius_m"]
    lift = lambda x, y: (x, y, plane(x, y) + MULCH + 0.012)  # noqa: E731
    runs = [[lift(r * cos(a0 + (a1 - a0) * k / 60), r * sin(a0 + (a1 - a0) * k / 60)) for k in range(61)] for _, a0, a1, _ in bed_edges()]
    runs.append([(sx, sy, g + 0.2), (sx, sy, g + 0.02), runs[0][0]])
    for q in GROUND["plants"]:
        zx, zy = q["root_m"]
        b = atan2(zy, zx)
        runs.append([lift(zx + 0.26 * cos(2 * pi * k / 24), zy + 0.26 * sin(2 * pi * k / 24)) for k in range(25)])
        runs.append([lift(r * cos(b), r * sin(b)), lift(zx + 0.26 * cos(b), zy + 0.26 * sin(b))])
    poly_curve("WA_drip_line", runs, 0.009, colls["S60_WATER"], mats["drip"], PROPOSAL, w["note"])
    outward(add_mesh("WA_swale_bed", *ribbon(SWALE[:-1], 0.28, lambda x, y: ground_z(x, y) + 0.015, lambda x, y: ground_z(x, y) - 0.03), colls["S60_WATER"], mats["pebble"], PROPOSAL, f"The bed of the swale, in pebbles: a shallow cut {s['depth_m']} m deep round the uphill side of the room, which takes what runs off the garden round it instead of through it, and falls both ways to the meadow and the hollow. A drainage proposal; no rainfall or soil is known."))
    outward(add_mesh("WA_rill", *ribbon(RILL, 0.16, lambda x, y: ground_z(x, y) + 0.018, lambda x, y: ground_z(x, y) - 0.03), colls["S60_WATER"], mats["pebble"], PROPOSAL, "A line of pebbles from the low edge of the floor to the hollow: where the floor's own water goes, made visible."))
    hx, hy = h["at_m"]
    wobble = [1.0 + 0.1 * sin(2 * pi * k / 28 * 2 + 0.7) + 0.06 * sin(2 * pi * k / 28 * 3) for k in range(28)]
    damp = [(hx + (x - hx) * f, hy + (y - hy) * f) for f, (x, y) in zip(wobble, circle(hx, hy, h["radius_m"] * 0.42, 28))]
    damp = [(x, y, ground_z(x, y) + 0.015) for x, y in damp]
    add_mesh("WA_damp_hollow", [(hx, hy, ground_z(hx, hy) + 0.015)] + damp, [(0, 1 + k, 1 + (k + 1) % 28) for k in range(28)], colls["S60_WATER"], mats["damp"], PROPOSAL, f"The planted hollow below the room, {h['depth_m']} m down: where the swale and the rill end, and water stands for a while after rain. Its use to other life is an intention, not a finding.")
    rng = random.Random(3)
    ferns, rushes = [], []
    while len(ferns) < 46:
        t, d = rng.uniform(0, 2 * pi), h["radius_m"] * rng.uniform(0.3, 1.0)
        x, y = hx + d * cos(t), hy + d * sin(t)
        (ferns if len(ferns) <= len(rushes) * 1.2 else rushes).append((x, y, ground_z(x, y) + 0.04))
    for k, (x, y) in enumerate(SWALE[:-1]):
        if k % 3 == 0 and not on_arrival(x, y, 1.2):
            ferns.append((x + rng.uniform(-0.5, 0.5), y + rng.uniform(-0.5, 0.5), ground_z(x, y) + 0.05))
    scatter("WA_hollow_ferns", ferns, assets["fern_02"], colls["S60_WATER"], (1.0, 1.9), BORROWED, "Ferns in the hollow and along the swale: a borrowed model (fern_02, Poly Haven, CC0) marking ground that is meant to stay damp.")
    scatter("WA_hollow_grass", rushes, assets["grass_medium_02"], colls["S60_WATER"], (1.8, 3.0), BORROWED, "Tall grass in the hollow (grass_medium_02, Poly Haven, CC0), standing in for whatever likes wet feet there.")


def garden(colls, assets) -> None:
    rng = random.Random(8)
    wood, veil = SITE["woodland"], SITE["veil"]
    trees, x = 0, wood["from_x_m"]
    while x <= wood["to_x_m"]:
        y = wood["edge_y_m"] + 1.6
        while y <= wood["edge_y_m"] + wood["depth_m"]:
            px, py = x + rng.uniform(-1.9, 1.9), y + rng.uniform(-1.9, 1.9)
            if rng.random() < 0.82:
                trees += 1
                instance(f"GD_wood_{trees:03d}", assets["tree_small_02"], colls["S70_GARDEN"], (px, py, ground_z(px, py) - 0.05), rng.uniform(*wood["scale"]), rng.uniform(0, 360), BORROWED, "A tree of the woodland along the north-east edge. A borrowed model (tree_small_02, Poly Haven, CC0) for a small deciduous tree, at several sizes; no species is meant.")
            y += wood["spacing_m"]
        x += wood["spacing_m"]
    for k, (tx, ty, s, t) in enumerate(veil["trees"]):
        instance(f"GD_veil_tree_{k + 1}", assets["tree_small_02"], colls["S70_GARDEN"], (tx, ty, ground_z(tx, ty) - 0.03), s * 1.35, t, BORROWED, veil["note"] + " A borrowed tree (tree_small_02, Poly Haven, CC0).")
    shrubs = [(sx, sy, ground_z(sx, sy)) for sx, sy in veil["shrubs"]]
    low = []
    for sx, sy in veil["shrubs"]:
        for _ in range(5):
            px, py = sx + rng.uniform(-1.3, 1.3), sy + rng.uniform(-1.3, 1.3)
            if not on_arrival(px, py, 0.4):
                low.append((px, py, ground_z(px, py)))
    scatter("GD_veil_shrubs", shrubs, assets["shrub_01"], colls["S70_GARDEN"], (2.2, 3.4), BORROWED, veil["note"] + " Borrowed shrubs (shrub_01, Poly Haven, CC0).", seed=4)
    scatter("GD_veil_ferns", low, assets["fern_02"], colls["S70_GARDEN"], (1.0, 1.7), BORROWED, "Low planting under the veil (fern_02, Poly Haven, CC0).", seed=6)
    edge, under = [], []
    for _ in range(170):
        px = rng.uniform(wood["from_x_m"] + 8.0, wood["to_x_m"] - 8.0)
        py = wood["edge_y_m"] + 1.3 * sin(0.3 * px) + rng.uniform(-1.4, 3.0)
        (edge if rng.random() < 0.3 else under).append((px, py, ground_z(px, py)))
    scatter("GD_wood_edge_shrubs", edge, assets["shrub_04"], colls["S70_GARDEN"], (2.0, 3.6), BORROWED, "Shrubs at the woodland's edge: cover between the trees and the open ground. Borrowed (shrub_04, Poly Haven, CC0); its use to birds and insects is an intention, not a finding.", seed=9)
    scatter("GD_wood_edge_ferns", under, assets["fern_02"], colls["S70_GARDEN"], (1.1, 2.0), BORROWED, "Ferns at the woodland's edge (fern_02, Poly Haven, CC0).", seed=10)
    lx, ly = -11.5, 11.2
    instance("GD_log", assets["dead_tree_trunk"], colls["S70_GARDEN"], (lx, ly, ground_z(lx, ly) + 0.02), 1.0, 70.0, BORROWED, "A log left at the woodland's edge: dead wood kept on purpose. A borrowed model (dead_tree_trunk, Poly Haven, CC0); what lives in it is not claimed.")
    m = SITE["meadow"]
    tufts, flowers = [], []
    tries = 0
    while len(tufts) < m["tufts"] and tries < 60000:
        tries += 1
        d, t = m["reach_m"] * sqrt(rng.random()) , rng.uniform(LOOKOUT - 1.25, LOOKOUT + 1.25)
        px, py = d * cos(t), d * sin(t)
        if kind_of_ground(px, py) != 1 or _to_line(px, py, MOWN) < SITE["paths"]["mown"]["width_m"] / 2.0 + 0.25 or _to_line(px, py, RILL) < 0.3:
            continue
        tufts.append((px, py, ground_z(px, py) + 0.01))
        if len(tufts) % 9 == 0:
            flowers.append((px + 0.15, py + 0.1, ground_z(px, py) + 0.01))
    scatter("GD_meadow_grass", tufts, assets["grass_medium_02"], colls["S70_GARDEN"], (2.0, 3.8), BORROWED, m["note"] + f" {len(tufts)} tufts of a borrowed model (grass_medium_02, Poly Haven, CC0), thickest toward the look-out; a meadow's own mix of plants is not modelled, and its use to insects is an intention.", seed=12)
    scatter("GD_meadow_flowers", flowers, assets["dandelion_01"], colls["S70_GARDEN"], (1.3, 2.2), BORROWED, "Flowers in the meadow (dandelion_01, Poly Haven, CC0).", seed=13)
    log(f"garden: {trees} woodland trees, {len(tufts)} meadow tufts")


def people(colls) -> None:
    for k, q in enumerate(SITE["people"]):
        figure(colls, q["avatar"], q["pose"], list(q["at_m"]), q["facing_deg"], q["does"], f"PP_{k + 1}_{q['does'].split(',')[0].split(' ')[0]}")
    log(f"people: {len(SITE['people'])} figures")


def cameras(scene, colls) -> dict:
    made = {}
    for key, v in SITE["cameras"].items():
        data = bpy.data.cameras.new(f"CAM_{key}")
        cam = bpy.data.objects.new(f"CAM_{key}", data)
        if v.get("section"):  # looking along +Y: its near clipping plane is the cut
            data.type = "ORTHO"
            data.ortho_scale = v["width_m"] * max(1.0, v["size_px"][1] / v["size_px"][0])  # Blender measures the longer side
            data.clip_start, data.clip_end = 30.0, 400.0
            cam.location = (v["centre_m"][0], v["cut_y_m"] - 30.0, v["centre_m"][1])
            cam.rotation_euler = (radians(90.0), 0.0, 0.0)
            note = v["note"] + " Its near clipping plane is the cut; turn the section switch on with it (see `render` in build_scene.py)."
        elif v.get("plan"):
            data.type, data.ortho_scale, data.clip_end = "ORTHO", v["width_m"], 400.0
            cam.location = (v["centre_m"][0], v["centre_m"][1], 80.0)
            note = v["note"]
        else:
            data.lens, data.clip_start, data.clip_end = v["lens_mm"], 0.1, 800.0
            if "at_m" in v:  # an eye: so far above whatever is stood on there
                x, y = v["at_m"]
                cam.location = (x, y, surface_z(x, y) + v["eye_m"])
                note = v["note"] + f" {v['eye_m']} m above the ground there."
            else:
                cam.location = v["location_m"]
                note = v["note"]
            cam.rotation_euler = (Vector(v["target_m"]) - cam.location).to_track_quat("-Z", "Y").to_euler()
        made[key] = tag(cam, PROPOSAL, note)
        colls["S90_CAMERAS"].objects.link(cam)
    scene.camera = made["arrival"]
    return made


def render(scene, cams: dict, colls: dict, views: list, samples: int, out_dir: Path, scale: float = 1.0) -> None:
    switch = bpy.data.node_groups["STUDY_section_switch"].nodes
    notes = {"section": colls["S95_SECTION_NOTES"], "plant": colls["S96_PLANT_NOTES"]}
    out_dir.mkdir(parents=True, exist_ok=True)
    for view in views:
        v = SITE["cameras"][view]
        scene.camera = cams[view]
        on = bool(v.get("section"))
        switch["section_on"].outputs[0].default_value = 1.0 if on else 0.0
        switch["section_y"].outputs[0].default_value = v.get("cut_y_m", CUT_Y)
        for key, coll in notes.items():
            coll.hide_render = key != view
        scene.cycles.samples = max(24, samples // 2) if on or v.get("plan") else samples
        scene.render.resolution_x, scene.render.resolution_y = (int(s * scale) for s in v["size_px"])
        scene.render.filepath = str(out_dir / f"{view}.png")
        started = time.time()
        bpy.ops.render.render(write_still=True)
        log(f"rendered {view} at {scene.render.resolution_x} x {scene.render.resolution_y} in {round(time.time() - started)} s")
    switch["section_on"].outputs[0].default_value = 0.0
    for coll in notes.values():
        coll.hide_render = True
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
    water(colls, mats, assets)
    garden(colls, assets)
    people(colls)
    sky(scene)
    cams = cameras(scene, colls)
    render_settings(scene, samples)
    layer_of(bpy.context.view_layer.layer_collection, "S99_ASSET_SOURCES").exclude = True
    sys.path.insert(0, str(HERE))
    import place_notes

    place_notes.add(colls, SITE, GROUND, {"plane": plane, "ground_z": ground_z, "tag": tag, "status": PROPOSAL})
    for name in ("S95_SECTION_NOTES", "S96_PLANT_NOTES"):
        colls[name].hide_render = True
    scene["study"] = "inhabited-room: the six-bay Bower as a place, on the day it is planted"
    scene["study_site"] = SITE["intention"]
    scene["study_configuration"] = f"{CONFIG}: {CFG['what']}"
    scene["study_baseline"] = f"releases/{SNAPSHOT}, linked"
    scene["study_section"] = "Set node group STUDY_section_switch > section_on to 1 and look through CAM_section or CAM_plant; show S95_SECTION_NOTES or S96_PLANT_NOTES."
    scene["study_statuses"] = " | ".join((LINKED, GENERATED, PROPOSAL, BORROWED, CARRIED))
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
    for k, entry in enumerate(SITE["people"]):
        p = {**entry, **entry.get("by_configuration", {}).get(CONFIG, {})}
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
        out_dir = HERE / argv[argv.index("--out") + 1] if "--out" in argv else HERE / "views"  # a relative folder is beside this file, wherever Blender was started
        if "--poses" in argv:
            pose_sheet(out_dir)
            return
        if "--export" in argv:
            raise RuntimeError("the coordinated layers have not been re-made for the designed site: see the note above LAYERS")
        scale = float(argv[argv.index("--scale") + 1]) if "--scale" in argv else 1.0  # smaller pictures, for a cheap look
        scene, colls, cams = build(samples)
        render(scene, cams, colls, views, samples, out_dir, scale)
        bpy.ops.wm.save_mainfile()
        log("done")
    except Exception:
        log("FAILED\n" + traceback.format_exc())


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
