"""The labels of the section and of the plant's view: a few words each, standing in the plane of the cut.

Called by build_scene.py. The section's labels live in S95_SECTION_NOTES and the plant's view's in
S96_PLANT_NOTES; each collection is hidden from every render but its own view's. The numbers in the
labels are read from ground/<configuration>.json and site.json, so they follow the scene.
"""
from __future__ import annotations

from math import cos, pi, radians, sin

import bpy

PAPER = (0.9, 0.89, 0.86)
INK = (0.015, 0.015, 0.015)
ACCENT = (0.5, 0.08, 0.03)


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


class Sheet:
    """Labels for one cut: text, leaders and dots just behind the cut plane."""

    def __init__(self, coll, cut_y, tag, status, size):
        self.coll, self.tag, self.status, self.size = coll, tag, status, size
        self.front, self.back = cut_y + 0.03, cut_y + 0.06
        self.ink, self.accent, self.paper = _emit("STUDY_note_ink", INK), _emit("STUDY_note_accent", ACCENT), _emit("STUDY_note_paper", PAPER, 1.5)
        self.count = 0

    def _text(self, body, x, z, size, material, name):
        curve = bpy.data.curves.new(name, "FONT")
        curve.body, curve.size, curve.space_line = body, size, 1.2
        curve.materials.append(material)
        obj = bpy.data.objects.new(name, curve)
        obj.location, obj.rotation_euler = (x, self.front, z), (radians(90.0), 0.0, 0.0)
        self.coll.objects.link(obj)
        self.tag(obj, self.status, "A label.")
        return obj

    def _quad(self, points, material, name, y=None):
        y = self.front if y is None else y
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(px, y, pz) for px, pz in points], [], [tuple(range(len(points)))])
        mesh.materials.append(material)
        obj = bpy.data.objects.new(name, mesh)
        self.coll.objects.link(obj)
        self.tag(obj, self.status, "Part of a label.")

    def stroke(self, a, b, material=None, width=None):
        width = width or self.size * 0.09
        dx, dz = b[0] - a[0], b[1] - a[1]
        length = (dx * dx + dz * dz) ** 0.5 or 1.0
        nx, nz = -dz / length * width / 2.0, dx / length * width / 2.0
        self.count += 1
        self._quad([(a[0] - nx, a[1] - nz), (b[0] - nx, b[1] - nz), (b[0] + nx, b[1] + nz), (a[0] + nx, a[1] + nz)], material or self.ink, f"{self.coll.name}_stroke_{self.count}")

    def dot(self, at, material=None):
        r = self.size * 0.22
        self.count += 1
        self._quad([(at[0] + r * cos(2 * pi * k / 14), at[1] + r * sin(2 * pi * k / 14)) for k in range(14)], material or self.ink, f"{self.coll.name}_dot_{self.count}")

    def note(self, words, x, z, target=None, small="", accent=False, backed=True):
        """A few words with their top-left at (x, z), a smaller line under them, and a leader to `target`."""
        self.count += 1
        name = f"{self.coll.name}_{self.count:02d}"
        colour = self.accent if accent else self.ink
        head = self._text(words, x, z - self.size * 0.8, self.size, colour, name)
        bottom = z - self.size * 1.1
        width = 0.0
        if small:
            sub = self._text(small, x, bottom - self.size * 0.62, self.size * 0.68, self.ink, name + "_small")
            bottom -= self.size * 0.68 * 1.2 * (small.count(chr(10)) + 1) + self.size * 0.1
        bpy.context.view_layer.update()
        width = max(head.dimensions.x, sub.dimensions.x if small else 0.0)
        pad = self.size * 0.42
        if backed:
            self._quad([(x - pad, bottom - pad), (x + width + pad, bottom - pad), (x + width + pad, z + pad), (x - pad, z + pad)], self.paper, name + "_backing", self.back)
        if target:
            corners = [(x - pad, (z + bottom) / 2.0), (x + width + pad, (z + bottom) / 2.0), (x + width / 2.0, bottom - pad), (x + width / 2.0, z + pad)]
            start = min(corners, key=lambda c: (c[0] - target[0]) ** 2 + (c[1] - target[1]) ** 2)
            self.stroke(start, target, colour)
            self.dot(target, colour)


def extent(view) -> tuple:
    """A cut's picture: its left, right, bottom and top in the plane of the cut."""
    (cx, cz), w = view["centre_m"], view["width_m"]
    h = w * view["size_px"][1] / view["size_px"][0]
    return cx - w / 2.0, cx + w / 2.0, cz - h / 2.0, cz + h / 2.0


