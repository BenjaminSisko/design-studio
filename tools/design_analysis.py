"""Deterministic analysis of entered Design Studio models; no live network access.

Services are available while at least one instance remains. Hard All dependencies
are conjunctive; Any and Fallback dependencies are alternatives grouped by source
service and kind. Optional dependencies degrade rather than remove availability.
"""
from __future__ import annotations

import csv
import io
import ipaddress
import re

LIMIT = 'Entered model only; no live reachability, configuration, health, or failover verification.'


def rows(model, key):
    value = model.get(key, [])
    return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []


def index(model):
    return {r['id']: r for value in model.values() if isinstance(value, list) for r in value if isinstance(r, dict) and isinstance(r.get('id'), str)}


def title(row):
    return str(row.get('name') or row.get('title') or row.get('label') or row.get('id') or 'Unspecified')


def uniq(values):
    return list(dict.fromkeys(v for v in values if v))


def ip(value):
    try:
        text = str(value).strip()
        if '%' in text or ('/' in text and not re.fullmatch(r'.+/[0-9]+', text)):
            return None
        return ipaddress.ip_interface(text).ip
    except ValueError:
        return None


def subnet(value):
    try:
        return ipaddress.ip_network(str(value).strip(), strict=False) if '/' in str(value) else None
    except ValueError:
        return None


def contains(network, address):
    return bool(network is not None and address is not None and network.version == address.version and address in network)


def interfaces(model, entity_id, seen=None):
    seen = set() if seen is None else set(seen)
    if entity_id in seen:
        return []
    seen.add(entity_id)
    by_id = index(model)
    entity = by_id.get(entity_id, {})
    if any(r['id'] == entity_id for r in rows(model, 'interfaces')):
        return [entity]
    if entity.get('interfaceId'):
        return interfaces(model, entity['interfaceId'], seen)
    if any(r['id'] == entity_id for r in rows(model, 'devices')):
        own = [r for r in rows(model, 'interfaces') if r.get('deviceId') == entity_id]
        return own or interfaces(model, entity.get('hostedBy', ''), seen)
    endpoint_rows = [r for r in rows(model, 'endpoints') if r.get('serviceId') == entity_id or r.get('instanceId') == entity_id]
    result = [i for endpoint in endpoint_rows for i in interfaces(model, endpoint['id'], seen)]
    if entity.get('instanceId'):
        result.extend(interfaces(model, entity['instanceId'], seen))
    if entity.get('deviceId'):
        result.extend(interfaces(model, entity['deviceId'], seen))
    for instance in rows(model, 'serviceInstances'):
        if instance.get('serviceId') == entity_id:
            result.extend(interfaces(model, instance['id'], seen))
    return list({r['id']: r for r in result}.values())


def networks(model, entity_id):
    by_id = index(model)
    entity = by_id.get(entity_id, {})
    ids = [entity.get('networkId')]
    for interface in interfaces(model, entity_id):
        ids.extend(interface_networks(interface))
    if entity.get('instanceId'):
        ids.append(by_id.get(entity['instanceId'], {}).get('networkId'))
    return uniq(ids)


def interface_networks(interface):
    return uniq([interface.get('networkId'), interface.get('untaggedNetworkId')] + interface.get('taggedNetworkIds', []))


def effective_address(model, entity):
    linked = index(model).get(entity.get('interfaceId'), {}).get('address', '')
    return linked or entity.get('address', '')


def equivalents(model, entity_id):
    by_id = index(model)
    entity = by_id.get(entity_id, {})
    result = [entity_id, entity.get('serviceId'), entity.get('instanceId'), entity.get('deviceId')]
    result.extend(networks(model, entity_id))
    for interface in interfaces(model, entity_id):
        result.extend([interface['id'], interface.get('deviceId')])
    return uniq(result)


def zones(model, entity_id):
    by_id = index(model)
    return uniq(by_id.get(n, {}).get('zoneId') for n in networks(model, entity_id))


def dependencies(model):
    result = list(rows(model, 'serviceDependencies'))
    explicit = {(r.get('fromServiceId'), r.get('toServiceId')) for r in result}
    for service in rows(model, 'services'):
        for target in service.get('dependsOn', []):
            if (service['id'], target) not in explicit:
                result.append(dict(id=service['id'] + ':legacy:' + target, name='Legacy runtime dependency', fromServiceId=service['id'], toServiceId=target, kind='Runtime', requirement='All'))
    return result


def port_ranges(value):
    text = str(value).strip().lower()
    if text in ('*', 'any', 'all'):
        return [(0, 65535)]
    result = []
    for token in re.split(r'[,;\s]+', text):
        if not token:
            continue
        match = re.fullmatch(r'(\d+)(?:-(\d+))?', token)
        if not match:
            return None
        low, high = int(match[1]), int(match[2] or match[1])
        if not 0 <= low <= high <= 65535:
            return None
        result.append((low, high))
    return result or None


def ports_covered(flow, policy):
    wanted, allowed = port_ranges(flow), port_ranges(policy)
    if wanted is None or allowed is None:
        return None
    # A flow range can be covered by adjoining policy ranges.
    allowed = sorted(allowed)
    for low, high in wanted:
        cursor = low
        for start, end in allowed:
            if start <= cursor <= end:
                cursor = end + 1
            if cursor > high:
                break
        if cursor <= high:
            return False
    return True


def no_ports(protocol):
    return str(protocol).lower().strip() in ('icmp', 'icmpv6', 'ip', 'esp', 'ah')


