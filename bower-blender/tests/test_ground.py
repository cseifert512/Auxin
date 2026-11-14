"""Checks on the ground at a pier (bower/ground.py): root zones, footings on screw piles or pads, feeders and hand-overs. No Blender needed: python tests/test_ground.py"""
import copy
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import ground as G  # noqa: E402
from bower import topology as T  # noqa: E402
from bower.centreline import add, dot, mul, norm, sub  # noqa: E402
from bower.joints import find_joints  # noqa: E402
from bower.lines import Bodies, check_lines, design_lines, line_rows, standoff_joints, training_lines  # noqa: E402
from bower.timber import build_design_timber  # noqa: E402

NOW = T.load(REPO / "design.json")  # the design as it stands
SIX = T.load(REPO.parent / "releases" / "six-bay-v1" / "design.json")  # a frozen design, made before any of this
PIER = "R1.P6"
PAD = {"footings": {"type": "pad"}}  # the earlier footing, kept as an option

_BUILT = {}


def built(design):
    """A design's one group of rooms with its joints and its training lines under the default settings, built once."""
    if id(design) not in _BUILT:
        groups = build_design_timber(design)
        assert len(groups) == 1
        joints = find_joints(groups[0]["members"], design["timber"])[0]
        timber = {**design["timber"], "training_lines": {}}
        _BUILT[id(design)] = (groups[0], joints, training_lines(groups[0]["members"], timber, joints), timber)
    return _BUILT[id(design)]


def laid(design, zones, **own):
    """The ground of a design with these root zones, whatever the design file itself sets out."""
    group, joints, lines, timber = built(design)
    planted = {**design, "timber": timber, "ground": {"root_zones": zones, **own}}
    return G.lay(planted, group, joints, lines), planted


def beside(design, pier=PIER, **zone):
    return G.beside_pier({**design, "timber": built(design)[3]}, built(design)[0], pier, **zone)


def test_a_design_that_sets_out_no_ground_has_none():
    assert G.settings(SIX) is None
    plain = {k: v for k, v in NOW.items() if k != "ground"}
    assert G.settings(plain) is None
    assert all(group["ground"] is None and all(line.kind == "training" for line in group["lines"]) for group in design_lines(plain, build_design_timber(plain)))


def test_root_zones_beside_a_pier_lie_outside_the_room_one_by_each_arch_leg():
    zones = beside(NOW, out_m=0.65)
    assert [z["id"] for z in zones] == [f"{PIER}.root.1", f"{PIER}.root.2"]
    ground, _ = laid(NOW, zones)
    pier = next(p["position_m"] for p in NOW["rooms"][0]["piers"] if p["id"] == PIER)
    crown = NOW["rooms"][0]["crown"]["centre_m"]
    for zone in ground["root_zones"]:
        assert zone.pier == PIER and zone.outside and zone.review == "", zone
        assert math.dist(zone.position, crown) > math.dist(pier, crown) + 0.3  # further from the crown than the pier is
        assert abs(zone.to_feeder_m - 0.65) < 0.01 and zone.feeder.startswith("R1.B") and ".arch." in zone.feeder
        assert 0.8 * math.pi * zone.radius_m**2 * zone.depth_m < zone.soil_m3 <= math.pi * zone.radius_m**2 * zone.depth_m + 1e-9
    assert len({zone.feeder for zone in ground["root_zones"]}) == 2  # one arch leg each


