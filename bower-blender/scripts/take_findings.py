"""Take what a grown planting found about this building's joints into the design.

    cd bower-blender
    python scripts/take_findings.py                       # six-bay-radial-v1 into design/six_bay_radial.json
    python scripts/take_findings.py <snapshot> <design>

Reads  ../drawings-in-code/scenes/<snapshot>/joints-reached.json, which the drawings write: the joints
       of that snapshot's schedule that a plant clinging to the timber reaches, in how many of the
       grown runs, and how soon.
Writes timber.joints.reached_by_plants in the design, with where it came from.

The design is the source of the building, so the finding is copied in, not read from the other
folder each time: a snapshot made from the design then says what it was told. Every joint named
must be one this design still has; a design that has changed since the planting was grown is
refused, and the planting is to be grown again on it. No Blender.

What is then done about them is the design's own say, in timber.joints.plant_detail: bower/joints.py
cuts a lap among them splayed, and notes any other kind of joint as still wanting a detail.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import snapshot, topology  # noqa: E402


def main(name: str = "six-bay-radial-v1", design_file: str = "design/six_bay_radial.json") -> None:
    back = REPO.parent / "drawings-in-code" / "scenes" / name / "joints-reached.json"
    found = json.loads(back.read_text(encoding="utf-8"))
    path = REPO / design_file
    design = json.loads(path.read_text(encoding="utf-8"))
    design["timber"]["joints"].pop("reached_by_plants", None)
    have = {row["id"] for row in snapshot.schedules(topology.load(path))[1]}
    gone = [j["id"] for j in found["joints"] if j["id"] not in have]
    if gone:
        raise SystemExit(f"{len(gone)} of the joints found are not in {design_file} as it is now (the first: {gone[0]}): grow the planting again on this design")
    design["timber"]["joints"]["reached_by_plants"] = {
        "note": "Joints that a plant clinging to the timber reaches unaided in a grown planting. Copied in by scripts/take_findings.py, not authored by hand. How a joint named here is cut is set in plant_detail.",
        "source": {
            "file": f"drawings-in-code/scenes/{name}/joints-reached.json",
            "snapshot": found["snapshot"],
            "runs": found["runs"],
            "statement": found["statement"],
        },
        "joints": {j["id"]: {"runs": j["runs"], "of": j["of"], "first_year": j["first_year"], "plants": j["plants"]} for j in found["joints"]},
    }
    path.write_text(json.dumps(design, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    facts = snapshot.summary(topology.load(path))["joints"]
    print(f"{design_file}: {len(found['joints'])} joints taken from {back.name}; the schedule now notes {facts['reached_by_plants']} of its {facts['joints']} joints as reached by plants ({facts['to_review']} to review in all)")


if __name__ == "__main__":
    main(*sys.argv[1:])