def policy_state(model, flow):
    by_id = index(model)
    source, destination = flow.get('sourceId', ''), flow.get('destinationId', '')
    matched, uncertain = [], []
    for policy in rows(model, 'policies'):
        if flow.get('policyIds') and policy['id'] not in flow['policyIds']:
            # Other definite Deny rules still matter; explicit lists do not hide them.
            if policy.get('action') != 'Deny':
                continue
        match = True
        unknown = False
        for key, zone_key, endpoint in [('sourceIds', 'sourceZoneId', source), ('destinationIds', 'destinationZoneId', destination)]:
            ids, zone = policy.get(key, []), policy.get(zone_key, '')
            if ids and not set(ids).intersection(equivalents(model, endpoint)):
                match = False
            if zone:
                endpoint_zones = zones(model, endpoint)
                if endpoint_zones and zone not in endpoint_zones:
                    match = False
                elif not endpoint_zones:
                    unknown = True
            if not ids and not zone:
                unknown = True
        fp, pp = str(flow.get('protocol', '')).lower(), str(policy.get('protocol', '')).lower()
        if not fp or not pp:
            unknown = True
        elif pp not in ('any', '*', 'all') and fp != pp:
            match = False
        if not no_ports(fp):
            covered = ports_covered(flow.get('ports', ''), policy.get('ports', ''))
            if covered is False:
                match = False
            elif covered is None:
                unknown = True
        if match:
            (uncertain if unknown else matched).append(policy)
    denied = [p for p in matched if p.get('action') == 'Deny']
    allowed = [p for p in matched if p.get('action') == 'Allow' and p.get('enforcementDeviceId') and p.get('owner')]
    state = 'blocked' if denied else 'documented' if allowed else 'unknown'
    return dict(state=state, policyIds=[p['id'] for p in matched], uncertainPolicyIds=[p['id'] for p in uncertain], reason='A matching entered Deny policy blocks this flow.' if denied else 'A matching Allow policy, enforcement device, and owner are documented.' if allowed else 'No complete matching Allow policy is documented; unknown policy is not permission.')


def target_addresses(model, target_id, seen=None):
    seen = set() if seen is None else set(seen)
    if target_id in seen: return []
    seen.add(target_id)
    target = index(model).get(target_id, {})
    values = [effective_address(model, target)] + [i.get('address', '') for i in interfaces(model, target_id)]
    if any(r['id'] == target_id for r in rows(model, 'dnsRecords')):
        values.append(target.get('value', ''))
        values.extend(target_addresses(model, target.get('targetId', ''), seen))
    return values


def target_dns_name(model, target_id):
    by_id = index(model)
    target = by_id.get(target_id, {})
    if target.get('dnsName'): return target['dnsName']
    if any(r['id'] == target_id for r in rows(model, 'dnsRecords')):
        name = target.get('name', '')
        zone = by_id.get(target.get('zoneId'), {}).get('name', '')
        return name if '.' in name or not zone else name + '.' + zone
    return ''


