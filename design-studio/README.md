---
doc_id: OD-ARCH-005
title: Design Studio Operator Guide
type: guide
version: 2.0
owner: Design Studio maintainers
date: 2026-10-29
classification: UNCLASSIFIED
classification_color: "#15803d"
---

# Design Studio operator guide

Design Studio carries an engineering and IT design from requirements through
rack placement, networks, shared services, communication policy, implementation,
and recorded verification. Its diagrams and reports reuse structured records,
so a rename, endpoint change, or new relationship stays linked across views.

Open [index.html](index.html) directly in a desktop browser. It is one
self-contained offline HTML file. Running it needs no installation, build,
server, account, API key, or internet connection. Included `SAMPLE-` records are
fictional; choose **New project** for a clean design.

## Run the meeting

1. Set the project name, local author label, and applicable marking under
   **Project settings**. Keep unknown facts blank or explicitly undecided.
2. Attach existing rack/network diagrams, photos, PDFs, and supporting material
   under **Evidence**. Comments and decisions can reference the actual records.
3. Add equipment and interfaces, networks and zones, then services and their
   deployments. A device has one identity across the physical and logical views.
4. Open **Architecture workbench**. Use **Design a service journey** to start
   with an engineering client and the capability it needs, then refine the
   resulting linked records in their editors.
5. Review the documented path, communications, checks, and failure dependencies.
   Assign follow-up work rather than filling gaps with assumptions.
6. Capture a named revision and, when appropriate, a baseline. Export the edited
   project for the next session and generate review diagrams or a build pack.

Use one active editor during a meeting. Choose one exported file as the working
handoff; separately edited copies do not synchronize.

## Design the physical rack with Rack Studio

The physical workspace integrates the renderer and public equipment catalog
from your existing Rack Studio. Search the catalog directly; importing a prior
layout is optional. The bundle contains 5,835 models, nine original front-panel
images, and twenty original generic network stencils.

Create a rack with its name, capacity in U, site, and location. Choose equipment
from the catalog, select the rack, and enter its **lowest occupied U**. A 2U
server at U10 occupies U10 and U11. Placement must fit and cannot overlap other
equipment in that rack. Drag equipment within the rack to change its position;
the same device record changes, keeping its service and interface links intact.
Use the equipment editor to enter precise placement or change racks.

Models without a bundled front image use synthetic panels. Upload a local PNG,
JPEG, WebP, or GIF panel through the equipment editor for a custom view. The
image embeds in project and portable exports; no external asset connection is
needed. The original 857 MB elevation tree is not required. A custom image is
visual evidence of the front panel; its contents do not create interfaces or
ports automatically.

Use equipment/virtualization roles and **Hosted by** for hypervisors, VMs, and
chassis children. Hosted equipment appears alongside the rack or in chassis bays
and does not also consume rack units. Existing Rack Studio layout JSON can
still import equipment and chassis relationships. Check imported positions,
heights, and catalog selections before adopting them; the import does not
recreate its separate network topology or synchronize the two applications.

## Model the network at interface level

Equipment can retain primary network membership for overview diagrams. Use
**Interfaces** for distinct physical and virtual paths: device, port name,
address, speed, mode, gateway, MTU, untagged network, tagged networks, and parent
bond/aggregate. An access port and a trunk carry different entered facts.
Physical links can select source and destination interfaces belonging to the
corresponding devices.

Under **Architecture workbench → Network path**, edit routing contexts, security
zones, and routes. Networks can link to a routing context and a security zone;
routes record a device, destination, next hop, and optional interface/context.
For a host with separate engineering and management interfaces, enter both so
the design retains two distinct paths.

In **Architecture**, use **Overview** for the broad equipment/network/service
picture and **L2 / L3 interfaces** for individual interface cards, physical
connections, tagged/untagged network relationships, and VRF/routing contexts.
Select an interface card to inspect and edit its shared record. The same L2/L3
diagram appears in the workbench **Network path** tab alongside the trace tool.

Select an initiating item and a destination capability or endpoint, then choose
**Trace documented design**. Inspect the linked steps and unresolved questions.
A route, DNS relationship, authentication dependency, application flow, and
policy are separate facts. The trace uses what the team entered; it does not
send traffic, query DNS, inspect device configuration, or verify reachability.

## Separate capabilities, deployments, and endpoints

Use **Services** for capabilities such as DNS, identity, time, logging, MATLAB,
or an applicable license service. Under **Service deployment**, add:

