"""Geometry checks for the Gate 0 member. No Blender needed: python tests/test_gate0_geometry.py"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower.centreline import cross, dot, norm, sub  # noqa: E402
from bower.member import member_from_spec, sweep  # noqa: E402

DESIGN = json.loads((REPO / "design" / "gate0_member.json").read_text(encoding="utf-8"))
SPEC = DESIGN["members"][0]
MEMBER = member_from_spec(SPEC)
STATIONS = MEMBER.path.stations(DESIGN["sampling"]["mesh_station_spacing_m"])


def test_length_and_radius_match_the_spec():
    arc = SPEC["centreline"]
    assert abs(MEMBER.path.length - arc["length_m"]) < 1e-5
    radius, _ = MEMBER.path.min_bend_radius()
    assert abs(radius - arc["radius_m"]) < 1e-3


def test_ends_are_where_the_arc_formula_puts_them():
    arc = SPEC["centreline"]
    r, sweep_angle = arc["radius_m"], arc["length_m"] / arc["radius_m"]
    x0, y0, z0 = arc["start_m"]
    expected_end = (x0 + r * (1 - math.cos(sweep_angle)), y0, z0 + r * math.sin(sweep_angle))
    assert norm(sub(STATIONS[0].point, tuple(arc["start_m"]))) < 1e-9
    assert norm(sub(STATIONS[-1].point, expected_end)) < 1e-6


def test_stations_are_evenly_spaced_within_the_limit():
    spacing = DESIGN["sampling"]["mesh_station_spacing_m"]
    steps = [b.s - a.s for a, b in zip(STATIONS, STATIONS[1:])]
    assert max(steps) <= spacing * (1 + 1e-6)
    assert max(steps) - min(steps) < 1e-9
    assert abs(STATIONS[-1].s - MEMBER.path.length) < 1e-12


def test_frames_are_orthonormal_and_depth_points_at_the_arc_centre():
    arc = SPEC["centreline"]
    centre = (arc["start_m"][0] + arc["radius_m"], arc["start_m"][1], arc["start_m"][2])
    for st in STATIONS:
        for axis in (st.tangent, st.depth_axis, st.width_axis):
            assert abs(norm(axis) - 1.0) < 1e-9
        assert abs(dot(st.tangent, st.depth_axis)) < 1e-9
        assert norm(sub(cross(st.width_axis, st.depth_axis), st.tangent)) < 1e-9
        to_centre = sub(centre, st.point)
        assert dot(st.depth_axis, to_centre) / norm(to_centre) > 1 - 1e-6


def test_swept_mesh_is_closed_outward_facing_and_the_right_volume():
    verts, faces = sweep(MEMBER, STATIONS)
    edge_use = Counter()
    for face in faces:
        for a, b in zip(face, face[1:] + face[:1]):
            edge_use[(a, b)] += 1
    assert all(edge_use[(b, a)] == 1 and n == 1 for (a, b), n in edge_use.items())
    volume = 0.0
    for face in faces:
        for i in range(1, len(face) - 1):
            volume += dot(verts[face[0]], cross(verts[face[i]], verts[face[i + 1]])) / 6.0
    exact = MEMBER.width * MEMBER.depth * MEMBER.path.length
    assert volume > 0
    assert abs(volume - exact) / exact < 1e-3


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"{len(tests)} passed; length = {MEMBER.path.length:.6f} m, stations = {len(STATIONS)}")