def lint(model):
    findings = []
    by_id = index(model)
    def add(code, severity, message, ids):
        findings.append(dict(id=code + ':' + ':'.join(uniq(ids)), severity=severity, code=code, message=message, entityIds=uniq(ids)))
    nets = rows(model, 'networks')
    for a, network in enumerate(nets):
        cidr = subnet(network.get('cidr'))
        if not cidr:
            add('network-address-unknown', 'warning', title(network) + ': subnet is missing or is not a CIDR.', [network['id']])
        if network.get('gateway'):
            gateway = ip(network['gateway'])
            if not gateway:
                add('gateway-unknown', 'warning', title(network) + ': gateway is not a parseable IP address.', [network['id']])
            elif cidr and not contains(cidr, gateway):
                add('gateway-outside-subnet', 'error', title(network) + ': gateway is outside its subnet.', [network['id']])
        for other in nets[a + 1:]:
            other_cidr = subnet(other.get('cidr'))
            if network.get('vrfId', '') == other.get('vrfId', '') and cidr and other_cidr and cidr.version == other_cidr.version and cidr.overlaps(other_cidr):
                add('overlapping-subnets', 'error', 'Subnets overlap in the same routing context.', [network['id'], other['id']])
    addresses = {}
    for interface in rows(model, 'interfaces'):
        address = ip(interface.get('address'))
        network = by_id.get(interface.get('networkId'), {})
        cidr = subnet(network.get('cidr'))
        if interface.get('address') and not address:
            add('interface-address-unknown', 'warning', title(interface) + ': address contains unresolved or unparseable design text.', [interface['id']])
        if address:
            key = (network.get('vrfId', ''), address.version, int(address))
            if key in addresses:
                add('duplicate-address', 'error', 'Duplicate interface IP address in the same routing context.', [addresses[key], interface['id']])
            else:
                addresses[key] = interface['id']
            if cidr and not contains(cidr, address):
                add('address-outside-subnet', 'error', title(interface) + ': IP address is outside the associated subnet.', [interface['id'], network['id']])
            gateway = ip(interface.get('gateway') or network.get('gateway'))
            if interface.get('gateway') and not gateway:
                add('gateway-unknown', 'warning', title(interface) + ': gateway is unresolved design text.', [interface['id']])
            if gateway and cidr and not contains(cidr, gateway):
                add('gateway-outside-subnet', 'error', title(interface) + ': gateway is outside the associated subnet.', [interface['id']])
        if interface.get('mode') == 'Trunk' and not interface_networks(interface):
            add('trunk-vlans-unknown', 'warning', title(interface) + ': trunk allowed networks are not entered.', [interface['id']])
    for link in rows(model, 'links'):
        ends = [by_id.get(link.get(key + 'InterfaceId'), {}) for key in ('from', 'to')]
        if not all(ends):
            add('cable-ports-unknown', 'info', title(link) + ': select both interface records to analyze its physical path.', [link['id']])
        else:
            for a, b in (ends, list(reversed(ends))):
                if a.get('mode') == 'Trunk':
                    missing = set(interface_networks(b)) - set(interface_networks(a))
                    if missing:
                        add('trunk-vlan-missing', 'error', 'Connected interface networks are absent from the trunk allowed networks.', [link['id'], a['id'], b['id']] + sorted(missing))
    for endpoint in rows(model, 'endpoints'):
        interface = by_id.get(endpoint.get('interfaceId'), {})
        if endpoint.get('address') and interface.get('address') and ip(endpoint['address']) and ip(interface['address']) and ip(endpoint['address']) != ip(interface['address']):
            add('endpoint-address-mismatch', 'warning', title(endpoint) + ': explicit address differs from its linked interface; document a VIP/translation or correct the address.', [endpoint['id'], interface['id']])
        if not effective_address(model, endpoint) and not endpoint.get('dnsName'):
            add('endpoint-address-unknown', 'warning', title(endpoint) + ': neither an address nor a DNS name is documented.', [endpoint['id']])
    for record in rows(model, 'dnsRecords'):
        target = by_id.get(record.get('targetId'), {})
        addresses_target = target_addresses(model, target.get('id', ''))
        known = [ip(a) for a in addresses_target if ip(a)]
        if str(record.get('type', '')).upper() in ('A', 'AAAA'):
            answer = ip(record.get('value'))
            if answer and answer.version != (4 if str(record.get('type', '')).upper() == 'A' else 6):
                add('dns-answer-family', 'error', title(record) + ': answer address family does not match the record type.', [record['id']])
            if answer and known and answer not in known:
                add('dns-target-mismatch', 'warning', title(record) + ': entered answer differs from the linked target addresses.', [record['id'], target.get('id')])
            if not answer and not known:
                add('dns-answer-unknown', 'warning', title(record) + ': no parseable answer or linked target address is available.', [record['id'], target.get('id')])
        if str(record.get('type', '')).upper() in ('CNAME', 'NS', 'PTR'):
            target_name = target_dns_name(model, target.get('id', ''))
            if not record.get('value') and not target_name:
                add('dns-target-name-unknown', 'warning', title(record) + ': target DNS name is unresolved; inventory display names are not assumed to be DNS names.', [record['id']])
            if record.get('value') and target_name and record['value'].rstrip('.').lower() != target_name.rstrip('.').lower():
                add('dns-name-target-mismatch', 'warning', title(record) + ': entered target name differs from the linked DNS name.', [record['id'], target.get('id')])
    for flow in rows(model, 'flows'):
        missing = []
        if not flow.get('protocol'): missing.append('protocol')
        if not no_ports(flow.get('protocol')) and not flow.get('ports'): missing.append('ports')
        if not flow.get('purpose'): missing.append('purpose')
        if not flow.get('requirementIds'): missing.append('requirement/acceptance criteria')
        if missing:
            add('flow-details-unknown', 'warning', title(flow) + ': document ' + ', '.join(missing) + '.', [flow['id']])
        path = physical_path(model, flow.get('sourceId', ''), flow.get('destinationId', ''), flow.get('sourceInterfaceId', ''))
        if path['state'] == 'unknown':
            add('flow-route-unknown', 'warning', title(flow) + ': ' + (' '.join(path['unknowns']) or path['label']), [flow['id']] + path['entityIds'])
        state = policy_state(model, flow)
        if state['state'] != 'documented':
            add('flow-denied' if state['state'] == 'blocked' else 'flow-policy-unknown', 'error' if state['state'] == 'blocked' else 'warning', title(flow) + ': ' + state['reason'], [flow['id']] + state['policyIds'])
        tests = [t for t in rows(model, 'verificationTests') if flow['id'] in t.get('relatedIds', []) or set(t.get('requirementIds', [])).intersection(flow.get('requirementIds', []))]
        if not tests:
            add('flow-verification-missing', 'warning', title(flow) + ': no acceptance test is linked.', [flow['id']])
    for policy in rows(model, 'policies'):
        missing = [name for name in ('owner', 'enforcementDeviceId', 'ruleReference') if not policy.get(name)]
        if missing:
            add('policy-details-unknown', 'warning', title(policy) + ': document ' + ', '.join(missing) + '.', [policy['id']])
    for identity in rows(model, 'identity'):
        if str(identity.get('implementation', '')).lower() in ('', 'undecided'):
            add('identity-provider-undecided', 'info', title(identity) + ': provider capabilities remain an open decision.', [identity['id']])
        if 'idm' in str(identity.get('implementation', '')).lower():
            for obj in rows(model, 'directoryObjects'):
                if obj.get('identityId') == identity['id'] and obj.get('kind') == 'OU':
                    add('directory-capability-review', 'warning', 'Review the planned OU concept against the selected identity implementation and record the supported mapping.', [identity['id'], obj['id']])
    for group in rows(model, 'groups'):
        if str(group.get('kind', '')).lower() in ('ou', 'organizational unit', 'container'):
            add('legacy-directory-group', 'warning', title(group) + ': model organizational containment as a directory object, separately from group membership.', [group['id']])
    for service in rows(model, 'services'):
        instances = [r for r in rows(model, 'serviceInstances') if r.get('serviceId') == service['id']]
        if not instances and not service.get('deviceId'):
            add('service-host-unknown', 'warning', title(service) + ': no instance or legacy host is documented.', [service['id']])
        if 'application' in str(service.get('kind', '')).lower() and not any(d.get('fromServiceId') == service['id'] for d in dependencies(model)) and not any(r.get('from') == service['id'] for r in rows(model, 'relationships')):
            add('service-dependencies-unreviewed', 'info', title(service) + ': dependencies are not recorded; confirm and document whether any are required.', [service['id']])
        if not service.get('owner'):
            add('owner-missing', 'warning', title(service) + ': no operational owner is assigned.', [service['id']])
        for a, first in enumerate(instances):
            for second in instances[a + 1:]:
                shared = set(replica_domains(model, first)) & set(replica_domains(model, second))
                if shared:
                    add('shared-failure-domain', 'warning', 'Service replicas share a host, switch, rack, or entered failure domain; record and verify the intended resilience.', [service['id'], first['id'], second['id']] + sorted(shared))
    tests = rows(model, 'verificationTests')
    if not rows(model, 'requirements') and (rows(model, 'services') or rows(model, 'devices')):
        add('requirements-missing', 'warning', 'No requirements or acceptance criteria are recorded for this design.', [])
    for requirement in rows(model, 'requirements'):
        related = [t for t in tests if requirement['id'] in t.get('requirementIds', [])]
        if not requirement.get('relatedIds') or not requirement.get('acceptanceCriteria') or not related:
            add('requirement-traceability-gap', 'warning', title(requirement) + ': link design records, acceptance criteria, and a verification test.', [requirement['id']])
        if str(requirement.get('status', '')).lower() in ('verified', 'accepted') and not any(test_passes(t, by_id) for t in related):
            add('verified-without-evidence', 'warning', title(requirement) + ': verified/accepted status lacks a passing test with procedure, result, performer, time, and evidence.', [requirement['id']])
    for test in tests:
        if test.get('result') == 'Pass' and not test_passes(test, by_id):
            add('passing-test-incomplete', 'warning', title(test) + ': a Pass label alone is not recorded verification; complete procedure, expected/actual result, performer, time, and evidence.', [test['id']])
    for observation in rows(model, 'observations'):
        if not observation.get('source') or not observation.get('observedAt') or not observation.get('observedBy') or not observation.get('evidenceIds'):
            add('observation-evidence-missing', 'warning', title(observation) + ': record source, observer, time, and evidence for the as-built observation.', [observation['id']])
    return findings


