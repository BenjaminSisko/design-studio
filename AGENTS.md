# Agent guide for Design Studio

Read this file before changing the application or an infrastructure design.
[The operator guide](design-studio/README.md) describes the UI; the
[LLM guide](design-studio/LLM_GUIDE.md) defines the file exchange. Use fresh
exported `recordSchemas` and `architectureSchemas` for field names, required
keys, enums, and references. JSON is canonical; do not invent a second YAML
schema.

## Purpose

Design Studio is an offline architecture workspace spanning requirements,
physical racks, interfaces and networks, service deployment, identity and DNS,
application communications, design checks, failure analysis, implementation,
and recorded verification. A record is entered once and reused by generated
views and reports. Designs, scenarios, evidence, comments, decisions, and local
revision history travel together in exported project files.

The public repository contains source and fictional examples. Real designs,
internal addressing, attachments, credentials, and generated handoffs belong in
the ignored `workspace/` directory or a separate private repository. Do not copy
user data into public source, sample files, tests, screenshots, or commits.

## Authoring and generated files

| Path | Role |
| --- | --- |
| `src/model.js` | DOM-independent model, migration, validation, guarded proposals, fingerprints, fictional seed. |
| `src/architecture-schema.json` | Canonical descriptors for 17 architecture collections and extensions to existing records. |
| `src/logical.js` | Identity, DNS, application, and logical service views. |
| `src/analysis.js` | Model-based findings, paths, failure impact, and handoff reports. |
| `src/workbench.js` | Architecture workbench, collection forms, deployment and communication views. |
| `src/rack.js` | Reused/adapted Rack Studio physical renderer and inline stencil API. |
| `src/rack-catalog.js` | Generated public catalog, selected embedded front panels, and generic stencils. |
| `src/app.js` | UI, editing, scenarios and baselines, storage, revisions, attachments, imports, exports. |
| `src/shell.html` | HTML and CSS shell with module insertion markers. |
| `tools/build_app.py` | Standard-library reproducible build; inlines modules/schema into the distributable. |
| `design-studio/index.html` | Generated, self-contained application and portable-project template. |
| `design-studio/sample-model.json` | Fictional starter matching `DS.seed()`. |
| `tools/design_studio.py` | Project CLI, validation, proposal application, analysis, and handoff commands. |
| `tools/build_rack_catalog.py` | Optional maintainer import from the existing Rack Studio public asset tree. |
| `THIRD_PARTY_NOTICES.md` | Renderer provenance and full asset license notices. |
| `tests/` | Model, architecture, analysis, renderer, export, and cross-runtime checks. |

Edit authoring sources, then run `python3 tools/build_app.py`. Do not make an
application change only in generated `design-studio/index.html`.
`python3 tools/build_app.py --check` rejects a stale distributable. Running the
committed HTML requires no build, server, Python, Node, account, API key, or
internet connection. Keep `script#project-data` as `null` in the public template;
only exported user copies embed a project. Preserve offline `file://` operation,
portable exports, embedded third-party notices, escaping, keyboard access,
readable SVG, and print output. Do not add remote fonts, CDN dependencies,
telemetry, provider calls, or runtime asset fetches.

## Working on an infrastructure design

Prefer a guarded proposal:

1. Obtain fresh **LLM exchange → Export LLM context**, or use CLI `summary` on
   the actual project. Read the active scenario, model, schemas, findings, and
   change-set template.
2. Return `opsdeck-design-changes`, version `1`, retaining `baseProjectId`,
   `baseFingerprint`, and the provided `baseScenarioId` exactly.
3. `upsert` replaces a complete record. Preserve all existing fields and stable
   IDs; `delete` uses collection/ID; `meta` updates allowed values without
   changing `meta.id`. Repair dependent references in the same proposal.
4. Validate and inspect before/after values and downstream effects. The UI
   previews before application; CLI `apply` writes the proposed result
   immediately, so use a separate output file and inspect it.
5. Review diagrams and findings, record unresolved questions, and export the
   reviewed project. Stale model or scenario context requires a new export;
   never forge a fingerprint to force application.

A context is not a project backup. It omits evidence and custom front-panel
image bytes. Never submit an omission marker as evidence `data` or device
`panelImage`. Obtain the full project when a complete-record edit must preserve
those fields. Preserve pooled `assets`, `@asset:`
references, revisions, scenarios, active-scenario identity, baselines, and
activity in a project envelope. Local history, baseline labels, and Git commits
are different mechanisms. Author labels are entered attribution, not
signatures or authenticated approvals.

## Model invariants and architecture meaning

- Preserve `schemaVersion: 1` and compatibility with older projects. Migration
  adds missing collections and defaults without silently repairing malformed
  existing values or changing the meaning of an existing design.
- IDs are globally unique, including the project and decision-option IDs.
  References use IDs, not copied names. Empty optional references use `""`;
  unplaced equipment has `rackU: null`.
