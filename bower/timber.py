"""Level C: the primary timber, generated from the plan graph and the roof surface.

A small engine. `build_timber` runs one generator for the arches and one for the
lattice, each chosen by name in design["timber"], and shares the piers out
between them:

    timber["arches"]["type"]     edge | paired | none     (ARCHES)
    timber["lattice"]["type"]    spiral | none            (LATTICES)

A new way of building either is a new generator class registered below; the
rest of the pipeline (sections, pier places, clearances, schedule, Blender
objects) does not change. A generator is given the shared `Build`, traces what
it means to build, says which of its members want to stand at a pier
(`claims`), and then builds them (`members`).

Members
    <bay>.arch.L / .R        the arch: foot -> shaft -> arch half -> apex
    <bay>.hoopN              hoops: lighter arches lying in the roof a set distance inside the arch, pier to pier
    <room>.<tier>.ccw.NN     lattice ribs that turn counter-clockwise as they climb
    <room>.<tier>.cw.NN      lattice ribs that turn clockwise
    <room>.ring.top          the crown ring, a level collar seated on the heads of the ribs that reach the top
    <room>.ring.*            the ring at the head of each tier, and rings through rows of crossings
    <bay>.inner.L / .R       (paired arches only) the lighter arch on the roof's edge

Arches, `edge`. The arch stands on the roof's edge, so it is the edge: every
lattice rib that reaches it turns to meet it squarely and is housed into it. The
two arch legs at a pier are set close enough to be mitred into one trunk. Hoops
follow each arch inside it, lying in the roof: with the rib ends that cross
them they make the laddered band behind the arch. `paired` is the earlier
arrangement, kept as an option: a light arch on the edge and a heavier one
standing proud of it.

Lattice, `spiral`. Ribs lie in the roof surface and hold a set angle to its
meridians (`lean_deg`; `lean_rim_deg` lets that angle change toward the
arches), so the two hands cross at a steady angle. The lattice is laid out from
the crown: ribs reach the top ring evenly spaced, in pairs of opposite hand,
and run outward from there. It is built in tiers, each its own family with its
own section, each starting further out than the last (top ring, part-way up the
lantern, a ring on the canopy), so the weave gets finer as the roof gets wider.

Piers. A rib whose course passes within `gather_m` of a pier is drawn into it:
it bends round, runs straight down the pier's funnel and stands on the floor as
a leg. Hoops come down the same way. The legs stand evenly spaced on an arc in
the angle between the pier's two arch legs, in the order they arrive, so a pier
is a bundle of members that each continue into the roof.

Crossings. Where two lattice members cross (ribs of either hand, hoops, rings)
both are notched and they lie flush in one surface: every lattice member has
the same depth. The joints themselves, and the cut each one makes in each
member, are set out in `bower/joints.py`.

Rib IDs follow the bearing at which a rib reaches the top ring, so they do not
change when bays are added or removed.

Pure Python (no bpy). Sections are provisional concept values: nothing here is a
structural or fabrication check.
"""
from __future__ import annotations

import math
from collections import defaultdict

from .centreline import Anchor, BezierPath, arc_path, cross, dot, mul, norm, plane_path, sub, unit
from .envelope import Roof, arch_profile, closed_spline, spline
from .member import Member
from .topology import DesignError

UP = (0.0, 0.0, 1.0)
LATTICE = ("rib", "fill", "fine", "hoop", "ring")  # families that are notched where they cross each other


class Build:
    """What the generators share while one room's timber is built."""

    def __init__(self, room: dict, timber: dict):
        self.room, self.timber, self.roof = room, timber, Roof(room)
        self.rid, self.shape, self.z0 = room["id"], room["shape"], room["floor_z_m"]
        self.section = {family: tuple(size) for family, size in timber["sections_m"].items()}
        self.members: list[Member] = []
        self.landings = defaultdict(list)  # (bay, side) -> feet of the lattice members housed into that arch half
        self.place = {}  # member ID -> plan position of its leg at a pier
        self.knee = timber.get("piers", {}).get("knee_drop_m")  # None: each leg's knee matches its first run in the roof
        self.rim_inset = 0.0  # how far short of an arch's plane a rib stops: set once the arches are known
        self.rim_band = 0.0  # how far inside the arches their hoops reach
        # the widest circle about the crown's axis that stays inside every arch
        self.clear_radius = min(self.roof.rim(2.0 * math.pi * i / 360)[0] for i in range(360))

    def member(self, member_id: str, family: str, parent: str, path: BezierPath, nodes, end_cut=None, start_cut=None) -> None:
        if family not in self.section:
            raise DesignError(f"timber.sections_m has no section for the family {family!r}")
        width, depth = self.section[family]
        self.members.append(Member(member_id, "primary", width, depth, path, parent, family, tuple(nodes), end_cut, start_cut))

    def in_roof(self, samples) -> BezierPath:
        """A path through (point, normal) samples of the roof, with the section's depth square to the surface."""
        return spline([point for point, _ in samples], [mul(normal, -1.0) for _, normal in samples])


