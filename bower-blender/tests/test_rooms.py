"""Checks on rooms joined to rooms: the shared arch, the shared piers, and each room staying its own. No Blender needed: python tests/test_rooms.py"""
import copy
import math
import runpy
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import topology as T  # noqa: E402
from bower.envelope import build_envelope, check_connections, check_envelope  # noqa: E402
from bower.joints import find_joints  # noqa: E402
from bower.snapshot import centrelines, schedules  # noqa: E402
from bower.timber import build_design_timber, build_timber, clearances, room_timber  # noqa: E402

SCRIPT = runpy.run_path(str(REPO / "scripts" / "gate3_rooms.py"))
FORMS = runpy.run_path(str(REPO / "scripts" / "gate2_forms.py"))
NOW = T.load(REPO / "design.json")
PAIR = SCRIPT["joined"](NOW)
HOST, PORTAL = "R1.B3", "R2.B1"  # the bay the second room is grown out of, and the same opening seen from the second room
(GROUP,) = build_design_timber(PAIR)
MEMBERS = {m.id: m for m in GROUP["members"]}
JOINTS, _, CUTTERS = find_joints(GROUP["members"], PAIR["timber"])


def rejected(action) -> bool:
    try:
        action()
    except T.DesignError:
        return True
    return False


def place(design, pier_id):
    return T.find(design, "piers", pier_id)[1]["position_m"]


def apex(design, bay_id):
    return T.apex_point(*T.find(design, "bays", bay_id))


def test_a_room_grown_out_of_a_bay_shares_its_piers_and_its_arch():
    first, second = PAIR["rooms"]
    assert (first["id"], second["id"]) == ("R1", "R2") and PAIR["connections"] == [{"id": "C1", "bays": [HOST, PORTAL]}]
    assert T.get_bay(first, HOST)["type"] == T.get_bay(second, PORTAL)["type"] == "portal"
    assert sum(bay["type"] == "portal" for room in PAIR["rooms"] for bay in room["bays"]) == 2
    host, portal = T.get_bay(first, HOST), T.get_bay(second, PORTAL)
    assert place(PAIR, host["from"]) == place(PAIR, portal["to"]) and place(PAIR, host["to"]) == place(PAIR, portal["from"])  # the two rings run opposite ways
    assert math.dist(apex(PAIR, HOST), apex(PAIR, PORTAL)) < 1e-9
    assert T.same_piers(PAIR) == {host["from"]: host["from"], portal["to"]: host["from"], host["to"]: host["to"], portal["from"]: host["to"]}
    assert T.joined_rooms(PAIR) == [["R1", "R2"]] and T.joined_rooms(NOW) == [["R1"]]
    # the first room is the room it was: only the bay's type has changed, and its ring is now edited bay by bay
    was, now = NOW["rooms"][0], copy.deepcopy(first)
    T.get_bay(now, HOST)["type"] = "open"
    assert {k: v for k, v in now.items() if k != "layout"} == {k: v for k, v in was.items() if k != "layout"} and first["layout"] == {"bays": 8}
    # the second room is a whole room of its own, smaller, on the far side of the arch
    assert len(second["bays"]) == 6 and second["crown"]["radius_m"] < first["crown"]["radius_m"] and second["crown"]["height_m"] < first["crown"]["height_m"]
    mid, _, outward, _ = T.chord_frame(first, host)
    assert all((p["position_m"][0] - mid[0]) * outward[0] + (p["position_m"][1] - mid[1]) * outward[1] > 1.0 for p in second["piers"][2:])
    for room in PAIR["rooms"]:
        assert check_envelope(build_envelope(room, PAIR["sampling"]))["ok"], room["id"]


