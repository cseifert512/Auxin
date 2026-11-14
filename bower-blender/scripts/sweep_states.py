"""Sweep one control of the building at a time and write the states in between, for the design-space sketch.

    cd bower-blender
    python scripts/sweep_states.py

Writes ../drawings-in-code/sketches/design-space/states.js, which the page beside it reads.
No Blender. About four seconds a state.

This is a sketch for trying things, not the study writer described in docs/studies.md.
The measures are read off centre lines only and are rough: see each one's note.
"""

import copy
import heapq
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from bower import controls, snapshot, topology  # noqa: E402

DESIGN = "design/six_bay_radial.json"
ROOM = "R1"
STATES = 7          # states written per sweep, ends included
POINTS = 16         # every member is resampled to this many points, so it can be moved point by point
FLOOR_M = 0.08      # a member end lower than this stands on the floor
TOUCH_M = 0.30      # two members this close (centre line to centre line) are taken to touch
OUT = HERE.parent.parent / "drawings-in-code" / "sketches" / "design-space" / "states.js"

NOT_RECORDED = "Not recorded yet."
FROM_STUDIES = "docs/studies.md. Plant numbers there are the simulator's assumptions, not measurements."


def _pier_ring(design: dict, value: float) -> dict:
    new = copy.deepcopy(design)
    new["timber"]["piers"]["ring_radius_m"] = value
    return new


def _control(key: str):
    return lambda design, value: controls.adjust(design, ROOM, key, value)


SWEEPS = (
    {
        "id": "pier-opens", "title": "The pier opens", "parameter": "timber.piers.ring_radius_m", "unit": "m",
        # Set at 0.34 in the design, but the generator widens the ring until the legs fit, and on this
        # room nothing moves below about 0.6. So the sweep starts where the setting begins to bite.
        "from": 0.58, "to": 1.20, "set": _pier_ring,
        "need": "Soil beside the plant's own way up.",
        "disagrees": "A pier's feet stand about 0.15 m apart, with no soil between.",
        "costs": "The pier stops reading as one tight trunk. The entrance narrows. The footing spreads.",
        "source": FROM_STUDIES,
    },
    {
        "id": "ribs-straighten", "title": "The ribs straighten", "parameter": "lattice lean_deg", "unit": "deg",
        "from": 40.0, "to": 20.0, "set": _control("lean"),
        "need": "A way up it can cover in a few years.",
        "disagrees": "10 to 11 m of timber to the crown at a rib lean of 40 degrees.",
        "costs": "Less weave.",
        "source": FROM_STUDIES,
    },
    {
        "id": "crown-comes-down", "title": "The crown comes down", "parameter": "crown height_m", "unit": "m",
        "from": 6.3, "to": 5.2, "set": _control("crown_height"),
        "need": "A gardener's reach, and a shorter way up.",
        "disagrees": "Crown at 6.3 m; pruning two to four times a year.",
        "costs": "Height and spectacle. A lower room.",
        "source": FROM_STUDIES,
    },
    {
        "id": "crown-opens", "title": "The crown opens", "parameter": "crown radius_m", "unit": "m",
        "from": 1.0, "to": 2.0, "set": _control("crown_radius"),
        "need": NOT_RECORDED, "disagrees": NOT_RECORDED, "costs": NOT_RECORDED, "source": "",
    },
    {
        "id": "arches-lower", "title": "The arches lower", "parameter": "arch apex_height_m", "unit": "m",
        "from": 4.6, "to": 3.6, "set": _control("arch_height"),
        "need": NOT_RECORDED, "disagrees": NOT_RECORDED, "costs": NOT_RECORDED, "source": "",
    },
    {
        "id": "room-tightens", "title": "The room tightens", "parameter": "room radius_m", "unit": "m",
        "from": 6.2, "to": 5.0, "set": _control("room_radius"),
        "need": NOT_RECORDED, "disagrees": NOT_RECORDED, "costs": NOT_RECORDED, "source": "",
    },
)