def test_a_pad_holds_every_foot_and_gives_way_to_a_root_zone():
    group = built(NOW)[0]
    bare, _ = laid(NOW, [], **PAD)
    ground, planted = laid(NOW, beside(NOW, out_m=0.65), **PAD)
    cfg = G.settings(planted)["footings"]["pad"]
    feet = G.feet_at_piers(planted, group)["feet"]
    assert set(ground["footings"]) == set(feet) == {p["id"] for p in NOW["rooms"][0]["piers"]}  # one under every pier
    for pier_id, footing in ground["footings"].items():
        assert footing.area_m2 > 0.5 and len(footing.feet) == len(feet[pier_id])
        for _, _, corners in feet[pier_id]:  # every foot stands on it, with at least the least margin of footing beyond
            assert all(G._within(list(footing.outline), c) >= cfg["least_m"] - 1e-6 for c in corners), pier_id
        if pier_id != PIER:  # a pier with no plant beside it has the plain footing
            assert footing.cut_for == () and footing.outline == bare["footings"][pier_id].outline
    cut = ground["footings"][PIER]
    assert set(cut.cut_for) == {z.id for z in ground["root_zones"]} and cut.area_m2 < cut.plain_area_m2 - 0.05 and cut.review == ""
    for zone in ground["root_zones"]:  # and keeps clear of each zone by the clearance asked for
        nearest = min(math.dist(zone.position, p) for p in cut.outline)
        assert nearest >= zone.radius_m + cfg["root_clear_m"] - 1e-6 and zone.taken == 0.0, (zone.id, nearest)


def test_a_root_zone_too_close_to_the_feet_loses_ground_to_a_pad_and_says_so():
    ground, _ = laid(NOW, beside(NOW, out_m=0.2), **PAD)
    for zone in ground["root_zones"]:
        assert zone.taken > 0.05 and "a footing takes" in zone.review, zone
        assert zone.soil_m3 < 0.9 * math.pi * zone.radius_m**2 * zone.depth_m
    assert "a foot stands in the way" in ground["footings"][PIER].review
    assert ground["report"]["to_review"]  # it is in the report to be dealt with, not hidden
    # and what a plant is said to need is carried, and compared with what the zone has
    wanting, _ = laid(NOW, beside(NOW, out_m=0.65, needs_soil_m3=2.0))
    assert all("is said to need 2.0" in zone.review for zone in wanting["root_zones"])
    enough, _ = laid(NOW, beside(NOW, out_m=0.65, needs_soil_m3=0.3))
    assert all(zone.review == "" for zone in enough["root_zones"])


def test_every_pier_stands_on_a_ring_of_screw_piles_under_a_cap_that_holds_its_feet():
    group = built(NOW)[0]
    ground, planted = laid(NOW, beside(NOW, out_m=0.4))
    p = G.settings(planted)["footings"]["piles"]
    feet = G.feet_at_piers(planted, group)["feet"]
    assert G.settings(planted)["footings"]["type"] == "piles" and set(ground["footings"]) == set(feet)
    for pier_id, footing in ground["footings"].items():
        assert footing.kind == "piles" and len(footing.piles) == p["least"] == 3 and footing.review == "", (pier_id, footing.review)
        apart = [math.dist(a, b) for i, a in enumerate(footing.piles) for b in footing.piles[i + 1 :]]
        assert min(apart) >= p["spacing_m"] - 2e-3, (pier_id, apart)  # no two closer than piles may stand
        cap = list(footing.outline)
        assert all(G._within(cap, q) >= p["edge_m"] - 5e-3 for q in footing.piles)  # each under the cap, clear of its edge
        for _, _, corners in feet[pier_id]:  # every foot stands on the cap, and within reach of a pile
            assert all(G._within(cap, c) >= p["cap_margin_m"] - 5e-3 for c in corners)
            assert all(min(math.dist(c, q) for q in footing.piles) <= p["reach_m"] for c in corners)
        assert footing.area_m2 < 1.25 * footing.plain_area_m2  # the cap is hardly larger than the feet need
    assert ground["report"]["piles"] == 3 * len(feet) and ground["report"]["footing_type"] == "piles"
    for zone in ground["root_zones"]:  # and no pile stands where a plant does
        assert min(math.dist(zone.position, q) for q in ground["footings"][zone.pier].piles) >= p["plant_clear_m"]


