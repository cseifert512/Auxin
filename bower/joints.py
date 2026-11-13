"""Joints: where members meet, and what is cut out of each member there.

Every joint names its two members, where it is, the angle they meet at and the
cuts it needs: one `Cut` per member, stated along that member's own centreline
so that it can be set out on the piece. Joints are derived from the members, so
they regenerate with them.

    cross_lap     two lattice members (ribs, hoops, rings) crossing flush. Each is notched to half
                  its depth where the other passes. Which is cut on its outer face is fixed by
                  timber["joints"]["lap_order"]: a member earlier in that order goes in first and
                  is notched on its outer face; one later in the order drops onto it from outside
                  and is notched on its inner face.
    housing       a rib's foot let into the inner face of the arch it lands on, or its head let
                  into the side of the ring it stops at
    crown_seat    the level-cut head of a rib let into the underside of the crown ring
    paired_heads  the two ribs that arrive side by side at one point of the crown ring
    mitre         the two halves of an arch or of a hoop meeting at the bay's apex
    pier_mitre    the two arch legs at a pier, mitred together over the height of the pier
    scarf         a splice in a closed ring, or in a member longer than max_piece_length_m
    base          a leg or arch foot on its footing

`Cut.face` is `outer` or `inner` for a face of a member lying in the roof (outer
is the roof's upper side), `room` for the room-side face of an arch, `side`,
`underside`, `start` or `end`.

`review` is set where a joint cannot be made as drawn: two members running
alongside each other, a crossing too oblique to notch, or notches on opposite
faces of one member that would meet. Those are listed, not hidden, and are left
uncut in the model. It is also set where a lap can be cut but needs more than
flat walls, because the member's section turns across the notch.

Lap notches are also returned as `Notch`es for the member meshes, so the model
shows each member as it would be cut.

Pure Python (no bpy). Depths and clearances are provisional concept values: this
sets joints out, it does not prove them.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from .centreline import dot, norm, sub, unit
from .member import Member, Notch, fit_notches
from .timber import LATTICE

LAP_ORDER = ("ring", "hoop", "cw", "ccw")


@dataclass(frozen=True)
class Cut:
    """One machining operation on one member, set out along that member's centreline."""

    member: str
    operation: str  # lap | housing | shoulder | level | mitre | scarf | square
    at_m: float  # station of the cut's centre, from the member's start
    length_m: float  # its extent along the member
    face: str
    depth_m: float
    skew_deg: float  # angle between the cut's walls and the square across the member


@dataclass(frozen=True)
class Joint:
    id: str
    kind: str
    members: tuple
    at_m: tuple
    angle_deg: float
    cuts: tuple
    review: str = ""


def lap_layer(member: Member) -> str | None:
    """Which layer of the lattice a member belongs to when laps are ordered: ring, hoop, cw or ccw."""
    parts = member.id.split(".")
    if ".ring." in member.id:
        return "ring" if member.family in LATTICE else None
    if member.family == "hoop":
        return "hoop"
    if len(parts) == 4 and parts[2] in ("ccw", "cw") and member.family in LATTICE:
        return parts[2]
    return None


def _crossings(lattice: list[Member]) -> list:
    """Every place two lattice members' centrelines cross: (i, j, station on i, station on j), or
    (i, j, station, None) where they run alongside each other instead."""
    step, cell, reach = 0.05, 0.2, 0.12
    stations = [m.path.stations(step) for m in lattice]
    nodes = [set(m.nodes) for m in lattice]

    def key(p):
        return (math.floor(p[0] / cell), math.floor(p[1] / cell), math.floor(p[2] / cell))

    grid = defaultdict(list)
    for i, along in enumerate(stations):
        for k, st in enumerate(along):
            grid[key(st.point)].append((i, k))
    near = defaultdict(list)
    for i, along in enumerate(stations):
        for k, st in enumerate(along):
            gx, gy, gz = key(st.point)
            for cx in (gx - 1, gx, gx + 1):
                for cy in (gy - 1, gy, gy + 1):
                    for cz in (gz - 1, gz, gz + 1):
                        for j, l in grid.get((cx, cy, cz), ()):
                            if j > i:
                                d = norm(sub(st.point, stations[j][l].point))
                                if d < reach:
                                    near[(i, j)].append((k, d, l))
    found = []
    for (i, j), hits in sorted(near.items()):
        if nodes[i] & nodes[j]:
            continue  # jointed at a named node: not a crossing
        hits.sort()
        runs, run = [], [hits[0]]
        for hit in hits[1:]:
            if hit[0] - run[-1][0] > 8:
                runs.append(run)
                run = []
            run.append(hit)
        runs.append(run)
        for run in runs:
            k, _, l = min(run, key=lambda h: h[1])
            a, b = stations[i][k], stations[j][l]
            crossing = True
            for _ in range(3):  # closest approach of the two tangent lines, re-taken from the new stations
                c = dot(a.tangent, b.tangent)
                if 1.0 - c * c < 0.03:  # under about 10 degrees apart
                    crossing = False
                    break
                r = sub(a.point, b.point)
                da = (c * dot(b.tangent, r) - dot(a.tangent, r)) / (1.0 - c * c)
                db = (dot(b.tangent, r) - c * dot(a.tangent, r)) / (1.0 - c * c)
                a = lattice[i].path.station_at(a.s + max(-0.08, min(0.08, da)))
                b = lattice[j].path.station_at(b.s + max(-0.08, min(0.08, db)))
            if not crossing:
                if len({h[0] for h in run}) > 6:  # alongside each other for 0.3 m or more
                    found.append((i, j, a, None))
            elif norm(sub(a.point, b.point)) < 0.1:
                found.append((i, j, a, b))
    return found


