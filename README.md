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

Which building is drawn is one setting: the snapshot named in `snapshot.json`. Every command below reads it, and
so does the studio. To draw another building, copy its snapshot into `releases/`, name it there, and run the same
commands again.

```bash
npm run convert                         # releases/<snapshot> -> scenes/<snapshot>/bower.json
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

The views a plate can use beyond the studio's three: `plan` (from straight above, cut 1.2 m up, so that what
shows is the floor and the shade on it) and `round`.

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

## What this is not

The growth is a scenario on stated assumptions, not a forecast: the statement under the drawing travels with every
picture made from it. The planting is a trial arrangement, not a planting design. The timber is concept geometry,
and its colour and ageing are pictures, not models.
