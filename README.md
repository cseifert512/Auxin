# drawings-in-code

Bower's building and its plants, drawn together through time. One line of time runs from the design, through the
building going together, into ten years of growth. The timber is drawn as the factory drawings are, in their
projection and line, or in its own colour; the plants are in colour.

This repository joins three others and changes none of them:

| It reads | From | For |
|---|---|---|
| a frozen snapshot of the building | `releases/<snapshot>/`, made in `bower-blender` | the timber: one mesh and one centre line per member |
| the plant simulator and its viewer | `../Horti-code-ture` (or `HORTI_DIR`) | growing a planting, and drawing each plant |
| the factory drawings' projection | `bower-factory`, `engine/projection.js` | the view the drawing is set up in |

## Run it

Needs Node 24 and `npm install` done once in `Horti-code-ture`. `npm install` here is needed only for films: it
brings ffmpeg.

```bash
npm run convert                         # releases/six-bay-v1 -> scenes/six-bay-v1/bower.json
npm run plant                           # the planting, from its rule -> scenes/six-bay-v1/planting.json
npm run assemble                        # the order the joints allow -> scenes/six-bay-v1/assembly.json
npm run grow -- six-bay-v1 trained 10 7 --specimen=3    # ten tended years -> scenes/six-bay-v1/runs/trained-10y/
npm run compare                         # the runs of a scene side by side
npm run studio                          # the drawing, on http://localhost:5310
npm run film                            # exports/approach-ink/: the line of time as a film, wide and upright
```

In the studio: **Play** or drag the line of time; Space plays, the arrow keys step along it (further with Shift).
Drag to turn the drawing, scroll to come closer. **Timber / Left to silver / Ink** draws the timber in its own
colour, held by a finish that is kept up; the same left bare to weather; or as plain ink on paper.
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

## What is where

- `pipeline/convert.mjs` writes the simulator's input from a snapshot, and adds what the building model does not
  hold yet: the training lines, where plants go into the ground, and where a visitor stands. Plants go in where
  the timber meets the ground and nowhere else: at the piers. `--no-lines` leaves the timber bare.
- `pipeline/lines.mjs` lays out the training lines: thin cable on the outside of the structure, fixed only at the
  lap joints the building already has. They lead plants up the way the loads come down. A *bough* follows the
  hoop inside each arch, from the ground at one pier, over the bay, to the ground at the next; *branches* leave
  it and run from joint to joint straight up the slope to the crown, across the open cells of the lattice.
  Nothing is strung across an opening. It is a rule, not a drawing: it reads any snapshot's joints, so it goes
  on working as the building changes. `--boughs=` and `--spacing=` say which members carry boughs and how far
  apart the branches leave them. Where a cable is fixed and how it is tensioned are not worked out.
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

## What this is not

The growth is a scenario on stated assumptions, not a forecast: the statement under the drawing travels with every
picture made from it. The planting is a trial arrangement, not a planting design. The timber is concept geometry,
and its colour and ageing are pictures, not models.
