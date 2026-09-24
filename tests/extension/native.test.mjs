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