def test_joined_rooms_are_held_to_one_arch():
    def broken(change) -> bool:
        design = copy.deepcopy(PAIR)
        change(design)
        return rejected(lambda: T.validate(design))

    assert broken(lambda d: d["rooms"][1]["piers"][0]["position_m"].__setitem__(0, 6.5))  # a shared pier moved in one room only
    assert broken(lambda d: T.get_bay(d["rooms"][1], PORTAL).__setitem__("apex_height_m", 4.9))  # the apex raised on one side only
    assert broken(lambda d: d["rooms"][1]["shape"].__setitem__("arch_shoulder", 0.55))  # a different arch on one side
    assert broken(lambda d: T.get_bay(d["rooms"][1], "R2.B3").__setitem__("type", "portal"))  # a portal to nowhere
    assert broken(lambda d: T.get_bay(d["rooms"][0], HOST).__setitem__("type", "open"))
    assert broken(lambda d: d["connections"].append({"id": "C2", "bays": [HOST, "R2.B4"]}))  # one bay, two rooms
    assert rejected(lambda: T.add_room_from_bay(PAIR, HOST))  # already a portal
    assert rejected(lambda: T.add_room_from_bay(NOW, HOST, radius_m=2.0))  # too small a circle to pass through both piers
    assert rejected(lambda: T.add_room_from_bay(NOW, HOST, shape={"pier_height_m": 2.2}))  # the new room cannot have its own arch curve
    assert rejected(lambda: T.add_bay(PAIR, HOST)) and rejected(lambda: T.remove_bay(PAIR, HOST)) and rejected(lambda: T.add_bay(PAIR, PORTAL))
    assert rejected(lambda: T.set_bay_count(PAIR, "R1", 9))  # the first room's ring is tied to its neighbour


def test_a_shared_pier_and_a_shared_apex_move_in_both_rooms():
    host, portal = T.get_bay(PAIR["rooms"][0], HOST), T.get_bay(PAIR["rooms"][1], PORTAL)
    x, y = place(PAIR, host["to"])
    for moved_as in (host["to"], portal["from"]):  # by either of its two names
        moved, change = T.move_pier(PAIR, moved_as, [x + 0.3, y + 0.25])
        assert place(moved, host["to"]) == place(moved, portal["from"]) == [x + 0.3, y + 0.25]
        assert {host["to"], portal["from"], HOST, PORTAL} <= set(change["modified"]) and len(change["modified"]) == 6
        assert math.dist(apex(moved, HOST), apex(moved, PORTAL)) < 1e-9 and check_connections(moved)[0]["one_arch"]
    raised, change = T.set_apex(PAIR, HOST, height_m=4.9, shift=0.1)
    assert change["modified"] == [HOST, PORTAL] and math.dist(apex(raised, HOST), apex(raised, PORTAL)) < 1e-9
    assert T.get_bay(raised["rooms"][1], PORTAL)["apex_shift"] == -0.1  # the same apex, seen from the other side
    back, _ = T.set_apex(raised, PORTAL, height_m=4.54, shift=0.0)
    assert T.get_bay(back["rooms"][0], HOST) == host


def test_the_second_room_is_resized_and_recounted_from_its_layout():
    second = PAIR["rooms"][1]
    assert second["layout"]["outline"] == {"radius_m": 4.417, "through": "C1"} and T.reconcile(PAIR) == (PAIR, [])
    larger, change = T.set_layout(PAIR, "R2", outline={"radius_m": 5.2, "through": "C1"})
    grown = larger["rooms"][1]
    assert larger["rooms"][0] == PAIR["rooms"][0]  # the first room is not touched
    assert [p["id"] for p in grown["piers"]] == [p["id"] for p in second["piers"]] and grown["piers"][:2] == second["piers"][:2]
    (p0, p1), (cx, cy) = (p["position_m"] for p in grown["piers"][:2]), grown["crown"]["centre_m"]
    centre = T._ring_through(p0, p1, 5.2, [1.0, 1.0])[0]
    assert all(abs(math.dist(p["position_m"], centre) - 5.2) < 2e-3 for p in grown["piers"])  # every pier on the new circle, the shared two included
    assert math.dist((cx, cy), centre) < 2e-3 and math.dist((cx, cy), second["crown"]["centre_m"]) > 0.5  # and the crown has gone with its centre
    assert T.reconcile(larger) == (larger, []) and check_connections(larger)[0]["one_arch"]

    by_hand = copy.deepcopy(PAIR)  # the file edited by hand: seven bays, and a wider circle
    by_hand["rooms"][1]["layout"].update({"bays": 7, "outline": {"radius_m": 4.9, "through": "C1"}})
    laid, changes = T.reconcile(by_hand)
    seven = laid["rooms"][1]
    assert len(changes) == 1 and len(seven["bays"]) == 7 and seven["bays"][0] == second["bays"][0] and laid["rooms"][0] == PAIR["rooms"][0]
    assert [p["id"] for p in seven["piers"]][:6] == [p["id"] for p in second["piers"]] and seven["piers"][6]["id"] == "R2.P7"
    fewer, _ = T.set_layout(laid, "R2", bays=5)
    again = T.set_layout(fewer, "R2", bays=7)[0]["rooms"][1]
    assert len(fewer["rooms"][1]["bays"]) == 5 and [p["id"] for p in again["piers"]][5:] == ["R2.P8", "R2.P9"]  # an ID is never reissued
    assert rejected(lambda: T.set_layout(PAIR, "R2", outline={"radius_m": 2.0, "through": "C1"}))


