"""Snapshots: a named, self-contained copy of a design's generated model, for other work to build on.

A snapshot is a folder, releases/<name>/, written by scripts/export_snapshot.py:

    bower.blend        the generated collections only, for linking into another Blender file
    bower.glb          the milled timber meshes, for any other tool (glTF: metres, Y up)
    centrelines.json   every member's centreline, section and joints-at-nodes (metres, Z up, Y north)
    members.csv        the member schedule
    joints.csv         the joint schedule
    design.json        the authored parameters the snapshot was generated from
    manifest.json      what the snapshot is: name, source commit, counts, checks, file hashes

Other work pins a snapshot by name and never edits it. A refined model is a new
snapshot under a new name; whoever uses the old one moves across when they
choose. Member IDs are persistent, so anything keyed to a member ID (a plant's
route, an annotation) carries over from one snapshot to the next.

`centrelines.json` is this project's own neutral format, schema
"bower.centrelines/1". It is not the plant simulator's format: that exporter is
to be written against the simulator's real examples and parser.

Pure Python (no bpy): this module builds the data; the Blender files are written
by bower/blender_scene.py.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

from .joints import find_joints, joint_rows, joint_summary
from .timber import build_design_timber, clearances, schedule

CENTRELINE_SCHEMA = "bower.centrelines/1"
SNAPSHOT_SCHEMA = "bower.snapshot/1"


def centrelines(design: dict, spacing: float | None = None) -> dict:
    """Every member of the design as sampled centreline points with its section and frame.

    `points_m` are spaced no more than `spacing` apart along the member (by default the
    design's export spacing). `depth_axes` gives the direction of the section's depth at each
    point; the section's width is square to that and to the centreline. `bezier_m` is the exact
    curve: each entry is an anchor, its left handle and its right handle.
    """
    spacing = spacing or design["timber"]["sampling"]["export_station_spacing_m"]
    members = []
    for group in build_design_timber(design):
        for m in group["members"]:
            stations = m.path.stations(spacing)
            start, end = m.path.anchors[0].co, m.path.anchors[-1].co
            members.append(
                {
                    "id": m.id,
                    "room": group["room_of"][m.id],
                    "parent": m.parent,
                    "role": m.role,
                    "family": m.family,
                    "width_m": m.width,
                    "depth_m": m.depth,
                    "length_m": round(m.path.length, 4),
                    "closed": sum((a - b) ** 2 for a, b in zip(start, end)) < 1e-12,
                    "nodes": list(m.nodes),
                    "points_m": [[round(c, 4) for c in st.point] for st in stations],
                    "depth_axes": [[round(c, 4) for c in st.depth_axis] for st in stations],
                    "bezier_m": [[[round(c, 5) for c in p] for p in (a.co, a.handle_left, a.handle_right)] for a in m.path.anchors],
                }
            )
    return {
        "schema": CENTRELINE_SCHEMA,
        "units": "m",
        "axes": design.get("axes", {"up": "+Z", "north": "+Y"}),
        "sample_spacing_m": spacing,
        "note": "Centrelines are the members; solids are derived from them. Sections are provisional concept values.",
        "members": members,
    }


def schedules(design: dict) -> tuple[list[dict], list[dict]]:
    """The member schedule and the joint schedule of the whole design, as rows."""
    member_rows, joints = [], []
    for group in build_design_timber(design):
        members = group["members"]
        found = find_joints(members, design["timber"])[0]
        member_rows += schedule(members, design["timber"], clearances(members), found)
        joints += joint_rows(found)
    return member_rows, joints


def summary(design: dict) -> dict:
    """Counts and totals for the manifest."""
    members, joints = [], []
    for group in build_design_timber(design):
        members += group["members"]
        joints += find_joints(group["members"], design["timber"])[0]
    points = [a.co for m in members for a in m.path.anchors]
    return {
        "rooms": [{"id": room["id"], "bays": len(room["bays"]), "piers": len(room["piers"])} for room in design["rooms"]],
        "members": len(members),
        "members_by_family": dict(sorted(Counter(m.family for m in members).items())),
        "total_length_m": round(sum(m.path.length for m in members), 1),
        "total_volume_m3": round(sum(m.width * m.depth * m.path.length for m in members), 2),
        "joints": joint_summary(joints),
        "bounds_m": {"min": [round(min(p[k] for p in points), 2) for k in range(3)], "max": [round(max(p[k] for p in points), 2) for k in range(3)]},
    }


def manifest(name: str, design: dict, folder, created: str, commit: str | None = None, checks: dict | None = None, tools: dict | None = None) -> dict:
    """What a snapshot folder holds. Call it last: it hashes the files already written there."""
    folder = Path(folder)
    files = {}
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            data = path.read_bytes()
            files[path.name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return {
        "schema": SNAPSHOT_SCHEMA,
        "name": name,
        "created": created,
        "source_commit": commit,
        "generated_from": "design.json in this folder, by scripts/export_snapshot.py",
        "units": "m",
        "axes": {**design.get("axes", {"up": "+Z", "north": "+Y"}), "bower.glb": "glTF convention: +Y up, metres"},
        "status": "Concept geometry. Sections, joint depths and clearances are provisional; nothing here is a structural, fabrication or horticultural check.",
        "model": summary(design),
        "checks_at_export": checks,
        "tools": tools,
        "files": files,
        "use": {
            "blender": "File > Link > bower.blend > Collection. Link 21_PRIMARY_MESHES for the timber, 20_PRIMARY_CENTERLINES for the centreline curves, or BOWER_V1 for everything generated.",
            "other tools": "bower.glb holds the timber meshes; each mesh carries its member ID.",
            "data": "centrelines.json, members.csv and joints.csv are keyed by member ID.",
        },
    }
