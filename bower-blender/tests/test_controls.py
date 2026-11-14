"""Checks on what the panel's sliders do to a design. No Blender needed: python tests/test_controls.py"""
import copy
import math
import runpy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import controls as C  # noqa: E402
from bower import topology as T  # noqa: E402
from bower.envelope import Roof, check_connections  # noqa: E402
from bower.spine import crown_spine  # noqa: E402
from bower.timber import build_design_timber, clearances  # noqa: E402

NOW = T.load(REPO / "design.json")
PAIR = runpy.run_path(str(REPO / "scripts" / "gate3_rooms.py"))["joined"](NOW)


def room(design, room_id="R1"):
    return T.get_room(design, room_id)


def rejected(action) -> bool:
    try:
        action()
    except T.DesignError:
        return True
    return False


def builds(design) -> int:
    """The number of members, having checked that the roofs can be made and nothing collides."""
    for one in design["rooms"]:
        Roof(one)
    groups = build_design_timber(design)
    assert all(clearances(group["members"])["collisions"] == [] for group in groups)
    return sum(len(group["members"]) for group in groups)


def test_every_slider_reads_the_design_and_writes_what_it_reads():
    assert [c.key for c in C.CONTROLS] == list(C.BY_KEY) and set(C.GROUPS) == {"Crown", "Room", "Lattice"}
    for design, room_id in ((NOW, "R1"), (PAIR, "R2")):
        values = C.values(design, room_id)
        assert set(values) == set(C.BY_KEY)
        for control in C.CONTROLS:
            assert control.lo <= values[control.key] <= control.hi, control.key  # every value can be shown on its slider
            if control.key in C.blocked(design, room_id):
                continue
            same = C.adjust(design, room_id, control.key, values[control.key])  # setting a control to what it shows changes nothing it shows
            assert abs(C.values(same, room_id)[control.key] - values[control.key]) < 2e-3, control.key
    assert C.values(NOW, "R1")["crown_height"] == room(NOW)["crown"]["height_m"] and C.values(NOW, "R1")["bays"] == 8
    assert C.values(NOW, "R1")["top_slope"] == 90.0 and C.values(NOW, "R1")["spine_length"] == 0.0 and C.values(NOW, "R1")["hoops"] == 2


def test_each_slider_changes_its_own_value_and_the_room_still_builds():
    moves = {"crown_height": 7.2, "crown_radius": 1.5, "lantern_radius": 3.3, "lantern_base": 5.1, "top_slope": 118.0, "room_radius": 6.8, "bays": 10, "arch_height": 5.0, "pier_height": 2.0, "ribs": 15, "lean": 32.0, "hoops": 1}
    before = C.values(NOW, "R1")
    for key, value in moves.items():
        after = C.adjust(NOW, "R1", key, value)
        now = C.values(after, "R1")
        assert abs(now[key] - value) < 2e-3, key
        stay = set(moves) - {key} - {"room_radius", "arch_height"}  # those two are read off the ring, which a new bay count or outline moves a little
        assert all(abs(now[k] - before[k]) < 1e-9 for k in stay), key
        assert builds(after) > 80, key
    assert C.adjust(NOW, "R1", "crown_height", 7.2) is not NOW and room(NOW)["crown"]["height_m"] == 6.3  # the design handed in is left alone


def test_a_slider_pushed_too_far_is_refused_with_a_reason():
    for key, value in (("crown_radius", 4.0), ("room_radius", 3.0), ("lantern_radius", 5.6), ("crown_height", -1.0)):
        try:
            C.adjust(NOW, "R1", key, value)
        except T.DesignError as error:
            assert "R1" in str(error)
        else:
            raise AssertionError(f"{key} = {value} was accepted")
    pinched = C.adjust(NOW, "R1", "top_slope", 150.0)  # a valid plan graph whose crown closes on itself: the roof refuses it
    pinched = C.adjust(pinched, "R1", "crown_radius", 0.3)
    assert rejected(lambda: Roof(room(pinched)))


def test_the_spine_slider_turns_a_round_room_into_a_hall_and_back():
    hall = C.adjust(NOW, "R1", "spine_length", 5.0)
    spine = crown_spine(room(hall)["crown"])
    assert abs(spine.length - 5.0) < 1e-6 and math.dist(spine.centre, room(NOW)["crown"]["centre_m"]) < 1e-6
    reach = room(hall)["layout"]["outline"]["radius_m"]
    assert all(abs(spine.locate(p["position_m"])[1] - reach) < 2e-3 for p in room(hall)["piers"])  # the ring is laid out round the spine
    assert [p["id"] for p in room(hall)["piers"]] == [p["id"] for p in room(NOW)["piers"]] and builds(hall) > 80
    longer = C.adjust(hall, "R1", "spine_length", 7.5)
    assert abs(crown_spine(room(longer)["crown"]).length - 7.5) < 1e-6 and room(longer)["layout"]["outline"]["radius_m"] == reach
    turned, _ = T.set_spine(hall, "R1", 5.0, heading_deg=90.0)
    assert abs(crown_spine(room(turned)["crown"]).u[1]) > 0.999  # now running north-south
    back = C.adjust(longer, "R1", "spine_length", 0.0)
    assert "spine_m" not in room(back)["crown"] and builds(back) > 80
    centre = room(back)["crown"]["centre_m"]
    assert all(abs(math.dist(p["position_m"], centre) - reach) < 2e-3 for p in room(back)["piers"])  # and round again


