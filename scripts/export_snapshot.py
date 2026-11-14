"""Write a named snapshot of the model to releases/<name>/ for other work to build on.

The scene is first rebuilt from design.json, so the snapshot is what the source
generates, not whatever happens to be open. See bower/snapshot.py for what the
folder holds and how it is meant to be used.

Run inside Blender:
    runpy.run_path(r"<repo>/scripts/export_snapshot.py")["main"]("six-bay-v1")

`commit` is the git commit of the source, recorded in the manifest. It is passed
in because this script runs no shell commands.
"""
import csv
import datetime
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "design.json"


def main(name: str, commit: str | None = None, design_path=DESIGN, rebuild: bool = True) -> dict:
    import bpy

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    for module in [m for m in sys.modules if m == "bower" or m.startswith("bower.")]:
        del sys.modules[module]
    from bower import snapshot, topology
    from bower.blender_scene import build_design, write_snapshot

    if not name or any(c in name for c in '\\/:*?"<>| '):
        raise ValueError(f"snapshot name {name!r} must be usable as a folder name, without spaces")
    folder = REPO / "releases" / name
    if folder.exists() and any(folder.iterdir()):
        raise FileExistsError(f"{folder} already holds a snapshot; snapshots are not overwritten, give the new one a new name")
    scene = bpy.context.scene
    design = topology.load(design_path)

    checks = None
    if rebuild:
        report = build_design(scene, design)
        checks = [
            {
                "room": room["room"],
                "meshes_closed": room["timber"]["meshes_closed"],
                "collisions_estimated": len(room["timber"]["collisions_estimated"]),
                "milled": room["timber"]["milled"],
                "mesh_intersections_in_scene": room["timber"]["mesh_intersections_in_scene"],
                "max_centreline_deviation_m": room["timber"]["max_centreline_deviation_m"],
            }
            for room in report["rooms"]
            if room["timber"]
        ]

    folder.mkdir(parents=True, exist_ok=True)
    (folder / "design.json").write_bytes(Path(design_path).read_bytes())
    # every text file is written with the same line endings on any platform, since the manifest hashes them
    (folder / "centrelines.json").write_text(json.dumps(snapshot.centrelines(design), separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    member_rows, joints = snapshot.schedules(design)
    for filename, rows in (("members.csv", member_rows), ("joints.csv", joints)):
        with open(folder / filename, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    written = write_snapshot(scene, folder)
    tools = {"blender": bpy.app.version_string, **written}
    record = snapshot.manifest(name, design, folder, datetime.date.today().isoformat(), commit, checks, tools)
    (folder / "manifest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return {"folder": str(folder), "files": {k: v["bytes"] for k, v in record["files"].items()}, "model": record["model"], "checks_at_export": checks}


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[-1]), indent=2))
