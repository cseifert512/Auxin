# BOWER V1 — Computational Architectural Design Brief

**Date:** 13 November 2026  
**Audience:** Claude Desktop (connected to Blender using the official Blender Lab MCP connector)  
**Status:** Development brief; not a completed engineering or horticultural design  
**Primary goal:** Create **one convincing, editable and reproducible multi-bay Bower prototype** whose geometry can eventually grow into adjoining rooms and be evaluated by the climbing-plant simulator.

## 0. Instructions to the Claude agent

Read this document and inspect the accompanying photographic reference and horticultural report before starting. **Do not begin by generating a detailed mesh or making a render.** First verify your live Blender connection and agree a minimal model architecture and a first build milestone. Treat the reference photo as a *design-language reference*, not a reliable dimensional record or an exact construction drawing. Preserve the distinction between visually plausible geometry and verified fabrication/structural feasibility.

You are the computational architectural designer and implementer. The human designer retains the final judgment on form. Work incrementally, show clear evidence of progress, and stop at defined review gates. The work must be reproducible from source files, not dependent on a single opaque `.blend` file or a chat history.

**Hard cost constraints:** Do not call Higgsfield, paid image/video/3D generation, cloud rendering, or any other credit-consuming service without explicit permission. Do not autonomously explore numerous variations. Use Blender's fast preview tools and one design candidate at a time. Favor deterministic code and small, inspectable tests over prolonged tool-calling.

## 1. Why this is being developed

Bower designs architecture whose permanent structure is a curved timber lattice and whose appearance and use evolve as climbing plants colonise it. The current need is one developed Bower form that can be edited intelligently and serve as the beginning of a reusable architectural design engine. The longer-term ambition is that a designer can add or delete a vaulted face/bay, extrude a room, intersect or join chambers, move control points, and have the architectural envelope and timber lattice regenerate coherently.

**Do not confuse the three deliverables:** (1) a Bower with architectural character, (2) an *editable topological model* controlling rooms and openings, and (3) an *exportable physical member-centreline model* for plants and fabrication checks. They must remain separate but linked.

## 2. Inputs, references and limits of the reference image

- `reference_images/orchard_approach_reference.jpg`: one perspective image of a multi-bay timber pavilion in an orchard. Use for architecture/ambience/form language, **not for exact dimensions**.
- `horticulture/Plants_and_the_shape_of_a_Bower.pdf`: ten-page report dated 13 November 2026, compiled from a 16-species climbing-plant library and simulator. Important quantitative values are largely modelling assumptions, not verified construction limits.
- An existing horticultural growth-simulator repository exists but **is not included in this bundle**. When access is provided, inspect its working `examples/` structure file and parser before writing any exporter. Do not invent the simulator's data schema or claim integration until its tests pass.
- The designer may provide further reference views. Use them to clarify plan/section ambiguity; do not hallucinate the exact hidden geometry from one image.

### Observed architectural qualities to preserve

The picture suggests a clustered, non-rectilinear pavilion composed of deep pointed/ogival openings, curved timber ribs spreading and reconverging, layered secondary members, and an elevated crown or lantern-like ring. The composition feels organic and animated, yet organised at global and local scales. Timber is substantial, not a delicate net; voids have carefully composed proportions; open arches create access without losing enclosure. The planted landscape is part of the long-term architecture, not a decal.

**Do not implement:** rectangular gridded walls, a generic geodesic dome, random woven noodles, gratuitous intersecting timbers, or a highly detailed non-editable sculptural mesh. Avoid chasing the photographic planting or visual realism while the geometry is unresolved.

### Starting design parameters — explicitly provisional

- Overall prototype: approximately **11 m across** and **6 m high**, for convenient initial scale only.
- Single primary room with **5-ish nonidentical vaulted bays** and an elevated open crown. Exact bay count, proportions and crown geometry are subject to visual review; do not claim they are inferred exactly from the image.
- Several accessible, deep arch openings; one principal approach view plus interior and aerial cameras.
- Curved glulam **primary ribs**, coherent **secondary plant-support lattice**, distinct **small-diameter cables** where needed.
- Geometry may be asymmetric, but should display controlled, recurring families and legible load paths rather than random variation.
- No final glulam sizes, bending radii, foundations or structural capacities are specified. Treat such values as provisional test parameters requiring fabrication/engineering verification.

## 3. Required geometry architecture: three linked levels

### Level A — Room graph and editable control topology (source of truth)

Represent **rooms, bays, boundary vertices/edges, openings and connections** as stable semantic entities with IDs. Store editable parameters in a human-readable `design.json` or equivalent Python-dataclass-plus-JSON representation. This is the **source of truth**, not final render meshes.

