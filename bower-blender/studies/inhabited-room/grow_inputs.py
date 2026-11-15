"""Hand this scene's own cables, planting places and site to the growth simulator.

    cd ../../../drawings-in-code && npm run convert -- <snapshot>        # first: its own reading of the snapshot
    python grow_inputs.py                                                # then this
    npm run grow -- <snapshot> trained 10 7 --specimen=3 --bower=bower-place.json --name=place-10y

drawings-in-code's convert strings its own cables, 75 mm off every leg, puts every planting place at the level of
the highest pier's feet, and knows nothing of the site. This writes a second description of the building beside its
bower.json, the same but for:

    cables      the trunk cables of the set-out: bower/lines.py's, with the design's wider gap at a foot, in the
                stretches they are really strung in, at each pier's own level
    stations    where this study plants each climber: beside the foot of its own cable, at the soil
    site        which way the building is turned (site.json, setting.north_deg), an assumed latitude, and what
                stands near enough to shade it: the woodland's front rows, the trees on the bend of the path, the wall

and copies the planting (which climber at which place) from the level room it was made for. Nothing in
drawings-in-code or the simulator is changed. What the simulator still gets wrong on sloping ground is said in
README.md, "Time".

`write(snapshot, ground)` does it for any snapshot and its set-out: study_openings.py uses it for each opening of the pier.
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SITE = json.loads((HERE / "site.json").read_text(encoding="utf-8"))
SCENES = REPO / "drawings-in-code" / "scenes"
TREE_M = 4.56  # the borrowed tree's own height, and its spread: measured from the model
SPREAD_M = 4.29


def site_for_the_simulator() -> dict:
    """The site as the simulator's light model takes it. The trees are the scene's, put more simply: two rows for
    the woodland's front, at the middle of the sizes it is drawn at, and the three trees on the bend of the path."""
    setting, wood, wall = SITE["setting"], SITE["woodland"], SITE["wall"]
    scale = sum(wood["scale"]) / 2.0
    things = []
    for row in range(2):
        x = -24.0 + (wood["spacing_m"] / 2.0 if row else 0.0)
        while x <= 30.0:
            things.append({"id": f"wood.{row + 1}.{len(things) + 1}", "kind": "tree", "at": [round(x, 2), round(wood["edge_y_m"] + 1.6 + row * wood["spacing_m"], 2)], "heightM": round(TREE_M * scale, 1), "crownRadiusM": round(SPREAD_M * scale / 2.0, 1), "leafHabit": "deciduous", "note": "the woodland along the north-east edge, put simply"})
            x += wood["spacing_m"]
    for k, (x, y, s, _) in enumerate(SITE["veil"]["trees"]):
        things.append({"id": f"bend.{k + 1}", "kind": "tree", "at": [x, y], "heightM": round(TREE_M * s * 1.35, 1), "crownRadiusM": round(SPREAD_M * s * 1.35 / 2.0, 1), "leafHabit": "deciduous", "note": "a tree on the inside of the path's bend"})
    (wx, wy), a = wall["through_m"], math.radians(wall["along_deg"])
    for name, s0, s1 in (("south", wall["from_m"], -wall["gate_m"] / 2.0), ("north", wall["gate_m"] / 2.0, wall["to_m"])):
        things.append({"id": f"wall.{name}", "kind": "wall", "from": [round(wx + s0 * math.cos(a), 2), round(wy + s0 * math.sin(a), 2)], "to": [round(wx + s1 * math.cos(a), 2), round(wy + s1 * math.sin(a), 2)], "heightM": wall["height_m"], "note": "the garden wall"})
    return {
        "name": "the designed site of the inhabited-room study (latitude assumed)",
        "latitudeDeg": setting["latitude_deg"],
        "bearingDeg": (setting["north_deg"] - 90.0) % 360.0,  # the compass bearing of +y, when north lies toward north_deg
        "obstructions": things,
    }


def write(snapshot: str, ground: dict, planting_from: str) -> dict:
    scene = SCENES / snapshot
    bower = json.loads((scene / "bower.json").read_text(encoding="utf-8"))
    cables = [{"id": line["id"], "diameterMm": round(ground["cable"]["diameter_m"] * 1000), "points": line["points_m"]} for line in ground["training_lines"]]
    stations = []
    for plant in ground["plants"]:
        sid = plant["id"].replace("climber.", "bed.")  # this study's own places replace convert's, whichever legs it chose: the planting names them by these ids
        stations.append({"id": sid, "position": [plant["root_m"][0], plant["root_m"][1], plant["root_level_m"]], "note": f"beside the foot of the cable on {plant['leg']}"})
    bower["cables"], bower["stations"], bower["site"] = cables, stations, site_for_the_simulator()
    bower["name"] = bower.get("name", snapshot) + ", with the inhabited-room study's own cables, planting places and site"
    (scene / "bower-place.json").write_text(json.dumps(bower) + "\n", encoding="utf-8")
    shutil.copyfile(SCENES / planting_from / "planting.json", scene / "planting.json")
    return {"cables": len(cables), "stations": len(stations), "shading": len(bower["site"]["obstructions"]), "bearing": bower["site"]["bearingDeg"]}


def main() -> None:
    config = SITE["default_configuration"]
    cfg = SITE["configurations"][config]
    ground = json.loads((HERE / "ground" / f"{config}.json").read_text(encoding="utf-8"))
    did = write(cfg["snapshot"], ground, cfg["planting_from"])
    print(f"{cfg['snapshot']}: {did['cables']} stretches of cable, {did['stations']} planting places and a site (+y bears {did['bearing']} degrees, {did['shading']} things that shade) written to bower-place.json; planting copied from {cfg['planting_from']}")


if __name__ == "__main__":
    main()
