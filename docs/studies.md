# Studies: showing the building change, and why

A proposal, not built. Written 14 November 2026 to hand the idea over to whoever takes it up in this repository. It says what a study is, why it is wanted, what it would hold, what is already known to work, and what is still to decide. Numbers about plants are the simulator's running assumptions, not measurements.

## Why this is wanted

The deck has a slide called "Growth changes the geometry" (slide 5, tab "Shaded room", plate `drawings-in-code/plates/05-shaded-room.json`). Its three panels are headed "We want", "We ask" and "We reconsider". The review of it said that it shows shade, growth routes and a pier detail, but not the design changing because of what was learned, and asked for one concrete case: take a question the planting raised, change the geometry, and compare the two versions under the same planting assumptions. A trade-off is an acceptable result.

Clay's direction on top of that, 14 November:

- It should not be as simple as a before and after.
- The model is the factory drawings in `bower-factory`: you see the thing adjusting, and the drawing explains itself as it goes.
- The drawing should dissect why a change is being made and show it moving between stages.
- The drawings already run along one axis, time (design, assembly, planting, ten years of growth). This opens a second: how the building's geometry answers the planting. Shade and views belong on the same page.
- Anyone can make a parametric model. What is Bower's own is a method in which the planting visibly drives the design.

## The idea

A snapshot (`releases/<name>/`) hands the drawings one frozen building. A study hands them a design change as it happens: where the building started, what the plants needed that it did not give, how it moved, what that cost, and what grew on the result.

## What a study would hold

| Part | What it is |
|---|---|
| The path | Ordered steps. Each step moves one or two parameters of the design from one value to another. |
| The reason for each step | Data, not a caption: which plant need, which measure of the building was failing it, the threshold, and where the need is sourced. |
| The states in between | A dozen or so per step. Centre lines only, in the same format as a snapshot's `centrelines.json`, keyed by the same member IDs. |
| The measures at every state | What can be read off the geometry without growing anything: soil kept, the height at which a plant first meets a line, entrance width, cable length, timber volume, joint count. |
| The resting states | The start and end of each step as ordinary snapshots, with their milled meshes, each grown with the same planting. Shade, views and the gardener's work are read there. |

That gives a grid: geometry along one axis, time along the other. Each resting state has its own ten years of growth. The states between them have timber only.

A sketch of the file that would describe one, to make the idea concrete. Every name and value in it is a placeholder:

```json
{
  "schema": "bower.study/0",
  "name": "pier-opens",
  "base": "six-bay-radial-v1",
  "planting": { "care": "trained", "years": 10, "seed": 7, "specimen_m": 3 },
  "steps": [
    {
      "id": "open-the-pier",
      "because": {
        "need": "soil beside the plant's own way up",
        "plant": "wisteria-sinensis",
        "source": "where the need is stated, with its evidence status",
        "measure": "first_line_height_m",
        "was": 2.8,
        "wanted": "under 0.5"
      },
      "moves": [{ "parameter": "timber.piers.ring_radius_m", "from": 0.34, "to": 0.8 }],
      "costs": ["entrance_clear_m", "footing_spread_m"],
      "states": ["000", "001", "002"]
    }
  ],
  "states": {
    "000": { "centrelines": "states/000.json", "measures": {}, "snapshot": "six-bay-radial-v1" },
    "001": { "centrelines": "states/001.json", "measures": {} }
  }
}
```

## What the drawing becomes

A loop in the manner of the factory drawings, in stages:

1. The room, grown. The existing line of time plays.
2. What the plant needs. The place where the building disagrees is marked in red.
3. The building gives way. The timber moves from state to state while the measures count beside it.
4. What it cost. Whatever got worse is marked in red.
5. The same planting, grown again on the new building.

Beside it, a card like the factory's: what the plant needs (with its source), what moved, what it cost, what is still to prove.

