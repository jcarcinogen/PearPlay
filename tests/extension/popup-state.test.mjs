import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const source=await readFile(new URL('../../extension/popup.js',import.meta.url),'utf8');
const html=await readFile(new URL('../../extension/popup.html',import.meta.url),'utf8');
async function popup(overrides={}) {
  const {rejectOps={}, ...rest} = overrides;
  const elements=new Map([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],{value:'',textContent:'',disabled:false,dataset:{},replaceChildren(){},append(){},addEventListener(){}}]));
  const view={enabled:true,selected:'video',receiver:'tv',localAvailable:false,candidates:[{id:'video',label:'Example film',videoId:'element'}],native:{state:'idle',error:null,receivers:[{identifier:'tv',label:'Living Room'}],capabilities:['start','stop']},...rest};
  let timer;const calls=[];let fail=false;let release;let hold=false;
  const chrome={tabs:{query:async()=>[{id:1,url:'https://example.test/watch'}]},permissions:{getAll:async()=>({origins:['http://*/*','https://*/*']})},runtime:{getPlatformInfo:async()=>({os:'linux'}),sendMessage:async m=>{calls.push(m);if(m.op==='view')return structuredClone(view);if(rejectOps[m.op]!==undefined)return {ok:false,error:rejectOps[m.op]};if(fail)throw Error('NATIVE_DISCONNECTED');if(hold)await new Promise(r=>{release=r});return m.op==='discover'?{receivers:view.native.receivers}:{ok:true}}}};
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
test('playback failure displays a safe diagnostic instead of reconnect advice',async()=>{
 const p=await popup();p.view.native.state='error';p.view.native.error='transport_failed';
 p.view.native.diagnostic={stage:'await-playing',reason:'timeout'};await p.refresh();
 assert.match(p.elements.get('tvStatus').textContent,/TV did not confirm playback/);
 assert.match(p.elements.get('tvStatus').textContent,/await-playing \/ timeout/);
 assert.doesNotMatch(p.elements.get('tvStatus').textContent,/Reconnect/);
 p.view.native.diagnostic=null;await p.refresh();
 assert.match(p.elements.get('state').textContent,/Playback failed/);
});
test('firewall onboarding states saved-rule limits and requires explicit scoped consent',async()=>{
 const p=await popup();p.view.native.firewallSupport=true;
 p.view.native.receivers[0].address='192.168.1.50';
 p.view.firewall={receiver:'tv',host:'192.168.1.50',supported:true,enabled:true,allowance:'missing',owned:false};
 await p.refresh();
 assert.match(p.elements.get('firewallStatus').textContent,/UFW.*saved|saved.*UFW/);
 assert.match(p.elements.get('firewallScope').textContent,/192.168.1.50.*UDP 49170/);
 assert.equal(p.elements.get('firewallAllow').hidden,false);
 assert.equal(p.elements.get('firewallRemove').hidden,true);
 await p.elements.get('firewallAllow').onclick();assert.equal(p.calls.some(c=>c.op==='firewall'&&c.action==='allow'),false);
 p.elements.get('firewallConsent').checked=true;await p.elements.get('firewallAllow').onclick();
 assert.equal(p.calls.find(c=>c.op==='firewall'&&c.action==='allow').confirmed,true);
 p.view.firewall.change={ok:false,error:'auth_cancelled'};await p.refresh();
 assert.match(p.elements.get('firewallStatus').textContent,/cancelled/i);
 p.view.firewall={...p.view.firewall,allowance:'present',owned:true,change:null};await p.refresh();
 assert.equal(p.elements.get('firewallRemove').hidden,false);
 p.view.receiver='different';await p.refresh();
 assert.equal(p.elements.get('firewallConsent').checked,false);
 assert.equal(p.elements.get('firewallAllow').hidden,true);
});
test('unknown allowance never offers Allow and offers remove-if-present only for private IPv4',async()=>{
 const p=await popup();p.view.native.firewallSupport=true;
 p.view.native.receivers[0].address='192.168.1.50';
 p.view.firewall={receiver:'tv',host:'192.168.1.50',supported:true,enabled:true,allowance:'unknown',owned:false};
 await p.refresh();
 assert.equal(p.elements.get('firewallAllow').hidden,true);
 assert.equal(p.elements.get('firewallRemoveIfPresent').hidden,false);
 assert.match(p.elements.get('firewallStatus').textContent,/could not be read/);
 assert.match(p.elements.get('firewallStatus').textContent,/will not remove administrator/);
 await p.elements.get('firewallRemoveIfPresent').onclick();
 assert.equal(p.calls.some(c=>c.op==='firewall'&&c.action==='remove'),false);
 p.elements.get('firewallConsent').checked=true;await p.elements.get('firewallRemoveIfPresent').onclick();
 assert.equal(p.calls.find(c=>c.op==='firewall'&&c.action==='remove').confirmed,true);
 p.view.native.receivers[0].address='8.8.8.8';p.view.firewall.host='8.8.8.8';await p.refresh();
 assert.equal(p.elements.get('firewallRemoveIfPresent').hidden,true);
 assert.equal(p.elements.get('firewallAllow').hidden,true);
});
test('ambiguous removal shows a clear static refusal and does not claim success',async()=>{
 const p=await popup();p.view.native.firewallSupport=true;
 p.view.native.receivers[0].address='192.168.1.50';
 p.view.firewall={receiver:'tv',host:'192.168.1.50',supported:true,enabled:true,allowance:'present',owned:true,change:{ok:false,error:'ambiguous_rule'}};
 await p.refresh();
 assert.match(p.elements.get('firewallStatus').textContent,/will not remove a rule it did not create/);
});
test('reopening during firewallBusy skips initial hello/discover and shows pending status',async()=>{
 const p=await popup({firewallBusy:true});
 assert.equal(p.calls.some(c=>c.op==='hello'),false);
 assert.equal(p.calls.some(c=>c.op==='discover'),false);
 assert.match(p.elements.get('firewallStatus').textContent,/Waiting for administrator approval/);
});
test('native errors take precedence over idle and disconnected controls remain gated',async()=>{
  const p=await popup();p.view.native.error='NATIVE_DISCONNECTED';await p.refresh();
  assert.equal(p.elements.get('phase')?.dataset.state,'error');
  assert.equal(p.elements.get('helperSetup')?.textContent,'Finish setup');
  await p.elements.get('helperSetup').onclick();
  assert.equal(p.calls.at(-1).op,'openSetup');
  for(const id of ['discover','host','start'])assert.equal(p.elements.get(id).disabled,true);
});
test('receiver_unavailable shows a specific actionable message with no reinstall or firewall blame',async()=>{
  const p=await popup();p.view.native.state='error';p.view.native.error='receiver_unavailable';await p.refresh();
  assert.match(p.elements.get('tvStatus').textContent,/pairing or playback could not start/i);
  assert.match(p.elements.get('tvStatus').textContent,/Find TVs/i);
  assert.doesNotMatch(p.elements.get('tvStatus').textContent,/Reconnect/);
  assert.doesNotMatch(p.elements.get('tvStatus').textContent,/reinstall|firewall/i);
});
test('pairing_failed shows a specific message instead of generic reconnect advice',async()=>{
  const p=await popup();p.view.native.state='error';p.view.native.error='pairing_failed';await p.refresh();
  assert.match(p.elements.get('tvStatus').textContent,/Pairing did not finish/i);
  assert.doesNotMatch(p.elements.get('tvStatus').textContent,/Reconnect/);
});
test('pairing_required surfaces a PIN instruction in the status line instead of generic advice',async()=>{
  const p=await popup();p.view.native.state='error';p.view.native.error='pairing_required';await p.refresh();
  assert.doesNotMatch(p.elements.get('state').textContent,/Helper needs attention/);
  assert.match(p.elements.get('state').textContent,/digits/i);
});
test('a failed pairBegin is not auto-repeated on later polling refreshes',async()=>{
  const p=await popup({rejectOps:{pairBegin:'receiver_unavailable'}});
  p.view.native.state='error';p.view.native.error='pairing_required';await p.refresh();
  assert.equal(p.calls.filter(c=>c.op==='pairBegin').length,1);
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(p.elements.get('tvStatus').textContent,/Find TVs/i, 'failed pairing must immediately preserve the specific native error');
  await p.refresh();
  assert.equal(p.calls.filter(c=>c.op==='pairBegin').length,1,'pairBegin must not be auto-repeated while pairing_required persists');
});
test('a failed pairBegin leaves the accurate receiver_unavailable wording on refresh',async()=>{
  const p=await popup({rejectOps:{pairBegin:'receiver_unavailable'}});
  p.view.native.state='error';p.view.native.error='pairing_required';await p.refresh();
  p.view.native.error='receiver_unavailable';await p.refresh();
  assert.match(p.elements.get('tvStatus').textContent,/pairing or playback could not start/i);
  assert.match(p.elements.get('tvStatus').textContent,/Find TVs/i);
});