def _inward(roof: Roof, half) -> tuple:
    """Horizontal unit vector square to an arch half, pointing into the room."""
    dx, dy = half.direction[0], half.direction[1]
    side = -dy * (roof.centre[0] - half.foot[0]) + dx * (roof.centre[1] - half.foot[1])
    return (-dy, dx, 0.0) if side > 0 else (dy, -dx, 0.0)


def pier_places(b: Build, claims: list, rim_width: float) -> dict:
    """Plan positions for the legs of the members that come down into each pier.

    `claims` are (pier, plan point the member comes from, member ID, family). At each pier the
    legs stand evenly spaced on an arc about the pier's axis, in the angle between its two arch
    legs, in the order they arrive. The arc is the smallest that keeps the legs clear of each
    other and of the arch legs by timber["piers"]["gap_m"].
    """
    cfg = b.timber.get("piers", {})
    gap = cfg.get("gap_m", 0.03)
    by_pier = defaultdict(list)
    for claim in claims:
        by_pier[claim[0]].append(claim)
    places = {}
    for pid, group in by_pier.items():
        (px, py), halves = b.roof.piers[pid]
        da, db = halves[0].direction, halves[1].direction
        bx, by = da[0] + db[0], da[1] + db[1]
        if math.hypot(bx, by) < 1e-6:  # the arches run straight through the pier
            bx, by = -da[1], da[0]
        if bx * (b.roof.centre[0] - px) + by * (b.roof.centre[1] - py) < 0.0:
            bx, by = -bx, -by
        length = math.hypot(bx, by)
        bx, by = bx / length, by / length
        half_angle = math.acos(max(-1.0, min(1.0, da[0] * bx + da[1] * by)))  # from the bisector to each arch

        def bearing(q):
            vx, vy = q[0] - px, q[1] - py
            return math.atan2(bx * vy - by * vx, bx * vx + by * vy)

        group.sort(key=lambda claim: bearing(claim[1]))
        half_w = max(b.section[claim[3]][0] for claim in group) / 2.0
        half_d = max(b.section[claim[3]][1] for claim in group) / 2.0
        count, radius, widest = len(group), cfg.get("ring_radius_m", 0.34), 0.0
        while True:
            # A leg at angle psi from the square to an arch leg's inner face clears that face by this much.
            def clear(psi: float) -> float:
                return (radius - half_d) * math.cos(psi) - half_w * math.sin(psi) - rim_width / 2.0 - gap

            if clear(0.0) > 0.0:
                lo, hi = 0.0, math.pi / 2.0
                for _ in range(40):
                    mid = 0.5 * (lo + hi)
                    lo, hi = (mid, hi) if clear(mid) >= 0.0 else (lo, mid)
                widest = lo - (math.pi / 2.0 - half_angle)  # the furthest a leg may stand from the bisector
                if count == 1 and widest >= 0.0:
                    break
                if count > 1 and widest > 0.0 and 2.0 * (radius - half_d) * math.sin(widest / (count - 1)) >= 2.0 * half_w + gap:
                    break
            radius += 0.02
            if radius > 2.5:
                raise DesignError(f"{pid}: no room for {count} legs between its arches")
        for i, claim in enumerate(group):
            phi = 0.0 if count == 1 else -widest + 2.0 * widest * i / (count - 1)
            c, s = math.cos(phi), math.sin(phi)
            places[claim[2]] = (px + radius * (bx * c - by * s), py + radius * (bx * s + by * c))
    return places


# --- lattices -----------------------------------------------------------------------------


