/* Entered-model architecture analysis. No network calls or live simulation. */
(function (root) {
  'use strict';
  const LIMIT = 'Entered model only; no live reachability, configuration, health, or failover verification.';
  const rows = (model,key) => Array.isArray(model[key]) ? model[key].filter(r=>r&&typeof r==='object'&&!Array.isArray(r)) : [];
  const index = model => Object.fromEntries(Object.values(model).filter(Array.isArray).flatMap(values=>values.filter(r=>r&&typeof r==='object'&&typeof r.id==='string').map(r=>[r.id,r])));
  const title = row => String(row.name||row.title||row.label||row.id||'Unspecified');
  const uniq = values => [...new Set(values.filter(Boolean))];
  function ip(value){
    const entered=String(value||'').trim().split('/');let text=entered[0],parts=[];if(entered.length>2||(entered.length===2&&(!/^\d+$/.test(entered[1])||Number(entered[1])>(text.includes(':')?128:32))))return null;
    if(/^\d{1,3}(\.\d{1,3}){3}$/.test(text)){
      if(text.split('.').some(p=>p.length>1&&p.startsWith('0')))return null;parts=text.split('.').map(Number);if(parts.some(p=>p>255))return null;
      return {version:4,n:parts.reduce((n,p)=>(n<<8n)+BigInt(p),0n),bits:32};
    }
    if(text.includes('.')){const last=text.lastIndexOf(':'),tail=ip(text.slice(last+1));if(last<0||!tail||tail.version!==4)return null;text=text.slice(0,last+1)+(tail.n>>16n).toString(16)+':'+(tail.n&65535n).toString(16);}
    if(!/^[0-9a-fA-F:]+$/.test(text))return null;
    const halves=text.split('::');if(halves.length>2)return null;
    let left=halves[0]?halves[0].split(':'):[],right=halves.length===2&&halves[1]?halves[1].split(':'):[];
    if(left.concat(right).some(p=>!/^\w{1,4}$/.test(p)||!/^[a-fA-F0-9]+$/.test(p)))return null;
    if(halves.length===1){if(left.length!==8)return null;parts=left;}else{if(left.length+right.length>=8)return null;parts=left.concat(Array(8-left.length-right.length).fill('0'),right);}
    return {version:6,n:parts.reduce((n,p)=>(n<<16n)+BigInt('0x'+p),0n),bits:128};
  }
  function subnet(value){const text=String(value||'').trim(),halves=text.split('/'),address=ip(halves[0]);if(halves.length!==2||!address||!/^\d+$/.test(halves[1]))return null;const prefix=Number(halves[1]);if(prefix>address.bits)return null;const shift=BigInt(address.bits-prefix);return {...address,n:(address.n>>shift)<<shift,prefix};}
  const contains=(network,address)=>!!(network&&address&&network.version===address.version&&(network.n>>BigInt(network.bits-network.prefix))===(address.n>>BigInt(network.bits-network.prefix)));
  const ipEqual=(a,b)=>!!(a&&b&&a.version===b.version&&a.n===b.n);
  const interfaceNetworks=i=>uniq([i.networkId,i.untaggedNetworkId,...(i.taggedNetworkIds||[])]);
  function interfaces(model,entityId,seen=new Set()){
    seen=new Set(seen);if(seen.has(entityId))return [];seen.add(entityId);
    const byId=index(model),entity=byId[entityId]||{};
    if(rows(model,'interfaces').some(r=>r.id===entityId))return [entity];
    if(entity.interfaceId)return interfaces(model,entity.interfaceId,seen);
    if(rows(model,'devices').some(r=>r.id===entityId)){const own=rows(model,'interfaces').filter(r=>r.deviceId===entityId);return own.length?own:interfaces(model,entity.hostedBy||'',seen);}
    let result=rows(model,'endpoints').filter(r=>r.serviceId===entityId||r.instanceId===entityId).flatMap(r=>interfaces(model,r.id,seen));
    if(entity.instanceId)result.push(...interfaces(model,entity.instanceId,seen));
    if(entity.deviceId)result.push(...interfaces(model,entity.deviceId,seen));
    rows(model,'serviceInstances').filter(r=>r.serviceId===entityId).forEach(r=>result.push(...interfaces(model,r.id,seen)));
    return [...new Map(result.map(r=>[r.id,r])).values()];
  }
  function networks(model,entityId){const byId=index(model),entity=byId[entityId]||{};return uniq([entity.networkId,...interfaces(model,entityId).flatMap(interfaceNetworks),(byId[entity.instanceId]||{}).networkId]);}
  const effectiveAddress=(model,entity)=>(index(model)[entity.interfaceId]||{}).address||entity.address||'';
  function equivalents(model,entityId){const e=index(model)[entityId]||{};return uniq([entityId,e.serviceId,e.instanceId,e.deviceId,...networks(model,entityId),...interfaces(model,entityId).flatMap(i=>[i.id,i.deviceId])]);}
  function zones(model,entityId){const byId=index(model);return uniq(networks(model,entityId).map(n=>(byId[n]||{}).zoneId));}
  function dependencies(model){const result=rows(model,'serviceDependencies').slice(),explicit=new Set(result.map(r=>JSON.stringify([r.fromServiceId,r.toServiceId])));rows(model,'services').forEach(s=>(s.dependsOn||[]).forEach(target=>{if(!explicit.has(JSON.stringify([s.id,target])))result.push({id:s.id+':legacy:'+target,name:'Legacy runtime dependency',fromServiceId:s.id,toServiceId:target,kind:'Runtime',requirement:'All'});}));return result;}
  function portRanges(value){const text=String(value||'').trim().toLowerCase();if(['*','any','all'].includes(text))return [[0,65535]];const result=[];for(const token of text.split(/[,;\s]+/)){if(!token)continue;const match=token.match(/^(\d+)(?:-(\d+))?$/);if(!match)return null;const low=Number(match[1]),high=Number(match[2]||match[1]);if(low>high||high>65535)return null;result.push([low,high]);}return result.length?result:null;}
  function portsCovered(flow,policy){const wanted=portRanges(flow),allowed=portRanges(policy);if(!wanted||!allowed)return null;allowed.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);for(const [low,high] of wanted){let cursor=low;for(const [start,end] of allowed){if(start<=cursor&&cursor<=end)cursor=end+1;if(cursor>high)break;}if(cursor<=high)return false;}return true;}
  const noPorts=protocol=>['icmp','icmpv6','ip','esp','ah'].includes(String(protocol||'').toLowerCase().trim());
  function policyState(model,flow){
    const source=flow.sourceId||'',destination=flow.destinationId||'',matched=[],uncertain=[];
    for(const policy of rows(model,'policies')){
      if((flow.policyIds||[]).length&&!flow.policyIds.includes(policy.id)&&policy.action!=='Deny')continue;
      let match=true,unknown=false;
      for(const [key,zoneKey,endpoint] of [['sourceIds','sourceZoneId',source],['destinationIds','destinationZoneId',destination]]){
        const ids=policy[key]||[],zone=policy[zoneKey]||'';
        if(ids.length&&!ids.some(id=>equivalents(model,endpoint).includes(id)))match=false;
        if(zone){const ez=zones(model,endpoint);if(ez.length&&!ez.includes(zone))match=false;else if(!ez.length)unknown=true;}
        if(!ids.length&&!zone)unknown=true;
      }
      const fp=String(flow.protocol||'').toLowerCase(),pp=String(policy.protocol||'').toLowerCase();
      if(!fp||!pp)unknown=true;else if(!['any','*','all'].includes(pp)&&fp!==pp)match=false;
      if(!noPorts(fp)){const covered=portsCovered(flow.ports||'',policy.ports||'');if(covered===false)match=false;else if(covered===null)unknown=true;}
      if(match)(unknown?uncertain:matched).push(policy);
    }
    const denied=matched.filter(p=>p.action==='Deny'),allowed=matched.filter(p=>p.action==='Allow'&&p.enforcementDeviceId&&p.owner);
    return {state:denied.length?'blocked':allowed.length?'documented':'unknown',policyIds:matched.map(p=>p.id),uncertainPolicyIds:uncertain.map(p=>p.id),reason:denied.length?'A matching entered Deny policy blocks this flow.':allowed.length?'A matching Allow policy, enforcement device, and owner are documented.':'No complete matching Allow policy is documented; unknown policy is not permission.'};
  }
  function testPasses(test,byId){return test.result==='Pass'&&['procedure','expectedResult','actualResult','performedBy','performedAt'].every(k=>test[k])&&(test.evidenceIds||[]).some(e=>byId[e]);}
  function failureDomains(model,entity){const byId=index(model),result=[],seen=new Set();let current=entity;while(current&&Object.keys(current).length&&!seen.has(current.id)){seen.add(current.id);result.push(...(current.failureDomainIds||[]));if(current.rackId)result.push(current.rackId);const host=current.deviceId||current.hostedBy;if(host)result.push(host);current=byId[host]||{};}return uniq(result);}
  function targetAddresses(model,targetId,seen=new Set()){seen=new Set(seen);if(seen.has(targetId))return [];seen.add(targetId);const target=index(model)[targetId]||{},values=[effectiveAddress(model,target),...interfaces(model,targetId).map(i=>i.address||'')];if(rows(model,'dnsRecords').some(r=>r.id===targetId)){values.push(target.value||'',...targetAddresses(model,target.targetId||'',seen));}return values;}
  function targetDNSName(model,targetId){const byId=index(model),target=byId[targetId]||{};if(target.dnsName)return target.dnsName;if(rows(model,'dnsRecords').some(r=>r.id===targetId)){const name=target.name||'',zone=(byId[target.zoneId]||{}).name||'';return name.includes('.')||!zone?name:name+'.'+zone;}return '';}
  function lint(model){
    const findings=[],byId=index(model),add=(code,severity,message,ids)=>findings.push({id:code+':'+uniq(ids).join(':'),severity,code,message,entityIds:uniq(ids)}),nets=rows(model,'networks');
    nets.forEach((network,a)=>{
      const cidr=subnet(network.cidr);if(!cidr)add('network-address-unknown','warning',title(network)+': subnet is missing or is not a CIDR.',[network.id]);
      if(network.gateway){const gateway=ip(network.gateway);if(!gateway)add('gateway-unknown','warning',title(network)+': gateway is not a parseable IP address.',[network.id]);else if(cidr&&!contains(cidr,gateway))add('gateway-outside-subnet','error',title(network)+': gateway is outside its subnet.',[network.id]);}
      nets.slice(a+1).forEach(other=>{const second=subnet(other.cidr);if((network.vrfId||'')===(other.vrfId||'')&&cidr&&second&&cidr.version===second.version&&(contains(cidr,second)||contains(second,cidr)))add('overlapping-subnets','error','Subnets overlap in the same routing context.',[network.id,other.id]);});
    });
    const addresses=new Map();
    rows(model,'interfaces').forEach(i=>{
      const address=ip(i.address),network=byId[i.networkId]||{},cidr=subnet(network.cidr);
      if(i.address&&!address)add('interface-address-unknown','warning',title(i)+': address contains unresolved or unparseable design text.',[i.id]);
      if(address){const key=(network.vrfId||'')+':'+address.version+':'+String(address.n);if(addresses.has(key))add('duplicate-address','error','Duplicate interface IP address in the same routing context.',[addresses.get(key),i.id]);else addresses.set(key,i.id);
        if(cidr&&!contains(cidr,address))add('address-outside-subnet','error',title(i)+': IP address is outside the associated subnet.',[i.id,network.id]);
        const gateway=ip(i.gateway||network.gateway);if(i.gateway&&!gateway)add('gateway-unknown','warning',title(i)+': gateway is unresolved design text.',[i.id]);if(gateway&&cidr&&!contains(cidr,gateway))add('gateway-outside-subnet','error',title(i)+': gateway is outside the associated subnet.',[i.id]);
      }
      if(i.mode==='Trunk'&&!interfaceNetworks(i).length)add('trunk-vlans-unknown','warning',title(i)+': trunk allowed networks are not entered.',[i.id]);
    });
    rows(model,'links').forEach(link=>{
      const ends=['from','to'].map(key=>byId[link[key+'InterfaceId']]);
      if(!ends.every(Boolean))add('cable-ports-unknown','info',title(link)+': select both interface records to analyze its physical path.',[link.id]);
      else [ends,ends.slice().reverse()].forEach(([a,b])=>{if(a.mode==='Trunk'){const missing=interfaceNetworks(b).filter(n=>!interfaceNetworks(a).includes(n));if(missing.length)add('trunk-vlan-missing','error','Connected interface networks are absent from the trunk allowed networks.',[link.id,a.id,b.id,...missing.sort()]);}});
    });
    rows(model,'endpoints').forEach(endpoint=>{const i=byId[endpoint.interfaceId]||{};if(endpoint.address&&i.address&&ip(endpoint.address)&&ip(i.address)&&!ipEqual(ip(endpoint.address),ip(i.address)))add('endpoint-address-mismatch','warning',title(endpoint)+': explicit address differs from its linked interface; document a VIP/translation or correct the address.',[endpoint.id,i.id]);if(!effectiveAddress(model,endpoint)&&!endpoint.dnsName)add('endpoint-address-unknown','warning',title(endpoint)+': neither an address nor a DNS name is documented.',[endpoint.id]);});
    rows(model,'dnsRecords').forEach(record=>{
      const target=byId[record.targetId]||{},known=targetAddresses(model,target.id||'').map(ip).filter(Boolean);
      if(['A','AAAA'].includes(String(record.type||'').toUpperCase())){const answer=ip(record.value);if(answer&&answer.version!==(String(record.type||'').toUpperCase()==='A'?4:6))add('dns-answer-family','error',title(record)+': answer address family does not match the record type.',[record.id]);if(answer&&known.length&&!known.some(a=>ipEqual(a,answer)))add('dns-target-mismatch','warning',title(record)+': entered answer differs from the linked target addresses.',[record.id,target.id]);if(!answer&&!known.length)add('dns-answer-unknown','warning',title(record)+': no parseable answer or linked target address is available.',[record.id,target.id]);}
      if(['CNAME','NS','PTR'].includes(String(record.type||'').toUpperCase())){const targetName=targetDNSName(model,target.id||'');if(!record.value&&!targetName)add('dns-target-name-unknown','warning',title(record)+': target DNS name is unresolved; inventory display names are not assumed to be DNS names.',[record.id]);if(record.value&&targetName&&record.value.replace(/\.$/,'').toLowerCase()!==targetName.replace(/\.$/,'').toLowerCase())add('dns-name-target-mismatch','warning',title(record)+': entered target name differs from the linked DNS name.',[record.id,target.id]);}
    });
    rows(model,'flows').forEach(flow=>{
      const missing=[];if(!flow.protocol)missing.push('protocol');if(!noPorts(flow.protocol)&&!flow.ports)missing.push('ports');if(!flow.purpose)missing.push('purpose');if(!(flow.requirementIds||[]).length)missing.push('requirement/acceptance criteria');if(missing.length)add('flow-details-unknown','warning',title(flow)+': document '+missing.join(', ')+'.',[flow.id]);
      const path=physicalPath(model,flow.sourceId||'',flow.destinationId||'',flow.sourceInterfaceId||'');if(path.state==='unknown')add('flow-route-unknown','warning',title(flow)+': '+(path.unknowns.join(' ')||path.label),[flow.id,...path.entityIds]);
      const state=policyState(model,flow);if(state.state!=='documented')add(state.state==='blocked'?'flow-denied':'flow-policy-unknown',state.state==='blocked'?'error':'warning',title(flow)+': '+state.reason,[flow.id,...state.policyIds]);
      const tests=rows(model,'verificationTests').filter(t=>(t.relatedIds||[]).includes(flow.id)||(t.requirementIds||[]).some(r=>(flow.requirementIds||[]).includes(r)));if(!tests.length)add('flow-verification-missing','warning',title(flow)+': no acceptance test is linked.',[flow.id]);
    });
    rows(model,'policies').forEach(p=>{const missing=['owner','enforcementDeviceId','ruleReference'].filter(k=>!p[k]);if(missing.length)add('policy-details-unknown','warning',title(p)+': document '+missing.join(', ')+'.',[p.id]);});
    rows(model,'identity').forEach(identity=>{
      if(['','undecided'].includes(String(identity.implementation||'').toLowerCase()))add('identity-provider-undecided','info',title(identity)+': provider capabilities remain an open decision.',[identity.id]);
      if(String(identity.implementation||'').toLowerCase().includes('idm'))rows(model,'directoryObjects').filter(o=>o.identityId===identity.id&&o.kind==='OU').forEach(o=>add('directory-capability-review','warning','Review the planned OU concept against the selected identity implementation and record the supported mapping.',[identity.id,o.id]));
    });
    rows(model,'groups').forEach(g=>{if(['ou','organizational unit','container'].includes(String(g.kind||'').toLowerCase()))add('legacy-directory-group','warning',title(g)+': model organizational containment as a directory object, separately from group membership.',[g.id]);});
    rows(model,'services').forEach(s=>{
      const instances=rows(model,'serviceInstances').filter(r=>r.serviceId===s.id);if(!instances.length&&!s.deviceId)add('service-host-unknown','warning',title(s)+': no instance or legacy host is documented.',[s.id]);if(String(s.kind||'').toLowerCase().includes('application')&&!dependencies(model).some(d=>d.fromServiceId===s.id)&&!rows(model,'relationships').some(r=>r.from===s.id))add('service-dependencies-unreviewed','info',title(s)+': dependencies are not recorded; confirm and document whether any are required.',[s.id]);if(!s.owner)add('owner-missing','warning',title(s)+': no operational owner is assigned.',[s.id]);
      instances.forEach((first,a)=>instances.slice(a+1).forEach(second=>{const shared=replicaDomains(model,first).filter(d=>replicaDomains(model,second).includes(d));if(shared.length)add('shared-failure-domain','warning','Service replicas share a host, switch, rack, or entered failure domain; record and verify the intended resilience.',[s.id,first.id,second.id,...shared.sort()]);}));
    });
    const tests=rows(model,'verificationTests');if(!rows(model,'requirements').length&&(rows(model,'services').length||rows(model,'devices').length))add('requirements-missing','warning','No requirements or acceptance criteria are recorded for this design.',[]);rows(model,'requirements').forEach(r=>{const related=tests.filter(t=>(t.requirementIds||[]).includes(r.id));if(!(r.relatedIds||[]).length||!r.acceptanceCriteria||!related.length)add('requirement-traceability-gap','warning',title(r)+': link design records, acceptance criteria, and a verification test.',[r.id]);if(['verified','accepted'].includes(String(r.status||'').toLowerCase())&&!related.some(t=>testPasses(t,byId)))add('verified-without-evidence','warning',title(r)+': verified/accepted status lacks a passing test with procedure, result, performer, time, and evidence.',[r.id]);});
    tests.forEach(t=>{if(t.result==='Pass'&&!testPasses(t,byId))add('passing-test-incomplete','warning',title(t)+': a Pass label alone is not recorded verification; complete procedure, expected/actual result, performer, time, and evidence.',[t.id]);});
    rows(model,'observations').forEach(o=>{if(!o.source||!o.observedAt||!o.observedBy||!(o.evidenceIds||[]).length)add('observation-evidence-missing','warning',title(o)+': record source, observer, time, and evidence for the as-built observation.',[o.id]);});
    return findings;
  }
  function replicaDomains(model,entity){const byId=index(model),result=failureDomains(model,entity),hostIds=new Set(result.concat(interfaces(model,entity.id||'').map(i=>i.deviceId)));rows(model,'links').forEach(link=>[['from','to'],['to','from']].forEach(([a,b])=>{const target=byId[link[b]]||{};if(hostIds.has(link[a])&&String(target.type||'').toLowerCase().includes('switch'))result.push(target.id);}));return uniq(result);}
  function routeFor(model,deviceId,target,outbound=null,vrfId=null){const candidates=rows(model,'routes').filter(r=>r.deviceId===deviceId&&contains(subnet(r.destination),target)&&(!outbound||r.interfaceId===outbound)&&(vrfId===null||(r.vrfId||'')===vrfId));candidates.sort((a,b)=>subnet(b.destination).prefix-subnet(a.destination).prefix||(a.metric||0)-(b.metric||0));return candidates[0]||null;}
  function physicalPath(model,sourceId,destinationId,sourceInterfaceId=''){
    const byId=index(model),starts=interfaces(model,sourceId).filter(i=>!sourceInterfaceId||i.id===sourceInterfaceId),targets=interfaces(model,destinationId);
    if(!starts.length||!targets.length)return {state:'unknown',label:'Endpoint interface/host mapping is incomplete.',entityIds:[],unknowns:['Select endpoint interfaces and document hosting before tracing a physical route.']};
    const graph=Object.fromEntries(rows(model,'interfaces').map(i=>[i.id,[]]));
    rows(model,'links').forEach(l=>{const a=l.fromInterfaceId,b=l.toInterfaceId;if(graph[a]&&graph[b]){graph[a].push([b,[l.id],'cable']);graph[b].push([a,[l.id],'cable']);}});
    rows(model,'devices').forEach(device=>{
      const own=rows(model,'interfaces').filter(i=>i.deviceId===device.id),role=(String(device.type||'')+' '+String(device.role||'')).toLowerCase();
      own.forEach(a=>own.forEach(b=>{if(a.id===b.id)return;const shared=interfaceNetworks(a).some(n=>interfaceNetworks(b).includes(n));if(['switch','bridge','router','firewall','gateway'].some(t=>role.includes(t))&&shared)graph[a.id].push([b.id,[device.id],'switch']);else if(['router','firewall','gateway'].some(t=>role.includes(t)))graph[a.id].push([b.id,[device.id],'route']);else if(a.aggregateId===b.id||b.aggregateId===a.id||(a.aggregateId&&a.aggregateId===b.aggregateId))graph[a.id].push([b.id,[device.id],'aggregate']);}));
    });
    const queue=starts.map(i=>[i.id,[i.id],[]]),visited=new Set(),targetIds=new Set(targets.map(i=>i.id));let found=null;
    while(queue.length){const [here,path,edges]=queue.shift();if(visited.has(here))continue;visited.add(here);if(targetIds.has(here)){found=[path,edges];break;}for(const [there,ids,kind] of graph[here]||[])if(!visited.has(there))queue.push([there,path.concat(there),edges.concat([[here,there,ids,kind]])]);}
    if(!found)for(const start of starts){for(const target of targets)if(start.deviceId===target.deviceId){found=[[start.id,target.id],[]];break;}}
    if(!found)return {state:'unknown',label:'No complete interface-and-cable path is documented.',entityIds:uniq(starts.concat(targets).map(i=>i.id)),unknowns:['Document cable ports, switch VLAN membership, and forwarding devices. Network membership alone does not establish a path.']};
    const [path,edges]=found,source=byId[path[0]],target=byId[path[path.length-1]],targetAddress=ip(effectiveAddress(model,byId[destinationId]||{}))||ip(target.address),unknowns=[];
    if(!interfaceNetworks(source).some(n=>interfaceNetworks(target).includes(n))){const network=byId[source.networkId]||{};if(!ip(source.gateway||network.gateway)&&!routeFor(model,source.deviceId,targetAddress))unknowns.push('The source has no documented gateway or route toward the destination network.');if(!edges.some(e=>e[3]==='route'))unknowns.push('The physical path has no documented routing transition between the endpoint networks.');}
    for(const [aId,bId,ids,kind] of edges)if(kind==='route'){const a=byId[aId],b=byId[bId],vrf=(byId[b.networkId]||{}).vrfId||'',targetNet=subnet((byId[b.networkId]||{}).cidr);if(!contains(targetNet,targetAddress)&&!routeFor(model,a.deviceId,targetAddress,bId,vrf))unknowns.push('Document a route on '+title(byId[a.deviceId]||{})+' using the entered outbound interface and routing context.');}
    if(edges.some(e=>e[3]==='route')){
      const sourceAddress=ip(effectiveAddress(model,byId[sourceId]||{}))||ip(source.address);
      for(const [origin,peer,peerAddress,direction] of [[source,target,targetAddress,'forward'],[target,source,sourceAddress,'return']]){
        const network=byId[origin.networkId]||{},route=routeFor(model,origin.deviceId,peerAddress,origin.id,network.vrfId||''),gateway=ip(origin.gateway||network.gateway||(route||{}).gateway);
        if(!gateway)unknowns.push('The '+direction+' path has no documented endpoint gateway/next hop.');else if(!path.some(p=>ipEqual(ip(byId[p].address),gateway)&&byId[p].deviceId!==origin.deviceId))unknowns.push('The '+direction+' gateway does not match a forwarding interface on the entered cable path.');
      }
      for(const [aId,bId,ids,kind] of edges.slice().reverse())if(kind==='route'){
        const a=byId[bId],b=byId[aId],vrf=(byId[b.networkId]||{}).vrfId||'',returnNet=subnet((byId[b.networkId]||{}).cidr);
        if(!contains(returnNet,sourceAddress)&&!routeFor(model,a.deviceId,sourceAddress,b.id,vrf))unknowns.push('Document a return route on '+title(byId[a.deviceId]||{})+' using the entered outbound interface and routing context.');
        if(((byId[a.networkId]||{}).vrfId||'')!==vrf)unknowns.push('The path crosses routing contexts; the route-leaking design is not established by interface connectivity.');
      }
    }
    return {state:unknowns.length?'unknown':'documented',label:'Entered interface/cable path: '+path.map(p=>title(byId[p])).join(' → '),entityIds:uniq(path.concat([source.deviceId,target.deviceId],edges.flatMap(e=>e[2]))),unknowns};
  }
  function trace(model,options={}){
    const byId=index(model);let flow=byId[options.flowId]||{},source=options.sourceId||flow.sourceId||'',destination=options.destinationId||flow.destinationId||'';
    if(!Object.keys(flow).length)flow=rows(model,'flows').find(f=>f.sourceId===source&&f.destinationId===destination)||{};
    const steps=[],unknowns=[],warnings=[],related=[source,destination],step=(kind,label,ids,state='documented')=>{steps.push({kind,label,entityIds:uniq(ids),state});related.push(...ids);};
    if(!byId[source]||!byId[destination])unknowns.push('Both source and destination must reference existing design records.');
    step('endpoint','Source: '+title(byId[source]||{})+'; destination: '+title(byId[destination]||{}),[source,destination],byId[source]&&byId[destination]?'documented':'unknown');
    [source,destination].forEach(eid=>{const hostIds=uniq(interfaces(model,eid).map(i=>i.deviceId));step('hosting',title(byId[eid]||{})+': '+(hostIds.map(h=>title(byId[h]||{})).join(', ')||'host mapping unresolved'),[eid,...hostIds],hostIds.length?'documented':'unknown');});
    const resolverRows=rows(model,'resolverAssignments').filter(r=>equivalents(model,source).includes(r.clientId));resolverRows.forEach(r=>step('dns','Configured resolver endpoints: '+((r.resolverEndpointIds||[]).map(e=>title(byId[e]||{})).join(', ')||'not entered'),[r.id,...(r.resolverEndpointIds||[])],(r.resolverEndpointIds||[]).length?'documented':'unknown'));
    const destinationEquiv=equivalents(model,destination),dnsRows=rows(model,'dnsRecords').filter(r=>destinationEquiv.includes(r.targetId));dnsRows.forEach(r=>step('dns',title(r)+' resolves to '+title(byId[r.targetId]||{}),[r.id,r.targetId]));
    if((dnsRows.length||(byId[destination]||{}).dnsName)&&!resolverRows.length)unknowns.push('Destination uses DNS but no resolver assignment is documented for the source.');
    rows(model,'relationships').filter(r=>uniq(equivalents(model,source).concat(destinationEquiv)).includes(r.from)&&['authenticates','uses-license','depends','resolves','forwards','access'].includes(r.kind)).forEach(r=>step('dependency',(r.kind||'')+': '+title(byId[r.from]||{})+' → '+title(byId[r.to]||{})+' (logical dependency; separate path required)',[r.id,r.from,r.to]));
    dependencies(model).filter(d=>destinationEquiv.includes(d.fromServiceId)).forEach(d=>step('dependency',(d.kind||'Runtime')+' / '+(d.requirement||'All')+': requires '+title(byId[d.toServiceId]||{})+' (logical dependency; separate path required)',[d.id,d.fromServiceId,d.toServiceId]));
    const networkIds=uniq(networks(model,source).concat(networks(model,destination)));step('network','Endpoint networks: '+(networkIds.map(n=>title(byId[n]||{})).join(', ')||'unresolved'),networkIds,networkIds.length?'documented':'unknown');
    let policy;if(!Object.keys(flow).length){unknowns.push('No communication flow records the initiator, protocol, ports, policy, and acceptance requirement for this pair.');policy={state:'unknown',policyIds:[],reason:'No communication flow is documented.'};}else{if(!flow.protocol||(!noPorts(flow.protocol)&&!flow.ports))unknowns.push('Flow protocol or transport ports remain unresolved.');policy=policyState(model,flow);related.push(flow.id);}
    step('enforcement',policy.reason,policy.policyIds.concat(flow.enforcementDeviceIds||[]),policy.state);if(policy.state==='unknown')unknowns.push(policy.reason);
    const path=physicalPath(model,source,destination,flow.sourceInterfaceId||'');step('physical-path',path.label,path.entityIds,path.state);unknowns.push(...path.unknowns);
    if(lint(model).some(f=>f.code==='trunk-vlan-missing'&&f.entityIds.some(id=>path.entityIds.includes(id)))){warnings.push('A modeled trunk is missing a connected VLAN; resolve the design error before accepting this path.');unknowns.push('VLAN continuity is inconsistent on the entered path.');}
    if(flow.id&&!rows(model,'verificationTests').some(t=>(t.relatedIds||[]).includes(flow.id)||(flow.requirementIds||[]).some(r=>(t.requirementIds||[]).includes(r))))warnings.push('No acceptance test is linked to this communication flow.');
    const state=policy.state==='blocked'?'blocked':unknowns.length||steps.some(s=>s.state==='unknown')?'unknown':'documented';
    return {status:state,summary:state==='blocked'?'Blocked by entered policy.':state==='documented'?'Design path is documented; this is not a live reachability result.':'The design contains unresolved path or policy information.',steps,unknowns:uniq(unknowns),warnings:uniq(warnings),relatedIds:uniq(related),modelOnly:true,limitations:LIMIT};
  }
  function impact(model,options={}){
    const byId=index(model),failed=uniq(options.failedIds||[]),lost=new Set(failed),degraded=new Set(),explanations=[],unknowns=[],explain=(entityId,cause,message)=>{const item={entityId,causeIds:uniq(cause),message};if(!explanations.some(e=>JSON.stringify(e)===JSON.stringify(item)))explanations.push(item);};
    failed.forEach(id=>{if(!byId[id])unknowns.push('Unknown failed record: '+id);});const instances=rows(model,'serviceInstances');
    for(let n=0;n<=Object.keys(byId).length;n++){const before=[...lost].sort().join('\n');for(const collection of ['devices','interfaces','serviceInstances','endpoints'])for(const e of rows(model,collection)){const causes=[e.hostedBy,e.deviceId,e.instanceId,e.interfaceId,e.networkId,...failureDomains(model,e)].filter(r=>lost.has(r));if(causes.length){lost.add(e.id);explain(e.id,causes,'Unavailable because an entered host, interface, network, or failure domain failed.');}}for(const instance of instances){const ownEndpoints=rows(model,'endpoints').filter(e=>e.instanceId===instance.id);if(ownEndpoints.length&&ownEndpoints.every(e=>lost.has(e.id))){lost.add(instance.id);explain(instance.id,ownEndpoints.map(e=>e.id),'All entered endpoints for this instance are unavailable.');}}if(before===[...lost].sort().join('\n'))break;}
    const adjacency={};rows(model,'links').forEach(l=>{if(byId[l.from]&&byId[l.to]){(adjacency[l.from]||=[]).push([l.to,l.id]);(adjacency[l.to]||=[]).push([l.from,l.id]);}});
    const queue=[],seen=new Set();failed.forEach(id=>{if(adjacency[id])queue.push(id);rows(model,'links').forEach(l=>{if([l.id,l.fromInterfaceId,l.toInterfaceId].includes(id))queue.push(l.from,l.to);});});
    while(queue.length){const here=queue.shift();if(seen.has(here))continue;seen.add(here);for(const [neighbor,linkId] of adjacency[here]||[]){if(!lost.has(neighbor)){degraded.add(neighbor);explain(neighbor,failed,'Entered cabling intersects the failure; connectivity or redundancy may be affected. Alternate paths require verification.');}const role=String((byId[neighbor]||{}).type||'').toLowerCase();if(['switch','router','firewall','gateway'].some(t=>role.includes(t))&&!seen.has(neighbor))queue.push(neighbor);}}
    instances.forEach(i=>{if(failureDomains(model,i).some(d=>degraded.has(d))||degraded.has(i.deviceId))degraded.add(i.id);});
    const state=Object.fromEntries(rows(model,'services').map(s=>[s.id,lost.has(s.id)?'affected':'available'])),deps=dependencies(model);
    for(let n=0;n<Object.keys(state).length*3+1;n++){
      const old=JSON.stringify(state);
      rows(model,'services').forEach(service=>{
        const sid=service.id;let next;
        if(failed.includes(sid))next='affected';else{
          const own=instances.filter(i=>i.serviceId===sid);
          if(own.length){const alive=own.filter(i=>!lost.has(i.id)),documented=alive.filter(i=>i.deviceId||interfaces(model,i.id).length);next=!alive.length?'affected':!documented.length?'unknown':alive.length<own.length||documented.length<alive.length||alive.some(i=>degraded.has(i.id))?'degraded':'available';if(!documented.length&&alive.length)unknowns.push(title(service)+': surviving instances have no host assignment, so availability is unresolved.');}
          else if(service.deviceId)next=lost.has(service.deviceId)?'affected':degraded.has(service.deviceId)?'degraded':'available';
          else if(interfaces(model,sid).some(i=>!lost.has(i.deviceId)))next=interfaces(model,sid).some(i=>degraded.has(i.deviceId))?'degraded':'available';else{next='unknown';unknowns.push(title(service)+': instance/host is undocumented, so direct availability cannot be determined.');}
          const serviceEndpoints=rows(model,'endpoints').filter(e=>e.serviceId===sid);if(!serviceEndpoints.length&&next!=='affected'){next='unknown';unknowns.push(title(service)+': no service endpoints are documented; surviving hosting does not establish availability to clients.');}if(serviceEndpoints.length&&serviceEndpoints.every(e=>lost.has(e.id))){next='affected';explain(sid,serviceEndpoints.map(e=>e.id),'All entered service endpoints are unavailable.');}
          const alternatives={};deps.filter(d=>d.fromServiceId===sid).forEach(dep=>{const target=state[dep.toServiceId]||'unknown';if(dep.kind==='Optional'){if(target!=='available'&&!['affected','unknown'].includes(next))next='degraded';}else if(dep.requirement==='Any'||dep.kind==='Fallback'){(alternatives[dep.kind||'Runtime']||=[]).push(dep);}else if(target==='affected'){next='affected';explain(sid,[dep.toServiceId],'Required '+(dep.kind||'Runtime')+' dependency is unavailable.');}else if(target==='unknown'&&next!=='affected')next='unknown';else if(target==='degraded'&&!['affected','unknown'].includes(next))next='degraded';});
          Object.values(alternatives).forEach(group=>{const states=group.map(d=>state[d.toServiceId]||'unknown');if(states.length&&states.every(s=>s==='affected')){next='affected';explain(sid,group.map(d=>d.toServiceId),'All entered alternative dependencies are unavailable.');}else if(!states.some(s=>['available','degraded'].includes(s))&&states.includes('unknown')&&next!=='affected')next='unknown';else if(states.some(s=>s!=='available')&&!['affected','unknown'].includes(next))next='degraded';});
        }state[sid]=next;
      });if(old===JSON.stringify(state))break;
    }
    Object.entries(state).forEach(([sid,value])=>{if(value==='affected')lost.add(sid);if(['degraded','unknown'].includes(value))degraded.add(sid);});lost.forEach(sid=>degraded.delete(sid));
    return {failedIds:failed,affectedIds:[...lost].sort(),degradedIds:[...degraded].sort(),unaffectedServiceIds:Object.keys(state).filter(s=>state[s]==='available').sort(),availableServiceIds:Object.keys(state).filter(s=>['available','degraded'].includes(state[s])).sort(),unknownServiceIds:Object.keys(state).filter(s=>state[s]==='unknown').sort(),serviceStates:state,explanations,unknowns:uniq(unknowns),modelOnly:true,limitations:LIMIT};
  }
  const md=value=>String(value===null||value===undefined||value===''?'Unspecified':value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('|','\\|').replace(/[\r\n]/g,' ');
  function table(headers,values){return '| '+headers.join(' | ')+' |\n| '+headers.map(()=>'---').join(' | ')+' |\n'+values.map(row=>'| '+row.map(md).join(' | ')+' |').join('\n')+'\n';}
  function csvReport(headers,values){const cell=value=>{let text=String(value===null||value===undefined?'':value);if(/^[=+@-]/.test(text.trimStart()))text="'"+text;return /[",\r\n]/.test(text)?'"'+text.replaceAll('"','""')+'"':text;};return [['Scope',...headers],...values.map(row=>[LIMIT,...row])].map(row=>row.map(cell).join(',')).join('\r\n')+'\r\n';}
  function report(model,options={}){
    const kind=options.kind||'handoff',byId=index(model),name=id=>id?title(byId[id]||{}):'Unspecified',names=ids=>ids.map(name).join('; ');
    if(kind==='addresses'){
      const values=rows(model,'interfaces').map(i=>{const network=byId[i.networkId]||{};return [name(i.deviceId),title(i),name(i.networkId),name(network.vrfId),i.address||'',i.gateway||network.gateway||'',i.mode||'',names(i.taggedNetworkIds||[]),''];});
      rows(model,'endpoints').forEach(e=>values.push([names(uniq(interfaces(model,e.id).map(i=>i.deviceId))),name(e.interfaceId),names(networks(model,e.id)),'',effectiveAddress(model,e),'','','',title(e)]));
      return csvReport(['Device','Interface','Network','Routing context','Address','Gateway','Mode','Tagged networks','Service endpoint'],values);
    }
    if(kind==='ports')return csvReport(['Connection','From device','From port','To device','To port','Status'],rows(model,'links').map(l=>[title(l),name(l.from),name(l.fromInterfaceId),name(l.to),name(l.toInterfaceId),l.status||'']));
    if(kind==='flows')return csvReport(['Flow','Initiator','Destination','Direction','Protocol','Ports','Purpose','Zones','Enforcement','Policies','Policy owner','Design policy state','Acceptance requirements'],rows(model,'flows').map(f=>{const state=policyState(model,f),policies=state.policyIds.map(p=>byId[p]||{});return [title(f),name(f.sourceId),name(f.destinationId),f.direction||'',f.protocol||'',f.ports||'',f.purpose||'',names(uniq([...zones(model,f.sourceId),...zones(model,f.destinationId),...(f.zoneIds||[])])),names(uniq([...(f.enforcementDeviceIds||[]),...policies.map(p=>p.enforcementDeviceId)])),names(state.policyIds),uniq(policies.map(p=>p.owner)).join('; '),state.state,names(f.requirementIds||[])];}));
    const meta=model.meta||{},heading='# '+md(meta.name||'Design')+' — '+({handoff:'Architecture handoff',build:'Build order',requirements:'Requirement traceability'}[kind]||kind)+'\n\n'+LIMIT+'\n\n';
    if(kind==='requirements')return heading+table(['Requirement','Owner','Design records','Decisions','Implementation tasks','Acceptance criteria','Tests','Evidence','Verification'],rows(model,'requirements').map(r=>{const linked=r.relatedIds||[],tasks=rows(model,'tasks').filter(t=>[r.id,...linked].includes(t.relatedId)||(t.requirementIds||[]).includes(r.id)),tests=rows(model,'verificationTests').filter(t=>(t.requirementIds||[]).includes(r.id));return [title(r),r.owner,names(linked),names(r.decisionIds||[]),tasks.map(t=>title(t)+': '+(t.status||'')).join('; '),r.acceptanceCriteria,tests.map(t=>title(t)+': '+(t.result||'Not run')).join('; '),names(uniq(tests.flatMap(t=>t.evidenceIds||[]))),tests.some(t=>testPasses(t,byId))?'Recorded pass with evidence':'Verification incomplete'];}))+'\nTask completion does not imply test success or verified implementation.\n';
    if(kind==='build'){
      const remaining=new Set(rows(model,'services').map(s=>s.id)),deps=dependencies(model).filter(d=>d.kind==='Startup'),complete=new Set(),stages=[];
      while(remaining.size){const ready=[...remaining].sort().filter(sid=>{const own=deps.filter(d=>d.fromServiceId===sid),allDeps=own.filter(d=>d.requirement!=='Any').map(d=>d.toServiceId),anyDeps=own.filter(d=>d.requirement==='Any').map(d=>d.toServiceId);return allDeps.every(d=>complete.has(d))&&(!anyDeps.length||anyDeps.some(d=>complete.has(d)));});if(!ready.length)break;stages.push(ready);ready.forEach(id=>{complete.add(id);remaining.delete(id);});}
      let body='Confirm rack/power, management access, interface addressing, cabling, and network policies before service acceptance. The order below uses entered Startup dependencies only; Runtime, Optional, and Fallback dependencies are not installation-order claims.\n\n'+stages.map((s,n)=>(n+1)+'. '+names(s)).join('\n')+'\n';if(remaining.size)body+='\nUnresolved startup cycle or missing prerequisite: '+names([...remaining].sort())+'\n';body+='\n'+table(['Task','Owner','Status','Related design'],rows(model,'tasks').map(t=>[title(t),t.owner,t.status,name(t.relatedId)]));return heading+body;
    }
    if(kind!=='handoff')throw new Error('Unknown report kind: '+String(kind));
    let body='## Design context\n\n'+md(meta.description||'')+'\n\nPhase: '+md(meta.phase||'')+'\n\n';
    body+='## Service catalog\n\n'+table(['Service','Owner','Instances / host','Endpoints','Dependencies'],rows(model,'services').map(s=>[title(s),s.owner,names(rows(model,'serviceInstances').filter(i=>i.serviceId===s.id).map(i=>i.id))||name(s.deviceId),names(rows(model,'endpoints').filter(e=>e.serviceId===s.id).map(e=>e.id)),dependencies(model).filter(d=>d.fromServiceId===s.id).map(d=>(d.kind||'Runtime')+'/'+(d.requirement||'All')+': '+name(d.toServiceId)).join('; ')]));
    body+='\n## Ownership\n\n'+table(['Record','Owner','Lifecycle'],['devices','networks','services','requirements'].flatMap(key=>rows(model,key).map(r=>[title(r),r.owner,r.status])));
    body+='\n## Decisions and open questions\n\n'+table(['Decision','Status','Owner','Alternatives','Rationale'],rows(model,'decisions').map(d=>[title(d),d.status,d.owner,(d.options||[]).map(title).join('; '),d.rationale]));
    body+='\n## Design checks\n\n'+table(['Severity','Check','Finding','Records'],lint(model).map(f=>[f.severity,f.code,f.message,names(f.entityIds)]));
    body+='\n'+report(model,{kind:'requirements'})+'\n'+report(model,{kind:'build'});return heading+body;
  }
  root.ANALYSIS={lint,trace,impact,report,policyState,effectiveAddress,limitations:LIMIT};
  if(typeof module!=='undefined'&&module.exports)module.exports=root.ANALYSIS;
})(typeof window!=='undefined'?window:globalThis);
