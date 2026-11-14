"""Timber members: a stable ID, a role, a rectangular section and a centreline.

Pure Python (no bpy). The centreline is the member; the swept solid is only a
way of looking at it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .centreline import BezierPath, Station, add, arc_path, mul

ROLES = ("primary", "secondary", "cable")
CUT_SLIDE_LIMIT_M = 0.5


@dataclass(frozen=True)
class Member:
    id: str
    role: str
    width: float  # m, along the section width axis
    depth: float  # m, along the section depth axis
    path: BezierPath
    parent: str | None = None
    family: str = ""  # arch | hoop | rib | fill | fine | ring ... for generated primaries; sets section and colour
    nodes: tuple = ()  # named points this member is jointed at, start first and end last
    end_cut: tuple | None = None  # unit normal of the plane its end face is cut to, for a mitred joint
    start_cut: tuple | None = None  # the same for its start face, for a member housed into another


def _path_from_spec(spec: dict) -> BezierPath:
    if spec["type"] == "arc":
        return arc_path(
            tuple(spec["start_m"]),
            tuple(spec["start_tangent"]),
            tuple(spec["bend_toward"]),
            spec["radius_m"],
            spec["length_m"],
        )
    raise ValueError(f"unknown centreline type {spec['type']!r}")


def member_from_spec(spec: dict) -> Member:
    """Build a member from its JSON description."""
    if spec["role"] not in ROLES:
        raise ValueError(f"member {spec['id']!r}: unknown role {spec['role']!r}")
    section = spec["section"]
    if section["shape"] != "rect":
        raise ValueError(f"member {spec['id']!r}: unknown section shape {section['shape']!r}")
    return Member(
        id=spec["id"],
        role=spec["role"],
        width=section["width_m"],
        depth=section["depth_m"],
        path=_path_from_spec(spec["centreline"]),
        parent=spec.get("parent"),
    )


@dataclass(frozen=True)
class Notch:
    """A lap notch across a member: between two wall planes, one face is cut back to a floor."""

    lo: float  # stations of its two walls, metres along the centreline
    hi: float
    face: int  # +1 cuts the face on the +depth side of the section, -1 the other
    floor: tuple  # the notch floor: (a point on its plane, the plane's unit normal)
    lo_wall: tuple  # (a point on the wall plane, its unit normal): the crossing member's side faces
    hi_wall: tuple


def _wall(member: Member, at: float, wall) -> tuple[float, float]:
    """How squarely a wall plane crosses the member at a station (sine of the crossing angle), and
    how far along the member the skewed wall runs between the member's centreline and its edge."""
    sine = abs(sum(a * b for a, b in zip(member.path.station_at(at).tangent, wall[1])))
    if sine < 1e-6:
        return sine, float("inf")
    return sine, member.width / 2.0 * (max(0.0, 1.0 - sine * sine) ** 0.5) / sine


def fit_notches(member: Member, notches) -> tuple[list, list]:
    """Turn the notches asked of a member into the notches that can be cut.

    Notches on the same face that run into each other are merged into one. A notch is turned
    away where it crosses too obliquely to have walls (under about 15 degrees), where it would
    run into an end of the member, or where it overlaps a notch on the opposite face, which
    would cut the member through. Returns the notches to cut, in order along the member, and
    the indices into `notches` of those turned away.
    """
    length = member.path.length
    lo_clear = 0.15 if member.start_cut else 0.03
    hi_clear = 0.15 if member.end_cut else 0.03
    fitted, rejected = [], []  # fitted: [notch, lowest station it reaches, highest]
    for i in sorted(range(len(notches)), key=lambda k: notches[k].lo):
        notch = notches[i]
        (sine_lo, run_lo), (sine_hi, run_hi) = _wall(member, notch.lo, notch.lo_wall), _wall(member, notch.hi, notch.hi_wall)
        lo, hi = notch.lo - run_lo - 0.003, notch.hi + run_hi + 0.003
        if min(sine_lo, sine_hi) < 0.25 or lo < lo_clear or hi > length - hi_clear:
            rejected.append(i)
            continue
        clashing = [f for f in fitted if lo < f[2] + 0.004 and f[1] - 0.004 < hi]
        if any(f[0].face != notch.face for f in clashing):
            rejected.append(i)
            continue
        for f in clashing:  # same face: one wider notch, as deep as the deeper of the two
            first = f[0] if f[0].lo <= notch.lo else notch
            far = notch if notch.hi >= f[0].hi else f[0]
            notch = Notch(first.lo, far.hi, notch.face, first.floor, first.lo_wall, far.hi_wall)
            lo, hi = min(lo, f[1]), max(hi, f[2])
            fitted.remove(f)
        fitted.append([notch, lo, hi])
    return [f[0] for f in sorted(fitted, key=lambda f: f[0].lo)], rejected


