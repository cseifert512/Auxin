"""A tour of the forms one room can take: the states between them, and a trial building at each form.

    cd bower-blender
    python scripts/tour_states.py ../drawings-in-code/tours/first/tour.json
    python scripts/tour_states.py ../drawings-in-code/tours/first/tour.json --check     # build, write nothing

A tour is a list of forms. Each form sets some controls of the room (the keys of bower/controls.py, or
`base_slope` for the crown's `base_slope_deg`); what a form does not set stays as the design has it.
Between one form and the next every control moves in a straight line, and `between` states are built
on the way. With `"loop": true` the last form goes on to the first.

Writes, beside the tour's description:
    states.json                     every state: each member's centre line as the same number of points,
                                    with the way its depth is turned at each, so that a drawing can move
                                    a member from one state to the next point by point
and, for every form but one that changes nothing:
    ../releases/trial-tour-<tour>-<form>/    centre lines and design, for a planting to be grown on

No Blender. About two seconds a state. Nothing here is a snapshot: git ignores all of it, and the same
command makes it again.

The members are not the same in every state. The lattice's third tier fills the slots that fit, and
which fit changes with the form; the crown's ring is not there when the crown stands on the floor.
So states.json lists every member met on the tour, and each state says which of them it has.
"""

import copy
import json
import math
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bower import controls, snapshot, topology  # noqa: E402

SAMPLES = 64  # points kept of every member's centre line
RIBS = ("rib", "fill", "fine")  # the lattice's ribs: each runs from a head, on the crown or on a ring, to a foot that lands where the form lets it


def _base_slope(design: dict, room_id: str, value: float) -> dict:
    new = topology.set_crown(design, room_id, section={"base_slope_deg": value})[0]
    topology.validate(new)
    return new


def _read(design: dict, room_id: str, key: str) -> float:
    room = topology.get_room(design, room_id)
    if key == "base_slope":
        return room["crown"].get("section", {}).get("base_slope_deg", 0.0)
    return controls.BY_KEY[key].get(design, room)


def _apply(design: dict, room_id: str, key: str, value: float) -> dict:
    if key == "base_slope":
        return _base_slope(design, room_id, value)
    if controls.BY_KEY[key].kind == "count":
        raise SystemExit(f"{key} is a count: a tour moves lengths and angles only, since a member cannot be half there")
    return controls.adjust(design, room_id, key, value)


def shaped(design: dict, room_id: str, values: dict) -> dict:
    """The design with every control in `values` set. Some settings are only valid together (a crown on the
    floor has to arrive pointing down), so each is tried in turn until all are in, whatever order that takes."""
    left = {k: v for k, v in values.items() if abs(_read(design, room_id, k) - v) > 1e-9}
    while left:
        refused = {}
        for key in list(left):
            try:
                design = _apply(design, room_id, key, left[key])
                del left[key]
            except topology.DesignError as error:
                refused[key] = error
        if len(refused) == len(left) and left:
            raise topology.DesignError("; ".join(f"{k} = {left[k]}: {e}" for k, e in refused.items()))
    return design


def _dist(a, b) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def resampled(member: dict, count: int = SAMPLES, spacing=None) -> tuple:
    """A member's centre line as `count` points evenly spaced along it, and its depth axis at each.

    With `spacing`, the points are that far apart and counted back from the member's last point, its head; those
    that would fall beyond its first point, its foot, all lie on the foot. Two states of one rib then agree point
    for point down from the head, however much further one of them runs on."""
    points, axes = member["points_m"], member["depth_axes"]
    if member["closed"] and _dist(points[0], points[-1]) > 1e-6:
        points, axes = points + [points[0]], axes + [axes[0]]
    run = [0.0]
    for a, b in zip(points, points[1:]):
        run.append(run[-1] + _dist(a, b))
    at_points, at_axes, seg = [], [], 0
    for i in range(count):
        if spacing is not None:
            at = max(0.0, run[-1] - (count - 1 - i) * spacing)
        else:
            at = run[-1] * (i / count if member["closed"] else i / (count - 1))
        while seg < len(points) - 2 and run[seg + 1] < at:
            seg += 1
        span = run[seg + 1] - run[seg]
        t = 0.0 if span <= 0 else min(1.0, (at - run[seg]) / span)
        at_points.append([points[seg][k] + (points[seg + 1][k] - points[seg][k]) * t for k in range(3)])
        axis = [axes[seg][k] + (axes[seg + 1][k] - axes[seg][k]) * t for k in range(3)]
        size = math.sqrt(sum(c * c for c in axis)) or 1.0
        at_axes.append([c / size for c in axis])
    return at_points, at_axes


