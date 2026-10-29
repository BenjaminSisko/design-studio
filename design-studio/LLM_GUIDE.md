---
doc_id: OD-ARCH-006
title: Design Studio LLM Exchange Guide
type: guide
version: 1.0
owner: Design Studio maintainers
date: 2026-10-29
classification: UNCLASSIFIED
classification_color: "#15803d"
---

# Design Studio LLM exchange

Design Studio keeps the design in canonical JSON. You can edit the design in the
offline HTML application, exchange files with an LLM, or maintain the JSON source
in a repository and render a new standalone HTML copy. The same structured model
drives the equipment, interface, network, service, and diagram views.

The application does not require a live LLM endpoint, an API key, or a network
connection. You decide which files to provide to an LLM in an environment
authorized for their contents. The application exchanges files and previews the
result; it does not send project information to a provider.

Read the [operator guide](README.md) for the meeting and diagram workflow.

## Propose a change through LLM exchange

Use guarded change sets when asking an LLM to modify a design:

1. Save the current work and capture a named revision before a substantial change.
2. Open **LLM exchange** and export the context JSON from the current project.
3. Give the context and a concrete request to your LLM. Ask for a JSON change set
   using the provided template, retaining the project ID and base fingerprint.
4. Import the proposed change set through **LLM exchange**. The application checks
   that its base matches the current project and model, validates the proposal,
   and presents the full difference for human review.
5. Review every addition, edit, deletion, and metadata change. Apply only when the
   proposed result matches the intended design. Applying records a revision.
6. Review the updated diagrams and export the resulting project JSON or portable
   HTML for the next session.

If the project changed after the context export, export fresh context and ask the
LLM to regenerate its proposal. Do not change the fingerprint manually to bypass
the stale-base check. A fingerprint guards against applying a proposal to a
different starting model; it is not a digital signature or proof of authorship.

## Files and envelopes

Project JSON is a versioned envelope containing the current model and its local
history:

```json
{
  "format": "opsdeck-design-studio",
  "version": 1,
  "model": {},
  "revisions": [],
  "activity": [],
  "assets": {},
  "savedAt": "2026-10-29T12:00:00.000Z"
}
```

`model` has `schemaVersion: 1`, a `meta` object, and the collection arrays listed
below. The export may pool embedded evidence in `assets`; preserve those entries
and their references. Use the application or CLI to load and render the envelope
instead of rebuilding its attachment or history structures by hand. As with the
context illustration below, `{}` is a placeholder for actual exported data.

An LLM context export has this envelope:

```json
{
  "format": "opsdeck-design-context",
  "version": 1,
  "baseProjectId": "COPY_FROM_EXPORTED_CONTEXT",
  "baseFingerprint": "COPY_FROM_EXPORTED_CONTEXT",
  "instructions": ["Instructions supplied by Design Studio"],
  "model": {},
  "changeSetTemplate": {}
}
```

The exported file supplies the actual model, instructions, and change-set
template. The empty objects above illustrate the envelope only; they are not an
empty project to submit. Use the exported values exactly. The context contains
the structured model and attachment captions, with embedded file data replaced
by omission markers. Project exports carry the actual evidence and history.
Review either file's contents before transferring it. Do not use context JSON as
a replacement project or upsert evidence with an omission marker as its data.

The proposed-change envelope is:

```json
{
  "format": "opsdeck-design-changes",
  "version": 1,
  "baseProjectId": "COPY_FROM_EXPORTED_CONTEXT",
  "baseFingerprint": "COPY_FROM_EXPORTED_CONTEXT",
  "summary": "Describe the intended design changes and remaining questions.",
  "changes": []
}
```

The `changes` array contains these operations:

| Operation | Shape and meaning |
| --- | --- |
| Upsert | `{"op":"upsert","collection":"services","record":{...}}` adds or replaces one complete record by its stable ID. |
| Delete | `{"op":"delete","collection":"services","id":"existing-id"}` removes the identified record. |
| Metadata | `{"op":"meta","values":{...}}` updates permitted project metadata. |