def test_screw_piles_leave_a_root_zone_the_ground_a_pad_takes():
    zones = beside(NOW, out_m=0.4)  # as near the arch leg as a plant is usually set from a wall
    piled, planted = laid(NOW, zones)
    padded, _ = laid(NOW, zones, **PAD)
    full = math.pi * 0.5**2 * 0.6
    for on_piles, on_pad in zip(piled["root_zones"], padded["root_zones"]):
        assert on_piles.review == "" and on_piles.taken < 0.05 and on_piles.soil_m3 > 0.85 * full  # only the sleeves round the shafts are lost
        assert "a footing takes" in on_pad.review and on_pad.taken > 0.05 and on_pad.soil_m3 < on_piles.soil_m3
        assert 0.0 < on_piles.covered < 0.3 and on_pad.covered == 0.0  # some of its ground lies under the cap, open but out of the rain
        assert on_piles.top_m == G.settings(planted)["footings"]["piles"]["feet_above_soil_m"] and on_pad.top_m == 0.0
    assert "a foot stands in the way" in padded["footings"][PIER].review and piled["footings"][PIER].review == ""
    # a plant set where a pile would stand moves the piles, not the other way about
    bare, _ = laid(NOW, [])
    spot = bare["footings"][PIER].piles[0]
    moved, _ = laid(NOW, [{"id": "on_a_pile", "position_m": list(spot)}])
    assert moved["footings"][PIER].piles != bare["footings"][PIER].piles
    assert min(math.dist(spot, q) for q in moved["footings"][PIER].piles) >= 0.3
    assert all(moved["footings"][k].piles == bare["footings"][k].piles for k in bare["footings"] if k != PIER)  # and only at that pier


def test_feeders_climb_the_outside_of_the_arch_leg_then_its_back():
    group, joints, lines, timber = built(NOW)
    by_id = {m.id: m for m in group["members"]}
    ground, planted = laid(NOW, beside(NOW, out_m=0.65))
    crown = NOW["rooms"][0]["crown"]["centre_m"]
    feeders = ground["feeders"]
    assert [f.id.split(".arch.")[1] for f in feeders] == ["R.feeder", "R.feeder.back", "L.feeder", "L.feeder.back"] and all(f.kind == "feeder" for f in feeders)
    for front, back in (feeders[:2], feeders[2:]):
        arch = by_id[front.member]
        assert front.member == back.member and arch.family == "arch"
        assert front.face == "exterior" and abs(front.from_m - 0.1) < 1e-6  # from the floor, up the face that looks away from the room
        for standoff in front.standoffs:
            st = arch.path.station_at(standoff.at_m)
            assert math.dist(standoff.head[:2], crown) > math.dist(st.point[:2], crown) + 0.1
            assert abs(abs(dot(sub(standoff.head, st.point), st.width_axis)) - (arch.width / 2.0 + front.gap_m)) < 1e-3
        assert back.face == "outer" and back.from_m > 1.5  # the back comes free only where the two arches have parted
        assert front.to_m >= back.from_m + 0.4  # the two run side by side for a stretch: the plant is led round one corner of the arch
        beside_each_other = min(norm(sub(a.head, b.head)) for a in front.standoffs for b in back.standoffs)
        assert beside_each_other < 0.6
    report = check_lines(lines + feeders, group["members"], timber)
    assert report["clear_of_other_members"] and report["feeders"] == 4 and report["lines_from_the_floor"] == len(lines)
    holes = standoff_joints(feeders, timber)
    assert len(holes) == sum(len(f.standoffs) for f in feeders) and {h.cuts[0].face for h in holes} == {"exterior", "outer"}
    rows = line_rows(lines + feeders, group["members"])
    assert [r["kind"] for r in rows].count("feeder") == 4


def test_every_line_that_starts_at_the_pier_is_handed_over_by_a_tie_clear_of_the_timber():
    group, joints, lines, timber = built(NOW)
    ground, planted = laid(NOW, beside(NOW, out_m=0.65))
    reach = G.settings(planted)["feeders"]["reach_m"]
    feet = {m.id for m, _, _ in G.feet_at_piers(planted, group)["feet"][PIER]}
    legs = {line.id for line in lines if line.member in feet}
    assert {h.line for h in ground["handovers"]} == legs and len(legs) >= 6
    bodies = Bodies(group["members"], 0.2)
    for h in ground["handovers"]:
        assert 0.05 < h.gap_m <= reach and abs(norm(sub(h.end, h.start)) - h.gap_m) < 1e-3
        assert h.end[2] > 2.0 and h.below_m > 2.0  # above head height: below it the line is behind the arch legs
        clear = min(bodies.clearance(add(h.start, mul(sub(h.end, h.start), k / 20.0)))[0] for k in range(1, 20))
        assert clear >= 0.015, (h.line, clear)
    assert ground["report"]["handovers"] == len(legs) and not ground["report"]["to_review"]


