"""Level B: a room's envelope as fans and roof panels between shared boundary curves.

Every boundary curve is built once, under its own ID, from the plan graph:

    <pier>.pier              base   -> spring   the vertical shaft
    <pier>.groin.lower       spring -> eave     } one smooth curve: the valley between two bays,
    <pier>.groin.upper       eave   -> crown    } with the eave node marked on it at eave height
    <bay>.arch.L / .R        spring -> apex     the two halves of the pointed arch
    <bay>.eave.L / .R        eave   -> apex -> eave   the line where the roof starts
    <bay>.ridge              apex   -> crown
    <bay>.crown.L / .R       arcs of the crown ring

A curve depends only on the elements in its name, on the crown and on the room's
shape parameters, so editing one bay cannot disturb a curve that belongs to another.

Each half of a bay is two patches:

    fan    the spandrel between the arch half and the valley. It is ruled by
           level lines: every ruling is horizontal, joining the arch to the
           lower groin below eave height and to the eave line above it. Where
           the arch leg and the groin leave the spring together the surface is
           a thin wedge, and level rulings are what keep that wedge well formed.
    roof   a four-sided Coons patch: eave line below, crown arc above, the
           upper groin on one side and the bay's ridge on the other.

Neighbouring patches name the same curve and the mesh gives them the same
vertices along it, so the surface is continuous along whole curves by
construction. Groins, ridges and eaves are deliberate creases, as in a rib
vault; inside a patch the surface is smooth, apart from a mild break in each
fan along its ruling at eave height. The surface starts at the springs: below
them an arch leg and a groin are the same vertical line, a shaft.

Shape parameters (room["shape"]), dimensionless unless marked:
    pier_height_m      height of the vertical shaft, floor to spring (metres)
    eave_height_m      height at which each groin carries its eave node (metres)
    arch_shoulder      vertical run of the arch above the spring, as a fraction of its rise
    arch_point_deg     slope of the arch where it meets the apex (0 would be a round arch)
    arch_reach         how far back from the apex that slope is held, as a fraction of the half-span
    groin_rise         vertical run of the groin above the spring, as a fraction of its rise
    groin_reach        how far out from the crown the arrival slope is held, as a fraction of the plan run
    ridge_pitch_deg    slope of the ridge as it leaves the apex (negative dips)
    ridge_run          how far the ridge holds that slope, as a fraction of its plan run
    ridge_reach        as groin_reach, for ridges
    crown_arrival_deg  slope at which groins and ridges meet the crown ring

Arches and groins are kept rising all the way (a wide, low arch is made less
pointed rather than allowed to sag), which is what lets them be cut at a height.

Pure Python (no bpy).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass

from .centreline import Anchor, BezierPath, Vec, add, arc_path, cross, dot, mul, norm, sub
from .topology import apex_point

CREASE_KINDS = ("groin", "ridge", "eave")


@dataclass(frozen=True)
class Edge:
    """One boundary curve, running between two named nodes."""

    id: str
    kind: str  # pier | groin | arch | eave | ridge | crown
    start: str
    end: str
    path: BezierPath


@dataclass(frozen=True)
class Patch:
    """One surface patch, named by the boundary curves around it."""

    id: str
    bay: str
    kind: str  # fan | roof
    edges: tuple


@dataclass(frozen=True)
class Envelope:
    room_id: str
    nodes: dict  # node ID -> point
    edges: dict  # edge ID -> Edge
    patches: dict  # patch ID -> Patch
    verts: list
    faces: list  # quads, with triangles where a fan's rulings close onto a node
    face_patch: list  # patch ID of each face
    edge_verts: dict  # edge ID -> vertex indices along it, ends included


def _cubic(p0: Vec, p1: Vec, p2: Vec, p3: Vec) -> BezierPath:
    return BezierPath([Anchor(p0, p0, p1), Anchor(p3, p2, p3)])


def _line(p0: Vec, p1: Vec) -> BezierPath:
    third = mul(sub(p1, p0), 1.0 / 3.0)
    return _cubic(p0, add(p0, third), sub(p1, third), p1)


def _split(p0: Vec, p1: Vec, p2: Vec, p3: Vec, t: float) -> tuple[BezierPath, BezierPath]:
    """Cut a cubic at parameter t into two cubics that together trace exactly the same curve."""

    def mix(a: Vec, b: Vec) -> Vec:
        return add(mul(a, 1.0 - t), mul(b, t))

    a, b, c = mix(p0, p1), mix(p1, p2), mix(p2, p3)
    d, e = mix(a, b), mix(b, c)
    cut = mix(d, e)
    return _cubic(p0, a, d, cut), _cubic(cut, e, c, p3)


def _up(height: float) -> Vec:
    return (0.0, 0.0, height)


def _parameter_at_height(controls, z: float) -> float:
    """Bezier parameter at which a cubic that rises all the way reaches height z."""
    z0, z1, z2, z3 = (p[2] for p in controls)
    lo, hi = 0.0, 1.0
    for _ in range(60):
        t = 0.5 * (lo + hi)
        u = 1.0 - t
        if u * u * u * z0 + 3 * u * u * t * z1 + 3 * u * t * t * z2 + t * t * t * z3 < z:
            lo = t
        else:
            hi = t
    return 0.5 * (lo + hi)


def _at_heights(path: BezierPath, heights) -> list:
    """Points of a single-cubic path at the given heights."""
    controls = (path.anchors[0].co, path.anchors[0].handle_right, path.anchors[1].handle_left, path.anchors[1].co)
    return [path.point(0, _parameter_at_height(controls, z)) for z in heights]


def _steps(a: float, b: float, n: int) -> list:
    """The n - 1 values strictly between a and b at equal spacing."""
    return [a + (b - a) * k / n for k in range(1, n)]


def arch_profile(span: float, rise: float, shape: dict) -> tuple:
    """A half-arch in its own vertical plane, as (distance toward the apex, height above the spring).

    It meets the apex at `arch_point_deg`, or more steeply where the bay is narrow for its
    height: a tall narrow arch becomes a sharper lancet instead of turning tightly at the top.
    """
    point = math.tan(max(math.radians(shape["arch_point_deg"]), math.pi / 2.0 - 2.0 * math.atan2(span, rise)))
    shoulder = shape["arch_shoulder"] * rise
    reach = min(shape["arch_reach"] * span, 0.9 * (rise - shoulder) / point)  # keeps the arch rising
    return ((0.0, 0.0), (0.0, shoulder), (span - reach, rise - reach * point), (span, rise))


def groin_profile(run: float, rise: float, shape: dict) -> tuple:
    """A groin in its own vertical plane, as (distance toward the crown, height above the spring)."""
    arrival = math.tan(math.radians(shape["crown_arrival_deg"]))
    upright = shape["groin_rise"] * rise
    reach = min(shape["groin_reach"] * run, 0.9 * (rise - upright) / arrival)  # keeps the groin rising
    return ((0.0, 0.0), (0.0, upright), (run - reach, rise - reach * arrival), (run, rise))


def ridge_profile(run: float, rise: float, shape: dict) -> tuple:
    """A ridge in its own vertical plane, as (distance toward the crown, height above the apex).

    It leaves the apex at `ridge_pitch_deg`, or more steeply where the climb to the crown needs
    it: the steeper start is the one that makes the ridge a single even arc, not a level run
    followed by a tight turn.
    """
    arrival = math.radians(shape["crown_arrival_deg"])
    fair = min(2.0 * math.atan2(rise, run) - arrival, math.radians(60.0))
    pitch = math.tan(max(math.radians(shape["ridge_pitch_deg"]), fair))
    out, back = shape["ridge_run"] * run, shape["ridge_reach"] * run
    return ((0.0, 0.0), (out, out * pitch), (run - back, rise - back * math.tan(arrival)), (run, rise))


def lift(profile, origin: Vec, direction: Vec) -> tuple:
    """Stand a (distance, height) profile up in the vertical plane through `origin` along `direction`."""
    return tuple((origin[0] + direction[0] * d, origin[1] + direction[1] * d, origin[2] + z) for d, z in profile)


def boundary(room: dict) -> tuple[dict, dict]:
    """The named nodes and boundary curves of a room."""
    shape, crown = room["shape"], room["crown"]
    z0 = room["floor_z_m"]
    cx, cy = crown["centre_m"]
    radius, height = crown["radius_m"], crown["height_m"]
    shaft, eave_z = shape["pier_height_m"], z0 + shape["eave_height_m"]
    nodes, edges = {}, {}

    def landing(x: float, y: float):
        """Where a curve from plan point (x, y) meets the crown ring, the inward direction and the plan run."""
        dx, dy = cx - x, cy - y
        distance = math.hypot(dx, dy)
        inward = (dx / distance, dy / distance, 0.0)
        return (cx - radius * inward[0], cy - radius * inward[1], z0 + height), inward, distance - radius

    def edge(edge_id: str, kind: str, start: str, end: str, path: BezierPath) -> None:
        edges[edge_id] = Edge(edge_id, kind, start, end, path)

    for pier in room["piers"]:
        pid = pier["id"]
        base = (pier["position_m"][0], pier["position_m"][1], z0)
        spring = add(base, _up(shaft))
        top, inward, run = landing(base[0], base[1])
        controls = lift(groin_profile(run, height - shaft, shape), spring, inward)
        lower, upper = _split(*controls, _parameter_at_height(controls, eave_z))
        nodes[pid + ".base"], nodes[pid + ".spring"] = base, spring
        nodes[pid + ".eave"], nodes[pid + ".crown"] = upper.anchors[0].co, top
        edge(pid + ".pier", "pier", pid + ".base", pid + ".spring", _line(base, spring))
        edge(pid + ".groin.lower", "groin", pid + ".spring", pid + ".eave", lower)
        edge(pid + ".groin.upper", "groin", pid + ".eave", pid + ".crown", upper)

    for bay in room["bays"]:
        bid = bay["id"]
        apex = apex_point(room, bay)
        top, inward, run = landing(apex[0], apex[1])
        nodes[bid + ".apex"], nodes[bid + ".crown"] = apex, top
        path = _cubic(*lift(ridge_profile(run, top[2] - apex[2], shape), apex, inward))
        edge(bid + ".ridge", "ridge", bid + ".apex", bid + ".crown", path)

        for side, pid in (("L", bay["from"]), ("R", bay["to"])):
            spring = nodes[pid + ".spring"]
            dx, dy = apex[0] - spring[0], apex[1] - spring[1]
            span = math.hypot(dx, dy)
            half = lift(arch_profile(span, apex[2] - spring[2], shape), spring, (dx / span, dy / span, 0.0))
            edge(f"{bid}.arch.{side}", "arch", pid + ".spring", bid + ".apex", _cubic(*half))

        edge(f"{bid}.eave.L", "eave", bay["from"] + ".eave", bid + ".apex", _line(nodes[bay["from"] + ".eave"], apex))
        edge(f"{bid}.eave.R", "eave", bid + ".apex", bay["to"] + ".eave", _line(apex, nodes[bay["to"] + ".eave"]))

        for side, start, end in (("L", bay["from"] + ".crown", bid + ".crown"), ("R", bid + ".crown", bay["to"] + ".crown")):
            a, b = nodes[start], nodes[end]
            bearing = math.atan2(a[1] - cy, a[0] - cx)
            sweep = (math.atan2(b[1] - cy, b[0] - cx) - bearing) % (2.0 * math.pi)
            tangent = (-math.sin(bearing), math.cos(bearing), 0.0)
            path = arc_path(a, tangent, (cx - a[0], cy - a[1], 0.0), radius, radius * sweep)
            edge(f"{bid}.crown.{side}", "crown", start, end, path)

    return nodes, edges


def _coons_grid(bottom: list, top: list, left: list, right: list, verts: list) -> list:
    """Vertex indices of a four-sided patch as grid[i][j], i across and j up.

    The four lists are the boundary curves' own vertex indices; interior vertices are new.
    """
    nu, nv = len(bottom) - 1, len(left) - 1
    corners_meet = (bottom[0], bottom[-1], top[0], top[-1]) == (left[0], right[0], left[-1], right[-1])
    if len(top) != nu + 1 or len(right) != nv + 1 or not corners_meet:
        raise ValueError("boundary curves do not meet at shared nodes")
    p00, p10, p01, p11 = verts[bottom[0]], verts[bottom[-1]], verts[top[0]], verts[top[-1]]
    grid = [[None] * (nv + 1) for _ in range(nu + 1)]
    for i in range(nu + 1):
        grid[i][0], grid[i][nv] = bottom[i], top[i]
    for j in range(nv + 1):
        grid[0][j], grid[nu][j] = left[j], right[j]
    for i in range(1, nu):
        u = i / nu
        lo, hi = verts[bottom[i]], verts[top[i]]
        for j in range(1, nv):
            v = j / nv
            l, r = verts[left[j]], verts[right[j]]
            verts.append(
                tuple(
                    (1 - v) * lo[k] + v * hi[k] + (1 - u) * l[k] + u * r[k]
                    - ((1 - u) * (1 - v) * p00[k] + u * (1 - v) * p10[k] + (1 - u) * v * p01[k] + u * v * p11[k])
                    for k in range(3)
                )
            )
            grid[i][j] = len(verts) - 1
    return grid


def _ruled_grid(left: list, right: list, columns: int, verts: list) -> list:
    """Vertex indices of a ruled patch as grid[i][j]: a straight ruling joins left[j] to right[j].

    Both sides start at one node and end at one node, so the first and last rulings have no length.
    """
    if len(left) != len(right) or left[0] != right[0] or left[-1] != right[-1]:
        raise ValueError("the two sides of a ruled patch must share their end nodes")
    grid = [[None] * len(left) for _ in range(columns + 1)]
    for j, (a, b) in enumerate(zip(left, right)):
        grid[0][j], grid[columns][j] = a, b
        for i in range(1, columns):
            if a == b:
                grid[i][j] = a
            else:
                u = i / columns
                verts.append(tuple((1 - u) * verts[a][k] + u * verts[b][k] for k in range(3)))
                grid[i][j] = len(verts) - 1
    return grid


def build_envelope(room: dict, sampling: dict) -> Envelope:
    """Mesh a room's envelope. Each node and each edge sample is one vertex, shared by every patch that touches it."""
    nodes, edges = boundary(room)
    across, fan_up, roof_up = sampling["across"], sampling["fan_up"], sampling["roof_up"]
    eave_z = room["floor_z_m"] + room["shape"]["eave_height_m"]
    verts, node_vert, edge_verts = [], {}, {}

    def at_node(node_id: str) -> int:
        if node_id not in node_vert:
            node_vert[node_id] = len(verts)
            verts.append(nodes[node_id])
        return node_vert[node_id]

    def inner_points(e: Edge) -> list:
        """Sample points strictly inside an edge. The two sides of a fan are sampled level with each other."""
        z_start, z_end = nodes[e.start][2], nodes[e.end][2]
        if e.id.endswith(".groin.lower"):
            return _at_heights(e.path, _steps(z_start, z_end, fan_up))
        if e.kind == "arch":
            return _at_heights(e.path, _steps(z_start, eave_z, fan_up) + [eave_z] + _steps(eave_z, z_end, across))
        n = across if e.kind in ("eave", "crown") else roof_up
        return [e.path.point_at(k / n) for k in range(1, n)]

    for e in edges.values():
        if e.kind == "pier":
            continue  # shafts bound no patch
        start, end, points = at_node(e.start), at_node(e.end), inner_points(e)
        edge_verts[e.id] = [start, *range(len(verts), len(verts) + len(points)), end]
        verts.extend(points)

    patches, faces, face_patch = {}, [], []

    def add_patch(patch_id: str, bay_id: str, kind: str, edge_ids: tuple, grid: list) -> None:
        patches[patch_id] = Patch(patch_id, bay_id, kind, edge_ids)
        for i in range(len(grid) - 1):
            for j in range(len(grid[0]) - 1):
                quad = (grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])
                face = tuple(v for k, v in enumerate(quad) if v != quad[k - 1])  # a ruling of no length leaves a triangle
                if len(face) >= 3:
                    faces.append(face)
                    face_patch.append(patch_id)

    columns = sampling["fan_across"]
    for bay in room["bays"]:
        bid, a, b = bay["id"], bay["from"], bay["to"]
        ev = edge_verts
        arch_l, arch_r, eave_l, eave_r, ridge = (ev[f"{bid}.{n}"] for n in ("arch.L", "arch.R", "eave.L", "eave.R", "ridge"))
        # A fan's inner side runs up the lower groin to the eave node, then along the eave line to the apex.
        inner_l = ev[f"{a}.groin.lower"] + eave_l[1:]
        inner_r = ev[f"{b}.groin.lower"] + eave_r[-2::-1]
        add_patch(f"{bid}.fan.L", bid, "fan", (f"{a}.groin.lower", f"{bid}.eave.L", f"{bid}.arch.L"), _ruled_grid(inner_l, arch_l, columns, verts))
        add_patch(
            f"{bid}.roof.L", bid, "roof", (f"{a}.groin.upper", f"{bid}.ridge", f"{bid}.eave.L", f"{bid}.crown.L"),
            _coons_grid(eave_l, ev[f"{bid}.crown.L"], ev[f"{a}.groin.upper"], ridge, verts),
        )
        add_patch(
            f"{bid}.roof.R", bid, "roof", (f"{bid}.ridge", f"{b}.groin.upper", f"{bid}.eave.R", f"{bid}.crown.R"),
            _coons_grid(eave_r, ev[f"{bid}.crown.R"], ridge, ev[f"{b}.groin.upper"], verts),
        )
        add_patch(f"{bid}.fan.R", bid, "fan", (f"{bid}.arch.R", f"{b}.groin.lower", f"{bid}.eave.R"), _ruled_grid(arch_r, inner_r, columns, verts))
    return Envelope(room["id"], nodes, edges, patches, verts, faces, face_patch, edge_verts)