| Record | Purpose |
| --- | --- |
| Service instance | A deployment of a capability on a host/network, with role and shared failure-domain references. |
| Service endpoint | A usable endpoint with instance, interface/network, entered address or DNS name, protocol, port, and role. |
| Client resolver assignment | A client's ordered resolver endpoint references and search domains. |
| Typed dependency | One service's startup, runtime, optional, or fallback need for another service; availability rule `All` or `Any`. |
| Failure domain | A shared host, power, storage, switching, rack, or other dependency relevant to impact review. |

One capability can have several instances and endpoints. Use these records to
document replicas or active/standby arrangements rather than copying a service
for every host. A service's legacy host field remains available for older
projects. Explicit startup dependency cycles are invalid; reciprocal runtime
relationships can be represented and reviewed.

The deployment diagram connects capabilities, instances, endpoints, and hosts.
A surviving modeled instance does not establish that its data replication or
failover works; record those assumptions and test them.

## Design identity, DNS, and application access

Keep an identity implementation undecided until the team records a choice.
An **Identity system** links to its service and records implementation, domain,
and realm. Preserve AD, Red Hat IdM, and other alternatives in **Decisions**.

Use **Directory containers** for organizational containment, **Directory
principals** for users/service accounts/computers, **Directory groups** for
membership and nesting, and **Role & access mappings** for application roles,
resources, and permissions. An OU, a group, and an application role have
separate meanings. Associate them with the appropriate identity system and
validate the intended structure for the chosen implementation. These records
do not provision a directory or grant access.

Define DNS services and instances, zones, then records with a zone, type,
entered answer, TTL, and optional linked target. A target can reference a device,
service, endpoint, or another record. Client resolver assignments and forwarding
relationships document how clients find answers. The DNS view distinguishes
resolution from general dependency and physical connectivity. Renaming a target
keeps its ID-based relationships intact.

Applications, clients, and license services use the same deployment and
relationship model. Record the actual selected product/deployment requirement;
do not assume all Atlassian products use a license server. Enter protocol,
ports, endpoints, license-manager information, and redundancy only when known.
The logical views provide overview, directory/group, DNS, and application/license
focus controls, with SVG export.

## Record communications and intended policy

Under **Communication**, add each required interaction with its source,
destination, initiating interface when known, protocol/ports, direction,
purpose, crossed zones, enforcement devices, policies, and related requirements.
Include administrative, management, backup, and logging needs as applicable.

A **Network policy** records intended allow/deny/review behavior, source and
destination records or zones, protocol/ports, enforcement device, rule/change
reference, and owner. Leave a missing policy visible as work to resolve. Use
**Inspect path** to review an interaction and **Export communication matrix CSV**
for a firewall/change-request discussion. The matrix is a design handoff; it
does not configure an enforcement device or establish that a rule is effective.

## Review design checks and failure impact

**Design checks** lists model errors, warnings, and information with links to
relevant records. Use it to find conflicting or incomplete addressing,
interface/VLAN/gateway plans, unresolved communication policy, ownership gaps,
and shared failure dependencies where the model contains the supporting facts.
Fix the source records so all views improve together. An empty findings list
means no listed model checks fired, not that the network has passed validation.

Under **Failure impact**, select one or more devices, racks, instances,
endpoints, networks, or failure domains, then analyze the result. Review affected
records, degraded/uncertain records, services with a surviving modeled path,
and the accompanying explanations. Recording shared power, host, storage, and
switch dependencies makes the analysis useful. Missing facts limit the answer;
this is dependency analysis rather than an executed failure or failover test.

## Carry requirements into build and verification

Under **Requirements & tests**, link each requirement to affected design records,
decisions, and acceptance criteria. Keep implementation action items in
**Build & verify** with owners and completion states. Add verification tests with
procedure, expected outcome, actual outcome, result, performer, time, and evidence.
Available test results include **Not run**, **Pass**, **Fail**, and **Blocked**.

Marking a build task **Done** does not mark a test **Pass**. A passing result
should record what was performed and its supporting evidence. Use **As-built
observations** to retain observed field values, source, observer, time, and
evidence alongside the proposed model, then review differences before changing
the accepted design.

Comments retain discussion. Decisions retain alternatives, rationale, owner,
and affected records. A decided outcome requires a selected option and rationale.
Local author labels are operator-entered attribution, not authenticated approval.

