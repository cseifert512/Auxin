"""The labels of the section: text, leaders and a sun arrow standing in the plane of the cut.

Called by build_scene.py. They live in the collection S95_SECTION_NOTES, which is hidden from every
render but the section's. Each label says what a thing is and which of the four kinds it belongs to:

    linked      the snapshot's geometry
    generated   set out by bower/ground.py and bower/lines.py on the snapshot's design
    proposal    authored for this study
    borrowed    people, garden plants, sky

The numbers in the labels are read from ground.json and site.json, so they follow the scene.
"""
from __future__ import annotations

import textwrap
from math import cos, pi, radians, sin

import bpy

PAPER = (0.9, 0.89, 0.86)
INK = (0.015, 0.015, 0.015)
ACCENT = (0.5, 0.08, 0.03)
SUN = (0.9, 0.45, 0.02)
BODY, HEAD, LINE = 0.25, 0.3, 1.22


def _emit(name, colour, strength=1.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = (*colour, 1.0)
    nt = m.node_tree
    nt.nodes.clear()
    out, e = nt.nodes.new("ShaderNodeOutputMaterial"), nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*colour, 1.0)
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    return m


def add(coll, site, ground, cut_y, tag, status) -> None:
    ink, accent, paper, sun = _emit("STUDY_note_ink", INK), _emit("STUDY_note_accent", ACCENT), _emit("STUDY_note_paper", PAPER, 1.5), _emit("STUDY_note_sun", SUN)
    front, back = cut_y + 0.03, cut_y + 0.06  # the text just behind the cut, its backing just behind the text
    count = [0]

    def text(body, x, z, size, material, name):
        curve = bpy.data.curves.new(name, "FONT")
        curve.body, curve.size, curve.space_line = body, size, LINE
        curve.materials.append(material)
        obj = bpy.data.objects.new(name, curve)
        obj.location, obj.rotation_euler = (x, front, z), (radians(90.0), 0.0, 0.0)
        coll.objects.link(obj)
        tag(obj, status, "A label of the section.")
        return obj

    def quad(points, material, name, y=None):
        y = front if y is None else y
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(px, y, pz) for px, pz in points], [], [tuple(range(len(points)))])
        mesh.materials.append(material)
        obj = bpy.data.objects.new(name, mesh)
        coll.objects.link(obj)
        tag(obj, status, "Part of a label of the section.")
        return obj

    def stroke(a, b, material, name, width=0.022):
        dx, dz = b[0] - a[0], b[1] - a[1]
        length = (dx * dx + dz * dz) ** 0.5 or 1.0
        nx, nz = -dz / length * width / 2.0, dx / length * width / 2.0
        quad([(a[0] - nx, a[1] - nz), (b[0] - nx, b[1] - nz), (b[0] + nx, b[1] + nz), (a[0] + nx, a[1] + nz)], material, name)

    def dot(at, material, name, r=0.06):
        quad([(at[0] + r * cos(2 * pi * k / 14), at[1] + r * sin(2 * pi * k / 14)) for k in range(14)], material, name)

    def note(heading, body, x, z, wrap=30, target=None, kind="", backed=False, colour=None):
        """A heading and a paragraph with their top-left at (x, z); a leader to `target`; a paper backing over a busy background."""
        count[0] += 1
        name = f"NT_{count[0]:02d}"
        colour = colour or ink
        lines = textwrap.wrap(body + (f" ({kind})" if kind else ""), wrap)
        head = text(heading, x, z - HEAD * 0.8, HEAD, colour, name + "_heading")
        para = text(chr(10).join(lines), x, z - HEAD * 0.8 - HEAD * 0.55 - BODY * 0.8, BODY, ink, name + "_text")
        bpy.context.view_layer.update()
        width = max(head.dimensions.x, para.dimensions.x)
        bottom = z - HEAD * 1.35 - BODY * LINE * len(lines) - 0.02
        if backed:
            quad([(x - 0.12, bottom - 0.08), (x + width + 0.12, bottom - 0.08), (x + width + 0.12, z + 0.1), (x - 0.12, z + 0.1)], paper, name + "_backing", back)
        if target:
            corners = [(x - 0.06, z - HEAD * 0.45), (x + width + 0.06, z - HEAD * 0.45), (x - 0.06, bottom), (x + width + 0.06, bottom), (x + width / 2.0, bottom - 0.04), (x + width / 2.0, z + 0.06)]
            start = min(corners, key=lambda c: (c[0] - target[0]) ** 2 + (c[1] - target[1]) ** 2)
            stroke(start, target, colour, name + "_leader")
            dot(target, colour, name + "_dot")
        return bottom

    report = ground["report"]
    lo, hi = report["handover_height_m"]
    zone = ground["root_zones"][0]
    piles = ground["piles"]
    planted = ground["stations_of_the_grown_planting"]
    on_cap = sum(1 for s in planted if s["on_the_cap"])
    out = round(sum(s["to_nearest_root_zone_m"] for s in planted) / max(1, len(planted)), 1)
    soil = -piles["feet_above_soil_m"]
    built_up = round(site["levels"]["floor_centre_m"] - soil, 2)
    fall = round(1.0 / site["levels"]["floor_fall"])
    cx, cz = site["cameras"]["section"]["centre_m"]
    top = cz + site["cameras"]["section"]["width_m"] * 0.45 / 2.0  # the top of the picture, which is 0.45 as tall as it is wide
    left = cx - site["cameras"]["section"]["width_m"] / 2.0 + 0.3

    # the title, and what the four kinds are
    title = text("Section through piers P6 and P3, looking north", left, top - 0.62, 0.42, ink, "NT_title")
    kinds = "The same scene as the arrival view, cut at the southern feet of the two piers, at installation. Every size is provisional. Linked: the timber, snapshot %s. Generated: set out by the building model's own ground and line code on that snapshot's design. Proposal: authored for this study. Borrowed: people, garden plants, sky." % ground["snapshot"]
    text(chr(10).join(textwrap.wrap(kinds, 86)), left, top - 1.02, 0.21, ink, "NT_kinds")
    row = top - 2.25

    # sky, left: the sun and the care
    note("Late afternoon sun", "From the west-south-west, 27 degrees up. The sky is a photograph: no date or latitude is modelled.", left, row, 30, None, "borrowed", True)
    a = (left + 0.6, row - 2.45)
    b = (a[0] + 2.6, a[1] - 2.6 * 0.56)
    stroke(a, b, sun, "NT_sun_ray", 0.05)
    quad([b, (b[0] - 0.36, b[1] + 0.02), (b[0] - 0.2, b[1] + 0.32)], sun, "NT_sun_head")
    note("Care from outside", f"A woodchip path behind the beds and a standing pad at each pier: tending crosses neither the entrance nor a bed. The hand-overs are {lo} to {hi} m up, so it takes a pair of steps.", left + 4.9, row, 30, (-7.3, 1.45), "proposal", True)

    # sky, right
    high = top - 0.62
    note("Supports for the climbers", "Training lines on the legs and hoops (blue); feeders up the outside of the arch legs (red); ties where a shoot is handed across (green).", -3.7, high, 30, (-6.05, 2.75), "generated", True)
    note("Shade comes later", "Today the timber alone filters the sun. The canopy over this floor is years of growth and care away, and is not drawn.", 1.5, high, 30, (2.2, 4.72), "", True)
    note("Climbers as planted", f"Twelve, {site['planting_at_installation']['cane_height_m']} m long, one at each root zone, tied to a feeder. A diagram of a new plant, not a grown or simulated one.", 6.3, high, 30, (6.52, 1.5), "proposal", True)
    note("A garden around it", "Trees to the north; south and west left open to the sun. Border, unmown strip, log and damp hollow are meant for other life: intentions, not findings.", 10.9, high, 27, (10.0, -0.1), "borrowed models", True)

    # in the ground, first row: between the surface and the pile tips
    under = soil - 0.7
    note("The garden's own soil", "Beds are not containers: the ground is loosened and mulched in place, and roots can run on under path and lawn. No site, so no known soil.", left, under, 30, (-11.3, soil - 0.3), "proposal")
    note("Root zone", f"{zone['soil_m3']} m3 kept for one climber, {piles['feet_above_soil_m']} m below the feet. The code's default size, not a plant's need.", -10.2, under, 25, (zone["radius_m"] * -1.0 - 6.3, soil - 0.42), "generated")
    note("A floor built up, not dug in", f"Bound gravel on a free-draining base, {built_up} m above the soil, falling 1 in {fall} to the beds, which take its water.", -4.9, under, 30, (-2.6, soil + 0.1), "proposal")
    note("Cap and screw piles", f"A steel cap lifted clear of the soil on three {piles['length_m']} m piles keeps the ground open under the pier. Set out, not engineered.", 0.4, under, 30, (5.57, -1.75), "generated")
    note("Water for establishment", "A standpipe on the care path feeds a drip line behind the beds, with a ring at each root zone. How much and how long: the plant side's to say.", 7.75, under, 34, (7.55, soil + 0.07), "proposal")

    # in the ground, second row: the question, and where the water goes
    deep = soil - 2.78
    question = f"All {on_cap} climbers that the grown planting starts from stand at the foot of a training line, and every one of those places is on a steel pile cap. The ground draft moves them {out} m out, to twelve root zones, and joins each to its lines only {lo} to {hi} m up. Which gives way at the pier: the footing, the lines or the planting?"
    note("Next: one conflict at a pier", question, left, deep, 100, None, "", False, accent)
    note("Where the water goes", "Past the level ground the garden falls north-east to a damp hollow, beyond this cut. A drainage proposal; its use to other life is an intention.", 6.9, deep, 62, None, "proposal")
