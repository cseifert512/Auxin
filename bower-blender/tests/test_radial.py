"""The regular six-bay design: every bay the same, and each its own mirror image.

design/six_bay_radial.json is the six-bay room with its piers on one circle about the crown,
equal bays and one apex height. No Blender needed: python tests/test_radial.py
"""
import math
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import topology as T  # noqa: E402
from bower.joints import find_joints, joint_rows  # noqa: E402
from bower.snapshot import centrelines  # noqa: E402
from bower.timber import build_design_timber  # noqa: E402

DESIGN = T.load(REPO / "design" / "six_bay_radial.json")
ROOM = DESIGN["rooms"][0]
CENTRE = ROOM["crown"]["centre_m"]
BEARINGS = [math.degrees(math.atan2(p["position_m"][1] - CENTRE[1], p["position_m"][0] - CENTRE[0])) for p in ROOM["piers"]]
TURN = 360.0 / len(ROOM["bays"])
BAY_AXIS = BEARINGS[0] + TURN / 2.0  # from the crown out through the middle of the first bay
TWIN_WITHIN_M = 0.01  # what is left is millimetres: pier positions are rounded to the millimetre


def _turned(p, deg):
    a = math.radians(deg)
    x, y = p[0] - CENTRE[0], p[1] - CENTRE[1]
    return (CENTRE[0] + x * math.cos(a) - y * math.sin(a), CENTRE[1] + x * math.sin(a) + y * math.cos(a), p[2])


def _mirrored(p, deg):
    """In the vertical plane through the crown's axis along bearing `deg`."""
    a = math.radians(deg)
    x, y = p[0] - CENTRE[0], p[1] - CENTRE[1]
    along, across = x * math.cos(a) + y * math.sin(a), x * math.sin(a) - y * math.cos(a)
    return (CENTRE[0] + along * math.cos(a) - across * math.sin(a), CENTRE[1] + along * math.sin(a) + across * math.cos(a), p[2])


def _to_line(p, line) -> float:
    best = 1e9
    for a, b in zip(line, line[1:]):
        ab = [b[i] - a[i] for i in range(3)]
        t = min(1.0, max(0.0, sum((p[i] - a[i]) * ab[i] for i in range(3)) / max(sum(c * c for c in ab), 1e-18)))
        best = min(best, math.dist(p, [a[i] + ab[i] * t for i in range(3)]))
    return best


def _furthest_from_a_twin(move) -> tuple[float, str]:
    """Move every member and find the member of its family it then lies along: the worst distance left, and whose."""
    members = centrelines(DESIGN, spacing=0.25)["members"]
    families = defaultdict(list)
    for m in members:
        families[m["family"]].append(m)
    worst = (0.0, "")
    for m in members:
        moved = [move(p) for p in m["points_m"]]
        best = 1e9
        for other in families[m["family"]]:
            line = other["points_m"]
            if not m["closed"]:  # only members whose ends fall together can be twins
                ends = min(max(math.dist(moved[0], line[0]), math.dist(moved[-1], line[-1])), max(math.dist(moved[0], line[-1]), math.dist(moved[-1], line[0])))
                if ends > 0.25:
                    continue
            best = min(best, max(max(_to_line(p, line) for p in moved), max(_to_line(q, moved) for q in line)))
        worst = max(worst, (best, m["id"]))
    return worst


def test_the_ring_is_what_its_layout_says_and_is_regular():
    assert T.reconcile(DESIGN)[1] == []
    assert len(ROOM["piers"]) == len(ROOM["bays"]) == 6
    radii = [math.dist(p["position_m"], CENTRE) for p in ROOM["piers"]]
    assert max(radii) - min(radii) < 0.001
    for one, other in zip(BEARINGS, BEARINGS[1:] + BEARINGS[:1]):
        assert abs((other - one) % 360.0 - TURN) < 0.01
    assert len({b["apex_height_m"] for b in ROOM["bays"]}) == 1
    assert all(b["apex_shift"] == 0.0 and b["apex_out_m"] == 0.0 for b in ROOM["bays"])


