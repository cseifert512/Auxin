# Room through time: isolated delivery experiment

Open `/designx/v8/tests/room-time-hybrid/` using `node deck/serve.mjs`. The existing presentation, source films, scene renderer, growth runs and frozen releases are unchanged. This test has no incoming link from the deck.

The question is whether a programmed orbit can keep the timber sharp in live 3D while delivering the costly planting as compressed pictures. The same room, camera path and 51-second scenario clock are used throughout. There is no free camera in this experiment.

## The three versions

- **Original film:** the existing 1600 × 900 low-orbit film, referenced in place. It was rendered at 12 distinct frames per second and encoded at 24 fps.
- **Hybrid:** the source timber, assembly and lighting functions run in the browser. A 12 fps film carries a 1280 × 720 vegetation/shadow image and its coverage mask in two side-by-side halves. No growth record, plant meshes or biological simulation are loaded by the reader.
- **Compressed film:** the existing complete film reduced to 1280 × 720, 12 fps, H.264 CRF 25 with the slow encoding preset. This control separates ordinary media-encoding savings from the effect of hybrid rendering.

Switching versions preserves the current moment. Only one version runs. The comparison page reports loading and playback observations from the reader's own browser and can export them as JSON. These observations include cache effects; use the repeatable measurement script for controlled cold loads.

## What the baked layer contains

For each moment the source studio renders a full scene and a second image with plants hidden. A difference mask identifies the vegetation and its effects on timber and ground shadows. The overlay carries the full scene's colour only where that mask applies. This preserves the source view's occlusion without importing plant geometry into the reader's browser.

This is a view-specific compositing approximation. A 3/255 colour-difference threshold rejects small precision differences, a one-pixel dilation protects edges, and the layer is downsampled. Colour outside an expanded mask is replaced with paper to avoid paying to encode invisible timber. The browser uses the decoded film frame's camera and growth moment, so geometry cannot run ahead of the baked foliage.

The live timber uses the existing shader, material-ageing, assembly order, stable member IDs, environment and 4096-pixel timber shadow map. The 12–14 second ink-to-timber transition is preserved. The canvas is 1600 × 900 at pixel ratio 1; it scales to the available page width. Texture/mask softness and approximated shadow boundaries need visual review. This delivery test does not establish growth, structural or daylight performance.

The original film advances its wind clock an extra time while rendering the ink transition. The new bake preserves the growth dates and camera but can have a different wind phase. Original-versus-hybrid pixel differences therefore include wind motion. The source-versus-client **bare timber** comparison isolates camera/material alignment; the new full-frame intermediates isolate compositing quality. Repacking uses the saved quality-94 full-frame JPEGs as its colour source.

## Provenance and boundaries

- Building: frozen `six-bay-radial-v1`, copied byte-for-byte into this test's assets.
- Growth: existing `trained-10y` scenario, rendered offline through the source studio.
- Camera and timeline: the existing `v8/assets/time-experiment` low orbit; assembly 0–12 seconds, planting to 13 seconds, growth to the last summer at 49 seconds, final hold to 51 seconds.
- Authored walking figures belong to the presentation overlay and are omitted equally from all three test versions.
- Asset sizes/hashes and display settings are recorded in `manifest.json`. Full-frame render intermediates, probes and browser screenshots stay in the ignored `.qa/` folder.

## Reproduce

Run these from this folder, or prefix their paths from the repository root:

```powershell
node build-renderer.mjs
node bake.mjs --probe
node bake.mjs --render --no-encode
node bake.mjs --repack
node measure.mjs
node measure.mjs --slow-playback=1 --budget=360
```

The bake imports the existing studio and reads source data; it writes only in this test folder. Run one rendering/measurement process at a time on this laptop. The bake needs the installed local Chrome/Edge, the simulator's Vite/Three.js, and the existing sharp/FFmpeg dependencies. Local browser/server access must be permitted.

`--repack` rebuilds an existing set of packed frames with colour outside the foliage mask cleared, then re-encodes. `--encode` re-encodes existing frames. `--manifest` refreshes delivery sizes after a renderer rebuild. The unchanged compressed control is reused after checking its recorded hash; `--reencode-control` forces it to be rebuilt. These commands do not alter the source media.

The measurement script serves the files through its own local HTTP server, supports video byte ranges, gzips text, and disables caches. It tests each version in a fresh browser context under unthrottled conditions and a 5 Mbps / 80 ms profile. It captures five matched moments and samples seven seconds of mature-growth playback. GPU identity, received bytes, decoder drops, stalls and timing qualifications are recorded in `.qa/measurement-latest.json`.

The optional `--slow-playback=1` also plays the whole sequence over the throttled connection. A quick first frame does not establish that the film will keep playing without buffering.

The display callback rate is not unique animation frames per second. Renderer timings measure CPU command submission, not GPU completion. A local headless test is evidence about this device and configuration, not a guarantee about public hosting or other computers.