class SpiralLattice:
    """Ribs that hold a set angle to the roof's meridians, laid out from the crown outward, in tiers.

    timber["lattice"]:
        ribs_per_family     ribs of each hand in a tier, per phase
        lean_deg            the angle the ribs hold to the meridians
        lean_top_deg        optional: the angle they have straightened to by the top ring
        lean_rim_deg        optional: the angle they have turned to by the time they reach the piers' distance
        pair_gap_m          optional: the two ribs that share a point on the top ring arrive side by side this far apart
        land_square_m       within this distance of an arch a rib turns to meet it squarely (0: it holds its course)
        land_gap_m          squared ribs are moved along the arch until neighbouring feet stand this far apart
        sample_spacing_m    distance between the points a rib is drawn through
        gather_m            a rib passing nearer than this to a pier is drawn into it
        tiers               each {family, phases, from, gathers, ring_family}:
                              phases   where its ribs fall between one top-ring position (0) and the next (1)
                              from     "top", {"lantern": 0..1} part-way up the lantern, or {"radius_m": r} on the canopy
                              gathers  false leaves out the ribs that would be drawn into a pier (default true)
                              ring_family  the family (so the section) of the ring at its head (default "ring")
        ring_rows           rows of crossings below the top ring that get a ring through them (may be fractional)

    timber["crown"]: seat_m, how far the heads of the ribs are let into the crown ring.
    """

    def __init__(self, b: Build, cfg: dict):
        self.b, self.cfg = b, cfg
        roof, rid = b.roof, b.rid
        self.count, self.lean = cfg["ribs_per_family"], math.radians(cfg["lean_deg"])
        lean_rim = math.radians(cfg["lean_rim_deg"]) if cfg.get("lean_rim_deg") is not None else None
        self.lean_top = math.radians(cfg["lean_top_deg"]) if cfg.get("lean_top_deg") is not None else None
        self.legs = b.timber.get("piers", {}).get("legs", True)
        self.ribs, self.top_heads, self.rings = [], [], []
        wound, swing = roof.winding(self.lean, self.lean_top), roof._swing(self.lean, lean_rim)
        present = []  # (phases, half the angle between a pair at the top ring) of the tiers laid so far

        def clearest(candidates, turned, radius_at, phases):
            """Of the candidate positions for a ring, the one where the members crossing it or stopping at it are furthest apart."""

            def tightest(x) -> float:
                bearings = sorted((2.0 * math.pi * (j + phase) / self.count - sense * (apart + turned(x))) % (2.0 * math.pi) for tier_phases, apart in present + [(phases, 0.0)] for phase in tier_phases for j in range(self.count) for sense in (1.0, -1.0))
                return min((b2 - b1) % (2.0 * math.pi) for b1, b2 in zip(bearings, bearings[1:] + bearings[:1])) * radius_at(x)

            return max(candidates, key=tightest)

        for tier in cfg["tiers"]:
            family, phases, start = tier["family"], tier.get("phases", [0.0]), tier.get("from", "top")
            if family not in LATTICE:
                raise DesignError(f"lattice tier family {family!r} is not one of {LATTICE}")
            top, radius, apart = 1.0, None, 0.0
            if start == "top":
                if cfg.get("pair_gap_m") is not None:
                    # Half the angle between the two ribs of a pair at the top ring: enough for the gap to
                    # hold at their inner edges, which stand nearer the crown's axis than their centrelines.
                    width, depth = b.section[family]
                    apart = (width / math.cos(self.lean_top or self.lean) + cfg["pair_gap_m"]) / (2.0 * (roof.top_radius - depth / 2.0))
            elif "lantern" in start:
                # The ring at the head of the tier is nudged to where it crosses the ribs clear of their own crossings.
                near = [min(max(start["lantern"] + 0.1 * (k - 20) / 20, 0.05), 0.95) for k in range(41)]
                top = clearest(near, wound, lambda lam: math.hypot(roof.on_lantern(0.0, lam)[0][0] - roof.centre[0], roof.on_lantern(0.0, lam)[0][1] - roof.centre[1]), phases)
            else:
                widest = b.clear_radius - max(0.8, b.rim_band + 0.35)  # stay inside the arches and clear of their hoops
                if widest < roof.base_radius + 0.3:
                    widest = b.clear_radius - 0.8  # a tight room: keep the tier, and let its ring run near the hoops
                radius = min(start["radius_m"], widest)
                if radius < roof.base_radius + 0.3:
                    continue  # the room is too tight here for a tier that starts on the canopy
                near = [min(max(radius + 0.3 * (k - 20) / 20, roof.base_radius + 0.3), widest) for k in range(41)]
                radius = clearest(near, lambda r: wound(0.0) + swing(r), lambda r: r, phases)
            present.append((phases, apart))
            heads = []
            for j in range(self.count):
                for p, phase in enumerate(phases):
                    n = j * len(phases) + p
                    for sense, hand in ((1.0, "ccw"), (-1.0, "cw")):
                        arrival = 2.0 * math.pi * (j + phase) / self.count - sense * apart
                        course = roof.trace(arrival, sense, self.lean, cfg["sample_spacing_m"], b.rim_inset, cfg["gather_m"], top, radius, lean_rim, self.lean_top)
                        if course.pier and not tier.get("gathers", True):
                            continue
                        rib_id = f"{rid}.{family}.{hand}.{n:02d}"
                        if start != "top":
                            head = rib_id + ".head"
                        else:  # the two hands share a point on the top ring
                            head = f"{rid}.top.{n:02d}" if family == "rib" else f"{rid}.top.{family}.{n:02d}"
                        heads.append(head)
                        self.ribs.append((rib_id, family, head, course, start == "top"))
            if start == "top":
                self.top_heads += heads
            elif heads:
                self.rings.append((family, top if radius is None else None, radius, tuple(heads), tier.get("ring_family", "ring")))

    def claims(self) -> list:
        if not self.legs:
            return []
        return [(course.pier, course.trail[course.turn][1], rib_id, family) for rib_id, family, _, course, _ in self.ribs if course.pier]

    def members(self) -> None:
        b, roof, rid = self.b, self.b.roof, self.b.rid
        square, spacing = self.cfg.get("land_square_m", 0.0), self.cfg["sample_spacing_m"]
        shifts = self._spread_landings(square) if square > 0.0 else {}
        for rib_id, family, head, course, to_top in self.ribs:
            foot, cut = rib_id + ".foot", None
            slot = b.place.get(rib_id)
            samples, half, along = roof.lay(course, slot, square, shifts.get(rib_id, (0.0, 0.0)))
            if slot:
                samples = roof.stand(samples, roof.piers[course.pier][0], b.knee)
            else:
                b.landings[(half.bay, half.side)].append(foot)
                # A rib that comes down at a pier or at an apex meets both of the arch halves that meet there.
                # One that arrives at a glancing angle lies against the arch for longer, so it counts from further off.
                arriving = unit(sub(samples[1][0], samples[0][0]))
                glancing = 0.2 * abs(dot(arriving, half.direction)) / max(abs(dot(arriving, _inward(roof, half))), 0.05)
                for other in roof.halves:
                    at_pier = along < roof.pier_radius + 0.3 and other.pier == half.pier and other.bay != half.bay
                    at_apex = half.span - along < max(0.4, glancing + 0.15) and other.bay == half.bay and other.side != half.side
                    if at_pier or at_apex:
                        b.landings[(other.bay, other.side)].append(foot)
                if not course.pier:  # cut to the arch's plane and housed into it
                    cut = mul(_inward(roof, half), -1.0)
            # a rib that reaches the top is cut level there, to seat in the crown ring
            b.member(rib_id, family, rid, b.in_roof(samples), (foot, head), end_cut=UP if to_top else None, start_cut=cut)

        if self.top_heads:
            self._crown(tuple(dict.fromkeys(self.top_heads)))
        for family, lam, radius, heads, ring_family in self.rings:
            self._ring(f"{rid}.ring.{family}", ring_family, roof.ring(lam, radius, spacing), heads)
        # Opposite-handed ribs cross wherever they have each turned a whole number of half-spacings
        # from the top ring. Rings can be run through chosen rows of crossings, or between rows.
        wound = roof.winding(self.lean, self.lean_top)
        for row in self.cfg.get("ring_rows", []) if self.top_heads else []:
            lo, hi = 0.0, 1.0
            for _ in range(50):
                mid = 0.5 * (lo + hi)
                lo, hi = (lo, mid) if wound(mid) < row * math.pi / self.count else (mid, hi)
            if lo > 0.02:  # the row falls inside the lantern
                self._ring(f"{rid}.ring.row{row}", "ring", roof.ring(0.5 * (lo + hi), None, spacing), (f"{rid}.ring.row{row}",))

    def _spread_landings(self, square: float) -> dict:
        """How far to move each squared rib's foot along its arch so that no two land on top of each other.

        Ribs of the two hands turn to meet an arch side by side, and some would arrive at almost
        the same place. Along each bay their feet are pushed apart until neighbours stand at
        least timber["lattice"]["land_gap_m"] clear. Returns plan shifts by rib ID.
        """
        b, roof = self.b, self.b.roof
        gap = self.cfg.get("land_gap_m", 0.04)
        bays, along_bay = defaultdict(list), {}
        for half in roof.halves:
            if half.side == "L":
                along_bay[half.bay] = (half.foot, half.direction)
        for rib_id, family, _, course, _ in self.ribs:
            if course.pier is None:
                samples, half, _ = roof.lay(course, None, square)
                origin, direction = along_bay[half.bay]
                foot = samples[0][0]
                bays[half.bay].append([(foot[0] - origin[0]) * direction[0] + (foot[1] - origin[1]) * direction[1], b.section[family][0], rib_id])
        shifts = {}
        for bay, feet in bays.items():
            feet.sort()
            start = [f[0] for f in feet]
            for _ in range(40):
                moved = False
                for one, other in zip(feet, feet[1:]):
                    short = (one[1] + other[1]) / 2.0 + gap - (other[0] - one[0])
                    if short > 1e-4:
                        one[0] -= short / 2.0
                        other[0] += short / 2.0
                        moved = True
                if not moved:
                    break
            direction = along_bay[bay][1]
            for (now, _, rib_id), was in zip(feet, start):
                if abs(now - was) > 1e-6:
                    shifts[rib_id] = ((now - was) * direction[0], (now - was) * direction[1])
        return shifts

    def _ring(self, ring_id: str, family: str, samples: list, nodes: tuple) -> None:
        """A ring lying in the roof surface, flush with the ribs it crosses."""
        self.b.member(ring_id, family, self.b.rid, closed_spline([p for p, _ in samples], [mul(n, -1.0) for _, n in samples]), nodes)

    def _crown(self, nodes: tuple) -> None:
        """The crown ring: a level collar seated on the heads of the ribs that reach the top."""
        b, roof = self.b, self.b.roof
        family = "crown" if "crown" in b.section else "ring"
        z = roof.top_z + b.section[family][1] / 2.0 - b.timber.get("crown", {}).get("seat_m", 0.03)
        circle = arc_path((roof.centre[0] + roof.top_radius, roof.centre[1], z), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), roof.top_radius, 2.0 * math.pi * roof.top_radius)
        b.member(f"{b.rid}.ring.top", family, b.rid, BezierPath(Anchor(a.co, a.handle_left, a.handle_right, UP) for a in circle.anchors), nodes)


