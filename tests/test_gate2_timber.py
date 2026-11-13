"""Primary timber checks for the Gate 2 room. No Blender needed: python tests/test_gate2_timber.py"""
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import topology as T  # noqa: E402
from bower.centreline import cross, dot, norm, sub, unit  # noqa: E402
from bower.envelope import boundary  # noqa: E402
from bower.timber import build_timber, clearances, schedule  # noqa: E402

BASE = T.load(REPO / "design.json")


def timber(design):
    return build_timber(design["rooms"][0], design["timber"])


def shapes(members):
    """Each member's exact control geometry, for testing that an edit left it untouched."""
    return {m.id: tuple((a.co, a.handle_left, a.handle_right) for a in m.path.anchors) for m in members}


def owner(member):
    """The bay or pier a member is generated for."""
    return member.parent


MEMBERS = timber(BASE)
BY_ID = {m.id: m for m in MEMBERS}


def test_every_pier_and_bay_gets_its_members_once():
    room = BASE["rooms"][0]
    assert len(BY_ID) == len(MEMBERS) == 54
    assert Counter(m.family for m in MEMBERS) == {"arch": 12, "sweep": 12, "lierne": 12, "groin": 6, "ridge": 6, "crown": 6}
    for pier in room["piers"]:
        assert pier["id"] + ".groin" in BY_ID
    for bay in room["bays"]:
        for part in ("arch.L", "arch.R", "ridge", "sweep.L", "sweep.R", "lierne.L", "lierne.R", "crown"):
            assert f"{bay['id']}.{part}" in BY_ID


def test_every_member_is_planar_with_a_sound_section_frame():
    for m in MEMBERS:
        stations = m.path.stations(0.1)
        a, b, c = stations[0].point, stations[len(stations) // 2].point, stations[-1].point
        normal = cross(sub(b, a), sub(c, a))
        # A straight member has no plane of its own; any plane through it will do.
        if norm(normal) > 1e-6:
            normal = unit(normal)
            assert max(abs(dot(sub(s.point, a), normal)) for s in stations) < 1e-6, f"{m.id} is not planar"
        for s in stations:
            assert abs(norm(s.depth_axis) - 1) < 1e-9 and abs(dot(s.tangent, s.depth_axis)) < 1e-9
            assert norm(sub(cross(s.width_axis, s.depth_axis), s.tangent)) < 1e-9


def test_members_meet_at_the_nodes_they_name():
    nodes, _ = boundary(BASE["rooms"][0])
    ends = {m.id: (m.path.anchors[0].co, m.path.anchors[-1].co) for m in MEMBERS}
    for m in MEMBERS:
        start, end = ends[m.id]
        if m.family == "arch":
            assert norm(sub(end, nodes[m.nodes[-1]])) < 1e-9  # the two halves meet exactly at the apex
            assert abs(start[2]) < 1e-9  # and stand on the floor
        if m.family in ("ridge", "lierne"):
            assert norm(sub(start, nodes[m.nodes[0]])) < 0.35  # beside the apex, at the arch's inner face
        if m.family in ("groin", "ridge"):
            assert norm(sub(end, nodes[m.nodes[-1]])) < 0.1  # stops at the outer face of the crown ring
        if m.family == "crown":
            assert norm(sub(start, nodes[m.nodes[0]])) < 1e-6 and norm(sub(end, nodes[m.nodes[-1]])) < 1e-4
    for bay in BASE["rooms"][0]["bays"]:
        ridge = BY_ID[bay["id"] + ".ridge"]
        for side in "LR":
            sweep_end = ends[f"{bay['id']}.sweep.{side}"][1]
            assert min(norm(sub(s.point, sweep_end)) for s in ridge.path.stations(0.05)) < 0.2  # at the ridge's side face


def test_nothing_collides_and_each_lierne_rests_on_its_sweep():
    report = clearances(MEMBERS)
    assert report["collisions"] == []
    laps = {frozenset((p["a"], p["b"])): p["gap_m"] for p in report["close"]}
    for bay in BASE["rooms"][0]["bays"]:
        for side in "LR":
            pair = frozenset((f"{bay['id']}.lierne.{side}", f"{bay['id']}.sweep.{side}"))
            assert pair in laps and 0 <= laps[pair] < 0.06, f"{sorted(pair)} do not lap"


def test_bend_radii_stay_above_the_floor_this_design_was_tuned_to():
    rows = {r["id"]: r for r in schedule(MEMBERS, BASE["timber"], clearances(MEMBERS))}
    for m in MEMBERS:
        radius = rows[m.id]["min_bend_radius_m"]
        if m.family == "crown":
            assert abs(radius - BASE["rooms"][0]["crown"]["radius_m"]) < 0.01  # the ring is as tight as its radius
        elif m.family == "lierne":
            assert radius == "" or radius >= 1.8
        else:
            assert radius >= 3.0, f"{m.id}: {radius} m"


def assert_regenerates(edited, changed_owners):
    """The edited room builds, nothing collides, and members owned elsewhere are exactly as they were."""
    members = timber(edited)
    room = edited["rooms"][0]
    assert len(members) == 8 * len(room["bays"]) + len(room["piers"])
    assert clearances(members)["collisions"] == []
    before, after = shapes(MEMBERS), shapes(members)
    for m in members:
        if m.id in before and owner(m) not in changed_owners:
            assert after[m.id] == before[m.id], f"{m.id} changed although {owner(m)} was not edited"
    return members


def test_moving_a_pier_regenerates_only_what_stands_on_it_or_its_bays():
    edited, change = T.move_pier(BASE, "R1.P3", [5.9, 0.3])
    assert_regenerates(edited, set(change["modified"]))


def test_crown_height_regenerates_every_member_that_reaches_it():
    edited, _ = T.set_crown(BASE, "R1", height_m=7.2)
    room = edited["rooms"][0]
    members = assert_regenerates(edited, {e["id"] for e in room["piers"] + room["bays"]})
    assert max(a.co[2] for m in members for a in m.path.anchors) == 7.2


def test_adding_a_bay_adds_its_members_and_leaves_the_others():
    edited, change = T.add_bay(BASE, "R1.B1")
    members = assert_regenerates(edited, set(change["modified"]) | set(change["added"]))
    new = {m.id for m in members} - set(BY_ID)
    assert new == {"R1.P7.groin"} | {f"R1.B7.{part}" for part in ("arch.L", "arch.R", "ridge", "sweep.L", "sweep.R", "lierne.L", "lierne.R", "crown")}


def test_removing_a_bay_removes_its_members_and_leaves_the_others():
    edited, change = T.remove_bay(BASE, "R1.B2")
    members = assert_regenerates(edited, set(change["modified"]))
    gone = set(BY_ID) - {m.id for m in members}
    assert gone == {"R1.P3.groin"} | {f"R1.B2.{part}" for part in ("arch.L", "arch.R", "ridge", "sweep.L", "sweep.R", "lierne.L", "lierne.R", "crown")}


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"{len(tests)} passed")
