#!/usr/bin/env python3
"""Offline Design Studio JSON tools. Python standard library only; no network or eval.

Concurrency fingerprint: canonical compact JSON with UTF-16 sorted object keys and
JavaScript-compatible JSON scalar serialization, then FNV-1a32 over UTF-16 code
units. Output is ds1- plus eight lowercase hex digits. This detects stale edits;
it is not a cryptographic integrity or authentication mechanism.
"""
from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
from decimal import Decimal
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
ARCH_SCHEMA = json.loads((ROOT/'src'/'architecture-schema.json').read_text(encoding='utf-8'))
ARCH_COLLECTIONS = tuple(key for key in ARCH_SCHEMA if key not in ('devices','networks','interfaces','groups'))
NODE_COLLECTIONS = ('devices','networks','services','identity','groups','dnsZones','dnsRecords','racks','vrfs','securityZones','failureDomains','serviceInstances','endpoints','directoryObjects','principals')
OPTIONAL_COLLECTIONS = ('identity','groups','dnsZones','dnsRecords','relationships') + ARCH_COLLECTIONS
COLLECTIONS = ('devices','networks','services','interfaces','links','decisions','tasks','evidence','comments','diagrams') + OPTIONAL_COLLECTIONS
NAMED = {'devices','networks','services','interfaces','evidence','diagrams','identity','groups','dnsZones','dnsRecords'} | set(ARCH_COLLECTIONS)
RESERVED = {'__proto__','constructor','prototype'}
REQUIRED = {
    'devices':'id name type owner status networkId rackU height notes',
    'networks':'id name cidr vlan purpose owner status',
    'services':'id name platform owner status deviceId networkId notes dependsOn',
    'interfaces':'id name deviceId networkId address mac speed status notes',
    'links':'id from to label status',
    'decisions':'id title status owner due context options selectedOptionId rationale relatedIds',
    'tasks':'id title owner status due relatedId',
    'evidence':'id name mime data caption relatedId createdAt',
    'comments':'id entityId author text createdAt resolved',
    'diagrams':'id name nodeIds notes',
    'identity':'id name serviceId implementation domain realm notes status',
    'groups':'id name identityId parentId kind memberIds accessIds notes status',
    'dnsZones':'id name serviceId kind notes status',
    'dnsRecords':'id name zoneId type value targetId ttl notes status',
    'relationships':'id from to kind label protocol port endpoint notes status',
}
REQUIRED.update({key:descriptor['required'] for key,descriptor in ARCH_SCHEMA.items()})


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')


def read_json(path):
    def bad_constant(value):
        raise ValueError('Invalid JSON constant: ' + value)
    with Path(path).open(encoding='utf-8') as stream:
        value = json.load(stream, parse_constant=bad_constant)
    return value


