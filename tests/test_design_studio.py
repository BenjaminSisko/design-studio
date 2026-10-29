"""Offline schema migration, logical modeling, and CLI exchange integration."""
import contextlib
import copy
import importlib.util
import io
import json
import shutil
import subprocess
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ds',ROOT/'tools'/'design_studio.py')
ds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ds)

def fixture():
    model = ds.blank()
    model['devices'] = [dict(id='d',name='SAMPLE-Device',type='Server',owner='',status='Proposed',networkId='',rackU=None,height=1,notes='')]
    model['services'] = [dict(id='s',name='SAMPLE-Identity service',platform='',owner='',status='Proposed',deviceId='d',networkId='',notes='',dependsOn=[],kind='Identity',endpoint='',protocol='',port='',licenseManager='',redundancy='')]
    model['identity'] = [dict(id='i',name='SAMPLE-Identity',serviceId='s',implementation='Undecided',domain='',realm='',notes='',status='Proposed')]
    model['groups'] = [dict(id='g',name='SAMPLE-Admins',identityId='i',parentId='',kind='Group',memberIds=['g2','d'],accessIds=['s'],notes='',status='Proposed'),dict(id='g2',name='SAMPLE-Subgroup',identityId='i',parentId='g',kind='Group',memberIds=[],accessIds=[],notes='',status='Proposed')]
    model['dnsZones'] = [dict(id='z',name='SAMPLE-sample.invalid',serviceId='s',kind='Forward',notes='',status='Proposed')]
    model['dnsRecords'] = [dict(id='r',name='SAMPLE-host',zoneId='z',type='A',value='',targetId='d',ttl=0,notes='',status='Proposed')]
    model['relationships'] = [dict(id='rel',from_='d',to='s',kind='authenticates',label='',protocol='',port='',endpoint='',notes='',status='Proposed')]
    model['relationships'][0]['from'] = model['relationships'][0].pop('from_')
    model['diagrams'] = [dict(id='diagram',name='SAMPLE-Logical diagram',nodeIds=['d','s'],notes='',layout={'d':{'x':0,'y':100000}})]
    return model

