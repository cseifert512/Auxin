"""Check the root drawing rule in roots.py. Run: python check_roots.py

These checks test that the drawing obeys its own rules (growth order, the
ground, the steel). They say nothing about real roots.
"""
import math
import time

import roots

LAST_DAY = 3394
DAYS = (12, 136, 837, 1933, 3394)
CLEAR = 0.015


def surface(x, y):
    return 0.05 + 0.03 * math.sin(0.7 * x) + 0.02 * math.cos(0.9 * y)


SOIL = roots.Soil(surface, loosened_depth_m=0.6, ring=(4.55, 9.3), floor_base_m=0.2)
AT = (0.0, 8.6, surface(0.0, 8.6))


def obstacles_near(at):
    ax, ay, _ = at
    s = surface(ax, ay)
    out = []
    for d, ang in ((0.3, 0.4), (0.7, 2.3), (1.1, 4.1)):
        x, y = ax + d * math.cos(ang), ay + d * math.sin(ang)
        out.append({"kind": "post", "at": (x, y), "half_m": 0.04, "top": s + 0.4, "bottom": s - 0.65})
    for d, ang in ((0.25, 3.3), (0.9, 5.5)):
        out.append({"kind": "pile", "at": (ax + d * math.cos(ang), ay + d * math.sin(ang)),
                    "radius_m": 0.045, "top": s - 0.05})
    out.append({"kind": "plate", "outline": [(ax + 0.2, ay - 0.6), (ax + 1.2, ay - 0.6),
                                             (ax + 1.2, ay - 0.5), (ax + 0.2, ay - 0.5)],
                "top": s - 0.6, "bottom": s - 0.72})
    return out


OBS = obstacles_near(AT)


def build(seed="clematis-3", at=AT, reach=2.5, obs=OBS):
    return roots.system(seed, at, reach, 0.03, SOIL, obs, LAST_DAY)


def length(listing):
    return sum(math.dist(a, b) for r in listing for a, b in zip(r["points"], r["points"][1:]))


def all_points(sysm):
    return [p for r in sysm["roots"] for p in r["points"]]


def check_determinism():
    assert build() == build()
    assert build("a") != build("b")


def check_monotone():
    sysm = build()
    days = sorted(set(DAYS) | {11, 13, 50, 400, 2500})
    for a, b in zip(days, days[1:]):
        A, B = roots.on_day(sysm, a, LAST_DAY), roots.on_day(sysm, b, LAST_DAY)
        j = 0
        for rb in B:
            if j < len(A):
                ra = A[j]
                n = len(ra["points"])
                if ra["kind"] == rb["kind"] and rb["points"][:n] == ra["points"]:
                    assert all(y >= x - 1e-15 for x, y in zip(ra["radius_m"], rb["radius_m"])), (a, b)
                    j += 1
        assert j == len(A), (a, b, j, len(A))


def check_ground_and_obstacles():
    for k in range(12):
        sysm = build(f"seed-{k}")
        for p in all_points(sysm):
            assert p[2] <= surface(p[0], p[1]) - 0.03 + 1e-9, p
            assert not roots.inside_obstacle(p, OBS, CLEAR), p


def check_plate_under_ball():
    s = surface(AT[0], AT[1])
    plate = [{"kind": "plate", "outline": [(-0.5, 8.2), (0.5, 8.2), (0.5, 8.9), (-0.5, 8.9)],
              "top": s - 0.6, "bottom": s - 0.72}]
    for k in range(6):
        for p in all_points(build(f"plate-{k}", obs=plate)):
            assert not roots.inside_obstacle(p, plate, CLEAR), p


def check_floor():
    at = (0.0, 5.0, surface(0.0, 5.0))
    sysm = build("by-the-floor", at=at, obs=[])
    under = [p for p in all_points(sysm) if math.hypot(p[0], p[1]) < SOIL.ring[0]]
    assert under, "test plant should send roots under the floor"
    for p in under:
        assert p[2] <= surface(p[0], p[1]) - SOIL.floor_base_m + 1e-9, p


def check_reach():
    for reach in (1.2, 2.5, 3.5):
        for k in range(8):
            sysm = build(f"reach-{k}", reach=reach)
            far = max(math.hypot(p[0] - AT[0], p[1] - AT[1]) for p in all_points(sysm))
            assert 0.8 * reach <= far <= 1.05 * reach, (reach, k, far)


def check_lengths():
    for k in range(8):
        sysm = build(f"len-{k}")
        assert length(roots.on_day(sysm, 12, LAST_DAY)) < 2.0
        total = length(roots.on_day(sysm, LAST_DAY, LAST_DAY))
        assert 20 <= total <= 400, total


def check_sinkers():
    for k in range(8):
        sysm = build(f"sink-{k}")
        sinkers = [r for r in sysm["roots"] if r["kind"] == "sinker"]
        assert sinkers
        for r in sinkers:
            deepest = max(surface(p[0], p[1]) - p[2] for p in r["points"])
            assert deepest >= 0.8, deepest


def check_spacing():
    for r in build()["roots"]:
        for a, b in zip(r["points"], r["points"][1:]):
            assert 0.04 <= math.dist(a, b) <= 0.09, math.dist(a, b)


def check_speed():
    t = time.perf_counter()
    build("speed", reach=3.5)
    assert time.perf_counter() - t < 1.0


def table():
    sysm = build()
    print(f"{'day':>5} {'roots':>6} {'points':>7} {'length m':>9} {'reach m':>8} {'deepest m':>10}")
    for d in DAYS:
        ls = roots.on_day(sysm, d, LAST_DAY)
        pts = [p for r in ls for p in r["points"]]
        far = max((math.hypot(p[0] - AT[0], p[1] - AT[1]) for p in pts), default=0.0)
        deep = max((surface(p[0], p[1]) - p[2] for p in pts), default=0.0)
        print(f"{d:>5} {len(ls):>6} {len(pts):>7} {length(ls):>9.2f} {far:>8.2f} {deep:>10.2f}")


if __name__ == "__main__":
    checks = [v for k, v in sorted(globals().items()) if k.startswith("check_")]
    for c in checks:
        c()
    print(f"{len(checks)} passed")
    table()
