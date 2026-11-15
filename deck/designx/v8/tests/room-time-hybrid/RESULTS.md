# Room through time: first comparison

Measured 15 November 2026 in Chrome on this laptop's Intel UHD graphics. The existing presentation was not changed by this experiment.

The compressed complete film was the strongest delivery option in this run. The hybrid successfully combines live timber with baked vegetation and shadows, but requires a larger download and more preparation before playback.

| Version | Delivery assets | Animation ready at 5 Mbps | Wall time to play the 51-second sequence | Buffering events |
|---|---:|---:|---:|---:|
| Original film | 39.60 MB | 0.96 s | 65.27 s | 28 |
| Hybrid | 25.36 MB | 9.84 s | 51.30 s | 0 |
| Compressed film | 11.20 MB | 0.93 s | 51.16 s | 0 |

The hybrid total includes its 19.46 MB packed vegetation/mask film, 4.49 MB timber model, supporting geometry/configuration data and 0.70 MB renderer bundle. The film totals are their media files. All exclude the shared comparison page and poster. These are raw file sizes; network measurements also account for text compression and progressive media requests.

The compressed film is about 72% smaller than the original. It retains the complete camera and scenario sequence, at 1280 × 720 and 12 unique frames per second. The original was drawn at 12 unique frames per second and encoded at 24 fps. The hybrid uses a 1600 × 900 live canvas with a 1280 × 720 foliage layer at 12 fps.

## What was checked

- Fresh browser contexts, HTTP caches disabled, a local HTTP server with byte ranges and gzip text, 5 Mbps download and 80 ms added latency. The 51-second playback measurement starts after the first animated frame is ready. A still is visible while each version prepares.
- All three versions played the dense seven-second sample without stalls or dropped decoder frames under unthrottled local conditions.
- The hybrid's median CPU render-submission time in that sample was approximately 2.1 ms. This is not a GPU execution measurement.
- The live timber matched the source base image pixel-for-pixel at 6, 28, 42 and 49 seconds. The ink/material transition at 13 seconds differed by an average of 0.095 on a 0–255 colour scale.
- The final foliage composite was visually inspected at the matched moments. The silhouette, timber overlap and shadows remain coherent; foliage and shadow edges are softer than the source.
- Direct links to a chosen moment, version switching, play/pause, scrubbing, cancellation during a quick switch and the mobile layout passed. The original film's SHA-256 hash remained unchanged.

## Limits and decision

This is one exploratory run on one laptop, not a cross-device performance guarantee. Public hosting, DNS/TLS and other networks were not measured. The test omits the separately authored walking figures equally from all variants. The new bake can have a different wind phase from the original film; original-versus-hybrid pixel differences therefore include motion as well as compression.

The hybrid preserves crisp live architectural geometry and could support future architectural interaction. For the presently agreed programmed orbit, the compressed film starts sooner, transfers less and avoids buffering in this test. Keep the original slide intact while reviewing visual quality in the separate comparison.

The reproducible procedure is in [README.md](README.md). Detailed machine-local records, request accounting and screenshots are in the ignored `.qa/` directory; a compact measurement record is saved in [results.json](results.json).
