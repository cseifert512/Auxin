"""Roots for one climber in the inhabited room: a drawing rule, not a model.

This is a sketch of a root system from stated rules; not simulated, not
sourced, not a horticultural claim. The plant simulator does not grow roots.
The owner wants the cut-away section to show the plant below ground too,
growing over the same ten years as the shoots above it. Every number below is
an authored assumption chosen so the drawing reads like a woody climber
(wisteria was the picture in mind): a few strong, far-running, shallow
laterals, some sinkers, fine roots near the surface. None of it is evidence
about any plant, and nothing about the building should be decided from it.

What the caller gives (and so what is not authored here): where the plant
stands, how far its longest lateral runs by the last day (`reach_m`), the
stem's radius at the ground on the last day, the ground around the pier
(`Soil`) and the steel and timber it must not pass through (`obstacles`).

    system(seed, at, reach_m, base_radius_m, soil, obstacles, last_day) -> dict
    on_day(system, day, last_day) -> list

Pure Python, standard library only. The same seed and arguments always give
the same system, and an earlier day is always a prefix of a later one.
"""
import math
import random

# --- time (all authored assumptions) ---------------------------------------
PLANTED_DAY = 11            # authored: nothing outside the root ball exists before this day
TEASED_M = 0.12             # authored: length of each main root teased out of the ball at planting
GROWTH_POWER = 1.6          # authored: born = start + span * (d / L) ** this; early growth is fast
RADIUS_POWER = 1.35         # authored: same thickening curve as the simulator's stems

# --- thickness ---------------------------------------------------------------
TIP_RADIUS_M = 0.0008       # authored: radius of a growing root tip
MAIN_RADIUS_FRAC = 0.45     # authored: main lateral base radius as a share of the stem's
SECOND_RADIUS_FRAC = 0.5    # authored: second order starts at this share of its parent at the joint
FEEDER_RADIUS_FRAC = 0.4    # authored: feeders start at this share of their parent at the joint
SINKER_RADIUS_FRAC = 0.35   # authored: sinker base radius as a share of the stem's
TAPER_POWER = 1.2           # authored: final radius = tip + (base - tip) * (1 - d / L) ** this

# --- the root ball -----------------------------------------------------------
BALL_RADIUS_M = 0.15        # authored: ball 0.3 m across
BALL_CENTRE_DEPTH_M = 0.15  # authored: ball centre below the surface (its top at the surface)

# --- main laterals -----------------------------------------------------------
MAIN_COUNT = (5, 8)         # authored: how many leave the ball
MAIN_JITTER = 0.3           # authored: heading jitter as a share of the even spacing
MAIN_LENGTH_FRAC = (0.45, 1.0)  # authored: length as a share of reach_m (one is always 1.0)
LATERAL_DEPTH_M = (0.10, 0.35)  # authored: depth band of laterals in the loosened ring
BASE_DEPTH_M = (0.14, 0.28)     # authored: each lateral's mean depth
WAVE_AMP_M = (0.02, 0.06)   # authored: gentle undulation in depth
WAVE_LENGTH_M = (0.7, 1.6)  # authored: wavelength of that undulation along the root
YAW_NOISE_RAD = 0.03        # authored: random change of heading per step
YAW_DAMP = 0.85             # authored: how long a turn persists (slow wander)
YAW_RETURN = 0.04           # authored: pull back toward the root's first heading per step
MAX_DZ_M = 0.025            # authored: most a lateral rises or falls per step
STEP_M = 0.06               # authored: plan spacing of points along a root

# --- second order and feeders -----------------------------------------------
SECOND_COUNT = (2, 5)       # authored: second-order laterals per main lateral
SECOND_ANGLE_DEG = (35, 70)  # authored: branching angle from the parent
SECOND_LENGTH_FRAC = (0.25, 0.5)  # authored: length as a share of the parent's
SECOND_ATTACH_FRAC = (0.2, 0.85)  # authored: where along the parent they leave
FEEDER_LENGTH_M = (0.08, 0.3)     # authored: feeder length
FEEDER_SPACING_M = 0.08     # authored: one chance of a feeder per this length of second order
FEEDER_SHALLOW_M = 0.25     # authored: feeders are densest above this depth
FEEDER_P_SHALLOW = 0.8      # authored: chance of a feeder at a shallow spot
FEEDER_P_DEEP = 0.2         # authored: chance of a feeder at a deeper spot
FEEDER_ANGLE_DEG = (40, 90)  # authored: feeder branching angle
FEEDER_RISE_M = 0.04        # authored: feeders sit this much shallower than their parent

