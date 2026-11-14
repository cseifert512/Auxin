"""Training lines: thin steel cables held off the timber on standoffs, for plants to climb.

A line belongs to one member and has no direction of its own. It runs along that member's
centreline, a set gap off one face of its section, so it has the member's curve. It is part of
the building: it is derived from the members and the joints, and regenerates with them.

    design["timber"]["training_lines"]
        carry                grounded | all | none. `grounded` is every member of `families` that stands
                             on the floor, so that a plant has one timber from the soil upward
        families             the families that may carry a line
        members              optional: IDs of members that carry one whatever `carry` says
        without              optional: IDs of members that carry none
        face                 outer | inner: the face of the section the line stands off. Outer is the
                             roof's upper side (the back of an arch), inner the room's
        gap_m                from that face to the middle of the cable
        cable_diameter_m
        standoff_spacing_m   the furthest apart two standoffs stand
        standoff_sag_m       a cable is straight from one standoff to the next. On a bend they are set
                             closer, so that it strays no further than this from the member's own curve
        standoff_diameter_m  the standoff, and
        hole_depth_m         the hole drilled in the member for it
        joint_clear_m        a standoff keeps this far from a housing, and from a lap cut in the face it is fixed to
        clear_m              a line keeps this far from every other member; where it cannot, it is cut back
        foot_clear_m         how far above the floor a line starts on a member that stands on it
        end_clear_m          how far short of any other end of its member a line stops
        min_length_m         a stretch of line shorter than this is left out

A design without that block has no lines.

Setting out. The line's course is the member's centreline moved off the chosen face by the
gap. Standoffs are set out along it from the member's start: each as far from the last as the
spacing and the sag allow. One is kept out of a housing, and out of a lap cut in the face it is
fixed to, where that face belongs to the other member; only where a bend leaves no other place
does one stand in such a joint, and the schedule says so. The cable is then the straight runs
between standoff heads, which is what a taut cable is. Where the course comes within `clear_m`
of another member the line stops and starts again beyond; the schedule says where and why.

The lattice is flush, so a line on a lattice member passes over every member that crosses it
by the gap. Two lines whose members cross therefore cross each other at the same height: they
touch there, and `check_lines` counts those places. Which cable goes over is left to the site.

Not modelled: end fittings and tensioners, the cable's own sag under a plant's weight, and
what a plant does. Pure Python (no bpy). Every dimension is a provisional concept value.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from .centreline import add, dot, mul, norm, sub
from .joints import Cut, Joint, find_joints
from .member import Member
from .timber import LATTICE, build_design_timber
from .topology import DesignError

DEFAULTS = {
    "carry": "grounded",
    "families": ["rib", "fill", "fine", "hoop"],
    "members": [],
    "without": [],
    "face": "outer",
    "gap_m": 0.075,
    "cable_diameter_m": 0.004,
    "standoff_spacing_m": 0.9,
    "standoff_sag_m": 0.012,
    "standoff_diameter_m": 0.01,
    "hole_depth_m": 0.04,
    "joint_clear_m": 0.03,
    "clear_m": 0.025,
    "foot_clear_m": 0.1,
    "end_clear_m": 0.3,
    "min_length_m": 1.0,
}
CARRY = ("grounded", "all", "none")
FACES = {"outer": -1.0, "inner": 1.0}  # sections lie with +depth toward the room (see bower/joints.py)
EXTERIOR = "exterior"  # the side of a section's width that looks away from its room: for a feeder up an arch leg (bower/ground.py)
FAMILIES = LATTICE + ("arch", "inner")  # a crown ring's depth runs up the roof's section, so it has no outer face
STEP_M = 0.05  # how finely a member is sampled: for clearance, and for where a standoff may stand
REACH_M = 0.1  # clearances are measured at least this far out; anything further is reported as the reach
MIN_SPACING_M = 0.15  # two standoffs of one line are never closer than this


@dataclass(frozen=True)
class Standoff:
    at_m: float  # station along the member, from its start
    foot: tuple  # on the member's face, where it is fixed
    head: tuple  # on the cable
    note: str = ""  # set where it has had to stand in a joint


@dataclass(frozen=True)
class Line:
    id: str
    member: str
    face: str
    gap_m: float
    standoffs: tuple  # in order along the member; the cable runs straight from head to head
    closed: bool = False  # a line right round a ring: the cable runs on from the last standoff to the first
    clearance_m: float = REACH_M  # the nearest any other member comes to the line's course,
    nearest: str = ""  # and that member; none named, and the distance looked out to, where nothing is near
    stray_m: float = 0.0  # the furthest the cable strays from the member's own curve between two standoffs
    review: str = ""
    kind: str = "training"  # or "feeder": a plant's way from its root zone up to the training lines (bower/ground.py)

    @property
    def points(self) -> tuple:
        return tuple(s.head for s in self.standoffs)

    @property
    def from_m(self) -> float:
        return self.standoffs[0].at_m

    @property
    def to_m(self) -> float:
        return self.standoffs[-1].at_m

    @property
    def length_m(self) -> float:
        points = self.points + (self.points[:1] if self.closed else ())
        return sum(norm(sub(b, a)) for a, b in zip(points, points[1:]))


def settings(timber: dict) -> dict | None:
    """A design's training-line settings with every default filled in, or None if it asks for no lines."""
    own = timber.get("training_lines")
    if own is None:
        return None
    unknown = sorted(set(own) - set(DEFAULTS) - {"note"})
    if unknown:
        raise DesignError(f"timber.training_lines has no setting called {', '.join(unknown)}")
    cfg = {**DEFAULTS, **{k: v for k, v in own.items() if k != "note"}}
    if cfg["carry"] not in CARRY:
        raise DesignError(f"timber.training_lines.carry {cfg['carry']!r} is not one of {', '.join(CARRY)}")
    if cfg["face"] not in FACES:
        raise DesignError(f"timber.training_lines.face {cfg['face']!r} is not one of {', '.join(FACES)}")
    odd = sorted(set(cfg["families"]) - set(FAMILIES))
    if odd:
        raise DesignError(f"timber.training_lines.families: {', '.join(odd)} cannot carry a line; the families that can are {', '.join(FAMILIES)}")
    for key in ("gap_m", "cable_diameter_m", "standoff_spacing_m", "standoff_sag_m", "standoff_diameter_m", "hole_depth_m"):
        if not cfg[key] > 0.0:
            raise DesignError(f"timber.training_lines.{key} must be more than 0")
    if cfg["standoff_spacing_m"] < 2.0 * MIN_SPACING_M:
        raise DesignError(f"timber.training_lines.standoff_spacing_m must be at least {2.0 * MIN_SPACING_M} m")
    if cfg["clear_m"] >= cfg["gap_m"]:
        raise DesignError("timber.training_lines.clear_m must be less than gap_m, or no line could stand off its own member")
    return cfg