- Explicit `racks` use `units`; legacy projects fall back to
  `meta.rackName`/`meta.rackUnits`. `rackU` is the lowest occupied unit:
  `rackU` through `rackU + height - 1`. Height is positive, placement fits its
  rack, and ranges cannot overlap within that rack. `hostedBy` cannot cycle;
  hosted equipment does not also occupy rack units. A model catalog selection,
  custom panel, rack placement, and logical views reference the same device ID.
- Interfaces belong to devices. Physical-link endpoint interfaces must belong
  to the corresponding endpoint device. Preserve mode, untagged/tagged network
  references, aggregates/bonds, MTU, addressing, and gateways. Networks can carry
  routing-context and security-zone references. Routes are entered plans;
  presence of a route does not establish live routing behavior.
  Preserve both Architecture **Overview** and **L2 / L3 interfaces** views;
  the latter draws actual interface cards, tagged/untagged membership, and
  routing contexts. The workbench Network path also includes this diagram.
- A `service` is a capability, a `serviceInstance` is its deployment, and an
  `endpoint` is a listening/usable endpoint. Resolver assignments associate
  clients with endpoint IDs. DNS targets may reference endpoints as well as
  devices, services, and other DNS records. DNS target chains cannot cycle.
- `serviceDependencies` distinguish `Startup`, `Runtime`, `Optional`, and
  `Fallback`, with `All`/`Any` requirement semantics. Only explicit startup
  cycles are invalid; legacy `dependsOn` describes runtime dependency. Do not
  reinstate blanket rejection of all service cycles.
- Directory containment (`directoryObjects`), group membership (`groups` and
  `principals`), and application permission (`accessMappings`) are distinct.
  Keep containment and membership acyclic and within the proper identity
  system. Preserve legacy group fields during migration. AD, Red Hat IdM,
  other implementations, and undecided alternatives remain explicit choices.
- `flows` record communication needs: source, destination, initiating interface,
  protocol/ports, purpose, zones, enforcement devices, policies, and requirement
  links. `policies` record intended rules and ownership. A matching modeled
  policy or visible path is not proof that a live firewall permits traffic.
- `failureDomains` and deployment relationships support modeled impact and
  shared-dependency findings. Document assumptions and uncertainty. Do not
  describe dependency traversal as an outage simulation or verified failover.
- Requirements link decisions and affected records to acceptance criteria.
  Verification tests retain procedure, expected/actual results, performer,
  time, and evidence. A task marked `Done` is distinct from a test result
  `Pass`. Never invent observed values, successful tests, vendor ports,
  licenses, addressing, approvals, or evidence.
- `observations` preserve as-built values, source, observer, time, and evidence
  alongside the proposed records. Installed, target, accepted, and verified
  baseline labels point to saved revision snapshots; a label alone does not
  verify implementation or approve it.
- Scenarios are local design branches with stable scenario IDs, branched models,
  and preserved history. Compare actual before/after values, retain open
  alternatives, and keep proposals scoped to the current scenario.
- Decisions marked `Decided` require a selected option and rationale. Preserve
  alternatives and history. Do not assume every application or Atlassian
  deployment uses a license server.

## Rack Studio provenance

Use `RACK.search()`/`describe()` for the bundled 5,835-model catalog and
`RACK.draw()` for shared device records. Nine original front panels and twenty
MDI stencils are embedded; other models use synthetic panels until the operator
uploads a panel image. Do not add requests for the original relative image
paths. Only validated inline raster images are permitted for custom panels;
SVG and arbitrary URLs must not become executable image or markup sources.

Catalog/front images originate in NetBox devicetype-library (CC0). Stencils
carry the Pictogrammers/Apache 2.0 notice. Preserve full notices both in the
repository and standalone HTML. Import only public assets when regenerating;
never copy Rack Studio's user layout, network topology, addresses, or notes.

## Application changes and verification

Keep JavaScript and Python normalization, schemas, validation, proposals,
reference handling, and fingerprints consistent. Keep analysis behavior and
CLI/UI reports aligned. Fingerprints use canonical compact JSON, UTF-16 key
ordering and JavaScript-compatible numbers, then FNV-1a32 over UTF-16 code units
(`ds1-` plus eight hex digits). It is a stale-base guard, not a signature.

Treat project text as untrusted: retain HTML/SVG escaping, safe embedded JSON,
reserved-key rejection, attachment MIME/base64 validation, atomic CLI output,
and preservation of the prior design on failure. Extend forms, diagrams,
context guidance, sample data, reports, and tests together.

Run from the repository root:

```sh
python3 tools/build_app.py
python3 tools/build_app.py --check
npm ci
npm test
python3 -m unittest discover -s tests -v
python3 tools/design_studio.py validate design-studio/sample-model.json
git diff --check
```

`npm ci` installs pinned, development-only DOM tooling; `npm test` runs the
interaction harness. Neither the production HTML nor the Python CLI has npm
runtime dependencies. Have Node on `PATH` for the DOM, JavaScript/Python parity,
model-analysis, and renderer checks; report any skipped checks. Exercise changed UI workflows, guarded
proposals, project/portable-HTML round trips, and scenario/history/attachment
preservation. Distinguish automated checks from a browser walkthrough. Report
concrete changes, checks run, assumptions, and remaining limitations.