FOLLOW_M = 4.0  # two centre lines further apart than this, on average along them, are not one timber moved
REJOIN_M = 1.5  # a timber that was gone for a few states is the same one again only if it comes back about where it stood


def _apart(a: list, b: list) -> float:
    return sum(_dist(p, q) for p, q in zip(a, b)) / len(a)


def _paired(here: list, there: list, limit: float = FOLLOW_M) -> dict:
    """Pair centre lines of one state with those of the next: nearest first, each used once, none further than `limit`.
    `here` and `there` are lists of (key, kind, points), and only two of a kind are paired; returns {key here: key there}."""
    pairs = sorted((_apart(pa, pb), ka, kb) for ka, fa, pa in here for kb, fb, pb in there if fa == fb)
    out, taken = {}, set()
    for cost, ka, kb in pairs:
        if cost > limit:
            break
        if ka not in out and kb not in taken:
            out[ka] = kb
            taken.add(kb)
    return out


def _kind(member_id: str) -> str:
    """What a member is, apart from which of them: its room, family and hand ("R1.rib.ccw."). A rib of one hand never becomes one of the other."""
    return member_id.rstrip("0123456789")


def followed(built: list, loop: bool, snapshot_state) -> tuple:
    """Follow each timber through the states by where it is, not by what it is called.

    A member's name is its slot in the lattice, and a slot is not a place: as the form changes, the rib of one slot
    comes to land on the next pier round, and the name goes with the slot while the timber that stood there is now
    under another name. Followed by name, a rib would leap a whole bay between two states. So each timber of one
    state is paired with the nearest centre line of its family in the next, and keeps one number throughout.
    A timber with no pair in the next state has gone; one that nothing led to is new, unless it stands where
    one stood a few states before.

    Not every step is a small one even so. A rib that passes near enough to a pier is drawn into it and stands on
    the floor; one that passes wider lands on an arch. Which it does changes at once as the form changes, and the
    lower part of the rib is then somewhere else in the next state. That is the lattice re-forming, and it is the
    generator's: the two shapes are paired as one timber, and a drawing shows its foot crossing over.
    """
    tracks, states, last = [], [], {}  # last: track -> (state it last stood in, its points then)
    for at, state in enumerate(built):
        now = [(k, _kind(m["id"]), m["line"][0]) for k, m in enumerate(state["members"])]
        before = [(t, tracks[t]["kind"], points) for t, (seen, points) in last.items() if seen == at - 1]
        waiting = [(t, tracks[t]["kind"], points) for t, (seen, points) in last.items() if at - 4 <= seen < at - 1]
        to = _paired(before, now)
        plays = {k: t for t, k in to.items()}
        back = _paired(waiting, [n for n in now if n[0] not in plays], REJOIN_M)
        plays.update({k: t for t, k in back.items()})
        for k, m in enumerate(state["members"]):
            if k not in plays:
                plays[k] = len(tracks)
                tracks.append({"id": f"{m['id']}@{at}" if at else m["id"], "kind": _kind(m["id"]), "family": m["family"], "width_m": m["width_m"], "depth_m": m["depth_m"], "closed": m["closed"], "from_head": m["family"] in RIBS, "mesh": None})
            if at == snapshot_state:
                tracks[plays[k]]["mesh"] = m["id"]  # the snapshot's milled mesh of this name is this timber
            last[plays[k]] = (at, m["line"][0])
        if at == 0:
            first_plays = dict(plays)
        order = sorted(range(len(state["members"])), key=lambda k: plays[k])
        states.append({
            "values": state["values"],
            "has": [plays[k] for k in order],
            "mm": [round(c * 1000) for k in order for p in state["members"][k]["line"][0] for c in p],
            "axes": [round(c * 10000) for k in order for d in state["members"][k]["line"][1] for c in d],
        })
    wrap = None
    if loop:
        # going round: each timber standing in the last state, paired with one of the first state, which has a number already
        first = [(k, _kind(m["id"]), m["line"][0]) for k, m in enumerate(built[0]["members"])]
        ends = [(t, tracks[t]["kind"], points) for t, (seen, points) in last.items() if seen == len(built) - 1]
        becomes = [-1] * len(tracks)
        for t, k in _paired(ends, first).items():
            becomes[t] = first_plays[k]
        if any(becomes[t] != t for t, _, _ in ends):
            wrap = becomes
    return tracks, states, wrap