## Branch scenarios and capture baselines

Use **Scenarios & baselines** to create a local alternative from the current
design, such as an AD option and an IdM option. Switch scenarios to work on each
branched model while preserving the design history. Export the project to carry
all scenarios with it. An LLM proposal is scoped to the active scenario and its
starting model; switching alternatives calls for fresh LLM context.

Capture useful milestones as named revisions. **Installed**, **Target**,
**Accepted**, and **Verified** baselines point to revision snapshots. Compare a
baseline with the current design to review actual before/after field values.
A baseline label records the team's intent; it does not itself approve a design,
prove deployment, or imply acceptance tests passed. Keep verification records
and evidence explicit.

Restoring a prior revision creates a safety snapshot of the current draft.
Local revisions and scenarios are preserved with project exports. They do not
commit to Git, synchronize files, or merge concurrent edits automatically.

## Generate visual products and build packs

Use the Architecture **Overview**, **L2 / L3 interfaces**, **Rack Studio**,
**Service deployment**, **Dependencies**, logical-service, and custom diagrams for
reviews. Select records to inspect relationships. Custom diagram selections use
shared IDs; **Arrange nodes** saves manual positions, and **Auto layout** resets
them. **Meeting mode** focuses the presentation. SVG exports retain embedded
panel images and vector labels.

**Build pack** generates these products from the entered model:

| Product | Contents |
| --- | --- |
| Architecture and build handoff | Project context, capabilities, ownership, decisions, verification, and unresolved facts. |
| Address plan CSV | Interface/endpoint addresses, networks, gateways, and routing context. |
| Port and cable map CSV | Physical links, endpoint interfaces, media/speed, and lifecycle. |
| Communication matrix CSV | Initiators, destinations, protocol/ports, intended policy, and purpose. |
| Build sequence | Startup dependencies, deployed instances, work items, and verification order. |
| Requirement traceability | Requirements, design records, decisions, tasks, tests, and evidence. |

Build packs describe the entered model and its unknowns. They do not generate
or deploy live device configurations. Use the browser print workflow for a
review copy or PDF.

## Save, transfer, and work with an LLM

| Export | Use |
| --- | --- |
| Project JSON | Editable backup with model, assets, scenarios, baselines, and history. |
| Portable HTML | A complete offline application with the project embedded for another workstation. |
| Diagram SVG | A visual for a document or slide; not a project backup. |
| Reports / print | Review and implementation handoff material; not an editable model replacement. |

Open or import the exported handoff and confirm expected records, scenario,
revision names, images, and evidence before relying on it. The portable file
contains the project information and its saved history.

For LLM changes, export fresh context under **LLM exchange**, give it and your
request to an LLM, then import its guarded JSON proposal. Review additions,
edits, deletions, and downstream effects before applying. Project ID,
fingerprint, and scenario scope must match. Applying preserves before/after
revisions. See the [LLM guide](LLM_GUIDE.md) for the contract and CLI examples.
The application performs file exchange without contacting an LLM provider.
Context exports omit evidence and custom front-panel image bytes. Those omission
markers are not valid attachment values; use the complete project when an LLM
must preserve embedded images during a full-record edit.

## Local storage and troubleshooting

Browser localStorage belongs to a browser profile and file context. Moving the
HTML, changing browsers, restricted browsing modes, or clearing browser data can
affect availability. Export regularly and after reviews. Large evidence and
revision snapshots consume finite browser storage; if a save warning appears,
export immediately and retain an external backup.

| Symptom | Next action |
| --- | --- |
| An item is absent from a diagram | Check its source record, hosting/rack/network assignments, relationship references, focus, and custom selection. |
| A panel is synthetic | Choose a model with an embedded image or upload a local raster front panel. |
| A diagram photo did not create equipment | Keep it as evidence and enter the records that should generate views. |
| Trace or impact output is uncertain | Record missing interfaces, deployments, policies, routes, or shared dependencies; inspect the listed assumptions. |
| A proposal is stale or belongs to another scenario | Export current context from the intended scenario and regenerate it. |
| A different browser shows a different design | Import the chosen current project JSON or open its portable HTML handoff. |
| Teammates have diverging copies | Choose a working handoff and reconcile changes deliberately before continuing. |

The application provides local editing, history, and file handoffs. Team
accounts, authenticated approvals, simultaneous editing, automatic Git
synchronization, live discovery, and infrastructure provisioning require
separate workflows.
