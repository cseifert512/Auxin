"""Checks on the crown's section and the plan's outline as parameters. No Blender needed: python tests/test_forms.py"""
import copy
import math
import runpy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import topology as T  # noqa: E402
from bower.envelope import KAPPA, Roof, build_envelope, check_envelope, cubic_at, lantern_profile  # noqa: E402
from bower.joints import find_joints  # noqa: E402
from bower.timber import build_timber, clearances  # noqa: E402

SCRIPT = runpy.run_path(str(REPO / "scripts" / "gate2_forms.py"))
FORMS = {name: changes for name, _, changes in SCRIPT["FORMS"]}
NOW = T.load(REPO / "design.json")
SIX = T.load(REPO.parent / "releases" / "six-bay-v1" / "design.json")


def room(design):
    return design["rooms"][0]


def form(name):
    return SCRIPT["formed"](NOW, FORMS[name])


def built(design):
    members = build_timber(room(design), design["timber"])
    return members, find_joints(members, design["timber"])[0]


def test_the_default_section_is_the_lantern_it_always_was():
    for design in (SIX, NOW):
        shape, crown = room(design)["shape"], room(design)["crown"]
        a, b = shape["lantern_radius_m"] - crown["radius_m"], crown["height_m"] - shape["lantern_base_height_m"]
        was = ((0.0, 0.0), (KAPPA * a, 0.0), (a, b * (1.0 - KAPPA)), (a, b))
        assert all(math.dist(p, q) < 1e-12 for p, q in zip(lantern_profile(shape, crown), was))


def test_every_form_is_a_valid_room_with_a_clean_timber_model():
    for name in FORMS:
        design = form(name)
        T.validate(design)
        assert check_envelope(build_envelope(room(design), design["sampling"]))["ok"], name
        members, joints = built(design)
        assert clearances(members)["collisions"] == [], name
        assert sum(m.family == "arch" for m in members) == 2 * len(room(design)["bays"]), name
        assert sum(1 for j in joints if j.review) <= 4, name


def test_the_section_makes_a_flare_a_dome_an_oculus_or_a_trunk():
    floor = room(NOW)["floor_z_m"]

    def heads(members):
        return [m.path.anchors[-1].co for m in members if m.id.split(".")[1] == "rib"]

    flared = Roof(room(form("1_flared_basket")))
    waist = flared.base_radius - max(cubic_at(flared.lantern, i / 50)[0][0] for i in range(51))
    assert waist < flared.top_radius - 0.1 and flared.top_direction(0.0)[0] > 0.2  # narrower below its top, and leaning out there

    dome = Roof(room(form("2_dome")))
    assert 0.0 < dome.top_direction(0.0)[2] < 0.3  # nearly level where it reaches its oculus

    design = form("3_open_oculus")
    members, joints = built(design)
    level = floor + room(design)["shape"]["lantern_base_height_m"]
    assert all(abs(p[2] - level) < 1e-6 for p in heads(members))  # no lantern: the ribs end at canopy height
    ring = next(m for m in members if m.id == "R1.ring.top")
    radius = math.hypot(ring.path.anchors[0].co[0] - room(design)["crown"]["centre_m"][0], ring.path.anchors[0].co[1] - room(design)["crown"]["centre_m"][1])
    assert radius < room(design)["crown"]["radius_m"] and abs(ring.path.anchors[0].co[2] - level) < 1e-6  # the ring stands inside the rib heads

    design = form("4_trunk")
    members, joints = built(design)
    assert all(abs(p[2] - floor) < 1e-6 for p in heads(members))  # the ribs come down to the floor
    assert "R1.ring.top" not in {m.id for m in members}  # and stand there: no crown ring
    bases = {j.members[0] for j in joints if j.kind == "base"}
    assert {m.id for m in members if m.id.split(".")[1] == "rib"} <= bases


def test_a_section_that_closes_on_its_own_axis_is_rejected():
    pinched = copy.deepcopy(NOW)
    room(pinched)["crown"].update({"radius_m": 0.3, "section": {"top_slope_deg": 150.0}})
    try:
        Roof(room(pinched))
    except T.DesignError:
        pass
    else:
        raise AssertionError("a crown that pinches shut was accepted")


def test_the_outline_sets_where_the_piers_stand():
    assert abs(T.outline_radius({"radius_m": 5.0}, 1.234) - 5.0) < 1e-12
    oval = {"radius_m": 5.0, "stretch": 1.5, "stretch_bearing_deg": 30.0}
    assert abs(T.outline_radius(oval, math.radians(30.0)) - 7.5) < 1e-9 and abs(T.outline_radius(oval, math.radians(120.0)) - 5.0) < 1e-9
    assert T.outline_radius({"radius_m": 5.0, "taper": 0.1}, 0.0) > 5.0 > T.outline_radius({"radius_m": 5.0, "taper": 0.1}, math.pi)

    design = form("5_oval")
    outline = room(design)["layout"]["outline"]
    cx, cy = room(design)["crown"]["centre_m"]
    for pier in room(design)["piers"]:
        x, y = pier["position_m"]
        assert abs(math.hypot(x - cx, y - cy) - T.outline_radius(outline, math.atan2(y - cy, x - cx))) < 2e-3  # every pier is on the outline
    away = [math.hypot(p["position_m"][0] - cx, p["position_m"][1] - cy) for p in room(design)["piers"]]
    assert max(away) > 1.25 * min(away)  # and the room is visibly longer than it is wide


def test_a_ring_laid_from_an_outline_stays_put_until_the_outline_changes():
    design = form("5_oval")
    assert T.reconcile(design) == (design, [])  # the same layout always gives the same ring
    wider = copy.deepcopy(design)
    room(wider)["layout"]["outline"]["radius_m"] = 5.9  # edited by hand in the file
    laid, changes = T.reconcile(wider)
    assert len(changes) == 1 and room(laid)["piers"] != room(design)["piers"]
    assert [p["id"] for p in room(laid)["piers"]] == [p["id"] for p in room(design)["piers"]]
    assert T.reconcile(laid) == (laid, [])
    taller, _ = T.set_layout(design, "R1", apex_heights_m=[5.0, 4.6])
    assert [b["apex_height_m"] for b in room(taller)["bays"]] == [5.0, 4.6] * 5


def test_a_pier_or_apex_moved_by_hand_is_not_put_back():
    design = form("5_oval")
    pier = room(design)["piers"][3]
    cx, cy = room(design)["crown"]["centre_m"]
    out = [round(cx + 1.05 * (pier["position_m"][0] - cx), 3), round(cy + 1.05 * (pier["position_m"][1] - cy), 3)]
    moved, _ = T.move_pier(design, pier["id"], out)
    assert room(moved)["layout"] == {"bays": 10}  # the outline no longer describes the ring, so it is dropped
    assert T.reconcile(moved) == (moved, []) and T.get_pier(room(moved), pier["id"])["position_m"] == out
    heights, _ = T.set_layout(design, "R1", apex_heights_m=4.7)
    raised, _ = T.set_apex(heights, room(heights)["bays"][0]["id"], height_m=5.2)
    assert "apex_heights_m" not in room(raised)["layout"] and T.reconcile(raised)[1] == []


def test_unknown_layout_keys_are_rejected():
    try:
        T.set_layout(NOW, "R1", bay=9)
    except T.DesignError:
        pass
    else:
        raise AssertionError("a misspelt layout key was accepted")


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"{len(tests)} passed")
