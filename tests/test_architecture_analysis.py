"""Meaningful model analysis checks and browser/CLI result parity."""
import copy
import csv
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('analysis', ROOT/'tools'/'design_analysis.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def fixture():
    model = dict(meta=dict(id='project', name='Fictional design', description='Model analysis fixture', phase='Design'),
        networks=[dict(id='lan', name='Engineering LAN', cidr='192.0.2.0/24', vlan=20, vrfId='', zoneId='zone', gateway='')],
        securityZones=[dict(id='zone', name='Engineering')],
        failureDomains=[dict(id='power-a', name='Power A', kind='Power')],
        devices=[dict(id=k, name=k, type=t, networkId='lan', owner='IT') for k,t in [('client','Workstation'),('sw','Switch'),('h1','Server'),('h2','Server')]],
        services=[dict(id=k, name=k, deviceId='', owner='IT', dependsOn=[]) for k in ['dns','application']],
        serviceInstances=[dict(id='dns1', name='DNS one', serviceId='dns', deviceId='h1', networkId='lan', failureDomainIds=[]),dict(id='dns2', name='DNS two', serviceId='dns', deviceId='h2', networkId='lan', failureDomainIds=[]),dict(id='app1', name='Application one', serviceId='application', deviceId='h1', networkId='lan', failureDomainIds=[])],
        interfaces=[dict(id=k, name=k, deviceId=d, networkId='lan', address=a, mode='Access') for k,d,a in [('c1','client','192.0.2.10/24'),('s1','sw',''),('s2','sw',''),('s3','sw',''),('a1','h1','192.0.2.11/24'),('b1','h2','192.0.2.12/24')]],
        endpoints=[dict(id=k, name=k, serviceId=s, instanceId=i, interfaceId=p, networkId='lan', address='', dnsName='') for k,s,i,p in [('dns-e1','dns','dns1','a1'),('dns-e2','dns','dns2','b1'),('app-e','application','app1','a1')]],
        links=[dict(id=k, name=k, **{'from':a,'to':b,'fromInterfaceId':ai,'toInterfaceId':bi}) for k,a,b,ai,bi in [('l1','client','sw','c1','s1'),('l2','sw','h1','s2','a1'),('l3','sw','h2','s3','b1')]],
        flows=[dict(id='flow', name='Client to application', sourceId='client', destinationId='app-e', sourceInterfaceId='c1', protocol='TCP', ports='443', direction='Initiated', purpose='Application access', policyIds=['allow'], enforcementDeviceIds=['sw'], requirementIds=['req'])],
        policies=[dict(id='allow', name='Allow application', sourceIds=['client'], destinationIds=['app-e'], sourceZoneId='zone', destinationZoneId='zone', protocol='TCP', ports='443', action='Allow', enforcementDeviceId='sw', owner='IT', ruleReference='Proposed ACL 1')],
        requirements=[dict(id='req', name='Engineering application access', owner='IT', relatedIds=['application','flow'], decisionIds=[], acceptanceCriteria='Client opens application', status='Proposed')],
        verificationTests=[dict(id='test', name='Application access test', requirementIds=['req'], relatedIds=['flow'], procedure='Open application', expectedResult='Application opens', result='Not run', evidenceIds=[])],
        tasks=[dict(id='task', title='Install application', relatedId='application', status='Done', owner='IT')],
        serviceDependencies=[], dnsRecords=[], resolverAssignments=[], identity=[], directoryObjects=[], groups=[], evidence=[], observations=[], decisions=[], relationships=[])
    return model


class ArchitectureAnalysisTests(unittest.TestCase):
    def codes(self, model):
        return [finding['code'] for finding in analysis.lint(model)]

    def test_ip_validation_is_scoped_to_routing_context(self):
        model=fixture()
        model['interfaces'][-1]['address']='192.0.2.11/24'
        self.assertIn('duplicate-address', self.codes(model))
        model['networks'].append(dict(id='other', name='Other', cidr='192.0.2.0/24', vrfId='isolated'))
        model['interfaces'][-1]['networkId']='other'
        self.assertNotIn('duplicate-address',self.codes(model))
        self.assertNotIn('overlapping-subnets',self.codes(model))
        model['networks'][-1]['vrfId']=''
        self.assertIn('overlapping-subnets',self.codes(model))
        model['interfaces'][-1]['address']='198.51.100.5/24'
        self.assertIn('address-outside-subnet',self.codes(model))
        model['interfaces'][-1]['gateway']='203.0.113.1'
        self.assertIn('gateway-outside-subnet',self.codes(model))
        model['interfaces'][-1]['address']='TBD after meeting'
        self.assertIn('interface-address-unknown',self.codes(model))

    def test_vlan_continuity_and_real_physical_path(self):
        model=fixture()
        self.assertEqual(analysis.trace(model,dict(flowId='flow'))['status'],'documented')
        model['links']=[]
        result=analysis.trace(model,dict(flowId='flow'))
        self.assertEqual(result['status'],'unknown')
        self.assertTrue(any('cable' in u for u in result['unknowns']))
        model=fixture()
        model['networks'].append(dict(id='wrong',name='Wrong VLAN',cidr='198.51.100.0/24',vlan=30))
        model['interfaces'][1].update(mode='Trunk',networkId='wrong',taggedNetworkIds=[])
        self.assertIn('trunk-vlan-missing',self.codes(model))
        self.assertEqual(analysis.trace(model,dict(flowId='flow'))['status'],'unknown')

    def test_routed_path_requires_gateway_and_return_design(self):
        model=fixture()
        model['networks'].append(dict(id='server-net',name='Server subnet',cidr='198.51.100.0/24',vrfId='',zoneId='zone',gateway='198.51.100.1'))
        model['networks'][0]['gateway']='192.0.2.1'
        model['devices'][1]['type']='Router'
        model['interfaces'][1]['address']='192.0.2.1/24'
        model['interfaces'][2].update(address='198.51.100.1/24',networkId='server-net',mode='Routed')
        model['interfaces'][4].update(address='198.51.100.11/24',networkId='server-net')
        model['endpoints'][2]['networkId']='server-net'
        result=analysis.trace(model,dict(flowId='flow'))
        self.assertEqual(result['status'],'documented',result['unknowns'])
        model['networks'][1]['gateway']=''
        result=analysis.trace(model,dict(flowId='flow'))
        self.assertEqual(result['status'],'unknown')
        self.assertTrue(any('return' in item for item in result['unknowns']))
        model['networks'][0]['gateway']='192.0.2.99'
        self.assertTrue(any('does not match' in item for item in analysis.trace(model,dict(flowId='flow'))['unknowns']))

    def test_no_policy_is_unknown_and_deny_wins(self):
        model=fixture();model['policies']=[]
        self.assertEqual(analysis.trace(model,dict(flowId='flow'))['status'],'unknown')
        self.assertIn('flow-policy-unknown',self.codes(model))
        model=fixture();deny=copy.deepcopy(model['policies'][0]);deny.update(id='deny',action='Deny',ports='440-450');model['policies'].append(deny)
        self.assertEqual(analysis.trace(model,dict(flowId='flow'))['status'],'blocked')
        deny['destinationIds']=['dns-e2']
        # Endpoint scope is specific: another endpoint on a different host is not the destination.
        self.assertEqual(analysis.trace(model,dict(flowId='flow'))['status'],'documented')
        model['policies'][0]['ports']='TBD'
        self.assertEqual(analysis.trace(model,dict(flowId='flow'))['status'],'unknown')

    def test_replica_survival_and_all_any_dependencies(self):
        model=fixture()
        result=analysis.impact(model,dict(failedIds=['h1']))
        self.assertIn('dns1',result['affectedIds'])
        self.assertNotIn('dns2',result['affectedIds'])
        self.assertIn('dns',result['availableServiceIds'])
        self.assertNotIn('dns',result['affectedIds'])
        for sid,host in [('first','h1'),('second','h2'),('consumer','h2')]:
            model['services'].append(dict(id=sid,name=sid,deviceId=host,owner='IT',dependsOn=[]))
        model['serviceDependencies']=[dict(id='dep-'+target,fromServiceId='consumer',toServiceId=target,kind='Runtime',requirement='All') for target in ['first','second']]
        self.assertIn('consumer',analysis.impact(model,dict(failedIds=['h1']))['affectedIds'])
        for dep in model['serviceDependencies']:dep['requirement']='Any'
        self.assertNotIn('consumer',analysis.impact(model,dict(failedIds=['h1']))['affectedIds'])
        self.assertIn('consumer',analysis.impact(model,dict(failedIds=['h1','h2']))['affectedIds'])
        for dep in model['serviceDependencies']:dep.update(kind='Optional',requirement='All')
        result=analysis.impact(model,dict(failedIds=['h1']))
        self.assertIn('consumer',result['degradedIds']);self.assertNotIn('consumer',result['affectedIds'])

    def test_endpoint_only_failure_and_unknown_hosting(self):
        model=fixture()
        result=analysis.impact(model,dict(failedIds=['dns-e1']))
        self.assertIn('dns1',result['affectedIds'])
        self.assertNotIn('dns2',result['affectedIds'])
        self.assertIn('dns',result['availableServiceIds'])
        self.assertIn('application',analysis.impact(model,dict(failedIds=['app-e']))['affectedIds'])
        model['serviceInstances']=[]
        model['endpoints']=[]
        result=analysis.impact(model,dict(failedIds=[]))
        self.assertEqual(result['serviceStates']['dns'],'unknown')
        self.assertNotIn('dns',result['availableServiceIds'])
        self.assertIn('dns',result['unknownServiceIds'])
        model['services'][0]['deviceId']='h2'
        result=analysis.impact(model,dict(failedIds=[]))
        self.assertNotIn('dns',result['availableServiceIds'])
        self.assertTrue(any('no service endpoints' in u for u in result['unknowns']))

    def test_failure_domains_switch_and_cycles(self):
        model=fixture()
        model['devices'][2]['failureDomainIds']=['power-a'];model['devices'][3]['failureDomainIds']=['power-a']
        self.assertIn('shared-failure-domain',self.codes(model))
        self.assertIn('dns',analysis.impact(model,dict(failedIds=['power-a']))['affectedIds'])
        result=analysis.impact(model,dict(failedIds=['sw']))
        self.assertIn('dns',result['degradedIds'])
        self.assertNotIn('h1',result['affectedIds'])
        model['serviceDependencies']=[dict(id='d1',fromServiceId='dns',toServiceId='application',kind='Runtime',requirement='All'),dict(id='d2',fromServiceId='application',toServiceId='dns',kind='Runtime',requirement='All')]
        self.assertTrue(analysis.impact(model,dict(failedIds=['h1']))['modelOnly'])

    def test_linked_dns_address_and_verification_are_not_status_labels(self):
        model=fixture()
        model['endpoints'][2]['address']='192.0.2.100'
        model['dnsRecords']=[dict(id='record',name='app.example.invalid',type='A',targetId='app-e',value='192.0.2.100')]
        self.assertIn('endpoint-address-mismatch',self.codes(model))
        self.assertIn('dns-target-mismatch',self.codes(model))
        self.assertEqual(analysis.effective_address(model,model['endpoints'][2]),'192.0.2.11/24')
        model['requirements'][0]['status']='Verified'
        self.assertIn('verified-without-evidence',self.codes(model))
        model['verificationTests'][0]['result']='Pass'
        self.assertIn('passing-test-incomplete',self.codes(model))
        model['evidence']=[dict(id='e',name='Screenshot')]
        model['verificationTests'][0].update(actualResult='Application opened',performedBy='Tester',performedAt='2026-10-29',evidenceIds=['e'])
        self.assertNotIn('verified-without-evidence',self.codes(model))

    def test_reports_escape_csv_and_markdown_and_preserve_unknowns(self):
        model=fixture();model['devices'][0]['name']='Client, "west"\n=SUM(1,2)';model['meta']['name']='<script>alert(1)</script>'
        result=list(csv.reader(io.StringIO(analysis.report(model,dict(kind='addresses')))))
        self.assertEqual(result[1][1],model['devices'][0]['name'])
        self.assertTrue(all(len(row)==len(result[0]) for row in result))
        self.assertIn('192.0.2.11/24',analysis.report(model,dict(kind='addresses')))
        handoff=analysis.report(model,dict(kind='handoff'))
        self.assertIn('&lt;script&gt;',handoff);self.assertNotIn('<script>',handoff)
        self.assertIn('Verification incomplete',handoff)
        self.assertIn('Task completion does not imply',handoff)
        model['services'][0]['name']='=HYPERLINK("evil")'
        self.assertIn("'=HYPERLINK",analysis.csv_report(['x'],[[model['services'][0]['name']]]))
        model['serviceDependencies']=[dict(id='start',fromServiceId='application',toServiceId='dns',kind='Startup',requirement='All')]
        order=analysis.report(model,dict(kind='build'))
        self.assertLess(order.index('1. =HYPERLINK'),order.index('2. application'))

    @unittest.skipUnless(shutil.which('node'),'Node unavailable; logical SVG source needs Node for this check.')
    def test_logical_semantic_views_render_safe_svg_and_distinct_edges(self):
        import xml.etree.ElementTree as ET
        model=fixture()
        model['identity']=[dict(id='identity',name='Undecided identity',serviceId='dns',implementation='Undecided',domain='',realm='')]
        model['directoryObjects']=[dict(id='ou',name='Engineering container',identityId='identity',parentId='',kind='OU')]
        model['principals']=[dict(id='person',name='Engineer <one>',identityId='identity',kind='User',nativeId='engineer1')]
        model['groups']=[dict(id='group',name='Engineering',identityId='identity',parentId='',containerId='ou',kind='Security',memberIds=['person'],accessIds=[])]
        model['accessMappings']=[dict(id='access',name='Application permission',principalId='group',serviceId='application',role='User',permission='Execute',resource='Engineering')]
        model['dnsZones']=[dict(id='zone-dns',name='example.invalid',serviceId='dns',kind='Forward')]
        model['dnsRecords']=[dict(id='dns-record',name='application',zoneId='zone-dns',type='A',value='192.0.2.11',targetId='app-e')]
        model['resolverAssignments']=[dict(id='resolver',name='Client resolvers',clientId='client',resolverEndpointIds=['dns-e1','dns-e2'])]
        model['serviceDependencies']=[dict(id='dep',fromServiceId='application',toServiceId='dns',kind='Runtime',requirement='All')]
        code="""const ls=require('./src/logical.js');let data='';process.stdin.on('data',s=>data+=s);process.stdin.on('end',()=>{const m=JSON.parse(data),esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('\"','&quot;'),h={esc,svgStart:(w,h,t)=>'<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"'+w+'\" height=\"'+h+'\"><title>'+esc(t)+'</title>',svgEnd:()=>'</svg>'},f=(key,label,type,options)=>({key,label,type,...options});process.stdout.write(JSON.stringify({svgs:['logical','identity','dns','applications'].map(v=>ls.draw(m,v,h)),fresh:ls.defs('groups',{id:'new',identityId:'identity',kind:''},{f,model:m}),legacy:ls.defs('groups',{id:'old',identityId:'identity',kind:'Organizational unit'},{f,model:m})}));});"""
        result=subprocess.run(['node','-e',code],cwd=ROOT,input=json.dumps(model),text=True,capture_output=True,check=True)
        actual=json.loads(result.stdout)
        for svg in actual['svgs']:
            ET.fromstring(svg)
            self.assertNotIn('Engineer <one>',svg)
        logical,identity,dns,applications=actual['svgs']
        self.assertIn('Contained by directory object',identity)
        self.assertIn('Member of group',identity)
        self.assertIn('Permission: User / Execute',identity)
        self.assertIn('Engineer &lt;one&gt;',identity)
        self.assertIn('Resolver priority 1',dns)
        self.assertIn('data-id="resolver"',dns)
        self.assertIn('Resolves to',dns)
        self.assertIn('Provided by instance',applications)
        self.assertIn('Runtime dependency / All',applications)
        self.assertIn('data-id="dep"',applications)
        self.assertIn('Endpoint provided by instance',logical)
        fresh=next(field for field in actual['fresh'] if field['key']=='kind')['options']
        legacy=next(field for field in actual['legacy'] if field['key']=='kind')['options']
        self.assertNotIn('Organizational unit',fresh)
        self.assertIn('Organizational unit',legacy)
        members=next(field for field in actual['fresh'] if field['key']=='memberIds')['rows']
        self.assertIn('person',[r['id'] for r in members])

    @unittest.skipUnless(shutil.which('node'),'Node unavailable; Python analysis remains standalone.')
    def test_javascript_python_analysis_parity(self):
        cases=[fixture()]
        duplicate=fixture();duplicate['interfaces'][-1]['address']='192.0.2.11/24';cases.append(duplicate)
        deny=fixture();deny['policies'][0]['action']='Deny';cases.append(deny)
        unknown=fixture();unknown['policies']=[];unknown['interfaces'][0]['address']='TBD';cases.append(unknown)
        ipv6=fixture();ipv6['networks'][0]['cidr']='2001:db8::/64';ipv6['interfaces'][0]['address']='2001:db8::1/64';ipv6['interfaces'][4]['address']='2001:0db8:0:0:0:0:0:1/64';cases.append(ipv6)
        routed=fixture();routed['networks'].append(dict(id='net2',name='Net2',cidr='198.51.100.0/24',zoneId='zone'));routed['devices'][1]['type']='Router';routed['interfaces'][2].update(networkId='net2',address='198.51.100.1/24');routed['interfaces'][4].update(networkId='net2',address='198.51.100.11/24');cases.append(routed)
        nohost=fixture();nohost['serviceInstances']=[];nohost['endpoints']=[];cases.append(nohost)
        shared=fixture();shared['devices'][2]['failureDomainIds']=['power-a'];shared['devices'][3]['failureDomainIds']=['power-a'];cases.append(shared)
        code="const a=require('./src/analysis.js');let data='';process.stdin.on('data',s=>data+=s);process.stdin.on('end',()=>process.stdout.write(JSON.stringify(JSON.parse(data).map(m=>({lint:a.lint(m),trace:a.trace(m,{flowId:'flow'}),impact:a.impact(m,{failedIds:['h1']}),reports:['addresses','ports','flows','requirements','build','handoff'].map(kind=>a.report(m,{kind}))})))));"
        result=subprocess.run(['node','-e',code],cwd=ROOT,input=json.dumps(cases),text=True,capture_output=True,check=True)
        actual=json.loads(result.stdout)
        expected=[dict(lint=analysis.lint(m),trace=analysis.trace(m,dict(flowId='flow')),impact=analysis.impact(m,dict(failedIds=['h1'])),reports=[analysis.report(m,dict(kind=k)) for k in ['addresses','ports','flows','requirements','build','handoff']]) for m in cases]
        self.assertEqual(actual,expected)

if __name__=='__main__':unittest.main()
