"""Level B: a room's roof as one smooth surface between its arches and its crown.

The roof is described by two coordinates: a bearing round the crown's axis, and
how far along the meridian at that bearing a point lies, from the arch (0) to
the crown ring (1). Three things shape it:

    rim      the pointed arches, pier to apex to pier. At every bearing the roof
             starts on the arch that faces that way.
    canopy   from the arch the roof rises to the canopy and runs across it to the
             foot of the lantern. Near a pier, where it starts low on the arch
             leg, it climbs steeply at first and levels out within `fan_radius_m`.
             Within `pier_funnel_m` of a pier the roof is a round funnel about
             the pier's own axis, so each pier opens upward like a tree and
             there is no sharp valley over it.
    lantern  inside `lantern_radius_m` the roof turns up and narrows to the crown
             ring. The lantern is a surface of revolution about the crown's axis.

The roof over a bay depends on that bay's arch, on the arches of the bays either
side (it eases toward their apex heights, and shares a pier funnel with each) and
on the crown. Editing one bay reshapes its neighbours and leaves the rest exactly
as they were.

The surface is meshed as one patch per half-bay, bounded by named curves that are
each built once: the arch half below, the crown arc above, the meridian over the
pier (`<pier>.groin`) on one side and the meridian through the apex
(`<bay>.ridge`) on the other. Neighbouring patches name the same meridian and the
mesh gives them the same vertices along it, so the surface is continuous along
whole curves by construction. The roof creases gently along those meridians near
the arches and is smooth elsewhere.

Shape parameters (room["shape"]):
    pier_height_m            height of the pier, floor to spring
    pier_radius_m            how far from the pier point each arch leg's centreline stands
    arch_shoulder            vertical run of the arch above the spring, as a fraction of its rise
    arch_point_deg           slope of the arch where it meets the apex (0 would be a round arch)
    arch_reach               how far back from the apex that slope is held, as a fraction of the half-span
    fan_radius_m             how far from an arch the roof takes to reach the canopy
    pier_funnel_m            radius of the round funnel in which the roof gathers onto each pier
    ridge_soften             how quickly the point of an arch is rounded off going in from it (width rounded per metre in)
    lantern_radius_m         radius of the ring where the canopy turns up into the lantern
    lantern_base_height_m    height of that ring
The canopy meets each arch at its apex height. The crown's radius and height are
the lantern's top ring.

Pure Python (no bpy).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass

from .centreline import Anchor, BezierPath, Vec, add, arc_path, cross, dot, mul, norm, plane_path, sub, unit
from .topology import apex_point

CREASE_KINDS = ("groin", "ridge")
KAPPA = 0.5523  # Bezier handle length that makes a cubic follow a quarter ellipse
CANOPY_SHARE = 0.5  # share of a meridian's parameter spent crossing the canopy; the rest climbs the lantern
TWO_PI = 2.0 * math.pi


@dataclass(frozen=True)
class Edge:
    """One boundary curve, running between two named nodes."""

    id: str
    kind: str  # pier | groin | ridge | arch | crown
    start: str
    end: str
    path: BezierPath


@dataclass(frozen=True)
class Patch:
    """One surface patch, named by the boundary curves around it."""

    id: str
    bay: str
    kind: str
    edges: tuple


@dataclass(frozen=True)
class Envelope:
    room_id: str
    nodes: dict  # node ID -> point
    edges: dict  # edge ID -> Edge
    patches: dict  # patch ID -> Patch
    verts: list
    faces: list
    face_patch: list  # patch ID of each face
    edge_verts: dict  # edge ID -> vertex indices along it, ends included


@dataclass(frozen=True)
class Course:
    """The free course of a lattice rib over the canopy, before it is given a foot."""

    head: tuple  # (point, normal) samples from its upper end out to where its canopy run begins
    at: object  # canopy radius -> (bearing, plan point)
    start: float  # radius at which its canopy run begins
    end: float  # radius at which it meets the arches
    step: float  # radial distance between samples
    trail: tuple  # (radius, plan point) at close intervals along the canopy run
    pier: str | None  # the pier it passes within gathering distance of, if any
    passes: float  # how close it passes to that pier
    turn: int  # index into `trail` where a rib drawn to the pier leaves its free course
    inset: float  # how far short of the arch's plane it stops


@dataclass(frozen=True)
class Half:
    """One half of a bay's arch: the roof's rim between a pier and the bay's apex."""

    bay: str
    side: str  # L starts at the bay's `from` pier, R at its `to` pier
    pier: str
    foot: tuple  # the pier point, in plan
    direction: Vec  # horizontal unit vector from the pier toward the apex
    span: float  # plan distance from the pier to the apex
    profile: tuple  # the arch above its spring, as (distance from the leg, height above the spring)
    apex: Vec
    lo: float  # bearings of its two ends round the crown's axis, lo < hi
    hi: float


# --- profiles and small geometry -------------------------------------------------------


