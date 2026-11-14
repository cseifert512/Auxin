# deck

The presentation the drawings are made for: "Buildings That Grow", Bower's deck for MIT DesignX × LUMA. This folder holds a copy of it as it stood on the website, and is where our own versions of it are made.

## What was copied

`designx/` is `public/designx/` from the website's repository (`C:\BOWER\Bower_Web`, branch `codex/designx`, commit `5253386`), copied on 14 November 2026. Every file is byte for byte the same as there, at the same path. `designx/README.md` is that repository's own account of the deck, edition by edition.

The deck that is live at bowerbuild.org/designx/v7 is the edition in `designx/v7/`. It is not a folder that stands alone. Each edition is written as changes to the one before, so v7 loads files from all of these:

| Where | What v7 takes from it |
|---|---|
| `designx/` (top) | The viewer (`deck.js`, `deck.css`), the first telling of the story (`slides.js`), shared scenes and pictures (`scenes/`, `assets/`) |
| `designx/2/` | The editorial look, scrolling between slides |
| `designx/3/` | The opening two slides, the logo, the three organisations' marks |
| `designx/4/` | The two typefaces and the dark drawing-board look |
| `designx/5/` | Daniel's factory drawings (`factory/`) and the code that shows them |
| `designx/v7/` | Slides 4, 5, 6 and 9 (`living.js`), the learning flow, the price, the five futures, and `edition.js`, which puts the eighteen slides in order |

The earlier editions' own pages came along too (they are small), so `/designx`, `/designx/2` … `/designx/6` still open for comparison.

## What was left behind

- **The PDFs of editions 01, 03, 04 and 05** (54 MB). They are exports of older editions and are still in the website's repository. Those editions' PDF buttons lead nowhere here. v7's PDF is here: `designx/v7/downloads/`.
- **The scripts that export a PDF and check an edition** (`scripts/designx/` there). They need Playwright and sharp, which this repository does not have, and they write into the website's folders. Until they are brought across, a PDF cannot be made from this folder.
- **The private notes** (`docs/private/designx/` there: the hand-off, the claims review, the speaker notes' source). They are kept out of that repository on purpose and this one is public, so they stay where they are.

## Opening it

```bash
node deck/serve.mjs
```

Then http://localhost:5312/designx/v8 for ours, or `/designx/v7` for the deck as copied. From the top of the repository, `.claude/launch.json` starts the same thing as `deck`. Nothing is built or installed. `serve.mjs` is about ninety lines and exists so that the deck sits at the same addresses as on the website, the customer film can be sought through, and an edit shows on the next reload.

Add `?print=1` to an edition's address to see every slide as it is laid out for the PDF. `#slide-04` goes to a slide.

## Our own versions

The copy is kept as it came so that it can always be compared with the website's. A version of ours is a new folder beside `v7`.

| Version | What it is |
|---|---|
| [`designx/v8/`](designx/v8/README.md) | The first of ours: one page that is scrolled, not a set of slides. Scrolling is the only control and it moves time: the room through its years, a day on its floor, seconds at the mill. |

`node deck/pieces.mjs` copies the pictures a version uses out of `../drawings-in-code/exports/deck/` into that version's folder. Run it again after a plate is remade.

Two things to know before starting one from the slides:

- The story is not in one place. `slides.js` holds the first edition's slides, and `2/edition.js`, `3/edition.js` and `v7/edition.js` each rewrite that list in turn. To find where a slide's words come from, search for them.
- Slides 4, 5 and 14 hold a note where a drawing goes. The drawings made so far for 4 and 5 are in `../drawings-in-code/exports/deck/`.
