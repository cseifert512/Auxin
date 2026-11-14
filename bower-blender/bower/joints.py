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
    crown_seat    the head of a rib, cut square to the roof's section there, let into the crown ring
    paired_heads  the two ribs that arrive side by side at one point of the crown ring
    mitre         the two halves of an arch or of a hoop meeting at the bay's apex
    pier_mitre    two arch legs at a pier, mitred together over the height of the pier (three legs
                  meet at a pier that two rooms share: each pair of them is one such joint)
    scarf         a splice in a closed ring, or in a member longer than max_piece_length_m
    base          a leg or arch foot on its footing

`Cut.face` is `outer` or `inner` for a face of a member lying in the roof (outer
is the roof's upper side), `room` for the room-side face of an arch, `side`,
`underside`, `start` or `end`.

Members are milled by robot, so a joint is cut as the true shape of what it
receives. With timber["joints"]["cut_meshes"] set to "milled", every lap,
housing, seat and pier mitre comes with a cutter: a closed mesh of the volume
to remove from the member, which is the mating member's own volume, a clearance
larger, on the cut side of the plane the two meet on. A lap's walls therefore
follow the other member's sides as they turn, and a pocket is the shape of the
end it takes. Where a member is crossed on both faces at one place it keeps the
middle third of its depth and those two laps are made a third deep.

"notches" is the earlier, simpler model, kept as an option: flat-walled lap
notches stepped into the section sweep, laps only. It cannot cut a lap that is
too oblique, too near an end, or opposite another notch, and says so.

`review` is set where a joint still needs a detail of its own: two members
running alongside each other, four members meeting at one place, or a lap whose
two centrelines pass at different heights.

Pure Python (no bpy). Depths and clearances are provisional concept values: this
sets joints out, it does not prove them.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from .centreline import dot, norm, sub, unit
from .member import Member, Notch, block, box, fit_notches
from .timber import LATTICE

LAP_ORDER = ("ring", "hoop", "cw", "ccw")
CUTTER_REACH_M = 0.25  # how far from the other member's centreline a lap cutter runs, to be sure of clearing the face


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


def _crossings(lattice: list[Member], shallowest: float = 0.03) -> list:
    """Every place two lattice members' centrelines cross: (i, j, station on i, station on j), or
    (i, j, station, None) where they run alongside each other instead.

    `shallowest` is the squared sine of the smallest crossing angle that still counts as a
    crossing: 0.03 is about 10 degrees. A crossing also carries, for each member, the stations
    between which the two bodies overlap in plan: members that cross at a shallow angle, or
    cross and then run on side by side, overlap for much longer than their widths.
    """
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
                if 1.0 - c * c < shallowest:
                    crossing = False
                    break
                r = sub(a.point, b.point)
                da = (c * dot(b.tangent, r) - dot(a.tangent, r)) / (1.0 - c * c)
                db = (dot(b.tangent, r) - c * dot(a.tangent, r)) / (1.0 - c * c)
                span = 0.08 if 1.0 - c * c >= 0.03 else 0.4  # a shallow crossing may lie well along from the nearest samples
                a = lattice[i].path.station_at(a.s + max(-span, min(span, da)))
                b = lattice[j].path.station_at(b.s + max(-span, min(span, db)))
            if not crossing:
                if len({h[0] for h in run}) > 6:  # alongside each other for 0.3 m or more
                    found.append((i, j, a, None, None))
            elif norm(sub(a.point, b.point)) < 0.1:
                close = [h for h in run if h[1] < (lattice[i].width + lattice[j].width) / 2.0 + 0.01] or [(k, 0.0, l)]
                over_i = (stations[i][min(h[0] for h in close)].s, stations[i][max(h[0] for h in close)].s)
                over_j = (stations[j][min(h[2] for h in close)].s, stations[j][max(h[2] for h in close)].s)
                found.append((i, j, a, b, (over_i, over_j)))
    return found


def find_joints(members: list[Member], timber: dict) -> tuple[list[Joint], dict, dict]:
    """The joints of a room's members, and what to cut out of each member's mesh for them.

    Returns (joints, notches, cutters), the last two keyed by member ID. Which is filled depends
    on timber["joints"]["cut_meshes"]:
        "milled"   cutters: closed meshes of the volumes to mill out of the member, every joint
        "notches"  notches: flat-walled lap notches the section sweep can step in, laps only
        "none"     neither
    """
    cfg = timber.get("joints", {})
    mode = cfg.get("cut_meshes", "milled")
    mode = "milled" if mode is True else (mode or "none")
    clearance = cfg.get("lap_clearance_m", 0.001)
    order = list(cfg.get("lap_order", LAP_ORDER))
    housing_depth = cfg.get("housing_depth_m", 0.05)
    longest = cfg.get("max_piece_length_m", 12.0)
    by_id = {m.id: m for m in members}
    joints, cutters = [], defaultdict(list)
    wanted = defaultdict(list)  # member ID -> [(Notch, index into joints)], for "notches"
    # A cutter that stands for a member is built through the stations of that member's own mesh.
    mesh_spacing = timber.get("sampling", {}).get("mesh_station_spacing_m", 0.08)
    meshed = {m.id: [st.s for st in m.path.stations(mesh_spacing)] for m in members} if mode == "milled" else {}

    def angle_between(a, b) -> float:
        return math.degrees(math.acos(min(1.0, abs(dot(a, b)))))

    def point(p) -> tuple:
        return tuple(round(c, 3) for c in p)

    # --- cross laps --------------------------------------------------------------------------
    lattice = [m for m in members if lap_layer(m)]
    laps = []
    # A robot can mill a lap however obliquely two members cross, so only members that never cross are left as "alongside".
    for i, j, a, b, over in _crossings(lattice, 0.004 if mode == "milled" else 0.03):
        first, second = lattice[i], lattice[j]
        if b is None:
            joints.append(Joint(f"alongside:{first.id}:{second.id}", "alongside", (first.id, second.id), point(a.point), 0.0, (), "the two run alongside each other here; no lap is set out"))
            continue
        if (order.index(lap_layer(first)), first.id) > (order.index(lap_layer(second)), second.id):
            first, second, a, b, over = second, first, b, a, over[::-1]  # `first` goes in first and is notched on its outer face
        laps.append({"first": first, "second": second, "a": a, "b": b, "over": over, "shifts": set()})

    def sides(lap):
        """Each member of a lap with its station, the other member and its station, the face it is cut on and that face's sign."""
        # Sections lie with +depth toward the room, so the outer face is the -depth side.
        return ((lap["first"], lap["a"], lap["second"], lap["b"], "outer", -1, lap["over"][0], lap["over"][1]), (lap["second"], lap["b"], lap["first"], lap["a"], "inner", 1, lap["over"][1], lap["over"][0]))

    # A member crossed on both faces at one place cannot be halved twice. There it keeps the middle
    # third of its depth: the lap on its inner face is made a third deep, and so is the one on its outer face.
    reach = defaultdict(list)  # member ID -> [(station, reach of the notch along it, face sign, lap)]
    for lap in laps:
        for member, here, other, there, _, sign, mine, _ in sides(lap):
            sine = max(abs(dot(here.tangent, there.width_axis)), 0.06)
            straight = (other.width / 2.0 + clearance + member.width / 2.0) / sine + 0.005
            reach[member.id].append(((mine[0] + mine[1]) / 2.0, max(straight, (mine[1] - mine[0]) / 2.0 + 0.03), sign, lap))
    for member_id, mine in reach.items():
        for s1, r1, sign1, lap in mine:
            if any(sign2 != sign1 and abs(s1 - s2) < r1 + r2 for s2, r2, sign2, _ in mine):
                lap["shifts"].add(sign1 * by_id[member_id].depth / 6.0)  # toward the room for an inner-face lap, away for an outer

    for lap in laps:
        first, second, a, b = lap["first"], lap["second"], lap["a"], lap["b"]
        square = unit(tuple(a.depth_axis[k] + b.depth_axis[k] for k in range(3)))  # normal of the plane the two parts meet on
        review = ""
        shift = 0.0
        if len(lap["shifts"]) == 1:
            shift = next(iter(lap["shifts"]))
        elif lap["shifts"]:
            review = "four members meet here: each of these two is already cut from both faces, so this lap needs its own detail"
        middle = tuple((a.point[k] + b.point[k]) / 2.0 + shift * square[k] for k in range(3))
        angle = angle_between(a.tangent, b.tangent)
        cuts = []
        for member, here, other, there, face, sign, mine, theirs in sides(lap):
            half_gap = other.width / 2.0 + clearance
            across = dot(here.tangent, there.width_axis)
            sine, way = max(abs(across), 0.2 if mode == "notches" else 0.06), (1.0 if across > 0 else -1.0)
            # the floor is a plane parallel to the one the two parts meet on, half the clearance back from it
            level = tuple(middle[k] - sign * clearance / 2.0 * square[k] for k in range(3))
            depth = member.depth / 2.0 - sign * dot(sub(level, here.point), here.depth_axis)
            cuts.append(Cut(member.id, "lap", round(here.s, 3), round(max(2.0 * half_gap / sine, mine[1] - mine[0]), 3), face, round(depth, 3), round(90.0 - angle, 1)))
            if not 0.25 * member.depth <= depth <= 0.75 * member.depth and not review:
                review = "the two centrelines pass at different heights here, so the lap is uneven"
            if mode == "notches":
                walls = [(tuple(middle[k] + side * way * half_gap * there.width_axis[k] for k in range(3)), there.width_axis) for side in (-1, 1)]
                wanted[member.id].append((Notch(here.s - half_gap / sine, here.s + half_gap / sine, sign, (level, square), walls[0], walls[1]), len(joints)))
                # flat walls bind where the member's section turns across the notch by more than the clearance
                lo, hi = (member.path.station_at(here.s + side * half_gap / sine) for side in (-1, 1))
                turned = abs(dot(sub(hi.depth_axis, lo.depth_axis), here.width_axis)) * member.depth / 4.0
                if turned > clearance and not review:
                    review = f"the section of {member.id} turns {turned * 1000:.0f} mm across the notch, more than the clearance: its walls must follow the turn"
            elif mode == "milled":
                # What is milled out of this member is the other member's own volume, a clearance larger,
                # on this member's cut side of the floor: it follows the other member's sides as they turn.
                run = (member.width / 2.0) / sine + other.width / 2.0 + 0.03
                far = (-CUTTER_REACH_M, 0.0) if sign < 0 else (0.0, CUTTER_REACH_M)
                lo, hi = min(there.s - run, theirs[0] - 0.05), max(there.s + run, theirs[1] + 0.05)  # the whole stretch the two overlap
                cutters[member.id].append(block(other.path, lo, hi, half_gap, far, step=(-sign, (level, square)), stations=meshed[other.id]))
        joints.append(Joint(f"lap:{first.id}:{second.id}", "cross_lap", (first.id, second.id), point(middle), round(angle, 1), tuple(cuts), review))

    notches = {}
    if mode == "notches":
        # A lap that cannot be stepped into one of its members is left uncut in both, and the members'
        # notches fitted again without it, until every remaining lap can be cut in both.
        uncut = set()
        while True:
            dropped = False
            for member_id, mine in wanted.items():
                asked = [(n, index) for n, index in mine if index not in uncut]
                notches[member_id], rejected = fit_notches(by_id[member_id], [n for n, _ in asked])
                for k in rejected:
                    index = asked[k][1]
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

    def near_station(member: Member, at) -> float:
        return min(member.path.stations(0.05), key=lambda st: norm(sub(st.point, at))).s

    def pocket(guest: Member, lo: float, hi: float, lo_plane=None, hi_plane=None):
        """The volume to mill out of a host for the end of `guest`: the guest's own section, a clearance larger."""
        return block(guest.path, lo, hi, guest.width / 2.0 + clearance, guest.depth / 2.0 + clearance, lo_plane=lo_plane, hi_plane=hi_plane, stations=meshed[guest.id])

    floor = min(m.path.anchors[0].co[2] for m in members)
    for m in members:
        start, end = m.path.station_at(0.0), m.path.station_at(m.path.length)
        layer = lap_layer(m)
        if m.start_cut and layer in ("cw", "ccw"):  # a rib's foot in an arch
            hosts = [h for h in by_node[m.nodes[0]] if h.family in ("arch", "inner")]
            if hosts:
                away = {h.id: min(norm(sub(st.point, start.point)) for st in h.path.stations(0.1)) for h in hosts}
                host = min(hosts, key=lambda h: away[h.id])
                flat = math.hypot(start.tangent[0], start.tangent[1])  # in plan: how far from square it meets the arch
                skew = round(angle_between((start.tangent[0] / flat, start.tangent[1] / flat, 0.0), m.start_cut), 1)
                width = m.width / max(math.cos(math.radians(skew)), 0.2) + 2.0 * clearance
                joints.append(
                    Joint(
                        f"housing:{m.id}:{host.id}", "housing", (m.id, host.id), point(start.point), round(90.0 - skew, 1),
                        # an arch shared by two rooms is housed on both faces: its own room's, and the far one
                        (Cut(m.id, "shoulder", 0.0, 0.0, "start", 0.0, skew), Cut(host.id, "housing", round(near_station(host, start.point), 3), round(width, 3), "room" if m.parent.split(".")[0] == host.parent.split(".")[0] else "far", housing_depth, skew)),
                        "meets the arch at a glancing angle" if skew > 55.0 else "",
                    )
                )
                if mode == "milled":  # the pocket's back is the rib's own end plane, a clearance further in
                    back = (tuple(start.point[k] + clearance * m.start_cut[k] for k in range(3)), m.start_cut)
                    taking = {host.id}
                    if norm(sub(host.path.anchors[-1].co, start.point)) < 0.9:  # near the apex the foot may reach into the other half too
                        taking.add(host.id[:-1] + ("R" if host.id.endswith("L") else "L"))
                    for host_id in sorted(taking & set(by_id)):
                        cutters[host_id].append(pocket(m, 0.0, min(0.45, m.path.length / 2.0), lo_plane=back))
        if layer in ("cw", "ccw"):  # a rib's head in a ring
            for host in by_node[m.nodes[-1]]:
                if ".ring." not in host.id:
                    continue
                if host.family == "crown":
                    seat = timber.get("crown", {}).get("seat_m", 0.03)
                    joints.append(Joint(f"seat:{m.id}:{host.id}", "crown_seat", (m.id, host.id), point(end.point), 90.0, (Cut(m.id, "level", round(m.path.length, 3), 0.0, "end", 0.0, 0.0), Cut(host.id, "housing", round(near_station(host, end.point), 3), round(m.width + 2.0 * clearance, 3), "underside", seat, 0.0))))
                    if mode == "milled":
                        square = m.end_cut or end.tangent  # the plane the rib's head is cut to
                        cutters[host.id].append(pocket(m, m.path.length - 0.3, m.path.length, hi_plane=(tuple(end.point[k] + clearance * square[k] for k in range(3)), square)))
                else:
                    at = near_station(host, end.point)
                    angle = angle_between(end.tangent, host.path.station_at(at).tangent)
                    joints.append(Joint(f"housing:{m.id}:{host.id}", "housing", (m.id, host.id), point(end.point), round(angle, 1), (Cut(m.id, "shoulder", round(m.path.length, 3), 0.0, "end", 0.0, round(90.0 - angle, 1)), Cut(host.id, "housing", round(at, 3), round(m.width / max(math.sin(math.radians(angle)), 0.2) + 2.0 * clearance, 3), "side", round(host.width / 2.0, 3), round(90.0 - angle, 1)))))
                    if mode == "milled":
                        cutters[host.id].append(pocket(m, m.path.length - 0.3, m.path.length, hi_plane=(tuple(end.point[k] + clearance * end.tangent[k] for k in range(3)), end.tangent)))
        for tag, st, at, upright in (("", start, 0.0, start.tangent[2]), (":end", end, m.path.length, -end.tangent[2])):
            if abs(st.point[2] - floor) < 1e-6 and upright > 0.9:  # stands on the floor, upright or nearly
                joints.append(Joint(f"base:{m.id}{tag}", "base", (m.id, ""), point(st.point), 90.0, (Cut(m.id, "square", round(at, 3), 0.0, "end" if tag else "start", 0.0, 0.0),)))
        closed = norm(sub(start.point, end.point)) < 1e-6
        pieces = max(2 if closed else 1, math.ceil(m.path.length / longest))
        if pieces > 1:  # splices, each moved to the middle of the widest gap between laps near where it would fall
            taken = sorted(c.at_m for j in joints if j.kind == "cross_lap" for c in j.cuts if c.member == m.id)
            for k in range(pieces if closed else pieces - 1):
                want = m.path.length * (k + (0.5 if closed else 1.0)) / pieces
                gaps = [(b - a, (a + b) / 2.0) for a, b in zip(taken, taken[1:]) if abs((a + b) / 2.0 - want) < m.path.length / (2.0 * pieces)]
                at = max(gaps)[1] if gaps else want
                joints.append(Joint(f"scarf:{m.id}:{k + 1}", "scarf", (m.id, m.id), point(m.path.station_at(at).point), 0.0, (Cut(m.id, "scarf", round(at, 3), round(4.0 * m.depth, 3), "side", round(m.width, 3), 0.0),)))

    for node, group in sorted(by_node.items()):
        if ".top." in node:  # the ribs that arrive together at one point of the crown ring
            group = [m for m in group if lap_layer(m) in ("cw", "ccw")]
        if node.endswith(".mitre") and len(group) > 2:  # a pier that rooms share: every two of its arch legs are mitred together
            pairs = [(a, b) for i, a in enumerate(group) for b in group[i + 1 :]]
        elif len(group) == 2:
            pairs = [tuple(group)]
        else:
            continue
        for a, b in pairs:
            if node.endswith(".apex"):
                end = a.path.station_at(a.path.length)
                slope = round(math.degrees(math.asin(min(1.0, abs(end.tangent[2])))), 1)
                joints.append(Joint(f"mitre:{a.id}:{b.id}", "mitre", (a.id, b.id), point(end.point), round(2.0 * slope, 1), tuple(Cut(m.id, "mitre", round(m.path.length, 3), 0.0, "end", 0.0, slope) for m in (a, b))))
            elif node.endswith(".mitre"):
                foot, height = a.path.station_at(0.0), a.path.anchors[1].co[2] - a.path.anchors[0].co[2]
                lean_a, lean_b = a.path.station_at(a.path.length * 0.5).width_axis, b.path.station_at(b.path.length * 0.5).width_axis
                angle = angle_between(lean_a, lean_b)
                joints.append(Joint(f"pier_mitre:{a.id}:{b.id}", "pier_mitre", (a.id, b.id), point(foot.point), round(180.0 - angle, 1), tuple(Cut(m.id, "mitre", round(height / 2.0, 3), round(height, 3), "side", round(m.depth, 3), round(angle / 2.0, 1)) for m in (a, b))))
                if mode == "milled":
                    # Each leg is cut back to the upright plane that halves the angle between the two arches,
                    # through the point where their planes meet: the pier's own axis.
                    da, db = a.path.station_at(0.0).depth_axis, b.path.station_at(0.0).depth_axis  # each points along its arch, away from the pier
                    fa, fb = a.path.anchors[0].co, b.path.anchors[0].co
                    det = da[0] * db[1] - da[1] * db[0]
                    if abs(det) > 1e-6:
                        t = ((fb[0] - fa[0]) * db[1] - (fb[1] - fa[1]) * db[0]) / det
                        axis = (fa[0] + da[0] * t, fa[1] + da[1] * t, floor - 0.1)
                    else:  # the two arches run straight through the pier: its axis is half-way between their legs
                        axis = ((fa[0] + fb[0]) / 2.0, (fa[1] + fb[1]) / 2.0, floor - 0.1)
                    # With more than two legs at a pier each keeps what lies nearer its own arch than any other's,
                    # which is what cutting it back to the halving plane against every other leg leaves.
                    toward_b = unit((db[0] - da[0], db[1] - da[1], 0.0))
                    along = (-toward_b[1], toward_b[0], 0.0)
                    tall = height + 2.5
                    cutters[a.id].append(box(axis, (toward_b, along, (0.0, 0.0, 1.0)), ((-clearance / 2.0, 0.9), (-0.9, 0.9), (0.0, tall))))
                    cutters[b.id].append(box(axis, (toward_b, along, (0.0, 0.0, 1.0)), ((-0.9, clearance / 2.0), (-0.9, 0.9), (0.0, tall))))
            elif ".top." in node and {lap_layer(a), lap_layer(b)} == {"cw", "ccw"}:
                joints.append(Joint(f"pair:{a.id}:{b.id}", "paired_heads", (a.id, b.id), point(a.path.station_at(a.path.length).point), round(angle_between(a.path.station_at(a.path.length).tangent, b.path.station_at(b.path.length).tangent), 1), ()))
    return joints, notches, dict(cutters)


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
    def third(joint: Joint) -> bool:
        return joint.kind == "cross_lap" and abs(joint.cuts[0].depth_m - joint.cuts[1].depth_m) > 0.25 * (joint.cuts[0].depth_m + joint.cuts[1].depth_m)

    return {
        "joints": len(joints),
        "by_kind": dict(sorted(kinds.items())),
        "third_depth_laps": sum(1 for j in joints if third(j)),
        "to_review": sum(1 for j in joints if j.review),
        "laps_left_uncut": sum(1 for j in joints if "not cut in the model" in j.review),
        "laps_whose_walls_must_follow_a_turn": sum(1 for j in joints if "must follow the turn" in j.review and "not cut in the model" not in j.review),
    }
