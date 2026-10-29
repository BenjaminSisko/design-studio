---
doc_id: OD-ARCH-005
title: Design Studio Operator Guide
type: guide
version: 1.0
owner: Design Studio maintainers
date: 2026-10-29
classification: UNCLASSIFIED
classification_color: "#15803d"
---

# Design Studio

Design Studio is a local engineering and IT design workspace. Enter equipment,
interfaces, networks, services, and connections once, then use generated diagrams
to explain how the system fits together. Keep open decisions, comments, evidence, action
items, and named revisions with the design as it moves from planning through
installation and verification.

Open [index.html](index.html) directly in a desktop browser. The application is a single
self-contained HTML file with inline code and system fonts. It works offline
without an installation, server, account, or external service.

## Run a design meeting

1. Open **Project settings** to set the project name and local author label.
   Review the classification banner and use only the authorized marking for your
   environment.
2. Review the starting records. Any included `SAMPLE-` records are fictional;
   replace them with verified project information before using the design as an
   operational record.
3. In **Equipment**, add the engineering equipment and infrastructure devices.
   Enter rack placement where known, record ownership and lifecycle status, and
   leave unknown facts visibly unresolved.
4. Add **Networks**, **Interfaces**, and **Services**. Record each port under its
   device, associate services with their hosts and dependencies, and add links
   between the relevant records. Select source and destination interfaces on a
   connection when the endpoint ports are known.
5. In **Architecture**, walk through **Rack**, **Network**, and **Dependencies**.
   Changes to records feed the diagrams, so update the model when a fact changes.
   Use **Meeting mode** for a focused review.
6. In **Evidence**, attach existing diagrams, photos, and other supporting
   material. Use **Discussion** for comments and **Build & verify** for action
   items someone must complete.
7. In **Decisions**, record unresolved choices with alternatives, an owner, and
   a rationale. For example, keep Red Hat IdM and Microsoft AD as alternatives
   until the team makes and records its choice. Document DNS placement and
   dependencies as their own facts or decisions.
8. In **Revisions**, select **Capture revision** and use a name such as
   `Design review - 2026-10-29`. Use **Export** to save the project and print the
   meeting pack when a review copy is needed.

Use one active editor during a meeting. Afterward, distribute an exported project
or portable HTML copy and identify which file is the working handoff for the next
session.

## Keep the model and views consistent

| Record or view | What to capture |
| --- | --- |
| Devices | Equipment identity, role, owner, lifecycle, and rack placement where applicable. |
| Interfaces | Device, interface name or port, network, IP/CIDR text, MAC address, speed, lifecycle, and notes. |
| Networks | The segments that connect engineering equipment and IT services, including known addressing details. |
| Services | Responsibilities such as identity, DNS, time, logging, or security; their hosting and dependencies. |
| Links | Relationships and connections between model records, with optional source and destination interfaces. Use the relationship type and label to explain their meaning. |
| Rack view | Physical placement from device records. Equipment outside a rack still belongs in the model. |
| Network view | Network membership and connections from the model. |
| Dependency view | Service relationships that explain what must be available for other functions to work. |
| Custom selection view | A chosen subset of model records for a focused discussion. |

Use **Interfaces** to edit ports and addressing as structured records. Choose the
device the interface belongs to, then enter its port name, network, IP/CIDR text,
MAC address, speed, lifecycle, and notes. A connection can select these records as
its source and destination interfaces; diagrams label the entered endpoint ports.
Keep IP/CIDR entries as recorded design information and verify them during build
and validation.

The **Architecture** workspace generates the rack, network, and dependency views
from the model. Save a custom selection when a meeting needs a focused subset,
such as engineering equipment and the services it consumes. For a custom view,
select **Arrange nodes**, drag a node to place it, then select **Finish arranging**.
Positions save with that diagram and its revisions. Use **Auto layout** to reset
the custom view to generated positions. Use record editors and selection controls
to change the diagram's contents. Attach a separately drawn sketch as evidence
when it adds context.

The diagrams represent the facts entered into the model. A displayed connection
does not by itself verify cabling, routing, firewall behavior, or service health.
Track verification explicitly as the system is built.

Evidence attachments preserve source material. Attaching an existing rack image
does not automatically convert its contents into devices, ports, or connections;
enter the structured facts that should appear in generated views.

## Design identity, DNS, applications, and access

Use **Logical service design** to follow responsibilities and dependencies beyond
physical cabling. Its focused views cover **Overview**, **Directory & groups**,
**DNS**, and **Applications & licenses**. Select a node or an entered relationship
to inspect its details. Use **Focus** to show one item and up to two relationship
steps around it, or select **All items** to review the complete view. Keep physical
links in the connection model and record logical behavior with directed relationships.

1. Define an identity service under **Services**, then add an **Identity system**
   with its service, implementation, domain, and realm. Leave the implementation
   undecided while the Red Hat IdM versus Microsoft AD decision is open.
2. Add directory objects under **Directory & groups** in that identity system.
   Record organizational units, containers, or group kinds, the parent object,
   member groups/devices/services, and intended service access.
   Parent groups belong to the same identity system. Save a changed identity
   assignment before choosing a parent from that system.
3. Define the DNS service, add its **DNS zones**, then add **DNS records** with a
   zone, type, answer, optional target model item, and TTL. A target links the
   record to the device, service, or other DNS record it should resolve to; it
   does not perform a DNS query or establish that the entered answer is correct.