# --- sinkers -----------------------------------------------------------------
SINKER_COUNT = (1, 3)       # authored: how many go down from near the ball
SINKER_DEPTH_M = (0.8, 1.3)  # authored: how deep they end, below the surface
SINKER_BELOW_LOOSENED_M = 0.2  # authored: they end at least this far under the loosened soil
SINKER_PITCH_DEG = (65, 82)  # authored: steepness below horizontal
SINKER_START_DEPTH_M = 0.25  # authored: they leave the ball this far down
SINKER_WANDER_RAD = 0.08    # authored: heading wander per step
SINKER_MAX_STEPS = 220      # authored: give up after this many steps (e.g. stuck over a plate)

# --- ground and obstacles ----------------------------------------------------
OUTSIDE_EXTRA_DEPTH_M = 0.12  # authored: outside the planted ring roots run this much deeper
FLOOR_MARGIN_M = 0.04       # authored: under the floor roots aim this far below floor_base_m
MIN_COVER_M = 0.03          # authored: never closer to the surface than this
LOOKAHEAD_M = 0.3           # authored: a root anticipates the ground this far ahead
MIN_CLEAR_M = 0.015         # authored: clear gap to steel and timber (plus the root's radius)
PILE_LENGTH_M = 2.5         # given: piles go this far down from their top
AVOID_TURNS_RAD = (0.35, 0.7, 1.05, 1.4, 1.75, 2.1)  # authored: turns tried to get round things


class Soil:
    """The ground around one pier, as given by the caller."""

    def __init__(self, surface, loosened_depth_m=0.6, ring=(4.55, 9.0), floor_base_m=0.2):
        self._surface = surface
        self.loosened_depth_m = loosened_depth_m
        self.ring = tuple(ring)
        self.floor_base_m = floor_base_m

    def surface(self, x, y):
        return self._surface(x, y)


