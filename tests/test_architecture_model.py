"""Architecture contract, migration, guarded changes, and cross-runtime parity."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('architecture_ds',ROOT/'tools/design_studio.py')
ds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ds)


def sample():
    return ds.read_json(ROOT/'design-studio/sample-model.json')


def complete(collection,record_id,**values):
    descriptor = ds.ARCH_SCHEMA[collection]
    row = {}
    for key in descriptor['required'].split():
        field = descriptor['fields'].get(key,{})
        row[key] = [] if field.get('type') in ('references','strings') else field['options'][0] if field.get('type') == 'enum' else 1 if field.get('type') == 'integer' and not field.get('blank') else ''
    row.update(id=record_id,name='SAMPLE-'+record_id,status='Proposed',**values)
    return row


def proposal(model,changes):
    return dict(format='opsdeck-design-changes',version=1,baseProjectId=model['meta']['id'],baseFingerprint=ds.fingerprint(model),summary='SAMPLE-Architecture design change',changes=changes)


class ArchitectureModelTests(unittest.TestCase):
    def test_legacy_collections_migrate_without_changing_semantics(self):
        legacy = ds.blank()
        for key in ds.OPTIONAL_COLLECTIONS:
            del legacy[key]
        original = copy.deepcopy(legacy)
        self.assertEqual(ds.validate(legacy),[])
        migrated = ds.normalize_model(legacy)
        self.assertEqual(legacy,original)
        self.assertEqual(migrated['meta'],legacy['meta'])
        self.assertTrue(all(migrated[key] == [] for key in ds.OPTIONAL_COLLECTIONS))
        self.assertEqual(ds.normalize_model(migrated),migrated)
        malformed = copy.deepcopy(legacy); malformed['flows'] = None
        self.assertIsNone(ds.normalize_model(malformed)['flows'])
        self.assertTrue(ds.validate(malformed))

    def test_rack_placement_is_scoped_and_checks_selected_rack_height(self):
        model = sample()
        device = model['devices'][0]
        model['devices'].append({**device,'id':'sample-second-rack-device','rackId':'sample-rack-b'})
        self.assertEqual(ds.validate(model),[])
        model['devices'][-1]['rackId'] = device['rackId']
        self.assertTrue(any('overlap' in e for e in ds.validate(model)))
        model['devices'][-1]['rackId'] = 'sample-rack-b'
        model['racks'][1]['units'] = 10
        self.assertTrue(any('fit inside' in e for e in ds.validate(model)))
        model['racks'][1]['units'] = 42
        model['devices'][-1]['rackId'] = []
        self.assertTrue(ds.validate(model))

    def test_interface_bond_ownership_modes_and_cycles(self):
        model = sample()
        port = model['interfaces'][0]
        bond = {**port,'id':'sample-bond','name':'SAMPLE-Bond','mode':'Bond','aggregateId':''}
        model['interfaces'].append(bond)
        port['aggregateId'] = bond['id']
        self.assertEqual(ds.validate(model),[])
        bond['deviceId'] = 'sample-device-linux'
        self.assertTrue(any('same device' in e for e in ds.validate(model)))
        bond['deviceId'] = port['deviceId']; bond['mode'] = 'Access'
        self.assertTrue(any('Bond mode' in e for e in ds.validate(model)))
        bond['mode'] = port['mode'] = 'Bond'; bond['aggregateId'] = port['id']
        self.assertTrue(any('cycle' in e for e in ds.validate(model)))

    def test_runtime_cycles_are_valid_startup_cycles_are_errors(self):
        model = sample()
        a,b = model['services'][:2]
        a['dependsOn'] = [b['id']]; b['dependsOn'] = [a['id']]
        self.assertEqual(ds.validate(model),[])
        model['serviceDependencies'] = [complete('serviceDependencies','sample-start-a',fromServiceId=a['id'],toServiceId=b['id'],kind='Startup'),complete('serviceDependencies','sample-start-b',fromServiceId=b['id'],toServiceId=a['id'],kind='Runtime')]
        self.assertEqual(ds.validate(model),[])
        model['serviceDependencies'][1]['kind'] = 'Startup'
        self.assertTrue(any('cycle' in e for e in ds.validate(model)))

    def test_directory_containment_membership_and_access_are_distinct(self):
        model = sample()
        self.assertEqual(ds.validate(model),[])
        group = model['groups'][0]
        self.assertEqual(group['containerId'],model['directoryObjects'][0]['id'])
        self.assertIn(model['groups'][1]['id'],group['memberIds'])
        self.assertEqual(model['accessMappings'][0]['principalId'],group['id'])
        model['directoryObjects'][0]['parentId'] = model['directoryObjects'][0]['id']
        self.assertTrue(any('cycle' in e for e in ds.validate(model)))
        model['directoryObjects'][0]['parentId'] = ''
        model['identity'].append({**model['identity'][0],'id':'sample-other-identity'})
        model['principals'][0]['identityId'] = 'sample-other-identity'
        self.assertTrue(any('Principal container' in e for e in ds.validate(model)))
        self.assertTrue(any('same identity' in e for e in ds.validate(model)))

    def test_endpoint_consistency_dns_and_flow_references(self):
        model = sample()
        self.assertEqual(ds.validate(model),[])
        endpoint = model['endpoints'][0]
        self.assertIn(model['dnsRecords'][0]['targetId'],{row['id'] for row in model['endpoints']})
        endpoint['serviceId'] = 'sample-service-license'
        self.assertTrue(any('provide its service' in e for e in ds.validate(model)))
        endpoint['serviceId'] = 'sample-service-dns'
        endpoint['interfaceId'] = 'sample-interface-dns-b'
        self.assertTrue(any('instance device' in e for e in ds.validate(model)))
        endpoint['interfaceId'] = 'sample-interface-dns-a'; endpoint['networkId'] = 'sample-net-engineering'
        self.assertTrue(any('carried by its interface' in e for e in ds.validate(model)))
        endpoint['networkId'] = 'sample-net-infrastructure'
        model['flows'][0]['sourceInterfaceId'] = 'sample-interface-dns-a'
        self.assertTrue(any('source device' in e for e in ds.validate(model)))

    def test_complete_proposals_and_unknown_facts(self):
        model = sample()
        row = complete('observations','sample-observation',entityId='sample-device-linux',field='owner',value='SAMPLE-Lab team',source='SAMPLE-Inventory review')
        changed = ds.apply_changes(model,proposal(model,[dict(op='upsert',collection='observations',record=row)]))
        self.assertEqual(changed['observations'],[row])
        self.assertEqual(changed['flows'][0]['ports'],'')
        self.assertEqual(changed['verificationTests'][0]['result'],'Not run')
        del row['observedBy']
        with self.assertRaisesRegex(ValueError,'complete'):
            ds.apply_changes(model,proposal(model,[dict(op='upsert',collection='observations',record=row)]))
        for collection in ds.ARCH_COLLECTIONS:
            if not model[collection]:
                continue
            bad = copy.deepcopy(model)
            del bad[collection][0]['status']
            self.assertTrue(ds.validate(bad),collection)

    def test_malformed_fields_do_not_silently_migrate(self):
        cases = [('devices','failureDomainIds','bad'),('devices','panelImage','https://example.invalid/image.png'),('networks','vrfId',[]),('interfaces','mode','Auto'),('interfaces','taggedNetworkIds',['unknown']),('interfaces','mtu',True),('routes','metric',-1),('routes','metric',10**1000),('resolverAssignments','searchDomains',[{}]),('endpoints','port',443),('policies','action','Permit'),('flows','policyIds',[{}]),('verificationTests','result','Verified'),('requirements','decisionIds',['unknown'])]
        for collection,key,value in cases:
            with self.subTest(collection=collection,key=key):
                model = sample(); model[collection][0][key] = value
                self.assertTrue(ds.validate(model))

    def test_scenarios_baselines_assets_and_scoped_cli_apply(self):
        model = sample()
        model['evidence'] = [dict(id='sample-evidence',name='SAMPLE-Proof',mime='image/png',data='@asset:pic',caption='',relatedId='sample-device-linux',createdAt=ds.now())]
        document = ds.envelope(model)
        document['assets']['pic'] = 'data:image/png;base64,AAAA'
        document['revisions'] = [dict(id='sample-baseline',name='SAMPLE-Accepted design',time=ds.now(),model=copy.deepcopy(model),kind='accepted')]
        document['scenarios'] = [dict(id='sample-option-a',name='SAMPLE-Option A',description='',baseRevisionId='sample-baseline',model=copy.deepcopy(model),createdAt=ds.now(),updatedAt=ds.now(),author='SAMPLE-Team',customMetadata='preserved')]
        document['activeScenarioId'] = 'sample-option-a'; document['baselines'] = {'accepted':'sample-baseline'}
        expanded = ds.checked(document)
        change = proposal(expanded,[dict(op='meta',values={'phase':'Design'})]); change['baseScenarioId'] = 'wrong'
        with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            folder = Path(folder); source,prop,out = [folder/x for x in ('source.json','change.json','out.json')]
            source.write_text(json.dumps(document)); prop.write_text(json.dumps(change))
            self.assertEqual(ds.main(['apply',str(source),str(prop),'--output',str(out)]),1)
            self.assertFalse(out.exists())
            change['baseScenarioId'] = 'sample-option-a'; prop.write_text(json.dumps(change))
            self.assertEqual(ds.main(['apply',str(source),str(prop),'--output',str(out)]),0)
            result = ds.envelope(ds.read_json(out)); ds.checked(result)
            self.assertEqual(result['scenarios'][0]['model']['meta']['phase'],'Design')
            self.assertEqual(result['scenarios'][0]['customMetadata'],'preserved')
            self.assertEqual(result['baselines'],document['baselines'])
            self.assertEqual(result['revisions'][0]['scenarioId'],'sample-option-a')
            self.assertEqual(result['scenarios'][0]['model']['evidence'][0]['data'],'data:image/png;base64,AAAA')
        for key,value in [('activeScenarioId','missing'),('baselines',{'accepted':'missing'})]:
            bad = copy.deepcopy(document); bad[key] = value
            with self.assertRaises(ValueError):ds.checked(bad)

    @unittest.skipUnless(shutil.which('node'),'Node optional for Python CLI users.')
    def test_javascript_python_contract_fingerprints_and_validation_parity(self):
        model = sample(); cases = [model,ds.blank()]
        for collection,key,value in [('devices','rackId',[]),('endpoints','serviceId','unknown'),('interfaces','aggregateId','sample-interface-dns-b'),('flows','ports',[]),('serviceDependencies','kind','Startup'),('resolverAssignments','resolverEndpointIds',[{}]),('verificationTests','evidenceIds','bad')]:
            bad = copy.deepcopy(model); bad[collection][0][key] = value; cases.append(bad)
        runtime = copy.deepcopy(model);runtime['services'][0]['dependsOn']=['sample-service-dns'];runtime['services'][1]['dependsOn']=['sample-service-identity'];cases.append(runtime)
        cycle = copy.deepcopy(model);cycle['serviceDependencies']=[complete('serviceDependencies','sample-start-a',fromServiceId='sample-service-dns',toServiceId='sample-service-license',kind='Startup'),complete('serviceDependencies','sample-start-b',fromServiceId='sample-service-license',toServiceId='sample-service-dns',kind='Startup')];cases.append(cycle)
        legacy = copy.deepcopy(ds.blank())
        for key in ds.OPTIONAL_COLLECTIONS:del legacy[key]
        cases.extend([legacy,ds.normalize_model(legacy)])
        code = "const ds=require('./src/model.js');const cases=JSON.parse(require('fs').readFileSync(0,'utf8'));process.stdout.write(JSON.stringify({required:ds.requiredFields,schema:ds.schema,results:cases.map(m=>({valid:!ds.validate(m).length,fingerprint:ds.fingerprint(m)}))}));"
        output = subprocess.run(['node','-e',code],cwd=ROOT,input=json.dumps(cases),text=True,capture_output=True,check=True)
        huge = copy.deepcopy(model); huge['routes'][0]['metric'] = 10**1000
        checked_huge = subprocess.run(['node','-e',"const ds=require('./src/model.js');process.stdout.write(String(ds.validate(JSON.parse(require('fs').readFileSync(0,'utf8'))).length>0));"],cwd=ROOT,input=json.dumps(huge),text=True,capture_output=True,check=True)
        self.assertEqual(checked_huge.stdout,'true')
        self.assertTrue(ds.validate(huge))
        actual = json.loads(output.stdout)
        self.assertEqual(actual['required'],ds.REQUIRED)
        self.assertEqual(actual['schema'],ds.ARCH_SCHEMA)
        self.assertEqual(actual['results'],[dict(valid=not ds.validate(case),fingerprint=ds.fingerprint(case)) for case in cases])


if __name__ == '__main__':unittest.main()