Required concepts:

- `Room`: room ID, footprint/control polygon, crown/apex/oculus controls, elevation, parameter overrides, portal relationships.
- `Bay` or `Face`: persistent ID, parent room, boundary segment or sector, type (`open`, `lattice`, `partly_closed`, `shared/portal`), optional local control handles.
- `Connection`: room A/room B and their associated bay IDs, desired portal/opening, resolved shared boundary and continuity status.
- `ControlHandle`: editable point/curve control with stable identity and clear units.
- `DesignOperation`: `add_bay`, `remove_bay`, `move_handle`, `set_bay_type`, `add_room_from_bay`, `connect_rooms`, `regenerate`.

Be precise about meaning: "add/delete faces" initially means editing the **semantic room/bay control topology**, **not** modifying arbitrary faces on a final dense timber mesh. A simple Python command or minimal Blender UI panel is acceptable for V1. Direct Blender Edit Mode face manipulation can follow once the system is robust.

**Critical**: a room joining another room is not achieved by applying a Boolean to finished glulam. Merge/resolve the **control envelope and shared portals first**, then regenerate the connected member system. For the first prototype, a shared portal between adjacent bays is sufficient; support for arbitrary overlapping freeform rooms is a later milestone and must not be represented as finished.

### Level B — Architectural envelope / vaulted surface family

Generate an editable and lightweight envelope from Level A: deep pointed entrances, smooth rise into a high crown, differing bay heights, clear access zones and plausible joins. Use patch/loft/spline constructs as appropriate. Hide this envelope in final visualisations, but retain it as an inspectable guide.

Checks:
- The envelope has no unexplained tears, twisted patches or abrupt tangency changes at adjacent bays.
- The crown or oculus remains geometrically valid after changing height/diameter/bay count.
- An opening can be widened or closed without unrelated bays collapsing.
- The surface represents architectural **space**. It is not automatically a structural membrane or the literal timber.

### Level C — Member-centreline network and geometry

Generate each primary rib, secondary lath and optional cable from its own centreline with a stable ID and section metadata. **Preserve original centrelines as editable curves or edge chains.** Use a bevel, swept cross-section, Blender Curve-to-Mesh or Geometry Nodes only to display the physical timber. Never rely on reverse-engineering centreline data from solid meshes.

For each member store at least:
- Stable ID and parent room/bay/assembly; primary vs secondary vs cable.
- Ordered 3D centreline sample points or analytic curve controls in **metres**.
- Width/depth and orientation for timber, or diameter for cables.
- Start/end locations and meaningful connection-node IDs; distinguish real mechanical connections from visual crossings.
- Estimated total length, minimum sampled bend radius, approximate volume/quantity, geometry warnings.
- Optional material/lamination family, fabrication family and revision ID.

Default units and axes match the simulator report: **metres, Z up, Y north**. Curve sampling/export density must be explicit and independently configurable, and sampled geometry should be checked against the Blender scene.

Recommended Blender collections:
`00_CONTROLS`, `10_ENVELOPES`, `20_PRIMARY_CENTERLINES`, `21_PRIMARY_MESHES`, `30_SECONDARY_CENTERLINES`, `31_SECONDARY_MESHES`, `40_CABLES`, `50_PLANTING_POINTS`, `60_CONTEXT`, `70_CAMERAS`, `80_DIAGNOSTICS`.

## 4. Climbing-plant requirements (from supplied horticultural report)

The report's most consequential point: **the way each plant attaches determines which support diameters and geometries it can use.** The simulator currently assumes:

- Twining stems (e.g. wisteria, akebia, honeysuckle, star jasmine) need graspable supports or deliberate ties. A large glulam member is not automatically an effective climbing support.
- Clematis leaf petioles and *Vitis coignetiae* tendrils need **fine cable/battens**; the report's 8–12 mm grasp values are especially uncertain, and require physical validation.
- Ivy and climbing hydrangea can cling to broad faces but can enter/obscure joints, requiring inspection.
- Climbing roses require tie points; mature wisteria should be trained with adjustable ties rather than allowed to constrict slender members.
- The report suggests many shoots cannot bridge an unsupported opening substantially wider than about **0.5 m** unaided; this is a *design-direction heuristic*, not a universal spacing requirement. Pattern spacing should be assessed **along likely shoot travel paths** rather than naively applying an indiscriminate dense grid.
- Rooting locations are part of the plan and should be represented as Blender empties; a plant's route to the crown is measured **along member paths**, not vertical height alone.
- Wisteria flower racemes hang below overhead members; the *W. floribunda* 'Macrobotrys' profile suggests ~0.6–1.1 m in the report's model. Account for clear headroom rather than assuming every arch can be densely planted overhead.
- Winter coverage must be evaluated by specific camera view. The project target in the report is **25–40% evergreen coverage in key winter views**; the report's reference dome did not achieve this in its approach view. This is a design objective, not a guarantee.
- Gardener access to high routes and inspection of joints are architectural constraints. Mature plant weights, wind, climate/warmth and frost are **not** simulated or verified in the current model.

