# drawings-in-code

Bower's building and its plants, drawn together through time. The timber is an ink drawing in the projection and
line of the factory drawings; the plants are in colour; one line of time runs from the day of planting.

This repository joins three others and changes none of them:

| It reads | From | For |
|---|---|---|
| a frozen snapshot of the building | `releases/<snapshot>/`, made in `bower-blender` | the timber: one mesh and one centre line per member |
| the plant simulator and its viewer | `../Horti-code-ture` (or `HORTI_DIR`) | growing a planting, and drawing each plant |
| the factory drawings' projection | `bower-factory`, `engine/projection.js` | the view the drawing is set up in |

## Run it

Needs Node 24 and `npm install` done once in `Horti-code-ture`. Nothing is installed here.

```bash
npm run convert                              # releases/six-bay-v1 -> scenes/six-bay-v1/bower.json
npm run assemble                             # the order the joints allow -> scenes/six-bay-v1/assembly.json
npm run grow -- six-bay-v1 trained 10        # ten tended years -> scenes/six-bay-v1/runs/trained-10y/
npm run grow -- six-bay-v1 trained 10 7 --specimen=2 --name=specimens-10y                            # planted standing 2 m
npm run grow -- six-bay-v1 trained 10 7 --specimen=2 --plan=planting-24.json --name=specimens-24-10y   # and twice as many
npm run compare                              # the runs side by side: timber held, and what a visitor sees
npm run studio                               # the drawing, on http://localhost:5310
```

The line of time has three parts: the design (every centre line drawn), the assembly (each member brought on to
its line, in red while it moves), and ten years of growth from the day of planting.

In the studio: **Play** or drag the line of time; Space plays, the arrow keys step along it (further with Shift).
Drag to turn the drawing, scroll to come closer. `?day=3363&view=inside` opens on a day of growth and a view,
`?build=0.5` half-way through the assembly; `?bare` hides the controls for a still. The chooser at the top
right swaps between the plantings that have been grown on this machine (`?run=specimens-10y`), and **Timber / Ink**
between timber in its own colour, greying with the years, and the plain ink drawing (`?timber=ink`).

## What is where

- `pipeline/convert.mjs` writes the simulator's input from a snapshot, and adds what the building model does not
  hold yet: four planting beds at the foot of each pier, and where a visitor stands. A bed has to be within 1.5 m
  of something to climb, so on this building beds can only be at the piers.
- `pipeline/assemble.mjs` reads the joint schedule for what has to be in place before what (a member lapped
  under another, a member housed into another) and puts the members in an order that keeps to it. It is the order
  the joints allow, not a method statement: lifting, propping and scaffold are not worked out.
- `pipeline/grow.mjs` runs the simulator and keeps the record of every stem, leaf and flower with its days, the
  design report, and `run.json` (which simulator commit, what it warned of, what it assumed).
- `pipeline/reseat.mjs` moves each supported stem on to the timber faces that are really there. The simulator's
  input cannot say which way a section is turned; the snapshot can.
- `pipeline/thin.mjs` drops the points of free-hanging shoots that a drawing of a whole room cannot show.
- `scenes/<snapshot>/planting.json` is the planting: which plant goes in at which bed. `planting-24.json` is the
  same with a second plant beside each. The simulator plants every climber as a 0.6 m cane; `--specimen=2` has
  it go in standing 2 m, and changes nothing else about how it grows.
- `pipeline/compare.mjs` sets the runs of a scene side by side.
- `studio/` is the drawing.

## What this is not

The growth is a scenario on stated assumptions, not a forecast: the statement under the drawing travels with every
picture made from it. The planting is a trial arrangement, not a planting design. The timber is concept geometry.
