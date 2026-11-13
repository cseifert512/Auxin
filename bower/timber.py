"""Level C: the primary timber, generated from the plan graph with the envelope's shape rules.

Every primary is a planar, single-curvature member. All but the crown ring lie
in vertical planes; the pattern comes from how those planes cross.

    <bay>.arch.L / .R     foot -> arch half -> bay apex
    <pier>.groin          foot -> valley rib -> crown ring
    <bay>.ridge           bay apex -> crown ring
    <bay>.sweep.L / .R    foot -> the knot on the bay's ridge
    <bay>.lierne.L / .R   bay apex -> the knot on the groin of the pier on that side
    <bay>.crown           the crown ring between the bay's two groin landings

Five members leave every pier (two arch halves, the groin, two sweeps) and five
meet at every apex (two arch halves, the ridge, two liernes). In each half-bay
a sweep rising from the pier and a lierne coming in from the apex cross once;
around the room those crossings link into a band of diamonds between the eave
and the crown. Nothing is cut where they cross: the lierne is bowed just enough
to lie against the sweep, over it or under it, whichever takes the smaller bow.

Piers. Each member at a pier starts `pier_cluster_radius_m` from the pier point
along its own line of travel, so the cluster is a palm whose fingers already
point where their ribs go. A sweep's foot is kept `pier_finger_gap_deg` clear of
the groin's and the arch's on either side of it. The radius is one value for
the room, so that moving a pier cannot shift the members of a pier elsewhere.

Curvature. Ribs are close to circular arcs from the ground up, which is what
keeps their radii large: a rib that stood upright first and turned afterwards
would have to turn much more tightly. Arches, groins and ridges use the same
profile rules as the envelope curves of the same name.

Pure Python (no bpy). Sections and clearances are provisional concept values:
nothing here is a structural or fabrication check.
"""
from __future__ import annotations

import math
from collections import defaultdict

from .centreline import Anchor, BezierPath, arc_path, cross, dot, norm, sub, unit
from .envelope import arch_profile, groin_profile, ridge_profile
from .member import Member
from .topology import apex_point

UP = (0.0, 0.0, 1.0)
FAMILIES = ("arch", "groin", "ridge", "sweep", "lierne", "crown")


# --- planar paths -----------------------------------------------------------------


def _plane_path(origin, direction, segments) -> BezierPath:
    """A path in the vertical plane through `origin` along the horizontal unit vector `direction`.

    `segments` are cubics in plane coordinates, four (distance, height) points each, every one
    starting where the last ended. The section depth axis is the in-plane normal on the right of
    travel, which is the underside of a rising rib.
    """

    def lift(p):
        return (origin[0] + direction[0] * p[0], origin[1] + direction[1] * p[0], origin[2] + p[1])

    def normal(a, b):
        td, tz = b[0] - a[0], b[1] - a[1]
        length = math.hypot(td, tz)
        return (direction[0] * tz / length, direction[1] * tz / length, -td / length)

    first = segments[0]
    anchors = [Anchor(lift(first[0]), lift(first[0]), lift(first[1]), normal(first[0], first[1]))]
    for k, (_, _, p2, p3) in enumerate(segments):
        leaving = segments[k + 1][1] if k + 1 < len(segments) else p3
        anchors.append(Anchor(lift(p3), lift(p2), lift(leaving), normal(p2, p3)))
    return BezierPath(anchors)


def _at(cubic, t: float):
    """Point and derivative of a plane-coordinate cubic at parameter t."""
    u = 1.0 - t
    point = tuple(u**3 * cubic[0][k] + 3 * u * u * t * cubic[1][k] + 3 * u * t * t * cubic[2][k] + t**3 * cubic[3][k] for k in (0, 1))
    slope = tuple(
        3 * u * u * (cubic[1][k] - cubic[0][k]) + 6 * u * t * (cubic[2][k] - cubic[1][k]) + 3 * t * t * (cubic[3][k] - cubic[2][k])
        for k in (0, 1)
    )
    return point, slope


