# Edition 08: one continuous story

Open the [story map](http://localhost:5312/designx/v8/story-map.html) or the [working deck](http://localhost:5312/designx/v8/). Run `node deck/serve.mjs` from the repository root if needed.

This is the replacement v8 requested on 15 November 2026. It uses v7's visual system, viewer and all eighteen original scenes in a new sequence, with two additional drawing spaces. The previous 21-slide v8 and the standalone v9 narrative are superseded. V7 and earlier editions are unchanged. No repository-root document was changed by this revision.

## The story

We encounter a Bower and understand why someone would want it. Looking more closely reveals the relationships that give it its character. Designing those relationships raises decisions that computation helps us explore. Those decisions produce particular parts and manufacturing requirements. Bringing the place into someone's garden requires a credible commission and delivery process. Its continuing life requires care, and that experience informs the next Bower.

`story.js` is the slide-by-slide editorial map. Every entry records the source v7 slide, its role, what stays, the intended drawing, current evidence status and the connection to the next slide. `story-map.html` presents that map with links to each slide. The deck's Notes include the same connections and drawing briefs alongside the original source notes.

The twenty-slide sequence is: Bower → customers and desire → space/light/time → ground → design decision → computational checks → variability → manufacturing process → forming/measurement/machining → commission/build/grow → care → shared design knowledge → project learning cycle → information flow → references and demand → reusable capability → team → construction at scale → future possibilities → the first Bower and the means to make many.

## What is present

- The original customer settings and film, named conversations with their discussion status, the proposed £65,000 commission credited against the build, fixed build price and annual care.
- The original computational explanation, assembly/learning lenses, technical and commercial learning diagrams, both founder theses, team and future imagery.
- Daniel's original factory map, fourteen stations, Form/Measure/Machine views, playback, notes and print drawings. This uses the v7 factory system, without a second implementation.
- The existing Space/Light/Time growth drawing inside the original drawing space. Play, pause, scrub or enlarge it. Space retains native drag-to-turn. Timeline and selected mode persist across slide visits; the dragged panorama orientation resets when its frame unloads.
- The existing pier comparison and an explorable four-stage study opened within the presentation. Selecting a moment pauses it; enlargement and return preserve its timeline position.

## New drawings and current limits

Slide 04 reserves the section of the same inhabited room, making root space, footing, water provision, supports and care access legible. Slide 11 reserves establishment and care in that room. These production briefs are visible in the working deck; it is not a finished submission while those compositions remain unresolved.

First arrival and annotated-section drafts are copied in `assets/scene-drafts/` and linked from the story map. They came from `bower-blender/studies/inhabited-room/views/arrival.png` and `section.png`, visually inspected on 15 November. Their baseline is `six-bay-radial-v1`; site and ground arrangements are provisional proposals in the source study. They show the same room with no furniture. The section needs a presentation composition and contains more annotation than a slide can comfortably carry. V7's opening and closing artwork remains until the new scene is ready for those compositions. The care view remains to be made.

The pier animation compares existing variants. It is not yet a change propagated through the inhabited scene and its ground. The integrated plantability/cost checks remain proposed; playback does not recompute or validate those relationships. The map keeps these distinctions explicit.

## Files and verification

`index.html` loads the unchanged v7 dependencies, followed by `story.js`, `studies.js` and `edition.js`. `edition.js` reorders the scenes and fills the existing study spaces. `edition.css` adds the two drawing-brief layouts and study dialog; `studies.css` styles the controls.

The growth stills copy `time-26.webp` and `time-30.webp` from `04-plants-make-space-timber`. The pier stills copy `bare-was-room-00.webp` and `bare-now-room-00.webp` from `shaded-at-the-pier`. All dynamic exports are served through the existing `/designx/pieces/` route. No dependency points at v9.

The **Print view** link opens this edition's static reading layout. No new PDF has been exported. Direct file opening shows static images; use the local server for interactions. The browser check in `scripts/check.mjs` uses the installed Playwright/Chromium, routes local assets from disk for sandboxed QA, and writes private screenshots/results to ignored `.qa/`.