class DesignStudioTests(unittest.TestCase):
    def test_valid_and_migration(self):
        model = fixture()
        self.assertEqual(ds.validate(model),[])
        legacy = ds.blank()
        for key in ds.OPTIONAL_COLLECTIONS:
            del legacy[key]
        self.assertEqual(ds.validate(legacy),[])
        document = ds.envelope({'format':'opsdeck-design-studio','version':1,'model':legacy,'revisions':[{'id':'rev','name':'Legacy','time':ds.now(),'model':legacy}],'activity':[],'assets':{}})
        ds.checked(document)
        for model in (document['model'],document['revisions'][0]['model']):
            self.assertTrue(all(model[key] == [] for key in ds.OPTIONAL_COLLECTIONS))
        self.assertNotIn('identity',legacy)
        proposal = dict(format='opsdeck-design-changes',version=1,baseProjectId=legacy['meta']['id'],baseFingerprint=ds.fingerprint(legacy),summary='SAMPLE-Legacy update',changes=[dict(op='meta',values={'phase':'Design'})])
        changed = ds.apply_changes(legacy,proposal)
        self.assertTrue(all(key in changed for key in ds.OPTIONAL_COLLECTIONS))
        bad = copy.deepcopy(legacy); bad['identity'] = None
        self.assertTrue(ds.validate(bad))

    def test_invalid_references_cycles_and_layout(self):
        cases = [
            ('identity','serviceId','unknown'),('groups','identityId','unknown'),
            ('groups','parentId','g2'),('groups','memberIds',['g']),('groups','accessIds',['d']),
            ('dnsZones','serviceId','d'),('dnsRecords','zoneId','s'),('dnsRecords','targetId','g'),
            ('dnsRecords','ttl',-1),('dnsRecords','type',''),('relationships','kind','invented'),
            ('relationships','from','unknown'),('services','endpoint',{}),
            ('diagrams','layout',{'missing':{'x':1,'y':2}}),
            ('diagrams','layout',{'d':{'x':True,'y':2}}),
            ('diagrams','layout',{'d':{'x':'1','y':2}}),
            ('diagrams','layout',{'d':{'x':1e100,'y':2}}),
            ('diagrams','layout',{'d':{'x':float('nan'),'y':2}}),
            ('diagrams','layout',{'d':{'x':10**1000,'y':2}}),
        ]
        for collection,key,value in cases:
            model = fixture(); model[collection][0][key] = value
            self.assertTrue(ds.validate(model),(collection,key,value))
        model = fixture(); model['groups'][1]['memberIds'] = ['g']
        self.assertTrue(any('cycle' in error for error in ds.validate(model)))
        model = fixture(); model['identity'].append({**model['identity'][0],'id':'other','name':'SAMPLE-Other'})
        model['groups'][1]['identityId'] = 'other'
        self.assertTrue(any('same identity' in error for error in ds.validate(model)))
        model = fixture()
        model['dnsRecords'].append({**model['dnsRecords'][0],'id':'alias','name':'SAMPLE-Alias','type':'CNAME','targetId':'r'})
        self.assertEqual(ds.validate(model),[])
        model['dnsRecords'][0]['targetId'] = 'alias'
        self.assertTrue(any('cycle' in error for error in ds.validate(model)))

    def test_apply_render_and_rollback(self):
        model = fixture()
        changed = copy.deepcopy(model['relationships'][0]); changed['port'] = '389'
        proposal = dict(format='opsdeck-design-changes',version=1,baseProjectId=model['meta']['id'],baseFingerprint=ds.fingerprint(model),summary='SAMPLE-Capture logical authentication path',changes=[dict(op='upsert',collection='relationships',record=changed)])
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            folder = Path(folder)
            source,changefile,output,html = [folder/name for name in ('source.json','changes.json','result.json','result.html')]
            source.write_text(json.dumps(ds.envelope(model))); changefile.write_text(json.dumps(proposal))
            self.assertEqual(ds.main(['apply',str(source),str(changefile),'--output',str(output)]),0)
            result = ds.envelope(ds.read_json(output)); ds.checked(result)
            self.assertEqual(result['model']['relationships'][0]['port'],'389')
            self.assertEqual(len(result['revisions']),2)
            self.assertEqual(result['revisions'][1]['model'],model)
            self.assertEqual(ds.main(['render',str(output),'--output',str(html)]),0)
            self.assertIn('SAMPLE-Capture logical authentication path',html.read_text())
            proposal['baseFingerprint'] = ds.fingerprint(result['model'])
            proposal['changes'][0]['record']['to'] = 'unknown'
            changefile.write_text(json.dumps(proposal)); previous = output.read_bytes()
            self.assertEqual(ds.main(['apply',str(output),str(changefile),'--output',str(output)]),1)
            self.assertEqual(previous,output.read_bytes())

    def test_evidence_assets_survive_apply_and_safe_render(self):
        model = fixture()
        model['meta']['description'] = '</script><script>alert(1)</script>'
        model['evidence'] = [dict(id='e',name='SAMPLE-Evidence',mime='image/png',data='@asset:pic',caption='SAMPLE-Image',relatedId='s',createdAt=ds.now())]
        document = ds.envelope(model)
        document['assets']['pic'] = 'data:image/png;base64,AAAA'
        expanded = ds.checked(document)
        proposal = dict(format='opsdeck-design-changes',version=1,baseProjectId=model['meta']['id'],baseFingerprint=ds.fingerprint(expanded),summary='SAMPLE-Evidence update',changes=[dict(op='meta',values={'phase':'Design'})])
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            folder = Path(folder)
            source,changefile,output,html = [folder/name for name in ('source.json','changes.json','result.json','result.html')]
            source.write_text(json.dumps(document)); changefile.write_text(json.dumps(proposal))
            self.assertEqual(ds.main(['apply',str(source),str(changefile),'--output',str(output)]),0)
            result = ds.read_json(output)
            self.assertEqual(ds.checked(result)['evidence'][0]['data'],document['assets']['pic'])
            self.assertEqual(result['assets']['pic'],document['assets']['pic'])
            self.assertEqual(ds.main(['render',str(output),'--output',str(html)]),0)
            self.assertNotIn('</script><script>alert(1)</script>',html.read_text())
            self.assertIn('data:image/png;base64,AAAA',html.read_text())
            proposal['baseFingerprint'] = 'ds1-00000000'
            changefile.write_text(json.dumps(proposal)); previous = output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(ds.main(['apply',str(output),str(changefile),'--output',str(output)]),1)
            self.assertEqual(output.read_bytes(),previous)

    def test_saved_sample_and_complete_record_guard(self):
        model = ds.read_json(ROOT/'design-studio'/'sample-model.json')
        self.assertEqual(ds.validate(model),[])
        self.assertTrue(model['identity'] and model['relationships'])
        proposal = dict(format='opsdeck-design-changes',version=1,baseProjectId=model['meta']['id'],baseFingerprint=ds.fingerprint(model),summary='SAMPLE-Incomplete record',changes=[dict(op='upsert',collection='identity',record={'id':'new','name':'SAMPLE-New'})])
        with self.assertRaisesRegex(ValueError,'complete'):
            ds.apply_changes(model,proposal)

    @unittest.skipUnless(shutil.which('node'),'Node is optional; Python CLI needs only the standard library.')
    def test_repository_javascript_fingerprint_and_schema_parity(self):
        model = fixture()
        legacy = ds.blank()
        for key in ds.OPTIONAL_COLLECTIONS:
            del legacy[key]
        cases = [model,ds.read_json(ROOT/'design-studio'/'sample-model.json'),ds.normalize_model(legacy)]
        for collection,key,value in [('groups','memberIds',['g']),('dnsRecords','ttl',-1),('dnsRecords','targetId','g'),('relationships','kind','invented'),('diagrams','layout',{'d':{'x':'1','y':2}}),('identity','implementation','')]:
            bad = fixture(); bad[collection][0][key] = value; cases.append(bad)
        code = "const fs=require('fs'),vm=require('vm');const html=fs.readFileSync(process.argv[1],'utf8');const start=html.indexOf('(function (root) {');if(start<0)throw Error('Repository HTML needs embedded DS core');vm.runInThisContext(html.slice(start,html.indexOf('</script>',start)));const input=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(input.map(m=>({valid:DS.validate(m).length===0,fingerprint:DS.fingerprint(m)}))));"
        result = subprocess.run(['node','-e',code,str(ROOT/'design-studio'/'index.html')],input=json.dumps(cases),text=True,capture_output=True,check=True)
        actual = json.loads(result.stdout)
        self.assertEqual(actual,[{'valid':not ds.validate(model),'fingerprint':ds.fingerprint(model)} for model in cases])

if __name__ == '__main__':
    unittest.main()