# --- arches -------------------------------------------------------------------------------


def _shaft(height: float) -> tuple:
    return ((0.0, 0.0), (0.0, height / 3.0), (0.0, 2.0 * height / 3.0), (0.0, height))


class EdgeArches:
    """One arch per bay standing on the roof's edge, with the lattice housed into it and hoops inside it.

    timber["arches"]:
        hoops_m                  how far inside the arch each hoop runs, nearest first (may be empty)
        hoop_nudge_m             how far a hoop may be moved from that distance to pass clear of the ribs' own crossings
        hoop_sample_spacing_m    distance between the points a hoop is drawn through

    A hoop is one member from pier to pier: up from a leg at one pier, out to its distance inside
    the arch, over the bay's ridge and down to a leg at the other pier.
    """

    def __init__(self, b: Build, cfg: dict):
        self.b, self.cfg = b, cfg
        self.offsets = list(cfg.get("hoops_m", []))
        self.rim_width = b.section["arch"][0]
        b.rim_band = max(self.offsets, default=0.0) + (cfg.get("hoop_nudge_m", 0.12) if self.offsets else 0.0)

    def claims(self) -> list:
        roof, out = self.b.roof, []
        for half in roof.halves:
            n = _inward(roof, half)
            for k in range(len(self.offsets)):
                # where it comes from: a little way along the arch, the nearer hoop nearer to it
                origin = (half.foot[0] + half.direction[0] + n[0] * 0.05 * (k + 1), half.foot[1] + half.direction[1] + n[1] * 0.05 * (k + 1))
                out.append((half.pier, origin, f"{half.bay}.hoop{k}@{half.side}", "hoop"))
        return out

    def members(self) -> None:
        b, roof = self.b, self.b.roof
        shaft = b.shape["pier_height_m"]
        for half in roof.halves:
            bid, side = half.bay, half.side
            leg = (half.foot[0] + half.direction[0] * roof.pier_radius, half.foot[1] + half.direction[1] * roof.pier_radius, b.z0)
            arch_id = f"{bid}.arch.{side}"
            path = plane_path(leg, half.direction, [_shaft(shaft), tuple((d, z + shaft) for d, z in half.profile)])
            # The two legs at a pier are mitred into one trunk; the two halves of an arch are mitred at the apex.
            b.member(arch_id, "arch", bid, path, (arch_id + ".foot", half.pier + ".mitre", *b.landings[(bid, side)], bid + ".apex"), half.direction)
        if not self.offsets:
            return
        bays = defaultdict(list)
        for half in roof.halves:
            bays[half.bay].append(half)
        for pair in bays.values():
            crossings = self._rib_crossings(pair[0])
            for k, offset in enumerate(self.offsets):
                self._hoop(pair, k, self._clear_offset(pair[0], offset, crossings))

    def _inside(self, half, q) -> tuple[float, float]:
        """A plan point as (distance along the arch half from its pier, distance inside its plane)."""
        n = _inward(self.b.roof, half)
        vx, vy = q[0] - half.foot[0], q[1] - half.foot[1]
        return vx * half.direction[0] + vy * half.direction[1], vx * n[0] + vy * n[1]

    def _rib_crossings(self, half) -> list:
        """Where ribs of opposite hands cross each other in the band behind a bay's arch, in plan, as `_inside` gives them."""
        reach = max(self.offsets) + 0.6
        hands = {"cw": [], "ccw": []}
        for m in self.b.members:
            parts = m.id.split(".")
            if len(parts) == 4 and parts[2] in hands:
                line = [(a.co[0], a.co[1]) for a in m.path.anchors]
                near = [k for k, q in enumerate(line) if -0.3 < self._inside(half, q)[1] < reach]
                if near:
                    hands[parts[2]].append(line[max(near[0] - 1, 0) : near[-1] + 2])
        found = []
        for one in hands["cw"]:
            for other in hands["ccw"]:
                for p1, p2 in zip(one, one[1:]):
                    for q1, q2 in zip(other, other[1:]):
                        rx, ry, sx, sy = p2[0] - p1[0], p2[1] - p1[1], q2[0] - q1[0], q2[1] - q1[1]
                        det = rx * sy - ry * sx
                        if abs(det) > 1e-12:
                            t = ((q1[0] - p1[0]) * sy - (q1[1] - p1[1]) * sx) / det
                            u = ((q1[0] - p1[0]) * ry - (q1[1] - p1[1]) * rx) / det
                            if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
                                found.append(self._inside(half, (p1[0] + rx * t, p1[1] + ry * t)))
        return found

    def _clear_offset(self, half, offset: float, crossings: list) -> float:
        """The distance inside the arch, near `offset`, at which a hoop passes furthest from any crossing of two ribs."""
        nudge = self.cfg.get("hoop_nudge_m", 0.12)
        mine = [inside for along, inside in crossings if along > 1.0]
        if nudge <= 0.0 or not mine:
            return offset
        return max((offset + nudge * (k - 6) / 6 for k in range(13)), key=lambda d: (round(min(abs(inside - d) for inside in mine), 3), -abs(d - offset)))

    def _meets_ridge(self, half, offset: float) -> tuple:
        """Where the line `offset` inside an arch half crosses the vertical plane through the crown's axis and the apex."""
        roof = self.b.roof
        n, (dx, dy) = _inward(roof, half), half.direction[:2]
        wx, wy = half.apex[0] - roof.centre[0], half.apex[1] - roof.centre[1]
        ox, oy = half.foot[0] + n[0] * offset, half.foot[1] + n[1] * offset
        rx, ry = roof.centre[0] - ox, roof.centre[1] - oy
        a = (ry * wx - rx * wy) / (dy * wx - dx * wy)
        return (ox + dx * a, oy + dy * a)

    def _rise(self, half, hoop_id: str, offset: float, end: tuple) -> list:
        """Plan points of one half of a hoop: from its leg at the pier, out to its distance inside the arch, on to the bay's ridge."""
        roof, spacing = self.b.roof, self.cfg.get("hoop_sample_spacing_m", 0.45)
        (px, py), (dx, dy), n = half.foot, half.direction[:2], _inward(roof, half)
        slot = self.b.place[f"{hoop_id}@{half.side}"]
        a_slot = (slot[0] - px) * dx + (slot[1] - py) * dy
        a_end = (end[0] - px) * dx + (end[1] - py) * dy
        a_out = min(a_slot + max(1.0, 2.5 * offset), 0.8 * a_end)  # where it has reached its distance from the arch
        out = (px + dx * a_out + n[0] * offset, py + dy * a_out + n[1] * offset)
        reach = math.hypot(slot[0] - px, slot[1] - py)
        run, onward = math.hypot(out[0] - slot[0], out[1] - slot[1]), math.hypot(end[0] - out[0], end[1] - out[1])
        # leaves its leg straight up the pier's funnel, arrives running along the arch
        c1 = tuple(slot[i] + (slot[i] - half.foot[i]) / reach * 0.4 * run for i in (0, 1))
        c2 = tuple(out[i] - (end[i] - out[i]) / onward * 0.4 * run for i in (0, 1))
        plan, pieces = [], max(3, round(run / spacing))
        for i in range(pieces + 1):
            t = i / pieces
            u = 1.0 - t
            plan.append(tuple(u**3 * slot[j] + 3 * u * u * t * c1[j] + 3 * u * t * t * c2[j] + t**3 * out[j] for j in (0, 1)))
        pieces = max(1, round(onward / spacing))
        return plan + [tuple(out[j] + (end[j] - out[j]) * i / pieces for j in (0, 1)) for i in range(1, pieces + 1)]

    def _hoop(self, pair: list, k: int, offset: float) -> None:
        b, roof = self.b, self.b.roof
        hoop_id = f"{pair[0].bay}.hoop{k}"
        ends = [self._meets_ridge(half, offset) for half in pair]
        ridge = tuple(sum(e[i] for e in ends) / len(ends) for i in (0, 1))
        left, right = (self._rise(half, hoop_id, offset, ridge) for half in pair)
        samples = [roof.drape(q) for q in left + right[-2::-1]]
        samples = roof.stand(samples, pair[0].foot, b.knee)
        samples = roof.stand(samples[::-1], pair[1].foot, b.knee)[::-1]
        b.member(hoop_id, "hoop", pair[0].bay, b.in_roof(samples), (hoop_id + ".foot.L", hoop_id + ".foot.R"))


