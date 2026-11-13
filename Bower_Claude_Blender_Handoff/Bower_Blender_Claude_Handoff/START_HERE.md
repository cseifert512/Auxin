# START HERE — Bower / Claude / Blender

This bundle contains:
- `BOWER_V1_CLAUDE_HANDOFF.md` — agent brief, project architecture, milestone acceptance tests.
- `reference_images/orchard_approach_reference.jpg` — visual architecture reference.
- `horticulture/Plants_and_the_shape_of_a_Bower.pdf` — constraints report from plant-growth research.

## Human setup

1. Install Blender **5.2 LTS** from https://www.blender.org/download/lts/.
2. In **Claude Desktop**, go to **Customize > Connectors**, find **Blender** and select **Add** (https://claude.com/connectors/blender).
3. Open https://www.blender.org/lab/mcp-server/ beside Blender. Drag its install link into Blender **twice**, approving the Blender Lab extension repository on the first pass and installing the add-on on the second.
4. In Blender **Edit > Preferences > Add-ons**, find and enable **BlenderMCP**, and start the MCP server.
5. Keep Blender open and allow the Claude connector. Ask Claude to verify the active scene and generate one centreline beam before starting the full project.

The official source requires Blender 5.1+; using 5.2 LTS satisfies it. Anthropic's tutorial: https://academy.claude.com/tutorials/using-the-blender-connector-in-claude

## First message to Claude

"I am building Bower's first modular procedural architectural model. Read `BOWER_V1_CLAUDE_HANDOFF.md`, examine the reference photo and the plant-growth report, and follow the staged gates exactly. Connect to my open Blender scene using the official connector. Start with Gate 0 ONLY; do not create the pavilion until we have verified the connection and reviewed the proposed control topology. All geometry must be regenerable from editable control parameters, with stable centreline data for the plant simulator. Do not call any paid generation tools."

## Not supplied

The actual plant simulator repository is **not** included. Its exporter must be written only after Claude can inspect the repository's real working examples and parser. Add any other image references in `reference_images/` before sharing the bundle.