def find_joints(members: list[Member], timber: dict) -> tuple[list[Joint], dict]:
    """The joints of a room's members, and the lap notches to cut into each member's mesh (by member ID)."""
    cfg = timber.get("joints", {})
    clearance = cfg.get("lap_clearance_m", 0.001)
    order = list(cfg.get("lap_order", LAP_ORDER))
    housing_depth = cfg.get("housing_depth_m", 0.05)
    longest = cfg.get("max_piece_length_m", 12.0)
    joints, laps = [], defaultdict(list)  # laps: member ID -> [(Notch, index into joints)]

    def angle_between(a, b) -> float:
        return math.degrees(math.acos(min(1.0, abs(dot(a, b)))))

    # --- cross laps --------------------------------------------------------------------------
    lattice = [m for m in members if lap_layer(m)]
    for i, j, a, b in _crossings(lattice):
        first, second = lattice[i], lattice[j]
        if b is None:
            joints.append(Joint(f"alongside:{first.id}:{second.id}", "alongside", (first.id, second.id), tuple(round(c, 3) for c in a.point), 0.0, (), "the two run alongside each other here; no lap is set out"))
            continue
        if (order.index(lap_layer(first)), first.id) > (order.index(lap_layer(second)), second.id):
            first, second, a, b = second, first, b, a  # `first` goes in first and is notched on its outer face
        middle = tuple((a.point[k] + b.point[k]) / 2.0 for k in range(3))
        square = unit(tuple(a.depth_axis[k] + b.depth_axis[k] for k in range(3)))  # normal of the plane the two halves meet on
        angle = angle_between(a.tangent, b.tangent)
        cuts, review = [], ""
        # Sections lie with +depth toward the room, so the outer face is the -depth side.
        for member, here, other, there, face, sign in ((first, a, second, b, "outer", -1), (second, b, first, a, "inner", 1)):
            floor = dot(sub(middle, here.point), here.depth_axis) - sign * clearance / 2.0
            half_gap = other.width / 2.0 + clearance
            across = dot(here.tangent, there.width_axis)
            sine, way = max(abs(across), 0.2), (1.0 if across > 0 else -1.0)
            depth = member.depth / 2.0 - sign * floor
            walls = [(tuple(middle[k] + side * way * half_gap * there.width_axis[k] for k in range(3)), there.width_axis) for side in (-1, 1)]
            # the floor is a plane parallel to the one the halves meet on, half the clearance back from it
            level = tuple(middle[k] - sign * clearance / 2.0 * square[k] for k in range(3))
            laps[member.id].append((Notch(here.s - half_gap / sine, here.s + half_gap / sine, sign, (level, square), walls[0], walls[1]), len(joints)))
            cuts.append(Cut(member.id, "lap", round(here.s, 3), round(2.0 * half_gap / sine, 3), face, round(depth, 3), round(90.0 - angle, 1)))
            if not 0.3 * member.depth <= depth <= 0.7 * member.depth:
                review = "the two centrelines pass at different heights here, so the lap is uneven"
            # On a tightly curved roof a member's section turns as it runs. Where it turns further across
            # the notch than the clearance allows, flat notch walls will bind.
            lo, hi = (member.path.station_at(here.s + side * half_gap / sine) for side in (-1, 1))
            # twist about its own axis only, as the distance its faces move off a flat wall between the middle of the notch and its ends
            turned = abs(dot(sub(hi.depth_axis, lo.depth_axis), here.width_axis)) * member.depth / 4.0
            if turned > clearance and not review:
                review = f"the section of {member.id} turns {turned * 1000:.0f} mm across the notch, more than the clearance: its walls must follow the turn"
        joints.append(Joint(f"lap:{first.id}:{second.id}", "cross_lap", (first.id, second.id), tuple(round(c, 3) for c in middle), round(angle, 1), tuple(cuts), review))
    # A lap that cannot be cut in one of its members is left uncut in both, and the members' notches
    # fitted again without it, until every remaining lap can be cut in both.
    by_id = {m.id: m for m in members}
    uncut, notches = set(), {}
    while True:
        dropped = False
        for member_id, mine in laps.items():
            wanted = [(n, index) for n, index in mine if index not in uncut]
            notches[member_id], rejected = fit_notches(by_id[member_id], [n for n, _ in wanted])
            for k in rejected:
                index = wanted[k][1]
                old = joints[index]
                note = f"its notch in {member_id} is too oblique, too near an end, or opposite another notch; not cut in the model"
                joints[index] = Joint(old.id, old.kind, old.members, old.at_m, old.angle_deg, old.cuts, (old.review + "; " if old.review else "") + note)
                uncut.add(index)
                dropped = True
        if not dropped:
            break

    # --- joints at named nodes ---------------------------------------------------------------
    by_node = defaultdict(list)
    for m in members:
        for node in m.nodes:
            by_node[node].append(m)

    def near_station(member: Member, point) -> float:
        return min(member.path.stations(0.05), key=lambda st: norm(sub(st.point, point))).s

    def point(p) -> tuple:
        return tuple(round(c, 3) for c in p)

    floor = min(m.path.anchors[0].co[2] for m in members)
    for m in members:
        start, end = m.path.station_at(0.0), m.path.station_at(m.path.length)
        layer = lap_layer(m)
        if m.start_cut and layer in ("cw", "ccw"):  # a rib's foot in an arch
            hosts = [h for h in by_node[m.nodes[0]] if h.family in ("arch", "inner")]
            if hosts:
                host = min(hosts, key=lambda h: min(norm(sub(st.point, start.point)) for st in h.path.stations(0.1)))
                flat = math.hypot(start.tangent[0], start.tangent[1])  # in plan: how far from square it meets the arch
                skew = round(angle_between((start.tangent[0] / flat, start.tangent[1] / flat, 0.0), m.start_cut), 1)
                width = m.width / max(math.cos(math.radians(skew)), 0.2) + 2.0 * clearance
                joints.append(
                    Joint(
                        f"housing:{m.id}:{host.id}", "housing", (m.id, host.id), point(start.point), round(90.0 - skew, 1),
                        (Cut(m.id, "shoulder", 0.0, 0.0, "start", 0.0, skew), Cut(host.id, "housing", round(near_station(host, start.point), 3), round(width, 3), "room", housing_depth, skew)),
                        "meets the arch at a glancing angle" if skew > 55.0 else "",
                    )
                )
        if layer in ("cw", "ccw"):  # a rib's head in a ring
            for host in by_node[m.nodes[-1]]:
                if ".ring." not in host.id:
                    continue
                if host.family == "crown":
                    seat = timber.get("crown", {}).get("seat_m", 0.03)
                    joints.append(Joint(f"seat:{m.id}:{host.id}", "crown_seat", (m.id, host.id), point(end.point), 90.0, (Cut(m.id, "level", round(m.path.length, 3), 0.0, "end", 0.0, 0.0), Cut(host.id, "housing", round(near_station(host, end.point), 3), round(m.width + 2.0 * clearance, 3), "underside", seat, 0.0))))
                else:
                    at = near_station(host, end.point)
                    angle = angle_between(end.tangent, host.path.station_at(at).tangent)
                    joints.append(Joint(f"housing:{m.id}:{host.id}", "housing", (m.id, host.id), point(end.point), round(angle, 1), (Cut(m.id, "shoulder", round(m.path.length, 3), 0.0, "end", 0.0, round(90.0 - angle, 1)), Cut(host.id, "housing", round(at, 3), round(m.width / max(math.sin(math.radians(angle)), 0.2) + 2.0 * clearance, 3), "side", round(host.width / 2.0, 3), round(90.0 - angle, 1)))))
        for tag, st, at, upright in (("", start, 0.0, start.tangent[2]), (":end", end, m.path.length, -end.tangent[2])):
            if abs(st.point[2] - floor) < 1e-6 and upright > 0.99:  # stands upright on the floor
                joints.append(Joint(f"base:{m.id}{tag}", "base", (m.id, ""), point(st.point), 90.0, (Cut(m.id, "square", round(at, 3), 0.0, "end" if tag else "start", 0.0, 0.0),)))
        closed = norm(sub(start.point, end.point)) < 1e-6
        pieces = max(2 if closed else 1, math.ceil(m.path.length / longest))
        if pieces > 1:  # splices, each moved to the middle of the widest gap between cuts near where it would fall
            taken = sorted((n.lo + n.hi) / 2.0 for n in notches.get(m.id, []))
            for k in range(pieces if closed else pieces - 1):
                want = m.path.length * (k + (0.5 if closed else 1.0)) / pieces
                gaps = [(b - a, (a + b) / 2.0) for a, b in zip(taken, taken[1:]) if abs((a + b) / 2.0 - want) < m.path.length / (2.0 * pieces)]
                at = max(gaps)[1] if gaps else want
                joints.append(Joint(f"scarf:{m.id}:{k + 1}", "scarf", (m.id, m.id), point(m.path.station_at(at).point), 0.0, (Cut(m.id, "scarf", round(at, 3), round(4.0 * m.depth, 3), "side", round(m.width, 3), 0.0),)))

    for node, group in sorted(by_node.items()):
        if ".top." in node:  # the ribs that arrive together at one point of the crown ring
            group = [m for m in group if lap_layer(m) in ("cw", "ccw")]
        if len(group) != 2:
            continue
        a, b = group
        if node.endswith(".apex"):
            end = a.path.station_at(a.path.length)
            slope = round(math.degrees(math.asin(min(1.0, abs(end.tangent[2])))), 1)
            joints.append(Joint(f"mitre:{a.id}:{b.id}", "mitre", (a.id, b.id), point(end.point), round(2.0 * slope, 1), tuple(Cut(m.id, "mitre", round(m.path.length, 3), 0.0, "end", 0.0, slope) for m in (a, b))))
        elif node.endswith(".mitre"):
            foot, height = a.path.station_at(0.0), a.path.anchors[1].co[2] - a.path.anchors[0].co[2]
            angle = angle_between(a.path.station_at(a.path.length * 0.5).width_axis, b.path.station_at(b.path.length * 0.5).width_axis)
            joints.append(Joint(f"pier_mitre:{a.id}:{b.id}", "pier_mitre", (a.id, b.id), point(foot.point), round(180.0 - angle, 1), tuple(Cut(m.id, "mitre", round(height / 2.0, 3), round(height, 3), "side", round(m.depth, 3), round(angle / 2.0, 1)) for m in (a, b))))
        elif ".top." in node and {lap_layer(a), lap_layer(b)} == {"cw", "ccw"}:
            joints.append(Joint(f"pair:{a.id}:{b.id}", "paired_heads", (a.id, b.id), point(a.path.station_at(a.path.length).point), round(angle_between(a.path.station_at(a.path.length).tangent, b.path.station_at(b.path.length).tangent), 1), ()))
    return joints, notches


