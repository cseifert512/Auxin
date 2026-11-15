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
npm run grow -- <snapshot> trained 10 7 --specimen=3 --tall=wisteria:4    # ten tended years -> scenes/<snapshot>/runs/trained-10y/
npm run compare                         # the runs of a scene side by side
npm run studio                          # the drawing, on http://localhost:5310
npm run film                            # exports/approach-ink/: the line of time as a film, wide and upright
```

**Which simulator grows the plants.** The checkout beside this repository, unless `snapshot.json` names a
`simulator` folder or `HORTI_DIR` is set. Since 14 November 2026 its `main` no longer stops a main stem at a length
the model assumed (for the wisterias, the route of an earlier prototype's vault): how far a plant is taken is the
gardener's plan. Each run's `run.json` says which branch and commit grew it, and what the gardener cut off, act
by act.

**The planting is a design, and there are two to choose between** (`npm run plant -- --scheme=`; the rule and
the reasons are at the head of `pipeline/plant.mjs`):

- `piers`, the one in use: **divided**. Each pier is one character and the characters alternate round the room, so
  every plant is met on every side. A wisteria pier has two wisterias over the roof, the Chinese and the Japanese,
  and the woodbine and an evergreen beside the doorways. A vine pier has the vine and the akebia over the roof, and evergreen honeysuckle and
  ivy on the legs, held below the spring of the roof so that the piers are clothed in winter and the roof lets the
  light in. The wisterias take the warmer piers.
- `woven`: **integrated**. Every pier carries the same company (a wisteria, an akebia or the vine, a woodbine, an
  evergreen) and nothing is held back, so the plants grow through one another and the building is one texture.

Both have 24 plants, at the feet of the lines. They go in as nursery specimens standing 3 m, and the wisterias
at 4 m, a size mature wisterias are sold at (`--specimen=3 --tall=wisteria:4`); the slow first seasons the plant
models give a newly planted climber are kept. `cover` and `even` are the earlier trials, by the side of the room.

| Run of `six-bay-radial-v1` | What it is | Routes held | Framework | Timber seen in June: inside / approach / above | Evergreens in winter |
|---|---|---|---|---|---|
| `trained-10y` | **divided by pier**, as modelled: what every drawing is made from | 96% | 3,042 m | 41% / 45% / 24% | 33% |
| `woven-10y` | woven (`--plan=planting-woven.json`) | 95% | 2,733 m | 51% / 45% / 27% | 30% |
| `high-10y` | divided by pier, every plant at the high end of what is published for a year's growth (`--band=high`) | 96% | 3,412 m | 33% / 43% / 20% | 31% |
| `cover-10y` | earlier trial: by side, three vigorous climbers and an accent to a pier | 94% | 2,942 m | 85% / 58% / 31% | 27% |
| `even-10y` | earlier trial: by side, every bed alike, small plants and vigorous | 83% | 2,101 m | 81% / 68% / 62% | 31% |
| `even-loose-10y` | the same with a lighter hand (`--free=vine,akebia,honeysuckle --loose=1.2`) | 84% | 1,999 m | 79% / 65% / 58% | |
| `capped-10y` | as the drawings were first grown: main stems stopped at an assumed length | 75% | 1,781 m | 85% / 73% / 71% | 28% |

`npm run compare` sets them side by side. `--band=low` is the other end of what is published, and
`--stems=2` lets twice as many stems share a member (it adds little on this building).

**The gardener's hand is a design setting too**, not a fact about a plant. A planting plan can hold a plant below
a height (the divided scheme does, for the evergreens on the legs). The simulator writes each plant the RHS's
routine for a plant kept within bounds; `--free=` and `--loose=` loosen that before it is carried out. Tried on the
earlier planting: it took the cutting from 6.8 km of stem in ten years to 0.6 km and changed what is seen by a few
points of leaf. The knife is not what keeps a planting thin: which plants are planted is.

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
npm run film -- --view=approach --timber=wood --name=approach-timber    # the same with the timber in its colour
npm run film -- --camera=tour --timber=wood --name=tour-timber --format=landscape    # a camera that moves
npm run film -- --view=drawing --timber=wood --format=landscape --build=10 --grow=40
```

