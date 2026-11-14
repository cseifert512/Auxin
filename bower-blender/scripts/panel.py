"""Open the Bower panel: sliders, live handles and rebuild buttons in the 3D viewport's sidebar.

Run once per Blender session, from the Python console, the Text Editor or the MCP connector:

    import runpy
    runpy.run_path(r"<repo>/scripts/panel.py")["main"]()

Then press N in the 3D viewport and choose the "Bower" tab. Pass design_path= to work on
another design file (design/two_rooms.json). See bower/blender_ui.py for what the panel does.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main(design_path=None, reload_design: bool = False) -> dict:
    import bpy

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    if "bower.blender_ui" in sys.modules:  # take the old panel out before its code is replaced
        sys.modules["bower.blender_ui"].unregister()
    for name in [m for m in sys.modules if m == "bower" or m.startswith("bower.")]:
        del sys.modules[name]  # pick up source edits in a long-lived Blender session
    from bower import blender_ui

    blender_ui.register()
    scene = bpy.context.scene
    units = scene.unit_settings
    if units.system != "METRIC" or abs(units.scale_length - 1.0) > 1e-9:
        raise RuntimeError(f"scene units are {units.system} x {units.scale_length}; bower geometry is in metres at scale 1.0")
    if design_path is not None or reload_design or not scene.get("bower_design"):
        design = blender_ui.load(scene, design_path)
    else:  # carry on with the working design kept in the scene
        design = blender_ui.working(scene)
        blender_ui._sync(scene)
    for window in bpy.context.window_manager.windows:  # show the sidebar, where the panel lives
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.spaces[0].show_region_ui = True
                area.tag_redraw()
    return {
        "panel": "3D viewport > sidebar (N) > Bower",
        "design": bpy.path.abspath(scene.bower.design_path),
        "rooms": [room["id"] for room in design["rooms"]],
        "status": scene.bower.status,
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