def test_passes(test, by_id):
    return test.get('result') == 'Pass' and all(test.get(k) for k in ('procedure', 'expectedResult', 'actualResult', 'performedBy', 'performedAt')) and any(e in by_id for e in test.get('evidenceIds', []))


def failure_domains(model, entity):
    by_id, result, seen = index(model), [], set()
    current = entity
    while current and current.get('id') not in seen:
        seen.add(current.get('id'))
        result.extend(current.get('failureDomainIds', []))
        if current.get('rackId'): result.append(current['rackId'])
        host = current.get('deviceId') or current.get('hostedBy')
        if host: result.append(host)
        current = by_id.get(host, {})
    return uniq(result)


def replica_domains(model, entity):
    """Shared switches are resilience concerns, not host power-outage causes."""
    by_id = index(model)
    result = failure_domains(model, entity)
    host_ids = set(result + [i.get('deviceId') for i in interfaces(model, entity.get('id', ''))])
    for link in rows(model, 'links'):
        for a, b in [('from', 'to'), ('to', 'from')]:
            target = by_id.get(link.get(b), {})
            if link.get(a) in host_ids and 'switch' in str(target.get('type', '')).lower():
                result.append(target['id'])
    return uniq(result)


def route_for(model, device_id, target, outbound=None, vrf_id=None):
    candidates = []
    for route in rows(model, 'routes'):
        cidr = subnet(route.get('destination'))
        if route.get('deviceId') == device_id and contains(cidr, target) and (not outbound or route.get('interfaceId') == outbound) and (vrf_id is None or route.get('vrfId', '') == vrf_id):
            candidates.append((cidr.prefixlen, -int(route.get('metric') or 0), route))
    return max(candidates, key=lambda entry: (entry[0], entry[1]))[2] if candidates else None


