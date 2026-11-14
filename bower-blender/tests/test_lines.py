"""Checks on the training lines (bower/lines.py). No Blender needed: python tests/test_lines.py"""
import copy
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import topology as T  # noqa: E402
from bower.centreline import add, dot, mul, norm, sub  # noqa: E402
from bower.joints import find_joints, joint_rows  # noqa: E402
from bower.lines import DEFAULTS, MIN_SPACING_M, _floor, check_lines, design_lines, line_rows, on_floor, settings, standoff_joints, training_lines  # noqa: E402
from bower.timber import build_design_timber  # noqa: E402

NOW = T.load(REPO / "design.json")  # the design as it stands
SIX = T.load(REPO.parent / "releases" / "six-bay-v1" / "design.json")  # a frozen design, made before there were lines
PAIR = T.load(REPO / "design" / "two_rooms.json")  # two rooms joined through a bay
LATTICE_LEGS = ("rib", "fill", "fine", "hoop")

_BUILT = {}


def built(design):
    """The members and joints of a design whose rooms are all one group, built once."""
    if id(design) not in _BUILT:
        groups = build_design_timber(design)
        assert len(groups) == 1
        members = groups[0]["members"]
        _BUILT[id(design)] = (members, find_joints(members, design["timber"])[0], groups[0]["room_of"])
    return _BUILT[id(design)]


def strung(design, **own):
    """The lines of a design under the default settings with `own` laid over them, whatever the design file asks for."""
    members, joints, _ = built(design)
    timber = {**design["timber"], "training_lines": dict(own)}
    return training_lines(members, timber, joints), members, timber


def grounded(members, families=LATTICE_LEGS):
    floor = _floor(members)
    return [m for m in members if m.family in families and any(on_floor(m, floor))]


def course(member, line, s):
    """The point of the line's course at a station of its member: the centreline moved off the face by the gap."""
    st = member.path.station_at(s)
    sign = -1.0 if line.face == "outer" else 1.0
    return add(st.point, mul(st.depth_axis, sign * (member.depth / 2.0 + line.gap_m)))


def away_from_segment(p, a, b) -> float:
    ab, v = sub(b, a), sub(p, a)
    t = min(1.0, max(0.0, dot(v, ab) / dot(ab, ab)))
    return norm(sub(v, mul(ab, t)))


def test_a_design_without_the_block_has_no_lines():
    assert "training_lines" not in SIX["timber"]
    assert settings(SIX["timber"]) is None
    assert design_lines(SIX) == []
    members, joints, _ = built(SIX)
    assert training_lines(members, SIX["timber"], joints) == []


def test_every_lattice_member_that_stands_on_the_floor_carries_one_line_from_the_floor():
    lines, members, timber = strung(NOW)
    cfg, by_id, floor = settings(timber), {m.id: m for m in members}, _floor(members)
    assert sorted(line.member for line in lines) == sorted(m.id for m in grounded(members))
    assert all(line.id == line.member + ".line" for line in lines)  # one each, none cut back
    for line in lines:
        m = by_id[line.member]
        starts, ends = on_floor(m, floor)
        assert starts and abs(line.standoffs[0].head[2] - floor - cfg["foot_clear_m"]) < 1e-3, line.id
        if ends:  # a hoop comes down to the floor again at the next pier
            assert abs(line.standoffs[-1].head[2] - floor - cfg["foot_clear_m"]) < 1e-3, line.id
        else:  # a rib's line stops short of its head, clear of the ring it is let into
            short = m.path.length - line.to_m
            assert cfg["end_clear_m"] - 1e-3 <= short < cfg["end_clear_m"] + 0.6, (line.id, short)


def test_a_line_stands_off_its_member_by_the_gap_and_follows_its_curve():
    lines, members, timber = strung(NOW)
    cfg, by_id = settings(timber), {m.id: m for m in members}
    worst = 0.0
    for line in lines:
        m = by_id[line.member]
        for standoff in line.standoffs:
            st = m.path.station_at(standoff.at_m)
            assert norm(sub(standoff.foot, sub(st.point, mul(st.depth_axis, m.depth / 2.0)))) < 1e-3  # on the outer face, over the centreline
            assert abs(norm(sub(standoff.head, standoff.foot)) - cfg["gap_m"]) < 1e-9
            assert norm(sub(standoff.head, course(m, line, standoff.at_m))) < 1e-3
        for a, b in zip(line.standoffs, line.standoffs[1:]):  # the straight cable against the member's own curve
            count = max(2, math.ceil((b.at_m - a.at_m) / 0.01))
            worst = max(worst, max(away_from_segment(course(m, line, a.at_m + (b.at_m - a.at_m) * i / count), a.head, b.head) for i in range(count + 1)))
    assert worst <= cfg["standoff_sag_m"] + 5e-4, worst
    report = check_lines(lines, members, timber)
    lo, hi = report["gap_to_own_member_m"]
    assert cfg["gap_m"] - cfg["standoff_sag_m"] - 2e-3 <= lo and hi <= cfg["gap_m"] + cfg["standoff_sag_m"] + 5e-3, (lo, hi)