def arch_profile(span: float, rise: float, shape: dict) -> tuple:
    """A half-arch in its own vertical plane, as (distance toward the apex, height above the spring).

    It meets the apex at `arch_point_deg`, or more steeply where the bay is narrow for its
    height: a tall narrow arch becomes a sharper lancet instead of turning tightly at the top.
    """
    point = math.tan(max(math.radians(shape["arch_point_deg"]), math.pi / 2.0 - 2.0 * math.atan2(span, rise)))
    shoulder = shape["arch_shoulder"] * rise
    reach = min(shape["arch_reach"] * span, 0.9 * (rise - shoulder) / point)  # keeps the arch rising
    return ((0.0, 0.0), (0.0, shoulder), (span - reach, rise - reach * point), (span, rise))


def lantern_profile(shape: dict, crown: dict) -> tuple:
    """The lantern, as (distance inward from its base ring, height above it): level at the base, upright at the top."""
    a = shape["lantern_radius_m"] - crown["radius_m"]
    b = crown["height_m"] - shape["lantern_base_height_m"]
    return ((0.0, 0.0), (KAPPA * a, 0.0), (a, b * (1.0 - KAPPA)), (a, b))


def cubic_at(cubic, t: float):
    """Point and derivative of a plane-coordinate cubic at parameter t."""
    u = 1.0 - t
    point = tuple(u**3 * cubic[0][k] + 3 * u * u * t * cubic[1][k] + 3 * u * t * t * cubic[2][k] + t**3 * cubic[3][k] for k in (0, 1))
    slope = tuple(
        3 * u * u * (cubic[1][k] - cubic[0][k]) + 6 * u * t * (cubic[2][k] - cubic[1][k]) + 3 * t * t * (cubic[3][k] - cubic[2][k])
        for k in (0, 1)
    )
    return point, slope


def cubic_at_distance(cubic, distance: float):
    """Point and derivative of a profile cubic where it has travelled `distance` horizontally."""
    lo, hi = 0.0, 1.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if cubic_at(cubic, mid)[0][0] < distance:
            lo = mid
        else:
            hi = mid
    return cubic_at(cubic, 0.5 * (lo + hi))


def spline(points, depth_axes=None) -> BezierPath:
    """A smooth path through `points`: at each one it runs parallel to the chord between its neighbours."""
    last = len(points) - 1
    anchors = []
    for i, p in enumerate(points):
        along = unit(sub(points[min(i + 1, last)], points[max(i - 1, 0)]))
        before = norm(sub(p, points[i - 1])) / 3.0 if i else 0.0
        after = norm(sub(points[i + 1], p)) / 3.0 if i < last else 0.0
        anchors.append(Anchor(p, sub(p, mul(along, before)), add(p, mul(along, after)), depth_axes[i] if depth_axes else None))
    return BezierPath(anchors)


def closed_spline(points, depth_axes=None) -> BezierPath:
    """A smooth closed path through `points`, ending where it starts."""
    count, anchors = len(points), []
    for i in range(count + 1):
        p, before, after = points[i % count], points[(i - 1) % count], points[(i + 1) % count]
        along = unit(sub(after, before))
        anchors.append(Anchor(p, sub(p, mul(along, norm(sub(p, before)) / 3.0)), add(p, mul(along, norm(sub(after, p)) / 3.0)), depth_axes[i % count] if depth_axes else None))
    return BezierPath(anchors)


def _line(p0: Vec, p1: Vec) -> BezierPath:
    third = mul(sub(p1, p0), 1.0 / 3.0)
    return BezierPath([Anchor(p0, p0, add(p0, third)), Anchor(p1, sub(p1, third), p1)])


# --- the roof surface --------------------------------------------------------------------


