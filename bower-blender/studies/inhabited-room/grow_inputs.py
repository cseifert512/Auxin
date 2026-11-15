"""Hand this scene's own cables and planting places to the growth simulator.

    cd ../../../drawings-in-code && npm run convert -- <snapshot>        # first: its own reading of the snapshot
    python grow_inputs.py                                                # then this
    npm run grow -- <snapshot> trained 10 7 --specimen=3 --bower=bower-place.json --name=place-10y

drawings-in-code's convert strings its own cables, 75 mm off every leg, and puts every planting place at the level of
the highest pier's feet. This writes a second description of the building beside its bower.json, the same but for:

    cables      the trunk cables of ground/<configuration>.json: bower/lines.py's, with the design's wider gap at a
                foot, in the stretches they are really strung in, at each pier's own level
    stations    where this study plants each climber: beside the foot of its own cable, at the soil

and copies the planting (which climber at which place) from the level room it was made for. Nothing in
drawings-in-code or the simulator is changed. What the simulator still gets wrong on sloping ground is said in
README.md, "Time".
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SITE = json.loads((HERE / "site.json").read_text(encoding="utf-8"))
CONFIG = SITE["default_configuration"]
CFG = SITE["configurations"][CONFIG]
GROUND = json.loads((HERE / "ground" / f"{CONFIG}.json").read_text(encoding="utf-8"))
SCENES = REPO / "drawings-in-code" / "scenes"


def main() -> None:
    scene = SCENES / CFG["snapshot"]
    bower = json.loads((scene / "bower.json").read_text(encoding="utf-8"))
    theirs = {s["id"]: s for s in bower["stations"]}
    cables = [{"id": line["id"], "diameterMm": round(GROUND["cable"]["diameter_m"] * 1000), "points": line["points_m"]} for line in GROUND["training_lines"]]
    stations = []
    for plant in GROUND["plants"]:
        sid = plant["id"].replace("climber.", "bed.")
        if sid not in theirs or not theirs[sid]["note"].endswith(plant["leg"]):
            raise SystemExit(f"{sid}: drawings-in-code has {theirs.get(sid, {}).get('note')!r} there and this study plants on {plant['leg']}: the two no longer agree")
        stations.append({"id": sid, "position": [plant["root_m"][0], plant["root_m"][1], plant["root_level_m"]], "note": f"beside the foot of the cable on {plant['leg']}"})
    bower["cables"], bower["stations"] = cables, stations
    bower["name"] = bower.get("name", CFG["snapshot"]) + ", with the inhabited-room study's own cables and planting places"
    (scene / "bower-place.json").write_text(json.dumps(bower) + "\n", encoding="utf-8")
    shutil.copyfile(SCENES / CFG["planting_from"] / "planting.json", scene / "planting.json")
    low = min(s["position"][2] for s in stations)
    print(f"{scene.name}: {len(cables)} stretches of cable and {len(stations)} planting places written to bower-place.json; the lowest place is at {low} m; planting copied from {CFG['planting_from']}")


if __name__ == "__main__":
    main()