def add(colls, site, ground, tools) -> None:
    plane, tag, status = tools["plane"], tools["tag"], tools["status"]
    q = ground["quantities"]
    cams = site["cameras"]
    cut = cams["section"]["cut_y_m"]
    level, piers = ground["pier_levels_m"], ground["piers"]
    high, low = max(level, key=level.get), min(level, key=level.get)
    fall = round(1.0 / site["ground"]["fall"])
    drop = q["fall_across_the_room_m"]["value"]
    sunk = round(site["ground"]["feet_below_soil_m"] * 1000)
    cable = ground["cable"]
    hx, hz = piers[high][0], level[high]
    lx, lz = piers[low][0], level[low]

    # --- the section: the whole place, cut through the uphill and the downhill pier ---
    s = Sheet(colls["S95_SECTION_NOTES"], cut, tag, status, 0.4)
    left, right, bottom, top = extent(cams["section"])
    s.note("One fall, and nothing levelled", left + 0.6, top - 0.6, small=f"The place cut through its uphill and its downhill pier, on the day it is planted." + chr(10) + f"The ground falls 1 in {fall}: {drop} m across the room.")
    hol = site["ground"]["hollow"]
    s.note("planted hollow", left + 0.9, 3.0, (hol["at_m"][0], plane(hol["at_m"][0], cut) - hol["depth_m"] + 0.06), small="where the swale and the" + chr(10) + "floor's water end")
    s.note("longest legs", lx - 7.6, lz + 6.2, (lx + 0.05, lz + 1.3), small=f"{drop} m longer than uphill")
    s.note("the same roof", -2.9, 9.0, (0.0, 6.2), small="nothing above the feet moves")
    s.note("legs cut to the ground", hx + 1.9, hz + 6.0, (hx - 0.05, hz + 1.3), small=q["members_made_longer"]["says"].split(",")[0])
    sw = site["ground"]["swale"]["radius_m"]
    s.note("swale", sw - 1.4, plane(sw, cut) + 3.0, (sw, plane(sw, cut) - 0.16), small="the garden's run-off" + chr(10) + "goes round the room")
    s.note("bed soil, loosened in place", lx - 8.2, lz - 1.9, (lx + 0.9, lz - 0.75), small="open to the ground round it")
    s.note("the floor follows the ground", -3.6, plane(0.0, cut) - 1.3, (-1.5, plane(-1.5, cut) + 0.03), small="bound gravel, no platform, no step")
    s.note("buried sole on screw piles", hx + 1.7, hz - 1.9, (hx - 0.08, hz - 1.5), small="no footing is seen")

    # --- the plant's view: the same cut at the uphill pier ---
    p = Sheet(colls["S96_PLANT_NOTES"], cams["plant"]["cut_y_m"], tag, status, 0.105)
    left, right, bottom, top = extent(cams["plant"])
    soil = ground["soil_at_pier_m"][high]
    near = min((pl for pl in ground["plants"] if pl["pier"] == high), key=lambda pl: abs(pl["root_m"][1] - cut))
    rx = near["root_m"][0]
    up = min(near["route_m"], key=lambda pt: abs(pt[2] - (hz + 1.9)))
    seen = [m for m in ground["mesh_sleeves"] if m["kind"] not in ("base", "pier_mitre") and left + 0.4 < m["at_m"][0] < right - 0.4 and hz + 1.6 < m["at_m"][2] < top - 0.5 and m["at_m"][1] > cut]
    p.note("What the plant asked for", left + 0.15, bottom + 0.6, small="One pier, from under its roots to its first joints," + chr(10) + "on the day it is planted.")
    p.note("cable for the trunk", left + 0.15, top - 1.15, (up[0], up[2]), small=f"{round(cable['foot_gap_m'] * 1000)} mm off the leg at the foot," + chr(10) + f"{round(cable['gap_m'] * 1000)} mm higher up")
    p.note("thin growth on the timber", left + 0.15, top - 2.1, small="tied in by hand; not drawn")
    if seen:
        m = min(seen, key=lambda m: m["at_m"][1])
        p.note("mesh at each joint", right - 1.75, top - 0.6, (m["at_m"][0], m["at_m"][2]), small="keeps growth out of the joints")
    p.note("planted at its cable", right - 1.55, soil + 1.75, (rx, soil + 0.14), small=f"{round(q['planted_from_its_cable_m']['value'] * 1000)} mm from the cable's foot")
    p.note("timber into the soil", right - 1.55, soil + 1.0, (hx - 0.1, soil - 0.03), small=f"{sunk} mm; the steel is under it, unseen")
    p.note("root ball, in open soil", left + 0.15, soil - 0.5, (rx, soil - 0.16), small="no plate under it")
    p.note("screw pile", right - 1.5, soil - 0.75, (hx - 0.08, soil - 1.1), small=f"{ground['piles']['length_m']} m long, {ground['footings'][high]['nearest_pile_to_a_climber_m']} m from" + chr(10) + "the nearest climber")
