"""Open the pier by degrees, on this site, and work out what each opening does: ground/openings.json.

    python study_openings.py            # every opening of site.json, pier_study.ring_radius_m
    python study_openings.py --keep     # do not grow again where a run's report is already there
    python study_openings.py --no-light # do not make the light copies of the runs (scenes/<snapshot>/light/, 7 MB each)

For each opening this makes the building (a trial of design/six_bay_meadow.json with that ring radius, or the real
snapshot where the opening is the design's own), sets its pier out as this study does (set_out_meadow.py), hands the
growth simulator that building with this scene's cables, planting places and site (grow_inputs.py), grows it for ten
years, and reads back what the run says. No Blender. Where each figure comes from:

    generated   the members, the feet, how far apart they stand, the way in between the legs: the building model
    proposal    the sole under each pier and where each climber is planted: this study's set-out
    simulated   hours of direct sun at each planting place, month by month; each climber's light class; growth by
                year: the simulator's run, one seed, on a provisional light model and an assumed latitude

Nothing is measured, and no opening is chosen here: the drawing that reads this file says which one the design uses.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLENDER = HERE.parents[1]
REPO = BLENDER.parent
DRAWINGS = REPO / "drawings-in-code"
sys.path.insert(0, str(HERE))

import grow_inputs  # noqa: E402
import set_out_ground as S  # noqa: E402
import set_out_meadow  # noqa: E402

SITE = json.loads((HERE / "site.json").read_text(encoding="utf-8"))
CFG = SITE["configurations"][SITE["default_configuration"]]
STUDY = SITE["pier_study"]
RUN = SITE["growth"]["run"]
POINTS = 16  # how many places along each member the drawing is given


def run(command: str, cwd: Path) -> None:
    done = subprocess.run(command, cwd=str(cwd), shell=True, capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"{command}\n{done.stdout[-1500:]}\n{done.stderr[-1500:]}")


def r3(p):
    return [round(float(c), 3) for c in p]


def one(radius: float, keep: bool) -> dict:
    design = json.loads((BLENDER / "design" / "six_bay_meadow.json").read_text(encoding="utf-8"))
    own = abs(design["timber"]["piers"]["ring_radius_m"] - radius) < 1e-9
    name = CFG["snapshot"] if own else f"trial-meadow-pier-{round(radius * 100):03d}"
    if not own:
        run(f'"{sys.executable}" scripts/trial_snapshot.py {name} timber.piers.ring_radius_m={radius} --design=design/six_bay_meadow.json', BLENDER)
    ground = set_out_meadow.set_out("meadow", {**CFG, "snapshot": name}, SITE)
    members = S.built(name)["group"]["members"]
    run(f"npm run convert -- {name}", DRAWINGS)
    grow_inputs.write(name, ground, CFG["planting_from"])
    report_file = DRAWINGS / "scenes" / name / "runs" / RUN / "report.json"
    if not (keep and report_file.exists()):
        run(f"npm run grow -- {name} trained 10 7 --specimen=3 --bower=bower-place.json --name={RUN}", DRAWINGS)
    report = json.loads(report_file.read_text(encoding="utf-8"))
    light = report["light"]
    stations = {s["stationId"].replace("bed.", "climber."): {"june_h": round(s["hours"][5], 2), "class": s["sunClass"], "hours": [round(h, 1) for h in s["hours"]]} for s in light["stations"]}
    by_year = {}
    for m in report["milestones"]:
        by_year[m["yearsAfterPlanting"]] = by_year.get(m["yearsAfterPlanting"], 0.0) + m["frameworkM"]
    classes = {}
    for s in stations.values():
        classes[s["class"]] = classes.get(s["class"], 0) + 1
    way = next(e for e in ground["entrances"] if e["bay"] == SITE["room"]["entry_bay"])
    apart = []
    for pid, feet in ground["feet"].items():
        px, py = ground["piers"][pid]
        centres = sorted(((sum(c[0] for c in f["corners_m"]) / 4.0, sum(c[1] for c in f["corners_m"]) / 4.0) for f in feet if f["family"] != "arch"), key=lambda c: math.atan2(c[1] - py, c[0] - px) % (2 * math.pi))
        apart += [math.dist(a, b) for a, b in zip(centres, centres[1:])]
    first = next(iter(ground["footings"].values()))
    return {
        "ring_radius_m": radius,
        "snapshot": name,
        "is_the_design": own,
        "feet_apart_m": round(min(apart), 3),
        "way_in_m": way["between_innermost_legs_m"],
        "way_in_points_m": way["innermost_points_m"],
        "sun": {"mean_june_h": round(sum(s["june_h"] for s in stations.values()) / len(stations), 2), "full_sun": classes.get("full_sun", 0), "classes": classes, "stations": stations, "possible_june_h": round(light["possibleHours"][5], 1)},
        "growth": {"stem_m_by_year": {str(k): round(v) for k, v in sorted(by_year.items())}, "light_factor_mean": round(sum(p["growthFactor"] for p in light["plants"]) / len(light["plants"]), 3)},
        "steel_m2": first["steel_area_m2"],
        "footing_review": sorted({f["review"] for f in ground["footings"].values() if f["review"]}),
        "joints": ground["quantities"]["joints"]["value"],
        "levels_m": ground["pier_levels_m"],
        "members": [{"id": m.id, "family": m.family, "w": round(m.width, 3), "d": round(m.depth, 3), "pts": [r3(m.path.station_at(m.path.length * k / (POINTS - 1)).point) for k in range(POINTS)]} for m in members],
        "feet": {pid: [{"member": f["member"], "family": f["family"], "corners": f["corners_m"]} for f in feet] for pid, feet in ground["feet"].items()},
        "plants": [{"id": p["id"], "pier": p["pier"], "taxon": p["taxon"], "root": p["root_m"], "soil_z": p["root_level_m"], "cable_foot": p["cable_foot_m"], "leg": p["leg"]} for p in ground["plants"]],
        "cables": [[r3(q) for q in line["points_m"]] for line in ground["training_lines"]],
        "sole": {pid: {"plates": f["plates_m"], "stubs": f["stubs_m"], "piles": f["piles_m"]} for pid, f in ground["footings"].items()},
    }


def main() -> None:
    keep = "--keep" in sys.argv
    g = SITE["ground"]
    arrival = SITE["paths"]["arrival"]
    path = [[round(arrival["centre_m"][0] + arrival["radius_m"] * math.cos(math.radians(arrival["from_deg"] + (arrival["to_deg"] - arrival["from_deg"]) * k / 24)), 2), round(arrival["centre_m"][1] + arrival["radius_m"] * math.sin(math.radians(arrival["from_deg"] + (arrival["to_deg"] - arrival["from_deg"]) * k / 24)), 2)] for k in range(25)]
    out = {
        "note": "Written by study_openings.py: what each opening of the pier does on this site. Generated, proposed and simulated as its header says. One run and one seed for each opening; the light model is provisional and the latitude assumed.",
        "site": {"latitude_deg": SITE["setting"]["latitude_deg"], "north_deg": SITE["setting"]["north_deg"], "floor_radius_m": SITE["floor"]["radius_m"], "entry_deg": SITE["room"]["entry_deg"], "lookout_deg": SITE["room"]["lookout_deg"], "entry_bay": SITE["room"]["entry_bay"], "path_m": path, "path_width_m": arrival["width_m"], "fall": g["fall"], "fall_towards_deg": g["fall_towards_deg"], "feet_below_soil_m": g["feet_below_soil_m"], "sole_below_soil_m": g["sole_below_soil_m"]},
        "chosen_ring_radius_m": STUDY["chosen_m"],
        "run": RUN,
        "openings": [],
    }
    target = HERE / "ground" / "openings.json"
    for radius in STUDY["ring_radius_m"]:
        entry = one(radius, keep)
        out["openings"].append(entry)
        target.write_text(json.dumps(out) + "\n", encoding="utf-8")  # after each, so that a stopped run still says what it made
        print(f"{entry['snapshot']}: ring {radius} m, feet {entry['feet_apart_m']} m apart, way in {entry['way_in_m']} m, June sun {entry['sun']['mean_june_h']} h a climber, {entry['sun']['full_sun']} of {len(entry['plants'])} in full sun, stems by year {entry['growth']['stem_m_by_year']}, review {entry['footing_review'] or 'nothing'}", flush=True)
    for entry in out["openings"]:  # a light copy of every opening's run, so that a drawing can show the plants at any of them
        if "--no-light" in sys.argv or not (DRAWINGS / "scenes" / entry["snapshot"] / "runs" / RUN / "growth.json").exists():
            continue
        run(f"npm run lighten -- {entry['snapshot']} {RUN}", DRAWINGS)
        print("lightened", entry["snapshot"], flush=True)


if __name__ == "__main__":
    main()
