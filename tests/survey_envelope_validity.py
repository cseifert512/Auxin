"""Random walks of valid topology edits, checking the envelope after every one.

A robustness survey rather than a pass/fail test, because it is slow:
    python tests/survey_envelope_validity.py [edits_per_walk]

Each walk starts from design.json and applies random pier moves, crown and apex
changes, bay splits and bay collapses. Edits the topology rules reject are
counted separately; every edit they accept must give a valid envelope.
"""
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import topology as T  # noqa: E402
from bower.envelope import build_envelope, check_envelope  # noqa: E402


def random_edit(design, rng):
    room = design["rooms"][0]
    kind = rng.choice(["pier", "pier", "crown_height", "crown_centre", "crown_radius", "apex", "add", "remove"])
    if kind == "pier":
        pier = rng.choice(room["piers"])
        x, y = pier["position_m"]
        return kind, T.move_pier(design, pier["id"], [x + rng.uniform(-0.8, 0.8), y + rng.uniform(-0.8, 0.8)])[0]
    if kind == "crown_height":
        return kind, T.set_crown(design, room["id"], height_m=rng.uniform(4.6, 8.0))[0]
    if kind == "crown_centre":
        return kind, T.set_crown(design, room["id"], centre_m=[rng.uniform(-1, 1), rng.uniform(-1, 1)])[0]
    if kind == "crown_radius":
        return kind, T.set_crown(design, room["id"], radius_m=rng.uniform(0.6, 2.2))[0]
    if kind == "apex":
        bay = rng.choice(room["bays"])
        return kind, T.set_apex(design, bay["id"], height_m=rng.uniform(3.2, 5.6), shift=rng.uniform(-0.3, 0.3), out_m=rng.uniform(-0.2, 0.6))[0]
    if kind == "add":
        if len(room["bays"]) >= 9:
            raise T.DesignError("survey keeps rooms to nine bays")
        return kind, T.add_bay(design, rng.choice(room["bays"])["id"], rng.uniform(0.35, 0.65))[0]
    return kind, T.remove_bay(design, rng.choice(room["bays"])["id"], rng.choice([0, 0.5, 1]))[0]


def walk(seed: int, edits: int) -> dict:
    rng = random.Random(seed)
    design = T.load(REPO / "design.json")
    valid, rejected, failures, worst = 0, 0, [], 1.0
    for _ in range(edits):
        try:
            kind, candidate = random_edit(design, rng)
        except T.DesignError:
            rejected += 1
            continue
        report = check_envelope(build_envelope(candidate["rooms"][0], candidate["sampling"]))
        worst = min(worst, report["min_normal_agreement_in_patch"])
        if report["ok"]:
            valid += 1
            design = candidate
        else:
            failures.append((kind, len(candidate["rooms"][0]["bays"]), report["problems"]))
    return {"seed": seed, "valid": valid, "invalid": len(failures), "rejected_by_topology": rejected, "worst_agreement": worst, "failures": failures}


if __name__ == "__main__":
    edits = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    started = time.time()
    totals = {"valid": 0, "invalid": 0}
    for seed in (7, 11, 23):
        result = walk(seed, edits)
        totals["valid"] += result["valid"]
        totals["invalid"] += result["invalid"]
        print("seed {seed}: valid {valid}, invalid {invalid}, rejected by topology rules {rejected_by_topology}, worst in-patch agreement {worst_agreement:.3f}".format(**result))
        for failure in result["failures"][:5]:
            print("   invalid:", failure)
    print(f"total: {totals['valid']} valid envelopes, {totals['invalid']} invalid, {time.time() - started:.0f} s")
