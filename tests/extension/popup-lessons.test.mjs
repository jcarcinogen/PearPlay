import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const source=await readFile(new URL('../../extension/popup.js',import.meta.url),'utf8');
const html=await readFile(new URL('../../extension/popup.html',import.meta.url),'utf8');
async function mount(os='linux', initialVisibility='visible') {
 const elements=new Map([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],{value:'',textContent:'',dataset:{},disabled:false,replaceChildren(){this.replacements=(this.replacements??0)+1;},append(){},addEventListener(){}}]));
 const view={enabled:true,selected:'c1',receiver:'r',candidates:[{id:'c1',label:'Example film'},{id:'c2',label:'Second film'},{id:'c3',label:'Third film'}],native:{state:'idle',error:null,capabilities:['start','stop'],receivers:[{identifier:'r',label:'Example TV',address:'192.168.1.5'},{identifier:'r2',label:'Second TV',address:'192.168.1.6'}]}};
 let tick,hold=false,release,allowed=true,grant=false,holdPair=false,releasePair;
 const calls=[],events={},writes=[],gates=new Map(),failures=new Map();
 const document={visibilityState:initialVisibility,getElementById:id=>elements.get(id),createElement:()=>({}),addEventListener:(e,f)=>{events[e]=f},removeEventListener(){}};
 const chrome={tabs:{query:async()=>[{id:1,url:'https://example.test/watch'}],create:async()=>{}},storage:{session:{get:async()=>({}),set:async o=>writes.push(o)}},permissions:{getAll:async()=>({origins:allowed?['http://*/*','https://*/*']:[]}),request:async()=>{allowed=grant;return grant;}},runtime:{getPlatformInfo:async()=>({os}),getURL:p=>p,sendMessage:async m=>{
  calls.push(m);
  const snapshot=m.op==='view'?structuredClone(view):null;
  if(gates.has(m.op))await gates.get(m.op);
  const failure=failures.get(m.op);failures.delete(m.op);
  if(failure==='before')return {ok:false,error:'ACTION_FAILED'};
  if(m.op==='view'){if(hold)await new Promise(r=>{release=r});return snapshot;}
  if(m.op==='pairBegin'&&holdPair)await new Promise(r=>{releasePair=r});
  if(m.op==='select')view.selected=m.id;
  if(m.op==='receiver')view.receiver=m.id;
  if(m.op==='start')calls.push({op:'dispatch',selected:view.selected,receiver:view.receiver});
  if(m.op==='stop'){view.native.error=null;view.native.state='stopped';}
  if(failure==='after')throw Error('NATIVE_DISCONNECTED');
  return m.op==='discover'?{receivers:view.native.receivers}:{ok:true};
 }}};
 const initialization=vm.runInNewContext(source,{document,chrome,URL,setInterval:f=>{tick=f},clearInterval(){},addEventListener:(e,f)=>{events[e]=f}});
 if(initialVisibility==='hidden'){assert.equal(calls.length,0);document.visibilityState='visible';events.visibilitychange();}
 await initialization;
 return {elements,calls,view,writes,document,holdOp:op=>{let done;gates.set(op,new Promise(r=>{done=r}));return ()=>{gates.delete(op);done()};},failOp:(op,when='before')=>failures.set(op,when),refresh:()=>tick(),hold:()=>{hold=true},release:()=>{hold=false;release()},holdPair:()=>{holdPair=true},releasePair:()=>releasePair(),close:()=>events.pagehide(),deny:()=>{allowed=false;grant=false},grant:()=>{grant=true}};
}
for(const os of ['linux','mac','win']) test(`${os} popup keeps existing helper flow available`,async()=>{const p=await mount(os);assert.ok(p.calls.some(m=>m.op==='view'));assert.equal(p.calls.some(m=>['hello','discover'].includes(m.op)),false);assert.equal(p.elements.get('start').disabled,false);});
test('initially hidden action document waits then initializes when Chrome makes it visible',async()=>{const p=await mount('mac','hidden');assert.ok(p.calls.some(m=>m.op==='view'));assert.equal(p.calls.some(m=>['hello','discover'].includes(m.op)),false);});
test('other OS stops before native connection and shows clear unavailability',async()=>{const p=await mount('cros');assert.equal(p.calls.length,0);assert.equal(p.elements.get('casting').hidden,true);assert.match(p.elements.get('platformNotice').textContent,/not supported/);});
test('quiet refresh has one in-flight view, blocks racing actions and preserves unchanged option DOM',async()=>{
 const p=await mount();const before=p.elements.get('candidate').replacements;
 const viewsBefore=p.calls.filter(m=>m.op==='view').length;
 p.hold();const a=p.refresh(),b=p.refresh();await p.elements.get('start').onclick();
 assert.equal(p.calls.filter(m=>m.op==='view').length,viewsBefore+1); // exactly one new pending view
 assert.equal(p.calls.some(m=>m.op==='start'),false);assert.equal(p.elements.get('start').disabled,false);
 p.release();await Promise.all([a,b]);assert.equal(p.elements.get('candidate').replacements,before);
 await p.elements.get('start').onclick();assert.equal(p.calls.filter(m=>m.op==='start').length,1);
});
test('deliberate dropdown choice waits for quiet refresh instead of being swallowed',async()=>{
 const p=await mount();p.hold();const pending=p.refresh();p.elements.get('candidate').value='c2';const choice=p.elements.get('candidate').onchange();
 assert.equal(p.calls.some(m=>m.op==='select'),false);p.release();await Promise.all([pending,choice]);assert.equal(p.calls.find(m=>m.op==='select').id,'c2');
});
for(const order of [['candidate','receiver'],['receiver','candidate']]) test(`independent choices survive delayed quiet view: ${order.join(' then ')}`,async()=>{
 const p=await mount();p.hold();const poll=p.refresh();const choices=order.map(field=>{p.elements.get(field).value=field==='candidate'?'c2':'r2';return p.elements.get(field).onchange();});
 p.release();await Promise.all([poll,...choices]);
 assert.equal(p.view.selected,'c2');assert.equal(p.view.receiver,'r2');
 assert.equal(p.elements.get('candidate').value,p.view.selected);assert.equal(p.elements.get('receiver').value,p.view.receiver);
 await p.elements.get('start').onclick();assert.deepEqual(p.calls.find(m=>m.op==='dispatch'),{op:'dispatch',selected:'c2',receiver:'r2'});
});
test('closed popup discards pending refresh without selection, DOM or session writes',async()=>{
 const p=await mount();p.view.selected=null;p.view.candidates=[{id:'c2',label:'Replacement'}];p.hold();const pending=p.refresh();
 const title=p.elements.get('identity').textContent,ops=p.calls.length,writes=p.writes.length;p.close();p.release();await pending;
 assert.equal(p.elements.get('identity').textContent,title);assert.equal(p.calls.length,ops);assert.equal(p.writes.length,writes);
});
test('lost deliberate selection is not auto-retargeted to sole replacement',async()=>{
 const p=await mount();p.view.selectionLost=true;p.view.selected=null;p.view.candidates=[{id:'c2',label:'Replacement'}];await p.refresh();
 assert.equal(p.calls.some(m=>m.op==='select'),false);assert.equal(p.elements.get('start').disabled,true);assert.match(p.elements.get('identity').textContent,/choose again/);
});
test('permission denial is recoverable by another deliberate grant',async()=>{
 const p=await mount();p.deny();await p.refresh();await p.elements.get('grantAll').onclick();assert.equal(p.elements.get('enable').disabled,true);assert.match(p.elements.get('tvStatus').textContent,/Not allowed/);
 p.grant();await p.elements.get('grantAll').onclick();assert.equal(p.elements.get('enable').disabled,false);assert.equal(p.elements.get('permissionBox').hidden,true);
});
test('late pairing result cannot reopen PIN after the helper session is ended',async()=>{
 const p=await mount();p.holdPair();p.view.native.error='pairing_required';await p.refresh();
 const begin=p.elements.get('pairRestart').onclick();await new Promise(r=>setImmediate(r));
 await p.elements.get('stop').onclick();assert.equal(p.calls.some(m=>m.op==='stop'),false);
 p.releasePair();await begin;await p.elements.get('stop').onclick();
 assert.equal(p.elements.get('pairBox').hidden,true);assert.equal(p.elements.get('candidate').hidden,false);
});
test('hidden popup polling performs no new work',async()=>{
 const p=await mount();const count=p.calls.length;p.document.visibilityState='hidden';await p.refresh();assert.equal(p.calls.length,count);
});
const turn=()=>new Promise(r=>setImmediate(r));
const choose=(p,field,value)=>{p.elements.get(field).value=value;return p.elements.get(field).onchange();};
const reconciled=p=>{assert.equal(p.elements.get('candidate').value,p.view.selected??'');assert.equal(p.elements.get('receiver').value,p.view.receiver??'');};
test('cached options restore actual value without replacing option DOM',async()=>{
 const p=await mount(),count=p.elements.get('candidate').replacements;p.elements.get('candidate').value='c2';await p.refresh();reconciled(p);assert.equal(p.elements.get('candidate').replacements,count);
});
test('rapid same-field choices during delayed view keep latest and other field intent',async()=>{
 const p=await mount();p.hold();const poll=p.refresh();const a=choose(p,'candidate','c2'),b=choose(p,'receiver','r2'),c=choose(p,'candidate','c3');
 assert.equal(p.elements.get('start').disabled,true);await p.elements.get('start').onclick();assert.equal(p.calls.some(m=>m.op==='start'),false);
 p.release();await Promise.all([poll,a,b,c]);reconciled(p);assert.equal(p.view.selected,'c3');assert.equal(p.view.receiver,'r2');assert.deepEqual(p.calls.filter(m=>m.op==='select').map(m=>m.id),['c3']);assert.equal(p.elements.get('start').disabled,false);
});
test('new choices during delayed commit survive; polling never retries or overlaps',async()=>{
 const p=await mount(),release=p.holdOp('select');const a=choose(p,'candidate','c2');await turn();assert.equal(p.calls.filter(m=>m.op==='select').length,1);
 const b=choose(p,'candidate','c3'),c=choose(p,'receiver','r2');const views=p.calls.filter(m=>m.op==='view').length;await p.refresh();await p.elements.get('start').onclick();
 assert.equal(p.calls.filter(m=>m.op==='view').length,views);assert.equal(p.calls.some(m=>m.op==='start'),false);assert.equal(p.elements.get('start').disabled,true);
 release();await Promise.all([a,b,c]);reconciled(p);assert.equal(p.view.selected,'c3');assert.equal(p.view.receiver,'r2');await p.elements.get('start').onclick();assert.deepEqual(p.calls.find(m=>m.op==='dispatch'),{op:'dispatch',selected:'c3',receiver:'r2'});
});
for(const when of ['before','after'])test(`failed commit (${when} worker mutation) reconciles truth without polling retry`,async()=>{
 const p=await mount();p.failOp('select',when);await choose(p,'candidate','c2');reconciled(p);assert.equal(p.view.selected,when==='before'?'c1':'c2');assert.equal(p.elements.get('phase').dataset.state,'error');
 await p.refresh();await p.refresh();assert.equal(p.calls.filter(m=>m.op==='select').length,1);await p.elements.get('start').onclick();assert.equal(p.calls.find(m=>m.op==='dispatch').selected,p.view.selected);
});
test('failed reconciliation stays Send-blocked until worker view is confirmed',async()=>{
 const p=await mount();p.failOp('view');await choose(p,'candidate','c2');assert.equal(p.elements.get('start').disabled,true);await p.elements.get('start').onclick();assert.equal(p.calls.some(m=>m.op==='start'),false);
 await p.refresh();reconciled(p);assert.equal(p.elements.get('start').disabled,false);
});
for(const op of ['status','start'])test(`choices during pending ${op} action commit afterward, never auto-Send`,async()=>{
 const p=await mount(),release=p.holdOp(op);const action=p.elements.get(op).onclick();await turn();const a=choose(p,'candidate','c2'),b=choose(p,'receiver','r2');await turn();assert.equal(p.calls.some(m=>m.op==='select'||m.op==='receiver'),false);
 release();await Promise.all([action,a,b]);reconciled(p);assert.equal(p.view.selected,'c2');assert.equal(p.view.receiver,'r2');assert.equal(p.calls.filter(m=>m.op==='start').length,op==='start'?1:0);
 if(op==='start')assert.deepEqual(p.calls.find(m=>m.op==='dispatch'),{op:'dispatch',selected:'c1',receiver:'r'});
 await p.refresh();assert.equal(p.calls.filter(m=>m.op==='start').length,op==='start'?1:0);
 await p.elements.get('start').onclick();assert.deepEqual(p.calls.filter(m=>m.op==='dispatch').at(-1),{op:'dispatch',selected:'c2',receiver:'r2'});
});
for(const pending of ['view','select','status'])test(`popup closed during pending ${pending} drops queued choices and late DOM writes`,async()=>{
 const p=await mount(),release=p.holdOp(pending);let work;
 if(pending==='view')work=p.refresh();else if(pending==='status')work=p.elements.get('status').onclick();else work=choose(p,'candidate','c2');
 await turn();const choices=[choose(p,'receiver','r2'),choose(p,'candidate','c3')];const values=[p.elements.get('candidate').value,p.elements.get('receiver').value,p.elements.get('identity').textContent];const count=p.calls.length,writes=p.writes.length;
 p.close();release();await Promise.all([work,...choices]);assert.equal(p.calls.length,count);assert.equal(p.writes.length,writes);assert.deepEqual([p.elements.get('candidate').value,p.elements.get('receiver').value,p.elements.get('identity').textContent],values);
});
test('receiver commit clears old PIN state and ignores late pairing completion',async()=>{
 const p=await mount();p.holdPair();p.view.native.error='pairing_required';await p.refresh();
 const begin=p.elements.get('pairRestart').onclick();await turn();const old=p.calls.filter(m=>m.op==='pairBegin').length;
 p.view.native.error=null;const choice=choose(p,'receiver','r2');p.releasePair();await Promise.all([begin,choice]);await turn();reconciled(p);assert.equal(p.calls.filter(m=>m.op==='pairBegin').length,old);assert.equal(p.elements.get('pairBox').hidden,true);assert.equal(p.elements.get('candidate').hidden,false);
});
for(const os of ['mac','win']) test(`${os} never offers automatic UFW changes even with legacy capability`,async()=>{
 const p=await mount(os);p.view.native.firewallSupport=true;p.view.firewall={receiver:'r',host:'192.168.1.5',supported:true,enabled:true,allowance:'missing',owned:true};await p.refresh();
 for(const id of ['firewallAllow','firewallRemove','firewallRemoveIfPresent','firewallConsent'])assert.equal(p.elements.get(id).hidden,true);
 assert.equal(p.elements.get('firewallCheck').disabled,true);assert.match(p.elements.get('firewallStatus').textContent,/manually/);
});