class PairedArches:
    """The earlier arrangement: a light arch on the roof's edge that the lattice lands on, and a
    heavier arch standing proud of it.

    timber["arches"]:
        reveal_m    how far the outer arch stands outside the inner one
        crest_m     how far its apex rises above the inner one's
    """

    def __init__(self, b: Build, cfg: dict):
        self.b, self.cfg = b, cfg
        self.rim_width = b.section["inner"][0]

    def claims(self) -> list:
        return []

    def members(self) -> None:
        b, roof = self.b, self.b.roof
        shaft, reveal, crest = b.shape["pier_height_m"], self.cfg["reveal_m"], self.cfg["crest_m"]
        for half in roof.halves:
            bid, side, n = half.bay, half.side, _inward(roof, half)
            leg = (half.foot[0] + half.direction[0] * roof.pier_radius, half.foot[1] + half.direction[1] * roof.pier_radius)
            rise = half.apex[2] - b.z0 - shaft
            inner_id = f"{bid}.inner.{side}"
            inner = [_shaft(shaft), tuple((d, z + shaft) for d, z in half.profile)]
            b.member(inner_id, "inner", bid, plane_path((leg[0], leg[1], b.z0), half.direction, inner), (inner_id + ".foot", half.pier + ".mitre", *b.landings[(bid, side)], bid + ".inner.apex"), half.direction)
            proud = (leg[0] - n[0] * reveal, leg[1] - n[1] * reveal, b.z0)
            outer = [_shaft(shaft), tuple((d, z + shaft) for d, z in arch_profile(half.span - roof.pier_radius, rise + crest, b.shape))]
            b.member(f"{bid}.arch.{side}", "arch", bid, plane_path(proud, half.direction, outer), (f"{bid}.arch.{side}.foot", bid + ".apex"), half.direction)


