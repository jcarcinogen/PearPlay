// Actual popup + worker + Native, synthetic no-network native port.
// Fixture mirrors helper.Host's consume-on-pair and replace-on-pair_begin contract.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {createWorker} from '../../extension/worker.mjs';
import {Native} from '../../extension/native.mjs';
const source=readFileSync(new URL('../../extension/popup.js',import.meta.url),'utf8');
const html=readFileSync(new URL('../../extension/popup.html',import.meta.url),'utf8');
const turn=()=>new Promise(r=>setImmediate(r));
async function fixture(){
 const receiver='AA:BB:CC:DD:EE:01',other='AA:BB:CC:DD:EE:02';
 const receivers=[{identifier:receiver,address:'192.168.1.5',kind:'apple-tv',timingRequired:false}];
 let receive,openPair=false,success=false,blocked;
 const operations=[];
 const event=()=>({addListener(){},removeListener(){}});
 const port={onDisconnect:event(),onMessage:{addListener:fn=>{receive=fn}},disconnect(){},postMessage(m){
  operations.push(m.op); // Never retain or report PIN payloads.
  let error;
  if(m.op==='pair_begin')openPair=true;
  if(m.op==='pair'){error=!openPair?'pairing_required':success?null:'pairing_failed';openPair=false;}
  const reply=()=>receive({v:1,id:m.id,ok:!error,state:'idle',evidence:'none',capabilities:['hello','discover','start','status','stop','pair','pair_begin'],firewallSupport:false,...(m.op==='discover'?{receivers}:{}),...(error?{error}:{})});
  if(blocked?.op===m.op)blocked.reply=reply;else queueMicrotask(reply);
 }};
 const native=new Native(()=>port);
 const chrome={runtime:{getURL:p=>p,onMessage:event(),getPlatformInfo:async()=>({os:'mac'}),sendMessage:m=>worker.message(m,{url:'popup.html'})},permissions:{getAll:async()=>({origins:['http://*/*','https://*/*']}),onAdded:event(),onRemoved:event()},webRequest:{onBeforeRequest:event(),onResponseStarted:event()},webNavigation:{onCommitted:event(),onHistoryStateUpdated:event(),getAllFrames:async()=>[]},tabs:{get:async()=>({title:'Fixture page'}),query:async()=>[{id:1,url:'https://example.invalid/fixture'}],onRemoved:event()},alarms:{create(){},onAlarm:event()}};
 const worker=createWorker(chrome,native);
 async function mount(){
  const elements=new Map([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],{value:'',textContent:'',dataset:{},disabled:false,replaceChildren(){},append(){},addEventListener(){}}]));
  let tick;const events={};
  await vm.runInNewContext(source,{document:{visibilityState:'visible',getElementById:id=>elements.get(id),createElement:()=>({})},chrome,URL,setInterval:fn=>{tick=fn},clearInterval(){},addEventListener:(e,f)=>{events[e]=f}});
  return {el:id=>elements.get(id),click:id=>elements.get(id).onclick(),refresh:()=>tick(),close:()=>events.pagehide()};
 }
 await worker.message({op:'discover'},{url:'popup.html'});
 const p=await mount();native.state.error='pairing_required';await p.refresh();
 return {p,native,operations,mount,other,success:()=>{success=true},addReceiver:()=>native.state.receivers.push({...native.state.receivers[0],identifier:other}),hold:op=>{blocked={op};return()=>{const reply=blocked.reply;blocked=null;reply()}}};
}
async function submit(p){p.el('pin').value='0000';await p.click('pair');assert.equal(p.el('pin').value,'');}
test('failed PIN consumes session; repeated failure and explicit fresh retry succeed without auto-send',async()=>{
 const f=await fixture(),{p}=f;
 assert.equal(p.el('pairRestart').hidden,false);assert.equal(f.operations.includes('pair_begin'),false);
 for(let i=0;i<2;i++){
  await p.click('pairRestart');assert.equal(p.el('pairBox').hidden,false);
  await submit(p);assert.equal(f.native.view().error,'pairing_failed');
  assert.equal(p.el('pairBox').hidden,true);assert.equal(p.el('pairRestart').hidden,false);
  const count=f.operations.length;await p.click('pair');await p.refresh();await p.refresh();assert.equal(f.operations.length,count);
 }
 f.success();await p.click('pairRestart');await submit(p);
 assert.equal(f.native.view().error,null);assert.equal(p.el('start').hidden,false);
 assert.equal(f.operations.filter(op=>op==='pair_begin').length,3);assert.equal(f.operations.filter(op=>op==='pair').length,3);
 assert.equal(f.operations.includes('start'),false);
});
test('reopening after failure offers fresh pairing but never auto-begins',async()=>{
 const f=await fixture();await f.p.click('pairRestart');await submit(f.p);f.p.close();
 const before=f.operations.filter(op=>op==='pair_begin').length,p=await f.mount();
 assert.equal(p.el('pairRestart').hidden,false);assert.equal(p.el('pairBox').hidden,true);
 assert.equal(f.operations.filter(op=>op==='pair_begin').length,before);
 f.success();await p.click('pairRestart');await submit(p);assert.equal(f.native.view().error,null);
});
for(const op of ['pair_begin','pair'])test(`pending ${op} blocks actions and stale receiver result never opens PIN`,async()=>{
 const f=await fixture(),{p}=f;f.addReceiver();
 if(op==='pair')await p.click('pairRestart');
 const release=f.hold(op);p.el('pin').value='0000';
 const action=p.click(op==='pair'?'pair':'pairRestart');await turn();
 const count=f.operations.length;await p.click('pairRestart');await p.click('pair');await p.click('start');assert.equal(f.operations.length,count);
 p.el('receiver').value=f.other;const choice=p.el('receiver').onchange();
 release();await Promise.all([action,choice]);assert.equal(p.el('pairBox').hidden,true);assert.equal(p.el('pin').value,'');
 const begins=f.operations.filter(x=>x==='pair_begin').length;await p.refresh();assert.equal(f.operations.filter(x=>x==='pair_begin').length,begins);
});
test('closed pending begin drops completion and reopen requires a deliberate fresh begin',async()=>{
 const f=await fixture(),release=f.hold('pair_begin');const action=f.p.click('pairRestart');await turn();f.p.close();release();await action;
 assert.equal(f.p.el('pairBox').hidden,true);
 const p=await f.mount();assert.equal(p.el('pairBox').hidden,true);assert.equal(f.operations.filter(x=>x==='pair_begin').length,1);
});