def _near_polygon(x, y, outline, clear):
    n, sign, inside = len(outline), 0, True
    for i in range(n):
        (ax, ay), (bx, by) = outline[i], outline[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        c = ex * (y - ay) - ey * (x - ax)
        s = 1 if c > 0 else -1 if c < 0 else 0
        if s and sign and s != sign:
            inside = False
        sign = sign or s
        L2 = ex * ex + ey * ey or 1e-12
        t = max(0.0, min(1.0, ((x - ax) * ex + (y - ay) * ey) / L2))
        if math.hypot(ax + t * ex - x, ay + t * ey - y) <= clear:
            return True
    return inside


def inside_obstacle(p, obstacles, clear):
    """True if point p is within `clear` of any obstacle."""
    x, y, z = p
    for ob in obstacles:
        k = ob["kind"]
        if k == "post":
            ax, ay = ob["at"]
            h = ob["half_m"] + clear
            if abs(x - ax) <= h and abs(y - ay) <= h and ob["bottom"] - clear <= z <= ob["top"] + clear:
                return True
        elif k == "pile":
            ax, ay = ob["at"]
            r = ob["radius_m"] + clear
            if (x - ax) ** 2 + (y - ay) ** 2 <= r * r and ob["top"] - PILE_LENGTH_M - clear <= z <= ob["top"] + clear:
                return True
        elif k == "plate":
            if ob["bottom"] - clear <= z <= ob["top"] + clear and _near_polygon(x, y, ob["outline"], clear):
                return True
    return False


class _Ground:
    def __init__(self, soil, at, reach_m, obstacles):
        self.soil, self.at, self.reach, self.obstacles = soil, at, reach_m, obstacles

    def depth_rule(self, x, y, d):
        r_in, r_out = self.soil.ring
        r = math.hypot(x, y)
        if r < r_in:
            return max(d + OUTSIDE_EXTRA_DEPTH_M, self.soil.floor_base_m + FLOOR_MARGIN_M)
        if r > r_out:
            return d + OUTSIDE_EXTRA_DEPTH_M
        return d

    def cap(self, x, y, z):
        top = self.soil.surface(x, y) - MIN_COVER_M
        if math.hypot(x, y) < self.soil.ring[0]:
            top = min(top, self.soil.surface(x, y) - self.soil.floor_base_m)
        return min(z, top)

    def ok(self, a, b, clear):
        if math.hypot(b[0] - self.at[0], b[1] - self.at[1]) > self.reach:
            return False
        for t in (0.25, 0.5, 0.75, 1.0):
            q = tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
            if inside_obstacle(q, self.obstacles, clear):
                return False
        return True


def _turns(rng):
    s = 1 if rng.random() < 0.5 else -1
    yield 0.0
    for t in AVOID_TURNS_RAD:
        yield s * t
        yield -s * t


def _walk_lateral(rng, g, start, yaw, length, clear, base_depth, amp=None):
    amp = rng.uniform(*WAVE_AMP_M) if amp is None else amp
    wl, ph = rng.uniform(*WAVE_LENGTH_M), rng.uniform(0, 2 * math.pi)
    pts, yaw0, rate, s = [start], yaw, 0.0, 0.0
    while s < length - 1e-9:
        rate = rate * YAW_DAMP + rng.gauss(0, YAW_NOISE_RAD)
        yaw += rate + (yaw0 - yaw) * YAW_RETURN
        p, nxt = pts[-1], None
        d = min(max(base_depth + amp * math.sin(2 * math.pi * s / wl + ph), LATERAL_DEPTH_M[0]), LATERAL_DEPTH_M[1])
        for turn in _turns(rng):
            c, sn = math.cos(yaw + turn), math.sin(yaw + turn)
            x, y = p[0] + STEP_M * c, p[1] + STEP_M * sn
            ax, ay = x + LOOKAHEAD_M * c, y + LOOKAHEAD_M * sn
            depth = max(g.depth_rule(x, y, d), g.depth_rule(ax, ay, d))
            dz = g.soil.surface(x, y) - depth - p[2]
            z = g.cap(x, y, p[2] + max(-MAX_DZ_M, min(MAX_DZ_M, dz)))
            if g.ok(p, (x, y, z), clear):
                nxt, yaw = (x, y, z), yaw + turn
                break
        if nxt is None:
            break
        s += math.dist(p, nxt)
        pts.append(nxt)
    return pts


def _walk_sinker(rng, g, start, yaw, pitch, target_depth, clear):
    pts = [start]
    for _ in range(SINKER_MAX_STEPS):
        p = pts[-1]
        if g.soil.surface(p[0], p[1]) - p[2] >= target_depth:
            break
        yaw += rng.gauss(0, SINKER_WANDER_RAD)
        pj = pitch + rng.gauss(0, SINKER_WANDER_RAD * 0.5)
        options = [(t, pj) for t in _turns(rng)] + [(t, 0.0) for t in _turns(rng)]
        nxt = None
        for turn, pt in options:
            h = STEP_M * math.cos(pt)
            x, y = p[0] + h * math.cos(yaw + turn), p[1] + h * math.sin(yaw + turn)
            z = g.cap(x, y, p[2] - STEP_M * math.sin(pt))
            if g.ok(p, (x, y, z), clear):
                nxt = (x, y, z)
                yaw += turn if pt else 0.0
                break
        if nxt is None:
            break
        pts.append(nxt)
    return pts


def _distances(pts):
    out, s = [0.0], 0.0
    for a, b in zip(pts, pts[1:]):
        s += math.dist(a, b)
        out.append(s)
    return out


def _born(pts, b0, last_day, floor_day=None, teased=False):
    ds = _distances(pts)
    L = ds[-1] or 1.0
    born = []
    for d in ds:
        b = b0 + (last_day - b0) * (d / L) ** GROWTH_POWER
        if teased and d <= TEASED_M:
            b = PLANTED_DAY + 1
        if floor_day is not None:
            b = max(b, floor_day)
        born.append(b)
    return born


def _taper(pts, r0):
    ds = _distances(pts)
    L = ds[-1] or 1.0
    r0 = max(r0, TIP_RADIUS_M)
    return [TIP_RADIUS_M + (r0 - TIP_RADIUS_M) * (1 - d / L) ** TAPER_POWER for d in ds]


def _heading(pts, i):
    a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
    return math.atan2(b[1] - a[1], b[0] - a[0])


def _branches(rng, g, parent, attach, angle, length_of, radius_frac, kind, order, last_day, rise=0.0):
    pts, out = parent["points"], []
    for i in sorted(attach):
        b0 = parent["born"][i]
        if b0 >= last_day - 1:
            continue
        p = pts[i]
        r0 = radius_frac * parent["final_radius_m"][i]
        yaw = _heading(pts, i) + rng.choice((-1, 1)) * math.radians(rng.uniform(*angle))
        depth = g.soil.surface(p[0], p[1]) - p[2] - rise
        bp = _walk_lateral(rng, g, p, yaw, length_of(), MIN_CLEAR_M + r0, depth)
        if len(bp) < 2:
            continue
        out.append({"order": order, "kind": kind, "points": bp,
                    "born": _born(bp, b0, last_day), "final_radius_m": _taper(bp, r0)})
    return out


def system(seed, at, reach_m, base_radius_m, soil, obstacles, last_day):
    """The whole root system of one climber up to last_day, made once."""
    rng = random.Random(seed)
    at = tuple(float(v) for v in at)
    g = _Ground(soil, at, reach_m, obstacles)
    roots = []
    n = rng.randint(*MAIN_COUNT)
    base_yaw, longest = rng.uniform(0, 2 * math.pi), rng.randrange(n)
    for k in range(n):
        yaw = base_yaw + 2 * math.pi * (k + rng.uniform(-MAIN_JITTER, MAIN_JITTER)) / n
        frac = 1.0 if k == longest else rng.uniform(*MAIN_LENGTH_FRAC)
        r0 = MAIN_RADIUS_FRAC * base_radius_m
        clear = MIN_CLEAR_M + r0
        start = None
        for turn in _turns(rng):  # leave the ball where nothing is in the way
            c, s = math.cos(yaw + turn), math.sin(yaw + turn)
            q = (at[0] + BALL_RADIUS_M * c, at[1] + BALL_RADIUS_M * s, at[2] - BALL_CENTRE_DEPTH_M)
            if not inside_obstacle(q, obstacles, clear):
                start, yaw = q, yaw + turn
                break
        if start is None:
            continue
        pts = _walk_lateral(rng, g, start, yaw, frac * reach_m - BALL_RADIUS_M, clear, rng.uniform(*BASE_DEPTH_M))
        if len(pts) < 2:
            continue
        main = {"order": 0, "kind": "lateral", "points": pts,
                "born": _born(pts, PLANTED_DAY, last_day, PLANTED_DAY + 1, teased=True),
                "final_radius_m": _taper(pts, r0)}
        roots.append(main)
        m = len(pts)
        attach = {int(rng.uniform(*SECOND_ATTACH_FRAC) * (m - 1)) for _ in range(rng.randint(*SECOND_COUNT))}
        L = _distances(pts)[-1]
        seconds = _branches(rng, g, main, attach, SECOND_ANGLE_DEG,
                            lambda: rng.uniform(*SECOND_LENGTH_FRAC) * L,
                            SECOND_RADIUS_FRAC, "lateral", 1, last_day)
        roots.extend(seconds)
        for sec in seconds:
            sp, ds, fa, next_d = sec["points"], _distances(sec["points"]), [], FEEDER_SPACING_M
            for i in range(1, len(sp)):
                if ds[i] >= next_d:
                    next_d += FEEDER_SPACING_M
                    depth = soil.surface(sp[i][0], sp[i][1]) - sp[i][2]
                    if rng.random() < (FEEDER_P_SHALLOW if depth <= FEEDER_SHALLOW_M else FEEDER_P_DEEP):
                        fa.append(i)
            roots.extend(_branches(rng, g, sec, fa, FEEDER_ANGLE_DEG,
                                   lambda: rng.uniform(*FEEDER_LENGTH_M),
                                   FEEDER_RADIUS_FRAC, "feeder", 2, last_day, FEEDER_RISE_M))
    for _ in range(rng.randint(*SINKER_COUNT)):
        yaw = rng.uniform(0, 2 * math.pi)
        off = rng.uniform(0, BALL_RADIUS_M * 0.6)
        start = (at[0] + off * math.cos(yaw), at[1] + off * math.sin(yaw), at[2] - SINKER_START_DEPTH_M)
        r0 = SINKER_RADIUS_FRAC * base_radius_m
        target = max(rng.uniform(*SINKER_DEPTH_M), soil.loosened_depth_m + SINKER_BELOW_LOOSENED_M)
        if inside_obstacle(start, obstacles, MIN_CLEAR_M + r0):
            continue
        pts = _walk_sinker(rng, g, start, yaw, math.radians(rng.uniform(*SINKER_PITCH_DEG)), target, MIN_CLEAR_M + r0)
        if len(pts) < 2:
            continue
        roots.append({"order": 0, "kind": "sinker", "points": pts,
                      "born": _born(pts, PLANTED_DAY, last_day, PLANTED_DAY + 1),
                      "final_radius_m": _taper(pts, r0)})
    return {"roots": roots}


def on_day(system, day, last_day):
    """What exists on a day: points born by then, each thickened by its age."""
    out = []
    for r in system["roots"]:
        n = 0
        for b in r["born"]:
            if b > day:
                break
            n += 1
        if n < 2:
            continue
        radii = []
        for b, f in zip(r["born"][:n], r["final_radius_m"][:n]):
            span = last_day - b
            t = 1.0 if span <= 0 else min(1.0, max(0.0, (day - b) / span))
            radii.append(TIP_RADIUS_M + (f - TIP_RADIUS_M) * t ** RADIUS_POWER)
        out.append({"kind": r["kind"], "order": r["order"], "points": r["points"][:n], "radius_m": radii})
    return out