MEASURES = (
    {"key": "feet_apart_m", "label": "Nearest two feet at a pier", "unit": "m", "digits": 2,
     "note": "Centre to centre, the pair of arch legs aside. Timber is not taken off it."},
    {"key": "pier_ground_m2", "label": "Ground inside a pier's feet", "unit": "m2", "digits": 2,
     "note": "Area of the outline round the centres of one pier's feet. Timber is not taken off it."},
    {"key": "way_through_m", "label": "Way through a bay", "unit": "m", "digits": 2,
     "note": "Nearest feet of two neighbouring piers, less half of each member's width."},
    {"key": "to_crown_m", "label": "Shortest way, soil to crown", "unit": "m", "digits": 1,
     "note": "Along centre lines, crossing wherever two members come within %.2f m. Not the planting's own route graph." % TOUCH_M},
    {"key": "crown_m", "label": "Crown above the floor", "unit": "m", "digits": 2, "note": ""},
    {"key": "timber_m", "label": "Timber, total length", "unit": "m", "digits": 0, "note": ""},
    {"key": "timber_m3", "label": "Timber, volume", "unit": "m3", "digits": 2,
     "note": "Length by width by depth of each member, before any milling."},
)


def _dist(a, b) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _path(member: dict) -> list:
    points = member["points_m"]
    if member["closed"] and _dist(points[0], points[-1]) > 1e-6:
        return points + [points[0]]
    return points


def resample(member: dict, count: int = POINTS) -> list:
    """The member's centre line as `count` points evenly spaced along it."""
    path = _path(member)
    run = [0.0]
    for a, b in zip(path, path[1:]):
        run.append(run[-1] + _dist(a, b))
    total, out, seg = run[-1], [], 0
    for i in range(count):
        at = total * (i / count if member["closed"] else i / (count - 1))
        while seg < len(path) - 2 and run[seg + 1] < at:
            seg += 1
        span = run[seg + 1] - run[seg]
        t = 0.0 if span <= 0 else min(1.0, (at - run[seg]) / span)
        out.append([path[seg][k] + (path[seg + 1][k] - path[seg][k]) * t for k in range(3)])
    return out


def _hull_area(points: list) -> float:
    pts = sorted(set((round(p[0], 4), round(p[1], 4)) for p in points))
    if len(pts) < 3:
        return 0.0

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and (out[-1][0] - out[-2][0]) * (p[1] - out[-2][1]) - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0]) <= 0:
                out.pop()
            out.append(p)
        return out

    hull = half(pts)[:-1] + half(reversed(pts))[:-1]
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(hull, hull[1:] + hull[:1]))) / 2.0


def _piers(members: list) -> list:
    """The feet on the floor, gathered into piers, in order round the room."""
    feet = [(p, m["width_m"], m["family"]) for m in members if not m["closed"] for p in (m["points_m"][0], m["points_m"][-1]) if p[2] < FLOOR_M]
    # A pier is where arch legs stand together; every other foot belongs to the pier it is nearest.
    legs = []
    for foot in (f for f in feet if f[2] == "arch"):
        near = [g for g in legs if any(_apart(foot, q) < 0.6 for q in g)]
        for g in near:
            legs.remove(g)
        legs.append(sum(near, []) + [foot])
    centre = lambda g: (sum(f[0][0] for f in g) / len(g), sum(f[0][1] for f in g) / len(g))
    centres = sorted((centre(g) for g in legs), key=lambda c: math.atan2(c[1], c[0]))
    piers = [[] for _ in centres]
    for foot in feet:
        piers[min(range(len(centres)), key=lambda i: math.hypot(foot[0][0] - centres[i][0], foot[0][1] - centres[i][1]))].append(foot)
    return piers


def _apart(a, b) -> float:
    return math.hypot(a[0][0] - b[0][0], a[0][1] - b[0][1])


def _clear(a, b) -> float:
    return _apart(a, b) - (a[1] + b[1]) / 2.0