def physical_path(model, source_id, destination_id, source_interface_id=''):
    by_id = index(model)
    starts = [i for i in interfaces(model, source_id) if not source_interface_id or i['id'] == source_interface_id]
    targets = interfaces(model, destination_id)
    if not starts or not targets:
        return dict(state='unknown', label='Endpoint interface/host mapping is incomplete.', entityIds=[], unknowns=['Select endpoint interfaces and document hosting before tracing a physical route.'])
    graph = {i['id']: [] for i in rows(model, 'interfaces')}
    for link in rows(model, 'links'):
        a, b = link.get('fromInterfaceId'), link.get('toInterfaceId')
        if a in graph and b in graph:
            graph[a].append((b, [link['id']], 'cable'))
            graph[b].append((a, [link['id']], 'cable'))
    for device in rows(model, 'devices'):
        own = [i for i in rows(model, 'interfaces') if i.get('deviceId') == device['id']]
        role = (str(device.get('type', '')) + ' ' + str(device.get('role', ''))).lower()
        for a in own:
            for b in own:
                if a['id'] == b['id']: continue
                shared = set(interface_networks(a)) & set(interface_networks(b))
                if ('switch' in role or 'bridge' in role or 'router' in role or 'firewall' in role or 'gateway' in role) and shared:
                    graph[a['id']].append((b['id'], [device['id']], 'switch'))
                elif any(kind in role for kind in ('router', 'firewall', 'gateway')):
                    graph[a['id']].append((b['id'], [device['id']], 'route'))
                elif a.get('aggregateId') == b['id'] or b.get('aggregateId') == a['id'] or (a.get('aggregateId') and a.get('aggregateId') == b.get('aggregateId')):
                    graph[a['id']].append((b['id'], [device['id']], 'aggregate'))
    queue = [(start['id'], [start['id']], []) for start in starts]
    visited, found = set(), None
    target_ids = {i['id'] for i in targets}
    while queue:
        here, path, edges = queue.pop(0)
        if here in visited: continue
        visited.add(here)
        if here in target_ids:
            found = (path, edges)
            break
        for there, ids, kind in graph.get(here, []):
            if there not in visited: queue.append((there, path + [there], edges + [(here, there, ids, kind)]))
    # Same-host communication needs no physical cable, but is not implied across arbitrary VMs.
    if found is None:
        for start in starts:
            for target in targets:
                if start.get('deviceId') == target.get('deviceId'):
                    found = ([start['id'], target['id']], [])
                    break
    if found is None:
        return dict(state='unknown', label='No complete interface-and-cable path is documented.', entityIds=uniq([i['id'] for i in starts + targets]), unknowns=['Document cable ports, switch VLAN membership, and forwarding devices. Network membership alone does not establish a path.'])
    path, edges = found
    source, target = by_id[path[0]], by_id[path[-1]]
    target_address = ip(effective_address(model, by_id.get(destination_id, {}))) or ip(target.get('address'))
    unknowns = []
    if not set(interface_networks(source)).intersection(interface_networks(target)):
        network = by_id.get(source.get('networkId'), {})
        if not ip(source.get('gateway') or network.get('gateway')) and not route_for(model, source.get('deviceId'), target_address):
            unknowns.append('The source has no documented gateway or route toward the destination network.')
        if not any(edge[3] == 'route' for edge in edges):
            unknowns.append('The physical path has no documented routing transition between the endpoint networks.')
    for a_id, b_id, ids, kind in edges:
        if kind == 'route':
            a, b = by_id[a_id], by_id[b_id]
            vrf = by_id.get(b.get('networkId'), {}).get('vrfId', '')
            target_net = subnet(by_id.get(b.get('networkId'), {}).get('cidr'))
            if not contains(target_net, target_address) and not route_for(model, a.get('deviceId'), target_address, b_id, vrf):
                unknowns.append('Document a route on ' + title(by_id.get(a.get('deviceId'), {})) + ' using the entered outbound interface and routing context.')
    # A gateway name/IP alone is insufficient: it must map to a forwarding port
    # on the entered path. Evaluate return routing as well as the forward design.
    if any(edge[3] == 'route' for edge in edges):
        source_address = ip(effective_address(model, by_id.get(source_id, {}))) or ip(source.get('address'))
        for origin, peer, peer_address, direction in [(source, target, target_address, 'forward'), (target, source, source_address, 'return')]:
            network = by_id.get(origin.get('networkId'), {})
            route = route_for(model, origin.get('deviceId'), peer_address, origin['id'], network.get('vrfId', ''))
            gateway = ip(origin.get('gateway') or network.get('gateway') or (route or {}).get('gateway'))
            if not gateway:
                unknowns.append('The ' + direction + ' path has no documented endpoint gateway/next hop.')
            elif not any(ip(by_id[p].get('address')) == gateway and by_id[p].get('deviceId') != origin.get('deviceId') for p in path):
                unknowns.append('The ' + direction + ' gateway does not match a forwarding interface on the entered cable path.')
        for a_id, b_id, ids, kind in reversed(edges):
            if kind == 'route':
                a, b = by_id[b_id], by_id[a_id]
                vrf = by_id.get(b.get('networkId'), {}).get('vrfId', '')
                return_net = subnet(by_id.get(b.get('networkId'), {}).get('cidr'))
                if not contains(return_net, source_address) and not route_for(model, a.get('deviceId'), source_address, b['id'], vrf):
                    unknowns.append('Document a return route on ' + title(by_id.get(a.get('deviceId'), {})) + ' using the entered outbound interface and routing context.')
                if by_id.get(a.get('networkId'), {}).get('vrfId', '') != vrf:
                    unknowns.append('The path crosses routing contexts; the route-leaking design is not established by interface connectivity.')
    return dict(state='unknown' if unknowns else 'documented', label='Entered interface/cable path: ' + ' → '.join(title(by_id[p]) for p in path), entityIds=uniq(path + [source.get('deviceId'), target.get('deviceId')] + [item for _, _, ids, _ in edges for item in ids]), unknowns=unknowns)


