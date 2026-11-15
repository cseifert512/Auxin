"""Checks on a room that stands on sloping ground (rooms[].piers[].foot_z_m, bower/floor.py) and on training
lines held further off at the foot (timber.training_lines.foot_gap_m). No Blender needed: python tests/test_slope.py"""
import copy
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import ground as G  # noqa: E402
from bower import topology as T  # noqa: E402
from bower.centreline import norm, sub  # noqa: E402
from bower.floor import Floor  # noqa: E402
from bower.joints import find_joints  # noqa: E402
from bower.lines import check_lines, on_floor, settings, training_lines  # noqa: E402
from bower.timber import build_design_timber  # noqa: E402
from bower.topology import DesignError  # noqa: E402

LEVEL = T.load(REPO.parent / "releases" / "six-bay-radial-open-pier" / "design.json")  # a frozen design on level ground
FALL = 0.04  # the ground falls 1 in 25 toward the south-west


def sloping(design=LEVEL, fall=FALL):
    """The same design with each pier's feet on ground that falls to the south-west, the highest pier where it was."""
    out = copy.deepcopy(design)
    piers = out["rooms"][0]["piers"]
    ground = {p["id"]: fall * (p["position_m"][0] + p["position_m"][1]) / math.sqrt(2.0) for p in piers}
    top = max(ground.values())
    for p in piers:
        p["foot_z_m"] = round(ground[p["id"]] - top, 3)
    return out


SLOPE = sloping()
_BUILT = {}


def built(design):
    if id(design) not in _BUILT:
        group = build_design_timber(design)[0]
        joints = find_joints(group["members"], design["timber"])[0]
        _BUILT[id(design)] = (group, joints)
    return _BUILT[id(design)]


def pier_of(design, point):
    return min(design["rooms"][0]["piers"], key=lambda p: math.hypot(p["position_m"][0] - point[0], p["position_m"][1] - point[1]))


def feet(members, floor):
    """Every member end that stands on the floor: (member, which end, its station)."""
    out = []
    for m in members:
        for end, (s, grounded) in enumerate(zip((0.0, m.path.length), on_floor(m, floor))):
            if grounded:
                out.append((m, end, m.path.station_at(s)))
    return out


def test_a_room_that_names_no_foot_levels_is_built_as_before():
    same = copy.deepcopy(LEVEL)
    for p in same["rooms"][0]["piers"]:
        p["foot_z_m"] = same["rooms"][0]["floor_z_m"]  # the room's own level, said aloud
    a, b = built(LEVEL)[0]["members"], build_design_timber(same)[0]["members"]
    assert [m.id for m in a] == [m.id for m in b]
    assert all(m.path.anchors == n.path.anchors for m, n in zip(a, b))
    assert Floor(a).level and Floor(a).at((3.0, 4.0)) == Floor(a) == min(m.path.anchors[0].co[2] for m in a)


def test_every_leg_runs_on_down_to_its_own_piers_level_and_nothing_else_moves():
    flat, slope = built(LEVEL)[0]["members"], built(SLOPE)[0]["members"]
    assert [m.id for m in flat] == [m.id for m in slope]
    floor_flat, floor_slope = Floor(flat), Floor(slope)
    assert not floor_slope.level
    standing = feet(flat, floor_flat)
    assert len(standing) == len(feet(slope, floor_slope)) > 0
    lengthened = 0
    for m, n in zip(flat, slope):
        grounded = on_floor(m, floor_flat)
        if not any(grounded):
            assert n.path.anchors == m.path.anchors  # everything that does not stand on the ground is as it was
            continue
        for end, s in ((0, 0.0), (1, m.path.length)):
            if not grounded[end]:
                continue
            old = m.path.station_at(s)
            level = pier_of(SLOPE, old.point)["foot_z_m"]
            new = n.path.station_at(0.0 if end == 0 else n.path.length)
            assert abs(new.point[2] - level) < 1e-6  # its foot is at its pier's level
            drop = old.point[2] - level
            if drop > 1e-9:
                lengthened += 1
                assert norm(sub(new.tangent, old.tangent)) < 1e-6  # it runs on the way it already stood
                assert abs(norm(sub(new.point, old.point)) - drop / abs(old.tangent[2])) < 1e-6
        # and above the old feet the member is where it was
        shift = norm(sub(n.path.station_at(0.0).point, m.path.station_at(0.0).point))  # how far its start has run on
        for k in range(1, 8):
            s = m.path.length * k / 8.0
            assert norm(sub(n.path.station_at(s + shift).point, m.path.station_at(s).point)) < 2e-3, (m.id, k)
    assert lengthened > 0


def test_a_base_joint_is_found_at_every_foot_whatever_its_level():
    flat = [j.id for j in built(LEVEL)[1] if j.kind == "base"]
    slope = {j.id: j for j in built(SLOPE)[1] if j.kind == "base"}
    assert sorted(flat) == sorted(slope) and flat
    for joint in slope.values():
        assert abs(joint.at_m[2] - pier_of(SLOPE, joint.at_m)["foot_z_m"]) < 1e-3
    kinds = lambda joints, scarf: sorted((j.kind, j.members) for j in joints if (j.kind == "scarf") == scarf)  # noqa: E731
    assert kinds(built(LEVEL)[1], False) == kinds(built(SLOPE)[1], False)  # the same joints between the same members
    # A longer leg may take a member past the longest piece that can be made, and then it is spliced once more.
    was, now = kinds(built(LEVEL)[1], True), kinds(built(SLOPE)[1], True)
    assert all(now.count(j) >= was.count(j) for j in set(was)) and len(was) <= len(now) <= len(was) + 12


