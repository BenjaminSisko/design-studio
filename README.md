# Design Studio

An offline architecture workspace for engineering and IT infrastructure. Enter
physical equipment, interfaces, networks, services, identity, DNS, application
communications, requirements, and verification records once. Generate linked
visuals, inspect design gaps and modeled failure impact, compare alternatives,
and carry the decisions through implementation.

The application is a **single self-contained HTML file**. Open the committed
file directly in a desktop browser; no installation, server, account, build,
API key, or internet connection is required.

## Start

1. Download **Code → Download ZIP**, or clone the public source:

   ```sh
   git clone https://github.com/BenjaminSisko/design-studio.git
   cd design-studio
   ```

2. Open [`design-studio/index.html`](design-studio/index.html).
3. Explore the clearly fictional `SAMPLE-` project or select **New project**.
4. Open **Architecture workbench** to follow a network path, inspect service
   deployments, review communication requirements, and track the build.
5. Export **Project JSON** or **Portable HTML** after meaningful edits.

Use one active editor during a meeting. Browser saves are local; exports carry
the model, assets, scenarios, baselines, and revision history between machines.

## Architecture workbench

| Workspace | Design activity |
| --- | --- |
| **Network path** | Follow the L2/L3 interface diagram and trace entered access/trunk VLAN membership, physical links, routes, and routing/security contexts. |
| **Service deployment** | Separate a service capability from its deployed instances, hosting, endpoints, resolver assignments, and failure domains. |
| **Communication** | Record required source/destination flows, initiator, purpose, protocol/ports, zones, enforcement devices, and intended policy. |
| **Design checks** | Review model findings such as address conflicts, incomplete network paths or policy, stale references, missing ownership, and shared failure dependencies. |
| **Failure impact** | Select failed items and inspect affected dependencies and the assumptions behind the model-based result. |
| **Requirements & tests** | Connect requirements and decisions to tasks, acceptance procedures, recorded results, observations, and evidence. |
| **Scenarios & baselines** | Branch alternatives; preserve installed, target, accepted, and verified snapshots; compare actual record values. |
| **Build pack** | Generate model-based handoff material: address plans, port/cable information, communication matrices, requirements, and implementation work. |

The **Architecture** canvas offers **Overview**, **L2 / L3 interfaces**, **Rack
Studio**, **Service deployment**, and **Dependencies** tabs. Overview presents
the broad network/service picture; L2/L3 shows individual interface cards,
tagged/untagged network relationships, and routing contexts. The logical-service, identity/group, DNS,
application/license, custom-diagram, evidence, comments, and decision workspaces
remain connected to the same stable records. Export generated SVGs and printable
review material for the team.

These views describe entered design information. A displayed path, modeled
policy match, failure analysis, baseline label, or completed task does not
establish live reachability or a passing acceptance test. Record verification
results and supporting evidence explicitly.

## Your existing Rack Studio, integrated

The physical rack workspace reuses the Rack Studio renderer and public catalog:
**5,835 models, 9 embedded front-panel images, and 20 generic network stencils**.
Search the catalog, choose equipment, place it in a rack by its lowest occupied
U, move it within the rack, or upload a panel image. Equipment shares its ID
with interfaces, hosts, services, decisions, and evidence throughout the app.
Multiple racks and hosted/VM inventory are supported.

Models without a bundled image use synthetic panels. The full 857 MB original
image tree is not required. Existing Rack Studio layout JSON remains an import
option; new equipment can be added directly from the integrated catalog.
[Third-party notices](THIRD_PARTY_NOTICES.md) document reuse and licenses.

## Work standalone or with an LLM

Start an agent with [`AGENTS.md`](AGENTS.md). The detailed contract is in the
[LLM exchange guide](design-studio/LLM_GUIDE.md).

**LLM exchange** exports the current model, schemas, findings, and a guarded
proposal template. Import the returned JSON, review before/after values, then
apply it as a revision. Project ID, model fingerprint, and scenario scope keep
proposals tied to their starting design. Design Studio does not contact an LLM
provider; the exchange is file based.

A file-capable agent can use the optional CLI:

```sh
python3 tools/design_studio.py init --sample --output workspace/project.design.json
python3 tools/design_studio.py validate workspace/project.design.json
python3 tools/design_studio.py summary workspace/project.design.json > workspace/context.json
python3 tools/design_studio.py apply workspace/project.design.json workspace/changes.json --output workspace/reviewed.design.json
python3 tools/design_studio.py render workspace/reviewed.design.json --output workspace/reviewed.design.html
python3 tools/design_studio.py lint workspace/reviewed.design.json
python3 tools/design_studio.py report workspace/reviewed.design.json --kind handoff --output workspace/handoff.md
```

Use the exported schemas for exact field names and preserve complete records,
stable IDs, history, assets, and unknown facts. JSON is canonical. CLI analysis,
report, scenario, and baseline workflows are described in the
[LLM guide](design-studio/LLM_GUIDE.md); the
[operator guide](design-studio/README.md) covers meetings and day-to-day editing.

## Source and reproducible build

| Path | Purpose |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Agent entry point, invariants, and delivery checks. |
| [`src/`](src/) | Authoring modules, schema, rack renderer/catalog, and HTML/CSS shell. |
| [`tools/build_app.py`](tools/build_app.py) | Inline authoring modules into the single-file deliverable. |
| [`design-studio/index.html`](design-studio/index.html) | Generated offline application; ready to open. |
| [`design-studio/sample-model.json`](design-studio/sample-model.json) | Fictional demonstration model. |
| [`tools/design_studio.py`](tools/design_studio.py) | Project validation, LLM changes, analysis, reports, and portable rendering. |
| [`tools/build_rack_catalog.py`](tools/build_rack_catalog.py) | Optional import of public assets from a Rack Studio checkout. |
| [`tests/`](tests/) | Model, analysis, schema parity, renderer, and export checks. |

Develop in `src/`, then regenerate and verify the distributable:

```sh
python3 tools/build_app.py
python3 tools/build_app.py --check
npm ci
npm test
python3 -m unittest discover -s tests -v
python3 tools/design_studio.py validate design-studio/sample-model.json
git diff --check
```

Python's standard library builds the application. `npm ci` installs the pinned
development-only DOM test tooling; `npm test` exercises UI workflows. Have Node
available for those checks and JavaScript parity/analysis/renderer tests; check
test output for skips. The production application has no runtime dependencies
and does not require Python, Node, or an npm installation.

Keep actual infrastructure exports and attachments in ignored `workspace/` or a
separate private design repository. Local scenarios and revisions are not Git
commits or automatic synchronization. Concurrent editing, authenticated
approvals, team access control, discovery, provisioning, and live network tests
need separate systems and procedures.
