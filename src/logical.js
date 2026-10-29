(function(root){
'use strict';
const labels={identity:'Identity systems',groups:'Directory groups',directoryObjects:'Directory containers',principals:'Users & service principals',accessMappings:'Roles & permissions',dnsZones:'DNS zones',dnsRecords:'DNS records',relationships:'Logical relationships',services:'Service catalog',serviceInstances:'Service instances',endpoints:'Service endpoints',resolverAssignments:'Resolver assignments',serviceDependencies:'Typed dependencies',flows:'Communication flows'};
const columns={
  identity:[['name','Identity system'],['implementation','Implementation'],['domain','Domain'],['realm','Realm'],['serviceId','Provided by'],['status','Lifecycle']],
  groups:[['name','Group'],['identityId','Identity system'],['parentId','Parent group'],['kind','Group kind'],['status','Lifecycle']],
  dnsZones:[['name','DNS zone'],['serviceId','DNS service'],['kind','Zone kind'],['status','Lifecycle']],
  dnsRecords:[['name','Record'],['zoneId','Zone'],['type','Type'],['value','Value / answer'],['targetId','Resolves to'],['ttl','TTL'],['status','Lifecycle']],
  relationships:[['label','Relationship'],['from','From'],['kind','Meaning'],['to','To'],['protocol','Protocol'],['port','Port'],['status','Lifecycle']]
};
const endpointCollections=['devices','networks','services','identity','directoryObjects','groups','principals','dnsZones','dnsRecords','serviceInstances','endpoints'];
const rows=(m,col)=>Array.isArray(m[col])?m[col]:[];
const endpoints=m=>endpointCollections.flatMap(col=>rows(m,col).map(r=>({...r,_collection:col})));
const statuses=['Proposed','Approved','Installed','Verified','Operational','Retired'];
function defs(col,row,{f,model}){
  const m=typeof model==='function'?model():model, life=f('status','Lifecycle','select',{options:statuses}),notes=f('notes','Notes / design rationale','textarea',{full:true});
  const refs=(key,label,col,extra={})=>f(key,label,'ref',{rows:rows(m,col).filter(r=>r.id!==row.id),...extra});
  const choices=endpoints(m).filter(r=>r.id!==row.id);
  switch(col){
    case 'identity':return [f('name','Identity system name','text',{required:true,full:true}),refs('serviceId','Identity service','services'),f('implementation','Implementation','select',{options:['Undecided','Red Hat IdM','Microsoft Active Directory','Other / combined']}),f('domain','Domain name'),f('realm','Realm'),life,notes];
    case 'groups':return [f('name','Group name','text',{required:true,full:true}),refs('identityId','Identity system','identity',{required:true}),f('parentId','Parent group','ref',{rows:rows(m,'groups').filter(r=>r.id!==row.id&&r.identityId===row.identityId),hint:'A parent group describes group nesting. Directory containment is a separate container assignment. Save the identity assignment before choosing a new parent.'}),f('kind','Group kind','select',{options:[...new Set(['Security','Distribution','POSIX','Role','Other',...(['Organizational unit','OU','Container','Group'].includes(row.kind)?[row.kind]:[])])]}),life,f('memberIds','Group members','checks',{rows:choices.filter(r=>['groups','devices','services','principals'].includes(r._collection)),full:true,hint:'Entered groups, principals, computers, and services. This records membership and does not provision accounts.'}),f('accessIds','Legacy service access assignments','checks',{rows:rows(m,'services'),full:true,hint:'Retained for earlier designs. Use Roles & permissions to specify a role, resource, and permission separately from membership.'}),notes];
    case 'dnsZones':return [f('name','DNS zone name','text',{required:true,full:true}),refs('serviceId','DNS service','services'),f('kind','Zone kind','select',{options:['Forward','Reverse','Delegated','Other']}),life,notes];
    case 'dnsRecords':return [f('name','Record name','text',{required:true,full:true}),refs('zoneId','DNS zone','dnsZones',{required:true}),f('type','Record type','select',{options:['A','AAAA','CNAME','PTR','SRV','TXT','MX','NS','SOA','CAA','Other']}),f('value','Value / answer','text',{full:true,hint:'Enter the intended answer. No DNS query or configuration is performed.'}),f('targetId','Resolves to endpoint, device, service, or DNS record','ref',{rows:choices.filter(r=>['devices','services','dnsRecords','endpoints'].includes(r._collection))}),f('ttl','TTL (seconds)','number',{min:0,max:2147483647}),life,notes];
    case 'relationships':return [f('label','Relationship label','text',{required:true,full:true}),f('from','Source item','ref',{rows:choices,required:true}),f('to','Destination item','ref',{rows:choices,required:true}),f('kind','Relationship meaning','select',{options:['authenticates','resolves','uses-license','hosts','forwards','depends','access']}),f('protocol','Protocol'),f('port','Port / transport'),f('endpoint','Endpoint / URI','text',{full:true,hint:'Descriptive information only; the application does not contact this endpoint.'}),life,notes];
    default:return null;
  }
}
function draw(m,type,h){
  const {esc,svgStart,svgEnd}=h;
  const all=endpoints(m),byId=new Map(all.map(n=>[n.id,n]));
  const services=rows(m,'services'),identities=rows(m,'identity'),groups=rows(m,'groups'),zones=rows(m,'dnsZones'),records=rows(m,'dnsRecords'),relationships=rows(m,'relationships');
  const instances=rows(m,'serviceInstances'),serviceEndpoints=rows(m,'endpoints'),containers=rows(m,'directoryObjects'),principals=rows(m,'principals');
  const everyRecord=new Map(Object.values(m).filter(Array.isArray).flatMap(list=>list.filter(r=>r&&r.id).map(r=>[r.id,r])));
  const chosen=new Set(),edges=[],edgeKeys=new Set();
  const add=id=>{if(byId.has(id))chosen.add(id);};
  const connect=(from,to,label,kind='entered',recordId='')=>{if(!byId.has(from)||!byId.has(to)||from===to)return;const key=[from,to,label,recordId].join('|');if(edgeKeys.has(key))return;edgeKeys.add(key);edges.push({from,to,label,kind,recordId});};
  const isIdentity=r=>r&&(/identity|directory|active directory|\bidm\b|\bldap\b|\bkerberos\b/i.test([r.kind,r.name,r.platform].join(' '))||identities.some(i=>i.serviceId===r.id));
  const isDNS=r=>r&&(/\bdns\b|name service/i.test([r.kind,r.name,r.platform].join(' '))||zones.some(z=>z.serviceId===r.id));
  const isApp=r=>r&&(/application|license|licence|flexnet|matlab|ansys|jupyter|\bcad\b/i.test([r.kind,r.name,r.platform].join(' '))||!!r.licenseManager);
  identities.forEach(r=>connect(r.id,r.serviceId,'Identity provided by','identity',r.id));
  containers.forEach(r=>{connect(r.id,r.identityId,'In identity namespace','containment',r.id);connect(r.id,r.parentId,'Contained by','containment',r.id);});
  principals.forEach(r=>connect(r.id,r.identityId,'Principal in identity system','identity',r.id));
  groups.forEach(r=>{
    connect(r.id,r.identityId,'Group in identity system','identity',r.id);
    connect(r.id,r.parentId,'Nested in parent group','membership',r.id);
    connect(r.id,r.containerId,'Contained by directory object','containment',r.id);
    (r.memberIds||[]).forEach(id=>connect(id,r.id,'Member of group','membership',r.id));
    (r.accessIds||[]).forEach(id=>connect(r.id,id,'Legacy service access assignment','permission',r.id));
  });
  rows(m,'accessMappings').forEach(r=>connect(r.principalId,r.serviceId,'Permission: '+[r.role,r.permission,r.resource&&'resource '+r.resource].filter(Boolean).join(' / '),'permission',r.id));
  zones.forEach(r=>connect(r.id,r.serviceId,'Zone served by','dns',r.id));
  records.forEach(r=>{connect(r.id,r.zoneId,'Record in zone','dns',r.id);connect(r.id,r.targetId,'Resolves to','dns',r.id);});
  const explicitDeps=new Set(rows(m,'serviceDependencies').map(r=>JSON.stringify([r.fromServiceId,r.toServiceId])));
  rows(m,'serviceDependencies').forEach(r=>connect(r.fromServiceId,r.toServiceId,(r.kind||'Runtime')+' dependency / '+(r.requirement||'All'),'dependency',r.id));
  services.forEach(r=>{
    (r.dependsOn||[]).filter(id=>!explicitDeps.has(JSON.stringify([r.id,id]))).forEach(id=>connect(r.id,id,'Runtime dependency / All (legacy)','dependency',r.id));
    if(!instances.some(i=>i.serviceId===r.id))connect(r.id,r.deviceId,'Legacy service hosted on','hosting',r.id);
    if(byId.has(r.licenseManager))connect(r.id,r.licenseManager,'Uses license service','license',r.id);
    if(r.networkId)connect(r.id,r.networkId,'Service network','network',r.id);
  });
  instances.forEach(r=>{connect(r.serviceId,r.id,'Provided by instance','provider',r.id);connect(r.id,r.deviceId,'Instance runs on','hosting',r.id);connect(r.id,r.networkId,'Instance network','network',r.id);});
  serviceEndpoints.forEach(r=>{
    connect(r.id,r.serviceId,'Endpoint for service','provider',r.id);
    connect(r.id,r.instanceId,'Endpoint provided by instance','provider',r.id);
    const iface=everyRecord.get(r.interfaceId);
    if(iface){connect(r.id,iface.deviceId,'Bound to interface '+iface.name,'hosting',r.id);connect(r.id,iface.networkId,'Endpoint interface network','network',r.id);}
    else connect(r.id,r.networkId,'Endpoint network','network',r.id);
  });
  rows(m,'resolverAssignments').forEach(r=>(r.resolverEndpointIds||[]).forEach((id,i)=>connect(r.clientId,id,'Resolver priority '+(i+1)+(r.name?' · '+r.name:''),'resolver',r.id)));
  rows(m,'devices').forEach(r=>{connect(r.id,r.hostedBy,'Hosted on / VM host','hosting',r.id);connect(r.id,r.networkId,'Device network','network',r.id);});
  relationships.forEach(r=>{
    const detail=[r.label||r.kind,r.label&&r.kind&&r.label!==r.kind?r.kind:'',[r.protocol,r.port].filter(Boolean).join('/')].filter(Boolean).join(' · ');
    connect(r.from,r.to,detail,r.kind==='authenticates'?'authentication':r.kind==='resolves'||r.kind==='forwards'?'dns':r.kind==='uses-license'?'license':r.kind==='access'?'permission':'entered',r.id);
  });
  rows(m,'flows').forEach(r=>connect(r.sourceId,r.destinationId,[r.direction==='Bidirectional'?'Bidirectional flow':'Initiated flow',r.protocol||'protocol undecided',r.ports||'ports undecided',r.purpose].filter(Boolean).join(' · '),'flow',r.id));
  if(type==='identity'){
    [...identities,...groups,...containers,...principals,...services.filter(isIdentity)].forEach(r=>add(r.id));
  }else if(type==='dns'){
    [...zones,...records,...services.filter(isDNS)].forEach(r=>add(r.id));
    rows(m,'resolverAssignments').forEach(r=>{add(r.clientId);(r.resolverEndpointIds||[]).forEach(add);});
  }else if(type==='applications')services.filter(isApp).forEach(r=>add(r.id));
  else [...services,...identities,...groups,...containers,...principals,...zones,...records,...instances,...serviceEndpoints].forEach(r=>add(r.id));
  const allowed=edges.filter(e=>type==='identity'?!['dns','resolver','flow','license'].includes(e.kind):type==='dns'?!['containment','membership','permission','authentication','flow','license'].includes(e.kind):true);
  if(h.focusId&&byId.has(h.focusId)){chosen.clear();add(h.focusId);}
  // Hardware and network nodes are peripheral: a shared subnet or host must not
  // pull every unrelated application into a focused logical view.
  let frontier=new Set(chosen);
  for(let step=0;step<2&&frontier.size;step++){
    const next=new Set();allowed.forEach(e=>{
      if(frontier.has(e.from)&&(!['devices','networks'].includes(byId.get(e.from)._collection)||e.from===h.focusId)&&!chosen.has(e.to))next.add(e.to);
      if(frontier.has(e.to)&&(!['devices','networks'].includes(byId.get(e.to)._collection)||e.to===h.focusId)&&!chosen.has(e.from))next.add(e.from);
    });next.forEach(add);frontier=next;
  }
  edges.splice(0,edges.length,...allowed);
  const visible=all.filter(r=>chosen.has(r.id));
  const order=type==='identity'?['principals','directoryObjects','groups','identity','services','serviceInstances','endpoints','devices','networks','dnsZones','dnsRecords']:
    type==='dns'?['devices','services','serviceInstances','dnsZones','dnsRecords','endpoints','networks','identity','groups','directoryObjects','principals']:
    type==='applications'?['principals','groups','devices','services','serviceInstances','endpoints','identity','dnsZones','dnsRecords','directoryObjects','networks']:
    ['identity','directoryObjects','principals','groups','services','serviceInstances','endpoints','dnsZones','dnsRecords','devices','networks'];
  const active=order.filter(col=>visible.some(r=>r._collection===col)),gap=350,w=270,cardH=86,step=126,pad=28,top=72,pos=new Map();
  active.forEach((col,c)=>visible.filter(r=>r._collection===col).forEach((r,i)=>pos.set(r.id,{x:pad+c*gap,y:top+i*step,w,h:cardH})));
  const height=Math.max(360,...active.map(col=>visible.filter(r=>r._collection===col).length*step+100)),width=Math.max(760,active.length*gap+pad);
  const titles={logical:'Logical service overview',identity:'Identity, groups & access',dns:'DNS zones, records & resolution',applications:'Applications, licenses & dependencies'};
  let out=svgStart(width,height,titles[type]||titles.logical).replace('<svg ','<svg style="min-width:'+width+'px" ');
  out+='<text x="28" y="21" fill="#aec9c0" font-size="9" letter-spacing="1.1">'+esc((titles[type]||titles.logical).toUpperCase())+' · ENTERED DESIGN</text>';
  active.forEach((col,i)=>{out+='<text x="'+(pad+i*gap)+'" y="49" fill="#d7e8dd" font-size="11" font-weight="600">'+esc(({devices:'Equipment / clients',services:'Services / applications',identity:'Identity systems',groups:'Groups',directoryObjects:'Directory containers',principals:'Users / principals',serviceInstances:'Service instances',endpoints:'Service endpoints',dnsZones:'Zones',dnsRecords:'Records',networks:'Networks'})[col])+'</text>';});
  edges.filter(e=>pos.has(e.from)&&pos.has(e.to)).forEach((e,i)=>{
    const p=pos.get(e.from),q=pos.get(e.to),sameCol=p.x===q.x;
    const forward=q.x>p.x,sx=sameCol?p.x+p.w:p.x+(forward?p.w:0),sy=p.y+p.h/2,tx=sameCol?q.x+q.w:q.x+(forward?0:q.w),ty=q.y+q.h/2;
    const lane=sameCol?Math.max(sx,tx)+28+(i%4)*12:(sx+tx)/2;
    const path=sameCol?'M'+sx+','+sy+' C'+lane+','+sy+' '+lane+','+ty+' '+tx+','+ty:'M'+sx+','+sy+' C'+lane+','+sy+' '+lane+','+ty+' '+tx+','+ty;
    const color=({entered:'#e3bd81',permission:'#c7a2e8',dns:'#91bfe8',resolver:'#91bfe8',membership:'#b7ca91',containment:'#85b5ad',authentication:'#d6a8dc',flow:'#e7a99a',license:'#e3bd81'})[e.kind]||'#85b5ad',label=String(e.label||'Related'),short=label.length>43?label.slice(0,42)+'…':label;
    out+='<g'+(e.recordId?' data-id="'+esc(e.recordId)+'" tabindex="0" role="button" aria-label="Inspect relationship record '+esc(label)+'"':'')+'><title>'+esc(label)+'</title><path d="'+path+'" fill="none" stroke="'+color+'" stroke-width="1.4"'+(e.kind==='entered'?'':' stroke-dasharray="4 4"')+' marker-end="url(#arrow)"/><text x="'+(sameCol?lane+4:(sx+tx)/2)+'" y="'+((sy+ty)/2-7-(i%2)*10)+'" text-anchor="'+(sameCol?'start':'middle')+'" fill="'+color+'" font-size="8" paint-order="stroke" stroke="#142f38" stroke-width="3">'+esc(short)+'</text></g>';
  });
  visible.forEach(r=>{
    const p=pos.get(r.id),col=r._collection;
    const color=({identity:'#b7a6da',groups:'#b7ca91',directoryObjects:'#85b5ad',principals:'#b7a6da',serviceInstances:'#dfbb83',endpoints:'#91bfe8',dnsZones:'#8fc6c2',dnsRecords:'#a2bedf',services:'#dfbb83',devices:'#89afa4',networks:'#8fc6ac'})[col]||'#9cb8b0';
    const lines=col==='identity'?[r.implementation||'Implementation undecided',[r.domain&&'Domain '+r.domain,r.realm&&'Realm '+r.realm].filter(Boolean).join(' · ')||'Domain / realm undecided']:
      col==='groups'?[r.kind||'Group kind undecided',(r.memberIds||[]).length+' members · '+rows(m,'accessMappings').filter(a=>a.principalId===r.id).length+' permission mappings']:
      col==='directoryObjects'?[r.kind+' · organizational containment',r.parentId?'Parent: '+(byId.get(r.parentId)?.name||r.parentId):'Root directory object']:
      col==='principals'?[r.kind||'Principal kind undecided',r.nativeId||'Native directory identifier undecided']:
      col==='serviceInstances'?[r.role||'Instance role undecided','Host: '+(byId.get(r.deviceId)?.name||'unassigned')]:
      col==='endpoints'?[(everyRecord.get(r.interfaceId)?.address||r.address||r.dnsName||'Address undecided'),[r.protocol,r.port,r.role].filter(Boolean).join(' · ')||'Protocol / ports undecided']:
      col==='dnsZones'?[r.kind||'Zone kind undecided',r.serviceId?'Service: '+(byId.get(r.serviceId)?.name||r.serviceId):'DNS service unassigned']:
      col==='dnsRecords'?[r.type+' '+(r.value||'Answer undecided'),r.ttl!==''&&r.ttl!==undefined?'TTL '+r.ttl+' seconds':'TTL undecided']:
      col==='services'?[[r.kind,r.platform].filter(Boolean).join(' · ')||'Platform undecided',[r.protocol,r.port,r.endpoint].filter(Boolean).join(' · ')||'Endpoint undecided']:
      col==='devices'?[r.type||'Equipment',r.owner||'Owner unassigned']:[r.cidr||'Addressing undecided',r.purpose||''];
    const shorten=(v,n=43)=>{const t=String(v||'');return t.length>n?t.slice(0,n-1)+'…':t;};
    out+='<g data-id="'+esc(r.id)+'" data-node="'+esc(r.id)+'" tabindex="0" role="button" aria-label="Inspect '+esc(r.name)+'"><title>'+esc([r.name,...lines,r.notes||''].join('\n'))+'</title><rect x="'+p.x+'" y="'+p.y+'" width="'+p.w+'" height="'+p.h+'" rx="6" fill="#203e47" stroke="'+color+'"/><rect x="'+p.x+'" y="'+(p.y+12)+'" width="3" height="22" fill="'+color+'"/><text x="'+(p.x+13)+'" y="'+(p.y+22)+'" fill="#f0f4e8" font-size="11" font-weight="600">'+esc(shorten(r.name,37))+'</text><text x="'+(p.x+13)+'" y="'+(p.y+41)+'" fill="#c0d0c8" font-size="8.5">'+esc(shorten(lines[0]))+'</text><text x="'+(p.x+13)+'" y="'+(p.y+57)+'" fill="#a9c3bb" font-size="8">'+esc(shorten(lines[1]))+'</text><text x="'+(p.x+13)+'" y="'+(p.y+74)+'" fill="'+color+'" font-size="8">'+esc(r.status||'Status not recorded')+'</text></g>';
  });
  if(!visible.length)out+='<text x="35" y="140" fill="#d4e3d7" font-size="15">'+esc(type==='applications'?'Add a service with kind Application or License manager to begin.':'Add identity systems, DNS zones, or services to begin this view.')+'</text><text x="35" y="165" fill="#a9c2b7" font-size="11">Use the editors above. Keep unknown details explicit.</text>';
  return out+svgEnd();
}
function render(m,h,view='logical'){
  const {header,diagramPanel,esc}=h,type=['logical','identity','dns','applications'].includes(view)?view:'logical';
  const tabs=[['logical','Overview'],['identity','Directory & groups'],['dns','DNS'],['applications','Applications & licenses']];
  const descriptions={logical:'Follow service capabilities through instances, endpoints, hosts, DNS, identity, permissions, and typed dependencies. Every view uses the same linked records.',identity:'Keep directory containment, group nesting, principal membership, and application permissions separate. Provider selection and supported concepts remain explicit design decisions.',dns:'Follow clients through ordered resolver assignments, DNS providers, zones, aliases, and linked endpoint targets. Addresses follow referenced interfaces.',applications:'Follow application and license consumers through endpoints, service instances, hosting, identity, and Startup, Runtime, Optional, or Fallback dependencies.'};
  let html=header('Logical service design',descriptions[type]);
  html+='<div class="sectionbar"><div class="tabs">'+tabs.map(([key,label])=>'<button data-action="logical-view" data-view="'+key+'" class="'+(key===type?'active':'')+'">'+esc(label)+'</button>').join('')+'</div><button data-action="edit" data-col="relationships" class="small">+ Logical relationship</button></div>';
  const controls=type==='identity'?['identity','directoryObjects','principals','groups','accessMappings','relationships']:type==='dns'?['dnsZones','dnsRecords','serviceInstances','endpoints','resolverAssignments','relationships']:type==='applications'?['services','serviceInstances','endpoints','serviceDependencies','flows','accessMappings','relationships']:['services','serviceInstances','endpoints','serviceDependencies','identity','dnsZones','resolverAssignments'];
  html+='<div class="filterbar"><div class="actions">'+controls.map(col=>'<button data-action="navigate" data-page="'+col+'" class="small">'+esc(labels[col]||(col==='services'?'Services':col))+' ('+rows(m,col).length+')</button>').join('')+'</div><label style="font-size:11px">Focus <select id="logical-focus" aria-label="Focus logical view" style="max-width:260px;padding:7px;border:1px solid #cad7cd;border-radius:5px"><option value=""'+(!h.focusId?' selected':'')+'>All items</option>'+endpoints(m).map(r=>'<option value="'+esc(r.id)+'"'+(h.focusId===r.id?' selected':'')+'>'+esc(r.name)+' · '+esc(labels[r._collection]||r._collection)+'</option>').join('')+'</select></label></div>';
  html+=diagramPanel(type);
  html+='<div class="inline-note">Focus shows the selected item and up to two logical relationship steps; hardware and networks remain peripheral. Arrows follow each label: contained by, member of, permission, resolves to, provided by, or typed dependency. Purple = permissions, blue = DNS/resolvers, green = membership, amber = entered relationships. Select a record or labeled edge to inspect its source record. Resolver priority follows the entered list order. These are entered design facts; no service is contacted, configured, or verified.</div>';
  const relevant=type==='identity'?rows(m,'identity'):type==='dns'?rows(m,'dnsZones'):type==='applications'?rows(m,'services').filter(r=>/application|license|licence/i.test([r.kind,r.name,r.platform].join(' '))||r.licenseManager):rows(m,'services');
  if(relevant.length)html+='<section class="panel" style="margin-top:18px"><div class="panel-head"><h2>Inspect the design details</h2></div><div class="panel-body"><div class="actions">'+relevant.map(r=>'<button data-action="inspect" data-id="'+esc(r.id)+'" class="small">'+esc(r.name)+'</button>').join('')+'</div></div></section>';
  return html;
}
root.LS={labels,columns,defs,draw,render};
if(typeof module!=='undefined'&&module.exports)module.exports=root.LS;
})(typeof window!=='undefined'?window:globalThis);