def _at_distance(cubic, distance: float):
    """Point and derivative of a profile cubic where it has travelled `distance` horizontally."""
    lo, hi = 0.0, 1.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if _at(cubic, mid)[0][0] < distance:
            lo = mid
        else:
            hi = mid
    return _at(cubic, 0.5 * (lo + hi))


def _toward(p, q):
    """Horizontal unit vector from p to q, and the plan distance between them."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    distance = math.hypot(dx, dy)
    return (dx / distance, dy / distance, 0.0), distance


def _angle(u, v) -> float:
    """Signed plan angle from u to v."""
    return math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])


def _butt(direction, onto, half_width: float) -> float:
    """How far short of another member's centreline to stop, to end at its side face."""
    sine = abs(direction[0] * onto[1] - direction[1] * onto[0])
    return half_width / max(sine, 0.35)


def _lap(depth_a: float, depth_b: float, tangent_a, tangent_b, clearance: float) -> float:
    """Vertical offset that keeps two crossing members `clearance` apart along their common normal."""
    n = cross(tangent_a, tangent_b)
    upright = abs(n[2]) / max(norm(n), 1e-9)
    return ((depth_a + depth_b) / 2.0 + clearance) / max(upright, 0.3)


def _fair_arc(run: float, rise: float, fullness: float) -> tuple:
    """A rib profile leaving the ground upright and reaching (run, rise) as one even arc.

    The arrival slope is the one a circular arc would have; `fullness` is the length of both
    Bezier handles as a fraction of the chord (0.35 is close to circular).
    """
    slope = max(math.pi / 2.0 - 2.0 * math.atan2(run, rise), math.radians(5.0))
    handle = fullness * math.hypot(run, rise)
    return ((0.0, 0.0), (0.0, handle), (run - handle * math.cos(slope), rise - handle * math.sin(slope)), (run, rise))


# --- the grammar ---------------------------------------------------------------------