def test_a_room_is_resized_about_its_crown():
    larger, change = T.scale_room(NOW, "R1", 1.1)
    centre = room(NOW)["crown"]["centre_m"]
    for was, now in zip(room(NOW)["piers"], room(larger)["piers"]):
        assert abs(math.dist(now["position_m"], centre) - 1.1 * math.dist(was["position_m"], centre)) < 2e-3
        assert abs(math.atan2(now["position_m"][1] - centre[1], now["position_m"][0] - centre[0]) - math.atan2(was["position_m"][1] - centre[1], was["position_m"][0] - centre[0])) < 1e-3
    assert room(larger)["layout"] == room(NOW)["layout"] and T.reconcile(larger) == (larger, [])
    assert rejected(lambda: T.scale_room(NOW, "R1", 0.5)) and rejected(lambda: T.scale_room(NOW, "R1", -1.0))
    oval, _ = T.set_layout(NOW, "R1", outline={"radius_m": 5.5, "stretch": 1.3})
    wider, _ = T.scale_room(oval, "R1", 1.2)
    assert room(wider)["layout"]["outline"]["radius_m"] == 6.6 and room(wider)["layout"]["outline"]["stretch"] == 1.3  # a ring on an outline is resized through it


def test_joined_rooms_say_which_sliders_they_cannot_use():
    assert C.blocked(NOW, "R1") == {} and C.blocked(PAIR, "R2") == {}
    assert set(C.blocked(PAIR, "R1")) == {"room_radius", "bays"}  # the first room's ring is tied to its neighbour
    assert rejected(lambda: C.adjust(PAIR, "R1", "bays", 9)) and rejected(lambda: C.adjust(PAIR, "R1", "room_radius", 6.5))
    larger = C.adjust(PAIR, "R2", "room_radius", 5.2)  # the second room is resized from its own layout
    assert larger["rooms"][0] == PAIR["rooms"][0] and room(larger, "R2")["layout"]["outline"]["radius_m"] == 5.2
    seven = C.adjust(PAIR, "R2", "bays", 7)
    assert len(room(seven, "R2")["bays"]) == 7 and seven["rooms"][0] == PAIR["rooms"][0] and builds(seven) > 150


def test_what_two_rooms_share_changes_in_both():
    taller = C.adjust(PAIR, "R1", "pier_height", 1.9)  # the arch's own curve: one arch, so both rooms
    assert room(taller, "R1")["shape"]["pier_height_m"] == room(taller, "R2")["shape"]["pier_height_m"] == 1.9
    lantern = C.adjust(PAIR, "R2", "lantern_base", 4.9)  # a room's own lantern is its own
    assert room(lantern, "R1")["shape"] == room(PAIR, "R1")["shape"] and room(lantern, "R2")["shape"]["lantern_base_height_m"] == 4.9
    raised = C.adjust(PAIR, "R2", "arch_height", C.values(PAIR, "R2")["arch_height"] + 0.2)
    assert check_connections(raised)[0]["one_arch"]  # the shared arch has gone up in both rooms
    assert abs(T.get_bay(room(raised, "R1"), "R1.B3")["apex_height_m"] - T.get_bay(room(PAIR, "R1"), "R1.B3")["apex_height_m"] - 0.2) < 1e-9
    assert rejected(lambda: T.set_shape(PAIR, "R1", lantern_colour=1.0))


def test_lattice_sliders_write_to_the_room_that_has_its_own_settings():
    denser = C.adjust(PAIR, "R2", "ribs", 10)
    assert room(denser, "R2")["timber"]["lattice"]["ribs_per_family"] == 10 and denser["timber"] == PAIR["timber"]  # the second room has its own
    whole = C.adjust(PAIR, "R1", "ribs", 14)
    assert whole["timber"]["lattice"]["ribs_per_family"] == 14 and "timber" not in room(whole, "R1")  # the first room uses the design's
    assert C.values(whole, "R2")["ribs"] == 8  # which the second room's own value still overrides
    none = C.adjust(NOW, "R1", "hoops", 0)
    assert none["timber"]["arches"]["hoops_m"] == [] and builds(none) > 80
    assert not any(m.family == "hoop" for group in build_design_timber(none) for m in group["members"])


def test_a_room_grown_from_the_panel_suits_its_size():
    grown = C.grow_room(NOW, "R1.B5")
    second = room(grown, "R2")
    assert grown["connections"] == [{"id": "C1", "bays": ["R1.B5", "R2.B1"]}] and len(second["bays"]) == 6
    assert second["timber"]["lattice"]["ribs_per_family"] < NOW["timber"]["lattice"]["ribs_per_family"] and len(second["timber"]["arches"]["hoops_m"]) == 1
    starts = [tier["from"]["radius_m"] for tier in second["timber"]["lattice"]["tiers"] if isinstance(tier.get("from"), dict) and "radius_m" in tier["from"]]
    assert all(second["shape"]["lantern_radius_m"] + 0.2 < radius < C.values(grown, "R2")["room_radius"] - 0.8 for radius in starts)
    assert builds(grown) > 150 and copy.deepcopy(NOW) == NOW


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"{len(tests)} passed")