# --- which members, and what is near them ---------------------------------------------------------


def _floor(members: list[Member]) -> float:
    return min(m.path.anchors[0].co[2] for m in members)


def on_floor(member: Member, floor: float) -> tuple[bool, bool]:
    """Whether the member's start, and its end, stands on the floor as a leg (as bower/joints.py finds a base)."""
    start, end = member.path.station_at(0.0), member.path.station_at(member.path.length)
    return (abs(start.point[2] - floor) < 1e-6 and start.tangent[2] > 0.9, abs(end.point[2] - floor) < 1e-6 and -end.tangent[2] > 0.9)


def _closed(member: Member) -> bool:
    return norm(sub(member.path.anchors[0].co, member.path.anchors[-1].co)) < 1e-6


def carriers(members: list[Member], cfg: dict) -> list[Member]:
    """The members that carry a line, in the order they were built."""
    floor, families = _floor(members), set(cfg["families"])
    named, without = set(cfg["members"]), set(cfg["without"])
    chosen = []
    for m in members:
        if m.id in without:
            continue
        if m.id in named:
            if m.family not in FAMILIES:
                raise DesignError(f"timber.training_lines.members: {m.id} is a {m.family}, which cannot carry a line")
            chosen.append(m)
        elif m.family in families and (cfg["carry"] == "all" or (cfg["carry"] == "grounded" and any(on_floor(m, floor)))):
            chosen.append(m)
    return chosen