A film is the studio's own drawing, taken frame by frame in a headless Chrome or Edge and put together with
ffmpeg: the same page, with the buttons hidden. It writes `exports/<name>/<name>-16x9.mp4` (1920 x 1080, for a
presentation) and `<name>-9x16.mp4` (1080 x 1920, for a phone), with a still of the last frame beside each. Every
frame is worked out in full, so a film is smooth although the studio, live, may not be. On the upright sheet the
approach is walked on, to stand before the bay in front. A film ends on the last midsummer of the run
(`--to-the-end` for the whole of it). The films themselves are not committed; the stills are.

`--camera=tour` moves the camera instead of standing it at a view: from where the approach stands it goes once
round the building as it is put up and grows, rising to look down on the roof; then in under the arch in front;
and from just short of the middle of the room it looks up into the crown (`tour` in `studio/src/paper.ts`). The
path is worked out from the building's own approach view, its middle and its height, so it follows a new
building. Nothing is written over the picture in this one.

`--still=day:3399` (a day of growth) or `--still=build:0.5` (a share of the assembly) takes one picture and makes
no film. The training lines are drawn as thin as they are, which is nearly not at all; `--lines=marked`, or
`?lines=marked` in the studio, draws them in green to be looked at.

## The live drawing, for the presentation

```bash
npm run live        # -> exports/deck/a-room-through-time/: the studio as plain files, about 12 MB
```

The room through time is the one drawing that goes to the presentation live: turned by hand, played, scrubbed,
changed from view to view. Drawn from the whole record of a run it is far too heavy for that (a hundred megabytes
to read, eight and a half million triangles a frame, most of them thinner than a pixel). `npm run live` makes it
light without changing what is seen:

- `pipeline/lighten.mjs` writes a light copy of each run, `scenes/<snapshot>/light/<run>.growth`: stems kept only
  where they bend, twigs too fine to see left out with the thorns and rootlets, and, where a plant is a crowd of
  leaves, fewer of them, each a little larger. About 5 MB, from about 100.
- the studio, when it draws live, draws a leaf far across the room as the outline of each blade
  (`studio/src/coarsen.ts`) and keeps the plants' own models for the leaves nearest the eye; it brings the leaves
  up to the day a few kinds at a time while it plays, so that no frame waits for all of them.
- a still of the established room is made first. The page shows it at once, brings the drawing up over it when
  it is ready, and keeps it if the machine cannot draw at all.