def test_training_lines_start_the_same_height_above_each_piers_own_feet():
    timber = {**SLOPE["timber"], "training_lines": {}}
    group, joints = built(SLOPE)
    lines = training_lines(group["members"], timber, joints)
    flat = training_lines(built(LEVEL)[0]["members"], {**LEVEL["timber"], "training_lines": {}}, built(LEVEL)[1])
    assert len(lines) == len(flat)
    report, was = check_lines(lines, group["members"], timber), check_lines(flat, built(LEVEL)[0]["members"], {**LEVEL["timber"], "training_lines": {}})
    assert report["lines_from_the_floor"] == was["lines_from_the_floor"] > 0
    # the upper pieces of a line that is cut back are where they were on the roof, so they start higher above ground that has fallen away
    drop = -min(p.get("foot_z_m", 0.0) for p in SLOPE["rooms"][0]["piers"])
    assert was["highest_start_above_floor_m"] <= report["highest_start_above_floor_m"] <= was["highest_start_above_floor_m"] + drop + 0.05


def test_a_foot_level_above_the_rooms_floor_is_refused():
    high = copy.deepcopy(LEVEL)
    high["rooms"][0]["piers"][0]["foot_z_m"] = 0.2
    try:
        build_design_timber(high)
    except DesignError as error:
        assert "lengthened, not shortened" in str(error)
    else:
        raise AssertionError("a foot above the floor was accepted")


def test_a_cable_can_stand_further_off_at_the_foot_and_come_in_as_it_climbs():
    group, joints = built(SLOPE)
    by_id = {m.id: m for m in group["members"]}
    plain = training_lines(group["members"], {**SLOPE["timber"], "training_lines": {}}, joints)
    again = training_lines(group["members"], {**SLOPE["timber"], "training_lines": {"foot_gap_m": None}}, joints)
    assert [line.points for line in plain] == [line.points for line in again]  # unasked for, nothing changes
    own = {"foot_gap_m": 0.2, "foot_taper_m": 2.0}
    wide = training_lines(group["members"], {**SLOPE["timber"], "training_lines": own}, joints)
    cfg, floor = settings({"training_lines": own}), Floor(group["members"])
    checked = 0
    for line in wide:
        m = by_id[line.member]
        grounded = on_floor(m, floor)
        for standoff in line.standoffs:
            out = norm(sub(standoff.head, standoff.foot))
            from_foot = min(standoff.at_m if grounded[0] else math.inf, m.path.length - standoff.at_m if grounded[1] else math.inf)
            want = cfg["gap_m"] + (0.2 - cfg["gap_m"]) * max(0.0, 1.0 - from_foot / 2.0)
            assert abs(out - want) < 1e-4, (line.id, standoff.at_m, out, want)  # a standoff's station is written to a tenth of a millimetre
            checked += from_foot < 2.0
    assert checked > 0
    for own in ({"foot_gap_m": 0.05}, {"foot_gap_m": 0.2, "foot_taper_m": 0.0}):
        try:
            settings({"training_lines": own})
        except DesignError:
            continue
        raise AssertionError(f"accepted {own}")


def test_the_ground_at_a_pier_is_set_out_at_that_piers_level():
    group, joints = built(SLOPE)
    timber = {**SLOPE["timber"], "training_lines": {}}
    lines = training_lines(group["members"], timber, joints)
    planted = {**SLOPE, "timber": timber}
    zones = [z for p in SLOPE["rooms"][0]["piers"] for z in G.beside_pier(planted, group, p["id"])]
    laid = G.lay({**planted, "ground": {"root_zones": zones}}, group, joints, lines)
    flat_group, flat_joints = built(LEVEL)
    flat_timber = {**LEVEL["timber"], "training_lines": {}}
    flat_lines = training_lines(flat_group["members"], flat_timber, flat_joints)
    flat_planted = {**LEVEL, "timber": flat_timber}
    flat_zones = [z for p in LEVEL["rooms"][0]["piers"] for z in G.beside_pier(flat_planted, flat_group, p["id"])]
    flat = G.lay({**flat_planted, "ground": {"root_zones": flat_zones}}, flat_group, flat_joints, flat_lines)
    assert len(laid["footings"]) == len(flat["footings"]) == 6
    assert len(laid["feeders"]) == len(flat["feeders"]) and len(laid["handovers"]) == len(flat["handovers"])
    # A hand-over is made at the same place on the roof, so it is higher above ground that has fallen away: by no more than the longest leg has grown.
    drop = -min(p.get("foot_z_m", 0.0) for p in SLOPE["rooms"][0]["piers"])
    (lo, hi), (was_lo, was_hi) = laid["report"]["handover_height_m"], flat["report"]["handover_height_m"]
    assert was_lo - 0.05 <= lo <= was_lo + drop + 0.05 and was_hi - 0.05 <= hi <= was_hi + drop + 0.05, (lo, hi, was_lo, was_hi)


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(f"{len(tests)} passed")
