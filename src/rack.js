/* Rack Studio renderer integration.
 * Adapted from BenjaminSisko/rack-studio drawRack(), ports(), rackUnitRef(),
 * and chassis-bay rendering. The original U/rail/panel/image placement is kept
 * and now reads Design Studio's stable device records instead of LAYOUT.
 * No user layout, private network model, or runtime asset fetch is included.
 * Catalog/front-panel and MDI stencil provenance: THIRD_PARTY_NOTICES.md.
 */
const RACK = (()=>{
  'use strict';
  const U=26,RW=300,PADX=46,PADY=14;
  const palette={bg:'#0b0d12',ink:'#e6e9ef',muted:'#aab4c4',rail:'#2a2f3a',slot:'#1b1f27',slotalt:'#202531',accent:'#79c6f3',chassis:'#263041',node:'#1f2733',net:'#2d3a2d',patch:'#3a2f26',blank:'#191c23',server:'#2b2740',storage:'#26323a',pdu:'#3a2630',device:'#222630',port:'#5ec8ff',line:'#47536b'};
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
  const rows=(m,k)=>Array.isArray(m?.[k])?m[k]:[];
  const library=()=>globalThis.RACK_LIBRARY||{};
  const icons=()=>globalThis.RACK_STENCILS||{};
  const info=()=>globalThis.RACK_LIBRARY_INFO||{};
  const short=(s,n=35)=>String(s??'').length>n?String(s).slice(0,n-1)+'…':String(s??'');
  const safeImage=value=>typeof value==='string'&&/^data:image\/(?:png|jpeg|webp|gif);base64,[A-Za-z0-9+/]+={0,2}$/.test(value)?value:'';
  function describe(key){const item=library()[key];return item?{...item}:null;}
  function search(query='',limit=60){
    const words=String(query).toLowerCase().trim().split(/\s+/).filter(Boolean);
    const cap=Math.min(6000,Math.max(0,Number(limit)||60));
    return Object.entries(library()).filter(([key,v])=>{const hay=[key,v.mfr,v.label,v.kind,v.u+'u'].join(' ').toLowerCase();return words.every(q=>hay.includes(q));})
      .sort(([ka,a],[kb,b])=>Number(!!b.img)-Number(!!a.img)||String(a.mfr).localeCompare(String(b.mfr))||String(a.label).localeCompare(String(b.label))||ka.localeCompare(kb))
      .slice(0,cap).map(([key,v])=>({key,...v,hasImage:!!v.img}));
  }
  function racks(m){
    const entered=rows(m,'racks');
    return entered.length?entered:[{id:'',name:m?.meta?.rackName||'Infrastructure rack',units:Number(m?.meta?.rackUnits)||42}];
  }
  function definition(device){
    const entry=library()[device?.model]||{};
    let kind=entry.kind;
    if(!kind||kind==='device'){
      const type=String(device?.type||'').toLowerCase();
      if(/switch|router|firewall|network/.test(type))kind='net';
      else if(/storage|nas|san/.test(type))kind='storage';
      else if(/server|hypervisor|compute/.test(type))kind='server';
      else if(/chassis/.test(type))kind='chassis';
      else if(/patch/.test(type))kind='patch';
      else if(/power|pdu|ups/.test(type))kind='pdu';
    }
    return {...entry,kind:kind||'device',u:Math.max(1,Number(device?.height)||Number(entry.u)||1),label:device?.name||entry.label||'Equipment'};
  }
  function ports(x,y,w,n,max){
    let s='',show=Math.min(Number(n)||0,max),gap=w/(show+1);
    for(let i=0;i<show;i++)s+=`<rect x="${x+gap*(i+1)-3}" y="${y}" width="6" height="5" rx="1" fill="${palette.port}" opacity=".85"/>`;
    if(n>max)s+=`<text x="${x+w-2}" y="${y+11}" text-anchor="end" font-size="8" fill="${palette.port}">+${n-max}</text>`;
    return s;
  }
  const unitRef=(device,def)=>def.u<=1?`U${device.rackU}`:`U${device.rackU}–U${Number(device.rackU)+def.u-1}`;
  const title=(device,meta)=>`<title>${esc([device.name,meta,device.status,device.owner,device.notes].filter(Boolean).join('\n'))}</title>`;
  function panel(m,device,def,x,y,options){
    const h=def.u*U,children=rows(m,'devices').filter(d=>d.hostedBy===device.id);
    const image=options.photoreal===false?'':safeImage(device.panelImage)||safeImage(def.img);
    const chassis=def.kind==='chassis'&&(children.length||Number(def.bays)>0);
    const showImg=image&&!chassis;
    let s=`<g data-id="${esc(device.id)}" data-equipment-id="${esc(device.id)}" data-rack-u="${esc(device.rackU)}" data-unit-height="${U}" data-height-u="${def.u}" tabindex="0" role="button" aria-label="${esc(device.name+' '+unitRef(device,def))}">`;
    s+=title(device,unitRef(device,def)+(device.model?' · '+device.model:''));
    s+=`<rect x="${x+2}" y="${y+1}" width="${RW-4}" height="${h-2}" rx="3" fill="${showImg?'#0b0d12':palette[def.kind]||palette.device}" stroke="${palette.accent}" stroke-width="1" opacity=".97"/>`;
    if(showImg)s+=`<image href="${esc(image)}" x="${x+3}" y="${y+2}" width="${RW-6}" height="${h-4}" preserveAspectRatio="none" style="image-rendering:auto"/><rect x="${x+2}" y="${y+1}" width="${RW-4}" height="17" fill="#080a10" opacity=".72"/>`;
    s+=`<text x="${x+12}" y="${y+15}" font-size="10.5" fill="${palette.ink}" font-weight="600">${esc(short(device.name||def.label,31))}</text>`;
    if(!showImg&&h>U)s+=`<text x="${x+12}" y="${y+29}" font-size="8" fill="${palette.muted}">${esc(short(device.model||device.type||'Equipment',44))}</text>`;
    if(chassis&&h>U){
      const count=Math.max(Number(def.bays)||0,children.length,1),columns=Math.min(count,8),bands=Math.ceil(count/columns);
      const bw=(RW-24)/columns,bh=Math.max(10,(h-32)/bands);
      for(let b=0;b<count;b++){
        const child=children[b],bx=x+12+(b%columns)*bw,by=y+25+Math.floor(b/columns)*bh;
        if(child)s+=`<g data-id="${esc(child.id)}" data-equipment-id="${esc(child.id)}" role="button" tabindex="0" aria-label="${esc(child.name)}">${title(child,'Hosted by '+device.name+' · bay '+(b+1))}`;
        s+=`<rect x="${bx}" y="${by}" width="${bw-6}" height="${Math.max(5,bh-4)}" rx="2" fill="${child?palette.node:'transparent'}" stroke="${palette.line}" stroke-dasharray="${child?'0':'3 3'}"/>`;
        s+=`<text x="${bx+4}" y="${by+Math.min(12,bh-5)}" font-size="8" fill="${child?palette.ink:palette.muted}">${esc(child?short(child.name,Math.max(4,Math.floor(bw/5)-2)):'empty')}</text>`;
        if(child)s+='</g>';
      }
    }else if(!showImg&&def.ports)s+=ports(x+12,y+h-9,RW-24,def.ports,24);
    if(options.selectedId===device.id)s+=`<rect x="${x}" y="${y-1}" width="${RW}" height="${h+2}" rx="5" fill="none" stroke="${palette.accent}" stroke-width="2.4"/>`;
    s+='</g>';
    return s;
  }
  function draw(m,options={}){
    const allRacks=racks(m),selected=options.rackId===undefined||options.rackId===null||options.rackId==='*'?allRacks:allRacks.filter(r=>r.id===options.rackId);
    const shown=selected.length?selected:allRacks.slice(0,1),devices=rows(m,'devices');
    const firstId=allRacks[0]?.id||'',rackOf=d=>d.rackId||firstId;
    const rackWidth=RW+PADX+42,unitCounts=shown.map(r=>Math.max(1,Math.min(200,Number(r.units)||Number(m?.meta?.rackUnits)||42)));
    const rackHeight=Math.max(...unitCounts)*U+PADY*2+26;
    const hosted=devices.filter(d=>d.hostedBy&&devices.some(p=>p.id===d.hostedBy&&shown.some(r=>r.id===rackOf(p))));
    const unplaced=devices.filter(d=>!d.hostedBy&&(d.rackU===null||d.rackU===undefined||d.rackU===''||!allRacks.some(r=>r.id===rackOf(d))));
    const side=[...hosted,...unplaced],sideWidth=side.length?315:0,W=shown.length*rackWidth+sideWidth,H=Math.max(rackHeight,side.length*62+110);
    let s=`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" data-unit-height="${U}" role="img" aria-label="Rack Studio physical rack elevation" style="font-family:system-ui,sans-serif"><title>Rack Studio · ${esc(shown.map(r=>r.name).join(', '))}</title><desc>Front rack elevation generated from Design Studio equipment. U is the lowest occupied unit. Hosted and unplaced equipment appear alongside. Embedded front panels are offline assets.</desc><rect width="${W}" height="${H}" fill="${palette.bg}"/>`;
    shown.forEach((rack,index)=>{
      const rackU=unitCounts[index],ox=index*rackWidth,x=ox+PADX;
      s+=`<g data-rack-id="${esc(rack.id)}" data-unit-height="${U}" data-rack-units="${rackU}"><text x="${x}" y="15" font-size="11" font-weight="600" fill="${palette.ink}">${esc(short(rack.name||'Infrastructure rack',36))} · ${rackU}U</text>`;
      s+=`<text x="${x}" y="29" font-size="9" fill="${palette.muted}">${esc(short([rack.site,rack.location].filter(Boolean).join(' · '),46))}</text>`;
      for(let u=1;u<=rackU;u++){
        const y=PADY+22+(rackU-u)*U;
        s+=`<rect x="${x}" y="${y}" width="${RW}" height="${U}" fill="${u%2?palette.slot:palette.slotalt}" stroke="${palette.line}" stroke-width=".5"/><text x="${x-8}" y="${y+U/2+4}" text-anchor="end" font-size="9" fill="${palette.muted}">${u}</text><text x="${x+RW+8}" y="${y+U/2+4}" font-size="9" fill="${palette.muted}">${u}</text>`;
      }
      s+=`<rect x="${x-4}" y="${PADY+22}" width="4" height="${rackU*U}" fill="${palette.rail}"/><rect x="${x+RW}" y="${PADY+22}" width="4" height="${rackU*U}" fill="${palette.rail}"/>`;
      devices.filter(d=>!d.hostedBy&&rackOf(d)===rack.id&&d.rackU!==null&&d.rackU!==undefined&&d.rackU!=='').forEach(device=>{
        const def=definition(device),y=PADY+22+(rackU-Number(device.rackU))*U-(def.u-1)*U;
        s+=panel(m,device,def,x,y,options);
      });
      s+='</g>';
    });
    if(side.length){
      const x=shown.length*rackWidth+12;
      s+=`<text x="${x}" y="16" fill="${palette.ink}" font-size="11" font-weight="600">Hosted / unplaced equipment</text><text x="${x}" y="31" fill="${palette.muted}" font-size="9">Select a record to edit its linked design.</text>`;
      side.forEach((device,i)=>{
        const y=48+i*62,parent=devices.find(d=>d.id===device.hostedBy);
        s+=`<g data-id="${esc(device.id)}" data-equipment-id="${esc(device.id)}" tabindex="0" role="button" aria-label="${esc(device.name)}">${title(device,parent?'Hosted by '+parent.name:'Unplaced equipment')}<rect x="${x}" y="${y}" width="285" height="53" rx="5" fill="${palette.device}" stroke="${options.selectedId===device.id?palette.accent:palette.line}"/><svg x="${x+10}" y="${y+13}" width="25" height="25" viewBox="0 0 24 24" color="${palette.accent}">${stencil(device.type)}</svg><text x="${x+44}" y="${y+19}" fill="${palette.ink}" font-size="10.5">${esc(short(device.name,33))}</text><text x="${x+44}" y="${y+36}" fill="${palette.muted}" font-size="9">${esc(short(parent?'Hosted by '+parent.name:'Unplaced · '+(device.type||'Equipment'),40))}</text></g>`;
      });
    }
    return s+'</svg>';
  }
  function stencil(kind){
    const text=String(kind||'').toLowerCase();
    if(icons()[text])return icons()[text];
    const key=/firewall|security/.test(text)?'wall-fire':/switch|patch/.test(text)?'switch':/storage|nas|san/.test(text)?'nas':/workstation|client|test|instrument|desktop/.test(text)?'desktop-tower-monitor':/network|subnet|vlan/.test(text)?'lan':/router|gateway/.test(text)?'router-network':/database/.test(text)?'database-outline':/cloud|internet/.test(text)?'cloud-outline':/wifi|wireless/.test(text)?'wifi':/app|service|license/.test(text)?'web-box':'server';
    return icons()[key]||'<rect x="3" y="3" width="18" height="18" rx="2" fill="none" stroke="currentColor"/>';
  }
  return {catalog:library,search,describe,draw,racks,definition,safeImage,stencil,stencils:()=>Object.keys(icons()),libraryInfo:info};
})();
globalThis.RACK=RACK;