**Do not model all 16 species initially.** For V1, define a few illustrative planting positions and support requirements, then adapt to whichever species the actual simulator can load. For reliable integration, preserve source confidence labels (measured, literature-based, assumption, unmodelled) for relevant thresholds.

See supplied report pages 3–5 (attachment, gap reach, rooting), 7–9 (evergreen views, clearance, maintenance), and 10 (model limitations and centreline export interface).

## 5. Interface with the existing plant simulator

The simulator does **not** need solid rendered timber meshes. It needs per-member centrelines plus section, role, cables and planting/camera metadata. The user supplied this intended interchange contract:

**Blender -> simulator**
- Timber: each member's ordered centreline and width/depth or diameter, with primary/secondary classification.
- Cables: distinct centrelines with diameter.
- Planting: ground points (Blender empties) and plant species assignments when available.
- Viewpoints: Blender cameras.
- Optional walls/trees/buildings and headroom/exclusion volumes.
- Axes: metres, Z up, Y north.

Build a small Blender export script **after reading the actual `examples/` structure file and parser in the simulator repo**. The exported file must match the true schema exactly. Include deterministic ordering, stable IDs, validation and a sample fixture checked against the viewer's “A design…” tab. Avoid speculating about format, nesting or units of the currently unseen repo.

**Simulator -> Claude**: request or add a machine-readable results file once the one-way export works. Useful per-member metrics include attachment compatibility, support/cable deficit, route continuity, estimated seasonal coverage from each camera, occlusion of timber, planting zones, headroom conflicts, pruning/maintenance burden and unmodelled-data flags. Add threshold/warnings with a reference to member IDs. Do not fabricate this output if the existing simulator doesn't yet provide it.

**Simulator -> Blender** 3D plant geometry is a *later* project. Current static simulator views are enough for the first architectural optimisation pass. A foliage renderer is not a prerequisite to a valid centreline integration.

## 6. Fabrication and engineering checks, without false precision

For V1, create automatic **geometric** checks, visibly labelled exploratory:

- Finite, nondegenerate curve samples; no unexpected zero-length members.
- Minimum sampled local bend radius by member and section; compare with a configurable supplier-specific limit **only when sourced**.
- Section intersections and collisions; differentiate crossings from specified joints.
- Distinct connection node IDs, locations, timber cut/interface candidates.
- Member count, total length, approximate wood volume, unique section and curvature families.
- Soil access, planting support connectivity, access clearances and areas requiring inspection.

Do **not** claim structural adequacy, safe span/load capacity, viable joinery or a constructible engineered glulam system from the Blender model alone. Engineering, fabrication and horticultural validations remain necessary.

## 7. Phased execution plan and acceptance criteria

**Gate 0 — Connection sanity test. STOP after test.**
- Inspect open Blender session through MCP; report exact Blender version and scene objects.
- Create a single curved centreline object and its swept rectangular beam profile, preserving the centreline.
- Report whether tool execution succeeded. Do not generate the pavilion until this works.

**Gate 1 — Single room control system. STOP for design review.**
- Implement the semantic graph/data model and generate only one room's **control geometry + light envelope**.
- Parameter controls: room scale, height/crown, approximate bay count, width of openings, one or more asymmetry controls.
- Provide plan, front perspective, interior and overhead screenshots from the actual Blender scene. Show control geometry in another view.
- Demonstrate: moving a single control point; deleting a bay; adding one bay; regenerating without rebuilding manually.
- Preserve `design.json`, generated script and `.blend` file.

**Gate 2 — Room connection. STOP for design review.**
- Add a second, smaller room through one selected bay/portal. Keep room IDs and controls independent.
- Resolve the shared interface, remove the inappropriate internal boundary/opening barrier, and form a legible transition. Avoid simply overlapping solid meshes.
- Demonstrate moving/resizing the second room, then regenerating without loss of the first room.
- Diagnose and report unresolved topology/continuity problems openly. Arbitrary room intersections are not a V1 promise.