def _ring(station: Station, half_width: float, depth, plane, step=None):
    """The four corners of the section at a station, optionally slid along the member onto a plane.

    `depth` is the half depth, or (offset of the -depth face, offset of the +depth face). With
    `step`, (face, floor plane), the two corners on that face of the section are brought in to
    the floor plane instead. Returns the corners and how far each was slid along the member
    (positive is onward).
    """
    minus, plus = (-depth, depth) if isinstance(depth, (int, float)) else depth
    corners = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        edge = add(station.point, mul(station.width_axis, sx * half_width))
        off = plus if sy > 0 else minus
        if step and step[0] == sy:
            point, normal = step[1]
            off = sum((point[k] - edge[k]) * normal[k] for k in range(3)) / sum(station.depth_axis[k] * normal[k] for k in range(3))
        corners.append(add(edge, mul(station.depth_axis, off)))
    slides = [0.0] * 4
    if plane:
        point, normal = plane
        across = sum(station.tangent[k] * normal[k] for k in range(3))
        if abs(across) > 1e-6:
            for i, corner in enumerate(corners):
                t = sum((point[k] - corner[k]) * normal[k] for k in range(3)) / across
                slides[i] = max(-CUT_SLIDE_LIMIT_M, min(CUT_SLIDE_LIMIT_M, t))
                corners[i] = add(corner, mul(station.tangent, slides[i]))
    return corners, slides


def sweep(member: Member, stations: list[Station], notches=()):
    """A closed quad mesh of the rectangular section swept through `stations`.

    Four vertices per ring, wound so that every face normal points outward. An end with a cut
    has its ring slid along the member onto the cut plane. Each of `notches` (as returned by
    `fit_notches`) steps one face of the section back to the notch floor between two walls
    that follow the sides of the crossing member.
    """
    hw, hd, path = member.width / 2.0, member.depth / 2.0, member.path
    rings = [(st.s, st, None, None) for st in stations]  # (station along the member, its frame, cut plane, step)
    for notch in notches:
        run_lo, run_hi = _wall(member, notch.lo, notch.lo_wall)[1], _wall(member, notch.hi, notch.hi_wall)[1]
        rings = [r for r in rings if not notch.lo - run_lo - 0.003 < r[0] < notch.hi + run_hi + 0.003]
        step = (notch.face, notch.floor)
        # a wall is two rings half a millimetre apart on the wall plane: the full section, then the stepped one
        for order, (s, wall, nudge, stepped) in enumerate(((notch.lo, notch.lo_wall, -1, None), (notch.lo, notch.lo_wall, 1, step), (notch.hi, notch.hi_wall, -1, step), (notch.hi, notch.hi_wall, 1, None))):
            station = path.station_at(s)
            rings.append((s + order * 1e-9, station, (add(wall[0], mul(station.tangent, nudge * 0.00025)), wall[1]), stepped))
    rings.sort(key=lambda r: r[0])
    if member.start_cut:
        rings[0] = (*rings[0][:2], (rings[0][1].point, member.start_cut), None)
    if member.end_cut:
        rings[-1] = (*rings[-1][:2], (rings[-1][1].point, member.end_cut), None)
    built = [_ring(st, hw, hd, plane, step) for _, st, plane, step in rings]
    # Plain rings that a cut end has been slid past are left out, so the mesh does not fold back on itself.
    past_start = max(0.0, max(built[0][1]))
    past_end = max(0.0, -min(built[-1][1]))
    last, length = len(rings) - 1, path.length
    keep = [k for k, r in enumerate(rings) if k in (0, last) or r[2] or (r[0] > past_start + 1e-3 and length - r[0] > past_end + 1e-3)]
    # A ring member comes back to where it started: its last ring is its first again, and it has no ends.
    closed = not member.start_cut and not member.end_cut and sum((a - b) ** 2 for a, b in zip(path.anchors[0].co, path.anchors[-1].co)) < 1e-12
    return _tube([built[k][0] for k in (keep[:-1] if closed else keep)], closed)