def test_taking_the_second_room_away_gives_the_first_back():
    alone, change = T.remove_room(PAIR, "R2")
    assert change["removed"] == ["R2", "C1"] and change["modified"] == [HOST]
    assert alone["rooms"] == [dict(NOW["rooms"][0], layout={"bays": 8})] and alone["connections"] == []
    assert rejected(lambda: T.remove_room(alone, "R1"))
    again, change = T.add_room_from_bay(alone, "R1.B5", bays=5)
    assert change["added"][:2] == ["R3", "C2"]  # room and connection IDs are not reused either


def test_the_first_rooms_timber_is_untouched_by_the_join():
    alone = {m.id: m for m in build_timber(NOW["rooms"][0], NOW["timber"])}
    mine = {member_id: m for member_id, m in MEMBERS.items() if GROUP["room_of"][member_id] == "R1"}
    assert mine.keys() == alone.keys()
    for member_id, m in mine.items():
        assert [(a.co, a.handle_left, a.handle_right) for a in m.path.anchors] == [(a.co, a.handle_left, a.handle_right) for a in alone[member_id].path.anchors], member_id
    assert sorted(k for k in mine if mine[k].nodes != alone[k].nodes) == [f"{HOST}.arch.L", f"{HOST}.arch.R"]  # only the shared arch gains joints
    # and one room of a design built on its own is what `build_timber` gives
    (single,) = build_design_timber(NOW)
    assert [m.id for m in single["members"]] == list(alone) and single["rooms"] == ["R1"]


def test_the_two_rooms_share_one_arch_housed_from_both_sides():
    by_room = Counter(GROUP["room_of"].values())
    assert GROUP["rooms"] == ["R1", "R2"] and by_room["R1"] == 108 and by_room["R2"] > 50
    arches = [m for m in MEMBERS.values() if m.family == "arch"]
    assert len(arches) == 16 + 10 and not any(m.id.startswith(PORTAL + ".arch") for m in arches)  # six bays, five arches: the sixth is the first room's
    assert f"{PORTAL}.hoop0" in MEMBERS and f"{HOST}.hoop0" in MEMBERS  # each room keeps its own hoops inside the shared arch
    assert clearances(GROUP["members"])["collisions"] == []
    housed = [j for j in JOINTS if j.kind == "housing" and j.members[1].startswith(HOST + ".arch")]
    faces = Counter(next(c.face for c in j.cuts if c.member == j.members[1]) for j in housed)
    assert faces["room"] >= 4 and faces["far"] >= 4  # ribs of both rooms are let into it, one room into each face
    assert all(GROUP["room_of"][j.members[0]] == ("R1" if face == "room" else "R2") for j in housed for face in [next(c.face for c in j.cuts if c.member == j.members[1])])
    for side in ("L", "R"):  # every one of them comes with its pocket to mill out of the arch
        pockets = sum(1 for j in housed if j.members[1] == f"{HOST}.arch.{side}")
        assert len(CUTTERS[f"{HOST}.arch.{side}"]) >= pockets + 2
    assert sum(1 for j in JOINTS if j.review) <= 4


