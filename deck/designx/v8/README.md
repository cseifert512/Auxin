# v8: edition 07 with the drawings in

The first version of ours. It is still the deck: the same viewer, the same 16:9 slides, the same words and order as edition 07. What is new is that the dynamic drawings made in `drawings-in-code` are in it.

Open it with `node deck/serve.mjs`, then http://localhost:5312/designx/v8.

## What changed from 07

Nothing of 07 is taken out. 07 has 18 slides; this has 21.

| Slide | What is there now |
|---|---|
| 4, Plants make space | The piece made for that space (`04-plants-make-space`) in place of the note. The slide's three tabs are the piece's three modes: Space is the room unrolled, Light is the floor through a midsummer day, Time is the building through design, assembly, planting and its seasons. Dragging and the line of time are the piece's own. |
| 5, Growth changes the geometry | The plate made for the Shaded room tab (`05-shaded-room`) in place of the note. The other two tabs keep 07's note: nothing is made for them yet. |
| 6, new | The vignette "The plants were shading each other" (`shaded-at-the-pier`), a slide to itself. |
| 7, new | The vignette "The clinging plants found the joints" (`found-the-joints`), a slide to itself. |
| 8 | 07's slide 6, Can we make it? Can it grow?, as it was. |
| 9, new | "Grown again" (`06-grown-again`): the same pier grown three times. |
| 10 to 21 | 07's slides 7 to 18, as they were. |

Three choices made here that are Clay's to overrule:

- **Slide 4 opens on Time**, not Space. The piece was made to open on Time, as the first sight of the building.
- **The two vignettes follow slide 5** as worked examples of it. Their own descriptions say only "not placed in the deck yet".
- **Grown again follows 07's slide 6 and replaces nothing.** Its description says it was made for slide 6, in place of the two checks side by side.

Words that are new: the last sentence under slide 4 (07 says "Growth drawings in development."; this gives the piece's own statement), the line under each added slide (each piece's own statement), and the speaker notes of the three added slides, which are each piece's own description from its `piece.json`.

## How it is made

- `index.html` is 07's, naming the edition and loading two more files.
- `edition.js` runs after 07's. It sets each piece into its slide, starts a piece from its beginning when its slide is shown and rests it when the slide goes (as the factory drawings do), passes the slide-4 tabs to the piece, and passes the deck's keys and the wheel on from inside a piece so the deck never gets stuck there.
- `pieces.css` is where the pieces sit, in the deck's own 1600 × 900 stage.
- The pieces are not copied here. `deck/serve.mjs` answers `/designx/pieces/<name>/` from `drawings-in-code/exports/deck/<name>/`, where they are made, so a piece that is remade shows in the deck at the next reload. `node deck/pieces.mjs` makes a copy beside the deck for when it has to stand alone.

## Not done

- **Paper.** Laid out for print (`?print=1`), slide 4 shows the piece's still and the vignettes their last moment, but this has not been looked at, and no PDF has been exported: the export scripts are still in the website's repository. The PDF button opens edition 07's.
- **Timber on slide 4.** The piece is the ink one. Its timber frames exist (`04-plants-make-space-timber`) but have no page of their own, and no Light mode.
- **Typefaces.** The vignettes and Grown again set their own words in Georgia and Segoe UI; the deck is Argesta and Safiro.
- **Not placed:** `a-room-through-time` (a slide of its own, not made in this repository yet). Slides 12 and 17 still hold 07's notes for a drawing.
- **Opening from a folder** needs `node deck/pieces.mjs` first, and has not been tried.

An earlier v8 was a page that was scrolled, with no slides. That was a misreading of what was asked and it was taken out; it is in the history at `0fd443d`.
