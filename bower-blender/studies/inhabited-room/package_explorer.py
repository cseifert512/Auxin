"""Pack the study's exports into the drawing the deck can show: pictures, layer masks, places and numbers.

    python package_explorer.py            needs Pillow; no Blender

Reads   export/<configuration>/      what `build_scene.py --config <c> --export export` wrote: a picture from each camera
                                     state, a mask of each layer in the same frame, export.json (cameras, where each named
                                     place falls in each picture, which objects each layer holds)
        ground/<configuration>.json  the quantities, and where each comes from (set_out_ground.py)
        explore/                     the page and its words: index.html, explore.js, explore.css, stations.json, README.md
Writes  ../../../drawings-in-code/exports/deck/inhabited-room/
            frames/<configuration>-<view>.webp               the picture
            frames/<configuration>-<view>-<layer>.webp       the layer alone, in its own colour (explore/stations.json), clear elsewhere
            manifest.js      window.BOWER_PLACE = {...}      everything a page needs, readable from a folder with no server
            manifest.json    the same, for anything that is not a browser
            index.html, explore.js, explore.css, README.md

That folder is where the deck's server looks for a piece (deck/serve.mjs answers /designx/pieces/<name>/ from
drawings-in-code/exports/deck/<name>/). Nothing in it is computed when it is shown: every picture, mask, place and
number is made here or before.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[2] / "drawings-in-code" / "exports" / "deck" / "inhabited-room"
SITE = json.loads((HERE / "site.json").read_text(encoding="utf-8"))
WORDS = json.loads((HERE / "explore" / "stations.json").read_text(encoding="utf-8"))


def picture(source: Path, to: Path) -> None:
    Image.open(source).convert("RGB").save(to, "WEBP", quality=82, method=5)


def mask(source: Path, to: Path, colour: str) -> bool:
    """A layer's render in the layer's own colour, clear where it does not show. False, and nothing written, where it shows nowhere.

    The colour is put in here and not by the page, because a picture used as a CSS mask does not load from a folder
    opened without a server, and the drawing has to open that way."""
    alpha = Image.open(source).convert("RGBA").getchannel("A")
    if alpha.getextrema()[1] < 8:
        return False
    flat = Image.new("RGBA", alpha.size, (*bytes.fromhex(colour), 0))
    flat.putalpha(alpha)
    flat.save(to, "WEBP", quality=84, alpha_quality=88, method=5, exact=True)
    return True


def aliases(points: dict, ground: dict) -> dict:
    """The same names in every configuration for where a pier's climbers root and where each meets its lines."""
    out = dict(points)
    by_pier: dict = {}
    for plant in ground["plants"]:
        by_pier.setdefault(plant["pier"], []).append(plant["id"])
    for pier, ids in by_pier.items():
        for k, plant in enumerate(sorted(ids)):
            if plant in points:
                out[f"rooted.{pier}.{k + 1}"] = points[plant]
            if plant + ".meets" in points:
                out[f"meets.{pier}.{k + 1}"] = points[plant + ".meets"]
    return out


def main() -> None:
    frames = OUT / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    configurations, views, size = {}, {}, None
    for name in WORDS["configurations"]:
        folder = HERE / "export" / name
        record = json.loads((folder / "export.json").read_text(encoding="utf-8"))
        ground = json.loads((HERE / "ground" / f"{name}.json").read_text(encoding="utf-8"))
        size = record["size"]
        entry = {
            "label": record["label"],
            "what": record["what"],
            "snapshot": record["snapshot"],
            "sources": {k: ground[k] for k in ("footing_status", "planting_status", "root_zone_status") if k in ground},
            "to_review": sorted({f["review"] for f in ground["footings"].values() if f.get("review")}),
            "quantities": ground["quantities"],
            "frames": {},
            "masks": {},
            "points": {},
            "objects": {layer: v["objects"] for layer, v in record["layers"].items()},
        }
        for view, v in record["views"].items():
            picture(folder / f"{view}.png", frames / f"{name}-{view}.webp")
            entry["frames"][view] = f"frames/{name}-{view}.webp"
            entry["masks"][view] = {}
            for layer in record["layers"]:
                source = folder / f"{view}.{layer}.png"
                if layer in WORDS["layers"] and source.exists() and mask(source, frames / f"{name}-{view}-{layer}.webp", WORDS["layers"][layer]["colour"]):
                    entry["masks"][view][layer] = f"frames/{name}-{view}-{layer}.webp"
            entry["points"][view] = aliases(v["points"], ground)
            views.setdefault(view, {"camera": v["camera"]})
        configurations[name] = entry
    manifest = {
        "schema": "bower.place/1",
        "name": "inhabited-room",
        "made_from": "bower-blender/studies/inhabited-room: one Blender scene built in each configuration by build_scene.py, set out by set_out_ground.py, packed by package_explorer.py",
        "computed": {
            "beforehand": "Every picture, layer mask, place and quantity. The quantities are measured from each configuration's geometry by set_out_ground.py, and each says where it comes from.",
            "when_shown": "Nothing. The page chooses which pictures, masks, labels and numbers to show; it measures and evaluates nothing.",
        },
        "status": "Preview pictures, to prove the drawing can be explored. Sizes are provisional; no footing is engineered; no growth is simulated in these pictures.",
        "size": size,
        "paper": WORDS["paper"],
        "ink": WORDS["ink"],
        "views": views,
        "layers": {key: {**WORDS["layers"][key], "what": json.loads((HERE / "export" / WORDS["configurations"][0] / "export.json").read_text(encoding="utf-8"))["layers"][key]["what"]} for key in WORDS["layers"]},
        "configurations": configurations,
        "start": WORDS["start"],
        "stations": WORDS["stations"],
        "measure_names": WORDS["measure_names"],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    (OUT / "manifest.js").write_text("window.BOWER_PLACE = " + json.dumps(manifest, separators=(",", ":")) + ";\n", encoding="utf-8")
    for name in ("index.html", "explore.js", "explore.css", "README.md"):
        shutil.copyfile(HERE / "explore" / name, OUT / name)
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"{OUT}: {len(list(frames.iterdir()))} frames, {total / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