def _to_crown(members: list) -> float:
    """Shortest way along centre lines from any foot to the crown, crossing where members touch."""
    nodes, owner, edges = [], [], {}

    def link(i, j, d):
        edges.setdefault(i, []).append((j, d))
        edges.setdefault(j, []).append((i, d))

    for index, member in enumerate(members):
        path, first = _path(member), len(nodes)
        for k, p in enumerate(path):
            nodes.append(p)
            owner.append(index)
            if k:
                link(first + k - 1, first + k, _dist(path[k - 1], p))
    cells = {}
    for i, p in enumerate(nodes):
        cells.setdefault(tuple(int(math.floor(c / TOUCH_M)) for c in p), []).append(i)
    for (cx, cy, cz), here in cells.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in cells.get((cx + dx, cy + dy, cz + dz), ()):
                        for i in here:
                            if i < j and owner[i] != owner[j]:
                                d = _dist(nodes[i], nodes[j])
                                if d <= TOUCH_M:
                                    link(i, j, d)
    goal = {i for i in range(len(nodes)) if members[owner[i]]["family"] == "crown"}
    best = {i: 0.0 for i in range(len(nodes)) if nodes[i][2] < FLOOR_M and not members[owner[i]]["closed"]}
    heap = [(0.0, i) for i in best]
    heapq.heapify(heap)
    while heap:
        d, i = heapq.heappop(heap)
        if d > best.get(i, math.inf):
            continue
        if i in goal:
            return d
        for j, step in edges.get(i, ()):
            if d + step < best.get(j, math.inf):
                best[j] = d + step
                heapq.heappush(heap, (d + step, j))
    return float("nan")


def measure(lines: dict) -> dict:
    members = lines["members"]
    piers = _piers(members)
    gaps = [min(_apart(a, b) for a in g for b in g if a is not b and not (a[2] == b[2] == "arch")) for g in piers if len(g) > 2]
    ways = [min(_clear(a, b) for a in g for b in h) for g, h in zip(piers, piers[1:] + piers[:1])] if len(piers) > 1 else []
    crown = [p[2] for m in members if m["family"] == "crown" for p in m["points_m"]]
    mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")
    return {
        "feet_apart_m": mean(gaps),
        "pier_ground_m2": mean([_hull_area([f[0] for f in g]) for g in piers]),
        "way_through_m": mean(ways),
        "to_crown_m": _to_crown(members),
        "crown_m": mean(crown),
        "timber_m": sum(m["length_m"] for m in members),
        "timber_m3": sum(m["length_m"] * m["width_m"] * m["depth_m"] for m in members),
    }


def main() -> None:
    base = topology.load(str(HERE.parent / DESIGN))
    out = {"base": DESIGN, "points": POINTS, "measures": list(MEASURES), "sweeps": []}
    for sweep in SWEEPS:
        values = [round(sweep["from"] + (sweep["to"] - sweep["from"]) * i / (STATES - 1), 4) for i in range(STATES)]
        # The members are not always the same ones from state to state (the fine tier of the lattice
        # is chosen afresh), so each sweep keeps one list of every member it meets, and each state
        # says which of them it has.
        members, index, states, measures = [], {}, [], []
        for value in values:
            try:
                lines = snapshot.centrelines(sweep["set"](base, value))
            except Exception as error:  # a value the generator will not build: stop the sweep here
                print(f"  {sweep['id']} stops before {value}: {error}")
                break
            for m in lines["members"]:
                if m["id"] not in index:
                    index[m["id"]] = len(members)
                    members.append({"id": m["id"], "family": m["family"], "width_m": m["width_m"], "depth_m": m["depth_m"], "closed": m["closed"]})
            states.append({
                "has": [index[m["id"]] for m in lines["members"]],
                "mm": [round(c * 1000) for m in lines["members"] for p in resample(m) for c in p],
            })
            measures.append({k: (None if v != v else round(v, 4)) for k, v in measure(lines).items()})
            print(f"  {sweep['id']} {value}: {len(lines['members'])} members, " + ", ".join(f"{k} {v}" for k, v in measures[-1].items()))
        if len(states) < 2:
            continue
        out["sweeps"].append({**{k: v for k, v in sweep.items() if k != "set"}, "values": values[: len(states)], "to": values[len(states) - 1], "members": members, "states": states, "measures": measures})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("window.DESIGN_SPACE = " + json.dumps(out, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB), {len(out['sweeps'])} sweeps")


if __name__ == "__main__":
    main()