class Nothing:
    """Builds no members: lets the arches or the lattice be looked at alone."""

    rim_width = 0.0

    def __init__(self, b: Build, cfg: dict):
        pass

    def claims(self) -> list:
        return []

    def members(self) -> None:
        pass


ARCHES = {"edge": EdgeArches, "paired": PairedArches, "none": Nothing}
LATTICES = {"spiral": SpiralLattice, "none": Nothing}


def build_timber(room: dict, timber: dict) -> list[Member]:
    """The primary members of one room, in a fixed order."""
    for key, registry in (("lattice", LATTICES), ("arches", ARCHES)):
        if timber[key]["type"] not in registry:
            raise DesignError(f"timber.{key}.type {timber[key]['type']!r} is not one of {sorted(registry)}")
    b = Build(room, timber)
    arches = ARCHES[timber["arches"]["type"]](b, timber["arches"])
    # a rib's foot is let into the inner face of the arch by the housing depth
    b.rim_inset = max(0.0, arches.rim_width / 2.0 - timber.get("joints", {}).get("housing_depth_m", 0.05))
    lattice = LATTICES[timber["lattice"]["type"]](b, timber["lattice"])
    b.place = pier_places(b, lattice.claims() + arches.claims(), arches.rim_width)
    lattice.members()  # first: the arches need to know what lands on them
    arches.members()
    return b.members


