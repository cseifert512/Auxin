"""Timber members: a stable ID, a role, a rectangular section and a centreline.

Pure Python (no bpy). The centreline is the member; the swept solid is only a
way of looking at it.
"""
from __future__ import annotations

from dataclasses import dataclass

from .centreline import BezierPath, Station, add, arc_path, mul

ROLES = ("primary", "secondary", "cable")


@dataclass(frozen=True)
class Member:
    id: str
    role: str
    width: float  # m, along the section width axis
    depth: float  # m, along the section depth axis
    path: BezierPath
    parent: str | None = None
    family: str = ""  # arch | groin | ridge | sweep | crown for generated primaries
    nodes: tuple = ()  # named points this member is jointed at, start first and end last


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


def sweep(member: Member, stations: list[Station]):
    """A closed quad mesh of the rectangular section swept through `stations`.

    Four vertices per station, wound so that every face normal points outward.
    """
    hw, hd = member.width / 2.0, member.depth / 2.0
    verts = []
    for st in stations:
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            verts.append(add(st.point, add(mul(st.width_axis, sx * hw), mul(st.depth_axis, sy * hd))))
    faces = []
    for j in range(len(stations) - 1):
        a, b = 4 * j, 4 * j + 4
        for k in range(4):
            k2 = (k + 1) % 4
            faces.append((a + k, a + k2, b + k2, b + k))
    end = 4 * (len(stations) - 1)
    faces.append((3, 2, 1, 0))
    faces.append((end, end + 1, end + 2, end + 3))
    return verts, faces


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
