import test from 'node:test';
import assert from 'node:assert/strict';
test('malformed receiver entries fail closed without throwing out of the message listener',async()=>{
 const {Native}=await import('../../extension/native.mjs');
 for(const receivers of [[null],[{}],[{identifier:'',address:'192.168.1.2'}],{},[{identifier:'r',address:'host.test'}]]) {
  const p=fakePort();const n=new Native(()=>p);const pending=n.request('discover');
  const rejected=assert.rejects(pending,/INVALID_RESPONSE/);
  try {
   assert.doesNotThrow(()=>p.onMessage.emit({v:1,id:p.sent[0].id,ok:true,state:'idle',evidence:'none',capabilities:['start'],receivers}));
   await rejected;assert.equal(n.view().state,'error');assert.deepEqual(n.view().receivers,[]);
  } finally {n.fail('INVALID_RESPONSE');await rejected;}
 }
});
test('video receiver kinds render static compatibility labels instead of trusting names',async()=>{
 const {Native}=await import('../../extension/native.mjs');const p=fakePort();const n=new Native(()=>p);
 const pending=n.request('discover');
 p.onMessage.emit({v:1,id:p.sent[0].id,ok:true,state:'idle',evidence:'none',capabilities:['discover'],receivers:[
 {identifier:'a',address:'192.0.2.10',kind:'apple-tv',label:'SECRET'},
 {identifier:'b',address:'192.0.2.20',kind:'airplay-video',label:'https://secret.test'}]});
 const result=await pending;
 assert.match(result.receivers[0].label,/Apple TV/);
 assert.match(result.receivers[1].label,/compatibility unverified/);
 assert.doesNotMatch(JSON.stringify(result),/SECRET|secret.test/);
});
test('discovery gets a separate deadline longer than ordinary requests',async()=>{
 const {Native}=await import('../../extension/native.mjs');const p=fakePort();const n=new Native(()=>p,{timeout:5,discoveryTimeout:100});
 const pending=n.request('discover');
 setTimeout(()=>p.onMessage.emit({v:1,id:p.sent[0].id,ok:true,state:'idle',evidence:'none',capabilities:['discover'],receivers:[]}),20);
 assert.equal((await pending).state,'idle');
});
test('pairing requests get their own 35s deadline without widening ordinary or discovery timeouts',async()=>{
 const {Native}=await import('../../extension/native.mjs');
 const p=fakePort();const n=new Native(()=>p,{timeout:5,discoveryTimeout:100});
 assert.equal(n.pairingTimeout,35000);
 const pb=n.request('pair_begin',{receiver:'AA:BB:CC:DD:EE:FF',host:'192.168.1.50'});
 setTimeout(()=>p.onMessage.emit({v:1,id:p.sent[0].id,ok:true,state:'idle',evidence:'none',capabilities:['pair_begin']}),20);
 assert.equal((await pb).state,'idle');
 const pr=n.request('pair',{receiver:'AA:BB:CC:DD:EE:FF',host:'192.168.1.50',pin:'1234'});
 setTimeout(()=>p.onMessage.emit({v:1,id:p.sent[1].id,ok:true,state:'idle',evidence:'none',capabilities:['pair']}),20);
 assert.equal((await pr).state,'idle');
 await assert.rejects(n.request('hello'),/NATIVE_TIMEOUT/);
});
test('a successful hello after a pairing error does not erase the safe error code',async()=>{
 const {Native}=await import('../../extension/native.mjs');const p=fakePort();const n=new Native(()=>p);
 const pb=n.request('pair_begin',{receiver:'AA:BB:CC:DD:EE:FF',host:'192.168.1.50'});
 p.onMessage.emit({v:1,id:p.sent[0].id,ok:false,state:'idle',evidence:'unverified',capabilities:['pair_begin','hello'],error:'receiver_unavailable'});
 await assert.rejects(pb,/receiver_unavailable/);assert.equal(n.view().error,'receiver_unavailable');
 const hello=n.request('hello');
 p.onMessage.emit({v:1,id:p.sent[1].id,ok:true,state:'idle',evidence:'none',capabilities:['hello'],receivers:[]});
 await hello;
 assert.equal(n.view().error,'receiver_unavailable');
});
test('playback diagnostics retain only safe bounded fields',async()=>{
 const {Native}=await import('../../extension/native.mjs');const p=fakePort();const n=new Native(()=>p);
 const pending=n.request('hello');p.onMessage.emit({v:1,id:p.sent[0].id,ok:true,state:'idle',evidence:'none',capabilities:['start']});await pending;
 const reply={v:1,id:'event',ok:false,state:'error',evidence:'unverified',capabilities:['start'],error:'transport_failed'};
 p.onMessage.emit({...reply,diagnostic:{stage:'command',reason:'rejected',httpStatus:403,url:'SECRET'}});
 assert.deepEqual(n.view().diagnostic,{stage:'command',reason:'rejected',httpStatus:403});
 p.onMessage.emit({...reply,diagnostic:{stage:'SECRET',reason:'timeout',httpStatus:999}});
 assert.equal(n.view().diagnostic,null);assert.doesNotMatch(JSON.stringify(n.view()),/SECRET/);
 p.onMessage.emit({...reply,diagnostic:{stage:'await-playing',reason:'timeout',httpStatus:true}});
 assert.deepEqual(n.view().diagnostic,{stage:'await-playing',reason:'timeout'});
});
test('firewall replies are sanitized separately and survive later playback events',async()=>{
 const {Native}=await import('../../extension/native.mjs');const p=fakePort();const n=new Native(()=>p,{timeout:5,firewallTimeout:100});
 const hello=n.request('hello');const base={v:1,ok:true,state:'idle',evidence:'none',capabilities:['start']};
 p.onMessage.emit({...base,id:p.sent[0].id,firewallSupport:true});await hello;
 assert.equal(n.view().firewallSupport,true);
 const pending=n.request('firewall',{receiver:'AA:BB:CC:DD:EE:FF',host:'192.168.1.50',action:'allow'});
 p.onMessage.emit({...base,id:'event',state:'playing',evidence:'protocol',firewallSupport:true});
 await new Promise(r=>setTimeout(r,15));
 p.onMessage.emit({...base,id:p.sent[1].id,firewall:{supported:true,enabled:true,allowance:'missing',owned:false,change:{ok:false,error:'SECRET'},secret:'URL'}});
 assert.deepEqual(await pending,{supported:true,enabled:true,allowance:'missing',owned:false,change:{ok:false,error:'ufw_failed'}});
 assert.equal(n.view().state,'playing');assert.equal(n.view().firewallSupport,true);
 await assert.rejects(n.request('firewall',{receiver:'tv',host:'192.168.1.50',action:'disable'}),/INVALID_REQUEST/);
});
test('ambiguous_rule firewall error passes sanitization for a clear popup refusal',async()=>{
 const {Native}=await import('../../extension/native.mjs');const p=fakePort();const n=new Native(()=>p);
 const hello=n.request('hello');const base={v:1,ok:true,state:'idle',evidence:'none',capabilities:['start']};
 p.onMessage.emit({...base,id:p.sent[0].id,firewallSupport:true});await hello;
 const pending=n.request('firewall',{receiver:'AA:BB:CC:DD:EE:FF',host:'192.168.1.50',action:'remove'});
 p.onMessage.emit({...base,id:p.sent[1].id,firewall:{supported:true,enabled:true,allowance:'present',owned:true,change:{ok:false,error:'ambiguous_rule'},secret:'URL'}});
 assert.deepEqual(await pending,{supported:true,enabled:true,allowance:'present',owned:true,change:{ok:false,error:'ambiguous_rule'}});
});
test('accepted V1 metadata is bounded, session-scoped and cleared by lifecycle replies',async()=>{
 const {Native}=await import('../../extension/native.mjs');const p=fakePort();const n=new Native(()=>p);
 const hello=n.request('hello');const base={v:1,id:p.sent[0].id,ok:true,state:'idle',evidence:'none',capabilities:['start','status','stop']};
 p.onMessage.emit({...base,receivers:[{identifier:'tv',address:'192.168.1.50',timingRequired:false}]});await hello;
 assert.equal(n.view().receivers[0].timingRequired,false);
 const session={receiver:'tv',host:'192.168.1.50',transport:'airplay-v1',delivery:'accepted',timingRequired:false};
 const accepted={...base,id:'event',state:'connecting',evidence:'unverified',session};
 p.onMessage.emit(accepted);assert.deepEqual(n.view().session,session);assert.equal(n.view().state,'connecting');
 for(const invalid of [{...session,host:'secret.test'},{...session,delivery:'playing'},{...session,timingRequired:true},{...session,secret:'SIGNED_URL'},null]){
  p.onMessage.emit({...accepted,session:invalid});assert.equal(n.view().session,null);
  assert.doesNotMatch(JSON.stringify(n.view()),/SIGNED_URL|secret.test/);
 }
 for(const state of ['stopped','error','playing','idle']){
  p.onMessage.emit(accepted);p.onMessage.emit({...accepted,state});assert.equal(n.view().session,null);
 }
 p.onMessage.emit(accepted);p.onMessage.emit({...base,id:'event',state:'connecting'});assert.equal(n.view().session,null);
 p.onMessage.emit(accepted);p.disconnect();assert.equal(n.view().session??null,null);
});
test('unsupported receiver details survive status refresh without exposing arbitrary text',async()=>{
 const {Native}=await import('../../extension/native.mjs');const p=fakePort();const n=new Native(()=>p);
 const hello=n.request('hello');const base={v:1,id:p.sent[0].id,ok:true,state:'idle',evidence:'none',capabilities:['start','status']};
 p.onMessage.emit(base);await hello;
 p.onMessage.emit({...base,id:'event',ok:false,state:'error',error:'transport_failed',receiverIssue:'unsupported_access'});
 assert.equal(n.view().receiverIssue,'unsupported_access');
 const status=n.request('status');p.onMessage.emit({...base,id:p.sent.at(-1).id});await status;
 assert.equal(n.view().receiverIssue,'unsupported_access');
 p.onMessage.emit({...base,id:'event',ok:false,state:'error',error:'transport_failed',receiverIssue:'SECRET_URL'});
 assert.equal(n.view().receiverIssue,null);assert.doesNotMatch(JSON.stringify(n.view()),/SECRET_URL/);
});
function signal(){const listeners=[];return {addListener:f=>listeners.push(f),emit:v=>listeners.forEach(f=>f(v))};}
export function fakePort(){return {onMessage:signal(),onDisconnect:signal(),sent:[],postMessage(m){this.sent.push(m);},disconnect(){this.onDisconnect.emit();}};}
test('late replies cannot roll newer native state back; helper failures and invalid frames fail closed',async()=>{
 const {Native}=await import('../../extension/native.mjs');const p=fakePort();const n=new Native(()=>p);const a=n.request('status');const b=n.request('stop');
 const base={v:1,ok:true,state:'stopped',evidence:'protocol',capabilities:['status','stop']};
 p.onMessage.emit({...base,id:p.sent[1].id});await b;p.onMessage.emit({...base,id:p.sent[0].id,state:'playing'});await a;assert.equal(n.view().state,'stopped');
 const c=n.request('status');p.onMessage.emit({...base,id:p.sent[2].id,ok:false,error:'secret https://x/signed'});await assert.rejects(c,/HELPER_ERROR/);assert.equal(JSON.stringify(n.view()).includes('signed'),false);
 const d=n.request('status');p.onMessage.emit({...base,id:p.sent[3].id,v:2});await assert.rejects(d,/INVALID_RESPONSE/);assert.equal(n.view().state,'error');
});
test('native port survives UI, validates replies, exact start and disconnect fails pending requests',async()=>{
 const {Native}=await import('../../extension/native.mjs');const p=fakePort();const n=new Native(()=>p,{timeout:30});
 const hello=n.request('hello');assert.deepEqual(p.sent[0].args,{});
 const reply={v:1,id:p.sent[0].id,ok:true,state:'idle',evidence:'none',capabilities:['start','status']};
 p.onMessage.emit({...reply,id:'stale',state:'playing'});assert.equal(n.view().state,'idle');
 p.onMessage.emit(reply);await hello;
 const url='https://x.test/%2f?a=+&a=%20';const start=n.request('start',{receiver:'r',host:'192.168.1.2',url});
 assert.equal(p.sent[1].args.url,url);
 p.onMessage.emit({...reply,id:p.sent[1].id,state:'playing',evidence:'protocol'});await start;
 const pending=n.request('status');p.disconnect();await assert.rejects(pending,/NATIVE_DISCONNECTED/);assert.equal(n.view().state,'error');
 await assert.rejects(n.request('start',{receiver:'r',host:'example.com',url}),/INVALID_REQUEST/);
 await assert.rejects(n.request('pause',{url}),/INVALID_REQUEST/);
 const timed=n.request('hello');await assert.rejects(timed,/NATIVE_TIMEOUT/);
});