An upsert is a complete record replacement, not a partial field patch. Copy the
existing record and preserve every field that should survive. For a new record,
use the canonical fields and valid values from the exported model and template.
Keep IDs stable when renaming or revising an item so references continue to point
to the same item.

Return plain JSON that parses without cleanup: no Markdown fences around the
submitted file, comments, trailing commas, executable code, or free-form YAML.
Do not convert the canonical model into a different schema.

## Model rules for an LLM

Use the exported model as the schema reference. Its property names, IDs, enum
values, and reference shapes take precedence over prose descriptions or a model
the LLM remembers from an earlier session.

| Model area | Information to preserve |
| --- | --- |
| `meta` | `id`, `name`, `description`, `phase`, `author`, `rackUnits`, `rackName`, `classification`, `classificationColor`. A metadata operation cannot change `id`. |
| `devices` | `id`, `name`, `type`, `owner`, `status`, `networkId`, `rackU`, `height`, `notes`; imported hosted equipment can also use `hostedBy`, `model`, and `sourceInfo`. |
| `interfaces` | `id`, `name` (port/interface name), `deviceId`, `networkId`, `address` (IP/CIDR text), `mac`, `speed`, `status`, `notes`. |
| `networks` | `id`, `name`, `cidr`, `vlan`, `purpose`, `owner`, `status`. |
| `services` | `id`, `name`, `platform`, `owner`, `status`, `deviceId`, `networkId`, `notes`, `dependsOn` (service IDs); optional configuration strings `kind`, `endpoint`, `protocol`, `port`, `licenseManager`, `redundancy`. |
| `links` | `id`, `from`, `to`, `fromInterfaceId`, `toInterfaceId`, `label`, `status`; preserve any additional existing notes. |
| `identity` | `id`, `name`, `serviceId`, `implementation`, `domain`, `realm`, `notes`, `status`. |
| `groups` | `id`, `name`, `identityId`, `parentId`, `kind`, `memberIds`, `accessIds`, `notes`, `status`. |
| `dnsZones` | `id`, `name`, `serviceId`, `kind`, `notes`, `status`. |
| `dnsRecords` | `id`, `name`, `zoneId`, `type`, `value`, `targetId`, `ttl`, `notes`, `status`. |
| `relationships` | `id`, `from`, `to`, `kind`, `label`, `protocol`, `port`, `endpoint`, `notes`, `status`. |
| `decisions` | `id`, `title`, `status`, `owner`, `due`, `context`, `options` (`id`, `label`, `pros`, `cons`), `selectedOptionId`, `rationale`, `relatedIds`. |
| `evidence` | `id`, `name`, `mime`, `data`, `relatedId`, plus existing captions or descriptions. Preserve embedded content or pooled asset references in the source envelope. |
| `tasks` | `id`, `title`, `owner`, `status`, `due`, `relatedId`. |
| `comments` | `id`, `entityId`, `author`, `text`, `resolved`, and `createdAt` when present. |
| `diagrams` | `id`, `name`, `nodeIds`, `notes`, and optional `layout` keyed by node ID with numeric `x` and `y` positions. Custom selections reference model nodes rather than duplicating them. |

Preserve every additional field already present in an exported record. IDs must
be unique throughout the model, including decision option IDs. Empty optional
references use `""`; an interface requires an existing `deviceId`. Link endpoints
and custom-selection nodes can refer to devices, networks, or services. The
`status` fields are nonempty strings; retain the team's established labels rather
than renaming them casually. Due dates use `YYYY-MM-DD` or an empty string.

Rack positions and equipment height must fit within the configured rack without
overlaps. Hosted equipment uses `hostedBy` and does not also occupy rack units.
Service dependencies and hosted-equipment relationships cannot contain cycles.
Network CIDR and VLAN entries are validated when present. Interface `address`
is entered text and does not establish address-allocation or connectivity checks.

