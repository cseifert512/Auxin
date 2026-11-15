# For Daniel: running the pier study's growth runs

Clay's laptop is busy rendering. This is the part of the work that is computation, not rendering,
and can run on another machine. It needs no Blender.

## What it is

The six-bay Bower's piers were opened: each pier's legs stand in a ring 2.4 m across instead of
bunched at 0.7 m. The study asks what that does for the climbers planted at the feet. It makes the
building at six openings, grows the same planting on each for ten years in the plant simulator, and
reads back the sun at each planting place, the way in between the piers and whether the buried
footing still fits.

One script does all of it. What comes out feeds a deck drawing that shows the same pier grown
twice, legs together and legs apart.

## What you need

- Git, Node 24 or newer, Python 3.11 or newer (standard library only).
- About 1 GB of free disk and 8 GB of free memory. One step asks Node for up to 6 GB.
- About 20 minutes on a recent laptop.

## Steps

```bash
git clone https://github.com/cseifert512/Auxin.git
```

```bash
cd Auxin/Horti-code-ture && npm install
```

```bash
cd ../bower-blender/studies/inhabited-room && python study_openings.py
```

On a Mac, use `python3` in the last line.

The script prints one line for each opening as it finishes, then one `lightened` line for each. For
every opening it:

1. makes a trial building (`releases/trial-meadow-pier-*`; the design's own opening uses the real
   snapshot `releases/six-bay-meadow-v2`),
2. sets its pier out and writes the simulator's inputs, including the site: latitude, which way the
   building is turned, the trees and wall that shade it,
3. grows 24 climbers for ten years (about a minute, and about 110 MB of `growth.json`),
4. makes a light copy of the run for drawing (about 7 MB).

Nothing it writes is tracked by git except `ground/openings.json`.

## What to check

These are the figures from Clay's machine. Yours should match, or come very close: the runs use
one fixed seed.

| Ring of legs, radius | Way in | June sun on a climber | Stem by year 10 | Footing draft's rules |
|---|---|---|---|---|
| 0.34 m | 4.92 m | 1.25 h | 2,182 m | not met |
| 0.6 m | 4.83 m | 1.51 h | 2,153 m | not met |
| 0.8 m | 4.41 m | 3.14 h | 2,031 m | not met |
| 1.0 m | 4.00 m | 3.58 h | 2,112 m | met |
| 1.2 m, the design | 3.60 m | 4.05 h | 2,081 m | met |
| 1.4 m | 3.19 m | 4.50 h | 2,088 m | not met |

```bash
git diff --stat -- ground/openings.json
```

No output means your results are identical to the committed ones. If the file changed, say so when
you send the files back: it would mean the simulator does not give the same run on two machines,
which we would want to know.

## What to send back

The six light copies, about 42 MB together. From the top of the repository:

```bash
tar -czf pier-study-runs.tgz drawings-in-code/scenes/trial-meadow-pier-034/light drawings-in-code/scenes/trial-meadow-pier-060/light drawings-in-code/scenes/trial-meadow-pier-080/light drawings-in-code/scenes/trial-meadow-pier-100/light drawings-in-code/scenes/trial-meadow-pier-140/light drawings-in-code/scenes/six-bay-meadow-v2/light bower-blender/studies/inhabited-room/ground/openings.json
```

Send `pier-study-runs.tgz` to Clay. Unpacked at the top of his checkout, the files land where the
drawings read them. Please do not commit the runs: they are left out of git on purpose.

## If something stops

- The script stops at the first failing step and prints that step's last output. Send that text.
- `python study_openings.py --keep` carries on without growing again the openings whose runs are
  already there.
- `npm run lighten` running out of memory: close other programs and run it again with `--keep`.

## What stands behind the numbers

One run and one seed for each opening. The simulator's species numbers are provisional
assumptions, each labelled with its status in `Horti-code-ture`. The light model is provisional and
the latitude (51.5 degrees) is assumed. The footing rules are a draft in this study
(`set_out_meadow.py`), not engineering. The study's own account is in
`bower-blender/studies/inhabited-room/README.md`, "How far to open the pier".

A possible next job, not asked for yet: the same study on several seeds, to see how much of the
difference between openings is the opening and how much is chance.
