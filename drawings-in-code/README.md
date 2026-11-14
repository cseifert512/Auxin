# drawings-in-code

Bower's building and its plants, drawn together through time. One line of time runs from the design, through the
building going together, into ten years of growth. The timber is drawn as the factory drawings are, in their
projection and line, or in its own colour; the plants are in colour.

This folder reads from three others and changes none of them. The first two are beside it in this repository:

| It reads | From | For |
|---|---|---|
| a frozen snapshot of the building | `../releases/<snapshot>/`, made by `../bower-blender` | the timber: one mesh and one centre line per member |
| the plant simulator and its viewer | `../Horti-code-ture` (or `HORTI_DIR`) | growing a planting, and drawing each plant |
| the factory drawings' projection | `bower-factory`, `engine/projection.js` | the view the drawing is set up in |

## Run it

Needs Node 24 and `npm install` done once in `Horti-code-ture`. `npm install` here is needed only for films: it
brings ffmpeg.

Which building is drawn is one setting: the snapshot named in `snapshot.json`. Every command below reads it, and
so does the studio. To draw another building, name its snapshot there (snapshots are in `../releases/`) and run the same
commands again.

```bash
npm run convert                         # ../releases/<snapshot> -> scenes/<snapshot>/bower.json
npm run plant                           # the planting, from its rule -> scenes/<snapshot>/planting.json
npm run assemble                        # the order the joints allow -> scenes/<snapshot>/assembly.json
npm run grow -- <snapshot> trained 10 7 --specimen=3    # ten tended years -> scenes/<snapshot>/runs/trained-10y/
npm run compare                         # the runs of a scene side by side
npm run studio                          # the drawing, on http://localhost:5310
npm run film                            # exports/approach-ink/: the line of time as a film, wide and upright
```

In the studio: **Play** or drag the line of time; Space plays, the arrow keys step along it (further with Shift).
Drag to turn the drawing, scroll to come closer. **Timber / Left to silver / Ink** draws the timber in its own
colour, held by a finish that is kept up; the same left bare to weather; or as plain ink on paper. Coloured
timber is drawn glue-laminated: boards stacked through each member's depth, the glue lines on its sides, and each
board's grain drawn as a few lines at a distance and more of the real rings close to (`?grain=0` for flat colour).
`?day=3363&view=inside` opens on a day of growth and a view, `?build=0.5` half-way through the assembly,
`?timber=ink` in ink, and `?bare` hides the controls for a still. A planting grown while the studio is running
shows after it is restarted.

## Films

```bash
npm run film -- --view=approach --timber=ink                # both proportions
npm run film -- --view=drawing --timber=wood --format=landscape --build=10 --grow=40
```

A film is the studio's own drawing, taken frame by frame in a headless Chrome or Edge and put together with
ffmpeg: the same page, with the buttons hidden. It writes `exports/<name>/<name>-16x9.mp4` (1920 x 1080, for a
presentation) and `<name>-9x16.mp4` (1080 x 1920, for a phone), with a still of the last frame beside each. Every
frame is worked out in full, so a film is smooth although the studio, live, may not be. On the upright sheet the
approach is walked on, to stand before the bay in front. A film ends on the last midsummer of the run
(`--to-the-end` for the whole of it). The films themselves are not committed; the stills are.

`--still=day:3399` (a day of growth) or `--still=build:0.5` (a share of the assembly) takes one picture and makes
no film. The training lines are drawn as thin as they are, which is nearly not at all; `--lines=marked`, or
`?lines=marked` in the studio, draws them in green to be looked at.

## Plates for the presentation

```bash
npm run plate                     # every plate described in plates/ -> exports/deck/<name>.png and .webp
npm run plate -- 05-shaded-room   # one of them
npm run plate -- 04-plants-make-space --timber=wood    # the same with the timber in its colour: <name>-timber
npm run plate -- 04-plants-make-space --mode=light     # one mode of a piece again, leaving the others
```

A plate is a drawing made to fit one space in the presentation, on that page's paper and in its ink, with
nothing on it but the drawing. Each is described in `plates/<name>.json`, not drawn by hand, so the same command
makes it again from a new snapshot. A description is a `row` of panels (a view at a moment, with the sun of a day
and an hour), or the room `round`: the whole room unrolled as seen turning on the spot in the middle of it, where
each bay can be drawn at its own moment, so a turn of the room is also a passage of time. `shows` in each
description says what the plate shows, for the caption.

Nothing that goes to the presentation works anything out when it is shown. The studio does (it reads ten years
of growth and draws every leaf), so the studio is for making drawings, not for showing them: what is shown is
pictures made from it beforehand, and a page that turns through them.

A description with `modes` makes a **piece** instead: a drawing to turn, scrub and play. Each mode is drawn at a
list of moments, and those frames go into `exports/deck/<name>/` with a small player (`deck/player/`): an
`index.html` that needs nothing but the files beside it. Dragging turns the room or moves along the day, the line
of time scrubs, and left alone it plays. On paper, or with `?print`, it shows one still for the mode, which is
also saved as `poster-<mode>.png`. Set into a slide with `?embed` it shows only the drawing, and the slide can
drive it (`__setMode`, `__setT`, `__play`, or the same by `postMessage`), as it does the factory drawings.

