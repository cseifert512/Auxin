"""Checks on the crown as a line (a spine) and on the long room it makes. No Blender needed: python tests/test_spine.py"""
import copy
import math
import runpy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import topology as T  # noqa: E402
from bower.envelope import Roof  # noqa: E402
from bower.joints import find_joints  # noqa: E402
from bower.spine import Spine, crown_spine  # noqa: E402
from bower.timber import build_timber, clearances  # noqa: E402

SCRIPT = runpy.run_path(str(REPO / "scripts" / "gate2_forms.py"))
NOW = T.load(REPO / "design.json")
HALL = SCRIPT["formed"](NOW, {name: changes for name, _, changes in SCRIPT["FORMS"]}["7_long_hall"])
SPINES = [Spine((0.3, -0.2), (6.3, -0.2)), Spine((1.0, 2.0), (-2.0, 6.0)), Spine((0.0, 0.0), (0.0, -4.5)), Spine((2.0, 1.0), (2.5, 1.2))]
TWO_PI = 2.0 * math.pi


def room(design):
    return design["rooms"][0]


def at(spine, bearing, distance):
    (fx, fy), (ux, uy) = spine.frame(bearing)
    return (fx + ux * distance, fy + uy * distance)


def to_segment(spine, p):
    (ax, ay), (bx, by) = spine.a, spine.b
    t = max(0.0, min(1.0, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / spine.length**2))
    return math.dist(p, (ax + t * (bx - ax), ay + t * (by - ay)))


def rejected(action) -> bool:
    try:
        action()
    except T.DesignError:
        return True
    return False


def test_round_a_point_the_coordinates_are_plain_polar():
    point = Spine((1.5, -2.0))
    assert point.length == 0.0 and point.period == TWO_PI and point.centre == (1.5, -2.0)
    for k in range(40):
        angle, radius = 0.17 * k, 0.5 + 0.3 * k
        bearing, distance = point.locate((1.5 + radius * math.cos(angle), -2.0 + radius * math.sin(angle)))
        assert abs(distance - radius) < 1e-12 and abs((bearing - angle + math.pi) % TWO_PI - math.pi) < 1e-12
        assert point.frame(angle) == ((1.5, -2.0), (math.cos(angle), math.sin(angle)))
    assert point.shift(0.4, 1.5, 3.0) == 0.4 + 1.5 / 3.0
    assert point.swing(0.4, 0.7, 2.0, 5.0) == 0.4 + 0.7 * math.log(5.0 / 2.0)  # an equal-angle spiral
    assert abs(point.arc(6.0, 0.5, 2.0) - 2.0 * ((0.5 - 6.0) % TWO_PI)) < 1e-12 and point.perimeter(2.0) == TWO_PI * 2.0


def test_bearing_and_distance_round_trip_round_a_spine():
    for spine in SPINES:
        assert abs(spine.period - (TWO_PI + 2.0 * spine.length)) < 1e-12
        for k in range(300):
            bearing, distance = spine.period * (k + 0.37) / 300, 0.4 + 0.02 * k
            p = at(spine, bearing, distance)
            assert abs(to_segment(spine, p) - distance) < 1e-9  # distance is measured to the nearest point of the spine
            back, away = spine.locate(p)
            assert abs(away - distance) < 1e-9 and abs((back - bearing + spine.period / 2.0) % spine.period - spine.period / 2.0) < 1e-9


