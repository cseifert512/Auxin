"""Checks on the bay count as a room parameter, and on the design as it stands. No Blender needed: python tests/test_bay_count.py"""
import copy
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import topology as T  # noqa: E402
from bower.envelope import build_envelope, check_envelope  # noqa: E402
from bower.joints import find_joints  # noqa: E402
from bower.timber import build_timber, clearances  # noqa: E402

SIX = T.load(REPO / "releases" / "six-bay-v1" / "design.json")  # a frozen design to lay out afresh
NOW = T.load(REPO / "design.json")  # the design as it stands


def room(design):
    return design["rooms"][0]


def ids(design, kind):
    return [e["id"] for e in room(design)[kind]]


def distance(design, point) -> float:
    cx, cy = room(design)["crown"]["centre_m"]
    return math.hypot(point[0] - cx, point[1] - cy)


def envelope_ok(design) -> bool:
    return check_envelope(build_envelope(room(design), design["sampling"]))["ok"]


def test_the_ring_can_be_laid_out_with_any_number_of_bays():
    radii = [distance(SIX, p["position_m"]) for p in room(SIX)["piers"]]
    for count in (4, 5, 6, 7, 8, 9, 10, 12):
        laid, change = T.set_bay_count(SIX, "R1", count)
        T.validate(laid)
        assert len(room(laid)["piers"]) == len(room(laid)["bays"]) == count == room(laid)["layout"]["bays"]
        assert envelope_ok(laid), f"{count} bays give an invalid envelope"
        # the room keeps its outline: every pier stands between the nearest and furthest of the old ones
        assert all(min(radii) - 1e-3 <= distance(laid, p["position_m"]) <= max(radii) + 1e-3 for p in room(laid)["piers"])
        assert room(laid)["piers"][0]["position_m"] == [round(c, 3) for c in room(SIX)["piers"][0]["position_m"]]  # and its first pier
        widths = [2 * T.chord_frame(room(laid), b)[3] for b in room(laid)["bays"]]
        assert max(widths) - min(widths) > 0.3 and max(widths) < 1.45 * min(widths)  # unequal, but one family
        # IDs: the first piers and bays keep theirs, extras are new, none is reused
        kept = min(count, 6)
        assert ids(laid, "piers")[:kept] == ids(SIX, "piers")[:kept] and ids(laid, "bays")[:kept] == ids(SIX, "bays")[:kept]
        assert change["added"] == [f"R1.P{n}" for n in range(7, count + 1)] + [f"R1.B{n}" for n in range(7, count + 1)]
        assert change["removed"] == ids(SIX, "piers")[count:] + ids(SIX, "bays")[count:]
    assert SIX == T.load(REPO / "releases" / "six-bay-v1" / "design.json")  # the operation is pure


def test_ids_are_not_reused_when_the_count_goes_down_and_up_again():
    eight, _ = T.set_bay_count(SIX, "R1", 8)
    five, _ = T.set_bay_count(eight, "R1", 5)
    seven, change = T.set_bay_count(five, "R1", 7)
    assert ids(five, "piers") == [f"R1.P{n}" for n in range(1, 6)]
    assert change["added"] == ["R1.P9", "R1.P10", "R1.B9", "R1.B10"]  # 6, 7 and 8 were retired, so the new ones are 9 and 10
    assert ids(seven, "piers") == [f"R1.P{n}" for n in (1, 2, 3, 4, 5, 9, 10)]


def test_editing_the_number_in_the_layout_is_enough():
    edited = copy.deepcopy(SIX)
    room(edited)["layout"] = {"bays": 9}
    laid, changes = T.reconcile(edited)
    assert len(changes) == 1 and len(room(laid)["bays"]) == 9
    assert T.reconcile(laid) == (laid, [])  # nothing more to do once the ring matches
    assert T.reconcile(SIX) == (SIX, [])  # a room with no layout is left as it is
    by_hand, _ = T.add_bay(laid, "R1.B1")  # a bay added by hand: the layout follows the ring, not the other way round
    assert room(by_hand)["layout"] == {"bays": 10} and T.reconcile(by_hand)[1] == []


def test_bad_counts_and_weights_are_rejected():
    for bad in (lambda: T.set_bay_count(SIX, "R1", 2), lambda: T.set_bay_count(SIX, "R1", 6.5), lambda: T.set_bay_count(SIX, "R1", 6, [1, 1, 1]), lambda: T.set_bay_count(SIX, "R1", 3, [1, 0, 1])):
        try:
            bad()
        except T.DesignError:
            pass
        else:
            raise AssertionError("an impossible layout was accepted")


def test_other_bay_counts_still_get_a_clean_timber_model():
    for count in (5, 7, 10):
        laid, _ = T.set_bay_count(SIX, "R1", count)
        members = build_timber(room(laid), laid["timber"])
        assert clearances(members)["collisions"] == [], f"{count} bays"
        assert sum(m.family == "arch" for m in members) == 2 * count
        joints, _, cutters = find_joints(members, laid["timber"])
        assert sum(1 for j in joints if j.review) <= 6, f"{count} bays: {sum(1 for j in joints if j.review)} joints flagged"


def test_the_design_as_it_stands_is_consistent_and_builds_clean():
    T.validate(NOW)
    assert T.reconcile(NOW) == (NOW, [])  # its ring already has the number of bays its layout asks for
    assert envelope_ok(NOW)
    members = build_timber(room(NOW), NOW["timber"])
    assert clearances(members)["collisions"] == []
    assert sum(m.family == "arch" for m in members) == 2 * len(room(NOW)["bays"])
    joints, _, cutters = find_joints(members, NOW["timber"])
    assert sum(1 for j in joints if j.review) <= 4
    assert set(cutters) == {m.id for m in members}


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"{len(tests)} passed")