def unsafe_keys(value):
    errors, stack = [], [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, child in item.items():
                if key in RESERVED:
                    errors.append('Unsupported property key: ' + key)
                stack.append(child)
        elif isinstance(item, list):
            stack.extend(item)
    return errors


def integer(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r'[0-9]+', value):
        return int(value)
    return None


def empty(value):
    return value is None or value == ''


def normalize_model(model):
    """Clone a model and add only absent, backwards-compatible collections.

    Existing malformed values remain intact so validation cannot silently repair
    invalid input. Fingerprints are calculated after this migration by callers.
    """
    result = copy.deepcopy(model)
    if isinstance(result,dict):
        for collection in OPTIONAL_COLLECTIONS:
            result.setdefault(collection,[])
    return result


def validate(model):
    errors = unsafe_keys(model)
    if not isinstance(model, dict):
        return errors + ['Project must be a JSON object.']
    if type(model.get('schemaVersion')) is not int or model.get('schemaVersion') != 1:
        errors.append('Unsupported schemaVersion; expected 1.')
    meta = model.get('meta')
    if not isinstance(meta, dict):
        return errors + ['Project metadata is required.']
    def string(value, path, required=False):
        if not isinstance(value, str) or (required and not value.strip()):
            errors.append(path + (' must be a nonempty string.' if required else ' must be a string.'))
    for key in ('id','name','phase'):
        string(meta.get(key), 'meta.'+key, True)
    for key in ('description','author','rackName','classification','classificationColor'):
        if key in meta:
            string(meta[key], 'meta.'+key)
    rack_units = integer(meta.get('rackUnits'))
    if rack_units is None or not 1 <= rack_units <= 200:
        errors.append('meta.rackUnits must be an integer from 1 to 200.')
    color = meta.get('classificationColor')
    if not empty(color) and (not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',color)):
        errors.append('meta.classificationColor must be a six digit hex color.')
    ids, lookup, typed, rows = set(), {}, {}, {}
    def claim(value, path):
        string(value, path, True)
        if isinstance(value,str):
            if value in RESERVED:
                errors.append(path+' uses a reserved ID.')
            if value in ids:
                errors.append('Duplicate ID: '+value)
            ids.add(value)
    claim(meta.get('id'), 'meta.id')
    for collection in COLLECTIONS:
        values = model.get(collection,[]) if collection in OPTIONAL_COLLECTIONS else model.get(collection)
        typed[collection], rows[collection] = set(), []
        if not isinstance(values,list):
            errors.append(collection+' must be an array.')
            continue
        for index,row in enumerate(values):
            path = f'{collection}[{index}]'
            if not isinstance(row,dict):
                errors.append(path+' must be an object.')
                continue
            rows[collection].append(row)
            claim(row.get('id'), path+'.id')
            if isinstance(row.get('id'),str):
                typed[collection].add(row['id'])
                lookup[row['id']] = (collection,row)
            if collection in NAMED:
                string(row.get('name'),path+'.name',True)
            if collection in ('decisions','tasks'):
                string(row.get('title'),path+'.title',True)
            if collection in ('devices','networks','services','interfaces','links','decisions','tasks') + OPTIONAL_COLLECTIONS:
                string(row.get('status'),path+'.status',True)
            for field in ('owner','notes','description','purpose','platform','type','label','caption','author','context','rationale','address','mac','speed','kind','endpoint','protocol','port','licenseManager','redundancy','implementation','domain','realm','value'):
                if field in row:
                    string(row[field],path+'.'+field)
            if not empty(row.get('due')):
                try:
                    if not isinstance(row['due'],str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',row['due']):
                        raise ValueError()
                    dt.date.fromisoformat(row['due'])
                except (ValueError,TypeError):
                    errors.append(path+'.due must be a valid YYYY-MM-DD date.')
            if 'createdAt' in row:
                try:
                    if not isinstance(row['createdAt'],str):
                        raise ValueError()
                    dt.datetime.fromisoformat(row['createdAt'].replace('Z','+00:00'))
                except (ValueError,TypeError):
                    errors.append(path+'.createdAt must be a valid date/time string.')
    entities = set(lookup)
    physical_nodes = typed['devices'] | typed['networks'] | typed['services']
    nodes = set().union(*(typed[key] for key in NODE_COLLECTIONS))
    def reference(value,allowed,path,required=False):
        if empty(value):
            if required:
                errors.append(path+' is required.')
        elif not isinstance(value,str) or value not in allowed:
            errors.append(path+' references an unknown or invalid ID.')
    def refs(values,allowed,path):
        if not isinstance(values,list):
            errors.append(path+' must be an array.')
            return
        seen = set()
        for value in values:
            reference(value,allowed,path,True)
            if isinstance(value,str):
                if value in seen:
                    errors.append(path+' has a duplicate ID: '+value)
                seen.add(value)
    def lookup_entity(value):
        return lookup.get(value,(None,{})) if isinstance(value,str) else (None,{})
    def allowed_for(field):
        allowed = set()
        for key in field.get('references',[]):
            allowed.update(entities if key == 'entities' else nodes if key == 'nodes' else typed.get(key,set()))
        return allowed
    for collection,descriptor in ARCH_SCHEMA.items():
        for row in rows[collection]:
            path = collection+' '+str(row.get('id','?'))
            is_new = collection in ARCH_COLLECTIONS
            if is_new:
                for key in descriptor['required'].split():
                    if key not in row:
                        errors.append(path+' is missing required field '+key+'.')
            for key,field in descriptor['fields'].items():
                if key not in row:
                    continue
                value,where = row[key],path+' '+key
                kind = field['type']
                if kind == 'string':
                    string(value,where)
                elif kind == 'reference':
                    reference(value,allowed_for(field),where,field.get('requiredReference',False))
                elif kind == 'references':
                    refs(value,allowed_for(field),where)
                elif kind == 'strings':
                    if not isinstance(value,list) or any(not isinstance(item,str) for item in value):
                        errors.append(where+' must be an array of strings.')
                elif kind == 'enum':
                    if not isinstance(value,str) or not (not is_new and value == '' or value in field['options']):
                        errors.append(where+' must be one of '+', '.join(field['options'])+'.')
                elif kind == 'integer':
                    if field.get('blank') and empty(value):
                        continue
                    n = integer(value)
                    try:
                        finite = n is not None and math.isfinite(float(n))
                    except (OverflowError,ValueError):
                        finite = False
                    if not finite or ('minimum' in field and n < field['minimum']) or ('maximum' in field and n > field['maximum']):
                        errors.append(where+' must be an integer within the documented bounds.')
    occupied = {}
    for row in rows['devices']:
        path = 'Device '+str(row.get('id','?'))
        reference(row.get('networkId'),typed['networks'],path+' networkId')
        if not empty(row.get('hostedBy')):
            reference(row['hostedBy'],typed['devices'],path+' hostedBy')
            if row['hostedBy'] == row.get('id'):
                errors.append(path+' cannot host itself.')
            if not empty(row.get('rackU')):
                errors.append(path+' is hosted equipment and cannot occupy rack units.')
        rack_kind,rack = lookup_entity(row.get('rackId'))
        units = integer(rack.get('units')) if rack_kind == 'racks' else rack_units
        height = integer(row.get('height'))
        if height is None or height < 1 or units is None or height > units:
            errors.append(path+' height must be a positive integer within the rack height.')
        if not empty(row.get('rackU')):
            unit = integer(row['rackU'])
            if unit is None or unit < 1 or height is None or height < 1 or units is None or not 1 <= units <= 200 or unit+height-1 > units:
                errors.append(path+' does not fit inside the rack.')
            else:
                for u in range(unit,unit+height):
                    key = (row.get('rackId') if isinstance(row.get('rackId'),str) and row.get('rackId') else 'legacy-rack',u)
                    if key in occupied:
                        errors.append(f'Rack overlap at U{u}: {occupied[key]} and {row.get("id")}')
                    occupied[key] = row.get('id')
        image = row.get('panelImage')
        if not empty(image):
            match = re.fullmatch(r'data:image/(?:png|jpeg|gif|webp|svg\+xml);base64,([a-z0-9+/]+={0,2})',image,re.I) if isinstance(image,str) else None
            if not match or len(match[1]) % 4:
                errors.append(path+' panelImage must be an embedded base64 image data URL.')
    for row in rows['networks']:
        vlan = integer(row.get('vlan'))
        if not empty(row.get('vlan')) and (vlan is None or not 1 <= vlan <= 4094):
            errors.append('Network VLAN must be empty or an integer from 1 to 4094.')
        if not empty(row.get('cidr')):
            try:
                if not isinstance(row['cidr'],str) or '/' not in row['cidr']:
                    raise ValueError()
                ipaddress.ip_interface(row['cidr'])
            except (ValueError,TypeError):
                errors.append('Network CIDR must be empty or valid CIDR notation.')
    for row in rows['services']:
        reference(row.get('deviceId'),typed['devices'],'Service deviceId')
        reference(row.get('networkId'),typed['networks'],'Service networkId')
        refs(row.get('dependsOn'),typed['services'],'Service dependsOn')
    for row in rows['identity']:
        string(row.get('implementation'),'Identity implementation',True)
        reference(row.get('serviceId'),typed['services'],'Identity serviceId')
    group_members = typed['groups'] | typed['devices'] | typed['services'] | typed['principals']
    for row in rows['groups']:
        string(row.get('kind'),'Group kind',True)
        reference(row.get('identityId'),typed['identity'],'Group identityId',True)
        reference(row.get('parentId'),typed['groups'],'Group parentId')
        parent = row.get('parentId')
        if isinstance(parent,str) and parent in typed['groups'] and lookup[parent][1].get('identityId') != row.get('identityId'):
            errors.append('Group parent must belong to the same identity system.')
        refs(row.get('memberIds'),group_members,'Group memberIds')
        refs(row.get('accessIds'),typed['services'],'Group accessIds')
    for row in rows['dnsZones']:
        string(row.get('kind'),'DNS zone kind',True)
        reference(row.get('serviceId'),typed['services'],'DNS zone serviceId')
    for row in rows['dnsRecords']:
        string(row.get('type'),'DNS record type',True)
        reference(row.get('zoneId'),typed['dnsZones'],'DNS record zoneId',True)
        reference(row.get('targetId'),typed['services'] | typed['devices'] | typed['dnsRecords'] | typed['endpoints'],'DNS record targetId')
        if row.get('targetId') == row.get('id'):
            errors.append('DNS record cannot target itself.')
        ttl = integer(row.get('ttl'))
        if not empty(row.get('ttl')) and (ttl is None or ttl < 0):
            errors.append('DNS record TTL must be empty or a nonnegative integer.')
    for row in rows['relationships']:
        reference(row.get('from'),nodes,'Relationship from',True)
        reference(row.get('to'),nodes,'Relationship to',True)
        if row.get('from') == row.get('to'):
            errors.append('Relationship cannot connect an item to itself.')
        if not isinstance(row.get('kind'),str) or row['kind'] not in ('authenticates','resolves','uses-license','hosts','forwards','depends','access'):
            errors.append('Relationship kind is not supported.')
    for row in rows['interfaces']:
        reference(row.get('deviceId'),typed['devices'],'Interface deviceId',True)
        reference(row.get('networkId'),typed['networks'],'Interface networkId')
    for row in rows['links']:
        reference(row.get('from'),physical_nodes,'Link from',True)
        reference(row.get('to'),physical_nodes,'Link to',True)
        if row.get('from') == row.get('to'):
            errors.append('Link cannot connect an item to itself.')
        for end in ('from','to'):
            port = row.get(end+'InterfaceId')
            reference(port,typed['interfaces'],'Link '+end+'InterfaceId')
            if isinstance(port,str) and port in typed['interfaces'] and lookup[port][1].get('deviceId') != row.get(end):
                errors.append('Link '+end+' interface does not belong to its device.')
        if not empty(row.get('fromInterfaceId')) and row.get('fromInterfaceId') == row.get('toInterfaceId'):
            errors.append('Link cannot connect an interface to itself.')
    for row in rows['interfaces']:
        kind,aggregate = lookup_entity(row.get('aggregateId'))
        if kind == 'interfaces':
            if aggregate.get('deviceId') != row.get('deviceId'):
                errors.append('Interface aggregate must belong to the same device.')
            if aggregate.get('mode') != 'Bond':
                errors.append('Interface aggregate must reference an interface in Bond mode.')
    for row in rows['directoryObjects']:
        kind,parent = lookup_entity(row.get('parentId'))
        if kind == 'directoryObjects' and parent.get('identityId') != row.get('identityId'):
            errors.append('Directory container parent must belong to the same identity.')
    for row in rows['principals']:
        kind,container = lookup_entity(row.get('containerId'))
        if kind == 'directoryObjects' and container.get('identityId') != row.get('identityId'):
            errors.append('Principal container must belong to the same identity.')
    for row in rows['groups']:
        kind,container = lookup_entity(row.get('containerId'))
        if kind == 'directoryObjects' and container.get('identityId') != row.get('identityId'):
            errors.append('Group container must belong to the same identity.')
        for member_id in row.get('memberIds',[]) if isinstance(row.get('memberIds'),list) else []:
            kind,member = lookup_entity(member_id)
            if kind in ('groups','principals') and member.get('identityId') != row.get('identityId'):
                errors.append('Group members must belong to the same identity.')
    for row in rows['endpoints']:
        instance_kind,instance = lookup_entity(row.get('instanceId'))
        port_kind,port = lookup_entity(row.get('interfaceId'))
        if instance_kind == 'serviceInstances' and instance.get('serviceId') != row.get('serviceId'):
            errors.append('Endpoint instance must provide its service.')
        if instance_kind == 'serviceInstances' and port_kind == 'interfaces' and not empty(instance.get('deviceId')) and port.get('deviceId') != instance.get('deviceId'):
            errors.append('Endpoint interface must belong to its instance device.')
        if port_kind == 'interfaces' and not empty(row.get('networkId')):
            networks = [port.get('networkId'),port.get('untaggedNetworkId')] + (port.get('taggedNetworkIds') if isinstance(port.get('taggedNetworkIds'),list) else [])
            if any(not empty(key) for key in networks) and row.get('networkId') not in networks:
                errors.append('Endpoint network must be carried by its interface.')
    for row in rows['routes']:
        kind,port = lookup_entity(row.get('interfaceId'))
        if kind == 'interfaces' and port.get('deviceId') != row.get('deviceId'):
            errors.append('Route interface must belong to its device.')
    for row in rows['flows']:
        source_kind,source = lookup_entity(row.get('sourceId'))
        device = source.get('id') if source_kind == 'devices' else source.get('deviceId') if source_kind in ('services','serviceInstances') else ''
        if source_kind == 'endpoints':
            _,source_port = lookup_entity(source.get('interfaceId'))
            _,source_instance = lookup_entity(source.get('instanceId'))
            device = source_port.get('deviceId') or source_instance.get('deviceId')
        kind,port = lookup_entity(row.get('sourceInterfaceId'))
        if kind == 'interfaces' and device and port.get('deviceId') != device:
            errors.append('Flow source interface must belong to its source device.')
    for row in rows['decisions']:
        refs(row.get('relatedIds'),entities,'Decision relatedIds')
        options, option_ids = row.get('options'), set()
        if not isinstance(options,list):
            errors.append('Decision options must be an array.')
        else:
            for option in options:
                if not isinstance(option,dict):
                    errors.append('Decision option must be an object.')
                    continue
                claim(option.get('id'),'Decision option ID')
                string(option.get('label'),'Decision option label',True)
                for key in ('pros','cons'):
                    if key in option:
                        string(option[key],'Decision option '+key)
                if isinstance(option.get('id'),str):
                    option_ids.add(option['id'])
        reference(row.get('selectedOptionId'),option_ids,'Decision selectedOptionId')
        if isinstance(row.get('status'),str) and row['status'].lower() == 'decided':
            selected, rationale = row.get('selectedOptionId'), row.get('rationale')
            if not isinstance(selected,str) or selected not in option_ids or not isinstance(rationale,str) or not rationale.strip():
                errors.append('Decision marked Decided requires a valid selection and a nonblank rationale.')
    for row in rows['tasks']:
        reference(row.get('relatedId'),entities,'Task relatedId')
    for row in rows['evidence']:
        reference(row.get('relatedId'),entities,'Evidence relatedId')
        string(row.get('mime'),'Evidence mime',True)
        string(row.get('data'),'Evidence data',True)
        match = re.fullmatch(r'data:(image/(?:png|jpeg|gif|webp|svg\+xml)|application/pdf);base64,([a-z0-9+/]+={0,2})',row['data'],re.I) if isinstance(row.get('data'),str) else None
        if not match or len(match[2])%4 or not isinstance(row.get('mime'),str) or match[1].lower() != row['mime'].lower():
            errors.append('Evidence must contain a MIME-matched embedded base64 image or PDF data URL.')
        elif match:
            try:
                base64.b64decode(match[2],validate=True)
            except ValueError:
                errors.append('Evidence base64 data is invalid.')
    comment_ids = entities | {'project'} | ({meta['id']} if isinstance(meta.get('id'),str) else set())
    for row in rows['comments']:
        reference(row.get('entityId'),comment_ids,'Comment entityId',True)
        string(row.get('author'),'Comment author')
        string(row.get('text'),'Comment text',True)
        if not isinstance(row.get('resolved'),bool):
            errors.append('Comment resolved must be boolean.')
    for row in rows['diagrams']:
        refs(row.get('nodeIds'),nodes,'Diagram nodeIds')
        if 'layout' in row:
            if not isinstance(row['layout'],dict):
                errors.append('Diagram layout must be an object.')
            else:
                selected = set(value for value in row.get('nodeIds',[]) if isinstance(value,str)) if isinstance(row.get('nodeIds'),list) else set()
                for key,position in row['layout'].items():
                    if key not in selected:
                        errors.append('Diagram layout references a node outside nodeIds.')
                    if not isinstance(position,dict) or any(isinstance(position.get(axis),bool) or not isinstance(position.get(axis),(int,float)) or not 0 <= position[axis] <= 100000 for axis in ('x','y')):
                        errors.append('Diagram layout positions need finite numeric x/y from 0 to 100000.')
    for collection,field in (('devices','hostedBy'),('services','startup'),('groups','containment'),('dnsRecords','targetId'),('directoryObjects','parentId'),('interfaces','aggregateId')):
        outgoing = {row['id']:[] for row in rows[collection] if isinstance(row.get('id'),str)}
        incoming = dict.fromkeys(outgoing,0)
        for row in rows[collection]:
            if not isinstance(row.get('id'),str):
                continue
            targets = row.get(field,[]) if field == 'dependsOn' else [row.get(field)]
            if field == 'startup':
                targets = [edge.get('toServiceId') for edge in rows['serviceDependencies'] if edge.get('kind') == 'Startup' and edge.get('fromServiceId') == row['id']]
            if field == 'containment':
                targets = row.get('memberIds',[]) if isinstance(row.get('memberIds'),list) else []
                parent = row.get('parentId')
                if isinstance(parent,str) and parent in incoming:
                    outgoing[parent].append(row['id'])
                    incoming[row['id']] += 1
            for target in targets if isinstance(targets,list) else []:
                if isinstance(target,str) and target in incoming:
                    outgoing[row['id']].append(target)
                    incoming[target] += 1
        queue = [key for key,count in incoming.items() if count == 0]
        cursor = 0
        while cursor < len(queue):
            for target in outgoing[queue[cursor]]:
                incoming[target] -= 1
                if incoming[target] == 0:
                    queue.append(target)
            cursor += 1
        if cursor < len(incoming):
            errors.append(collection+' relationships contain a cycle.')
    return errors


def js_number(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('Fingerprint requires finite JSON numbers.')
    if number == 0:
        return '0'
    text = repr(number).lower()
    if 1e-6 <= abs(number) < 1e21:
        text = format(Decimal(text),'f')
        return text.rstrip('0').rstrip('.') if '.' in text else text
    mantissa, exponent = text.split('e')
    return mantissa.removesuffix('.0')+'e'+('+' if int(exponent)>=0 else '-')+str(abs(int(exponent)))


def quote(value):
    result = json.dumps(value,ensure_ascii=False,separators=(',',':'))
    return ''.join('\\u%04x'%ord(c) if 0xD800 <= ord(c) <= 0xDFFF else c for c in result)


def fingerprint(model):
    chunks, stack = [], [('value',model)]
    while stack:
        kind,value = stack.pop()
        if kind == 'text':
            chunks.append(value)
        elif isinstance(value,dict):
            keys = sorted(value,key=lambda key:key.encode('utf-16-be','surrogatepass'))
            chunks.append('{'); stack.append(('text','}'))
            for index in range(len(keys)-1,-1,-1):
                key = keys[index]
                stack.extend([('value',value[key]),('text',quote(key)+':')])
                if index:
                    stack.append(('text',','))
        elif isinstance(value,list):
            chunks.append('['); stack.append(('text',']'))
            for index in range(len(value)-1,-1,-1):
                stack.append(('value',value[index]))
                if index:
                    stack.append(('text',','))
        elif value is None:
            chunks.append('null')
        elif isinstance(value,bool):
            chunks.append('true' if value else 'false')
        elif isinstance(value,(int,float)):
            chunks.append(js_number(value))
        elif isinstance(value,str):
            chunks.append(quote(value))
        else:
            raise ValueError('Fingerprint requires JSON values.')
    hashed = 0x811c9dc5
    for chunk in chunks:
        encoded = chunk.encode('utf-16-le','surrogatepass')
        for index in range(0,len(encoded),2):
            hashed = ((hashed ^ (encoded[index] | encoded[index+1]<<8))*0x01000193)&0xffffffff
    return 'ds1-'+format(hashed,'08x')


def expand_model(model,assets):
    expanded = normalize_model(model)
    for collection,field,label in (('evidence','data','evidence'),('devices','panelImage','front-panel')):
        for row in expanded.get(collection,[]) if isinstance(expanded,dict) and isinstance(expanded.get(collection),list) else []:
            if not isinstance(row,dict) or not isinstance(row.get(field),str) or not row[field].startswith('@asset:'):
                continue
            key = row[field][7:]
            asset = assets.get(key) if isinstance(assets,dict) else None
            data = asset.get('data') if isinstance(asset,dict) else asset
            if not isinstance(data,str):
                raise ValueError('Missing '+label+' asset: '+key)
            row[field] = data
    return expanded


def envelope(value):
    if isinstance(value,dict) and value.get('format') == 'opsdeck-design-studio':
        if type(value.get('version')) is not int or value.get('version') != 1 or not isinstance(value.get('model'),dict):
            raise ValueError('Invalid Design Studio envelope/version.')
        for key,kind in (('revisions',list),('activity',list),('assets',dict),('scenarios',list),('baselines',dict)):
            if key in value and not isinstance(value[key],kind):
                raise ValueError(key+' has an invalid type.')
        result = copy.deepcopy(value)
        result.setdefault('revisions',[]); result.setdefault('activity',[]); result.setdefault('assets',{})
        result.setdefault('scenarios',[]); result.setdefault('activeScenarioId',''); result.setdefault('baselines',{})
        for key,asset in result['assets'].items():
            if isinstance(asset,dict) and isinstance(asset.get('data'),str):
                result['assets'][key] = asset['data']
        result['model'] = normalize_model(result['model'])
        for revision in result['revisions']:
            if isinstance(revision,dict) and isinstance(revision.get('model'),dict):
                revision['model'] = normalize_model(revision['model'])
        for scenario in result['scenarios']:
            if isinstance(scenario,dict) and isinstance(scenario.get('model'),dict):
                scenario['model'] = normalize_model(scenario['model'])
        return result
    if isinstance(value,dict) and value.get('schemaVersion') == 1:
        return {'format':'opsdeck-design-studio','version':1,'model':normalize_model(value),'revisions':[],'activity':[],'assets':{},'scenarios':[],'activeScenarioId':'','baselines':{},'savedAt':now()}
    raise ValueError('Expected a Design Studio envelope or raw schemaVersion 1 model.')


def checked(document):
    errors = unsafe_keys(document)
    if any(not isinstance(asset,str) for asset in document['assets'].values()):
        errors.append('Assets must map keys to embedded data URL strings.')
    model = expand_model(document['model'],document['assets'])
    errors.extend(validate(model))
    for index,revision in enumerate(document['revisions']):
        if not isinstance(revision,dict) or not isinstance(revision.get('model'),dict):
            errors.append(f'Revision {index} needs a model.')
        else:
            if any(not isinstance(revision.get(key),str) or not revision[key].strip() for key in ('id','name','time')):
                errors.append(f'Revision {index} needs id, name, and time strings.')
            errors.extend(f'Revision {index}: {error}' for error in validate(expand_model(revision['model'],document['assets'])))
            if revision['model'].get('meta',{}).get('id') != model['meta']['id']:
                errors.append(f'Revision {index} must belong to the same project.')
    revision_ids = [revision.get('id') for revision in document['revisions'] if isinstance(revision,dict) and isinstance(revision.get('id'),str)]
    if len(set(revision_ids)) != len(revision_ids):
        errors.append('Revision IDs must be unique.')
    if any(key in RESERVED for key in revision_ids):
        errors.append('Revision IDs cannot use reserved names.')
    scenario_ids = []
    for index,scenario in enumerate(document.get('scenarios',[])):
        if not isinstance(scenario,dict) or not isinstance(scenario.get('model'),dict):
            errors.append(f'Scenario {index} needs a model.')
            continue
        if any(not isinstance(scenario.get(key),str) or not scenario[key].strip() for key in ('id','name')):
            errors.append(f'Scenario {index} needs id and name strings.')
        if isinstance(scenario.get('id'),str):
            scenario_ids.append(scenario['id'])
        for key in ('description','author','createdAt','updatedAt','baseRevisionId'):
            if key in scenario and not isinstance(scenario[key],str):
                errors.append(f'Scenario {index} {key} must be a string.')
        if not empty(scenario.get('baseRevisionId')) and scenario.get('baseRevisionId') not in revision_ids:
            errors.append(f'Scenario {index} references an unknown base revision.')
        expanded = expand_model(scenario['model'],document['assets'])
        errors.extend(f'Scenario {index}: {error}' for error in validate(expanded))
        if isinstance(expanded,dict) and isinstance(expanded.get('meta'),dict) and expanded['meta'].get('id') != model['meta']['id']:
            errors.append(f'Scenario {index} must belong to the same project.')
    if len(set(scenario_ids)) != len(scenario_ids):
        errors.append('Scenario IDs must be unique.')
    if any(key in RESERVED for key in scenario_ids):
        errors.append('Scenario IDs cannot use reserved names.')
    active = document.get('activeScenarioId','')
    if not isinstance(active,str) or active and active not in scenario_ids:
        errors.append('activeScenarioId references an unknown scenario.')
    for role,revision_id in document.get('baselines',{}).items():
        if role not in ('installed','target','accepted','verified') or not isinstance(revision_id,str) or revision_id and revision_id not in revision_ids:
            errors.append('Baselines must reference existing revisions using installed, target, accepted or verified roles.')
    for index,revision in enumerate(document['revisions']):
        if isinstance(revision,dict):
            if 'kind' in revision and not isinstance(revision['kind'],str):
                errors.append(f'Revision {index} kind must be a string.')
            scenario_id = revision.get('scenarioId','')
            if not isinstance(scenario_id,str) or scenario_id and scenario_id not in scenario_ids:
                errors.append(f'Revision {index} references an unknown scenario.')
    if errors:
        raise ValueError('\n'.join(errors))
    return model


def apply_changes(model,proposal):
    errors = validate(model)+unsafe_keys(proposal)
    if errors:
        raise ValueError('\n'.join(errors))
    if not isinstance(proposal,dict) or proposal.get('format') != 'opsdeck-design-changes' or type(proposal.get('version')) is not int or proposal.get('version') != 1 or not isinstance(proposal.get('summary'),str) or not isinstance(proposal.get('changes'),list):
        raise ValueError('Expected an opsdeck-design-changes version 1 proposal with summary and changes.')
    if proposal.get('baseProjectId') != model['meta']['id']:
        raise ValueError('Proposal project ID does not match this project.')
    if proposal.get('baseFingerprint') != fingerprint(model):
        raise ValueError('Proposal is stale: base fingerprint does not match the current project.')
    result = normalize_model(model)
    for change in proposal['changes']:
        if not isinstance(change,dict):
            raise ValueError('Each change must be an object.')
        if change.get('op') == 'meta':
            values = change.get('values')
            if not isinstance(values,dict) or 'id' in values:
                raise ValueError('Metadata changes require values and cannot change meta.id.')
            result['meta'].update(copy.deepcopy(values))
            continue
        collection = change.get('collection')
        if not isinstance(collection,str) or collection not in COLLECTIONS:
            raise ValueError('Unknown change collection.')
        rows = result[collection]
        if change.get('op') == 'upsert':
            row = change.get('record')
            if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'].strip():
                raise ValueError('Upsert requires a complete record with an ID.')
            missing = [key for key in REQUIRED[collection].split() if key not in row]
            if missing:
                raise ValueError('Upsert requires a complete '+collection+' record; missing '+', '.join(missing)+'.')
            at = next((i for i,old in enumerate(rows) if old['id']==row['id']),None)
            if at is None:
                rows.append(copy.deepcopy(row))
            else:
                rows[at] = copy.deepcopy(row)
        elif change.get('op') == 'delete':
            key = change.get('id')
            at = next((i for i,old in enumerate(rows) if old['id']==key),None) if isinstance(key,str) else None
            if at is None:
                raise ValueError('Delete references an unknown ID.')
            rows.pop(at)
        else:
            raise ValueError('Unknown change operation.')
    errors = validate(result)
    if errors:
        raise ValueError('Proposed project is invalid:\n'+'\n'.join(errors))
    return result


def write_atomic(path,text):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def blank():
    return {'schemaVersion':1,'meta':{'id':'project-'+str(uuid.uuid4()),'name':'New design','description':'','phase':'Concept','author':'','rackUnits':42,'rackName':'SAMPLE-INFRA-01','classification':'','classificationColor':'#29624b'},**{key:[] for key in COLLECTIONS}}


def analysis_module():
    """Load the sibling analyzer without depending on sys.path or the caller cwd."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('_design_studio_analysis',ROOT/'tools'/'design_analysis.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_workspace(document):
    """Introduce workspace metadata when explicitly using workspace commands."""
    timestamp = now()
    if not document['scenarios']:
        document['scenarios'] = [dict(id='main',name='Main design',description='Primary working design',baseRevisionId='',model=copy.deepcopy(document['model']),createdAt=timestamp,updatedAt=timestamp,author=document['model']['meta'].get('author') or 'CLI')]
    if not document['activeScenarioId']:
        document['activeScenarioId'] = document['scenarios'][0]['id']
    for kind in ('installed','target','accepted','verified'):
        document['baselines'].setdefault(kind,'')
    checked(document)


def save_active_scenario(document):
    for scenario in document['scenarios']:
        if scenario['id'] == document['activeScenarioId']:
            scenario['model'] = copy.deepcopy(document['model'])
            scenario['updatedAt'] = now()
            return
    raise ValueError('Active scenario was not found.')


def workspace_id(document,prefix):
    occupied = {row['id'] for key in ('revisions','scenarios') for row in document[key]}
    candidate = prefix+'-'+str(uuid.uuid4())
    while candidate in occupied:
        candidate = prefix+'-'+str(uuid.uuid4())
    return candidate


def capture_revision(document,name,author='CLI',kind=''):
    revision = dict(id=workspace_id(document,'revision'),name=name,author=author,time=now(),scenarioId=document['activeScenarioId'],model=copy.deepcopy(document['model']))
    if kind:
        revision['kind'] = kind
    document['revisions'].insert(0,revision)
    return revision


def save_workspace(document,output,message):
    document['savedAt'] = now()
    document['activity'].insert(0,dict(id='activity-'+str(uuid.uuid4()),time=document['savedAt'],author='CLI',text=message))
    checked(document)
    write_atomic(output,json.dumps(document,indent=2,ensure_ascii=True)+'\n')
    return dict(output=str(output),activeScenarioId=document['activeScenarioId'],fingerprint=fingerprint(expand_model(document['model'],document['assets'])))


def resolve_snapshot(document,reference):
    """Resolve an unambiguous scenario, revision, or baseline role reference."""
    prefix,key = reference.split(':',1) if ':' in reference and reference.split(':',1)[0] in ('scenario','revision','baseline') else ('',reference)
    matches = []
    if prefix in ('','scenario'):
        matches.extend(dict(kind='scenario',id=s['id'],name=s['name'],model=document['model'] if s['id'] == document['activeScenarioId'] else s['model']) for s in document['scenarios'] if s['id'] == key)
    if prefix in ('','revision'):
        matches.extend(dict(kind='revision',id=r['id'],name=r['name'],model=r['model']) for r in document['revisions'] if r['id'] == key)
    if prefix in ('','baseline') and key in document['baselines']:
        revision_id = document['baselines'][key]
        matches.extend(dict(kind='baseline',role=key,id=r['id'],name=r['name'],model=r['model']) for r in document['revisions'] if r['id'] == revision_id)
    if not matches:
        raise ValueError('Snapshot reference was not found: '+reference)
    if len(matches) != 1:
        raise ValueError('Snapshot reference is ambiguous: '+reference+'. Use scenario:, revision:, or baseline: to specify its type.')
    result = matches[0]
    result['model'] = expand_model(result['model'],document['assets'])
    result['fingerprint'] = fingerprint(result['model'])
    return result


def model_diff(before,after):
    """Stable-ID record differences compatible with the standalone app's DS.diff."""
    changes = []
    def changed_fields(a,b):
        return [key for key in dict.fromkeys([*a,*b]) if key not in a or key not in b or fingerprint(a[key]) != fingerprint(b[key])]
    changed = changed_fields(before.get('meta',{}),after.get('meta',{}))
    if changed:
        changes.append(dict(collection='meta',id=after['meta'].get('id'),name=after['meta'].get('name'),change='Modified',details=', '.join(changed)))
    def row_name(row):
        return next((row[key] for key in ('name','title','label','entityId','id') if isinstance(row.get(key),str) and row[key].strip()),'Record')
    for collection in COLLECTIONS:
        old,new = ({row['id']:row for row in model.get(collection,[])} for model in (before,after))
        for key,row in new.items():
            if key not in old:
                changes.append(dict(collection=collection,id=key,name=row_name(row),change='Added',details='New record'))
            else:
                fields = changed_fields(old[key],row)
                if fields:
                    changes.append(dict(collection=collection,id=key,name=row_name(row),change='Modified',details=', '.join(fields)))
        for key,row in old.items():
            if key not in new:
                changes.append(dict(collection=collection,id=key,name=row_name(row),change='Removed',details='Record removed'))
    return changes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    init = sub.add_parser('init'); init.add_argument('--output',required=True); init.add_argument('--sample',action='store_true')
    for command in ('validate','summary'):
        command_parser = sub.add_parser(command); command_parser.add_argument('project')
    apply = sub.add_parser('apply'); apply.add_argument('project'); apply.add_argument('proposal'); apply.add_argument('--output',required=True)
    render = sub.add_parser('render'); render.add_argument('project'); render.add_argument('--output',required=True); render.add_argument('--template',default=str(ROOT/'design-studio'/'index.html'))
    for command in ('lint','trace','impact','report'):
        command_parser = sub.add_parser(command); command_parser.add_argument('project')
        if command == 'trace':
            command_parser.add_argument('--source',required=True); command_parser.add_argument('--destination',required=True); command_parser.add_argument('--flow',default='')
        elif command == 'impact':
            command_parser.add_argument('--failed',action='append',required=True)
        elif command == 'report':
            command_parser.add_argument('--kind',choices=('addresses','ports','flows','handoff','build','requirements'),required=True); command_parser.add_argument('--output')
    scenario = sub.add_parser('scenario'); scenario_sub = scenario.add_subparsers(dest='workspace_action',required=True)
    scenario_list = scenario_sub.add_parser('list'); scenario_list.add_argument('project')
    scenario_create = scenario_sub.add_parser('create'); scenario_create.add_argument('project'); scenario_create.add_argument('--name',required=True); scenario_create.add_argument('--id'); scenario_create.add_argument('--from-revision',default=''); scenario_create.add_argument('--output')
    scenario_switch = scenario_sub.add_parser('switch'); scenario_switch.add_argument('project'); scenario_switch.add_argument('--id',required=True); scenario_switch.add_argument('--output')
    baseline = sub.add_parser('baseline'); baseline_sub = baseline.add_subparsers(dest='workspace_action',required=True)
    baseline_capture = baseline_sub.add_parser('capture'); baseline_capture.add_argument('project'); baseline_capture.add_argument('--kind',choices=('installed','target','accepted','verified'),required=True); baseline_capture.add_argument('--name',required=True); baseline_capture.add_argument('--author',default='CLI'); baseline_capture.add_argument('--output')
    baseline_compare = baseline_sub.add_parser('compare'); baseline_compare.add_argument('project'); baseline_compare.add_argument('--left',required=True); baseline_compare.add_argument('--right',required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            model = read_json(ROOT/'design-studio'/'sample-model.json') if args.sample else blank()
            model['meta']['id'] = 'project-'+str(uuid.uuid4())
            document = envelope(model); checked(document)
            write_atomic(args.output,json.dumps(document,indent=2,ensure_ascii=True)+'\n')
            print('Created '+str(args.output)); return 0
        document = envelope(read_json(args.project)); model = checked(document)
        if args.command in ('lint','trace','impact','report'):
            analyzer = analysis_module()
            by_id = analyzer.index(model)
            if args.command == 'lint':
                result = analyzer.lint(model)
            elif args.command == 'trace':
                for identifier in (args.source,args.destination):
                    if identifier not in by_id:
                        raise ValueError('Trace references an unknown design record: '+identifier)
                if args.flow:
                    flow = next((f for f in model['flows'] if f['id'] == args.flow),None)
                    if flow is None:
                        raise ValueError('Trace references an unknown communication flow: '+args.flow)
                    if flow['sourceId'] != args.source or flow['destinationId'] != args.destination:
                        raise ValueError('Trace source and destination must match the selected flow.')
                result = analyzer.trace(model,dict(sourceId=args.source,destinationId=args.destination,flowId=args.flow))
            elif args.command == 'impact':
                for identifier in args.failed:
                    if identifier not in by_id:
                        raise ValueError('Impact references an unknown design record: '+identifier)
                result = analyzer.impact(model,dict(failedIds=list(dict.fromkeys(args.failed))))
            else:
                report_text = analyzer.report(model,dict(kind=args.kind))
                if args.output:
                    if Path(args.output).resolve() == Path(args.project).resolve():
                        raise ValueError('Report output must differ from the source project.')
                    write_atomic(args.output,report_text)
                    print(json.dumps(dict(output=args.output,kind=args.kind,modelOnly=True),indent=2))
                else:
                    print(report_text,end='' if report_text.endswith('\n') else '\n')
                return 0
            print(json.dumps(result,indent=2,ensure_ascii=True)); return 0
        if args.command in ('scenario','baseline'):
            ensure_workspace(document)
            if args.command == 'scenario' and args.workspace_action == 'list':
                result = dict(activeScenarioId=document['activeScenarioId'],baselines=document['baselines'],scenarios=[{**{key:value for key,value in row.items() if key != 'model'},'fingerprint':fingerprint(expand_model(document['model'] if row['id'] == document['activeScenarioId'] else row['model'],document['assets']))} for row in document['scenarios']])
                print(json.dumps(result,indent=2,ensure_ascii=True)); return 0
            if args.command == 'baseline' and args.workspace_action == 'compare':
                left,right = resolve_snapshot(document,args.left),resolve_snapshot(document,args.right)
                differences = model_diff(left['model'],right['model'])
                print(json.dumps(dict(left={key:value for key,value in left.items() if key != 'model'},right={key:value for key,value in right.items() if key != 'model'},changes=differences),indent=2,ensure_ascii=True)); return 0
            output = args.output or args.project
            if args.command == 'scenario' and args.workspace_action == 'create':
                name = args.name.strip()
                if not name:
                    raise ValueError('Scenario name must be nonempty.')
                identifier = args.id.strip() if args.id is not None else workspace_id(document,'scenario')
                if not identifier or identifier in RESERVED:
                    raise ValueError('Scenario ID must be nonempty and cannot use a reserved name.')
                if any(row['id'] == identifier for row in document['scenarios']):
                    raise ValueError('Scenario ID already exists: '+identifier)
                source = document['model']
                if args.from_revision:
                    revision = next((r for r in document['revisions'] if r['id'] == args.from_revision),None)
                    if revision is None:
                        raise ValueError('Starting revision was not found: '+args.from_revision)
                    source = revision['model']
                save_active_scenario(document)
                safety = capture_revision(document,'Before creating scenario '+name)
                timestamp = now()
                document['scenarios'].append(dict(id=identifier,name=name,description='',baseRevisionId=args.from_revision or safety['id'],model=copy.deepcopy(source),createdAt=timestamp,updatedAt=timestamp,author=model['meta'].get('author') or 'CLI'))
                result = save_workspace(document,output,'Created scenario '+name)
                result.update(scenarioId=identifier,safetyRevisionId=safety['id'])
            elif args.command == 'scenario':
                selected = next((s for s in document['scenarios'] if s['id'] == args.id),None)
                if selected is None:
                    raise ValueError('Scenario was not found: '+args.id)
                save_active_scenario(document)
                safety = None
                if args.id != document['activeScenarioId']:
                    safety = capture_revision(document,'Before switching scenario to '+selected['name'])
                    document['model'] = copy.deepcopy(selected['model'])
                    document['activeScenarioId'] = selected['id']
                result = save_workspace(document,output,'Opened scenario '+selected['name'])
                result['safetyRevisionId'] = safety['id'] if safety else ''
            else:
                name,author = args.name.strip(),args.author.strip() or 'CLI'
                if not name:
                    raise ValueError('Baseline name must be nonempty.')
                save_active_scenario(document)
                revision = capture_revision(document,name,author,args.kind)
                document['baselines'][args.kind] = revision['id']
                result = save_workspace(document,output,'Captured '+args.kind+' baseline '+name)
                result.update(revisionId=revision['id'],kind=args.kind)
            print(json.dumps(result,indent=2,ensure_ascii=True)); return 0
        if args.command == 'validate':
            print(json.dumps({'valid':True,'projectId':model['meta']['id'],'fingerprint':fingerprint(model),'counts':{key:len(model[key]) for key in COLLECTIONS}},indent=2)); return 0
        if args.command == 'summary':
            context = copy.deepcopy(model)
            for row in context['evidence']:
                row['data'] = '[embedded evidence omitted from context]'
            for row in context['devices']:
                if row.get('panelImage'):
                    row['panelImage'] = '[embedded front panel omitted from context]'
            template = {'format':'opsdeck-design-changes','version':1,'baseProjectId':model['meta']['id'],'baseFingerprint':fingerprint(model),'summary':'Describe the proposed design change','changes':[]}
            if document.get('activeScenarioId'):
                template['baseScenarioId'] = document['activeScenarioId']
            instructions = [
                'Return opsdeck-design-changes version 1 using changeSetTemplate. Copy project ID and fingerprint exactly.',
                'Use complete records for upsert, preserving stable IDs. Use delete with collection/id or meta with values; meta.id cannot change.',
                'Required record keys are listed in recordSchemas. dependsOn, memberIds, accessIds, relatedIds and nodeIds are arrays; options is an array of {id,label,pros,cons}.',
                'Leave unknown text blank and rackU null if unplaced; height is positive integer. Decided requires selectedOptionId and nonblank rationale.',
                'Evidence and front-panel image bytes are omitted from this context. Do not replace evidence data or panelImage with omission placeholders; obtain original full project data if changing an affected record.',
                'Relationships kind is authenticates, resolves, uses-license, hosts, forwards, depends or access. DNS targets may also reference endpoints; DNS target cycles are invalid. Legacy dependsOn is Runtime; only explicit Startup serviceDependencies reject cycles.',
                'Never invent addressing, evidence, vendor defaults or approvals. Identity, applications and license implementation choices remain explicit.',
                'Services are capabilities; serviceInstances are deployments; endpoints are listening interfaces. Directory containment, group membership and accessMappings are separate facts. Flows and policies are planned requirements, not proof of reachability.',
                'Architecture field types, references, enums and required keys appear in architectureSchemas. Blank protocol/ports/address facts remain unresolved. Verification tests need evidence recorded by the team; an LLM must not claim unperformed tests passed.'
            ]
            schemas = dict(REQUIRED)
            schemas['services'] += ' [kind endpoint protocol port licenseManager redundancy]'
            print(json.dumps({'format':'opsdeck-design-context','version':1,'baseProjectId':model['meta']['id'],'baseFingerprint':fingerprint(model),'baseScenarioId':document.get('activeScenarioId',''),'baselines':document.get('baselines',{}),'model':context,'recordSchemas':schemas,'architectureSchemas':ARCH_SCHEMA,'instructions':instructions,'changeSetTemplate':template},indent=2,ensure_ascii=True)); return 0
        if args.command == 'apply':
            proposal = read_json(args.proposal)
            requires_scope = len(document.get('scenarios',[])) > 1 or document.get('activeScenarioId','') not in ('','main')
            if isinstance(proposal,dict) and requires_scope and 'baseScenarioId' not in proposal:
                raise ValueError('Proposal requires baseScenarioId for this workspace. Export fresh context from the intended scenario.')
            if isinstance(proposal,dict) and 'baseScenarioId' in proposal and proposal['baseScenarioId'] != document.get('activeScenarioId',''):
                raise ValueError('Proposal scenario does not match the active scenario.')
            changed = apply_changes(model,proposal)
            timestamp = now()
            revision = {'id':'revision-'+str(uuid.uuid4()),'name':proposal['summary'] or 'Applied change proposal','author':'CLI','time':timestamp,'model':copy.deepcopy(changed)}
            safety = {'id':'revision-'+str(uuid.uuid4()),'name':'Before proposal — '+(proposal['summary'] or 'design change'),'author':'CLI','time':timestamp,'model':copy.deepcopy(model)}
            if document.get('activeScenarioId'):
                revision['scenarioId'] = safety['scenarioId'] = document['activeScenarioId']
                for scenario in document.get('scenarios',[]):
                    if scenario.get('id') == document['activeScenarioId']:
                        scenario['model'],scenario['updatedAt'] = copy.deepcopy(changed),timestamp
            document['revisions'][0:0] = [revision,safety]
            document['activity'].insert(0,{'id':'activity-'+str(uuid.uuid4()),'time':timestamp,'author':'CLI','text':'Applied proposal: '+proposal['summary']})
            document['model'], document['savedAt'] = changed,timestamp
            checked(document)
            write_atomic(args.output,json.dumps(document,indent=2,ensure_ascii=True)+'\n')
            print(json.dumps({'output':args.output,'fingerprint':fingerprint(changed),'revisionId':revision['id']},indent=2)); return 0
        if args.command == 'render':
            template = Path(args.template).read_text(encoding='utf-8')
            document['savedAt'] = now()
            encoded = json.dumps(document,ensure_ascii=True,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
            pattern = r'(<script\b[^>]*\bid=["\']project-data["\'][^>]*>).*?(</script\s*>)'
            rendered,count = re.subn(pattern,lambda match:match[1]+encoded+match[2],template,count=1,flags=re.I|re.S)
            if count != 1:
                raise ValueError('Template needs one script#project-data JSON element.')
            write_atomic(args.output,rendered)
            print('Rendered '+str(args.output)); return 0
    except (ValueError,TypeError,KeyError,OSError,OverflowError,RecursionError) as error:
        print('Error: '+str(error),file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
