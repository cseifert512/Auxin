"""Checks on the data a snapshot carries. No Blender needed: python tests/test_snapshot.py"""
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import topology as T  # noqa: E402
from bower.snapshot import CENTRELINE_SCHEMA, centrelines, manifest, schedules, summary  # noqa: E402
from bower.timber import build_timber  # noqa: E402

BASE = T.load(REPO / "design.json")
MEMBERS = {m.id: m for room in BASE["rooms"] for m in build_timber(room, BASE["timber"])}
DATA = centrelines(BASE)


def test_every_member_is_there_once_with_its_section_and_centreline():
    assert DATA["schema"] == CENTRELINE_SCHEMA and DATA["units"] == "m" and DATA["axes"] == {"up": "+Z", "north": "+Y"}
    entries = {e["id"]: e for e in DATA["members"]}
    assert len(entries) == len(DATA["members"]) == len(MEMBERS) and set(entries) == set(MEMBERS)
    for member_id, entry in entries.items():
        m = MEMBERS[member_id]
        assert (entry["width_m"], entry["depth_m"], entry["family"], entry["role"]) == (m.width, m.depth, m.family, m.role)
        points = entry["points_m"]
        assert len(points) == len(entry["depth_axes"]) >= 2
        # the samples start and end on the member, are no further apart than asked, and add up to its length
        assert math.dist(points[0], m.path.anchors[0].co) < 1e-3 and math.dist(points[-1], m.path.anchors[-1].co) < 1e-3
        steps = [math.dist(a, b) for a, b in zip(points, points[1:])]
        assert max(steps) <= DATA["sample_spacing_m"] + 1e-3
        assert abs(sum(steps) - m.path.length) < 0.002 * m.path.length + 1e-3, member_id
        for (a, b), axis in zip(zip(points, points[1:]), entry["depth_axes"]):
            assert abs(math.hypot(*axis) - 1.0) < 1e-3
            along = [(q - p) / max(math.dist(a, b), 1e-9) for p, q in zip(a, b)]
            assert abs(sum(u * v for u, v in zip(along, axis))) < 0.08  # the section's depth stands across the member
        assert len(entry["bezier_m"]) == len(m.path.anchors)
    assert sorted(i for i, e in entries.items() if e["closed"]) == sorted(i for i in MEMBERS if ".ring." in i)


def test_it_is_plain_data_that_survives_json():
    again = json.loads(json.dumps(DATA))
    assert again == DATA


def test_schedules_and_summary_agree_with_the_members():
    member_rows, joint_rows = schedules(BASE)
    assert [row["id"] for row in member_rows] == list(MEMBERS)
    facts = summary(BASE)
    assert facts["members"] == len(MEMBERS) and facts["joints"]["joints"] == len(joint_rows)
    assert facts["rooms"] == [{"id": "R1", "bays": len(BASE["rooms"][0]["bays"]), "piers": len(BASE["rooms"][0]["piers"])}]
    assert abs(facts["total_length_m"] - sum(m.path.length for m in MEMBERS.values())) < 0.06
    low, high = facts["bounds_m"]["min"], facts["bounds_m"]["max"]
    assert low[2] == BASE["rooms"][0]["floor_z_m"] and 6.0 < high[2] < 7.0 and high[0] - low[0] > 10.0


def test_the_manifest_lists_and_hashes_the_files_beside_it():
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / "design.json").write_bytes((REPO / "design.json").read_bytes())
        (Path(folder) / "manifest.json").write_text("stale", encoding="utf-8")
        record = manifest("test-snapshot", BASE, folder, "2026-11-14", commit="abc123")
    assert record["name"] == "test-snapshot" and record["source_commit"] == "abc123"
    assert set(record["files"]) == {"design.json"} and len(record["files"]["design.json"]["sha256"]) == 64
    assert record["model"]["members"] == len(MEMBERS)
    json.dumps(record)


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"{len(tests)} passed")
