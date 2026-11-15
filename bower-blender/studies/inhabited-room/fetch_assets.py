"""Fetch the borrowed assets this study uses into ./assets. No Blender needed.

    python fetch_assets.py                      everything in assets.json
    python fetch_assets.py --only shrub_01,Gardener_Male_01

What they are, what each is for and its licence are in assets.json. Nothing here is Bower geometry
or Bower planting: these are people, surrounding vegetation, ground textures and a sky, borrowed so
that the study does not model generic things again.

    assets/polyhaven/hdris/<id>_<res>.hdr
    assets/polyhaven/textures/<id>/<id>_{diff,nor_gl,rough}_<res>.jpg
    assets/polyhaven/models/<id>/<id>_<res>.blend  and its textures/ beside it, as the file expects
    assets/rocketbox/<avatar>/<avatar>.fbx         and textures/*_color.{jpg,png}

A file already there with the right size is not fetched again. assets.lock.json is rewritten with
every file fetched: where it came from, its size and its MD5. The assets folder is not in git.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
AGENT = {"User-Agent": "blender-scene-study/1.0"}  # Poly Haven's API asks every client to name itself
POLYHAVEN = "https://api.polyhaven.com/files/"
TEXTURE_MAPS = {"Diffuse": "diff", "nor_gl": "nor_gl", "Rough": "rough"}


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=120) as reply:
        return reply.read()


def _fetch(url: str, to: Path, size: int | None, lock: list, source: str, licence: str) -> Path:
    if not (to.exists() and (size is None or to.stat().st_size == size)):
        to.parent.mkdir(parents=True, exist_ok=True)
        to.write_bytes(_get(url))
        print(f"  fetched {to.relative_to(HERE)}  {to.stat().st_size / 1e6:.2f} MB")
    lock.append({"file": to.relative_to(HERE).as_posix(), "from": url, "bytes": to.stat().st_size, "md5": hashlib.md5(to.read_bytes()).hexdigest(), "source": source, "licence": licence})
    return to


def polyhaven(manifest: dict, only: set, lock: list) -> None:
    licence = manifest["licence"]
    for item in manifest["hdris"]:
        if only and item["id"] not in only:
            continue
        files = json.loads(_get(POLYHAVEN + item["id"]))
        entry = files["hdri"][item["res"]]["hdr"]
        _fetch(entry["url"], ASSETS / "polyhaven" / "hdris" / f"{item['id']}_{item['res']}.hdr", entry["size"], lock, f"polyhaven.com/a/{item['id']}", licence)
    for item in manifest["textures"]:
        if only and item["id"] not in only:
            continue
        files = json.loads(_get(POLYHAVEN + item["id"]))
        for theirs, ours in TEXTURE_MAPS.items():
            entry = files[theirs][item["res"]]["jpg"]
            _fetch(entry["url"], ASSETS / "polyhaven" / "textures" / item["id"] / f"{item['id']}_{ours}_{item['res']}.jpg", entry["size"], lock, f"polyhaven.com/a/{item['id']}", licence)
    for item in manifest["models"]:
        if only and item["id"] not in only:
            continue
        files = json.loads(_get(POLYHAVEN + item["id"]))
        entry = files["blend"][item["res"]]["blend"]
        folder = ASSETS / "polyhaven" / "models" / item["id"]
        _fetch(entry["url"], folder / f"{item['id']}_{item['res']}.blend", entry["size"], lock, f"polyhaven.com/a/{item['id']}", licence)
        for relative, part in entry.get("include", {}).items():  # the textures, where the .blend looks for them
            _fetch(part["url"], folder / relative, part["size"], lock, f"polyhaven.com/a/{item['id']}", licence)


def _reduce(tga: Path, px: int) -> Path:
    """A colour texture as a smaller JPEG, or a PNG where it carries transparency. Without Pillow it is left as it came."""
    try:
        from PIL import Image
    except ImportError:
        return tga
    image = Image.open(tga)
    alpha = image.mode == "RGBA" and image.getchannel("A").getextrema()[0] < 255
    image.thumbnail((px, px), Image.LANCZOS)
    out = tga.with_suffix(".png" if alpha else ".jpg")
    if alpha:
        image.save(out)
    else:
        image.convert("RGB").save(out, quality=90)
    tga.unlink()
    return out


def rocketbox(manifest: dict, only: set, lock: list) -> None:
    licence, branch = manifest["licence"], manifest["branch"]
    raw = f"https://raw.githubusercontent.com/microsoft/Microsoft-Rocketbox/{branch}/Assets/Avatars/"
    listing = f"https://api.github.com/repos/microsoft/Microsoft-Rocketbox/contents/Assets/Avatars/"
    for item in manifest["avatars"]:
        name = item["path"].split("/")[-1]
        if only and name not in only:
            continue
        folder = ASSETS / "rocketbox" / name
        source = f"github.com/microsoft/Microsoft-Rocketbox/tree/{branch}/Assets/Avatars/{item['path']}"
        _fetch(f"{raw}{item['path']}/Export/{name}.fbx", folder / f"{name}.fbx", None, lock, source, licence)
        have = sorted((folder / "textures").glob("*_color.*")) if (folder / "textures").exists() else []
        if have:  # already fetched and reduced
            for path in have:
                lock.append({"file": path.relative_to(HERE).as_posix(), "from": f"{raw}{item['path']}/Textures/{path.stem}.tga", "bytes": path.stat().st_size, "md5": hashlib.md5(path.read_bytes()).hexdigest(), "source": source, "licence": licence, "reduced_to_px": manifest["texture_px"]})
            continue
        for entry in json.loads(_get(f"{listing}{item['path']}/Textures?ref={branch}")):
            if not entry["name"].endswith("_color.tga"):
                continue  # colour only: no normal or specular maps in a first pass
            tga = folder / "textures" / entry["name"]
            tga.parent.mkdir(parents=True, exist_ok=True)
            tga.write_bytes(_get(entry["download_url"]))
            small = _reduce(tga, manifest["texture_px"])
            print(f"  fetched {small.relative_to(HERE)}  {small.stat().st_size / 1e6:.2f} MB (from {entry['size'] / 1e6:.1f} MB)")
            lock.append({"file": small.relative_to(HERE).as_posix(), "from": entry["download_url"], "bytes": small.stat().st_size, "md5": hashlib.md5(small.read_bytes()).hexdigest(), "source": source, "licence": licence, "reduced_to_px": manifest["texture_px"]})


def main(argv: list) -> None:
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else set()
    manifest = json.loads((HERE / "assets.json").read_text(encoding="utf-8"))
    lock: list = []
    polyhaven(manifest["polyhaven"], only, lock)
    rocketbox(manifest["rocketbox"], only, lock)
    if not only:  # a partial fetch does not rewrite the record of the whole
        (HERE / "assets.lock.json").write_text(json.dumps({"note": "Written by fetch_assets.py: every borrowed file, where it came from and its hash.", "files": lock}, indent=1) + "\n", encoding="utf-8")
    print(f"{len(lock)} files, {sum(f['bytes'] for f in lock) / 1e6:.1f} MB in {ASSETS}")


if __name__ == "__main__":
    main(sys.argv[1:])