def build_timber(room: dict, timber: dict) -> list[Member]:
    """The primary members of one room, in a fixed order."""
    shape, crown = room["shape"], room["crown"]
    z0, shaft = room["floor_z_m"], shape["pier_height_m"]
    centre, ring_radius, top = crown["centre_m"], crown["radius_m"], crown["height_m"]
    section = {family: tuple(size) for family, size in timber["sections_m"].items()}
    rho, clearance = timber["pier_cluster_radius_m"], timber["lap_clearance_m"]
    half_arch, half_ring = section["arch"][0] / 2.0, section["crown"][0] / 2.0
    piers = {p["id"]: p["position_m"] for p in room["piers"]}
    shaft_run = ((0.0, 0.0), (0.0, shaft / 3.0), (0.0, 2.0 * shaft / 3.0), (0.0, shaft))
    members = []

    def member(member_id: str, family: str, parent: str, path: BezierPath, nodes: tuple) -> None:
        width, depth = section[family]
        members.append(Member(member_id, "primary", width, depth, path, parent, family, nodes))

    def standing(foot_xy, direction, profile) -> BezierPath:
        """A member standing on the floor: the short shaft, then `profile` given from the spring upward."""
        return _plane_path((foot_xy[0], foot_xy[1], z0), direction, [shaft_run, tuple((d, z + shaft) for d, z in profile)])

    def sprung(pier_xy, direction, profile) -> BezierPath:
        """A member standing at a pier, its foot out along its own line of travel."""
        return standing((pier_xy[0] + rho * direction[0], pier_xy[1] + rho * direction[1]), direction, profile)

    def knot(origin_xy, direction, base_z: float, profile, fraction: float):
        """The point `fraction` of the way along a rib's run, and the rib's direction there."""
        (d, z), (td, tz) = _at_distance(profile, fraction * profile[3][0])
        point = (origin_xy[0] + direction[0] * d, origin_xy[1] + direction[1] * d, base_z + z)
        return point, unit((direction[0] * td, direction[1] * td, tz))

    groins = {}  # pier ID -> (knot point, groin direction at the knot, inward direction)
    for pid, xy in piers.items():
        inward, distance = _toward(xy, centre)
        profile = groin_profile(distance - ring_radius - rho - half_ring, top - shaft, shape)
        foot = (xy[0] + rho * inward[0], xy[1] + rho * inward[1])
        groins[pid] = (*knot(foot, inward, z0 + shaft, profile, timber["net_groin_at"]), inward)
        member(f"{pid}.groin", "groin", pid, sprung(xy, inward, profile), (f"{pid}.groin.foot", f"{pid}.knot", f"{pid}.crown"))

    for bay in room["bays"]:
        bid, a, b = bay["id"], bay["from"], bay["to"]
        apex = apex_point(room, bay)
        inward, distance = _toward(apex, centre)
        ridge_start = (apex[0] + inward[0] * half_arch, apex[1] + inward[1] * half_arch, apex[2])
        profile = ridge_profile(distance - ring_radius - half_arch - half_ring, z0 + top - apex[2], shape)
        ridge_knot, ridge_heading = knot(ridge_start, inward, apex[2], profile, timber["net_ridge_at"])
        member(f"{bid}.ridge", "ridge", bid, _plane_path(ridge_start, inward, [profile]), (f"{bid}.apex", f"{bid}.knot", f"{bid}.crown"))

        for side, pid in (("L", a), ("R", b)):
            xy = piers[pid]
            direction, span = _toward(xy, apex)
            arch = arch_profile(span - rho, apex[2] - z0 - shaft, shape)
            member(f"{bid}.arch.{side}", "arch", bid, sprung(xy, direction, arch), (f"{bid}.arch.{side}.foot", f"{bid}.apex"))

            # The sweep: one even arc from this pier to the side face of the ridge at its knot.
            # Its foot sits on the cluster circle between the groin's and the arch's.
            groin_knot, groin_heading, groin_inward = groins[pid]
            to_knot, _ = _toward(xy, ridge_knot)
            opening, finger = _angle(groin_inward, direction), math.radians(timber["pier_finger_gap_deg"])
            turn = min(max(abs(_angle(groin_inward, to_knot)), finger), max(abs(opening) - finger, abs(opening) / 2.0))
            turn = math.copysign(turn, opening)
            sweep_foot = (
                xy[0] + rho * (groin_inward[0] * math.cos(turn) - groin_inward[1] * math.sin(turn)),
                xy[1] + rho * (groin_inward[0] * math.sin(turn) + groin_inward[1] * math.cos(turn)),
            )
            heading, reach = _toward(sweep_foot, ridge_knot)
            run = reach - _butt(heading, inward, section["ridge"][0] / 2.0)
            rise = ridge_knot[2] - z0 - shaft
            sweep = _fair_arc(run, rise, timber["sweep_fullness"])
            member(f"{bid}.sweep.{side}", "sweep", bid, standing(sweep_foot, heading, sweep), (f"{bid}.sweep.{side}.foot", f"{bid}.knot"))

            # The lierne: from beside the ridge at the apex to the side face of this pier's groin,
            # straight in plan and bowed in height so that it lies against the sweep it crosses.
            sideways, _ = _toward(apex, xy)
            step = (section["ridge"][0] + section["lierne"][0]) / 2.0 + 0.03
            start = (ridge_start[0] + sideways[0] * step, ridge_start[1] + sideways[1] * step, apex[2])
            along, length = _toward(start, groin_knot)
            length -= _butt(along, groin_inward, section["groin"][0] / 2.0)
            fall = groin_knot[2] - start[2]
            bow = 0.0
            # Where the two plan lines cross: s metres along the sweep from its foot, l along the lierne.
            det = heading[0] * -along[1] + along[0] * heading[1]
            if abs(det) > 1e-6:
                ex, ey = start[0] - sweep_foot[0], start[1] - sweep_foot[1]
                s = (ex * -along[1] + along[0] * ey) / det
                l = (heading[0] * ey - heading[1] * ex) / det
                if 0.1 * run < s < 0.95 * run and 0.1 * length < l < 0.9 * length:
                    (_, below), (td, tz) = _at_distance(sweep, s)
                    sweep_heading = unit((heading[0] * td, heading[1] * td, tz))
                    resting = _lap(section["lierne"][1], section["sweep"][1], sweep_heading, unit((along[0] * length, along[1] * length, fall)), clearance)
                    t = l / length
                    above = z0 + shaft + below - start[2] - fall * t  # the sweep's height over the unbowed lierne here
                    offset = above + resting if abs(above + resting) <= abs(above - resting) else above - resting
                    bow = offset / (3.0 * t * (1.0 - t))
            lierne = ((0.0, 0.0), (length / 3.0, fall / 3.0 + bow), (2.0 * length / 3.0, 2.0 * fall / 3.0 + bow), (length, fall))
            member(f"{bid}.lierne.{side}", "lierne", bid, _plane_path(start, along, [lierne]), (f"{bid}.apex", f"{pid}.knot"))

        bearing = math.atan2(piers[a][1] - centre[1], piers[a][0] - centre[0])
        turn = (math.atan2(piers[b][1] - centre[1], piers[b][0] - centre[0]) - bearing) % (2.0 * math.pi)
        ring_start = (centre[0] + ring_radius * math.cos(bearing), centre[1] + ring_radius * math.sin(bearing), z0 + top)
        arc = arc_path(ring_start, (-math.sin(bearing), math.cos(bearing), 0.0), (centre[0] - ring_start[0], centre[1] - ring_start[1], 0.0), ring_radius, ring_radius * turn)
        ring = BezierPath(Anchor(n.co, n.handle_left, n.handle_right, UP) for n in arc.anchors)  # section depth stands upright
        member(f"{bid}.crown", "crown", bid, ring, (f"{a}.crown", f"{bid}.crown", f"{b}.crown"))

    return members