def test_every_cable_keeps_clear_of_every_other_member():
    lines, members, timber = strung(NOW)
    cfg = settings(timber)
    report = check_lines(lines, members, timber)
    assert report["clear_of_other_members"] and report["nearest_other_member_m"]["clear_m"] >= cfg["clear_m"]
    assert report["carriers_without_a_line"] == [] and report["lines_cut_back"] == []
    # The same again by brute force, without the grid lines.py finds its neighbours with: points along
    # every cable against every box of every other member.
    boxes = {}
    for m in members:
        stations = m.path.stations(0.05)
        lo = [min(st.point[k] for st in stations) - 0.4 for k in range(3)]
        hi = [max(st.point[k] for st in stations) + 0.4 for k in range(3)]
        boxes[m.id] = (m, stations, lo, hi)
    nearest = 1.0
    for line in lines:
        for a, b in zip(line.points, line.points[1:]):
            for t in (0.0, 0.5):
                p = add(a, mul(sub(b, a), t))
                for other, (m, stations, lo, hi) in boxes.items():
                    if other == line.member or any(not lo[k] <= p[k] <= hi[k] for k in range(3)):
                        continue
                    for st in stations:
                        v = sub(p, st.point)
                        if dot(v, v) > 0.16:
                            continue
                        x, y, z = abs(dot(v, st.width_axis)) - m.width / 2.0, abs(dot(v, st.depth_axis)) - m.depth / 2.0, abs(dot(v, st.tangent)) - 0.027
                        nearest = min(nearest, math.sqrt(max(x, 0.0) ** 2 + max(y, 0.0) ** 2 + max(z, 0.0) ** 2) if max(x, y, z) > 0.0 else max(x, y, z))
    assert nearest >= cfg["clear_m"], nearest
    assert nearest >= report["nearest_other_member_m"]["clear_m"] - 1e-6  # the grid missed nothing nearer


def test_standoffs_are_spaced_by_the_bend_and_kept_out_of_joints():
    lines, members, timber = strung(NOW)
    cfg, by_id = settings(timber), {m.id: m for m in members}
    _, joints, _ = built(NOW)
    taken = {}
    for joint in joints:
        for cut in joint.cuts:
            if cut.operation == "housing" or (cut.operation == "lap" and cut.face == cfg["face"]):
                taken.setdefault(cut.member, []).append((cut.at_m - cut.length_m / 2.0, cut.at_m + cut.length_m / 2.0))
    count = noted = 0
    for line in lines:
        gaps = [b.at_m - a.at_m for a, b in zip(line.standoffs, line.standoffs[1:])]
        assert MIN_SPACING_M - 1e-6 <= min(gaps) and max(gaps) <= cfg["standoff_spacing_m"] + 1e-6, (line.id, min(gaps), max(gaps))
        for standoff in line.standoffs:
            count += 1
            inside = any(a < standoff.at_m < b for a, b in taken.get(line.member, []))
            assert inside == bool(standoff.note), (line.id, standoff.at_m)  # one that stands in a joint says so
            noted += inside
        if by_id[line.member].family == "rib":  # up the straight leg as far apart as allowed, closer round the roof
            assert abs(gaps[0] - cfg["standoff_spacing_m"]) < 0.051 and min(gaps) < 0.6 * cfg["standoff_spacing_m"], (line.id, gaps)
    assert noted <= 0.02 * count, (noted, count)
    report = check_lines(lines, members, timber)
    assert report["standoffs"] == count and report["standoffs_in_a_joint"] == noted


def test_gap_face_and_which_members_carry_a_line_are_settings():
    members, joints, _ = built(NOW)
    by_id = {m.id: m for m in members}
    wide, _, timber = strung(NOW, gap_m=0.12)
    assert all(abs(norm(sub(s.head, s.foot)) - 0.12) < 1e-9 for line in wide for s in line.standoffs)
    assert check_lines(wide, members, timber)["clear_of_other_members"]
    inner, _, timber = strung(NOW, face="inner")
    for line in inner:  # on the room's side of the member
        m = by_id[line.member]
        assert all(dot(sub(s.head, m.path.station_at(s.at_m).point), m.path.station_at(s.at_m).depth_axis) > m.depth / 2.0 for s in line.standoffs[::5])
    assert check_lines(inner, members, timber)["clear_of_other_members"]
    assert strung(NOW, carry="none")[0] == []
    every, _, timber = strung(NOW, carry="all")
    report = check_lines(every, members, timber)
    assert report["clear_of_other_members"]
    open_lattice = [m.id for m in members if m.family in LATTICE_LEGS]
    assert {line.member for line in every} | set(report["carriers_without_a_line"]) == set(open_lattice)
    assert len(report["carriers_without_a_line"]) <= 3  # a member too short to be worth a line has none
    # one arch, named: its line is cut back to where the two arches of the pier have parted
    arch = next(m for m in members if m.family == "arch")
    named, _, timber = strung(NOW, carry="none", members=[arch.id])
    assert [line.member for line in named] == [arch.id] and named[0].review.startswith("cut back") and named[0].from_m > 1.0
    assert check_lines(named, members, timber)["clear_of_other_members"]
    hoop = next(m for m in members if m.family == "hoop")
    assert hoop.id not in {line.member for line in strung(NOW, without=[hoop.id])[0]}


