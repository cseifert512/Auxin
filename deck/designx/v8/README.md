# Edition 08: one continuous story

Open the [story map](http://localhost:5312/designx/v8/story-map.html) or the [working deck](http://localhost:5312/designx/v8/). Run `node deck/serve.mjs` from the repository root if needed.

This is the replacement v8 requested on 15 November 2026. It uses v7's visual system, viewer and all eighteen original scenes in a new sequence, with two additional drawing spaces. The previous 21-slide v8 and the standalone v9 narrative are superseded. V7 and earlier editions are unchanged. No repository-root document was changed by this revision.

## The story

We encounter a Bower and understand why someone would want it. Looking more closely reveals the relationships that give it its character. Designing those relationships raises decisions that computation helps us explore. Those decisions produce particular parts and manufacturing requirements. Bringing the place into someone's garden requires a credible commission and delivery process. Its continuing life requires care, and that experience informs the next Bower.

`story.js` is the slide-by-slide editorial map. Every entry records the source v7 slide, its role, what stays, the intended drawing, current evidence status and the connection to the next slide. `story-map.html` presents that map with links to each slide. The deck's Notes include the same connections and drawing briefs alongside the original source notes.

The twenty-slide sequence is: Bower → customers and desire → space/light/time → ground → design decision → computational checks → variability → manufacturing process → forming/measurement/machining → commission/build/grow → care → shared design knowledge → project learning cycle → information flow → references and demand → reusable capability → team → construction at scale → future possibilities → the first Bower and the means to make many.

## What is present

- The original customer settings and film, named conversations with their discussion status, the proposed £65,000 commission credited against the build, fixed build price and annual care.
- A computational consequence drawing using the scene owner's existing handoff, the assembly/learning lenses, technical and commercial learning diagrams, both founder theses, team and future imagery.
- Daniel's original factory map, fourteen stations, Form/Measure/Machine views, playback, notes and print drawings. This uses the v7 factory system, without a second implementation.
- **A room through time** occupies slide 03, with one Inside view by default. Above / Approach / Inside selects a crop of the same pre-rendered Time frame. Light selects one growth stage across a midsummer day. Space retains its draggable panorama. Ghost people and birds are authored diagrammatic occupation, not simulated behaviour. Play, pause, scrub, hide inhabitants or enlarge; mode, view, panorama and moment persist.
- The existing pier comparison and an explorable four-stage study opened within the presentation. Selecting a moment pauses it; enlargement and return preserve its timeline position.

## New drawings and current limits

Slide 04 reserves the section of the same inhabited room, making root space, footing, water provision, supports and care access legible. Slide 11 reserves establishment and care in that room. These production briefs are visible in the working deck; it is not a finished submission while those compositions remain unresolved.

First arrival and annotated-section drafts are copied in `assets/scene-drafts/` and linked from the story map. They came from `bower-blender/studies/inhabited-room/views/arrival.png` and `section.png`, visually inspected on 15 November. Their baseline is `six-bay-radial-v1`; site and ground arrangements are provisional proposals in the source study. They show the same room with no furniture. The section needs a presentation composition and contains more annotation than a slide can comfortably carry. V7's opening and closing artwork remains until the new scene is ready for those compositions. The care view remains to be made.

The older pier animation on slide 05 compares existing variants. Slide 06 now reads the newer coordinated `inhabited-room` export: its baseline/opened-pier images, layer masks, stable threshold anchors and quantities. Plant support, Entrance, Making and Designer review expose different consequences of those authored alternatives. The 4.87 m / 3.61 m threshold widths come from that export's timber geometry; they are not the older pier sweep's centreline widths or physical measurements. The opened footing remains unengineered and its exported clearance flags remain visible. Nothing is recomputed during playback. Integrated plantability and cost evaluators remain proposed.

Slide 09 recomposes Form / Measure / Machine with the same compact heading, selection hierarchy and bottom control edge. Daniel's source geometry, animation timing, notes and fourteen-station explorer are untouched. Slide 14 adds an inspectable trace to the complete learning flow: an assumption or target, future observations, validation and possible rule revision. The trace is an authored explanation, not working automation.

## Drawing decisions

| Drawing | Pitch question | Treatment |
|---|---|---|
| Time, Space, Light | What changes about inhabiting this room? | Recompose as one selected view, with a separate authored occupation layer. This was the representative drawing developed and visually checked first. |
| Computational consequences | What else changes when we open the pier? | Replace generic text switches with the existing scene export and its evidence; keep the designer's review explicit. |
| Factory map and operations | How can varied parts become an assembled room? | Preserve the live SVG studies and notes; reframe the selected operations and connect each to assembly. |
| Shared learning object | What questions concern the same place? | Preserve the clearly labelled earlier assembly study pending the scene owner's coordinated replacement. |
| Project cycle | How can a project produce useful knowledge? | Preserve the overview as a bridge between care and detailed evidence flow. |
| Learning flow | How does checked evidence reach a design decision? | Add pause, scrub and node selection to the existing complete diagram. |

The room/site/plant–footing study, generators, exports, stable IDs and releases remain owned by their existing subsystems. This revision only reads their published handoff. Root documents and earlier deck editions are unchanged by this work.

## Files and verification

`index.html` loads unchanged v7 dependencies and v8 modules. `growth-player.js/css` owns the single-view raster player, lazy frame requests, six-frame cache and authored occupants. It never downloads plant geometry. `consequences.js` reads the scene export; `drawing-tools.js` supplies the explanation clock; `learning-trace.js` and `manufacturing.js` adapt presentation. `drawings.css` gives these drawings common framing. `edition.js` integrates them, while `studies.js` retains the older pier player. Load failures retain a labelled fallback or previous drawing, with retry.

The growth stills copy `time-26.webp` and `time-30.webp` from `04-plants-make-space-timber`. The pier stills copy `bare-was-room-00.webp` and `bare-now-room-00.webp` from `shaded-at-the-pier`. Dynamic exports use `/designx/pieces/`. A standalone publication must include **04-plants-make-space-timber**, **shaded-at-the-pier** and **inhabited-room**. No dependency points at v9. If publishing into Bower_Web, preserve that checkout's v8/baseline living files, which protect its newer v7.

The **Print view** link opens this edition's static reading layout. No new PDF has been exported. Direct file opening shows static images; use the local server for interactions. The browser check in `scripts/check.mjs` uses the installed Playwright/Chromium, routes local assets from disk for sandboxed QA, and writes private screenshots/results to ignored `.qa/`.
