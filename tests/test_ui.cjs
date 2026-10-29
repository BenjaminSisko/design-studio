/* Development-only DOM integration checks. No browser or network is used. */
const assert=require('node:assert/strict');
const {load}=require('./ui_harness.cjs');
const tick=()=>new Promise(setImmediate);
(async()=>{
 const t=load();assert.deepEqual(t.errors,[]);assert.equal(t.app.validate().length,0);
 const sample=t.app.getModel();
 for(const page of ['overview','architecture','devices','interfaces','networks','services','logical','workbench','decisions','evidence','tasks','comments','revisions','llm']){
  await t.click('[data-page="'+page+'"]');assert(t.document.querySelector('#main').textContent.length>150,page);
 }
 for(const view of ['topology','deployments','communication','checks','impact','assurance','baselines','handoff']){
  await t.click('[data-page="workbench"]');await t.click('[data-view="'+view+'"]');assert(t.document.querySelector('#main').textContent.length>100,view);
 }
 for(const col of t.c.DS.collections.filter(c=>c!=='comments')){
  await t.click('[data-action="add"]');const control=t.document.querySelector('#modal [data-col="'+col+'"]');if(!control)continue;
  await t.click(control);assert(t.document.querySelector('#record-form'),'form '+col);await t.click('#modal [data-action="close-modal"]');
 }
 // Render every built-in diagram and retain safe, finite SVG geometry.
 for(const kind of ['network','topology','rack','dependencies','deployments','logical','identity','dns','applications']){
  const svg=t.app.draw(kind);assert(svg.startsWith('<svg'),kind);assert(!/NaN|Infinity|undefined/.test(svg),kind+' finite');if(kind==='topology')for(const port of sample.interfaces)assert(svg.includes('data-id="'+port.id+'"'),'topology port '+port.id);
 }
 // The All racks selection renders each rack, and U drag uses the renderer's geometry.
 assert.equal((t.app.draw('rack').match(/data-rack-id=/g)||[]).length,sample.racks.length);
 const r=load(),rackModel=r.c.DS.blank('SAMPLE-Drag controller');rackModel.racks=[{id:'sample-ui-rack',name:'SAMPLE-20U rack',units:20,site:'',location:'',notes:'',status:'Proposed'}];rackModel.devices=[{id:'sample-ui-device',name:'SAMPLE-Drag device',type:'Server',owner:'',status:'Proposed',networkId:'',rackId:'sample-ui-rack',rackU:2,height:2,notes:''},{id:'sample-ui-blocker',name:'SAMPLE-Blocker',type:'Server',owner:'',status:'Proposed',networkId:'',rackId:'sample-ui-rack',rackU:6,height:1,notes:''}];r.app.loadProject(rackModel);await r.click('[data-page="architecture"]');await r.click('[data-diagram="rack"]');
 const move=async(delta)=>{const svg=r.document.querySelector('#diagram-canvas svg');svg.createSVGPoint=()=>({x:0,y:0,matrixTransform(){return{x:this.x,y:this.y}}});svg.getScreenCTM=()=>({inverse:()=>({})});svg.setPointerCapture=()=>{};const item=svg.querySelector('[data-equipment-id="sample-ui-device"]');for(const [type,y] of [['pointerdown',100],['pointermove',100-delta*26],['pointerup',100-delta*26]]){const event=new r.window.Event(type,{bubbles:true,cancelable:true});Object.assign(event,{clientX:10,clientY:y,pointerId:1});(type==='pointerdown'?item:svg).dispatchEvent(event);}await tick();};
 await move(1);assert.equal(r.app.getModel().devices[0].rackU,3);await move(3);assert.equal(r.app.getModel().devices[0].rackU,3);assert(/overlap/i.test(r.document.querySelector('#toast').textContent));
 // Add a route/context through the schema-driven form rather than fixture mutation.
 await t.click('[data-action="add"]');await t.click('#modal [data-col="vrfs"]');t.set('name','SAMPLE-Test VRF');await t.submit();assert(t.app.getModel().vrfs.some(r=>r.name==='SAMPLE-Test VRF'));
 // Catalog selection opens the shared device form, keeping its known height and model key.
 await t.click('[data-page="architecture"]');await t.click('[data-action="catalog"]');assert(t.document.querySelector('#modal').textContent.includes('5835'));
 const key='dell-poweredge-r750';t.document.querySelector('#catalog-search').value='PowerEdge R750';t.document.querySelector('#catalog-search').dispatchEvent(new t.window.Event('input',{bubbles:true}));await tick();await t.click('[data-model="'+key+'"]');
 t.set('name','SAMPLE-Catalog host');await t.submit();assert(!t.document.querySelector('#modal').open,t.document.querySelector('#form-error')?.textContent);
 let m=t.app.getModel(),device=m.devices.find(d=>d.name==='SAMPLE-Catalog host');assert(device);assert.equal(device.model,key);assert.equal(device.height,2);assert(t.app.draw('rack').includes(device.id));
 // A scenario is an independent model; baseline snapshots and earlier drafts survive changes/switches.
 await t.click('[data-page="workbench"]');await t.click('[data-view="baselines"]');await t.click('[data-action="baseline-capture"]');t.set('name','SAMPLE-Installed snapshot','#baseline-form');t.set('kind','installed','#baseline-form');await t.submit('#baseline-form');
 let project=t.app.getProject();assert(project.baselines.installed);assert(project.revisions.some(r=>r.id===project.baselines.installed));
 await t.click('[data-action="scenario-new"]');t.set('name','SAMPLE-Option B','#scenario-form');await t.submit('#scenario-form');const scenario=t.app.getWorkspace().activeScenarioId;assert.notEqual(scenario,'main');
 m=t.app.getModel();let proposal={format:'opsdeck-design-changes',version:1,baseProjectId:m.meta.id,baseFingerprint:t.c.DS.fingerprint(m),baseScenarioId:scenario,summary:'SAMPLE-Alternative DNS',changes:[{op:'upsert',collection:'services',record:{...m.services[0],platform:'SAMPLE-Option B platform'}}]};
 const before=JSON.stringify(m);t.app.previewProposal(proposal);assert.equal(JSON.stringify(t.app.getModel()),before);await t.click('[data-action="apply-proposal"]');assert.equal(t.app.getModel().services[0].platform,'SAMPLE-Option B platform');assert.throws(()=>t.app.previewProposal(proposal),/stale|changed|fingerprint/i);
 t.app.switchScenario('main');assert.equal(t.app.getModel().services[0].platform,sample.services[0].platform);assert.throws(()=>t.app.previewProposal({...proposal,baseFingerprint:t.c.DS.fingerprint(t.app.getModel())}),/scenario/i);const unscoped={...proposal,baseFingerprint:t.c.DS.fingerprint(t.app.getModel())};delete unscoped.baseScenarioId;assert.throws(()=>t.app.previewProposal(unscoped),/scenario/i);assert.throws(()=>t.app.previewProposal({...proposal,baseScenarioId:'',baseFingerprint:t.c.DS.fingerprint(t.app.getModel())}),/scenario/i);
 t.app.switchScenario(scenario);assert.equal(t.app.getModel().services[0].platform,'SAMPLE-Option B platform');assert(t.app.getProject().baselines.installed);
 // Preview is bound to its originating scenario even if both model fingerprints match.
 m=t.app.getModel();proposal={...proposal,baseFingerprint:t.c.DS.fingerprint(m),changes:[{op:'upsert',collection:'services',record:{...m.services[0],platform:'SAMPLE-Option C'}}]};t.app.previewProposal(proposal);t.app.switchScenario('main');await t.click('[data-page="llm"]'); // close removes pending preview; applying cannot use it.
 // Journey creates explicit requirements/flows/review policies and a test that has not run.
 await t.click('[data-page="workbench"]');await t.click('[data-action="journey"]');const old=t.app.getModel();t.set('name','SAMPLE-Engineering journey','#journey-form');t.set('sourceId',old.devices[0].id,'#journey-form');t.set('serviceId',old.services[0].id,'#journey-form');t.set('criteria','SAMPLE-Record the intended successful outcome.','#journey-form');await t.submit('#journey-form');
 m=t.app.getModel();const requirement=m.requirements.find(r=>r.name==='SAMPLE-Engineering journey');assert(requirement,t.document.querySelector('#form-error')?.textContent);assert(m.verificationTests.some(r=>r.requirementIds.includes(requirement.id)&&r.result==='Not run'));assert(m.flows.some(r=>r.requirementIds.includes(requirement.id)));assert(m.policies.some(r=>r.name.startsWith(requirement.name)&&r.action==='Review'));
 // Trace and failure forms produce analysis without mutating any design record.
 const unchanged=JSON.stringify(m);await t.click('[data-view="topology"]');t.set('sourceId',m.devices[0].id,'#trace-form');t.set('destinationId',m.services[0].id,'#trace-form');await t.submit('#trace-form');assert(t.document.querySelector('.path-steps'));await t.click('[data-view="impact"]');const checkbox=t.document.querySelector('#impact-form [name="failedIds"]');checkbox.checked=true;await t.submit('#impact-form');assert(t.document.querySelector('.impact-grid'));assert.equal(JSON.stringify(t.app.getModel()),unchanged);
 // All six reports are generated locally and carry usable content.
 await t.click('[data-view="handoff"]');for(const kind of ['handoff','addresses','ports','flows','build','requirements']){await t.click('[data-kind="'+kind+'"]');const last=t.downloads.at(-1);assert((await t.objects.get(last.href).text()).length>100,kind);}
 // Pooled evidence and local front panels survive scopes, exported HTML and JSON reload.
 const pixel='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';
 project=t.app.getProject();project.model.evidence.push({id:'SAMPLE-ui-evidence',name:'SAMPLE-Pixel',mime:'image/png',data:pixel,caption:'SAMPLE-Embedded image',relatedId:project.model.devices[0].id,createdAt:new Date().toISOString()});project.model.devices[0].panelImage=pixel;t.app.loadProject(project);project=t.app.getProject();assert.equal(Object.keys(project.assets).length,1);assert.equal(project.model.devices[0].panelImage,'@asset:image-1');assert.equal(t.app.getModel().devices[0].panelImage,pixel);
 t.app.exportHTML();const last=t.downloads.at(-1),html=await t.objects.get(last.href).text();assert(html.includes('id="third-party-notices"'));const re=load(html);assert.deepEqual(re.errors,[]);assert.equal(re.app.validate().length,0);assert.equal(re.app.getModel().devices[0].panelImage,pixel);assert(re.app.getWorkspace().scenarios.length>1);assert(re.app.getProject().baselines.installed);
 // LLM context omits binaries, includes schema and precise scenario scope.
 await re.click('[data-page="llm"]');await re.click('[data-action="llm-context"]');const context=JSON.parse(await re.objects.get(re.downloads.at(-1).href).text());assert(context.architectureSchemas.endpoints);assert.equal(context.changeSetTemplate.baseScenarioId,re.app.getWorkspace().activeScenarioId);assert(!JSON.stringify(context.model).includes(pixel));
 await re.click('[data-page="overview"]');await re.click('[data-action="print"]');assert(re.document.querySelector('#printpack').textContent.includes('Baselines and acceptance tests'));for(const rack of re.c.RACK.racks(re.app.getModel()))assert(re.document.querySelector('#printpack').textContent.includes(rack.name));
 // Malformed workspace imports preserve the current working project.
 const invalid=re.app.getProject();invalid.baselines.installed='missing';assert.throws(()=>re.app.loadProject(invalid),/baseline|revision/i);assert.equal(re.app.validate().length,0);
 console.log('PASS: DOM integration — all views/forms/SVGs, catalog, scenarios/baselines, scoped LLM proposals, service journey, path/impact forms, six reports, pooled panel/evidence + portable HTML, safe context and invalid-import preservation.');
})().catch(error=>{console.error(error);process.exitCode=1});
