const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const {parseHTML}=require('linkedom');
const filename=require('node:path').join(__dirname,'../design-studio/index.html');
const source=fs.readFileSync(filename,'utf8');
const downloadSinks=new WeakMap();
function load(html=source,storage=new Map()){
  const {window,document}=parseHTML(html),errors=[],downloads=[];
  window.print=()=>{};
  const localStorage={getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)};
  const dialog=document.querySelector('#modal');dialog.showModal=()=>{dialog.open=true;dialog.setAttribute('open','')};dialog.close=()=>{dialog.open=false;dialog.removeAttribute('open')};
  window.HTMLElement.prototype.scrollIntoView=function(){};window.HTMLElement.prototype.focus=function(){};
  downloadSinks.set(document,downloads);window.HTMLAnchorElement.prototype.click=function(){downloadSinks.get(this.ownerDocument).push({name:this.download,href:this.href})};
  const objects=new Map(),URLmock={createObjectURL:b=>{const key='blob:'+objects.size;objects.set(key,b);return key},revokeObjectURL:()=>{}};
  class FD{constructor(form){this.entries=[];for(const el of form.querySelectorAll('input,textarea,select')){if(!el.name||el.type==='checkbox'&&!el.checked)continue;let v=el.value;if(el.tagName==='SELECT')v=el.querySelector('option[selected]')?.getAttribute('value')??el.querySelector('option[selected]')?.textContent??el.querySelector('option')?.getAttribute('value')??el.querySelector('option')?.textContent??'';this.entries.push([el.name,v]);}}get(n){return this.entries.find(x=>x[0]===n)?.[1]??null}getAll(n){return this.entries.filter(x=>x[0]===n).map(x=>x[1])}}
  const c=vm.createContext({window,document,localStorage,console,Blob,URL:URLmock,DOMParser:window.DOMParser,XMLSerializer:class{serializeToString(el){return el.toString()}},FormData:FD,FileReader:class{},Date,JSON,Math,Map,Set,WeakMap,WeakSet,Number,String,Array,Object,Error,Uint8Array,crypto:require('node:crypto').webcrypto,setTimeout:()=>1,clearTimeout:()=>{},requestAnimationFrame:f=>f()});
  for(const script of document.querySelectorAll('script')){if(script.type&&script.type!=='text/javascript')continue;try{vm.runInContext(script.textContent,c);if(c.RACK)window.RACK=c.RACK;if(window.DS)c.DS=window.DS;for(const key of ['LS','AW','RACK','ANALYSIS'])if(window[key])c[key]=window[key];}catch(e){errors.push(e.stack);}}
  const click=async(selector)=>{const el=typeof selector==='string'?document.querySelector(selector):selector;assert(el,'missing '+selector);el.dispatchEvent(new window.Event('click',{bubbles:true}));await new Promise(setImmediate);};
  const submit=async(selector='#record-form')=>{document.querySelector(selector).dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));await new Promise(setImmediate);};
  const set=(name,value,form='#record-form')=>{const el=document.querySelector(form+' [name="'+name+'"]');assert(el,'missing form '+name);if(el.tagName==='SELECT'){for(const o of el.querySelectorAll('option')){o.removeAttribute('selected');if(o.getAttribute('value')===value||!o.hasAttribute('value')&&o.textContent===value)o.setAttribute('selected','');}}else el.value=value;};
  return {c,window,document,errors,downloads,objects,click,submit,set,storage,app:window.DesignStudio};
}

module.exports={load};
