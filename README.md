# Design Studio

An offline workspace for designing engineering and IT infrastructure together.
Enter equipment, interfaces, networks, services, identity structure, DNS, and
application dependencies once, then generate consistent diagrams and retain the
decisions behind the design.

The application is one self-contained HTML file. It needs no installation,
server, account, build step, or internet connection.

## Start the application

1. Download this repository using **Code → Download ZIP**, or clone it:

   ```sh
   git clone https://github.com/BenjaminSisko/design-studio.git
   cd design-studio
   ```

2. Open [`design-studio/index.html`](design-studio/index.html) in a desktop browser.
3. Inspect the fictional `SAMPLE-` design or choose **New project** to start clean.
4. Export **Project JSON** or **Portable HTML** to keep an editable handoff.

The HTML application does not require Python or Node.js. Browser storage is
local; exported files carry the model, attachments, and revision history between
machines. Use one active editor for a meeting.

## What it includes

- Rack elevations, network membership, interfaces, ports, and entered connections.
- Shared services, hosting, dependencies, ownership, and lifecycle status.
- Identity implementation choices, domains and realms, directory containers,
  nested groups, membership, and intended application access.
- DNS zones, records, aliases, referenced targets, and resolver/forwarding
  relationships entered as logical design records.
- Applications and applicable license dependencies, with team-entered endpoints,
  protocols, ports, license managers, and redundancy plans.
- Logical service maps, focused identity/DNS/application views, custom diagram
  selections and positioning, SVG exports, and printable meeting packs.
- Evidence attachments, comments, alternatives and rationale, build tasks, named
  revisions, before/after comparisons, and restoration with a safety snapshot.
- LLM context export, validated change proposals, and a file-based editing CLI.

The sample keeps platform choices, real addresses, and endpoints undecided.
Displayed paths describe entered design information and lifecycle status; they
do not discover, configure, or verify live infrastructure.

## Work with an agent or LLM

**Start with [`AGENTS.md`](AGENTS.md).** It explains the repository architecture,
model invariants, editing workflow, and checks an agent should run. The detailed
file contract and examples are in the [LLM exchange guide](design-studio/LLM_GUIDE.md).

For an LLM without filesystem access, use **LLM exchange** in the application:
export the context, request a change-set JSON, import it, review the before/after
values, and apply it as a recorded revision. A stale project ID or fingerprint is
rejected. Design Studio does not call an LLM provider or require an API key.

For a file-capable agent, the optional Python command-line tool uses only the
standard library:

```sh
python3 tools/design_studio.py init --sample --output workspace/project.design.json
python3 tools/design_studio.py validate workspace/project.design.json
python3 tools/design_studio.py summary workspace/project.design.json > workspace/context.json
python3 tools/design_studio.py apply workspace/project.design.json workspace/changes.json --output workspace/revised.design.json
python3 tools/design_studio.py render workspace/revised.design.json --output workspace/revised.design.html
```

`summary` emits LLM context with the model, record schemas, instructions, and a
guarded change-set template. `apply` validates the complete result and preserves
before/after revisions. `render` embeds the project in another standalone HTML
copy. JSON is the canonical interchange format.

## Repository map

| Path | Purpose |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Entry point for coding agents and file-based design agents |
| [`design-studio/index.html`](design-studio/index.html) | Complete offline application and embedded JavaScript model core |
| [`design-studio/README.md`](design-studio/README.md) | Operator and meeting guide |
| [`design-studio/LLM_GUIDE.md`](design-studio/LLM_GUIDE.md) | JSON envelopes, schema fields, proposal examples, and LLM workflow |
| [`design-studio/sample-model.json`](design-studio/sample-model.json) | Fictional service-oriented demonstration model |
| [`tools/design_studio.py`](tools/design_studio.py) | Standard-library CLI and mirrored schema validation |
| [`tests/test_design_studio.py`](tests/test_design_studio.py) | Migration, model, proposal, export, and cross-language tests |

## Development checks

With Python 3.14 and Node.js available, run:

```sh
python3 -m unittest discover -s tests -v
python3 tools/design_studio.py validate design-studio/sample-model.json
git diff --check
```

Node is used for the JavaScript/Python parity check and is optional for CLI use.
Without Node, that one test is skipped. CI runs all checks with both runtimes.

The source template contains no saved real project or evidence. Keep actual
infrastructure designs in the ignored `workspace/` directory or a separate
private repository. Local snapshots, exported files, and Git commits are
different history mechanisms; local author labels are not authenticated approvals.