def test_the_curve_at_one_distance_is_two_straight_sides_and_two_half_circles():
    for spine in SPINES:
        distance, n = 2.3, 400
        around = spine.perimeter(distance)
        assert abs(around - (TWO_PI * distance + 2.0 * spine.length)) < 1e-12
        bearings = [spine.along(around * k / n, distance) for k in range(n + 1)]
        points = [at(spine, b, distance) for b in bearings]
        assert math.dist(points[0], points[-1]) < 1e-6 and abs(bearings[-1] - bearings[0] - spine.period) < 1e-6  # once round, counter-clockwise
        chords = [math.dist(p, q) for p, q in zip(points, points[1:])]
        assert max(chords) <= around / n + 1e-9 and sum(chords) > 0.999 * around  # evenly spaced by distance, not by angle
        for one, other in zip(bearings, bearings[1:]):
            assert abs(spine.arc(one, other, distance) - around / n) < 1e-6
        for k in range(0, n, 23):  # moving along it can be undone
            assert abs(spine.shift(spine.shift(bearings[k], 3.1, distance), -3.1, distance) - bearings[k]) < 1e-6
        ux, uy = spine.u
        cross = [abs((p[0] - spine.a[0]) * uy - (p[1] - spine.a[1]) * ux) for p in points]
        assert sum(abs(c - distance) < 1e-9 for c in cross) > n * spine.length / around  # the sides are straight, and parallel to the spine


def test_a_course_runs_straight_beside_a_spine_and_spirals_round_its_ends():
    spine = Spine((0.0, 0.0), (6.0, 0.0))
    beside = spine.locate((3.0, 1.0))[0]  # half way along the left side
    stops = [at(spine, spine.swing(beside, 0.8, 1.0, out), out) for out in (1.0, 1.5, 2.0)]
    assert abs(abs(stops[2][0] - stops[0][0]) - 0.8) < 1e-9 and abs(stops[2][1] - stops[0][1] - 1.0) < 1e-9  # 0.8 along for 1.0 out
    assert math.dist(stops[1], ((stops[0][0] + stops[2][0]) / 2.0, (stops[0][1] + stops[2][1]) / 2.0)) < 1e-9  # in a straight line
    assert stops[2][0] < stops[0][0]  # a positive lean turns counter-clockwise: toward A along the left side
    round_the_end = spine.locate((7.0, 0.5))[0]
    assert abs(spine.swing(round_the_end, 0.8, 1.0, 2.0) - round_the_end - 0.8 * math.log(2.0)) < 1e-12


def test_a_spine_shrunk_to_nothing_gives_the_point_crowns_room_back():
    """The long-room code is the round room's code: draw the crown out by a micron and the same members come back."""
    cx, cy = room(NOW)["crown"]["centre_m"]
    tiny = copy.deepcopy(NOW)
    room(tiny)["crown"]["spine_m"] = [[cx - 3e-7, cy - 4e-7], [cx + 3e-7, cy + 4e-7]]
    one, other = Roof(room(NOW)), Roof(room(tiny))
    assert other.spine.length > 0.0 and one.spine.length == 0.0
    for k in range(300):
        angle, radius = TWO_PI * k / 300, 1.2 + 4.0 * ((k * 37) % 100) / 100
        p = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
        assert math.dist(one.drape(p)[0], other.drape(p)[0]) < 1e-5
    round_room = {m.id: m for m in build_timber(room(NOW), NOW["timber"])}
    drawn_out = {m.id: m for m in build_timber(room(tiny), tiny["timber"])}
    assert round_room.keys() == drawn_out.keys()
    for member_id, member in round_room.items():
        if member_id == "R1.ring.top":  # a circle of four arcs round a point, a fitted curve round a spine: the same ring
            assert abs(member.path.length - drawn_out[member_id].path.length) < 1e-3
            continue
        mine, theirs = member.path.anchors, drawn_out[member_id].path.anchors
        assert len(mine) == len(theirs) and max(math.dist(p.co, q.co) for p, q in zip(mine, theirs)) < 1e-4, member_id


