"""Write a changed design's centre lines as a trial building that a planting can be grown on.

    cd bower-blender
    python scripts/trial_snapshot.py trial-pier-120 timber.piers.ring_radius_m=1.2
    python scripts/trial_snapshot.py trial-crown-52 crown_height=5.2

A change is either a path into the design file, or the key of a control in bower/controls.py,
which is applied to room R1. Several may be given. The design changed is design/six_bay_radial.json
unless --design=<file> names another.

Writes ../releases/<name>/centrelines.json and design.json, which is all that `npm run convert`,
`plant` and `grow` in drawings-in-code read. No Blender, so there are no milled meshes, no schedules
and no manifest: a trial is not a snapshot, the studio cannot draw it, and git ignores it. Its name
must start with "trial-". Safe to delete, and remade by the same command.
"""

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import controls, snapshot, topology  # noqa: E402

ROOM = "R1"


def change(design: dict, key: str, value: float) -> dict:
    if key in controls.BY_KEY:
        return controls.adjust(design, ROOM, key, value)
    new = copy.deepcopy(design)
    at = new
    *path, last = key.split(".")
    for part in path:
        at = at[part]
    if last not in at:
        raise KeyError(f"{key}: the design has no such value")
    at[last] = value
    return new


def main(argv: list) -> None:
    options = dict(a[2:].split("=", 1) for a in argv if a.startswith("--"))
    name, *changes = [a for a in argv if not a.startswith("--")]
    if not name.startswith("trial-"):
        raise SystemExit('a trial\'s name must start with "trial-", so that it is never taken for a snapshot')
    folder = REPO.parent / "releases" / name
    design = topology.load(str(REPO / options.get("design", "design/six_bay_radial.json")))
    made = []
    for item in changes:
        key, value = item.split("=", 1)
        number = float(value)
        design = change(design, key, int(number) if number.is_integer() and "." not in value else number)
        made.append(f"{key} = {value}")
    lines = snapshot.centrelines(design)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "design.json").write_text(json.dumps(design, indent=2) + "\n", encoding="utf-8")
    (folder / "centrelines.json").write_text(json.dumps(lines, separators=(",", ":")) + "\n", encoding="utf-8")
    (folder / "TRIAL.md").write_text(
        f"# {name}\n\nA trial, not a snapshot: centre lines only, written by `bower-blender/scripts/trial_snapshot.py`\n"
        f"from `{options.get('design', 'design/six_bay_radial.json')}` with " + (", ".join(f"`{m}`" for m in made) or "nothing changed") + ".\n"
        "Not in git. Safe to delete.\n",
        encoding="utf-8",
    )
    print(f"wrote {folder}: {len(lines['members'])} members, " + (", ".join(made) or "nothing changed"))


if __name__ == "__main__":
    main(sys.argv[1:])
