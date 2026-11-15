"""Pack the drawing 'The place' (and its pier study page) from pictures and files that already exist.

    python package_place.py            needs Pillow; no Blender, no Node

Reads   views/<moment>/<view>.jpg          the pictures (re-rendered later under the same names: sizes are read here)
        export/places.json                 where each named place falls in each view
        site.json, ground/meadow.growth.json, ground/meadow.json, place/stations.json
        ../../../drawings-in-code/exports/deck/shaded-at-the-pier/   the pier study's numbers (data.js) and pictures
        ../../../drawings-in-code/sketches/design-space/grown-pier-opens.js   the two runs' year-10 totals
        ../../../releases/<snapshot>/design.json                    the pier ring radius as designed
        ../../../deck/designx/4/assets/fonts/                       the deck's fonts (copied, not changed)
Writes  ../../../drawings-in-code/exports/deck/the-place/
            index.html, pier-study.html, place.css, place.js, pier-study.js, README.md
            frames/<view>-<moment>.jpg, pier/*.webp, fonts/*.woff2
            manifest.js  (window.BOWER_THE_PLACE = {...}, for opening from a folder)  and manifest.json

Nothing in the piece is computed when it is shown. Differences between the two pier runs are worked out here.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "drawings-in-code" / "exports" / "deck" / "the-place"
PIER = ROOT / "drawings-in-code" / "exports" / "deck" / "shaded-at-the-pier"
GROWN = ROOT / "drawings-in-code" / "sketches" / "design-space" / "grown-pier-opens.js"
FONTS = ROOT / "deck" / "designx" / "4" / "assets" / "fonts"
WORDS = json.loads((HERE / "place" / "stations.json").read_text(encoding="utf-8"))
MAX_W = 1600


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def js_object(path: Path):
    """The JSON inside a file that sets a window global."""
    text = path.read_text(encoding="utf-8")
    start = re.search(r"[^?]=\s*[\[{]", text).end() - 1   # past `window.X =` or `(window.X ??= {})["y"] =`
    return json.loads(text[start:].strip().rstrip(";"))


def kind(source: str) -> str:
    word = source.split(":", 1)[0].strip()
    return {"measured": "measured from the model"}.get(word, word)   # README: nothing is measured from a real thing


def number(value: float, unit: str) -> str:
    text = f"{value:,.0f}" if abs(value) >= 100 or float(value).is_integer() else f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{text} {unit}".strip()


def pictures(frames: Path, days: dict) -> dict:
    """Each view as a sequence of frames on one line of days. Today that is one picture per named moment
    (views/<moment>/<view>.jpg); a longer sequence only needs more entries with their own day and date."""
    places = load(HERE / "export" / "places.json")["cameras"]
    crop = WORDS["crop_top"]
    views = {}
    for moment in WORDS["moments"]:
        for source in sorted((HERE / "views" / moment).glob("*.jpg")):
            view = source.stem
            image = Image.open(source).convert("RGB")
            w, h = image.size
            top = round(h * crop)   # the moment is stamped in the top-left strip; the page shows it itself
            image = image.crop((0, top, w, h))
            if image.width > MAX_W:
                image = image.resize((MAX_W, round(image.height * MAX_W / image.width)), Image.LANCZOS)
            name = f"{view}-{moment}.jpg"
            image.save(frames / name, "JPEG", quality=84, optimize=True, progressive=True)
            entry = views.setdefault(view, {"size": list(image.size), "frames": [], "places": {}})
            entry["frames"].append({"day": days[moment]["day"], "date": days[moment]["date"], "moment": moment, "file": f"frames/{name}"})
            if not entry["places"] and view in places:
                share = top / h
                for place, p in places[view]["places"].items():
                    y = (p["y"] - share) / (1 - share)
                    if p["in_frame"] and 0 <= y <= 1:
                        entry["places"][place] = [round(p["x"], 4), round(y, 4)]
    return views


def figures(growth: dict, meadow: dict) -> dict:
    out = {}
    for key, f in WORDS["figures"].items():
        entry = {"label": f["label"]}
        if f["source"] == "growth":
            entry.update(kind="simulated", source="ground/meadow.growth.json, run " + growth["run"],
                         values={m["id"]: number(m[key], f["unit"]) for m in growth["moments"]})
        else:
            q = meadow["quantities"][f.get("key", key)]
            value = q[f.get("field", "value")]
            entry.update(kind=kind(q["from"]), source="ground/meadow.json: " + q["says"],
                         value=number(value * f.get("scale", 1), f["unit"]))
        out[key] = entry
    return out


def line_of(path: Path, text: str) -> str:
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if text in line:
            return f"{path.relative_to(ROOT).as_posix()}:{n}"
    return path.relative_to(ROOT).as_posix()


def pier(folder: Path) -> dict:
    """The existing pier study: its numbers as its own files hold them, and its pictures copied unchanged."""
    words = WORDS["pier"]
    missing = []
    data = js_object(PIER / "data.js") if (PIER / "data.js").exists() else None
    grown = js_object(GROWN) if GROWN.exists() else None
    if data is None:
        missing.append("drawings-in-code/exports/deck/shaded-at-the-pier/data.js")
    if grown is None:
        missing.append("drawings-in-code/sketches/design-space/grown-pier-opens.js (make it with grown.mjs, drawings-in-code/README.md under sketches)")
    rings = []
    for snapshot in ("six-bay-radial-v1", "six-bay-radial-open-pier"):
        design = ROOT / "releases" / snapshot / "design.json"
        rings.append({"value": load(design)["timber"]["piers"]["ring_radius_m"], "from": line_of(design, '"ring_radius_m"')})
    shots = {}
    for state, set_ in (("closed", "was"), ("opened", "now")):
        shots[state] = {}
        for stage, pattern in (("bare", f"bare-{set_}-{{v}}-00.webp"), ("grown", f"grown-{set_}-{{v}}-23.webp")):
            shots[state][stage] = []
            for v in ("room", "close"):
                source = PIER / "frames" / pattern.format(v=v)
                if source.exists():
                    shutil.copyfile(source, folder / source.name)
                    with Image.open(source) as im:
                        shots[state][stage].append({"src": f"pier/{source.name}", "size": list(im.size)})
                else:
                    missing.append(source.relative_to(ROOT).as_posix())
    rows = []
    D = "drawings-in-code/exports/deck/shaded-at-the-pier/data.js"

    def row(group, label, was, now, unit, digits, source, of=None):
        diff = now - was
        if unit == "%":
            show = lambda v: f"{v:.{digits}f}"
            change = f"{diff:+.{digits}f}"
        else:
            show = lambda v: number(round(v, digits), unit) + (f" of {of}" if of else "")
            change = (f"{diff:+,.{digits}f} {unit}".strip()) + (f" ({diff / was * 100:+.0f}%)" if unit == "m" and was > 50 else "")
        rows.append({"group": group, "label": label, "closed": show(was), "opened": show(now), "change": change, "from": source})

    if data:
        w, n = data["was"], data["now"]
        row("ten", "Midsummer sun per plant", w["sunHours"], n["sunHours"], "h", 1, f"{D}: sunHours (mean of report.json light.plants midsummerHours, sketches/design-space/grown.mjs:73)")
        row("ten", "Climbers in full sun", w["fullSun"], n["fullSun"], "", 0, f"{D}: fullSun (grown.mjs:75)", of=w["plants"])
        row("ten", "Light factor on growth", w["lightGrowth"], n["lightGrowth"], "%", 2, f"{D}: lightGrowth, mean share of growth the light model allows (grown.mjs:74)")
    if grown:
        y10 = [next(y["frameworkM"] for y in grown[k]["report"]["byYear"] if y["year"] == 10) for k in ("start", "end")]
        row("ten", "Stems grown by year 10", y10[0], y10[1], "m", 0, "drawings-in-code/sketches/design-space/grown-pier-opens.js: byYear[10].frameworkM (sum of report.json milestones)")
    if data:
        row("before", f"Stems grown by year {data['years']}", data["was"]["frameworkM"], data["now"]["frameworkM"], "m", 0, f"{D}: frameworkM at year {data['years']}")
        row("before", "Way through the bay", data["wayThrough"][0], data["wayThrough"][1], "m", 2, f"{D}: wayThrough (sketches/design-space/states.js, sweep pier-opens)")
    feet = data["feetApart"] if data else [None, None]
    return {
        **words,
        "missing": missing,
        "values": [
            {"label": words["stops"][0], "feet_m": feet[0], "ring_m": rings[0]["value"], "ring_from": rings[0]["from"], "swept_m": data["ring"][0] if data else None},
            {"label": words["stops"][1], "feet_m": feet[1], "ring_m": rings[1]["value"], "ring_from": rings[1]["from"], "swept_m": data["ring"][1] if data else None},
        ],
        "feet_from": f"{D}: feetApart (sketches/design-space/states.js)",
        "ring_note": "The design sets the ring at 0.34 m, but the generator widens it until the legs fit; nothing moves below about 0.6 m, so the sweep starts at 0.58 m (bower-blender/scripts/sweep_states.py:50-52).",
        "setup": data["setup"] if data else None,
        "statement": data["statement"] if data else None,
        "rows": rows,
        "shots": shots,
    }


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    for sub in ("frames", "pier", "fonts"):
        (OUT / sub).mkdir(parents=True)
    site, growth, meadow = load(HERE / "site.json"), load(HERE / "ground" / "meadow.growth.json"), load(HERE / "ground" / "meadow.json")
    days = {m["id"]: m for m in growth["moments"]}
    views = pictures(OUT / "frames", days)
    for v in views.values():
        v["frames"].sort(key=lambda f: f["day"])
    for view, v in views.items():
        v["note"] = site["cameras"].get(view, {}).get("note", "")
    says = {m["id"]: m for m in site["growth"]["moments"]}
    for font in ("safiro-regular-webfont.woff2", "safiro-medium-webfont.woff2", "argestadisplay-regular-webfont.woff2", "argestatext-regular-webfont.woff2"):
        if (FONTS / font).exists():
            shutil.copyfile(FONTS / font, OUT / "fonts" / font)
    manifest = {
        "schema": "bower.the-place/1",
        "name": "the-place",
        "made_from": "bower-blender/studies/inhabited-room: the scene's pictures, places.json, site.json and ground/*.json, packed by package_place.py",
        "computed": {"beforehand": "Every picture, place and figure.", "when_shown": "Nothing. The page chooses what to show."},
        "intention": site["intention"],
        "growth_note": site["growth"]["note"],
        "moments": [{"id": m, "day": days[m]["day"], "date": says[m]["date"], "says": says[m]["says"]} for m in WORDS["moments"]],
        "views": views,
        "figures": figures(growth, meadow),
        "real": WORDS["real"],
        "life": WORDS["life"],
        "start": WORDS["start"],
        "stations": WORDS["stations"],
        "pier": pier(OUT / "pier"),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "manifest.js").write_text("window.BOWER_THE_PLACE = " + json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    for name in ("index.html", "pier-study.html", "place.css", "place.js", "pier-study.js", "README.md"):
        shutil.copyfile(HERE / "place" / name, OUT / name)
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"{OUT}: {len(list((OUT / 'frames').iterdir()))} frames, {total / 1e6:.1f} MB")
    for m in manifest["pier"]["missing"]:
        print("missing for the pier study:", m)


if __name__ == "__main__":
    main()