def test_a_crown_takes_a_spine_and_carries_it_when_it_moves():
    crown = room(HALL)["crown"]
    (ax, ay), (bx, by) = crown["spine_m"]
    assert math.dist(crown["centre_m"], ((ax + bx) / 2.0, (ay + by) / 2.0)) < 1e-9
    moved, change = T.set_crown(HALL, "R1", centre_m=[crown["centre_m"][0] + 0.2, crown["centre_m"][1] - 0.1])
    assert change["modified"] == ["R1.crown"]
    assert all(math.dist(p, (q[0] + 0.2, q[1] - 0.1)) < 1e-6 for p, q in zip(room(moved)["crown"]["spine_m"], crown["spine_m"]))
    longer, _ = T.set_crown(HALL, "R1", spine_m=[[-3.3, 0.0], [3.5, 0.2]])
    assert room(longer)["crown"]["centre_m"] == [0.1, 0.1] and abs(crown_spine(room(longer)["crown"]).length - math.hypot(6.8, 0.2)) < 1e-12
    point, _ = T.set_crown(HALL, "R1", spine_m=[])  # and back to a point, where the ring allows it
    assert "spine_m" not in room(point)["crown"] and crown_spine(room(point)["crown"]).length == 0.0

    off_centre = copy.deepcopy(HALL)
    room(off_centre)["crown"]["centre_m"] = [crown["centre_m"][0] + 0.5, crown["centre_m"][1]]
    assert rejected(lambda: T.validate(off_centre))  # the centre is the middle of the spine
    assert rejected(lambda: T.set_crown(HALL, "R1", spine_m=[[0.0, 0.0], [0.01, 0.0]]))  # too short to be a line
    assert rejected(lambda: T.set_crown(NOW, "R1", spine_m=crown["spine_m"]))  # the round room's ring is too small for this spine


def test_the_hall_is_laid_out_along_its_spine():
    spine, layout = crown_spine(room(HALL)["crown"]), room(HALL)["layout"]
    reach, weights = layout["outline"]["radius_m"], layout["bay_weights"]
    assert len(room(HALL)["bays"]) == 10 and spine.length > 5.0
    places = [spine.locate(p["position_m"]) for p in room(HALL)["piers"]]
    assert all(abs(distance - reach) < 2e-3 for _, distance in places)  # every pier stands on the offset of the spine
    around = spine.perimeter(reach)
    for k, weight in enumerate(weights):  # and the bays share out its length, not its angle
        assert abs(spine.arc(places[k][0], places[(k + 1) % 10][0], reach) / around - weight / sum(weights)) < 1e-3
    beside = [p["position_m"] for p in room(HALL)["piers"] if 1.0 < (p["position_m"][0] - spine.a[0]) * spine.u[0] + (p["position_m"][1] - spine.a[1]) * spine.u[1] < spine.length - 1.0]
    assert len(beside) >= 2 and all(abs(abs((p[0] - spine.a[0]) * spine.u[1] - (p[1] - spine.a[1]) * spine.u[0]) - reach) < 2e-3 for p in beside)  # straight sides

    # an arch stands across the axis at each end
    for end, outward in ((spine.a, -1.0), (spine.b, 1.0)):
        tip = (end[0] + outward * spine.u[0] * reach, end[1] + outward * spine.u[1] * reach)
        nearest = min(room(HALL)["bays"], key=lambda bay: math.dist(T.apex_point(room(HALL), bay)[:2], tip))
        assert math.dist(T.apex_point(room(HALL), nearest)[:2], tip) < 0.6

    assert T.reconcile(HALL) == (HALL, [])  # the same layout always gives the same ring
    more, change = T.set_bay_count(HALL, "R1", 12)
    assert len(room(more)["bays"]) == 12 and [p["id"] for p in room(more)["piers"]][:10] == [p["id"] for p in room(HALL)["piers"]]
    assert all(abs(spine.locate(p["position_m"])[1] - reach) < 2e-3 for p in room(more)["piers"])


