"""Primary timber and joint checks for the Gate 2 room. No Blender needed: python tests/test_gate2_timber.py"""
import copy
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import topology as T  # noqa: E402
from bower.centreline import cross, dot, norm, sub, unit  # noqa: E402
from bower.joints import LAP_ORDER, find_joints, joint_rows, lap_layer  # noqa: E402
from bower.member import sweep  # noqa: E402
from bower.timber import ARCHES, LATTICE, LATTICES, build_timber, clearances, schedule  # noqa: E402

BASE = T.load(REPO / "design.json")
ROOM = BASE["rooms"][0]
RIBS = BASE["timber"]["lattice"]["ribs_per_family"]
HOOPS = len(BASE["timber"]["arches"]["hoops_m"])
THROUGH = ("rib", "fill")  # tiers whose ribs are all kept: they follow bearings, not bays
FLOOR = ROOM["floor_z_m"]


def timber(design):
    return build_timber(design["rooms"][0], design["timber"])


def shapes(members):
    """Each member's exact control geometry, for testing that an edit left it untouched."""
    return {m.id: tuple((a.co, a.handle_left, a.handle_right) for a in m.path.anchors) for m in members}


def tier(member) -> str:
    """rib | fill | fine for a lattice rib, from its ID; empty for anything else."""
    parts = member.id.split(".")
    return parts[1] if len(parts) == 4 and parts[2] in ("ccw", "cw") else ""


def feet(member) -> list:
    """The ends of a member that stand on the floor."""
    return [a.co for a in (member.path.anchors[0], member.path.anchors[-1]) if abs(a.co[2] - FLOOR) < 1e-9]


def bay_parts(bay_id: str) -> set:
    return {f"{bay_id}.arch.{s}" for s in "LR"} | {f"{bay_id}.hoop{k}" for k in range(HOOPS)}


def shifted(**changes):
    """The base design with timber parameters changed, given as section__key=value."""
    design = copy.deepcopy(BASE)
    for path, value in changes.items():
        section, key = path.split("__")
        design["timber"][section][key] = value
    return design


MEMBERS = timber(BASE)
BY_ID = {m.id: m for m in MEMBERS}
REPORT = clearances(MEMBERS)
JOINTS, _, CUTTERS = find_joints(MEMBERS, BASE["timber"])  # as set: every joint milled


def closed_and_solid(verts, faces) -> bool:
    """A mesh every edge of which is shared by exactly two faces wound opposite ways, enclosing a positive volume."""
    edges = Counter((a, b) for f in faces for a, b in zip(f, f[1:] + f[:1]))
    volume = sum(dot(verts[f[0]], cross(verts[f[k]], verts[f[k + 1]])) / 6.0 for f in faces for k in range(1, len(f) - 1))
    return all(n == 1 for n in edges.values()) and all((b, a) in edges for a, b in edges) and volume > 0.0


def test_every_bay_gets_its_arch_and_hoops_and_the_room_its_lattice():
    assert len(BY_ID) == len(MEMBERS)
    for bay in ROOM["bays"]:
        assert bay_parts(bay["id"]) <= set(BY_ID)
    assert Counter(m.family for m in MEMBERS)["arch"] == 2 * len(ROOM["bays"])
    for hand in ("ccw", "cw"):
        for j in range(RIBS):
            assert f"R1.rib.{hand}.{j:02d}" in BY_ID and f"R1.fill.{hand}.{j:02d}" in BY_ID
    fine = {m.id for m in MEMBERS if tier(m) == "fine"}
    assert RIBS <= len(fine) <= 4 * RIBS  # those that would run into a pier are left out
    assert {m.id for m in MEMBERS if ".ring." in m.id} == {"R1.ring.top", "R1.ring.fill", "R1.ring.fine"}
    depths = {m.depth for m in MEMBERS if m.family in LATTICE}
    assert len(depths) == 1  # one depth, so the whole lattice is flush on both faces