Keep logical services distinct from their physical deployment. Identity systems
link to identity services and record the implementation, domain, and realm.
Directory groups link to an identity system; `parentId` must point to a group in
that same identity system. `memberIds` can reference groups, devices, or services;
`accessIds` reference services. Membership and parent relationships must remain
valid rather than creating cycles.

DNS zones link to their serving service. DNS records link to a zone and can link
to a device, service, or another DNS record through `targetId`. `ttl` is blank/null or a nonnegative integer
or numeric string. Entered DNS values and target references describe the design;
they are not live lookup results.

Logical `relationships` use one of these `kind` values: `authenticates`,
`resolves`, `uses-license`, `hosts`, `forwards`, `depends`, or `access`. Their
`from` and `to` endpoints can reference devices, networks, services, identity
systems, groups, DNS zones, or DNS records. Interfaces belong in physical
connections rather than logical relationship endpoints. Use a descriptive label
and explicit protocol, port, or endpoint details when known. Optional service
`licenseManager` text describes the configuration; use a `uses-license`
relationship to link actual model records.

Keep planned, approved, installed, and verified states distinct. Do not infer
that equipment exists, that a connection works, or that a service is approved
because it appears in a diagram. Use the actual lifecycle values supported by
the exported model.

Represent unresolved choices explicitly. A Red Hat IdM versus Microsoft AD
decision should retain both alternatives until a human records the outcome. A
decision with status `Decided` requires a valid `selectedOptionId` and a rationale;
an LLM recommendation alone does not establish that the team has decided.

For interface and port changes:

- Each interface belongs to its recorded device. A connection's source interface
  must belong to its source device, and its destination interface to its
  destination device.
- Use existing IDs for device, network, and interface references. Add new records
  in the same proposal when the intended relationship requires them.
- IP/CIDR values are entered design text. Do not invent address assignments,
  uniqueness checks, routes, or observed connectivity.
- Preserve an unknown endpoint as unknown. Do not add a physical port to a
  logical dependency just to make the diagram look more complete.
- A port label describes entered information. Verification requires the team's
  build and validation work.

Do not remove referenced records without also reviewing dependent references.
Review deletions of evidence or comments explicitly; a shorter project is not a
reason to discard the design rationale.

Local author labels help readers follow meeting contributions. They are not
authenticated accounts, signatures, or verified statements of who approved a
change. Keep model revision history and Git history intact rather than
rewriting them to make an LLM proposal look human-approved.

## Complete-record proposal example

This example uses the fictional starter's IDs. Copy the actual `baseProjectId`
and `baseFingerprint` from the context before applying it to that starter. For
another project, use its real IDs and records. The example retains unknown
platform and address values; it records design work without claiming a decision
or verification.

```json
{
  "format": "opsdeck-design-changes",
  "version": 1,
  "baseProjectId": "COPY_FROM_EXPORTED_CONTEXT",
  "baseFingerprint": "COPY_FROM_EXPORTED_CONTEXT",
  "summary": "SAMPLE-Record pending DNS design and services interface details; keep identity alternatives open.",
  "changes": [
    {
      "op": "upsert",
      "collection": "services",
      "record": {
        "id": "sample-service-dns",
        "name": "SAMPLE-DNS",
        "platform": "Undecided",
        "owner": "IT",
        "status": "Proposed",
        "deviceId": "sample-device-compute",
        "networkId": "sample-net-infrastructure",
        "notes": "SAMPLE-Document authoritative zones, forwarding, ownership, and acceptance criteria before selecting a platform.",
        "dependsOn": []
      }
    },
    {
      "op": "upsert",
      "collection": "interfaces",
      "record": {
        "id": "sample-interface-services",
        "name": "SAMPLE-Services host interface",
        "deviceId": "sample-device-compute",
        "networkId": "sample-net-infrastructure",
        "address": "",
        "mac": "",
        "speed": "Undecided",
        "status": "Proposed",
        "notes": "SAMPLE-Confirm physical port identifier and addressing during the design review."
      }
    },
    {
      "op": "upsert",
      "collection": "decisions",
      "record": {
        "id": "sample-decision-identity",
        "title": "SAMPLE-Identity platform selection",
        "status": "Open",
        "owner": "",
        "due": "",
        "context": "SAMPLE-Capture verified Linux integration, administration, DNS, and recovery requirements before selecting a platform.",
        "options": [
          {"id": "sample-option-idm", "label": "Red Hat IdM", "pros": "", "cons": ""},
          {"id": "sample-option-ad", "label": "Microsoft Active Directory", "pros": "", "cons": ""},
          {"id": "sample-option-other", "label": "Other / combined approach", "pros": "", "cons": ""}
        ],
        "selectedOptionId": "",
        "rationale": "",
        "relatedIds": ["sample-service-identity", "sample-device-linux"]
      }
    }
  ]
}
```

