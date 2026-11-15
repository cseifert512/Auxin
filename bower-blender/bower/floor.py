"""The level the members stand at, for a room on level ground or on a slope.

A room used to stand on one level, the lowest point of its members, and that number was worked out
afresh wherever it was wanted. On sloping ground each pier's feet stand at that pier's own level
(`rooms[].piers[].foot_z_m`: bower/timber.py lengthens the legs to it and changes nothing else).

`Floor(members)` is still that one number, the lowest level, so everything that reads it as a number
goes on exactly as before. It also answers `at(point)`: the level the feet stand at near a plan
point. On level ground that is the same number everywhere, whatever the point.

Pure Python (no bpy).
"""
from __future__ import annotations

import math

REACH_M = 2.0  # feet further apart than this, in plan, stand at different piers
UPRIGHT = 0.9  # a member end counts as standing if its direction is this near to plumb, as bower/joints.py finds a base


def _apart(p, q) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


class Floor(float):
    def __new__(cls, members):
        if isinstance(members, (int, float)):  # a plain level, as a copy of a Floor is made from
            self = super().__new__(cls, members)
            self._feet, self._level = (), True
            return self
        lowest = min(m.path.anchors[0].co[2] for m in members)
        self = super().__new__(cls, lowest)
        ends = []  # every member end that points down and stands up straight
        for m in members:
            for s, sign in ((0.0, 1.0), (m.path.length, -1.0)):
                st = m.path.station_at(s)
                if sign * st.tangent[2] > UPRIGHT:
                    ends.append(st.point)
        # a foot is a standing end with no other standing end below it at the same pier
        self._feet = tuple(p for p in ends if not any(q[2] < p[2] - 1e-6 and _apart(p, q) <= REACH_M for q in ends))
        self._level = all(abs(p[2] - lowest) < 1e-6 for p in self._feet)
        return self

    @property
    def level(self) -> bool:
        """Whether every pier's feet stand at one level."""
        return self._level

    def at(self, point) -> float:
        """The level the feet stand at near a point: that of the nearest foot, in plan."""
        if self._level or not self._feet:
            return float(self)
        return min(self._feet, key=lambda p: _apart(p, point))[2]

    def stands(self, point) -> bool:
        """Whether a point is at the level the feet stand at there."""
        return abs(point[2] - self.at(point)) < 1e-6


def level_at(floor, point) -> float:
    """The floor's level near a point, whether the floor is a `Floor` or a plain number."""
    return floor.at(point) if isinstance(floor, Floor) else float(floor)
