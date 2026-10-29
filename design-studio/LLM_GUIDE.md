---
doc_id: OD-ARCH-006
title: Design Studio LLM Exchange Guide
type: guide
version: 2.0
owner: Design Studio maintainers
date: 2026-10-29
classification: UNCLASSIFIED
classification_color: "#15803d"
---

# Design Studio LLM exchange

The same canonical JSON model drives standalone editing, diagrams, model-based
analysis, scenarios, and implementation handoffs. An LLM can propose changes to
that model through guarded file exchange. Design Studio does not call an LLM
provider or require a provider key or network connection.

Read [AGENTS.md](../AGENTS.md) before changing source or project files. The
[operator guide](README.md) describes the UI. Use fresh context and its machine
schemas as the authority for required fields, types, enums, and references.

## Safe editing workflow

1. Open the intended project and scenario. Capture a useful starting revision.
2. Export **LLM exchange → Export LLM context**, or run CLI `summary` against
   the current project file.
3. Give the context and a concrete design request to the LLM. Ask it to use the
   supplied `changeSetTemplate` and preserve every base guard.
4. Import the returned proposal. Design Studio checks its project, model
   fingerprint, scenario scope, complete records, and resulting references.
5. Review actual before/after values, additions, deletions, findings, and effects
   on other views. Apply only the intended proposal. Application preserves
   before/after revisions.
6. Inspect the resulting diagrams and reports, then export Project JSON or
   Portable HTML as the reviewed handoff.

A change or scenario switch after context export calls for fresh context. Do
not change a fingerprint to force a stale proposal through. The fingerprint
protects the starting model; it is not a digital signature or authenticated
approval.

## Project, context, and proposal envelopes

An exported project uses the following versioned envelope. Empty objects below
are illustration placeholders, not complete models:

```json
{
  "format": "opsdeck-design-studio",
  "version": 1,
  "model": {},
  "revisions": [],
  "activity": [],
  "assets": {},
  "scenarios": [],
  "activeScenarioId": "",
  "baselines": {},
  "savedAt": "2026-10-29T12:00:00.000Z"
}
```

`model` has `schemaVersion: 1`, `meta`, and collection arrays. Migration adds
missing collections for older projects. The envelope preserves the active
model, scenario branches, baseline references to revision snapshots, history,
and pooled assets. Evidence and custom panel images can be pooled through
`@asset:` references. Use the application or CLI to load/save the envelope
rather than reconstructing it by hand. Do not discard unknown existing fields.

A context has `format: "opsdeck-design-context"`, version `1`, the current
`baseProjectId`, `baseFingerprint`, `baseScenarioId`, model, instructions,
`recordSchemas`, `architectureSchemas`, model findings, baseline context, and a
`changeSetTemplate`. It is designed for reasoning and proposing changes; it is
not a replacement project backup. Embedded evidence and custom front-panel image
bytes are omitted. Never upsert evidence `data` or device `panelImage` with an
omission marker. Use the actual complete project to preserve those bytes when
editing an equipment or evidence record.

Return a proposal using the exported template:

```json
{
  "format": "opsdeck-design-changes",
  "version": 1,
  "baseProjectId": "COPY_FROM_CONTEXT",
  "baseFingerprint": "COPY_FROM_CONTEXT",
  "baseScenarioId": "COPY_FROM_CONTEXT",
  "summary": "Explain the proposed design change and unresolved questions.",
  "changes": []
}
```

Copy the supplied scenario value exactly, including `""` if there is no active
branch. A proposal for a different scenario must not be applied merely because
the two branches currently contain similar records.

| Operation | Meaning |
| --- | --- |
| `{"op":"upsert","collection":"services","record":{...}}` | Add or replace a **complete** record using its stable ID. |
| `{"op":"delete","collection":"services","id":"existing-id"}` | Delete a record after handling dependent references. |
| `{"op":"meta","values":{...}}` | Update permitted metadata; `meta.id` cannot change. |

Upserts replace entire records, not individual fields. Start from the existing
record, retain fields that should survive, and include every required key. Add
linked records within the same proposal. A rename retains its ID. Return plain,
parseable JSON without Markdown fences, comments, trailing commas, executable
code, or a parallel YAML format.

## Schema and references

The context's `recordSchemas` lists complete-record requirements.
`architectureSchemas`, generated from
[`src/architecture-schema.json`](../src/architecture-schema.json), supplies field
types, accepted enums, reference targets, bounds, and optional-reference rules.
The schema expands the original model with seventeen collections:

| Collection | Architectural meaning |
| --- | --- |
| `racks` | Named rack capacity (`units`), site, and location. |
| `vrfs` | Routing contexts and optional route distinguishers. |
| `securityZones` | Named policy boundaries and ownership. |
| `failureDomains` | Shared dependencies such as power, rack, storage, or switching. |
| `routes` | Device/context, destination, next hop, interface, and metric. |
| `serviceInstances` | A capability's deployment, host/network, role, and failure domains. |
| `endpoints` | Service/instance/interface/network references plus address, DNS name, protocol, port, and role. |
| `resolverAssignments` | Client and ordered resolver endpoint references with search domains. |
| `serviceDependencies` | Dependent/required services, dependency kind, and availability rule. |
| `directoryObjects` | OU/container hierarchy in an identity system. |
| `principals` | User, service-account, or computer identities. |
| `accessMappings` | Principal/group → application service, role, resource, and permission. |
| `flows` | Required interaction, initiating source/interface, destination, protocol/ports, purpose, zones, enforcement, policies, and requirements. |
| `policies` | Intended source/destination/zone rule, action, protocol/ports, enforcement, rule reference, and owner. |
| `requirements` | Description, owner, priority, affected records, decisions, and acceptance criteria. |
| `verificationTests` | Linked requirements/records, procedure, expected/actual result, result state, performer/time, and evidence. |
| `observations` | As-built field/value, observed item, source, observer/time, and evidence. |

The original collections remain: `devices`, `networks`, `interfaces`, `links`,
`services`, `identity`, `groups`, `dnsZones`, `dnsRecords`, `relationships`,
`decisions`, `tasks`, `evidence`, `comments`, and `diagrams`. They carry the
following additions or compatibility rules:

| Area | Rules |
| --- | --- |
| Equipment | Preserve `model`, `panelImage`, `rackId`, `deviceKind`, `failureDomainIds`, `hostedBy`, and additional imported fields when present. |
| Interfaces | Preserve mode, untagged/tagged network IDs, aggregate ID, gateway, MTU, and original port/address fields. |
| Networks | Preserve routing-context ID, security-zone ID, gateway, CIDR/VLAN, and original metadata. |
| Groups | Organizational placement uses `containerId`; retain legacy `parentId`, membership, and access fields. |
| Services | Retain legacy host/network, `dependsOn`, and optional kind/endpoint/protocol/port/license/redundancy fields. Use instances/endpoints and typed dependencies for richer designs. |
| DNS | `targetId` can reference a device, service, endpoint, or another DNS record. Keep zone and target links stable. |
| Tasks | Preserve requirement associations when supplied; a completion state is separate from a test result. |

IDs are unique across the model, including decision-option IDs. References
contain IDs rather than copied labels. Empty optional references use `""`;
unplaced equipment uses `rackU: null`. Preserve the existing lifecycle labels
and unknown facts. The machine schemas and current model take precedence over
this prose if more fields are added.

## Architectural invariants

- A rack uses `units`; legacy single-rack projects retain the metadata fallback.
  `rackU` is the lowest occupied unit, so height 2 at U10 occupies U10–U11.
  Placement fits the selected rack and cannot overlap within that rack. Hosted
  equipment does not also occupy rack U, and hosting relationships cannot cycle.
- An interface belongs to its device. A link's source/destination interfaces
  belong to the corresponding endpoint devices; aggregates refer to compatible
  interfaces on that same device. Use separate interfaces for distinct paths.
  The Architecture **L2 / L3 interfaces** tab and workbench **Network path**
  diagram render interface cards, tagged/untagged memberships, and routing
  contexts from these same records; **Overview** retains the broader view.
- Capabilities, deployments, and listening endpoints are separate records.
  Endpoint instance/interface/network references must describe a consistent
  deployment. Resolver assignments link clients to actual endpoint records.
- Typed service dependencies use `Startup`, `Runtime`, `Optional`, or `Fallback`,
  and `All` or `Any`. Only explicit startup cycles are rejected. Legacy
  `dependsOn` is a runtime dependency; do not reject every reciprocal dependency.
- Directory containment, membership, and permission mappings are distinct.
  Preserve valid, acyclic membership/containment and identity-system boundaries.
  Keep AD/IdM alternatives and provider-specific unknowns visible.