class Roof:
    """The roof of one room, evaluated at a bearing round the crown's axis and a position along the meridian."""

    def __init__(self, room: dict):
        shape, crown = room["shape"], room["crown"]
        self.floor_z = room["floor_z_m"]
        self.centre = tuple(crown["centre_m"])
        self.top_radius, self.top_z = crown["radius_m"], self.floor_z + crown["height_m"]
        self.base_radius, self.base_z = shape["lantern_radius_m"], self.floor_z + shape["lantern_base_height_m"]
        self.spring_z = self.floor_z + shape["pier_height_m"]
        self.pier_radius, self.fan_radius, self.funnel = shape["pier_radius_m"], shape["fan_radius_m"], shape["pier_funnel_m"]
        self.lantern = lantern_profile(shape, crown)
        self.ridge_soften = shape.get("ridge_soften", 1.5)
        self._swings = {}
        piers = {p["id"]: p["position_m"] for p in room["piers"]}
        cx, cy = self.centre

        self.halves, self._apexes = [], []
        for bay in room["bays"]:
            apex = apex_point(room, bay)
            at_apex = math.atan2(apex[1] - cy, apex[0] - cx)
            self._apexes.append((at_apex % TWO_PI, apex[2]))
            for side, pid in (("L", bay["from"]), ("R", bay["to"])):
                foot = piers[pid]
                dx, dy = apex[0] - foot[0], apex[1] - foot[1]
                span = math.hypot(dx, dy)
                at_pier = math.atan2(foot[1] - cy, foot[0] - cx)
                lo, hi = (at_pier, at_apex) if side == "L" else (at_apex, at_pier)
                profile = arch_profile(span - self.pier_radius, apex[2] - self.spring_z, shape)
                self.halves.append(Half(bay["id"], side, pid, tuple(foot), (dx / span, dy / span, 0.0), span, profile, apex, lo, lo + (hi - lo) % TWO_PI))
        self._apexes.sort()
        self.piers = {pid: (tuple(xy), [h for h in self.halves if h.pier == pid]) for pid, xy in piers.items()}

        # How far a rib held at a fixed angle to the meridian turns round the lantern: the integral of
        # (distance climbed) / (radius) from each height to the top ring, tabulated up the profile.
        steps = 120
        self._turn, self.climb, self._per_step = [0.0] * (steps + 1), 0.0, [0.0] * steps
        for i in range(steps, 0, -1):
            (d0, z0), (d1, z1) = cubic_at(self.lantern, (i - 1) / steps)[0], cubic_at(self.lantern, i / steps)[0]
            length = math.hypot(d1 - d0, z1 - z0)
            self.climb += length
            self._per_step[i - 1] = length / (self.base_radius - 0.5 * (d0 + d1))  # turn of a 45 degree rib over this step
            self._turn[i - 1] = self._turn[i] + self._per_step[i - 1]
        self._windings = {}

    # -- the rim: the arches -------------------------------------------------------------

    def half_at(self, bearing: float) -> Half:
        for half in self.halves:
            if (bearing - half.lo) % TWO_PI <= half.hi - half.lo:
                return half
        return min(self.halves, key=lambda h: min((bearing - h.lo) % TWO_PI, (h.hi - bearing) % TWO_PI))

    def rim(self, bearing: float):
        """Where the roof starts at `bearing`: its distance from the crown's axis, its height, the arch
        half it stands on and how far along that half (from the pier) it is."""
        half = self.half_at(bearing)
        ux, uy = math.cos(bearing), math.sin(bearing)
        wx, wy = half.foot[0] - self.centre[0], half.foot[1] - self.centre[1]
        dx, dy = half.direction[0], half.direction[1]
        facing = ux * dy - uy * dx
        radius = (wx * dy - wy * dx) / facing
        along = min(max((wx * uy - wy * ux) / facing, 0.0), half.span)
        if along <= self.pier_radius:
            return radius, self.spring_z, half, along
        return radius, self.spring_z + cubic_at_distance(half.profile, along - self.pier_radius)[0][1], half, along

    def eave(self, bearing: float) -> float:
        """Height at which the canopy meets the arches at `bearing`: each arch's apex height, eased between bays."""
        theta = bearing % TWO_PI
        ring = self._apexes + [(self._apexes[0][0] + TWO_PI, self._apexes[0][1])]
        if theta < ring[0][0]:
            theta += TWO_PI
        for (b0, z0), (b1, z1) in zip(ring, ring[1:]):
            if b0 <= theta <= b1:
                w = (theta - b0) / (b1 - b0)
                return z0 + (z1 - z0) * (1.0 - math.cos(math.pi * w)) / 2.0
        return ring[0][1]

    # -- the canopy and the lantern --------------------------------------------------------

    def height(self, bearing: float, radius: float) -> float:
        """Height of the roof outside the lantern, `radius` from the crown's axis."""
        rim_radius, _, half, along = self.rim(bearing)
        edge = self.eave(bearing)
        run = max(rim_radius - self.base_radius, 1e-6)
        level = self.base_z + (edge - self.base_z) * min(max((radius - self.base_radius) / run, 0.0), 1.0) ** 2  # level where it meets the lantern
        reach = min(self.fan_radius, 0.85 * run)
        inward = max(rim_radius - radius, 0.0)
        # The roof drops toward the arch it starts from. Further in, it answers to the arch a little
        # further from the pier, so the low part of an arch leg is felt only close to that leg and
        # leaves no trench along the meridian over the pier.
        seen = min(max(along, self.pier_radius + 0.6 * inward), half.span)
        rim_z = self.spring_z + (cubic_at_distance(half.profile, seen - self.pier_radius)[0][1] if seen > self.pier_radius else 0.0)
        # The arch comes to a point at the apex. Away from the arch that point is rounded off, over a
        # width that grows with the distance from it, so the crease it leaves along the bay's ridge fades.
        soft = min(self.ridge_soften * inward, 0.8 * (half.span - self.pier_radius))
        short = half.span - seen
        if short < soft:
            (d2, z2), (d3, z3) = half.profile[2], half.profile[3]
            rim_z -= (z3 - z2) / (d3 - d2) * ((short * short + soft * soft) / (2.0 * soft) - short)
        z = level - (edge - rim_z) * (1.0 - min(inward / reach, 1.0)) ** 2
        # Close to a pier the roof is a funnel about the pier's own axis: its height there depends
        # on the distance from the pier, following the legs of the two arches that stand on it.
        x, y = self.centre[0] + radius * math.cos(bearing), self.centre[1] + radius * math.sin(bearing)
        for pier_xy, halves in self.piers.values():
            away = math.hypot(x - pier_xy[0], y - pier_xy[1])
            if away < self.funnel:
                legs = [cubic_at_distance(h.profile, min(away - self.pier_radius, h.span - self.pier_radius))[0][1] if away > self.pier_radius else 0.0 for h in halves]
                w = 1.0 - away / self.funnel
                w = w * w * (3.0 - 2.0 * w)
                return z + (self.spring_z + sum(legs) / len(legs) - z) * w
        return z

    def on_canopy(self, bearing: float, radius: float):
        """A point of the roof outside the lantern, and the upward normal there."""

        def at(b, r):
            return (self.centre[0] + r * math.cos(b), self.centre[1] + r * math.sin(b), self.height(b, r))

        point = at(bearing, radius)
        across = sub(at(bearing + 0.004, radius), at(bearing - 0.004, radius))
        inward = sub(at(bearing, radius - 0.02), at(bearing, radius + 0.02))
        normal = unit(cross(inward, across))
        return point, normal if normal[2] > 0 else mul(normal, -1.0)

    def on_lantern(self, bearing: float, lam: float):
        """A point of the lantern, `lam` of the way from its base ring to the top ring, and the outward normal there."""
        (d, z), (dd, dz) = cubic_at(self.lantern, lam)
        radius, c, s = self.base_radius - d, math.cos(bearing), math.sin(bearing)
        return (self.centre[0] + radius * c, self.centre[1] + radius * s, self.base_z + z), unit((c * dz, s * dz, dd))

    def meridian(self, bearing: float, t: float) -> Vec:
        """The roof point `t` of the way along the meridian at `bearing`, from the arch (0) to the crown ring (1)."""
        if t <= CANOPY_SHARE:
            rim_radius = self.rim(bearing)[0]
            return self.on_canopy(bearing, rim_radius + (self.base_radius - rim_radius) * t / CANOPY_SHARE)[0]
        return self.on_lantern(bearing, (t - CANOPY_SHARE) / (1.0 - CANOPY_SHARE))[0]

    # -- ribs -------------------------------------------------------------------------------

    def turn(self, lam: float) -> float:
        """Angle a rib at 45 degrees to the meridian turns between lantern parameter `lam` and the top ring."""
        x = min(max(lam, 0.0), 1.0) * (len(self._turn) - 1)
        i = min(int(x), len(self._turn) - 2)
        return self._turn[i] + (self._turn[i + 1] - self._turn[i]) * (x - i)

    def winding(self, lean: float, lean_top: float | None = None):
        """How far round the crown's axis a rib turns between a lantern parameter and the top ring, as a function.

        The rib leans `lean` from the meridian at the lantern's foot. With `lean_top` its lean
        changes evenly on the way up to that angle at the top ring, so the ribs stand up
        straighter as the lantern narrows and the loops between them grow taller.
        """
        if lean_top is None or abs(lean_top - lean) < 1e-9:
            slope = math.tan(lean)
            return lambda lam: slope * self.turn(lam)
        if (lean, lean_top) not in self._windings:
            steps = len(self._per_step)
            table = [0.0] * (steps + 1)
            for i in range(steps, 0, -1):
                table[i - 1] = table[i] + math.tan(lean + (lean_top - lean) * (i - 0.5) / steps) * self._per_step[i - 1]
            self._windings[(lean, lean_top)] = table
        table = self._windings[(lean, lean_top)]

        def wound(lam: float) -> float:
            x = min(max(lam, 0.0), 1.0) * (len(table) - 1)
            i = min(int(x), len(table) - 2)
            return table[i] + (table[i + 1] - table[i]) * (x - i)

        return wound

    def drape(self, xy):
        """The roof point above a plan position outside the lantern, and the upward normal there."""
        dx, dy = xy[0] - self.centre[0], xy[1] - self.centre[1]
        return self.on_canopy(math.atan2(dy, dx), math.hypot(dx, dy))

    def _swing(self, lean: float, lean_rim: float | None):
        """How far round the crown's axis a rib has turned by each canopy radius, as a function.

        With one lean the rib is a spiral of constant angle. With `lean_rim` its angle to the
        meridians changes evenly from `lean` at the lantern to `lean_rim` at the piers' distance.
        """
        if lean_rim is None or abs(lean_rim - lean) < 1e-9:
            slope = math.tan(lean)
            return lambda radius: slope * math.log(radius / self.base_radius)
        if (lean, lean_rim) not in self._swings:
            reach = sum(math.hypot(xy[0] - self.centre[0], xy[1] - self.centre[1]) for xy, _ in self.piers.values()) / len(self.piers)
            dr, table, radius = 0.02, [0.0], self.base_radius
            while radius < reach + 4.0:
                mid = radius + dr / 2.0
                angle = lean + (lean_rim - lean) * min((mid - self.base_radius) / (reach - self.base_radius), 1.0)
                table.append(table[-1] + math.tan(angle) * dr / mid)
                radius += dr
            self._swings[(lean, lean_rim)] = (dr, table)
        dr, table = self._swings[(lean, lean_rim)]

        def swing(radius: float) -> float:
            x = min(max((radius - self.base_radius) / dr, 0.0), len(table) - 1.001)
            i = int(x)
            return table[i] + (table[i + 1] - table[i]) * (x - i)

        return swing

    def trace(self, arrival: float, sense: float, lean: float, spacing: float, inset: float, gather: float, top: float = 1.0, start_radius: float | None = None, lean_rim: float | None = None, lean_top: float | None = None) -> Course:
        """The free course of a rib that holds the angle `lean` to the roof's meridians.

        It is laid out from the top ring, which it reaches (or would reach) at the bearing
        `arrival`, outward and down until it meets an arch; `sense` is +1 for a rib that turns
        counter-clockwise as it climbs. With `top` below 1 it follows the same course but starts
        that far up the lantern; with `start_radius` it starts on the canopy, that far from the
        crown's axis. `lean_top` and `lean_rim` let its lean change up the lantern and out across
        the canopy. It stops `inset` short of the arch's plane. The course records which pier, if
        any, it passes within `gather` of.
        """
        wound = self.winding(lean, lean_top)
        at_foot = arrival - sense * wound(0.0)
        swing = self._swing(lean, lean_rim)

        def at(radius: float):
            bearing = at_foot - sense * swing(radius)
            return bearing, (self.centre[0] + radius * math.cos(bearing), self.centre[1] + radius * math.sin(bearing))

        if start_radius is None:
            steps = max(1, round(top * self.climb / (spacing * math.cos(lean))))
            head = tuple(self.on_lantern(arrival - sense * wound(top * (1.0 - i / steps)), top * (1.0 - i / steps)) for i in range(steps + 1))
            start = self.base_radius
        else:
            start = start_radius
            head = (self.on_canopy(at(start)[0], start),)

        def beyond(radius: float) -> float:
            return radius - (self.rim(at(radius)[0])[0] - inset)

        # Follow the course outward in small steps to see where it ends and what it passes.
        fine, radius, trail = 0.05, start, []
        while beyond(radius) < 0.0:
            trail.append((radius, at(radius)[1]))
            radius += fine
        if len(trail) < 3:
            raise ValueError(f"a rib starting {start:.2f} m from the crown's axis has no room to run before the arches")
        lo, hi = radius - fine, radius
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if beyond(mid) < 0.0 else (lo, mid)
        drawn_to, passes = None, gather
        for pid, (pier_xy, _) in self.piers.items():
            nearest = min(math.hypot(q[0] - pier_xy[0], q[1] - pier_xy[1]) for _, q in trail)
            if nearest < passes:
                drawn_to, passes = pid, nearest
        turn = 0
        if drawn_to is not None:
            pier_xy = self.piers[drawn_to][0]
            turn = next((k for k, (_, q) in enumerate(trail) if math.hypot(q[0] - pier_xy[0], q[1] - pier_xy[1]) < 2.0 * self.funnel), len(trail) - 1)
            turn = min(turn, len(trail) - 2)
        return Course(head, at, start, lo, spacing * math.cos(lean), tuple(trail), drawn_to, passes, turn, inset)

    def _squared(self, course: Course, within: float, shift=(0.0, 0.0)):
        """The last stretch of a free rib, turned to meet its arch squarely.

        Inside `within` of the arch's plane the rib leaves its course on an arc that arrives
        square to the arch. `shift` moves its foot along the arch from where that arc would
        land, to keep it clear of a neighbour. Returns the index into the course's trail where
        it leaves, and the plan points of the arc from there to its foot; None where the rib
        cannot be squared (it runs along the arch, or would land in a pier or on another bay).
        """
        _, _, half, _ = self.rim(course.at(course.end)[0])
        dx, dy = half.direction[0], half.direction[1]
        nx, ny = (dy, -dx) if dy * (half.foot[0] - self.centre[0]) - dx * (half.foot[1] - self.centre[1]) > 0 else (-dy, dx)  # outward

        def inside(q) -> float:
            return -((q[0] - half.foot[0]) * nx + (q[1] - half.foot[1]) * ny)

        trail = course.trail
        k = next((i for i in range(len(trail) - 2, -1, -1) if inside(trail[i][1]) >= within), 0)
        q0, q1 = trail[k][1], trail[k + 1][1]
        to_go = inside(q0) - course.inset
        if to_go < 0.4 * within:
            return None
        length = math.hypot(q1[0] - q0[0], q1[1] - q0[1])
        hx, hy = (q1[0] - q0[0]) / length, (q1[1] - q0[1]) / length
        facing = hx * nx + hy * ny  # cosine of the angle between its heading and the square to the arch
        if facing < 0.2:
            return None
        tangent = to_go / (1.0 + facing)  # both tangents of the arc, from its ends to where they meet
        foot = (q0[0] + (hx + nx) * tangent + shift[0], q0[1] + (hy + ny) * tangent + shift[1])
        _, _, landed, along = self.rim(math.atan2(foot[1] - self.centre[1], foot[0] - self.centre[0]))
        if landed.bay != half.bay or along < 0.6:
            return None
        # a cubic that leaves along the rib's heading and arrives along the square to the arch
        c1 = (q0[0] + hx * tangent * 2.0 / 3.0, q0[1] + hy * tangent * 2.0 / 3.0)
        c2 = (foot[0] - nx * tangent * 2.0 / 3.0, foot[1] - ny * tangent * 2.0 / 3.0)
        pieces = max(2, round(2.0 * tangent / course.step))
        arc = []
        for i in range(1, pieces + 1):
            t = i / pieces
            u = 1.0 - t
            arc.append(tuple(u**3 * q0[j] + 3.0 * u * u * t * c1[j] + 3.0 * u * t * t * c2[j] + t**3 * foot[j] for j in (0, 1)))
        return k, arc

    def lay(self, course: Course, slot=None, square: float = 0.0, shift=(0.0, 0.0)):
        """A traced rib's (point, normal) samples from its foot to its upper end, with the arch half
        it lands on and how far along that half it lands.

        A rib that passes no pier runs its free course to the arch; with `square`, it turns within
        that distance of the arch to meet it squarely. A rib drawn to a pier keeps its
        course until it is within reach of the pier, then bends round on one smooth curve. Given
        `slot`, a plan position beside the pier, it arrives there running straight down the pier's
        funnel, ready to be stood on the floor (see `stand`). Without one it stops just short of
        the pier's axis.
        """
        samples, step = list(course.head), course.step
        if course.pier is None:
            squared = self._squared(course, square, shift) if square > 0.0 else None
            last = course.trail[squared[0]][0] if squared else course.end
            pieces = max(1, round((last - course.start) / step)) if last - course.start > 0.3 * step else 0
            for i in range(1, pieces + 1):
                radius = course.start + (last - course.start) * i / pieces
                samples.append(self.on_canopy(course.at(radius)[0], radius))
            foot = course.at(course.end)[1]
            if squared:
                samples += [self.drape(q) for q in squared[1]]
                foot = squared[1][-1]
            _, _, half, along = self.rim(math.atan2(foot[1] - self.centre[1], foot[0] - self.centre[0]))
            return samples[::-1], half, along

        pier_xy, halves = self.piers[course.pier]
        trail, turn = course.trail, course.turn
        radius = course.start
        while radius + 1.7 * step < trail[turn][0]:
            radius += step
            samples.append(self.on_canopy(course.at(radius)[0], radius))
        p0, ahead = trail[turn][1], trail[turn + 1][1]
        heading = math.hypot(ahead[0] - p0[0], ahead[1] - p0[1])
        heading = ((ahead[0] - p0[0]) / heading, (ahead[1] - p0[1]) / heading)
        away = math.hypot(pier_xy[0] - p0[0], pier_xy[1] - p0[1])
        end = slot or (pier_xy[0] + (p0[0] - pier_xy[0]) * 0.12 / away, pier_xy[1] + (p0[1] - pier_xy[1]) * 0.12 / away)
        ahead_of = heading[0] * (end[0] - p0[0]) + heading[1] * (end[1] - p0[1])  # how far along its course the pier lies
        hold = min(max(0.6 * ahead_of, 0.2 * away), 0.75 * away)
        knee = (p0[0] + heading[0] * hold, p0[1] + heading[1] * hold)
        c1 = tuple(p0[k] + (knee[k] - p0[k]) * 2.0 / 3.0 for k in (0, 1))
        if slot is None:
            c2 = tuple(end[k] + (knee[k] - end[k]) * 2.0 / 3.0 for k in (0, 1))
        else:  # arrive along the line from the pier's axis through the slot: straight down the funnel
            reach = math.hypot(slot[0] - pier_xy[0], slot[1] - pier_xy[1])
            c2 = tuple(slot[k] + (slot[k] - pier_xy[k]) / reach * 0.4 * away for k in (0, 1))
        pieces = max(3, round(away / step))
        # The bend's first point is left out where it would crowd the point before it.
        for i in range(1 if trail[turn][0] - radius < 0.7 * step else 0, pieces + 1):
            t = i / pieces
            u = 1.0 - t
            samples.append(self.drape(tuple(u**3 * p0[k] + 3 * u * u * t * c1[k] + 3 * u * t * t * c2[k] + t**3 * end[k] for k in (0, 1))))
        return samples[::-1], halves[0], 0.0

    def stand(self, samples: list, pier_xy, knee_drop: float | None = None) -> list:
        """Carry a member whose first sample is on a pier's funnel down to the floor as an upright leg.

        The leg stands under that first sample and stops at a knee `knee_drop` below it (by default
        as far below as the member's next sample is beyond). From the knee the member rounds the
        corner on a parabola to that next sample, so leg and roof run into each other without a kink.
        """
        corner, _ = samples[0]
        onward, normal = samples[1]
        toward = unit((pier_xy[0] - corner[0], pier_xy[1] - corner[1], 0.0))
        knee = (corner[0], corner[1], corner[2] - (knee_drop or norm(sub(onward, corner))))
        leg = [((corner[0], corner[1], level), toward) for level in (self.floor_z, 0.5 * (self.floor_z + knee[2]), knee[2])]
        for t in (1.0 / 3.0, 2.0 / 3.0):
            u = 1.0 - t
            point = tuple(u * u * knee[k] + 2.0 * u * t * corner[k] + t * t * onward[k] for k in range(3))
            leg.append((point, unit(add(mul(toward, u), mul(normal, t)))))
        return leg + list(samples[1:])

    def ring(self, lam: float | None, radius: float | None, spacing: float) -> list:
        """(point, normal) samples round a ring: part-way up the lantern at `lam`, or on the canopy at `radius`."""
        if lam is not None:
            point, _ = self.on_lantern(0.0, lam)
            radius = math.hypot(point[0] - self.centre[0], point[1] - self.centre[1])
        count = max(24, round(TWO_PI * radius / spacing))
        if lam is not None:
            return [self.on_lantern(TWO_PI * i / count, lam) for i in range(count)]
        return [self.on_canopy(TWO_PI * i / count, radius) for i in range(count)]

    def spiral(self, arrival: float, sense: float, lean: float, spacing: float, inset: float, gather: float, top: float = 1.0):
        """`trace` and `lay` in one step, for a rib that needs no place at a pier."""
        return self.lay(self.trace(arrival, sense, lean, spacing, inset, gather, top))


