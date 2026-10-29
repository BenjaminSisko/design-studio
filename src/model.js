(function (root) {
  'use strict';
  const ARCH_SCHEMA = typeof module !== 'undefined' && module.exports ? require('./architecture-schema.json') : __ARCHITECTURE_SCHEMA__;
  const ARCH_COLLECTIONS = Object.keys(ARCH_SCHEMA).filter(key=>!['devices','networks','interfaces','groups'].includes(key));
  const NODE_COLLECTIONS = ['devices','networks','services','identity','groups','dnsZones','dnsRecords','racks','vrfs','securityZones','failureDomains','serviceInstances','endpoints','directoryObjects','principals'];
  const OPTIONAL_COLLECTIONS = ['identity','groups','dnsZones','dnsRecords','relationships',...ARCH_COLLECTIONS];
  const COLLECTIONS = ['devices','networks','services','interfaces','links','decisions','tasks','evidence','comments','diagrams',...OPTIONAL_COLLECTIONS];
  const NAMED = ['devices','networks','services','interfaces','evidence','diagrams','identity','groups','dnsZones','dnsRecords',...ARCH_COLLECTIONS];
  const REQUIRED = {devices:'id name type owner status networkId rackU height notes',networks:'id name cidr vlan purpose owner status',services:'id name platform owner status deviceId networkId notes dependsOn',interfaces:'id name deviceId networkId address mac speed status notes',links:'id from to label status',decisions:'id title status owner due context options selectedOptionId rationale relatedIds',tasks:'id title owner status due relatedId',evidence:'id name mime data caption relatedId createdAt',comments:'id entityId author text createdAt resolved',diagrams:'id name nodeIds notes',identity:'id name serviceId implementation domain realm notes status',groups:'id name identityId parentId kind memberIds accessIds notes status',dnsZones:'id name serviceId kind notes status',dnsRecords:'id name zoneId type value targetId ttl notes status',relationships:'id from to kind label protocol port endpoint notes status'};
  Object.entries(ARCH_SCHEMA).forEach(([key,descriptor])=>{REQUIRED[key]=descriptor.required;});
  const id = prefix => (prefix || 'item') + '-' + (root.crypto && root.crypto.randomUUID ? root.crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2,10));
  function copy(value){if(!value||typeof value!=='object')return value;const output=Array.isArray(value)?[]:Object.create(null),stack=[[value,output]],seen=new WeakSet([value]);while(stack.length){const [source,target]=stack.pop();Object.keys(source).forEach(key=>{const item=source[key];let cloned;if(item&&typeof item==='object'){if(seen.has(item))throw new Error('Metadata must contain JSON values without shared or circular references.');seen.add(item);cloned=Array.isArray(item)?[]:Object.create(null);stack.push([item,cloned]);}else if(item===null||['string','boolean'].includes(typeof item)||(typeof item==='number'&&Number.isFinite(item)))cloned=item;else throw new Error('Metadata contains a value that cannot be represented in JSON.');Object.defineProperty(target,key,{value:cloned,enumerable:true,configurable:true,writable:true});});}return output;}
  const empty = value => value === '' || value === null || value === undefined;
  const label = row => [row.name,row.title,row.label,row.entityId,row.id].find(value=>typeof value==='string'&&value.trim()) || 'Record';
  const record = value => !!value && typeof value === 'object' && !Array.isArray(value);
  const number = value => typeof value === 'number' ? value : typeof value === 'string' && /^\d+$/.test(value) ? Number(value) : NaN;
  const display = value => ['string','number','boolean'].includes(typeof value) ? String(value) : '(invalid value)';
  function ipv4(address){const parts=address.split('.');return parts.length===4&&parts.every(p=>/^\d{1,3}$/.test(p)&&Number(p)<=255);}
  function ipv6(address){
    let value=address;
    if(value.includes('.')){const colon=value.lastIndexOf(':');if(colon<0||!ipv4(value.slice(colon+1)))return false;value=value.slice(0,colon+1)+'0:0';}
    if(!/^[0-9a-fA-F:]+$/.test(value))return false;
    const halves=value.split('::');if(halves.length>2)return false;
    const groups=halves.flatMap(half=>half?half.split(':'):[]);
    return groups.every(g=>/^[0-9a-fA-F]{1,4}$/.test(g))&&(halves.length===2?groups.length<8:groups.length===8);
  }
  function blank(name) {
    const model = {schemaVersion:1,meta:{id:id('project'),name:String(name || 'New design'),description:'',phase:'Concept',author:'',rackUnits:42,rackName:'SAMPLE-INFRA-01',classification:'',classificationColor:'#29624b'}};
    COLLECTIONS.forEach(key => { model[key] = []; });
    return model;
  }
  function migrate(model){const next=copy(model);if(record(next))OPTIONAL_COLLECTIONS.forEach(key=>{if(next[key]===undefined)next[key]=[];});return next;}
  function seed() {
    const m = blank('SAMPLE-Engineering + IT integration');
    m.meta.description = 'Fictional meeting starter. Every item is proposed; replace sample records with the team’s verified design.';
    m.networks = [
      {id:'sample-net-engineering',name:'SAMPLE-Engineering segment',cidr:'',vlan:'',purpose:'Engineering hosts and test equipment; addressing and controls undecided.',owner:'Engineering',status:'Proposed'},
      {id:'sample-net-infrastructure',name:'SAMPLE-Infrastructure segment',cidr:'',vlan:'',purpose:'Shared IT services; addressing and controls undecided.',owner:'IT',status:'Proposed'},
      {id:'sample-net-management',name:'SAMPLE-Management segment',cidr:'',vlan:'',purpose:'Administration plane; addressing and access path undecided.',owner:'IT',status:'Proposed'}
    ];
    const device = (key,name,type,owner,net,u,height,notes) => ({id:'sample-device-'+key,name:'SAMPLE-'+name,type,owner,status:'Proposed',networkId:'sample-net-'+net,rackU:u,height,notes:notes || ''});
    m.devices = [
      device('firewall','Boundary gateway','Firewall','IT','management',42,1,'Placeholder. Hardware and policy are undecided.'),
      device('switch','Infrastructure switch','Switch','IT','management',40,1,'Placeholder placement; port count and uplinks are undecided.'),
      device('compute','Shared services host','Server','IT','infrastructure',36,2,'Placeholder compute capacity for proposed services.'),
      device('security','Security services host','Server','IT','infrastructure',33,2,'Placeholder for monitoring and security services.'),
      device('backup','Backup target','Storage','IT','infrastructure',30,2,'Backup architecture and retention are undecided.'),
      device('workstation','Engineering workstation','Workstation','Engineering','engineering',null,1,'Illustrative endpoint; ownership and support boundary need agreement.'),
      device('linux','Engineering Linux node','Linux host','Engineering','engineering',null,1,'Operating system version and identity integration are undecided.'),
      device('instrument','Test instrument','Test equipment','Engineering','engineering',null,1,'Connectivity, protocols, and support constraints need confirmation.')
    ];
    const service = (key,name,host,net,notes) => ({id:'sample-service-'+key,name:'SAMPLE-'+name,platform:'Undecided',owner:'IT',status:'Proposed',deviceId:host?'sample-device-'+host:'',networkId:'sample-net-'+net,notes,dependsOn:[]});
    m.services = [
      service('identity','Identity','compute','infrastructure','Open choice: evaluate Red Hat IdM and Microsoft Active Directory using team requirements.'),
      service('dns','DNS','compute','infrastructure','Resolve namespace, authority, forwarding, and ownership in the design workshop.'),
      service('ntp','Time service','compute','infrastructure','Choose authoritative sources, client configuration, and disconnected operation requirements.'),
      service('logging','Central logging','security','infrastructure','Choose collection scope, retention, platform, and operational owner.'),
      service('security','Security management','security','infrastructure','Define required security services and endpoint responsibilities.'),
      service('backup','Backup and recovery','backup','infrastructure','Define scope, recovery objectives, platform, and restore verification.'),
      service('matlab','MATLAB application','compute','infrastructure','Fictional application placeholder. Proposed license dependency needs verification; vendor, endpoint, and ports remain unassigned.'),
      service('atlassian','Atlassian application','compute','infrastructure','Fictional application placeholder. Proposed identity and DNS dependencies need verification; no licensing architecture is assumed.'),
      service('license','License management service','compute','infrastructure','Fictional service placeholder. Confirm product requirements and whether a shared license service is needed; do not infer vendor defaults.')
    ];
    const serviceKinds={identity:'Identity',dns:'DNS',ntp:'Time',logging:'Logging',security:'Security',backup:'Backup',matlab:'Application',atlassian:'Application',license:'License'};
    m.services.forEach(row=>{row.kind=serviceKinds[row.id.replace('sample-service-','')];row.endpoint='';row.protocol='';row.port='';row.licenseManager='';row.redundancy='';});
    m.services.find(row=>row.id==='sample-service-atlassian').dependsOn=['sample-service-identity','sample-service-dns'];
    m.identity=[{id:'sample-identity-workforce',name:'SAMPLE-Workforce identity',serviceId:'sample-service-identity',implementation:'Undecided',domain:'',realm:'',notes:'Proposed logical identity structure. Red Hat IdM and Microsoft Active Directory remain candidates; no provider capabilities are assumed.',status:'Proposed'}];
    m.groups=[
      {id:'sample-group-engineering',name:'SAMPLE-Engineering',identityId:'sample-identity-workforce',parentId:'',kind:'Group',memberIds:['sample-device-workstation','sample-device-linux'],accessIds:['sample-service-matlab','sample-service-atlassian'],notes:'Proposed membership and application access for team review; no authorization is granted by this diagram.',status:'Proposed'},
      {id:'sample-group-test',name:'SAMPLE-Test team',identityId:'sample-identity-workforce',parentId:'sample-group-engineering',kind:'Group',memberIds:['sample-device-instrument'],accessIds:['sample-service-matlab'],notes:'Proposed container/member structure; validate feasibility after choosing an identity platform.',status:'Proposed'}
    ];
    m.dnsZones=[{id:'sample-dns-zone',name:'SAMPLE-sample.invalid',serviceId:'sample-service-dns',kind:'Forward',notes:'Fictional sample.invalid namespace. Actual namespace, zone authority, and forwarding remain undecided.',status:'Proposed'}];
    m.dnsRecords=[
      {id:'sample-dns-matlab',name:'SAMPLE-matlab.sample.invalid',zoneId:'sample-dns-zone',type:'A',value:'',targetId:'sample-service-matlab',ttl:'',notes:'Proposed record target only. Address and TTL are unassigned.',status:'Proposed'},
      {id:'sample-dns-atlassian',name:'SAMPLE-atlassian.sample.invalid',zoneId:'sample-dns-zone',type:'A',value:'',targetId:'sample-service-atlassian',ttl:'',notes:'Proposed record target only. Address and TTL are unassigned.',status:'Proposed'},
      {id:'sample-dns-license',name:'SAMPLE-license.sample.invalid',zoneId:'sample-dns-zone',type:'A',value:'',targetId:'sample-service-license',ttl:'',notes:'Proposed record target only. Address and TTL are unassigned.',status:'Proposed'}
    ];
    const relationship=(key,from,to,kind,label)=>({id:'sample-relationship-'+key,from,to,kind,label:'SAMPLE-'+label,protocol:'',port:'',endpoint:'',notes:'Proposed relationship; confirm implementation and test before treating as verified.',status:'Proposed'});
    m.relationships=[
      relationship('matlab-license','sample-service-matlab','sample-service-license','uses-license','MATLAB → proposed license service'),
      relationship('atlassian-identity','sample-service-atlassian','sample-identity-workforce','authenticates','Atlassian → proposed identity'),
      relationship('atlassian-dns','sample-service-atlassian','sample-service-dns','resolves','Atlassian → proposed DNS'),
      relationship('engineering-matlab','sample-group-engineering','sample-service-matlab','access','Engineering → proposed MATLAB access'),
      relationship('engineering-atlassian','sample-group-engineering','sample-service-atlassian','access','Engineering → proposed Atlassian access')
    ];
    m.interfaces = [
      {id:'sample-interface-fw-uplink',name:'SAMPLE-Gateway uplink',deviceId:'sample-device-firewall',networkId:'sample-net-management',address:'',mac:'',speed:'Undecided',status:'Proposed',notes:'Port identifier and addressing need confirmation.'},
      {id:'sample-interface-switch-uplink',name:'SAMPLE-Switch uplink',deviceId:'sample-device-switch',networkId:'sample-net-management',address:'',mac:'',speed:'Undecided',status:'Proposed',notes:'Port identifier and addressing need confirmation.'},
      {id:'sample-interface-services',name:'SAMPLE-Services host interface',deviceId:'sample-device-compute',networkId:'sample-net-infrastructure',address:'',mac:'',speed:'Undecided',status:'Proposed',notes:'Connectivity requirements need confirmation.'},
      {id:'sample-interface-linux',name:'SAMPLE-Engineering Linux interface',deviceId:'sample-device-linux',networkId:'sample-net-engineering',address:'',mac:'',speed:'Undecided',status:'Proposed',notes:'Engineering-owned endpoint; port and addressing need confirmation.'}
    ];
    m.links = [
      {id:'sample-link-boundary',from:'sample-device-firewall',to:'sample-device-switch',fromInterfaceId:'sample-interface-fw-uplink',toInterfaceId:'sample-interface-switch-uplink',label:'SAMPLE-Uplink — design pending',status:'Proposed'},
      {id:'sample-link-engineering',from:'sample-net-engineering',to:'sample-device-firewall',label:'SAMPLE-Engineering connection — policy pending',status:'Proposed'},
      {id:'sample-link-compute',from:'sample-device-switch',to:'sample-device-compute',label:'SAMPLE-Services connection',status:'Proposed'}
    ];
    m.decisions = [
      {id:'sample-decision-identity',title:'SAMPLE-Identity platform selection',status:'Open',owner:'',due:'',context:'Compare the candidate platforms against the team’s verified requirements. Capture evidence and constraints before recording a selection.',options:[{id:'sample-option-idm',label:'Red Hat IdM',pros:'',cons:''},{id:'sample-option-ad',label:'Microsoft Active Directory',pros:'',cons:''},{id:'sample-option-other',label:'Other / combined approach',pros:'',cons:''}],selectedOptionId:'',rationale:'',relatedIds:['sample-service-identity','sample-device-linux']},
      {id:'sample-decision-dns',title:'SAMPLE-DNS design and ownership',status:'Open',owner:'',due:'',context:'Agree on namespace, authoritative zones, forwarding, and the support owner. No design is selected.',options:[{id:'sample-option-dns-integrated',label:'Identity-integrated DNS design',pros:'',cons:''},{id:'sample-option-dns-separate',label:'Separately managed DNS design',pros:'',cons:''}],selectedOptionId:'',rationale:'',relatedIds:['sample-service-dns','sample-service-identity']},
      {id:'sample-decision-boundary',title:'SAMPLE-Engineering / IT service boundary',status:'Open',owner:'',due:'',context:'Define which team owns hosts, shared services, incident response, and approved communication paths.',options:[{id:'sample-option-boundary-a',label:'Document candidate A in the workshop',pros:'',cons:''},{id:'sample-option-boundary-b',label:'Document candidate B in the workshop',pros:'',cons:''}],selectedOptionId:'',rationale:'',relatedIds:['sample-net-engineering','sample-net-infrastructure','sample-device-firewall']}
    ];
    m.tasks = [
      {id:'sample-task-inventory',title:'SAMPLE-Confirm equipment and existing diagrams',owner:'Engineering + IT',status:'Open',due:'',relatedId:'sample-device-instrument'},
      {id:'sample-task-identity',title:'SAMPLE-Capture identity requirements and platform constraints',owner:'',status:'Open',due:'',relatedId:'sample-decision-identity'},
      {id:'sample-task-dns',title:'SAMPLE-Document DNS namespace and ownership options',owner:'',status:'Open',due:'',relatedId:'sample-decision-dns'},
      {id:'sample-task-recovery',title:'SAMPLE-Agree recovery objectives and acceptance criteria',owner:'',status:'Open',due:'',relatedId:'sample-service-backup'}
    ];
    m.diagrams = [
      {id:'sample-diagram-integration',name:'SAMPLE-Engineering + IT overview',nodeIds:[...m.devices.map(x=>x.id),...m.networks.map(x=>x.id),...m.services.map(x=>x.id)],notes:'Fictional proposed architecture. Use the model to capture the real workshop outcomes.'},
      {id:'sample-diagram-logical',name:'SAMPLE-Logical services',nodeIds:['sample-service-identity','sample-service-dns','sample-service-matlab','sample-service-atlassian','sample-service-license',...m.identity.map(x=>x.id),...m.groups.map(x=>x.id),...m.dnsZones.map(x=>x.id),...m.dnsRecords.map(x=>x.id)],notes:'Proposed identity structure, DNS targets, application access, and license dependency. Names and relationships follow stable IDs across edits.'}
    ];
    // Illustrative architecture only: documentation address ranges and .invalid
    // names demonstrate relationships; they are never installation defaults.
    m.meta.modelVersion=2;
    m.racks=[{id:'sample-rack-a',name:'SAMPLE-IT rack A',units:42,site:'SAMPLE-Lab',location:'Unassigned',notes:'Fictional rack location.',status:'Proposed'},{id:'sample-rack-b',name:'SAMPLE-IT rack B',units:42,site:'SAMPLE-Lab',location:'Unassigned',notes:'Fictional second rack for comparing failure domains.',status:'Proposed'}];
    m.vrfs=[{id:'sample-vrf-lab',name:'SAMPLE-Lab routing context',routeDistinguisher:'',notes:'Fictional isolated design context; no deployment configuration implied.',status:'Proposed'}];
    m.securityZones=[{id:'sample-zone-engineering',name:'SAMPLE-Engineering zone',owner:'Engineering',notes:'Boundary and approved paths need team review.',status:'Proposed'},{id:'sample-zone-services',name:'SAMPLE-IT services zone',owner:'IT',notes:'Shared service access is a proposed requirement.',status:'Proposed'},{id:'sample-zone-management',name:'SAMPLE-Management zone',owner:'IT',notes:'Administrative path requires separate policy and verification.',status:'Proposed'}];
    m.failureDomains=[{id:'sample-failure-host-a',name:'SAMPLE-Hypervisor A failure',kind:'Host',notes:'Failure-domain placeholder.',status:'Proposed'},{id:'sample-failure-host-b',name:'SAMPLE-Hypervisor B failure',kind:'Host',notes:'Failure-domain placeholder.',status:'Proposed'},{id:'sample-failure-power-a',name:'SAMPLE-Power feed A',kind:'Power',notes:'Proposed feed; independence has not been verified.',status:'Proposed'},{id:'sample-failure-power-b',name:'SAMPLE-Power feed B',kind:'Power',notes:'Proposed feed; independence has not been verified.',status:'Proposed'}];
    const networkPlan={engineering:['192.0.2.0/24','10','192.0.2.1','sample-zone-engineering'],infrastructure:['198.51.100.0/24','20','198.51.100.1','sample-zone-services'],management:['203.0.113.0/24','30','203.0.113.1','sample-zone-management']};
    m.networks.forEach(row=>{const p=networkPlan[row.id.replace('sample-net-','')];Object.assign(row,{cidr:p[0],vlan:p[1],gateway:p[2],zoneId:p[3],vrfId:'sample-vrf-lab'});row.purpose+=' SAMPLE documentation addresses only.';});
    m.devices.forEach(row=>Object.assign(row,{rackId:row.rackU===null?'':'sample-rack-a',deviceKind:row.type==='Workstation'?'Workstation':'Physical',failureDomainIds:[],model:'',panelImage:''}));
    Object.assign(m.devices.find(row=>row.id==='sample-device-compute'),{deviceKind:'Hypervisor',failureDomainIds:['sample-failure-host-a','sample-failure-power-a']});
    Object.assign(m.devices.find(row=>row.id==='sample-device-security'),{deviceKind:'Hypervisor',rackId:'sample-rack-b',failureDomainIds:['sample-failure-host-b','sample-failure-power-b']});
    const vm=(key,host)=>({id:'sample-device-'+key,name:'SAMPLE-'+key,type:'Virtual machine',owner:'IT',status:'Proposed',networkId:'sample-net-infrastructure',rackU:null,height:1,notes:'Fictional DNS VM; platform, sizing and recovery remain undecided.',hostedBy:'sample-device-'+host,rackId:'',deviceKind:'VM',failureDomainIds:[],model:'',panelImage:''});
    m.devices.push(vm('dns-a','compute'),vm('dns-b','security'));
    m.interfaces.forEach(row=>Object.assign(row,{mode:'Unspecified',untaggedNetworkId:'',taggedNetworkIds:[],aggregateId:'',gateway:'',mtu:''}));
    const port=(key,name,device,network,address,mode,extra={})=>({id:'sample-interface-'+key,name:'SAMPLE-'+name,deviceId:'sample-device-'+device,networkId:'sample-net-'+network,address,mac:'',speed:'',status:'Proposed',notes:'Fictional interface; blank speed and MTU need confirmation.',mode,untaggedNetworkId:mode==='Access'?'sample-net-'+network:'',taggedNetworkIds:[],aggregateId:'',gateway:'',mtu:'',...extra});
    Object.assign(m.interfaces.find(row=>row.id==='sample-interface-linux'),{mode:'Access',address:'192.0.2.20/24',gateway:'192.0.2.1',untaggedNetworkId:'sample-net-engineering'});
    Object.assign(m.interfaces.find(row=>row.id==='sample-interface-services'),{mode:'Trunk',taggedNetworkIds:['sample-net-infrastructure','sample-net-management']});
    Object.assign(m.interfaces.find(row=>row.id==='sample-interface-switch-uplink'),{mode:'Trunk',taggedNetworkIds:m.networks.map(row=>row.id)});
    Object.assign(m.interfaces.find(row=>row.id==='sample-interface-fw-uplink'),{mode:'Trunk',taggedNetworkIds:m.networks.map(row=>row.id)});
    m.interfaces.push(port('linux-management','Linux management interface','linux','management','203.0.113.20/24','Access'),port('switch-engineering','Switch engineering access port','switch','engineering','','Access'),port('switch-services','Switch services trunk','switch','infrastructure','','Trunk',{taggedNetworkIds:['sample-net-infrastructure','sample-net-management']}),port('dns-a','DNS VM A interface','dns-a','infrastructure','198.51.100.53/24','Virtual'),port('dns-b','DNS VM B interface','dns-b','infrastructure','198.51.100.54/24','Virtual'));
    m.interfaces.push(port('switch-security','Switch second-host trunk','switch','infrastructure','','Trunk',{taggedNetworkIds:['sample-net-infrastructure','sample-net-management']}),port('security-services','Second hypervisor uplink','security','infrastructure','','Trunk',{taggedNetworkIds:['sample-net-infrastructure','sample-net-management']}));
    Object.assign(m.links.find(row=>row.id==='sample-link-compute'),{fromInterfaceId:'sample-interface-switch-services',toInterfaceId:'sample-interface-services'});
    m.links.push({id:'sample-link-linux-access',from:'sample-device-linux',to:'sample-device-switch',fromInterfaceId:'sample-interface-linux',toInterfaceId:'sample-interface-switch-engineering',label:'SAMPLE-Engineering client access link',status:'Proposed'});
    m.links.push({id:'sample-link-security-uplink',from:'sample-device-switch',to:'sample-device-security',fromInterfaceId:'sample-interface-switch-security',toInterfaceId:'sample-interface-security-services',label:'SAMPLE-Second hypervisor trunk',status:'Proposed'});
    m.routes=[{id:'sample-route-linux-default',name:'SAMPLE-Linux default route',deviceId:'sample-device-linux',vrfId:'sample-vrf-lab',destination:'0.0.0.0/0',gateway:'192.0.2.1',interfaceId:'sample-interface-linux',metric:'',notes:'Illustrative default route. Management routing remains unresolved.',status:'Proposed'}];
    m.serviceInstances=[{id:'sample-instance-dns-a',name:'SAMPLE-DNS instance A',serviceId:'sample-service-dns',deviceId:'sample-device-dns-a',networkId:'sample-net-infrastructure',role:'Proposed resolver A',failureDomainIds:['sample-failure-host-a','sample-failure-power-a'],notes:'Proposed deployment; shared switch dependence remains a design concern.',status:'Proposed'},{id:'sample-instance-dns-b',name:'SAMPLE-DNS instance B',serviceId:'sample-service-dns',deviceId:'sample-device-dns-b',networkId:'sample-net-infrastructure',role:'Proposed resolver B',failureDomainIds:['sample-failure-host-b','sample-failure-power-b'],notes:'Redundancy is a design proposal; no failover test has run.',status:'Proposed'}];
    const endpoint=(key,service,instance,iface,address,dnsName,role)=>({id:'sample-endpoint-'+key,name:'SAMPLE-'+key,serviceId:'sample-service-'+service,instanceId:instance?'sample-instance-'+instance:'',interfaceId:iface?'sample-interface-'+iface:'',networkId:'sample-net-infrastructure',address,dnsName,protocol:'',port:'',role,notes:'Fictional planned endpoint. Protocol and ports intentionally unresolved.',status:'Proposed'});
    m.endpoints=[endpoint('dns-a','dns','dns-a','dns-a','198.51.100.53','dns-a.sample.invalid','Resolver'),endpoint('dns-b','dns','dns-b','dns-b','198.51.100.54','dns-b.sample.invalid','Resolver'),endpoint('matlab','matlab','','','','matlab.sample.invalid','Application'),endpoint('atlassian','atlassian','','','','atlassian.sample.invalid','Application'),endpoint('license','license','','','','license.sample.invalid','Proposed license manager')];
    m.dnsRecords.forEach(row=>{const key=row.id.replace('sample-dns-','');if(['matlab','atlassian','license'].includes(key))row.targetId='sample-endpoint-'+key;});
    m.resolverAssignments=[{id:'sample-resolver-linux',name:'SAMPLE-Linux resolver plan',clientId:'sample-device-linux',resolverEndpointIds:['sample-endpoint-dns-a','sample-endpoint-dns-b'],searchDomains:['sample.invalid'],notes:'Two planned resolvers; client behavior and failover require verification.',status:'Proposed'}];
    m.serviceDependencies=[{id:'sample-dependency-license-dns',name:'SAMPLE-License name resolution',fromServiceId:'sample-service-license',toServiceId:'sample-service-dns',kind:'Runtime',requirement:'Any',notes:'Proposed dependency; confirm product and deployment requirements.',status:'Proposed'},{id:'sample-dependency-matlab-license',name:'SAMPLE-MATLAB license requirement',fromServiceId:'sample-service-matlab',toServiceId:'sample-service-license',kind:'Runtime',requirement:'All',notes:'Fictional licensing scenario for review, not a vendor default.',status:'Proposed'}];
    m.directoryObjects=[{id:'sample-directory-engineering',name:'SAMPLE-Engineering organizational container',identityId:'sample-identity-workforce',parentId:'',kind:'Container',notes:'Conceptual directory organization; provider support must be assessed before acceptance.',status:'Proposed'}];
    m.principals=[{id:'sample-principal-engineer',name:'SAMPLE-Engineer user',identityId:'sample-identity-workforce',kind:'User',nativeId:'',containerId:'sample-directory-engineering',notes:'Fictional principal; actual names and identifiers are unassigned.',status:'Proposed'}];
    m.groups.forEach(row=>{row.containerId='sample-directory-engineering';row.parentId='';});
    m.groups[0].memberIds=['sample-group-test','sample-principal-engineer','sample-device-linux'];
    m.groups[1].memberIds=['sample-device-instrument'];
    m.groups[1].notes='Nested membership is distinct from organizational container placement.';
    m.accessMappings=[{id:'sample-access-engineering-matlab',name:'SAMPLE-Engineering MATLAB access',principalId:'sample-group-engineering',serviceId:'sample-service-matlab',role:'Proposed engineering user',resource:'',permission:'',notes:'Role and permission mapping requires application-owner review.',status:'Proposed'},{id:'sample-access-engineering-atlassian',name:'SAMPLE-Engineering Atlassian access',principalId:'sample-group-engineering',serviceId:'sample-service-atlassian',role:'Proposed engineering user',resource:'',permission:'',notes:'Product and deployment-specific access model remains undecided.',status:'Proposed'}];
    m.requirements=[{id:'sample-requirement-engineering-license',name:'SAMPLE-Engineering license access',description:'The engineering Linux client must reach the confirmed application and licensing endpoints using approved paths.',owner:'Engineering + IT',priority:'High',relatedIds:['sample-device-linux','sample-service-matlab','sample-service-license'],decisionIds:['sample-decision-boundary'],acceptanceCriteria:'Resolve the agreed names, authenticate where required, complete a product-approved licensing test and record evidence.',notes:'Fictional requirement; validate licensing architecture before baseline acceptance.',status:'Proposed'}];
    m.policies=[{id:'sample-policy-license',name:'SAMPLE-License firewall request',sourceZoneId:'sample-zone-engineering',destinationZoneId:'sample-zone-services',sourceIds:['sample-device-linux'],destinationIds:['sample-endpoint-license'],protocol:'',ports:'',action:'Review',enforcementDeviceId:'sample-device-firewall',ruleReference:'',owner:'IT',notes:'Pending protocol/ports, licensing confirmation and policy approval. No rule is deployed.',status:'Proposed'}];
    m.flows=[{id:'sample-flow-license',name:'SAMPLE-Linux to license endpoint',sourceId:'sample-device-linux',destinationId:'sample-endpoint-license',sourceInterfaceId:'sample-interface-linux',protocol:'',ports:'',direction:'Initiated',purpose:'Proposed engineering license checkout; confirm deployment requirements.',zoneIds:['sample-zone-engineering','sample-zone-services'],enforcementDeviceIds:['sample-device-firewall'],policyIds:['sample-policy-license'],requirementIds:['sample-requirement-engineering-license'],notes:'Unknown ports are a visible design question. This path has not been tested.',status:'Proposed'}];
    m.verificationTests=[{id:'sample-test-license',name:'SAMPLE-Verify engineering licensing path',requirementIds:['sample-requirement-engineering-license'],relatedIds:['sample-flow-license','sample-endpoint-license'],procedure:'After the design is accepted, verify resolver behavior and the selected product licensing operation from the engineering interface; record results and evidence.',expectedResult:'Names resolve to the agreed endpoint and the authorized operation succeeds through the accepted policy.',actualResult:'',result:'Not run',performedBy:'',performedAt:'',evidenceIds:[],notes:'A proposed test procedure is not a test result.',status:'Proposed'}];
    m.observations=[];
    m.diagrams[1].nodeIds.push(...m.serviceInstances.map(row=>row.id),...m.endpoints.map(row=>row.id),...m.directoryObjects.map(row=>row.id),...m.principals.map(row=>row.id));
    return m;
  }
  function validate(model) {
    const errors = [];
    if (!record(model)) return ['Project must be a JSON object.'];
    const pending=[model],visited=new WeakSet();
    while(pending.length){const item=pending.pop();if(!item||typeof item!=='object')continue;if(visited.has(item)){errors.push('Project must contain JSON values without shared or circular object references.');continue;}visited.add(item);Object.keys(item).forEach(key=>{if(['__proto__','constructor','prototype'].includes(key))errors.push('Unsupported property key: '+key+'.');const value=item[key];if(value&&typeof value==='object')pending.push(value);else if(value!==null&&!['string','number','boolean'].includes(typeof value)||(typeof value==='number'&&!Number.isFinite(value)))errors.push('Property '+key+' cannot be represented in JSON.');});}
    if (model.schemaVersion !== 1) errors.push('Unsupported schemaVersion; expected 1.');
    const meta = model.meta;
    if (!record(meta)) return errors.concat('Project metadata is required.');
    const string = (value,path,required) => { if (typeof value !== 'string' || (required && !value.trim())) errors.push(path + (required?' must be a nonempty string.':' must be a string.')); };
    ['id','name','phase'].forEach(k=>string(meta[k],'meta.'+k,true));
    ['description','author','rackName','classification','classificationColor'].forEach(k=>{if(meta[k]!==undefined)string(meta[k],'meta.'+k,false);});
    const rackUnits=number(meta.rackUnits);
    if (!Number.isInteger(rackUnits) || rackUnits<1 || rackUnits>200) errors.push('meta.rackUnits must be an integer from 1 to 200.');
    if (!empty(meta.classificationColor) && (typeof meta.classificationColor!=='string'||!/^#[0-9a-fA-F]{6}$/.test(meta.classificationColor))) errors.push('meta.classificationColor must be a six digit hex color.');
    const ids = new Set(), byId = new Map(), typed = {};
    const claim = (value,path) => {string(value,path,true);if(typeof value==='string' && value.trim()){if(['__proto__','constructor','prototype'].includes(value))errors.push(path+' uses a reserved ID.');if(ids.has(value))errors.push('Duplicate ID: '+value+'.');ids.add(value);}};
    claim(meta.id,'meta.id');
    COLLECTIONS.forEach(key=>{
      if(model[key]===undefined&&OPTIONAL_COLLECTIONS.includes(key)){typed[key]=new Set();return;}
      if(!Array.isArray(model[key])) {errors.push(key+' must be an array.');typed[key]=new Set();return;}
      typed[key]=new Set();
      model[key].forEach((row,index)=>{
        const p=key+'['+index+']';
        if(!record(row)){errors.push(p+' must be an object.');return;}
        claim(row.id,p+'.id');if(typeof row.id==='string'){typed[key].add(row.id);byId.set(row.id,{collection:key,row});}
        if(NAMED.includes(key))string(row.name,p+'.name',true);
        if(key==='decisions'||key==='tasks')string(row.title,p+'.title',true);
        if(['devices','networks','services','interfaces','links','decisions','tasks',...OPTIONAL_COLLECTIONS].includes(key))string(row.status,p+'.status',true);
        ['owner','notes','description','purpose','platform','type','label','caption','author','context','rationale','address','mac','speed','implementation','domain','realm','kind','value','endpoint','protocol','port','licenseManager','redundancy'].forEach(field=>{if(row[field]!==undefined)string(row[field],p+'.'+field,false);});
        if(!empty(row.due)){let valid=typeof row.due==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(row.due);if(valid){const date=new Date(row.due+'T00:00:00Z');valid=Number.isFinite(date.getTime())&&date.toISOString().slice(0,10)===row.due;}if(!valid)errors.push(p+'.due must be a valid YYYY-MM-DD date.');}
        if(row.createdAt!==undefined&&(typeof row.createdAt!=='string'||!Number.isFinite(Date.parse(row.createdAt))))errors.push(p+'.createdAt must be a valid date/time string.');
      });
    });
    const rows=key=>Array.isArray(model[key])?model[key].filter(record):[];
    const reference=(value,allowed,path,required)=>{if(empty(value)){if(required)errors.push(path+' is required.');return;}if(typeof value!=='string'||!allowed.has(value))errors.push(path+' references an unknown or invalid ID: '+display(value)+'.');};
    const nodes=new Set([...typed.devices,...typed.networks,...typed.services]);
    const entities=new Set(byId.keys());
    const refList=(values,allowed,path)=>{if(!Array.isArray(values)){errors.push(path+' must be an array.');return;}const seen=new Set();values.forEach((v,i)=>{reference(v,allowed,path+'['+i+']',true);if(seen.has(v))errors.push(path+' has a duplicate ID: '+display(v)+'.');seen.add(v);});};
    const logicalNodes=new Set(NODE_COLLECTIONS.flatMap(key=>[...typed[key]]));
    const allowedFor=descriptor=>new Set((descriptor.references||[]).flatMap(key=>key==='entities'?[...entities]:key==='nodes'?[...logicalNodes]:[...(typed[key]||[])]));
    Object.entries(ARCH_SCHEMA).forEach(([collection,descriptor])=>rows(collection).forEach(row=>{
      const path=collection+' '+display(row.id),isNew=ARCH_COLLECTIONS.includes(collection);
      if(isNew)descriptor.required.split(' ').forEach(key=>{if(!Object.prototype.hasOwnProperty.call(row,key))errors.push(path+' is missing required field '+key+'.');});
      Object.entries(descriptor.fields).forEach(([key,field])=>{
        if(row[key]===undefined)return;const value=row[key],where=path+' '+key;
        if(field.type==='string')string(value,where,false);
        else if(field.type==='reference')reference(value,allowedFor(field),where,field.requiredReference);
        else if(field.type==='references')refList(value,allowedFor(field),where);
        else if(field.type==='strings'){if(!Array.isArray(value)||value.some(item=>typeof item!=='string'))errors.push(where+' must be an array of strings.');}
        else if(field.type==='enum'){if(!(typeof value==='string'&&(!isNew&&value===''||field.options.includes(value))))errors.push(where+' must be one of '+field.options.join(', ')+'.');}
        else if(field.type==='integer'){if(field.blank&&empty(value))return;const n=number(value);if(!Number.isInteger(n)||field.minimum!==undefined&&n<field.minimum||field.maximum!==undefined&&n>field.maximum)errors.push(where+' must be an integer within the documented bounds.');}
      });
    }));
    const occupied=new Map();
    rows('devices').forEach(row=>{
      const path='Device '+display(row.id),height=number(row.height),rack=byId.get(row.rackId)?.collection==='racks'?byId.get(row.rackId).row:null,units=rack?number(rack.units):rackUnits;
      reference(row.networkId,typed.networks,path+' networkId',false);
      if(!empty(row.hostedBy)){reference(row.hostedBy,typed.devices,path+' hostedBy',false);if(row.hostedBy===row.id)errors.push(path+' cannot host itself.');if(!empty(row.rackU))errors.push(path+' is hosted equipment and cannot also occupy rack units.');}
      if(!Number.isInteger(height)||height<1||height>units)errors.push(path+' height must be a positive integer within the rack height.');
      if(!empty(row.rackU)){
        const u=number(row.rackU);
        if(!Number.isInteger(u)||u<1||!Number.isInteger(height)||height<1||!Number.isInteger(units)||units<1||units>200||u+height-1>units)errors.push(path+' does not fit inside the rack.');
        else {for(let unit=u;unit<u+height;unit++){const key=(row.rackId||'legacy-rack')+':'+unit;if(occupied.has(key))errors.push('Rack overlap at U'+unit+': '+occupied.get(key)+' and '+display(row.id)+'.');else occupied.set(key,display(row.id));}}
      }
      if(!empty(row.panelImage)&&!(typeof row.panelImage==='string'&&/^data:image\/(?:png|jpeg|gif|webp|svg\+xml);base64,[a-z0-9+/]+={0,2}$/i.test(row.panelImage)&&row.panelImage.slice(row.panelImage.indexOf(',')+1).length%4===0))errors.push(path+' panelImage must be an embedded base64 image data URL.');
    });
    rows('networks').forEach(row=>{
      const path='Network '+display(row.id),vlan=number(row.vlan);
      if(!empty(row.vlan)&&(!Number.isInteger(vlan)||vlan<1||vlan>4094))errors.push(path+' VLAN must be empty or an integer from 1 to 4094.');
      if(!empty(row.cidr)){
        const cidr=typeof row.cidr==='string'?row.cidr:'',slash=cidr.lastIndexOf('/'),address=cidr.slice(0,slash),prefix=cidr.slice(slash+1),v6=address.includes(':');
        if(slash<0||!/^\d+$/.test(prefix)||Number(prefix)>(v6?128:32)||!(v6?ipv6(address):ipv4(address)))errors.push(path+' CIDR must be empty or valid CIDR notation.');
      }
    });
    rows('interfaces').forEach(row=>{const path='Interface '+display(row.id);reference(row.deviceId,typed.devices,path+' deviceId',true);reference(row.networkId,typed.networks,path+' networkId',false);});
    rows('services').forEach(row=>{const path='Service '+display(row.id);reference(row.deviceId,typed.devices,path+' deviceId',false);reference(row.networkId,typed.networks,path+' networkId',false);refList(row.dependsOn,typed.services,path+' dependsOn');});
    rows('identity').forEach(row=>{const path='Identity '+display(row.id);reference(row.serviceId,typed.services,path+' serviceId',false);string(row.implementation,path+' implementation',true);});
    rows('groups').forEach(row=>{const path='Group '+display(row.id);reference(row.identityId,typed.identity,path+' identityId',true);reference(row.parentId,typed.groups,path+' parentId',false);string(row.kind,path+' kind',true);if(typeof row.parentId==='string'&&byId.get(row.parentId)?.collection==='groups'&&byId.get(row.parentId).row.identityId!==row.identityId)errors.push(path+' parent must belong to the same identity.');refList(row.memberIds,new Set([...typed.groups,...typed.devices,...typed.services,...typed.principals]),path+' memberIds');refList(row.accessIds,typed.services,path+' accessIds');});
    rows('dnsZones').forEach(row=>{const path='DNS zone '+display(row.id);reference(row.serviceId,typed.services,path+' serviceId',false);string(row.kind,path+' kind',true);});
    rows('dnsRecords').forEach(row=>{const path='DNS record '+display(row.id);reference(row.zoneId,typed.dnsZones,path+' zoneId',true);reference(row.targetId,new Set([...typed.devices,...typed.services,...typed.dnsRecords,...typed.endpoints]),path+' targetId',false);if(!empty(row.targetId)&&row.targetId===row.id)errors.push(path+' cannot target itself.');string(row.type,path+' type',true);if(!empty(row.ttl)&&(!Number.isInteger(number(row.ttl))||number(row.ttl)<0))errors.push(path+' ttl must be blank or a nonnegative integer.');});
    rows('relationships').forEach(row=>{const path='Relationship '+display(row.id);reference(row.from,logicalNodes,path+' from',true);reference(row.to,logicalNodes,path+' to',true);if(!['authenticates','resolves','uses-license','hosts','forwards','depends','access'].includes(row.kind))errors.push(path+' kind is not supported.');if(row.from===row.to)errors.push(path+' cannot refer to itself.');});
    rows('links').forEach(row=>{const path='Link '+display(row.id);reference(row.from,nodes,path+' from',true);reference(row.to,nodes,path+' to',true);if(row.from===row.to)errors.push(path+' cannot connect an item to itself.');['from','to'].forEach(end=>{const interfaceId=row[end+'InterfaceId'];reference(interfaceId,typed.interfaces,path+' '+end+'InterfaceId',false);if(!empty(interfaceId)&&typeof interfaceId==='string'&&byId.get(interfaceId)?.collection==='interfaces'&&byId.get(interfaceId).row.deviceId!==row[end])errors.push(path+' '+end+' interface does not belong to the '+end+' device.');});if(!empty(row.fromInterfaceId)&&row.fromInterfaceId===row.toInterfaceId)errors.push(path+' cannot connect an interface to itself.');});
    rows('interfaces').forEach(row=>{const aggregate=byId.get(row.aggregateId);if(aggregate?.collection==='interfaces'){if(aggregate.row.deviceId!==row.deviceId)errors.push('Interface '+display(row.id)+' aggregate must belong to the same device.');if(aggregate.row.mode!=='Bond')errors.push('Interface '+display(row.id)+' aggregate must reference an interface in Bond mode.');}});
    rows('directoryObjects').forEach(row=>{const parent=byId.get(row.parentId);if(parent?.collection==='directoryObjects'&&parent.row.identityId!==row.identityId)errors.push('Directory container '+display(row.id)+' parent must belong to the same identity.');});
    rows('principals').forEach(row=>{const container=byId.get(row.containerId);if(container?.collection==='directoryObjects'&&container.row.identityId!==row.identityId)errors.push('Principal '+display(row.id)+' container must belong to the same identity.');});
    rows('groups').forEach(row=>{const container=byId.get(row.containerId);if(container?.collection==='directoryObjects'&&container.row.identityId!==row.identityId)errors.push('Group '+display(row.id)+' container must belong to the same identity.');if(Array.isArray(row.memberIds))row.memberIds.forEach(key=>{const member=byId.get(key);if(member&&['groups','principals'].includes(member.collection)&&member.row.identityId!==row.identityId)errors.push('Group '+display(row.id)+' members must belong to the same identity.');});});
    rows('endpoints').forEach(row=>{
      const instance=byId.get(row.instanceId),port=byId.get(row.interfaceId),path='Endpoint '+display(row.id);
      if(instance?.collection==='serviceInstances'&&instance.row.serviceId!==row.serviceId)errors.push(path+' instance must provide its service.');
      if(instance?.collection==='serviceInstances'&&port?.collection==='interfaces'&&!empty(instance.row.deviceId)&&port.row.deviceId!==instance.row.deviceId)errors.push(path+' interface must belong to its instance device.');
      if(port?.collection==='interfaces'&&!empty(row.networkId)){const networks=[port.row.networkId,port.row.untaggedNetworkId,...(Array.isArray(port.row.taggedNetworkIds)?port.row.taggedNetworkIds:[])];if(networks.some(key=>!empty(key))&&!networks.includes(row.networkId))errors.push(path+' network must be carried by its interface.');}
    });
    rows('routes').forEach(row=>{const port=byId.get(row.interfaceId);if(port?.collection==='interfaces'&&port.row.deviceId!==row.deviceId)errors.push('Route '+display(row.id)+' interface must belong to its device.');});
    const sourceDevice=row=>{const source=byId.get(row.sourceId);if(!source)return '';if(source.collection==='devices')return source.row.id;if(source.collection==='serviceInstances')return source.row.deviceId;if(source.collection==='services')return source.row.deviceId;if(source.collection==='endpoints'){const port=byId.get(source.row.interfaceId),instance=byId.get(source.row.instanceId);return port?.row.deviceId||instance?.row.deviceId||'';}return '';};
    rows('flows').forEach(row=>{const port=byId.get(row.sourceInterfaceId),device=sourceDevice(row);if(port?.collection==='interfaces'&&device&&port.row.deviceId!==device)errors.push('Flow '+display(row.id)+' source interface must belong to its source device.');});
    rows('decisions').forEach(row=>{
      const path='Decision '+display(row.id);refList(row.relatedIds,entities,path+' relatedIds');
      if(!Array.isArray(row.options))errors.push(path+' options must be an array.');
      else {const optionIds=new Set();row.options.forEach((option,i)=>{if(!record(option)){errors.push(path+' option '+i+' must be an object.');return;}claim(option.id,path+' option ID');string(option.label,path+' option label',true);['pros','cons'].forEach(k=>{if(option[k]!==undefined)string(option[k],path+' option '+k,false);});if(typeof option.id==='string')optionIds.add(option.id);});reference(row.selectedOptionId,optionIds,path+' selectedOptionId',false);if(typeof row.status==='string'&&row.status.toLowerCase()==='decided'&&(!optionIds.has(row.selectedOptionId)||typeof row.rationale!=='string'||!row.rationale.trim()))errors.push(path+' marked Decided requires a valid selection and a nonblank rationale.');}
    });
    rows('tasks').forEach(row=>reference(row.relatedId,entities,'Task '+display(row.id)+' relatedId',false));
    rows('evidence').forEach(row=>{const path='Evidence '+display(row.id);reference(row.relatedId,entities,path+' relatedId',false);string(row.mime,path+' mime',true);string(row.data,path+' data',true);const match=typeof row.data==='string'&&/^data:(image\/(?:png|jpeg|gif|webp|svg\+xml)|application\/pdf);base64,([a-z0-9+/]+={0,2})$/i.exec(row.data);if(!match||match[2].length%4!==0||typeof row.mime!=='string'||match[1].toLowerCase()!==row.mime.toLowerCase())errors.push(path+' must contain an embedded base64 image or PDF data URL matching its MIME type.');});
    const commentEntities=new Set([...entities,...(typeof meta.id==='string'?[meta.id]:[]),'project']);
    rows('comments').forEach(row=>{const path='Comment '+display(row.id);reference(row.entityId,commentEntities,path+' entityId',true);string(row.author,path+' author',false);string(row.text,path+' text',true);if(typeof row.resolved!=='boolean')errors.push(path+' resolved must be boolean.');});
    rows('diagrams').forEach(row=>{const path='Diagram '+display(row.id);refList(row.nodeIds,logicalNodes,path+' nodeIds');if(row.layout!==undefined){if(!record(row.layout))errors.push(path+' layout must be an object.');else Object.entries(row.layout).forEach(([key,position])=>{if(!Array.isArray(row.nodeIds)||!row.nodeIds.includes(key))errors.push(path+' layout references an unselected node: '+key+'.');if(!record(position)||typeof position.x!=='number'||typeof position.y!=='number'||!Number.isFinite(position.x)||!Number.isFinite(position.y)||position.x<0||position.y<0||position.x>100000||position.y>100000)errors.push(path+' layout '+key+' requires numeric x/y from 0 to 100000.');});}});
    const cycle=(collection,targets,message)=>{const entries=rows(collection).filter(row=>typeof row.id==='string'),incoming=new Map(entries.map(row=>[row.id,0])),outgoing=new Map(entries.map(row=>[row.id,[]]));entries.forEach(row=>{targets(row).forEach(target=>{if(incoming.has(target)){incoming.set(target,incoming.get(target)+1);outgoing.get(row.id).push(target);}});});const queue=Array.from(incoming).filter(pair=>pair[1]===0).map(pair=>pair[0]);let cursor=0;while(cursor<queue.length){outgoing.get(queue[cursor++]).forEach(target=>{incoming.set(target,incoming.get(target)-1);if(incoming.get(target)===0)queue.push(target);});}if(cursor<incoming.size)errors.push(message);};
    cycle('devices',row=>typeof row.hostedBy==='string'?[row.hostedBy]:[],'Hosted equipment relationships contain a cycle.');
    cycle('services',row=>rows('serviceDependencies').filter(edge=>edge.kind==='Startup'&&edge.fromServiceId===row.id).map(edge=>edge.toServiceId),'Startup service dependencies contain a cycle.');
    cycle('directoryObjects',row=>typeof row.parentId==='string'?[row.parentId]:[],'Directory containment contains a cycle.');
    cycle('interfaces',row=>typeof row.aggregateId==='string'?[row.aggregateId]:[],'Interface aggregation contains a cycle.');
    cycle('dnsRecords',row=>typeof row.targetId==='string'?[row.targetId]:[],'DNS record targets contain a cycle.');
    const groupRows=rows('groups').filter(row=>typeof row.id==='string'),groupEdges=new Map(groupRows.map(row=>[row.id,[]])),groupIncoming=new Map(groupRows.map(row=>[row.id,0]));
    groupRows.forEach(row=>{if(typeof row.parentId==='string'&&groupEdges.has(row.parentId))groupEdges.get(row.parentId).push(row.id);if(Array.isArray(row.memberIds))row.memberIds.forEach(member=>{if(typeof member==='string'&&groupEdges.has(member))groupEdges.get(row.id).push(member);});});
    groupEdges.forEach(targets=>targets.forEach(target=>groupIncoming.set(target,groupIncoming.get(target)+1)));const groupQueue=Array.from(groupIncoming).filter(pair=>pair[1]===0).map(pair=>pair[0]);let groupCursor=0;while(groupCursor<groupQueue.length){groupEdges.get(groupQueue[groupCursor++]).forEach(target=>{groupIncoming.set(target,groupIncoming.get(target)-1);if(groupIncoming.get(target)===0)groupQueue.push(target);});}if(groupCursor<groupIncoming.size)errors.push('Group nesting/membership contains a cycle.');
    return errors;
  }
  function same(a,b){const stack=[[a,b]],visited=new WeakMap();while(stack.length){const [x,y]=stack.pop();if(x===y)continue;if(!x||!y||typeof x!=='object'||typeof y!=='object'||Array.isArray(x)!==Array.isArray(y))return false;let pairs=visited.get(x);if(pairs?.has(y))continue;if(!pairs){pairs=new WeakSet();visited.set(x,pairs);}pairs.add(y);const keys=Object.keys(x);if(keys.length!==Object.keys(y).length)return false;for(const key of keys){if(!Object.prototype.hasOwnProperty.call(y,key))return false;stack.push([x[key],y[key]]);}}return true;}
  function diff(a,b){
    const result=[],before=a||{},after=b||{};
    const fields=(x,y)=>Array.from(new Set([...Object.keys(x||{}),...Object.keys(y||{})])).filter(k=>!same(x&&x[k],y&&y[k]));
    const metaFields=fields(before.meta,after.meta);
    if(metaFields.length)result.push({collection:'meta',id:after.meta?.id||before.meta?.id||'project',name:after.meta?.name||before.meta?.name||'Project',change:'Modified',details:metaFields.join(', ')});
    COLLECTIONS.forEach(collection=>{
      const oldMap=new Map((Array.isArray(before[collection])?before[collection]:[]).filter(row=>record(row)&&typeof row.id==='string').map(row=>[row.id,row]));
      const newMap=new Map((Array.isArray(after[collection])?after[collection]:[]).filter(row=>record(row)&&typeof row.id==='string').map(row=>[row.id,row]));
      newMap.forEach((row,key)=>{const old=oldMap.get(key);if(!old)result.push({collection,id:key,name:label(row),change:'Added',details:'New record'});else {const changed=fields(old,row);if(changed.length)result.push({collection,id:key,name:label(row),change:'Modified',details:changed.join(', ')});}});
      oldMap.forEach((row,key)=>{if(!newMap.has(key))result.push({collection,id:key,name:label(row),change:'Removed',details:'Record removed'});});
    });
    return result;
  }
  function rackImport(raw,rackUnits){
    let value=raw;
    if(typeof value==='string'){try{value=JSON.parse(value);}catch(_){throw new Error('Rack import needs valid JSON. Paste an array or {rackU, layout, catalog}; JavaScript const source is not accepted.');}}
    const layout=Array.isArray(value)?value:record(value)&&value.layout;
    if(!Array.isArray(layout))throw new Error('Rack import needs a layout array.');
    const units=number(!empty(rackUnits)?rackUnits:record(value)&&!empty(value.rackU)?value.rackU:42),warnings=[],devices=[],reserved=new Set();
    const catalog=record(value)&&record(value.catalog)?value.catalog:{};
    if(record(value)&&value.catalog!==undefined&&!record(value.catalog))warnings.push('Ignored catalog: expected an object keyed by model.');
    if(!Number.isInteger(units)||units<1||units>200)throw new Error('Rack height must be an integer from 1 to 200U.');
    const lookup=model=>Object.prototype.hasOwnProperty.call(catalog,model)&&record(catalog[model])?catalog[model]:{};
    const text=(preferred,fallback)=>typeof preferred==='string'&&preferred.trim()?preferred:fallback;
    const unique=base=>{let key=base,suffix=2;if(['__proto__','constructor','prototype'].includes(key))key='rack-'+key;while(reserved.has(key))key=base+'-'+suffix++;if(key!==base)warnings.push('Source ID '+base+' renamed to '+key+'.');reserved.add(key);return key;};
    const metadata=(value,context)=>{if(empty(value))return {};if(!record(value)){warnings.push(context+': ignored metadata; expected an object.');return {};}try{return copy(value);}catch(error){warnings.push(context+': ignored metadata; '+error.message);return {};}};
    layout.forEach((entry,index)=>{
      if(!record(entry)||typeof entry.model!=='string'||!entry.model.trim()){warnings.push('Skipped rack row '+(index+1)+': missing model.');return;}
      const def=lookup(entry.model),known=entry.height??def.u??def.height;
      let height=number(known);if(!Number.isInteger(height)||height<1){height=1;warnings.push(entry.model+': unknown rack height; defaulted to 1U. Confirm before accepting.');}
      const u=number(entry.u),deviceId=unique(text(entry.id,'rack-'+(index+1)));
      if(!Number.isInteger(u)||u<1||u+height-1>units)warnings.push(entry.model+': rack placement does not fit '+units+'U; correct the unit or height.');
      const info=metadata(entry.info,entry.model);let notes='Imported Rack Studio model: '+entry.model;try{if(Object.keys(info).length)notes+='\n'+JSON.stringify(info,null,2);}catch(_){notes+='\nMetadata retained in sourceInfo.';}
      devices.push({id:deviceId,name:text(entry.label,text(def.label,entry.model)),type:text(def.kind,'Equipment'),owner:text(info.owner,''),status:'Proposed',networkId:'',rackU:Number.isFinite(u)?u:null,height,notes,model:entry.model,sourceInfo:info});
      if(!empty(entry.nodes)&&!Array.isArray(entry.nodes))warnings.push(entry.model+': ignored chassis nodes; expected an array.');
      (Array.isArray(entry.nodes)?entry.nodes:[]).forEach((child,bay)=>{
        if(empty(child))return;const childModel=typeof child==='string'?child:record(child)&&child.model;if(typeof childModel!=='string'||!childModel.trim()){warnings.push(entry.model+' bay '+(bay+1)+': missing child model.');return;}
        const childDef=lookup(childModel),childInfo=metadata(record(child)?child.info:undefined,childModel);
        let childNotes='Imported chassis bay '+(bay+1)+' on '+deviceId+'; model '+childModel;try{if(Object.keys(childInfo).length)childNotes+='\n'+JSON.stringify(childInfo,null,2);}catch(_){childNotes+='\nMetadata retained in sourceInfo.';}
        devices.push({id:unique(text(record(child)?child.id:undefined,deviceId+'-bay-'+(bay+1))),name:text(record(child)?child.label:undefined,text(childDef.label,childModel)),type:'Hosted equipment',owner:text(childInfo.owner,text(info.owner,'')),status:'Proposed',networkId:'',rackU:null,height:1,notes:childNotes,hostedBy:deviceId,model:childModel,sourceInfo:childInfo});
      });
    });
    const occupied=new Map();devices.filter(d=>!empty(d.rackU)).forEach(d=>{for(let u=d.rackU;Number.isInteger(u)&&u<d.rackU+d.height&&u<=units;u++){if(occupied.has(u))warnings.push('Rack overlap at U'+u+': '+occupied.get(u)+' and '+d.name+'.');else occupied.set(u,d.name);}});
    return {devices,warnings};
  }
  // Concurrency token only: sorted-key compact JSON, JS scalar serialization,
  // FNV-1a32 over each UTF-16 code unit (not UTF-8 bytes), eight lowercase hex digits.
  function fingerprint(model){const chunks=[],stack=[{value:model}],seen=new WeakSet();while(stack.length){const task=stack.pop();if(task.text!==undefined){chunks.push(task.text);continue;}const value=task.value;if(value&&typeof value==='object'){if(seen.has(value))throw new Error('Fingerprint requires JSON without shared/circular references.');seen.add(value);const array=Array.isArray(value),keys=array?Array.from({length:value.length},(_,i)=>String(i)):Object.keys(value).sort();chunks.push(array?'[':'{');stack.push({text:array?']':'}'});for(let i=keys.length-1;i>=0;i--){stack.push({value:value[keys[i]]});if(!array)stack.push({text:JSON.stringify(keys[i])+':'});if(i>0)stack.push({text:','});}}else{if(value===undefined||typeof value==='function'||typeof value==='symbol'||typeof value==='bigint'||typeof value==='number'&&!Number.isFinite(value))throw new Error('Fingerprint requires JSON values.');chunks.push(JSON.stringify(value));}}let hash=0x811c9dc5;for(const chunk of chunks){for(let i=0;i<chunk.length;i++){hash^=chunk.charCodeAt(i);hash=Math.imul(hash,0x01000193)>>>0;}}return 'ds1-'+hash.toString(16).padStart(8,'0');}
  function applyChanges(model,proposal){
    const currentErrors=validate(model);if(currentErrors.length)throw new Error('Current project is invalid:\n'+currentErrors.join('\n'));
    if(!record(proposal)||proposal.format!=='opsdeck-design-changes'||proposal.version!==1||typeof proposal.summary!=='string'||!Array.isArray(proposal.changes))throw new Error('Expected an opsdeck-design-changes version 1 proposal with summary and changes.');
    const scan=[proposal],seen=new WeakSet();while(scan.length){const item=scan.pop();if(!item||typeof item!=='object')continue;if(seen.has(item))throw new Error('Proposal must contain JSON without shared/circular references.');seen.add(item);for(const key of Object.keys(item)){if(['__proto__','constructor','prototype'].includes(key))throw new Error('Unsupported property key: '+key);if(item[key]&&typeof item[key]==='object')scan.push(item[key]);}}
    if(proposal.baseProjectId!==model.meta.id)throw new Error('Proposal project ID does not match this project.');
    if(proposal.baseFingerprint!==fingerprint(model))throw new Error('Proposal is stale: base fingerprint does not match the current project.');
    const next=migrate(model);
    proposal.changes.forEach((change,index)=>{if(!record(change))throw new Error('Change '+index+' must be an object.');if(change.op==='meta'){if(!record(change.values)||Object.prototype.hasOwnProperty.call(change.values,'id'))throw new Error('Metadata changes require values and cannot change meta.id.');Object.keys(change.values).forEach(key=>{next.meta[key]=copy(change.values[key]);});return;}if(!COLLECTIONS.includes(change.collection))throw new Error('Unknown collection at change '+index+'.');const rows=next[change.collection];if(change.op==='upsert'){if(!record(change.record)||typeof change.record.id!=='string'||!change.record.id.trim())throw new Error('Upsert requires a complete record with an ID.');const missing=REQUIRED[change.collection].split(' ').filter(key=>!Object.prototype.hasOwnProperty.call(change.record,key));if(missing.length)throw new Error('Upsert requires a complete '+change.collection+' record; missing '+missing.join(', ')+'.');const at=rows.findIndex(row=>row.id===change.record.id);if(at<0)rows.push(copy(change.record));else rows[at]=copy(change.record);}else if(change.op==='delete'){if(typeof change.id!=='string')throw new Error('Delete requires an ID.');const at=rows.findIndex(row=>row.id===change.id);if(at<0)throw new Error('Delete references an unknown ID: '+change.id);rows.splice(at,1);}else throw new Error('Unknown change operation at index '+index+'.');});
    const errors=validate(next);if(errors.length)throw new Error('Proposed project is invalid:\n'+errors.join('\n'));return next;
  }
  root.DS={seed,blank,migrate,validate,diff,rackImport,fingerprint,applyChanges,id,collections:COLLECTIONS.slice(),schema:ARCH_SCHEMA,requiredFields:{...REQUIRED},nodeCollections:NODE_COLLECTIONS.slice()};
  if(typeof module!=='undefined'&&module.exports)module.exports=root.DS;
})(typeof window!=='undefined'?window:globalThis);

