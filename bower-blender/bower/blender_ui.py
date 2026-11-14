"""The Bower panel: sliders, live handles and rebuild buttons, in the 3D viewport's sidebar (N) under "Bower".

The panel works on a copy of the design that is kept in the scene, so it is saved with the
.blend. Every change goes through the operations in bower/topology.py (by way of
bower/controls.py) and is checked exactly as a hand edit of the design file is: a change that
would give an invalid design is refused, the panel says why, and nothing moves. "Save" writes
the working copy to the design file, which stays the source of truth; "Revert" reads the file
again.

Three speeds, so that the model can be played with:

    outline   while a slider or a handle is moving, the room's boundary curves (arches, crown
              ring, ridges) follow at once
    draft     a moment after it stops, all the timber is rebuilt: swept from its centrelines,
              with no joints cut and nothing checked (a few seconds)
    full      on the button: every joint milled and every check run (about a minute)

Handles are the empties in 00_CONTROLS: drag a pier, an apex or a crown and the design follows.

Registered by scripts/panel.py. This and bower/blender_scene.py are the only modules that
touch Blender.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup

from . import controls, topology
from .blender_scene import CENTRELINE_COLLECTION
from .blender_scene import CONTROLS as HANDLE_COLLECTION
from .blender_scene import build_design, read_dragged_handles
from .envelope import Roof

REPO = Path(__file__).resolve().parents[1]
DRAFT_AFTER_S = 0.4  # how long a slider or handle must be still before the timber is rebuilt
SETTLE_AFTER_S = 1.2  # how long a handle may sit where the design cannot follow before it is put back
UNDO_STEPS = 40
_STATE = {
    "syncing": False,  # sliders are being set from the design, not by the user
    "busy": False,  # the scene is being rebuilt: changes to it are ours
    "scene": None,
    "draft_at": None,
    "settle_at": None,
    "refused": None,  # handle positions the design could not follow
    "undo": [],
    "edit": ("", 0.0),
    "cache": ("", None),
    "rooms": [],
}


# --- the working design -----------------------------------------------------------------------------


def working(scene) -> dict | None:
    """The design the panel is working on (do not change it in place: every edit makes a new one)."""
    text = scene.get("bower_design")
    if not text:
        return None
    if _STATE["cache"][0] != text:
        _STATE["cache"] = (text, json.loads(text))
    return _STATE["cache"][1]


def _store(scene, design: dict) -> None:
    text = json.dumps(design)
    scene["bower_design"] = text
    _STATE["cache"] = (text, design)


def _room_id(scene, design: dict) -> str:
    ids = [room["id"] for room in design["rooms"]]
    chosen = scene.bower.room
    return chosen if chosen in ids else ids[0]


def _shown(scene, design: dict) -> dict:
    """The design as it is drawn while working on it: with its boundary curves showing, if the panel says so."""
    return {**design, "display": {**design.get("display", {}), "outline": bool(scene.bower.show_outline)}}


def _say(scene, text: str, refused: bool = False) -> None:
    scene.bower.status, scene.bower.refused = text, refused
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _sync(scene) -> None:
    """Set every slider from the working design."""
    design = working(scene)
    if design is None:
        return
    settings, values = scene.bower, controls.values(design, _room_id(scene, design))
    _STATE["syncing"] = True
    try:
        for control in controls.CONTROLS:
            value = int(round(values[control.key])) if control.kind == "count" else float(values[control.key])
            if abs(getattr(settings, control.key) - value) > 1e-6:
                setattr(settings, control.key, value)
    finally:
        _STATE["syncing"] = False


def _build(scene, design: dict, detail: str) -> tuple[dict, float]:
    _STATE["busy"] = True
    try:
        started = time.perf_counter()
        report = build_design(scene, _shown(scene, design), detail=detail)
        return report, time.perf_counter() - started
    finally:
        _STATE["busy"] = False


def _draft_soon(scene) -> None:
    _STATE["scene"], _STATE["draft_at"] = scene.name, time.monotonic() + DRAFT_AFTER_S
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=DRAFT_AFTER_S)


def apply(scene, change, label: str, coalesce: str = "") -> bool:
    """Make one edit to the working design: `change` takes the design and returns the edited one.

    If the result is a valid design the outline follows at once and the timber a moment later.
    If not, nothing changes and the panel says why.
    """
    before = working(scene)
    try:
        after = change(before)
        topology.validate(after)
        for room in after["rooms"]:
            Roof(room)  # a roof that cannot be made is refused before anything is drawn
        _build(scene, after, "outline")
    except topology.DesignError as error:
        _say(scene, f"Refused: {error}", refused=True)
        _sync(scene)
        return False
    except Exception as error:  # say what went wrong rather than leave the panel dead
        _say(scene, f"Error: {type(error).__name__}: {error}", refused=True)
        _sync(scene)
        return False
    key, now = coalesce or label, time.monotonic()
    if _STATE["edit"][0] != key or now - _STATE["edit"][1] > 1.0:  # one undo step for one sweep of a slider
        _STATE["undo"] = (_STATE["undo"] + [json.dumps(before)])[-UNDO_STEPS:]
    _STATE["edit"] = (key, now)
    _store(scene, after)
    scene["bower_unsaved"] = True
    _sync(scene)
    _say(scene, label)
    if scene.bower.live:
        _draft_soon(scene)
    return True


def draft(scene) -> bool:
    """Rebuild the timber of the working design as a draft. If it cannot be built, go back to the last design that could."""
    design = working(scene)
    try:
        report, seconds = _build(scene, design, "draft")
    except Exception as error:
        reason = str(error) if isinstance(error, topology.DesignError) else f"{type(error).__name__}: {error}"
        last = scene.get("bower_built")
        if last and last != scene.get("bower_design"):
            _store(scene, json.loads(last))
            _sync(scene)
            try:
                _build(scene, working(scene), "draft")
            except Exception:
                pass
            _say(scene, f"Refused, and put back: the timber cannot be built that way. {reason}", refused=True)
        else:
            _say(scene, f"The timber cannot be built: {reason}", refused=True)
        return False
    scene["bower_built"] = scene["bower_design"]
    members = sum(room["timber"]["members"] for room in {id(r["timber"]): r for r in report["rooms"] if r["timber"]}.values())
    _say(scene, f"Draft: {members} members in {seconds:.1f} s. Joints not cut yet.")
    return True


def load(scene, path=None) -> dict:
    """Read the design file into the working copy and build it as a draft."""
    if path is not None:
        scene.bower.design_path = str(path)
    design, relaid = topology.reconcile(topology.load(bpy.path.abspath(scene.bower.design_path)))
    _store(scene, design)
    scene["bower_built"], scene["bower_unsaved"] = scene["bower_design"], bool(relaid)
    _STATE["undo"], _STATE["refused"] = [], None
    _sync(scene)
    draft(scene)
    return design


# --- timers and the handle watch ---------------------------------------------------------------------


def _scene():
    return bpy.data.scenes.get(_STATE["scene"] or "") or bpy.context.scene


def _moved_handles(scene) -> tuple:
    """The handles that are not where the design put them, with where they are now."""
    collection = bpy.data.collections.get(HANDLE_COLLECTION)
    if collection is None:
        return ()
    moved = []
    for obj in collection.objects:
        if obj.get("bower_kind") == "handle":
            placed = obj["bower_placed_at"]
            if max(abs(obj.location[k] - placed[k]) for k in range(3)) > 1e-5:
                moved.append((obj.name, tuple(round(c, 4) for c in obj.location)))
    return tuple(sorted(moved))


def _tick():
    """The timber follows once things have been still for a moment; a handle the design could not follow is put back."""
    scene, now = _scene(), time.monotonic()
    waits = []
    if _STATE["settle_at"] is not None:
        if now >= _STATE["settle_at"]:
            _STATE["settle_at"] = None
            if _STATE["refused"] is not None and _moved_handles(scene) == _STATE["refused"] and working(scene):
                try:
                    _build(scene, working(scene), "outline")  # puts every handle back where the design has it
                except Exception:
                    pass
            _STATE["refused"] = None
        else:
            waits.append(_STATE["settle_at"] - now)
    if _STATE["draft_at"] is not None:
        if now >= _STATE["draft_at"]:
            _STATE["draft_at"] = None
            if working(scene):
                draft(scene)
        else:
            waits.append(_STATE["draft_at"] - now)
    return max(min(waits), 0.02) if waits else None


def _follow_handles():
    scene = _scene()
    moved = _moved_handles(scene)
    if not moved or moved == _STATE["refused"] or working(scene) is None:
        return None
    if apply(scene, lambda design: read_dragged_handles(design)[0], "Handle moved: " + ", ".join(name[2:] for name, _ in moved), coalesce="handles"):
        _STATE["refused"], _STATE["settle_at"] = None, None
    else:  # leave the handle where it was dragged for a moment, then put it back
        _STATE["refused"], _STATE["settle_at"] = moved, time.monotonic() + SETTLE_AFTER_S
        if not bpy.app.timers.is_registered(_tick):
            bpy.app.timers.register(_tick, first_interval=SETTLE_AFTER_S)
    return None


@persistent
def _on_depsgraph(scene, depsgraph=None):
    """A handle has been moved in the viewport: have the design follow it (outside this callback)."""
    if _STATE["busy"] or _STATE["syncing"] or not scene.get("bower_design") or not getattr(scene, "bower", None) or not scene.bower.live:
        return
    moved = _moved_handles(scene)
    if not moved or moved == _STATE["refused"]:
        return
    _STATE["scene"] = scene.name
    if not bpy.app.timers.is_registered(_follow_handles):
        bpy.app.timers.register(_follow_handles, first_interval=0.0)


# --- the sliders ---------------------------------------------------------------------------------------


def _changed(key: str):
    control = controls.BY_KEY[key]

    def update(self, context):
        if _STATE["syncing"]:
            return
        scene = context.scene
        design = working(scene)
        if design is None:
            return
        room_id = _room_id(scene, design)
        raw = getattr(self, key)
        value = int(raw) if control.kind == "count" else round(float(raw), 3 if control.kind == "length" else 1)
        if abs(value - control.get(design, topology.get_room(design, room_id))) < 5e-4:
            return
        shown = f"{value:g}" + {"length": " m", "angle": " deg", "count": ""}[control.kind]
        apply(scene, lambda d: controls.adjust(d, room_id, key, value), f"{room_id}: {control.group.lower()} {control.label.lower()} {shown}", coalesce=f"{room_id}.{key}")

    return update


def _property(control):
    common = {"name": control.label, "description": control.tip, "update": _changed(control.key)}
    if control.kind == "count":
        return IntProperty(min=int(control.lo), max=int(control.hi), default=int(control.lo), **common)
    if control.kind == "length":
        return FloatProperty(min=control.lo, max=control.hi, default=control.lo, step=control.step * 100.0, precision=2, unit="LENGTH", **common)
    return FloatProperty(min=control.lo, max=control.hi, default=max(control.lo, 0.0), step=control.step * 100.0, precision=1, **common)


def _room_items(self, context):
    design = working(context.scene) or {"rooms": []}
    _STATE["rooms"] = [(room["id"], f"{room['id']}: {len(room['bays'])} bays", "") for room in design["rooms"]] or [("", "no design", "")]
    return _STATE["rooms"]  # kept alive here: Blender does not hold on to these strings


def _room_changed(self, context):
    _sync(context.scene)


def _outline_toggled(self, context):
    for obj in bpy.data.objects:
        if obj.get("bower_kind") == "guide":
            obj.hide_viewport = not self.show_outline


def _centrelines_toggled(self, context):
    for name in set(CENTRELINE_COLLECTION.values()):
        collection = bpy.data.collections.get(name)
        if collection is not None:
            collection.hide_viewport = not self.show_centrelines


def _settings():
    annotations = {
        "design_path": StringProperty(name="Design file", description="The design file the panel loads and saves", subtype="FILE_PATH", default=str(REPO / "design.json")),
        "room": EnumProperty(name="Room", description="The room the sliders act on", items=_room_items, update=_room_changed),
        "live": BoolProperty(name="Live", description="Rebuild as sliders and handles move: outline at once, draft timber a moment later", default=True),
        "show_outline": BoolProperty(name="Outline", description="Show the room's boundary curves over the timber", default=True, update=_outline_toggled),
        "show_centrelines": BoolProperty(name="Centrelines", description="Show every member's centreline through its timber", default=True, update=_centrelines_toggled),
        "status": StringProperty(name="Status"),
        "refused": BoolProperty(name="Last change refused"),
    }
    for control in controls.CONTROLS:
        annotations[control.key] = _property(control)
    return type("BowerSettings", (PropertyGroup,), {"__annotations__": annotations, "__doc__": "What the Bower panel shows and edits"})


BowerSettings = _settings()


# --- operators -----------------------------------------------------------------------------------------


def _selected_bay(context) -> str | None:
    obj = context.active_object
    return obj["bower_id"] if obj is not None and obj.get("bower_handle") == "apex" else None


class BOWER_OT_load(Operator):
    """Read the design file, discarding changes that have not been saved, and rebuild"""

    bl_idname, bl_label = "bower.load", "Read the design file again and discard unsaved changes?"

    def invoke(self, context, event):
        if context.scene.get("bower_unsaved"):  # ask before throwing work away
            return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)

    def execute(self, context):
        try:
            load(context.scene)
        except Exception as error:
            _say(context.scene, f"Could not load: {error}", refused=True)
            return {"CANCELLED"}
        return {"FINISHED"}


class BOWER_OT_save(Operator):
    """Write the working design to the design file"""

    bl_idname, bl_label = "bower.save", "Save design"

    def execute(self, context):
        scene = context.scene
        path = bpy.path.abspath(scene.bower.design_path)
        topology.save(path, working(scene))
        scene["bower_unsaved"] = False
        _say(scene, f"Saved to {Path(path).name}")
        return {"FINISHED"}


class BOWER_OT_undo(Operator):
    """Take back the last change made through the panel or the handles"""

    bl_idname, bl_label = "bower.undo", "Undo"

    @classmethod
    def poll(cls, context):
        return bool(_STATE["undo"])

    def execute(self, context):
        scene = context.scene
        _store(scene, json.loads(_STATE["undo"].pop()))
        _STATE["edit"] = ("", 0.0)
        scene["bower_unsaved"] = True
        _sync(scene)
        _build(scene, working(scene), "outline")
        _say(scene, "Undone")
        _draft_soon(scene)
        return {"FINISHED"}


class BOWER_OT_rebuild(Operator):
    """Rebuild the scene from the working design"""

    bl_idname, bl_label = "bower.rebuild", "Rebuild"
    detail: EnumProperty(items=[("draft", "Draft", "Timber swept, joints not cut"), ("full", "Full", "Every joint milled and checked")], default="draft")

    def execute(self, context):
        scene = context.scene
        if self.detail == "draft":
            return {"FINISHED"} if draft(scene) else {"CANCELLED"}
        try:
            report, seconds = _build(scene, working(scene), "full")
        except Exception as error:
            _say(scene, f"Could not build: {error}", refused=True)
            return {"CANCELLED"}
        scene["bower_built"] = scene["bower_design"]
        timbers = list({id(r["timber"]): r["timber"] for r in report["rooms"] if r["timber"]}.values())
        found = [t.get("mesh_intersections_in_scene") or {} for t in timbers]
        _say(
            scene,
            f"Milled: {sum(t['members'] for t in timbers)} members, {sum(t['joints']['joints'] for t in timbers)} joints in {seconds:.0f} s. "
            f"Laps left overlapping: {sum(len(f.get('laps_not_clean', [])) for f in found)}. Clashes: {sum(len(f.get('clashes', [])) for f in found)}. "
            f"Meshes closed: {'yes' if all(t['meshes_closed'] for t in timbers) else 'no'}.",
        )
        return {"FINISHED"}


class BOWER_OT_bay(Operator):
    """Split the bay whose apex handle is selected, or remove it"""

    bl_idname, bl_label = "bower.bay", "Add or remove a bay"
    action: EnumProperty(items=[("add", "Add", "Split the selected bay in two"), ("remove", "Remove", "Remove the selected bay")], default="add")

    @classmethod
    def poll(cls, context):
        return _selected_bay(context) is not None

    def execute(self, context):
        bay_id = _selected_bay(context)
        edit = topology.add_bay if self.action == "add" else topology.remove_bay
        done = apply(context.scene, lambda design: edit(design, bay_id)[0], f"{'Split' if self.action == 'add' else 'Removed'} bay {bay_id}")
        return {"FINISHED"} if done else {"CANCELLED"}


class BOWER_OT_room(Operator):
    """Grow a new room out of the bay whose apex handle is selected, or remove the room the sliders act on"""

    bl_idname, bl_label = "bower.room", "Add or remove a room"
    action: EnumProperty(items=[("add", "Add", "Grow a room out of the selected bay"), ("remove", "Remove", "Remove the room chosen in the panel")], default="add")

    @classmethod
    def poll(cls, context):
        return working(context.scene) is not None

    def execute(self, context):
        scene = context.scene
        if self.action == "add":
            bay_id = _selected_bay(context)
            if bay_id is None:
                _say(scene, "Select the apex handle of the bay the new room should grow out of.", refused=True)
                return {"CANCELLED"}
            done = apply(scene, lambda design: controls.grow_room(design, bay_id), f"Room grown out of {bay_id}")
        else:
            room_id = _room_id(scene, working(scene))
            done = apply(scene, lambda design: topology.remove_room(design, room_id)[0], f"Removed room {room_id}")
        return {"FINISHED"} if done else {"CANCELLED"}


# --- the panel -----------------------------------------------------------------------------------------


def _lines(text: str, width: int = 44) -> list:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + ([line] if line else [])


class BOWER_PT_panel(Panel):
    bl_idname, bl_label = "BOWER_PT_panel", "Bower"
    bl_space_type, bl_region_type, bl_category = "VIEW_3D", "UI", "Bower"

    def draw(self, context):
        layout, scene = self.layout, context.scene
        settings, design = scene.bower, working(scene)
        column = layout.column(align=True)
        column.prop(settings, "design_path", text="")
        row = column.row(align=True)
        row.operator("bower.load", text="Load" if design is None else "Revert", icon="FILE_REFRESH")
        row.operator("bower.save", text="Save *" if scene.get("bower_unsaved") else "Save", icon="FILE_TICK")
        row.operator("bower.undo", text="Undo", icon="LOOP_BACK")
        if design is None:
            layout.label(text="Load a design to begin.")
            return
        row = layout.row(align=True)
        if len(design["rooms"]) > 1:
            row.prop(settings, "room", text="")
        row.prop(settings, "live", toggle=True)
        row.prop(settings, "show_outline", toggle=True)
        row.prop(settings, "show_centrelines", toggle=True)

        room_id = _room_id(scene, design)
        blocked = controls.blocked(design, room_id)
        for group in controls.GROUPS:
            box = layout.box()
            box.label(text=f"{group}  ({room_id})" if len(design["rooms"]) > 1 else group)
            column = box.column(align=True)
            for control in controls.CONTROLS:
                if control.group == group:
                    row = column.row(align=True)
                    row.enabled = control.key not in blocked
                    row.prop(settings, control.key, slider=True)
            for reason in sorted({reason for key, reason in blocked.items() if controls.BY_KEY[key].group == group}):
                for line in _lines(reason):
                    column.label(text=line, icon="INFO")

        box = layout.box()
        box.label(text="Handles")
        column = box.column(align=True)
        column.label(text="Drag piers, apexes and crowns in the view.")
        bay_id = _selected_bay(context)
        column.label(text=f"Selected bay: {bay_id}" if bay_id else "Select an apex handle to edit its bay.")
        row = column.row(align=True)
        row.operator("bower.bay", text="Split bay", icon="ADD").action = "add"
        row.operator("bower.bay", text="Remove bay", icon="REMOVE").action = "remove"
        row = column.row(align=True)
        grow = row.row(align=True)
        grow.enabled = bay_id is not None
        grow.operator("bower.room", text="Grow room", icon="ADD").action = "add"
        drop = row.row(align=True)
        drop.enabled = len(design["rooms"]) > 1
        drop.operator("bower.room", text=f"Remove {room_id}", icon="REMOVE").action = "remove"

        column = layout.column(align=True)
        column.operator("bower.rebuild", text="Rebuild draft", icon="FILE_REFRESH").detail = "draft"
        column.operator("bower.rebuild", text="Mill joints (about a minute)", icon="MOD_BOOLEAN").detail = "full"
        if settings.status:
            box = layout.box()
            for k, line in enumerate(_lines(settings.status)):
                box.label(text=line, icon=("ERROR" if settings.refused else "INFO") if k == 0 else "BLANK1")


# --- registration ----------------------------------------------------------------------------------------

_CLASSES = (BowerSettings, BOWER_OT_load, BOWER_OT_save, BOWER_OT_undo, BOWER_OT_rebuild, BOWER_OT_bay, BOWER_OT_room, BOWER_PT_panel)


def unregister() -> None:
    """Take the panel out again (also whatever an earlier load of this module registered)."""
    old = bpy.app.driver_namespace.pop("bower_ui", None)
    if not old:
        return
    for handler in list(bpy.app.handlers.depsgraph_update_post):
        if handler is old["handler"]:
            bpy.app.handlers.depsgraph_update_post.remove(handler)
    for timer in old["timers"]:
        if bpy.app.timers.is_registered(timer):
            bpy.app.timers.unregister(timer)
    if hasattr(bpy.types.Scene, "bower"):
        del bpy.types.Scene.bower
    for cls in reversed(old["classes"]):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


def register() -> None:
    unregister()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bower = PointerProperty(type=BowerSettings)
    bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)
    bpy.app.driver_namespace["bower_ui"] = {"classes": _CLASSES, "handler": _on_depsgraph, "timers": (_tick, _follow_handles)}
