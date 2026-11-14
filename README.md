# project-auxin

Bower's building, its plants and the drawings of both, in one place.

A Bower is a timber lattice that plants and gardeners finish. Designing one means designing three things together: the structure, the planting, and how the two change each other over years. This repository holds all three, so that a change to the building, the growth it leads to and the drawing that explains it can be made and checked as one piece of work.

## What is here

| Folder | What it is | Start with |
|---|---|---|
| [`bower-blender/`](bower-blender/README.md) | The building model: rooms, bays and crowns edited as a small plan, with the roof, the timber, every joint and the planting hardware regenerated from it. Python, drawn into Blender. | `bower-blender/README.md` |
| [`Horti-code-ture/`](Horti-code-ture/README.md) | The plant simulator: a library of climbers and a model of how they occupy a structure over years, with its own viewer. TypeScript. | `Horti-code-ture/README.md` |
| [`drawings-in-code/`](drawings-in-code/README.md) | The drawings: a snapshot of the building, a planting grown on it, and both drawn along one line of time. Node, with a three.js studio. | `drawings-in-code/README.md` |
| [`releases/`](releases/README.md) | Named, frozen snapshots of the building. The building model writes them and the drawings read them in place. | `releases/README.md` |

## How they fit together

```
bower-blender  ──writes──▶  releases/<snapshot>/  ──read by──▶  drawings-in-code  ──runs──▶  Horti-code-ture
      ▲                                                                │
      └────────────── scores from a grown planting ───────────────────┘
```

The building model owns everything that is physically part of the building. The simulator owns how plants behave and knows nothing of any one building. The drawings join the two and invent neither.

Everything in a snapshot is concept geometry, and most of the simulator's plant numbers are labelled assumptions. Nothing here is a structural, fabrication or horticultural check.

## Where it came from

Until 14 November 2026 these were three repositories: `bower-blender`, `horti-code-ture` and `drawings-in-code`. Each was brought in under its own folder with its whole history, so `git log --follow` on any file reaches back through the move, and the `model/six-bay-v1` tag still points at the commit that snapshot was made from.

Work that was still open in one of the old repositories can be brought across afterwards. From the top of this repository:

```bash
git fetch <path or URL of the old repository> <branch>
git merge -X subtree=<its folder here> FETCH_HEAD
```

For example, a branch of the old plant simulator merges with `-X subtree=Horti-code-ture`.
