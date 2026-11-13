"""Topology and envelope checks for the Gate 1 room. No Blender needed: python tests/test_gate1_room.py"""
import copy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import topology as T  # noqa: E402
from bower.envelope import bay_signature, build_envelope, check_envelope  # noqa: E402

BASE = T.load(REPO / "design.json")


def room(design):
    return design["rooms"][0]


def ids(design, kind):
    return [e["id"] for e in room(design)[kind]]


def envelope(design):
    return build_envelope(room(design), design["sampling"])


def assert_valid(design):
    T.validate(design)
    report = check_envelope(envelope(design))
    assert report["ok"], report["problems"]
    return report


def assert_only_these_bays_changed(before, after, changed):
    """Every bay present in both designs and not named in `changed` is vertex-for-vertex identical."""
    env_before, env_after = envelope(before), envelope(after)
    for bay_id in set(ids(before, "bays")) & set(ids(after, "bays")):
        same = bay_signature(env_before, bay_id) == bay_signature(env_after, bay_id)
        assert same != (bay_id in changed), f"{bay_id}: {'unchanged' if same else 'changed'} unexpectedly"


def test_base_room_is_six_unequal_bays_and_a_valid_envelope():
    report = assert_valid(BASE)
    assert ids(BASE, "piers") == [f"R1.P{i}" for i in range(1, 7)]
    assert ids(BASE, "bays") == [f"R1.B{i}" for i in range(1, 7)]
    widths = [2 * T.chord_frame(room(BASE), b)[3] for b in room(BASE)["bays"]]
    assert max(widths) - min(widths) > 0.5
    assert report["patches"] == 24 and report["open_rims"] == 2  # a fan and a roof panel per half-bay


def test_adjacent_patches_share_whole_curves_not_just_endpoints():
    env = envelope(BASE)
    report = check_envelope(env)
    # per bay: a ridge and two eave lines; per pier: the lower and the upper groin
    assert report["shared_curves"] == report["shared_curves_joined_full_length"] == 30
    used_by, bounded_by = {}, {}
    for face, patch in zip(env.faces, env.face_patch):
        for v in face:
            used_by.setdefault(v, set()).add(patch)
    for patch in env.patches.values():
        for edge_id in patch.edges:
            bounded_by.setdefault(edge_id, set()).add(patch.id)
    for edge_id, patch_ids in bounded_by.items():
        if len(patch_ids) == 2:
            verts = env.edge_verts[edge_id]
            assert len(verts) >= 5  # interior samples, not just the two end nodes
            for v in verts:
                assert patch_ids <= used_by[v], f"{edge_id}: a vertex along it is not shared by both patches"


def test_move_pier_reshapes_only_its_two_bays():
    after, change = T.move_pier(BASE, "R1.P3", [5.9, -1.1])
    assert_valid(after)
    assert ids(after, "piers") == ids(BASE, "piers") and ids(after, "bays") == ids(BASE, "bays")
    assert change["modified"] == ["R1.P3", "R1.B2", "R1.B3"]
    assert_only_these_bays_changed(BASE, after, {"R1.B2", "R1.B3"})


def test_crown_height_keeps_ids_and_pier_bases():
    after, _ = T.set_crown(BASE, "R1", height_m=6.8)
    assert_valid(after)
    assert ids(after, "piers") == ids(BASE, "piers") and ids(after, "bays") == ids(BASE, "bays")
    before_env, after_env = envelope(BASE), envelope(after)
    for node, point in after_env.nodes.items():
        if node.endswith(".crown"):
            assert abs(point[2] - 6.8) < 1e-12
        elif node.endswith(".eave"):  # slides along its reshaped groin, staying at eave height
            assert abs(point[2] - room(after)["shape"]["eave_height_m"]) < 1e-9
        else:
            assert point == before_env.nodes[node]


