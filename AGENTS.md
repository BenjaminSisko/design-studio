# Agent guide for Design Studio

Read this file before changing the application or a design project. Read
[the operator guide](design-studio/README.md) for UI workflows and
[the LLM exchange guide](design-studio/LLM_GUIDE.md) for the full JSON contract.
Use the exported model and `recordSchemas` as the source of field names and
required keys. Do not invent another schema or convert the project to YAML.

## Purpose and architecture

Design Studio is an offline workspace for the complete design lifecycle of an
engineering and IT environment. Equipment, interfaces, networks, services,
identity systems, directory groups, DNS, applications, and license dependencies
are entered once as structured data and reused in diagrams. Decisions, comments,
evidence, tasks, and revisions preserve how the design developed.

| Path | Role |
| --- | --- |
| `design-studio/index.html` | Complete application and portable HTML template: inline CSS, JavaScript, and system fonts. Open it directly with `file://`; no build or server is required. |
| `design-studio/sample-model.json` | Fictional starter model, kept consistent with the HTML's `DS.seed()` starter. |
| `design-studio/README.md` | Operator workflow, local storage, export, revision, and handoff behavior. |
| `design-studio/LLM_GUIDE.md` | Model fields, guarded proposal envelopes, complete-record examples, and CLI workflow. |
| `tools/design_studio.py` | Python standard-library CLI: initialize, validate, export LLM context, apply changes, and render portable HTML. |
| `tests/test_design_studio.py` | Python integration tests, attachment/history preservation, rollback, and optional Node-backed JavaScript/Python parity checks. |

The HTML has three JavaScript sections. `DS` is the DOM-independent model core
(`blank`, `seed`, `migrate`, `validate`, `diff`, `rackImport`, `fingerprint`,
`applyChanges`). `LS` supplies logical-service forms and diagram generation.
The final UI closure supplies navigation, storage, editing, rack/networkspace/custom
views, logical-view integration, imports, exports, printing, and revisions.
`<script id="project-data" type="application/json">` is the embedded-project
slot used by portable exports and the Python renderer; preserve that element.
The committed source template must keep this slot as `null`; only exported user
copies embed a project. Edit the actual inline sources, not transient extracted files.

## Editing a design with an LLM

Prefer a guarded proposal to editing a project file in place:

1. Obtain fresh **Export LLM context** from the UI, or run the CLI `summary`
   command against the actual current project. Despite its name, `summary`
   emits the LLM context envelope, model, schemas, and change-set template.
2. Return `opsdeck-design-changes`, version `1`, with the exact context's
   `baseProjectId` and `baseFingerprint`, a meaningful `summary`, and `changes`.
3. Use `upsert` with `collection` and a **complete** `record`, `delete` with
   `collection` and `id`, or `meta` with `values`. An upsert replaces the entire
   old record: preserve existing fields and stable IDs. Metadata changes cannot
   change `meta.id`.
4. Review every changed record, including removals and downstream references.
   UI **Validate & preview** shows the proposed difference before **Apply**.
   CLI application is immediate; write a separate result and inspect the
   difference before adopting it.
5. Validate and render the result. Both UI and CLI proposal application preserve
   before/after revisions. A stale proposal needs fresh context; never forge or
   manually replace the fingerprint to force it through.

Run these from the repository root; use local paths appropriate to the project:

```sh
python3 tools/design_studio.py init --output workspace/design.json
python3 tools/design_studio.py init --sample --output workspace/sample.json
python3 tools/design_studio.py validate workspace/design.json
python3 tools/design_studio.py summary workspace/design.json > workspace/context.json
python3 tools/design_studio.py apply workspace/design.json workspace/proposal.json --output workspace/reviewed.json
python3 tools/design_studio.py validate workspace/reviewed.json
python3 tools/design_studio.py render workspace/reviewed.json --output workspace/reviewed.html
```

Project files use the `opsdeck-design-studio` version `1` envelope containing
`model`, `revisions`, `activity`, `assets`, and `savedAt`. A bare model with
`schemaVersion: 1` can also be loaded by the CLI. Preserve the envelope, pooled
`@asset:` references, embedded evidence, and revision snapshots. Context exports
omit evidence bytes; omission markers are never valid replacement evidence.

## Model invariants