| Description | For |
|---|---|
| `04-plants-make-space` (piece) | Slide 4. Time, which it opens on: the whole building from above, on the approach and from inside, through design, assembly, planting, establishment and a year of seasons. Space: the room unrolled, from installation to established and through a year. Light: the floor in plan with its shade, frame alone beside established, through a midsummer day. Made in ink and, as `04-plants-make-space-timber`, in timber. |
| `a-room-through-time` (piece) | A slide of its own, 16:9. What the studio draws, made beforehand as pictures so that nothing is worked out when it is shown: the building on the approach, from above and from inside, along one line of time (design, assembly, planting, establishment season by season). Changing view keeps the moment. In ink and, as `a-room-through-time-timber`, in timber. |
| `05-shaded-room` (plate) | Slide 5, Shaded room: the shade wanted, the ways up from the soil, a pier with its lines |

The views a plate can use beyond the studio's three: `plan` (from straight above, cut 1.2 m up, so that what
shows is the floor and the shade on it) and `round`.

### The same view, grown again

```bash
node pipeline/again.mjs                 # deck/grown-again/piece.json -> exports/deck/06-grown-again/
node pipeline/again.mjs --frames=keep   # measure and lay out again from the pictures already made
```

One view on one day from several grown runs of the same planting: the same building, the same plants in the same
beds, the same care, and another seed. It is for the slide that joins making and growing: of everything in the
picture, what is the same every time was decided by us, and what is not was decided by the plant. The maker draws
each run (one studio at a time, stopped between runs, on a port of its own), then sets the pictures against each
other: `stayed` is what every run draws alike, `differs` is the rest, in the one red. For each place marked in the
description (`regions`, as shares of the picture) it measures, of what any run draws there, the share that
differs. Those shares fill the bars of the scale under the picture, from decided by us to decided by the plant;
the places on that scale this picture cannot measure (the forest, the factory) are left as dashed outlines.

The page (`deck/grown-again/index.html`, copied beside the pictures) plays by itself: each run in turn, the three
quickly one after another, then together. `?embed` shows only the drawing, `?print` the last step complete, which
is also saved as `still.png`. The measure is of these pictures, not of plants: it says how far three runs of one
scenario agree, on the simulator's assumptions.

## Vignettes

```bash
node pipeline/vignette.mjs ivy-at-a-lap           # deck/ivy-at-a-lap/ -> exports/deck/ivy-at-a-lap/
node pipeline/vignette.mjs shaded-at-the-pier
node pipeline/vignette.mjs shaded-at-the-pier --only=page   # the page and its numbers again, drawing nothing
```

A vignette shows one thing happening, so that seeing it is the explanation. The measure is the factory
drawings' station pages (`bower-factory`, `review/<nn>/`): the thing itself drawn large and moving, one red
for what is moving or forced, labels of a few words on the parts they are about, steps named for what happens,
a caption of one short line, and no paragraphs.

`deck/ivy-at-a-lap` is drawn that way, and is worked out afresh for every moment: one lap of the roof, from
the two members as Blender mills them (`bower-blender/scripts/joint_detail.py`), with the view turning. It
comes in from the whole room, an ivy stem creeps along a member into the gap beside the one that crosses it,
thickens and forces the lap; the lap is milled open; the stem has room; and the view goes back out to the room
with the laps cut this way marked. It has no studio pictures: its `piece.json` asks for none.

`deck/shaded-at-the-pier` is the older kind: studio pictures of the room and one pier, made beforehand and
shown in turn, with marks and labels drawn over them where the studio says each place falls. It does not yet
show its cause happening, and is to be drawn again in the manner of the first.

`deck/<name>/` holds what a vignette is made from: `piece.json` (views and sets of moments, if it uses studio
pictures), `data.mjs` (what it is drawn from, worked out from the model and the runs) and `index.html` (the
page). It opens from its folder in `exports/deck/`; `.claude/launch.json` serves that folder as `pieces` on
port 5313.

## What is where

- `pipeline/convert.mjs` writes the simulator's input from a snapshot, and adds what the building model does not
  hold yet: the training lines, where plants go into the ground, and where a visitor stands. Plants go in where
  the timber meets the ground and nowhere else: at the piers. `--no-lines` leaves the timber bare. Which
  members carry a line follows the building model's own rule (`bower-blender`, `bower/lines.py`): the lattice's
  members that stand on the floor, and not the arches, so no line or planting is hung on a doorway.
- `pipeline/lines.mjs` lays out the training lines. A line belongs to a member: thin cable held about 3 inches
  off its outer face on standoffs, going where the member goes, up the leg, through the curve of the pier and out
  over the roof. By default every member that reaches the ground carries one, with a bed at its foot
  (`--carry=ground+ribs`, `all`, or a pattern for others). It is a rule, not a drawing: it reads any snapshot,
  so it goes on working as the building changes. Standoffs and tension are not worked out, and the rule belongs
  in the building's own generator once it is settled.