4. For applications and license services, use service fields for kind, endpoint,
   protocol, port, license-manager details, and redundancy. Use kind
   `Application` or `License manager` to make the application view explicit.
   Hosting identifies the equipment; dependencies identify required services.
5. Add **Logical relationships** for authentication, resolution, license use,
   hosting, forwarding, dependencies, or access. Choose source and destination,
   then capture the meaning, label, protocol, port, endpoint, and notes. The arrow
   points from the entered source to the entered destination.
6. Review the focused diagrams and associated decisions, then capture a revision
   before building or changing the agreed design.

These records describe intended or verified design information according to their
lifecycle status. They do not create accounts, provision groups, grant access,
publish DNS records, contact endpoints, or deploy configuration. Keep unknowns,
ownership questions, and verification work explicit in the design.

## Record decisions and follow-through

Use a decision for a question with alternatives and an outcome. Keep the question,
options, rationale, owner, and affected records together. A pending identity
platform decision can coexist with a proposed identity service without implying
that a platform is approved or installed.

Use comments for observations and meeting discussion. Anchor them to the relevant
record when possible so their context survives a rename. Use evidence for the
image or source supporting that discussion, and tasks for follow-up work with an
owner and completion state.

The local author label helps meeting participants identify recorded contributions.
It is entered by the operator and is not an authenticated identity or an approval
signature.

## Save and compare revisions

Save a named revision at useful milestones: before a review, after a decision,
before implementation, and after verification. Compare a saved baseline with the
current design to see what changed. Restoring a prior design creates an automatic
pre-restore safety snapshot, preserving the design you were working on before
the restore.

Named revisions are local snapshots kept with the project. They are not Git
commits, signed approvals, or a shared audit service. When repository history is
needed, export a project file to an ignored local `workspace/` folder or a separate
private design repository. The public source repository contains fictional examples only.

## Choose the right export

| Export | Use it for |
| --- | --- |
| Project JSON | Back up and transfer the editable project, including its model, history, and evidence. Import it into Design Studio to continue work. |
| Portable HTML | Carry a working offline copy with the current model, history, and evidence embedded. It can be opened on another browser or workstation. |
| Current diagram SVG | Put the current generated diagram into a document, slide, or other review product. It is a diagram export, not an editable project backup. |
| Meeting pack / Print | Produce a readable review record through the browser's print dialog; choose a printer or save as PDF. |

After export, keep the downloaded file in a location you can recover and follow
your approved transfer procedure when moving it to another environment. A
portable HTML file contains the embedded project information, including evidence
and saved history; handle the entire file according to its contents.

To hand off the project, export JSON or portable HTML after the final meeting
edits. Open the exported copy or import the JSON and confirm that the expected
project, diagrams, revision names, and evidence are present before relying on it.

Rack Studio is an optional companion for an existing rack layout and stencil workflow.
Attach its exported diagram in Design Studio as evidence when it supports the
design. The two applications do not automatically synchronize their records.

## Exchange designs with an LLM

The project uses canonical JSON, so you can maintain it as a source file or use
**LLM exchange** to ask an LLM for a proposed change. Export the current context,
give it to an LLM with your request, then import the returned JSON change set.
The application checks its project ID and base fingerprint, previews the full
difference, and waits for human application. Applying the proposal records a
revision. Export fresh context if the starting model changed.

The exchange is file based and works without an LLM endpoint, API key, or network
connection in Design Studio. Local author labels are still operator-entered
labels. Keep unresolved options explicit, review every proposed change, and
export the reviewed result for handoff.

For JSON envelopes, complete-record examples, a reusable LLM prompt, and the
standard-library CLI for validation and standalone HTML rendering, see the
[LLM exchange guide](LLM_GUIDE.md).

## Understand local storage

Design Studio saves in browser localStorage. That storage belongs to the browser
profile and local file context; moving the file, switching browsers, clearing
browser data, or using a restricted browsing mode can affect what is available.
Export regularly and after every important review.

Images and revision snapshots increase project size. Browser storage has a finite
quota; a storage warning means the browser save cannot be relied on. Export the
current project promptly and reduce oversized evidence when needed. Keep an
external backup of the project exports.

An exported HTML copy contains a snapshot as of export. Subsequent edits in one
copy are not synchronized to another. Imported projects replace the active
project according to the application's import confirmation; export any unsaved
work you need to retain before importing.

The application provides local editing and file handoffs. Team accounts, concurrent
editing, access control, authenticated attribution, conflict resolution, and
automatic Git integration require a separate workflow. Do not treat two people
editing separate copies as a shared live session.

## Troubleshooting

| Symptom | Next step |
| --- | --- |
| Project looks different after changing browsers or moving the file | Import the latest project JSON or open the latest portable HTML handoff. |
| A diagram does not contain an expected item | Check the item record, relationships, and the active view or custom selection. |
| An uploaded rack image does not create equipment records | Keep it as evidence and enter the model records that should drive the views. |
| Browser reports that the project cannot be saved | Export immediately, then review evidence sizes and available browser storage. |
| Teammates see different designs | Choose one handoff file, export it, and import that same project before continuing. |
| An old decision needs to change | Record the new rationale, preserve a named baseline, and update the affected model records. |