# --- diagnostics -----------------------------------------------------------------------


def clearances(members: list[Member], spacing: float = 0.1, within: float = 0.06) -> dict:
    """Closest approach of every pair of members that are not jointed at a shared node.

    Each member is taken as a chain of short boxes, one per sampled station. Two boxes are tested
    on the line between their centres and on the three axes of each: the gap is the widest
    separation found. A positive gap proves the members are apart; a negative gap means they
    overlap, and may be slightly pessimistic since the edge-to-edge axes are not tested.

    Overlaps between two lattice members (ribs, hoops and rings) are `notches`: they are meant to
    cross flush, each cut to take the other. Any other overlap is a `collision`. `close` lists the
    remaining pairs that pass within `within` metres of each other.
    """
    stations = [m.path.stations(spacing) for m in members]
    at_node = defaultdict(set)
    for i, m in enumerate(members):
        for node in m.nodes:
            at_node[node].add(i)
    jointed = {(i, j) for group in at_node.values() for i in group for j in group if i < j}

    cell = 0.6

    def key(p):
        return (math.floor(p[0] / cell), math.floor(p[1] / cell), math.floor(p[2] / cell))

    grid = defaultdict(list)
    for i, along in enumerate(stations):
        for k, s in enumerate(along):
            grid[key(s.point)].append((i, k))

    def extent(m: Member, s, u) -> float:
        return abs(dot(u, s.width_axis)) * m.width / 2 + abs(dot(u, s.depth_axis)) * m.depth / 2 + abs(dot(u, s.tangent)) * spacing / 2

    closest = {}
    for i, along in enumerate(stations):
        for s in along:
            gx, gy, gz = key(s.point)
            for cx in (gx - 1, gx, gx + 1):
                for cy in (gy - 1, gy, gy + 1):
                    for cz in (gz - 1, gz, gz + 1):
                        for j, l in grid.get((cx, cy, cz), ()):
                            if j <= i or (i, j) in jointed:
                                continue
                            o = stations[j][l]
                            v = sub(o.point, s.point)
                            distance = norm(v)
                            if distance > cell:
                                continue
                            if distance < 1e-9:
                                gap = -max(members[i].depth, members[j].depth)
                            else:
                                u = (v[0] / distance, v[1] / distance, v[2] / distance)
                                gap = distance - extent(members[i], s, u) - extent(members[j], o, u)
                                if gap < within:  # look for a better separating axis among the boxes' own
                                    for axis in (s.width_axis, s.depth_axis, s.tangent, o.width_axis, o.depth_axis, o.tangent):
                                        gap = max(gap, abs(dot(v, axis)) - extent(members[i], s, axis) - extent(members[j], o, axis))
                            if (i, j) not in closest or gap < closest[(i, j)][0]:
                                closest[(i, j)] = (gap, s.point, o.point)

    report = {"jointed_pairs": len(jointed), "collisions": [], "notches": [], "close": []}
    for (i, j), (gap, p, q) in sorted(closest.items(), key=lambda item: (item[1][0], members[item[0][0]].id, members[item[0][1]].id)):
        if gap >= within:
            continue
        pair = {"a": members[i].id, "b": members[j].id, "gap_m": round(gap, 4), "at_m": [round((p[k] + q[k]) / 2, 3) for k in range(3)]}
        if gap >= -0.002:
            report["close"].append(pair)
        elif members[i].family in LATTICE and members[j].family in LATTICE:
            report["notches"].append(pair)
        else:
            report["collisions"].append(pair)
    return report


