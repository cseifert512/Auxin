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


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
FRAME_FIGURES = {"stem_m": "m", "thickest_stem_mm": "mm", "leaves": "", "flowers": "", "roots_m": "m", "root_reach_m": "m"}


def month(date: str) -> str:
    """'2029-06-15' as 'June 2029': the drawing never names a day of the month."""
    y, m = date.split("-")[:2]
    return f"{MONTHS[int(m) - 1]} {y}"


def place_shares(view: str, places: dict, share: float) -> dict:
    out = {}
    for place, p in places.get(view, {}).get("places", {}).items():
        y = (p["y"] - share) / (1 - share)
        if p["in_frame"] and 0 <= y <= 1:
            out[place] = [round(p["x"], 4), round(y, 4)]
    return out


def edges(image: Image.Image) -> dict:
    """The mean colour of each edge strip, so a picture shown whole can be continued to the stage's edges."""
    w, h = image.size
    strips = {"top": (0, 0, w, 3), "bottom": (0, h - 3, w, h), "left": (0, 0, 3, h), "right": (w - 3, 0, w, h)}
    out = {}
    for side, box in strips.items():
        r, g, b = image.crop(box).resize((1, 1), Image.BOX).getpixel((0, 0))[:3]
        out[side] = f"#{r:02x}{g:02x}{b:02x}"
    return out


def shares(places: dict) -> dict:
    """frames.json's per-frame places for one view, rounded; a name absent is out of frame."""
    return {n: [round(p[0], 4), round(p[1], 4)] for n, p in (places or {}).items() if p is not None}


def save(image: Image.Image, to: Path) -> Path:
    """WebP at quality 80 where Pillow can write it, JPEG otherwise."""
    if image.width > MAX_W:
        image = image.resize((MAX_W, round(image.height * MAX_W / image.width)), Image.LANCZOS)
    if to.suffix == ".webp":
        try:
            image.save(to, "WEBP", quality=80, method=4)
            return to
        except (OSError, KeyError, ValueError):
            to = to.with_suffix(".jpg")
    image.save(to, "JPEG", quality=84, optimize=True, progressive=True)
    return to


def timelapse(frames: Path, places: dict, moment_days: dict) -> dict:
    """views/timelapse/<view>/<nnn>.jpg with views/timelapse/frames.json, as far as it has been rendered.
    Not stamped, so not cropped. Each frame carries its own figures."""
    folder = HERE / "views" / "timelapse"
    if not (folder / "frames.json").exists():
        return {}
    try:
        record = load(folder / "frames.json")
        listed = record["frames"]
    except (json.JSONDecodeError, KeyError, OSError):
        print("views/timelapse/frames.json could not be read (being rewritten?): stills only this time")
        return {}
    views = {}
    for f in listed:
        for view in f.get("views", []):
            source = folder / view / f"{f['index']:03d}.jpg"
            if not source.exists():
                continue   # not rendered yet
            (frames / "tl" / view).mkdir(parents=True, exist_ok=True)
            try:
                with Image.open(source) as im:
                    picture = im.convert("RGB")
            except OSError:
                continue   # still being written
            written = save(picture, frames / "tl" / view / f"{f['index']:03d}.webp")
            if view not in views:
                # frames.json's `expected` (or `planned`) counts dates; a view photographed on only some of them
                # gets its share of those so far
                planned = record.get("expected", record.get("planned"))
                listing = sum(view in x.get("views", []) for x in listed)
                expected = planned.get(view) if isinstance(planned, dict) else round(planned * listing / len(listed)) if isinstance(planned, int) else None
                views[view] = {"size": list(picture.size), "frames": [], "places": place_shares(view, places, 0), "edges": edges(picture)}
                if expected:
                    views[view]["expected"] = expected
            entry = views[view]
            frame = {"day": f["day"], "date": f["date"], "month": month(f["date"]), "file": written.relative_to(OUT).as_posix(),
                     "fig": {k: number(f[k], u) for k, u in FRAME_FIGURES.items() if f.get(k) is not None}}
            if f["day"] in moment_days:
                frame["moment"] = moment_days[f["day"]]
            if isinstance(f.get("places"), dict) and view in f["places"]:
                frame["places"] = shares(f["places"][view])   # the camera moves: where each place falls on this frame
            entry["frames"].append(frame)
    return views


def pictures(frames: Path, days: dict) -> dict:
    """Each view as a sequence of frames on one line of days: the time-lapse where it has been rendered for a
    view, otherwise one still per named moment (views/<moment>/<view>.jpg, cropped below the stamped strip)."""
    places = load(HERE / "export" / "places.json")["cameras"]
    views = timelapse(frames, places, {m["day"]: m["id"] for m in days.values()})
    crop = WORDS["crop_top"]
    stills = {}
    for moment in WORDS["moments"]:
        for source in sorted((HERE / "views" / moment).glob("*.jpg")):
            view = source.stem
            if view in views:
                continue
            image = Image.open(source).convert("RGB")
            w, h = image.size
            top = round(h * crop)   # the moment is stamped in the top-left strip; the page shows it itself
            image = image.crop((0, top, w, h))
            written = save(image, frames / f"{view}-{moment}.jpg")
            if view not in stills:
                with Image.open(written) as im:
                    stills[view] = {"size": list(im.size), "frames": [], "places": place_shares(view, places, top / h), "edges": edges(image)}
            entry = stills[view]
            d = days[moment]
            entry["frames"].append({"day": d["day"], "date": d["date"], "month": month(d["date"]), "moment": moment, "file": f"frames/{written.name}"})
    return {**stills, **views}


def figures(growth: dict, meadow: dict) -> dict:
    out = {}
    for key, f in WORDS["figures"].items():
        entry = {"label": f["label"]}
        if f["source"] == "frame":   # only in the time-lapse's frames.json; nothing to fall back on in the stills
            entry.update(kind=f["kind"], source="views/timelapse/frames.json", values={})
        elif f["source"] == "growth":
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
    for font in ("safiro-regular-webfont.woff2", "safiro-medium-webfont.woff2", "argestadisplay-regular-webfont.woff2", "argestadisplay-regularitalic-webfont.woff2", "argestatext-regular-webfont.woff2"):
        if (FONTS / font).exists():
            shutil.copyfile(FONTS / font, OUT / "fonts" / font)
    manifest = {
        "schema": "bower.the-place/1",
        "name": "the-place",
        "made_from": "bower-blender/studies/inhabited-room: the scene's pictures, places.json, site.json and ground/*.json, packed by package_place.py",
        "computed": {"beforehand": "Every picture, place and figure.", "when_shown": "Nothing. The page chooses what to show."},
        "intention": site["intention"],
        "growth_note": site["growth"]["note"],
        "moments": [{"id": m, "day": days[m]["day"], "date": says[m]["date"], "month": month(says[m]["date"]), "says": says[m]["says"]} for m in WORDS["moments"]],
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
    tl = {v: f"{len(x['frames'])} of {x.get('expected') or '?'}" + (" with places" if any("places" in f for f in x["frames"]) else "")
          for v, x in views.items() if x["frames"] and "/tl/" in x["frames"][0]["file"]}
    print(f"{OUT}: {total / 1e6:.1f} MB; time-lapse frames by view: {tl or 'none yet'}")
    for m in manifest["pier"]["missing"]:
        print("missing for the pier study:", m)


if __name__ == "__main__":
    main()