def test_single_piers_and_bays_can_still_be_edited_on_a_hall():
    spine = crown_spine(room(HALL)["crown"])
    more, change = T.add_bay(HALL, room(HALL)["bays"][2]["id"])
    new = next(p for p in room(more)["piers"] if p["id"] in change["added"])
    assert len(room(more)["bays"]) == 11 and abs(spine.locate(new["position_m"])[1] - 5.6) < 1e-3  # the new pier stands on the same offset
    fewer, _ = T.remove_bay(more, room(more)["bays"][6]["id"])
    assert len(room(fewer)["bays"]) == 10
    pier = room(HALL)["piers"][4]
    bearing, distance = spine.locate(pier["position_m"])
    moved, _ = T.move_pier(HALL, pier["id"], [round(c, 3) for c in at(spine, bearing, distance + 0.4)])
    assert room(moved)["layout"] == {"bays": 10} and T.reconcile(moved) == (moved, [])  # moved by hand, it stays where it is put
    assert rejected(lambda: T.move_pier(HALL, pier["id"], at(spine, bearing, 3.0)))  # too near the lantern


def test_the_roof_keeps_one_section_all_the_way_round_a_spine():
    roof = Roof(room(HALL))
    spine = roof.spine
    for lam in (0.0, 0.35, 0.8, 1.0):  # the lantern is the same section at every bearing
        ring = [roof.on_lantern(spine.period * k / 240, lam)[0] for k in range(240)]
        assert max(p[2] for p in ring) - min(p[2] for p in ring) < 1e-9
        away = [spine.locate(p[:2])[1] for p in ring]
        assert max(away) - min(away) < 1e-9
    assert abs(spine.locate(roof.on_lantern(1.0, 1.0)[0][:2])[1] - roof.top_radius) < 1e-9
    # and the canopy has no step where a straight side meets a round end
    n, distance = 3000, roof.base_radius + 1.0
    heights = [roof.drape(at(spine, spine.along(spine.perimeter(distance) * k / n, distance), distance))[0][2] for k in range(n + 1)]
    assert max(abs(a - b) for a, b in zip(heights, heights[1:])) < 0.03


def test_the_hall_is_built_and_jointed_by_the_same_code_as_the_round_room():
    members = build_timber(room(HALL), HALL["timber"])
    joints = find_joints(members, HALL["timber"])[0]
    roof = Roof(room(HALL))
    spine = roof.spine
    by_family = {}
    for m in members:
        by_family.setdefault(m.family, []).append(m)
    assert clearances(members)["collisions"] == []
    assert len(by_family["arch"]) == 20 and len(by_family["hoop"]) == 20 and len(by_family["rib"]) == 2 * HALL["timber"]["lattice"]["ribs_per_family"]

    # the crown ring is drawn out with the spine, and the ribs reach it evenly spaced along it
    ring = next(m for m in members if m.id == "R1.ring.top")
    away = [spine.locate(a.co[:2])[1] for a in ring.path.anchors]
    assert max(away) - min(away) < 1e-9 and len({round(a.co[2], 9) for a in ring.path.anchors}) == 1
    assert abs(ring.path.length - spine.perimeter(away[0])) < 0.01 * spine.perimeter(away[0])
    heads = {}
    for m in by_family["rib"]:
        head = m.path.anchors[-1].co
        assert abs(spine.locate(head[:2])[1] - roof.top_radius) < 1e-6 and abs(head[2] - roof.top_z) < 1e-6
        heads.setdefault(m.id.rsplit(".", 1)[1], []).append(head)
    count = len(heads)
    middles = [spine.locate(((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0))[0] for _, (a, b) in sorted(heads.items())]
    for one, other in zip(middles, middles[1:] + middles[:1]):
        assert abs(spine.arc(one, other, roof.top_radius) - spine.perimeter(roof.top_radius) / count) < 0.02

    kinds = {}
    for j in joints:
        kinds[j.kind] = kinds.get(j.kind, 0) + 1
    assert {"cross_lap", "housing", "crown_seat", "paired_heads", "mitre", "pier_mitre", "base"} <= kinds.keys()
    assert kinds["cross_lap"] > 500 and kinds["crown_seat"] == len(by_family["rib"]) and kinds["pier_mitre"] == 10
    assert sum(1 for j in joints if j.review) <= 4


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"{len(tests)} passed")
