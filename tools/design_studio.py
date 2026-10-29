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

OPTIONAL_COLLECTIONS = ('identity','groups','dnsZones','dnsRecords','relationships')
COLLECTIONS = ('devices','networks','services','interfaces','links','decisions','tasks','evidence','comments','diagrams') + OPTIONAL_COLLECTIONS
NAMED = {'devices','networks','services','interfaces','evidence','diagrams','identity','groups','dnsZones','dnsRecords'}
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
ROOT = Path(__file__).resolve().parents[1]


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
    nodes = set().union(*(typed[key] for key in ('devices','networks','services','identity','groups','dnsZones','dnsRecords')))
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
        height = integer(row.get('height'))
        if height is None or height < 1 or rack_units is None or height > rack_units:
            errors.append(path+' height must be a positive integer within the rack height.')
        if not empty(row.get('rackU')):
            unit = integer(row['rackU'])
            if unit is None or unit < 1 or height is None or height < 1 or rack_units is None or not 1 <= rack_units <= 200 or unit+height-1 > rack_units:
                errors.append(path+' does not fit inside the rack.')
            else:
                for u in range(unit,unit+height):
                    if u in occupied:
                        errors.append(f'Rack overlap at U{u}: {occupied[u]} and {row.get("id")}')
                    occupied[u] = row.get('id')
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
    group_members = typed['groups'] | typed['devices'] | typed['services']
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
        reference(row.get('targetId'),typed['services'] | typed['devices'] | typed['dnsRecords'],'DNS record targetId')
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
    for collection,field in (('devices','hostedBy'),('services','dependsOn'),('groups','containment'),('dnsRecords','targetId')):
        outgoing = {row['id']:[] for row in rows[collection] if isinstance(row.get('id'),str)}
        incoming = dict.fromkeys(outgoing,0)
        for row in rows[collection]:
            if not isinstance(row.get('id'),str):
                continue
            targets = row.get(field,[]) if field == 'dependsOn' else [row.get(field)]
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
    for row in expanded.get('evidence',[]) if isinstance(expanded,dict) and isinstance(expanded.get('evidence'),list) else []:
        if not isinstance(row,dict) or not isinstance(row.get('data'),str) or not row['data'].startswith('@asset:'):
            continue
        key = row['data'][7:]
        asset = assets.get(key) if isinstance(assets,dict) else None
        data = asset.get('data') if isinstance(asset,dict) else asset
        if not isinstance(data,str):
            raise ValueError('Missing evidence asset: '+key)
        row['data'] = data
    return expanded


def envelope(value):
    if isinstance(value,dict) and value.get('format') == 'opsdeck-design-studio':
        if type(value.get('version')) is not int or value.get('version') != 1 or not isinstance(value.get('model'),dict):
            raise ValueError('Invalid Design Studio envelope/version.')
        for key,kind in (('revisions',list),('activity',list),('assets',dict)):
            if key in value and not isinstance(value[key],kind):
                raise ValueError(key+' has an invalid type.')
        result = copy.deepcopy(value)
        result.setdefault('revisions',[]); result.setdefault('activity',[]); result.setdefault('assets',{})
        for key,asset in result['assets'].items():
            if isinstance(asset,dict) and isinstance(asset.get('data'),str):
                result['assets'][key] = asset['data']
        result['model'] = normalize_model(result['model'])
        for revision in result['revisions']:
            if isinstance(revision,dict) and isinstance(revision.get('model'),dict):
                revision['model'] = normalize_model(revision['model'])
        return result
    if isinstance(value,dict) and value.get('schemaVersion') == 1:
        return {'format':'opsdeck-design-studio','version':1,'model':normalize_model(value),'revisions':[],'activity':[],'assets':{},'savedAt':now()}
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    init = sub.add_parser('init'); init.add_argument('--output',required=True); init.add_argument('--sample',action='store_true')
    for command in ('validate','summary'):
        command_parser = sub.add_parser(command); command_parser.add_argument('project')
    apply = sub.add_parser('apply'); apply.add_argument('project'); apply.add_argument('proposal'); apply.add_argument('--output',required=True)
    render = sub.add_parser('render'); render.add_argument('project'); render.add_argument('--output',required=True); render.add_argument('--template',default=str(ROOT/'design-studio'/'index.html'))
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            model = read_json(ROOT/'design-studio'/'sample-model.json') if args.sample else blank()
            model['meta']['id'] = 'project-'+str(uuid.uuid4())
            document = envelope(model); checked(document)
            write_atomic(args.output,json.dumps(document,indent=2,ensure_ascii=True)+'\n')
            print('Created '+str(args.output)); return 0
        document = envelope(read_json(args.project)); model = checked(document)
        if args.command == 'validate':
            print(json.dumps({'valid':True,'projectId':model['meta']['id'],'fingerprint':fingerprint(model),'counts':{key:len(model[key]) for key in COLLECTIONS}},indent=2)); return 0
        if args.command == 'summary':
            context = copy.deepcopy(model)
            for row in context['evidence']:
                row['data'] = '[embedded evidence omitted from context]'
            template = {'format':'opsdeck-design-changes','version':1,'baseProjectId':model['meta']['id'],'baseFingerprint':fingerprint(model),'summary':'Describe the proposed design change','changes':[]}
            instructions = [
                'Return opsdeck-design-changes version 1 using changeSetTemplate. Copy project ID and fingerprint exactly.',
                'Use complete records for upsert, preserving stable IDs. Use delete with collection/id or meta with values; meta.id cannot change.',
                'Required record keys are listed in recordSchemas. dependsOn, memberIds, accessIds, relatedIds and nodeIds are arrays; options is an array of {id,label,pros,cons}.',
                'Leave unknown text blank and rackU null if unplaced; height is positive integer. Decided requires selectedOptionId and nonblank rationale.',
                'Evidence bytes are omitted from this context. Do not replace evidence data with omission placeholders; obtain original full project data if changing evidence.',
                'Relationships kind is authenticates, resolves, uses-license, hosts, forwards, depends or access. DNS targets reference devices/services/DNS records; cycles are invalid.',
                'Never invent addressing, evidence, vendor defaults or approvals. Identity, applications and license implementation choices remain explicit.'
            ]
            schemas = dict(REQUIRED)
            schemas['services'] += ' [kind endpoint protocol port licenseManager redundancy]'
            print(json.dumps({'format':'opsdeck-design-context','version':1,'baseProjectId':model['meta']['id'],'baseFingerprint':fingerprint(model),'model':context,'recordSchemas':schemas,'instructions':instructions,'changeSetTemplate':template},indent=2,ensure_ascii=True)); return 0
        if args.command == 'apply':
            proposal = read_json(args.proposal)
            changed = apply_changes(model,proposal)
            timestamp = now()
            revision = {'id':'revision-'+str(uuid.uuid4()),'name':proposal['summary'] or 'Applied change proposal','author':'CLI','time':timestamp,'model':copy.deepcopy(changed)}
            safety = {'id':'revision-'+str(uuid.uuid4()),'name':'Before proposal — '+(proposal['summary'] or 'design change'),'author':'CLI','time':timestamp,'model':copy.deepcopy(model)}
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