def _out_of_plane(m: Member) -> float:
    """How far a member's centreline strays from the plane through its ends and its middle."""
    stations = m.path.stations(0.1)
    a = stations[0].point
    normal = cross(sub(stations[len(stations) // 2].point, a), sub(stations[-1].point, a))
    if norm(normal) < 1e-9:
        return 0.0
    normal = unit(normal)
    return max(abs(dot(sub(s.point, a), normal)) for s in stations)


def schedule(members: list[Member], timber: dict, report: dict, joints=()) -> list[dict]:
    """One row per member: identity, end nodes, section, length, tightest bend, volume, cuts, neighbours.

    Geometric quantities only. `review` marks members whose tightest radius falls under
    timber["bend_radius_review_m"], a provisional threshold that is not a supplier's limit.
    Given the room's `joints` (see bower/joints.py), each row counts the cuts made in that member.
    """
    cuts, flagged = defaultdict(lambda: defaultdict(int)), defaultdict(int)
    for joint in joints:
        for cut in joint.cuts:
            cuts[cut.member][cut.operation + ("_" + cut.face if cut.operation == "lap" else "")] += 1
        if joint.review:
            for member_id in set(joint.members):
                flagged[member_id] += 1
    tables = {kind: defaultdict(list) for kind in ("collisions", "notches", "close")}
    for kind, table in tables.items():
        for pair in report[kind]:
            table[pair["a"]].append(pair["b"])
            table[pair["b"]].append(pair["a"])
    rows = []
    for m in members:
        radius, at = m.path.min_bend_radius()
        tight = radius is not None and radius < timber["bend_radius_review_m"]
        stray = _out_of_plane(m)
        rows.append(
            {
                "id": m.id,
                "family": m.family,
                "parent": m.parent,
                "start_node": m.nodes[0],
                "end_node": m.nodes[-1],
                "width_m": m.width,
                "depth_m": m.depth,
                "length_m": round(m.path.length, 3),
                "min_bend_radius_m": "" if radius is None else round(radius, 2),
                "min_radius_at_m": round(at, 2),
                "radius_over_depth": "" if radius is None else round(radius / m.depth, 1),
                "volume_m3": round(m.width * m.depth * m.path.length, 4),
                "planar": "yes" if stray < 0.001 else f"no ({stray:.2f} m out of plane)",
                "laps_cut_on_outer_face": cuts[m.id]["lap_outer"],
                "laps_cut_on_inner_face": cuts[m.id]["lap_inner"],
                "housings": cuts[m.id]["housing"],
                "other_cuts": sum(n for op, n in cuts[m.id].items() if not op.startswith("lap") and op != "housing"),
                "joints_to_review": flagged[m.id],
                "review": "tight radius" if tight else "",
                "collides_with": " ".join(sorted(tables["collisions"][m.id])),
                "passes_close_to": " ".join(sorted(tables["close"][m.id])),
            }
        )
    return rows