class Bodies:
    """Every member as a chain of short boxes, one at each sampled station, found by where they are."""

    def __init__(self, members: list[Member], within: float = REACH_M, step: float = STEP_M):
        self.within, self.half = within, step / 2.0 + 0.002
        reaches = {m.id: math.sqrt((m.width / 2.0) ** 2 + (m.depth / 2.0) ** 2 + self.half**2) for m in members}
        self.cell = max(reaches.values()) + within + 0.01  # so that a box within reach of a point is in its cell or the next
        self.grid = defaultdict(list)
        for m in members:
            for st in m.path.stations(step):
                self.grid[self._key(st.point)].append((m, st, reaches[m.id]))

    def _key(self, p) -> tuple:
        return (math.floor(p[0] / self.cell), math.floor(p[1] / self.cell), math.floor(p[2] / self.cell))

    def clearance(self, p, skip: str = "", only: str = "") -> tuple[float, str]:
        """How far `p` is from the nearest member's body, and which member that is: out to
        `self.within`, beyond which it returns (`self.within`, ""). Negative inside a body.
        `skip` leaves one member out; `only` measures to that member alone."""
        best, who = self.within, ""
        gx, gy, gz = self._key(p)
        for cx in (gx - 1, gx, gx + 1):
            for cy in (gy - 1, gy, gy + 1):
                for cz in (gz - 1, gz, gz + 1):
                    for m, st, reach in self.grid.get((cx, cy, cz), ()):
                        if m.id == skip or (only and m.id != only):
                            continue
                        v = (p[0] - st.point[0], p[1] - st.point[1], p[2] - st.point[2])
                        if v[0] * v[0] + v[1] * v[1] + v[2] * v[2] > (reach + best) ** 2:
                            continue
                        x = abs(dot(v, st.width_axis)) - m.width / 2.0
                        y = abs(dot(v, st.depth_axis)) - m.depth / 2.0
                        z = abs(dot(v, st.tangent)) - self.half
                        outside = math.sqrt(max(x, 0.0) ** 2 + max(y, 0.0) ** 2 + max(z, 0.0) ** 2)
                        d = outside if outside > 0.0 else max(x, y, z)
                        if d < best:
                            best, who = d, m.id
        return best, who


# --- setting one line out -------------------------------------------------------------------------


def _stray(points: list, i0: int, i1: int) -> float:
    """How far the sampled course between two of its points strays from the straight line between them."""
    a, ab = points[i0], sub(points[i1], points[i0])
    l2, worst = dot(ab, ab), 0.0
    for i in range(i0 + 1, i1):
        v = sub(points[i], a)
        t = min(1.0, max(0.0, dot(v, ab) / l2)) if l2 > 0.0 else 0.0
        worst = max(worst, norm(sub(v, mul(ab, t))))
    return worst


def _set_out(ss: list, course: list, rank: list, lo: int, hi: int, widest: float, sag: float) -> list[int]:
    """The samples, from `lo` to `hi`, at which the standoffs of one stretch of line stand.

    `rank` says how good a place each sample is for a standoff: 2 clear of every joint, 1 beside
    one, 0 in one. Set out from the first good place: each standoff is the furthest sample that
    is no more than `widest` from the last and leaves the cable within `sag` of the course
    between them, a better place being taken before a further one. Where a bend is too tight
    for that at the closest two standoffs may stand, they stand that close.
    """
    best = max(rank[lo : hi + 1])
    spots = [i for i in range(lo, hi + 1) if rank[i] == best]
    first, last = spots[0], spots[-1]
    if last - first < 1:
        return []
    chosen = [first]
    while chosen[-1] != last:
        here = chosen[-1]
        apart = [i for i in range(here + 1, last + 1) if ss[i] - ss[here] >= MIN_SPACING_M - 1e-9] or [last]
        reach = [i for i in apart if ss[i] - ss[here] <= widest + 1e-9 and _stray(course, here, i) <= sag]
        if reach:
            finest = max(rank[i] for i in reach)
            chosen.append(max(i for i in reach if rank[i] == finest))
        else:
            chosen.append(apart[0])
    if len(chosen) > 2 and ss[chosen[-1]] - ss[chosen[-2]] < MIN_SPACING_M:
        # The one before the last would stand too close to it. It is moved back to where both of the
        # runs it parts are good, as near half-way between its neighbours as it can stand.
        before, end = chosen[-3], chosen[-1]
        fits = [i for i in range(before + 1, end) if min(ss[i] - ss[before], ss[end] - ss[i]) >= MIN_SPACING_M - 1e-9 and max(_stray(course, before, i), _stray(course, i, end)) <= sag]
        if fits:
            finest = max(rank[i] for i in fits)
            chosen[-2] = min((i for i in fits if rank[i] == finest), key=lambda i: abs(ss[i] - 0.5 * (ss[before] + ss[end])))
        elif _stray(course, before, end) <= sag:
            del chosen[-2]
    return chosen