# --- boundary curves and the mesh ------------------------------------------------------------


def boundary(room: dict, roof: Roof | None = None) -> tuple[dict, dict]:
    """The named nodes and boundary curves of a room."""
    roof = roof or Roof(room)
    cx, cy = roof.centre
    nodes, edges = {}, {}

    def edge(edge_id: str, kind: str, start: str, end: str, path: BezierPath) -> None:
        edges[edge_id] = Edge(edge_id, kind, start, end, path)

    def along_meridian(bearing: float) -> BezierPath:
        return spline([roof.meridian(bearing, j / 16) for j in range(17)])

    for pier in room["piers"]:
        pid, (x, y) = pier["id"], pier["position_m"]
        bearing = math.atan2(y - cy, x - cx)
        nodes[pid + ".base"], nodes[pid + ".spring"] = (x, y, roof.floor_z), (x, y, roof.spring_z)
        nodes[pid + ".crown"] = roof.on_lantern(bearing, 1.0)[0]
        edge(pid + ".pier", "pier", pid + ".base", pid + ".spring", _line(nodes[pid + ".base"], nodes[pid + ".spring"]))
        edge(pid + ".groin", "groin", pid + ".spring", pid + ".crown", along_meridian(bearing))

    for half in roof.halves:
        bid = half.bay
        if half.side == "L":
            nodes[bid + ".apex"] = half.apex
            nodes[bid + ".crown"] = roof.on_lantern(half.hi, 1.0)[0]
            edge(bid + ".ridge", "ridge", bid + ".apex", bid + ".crown", along_meridian(half.hi))
        leg = (half.foot[0] + half.direction[0] * roof.pier_radius, half.foot[1] + half.direction[1] * roof.pier_radius, roof.spring_z)
        edge(f"{bid}.arch.{half.side}", "arch", half.pier + ".spring", bid + ".apex", plane_path(leg, half.direction, [half.profile]))
        start, end = (half.pier, bid) if half.side == "L" else (bid, half.pier)
        a = nodes[start + ".crown"] if start + ".crown" in nodes else roof.on_lantern(half.lo, 1.0)[0]
        tangent = (-math.sin(half.lo), math.cos(half.lo), 0.0)
        arc = arc_path(a, tangent, (cx - a[0], cy - a[1], 0.0), roof.top_radius, roof.top_radius * (half.hi - half.lo))
        edge(f"{bid}.crown.{half.side}", "crown", start + ".crown", end + ".crown", arc)

    return nodes, edges