def test_three_arch_legs_meet_at_each_pier_the_rooms_share():
    host = T.get_bay(PAIR["rooms"][0], HOST)
    mitres = [j for j in JOINTS if j.kind == "pier_mitre"]
    assert len(mitres) == 6 + 4 + 2 * 3  # one at each pier of one room, three where three legs meet
    for pier_id in (host["from"], host["to"]):
        legs = [m for m in MEMBERS.values() if pier_id + ".mitre" in m.nodes]
        assert len(legs) == 3 and Counter(GROUP["room_of"][m.id] for m in legs) == {"R1": 2, "R2": 1}
        at = place(PAIR, pier_id)
        ways = [m.path.station_at(0.0).depth_axis for m in legs]  # each points along its arch, away from the pier
        assert all(math.dist(m.path.anchors[0].co[:2], at) < 0.11 for m in legs)
        for i in range(3):
            assert sum(1 for j in mitres if legs[i].id in j.members) == 2  # each leg is mitred against the other two
            for k in range(i + 1, 3):
                assert math.degrees(math.acos(sum(a * b for a, b in zip(ways[i], ways[k])))) > 80.0
    # each room's legs stand on its own side of the shared arch
    mid, _, outward, _ = T.chord_frame(PAIR["rooms"][0], host)
    for m in MEMBERS.values():
        if m.family in ("hoop", "rib", "fill", "fine"):
            for end in (m.path.anchors[0].co, m.path.anchors[-1].co):
                if end[2] < 1e-6 and min(math.dist(end[:2], place(PAIR, p)) for p in (host["from"], host["to"])) < 1.2:
                    beyond = (end[0] - mid[0]) * outward[0] + (end[1] - mid[1]) * outward[1]
                    assert (beyond > 0.1) == (GROUP["room_of"][m.id] == "R2") and abs(beyond) > 0.1, m.id


def test_a_room_has_its_own_lattice_and_hoops():
    second = PAIR["rooms"][1]
    assert room_timber(PAIR, PAIR["rooms"][0]) == PAIR["timber"]
    own = room_timber(PAIR, second)
    assert own["lattice"]["ribs_per_family"] == 8 and own["lattice"]["lean_deg"] == PAIR["timber"]["lattice"]["lean_deg"] and own["sections_m"] == PAIR["timber"]["sections_m"]
    ribs = Counter(GROUP["room_of"][m.id] for m in MEMBERS.values() if m.family == "rib")
    assert ribs == {"R1": 24, "R2": 16}
    assert f"{PORTAL}.hoop1" not in MEMBERS and f"{HOST}.hoop1" in MEMBERS
    for bad in ({"sections_m": {"arch": [0.3, 0.4]}}, {"joints": {"housing_depth_m": 0.1}}, {"arches": {"type": "paired"}}):
        design = copy.deepcopy(PAIR)
        design["rooms"][1]["timber"] = bad
        assert rejected(lambda: room_timber(design, design["rooms"][1]))  # sections, joints and the arch type belong to the whole design


def test_the_roofs_meet_on_the_shared_arch_in_a_fold():
    (met,) = check_connections(PAIR)
    assert met["id"] == "C1" and met["arch_gap_m"] < 1e-9 and met["one_arch"]
    assert 5.0 < met["fold_at_apex_deg"] < 40.0 and "fold" in met["continuity"]  # stated, not hidden
    assert check_connections(NOW) == []


def test_schedules_and_centrelines_cover_both_rooms_once():
    rows, joints = schedules(PAIR)
    assert len(rows) == len(MEMBERS) and len({row["id"] for row in rows}) == len(rows)
    lines = centrelines(PAIR)["members"]
    assert Counter(line["room"] for line in lines) == Counter(GROUP["room_of"].values())
    assert sum(1 for row in joints if row["kind"] == "pier_mitre") == 16


def test_a_room_can_be_joined_to_a_long_hall():
    hall = FORMS["formed"](NOW, {name: changes for name, _, changes in FORMS["FORMS"]}["7_long_hall"])
    second = dict(SCRIPT["SECOND_ROOM"], bay="R1.B3")  # a bay on the hall's long side
    joined, _ = T.add_room_from_bay(hall, second.pop("bay"), **second)
    (group,) = build_design_timber(joined)
    assert Counter(group["room_of"].values())["R1"] == 164 and clearances(group["members"])["collisions"] == []
    assert check_connections(joined)[0]["one_arch"]


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"{len(tests)} passed")
