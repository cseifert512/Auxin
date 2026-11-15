"""The climbers as the growth simulator grew them, drawn in the scene on one given day.

Called by build_scene.py. A run of the simulator (drawings-in-code `npm run grow`, Horti-code-ture) records every
stem point, leaf and flower with the day it came and the day it went. This reads a run and, for a date, makes:

    stems     one curve per climber, each point as thick as the run says it was on that day
    leaves    one point per leaf in leaf on that day, each drawn as an instance of its species' leaf, turned the way
              the run says its stalk leaves the stem, as far open and as far turned to autumn colour as it was
    flowers   one point per inflorescence in bud or open on that day, likewise

What is on the plant on a day is decided exactly as the simulator's own viewer decides it: `leaf_state`,
`flower_state` and the stem rules are Horti-code-ture/packages/core/src/render/presence.ts, line for line.

What is NOT the simulator's: the shapes and colours. The viewer draws each species from a modelled organ of its own;
here each has a plain leaf of the right kind (simple, pinnate, of three, of five, lobed) and a plain flower, coloured
with the viewer's own colours for that species where it has them (LOOKS). A picture from this is a true record of
where and when the run put growth, and only a sketch of what each plant looks like.

Coordinates need no conversion: a run is in the snapshot's own axes, in metres, Z up.
"""
from __future__ import annotations