def build_envelope(room: dict, sampling: dict) -> Envelope:
    """Mesh a room's roof. Each node and each sample of a shared meridian is one vertex, used by both patches beside it."""
    roof = Roof(room)
    nodes, edges = boundary(room, roof)
    across, up = sampling["across"], sampling["up"]
    verts, node_vert, edge_verts = [], {}, {}

    def new(point: Vec) -> int:
        verts.append(point)
        return len(verts) - 1

    def at_node(node_id: str) -> int:
        if node_id not in node_vert:
            node_vert[node_id] = new(nodes[node_id])
        return node_vert[node_id]

    def meridian(edge_id: str, bearing: float) -> list:
        if edge_id not in edge_verts:
            e = edges[edge_id]
            edge_verts[edge_id] = [at_node(e.start), *(new(roof.meridian(bearing, j / up)) for j in range(1, up)), at_node(e.end)]
        return edge_verts[edge_id]

    patches, faces, face_patch = {}, [], []
    for half in roof.halves:
        bid, side = half.bay, half.side
        bearings = [half.lo + (half.hi - half.lo) * i / across for i in range(across + 1)]
        groin, ridge = meridian(half.pier + ".groin", half.lo if side == "L" else half.hi), meridian(bid + ".ridge", half.hi if side == "L" else half.lo)
        left, right = (groin, ridge) if side == "L" else (ridge, groin)
        bottom = [left[0], *(new(roof.meridian(b, 0.0)) for b in bearings[1:-1]), right[0]]
        top = [left[-1], *(new(roof.on_lantern(b, 1.0)[0]) for b in bearings[1:-1]), right[-1]]
        edge_verts[f"{bid}.arch.{side}"], edge_verts[f"{bid}.crown.{side}"] = bottom, top
        grid = [left, *([bottom[i], *(new(roof.meridian(bearings[i], j / up)) for j in range(1, up)), top[i]] for i in range(1, across)), right]
        patch = Patch(f"{bid}.{side}", bid, "roof", (half.pier + ".groin", bid + ".ridge", f"{bid}.arch.{side}", f"{bid}.crown.{side}"))
        patches[patch.id] = patch
        for i in range(across):
            for j in range(up):
                faces.append((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
                face_patch.append(patch.id)
    return Envelope(room["id"], nodes, edges, patches, verts, faces, face_patch, edge_verts)


def bay_signature(env: Envelope, bay_id: str) -> tuple:
    """Every vertex position of a bay's patches, for testing that an edit left the bay exactly as it was."""
    return tuple(env.verts[i] for face, patch in zip(env.faces, env.face_patch) if env.patches[patch].bay == bay_id for i in face)


def check_envelope(env: Envelope) -> dict:
    """Validity of the envelope mesh: finite, consistently oriented, open only at the arches and the
    crown, free of collapsed or folded faces, and joined along the full length of every shared curve."""
    problems = []
    if not all(math.isfinite(c) for p in env.verts for c in p):
        problems.append("non-finite coordinates")

    directed = Counter((a, b) for face in env.faces for a, b in zip(face, face[1:] + face[:1]))
    if any(n > 1 for n in directed.values()):
        problems.append("faces are inconsistently wound or overlap")
    rim = {a: b for (a, b) in directed if (b, a) not in directed}
    loops, seen = 0, set()
    for start in rim:
        if start not in seen:
            loops += 1
            v = start
            while v not in seen:
                seen.add(v)
                v = rim[v]
    if loops != 2:
        problems.append(f"expected two open rims (arches and crown), found {loops}")

    normals, collapsed = [], 0
    for face in env.faces:
        p = [env.verts[i] for i in face]
        n = cross(sub(p[1], p[0]), sub(p[2], p[0])) if len(p) == 3 else cross(sub(p[2], p[0]), sub(p[3], p[1]))
        length = norm(n)
        collapsed += length < 2e-8
        normals.append(mul(n, 1.0 / length) if length >= 2e-8 else None)
    if collapsed:
        problems.append(f"{collapsed} collapsed faces")

    across = defaultdict(list)
    for f, face in enumerate(env.faces):
        for a, b in zip(face, face[1:] + face[:1]):
            across[frozenset((a, b))].append(f)
    agreement = 1.0
    for pair in across.values():
        if len(pair) == 2 and env.face_patch[pair[0]] == env.face_patch[pair[1]] and normals[pair[0]] and normals[pair[1]]:
            agreement = min(agreement, dot(normals[pair[0]], normals[pair[1]]))
    if agreement <= 0.0:
        problems.append("a patch folds back on itself")

    users = defaultdict(set)
    for patch in env.patches.values():
        for edge_id in patch.edges:
            users[edge_id].add(patch.id)
    shared = {edge_id: patch_ids for edge_id, patch_ids in users.items() if len(patch_ids) == 2}
    joined = 0
    for edge_id, patch_ids in shared.items():
        along = env.edge_verts[edge_id]
        joined += all({env.face_patch[f] for f in across[frozenset(pair)]} == patch_ids for pair in zip(along, along[1:]))
    if joined != len(shared):
        problems.append(f"{len(shared) - joined} shared curves are not joined along their full length")

    return {
        "ok": not problems,
        "problems": problems,
        "vertices": len(env.verts),
        "faces": len(env.faces),
        "patches": len(env.patches),
        "open_rims": loops,
        "shared_curves": len(shared),
        "shared_curves_joined_full_length": joined,
        "collapsed_faces": collapsed,
        "min_normal_agreement_in_patch": round(agreement, 4),
    }