- DNS record-target chains cannot cycle. Answers, TTL, addresses, and forwarding
  are entered design facts, not lookup results. Renaming a target retains its ID.
- Flows and policies document needs and intended enforcement. Model checks and
  traces can expose missing or inconsistent facts; they cannot establish live
  reachability, active firewall rules, health, replication, or working failover.
- Failure results depend on recorded hosts, instances, domains, and dependency
  semantics. A surviving modeled path is not a successful failover test.
- Verification `result` is `Not run`, `Pass`, `Fail`, or `Blocked`. Do not set
  `Pass`, invent a performer/time, or create evidence for an unperformed test.
  A `Done` task and a `Verified` label do not establish acceptance.
- Requirements, decisions, observations, tests, and evidence retain traceability.
  A `Decided` decision needs an existing selected option and recorded rationale.
  Baselines are named revision references; preserve scenarios and baseline
  history instead of rewriting them to appear approved.

No vendor addressing, protocols/ports, licensing arrangements, approvals,
observations, or test outcomes should be inferred just to complete a diagram.
In particular, an Atlassian application does not automatically require a license
server. Use a `uses-license` relationship only for the selected deployment's
applicable requirement. Keep unknown fields blank and record the question.

## Complete-record proposal example

This example creates a requirement and an unperformed test without assuming
vendor ports, host addresses, or approval. Copy the actual base values from the
current context, choose IDs unique in that project, and add its real affected
record references when known:

```json
{
  "format": "opsdeck-design-changes",
  "version": 1,
  "baseProjectId": "COPY_FROM_CONTEXT",
  "baseFingerprint": "COPY_FROM_CONTEXT",
  "baseScenarioId": "COPY_FROM_CONTEXT",
  "summary": "Record the engineering license-service acceptance need; leave deployment facts and test outcome unresolved.",
  "changes": [
    {
      "op": "upsert",
      "collection": "requirements",
      "record": {
        "id": "requirement-engineering-license-path",
        "name": "Engineering client license access",
        "description": "The chosen engineering application deployment must be usable from the intended client.",
        "owner": "",
        "priority": "",
        "relatedIds": [],
        "decisionIds": [],
        "acceptanceCriteria": "Confirm the selected deployment's applicable license requirement, then demonstrate the agreed client workflow and retain evidence.",
        "notes": "Client, service, policy, and decision references remain to be linked by the team.",
        "status": "Proposed"
      }
    },
    {
      "op": "upsert",
      "collection": "verificationTests",
      "record": {
        "id": "test-engineering-license-path",
        "name": "Engineering client license workflow",
        "requirementIds": ["requirement-engineering-license-path"],
        "relatedIds": [],
        "procedure": "After confirming the selected product/deployment requirements, perform the agreed client workflow and record the result.",
        "expectedResult": "The agreed workflow succeeds through the reviewed design and produces reviewable evidence.",
        "actualResult": "",
        "result": "Not run",
        "performedBy": "",
        "performedAt": "",
        "evidenceIds": [],
        "notes": "Procedure details and execution are pending.",
        "status": "Proposed"
      }
    }
  ]
}
```

## Reusable LLM request

> Read the current Design Studio context and its schemas. Propose the requested
> architecture change using `changeSetTemplate`. Preserve project, fingerprint,
> and scenario guards; stable IDs; complete existing record fields; evidence;
> and unresolved alternatives. Separate capabilities, instances, and endpoints;
> containment, membership, and permissions; flows and intended policy; tasks
> and test results. Do not invent vendor defaults, observed facts, approvals, or
> successful tests. Return only valid `opsdeck-design-changes` JSON. Use the
> summary and record notes to explain remaining questions.

## File-capable agent CLI

The CLI uses Python's standard library. Run from the repository root and keep
real projects in ignored `workspace/` or a private design repository:

```sh
python3 tools/design_studio.py init --output workspace/project.design.json
python3 tools/design_studio.py init --sample --output workspace/sample.design.json
python3 tools/design_studio.py validate workspace/project.design.json
python3 tools/design_studio.py summary workspace/project.design.json > workspace/context.json
python3 tools/design_studio.py apply workspace/project.design.json workspace/proposal.json --output workspace/reviewed.design.json
python3 tools/design_studio.py validate workspace/reviewed.design.json
python3 tools/design_studio.py render workspace/reviewed.design.json --output workspace/reviewed.design.html
```