def test_settings_that_make_no_sense_are_refused():
    for own in ({"carry": "some"}, {"face": "side"}, {"families": ["crown"]}, {"gap": 0.1}, {"gap_m": 0.0}, {"clear_m": 0.2}):
        try:
            settings({"training_lines": own})
        except T.DesignError:
            continue
        raise AssertionError(f"{own} was accepted")
    design = copy.deepcopy(NOW)
    design["timber"]["training_lines"] = {"members": ["R1.no.such.member"]}
    try:
        design_lines(design, build_design_timber(NOW))
    except T.DesignError:
        return
    raise AssertionError("a line on a member the design does not have was accepted")


def test_standoffs_enter_the_joint_schedule_and_lines_have_a_schedule_of_their_own():
    lines, members, timber = strung(NOW)
    cfg = settings(timber)
    _, joints, _ = built(NOW)
    holes = joint_rows(standoff_joints(lines, timber))
    assert len(holes) == sum(len(line.standoffs) for line in lines)
    assert list(holes[0]) == list(joint_rows(joints)[0])  # the same columns as any other joint
    assert all(row["kind"] == "standoff" and row["a_operation"] == "drill" and row["a_face"] == cfg["face"] and row["a_depth_m"] == cfg["hole_depth_m"] for row in holes)
    assert len({row["id"] for row in holes}) == len(holes)
    piers = {p["id"]: p["position_m"] for room in NOW["rooms"] for p in room["piers"]}
    rows = line_rows(lines, members, piers)
    assert [row["id"] for row in rows] == [line.id for line in lines]
    assert all(row["start_pier"] in piers for row in rows)  # every line starts at a pier
    hoops = [row for row in rows if row["family"] == "hoop"]
    assert hoops and all(row["end_pier"] in piers and row["end_pier"] != row["start_pier"] for row in hoops)  # and a hoop's ends at the next
    assert abs(sum(row["cable_length_m"] for row in rows) - sum(line.length_m for line in lines)) < 0.05


def test_lines_regenerate_with_the_building():
    before, members, timber = strung(NOW)
    top = {line.id: line.standoffs[-1].head[2] for line in before}
    raised = T.set_crown(NOW, "R1", height_m=NOW["rooms"][0]["crown"]["height_m"] + 0.5)[0]
    after, new_members, new_timber = strung(raised)
    assert sorted(line.member for line in after) == sorted(m.id for m in grounded(new_members))
    report = check_lines(after, new_members, new_timber)
    assert report["clear_of_other_members"] and report["lines_from_the_floor"] == len(after)
    shared = [line for line in after if line.id in top]
    assert len(shared) >= 0.8 * len(before)  # the same lines, by ID, on the same members
    ribs = [line for line in shared if ".rib." in line.id]
    assert ribs and all(0.4 < line.standoffs[-1].head[2] - top[line.id] < 0.6 for line in ribs)  # their heads went up with the crown


def test_the_frozen_six_bay_room_and_the_joined_rooms_take_lines_too():
    lines, members, timber = strung(SIX)
    families = sorted(m.family for m in grounded(members))
    assert len(lines) == len(families) == 28 and (families.count("rib"), families.count("fill"), families.count("hoop")) == (6, 10, 12)
    report = check_lines(lines, members, timber)
    assert report["clear_of_other_members"] and report["lines_from_the_floor"] == 28
    lines, members, timber = strung(PAIR)
    _, _, room_of = built(PAIR)
    assert {room_of[line.member] for line in lines} == {"R1", "R2"}
    assert sorted(line.member for line in lines) == sorted(m.id for m in grounded(members))
    report = check_lines(lines, members, timber)
    assert report["clear_of_other_members"] and report["lines_cut_back"] == []


def test_the_design_as_it_stands_strings_its_lines_clear():
    for group in design_lines(NOW):  # with whatever design.json asks for
        if group["lines"]:
            report = check_lines(group["lines"], group["members"], NOW["timber"])
            assert report["clear_of_other_members"], report["nearest_other_member_m"]
            assert sum(len(line.standoffs) for line in group["lines"]) == report["standoffs"]
    assert set(NOW["timber"].get("training_lines", {})) - {"note"} <= set(DEFAULTS)


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"{len(tests)} passed")