def _tube(rings: list, closed: bool = False) -> tuple[list, list]:
    """A closed quad mesh through rings of four corners: capped at both ends, or, for a member
    that comes back to where it started, joined end to start with no caps."""
    verts = [corner for ring in rings for corner in ring]
    count = len(rings)
    faces = []
    for j in range(count if closed else count - 1):
        a, b = 4 * j, 4 * ((j + 1) % count)
        for k in range(4):
            k2 = (k + 1) % 4
            faces.append((a + k, a + k2, b + k2, b + k))
    if closed:
        return verts, faces
    end = 4 * (count - 1)
    return verts, faces + [(3, 2, 1, 0), (end, end + 1, end + 2, end + 3)]


def block(path: BezierPath, lo: float, hi: float, half_width: float, depth, spacing: float = 0.03, lo_plane=None, hi_plane=None, step=None, stations=None):
    """The volume a rectangle sweeps along a path between two stations, as a closed mesh.

    This is what a cutter removes: it follows the path's own frames, so its sides turn with the
    member it stands for. `depth`, `step` and the end planes are as for a section ring: a face
    can be held to a floor plane, and either end slid onto a plane. On a closed path the
    stations wrap round.

    Given `stations`, the stations of that member's own mesh, the block is built through exactly
    those (reaching out to the next one beyond each end), so that it wraps the member's mesh
    and not just its ideal curve.
    """
    length = path.length
    closed = sum((a - b) ** 2 for a, b in zip(path.anchors[0].co, path.anchors[-1].co)) < 1e-12
    if not closed:
        lo, hi = max(lo, 0.0), min(hi, length)
    if stations is None:
        count = max(2, math.ceil((hi - lo) / spacing))
        along = [lo + (hi - lo) * k / count for k in range(count + 1)]
    else:
        every = sorted({s + turn for s in stations for turn in ((-length, 0.0, length) if closed else (0.0,))})
        lo = max((s for s in every if s <= lo + 1e-9), default=lo)
        hi = min((s for s in every if s >= hi - 1e-9), default=hi)
        along = [lo] + [s for s in every if lo + 1e-9 < s < hi - 1e-9] + [hi]
        count = len(along) - 1
    built = []
    for k, s in enumerate(along):
        plane = lo_plane if k == 0 else hi_plane if k == count else None
        built.append((s, *_ring(path.station_at(s % length if closed else s), half_width, depth, plane, step)))
    # as in a member's own mesh, rings that a slanted end has been slid past are left out
    past_lo, past_hi = max(0.0, max(built[0][2])), max(0.0, -min(built[-1][2]))
    rings = [corners for k, (s, corners, _) in enumerate(built) if k in (0, count) or (s - lo > past_lo + 1e-3 and hi - s > past_hi + 1e-3)]
    if stations is not None:
        # Between a member's stations its mesh runs straight, and a long panel between two rings that
        # are turned against each other is ambiguous. Rings are added along those straight runs so
        # that the block's panels are short and hug the mesh they wrap.
        fine = [rings[0]]
        for one, other in zip(rings, rings[1:]):
            fine += [[tuple(a[k] + (b[k] - a[k]) * i / 4 for k in range(3)) for a, b in zip(one, other)] for i in (1, 2, 3, 4)]
        rings = fine
    return _tube(rings)


def box(origin, axes, extents) -> tuple[list, list]:
    """A closed box mesh: from `origin`, between extents[k] = (lo, hi) along each of three unit `axes`."""
    verts = [tuple(origin[i] + sum(axes[k][i] * extents[k][bit] for k, bit in enumerate((bx, by, bz))) for i in range(3)) for bz in (0, 1) for by in (0, 1) for bx in (0, 1)]
    return verts, [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]


def diagnostics(member: Member, export_spacing: float) -> dict:
    """Geometric quantities for one member. Exploratory: not a structural or fabrication check."""
    path = member.path
    radius, at = path.min_bend_radius()
    export_count = len(path.stations(export_spacing))
    return {
        "id": member.id,
        "role": member.role,
        "parent": member.parent,
        "section_m": {"width": member.width, "depth": member.depth},
        "length_m": round(path.length, 6),
        "min_bend_radius_m": None if radius is None else round(radius, 4),
        "min_bend_radius_at_m": round(at, 4),
        "volume_m3": round(member.width * member.depth * path.length, 6),
        "start_m": [round(c, 6) for c in path.anchors[0].co],
        "end_m": [round(c, 6) for c in path.anchors[-1].co],
        "bezier_segments": path.segment_count,
        "export_stations": export_count,
        "export_spacing_m": round(path.length / (export_count - 1), 6),
    }