def bay_signature(env: Envelope, bay_id: str) -> tuple:
    """Every vertex position of a bay's patches, for testing that an edit left the bay exactly as it was."""
    return tuple(env.verts[i] for face, patch in zip(env.faces, env.face_patch) if env.patches[patch].bay == bay_id for i in face)


def check_envelope(env: Envelope) -> dict:
    """Validity of the envelope mesh: finite, consistently oriented, open only at the arches and the
    crown, free of collapsed or folded faces, and joined along the full length of every shared curve."""
    problems = []
    if not all(math.isfinite(c) for p in env.verts for c in p):
        problems.append("non-finite coordinates")

    directed = Counter((a, b) for face in env.faces for a, b in zip(face, face[1:] + face[:1]))
    if any(n > 1 for n in directed.values()):
        problems.append("faces are inconsistently wound or overlap")
    rim = {a: b for (a, b) in directed if (b, a) not in directed}
    loops, seen = 0, set()
    for start in rim:
        if start not in seen:
            loops += 1
            v = start
            while v not in seen:
                seen.add(v)
                v = rim[v]
    if loops != 2:
        problems.append(f"expected two open rims (arches and crown), found {loops}")

    normals, collapsed = [], 0
    for face in env.faces:
        p = [env.verts[i] for i in face]
        n = cross(sub(p[1], p[0]), sub(p[2], p[0])) if len(p) == 3 else cross(sub(p[2], p[0]), sub(p[3], p[1]))
        length = norm(n)
        collapsed += length < 2e-8
        normals.append(mul(n, 1.0 / length) if length >= 2e-8 else None)
    if collapsed:
        problems.append(f"{collapsed} collapsed faces")

    across = defaultdict(list)
    for f, face in enumerate(env.faces):
        for a, b in zip(face, face[1:] + face[:1]):
            across[frozenset((a, b))].append(f)
    agreement = 1.0
    for pair in across.values():
        if len(pair) == 2 and env.face_patch[pair[0]] == env.face_patch[pair[1]] and normals[pair[0]] and normals[pair[1]]:
            agreement = min(agreement, dot(normals[pair[0]], normals[pair[1]]))
    if agreement <= 0.0:
        problems.append("a patch folds back on itself")

    users = defaultdict(set)
    for patch in env.patches.values():
        for edge_id in patch.edges:
            users[edge_id].add(patch.id)
    shared = {edge_id: patch_ids for edge_id, patch_ids in users.items() if len(patch_ids) == 2}
    joined = 0
    for edge_id, patch_ids in shared.items():
        along = env.edge_verts[edge_id]
        joined += all({env.face_patch[f] for f in across[frozenset(pair)]} == patch_ids for pair in zip(along, along[1:]))
    if joined != len(shared):
        problems.append(f"{len(shared) - joined} shared curves are not joined along their full length")

    return {
        "ok": not problems,
        "problems": problems,
        "vertices": len(env.verts),
        "faces": len(env.faces),
        "patches": len(env.patches),
        "open_rims": loops,
        "shared_curves": len(shared),
        "shared_curves_joined_full_length": joined,
        "collapsed_faces": collapsed,
        "min_normal_agreement_in_patch": round(agreement, 4),
    }