def trace(model, options=None, **kwargs):
    options = dict(options or {}, **kwargs)
    by_id = index(model)
    flow = by_id.get(options.get('flowId'), {})
    source = options.get('sourceId') or flow.get('sourceId', '')
    destination = options.get('destinationId') or flow.get('destinationId', '')
    if not flow:
        flow = next((f for f in rows(model, 'flows') if f.get('sourceId') == source and f.get('destinationId') == destination), {})
    steps, unknowns, warnings, related = [], [], [], [source, destination]
    def step(kind, label, ids, state='documented'):
        steps.append(dict(kind=kind, label=label, entityIds=uniq(ids), state=state))
        related.extend(ids)
    if source not in by_id or destination not in by_id:
        unknowns.append('Both source and destination must reference existing design records.')
    step('endpoint', 'Source: ' + title(by_id.get(source, {})) + '; destination: ' + title(by_id.get(destination, {})), [source, destination], 'documented' if source in by_id and destination in by_id else 'unknown')
    for endpoint_id in (source, destination):
        host_ids = uniq(i.get('deviceId') for i in interfaces(model, endpoint_id))
        step('hosting', title(by_id.get(endpoint_id, {})) + ': ' + (', '.join(title(by_id.get(h, {})) for h in host_ids) or 'host mapping unresolved'), [endpoint_id] + host_ids, 'documented' if host_ids else 'unknown')
    resolver_rows = [r for r in rows(model, 'resolverAssignments') if r.get('clientId') in equivalents(model, source)]
    for resolver in resolver_rows:
        step('dns', 'Configured resolver endpoints: ' + (', '.join(title(by_id.get(e, {})) for e in resolver.get('resolverEndpointIds', [])) or 'not entered'), [resolver['id']] + resolver.get('resolverEndpointIds', []), 'documented' if resolver.get('resolverEndpointIds') else 'unknown')
    destination_equiv = equivalents(model, destination)
    dns_rows = [r for r in rows(model, 'dnsRecords') if r.get('targetId') in destination_equiv]
    for record in dns_rows:
        step('dns', title(record) + ' resolves to ' + title(by_id.get(record.get('targetId'), {})), [record['id'], record.get('targetId')])
    if (dns_rows or by_id.get(destination, {}).get('dnsName')) and not resolver_rows:
        unknowns.append('Destination uses DNS but no resolver assignment is documented for the source.')
    for relation in rows(model, 'relationships'):
        if relation.get('from') in uniq(equivalents(model, source) + destination_equiv) and relation.get('kind') in ('authenticates', 'uses-license', 'depends', 'resolves', 'forwards', 'access'):
            step('dependency', relation.get('kind', '') + ': ' + title(by_id.get(relation.get('from'), {})) + ' → ' + title(by_id.get(relation.get('to'), {})) + ' (logical dependency; separate path required)', [relation['id'], relation.get('from'), relation.get('to')])
    for dep in dependencies(model):
        if dep.get('fromServiceId') in destination_equiv:
            step('dependency', dep.get('kind', 'Runtime') + ' / ' + dep.get('requirement', 'All') + ': requires ' + title(by_id.get(dep.get('toServiceId'), {})) + ' (logical dependency; separate path required)', [dep.get('id'), dep.get('fromServiceId'), dep.get('toServiceId')])
    network_ids = uniq(networks(model, source) + networks(model, destination))
    step('network', 'Endpoint networks: ' + (', '.join(title(by_id.get(n, {})) for n in network_ids) or 'unresolved'), network_ids, 'documented' if network_ids else 'unknown')
    if not flow:
        unknowns.append('No communication flow records the initiator, protocol, ports, policy, and acceptance requirement for this pair.')
        policy = dict(state='unknown', policyIds=[], reason='No communication flow is documented.')
    else:
        if not flow.get('protocol') or (not no_ports(flow.get('protocol')) and not flow.get('ports')):
            unknowns.append('Flow protocol or transport ports remain unresolved.')
        policy = policy_state(model, flow)
        related.append(flow['id'])
    step('enforcement', policy['reason'], policy['policyIds'] + (flow.get('enforcementDeviceIds', []) if flow else []), policy['state'])
    if policy['state'] == 'unknown': unknowns.append(policy['reason'])
    path = physical_path(model, source, destination, flow.get('sourceInterfaceId', ''))
    step('physical-path', path['label'], path['entityIds'], path['state'])
    unknowns.extend(path['unknowns'])
    if any(f['code'] == 'trunk-vlan-missing' and set(f['entityIds']).intersection(path['entityIds']) for f in lint(model)):
        warnings.append('A modeled trunk is missing a connected VLAN; resolve the design error before accepting this path.')
        unknowns.append('VLAN continuity is inconsistent on the entered path.')
    if flow and not any(flow['id'] in t.get('relatedIds', []) or set(flow.get('requirementIds', [])).intersection(t.get('requirementIds', [])) for t in rows(model, 'verificationTests')):
        warnings.append('No acceptance test is linked to this communication flow.')
    state = 'blocked' if policy['state'] == 'blocked' else 'unknown' if unknowns or any(s['state'] == 'unknown' for s in steps) else 'documented'
    return dict(status=state, summary='Blocked by entered policy.' if state == 'blocked' else 'Design path is documented; this is not a live reachability result.' if state == 'documented' else 'The design contains unresolved path or policy information.', steps=steps, unknowns=uniq(unknowns), warnings=uniq(warnings), relatedIds=uniq(related), modelOnly=True, limitations=LIMIT)