Three rules from `bower-factory/docs/STYLE.md` that apply (that repository is Daniel Guerra's and is not part of this one): the drawings are loops that explain themselves, not things to hover over; one red, used only for what is moving or carrying force at that moment; at most two leaders and one dimension on screen at once.

One real limit. Plants cannot be blended between two buildings, because they are different plants. The move has to happen with the plants dimmed or cleared, as the factory drawings open an assembly in their exploded moment, and growth then replays on the new timber.

## What is known to work

Checked on 14 November, on `bower-blender/design/six_bay_radial.json`:

- **The engine makes an in-between state without Blender.** `bower.snapshot.centrelines(design)` is plain Python. It took 5 to 6 seconds per state, so a step of a dozen states is about a minute.

  ```python
  # from bower-blender/
  import copy
  from bower import snapshot, topology
  base = topology.load("design/six_bay_radial.json")
  state = copy.deepcopy(base)
  state["timber"]["piers"]["ring_radius_m"] = 0.8
  lines = snapshot.centrelines(state)        # {"members": [...]}; no Blender
  ```

- **Member IDs hold across the change.** At pier spacings of 0.34, 0.5 and 0.8 m the room has the same 111 members with the same IDs, so each timber can be followed from one state to the next.
- **Most members keep their sampling.** 99 of the 111 had the same number of sample points at 0.34 and 0.8. The other 12 need resampling before they can be moved point by point. Each member also carries its exact curve (`bezier_m`).
- **Growth is repeatable.** The ten-year trained run on `six-bay-radial-v1` was grown again and came out byte for byte the same. It takes about 90 seconds and writes a record of about 130 MB, which is not kept in git.
- **What a slider can change is already listed.** `bower-blender/bower/controls.py` holds each control as a pair of functions (read a value from a design, return a design with it changed), with no Blender in it. A step of a study can be written the same way.

## What is not built

| Where | What is needed |
|---|---|
| `bower-blender/` | A study writer: given a base design and a path, write the states, the measures at each, and the description. Plain Python for the states in between; Blender only for the milled meshes of the resting snapshots. |
| `bower-blender/` | The measures as functions of a design. Several exist inside `bower/ground.py` and `bower/lines.py` (soil kept, ground taken by a footing, the tie from a feeder to a line, the clear way through each bay, cable length) but are written out only as schedule rows. |
| `Horti-code-ture/` | The plant needs a step cites, as sourced values. The simulator's rule is no bare numbers about plants. Root-zone sizes are not in the library yet: roots are described in prose only (reported by the session that looked; not re-checked here). |
| `drawings-in-code/` | The studio reading a study. Today it loads one snapshot, chosen when it starts, and draws the timber from that snapshot's milled meshes (`studio/src/timber.ts`, `loadTimber`). Drawing timber from centre lines while it moves is new work, as are the stages, the measures counting, and the card. |
| `drawings-in-code/` | Growing every resting state of a study and reading shade, views and tie-ins from each. The steps exist (`npm run convert`, `plant`, `grow`, `compare`); running them over a study does not. |

## The first study: the pier opens

Why this one first:

- It is the question Clay put as "rooting vs foundations": the piers are where roots, footings and the plant's way up all want the same ground.
- It can be scored by measuring the geometry, so it does not lean on the simulator's growth numbers.
- Half of it exists as a draft.
- It fits the third panel of the plate, which already shows one pier close to.

What exists (`bower-blender/README.md`, "The ground at a pier"; in `bower-blender/design.json`, the eight-bay design, at pier `R1.P6`):

- Root zones authored outside the pier, a footing generated to give way to them, feeder cables up the outside of the arch legs, and the hand-overs from feeders to training lines measured.
- A solid pad took 9% of a root zone's ground and could not be cut back far enough; it needed the plant 0.65 m away. Screw piles under a lifted cap keep 97% of the ground with the plant 0.4 m away.
- A plant rooted outside the pier first meets a training line between 2.8 and 3.6 m up. Below that, about 3 m of each line is cable no plant can use.
- Two root zones beside a pier take 0.3 m off the way through each bay beside it.
- The feet of a pier stand about 0.15 m apart, with no soil between (`drawings-in-code/docs/for-the-building-model.md`).

What the study would do: let the legs stand apart round a bed, or split the pier in two with a planting slot, so that a plant is rooted beside its own way up.

What is not settled:

- **Which design it starts from.** The deck is on `six-bay-radial-v1`. That design has no training lines and no `ground` block; the draft is on the eight-bay `design.json`. The base needs both added before anything at its piers can be measured.
- **Which parameter moves.** `timber.piers.ring_radius_m` (0.34 today) is the obvious one, and the engine builds at 0.8. Whether 0.8 leaves room for a bed has not been checked. Splitting a pier in two is new work in the generator.
- **What it costs.** The pier stops reading as one tight trunk, which is what the reference images show. The entrance narrows. The footing spreads. No foundation has been designed or sized.

Measures to carry at each state: places a plant can be rooted beside its own line, soil kept per plant, the height at which each plant first meets a line, the clear way through each entrance, cable length, and how far the footing reaches.

## Other studies worth making

| The plant needs | Where the building disagrees today | What could move | What it costs |
|---|---|---|---|
| Undisturbed root ground | On piles the feet sit 0.3 m above the soil. | A plinth or a sunken bed at each pier; any tie between piers routed round the roots. | Nothing here is engineered. |
| Something thin to wrap | Lattice members are 178 to 197 mm round; only wisteria and the clingers hold on unaided. Lines cut the gardener's tie-ins from 4,587 to 1,634 over ten years. | Split a rib into two thin leaves with a gap, slim the rim tier where the short plants live, or mill a rough outer face for clingers. | Stiffness, more pieces, timber doing what cable now does. |
| A way up it can cover in a few years | 10 to 11 m of timber to the crown at a rib lean of 40 degrees. | Straighter ribs and a lower, wider crown. | Less weave and a lower room. See the note on the trials below. |
| Room for flowers to hang and come through | Wisteria flowers hang 0.2 to 1.1 m; the lattice is densest at the rim. | Lift or open the lattice where wisteria runs overhead, with openings sized so shoots pass. | Less shade from timber alone. |
| Light by compass | Six identical piers. | More members to ground on the sunny side; dense timber where plants will not reach, sparse where they will. | The regular radial room. |
| A gardener's reach | Crown at 6.3 m; pruning two to four times a year. | A lower crown, a ring that takes a ladder, a kept-clear band round the opening. | Height and spectacle. |

A plant's weight and the thickening of its trunk with age would also push section sizes and the gap of a training line. That is general knowledge, not from this repository's files, and would need sourcing first.

## Things to decide

- **Where a study lives.** Suggested: a folder beside the snapshots in `releases/`, marked by a `study.json` where a snapshot has a `manifest.json`, so that the rule that keeps snapshot files byte for byte covers it too.
- **Training lines are made in two places.** `bower-blender/bower/lines.py` makes them as part of the building, and `drawings-in-code/pipeline/lines.mjs` makes its own as a stand-in when it converts a snapshot. A study that measures lines needs one source. The planting brief asks for lines, beds and keep-clear zones to be carried in the snapshot; that changes the snapshot format, which is Clay's call.
- **Which way `depth_axes` point.** They are exported as the generator has them, which is inward for lattice members and a different convention for arches and the top ring. Drawing timber from centre lines needs a stated rule.
- **Members that appear or vanish.** Some changes alter the count of members (more ribs, another bay). Those cannot be moved point by point and would have to fade in and out.
- **Whether the simulator's growth can be shown as evidence.** See below.

## What was tried first, and why it was not used

The first attempt at a before and after changed the route to the crown. The same planting was grown for ten years on five versions of the six-bay room: three or four times as many ribs running from soil to crown, a lower and wider crown, and that crown with straighter ribs. More ribs changed nothing. The lowest version got four plants to the crown with training lines where none had arrived before.

It was not used, because the result came from a mechanism in the simulator, not from plants. Each main stem was given a fixed length at which it stops, and most of those lengths are unsourced. Which plants arrive is decided by that length against the length of the route. Clay's view: the simulator is not gospel, and a limit known to be wrong should not be kept. A change that removes the fixed lengths was started on the branch `claude/growth-without-stem-caps-e1458d` of the old `horti-code-ture` repository and had not landed when this was written. Once it does, "years to reach the crown" becomes something a study can score.

The five trial buildings and their runs are in the old `drawings-in-code` checkout as `trial-*` folders, marked safe to delete, and were not brought into this repository.