def test_every_bay_is_the_next_one_turned():
    distance, member = _furthest_from_a_twin(lambda p: _turned(p, TURN))
    assert distance < TWIN_WITHIN_M, (member, distance)


def test_each_bay_is_its_own_mirror_image():
    for axis in (BAY_AXIS, BEARINGS[0]):  # through the middle of a bay, and through a pier
        distance, member = _furthest_from_a_twin(lambda p: _mirrored(p, axis))
        assert distance < TWIN_WITHIN_M, (member, distance)


def test_the_lattice_meets_every_half_arch_the_same_way():
    met = defaultdict(list)  # arch half -> how far from the apex each lattice member is housed into it
    for group in build_design_timber(DESIGN):
        for row in joint_rows(find_joints(group["members"], DESIGN["timber"])[0]):
            pair = (row["member_a"], row["member_b"])
            arch = next((i for i in pair if ".arch." in i), None)
            other = next((i for i in pair if i != arch), "")
            if arch and other.split(".")[1:2] in (["rib"], ["fill"], ["fine"]):
                apex = T.apex_point(ROOM, T.get_bay(ROOM, arch.rsplit(".arch.", 1)[0]))
                met[arch].append(math.dist((row["x_m"], row["y_m"], row["z_m"]), apex))
    assert len(met) == 12
    first = sorted(next(iter(met.values())))
    assert len(first) >= 4
    for arch, distances in met.items():
        assert len(distances) == len(first), arch
        assert max(abs(a - b) for a, b in zip(sorted(distances), first)) < 0.005, arch


def _timber_without(*keys):
    return {**DESIGN["timber"], "joints": {k: v for k, v in DESIGN["timber"]["joints"].items() if k not in keys}}


def test_a_lap_a_planting_reached_is_cut_splayed_and_no_other_joint_changes():
    """timber.joints.reached_by_plants names joints by their IDs, and plant_detail says how a lap among them is cut.

    A named lap is opened at each of its eight mouths and says so. A named joint of another kind is
    noted as still wanting a detail. Every joint the planting did not name is cut as it was.
    """
    told = DESIGN["timber"]["joints"]["reached_by_plants"]["joints"]
    assert DESIGN["timber"]["joints"]["plant_detail"]["type"] == "splayed"
    seen = set()
    for group in build_design_timber(DESIGN):
        now, _, cutters = find_joints(group["members"], DESIGN["timber"])
        was, _, cutters_was = find_joints(group["members"], _timber_without("reached_by_plants", "plant_detail"))
        assert [j.id for j in now] == [j.id for j in was]
        opened = defaultdict(int)  # member -> openings cut into it
        for a, b in zip(now, was):
            if a.id not in told:
                assert (a.cuts, a.review) == (b.cuts, b.review), a.id
                continue
            seen.add(a.id)
            assert "a clinging plant reaches this joint" in a.review, a.id
            if a.kind == "cross_lap":
                assert "cut as a splayed lap" in a.review, a.id
                for member in a.members:
                    opened[member] += 4  # two walls, each opened toward both sides of the member
            else:
                assert "not designed" in a.review and a.cuts == b.cuts, a.id
        for member in {m.id for m in group["members"]}:
            assert len(cutters.get(member, [])) - len(cutters_was.get(member, [])) == opened[member], member
    assert seen == set(told)  # every joint the planting named is still a joint of this design


def test_without_a_detail_a_reached_joint_is_noted_and_cut_as_before():
    for group in build_design_timber(DESIGN):
        noted, _, cutters = find_joints(group["members"], _timber_without("plant_detail"))
        was, _, cutters_was = find_joints(group["members"], _timber_without("reached_by_plants", "plant_detail"))
        assert [(j.id, j.cuts) for j in noted] == [(j.id, j.cuts) for j in was]
        assert {k: len(v) for k, v in cutters.items()} == {k: len(v) for k, v in cutters_was.items()}
        assert sum("which is not designed" in j.review for j in noted) == len(DESIGN["timber"]["joints"]["reached_by_plants"]["joints"])


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"{len(tests)} passed")