def joint_rows(joints: list[Joint]) -> list[dict]:
    """One row per joint for the joint schedule: its members, place, angle and the cut in each member."""
    rows = []
    for joint in joints:
        row = {"id": joint.id, "kind": joint.kind, "member_a": joint.members[0], "member_b": joint.members[1], "x_m": joint.at_m[0], "y_m": joint.at_m[1], "z_m": joint.at_m[2], "angle_deg": joint.angle_deg}
        for tag, k in (("a", 0), ("b", 1)):
            cut = joint.cuts[k] if k < len(joint.cuts) else None
            for field in ("operation", "at_m", "length_m", "face", "depth_m", "skew_deg"):
                row[f"{tag}_{field}"] = getattr(cut, field) if cut else ""
        row["review"] = joint.review
        rows.append(row)
    return rows


def joint_summary(joints: list[Joint]) -> dict:
    kinds = defaultdict(int)
    for joint in joints:
        kinds[joint.kind] += 1
    return {
        "joints": len(joints),
        "by_kind": dict(sorted(kinds.items())),
        "to_review": sum(1 for j in joints if j.review),
        "laps_left_uncut": sum(1 for j in joints if "not cut in the model" in j.review),
        "laps_whose_walls_must_follow_a_turn": sum(1 for j in joints if "must follow the turn" in j.review and "not cut in the model" not in j.review),
    }
