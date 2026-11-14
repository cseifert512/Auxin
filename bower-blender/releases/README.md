# Snapshots

Each folder here is one named, frozen copy of the generated model, for other
work (drawings, the plant simulator) to build on while the geometry keeps
changing. A snapshot is never edited or overwritten: a refined model is a new
snapshot under a new name.

| Snapshot | Date | What it is |
|---|---|---|
| `six-bay-v1` | 2026-11-14 | One six-bay room, every joint milled. Source commit `342d327`, tag `model/six-bay-v1`. |
| `six-bay-radial-v1` | 2026-11-14 | The same room set out regularly: piers on one 6.2 m circle about the crown, equal bays, one apex height (4.6 m), so every bay is the same and each is its own mirror image. From `design/six_bay_radial.json`. Made on `5ee3b94` plus work not yet committed; not tagged yet. |

## What a snapshot holds

| File | For |
|---|---|
| `bower.blend` | Linking into another Blender file. Holds the generated collections only. |
| `bower.glb` | Any other tool. The timber meshes with their joints milled; glTF, so metres and +Y up. |
| `centrelines.json` | Per member: ID, family, section, sampled centreline and section direction, exact Bezier. Metres, Z up, Y north. |
| `members.csv`, `joints.csv` | The schedules. |
| `design.json` | The parameters the snapshot was generated from. |
| `manifest.json` | Name, source commit, counts, the checks at export, and a hash of every file. |

Everything is keyed by member ID (`R1.rib.ccw.03`, `R1.B2.arch.L`, ...). IDs
are persistent, so work attached to a member carries over to a later snapshot.

`centrelines.json` is this project's own neutral format. It is not the plant
simulator's input format.

The geometry is concept geometry: sections, joint depths and clearances are
provisional, and nothing in a snapshot is a structural, fabrication or
horticultural check.

## Using one in Blender

File > Link, choose the snapshot's `bower.blend`, open `Collection`, and link:

- `21_PRIMARY_MESHES` for the timber,
- `20_PRIMARY_CENTERLINES` for the centreline curves,
- `70_CAMERAS` for the view cameras, or
- `BOWER_V1` for everything generated.

Linked data stays tied to the file it came from and cannot be edited by
accident. Put your own work (people, plants, annotation, lighting) in your own
file around it.

## Moving to a newer snapshot

In the file that links it: Outliner > Blender File view > right-click the
library > Relocate, and pick the new snapshot's `bower.blend`. Everything
linked follows, and anything parented or keyed to a member by name stays with
it. The old snapshot stays here, so earlier drawings still open as they were.

## Making one

In Blender, with this repo's scene:

```python
import runpy
runpy.run_path(r"C:\BOWER\bower-blender\scripts\export_snapshot.py")["main"]("eight-bay-v1", commit="<git commit>")
```

The script rebuilds the scene from `design.json` first, so a snapshot is what
the source generates. Then commit the folder and tag it `model/<name>`.