def impact(model, options=None, **kwargs):
    options = dict(options or {}, **kwargs)
    by_id = index(model)
    failed = uniq(options.get('failedIds', []))
    lost, degraded, explanations, unknowns = set(failed), set(), [], []
    def explain(entity_id, cause, message):
        item = dict(entityId=entity_id, causeIds=uniq(cause), message=message)
        if item not in explanations: explanations.append(item)
    for entity_id in failed:
        if entity_id not in by_id: unknowns.append('Unknown failed record: ' + entity_id)
    instances = rows(model, 'serviceInstances')
    # Direct structural outages propagate through hosting, domains, interfaces and endpoints.
    for _ in range(len(by_id) + 1):
        before = set(lost)
        for collection in ('devices', 'interfaces', 'serviceInstances', 'endpoints'):
            for entity in rows(model, collection):
                causes = [r for r in [entity.get('hostedBy'), entity.get('deviceId'), entity.get('instanceId'), entity.get('interfaceId'), entity.get('networkId')] + failure_domains(model, entity) if r in lost]
                if causes:
                    lost.add(entity['id'])
                    explain(entity['id'], causes, 'Unavailable because an entered host, interface, network, or failure domain failed.')
        for instance in instances:
            instance_endpoints = [e for e in rows(model, 'endpoints') if e.get('instanceId') == instance['id']]
            if instance_endpoints and all(e['id'] in lost for e in instance_endpoints):
                lost.add(instance['id'])
                explain(instance['id'], [e['id'] for e in instance_endpoints], 'All entered endpoints for this instance are unavailable.')
        if before == lost: break
    # Physical equipment does not power off when a switch/cable fails. Flag the actual cable-connected neighborhood as connectivity uncertainty.
    adjacency = {}
    for link in rows(model, 'links'):
        if link.get('from') in by_id and link.get('to') in by_id:
            adjacency.setdefault(link['from'], []).append((link['to'], link['id']))
            adjacency.setdefault(link['to'], []).append((link['from'], link['id']))
    queue, seen = [], set()
    for entity_id in failed:
        if entity_id in adjacency: queue.append(entity_id)
        for link in rows(model, 'links'):
            if entity_id in (link['id'], link.get('fromInterfaceId'), link.get('toInterfaceId')):
                queue.extend([link.get('from'), link.get('to')])
    while queue:
        here = queue.pop(0)
        if here in seen: continue
        seen.add(here)
        for neighbor, link_id in adjacency.get(here, []):
            if neighbor not in lost:
                degraded.add(neighbor)
                explain(neighbor, failed, 'Entered cabling intersects the failure; connectivity or redundancy may be affected. Alternate paths require verification.')
            role = str(by_id.get(neighbor, {}).get('type', '')).lower()
            if any(t in role for t in ('switch', 'router', 'firewall', 'gateway')) and neighbor not in seen: queue.append(neighbor)
    for instance in instances:
        if set(failure_domains(model, instance)).intersection(degraded) or instance.get('deviceId') in degraded:
            degraded.add(instance['id'])
    state = {s['id']: 'affected' if s['id'] in lost else 'available' for s in rows(model, 'services')}
    deps = dependencies(model)
    for _ in range(len(state) * 3 + 1):
        old = dict(state)
        for service in rows(model, 'services'):
            sid = service['id']
            if sid in failed:
                next_state = 'affected'
            else:
                own = [i for i in instances if i.get('serviceId') == sid]
                if own:
                    alive = [i for i in own if i['id'] not in lost]
                    documented = [i for i in alive if i.get('deviceId') or interfaces(model, i['id'])]
                    next_state = 'affected' if not alive else 'unknown' if not documented else 'degraded' if len(alive) < len(own) or len(documented) < len(alive) or any(i['id'] in degraded for i in alive) else 'available'
                    if not documented and alive:
                        unknowns.append(title(service) + ': surviving instances have no host assignment, so availability is unresolved.')
                elif service.get('deviceId'):
                    next_state = 'affected' if service['deviceId'] in lost else 'degraded' if service['deviceId'] in degraded else 'available'
                elif any(i.get('deviceId') not in lost for i in interfaces(model, sid)):
                    next_state = 'degraded' if any(i.get('deviceId') in degraded for i in interfaces(model, sid)) else 'available'
                else:
                    next_state = 'unknown'
                    unknowns.append(title(service) + ': instance/host is undocumented, so direct availability cannot be determined.')
                service_endpoints = [e for e in rows(model, 'endpoints') if e.get('serviceId') == sid]
                if not service_endpoints and next_state != 'affected':
                    next_state = 'unknown'
                    unknowns.append(title(service) + ': no service endpoints are documented; surviving hosting does not establish availability to clients.')
                if service_endpoints and all(e['id'] in lost for e in service_endpoints):
                    next_state = 'affected'
                    explain(sid, [e['id'] for e in service_endpoints], 'All entered service endpoints are unavailable.')
                own_deps = [d for d in deps if d.get('fromServiceId') == sid]
                alternatives = {}
                for dep in own_deps:
                    target_state = state.get(dep.get('toServiceId'), 'unknown')
                    if dep.get('kind') == 'Optional':
                        if target_state != 'available' and next_state not in ('affected', 'unknown'): next_state = 'degraded'
                    elif dep.get('requirement') == 'Any' or dep.get('kind') == 'Fallback':
                        alternatives.setdefault(dep.get('kind', 'Runtime'), []).append(dep)
                    elif target_state == 'affected':
                        next_state = 'affected'
                        explain(sid, [dep['toServiceId']], 'Required ' + dep.get('kind', 'Runtime') + ' dependency is unavailable.')
                    elif target_state == 'unknown' and next_state != 'affected': next_state = 'unknown'
                    elif target_state == 'degraded' and next_state not in ('affected', 'unknown'): next_state = 'degraded'
                for group in alternatives.values():
                    states = [state.get(d.get('toServiceId'), 'unknown') for d in group]
                    if states and all(s == 'affected' for s in states):
                        next_state = 'affected'
                        explain(sid, [d['toServiceId'] for d in group], 'All entered alternative dependencies are unavailable.')
                    elif not any(s in ('available', 'degraded') for s in states) and any(s == 'unknown' for s in states) and next_state != 'affected': next_state = 'unknown'
                    elif any(s != 'available' for s in states) and next_state not in ('affected', 'unknown'): next_state = 'degraded'
            state[sid] = next_state
        if state == old: break
    for sid, value in state.items():
        if value == 'affected': lost.add(sid)
        if value in ('degraded', 'unknown'): degraded.add(sid)
    degraded.difference_update(lost)
    return dict(failedIds=failed, affectedIds=sorted(lost), degradedIds=sorted(degraded), unaffectedServiceIds=sorted(s for s, value in state.items() if value == 'available'), availableServiceIds=sorted(s for s, value in state.items() if value in ('available', 'degraded')), unknownServiceIds=sorted(s for s, value in state.items() if value == 'unknown'), serviceStates=state, explanations=explanations, unknowns=uniq(unknowns), modelOnly=True, limitations=LIMIT)


def md(value):
    return str(value if value not in (None, '') else 'Unspecified').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '\\|').replace('\r', ' ').replace('\n', ' ')


def table(headers, values):
    return '| ' + ' | '.join(headers) + ' |\n| ' + ' | '.join('---' for _ in headers) + ' |\n' + '\n'.join('| ' + ' | '.join(md(v) for v in row) + ' |' for row in values) + '\n'


def csv_report(headers, values):
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\r\n')
    def cell(value):
        text = str(value if value is not None else '')
        return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text
    writer.writerow(['Scope'] + headers)
    for row in values: writer.writerow([LIMIT] + [cell(value) for value in row])
    return output.getvalue()