What comes out is plain files. It needs a web server (any: the presentation's own) and nothing else: nothing to
install, nothing to run first. Set into a slide:

```html
<iframe src="a-room-through-time/index.html?embed&paper=EEF3EA&ink=102820&view=approach"></iframe>
```

`embed` leaves out the title and the words under the drawing; `paper` and `ink` are the slide's; `view` is where
it opens (`drawing`, `approach`, `inside`, `plan`); `play` starts it by itself. On this machine's built-in
graphics it plays at fifty to sixty frames a second, where the whole record gave fifteen.

Pictures made beforehand (plates, pieces, films) still take the whole record, and so does the studio with
`?whole`. `window.studio.bench()` and `.pools()` in the studio say what a frame costs and what is in it.

## A turn through the forms

```bash
cd ../bower-blender && python scripts/tour_states.py ../drawings-in-code/tours/first/tour.json   # every state, and a trial building at each form
cd ../drawings-in-code
node pipeline/tour.mjs first grow              # the same planting, ten years, on each form (--again: on all of them afresh)
node pipeline/tour.mjs first film              # exports/tour-first/tour-first.mp4
node pipeline/tour.mjs first film --still=12.5 # one picture, 12.5 s into the film
node pipeline/tour.mjs first film --still=7 --back=0.5 --lift=3.5   # the same from nearer and higher, to look at joints
```

A film of the room going from one form to another with a planting on it, while a year of seasons goes by and the
camera goes round. A tour is described in `tours/<name>/tour.json`: the forms (each sets some of the building's
controls, as its sliders do), and how the film is timed. `tours/first` goes from the lantern as designed to a flared
basket, an open oculus, the oculus turned down, a trunk standing on the floor, a tall close room, and back.
The planting is the one the other drawings use (`npm run plant`, then `--specimen=3 --tall=wisteria:4`), unless
the tour's `planting` says otherwise. Every form, the snapshot's own too, is grown as a trial under
`scenes/trial-tour-*`, so one command grows them all alike and no snapshot's scene is touched.

What it is, and is not:

- **The timber is the generator's at every state, joints and all.** Between two states a timber is moved point
  by point, and it is cut where it then crosses the others: each state carries the laps the building's joints
  code sets out for it. A timber is drawn as the generator's own simpler model of a milled piece, built here
  from its centre line: flat-walled laps, ends cut to their planes. It is not the milled mesh of a snapshot, so
  there are no housings, seats or splayed walls; a rib's end runs into the member it meets; and a lap too
  oblique or too near an end to step in is left uncut in both members (about 24 of 780 on the flared basket).
- **The lattice re-forms as the form changes**, and that is the generator's doing: a rib is drawn into a pier
  and stands on the floor, or lands on an arch, and which it does changes at once (`bower-blender`, README, "A
  tour of forms"). The film shows such a rib running out to its new foot or drawing back from its old one.
- **A planting is grown on each form, and on nothing between.** Away from its form a planting is carried: every
  stem point that lies on a timber keeps its place along that timber and its side of it, and what stands on it
  goes with it; shoots that hang free keep their shape. Across the middle of the way from one form to the next,
  one planting is dissolved into the other, picture into picture. So the film is taken once for each form and
  the takes are laid over each other.
- It is a picture of the forms one room can take, each with the same planting grown on it. No building moves, and
  nothing grew on the states in between. The line under the film says so.

A take draws the plants afresh for every picture in which the form has moved, so a film takes about as long as
its pictures number in seconds, several times over. `--fps`, `--scale` and `--size` make a quicker one to judge
the movement by.

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

A description with `modes` makes a **piece** instead: a drawing to turn, scrub and play. Each mode is drawn at a
list of moments, and those frames go into `exports/deck/<name>/` with a small player (`deck/player/`): an
`index.html` that needs nothing but the files beside it. Dragging turns the room or moves along the day, the line
of time scrubs, and left alone it plays. On paper, or with `?print`, it shows one still for the mode, which is
also saved as `poster-<mode>.png`. Set into a slide with `?embed` it shows only the drawing, and the slide can
drive it (`__setMode`, `__setT`, `__play`, or the same by `postMessage`), as it does the factory drawings.

| Description | For |
|---|---|
| `04-plants-make-space` (piece) | Slide 4. Time, which it opens on: the whole building from above, on the approach and from inside, through design, assembly, planting, establishment and a year of seasons. Space: the room unrolled, from installation to established and through a year. Light: the floor in plan with its shade, frame alone beside established, through a midsummer day. Made in ink and, as `04-plants-make-space-timber`, in timber. |
| `05-shaded-room` (plate) | Slide 5, Shaded room: the shade wanted, the ways up from the soil, a pier with its lines |

The views a plate can use beyond the studio's three: `plan` (from straight above, cut 2 m up, so that what
shows is the floor, the shade on it and the piers with what grows at them; the arches and the crown overhead are
drawn broken, and a small red sun stands on the side the light comes from) and `round`.

### The same view, grown again

```bash
node pipeline/again.mjs                 # deck/grown-again/piece.json -> exports/deck/06-grown-again/
node pipeline/again.mjs --frames=keep   # lay out again from the pictures already made
```

One view on one day from several grown runs of the same planting: the same building, the same plants in the same
beds, the same care, and another seed. The page turns one picture from one run to the next, so the timber holds
still and the plants do not. It is laid out as a station page of the factory drawings is: a name, one short line
for what is happening now, the steps, and the same plain questions beside it (what happens, what is Bower's, still
to prove). `?embed` shows only the drawing; `?print` shows the same band of each run one above another, which is
also saved as `still.png`.

A first version set the runs against each other in red, with a measured bar for each of four marked places and a
scale of eight steps under the picture. It showed too many things at once to be read and was taken out (it is in
commit `8e53829`).

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

`exports/deck/inhabited-room/` is not made here. It is a drawing to explore (one room, its ground, one pier,
and the pier designed three ways), packed from a Blender scene by
`../bower-blender/studies/inhabited-room/package_explorer.py`. Its own `README.md` says what it holds and how
a slide drives it.

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
- `pipeline/tour.mjs` grows a planting on each form of a tour and makes the film of it. `studio/src/tour.ts`
  is what moves the timber and carries the plants; the studio reads it only when asked for a tour.
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