def _off(member: Member, st, face: str, centre) -> tuple:
    """The unit direction a line stands off a member's section at a station, and how far the face is from the centreline."""
    if face == EXTERIOR:
        away = dot(st.width_axis, (st.point[0] - centre[0], st.point[1] - centre[1], 0.0))
        return mul(st.width_axis, 1.0 if away > 0.0 else -1.0), member.width / 2.0
    return mul(st.depth_axis, FACES[face]), member.depth / 2.0


def _line(member: Member, cfg: dict, bodies: Bodies, cuts: list, floor: float, face: str = "", span=None, centre=None, tag: str = "line", kind: str = "training") -> list[Line]:
    """The line of one member: usually one, more where it has had to be cut back, none where there is no room.

    `cuts` are the cuts in this member, each with the member it is cut for. `face` and `span`
    (two stations) set a face and a stretch other than the settings give, as a feeder needs;
    `centre` is the plan point an exterior face looks away from.
    """
    face = face or cfg["face"]
    gap, sag, clear = cfg["gap_m"], cfg["standoff_sag_m"], cfg["clear_m"]
    length, closed = member.path.length, _closed(member)
    # where the line may run at all: clear of the member's ends
    grounded = (False, False) if closed else on_floor(member, floor)
    lo = 0.0 if closed else cfg["foot_clear_m"] if grounded[0] else cfg["end_clear_m"]
    hi = length if closed else length - (cfg["foot_clear_m"] if grounded[1] else cfg["end_clear_m"])
    if span is not None:
        lo, hi = max(lo, span[0]), min(hi, span[1])
    if hi - lo < cfg["min_length_m"]:
        return []
    stations = [st for st in member.path.stations(STEP_M) if closed or lo + 1e-3 < st.s < hi - 1e-3]
    if not closed:
        stations = [member.path.station_at(lo)] + stations + [member.path.station_at(hi)]
    ss = [st.s for st in stations]
    offs = [_off(member, st, face, centre) for st in stations]
    course = [add(st.point, mul(axis, half + gap)) for st, (axis, half) in zip(stations, offs)]
    # and clear of every other member
    near = [bodies.clearance(p, skip=member.id) for p in course]
    free = [c >= clear for c, _ in near]
    # A standoff stands best clear of every joint. It cannot stand in a housing, or in a lap cut in
    # the face it is fixed to, where that face is another member's; it may stand beside one.
    joints = [(c.at_m - c.length_m / 2.0, c.at_m + c.length_m / 2.0, other) for c, other in cuts if c.operation == "housing" or (c.operation == "lap" and c.face == face)]
    margin = cfg["joint_clear_m"]

    def place(s: float) -> tuple[int, str]:
        for a, b, other in joints:
            if a < s < b:
                return 0, other
        return (1, "") if any(a - margin < s < b + margin for a, b, _ in joints) else (2, "")

    placed = [place(s) for s in ss]
    rank = [r for r, _ in placed]

    stretches, start = [], None
    for i, ok in enumerate(free + [False]):
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            stretches.append((start, i - 1))
            start = None
    whole = closed and stretches == [(0, len(ss) - 1)]

    lines = []
    for lo_i, hi_i in stretches:
        chosen = _set_out(ss, course, rank, lo_i, hi_i, cfg["standoff_spacing_m"], sag)
        if len(chosen) < 2 or ss[chosen[-1]] - ss[chosen[0]] < cfg["min_length_m"]:
            continue
        notes = []
        if kind == "training" and not whole and (ss[chosen[0]] - lo > 0.3 or hi - ss[chosen[-1]] > 0.3):
            blockers = sorted({w for c, w in near if w and c < clear})
            notes.append(f"cut back: it runs from {ss[chosen[0]]:.2f} to {ss[chosen[-1]]:.2f} m of a member {length:.2f} m long" + (f", to keep clear of {', '.join(blockers)}" if blockers else ""))
        # The cable is straight between standoffs. Where it strays from the course by more than the
        # sag allows, or the course itself passes something closely, the cable itself is measured.
        strays = [_stray(course, a, b) for a, b in zip(chosen, chosen[1:])]
        tight = []
        for (a, b), stray in zip(zip(chosen, chosen[1:]), strays):
            if stray <= sag and min(near[i][0] for i in range(a, b + 1)) - stray >= clear:
                continue
            count = max(1, math.ceil(norm(sub(course[b], course[a])) / 0.02))
            for i in range(count + 1):
                q = add(course[a], mul(sub(course[b], course[a]), i / count))
                for d, who in (bodies.clearance(q, skip=member.id), bodies.clearance(q, only=member.id)):
                    if d < clear:
                        tight.append((d, who, ss[a], ss[b]))
        if tight:
            d, who, a, b = min(tight)
            notes.append(f"the cable comes within {max(d, 0.0) * 1000:.0f} mm of {who} between its standoffs at {a:.2f} and {b:.2f} m")
        in_joint = [i for i in chosen if rank[i] == 0]
        if in_joint:
            notes.append(f"{len(in_joint)} of its standoffs stand where the face is another member's")
        c, who = min((near[i] for i in range(chosen[0], chosen[-1] + 1)), key=lambda pair: pair[0])
        if whole and chosen[0] == 0 and chosen[-1] == len(ss) - 1:
            chosen = chosen[:-1]  # right round a ring: the last standoff is the first again
        standoffs = tuple(
            Standoff(round(ss[i], 4), add(stations[i].point, mul(offs[i][0], offs[i][1])), course[i], f"in the joint with {placed[i][1]}: the face here is that member's" if rank[i] == 0 else "")
            for i in chosen
        )
        line_id = f"{member.id}.{tag}" if not lines else f"{member.id}.{tag}.{len(lines) + 1}"
        lines.append(Line(line_id, member.id, face, gap, standoffs, whole, round(c, 4), who, round(max(strays), 4), "; ".join(notes), kind))
    return lines