def test_frames_are_sound_and_the_arches_are_planar():
    for m in MEMBERS:
        stations = m.path.stations(0.1)
        for s in stations:
            assert abs(norm(s.depth_axis) - 1) < 1e-9 and abs(dot(s.tangent, s.depth_axis)) < 1e-9
            assert norm(sub(cross(s.width_axis, s.depth_axis), s.tangent)) < 1e-9
        if m.family == "arch":
            a, b, c = stations[0].point, stations[len(stations) // 2].point, stations[-1].point
            normal = unit(cross(sub(b, a), sub(c, a)))
            assert max(abs(dot(sub(s.point, a), normal)) for s in stations) < 1e-6, f"{m.id} is not planar"


def test_arch_legs_stand_upright_and_the_halves_meet_at_the_apex():
    for bay in ROOM["bays"]:
        left, right = BY_ID[f"{bay['id']}.arch.L"], BY_ID[f"{bay['id']}.arch.R"]
        assert norm(sub(left.path.anchors[-1].co, right.path.anchors[-1].co)) < 1e-9
        for half in (left, right):
            foot, spring = half.path.anchors[0].co, half.path.anchors[1].co
            assert abs(foot[2] - FLOOR) < 1e-9
            assert math.hypot(spring[0] - foot[0], spring[1] - foot[1]) < 1e-9
            assert abs(spring[2] - foot[2] - ROOM["shape"]["pier_height_m"]) < 1e-9
        for k in range(HOOPS):  # a hoop is one member, standing on the floor at both of the bay's piers
            assert len(feet(BY_ID[f"{bay['id']}.hoop{k}"])) == 2


def test_the_arch_is_the_edge_of_the_roof_and_the_lattice_is_housed_into_it():
    arches = [m for m in MEMBERS if m.family == "arch"]
    centrelines = {a.id: [s.point for s in a.path.stations(0.03)] for a in arches}
    housed = 0
    for m in MEMBERS:
        if not tier(m):
            continue
        foot = m.path.anchors[0].co
        if feet(m):
            assert tier(m) in THROUGH
        else:  # it stops inside the arch that lists it as a joint, cut to that arch's plane
            landed = [a for a in arches if m.nodes[0] in a.nodes]
            assert landed, f"{m.id} lands on no arch"
            assert min(norm(sub(p, foot)) for a in landed for p in centrelines[a.id]) < 0.15, f"{m.id} stops short of its arch"
            assert m.start_cut is not None and abs(m.start_cut[2]) < 1e-12
            housed += 1
    assert housed >= 4 * RIBS
    housings = [j for j in JOINTS if j.kind == "housing" and j.cuts[0].face == "start"]
    assert len(housings) == housed
    assert max(j.cuts[0].skew_deg for j in housings) < 15.0  # every rib turns to meet its arch squarely


def test_the_crown_is_a_collar_on_ribs_that_arrive_in_pairs():
    crown, ring = ROOM["crown"], BY_ID["R1.ring.top"]
    assert ring.family == "crown" and ring.family not in LATTICE
    heads = defaultdict(list)
    for m in MEMBERS:
        if tier(m) == "rib":
            head = m.path.anchors[-1].co
            assert abs(math.hypot(head[0] - crown["centre_m"][0], head[1] - crown["centre_m"][1]) - crown["radius_m"]) < 1e-6
            assert abs(head[2] - FLOOR - crown["height_m"]) < 1e-6
            assert m.end_cut == (0.0, 0.0, 1.0)  # cut level, to seat in the ring
            heads[m.nodes[-1]].append(m)
    assert len(heads) == RIBS and all(len(pair) == 2 for pair in heads.values())
    for a, b in heads.values():  # side by side: apart by a rib's width and the gap, not through each other
        apart = norm(sub(a.path.anchors[-1].co, b.path.anchors[-1].co))
        assert a.width < apart < a.width + 0.05
    # the ring covers the rib heads and sits on them
    assert ring.width >= max(m.depth for m in MEMBERS if tier(m) == "rib")
    assert min(a.co[2] for a in ring.path.anchors) - ring.depth / 2.0 < FLOOR + crown["height_m"]
    assert Counter(j.kind for j in JOINTS)["crown_seat"] == 2 * RIBS


def test_every_pier_is_a_bundle_of_legs_that_continue_into_the_roof():
    piers = {p["id"]: p["position_m"] for p in ROOM["piers"]}
    legs = defaultdict(list)
    for m in MEMBERS:
        if m.family in LATTICE:
            for foot in feet(m):
                pid = min(piers, key=lambda p: math.hypot(foot[0] - piers[p][0], foot[1] - piers[p][1]))
                legs[pid].append((m, foot))
    assert set(legs) == set(piers)
    for pid, group in legs.items():
        assert sum(m.family == "hoop" for m, _ in group) == 2 * HOOPS  # a hoop from the bay on each side
        assert len(group) > 2 * HOOPS, f"no rib comes down into {pid}"
        radii = {round(math.hypot(foot[0] - piers[pid][0], foot[1] - piers[pid][1]), 6) for _, foot in group}
        assert len(radii) == 1 and 0.3 < radii.pop() < 0.9  # they stand on one arc about the pier
        for m, foot in group:
            anchors = m.path.anchors if foot == m.path.anchors[0].co else m.path.anchors[::-1]
            up = anchors[1].co
            assert up[2] - foot[2] > 0.5 and math.hypot(up[0] - foot[0], up[1] - foot[1]) < 1e-9  # upright
            assert m.path.length > 3.0  # and it goes on into the roof


def test_nothing_touches_except_at_joints():
    assert REPORT["collisions"] == []
    family = {m.id: m.family for m in MEMBERS}
    assert all(family[p["a"]] in LATTICE and family[p["b"]] in LATTICE for p in REPORT["notches"])
    assert not [p for p in REPORT["notches"] if p["at_m"][2] < FLOOR + 2.0]  # the legs of a pier stand clear of each other


def test_every_crossing_of_the_lattice_is_a_lap_set_out_on_both_members():
    laps = [j for j in JOINTS if j.kind == "cross_lap"]
    assert len({j.id for j in JOINTS}) == len(JOINTS)
    crossed = {frozenset(j.members) for j in JOINTS if j.kind in ("cross_lap", "alongside")}
    for pair in REPORT["notches"]:  # every pair the clearance check finds overlapping has a joint
        assert frozenset((pair["a"], pair["b"])) in crossed, pair
    for j in laps:
        first, second = (BY_ID[i] for i in j.members)
        assert LAP_ORDER.index(lap_layer(first)) <= LAP_ORDER.index(lap_layer(second))  # the one that goes in first...
        assert [c.face for c in j.cuts] == ["outer", "inner"]  # ...is notched on its outer face
        for cut, member, other in zip(j.cuts, (first, second), (second, first)):
            assert cut.member == member.id and 0.0 <= cut.at_m <= member.path.length + 1e-3
            assert cut.length_m >= other.width  # wide enough to take the other member
            assert 0.25 * member.depth < cut.depth_m < 0.75 * member.depth
        assert abs(sum(c.depth_m for c in j.cuts) - (first.depth + second.depth) / 2.0) < 0.02  # the two halves make up the depth
    crossings = Counter(i for j in laps for i in j.members)
    for m in MEMBERS:
        if tier(m) == "rib":
            assert crossings[m.id] >= 6, f"{m.id} crosses only {crossings[m.id]} members"
    for bay in ROOM["bays"]:  # rib ends cross the hoops on their way to the arch: the laddered band
        assert crossings[f"{bay['id']}.hoop0"] >= 6
    assert not [j for j in JOINTS if j.review], "a joint is flagged as needing its own detail"
    rows = joint_rows(JOINTS)
    assert len(rows) == len(JOINTS) and all(row["a_operation"] == "lap" and row["b_operation"] == "lap" for row in rows if row["kind"] == "cross_lap")


def test_every_joint_comes_with_the_volume_to_mill_out_of_each_member():
    laps = Counter(c.member for j in JOINTS if j.kind == "cross_lap" for c in j.cuts)
    pockets = Counter(c.member for j in JOINTS if j.kind in ("housing", "crown_seat") for c in j.cuts if c.operation == "housing")
    mitres = Counter(c.member for j in JOINTS if j.kind == "pier_mitre" for c in j.cuts)
    for m in MEMBERS:
        mine = CUTTERS.get(m.id, [])
        assert len(mine) >= laps[m.id] + pockets[m.id] + mitres[m.id], m.id
        assert all(closed_and_solid(verts, faces) for verts, faces in mine), f"a cutter for {m.id} is not a closed solid"
    assert set(CUTTERS) == {m.id for m in MEMBERS}  # every member is cut somewhere
    # a plain member mesh is closed too, rings included: those have no ends
    for m in MEMBERS:
        assert closed_and_solid(*sweep(m, m.path.stations(0.08))), m.id


def test_a_member_crossed_on_both_faces_at_one_place_keeps_a_third_of_its_depth():
    thirds = [j for j in JOINTS if j.kind == "cross_lap" and abs(j.cuts[0].depth_m - j.cuts[1].depth_m) > 0.05]
    assert thirds, "this room has places where three members meet"
    by_member = defaultdict(list)
    for j in JOINTS:
        if j.kind == "cross_lap":
            for cut in j.cuts:
                by_member[cut.member].append(cut)
    for member_id, cuts in by_member.items():
        depth = BY_ID[member_id].depth
        for a in cuts:
            for b in cuts:
                if a.face == "outer" and b.face == "inner" and abs(a.at_m - b.at_m) < (a.length_m + b.length_m) / 2.0:
                    assert a.depth_m + b.depth_m <= 0.75 * depth, f"{member_id} is left under a quarter of its depth at {a.at_m} m"


def test_the_simpler_notch_model_is_still_available_and_says_what_it_cannot_cut():
    def volume(verts, faces):
        return sum(dot(verts[f[0]], cross(verts[f[k]], verts[f[k + 1]])) / 6.0 for f in faces for k in range(1, len(f) - 1))

    joints, NOTCHES, cutters = find_joints(MEMBERS, shifted(joints__cut_meshes="notches")["timber"])
    assert not cutters
    laps = [j for j in joints if j.kind == "cross_lap"]
    uncut = [j for j in laps if "not cut in the model" in j.review]
    assert 0 < len(uncut) <= 0.2 * len(laps)
    cut_laps = Counter(c.member for j in laps if "not cut in the model" not in j.review for c in j.cuts)
    for m in MEMBERS:
        stations = m.path.stations(0.08)
        notches = NOTCHES.get(m.id, [])
        assert len(notches) <= cut_laps[m.id]  # notches side by side on one face are merged
        assert bool(notches) == bool(cut_laps[m.id])
        verts, faces = sweep(m, stations, notches)
        edges = Counter((a, b) for f in faces for a, b in zip(f, f[1:] + f[:1]))
        assert all(n == 1 for n in edges.values()) and all((b, a) in edges for a, b in edges), f"{m.id}: mesh is not closed"
        whole, cut = volume(*sweep(m, stations)), volume(verts, faces)
        assert cut <= whole + 1e-9 and (cut > 0.75 * whole), m.id
        if notches:
            assert cut < whole
        for a, b in zip(notches, notches[1:]):
            assert a.hi < b.lo  # in order along the member, and apart


def test_bend_radii_stay_above_the_floor_this_design_was_tuned_to():
    rows = {r["id"]: r for r in schedule(MEMBERS, BASE["timber"], REPORT, JOINTS)}
    floor = {"arch": 1.5, "hoop": 0.6, "rib": 0.6, "fill": 0.6, "fine": 0.5, "ring": 0.9, "crown": 0.99}
    for m in MEMBERS:
        assert rows[m.id]["min_bend_radius_m"] >= floor[m.family], f"{m.id}: {rows[m.id]['min_bend_radius_m']} m"
    assert sum(r["laps_cut_on_outer_face"] + r["laps_cut_on_inner_face"] for r in rows.values()) == 2 * sum(j.kind == "cross_lap" for j in JOINTS)


def regenerated(edited):
    """The edited room's members, checked: the through tiers keep their members and IDs, nothing collides, joints are found."""
    members = timber(edited)
    assert clearances(members)["collisions"] == []
    assert {m.id for m in members if tier(m) in THROUGH} == {m.id for m in MEMBERS if tier(m) in THROUGH}
    possible = {f"R1.fine.{hand}.{n:02d}" for hand in ("ccw", "cw") for n in range(2 * RIBS)}
    assert {m.id for m in members if tier(m) == "fine"} <= possible
    bays = [b["id"] for b in edited["rooms"][0]["bays"]]
    assert {m.id for m in members if m.family in ("arch", "hoop")} == set().union(*(bay_parts(b) for b in bays))
    joints, _, cutters = find_joints(members, edited["timber"])
    laps = [j for j in joints if j.kind == "cross_lap"]
    assert len(laps) > 200 and sum(1 for j in joints if j.review) <= 0.02 * len(laps)
    assert all(closed_and_solid(verts, faces) for group in cutters.values() for verts, faces in group)
    return members


def test_moving_a_pier_regenerates_the_timber_and_leaves_distant_arches_alone():
    edited, _ = T.move_pier(BASE, "R1.P3", [7.0, 0.3])
    before, after = shapes(MEMBERS), shapes(regenerated(edited))
    for bay in ("R1.B1", "R1.B4", "R1.B5", "R1.B6"):  # arches that do not stand on the moved pier
        for side in "LR":
            assert after[f"{bay}.arch.{side}"] == before[f"{bay}.arch.{side}"]
    assert any(after[i] != before[i] for i in after if ".rib." in i)


def test_crown_height_regenerates_the_lantern_and_leaves_the_arches():
    edited, _ = T.set_crown(BASE, "R1", height_m=7.0)
    members = regenerated(edited)
    before, after = shapes(members and MEMBERS), shapes(members)
    for m in members:
        if m.family == "arch":
            assert after[m.id] == before[m.id], m.id
        if tier(m) == "rib":
            assert after[m.id] != before[m.id], m.id
            assert abs(m.path.anchors[-1].co[2] - 7.0) < 1e-9


def test_adding_a_bay_adds_its_arch_and_hoops_and_keeps_the_lattice():
    edited, _ = T.add_bay(BASE, "R1.B1")
    members = regenerated(edited)
    assert {m.id for m in members if not tier(m)} - set(BY_ID) == bay_parts("R1.B7")


def test_removing_a_bay_removes_its_arch_and_hoops_and_keeps_the_lattice():
    edited, _ = T.remove_bay(BASE, "R1.B2")
    members = regenerated(edited)
    assert {i for i, m in BY_ID.items() if not tier(m)} - {m.id for m in members} == bay_parts("R1.B2")


def test_the_generators_are_chosen_by_name_and_the_earlier_arrangements_still_build():
    assert {"edge", "paired", "none"} <= set(ARCHES) and {"spiral", "none"} <= set(LATTICES)
    paired = timber(shifted(arches__type="paired"))  # a light arch on the edge, a heavier one standing proud
    assert Counter(m.family for m in paired)["inner"] == Counter(m.family for m in paired)["arch"] == 2 * len(ROOM["bays"])
    assert clearances(paired)["collisions"] == []
    butted = timber(shifted(piers__legs=False))  # ribs drawn to a pier stop at its head instead of standing as legs
    assert not [m for m in butted if tier(m) and feet(m)] and clearances(butted)["collisions"] == []
    assert {m.family for m in timber(shifted(lattice__type="none"))} == {"arch", "hoop"}
    assert "arch" not in {m.family for m in timber(shifted(arches__type="none"))}
    oblique = timber(shifted(lattice__land_square_m=0.0, lattice__lean_top_deg=None, lattice__pair_gap_m=None))  # ribs hold one lean throughout
    assert clearances(oblique)["collisions"] == []
    try:
        timber(shifted(arches__type="portal"))
    except T.DesignError:
        pass
    else:
        raise AssertionError("an unknown generator was accepted")


def test_shifting_the_parameters_regenerates_without_collisions():
    for change in (
        {"lattice__lean_deg": 25.0},  # ribs nearer the meridians
        {"lattice__lean_rim_deg": 62.0},  # ribs that sweep round as they near the arches
        {"lattice__ribs_per_family": 16},  # a finer weave everywhere
        {"arches__hoops_m": [0.7]},  # one hoop instead of two
        {"lattice__gather_m": 1.6},  # bigger fans at the piers
    ):
        members = timber(shifted(**change))
        assert clearances(members)["collisions"] == [], change
        assert shapes(members) != shapes(MEMBERS), change
        assert find_joints(members, BASE["timber"])[0], change


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"{len(tests)} passed")