def report(model, options=None, **kwargs):
    options = dict(options or {}, **kwargs)
    kind, by_id = options.get('kind', 'handoff'), index(model)
    name = lambda entity_id: title(by_id.get(entity_id, {})) if entity_id else 'Unspecified'
    names = lambda ids: '; '.join(name(i) for i in ids)
    if kind == 'addresses':
        values = []
        for interface in rows(model, 'interfaces'):
            network = by_id.get(interface.get('networkId'), {})
            values.append([name(interface.get('deviceId')), title(interface), name(interface.get('networkId')), name(network.get('vrfId')), interface.get('address', ''), interface.get('gateway') or network.get('gateway', ''), interface.get('mode', ''), names(interface.get('taggedNetworkIds', [])), ''])
        for endpoint in rows(model, 'endpoints'):
            values.append([names(uniq(i.get('deviceId') for i in interfaces(model, endpoint['id']))), name(endpoint.get('interfaceId')), names(networks(model, endpoint['id'])), '', effective_address(model, endpoint), '', '', '', title(endpoint)])
        return csv_report(['Device', 'Interface', 'Network', 'Routing context', 'Address', 'Gateway', 'Mode', 'Tagged networks', 'Service endpoint'], values)
    if kind == 'ports':
        return csv_report(['Connection', 'From device', 'From port', 'To device', 'To port', 'Status'], [[title(l), name(l.get('from')), name(l.get('fromInterfaceId')), name(l.get('to')), name(l.get('toInterfaceId')), l.get('status', '')] for l in rows(model, 'links')])
    if kind == 'flows':
        values = []
        for flow in rows(model, 'flows'):
            state = policy_state(model, flow)
            policies = [by_id.get(p, {}) for p in state['policyIds']]
            values.append([title(flow), name(flow.get('sourceId')), name(flow.get('destinationId')), flow.get('direction', ''), flow.get('protocol', ''), flow.get('ports', ''), flow.get('purpose', ''), names(uniq(zones(model, flow.get('sourceId')) + zones(model, flow.get('destinationId')) + flow.get('zoneIds', []))), names(uniq(flow.get('enforcementDeviceIds', []) + [p.get('enforcementDeviceId') for p in policies])), names(state['policyIds']), '; '.join(uniq(p.get('owner') for p in policies)), state['state'], names(flow.get('requirementIds', []))])
        return csv_report(['Flow', 'Initiator', 'Destination', 'Direction', 'Protocol', 'Ports', 'Purpose', 'Zones', 'Enforcement', 'Policies', 'Policy owner', 'Design policy state', 'Acceptance requirements'], values)
    heading = '# ' + md(model.get('meta', {}).get('name', 'Design')) + ' — ' + {'handoff': 'Architecture handoff', 'build': 'Build order', 'requirements': 'Requirement traceability'}.get(kind, kind) + '\n\n' + LIMIT + '\n\n'
    if kind == 'requirements':
        values = []
        for requirement in rows(model, 'requirements'):
            linked = requirement.get('relatedIds', [])
            tasks = [t for t in rows(model, 'tasks') if t.get('relatedId') in [requirement['id']] + linked or set(t.get('requirementIds', [])).intersection([requirement['id']])]
            tests = [t for t in rows(model, 'verificationTests') if requirement['id'] in t.get('requirementIds', [])]
            values.append([title(requirement), requirement.get('owner'), names(linked), names(requirement.get('decisionIds', [])), '; '.join(title(t) + ': ' + t.get('status', '') for t in tasks), requirement.get('acceptanceCriteria'), '; '.join(title(t) + ': ' + t.get('result', 'Not run') for t in tests), names(uniq(e for t in tests for e in t.get('evidenceIds', []))), 'Recorded pass with evidence' if any(test_passes(t, by_id) for t in tests) else 'Verification incomplete'])
        return heading + table(['Requirement', 'Owner', 'Design records', 'Decisions', 'Implementation tasks', 'Acceptance criteria', 'Tests', 'Evidence', 'Verification'], values) + '\nTask completion does not imply test success or verified implementation.\n'
    if kind == 'build':
        remaining = {s['id'] for s in rows(model, 'services')}
        deps = [d for d in dependencies(model) if d.get('kind') == 'Startup']
        complete, stages = set(), []
        while remaining:
            ready = []
            for sid in sorted(remaining):
                own = [d for d in deps if d.get('fromServiceId') == sid]
                all_deps = [d['toServiceId'] for d in own if d.get('requirement') != 'Any']
                any_deps = [d['toServiceId'] for d in own if d.get('requirement') == 'Any']
                if all(d in complete for d in all_deps) and (not any_deps or any(d in complete for d in any_deps)): ready.append(sid)
            if not ready: break
            stages.append(ready); complete.update(ready); remaining.difference_update(ready)
        body = 'Confirm rack/power, management access, interface addressing, cabling, and network policies before service acceptance. The order below uses entered Startup dependencies only; Runtime, Optional, and Fallback dependencies are not installation-order claims.\n\n'
        body += '\n'.join(str(n + 1) + '. ' + names(stage) for n, stage in enumerate(stages)) + '\n'
        if remaining: body += '\nUnresolved startup cycle or missing prerequisite: ' + names(sorted(remaining)) + '\n'
        body += '\n' + table(['Task', 'Owner', 'Status', 'Related design'], [[title(t), t.get('owner'), t.get('status'), name(t.get('relatedId'))] for t in rows(model, 'tasks')])
        return heading + body
    if kind != 'handoff': raise ValueError('Unknown report kind: ' + str(kind))
    body = '## Design context\n\n' + md(model.get('meta', {}).get('description', '')) + '\n\nPhase: ' + md(model.get('meta', {}).get('phase', '')) + '\n\n'
    body += '## Service catalog\n\n' + table(['Service', 'Owner', 'Instances / host', 'Endpoints', 'Dependencies'], [[title(s), s.get('owner'), names([i['id'] for i in rows(model, 'serviceInstances') if i.get('serviceId') == s['id']]) or name(s.get('deviceId')), names([e['id'] for e in rows(model, 'endpoints') if e.get('serviceId') == s['id']]), '; '.join(d.get('kind', 'Runtime') + '/' + d.get('requirement', 'All') + ': ' + name(d.get('toServiceId')) for d in dependencies(model) if d.get('fromServiceId') == s['id'])] for s in rows(model, 'services')])
    body += '\n## Ownership\n\n' + table(['Record', 'Owner', 'Lifecycle'], [[title(r), r.get('owner'), r.get('status')] for key in ('devices', 'networks', 'services', 'requirements') for r in rows(model, key)])
    body += '\n## Decisions and open questions\n\n' + table(['Decision', 'Status', 'Owner', 'Alternatives', 'Rationale'], [[title(d), d.get('status'), d.get('owner'), '; '.join(title(o) for o in d.get('options', [])), d.get('rationale')] for d in rows(model, 'decisions')])
    body += '\n## Design checks\n\n' + table(['Severity', 'Check', 'Finding', 'Records'], [[f['severity'], f['code'], f['message'], names(f['entityIds'])] for f in lint(model)])
    body += '\n' + report(model, dict(kind='requirements')) + '\n' + report(model, dict(kind='build'))
    return heading + body
