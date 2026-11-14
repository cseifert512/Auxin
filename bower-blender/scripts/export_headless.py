"""Make a snapshot from a design in a windowless Blender, and say how it went in a log.

    blender-launcher.exe --background --factory-startup --python scripts/export_headless.py -- <name> <design file> <git commit>

for example
    ... -- six-bay-radial-v2 design/six_bay_radial.json 17eff3e

It clears the factory scene, then does what scripts/export_snapshot.py does in a Blender with a
window: rebuilds the building from the design and writes ../releases/<name>/. A windowless Blender
prints nothing back, so the result (the files, the model's counts and the checks made at export),
or the error, is written to output/export_<name>.log.
"""
import json
import runpy
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    name = args[0] if args else "unnamed"
    log = REPO / "output" / f"export_{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        import bpy

        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        export = runpy.run_path(str(REPO / "scripts" / "export_snapshot.py"))["main"]
        result = export(name, commit=args[2] if len(args) > 2 else None, design_path=REPO / (args[1] if len(args) > 1 else "design.json"))
        log.write_text("ok " + json.dumps(result, indent=1) + "\n", encoding="utf-8")
    except Exception:
        log.write_text("failed\n" + traceback.format_exc(), encoding="utf-8")