## A reusable request

```text
Use the attached Design Studio context JSON as the current source of truth.
Return only an opsdeck-design-changes version 1 JSON document using its
changeSetTemplate. Copy baseProjectId and baseFingerprint exactly.

Requested change: {{DESCRIBE THE CHANGE AND VERIFIED FACTS}}

Preserve stable IDs and unrelated fields. Every upsert must contain a complete
record in the exported schema. Do not invent missing equipment, addresses,
ports, approvals, or decisions. Keep unresolved alternatives explicit. Include
deletions only when I specifically requested them, and explain them in summary.
Do not change author labels, markings, or project identity unless requested.
```

## Work from a JSON source file

The Python helper uses only the standard library and supports a file-based
authoring workflow. Run commands from the Design Studio repository root:

```sh
python3 tools/design_studio.py init --output workspace/projects/design.json
python3 tools/design_studio.py validate workspace/projects/design.json
python3 tools/design_studio.py summary workspace/projects/design.json
```

Use `init --sample` only when you want the fictional sample model:

```sh
python3 tools/design_studio.py init --output workspace/projects/sample-design.json --sample
```

Apply a guarded proposal to a project file and write a separate result:

```sh
python3 tools/design_studio.py apply workspace/projects/design.json proposal.json \
  --output workspace/projects/design-reviewed.json
python3 tools/design_studio.py validate workspace/projects/design-reviewed.json
python3 tools/design_studio.py summary workspace/projects/design-reviewed.json
```

Render a standalone HTML copy with the current application template:

```sh
python3 tools/design_studio.py render workspace/projects/design-reviewed.json \
  --output workspace/projects/design-review.html
```

Use `--template design-studio/index.html` to select the template explicitly.
Open the rendered HTML, review the design and its diagrams, then continue with
the browser workflow. The CLI does not provide the interactive human-review
dialog; inspect the JSON difference or review the separate rendered copy before
adopting the result as the current source.

An LLM can also edit a project JSON file directly. Preserve the original, have it
write a separate proposed file, validate the proposal, inspect the full file
difference, and render it for review. Direct file editing does not provide the
change-set base check; guarded change sets are preferred for design changes.

Use `python3 tools/design_studio.py --help` and each subcommand's `--help` for
the current command options. Commit reviewed JSON and documentation through your
normal Git workflow when repository version control is needed. Browser snapshots
and CLI output files do not automatically create Git commits.

## Resolve exchange errors

| Result | Next step |
| --- | --- |
| Project ID or base fingerprint does not match | Export fresh context from the actual current project and regenerate the proposal. |
| JSON fails to parse | Ask for valid plain JSON with the required envelope; keep the current project unchanged. |
| A referenced ID is missing | Correct the ID or include the intended new record and valid references. |
| An interface does not belong to the connection endpoint | Select the port on the correct device or correct the device endpoint. |
| A decided choice lacks an option or rationale | Record the actual outcome and rationale, or keep the decision unresolved. |
| A valid proposal changes more than requested | Reject it and narrow the request. Validation establishes structural validity, not design correctness. |

The project remains an engineering record of entered facts and decisions. Human
review establishes whether a proposed change reflects the intended system;
validation and generated diagrams help make that review concrete.