- `pipeline/plant.mjs` writes the planting from a rule: every bed takes a plant, and which plants a pier takes
  depends on the side of the room it stands on.
- `pipeline/assemble.mjs` reads the joint schedule for what has to be in place before what (a member lapped
  under another, a member housed into another) and puts the members in an order that keeps to it. It is the order
  the joints allow, not a method statement: lifting, propping and scaffold are not worked out.
- `pipeline/grow.mjs` runs the simulator and keeps the record of every stem, leaf and flower with its days, the
  design report, and `run.json` (which simulator commit, what it warned of, what it assumed). The simulator
  plants each climber as a young cane, 0.15 to 1.2 m by kind; `--specimen=3` has it go in standing 3 m with all
  its main stems started, and changes nothing else about how it grows.
- `pipeline/reseat.mjs` moves each supported stem on to the timber faces that are really there. The simulator's
  input cannot say which way a section is turned; the snapshot can.
- `pipeline/thin.mjs` drops the points of free-hanging shoots that a drawing of a whole room cannot show.
- `pipeline/clear.mjs` keeps every stem outside the timber. The simulator winds a stem round the member it
  climbs and takes no account of the members crossing that one, so a tenth of the stem as recorded stands inside
  wood. Each such stretch is taken out by one face of the member it is in, and rests on that face from then on.
  `pipeline/solids.mjs` is the timber as solids, which this and the lines both ask.
- `pipeline/compare.mjs` sets the runs of a scene side by side: timber held, how, and what a visitor sees.
- `pipeline/film.mjs` makes the films.
- `studio/` is the drawing.
- `sketches/` is for trying things, and nothing in it is a drawing for the deck. `sketches/design-space/` moves
  one control of the building through a few values and draws the timber going from one to the next, with what
  can be measured off the centre lines counting beside it. Its states are made by
  `python scripts/sweep_states.py` in `bower-blender` (about two minutes, no Blender) and are not in git. Open
  `index.html` afterwards; it needs no server. A change can also have the same planting grown at its two ends,
  which adds a line of time to the page and the stems of each end to the drawing:

  ```bash
  cd ../bower-blender && python scripts/trial_snapshot.py trial-pier-120 timber.piers.ring_radius_m=1.2
  cd ../drawings-in-code
  npm run convert -- trial-pier-120 && npm run plant -- trial-pier-120
  npm run grow -- trial-pier-120 trained 10 7 --specimen=3
  node sketches/design-space/grown.mjs pier-opens six-bay-radial-v1/trained-10y-new-growth trial-pier-120/trained-10y
  ```

  A trial is centre lines only, written into `../releases/trial-*/` because that is where the steps above read
  from. It is not a snapshot: no milled meshes, no manifest, not in git, and the studio cannot draw it.

  `sketches/design-space/shaded-at-the-pier.html` is the form a drawing for the deck would take: one finding
  from growing a planting on the room, and the change to the building it led to. It is told in the deck's own
  words (We want, We ask, We reconsider) and then the same planting is grown again on the changed room. Its
  subject is what the plants did, not a parameter of the building, and there is nothing on it to set: it plays
  by itself, and the viewer may pause it or go to a step. The whole room and one pier are drawn together. It
  follows the factory drawings' rules (`bower-factory`, `docs/STYLE.md`): one red for what is moving or at
  issue, at most two leaders and one dimension at once, nothing to hover over. A version with a tag for every
  control of the building was tried and dropped (commit `6aeac0c`): organised by what the generator can vary, it
  read as a parametric model. The page with the sliders is the workbench. Both are sketches: centre lines and
  stems.

  `sketches/design-space/found-the-joints.html` is a second finding in the same form, and one addressed to
  single joints: which of the joints the mill cuts are reached by a plant that clings to the timber, and when.
  Asking again there is growing the same planting with other seeds: some joints are reached every time, some
  only sometimes. Its list is made by `joints.mjs`, which matches the places the simulator names (`j188`) to
  rows of the snapshot's `joints.csv`:

  ```bash
  npm run grow -- six-bay-radial-v1 trained 10 8 --specimen=3 --name=trained-10y-new-growth-seed8
  npm run grow -- six-bay-radial-v1 trained 10 9 --specimen=3 --name=trained-10y-new-growth-seed9
  node sketches/design-space/joints.mjs six-bay-radial-v1 trained-10y-new-growth trained-10y-new-growth-seed8 trained-10y-new-growth-seed9
  ```

  `joints.mjs` also writes `scenes/<snapshot>/joints-reached.json`, which is kept in git: it is what goes back
  to the building (`bower-blender`, README, "Joints the plants reach"). The joint drawn close to in the
  vignette is the two members as Blender mills them, before and after the building's answer, from
  `bower-blender/scripts/joint_detail.py`, which writes `joint-detail.js` beside the page.

## What this is not

The growth is a scenario on stated assumptions, not a forecast: the statement under the drawing travels with every
picture made from it. The planting is a trial arrangement, not a planting design. The timber is concept geometry,
and its colour and ageing are pictures, not models.