def test_a_root_zone_out_of_reach_of_any_arch_leg_has_no_feeder_and_says_so():
    zone = beside(NOW, out_m=3.0)[:1]
    ground, _ = laid(NOW, zone)
    assert ground["feeders"] == [] and ground["handovers"] == []
    assert ground["root_zones"][0].feeder == "" and "no arch leg stands within" in ground["root_zones"][0].review
    inside, _ = laid(NOW, [{"id": "in", "position_m": NOW["rooms"][0]["crown"]["centre_m"]}])
    assert "inside the room" in inside["root_zones"][0].review


def test_root_zones_narrow_the_way_through_the_bays_beside_them_and_no_other():
    bare, _ = laid(NOW, [])
    ground, _ = laid(NOW, beside(NOW, out_m=0.65))
    assert [e["bay"] for e in ground["entrances"]] == [b["id"] for b in NOW["rooms"][0]["bays"]]
    narrowed = []
    for before, after in zip(bare["entrances"], ground["entrances"]):
        assert before["between_root_zones_m"] == before["between_arch_legs_m"] > 2.5
        assert after["between_arch_legs_m"] == before["between_arch_legs_m"]
        if after["between_root_zones_m"] < before["between_root_zones_m"]:
            narrowed.append(after["bay"])
    pier_bays = [b["id"] for b in NOW["rooms"][0]["bays"] if PIER in (b["from"], b["to"])]
    assert sorted(narrowed) == sorted(pier_bays)
    tight, planted = laid(NOW, beside(NOW, out_m=0.65, radius_m=1.2), entrances={"least_m": 3.5})
    assert any("under the 3.5 m asked for" in e["review"] for e in tight["entrances"])


def test_the_ground_changes_nothing_else_and_settings_that_make_no_sense_are_refused():
    group, joints, lines, timber = built(NOW)
    planted = {**NOW, "timber": timber, "ground": {"root_zones": beside(NOW, out_m=0.65)}}
    strung = design_lines(planted, [group])[0]
    training = [line for line in strung["lines"] if line.kind == "training"]
    assert training == lines  # every training line is as it was: the ground adds to the building, it moves nothing
    assert [line.kind for line in strung["lines"]].count("feeder") == 4 and strung["ground"]["report"]["root_zones"] == 2
    for own in ({"roots": []}, {"root_zones": [{"id": "a"}]}, {"root_zones": [{"id": "a", "position_m": [0, 0]}, {"id": "a", "position_m": [1, 1]}]}, {"footings": {"margin_m": 1}}, {"footings": {"type": "raft"}}, {"footings": {"pad": {"least_m": 0.5, "margin_m": 0.2}}}, {"footings": {"piles": {"cap_depth_m": 0.4}}}, {"footings": {"piles": {"length": 3}}}, {"root_zones": [{"id": "a", "position_m": [0, 0], "radius_m": 0}]}):
        try:
            G.settings({"ground": own})
        except T.DesignError:
            continue
        raise AssertionError(f"{own} was accepted")


def test_the_frozen_six_bay_room_and_the_design_as_it_stands_take_ground_too():
    zones = beside(SIX, pier="R1.P2", out_m=0.65)
    ground, planted = laid(SIX, zones)
    assert len(ground["root_zones"]) == 2 and len(ground["footings"]) == 6 and len(ground["feeders"]) == 4
    assert ground["report"]["handovers"] >= 4 and all(z.outside for z in ground["root_zones"])
    group, _, lines, timber = built(SIX)
    assert check_lines(lines + ground["feeders"], group["members"], timber)["clear_of_other_members"]
    T.validate(NOW)  # the design file is still a valid design with its ground block in it
    for group in design_lines(NOW):
        if group["ground"]:
            assert check_lines(group["lines"], group["members"], NOW["timber"])["clear_of_other_members"]
            assert len(G.zone_rows(group["ground"])) == len(group["ground"]["root_zones"])


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"{len(tests)} passed")
