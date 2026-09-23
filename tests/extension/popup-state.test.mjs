import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const source=await readFile(new URL('../../extension/popup.js',import.meta.url),'utf8');
const html=await readFile(new URL('../../extension/popup.html',import.meta.url),'utf8');
async function popup(overrides={}) {
  const elements=new Map([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],{value:'',textContent:'',disabled:false,dataset:{},replaceChildren(){},append(){},addEventListener(){}}]));
  const view={enabled:true,selected:'video',receiver:'tv',localAvailable:false,candidates:[{id:'video',label:'Example film',videoId:'element'}],native:{state:'idle',error:null,receivers:[{identifier:'tv',label:'Living Room'}],capabilities:['start','stop']},...overrides};
  let timer;const calls=[];let fail=false;let release;let hold=false;
  const chrome={tabs:{query:async()=>[{id:1,url:'https://example.test/watch'}]},permissions:{getAll:async()=>({origins:['http://*/*','https://*/*']})},runtime:{sendMessage:async m=>{calls.push(m);if(m.op==='view')return structuredClone(view);if(fail)throw Error('NATIVE_DISCONNECTED');if(hold)await new Promise(r=>{release=r});return m.op==='discover'?{receivers:view.native.receivers}:{ok:true}}}};
  await vm.runInNewContext(source,{document:{getElementById:id=>elements.get(id),createElement:()=>({})},chrome,URL,setInterval:fn=>{timer=fn},clearInterval(){}});
  return {elements,view,calls,refresh:()=>timer(),fail:()=>{fail=true},hold:()=>{hold=true},release:()=>{hold=false;release()}};
}
test('visible phase distinguishes idle, empty and protocol playing without claiming TV confirmation',async()=>{
  const p=await popup();const phase=p.elements.get('phase');
  assert.ok(phase,'phase live region exists');
  assert.equal(phase.dataset.state,'idle');
  p.view.candidates=[];p.view.selected=null;await p.refresh();
  assert.equal(phase.dataset.state,'empty');assert.equal(p.elements.get('start').disabled,true);
  p.view.native.state='playing';await p.refresh();
  assert.equal(phase.dataset.state,'playing');assert.match(phase.textContent,/Helper reports playing/);
  assert.match(p.elements.get('tvStatus').textContent,/Helper reports playing/,'receiver status must not keep the stale Send instruction');
  assert.equal(p.calls.some(c=>c.op==='localPause'),false);
});
test('working state spans an awaited operation; failed actions stay visibly in error',async()=>{
  const p=await popup();const phase=p.elements.get('phase');assert.ok(phase);
  p.hold();const action=p.elements.get('discover').onclick();
  assert.equal(phase.dataset.state,'working');p.release();await action;assert.equal(phase.dataset.state,'idle');
  p.fail();await p.elements.get('hello').onclick();assert.equal(phase.dataset.state,'error');
  await p.refresh();assert.equal(phase.dataset.state,'error','polling must not hide an action error');
});
test('native errors take precedence over idle and disconnected controls remain gated',async()=>{
  const p=await popup();p.view.native.error='NATIVE_DISCONNECTED';await p.refresh();
  assert.equal(p.elements.get('phase')?.dataset.state,'error');
  assert.equal(p.elements.get('helperSetup')?.textContent,'Finish setup');
  await p.elements.get('helperSetup').onclick();
  assert.equal(p.calls.at(-1).op,'openSetup');
  for(const id of ['discover','host','start'])assert.equal(p.elements.get(id).disabled,true);
});