def training_lines(members: list[Member], timber: dict, joints=()) -> list[Line]:
    """The training lines of a set of members that were built together, in the members' order.

    `joints` are those members' joints (bower/joints.py): standoffs are kept out of their laps
    and housings. Without them the lines are the same but for where the standoffs stand.
    """
    cfg = settings(timber)
    if cfg is None:
        return []
    chosen = carriers(members, cfg)
    if not chosen:
        return []
    bodies, floor = Bodies(members, max(REACH_M, cfg["gap_m"] + cfg["standoff_sag_m"] + 0.02)), _floor(members)
    cuts = defaultdict(list)
    for joint in joints:
        for cut in joint.cuts:
            cuts[cut.member].append((cut, next((m for m in joint.members if m and m != cut.member), "")))
    return [line for m in chosen for line in _line(m, cfg, bodies, cuts[m.id], floor)]


def design_lines(design: dict, groups=None) -> list[dict]:
    """The lines of a whole design, for each group of rooms that are joined to each other:
    {"rooms", "members", "room_of", "joints", "lines", "ground"}. An empty list if the design
    asks for no lines and sets out no ground.

    Where the design sets out its ground (bower/ground.py), a group's lines include the feeders
    that take plants from their root zones up to the training lines, and "ground" holds the
    root zones, footings and hand-overs; otherwise "ground" is None.
    """
    from . import ground  # ground sets its feeders out with this module's own tools

    cfg, grounded = settings(design.get("timber", {})), ground.settings(design) is not None
    if cfg is None and not grounded:
        return []
    groups = build_design_timber(design) if groups is None else groups
    known = {m.id for group in groups for m in group["members"]}
    lost = sorted((set(cfg["members"]) | set(cfg["without"])) - known) if cfg else []
    if lost:
        raise DesignError(f"timber.training_lines names members the design does not have: {', '.join(lost)}")
    out = []
    for group in groups:
        joints = find_joints(group["members"], design["timber"])[0]
        lines = training_lines(group["members"], design["timber"], joints)
        laid = ground.lay(design, group, joints, lines) if grounded else None
        out.append({"rooms": group["rooms"], "members": group["members"], "room_of": group["room_of"], "joints": joints, "lines": lines + (laid["feeders"] if laid else []), "ground": laid})
    return out