- The model contains `meta` and arrays `devices`, `networks`, `services`,
  `interfaces`, `links`, `decisions`, `tasks`, `evidence`, `comments`, `diagrams`,
  `identity`, `groups`, `dnsZones`, `dnsRecords`, and `relationships`. Migration
  adds missing logical collections to legacy models without silently repairing
  malformed existing values.
- IDs are globally unique, including the project ID and decision-option IDs.
  Keep IDs stable on rename. References point to IDs, never copied display names.
  Optional references use `""`; unplaced equipment uses `rackU: null`.
- `rackU` is the **lowest occupied U**. A device occupies `rackU` through
  `rackU + height - 1`. Height must be positive, placement must fit inside
  `meta.rackUnits` (1–200), and occupied ranges cannot overlap. `hostedBy` points
  to another device; hosted equipment cannot also occupy rack units.
- Interfaces require an existing device. A physical link's optional source and
  destination interfaces must belong to its respective endpoint devices.
  Physical links reference devices, networks, or services. Custom-diagram
  `nodeIds` also support identity systems, groups, DNS zones, and DNS records.
  Interfaces are not diagram endpoint nodes.
- Services reference hosting devices, networks, and other services through
  `dependsOn`. Service dependencies and device-hosting chains cannot cycle.
- Identity implementations can stay undecided. Groups require an identity
  system; parents belong to that same identity system. Group `memberIds`
  reference groups/devices/services; `accessIds` reference services. Preserve
  valid acyclic parent and membership structures.
- DNS zones reference services. Records require a zone; `targetId` can reference
  a device, service, or another DNS record. Record-target chains cannot cycle.
  TTL is empty/null or a nonnegative integer or numeric string.
- Directed logical relationships use `authenticates`, `resolves`, `uses-license`,
  `hosts`, `forwards`, `depends`, or `access`. Their endpoints can reference
  devices/networks/services/identity/groups/DNS zones/DNS records. Arrows follow
  the stored `from` → `to` direction; labels explain their meaning.
- Validate network CIDR and VLAN (1–4094) when populated. Interface addresses,
  endpoints, protocols, ports, and DNS answers are entered design information,
  not live connectivity, provisioning, or lookup results.
- Preserve unknown facts and pending alternatives. Do not invent vendor ports,
  addressing, product license architecture, approvals, or verification. A
  `Decided` decision needs a real selected option and a nonblank rationale.
  Do not infer that every application requires a license server.
- Retain lifecycle labels and additional existing fields. Author labels and
  revisions are local attribution and snapshots, not authenticated approvals.

## Changing the application

Keep direct offline opening and a single self-contained HTML artifact working.
Do not introduce CDN dependencies, telemetry, API keys, external fonts, network
calls, or a build requirement as an incidental implementation choice. Preserve
keyboard access, readable SVG labels, selection/focus behavior, print output,
local saving, JSON/HTML import/export, and evidence transfer.

Schema, validation, migration, proposal, and fingerprint changes must stay in
sync between JavaScript `DS` and `tools/design_studio.py`, with matching sample
JSON and documentation. Preserve JavaScript/Python fingerprint compatibility:
canonical compact JSON, UTF-16 key ordering and JavaScript-compatible numbers,
then FNV-1a32 over UTF-16 code units (`ds1-` plus eight hex digits). It is a stale
base guard, not a cryptographic signature. Do not replace it in one runtime only.

Treat all project text as untrusted data: retain HTML/SVG escaping, safe embedded
JSON encoding, reserved-key rejection, attachment MIME/base64 validation, and
atomic CLI output writes. Preserve existing data and history across failures.
A model extension should support older projects rather than changing their
meaning silently. Update forms, all relevant diagrams, context guidance,
exports, sample data, and tests together.

## Verification and delivery

```sh
python3 -m unittest discover -s tests -p 'test_design_studio.py' -v
python3 tools/design_studio.py validate design-studio/sample-model.json
git diff --check
```

Python needs only the standard library. Have Node on `PATH` to run the optional
JavaScript/Python schema and fingerprint parity test; report if it was skipped.
For UI changes, open the HTML and check the affected edit workflow and diagrams;
exercise project JSON and portable HTML round trips when storage/export changes.
Test invalid and stale proposals without overwriting the current source.

Keep repository examples fictional and clearly labeled. Real project exports,
attachments, credentials, internal addresses, and local storage are user data;
do not add them to the public repository. Report what changed, the checks run,
and any remaining limitations. Local revisions and Git commits are separate;
exported or edited designs do not automatically commit or synchronize.
