"""The crown as a point or a line, and the two coordinates everything in a roof is measured in.

A room's roof is described by where a point lies round the crown (its bearing)
and how far it lies from the crown (its distance). For a crown that is a single
point these are plain polar coordinates: an angle in radians and a radius.

A crown can also be drawn out into a straight line, a spine, from A to B. The
same two coordinates then wrap round the line: distance is measured to the
nearest point of the spine, and bearing runs once round it, counter-clockwise,
as an angle while going round an end and as a length while running along a
side. The curves of equal distance are stadiums: two straight sides and two
half circles. Bearing runs from 0 to 2*pi + 2*length, and for a spine of no
length it is the plain angle again, so a point crown is the special case.

    frame(bearing)      the nearest point of the spine and the unit direction away from it
    locate(point)       the bearing and distance of a plan point
    shift(...)          a bearing moved sideways by a distance, along the curve of equal distance
    swing(...)          a bearing after running outward at a fixed angle to the way out
    arc(...)            distance along a curve of equal distance between two bearings
    along(...)          the bearing reached after going a distance along such a curve from bearing 0

Pure Python (no bpy). Plan positions are (x, y) in metres.
"""
from __future__ import annotations

import math

TWO_PI = 2.0 * math.pi


class Spine:
    """A crown's centre line (or centre point) with the coordinates measured from it."""

    def __init__(self, a, b=None):
        self.a = (float(a[0]), float(a[1]))
        self.b = self.a if b is None else (float(b[0]), float(b[1]))
        self.length = math.dist(self.a, self.b)
        if self.length < 1e-9:
            self.b, self.length = self.a, 0.0
        self.centre = ((self.a[0] + self.b[0]) / 2.0, (self.a[1] + self.b[1]) / 2.0)
        self.period = TWO_PI + 2.0 * self.length
        if self.length:
            self.u = ((self.b[0] - self.a[0]) / self.length, (self.b[1] - self.a[1]) / self.length)
            heading = math.atan2(self.u[1], self.u[0])
            left, right = (heading + math.pi / 2.0) % TWO_PI, (heading - math.pi / 2.0) % TWO_PI
            # the two sides, in the order their bearings come: (angle it faces, bearing it starts at, is it the left side)
            first, second = sorted(((left, True), (right, False)))
            self._sides = ((first[0], first[0], first[1]), (second[0], second[0] + self.length, second[1]))

    # -- between coordinates and plan positions -----------------------------------------------

    def _zone(self, bearing: float):
        """Where a bearing falls: ("side", side, distance along it) or ("end", angle, None)."""
        bearing %= self.period
        for side in self._sides:
            if side[1] <= bearing <= side[1] + self.length:
                return "side", side, bearing - side[1]
        angle = bearing - self.length * sum(1 for side in self._sides if bearing > side[1])
        return "end", angle, None

    def frame(self, bearing: float):
        """The point of the spine nearest to everything at this bearing, and the unit direction away from it."""
        if not self.length:
            return self.a, (math.cos(bearing), math.sin(bearing))
        kind, at, run = self._zone(bearing)
        if kind == "side":
            angle, _, is_left = at
            foot = (self.b[0] - run * self.u[0], self.b[1] - run * self.u[1]) if is_left else (self.a[0] + run * self.u[0], self.a[1] + run * self.u[1])
            return foot, (math.cos(angle), math.sin(angle))
        away = (math.cos(at), math.sin(at))
        return (self.b if away[0] * self.u[0] + away[1] * self.u[1] > 0.0 else self.a), away

    def locate(self, point) -> tuple[float, float]:
        """The bearing and distance of a plan point."""
        if not self.length:
            dx, dy = point[0] - self.a[0], point[1] - self.a[1]
            return math.atan2(dy, dx) % TWO_PI, math.hypot(dx, dy)
        along = (point[0] - self.a[0]) * self.u[0] + (point[1] - self.a[1]) * self.u[1]
        if 1e-9 < along < self.length - 1e-9:  # beside the spine
            foot = (self.a[0] + along * self.u[0], self.a[1] + along * self.u[1])
            vx, vy = point[0] - foot[0], point[1] - foot[1]
            on_left = self.u[0] * vy - self.u[1] * vx > 0.0
            side = next(s for s in self._sides if s[2] == on_left)
            return side[1] + (self.length - along if on_left else along), math.hypot(vx, vy)
        end = self.a if along <= 1e-9 else self.b  # round an end: measured on from the side that leads into it
        vx, vy = point[0] - end[0], point[1] - end[1]
        before = next(s for s in self._sides if s[2] == (end is self.a))  # the left side ends at A, the right side at B
        angle = math.atan2(vy, vx)
        return (before[1] + self.length + (angle - before[0]) % TWO_PI) % self.period, math.hypot(vx, vy)

    # -- moving about -------------------------------------------------------------------------------

    def shift(self, bearing: float, sideways: float, distance: float) -> float:
        """The bearing reached by moving `sideways` metres counter-clockwise along the curve `distance` from the spine.

        The result is not wrapped: it runs on past a whole turn, so that a rib's bearings can be
        read off in order.
        """
        if not self.length:
            return bearing + sideways / distance
        moved, left = bearing, abs(sideways)
        way = 1.0 if sideways >= 0.0 else -1.0
        for _ in range(64):
            if left <= 1e-12:
                break
            kind, at, run = self._zone(moved)
            if kind == "side":
                room = (self.length - run) if way > 0 else run
                if room <= 1e-12:  # at the very end of the side: step onto the end beyond it
                    turn = min(left / distance, 1e-9)
                    moved, left = moved + way * 1e-9, left - turn * distance
                    continue
                step = min(left, room)
                moved, left = moved + way * step, left - step
            else:
                position = moved % self.period
                edges = sorted(e for side in self._sides for e in (side[1], side[1] + self.length))
                if way > 0:
                    room = min((e - position for e in edges if e - position > 1e-12), default=self.period - position + edges[0])
                else:
                    room = min((position - e for e in edges if position - e > 1e-12), default=position + self.period - edges[-1])
                step = min(left / distance, room)
                moved, left = moved + way * step, left - step * distance
                if step == room and left > 1e-12:  # onto the side beyond
                    moved += way * 1e-12
        return moved

    def swing(self, bearing: float, tangent: float, start: float, end: float) -> float:
        """The bearing reached by running from distance `start` out to `end` while holding an angle to the way out.

        `tangent` is the tangent of that angle, positive for a course that turns counter-clockwise
        as it goes out. Round a point or an end the course is a spiral; along a side it is a
        straight line.
        """
        if not self.length or self._zone(bearing)[0] == "end":
            return bearing + tangent * math.log(end / start)
        return self.shift(bearing, tangent * (end - start), 0.5 * (start + end))

    def perimeter(self, distance: float) -> float:
        """The length of the curve `distance` from the spine."""
        return TWO_PI * distance + 2.0 * self.length

    def along(self, travelled: float, distance: float) -> float:
        """The bearing reached after going `travelled` metres counter-clockwise from bearing 0 along the curve `distance` from the spine."""
        return self.shift(0.0, travelled, distance)

    def arc(self, start: float, end: float, distance: float) -> float:
        """How far it is counter-clockwise from one bearing to another along the curve `distance` from the spine."""
        if not self.length:
            return ((end - start) % TWO_PI) * distance
        gone, at, target = 0.0, start % self.period, (end - start) % self.period
        edges = sorted(e for side in self._sides for e in (side[1], side[1] + self.length)) + [self.period]
        while target > 1e-12:
            kind, _, _ = self._zone(at + 1e-12)
            reach = min((e - at for e in edges if e - at > 1e-12), default=self.period - at)
            step = min(target, reach)
            gone += step if kind == "side" else step * distance
            at, target = (at + step) % self.period, target - step
        return gone


def crown_spine(crown: dict) -> Spine:
    """The spine of a room's crown: its `spine_m` line if it has one, or its centre point."""
    if crown.get("spine_m"):
        return Spine(*crown["spine_m"])
    return Spine(crown["centre_m"])
