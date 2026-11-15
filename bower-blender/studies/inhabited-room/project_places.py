"""Where named places of the scene fall in each camera's picture: export/places.json.

    blender-launcher.exe --background --factory-startup --disable-autoexec inhabited_room.blend --python project_places.py

A drawing to explore needs to know where, in each picture, a thing is: to put a click target or a label on it. This
opens the saved scene, renders nothing, and writes for every camera the place of each named point as a share of the
picture's width and height (0, 0 is the top left), with whether it is in front of the camera and inside the frame.
The places are read from site.json and ground/<configuration>.json, so they follow the scene.
"""
import json
import sys
from math import cos, radians, sin
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

HERE = Path(__file__).resolve().parent


def main() -> None:
    site = json.loads((HERE / "site.json").read_text(encoding="utf-8"))
    config = site["default_configuration"]
    ground = json.loads((HERE / "ground" / f"{config}.json").read_text(encoding="utf-8"))
    scene = bpy.context.scene
    g = site["ground"]
    gx, gy = -g["fall"] * cos(radians(g["fall_towards_deg"])), -g["fall"] * sin(radians(g["fall_towards_deg"]))
    level = ground["pier_levels_m"]
    top = max(level, key=level.get)
    z0 = level[top] + g["feet_below_soil_m"] - (gx * ground["piers"][top][0] + gy * ground["piers"][top][1])
    soil = lambda x, y: z0 + gx * x + gy * y  # noqa: E731
    rf = site["floor"]["radius_m"]
    entry, lookout = radians(site["room"]["entry_deg"]), radians(site["room"]["lookout_deg"])
    arrival = site["paths"]["arrival"]
    on_path = lambda deg: (arrival["centre_m"][0] + arrival["radius_m"] * cos(radians(deg)), arrival["centre_m"][1] + arrival["radius_m"] * sin(radians(deg)))  # noqa: E731
    places = {
        "room.middle": (0.0, 0.0, soil(0, 0) + 0.05),
        "room.crown": (0.0, 0.0, 6.2),
        "way-in": (rf * cos(entry), rf * sin(entry), soil(rf * cos(entry), rf * sin(entry)) + 0.05),
        "look-out": (rf * cos(lookout), rf * sin(lookout), soil(rf * cos(lookout), rf * sin(lookout)) + 0.05),
        "path.gate": (*on_path(arrival["from_deg"]), soil(*on_path(arrival["from_deg"])) + 0.05),
        "path.bend": (*on_path((arrival["from_deg"] + arrival["to_deg"]) / 2.0), soil(*on_path((arrival["from_deg"] + arrival["to_deg"]) / 2.0)) + 0.05),
        "hollow": (*g["hollow"]["at_m"], soil(*g["hollow"]["at_m"]) - g["hollow"]["depth_m"]),
        "swale.high": (g["swale"]["radius_m"] * cos(radians(15)), g["swale"]["radius_m"] * sin(radians(15)), soil(g["swale"]["radius_m"] * cos(radians(15)), g["swale"]["radius_m"] * sin(radians(15)))),
        "meadow.path": (14.0 * cos(lookout), 14.0 * sin(lookout), soil(14.0 * cos(lookout), 14.0 * sin(lookout))),
        "woodland.edge": (0.0, site["woodland"]["edge_y_m"], soil(0.0, site["woodland"]["edge_y_m"]) + 2.0),
    }
    for pid, (x, y) in ground["piers"].items():
        places[f"pier.{pid}.foot"] = (x, y, level[pid] + g["feet_below_soil_m"])
        places[f"pier.{pid}.head"] = (x, y, level[pid] + 2.6)
    for plant in ground["plants"]:
        places[f"{plant['id']}.root"] = (plant["root_m"][0], plant["root_m"][1], plant["root_level_m"])
    for k, person in enumerate(site["people"]):
        x, y = person["at_m"]
        places[f"person.{k + 1}"] = (x, y, soil(x, y) + 1.0)
    out = {"note": "Written by project_places.py from the saved scene: where each named place falls in each camera's picture, as shares of its width and height from the top left.", "cameras": {}}
    for key, view in site["cameras"].items():
        cam = bpy.data.objects.get(f"CAM_{key}")
        if cam is None:
            continue
        scene.camera = cam
        scene.render.resolution_x, scene.render.resolution_y = view["size_px"]
        shown = {}
        for name, at in places.items():
            co = world_to_camera_view(scene, cam, Vector(at))
            shown[name] = {"x": round(co.x, 4), "y": round(1.0 - co.y, 4), "in_front": co.z > 0, "in_frame": 0.0 <= co.x <= 1.0 and 0.0 <= co.y <= 1.0 and co.z > 0}
        out["cameras"][key] = {"size_px": view["size_px"], "places": shown}
    folder = HERE / "export"
    folder.mkdir(exist_ok=True)
    (folder / "places.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # a windowless Blender prints nothing back
        (HERE / "export").mkdir(exist_ok=True)
        (HERE / "export" / "places.error.txt").write_text(repr(error), encoding="utf-8")
        sys.exit(1)