import datetime
import gzip
import json
from math import cos, floor, pi, radians, sin
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def _rgb(code: str) -> tuple:
    """A colour written as the viewer writes it (sRGB hex), as the linear colour a shader wants."""
    out = []
    for k in (1, 3, 5):
        c = int(code[k : k + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


# Each species' leaf kind and colours. The colours are the viewer's own (packages/viewer/src/plant/taxa/<id>.ts) except
# those marked "stand-in", which that file gives under names this reader does not follow.
LOOKS = {
    "wisteria-sinensis": {"leaf": "pinnate", "green": ("#588737", "#6a9742"), "autumn": ("#e6c336", "#d0a02c"), "flower": ("#d0bdf0", "#a285d6"), "bloom": "raceme"},
    "wisteria-floribunda-macrobotrys": {"leaf": "pinnate", "green": ("#588737", "#6a9742"), "autumn": ("#e6c336", "#d0a02c"), "flower": ("#d3c2ef", "#9c86de"), "bloom": "raceme"},
    "akebia-quinata": {"leaf": "five", "green": ("#3c5d36", "#6a8a52"), "autumn": ("#5a4652", "#6b6a4c"), "flower": ("#6b2740", "#b47d95"), "bloom": "single"},
    "campsis-x-tagliabueana-madame-galen": {"leaf": "pinnate", "green": ("#304e20", "#43622a"), "autumn": ("#b3ad48", "#968c38"), "flower": ("#dc4a28", "#ef8f34"), "bloom": "single"},
    "clematis-armandi": {"leaf": "three", "green": ("#22381c", "#33482a"), "autumn": ("#33482a", "#22381c"), "flower": ("#fffae8", "#f7edc8"), "bloom": "single"},
    "clematis-cirrhosa-freckles": {"leaf": "three", "green": ("#1f3a1a", "#7f9468"), "autumn": ("#1f3a1a", "#7f9468"), "flower": ("#f8f2dc", "#c46a8e"), "bloom": "single"},
    "clematis-viticella-etoile-violette": {"leaf": "three", "green": ("#4f7f37", "#62923f"), "autumn": ("#b3a24a", "#8a6a3a"), "flower": ("#46135f", "#2a093f"), "bloom": "single"},
    "hedera-helix": {"leaf": "lobed", "green": ("#283d26", "#2b4c19"), "autumn": ("#283d26", "#2b4c19"), "flower": ("#c4cc6c", "#a9b85a"), "bloom": "head"},
    "hydrangea-anomala-subsp-petiolaris": {"leaf": "broad", "green": ("#3f6a2a", "#4f7d30"), "autumn": ("#e3c53a", "#d9cf73"), "flower": ("#f7f3e2", "#cfd6a6"), "bloom": "head"},
    "lonicera-henryi": {"leaf": "simple", "green": ("#2f4a26", "#4c6a36"), "autumn": ("#2f4a26", "#4c6a36"), "flower": ("#7e2040", "#ead8a0"), "bloom": "single"},  # greens: stand-in
    "lonicera-periclymenum-graham-thomas": {"leaf": "simple", "green": ("#304a2b", "#6c8656"), "autumn": ("#566a33", "#7c8046"), "flower": ("#f6ebbd", "#fdf5d6"), "bloom": "single"},
    "rosa-the-generous-gardener": {"leaf": "pinnate", "green": ("#66803e", "#6c8a3a"), "autumn": ("#66803e", "#8a7448"), "flower": ("#f6d5da", "#f3a6b6"), "bloom": "head"},  # open flower: stand-in from its bud colours
    "trachelospermum-jasminoides": {"leaf": "simple", "green": ("#27431f", "#365a29"), "autumn": ("#5a3a22", "#7c2a22"), "flower": ("#fbfbf3", "#eef0e2"), "bloom": "single"},
    "vitis-coignetiae": {"leaf": "lobed", "green": ("#3b6a22", "#4f7a2c"), "autumn": ("#a3142a", "#ee861c"), "flower": ("#cdd690", "#e6cf58"), "bloom": "head"},
}
PLAIN = {"leaf": "simple", "green": ("#3f6a2a", "#4f7d30"), "autumn": ("#b3a24a", "#8a6a3a"), "flower": ("#f2efe0", "#d8d2b0"), "bloom": "single"}
BARK = (0.11, 0.075, 0.05)


# --- reading a run, and what is on the plant on a day: presence.ts ----------------------------------


def load(path: Path) -> dict:
    """A run: growth.json as the simulator wrote it, or the lightened copy (`npm run lighten`), which is the same gzipped."""
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def day_of(run: dict, date: str) -> int:
    start = datetime.date.fromisoformat(run["start"])
    return (datetime.date.fromisoformat(date) - start).days


def year_of(run: dict, day: int) -> int:
    return (datetime.date.fromisoformat(run["start"]) + datetime.timedelta(days=day)).year


def jitter(x: float, y: float, z: float) -> float:
    s = sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453
    return s - floor(s)


def _clamp(x: float) -> float:
    return min(1.0, max(0.0, x))


def leaf_state(leaf: dict, season: dict | None, day: int):
    """(in leaf, how far open 0-1, how far turned 0-1): presence.ts `leafState`."""
    removed = leaf["removedDay"]
    if not season or day < leaf["bornDay"] or (removed >= 0 and day >= removed):
        return False, 0.0, 0.0
    p, last, evergreen = leaf["position"], leaf.get("lastYear"), leaf["evergreen"]
    before = season.get("leafFallBefore")
    if before and not evergreen and leaf["firstYear"] < season["year"] and (last is None or last >= season["year"] - 1):
        own = jitter(*p)
        if day <= before[0] + own * (before[1] - before[0]):
            turn = season.get("autumnColourBefore") or [before[0], before[0]]
            return True, 1.0, _clamp((day - turn[0] - own * 10) / max(1, turn[1] - turn[0]))
    if season["year"] < leaf["firstYear"] or (last is not None and season["year"] > last):
        return False, 0.0, 0.0
    flush0, flush1 = season["leafFlush"]
    j = jitter(*p)
    opens_from = max(flush0, leaf["bornDay"])
    opens_over = 21 if leaf["bornDay"] > flush0 else max(1, flush1 - flush0)
    if evergreen:
        if season["year"] == leaf["firstYear"]:
            if day < opens_from:
                return False, 0.0, 0.0
            return True, _clamp((day - opens_from) / opens_over), 0.0
        return True, 1.0, 0.0
    if day < opens_from:
        return False, 0.0, 0.0
    fall0, fall1 = season["leafFall"]
    if day > fall0 + j * (fall1 - fall0):
        after = season.get("leafFlushAfter")
        if after and day >= after[0] and (last is None or last > season["year"]):
            return True, _clamp((day - after[0]) / max(1, after[1] - after[0])), 0.0
        return False, 0.0, 0.0
    turn0, turn1 = season["autumnColour"]
    return True, _clamp((day - opens_from) / opens_over), _clamp((day - turn0 - j * 10) / max(1, turn1 - turn0))


def flower_state(flower: dict, day: int):
    """("absent" | "in_bud" | "open", 0-1 through that phase): presence.ts `flowerState`."""
    spent = flower["spentDay"]
    if day < flower["developDay"] or (spent >= 0 and day >= spent):
        return "absent", 0.0
    if day < flower["openDay"]:
        return "in_bud", _clamp((day - flower["developDay"]) / max(1, flower["openDay"] - flower["developDay"]))
    return "open", (_clamp((day - flower["openDay"]) / max(1, spent - flower["openDay"])) if spent >= 0 else 0.0)


def stem_runs(run: dict, stem: dict, day: int) -> list:
    """The stem on a day, as runs of (centre, radius in metres): presence.ts `stemPointAlive` and `stemRadiusM`."""
    tip, power, last = run["thickening"]["tipRadiusMm"], run["thickening"]["exponent"], run["lastDay"]
    contact, away, born, removed, final = stem["contact"], stem["away"], stem["bornDay"], stem["removedDay"], stem["radiusMm"]
    runs, now = [], []
    for i in range(len(born)):
        if born[i] <= day and (removed[i] < 0 or day < removed[i]):
            age = _clamp((day - born[i]) / max(1, last - born[i]))
            r = (tip + max(0.0, final[i] - tip) * age**power) / 1000.0
            now.append(((contact[3 * i] + away[3 * i] * r, contact[3 * i + 1] + away[3 * i + 1] * r, contact[3 * i + 2] + away[3 * i + 2] * r), r))
        elif now:
            runs.append(now)
            now = []
    if now:
        runs.append(now)
    return [r for r in runs if len(r) > 1]


# --- plain organs: one unit long, +Z along the stalk away from the stem, +Y the side that faces the sky ----


def _leaflet(base, along, length, width, verts, faces):
    """A leaflet in the X-Z plane from `base`, `along` degrees round from +Z, folded a little along its midrib."""
    a = radians(along)
    u, v = Vector((sin(a), 0.0, cos(a))), Vector((cos(a), 0.0, -sin(a)))
    base = Vector(base)
    k = len(verts)
    mid = [base, base + u * length * 0.5 - Vector((0, 0.03 * length, 0)), base + u * length]
    left = [base + u * length * t + v * width * w + Vector((0, 0.05 * length, 0)) for t, w in ((0.28, 0.42), (0.62, 0.5))]
    right = [base + u * length * t - v * width * w + Vector((0, 0.05 * length, 0)) for t, w in ((0.28, 0.42), (0.62, 0.5))]
    verts += [tuple(p) for p in mid + left + right]
    faces += [(k, k + 1, k + 3), (k + 1, k + 4, k + 3), (k + 1, k + 2, k + 4), (k, k + 5, k + 1), (k + 1, k + 5, k + 6), (k + 1, k + 6, k + 2)]


def _stalk(z0, z1, verts, faces, w=0.012):
    k = len(verts)
    verts += [(-w, 0, z0), (w, 0, z0), (w, 0, z1), (-w, 0, z1)]
    faces.append((k, k + 1, k + 2, k + 3))


def leaf_shape(kind: str):
    verts, faces = [], []
    if kind == "pinnate":
        _stalk(0.0, 1.0, verts, faces)
        for z in (0.24, 0.4, 0.56, 0.72, 0.88):
            _leaflet((0, 0, z), 62, 0.3, 0.26, verts, faces)
            _leaflet((0, 0, z), -62, 0.3, 0.26, verts, faces)
        _leaflet((0, 0, 0.94), 0, 0.3, 0.26, verts, faces)
    elif kind == "five":
        _stalk(0.0, 0.5, verts, faces)
        for a in (-78, -38, 0, 38, 78):
            _leaflet((0, 0, 0.5), a, 0.5, 0.42, verts, faces)
    elif kind == "three":
        _stalk(0.0, 0.42, verts, faces)
        for a in (-52, 0, 52):
            _leaflet((0, 0, 0.42), a, 0.58, 0.4, verts, faces)
    elif kind == "lobed":
        _stalk(0.0, 0.3, verts, faces)
        for a, length, width in ((-72, 0.5, 0.75), (-36, 0.62, 0.7), (0, 0.7, 0.7), (36, 0.62, 0.7), (72, 0.5, 0.75)):
            _leaflet((0, 0, 0.3), a, length, width, verts, faces)
    else:
        _stalk(0.0, 0.14, verts, faces)
        _leaflet((0, 0, 0.14), 0, 0.86, 0.95 if kind == "broad" else 0.6, verts, faces)
    return verts, faces


def flower_shape(kind: str):
    """A raceme one unit long down its axis; a single flower or a flat head one unit across, facing along +Z."""
    verts, faces = [], []
    if kind == "raceme":  # a hanging cluster of small flowers, set spirally down the stalk and smaller toward the tip
        count = 84
        _stalk(0.0, 1.0, verts, faces, 0.004)
        for k in range(count):
            t = (k + 0.5) / count
            turn, out, size = radians(137.5 * k), 0.02 + 0.085 * (1.0 - 0.72 * t) * min(1.0, 6.0 * t + 0.35), 0.075 * (1.0 - 0.55 * t)
            c = Vector((out * cos(turn), out * sin(turn), t))
            u = Vector((cos(turn), sin(turn), 0.25)).normalized()  # outward, and a little along the stalk
            v = Vector((-sin(turn), cos(turn), 0.0))
            w = u.cross(v)
            base = len(verts)
            verts += [tuple(c - u * size * 0.2), tuple(c + v * size * 0.5 + w * size * 0.15), tuple(c + u * size * 0.8), tuple(c - v * size * 0.5 + w * size * 0.15), tuple(c + u * size * 0.3 - w * size * 0.45)]
            faces += [(base, base + 1, base + 2), (base, base + 2, base + 3), (base, base + 4, base + 2)]
        return verts, faces
    petals = 11 if kind == "head" else 6
    verts.append((0.0, 0.0, 0.02))
    for i in range(petals):
        a0, a1, am = 2 * pi * (i - 0.42) / petals, 2 * pi * (i + 0.42) / petals, 2 * pi * i / petals
        k = len(verts)
        verts += [(0.2 * cos(a0), 0.2 * sin(a0), 0.06), (0.5 * cos(am), 0.5 * sin(am), 0.12 if kind == "single" else 0.04), (0.2 * cos(a1), 0.2 * sin(a1), 0.06)]
        faces.append((0, k, k + 1, k + 2))
    return verts, faces


# --- drawing ----------------------------------------------------------------------------------------


def _material(name: str, pair: tuple, turned: tuple | None, finish, light: float = 0.3):
    """A leaf's or a flower's material: its two colours mixed leaf by leaf, turning to autumn where the run says so."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    a, b = _rgb(pair[0]), _rgb(pair[1])
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = (*a, 1.0)
    nt = m.node_tree
    nt.nodes.clear()
    n, link = nt.nodes, nt.links.new
    tone = n.new("ShaderNodeAttribute")
    tone.attribute_type, tone.attribute_name = "INSTANCER", "tone"
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    link(tone.outputs["Fac"], mix.inputs[0])
    mix.inputs[6].default_value, mix.inputs[7].default_value = (*a, 1.0), (*b, 1.0)
    colour = mix.outputs[2]
    if turned:
        fall = n.new("ShaderNodeAttribute")
        fall.attribute_type, fall.attribute_name = "INSTANCER", "autumn"
        gold, mix2 = n.new("ShaderNodeMix"), n.new("ShaderNodeMix")
        gold.data_type = mix2.data_type = "RGBA"
        link(tone.outputs["Fac"], gold.inputs[0])
        gold.inputs[6].default_value, gold.inputs[7].default_value = (*_rgb(turned[0]), 1.0), (*_rgb(turned[1]), 1.0)
        link(fall.outputs["Fac"], mix2.inputs[0])
        link(colour, mix2.inputs[6])
        link(gold.outputs[2], mix2.inputs[7])
        colour = mix2.outputs[2]
    p, through, both = n.new("ShaderNodeBsdfPrincipled"), n.new("ShaderNodeBsdfTranslucent"), n.new("ShaderNodeMixShader")
    link(colour, p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.55
    link(colour, through.inputs["Color"])
    both.inputs[0].default_value = light  # a leaf lets some light through: it glows when the sun is behind it
    link(p.outputs["BSDF"], both.inputs[1])
    link(through.outputs["BSDF"], both.inputs[2])
    return finish(m, both.outputs[0], a, False)


def _organ(name: str, shape, material, sources):
    obj = bpy.data.objects.get(name)
    if obj:
        return obj
    verts, faces = shape
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    sources.objects.link(obj)
    return obj


def _instancer(organ):
    """Geometry nodes: on every point of the mesh, this organ, turned by `turn` and sized by `size`. One group to an organ."""
    ng = bpy.data.node_groups.get(f"STUDY_grown_{organ.name}")
    if ng:
        return ng
    ng = bpy.data.node_groups.new(f"STUDY_grown_{organ.name}", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, link = ng.nodes, ng.links.new
    gin, gout = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    info, place = n.new("GeometryNodeObjectInfo"), n.new("GeometryNodeInstanceOnPoints")
    info.inputs["As Instance"].default_value = True
    turn, size = n.new("GeometryNodeInputNamedAttribute"), n.new("GeometryNodeInputNamedAttribute")
    turn.data_type, size.data_type = "FLOAT_VECTOR", "FLOAT"
    turn.inputs["Name"].default_value, size.inputs["Name"].default_value = "turn", "size"
    link(gin.outputs["Geometry"], place.inputs["Points"])
    info.inputs["Object"].default_value = organ
    link(info.outputs["Geometry"], place.inputs["Instance"])
    link(next(s for s in turn.outputs if s.type == "VECTOR"), place.inputs["Rotation"])
    link(next(s for s in size.outputs if s.type == "VALUE"), place.inputs["Scale"])
    link(place.outputs["Instances"], gout.inputs["Geometry"])
    return ng


def _turned(direction, roll: float) -> tuple:
    """The Euler turn that puts an organ's +Z along `direction` and its +Y as far towards the sky as that allows."""
    z = Vector(direction).normalized()
    y = Vector((0.0, 0.0, 1.0)) - z * z.z
    if y.length < 1e-4:
        y = Vector((1.0, 0.0, 0.0))
    y.normalize()
    x = y.cross(z)
    m = Matrix((x, y, z)).transposed() @ Matrix.Rotation(roll, 3, "Z")
    return tuple(m.to_euler())


def _points(name, coll, rows, organ, tag, status, note):
    """`rows` are (position, turn, size, tone, autumn): one mesh of points that the organ is instanced on."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([r[0] for r in rows], [], [])
    for key, kind, field, index in (("turn", "FLOAT_VECTOR", "vector", 1), ("size", "FLOAT", "value", 2), ("tone", "FLOAT", "value", 3), ("autumn", "FLOAT", "value", 4)):
        layer = mesh.attributes.new(key, kind, "POINT")
        layer.data.foreach_set(field, [c for r in rows for c in r[index]] if kind == "FLOAT_VECTOR" else [r[index] for r in rows])
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    obj.modifiers.new("organs", "NODES").node_group = _instancer(organ)
    obj["study_instances"] = len(rows)
    return tag(obj, status, note)


def draw(run: dict, date: str, coll, sources, tools: dict, label: str) -> dict:
    """The run's climbers on `date`, into `coll`. Returns what it drew, for the log and the record."""
    tag, status, finish = tools["tag"], tools["status"], tools["finish"]
    day = day_of(run, date)
    year = year_of(run, day)
    taxon = {p["id"]: p["taxonId"] for p in run["plants"]}
    seasons = {s["plantId"]: s for s in run["seasons"] if s["year"] == year}
    bark = bpy.data.materials.get("STUDY_grown_stem")
    if not bark:
        bark = bpy.data.materials.new("STUDY_grown_stem")
        bark.use_nodes = True
        bark.diffuse_color = (*BARK, 1.0)
        nt = bark.node_tree
        nt.nodes.clear()
        p = nt.nodes.new("ShaderNodeBsdfPrincipled")
        p.inputs["Base Color"].default_value, p.inputs["Roughness"].default_value = (*BARK, 1.0), 0.8
        bark = finish(bark, p.outputs["BSDF"], BARK, False)

    # stems: one curve per climber
    by_plant, metres, thickest = {}, 0.0, 0.0
    for stem in run["stems"]:
        for points in stem_runs(run, stem, day):
            by_plant.setdefault(stem["plantId"], []).append(points)
    for plant_id, runs in by_plant.items():
        curve = bpy.data.curves.new(f"GP_{label}_{plant_id}_stems", "CURVE")
        curve.dimensions, curve.bevel_depth, curve.bevel_resolution, curve.use_fill_caps = "3D", 1.0, 1, True
        for points in runs:
            spline = curve.splines.new("POLY")
            spline.points.add(len(points) - 1)
            spline.points.foreach_set("co", [c for (x, y, z), _ in points for c in (x, y, z, 1.0)])
            spline.points.foreach_set("radius", [r for _, r in points])
            metres += sum((Vector(a[0]) - Vector(b[0])).length for a, b in zip(points, points[1:]))
            thickest = max(thickest, max(r for _, r in points))
        curve.materials.append(bark)
        obj = bpy.data.objects.new(curve.name, curve)
        coll.objects.link(obj)
        tag(obj, status, f"{plant_id} ({taxon.get(plant_id, '')}) on {date}: its stems as the run has them, each point as thick as it was that day.")

    # leaves and flowers: points, by species
    leaves, flowers = {}, {}
    for leaf in run["leaves"]:
        present, open_, turned = leaf_state(leaf, seasons.get(leaf["plantId"]), day)
        if not present or open_ <= 0.02:
            continue
        j = jitter(*leaf["position"])
        key = (taxon.get(leaf["plantId"], ""), leaf.get("form") or "")
        leaves.setdefault(key, []).append((tuple(leaf["position"]), _turned(leaf["direction"], (j - 0.5) * 0.9), leaf["lengthM"] * (0.25 + 0.75 * open_), j, turned))
    for flower in run["flowers"]:
        phase, progress = flower_state(flower, day)
        if phase == "absent":
            continue
        j = jitter(*flower["position"])
        size = flower["lengthM"] * (0.35 + 0.4 * progress if phase == "in_bud" else 1.0)
        flowers.setdefault(taxon.get(flower["plantId"], ""), []).append((tuple(flower["position"]), _turned(flower.get("direction") or (0.0, 0.0, -1.0), j * 6.283), size, j, 0.0))
    for (kind, form), rows in leaves.items():
        look = LOOKS.get(kind, PLAIN)
        organ = _organ(f"GO_leaf_{kind}", leaf_shape(look["leaf"]), _material(f"STUDY_grown_leaf_{kind}", look["green"], look["autumn"], finish), sources)
        _points(f"GP_{label}_{kind}{'_' + form if form else ''}_leaves", coll, rows, organ, tag, status, f"{len(rows)} leaves of {kind} in leaf on {date}, where the run put them. Their shape is a plain leaf of the right kind, not the species' own.")
    for kind, rows in flowers.items():
        look = LOOKS.get(kind, PLAIN)
        organ = _organ(f"GO_flower_{kind}", flower_shape(look["bloom"]), _material(f"STUDY_grown_flower_{kind}", look["flower"], None, finish, 0.15), sources)
        _points(f"GP_{label}_{kind}_flowers", coll, rows, organ, tag, status, f"{len(rows)} flowers of {kind} in bud or open on {date}, where the run put them. A plain shape in the species' colour.")
    return {"date": date, "day": day, "climbers": len(by_plant), "stem_m": round(metres), "thickest_stem_mm": round(thickest * 2000), "leaves": sum(len(r) for r in leaves.values()), "flowers": sum(len(r) for r in flowers.values())}