def test_add_bay_issues_new_ids_and_leaves_the_rest_alone():
    after, change = T.add_bay(BASE, "R1.B5")
    assert_valid(after)
    assert change["added"] == ["R1.P7", "R1.B7"] and change["modified"] == ["R1.B5"]
    assert ids(after, "bays") == ["R1.B1", "R1.B2", "R1.B3", "R1.B4", "R1.B5", "R1.B7", "R1.B6"]
    assert ids(after, "piers") == ["R1.P1", "R1.P2", "R1.P3", "R1.P4", "R1.P5", "R1.P7", "R1.P6"]
    for pier in room(BASE)["piers"]:
        assert T.get_pier(room(after), pier["id"]) == pier
    assert_only_these_bays_changed(BASE, after, {"R1.B5"})


def test_remove_bay_collapses_it_and_leaves_the_rest_alone():
    after, change = T.remove_bay(BASE, "R1.B2")
    assert_valid(after)
    assert change["removed"] == ["R1.B2", "R1.P3"]
    assert change["modified"] == ["R1.P2", "R1.B1", "R1.B3"]
    assert ids(after, "bays") == ["R1.B1", "R1.B3", "R1.B4", "R1.B5", "R1.B6"]
    assert ids(after, "piers") == ["R1.P1", "R1.P2", "R1.P4", "R1.P5", "R1.P6"]
    assert_only_these_bays_changed(BASE, after, {"R1.B1", "R1.B3"})


def test_remove_bay_in_place_touches_only_the_following_bay():
    after, change = T.remove_bay(BASE, "R1.B2", merge_at=0)
    assert_valid(after)
    assert change["modified"] == ["R1.B3"]
    assert_only_these_bays_changed(BASE, after, {"R1.B3"})


def test_removing_the_last_bay_of_the_ring_keeps_piers_and_bays_aligned():
    after, _ = T.remove_bay(BASE, "R1.B6")
    assert_valid(after)
    assert [b["from"] for b in room(after)["bays"]] == ids(after, "piers")


def test_ids_are_never_reused():
    d, _ = T.add_bay(BASE, "R1.B1")
    d, removal = T.remove_bay(d, "R1.B7")  # takes B7 and its `to` pier, P2, out of the design
    assert removal["removed"] == ["R1.B7", "R1.P2"]
    d, change = T.add_bay(d, "R1.B4")
    assert change["added"] == ["R1.P8", "R1.B8"]
    assert "R1.P2" not in ids(d, "piers") and "R1.B7" not in ids(d, "bays")
    assert_valid(d)


def test_an_invalid_edit_is_rejected_and_the_design_is_untouched():
    snapshot = copy.deepcopy(BASE)
    for bad in (
        lambda: T.move_pier(BASE, "R1.P3", [-4.0, 3.0]),  # dragged across the room, past its neighbours
        lambda: T.set_crown(BASE, "R1", radius_m=6.0),  # crown ring wider than the room
        lambda: T.move_pier(BASE, "R1.P9", [0.0, 0.0]),  # no such pier
    ):
        try:
            bad()
        except T.DesignError:
            pass
        else:
            raise AssertionError("an invalid edit was accepted")
    assert BASE == snapshot


def test_a_room_cannot_drop_below_three_bays():
    d, _ = T.set_crown(BASE, "R1", radius_m=0.5)  # a small crown leaves room for three wide bays
    for bay_id in ("R1.B6", "R1.B4", "R1.B2"):
        d, _ = T.remove_bay(d, bay_id, merge_at=0)
    assert_valid(d)
    assert len(room(d)["bays"]) == 3
    try:
        T.remove_bay(d, "R1.B1")
    except T.DesignError:
        pass
    else:
        raise AssertionError("a room was allowed to drop below three bays")


def test_apex_handle_round_trips_through_its_chord_relative_parameters():
    after, _ = T.set_apex(BASE, "R1.B3", height_m=5.1, shift=0.2, out_m=0.35)
    bay = T.get_bay(room(after), "R1.B3")
    params = T.apex_params(room(after), bay, T.apex_point(room(after), bay))
    for key, value in params.items():
        assert abs(value - bay[key]) < 1e-12
    assert_valid(after)


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"{len(tests)} passed")
