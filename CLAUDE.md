# project-auxin: working notes for agents

One repository for Bower's building model, its plant simulator and the drawings that join them. Until 14 November 2026 these were three repositories. Each is here under its old name, with its history, so one session can see and change all three.

## What is where

| Folder | Owns | Does not |
|---|---|---|
| `bower-blender/` | Everything that is physically part of the building, including what is fixed to it for plants: training lines, their fixings, the ground at the piers. Python, generated into Blender from `design.json`. | Hold plant biology (growth rates, what a species can grasp). |
| `Horti-code-ture/` | How plants behave: the species library, the growth simulator and its viewer. TypeScript. | Know anything about one particular building. |
| `drawings-in-code/` | Joining the two: converting a snapshot, growing a planting on it, scoring it, drawing and filming it. Node, with a three.js studio. | Invent parts of the building. |
| `releases/` | The hand-off: named, frozen snapshots of the building. Written by `bower-blender`, read in place by `drawings-in-code`. | Get edited. A snapshot is never changed or overwritten; a refined model is a new name. |

Authority runs one way: building, snapshot, plants, drawings. What comes back is scores from a grown planting, which inform the building's parameters.

## Each part keeps its own rules

Read the part's own notes before changing it. They still apply in full.

- `Horti-code-ture/CLAUDE.md`: the simulator's rules (no bare numbers about plants, vocabulary, conventions).
- `bower-blender/README.md`: the generator, its parameters, joints, training lines, the ground at a pier, tests.
- `drawings-in-code/README.md`: the pipeline, the studio, films and plates. `drawings-in-code/docs/for-the-building-model.md` is the planting side's brief for the building.
- `releases/README.md`: what a snapshot holds and how one is made.

## How the parts reach each other

- All paths between parts are relative (`../releases`, `../Horti-code-ture`), so the three folders keep these names.
- `drawings-in-code` has no three.js or build tool of its own: it uses the ones installed in `Horti-code-ture/node_modules`. Run `npm install` in `Horti-code-ture` first.
- The studio reads two fonts from a `Bower_Web` checkout beside this repository (`../Bower_Web` from the top). Nothing else is read from outside.
- A change that crosses parts, such as a new file in a snapshot and the code that reads it, goes in one commit.

## Running things

```bash
# building: no Blender needed for the tests (the list is in bower-blender/README.md)
cd bower-blender && python tests/test_snapshot.py

# simulator
cd Horti-code-ture && npm install && npm run check

# drawings: needs Node 24 and the simulator installed
cd drawings-in-code && npm run convert && npm run plant && npm run grow -- <snapshot> trained 10 7 --specimen=3
```

`.claude/launch.json` at the top starts the drawing studio on port 5310. Each part's own `.claude/launch.json` is for a session opened in that folder.

## Things that will catch you out

- Grown runs (`drawings-in-code/scenes/*/runs/*/growth.json`, over 100 MB each) and films are not in git. Remake them with `npm run grow` and `npm run film`.
- Files under `releases/` are stored byte for byte (`.gitattributes`), because each snapshot's manifest hashes them.
- The simulator's plant numbers are mostly provisional assumptions, each labelled with its status. Before resting a design change on a grown result, find which assumption drives it.
- This is developed on a 16 GB laptop. Run one heavy job at a time: the simulator's full test suite, a growth run, or a headless browser render.

## Git

- Branch `main`, remote `origin` (a public GitHub repository). Commit and push as work progresses.
- Write commit messages through a Bash heredoc (`git commit -F - <<'EOF'`).
- Later work from one of the three old repositories can still be brought in: see `README.md`.