# --- checking, and the schedules ------------------------------------------------------------------


def _between(a, b, p, q) -> float:
    """The shortest distance between the segments a-b and p-q."""
    u, v, w = sub(b, a), sub(q, p), sub(a, p)
    uu, uv, vv, uw, vw = dot(u, u), dot(u, v), dot(v, v), dot(u, w), dot(v, w)
    det = uu * vv - uv * uv
    s = min(1.0, max(0.0, (uv * vw - vv * uw) / det)) if det > 1e-12 else 0.0
    t = min(1.0, max(0.0, (uv * s + vw) / vv)) if vv > 1e-12 else 0.0
    s = min(1.0, max(0.0, (uv * t - uw) / uu)) if uu > 1e-12 else 0.0
    return norm(sub(add(a, mul(u, s)), add(p, mul(v, t))))


def check_lines(lines: list[Line], members: list[Member], timber: dict, step: float = 0.03) -> dict:
    """Measure the lines as they would be strung: every cable as straight runs between its standoffs.

    Returns how near any cable comes to a member that is not its own, how far every cable stands
    from its own member (the gap, less what it strays on a bend), which members that should carry
    a line have none or only part of one, and how many pairs of cables cross (they are strung at
    one height, so two that cross pass within twice the sag of each other).
    """
    cfg = settings(timber) or dict(DEFAULTS, carry="none")
    by_id = {m.id: m for m in members}
    bodies = Bodies(members, max(REACH_M, cfg["gap_m"] + 2.0 * cfg["standoff_sag_m"] + 0.02))
    report = {"lines": len(lines), "members_with_a_line": len({line.member for line in lines}), "length_m": round(sum(line.length_m for line in lines), 1), "standoffs": sum(len(line.standoffs) for line in lines)}
    nearest, own_lo, own_hi = (bodies.within, "", ""), bodies.within, 0.0
    runs = []  # (line index, a, b) for every straight run of cable
    for k, line in enumerate(lines):
        points = line.points + (line.points[:1] if line.closed else ())
        for a, b in zip(points, points[1:]):
            runs.append((k, a, b))
            count = max(1, math.ceil(norm(sub(b, a)) / step))
            for i in range(count + 1):
                p = add(a, mul(sub(b, a), i / count))
                c, who = bodies.clearance(p, skip=line.member)
                if c < nearest[0]:
                    nearest = (c, line.id, who)
                own = bodies.clearance(p, only=line.member)[0]
                own_lo, own_hi = min(own_lo, own), max(own_hi, own)
    report["nearest_other_member_m"] = {"clear_m": round(nearest[0], 4), "line": nearest[1], "member": nearest[2]} if nearest[1] else None
    report["clear_of_other_members"] = nearest[0] >= cfg["clear_m"] - 1e-6
    report["gap_to_own_member_m"] = [round(own_lo, 4), round(own_hi, 4)] if lines else None
    # members that should carry a line and have none, or less than all of one
    floor = _floor(members)
    have = {line.member for line in lines if line.kind == "training"}
    report["feeders"] = sum(1 for line in lines if line.kind == "feeder")
    report["carriers_without_a_line"] = [m.id for m in carriers(members, cfg) if m.id not in have]
    report["lines_cut_back"] = sorted(line.id for line in lines if line.review.startswith("cut back"))
    starts = [line.standoffs[0].head[2] - floor for line in lines if line.kind == "training" and any(on_floor(by_id[line.member], floor))]
    report["lines_from_the_floor"] = sum(1 for z in starts if z <= cfg["foot_clear_m"] + 1e-3)
    report["highest_start_above_floor_m"] = round(max(starts), 3) if starts else None
    # where two cables cross: found among runs that share a neighbourhood
    cell, grid = 0.25, defaultdict(set)
    for r, (k, a, b) in enumerate(runs):
        count = max(1, math.ceil(norm(sub(b, a)) / 0.1))
        for i in range(count + 1):
            p = add(a, mul(sub(b, a), i / count))
            grid[(math.floor(p[0] / cell), math.floor(p[1] / cell), math.floor(p[2] / cell))].add(r)
    pairs = set()
    for (gx, gy, gz), here in grid.items():
        around = set()
        for cx in (gx - 1, gx, gx + 1):
            for cy in (gy - 1, gy, gy + 1):
                for cz in (gz - 1, gz, gz + 1):
                    around |= grid.get((cx, cy, cz), set())
        pairs |= {(r, o) for r in here for o in around if r < o and runs[r][0] != runs[o][0]}
    touching = sorted({(lines[runs[r][0]].id, lines[runs[o][0]].id) for r, o in pairs if _between(*runs[r][1:], *runs[o][1:]) < 2.0 * cfg["standoff_sag_m"] + cfg["cable_diameter_m"]})
    report["cables_cross_each_other"] = len(touching)
    report["standoffs_in_a_joint"] = sum(1 for line in lines for s in line.standoffs if s.note)
    report["stray_from_curve_m"] = round(max((line.stray_m for line in lines), default=0.0), 4)
    report["to_review"] = sum(1 for line in lines if line.review)
    return report