# --- diagnostics -----------------------------------------------------------------------


def clearances(members: list[Member], spacing: float = 0.1, within: float = 0.06) -> dict:
    """Closest approach of every pair of members that are not jointed at a shared node.

    The gap is measured between the two section rectangles along the line joining the closest
    sampled centreline points. It is a separating-axis estimate: a positive gap proves the
    members are apart; a negative gap is reported as a collision and may be slightly pessimistic.

    Returns the collisions and the pairs that pass within `within` metres of each other, which
    are the laps and packed neighbours where a connection would go.
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
                            if (i, j) not in closest or gap < closest[(i, j)][0]:
                                closest[(i, j)] = (gap, s.point, o.point)

    pairs = sorted(
        (
            {"a": members[i].id, "b": members[j].id, "gap_m": round(gap, 4), "at_m": [round((p[k] + q[k]) / 2, 3) for k in range(3)]}
            for (i, j), (gap, p, q) in closest.items()
            if gap < within
        ),
        key=lambda pair: (pair["gap_m"], pair["a"], pair["b"]),
    )
    return {
        "jointed_pairs": len(jointed),
        "collisions": [p for p in pairs if p["gap_m"] < -0.002],
        "close": [p for p in pairs if p["gap_m"] >= -0.002],
    }


def schedule(members: list[Member], timber: dict, report: dict) -> list[dict]:
    """One row per member: identity, joints, section, length, tightest bend, volume, neighbours.

    Geometric quantities only. `review` marks members whose tightest radius falls under
    timber["bend_radius_review_m"], a provisional threshold that is not a supplier's limit.
    """
    collisions, close = defaultdict(list), defaultdict(list)
    for kind, table in (("collisions", collisions), ("close", close)):
        for pair in report[kind]:
            table[pair["a"]].append(pair["b"])
            table[pair["b"]].append(pair["a"])
    rows = []
    for m in members:
        radius, at = m.path.min_bend_radius()
        tight = radius is not None and radius < timber["bend_radius_review_m"]
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
                "review": "tight radius" if tight else "",
                "collides_with": " ".join(sorted(collisions[m.id])),
                "passes_close_to": " ".join(sorted(close[m.id])),
            }
        )
    return rows