**Gate 3 — Structural centreline grammar. STOP for review.**
- Generate a *restrained, legible* system of curved primary ribs and a separate coherent secondary lattice for ONE selected room composition. Avoid random members and unnecessary complexity.
- Every member is a named/typed centreline with display geometry derived from it.
- Produce plan, section, axonometric, worm's-eye and unplanted entry views; show a wireframe/centrelines-only view.
- Export a per-member diagnostic/quantity CSV, and flag severe bend radii or ambiguous crossings.

**Gate 4 — Plant simulator export. STOP at working integration.**
- Inspect simulator repo `examples/` and schema. Write `export_to_simulator.py` using the actual format.
- Add Blender empties for root points, distinct cable curves and three evaluation cameras.
- Validate that simulator viewer loads generated file; fix axis, sampling and naming issues.
- Test at least one planting and report actual viewer metrics (not invented outcomes).

**Gate 5 — Improvement iteration. Time-boxed.**
- Try **one** intentional geometric improvement based on simulator feedback, not a large unbounded optimisation search.
- Save before/after designs and compare both architectural legibility and planting metrics. Clearly describe trade-offs.
- Do not begin photorealistic planting, video or third-party generative asset work without authorisation.

## 8. Output package and reproducibility

Use a normal project directory with readable source and snapshots. The first version should contain:

```
bower-v1/
  README.md
  design.json                  # authored control topology / parameters
  scripts/
    generate.py               # rebuild scene from design.json
    operations.py             # add bay, remove bay, add room, connect rooms
    diagnostics.py            # member/curve diagnostics
    export_to_simulator.py    # after actual repo schema has been inspected
  output/
    bower_v1.blend
    member_schedule.csv
    scene_inventory.json
    simulator_structure.*     # use real extension, not a guessed one
  views/
    01_plan.png
    02_entry.png
    03_interior.png
    04_axo.png
    05_centrelines.png
  reference_images/
  horticulture/
```

- The user must be able to close and reopen Blender and regenerate the exact same scene from data and code.
- Use fixed numerical parameters and consistent IDs for repeatable outputs; no random seed unless intentional and explicitly fixed.
- Build new generated collections without deleting unrelated scene objects.
- Save milestones with descriptive checkpoint filenames or commits.
- Distinguish editable source controls from generated (regenerable) output. Do not make arbitrary manual edits to generated meshes that will be lost on rebuild.

## 9. Interaction, reporting and token discipline

**Work in narrow chunks.** For each gate: (a) state what you will change in at most a short paragraph, (b) run the minimum tools, (c) test via Blender, (d) report what truly succeeded/failed, (e) stop for human review. If a tool fails, debug a minimal repro rather than restarting the entire project. Do not overwrite a functioning stage with an experimental redesign.

Use simple viewport captures, wireframes and orthographic projections for feedback. Never spend paid generation credits without explicit approval. Prefer testing geometry with assertions and scene inventory over repeated visual guessing. Avoid redrawing a fixed mesh from the supplied perspective image; develop a design grammar.

**Safety:** The official Blender MCP server runs model-authored Python with no sandbox. Assume unrestricted code can harm data; work on copies in a dedicated, low-trust environment, with backups, and do not execute unexpected downloads, deletion, shell commands, or network requests without permission.

## 10. First agent response and exact first task

On receiving this brief and reference files, do **not** immediately build the whole Bower. Respond with:

1. Connection status and exact Blender version.
2. A concise proposed control topology, the geometry generation approach, and what remains ambiguous in the single reference image.
3. A small directory/file plan and the minimum first test.
4. The results of **Gate 0 only**: a 5 m curved member centreline with a separate preview mesh, visible in Blender, with named objects.
5. The next single action you recommend for Gate 1, and a clear point at which to ask for architectural feedback.

**Goal statement:** Develop one controlled architectural language that can be grown into multiple rooms, while retaining exportable glulam/trellis/cable centrelines and the ability to learn from a climbing-plant simulation. The enduring asset is the procedural design system, not merely the first image.

## 11. Technical sources and reference provenance

- Claude Academy official Blender connector tutorial: https://academy.claude.com/tutorials/using-the-blender-connector-in-claude
- Blender Lab official MCP server and security notice: https://www.blender.org/lab/mcp-server/
- Blender 5.2 LTS: https://www.blender.org/download/lts/
- Blender Curve-to-Mesh manual: https://docs.blender.org/manual/en/5.2/modeling/geometry_nodes/curve/operations/curve_to_mesh.html
- Horticultural constraints: accompanying PDF, particularly pages 3–5, 7–10. Its plant-grasp and growth assumptions are not independently verified by this brief.
- Reference photo: accompanying `orchard_approach_reference.jpg`. The actual hidden plan, structural capacity, dimensions and joinery cannot be recovered reliably from this one viewpoint.
