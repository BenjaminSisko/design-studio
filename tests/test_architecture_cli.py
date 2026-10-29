"""CLI architecture analysis and scenario/baseline workflows preserve user data."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('architecture_cli_ds',ROOT/'tools/design_studio.py')
ds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ds)


class ArchitectureCLITests(unittest.TestCase):
    def run_cli(self,args,code=0):
        stdout,stderr = io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            result = ds.main([str(value) for value in args])
        self.assertEqual(result,code,stderr.getvalue())
        return stdout.getvalue(),stderr.getvalue()

    def project(self,folder):
        model = ds.read_json(ROOT/'design-studio/sample-model.json')
        model['devices'][0]['panelImage'] = '@asset:panel'
        model['evidence'] = [dict(id='sample-evidence-cli',name='SAMPLE-Evidence',mime='image/png',data='@asset:evidence',caption='',relatedId='sample-device-linux',createdAt=ds.now())]
        doc = ds.envelope(model)
        doc['assets'] = {'panel':'data:image/png;base64,AAAA','evidence':'data:image/png;base64,AQID'}
        doc['customWorkspaceField'] = {'preserve':True}
        doc['revisions'] = [dict(id='sample-initial',name='SAMPLE-Initial record',time=ds.now(),model=copy.deepcopy(model),customRevisionField='keep')]
        path = folder/'project.json';path.write_text(json.dumps(doc))
        return path,doc

    def test_analysis_commands_and_report_export_leave_project_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder);path,_ = self.project(folder);original = path.read_bytes()
            stdout,_ = self.run_cli(['lint',path]); findings = json.loads(stdout)
            self.assertTrue(any(f['severity'] == 'warning' for f in findings))
            stdout,_ = self.run_cli(['trace',path,'--source','sample-device-linux','--destination','sample-endpoint-license','--flow','sample-flow-license'])
            trace = json.loads(stdout);self.assertTrue(trace['modelOnly']);self.assertEqual(trace['status'],'unknown')
            stdout,_ = self.run_cli(['impact',path,'--failed','sample-device-compute','--failed','sample-device-compute'])
            self.assertIn('sample-device-compute',json.loads(stdout)['affectedIds'])
            for kind in ('addresses','ports','flows','handoff','build','requirements'):
                stdout,_ = self.run_cli(['report',path,'--kind',kind])
                self.assertIn('Entered model only',stdout)
                output = folder/(kind+'.txt')
                self.run_cli(['report',path,'--kind',kind,'--output',output])
                self.assertEqual(output.read_bytes().decode(),stdout)
            self.assertEqual(path.read_bytes(),original)
            self.run_cli(['report',path,'--kind','handoff','--output',path],1)
            self.assertEqual(path.read_bytes(),original)

    def test_analysis_invalid_references_are_clear_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            path,_ = self.project(Path(folder));original = path.read_bytes()
            for args in (['trace',path,'--source','missing','--destination','sample-endpoint-license'],['trace',path,'--source','sample-device-linux','--destination','sample-endpoint-license','--flow','missing'],['trace',path,'--source','sample-device-compute','--destination','sample-endpoint-license','--flow','sample-flow-license'],['impact',path,'--failed','missing']):
                _,stderr = self.run_cli(args,1)
                self.assertTrue('unknown' in stderr or 'must match' in stderr)
            self.assertEqual(path.read_bytes(),original)

    def test_scenario_create_switch_baseline_compare_and_image_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder);path,original_doc = self.project(folder);original_bytes = path.read_bytes()
            listed,_ = self.run_cli(['scenario','list',path]);self.assertEqual(json.loads(listed)['activeScenarioId'],'main')
            self.assertEqual(path.read_bytes(),original_bytes)
            alternative = folder/'alternative.json'
            out,_ = self.run_cli(['scenario','create',path,'--name','SAMPLE-IdM alternative','--id','sample-idm','--from-revision','sample-initial','--output',alternative])
            self.assertEqual(json.loads(out)['scenarioId'],'sample-idm')
            self.assertEqual(path.read_bytes(),original_bytes)
            doc = ds.envelope(ds.read_json(alternative));ds.checked(doc)
            self.assertEqual(doc['activeScenarioId'],'main')
            self.assertEqual(doc['scenarios'][1]['baseRevisionId'],'sample-initial')
            self.assertTrue(any('Before creating scenario' in r['name'] for r in doc['revisions']))
            self.run_cli(['scenario','switch',alternative,'--id','sample-idm'])
            doc = ds.envelope(ds.read_json(alternative));self.assertEqual(doc['activeScenarioId'],'sample-idm')
            self.assertTrue(any('Before switching scenario' in r['name'] for r in doc['revisions']))
            expanded = ds.checked(doc)
            change = dict(format='opsdeck-design-changes',version=1,baseProjectId=expanded['meta']['id'],baseFingerprint=ds.fingerprint(expanded),baseScenarioId='sample-idm',summary='SAMPLE-Choose identity for comparison',changes=[dict(op='meta',values={'description':'SAMPLE-Alternative architecture'})])
            changefile = folder/'change.json';changefile.write_text(json.dumps(change))
            self.run_cli(['apply',alternative,changefile,'--output',alternative])
            baseline_out,_ = self.run_cli(['baseline','capture',alternative,'--kind','accepted','--name','SAMPLE-Team design review','--author','SAMPLE-Recorder'])
            revision_id = json.loads(baseline_out)['revisionId']
            compared,_ = self.run_cli(['baseline','compare',alternative,'--left','main','--right','accepted'])
            result = json.loads(compared)
            self.assertEqual(result['right']['id'],revision_id)
            self.assertTrue(any(c['collection']=='meta' and 'description' in c['details'] for c in result['changes']))
            doc = ds.envelope(ds.read_json(alternative));expanded = ds.checked(doc)
            self.assertEqual(doc['assets'],original_doc['assets'])
            self.assertEqual(doc['customWorkspaceField'],original_doc['customWorkspaceField'])
            self.assertEqual(next(r for r in doc['revisions'] if r['id']=='sample-initial')['customRevisionField'],'keep')
            self.assertEqual(expanded['devices'][0]['panelImage'],original_doc['assets']['panel'])
            self.assertTrue(all(ds.expand_model(s['model'],doc['assets'])['devices'][0]['panelImage']==original_doc['assets']['panel'] for s in doc['scenarios']))
            self.assertEqual(doc['revisions'][0]['kind'],'accepted')
            self.assertEqual(doc['revisions'][0]['author'],'SAMPLE-Recorder')
            self.run_cli(['scenario','switch',alternative,'--id','main'])
            self.assertEqual(ds.checked(ds.envelope(ds.read_json(alternative)))['meta']['description'],original_doc['model']['meta']['description'])
            html = folder/'handoff.html';self.run_cli(['render',alternative,'--output',html])
            self.assertIn('@asset:panel',html.read_text())
            self.assertIn('data:image/png;base64,AAAA',html.read_text())

    def test_workspace_commands_reject_duplicates_unknown_refs_and_ambiguous_compare(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder);path,_ = self.project(folder)
            self.run_cli(['scenario','create',path,'--name','SAMPLE-A','--id','accepted'])
            self.run_cli(['baseline','capture',path,'--kind','accepted','--name','SAMPLE-Review'])
            original = path.read_bytes()
            cases = (['scenario','create',path,'--name','SAMPLE-B','--id','accepted'],['scenario','create',path,'--name','SAMPLE-B','--from-revision','missing'],['scenario','create',path,'--name','   '],['scenario','create',path,'--name','SAMPLE-X','--id','__proto__'],['scenario','switch',path,'--id','missing'],['baseline','capture',path,'--kind','target','--name','   '],['baseline','compare',path,'--left','missing','--right','main'],['baseline','compare',path,'--left','accepted','--right','main'])
            for args in cases:
                self.run_cli(args,1)
                self.assertEqual(path.read_bytes(),original)
            out,_ = self.run_cli(['baseline','compare',path,'--left','scenario:accepted','--right','baseline:accepted'])
            self.assertEqual(json.loads(out)['changes'],[])

    def test_scope_omission_cannot_cross_identical_scenarios(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder);path,_ = self.project(folder)
            self.run_cli(['scenario','create',path,'--name','SAMPLE-Identical alternative','--id','sample-identical'])
            document = ds.envelope(ds.read_json(path));main = ds.checked(document)
            alternative = ds.expand_model(document['scenarios'][1]['model'],document['assets'])
            self.assertEqual(ds.fingerprint(main),ds.fingerprint(alternative))
            unscoped = dict(format='opsdeck-design-changes',version=1,baseProjectId=main['meta']['id'],baseFingerprint=ds.fingerprint(main),summary='SAMPLE-Scope guard',changes=[dict(op='meta',values={'description':'SAMPLE-Scoped edit'})])
            prop = folder/'proposal.json';prop.write_text(json.dumps(unscoped))
            # Identical model fingerprints do not identify the intended scenario.
            original = path.read_bytes()
            self.run_cli(['apply',path,prop,'--output',path],1)
            self.assertEqual(path.read_bytes(),original)
            self.run_cli(['scenario','switch',path,'--id','sample-identical'])
            original = path.read_bytes()
            for scope in (None,'','main','unknown'):
                change = copy.deepcopy(unscoped)
                if scope is not None:change['baseScenarioId'] = scope
                prop.write_text(json.dumps(change))
                self.run_cli(['apply',path,prop,'--output',path],1)
                self.assertEqual(path.read_bytes(),original)
            valid = {**unscoped,'baseScenarioId':'sample-identical'};prop.write_text(json.dumps(valid))
            self.run_cli(['apply',path,prop,'--output',path])
            self.assertEqual(ds.checked(ds.envelope(ds.read_json(path)))['meta']['description'],'SAMPLE-Scoped edit')
            # A named sole scenario also requires its explicit scope.
            document = ds.envelope(ds.read_json(path));document['scenarios'] = [document['scenarios'][1]]
            document['revisions'] = [];document['baselines'] = {};document['scenarios'][0]['baseRevisionId'] = ''
            path.write_text(json.dumps(document));model = ds.checked(document)
            unscoped['baseFingerprint'] = ds.fingerprint(model);prop.write_text(json.dumps(unscoped))
            self.run_cli(['apply',path,prop,'--output',path],1)
            # Legacy raw-model and sole-main proposals retain their existing contract.
            legacy = ds.blank();path.write_text(json.dumps(legacy))
            unscoped.update(baseProjectId=legacy['meta']['id'],baseFingerprint=ds.fingerprint(legacy));prop.write_text(json.dumps(unscoped))
            self.run_cli(['apply',path,prop,'--output',path])
            document = ds.envelope(ds.read_json(path));ds.ensure_workspace(document);path.write_text(json.dumps(document))
            unscoped['baseFingerprint'] = ds.fingerprint(ds.checked(document));prop.write_text(json.dumps(unscoped))
            self.run_cli(['apply',path,prop,'--output',path])

    def test_workspace_reserved_identifiers_are_rejected(self):
        for reserved in ('__proto__','constructor','prototype'):
            model = ds.blank();document = ds.envelope(model)
            document['scenarios'] = [dict(id=reserved,name='SAMPLE-Invalid scenario',model=copy.deepcopy(model))]
            document['activeScenarioId'] = reserved
            with self.assertRaisesRegex(ValueError,'reserved'):
                ds.checked(document)
            document = ds.envelope(model)
            document['revisions'] = [dict(id=reserved,name='SAMPLE-Invalid revision',time=ds.now(),model=copy.deepcopy(model))]
            with self.assertRaisesRegex(ValueError,'reserved'):
                ds.checked(document)

    def test_foreign_project_revision_is_rejected(self):
        model = ds.blank();document = ds.envelope(model)
        document['revisions'] = [dict(id='sample-foreign',name='SAMPLE-Foreign project revision',time=ds.now(),model=ds.blank())]
        with self.assertRaisesRegex(ValueError,'same project'):
            ds.checked(document)

    def test_raw_model_can_upgrade_and_sibling_import_works_outside_repo(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder);path = folder/'raw.json';path.write_text(json.dumps(ds.blank()))
            self.run_cli(['scenario','create',path,'--name','SAMPLE-Alternative','--id','sample-alternative'])
            doc = ds.envelope(ds.read_json(path));ds.checked(doc)
            self.assertEqual(len(doc['scenarios']),2)
            result = subprocess.run([sys.executable,str(ROOT/'tools/design_studio.py'),'lint',str(path)],cwd=folder,text=True,capture_output=True,check=True)
            self.assertIsInstance(json.loads(result.stdout),list)
            doc['assets'].clear();doc['model']['devices']=[dict(id='sample-panel-device',name='SAMPLE-Panel',type='Server',owner='',status='Proposed',networkId='',rackU=None,height=1,notes='',panelImage='@asset:missing')]
            with self.assertRaisesRegex(ValueError,'front-panel'):
                ds.checked(doc)


if __name__ == '__main__':unittest.main()
