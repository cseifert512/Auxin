"""Member centrelines as piecewise cubic Bezier paths.

Pure Python: no bpy and no numpy, so the same code runs inside Blender and in a
plain interpreter. Units are metres; axes are Z up, Y north.

A path carries a section-orientation hint at each anchor (`depth_axis`), so the
frame along a member is stated by whatever generated the path instead of being
guessed from curvature, which flips at inflections and is undefined on straights.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass

Vec = tuple[float, float, float]


def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a: Vec) -> float:
    return math.sqrt(dot(a, a))


def unit(a: Vec) -> Vec:
    length = norm(a)
    if length < 1e-12:
        raise ValueError("cannot normalise a zero-length vector")
    return mul(a, 1.0 / length)


def reject(v: Vec, axis: Vec) -> Vec:
    """The part of `v` perpendicular to the unit vector `axis`."""
    return sub(v, mul(axis, dot(v, axis)))


@dataclass(frozen=True)
class Anchor:
    """One Bezier anchor: a point, its two handles and the section depth direction there.

    `depth_axis` is only needed by paths that carry a section (members); envelope
    boundary curves leave it unset.
    """

    co: Vec
    handle_left: Vec
    handle_right: Vec
    depth_axis: Vec | None = None


@dataclass(frozen=True)
class Station:
    """A sample on a path with an orthonormal section frame (width x depth = tangent)."""

    s: float  # arc length from the start, m
    point: Vec
    tangent: Vec
    depth_axis: Vec
    width_axis: Vec


class BezierPath:
    """An open chain of cubic Bezier segments through `anchors`."""

    TABLE_STEPS = 64  # parameter steps per segment in the arc-length table

    def __init__(self, anchors):
        self.anchors = tuple(anchors)
        if len(self.anchors) < 2:
            raise ValueError("a path needs at least two anchors")
        self._lengths = self._arc_table()

    @property
    def segment_count(self) -> int:
        return len(self.anchors) - 1

    @property
    def length(self) -> float:
        return self._lengths[-1]

    def _controls(self, seg: int):
        a, b = self.anchors[seg], self.anchors[seg + 1]
        return a.co, a.handle_right, b.handle_left, b.co

    def point(self, seg: int, t: float) -> Vec:
        p0, p1, p2, p3 = self._controls(seg)
        u = 1.0 - t
        w0, w1, w2, w3 = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
        return tuple(w0 * p0[k] + w1 * p1[k] + w2 * p2[k] + w3 * p3[k] for k in range(3))

    def velocity(self, seg: int, t: float) -> Vec:
        p0, p1, p2, p3 = self._controls(seg)
        u = 1.0 - t
        w0, w1, w2 = 3 * u * u, 6 * u * t, 3 * t * t
        return tuple(
            w0 * (p1[k] - p0[k]) + w1 * (p2[k] - p1[k]) + w2 * (p3[k] - p2[k]) for k in range(3)
        )

    def acceleration(self, seg: int, t: float) -> Vec:
        p0, p1, p2, p3 = self._controls(seg)
        u = 1.0 - t
        return tuple(
            6 * (u * (p2[k] - 2 * p1[k] + p0[k]) + t * (p3[k] - 2 * p2[k] + p1[k])) for k in range(3)
        )

    def curvature(self, seg: int, t: float) -> float:
        v = self.velocity(seg, t)
        return norm(cross(v, self.acceleration(seg, t))) / norm(v) ** 3

    def _arc_table(self) -> list[float]:
        """Cumulative arc length at every 1/TABLE_STEPS of parameter (Simpson's rule per step)."""
        n = self.TABLE_STEPS
        lengths = [0.0]
        for seg in range(self.segment_count):
            for j in range(n):
                t0, t1 = j / n, (j + 1) / n
                speeds = (
                    norm(self.velocity(seg, t0))
                    + 4 * norm(self.velocity(seg, 0.5 * (t0 + t1)))
                    + norm(self.velocity(seg, t1))
                )
                lengths.append(lengths[-1] + (t1 - t0) / 6.0 * speeds)
        return lengths

    def _locate(self, s: float) -> tuple[int, float]:
        """Segment index and parameter at arc length `s`."""
        lengths, n = self._lengths, self.TABLE_STEPS
        i = min(max(bisect_right(lengths, s) - 1, 0), len(lengths) - 2)
        u = (i + (s - lengths[i]) / (lengths[i + 1] - lengths[i])) / n
        seg = min(int(u), self.segment_count - 1)
        return seg, min(max(u - seg, 0.0), 1.0)

    def _station(self, s: float, seg: int, t: float) -> Station:
        tangent = unit(self.velocity(seg, t))
        a, b = self.anchors[seg].depth_axis, self.anchors[seg + 1].depth_axis
        if a is None or b is None:
            raise ValueError("this path has no depth axes, so it cannot give section frames")
        hint = add(mul(a, 1.0 - t), mul(b, t))
        depth = unit(reject(hint, tangent))
        return Station(s, self.point(seg, t), tangent, depth, cross(depth, tangent))

    def stations(self, max_spacing: float) -> list[Station]:
        """Frames at equal arc-length intervals no longer than `max_spacing`, ends included.

        The limit has 1 ppm of slack so that a 5 m path approximated to within a
        micron still divides into 100 intervals of 0.05 m rather than 101.
        """
        count = max(1, math.ceil(self.length / max_spacing * (1 - 1e-6)))
        return [self._station(s, *self._locate(s)) for s in (self.length * j / count for j in range(count + 1))]

    def point_at(self, fraction: float) -> Vec:
        """The point at `fraction` of the path's arc length (0 is the start, 1 the end)."""
        return self.point(*self._locate(fraction * self.length))

    def reversed(self) -> "BezierPath":
        """The same curve traversed from its end to its start."""
        return BezierPath(Anchor(a.co, a.handle_right, a.handle_left, a.depth_axis) for a in reversed(self.anchors))

    def points_uniform_parameter(self, resolution: int) -> list[Vec]:
        """Points at `resolution` equal parameter steps per segment, as Blender evaluates a Bezier spline."""
        points = [self.anchors[0].co]
        for seg in range(self.segment_count):
            points.extend(self.point(seg, j / resolution) for j in range(1, resolution + 1))
        return points

    def min_bend_radius(self) -> tuple[float | None, float]:
        """Tightest sampled radius of curvature and the arc length where it occurs.

        Sampled at the arc-length table's density. The radius is None for a straight path.
        """
        n = self.TABLE_STEPS
        worst, at = 0.0, 0.0
        for i, s in enumerate(self._lengths):
            seg = min(i // n, self.segment_count - 1)
            k = self.curvature(seg, i / n - seg)
            if k > worst:
                worst, at = k, s
        return (1.0 / worst if worst > 1e-12 else None), at


def arc_path(
    start: Vec,
    start_tangent: Vec,
    bend_toward: Vec,
    radius: float,
    length: float,
    max_segment_angle: float = math.radians(45),
) -> BezierPath:
    """A circular arc leaving `start` along `start_tangent` and curving toward `bend_toward`.

    The arc is built from cubic Beziers of at most `max_segment_angle` each, which
    keeps the radial error under 5e-6 x radius. Section depth lies in the plane of
    curvature and points at the centre of the arc (the intrados side).
    """
    t0 = unit(start_tangent)
    d = unit(reject(bend_toward, t0))
    sweep = length / radius
    count = max(1, math.ceil(sweep / max_segment_angle - 1e-9))
    step = sweep / count
    handle = 4.0 / 3.0 * math.tan(step / 4.0) * radius
    centre = add(start, mul(d, radius))
    anchors = []
    for i in range(count + 1):
        phi = i * step
        to_centre = sub(mul(d, math.cos(phi)), mul(t0, math.sin(phi)))
        tangent = add(mul(d, math.sin(phi)), mul(t0, math.cos(phi)))
        co = sub(centre, mul(to_centre, radius))
        anchors.append(Anchor(co, sub(co, mul(tangent, handle)), add(co, mul(tangent, handle)), to_centre))
    return BezierPath(anchors)