def standoff_joints(lines: list[Line], timber: dict) -> list[Joint]:
    """Every standoff as one more operation on its member, for the joint schedule: a hole drilled
    square into the face the line stands off, at a station along the member's own centreline."""
    cfg = settings(timber) or DEFAULTS
    joints = []
    for line in lines:
        for k, standoff in enumerate(line.standoffs, start=1):
            cut = Cut(line.member, "drill", round(standoff.at_m, 3), cfg["standoff_diameter_m"], line.face, cfg["hole_depth_m"], 0.0)
            joints.append(Joint(f"standoff:{line.id}:{k:02d}", "standoff", (line.member, ""), tuple(round(c, 3) for c in standoff.foot), 90.0, (cut,), standoff.note))
    return joints


def line_rows(lines: list[Line], members: list[Member], piers: dict | None = None) -> list[dict]:
    """One row per line for the line schedule. `piers` is {pier ID: plan position}: given it, an
    end of a line that starts from the floor names the pier it stands at."""
    by_id, floor = {m.id: m for m in members}, _floor(members) if members else 0.0
    rows = []
    for line in lines:
        m = by_id[line.member]
        grounded = (False, False) if line.closed else on_floor(m, floor)

        def pier(end: int) -> str:
            if not piers or not grounded[end]:
                return ""
            p = line.standoffs[-end].head
            return min(piers, key=lambda pid: math.hypot(piers[pid][0] - p[0], piers[pid][1] - p[1]))

        first, last = line.standoffs[0].head, line.standoffs[-1].head
        rows.append(
            {
                "id": line.id,
                "kind": line.kind,
                "member": line.member,
                "family": m.family,
                "face": line.face,
                "gap_m": line.gap_m,
                "from_m": round(line.from_m, 3),
                "to_m": round(line.to_m, 3),
                "member_length_m": round(m.path.length, 3),
                "cable_length_m": round(line.length_m, 3),
                "closed": "yes" if line.closed else "",
                "standoffs": len(line.standoffs),
                "start_x_m": round(first[0], 3),
                "start_y_m": round(first[1], 3),
                "start_z_m": round(first[2], 3),
                "end_x_m": round(last[0], 3),
                "end_y_m": round(last[1], 3),
                "end_z_m": round(last[2], 3),
                "start_pier": pier(0),
                "end_pier": pier(1),
                "nearest_other_member": line.nearest,
                "clear_of_it_m": line.clearance_m if line.nearest else f"over {line.clearance_m}",
                "stray_from_curve_m": line.stray_m,
                "review": line.review,
            }
        )
    return rows