`summary` is the LLM context export despite its short name. `apply` validates
the whole result and preserves before/after revisions, but writes immediately;
use a separate output and review it before adopting it. `render` embeds the
whole project in the generated application template, preserving history and
assets. It does not regenerate source modules.

### Model analysis and reports

Use `lint` for findings, `trace` for an entered source/destination interaction,
`impact` for dependency effects of selected failures, and `report` for handoff
material. IDs in these examples are placeholders for current project IDs:

```sh
python3 tools/design_studio.py lint workspace/project.design.json
python3 tools/design_studio.py trace workspace/project.design.json --source CLIENT_ID --destination ENDPOINT_ID
python3 tools/design_studio.py trace workspace/project.design.json --source CLIENT_ID --destination ENDPOINT_ID --flow FLOW_ID
python3 tools/design_studio.py impact workspace/project.design.json --failed HOST_ID --failed POWER_DOMAIN_ID
python3 tools/design_studio.py report workspace/project.design.json --kind handoff --output workspace/handoff.md
python3 tools/design_studio.py report workspace/project.design.json --kind addresses --output workspace/addresses.csv
python3 tools/design_studio.py report workspace/project.design.json --kind ports --output workspace/ports.csv
python3 tools/design_studio.py report workspace/project.design.json --kind flows --output workspace/communications.csv
python3 tools/design_studio.py report workspace/project.design.json --kind build --output workspace/build.md
python3 tools/design_studio.py report workspace/project.design.json --kind requirements --output workspace/requirements.md
```

Analysis reports entered facts, gaps, and assumptions. It does not discover or
provision infrastructure, execute acceptance tests, or claim verified reachability.

### Scenario and baseline CLI

List local branches, create one from the current model or a saved revision, and
switch the active branch. Prefer a separate output file for a reviewable result:

```sh
python3 tools/design_studio.py scenario list workspace/project.design.json
python3 tools/design_studio.py scenario create workspace/project.design.json --name "Identity alternative" --id scenario-identity-alternative --output workspace/branched.design.json
python3 tools/design_studio.py scenario create workspace/project.design.json --name "Alternative from review" --from-revision REVISION_ID --output workspace/from-review.design.json
python3 tools/design_studio.py scenario switch workspace/branched.design.json --id SCENARIO_ID --output workspace/switched.design.json
python3 tools/design_studio.py baseline capture workspace/project.design.json --kind target --name "Target for design review" --author "Design workshop" --output workspace/baselined.design.json
python3 tools/design_studio.py baseline compare workspace/baselined.design.json --left target --right SCENARIO_OR_REVISION_ID
```

`scenario create` accepts optional `--id`, `--from-revision`, and `--output`;
`scenario switch` requires `--id` and accepts `--output`. These operations
preserve other branches and local history. A named alternative is a copy for
design work; its name does not itself change the selected identity platform.
Export new LLM context after switching branches.

`baseline capture` takes `--kind installed|target|accepted|verified`, a required
`--name`, and optional `--author`/`--output`. It captures a revision snapshot;
the label does not establish approval or verification. `baseline compare`
accepts baseline kinds, scenario IDs, or revision IDs for `--left` and
`--right`, and reports actual changed values. Keep observed facts and passing
tests in their own records. Use `--output` on mutation commands when retaining
the original file is useful; omitting it updates the project path.

### Source development and reproducibility

Edit authoring modules in `src/`, not only the generated HTML. The architecture
schema is shared with Python. Rebuild and check before delivering source changes:

```sh
python3 tools/build_app.py
python3 tools/build_app.py --check
npm ci
npm test
python3 -m unittest discover -s tests -v
python3 tools/design_studio.py validate design-studio/sample-model.json
git diff --check
```

`npm ci` installs pinned development-only dependencies for the DOM interaction
harness, and `npm test` runs those UI checks. Have Node available for that
harness and JavaScript model, renderer, analysis, and parity checks; report
skipped checks. Neither the deployed HTML nor the standard-library Python CLI
requires npm packages at runtime. The deployed HTML needs neither Python nor Node. The
Rack Studio catalog import is optional maintainer work using
`tools/build_rack_catalog.py`; preserve its public-asset boundary and
[third-party notices](../THIRD_PARTY_NOTICES.md). Never bring an existing private
rack layout or network inventory into the public source while updating assets.