def main(argv: list) -> None:
    check = "--check" in argv
    file = Path(next(a for a in argv if not a.startswith("--"))).resolve()
    tour = json.loads(file.read_text(encoding="utf-8"))
    name, room_id, between = tour["name"], tour.get("room", "R1"), int(tour.get("between", 8))
    release = REPO.parent / "releases" / tour["snapshot"]
    base = topology.load(str(release / "design.json"))
    forms = tour["forms"]
    keys = sorted({k for form in forms for k in form.get("set", {})})
    at_rest = {k: _read(base, room_id, k) for k in keys}
    values_of = [{**at_rest, **form.get("set", {})} for form in forms]
    legs = len(forms) if tour.get("loop") else len(forms) - 1

    built, problems = [], []
    began = time.time()
    for leg in range(legs):
        a, b = values_of[leg], values_of[(leg + 1) % len(forms)]
        steps = between + 1 if leg < legs - 1 or tour.get("loop") else between + 2  # an open tour ends on its last form
        for step in range(steps):
            u = step / (between + 1)
            values = {k: round(a[k] + (b[k] - a[k]) * u, 4) for k in keys}
            label = f"{forms[leg]['id']}" + (f" +{step}/{between + 1}" if step else "")
            try:
                design = shaped(base, room_id, values)
                lines = snapshot.centrelines(design)
            except Exception as error:  # a state the generator will not build
                problems.append(f"{label}: {error}")
                print(f"  {label}: NOT BUILT: {error}")
                continue
            built.append({"values": values, "members": [{**{k: m[k] for k in ("id", "family", "width_m", "depth_m", "closed")}, "length_m": m["length_m"], "raw": m} for m in lines["members"]]})
            print(f"  {label}: {len(lines['members'])} members")
            if step == 0 and forms[leg].get("set") and not check:
                trial = REPO.parent / "releases" / f"trial-tour-{name}-{forms[leg]['id']}"
                trial.mkdir(parents=True, exist_ok=True)
                (trial / "design.json").write_text(json.dumps(design, indent=2) + "\n", encoding="utf-8")
                (trial / "centrelines.json").write_text(json.dumps(lines, separators=(",", ":")) + "\n", encoding="utf-8")
                made = ", ".join(f"`{k} = {v}`" for k, v in forms[leg]["set"].items())
                (trial / "TRIAL.md").write_text(
                    f"# {trial.name}\n\nA trial, not a snapshot: centre lines only, written by `bower-blender/scripts/tour_states.py`\n"
                    f"from `releases/{tour['snapshot']}/design.json` with {made}.\nNot in git. Safe to delete.\n",
                    encoding="utf-8",
                )
    print(f"{len(built)} states, {len(problems)} not built, {time.time() - began:.0f} s")
    if problems:
        raise SystemExit("the tour passes through states the generator will not build:\n  " + "\n  ".join(problems))
    # A rib is measured down from its head, in steps that let the longest rib of the tour fit; anything else by its share.
    spacing = math.ceil(1000 * max(m["length_m"] for state in built for m in state["members"] if m["family"] in RIBS) / (SAMPLES - 1)) / 1000
    for state in built:
        for m in state["members"]:
            m["line"] = resampled(m.pop("raw"), SAMPLES, spacing if m["family"] in RIBS else None)
    snapshot_form = next((i for i, f in enumerate(forms) if not f.get("set")), None)
    members, states, wrap = followed(built, bool(tour.get("loop")), None if snapshot_form is None else snapshot_form * (between + 1))
    print(f"{len(members)} timbers followed through the tour" + ("" if wrap is None else "; going round once does not bring every one back to where it began"))
    if check:
        return
    out = {
        "tour": name,
        "snapshot": tour["snapshot"],
        "samples": SAMPLES,
        # a member marked "from_head" has its points this far apart, counted from its last; the rest are spread evenly along it
        "spacing_m": spacing,
        "loop": bool(tour.get("loop")),
        "between": between,
        "members": members,
        # which timber each one has become when a loop comes round to its first state again, where that is not itself
        **({} if wrap is None else {"wrap": wrap}),
        # a form that changes nothing is the snapshot itself; any other was written as a trial to grow on
        "forms": [{"id": f["id"], "title": f.get("title", f["id"]), "state": i * (between + 1), "grown_on": f"trial-tour-{name}-{f['id']}" if f.get("set") else tour["snapshot"]} for i, f in enumerate(forms)],
        "states": states,
    }
    target = file.parent / "states.json"
    target.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {target} ({target.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1:])
