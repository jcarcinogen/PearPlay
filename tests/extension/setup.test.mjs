import test from 'node:test';
import assert from 'node:assert/strict';
import {Native} from '../../extension/native.mjs';

test('setup offers only compatible, real release links and requires a current handshake', async () => {
  const {connectionState, downloadsFor}=await import('../../extension/setup-model.mjs');
  assert.equal(connectionState({helperVersion:'0.2.0',capabilities:['hello','discover','start']}).kind,'ready');
  assert.equal(connectionState({capabilities:['hello']}).kind,'update');
  assert.equal(connectionState(null,'NATIVE_DISCONNECTED').kind,'missing');
  assert.equal(connectionState(null,'INVALID_RESPONSE').kind,'broken');
  const catalog={extensionId:'a'.repeat(32),downloads:[{os:'mac',arch:'arm64',format:'pkg',url:'https://github.com/jcarcinogen/PearPlay/releases/download/v0.2.0/helper.pkg'}]};
  assert.equal(downloadsFor(catalog,{os:'mac',arch:'arm64'},'a'.repeat(32)).length,1);
  assert.equal(downloadsFor(catalog,{os:'linux',arch:'x86-64'},'a'.repeat(32)).length,0);
  assert.equal(downloadsFor(catalog,{os:'mac',arch:'arm64'},'b'.repeat(32)).length,0);
  catalog.downloads[0].url='https://evil.example/helper.pkg';
  assert.equal(downloadsFor(catalog,{os:'mac',arch:'arm64'},'a'.repeat(32)).length,0);
});

test('setup page checks connection without discovery and leaves downloads unavailable until published', async () => {
  const {mountSetup}=await import('../../extension/setup.mjs');
  const elements=new Map();
  const document={getElementById(id){if(!elements.has(id))elements.set(id,{textContent:'',hidden:false,disabled:false,dataset:{},append(){},replaceChildren(){}});return elements.get(id);},createElement(){return {textContent:'',append(){}};}};
  const calls=[];
  const chrome={runtime:{id:'a'.repeat(32),getURL:p=>p,getPlatformInfo:async()=>({os:'mac',arch:'arm64'}),sendMessage:async m=>{calls.push(m);return {ok:false,error:'NATIVE_DISCONNECTED'};}}};
  await mountSetup(document,chrome,async()=>({json:async()=>({extensionId:null,downloads:[]})}));
  assert.deepEqual(calls,[{op:'setupCheck'}]);
  assert.equal(elements.get('connection').dataset.state,'missing');
  assert.equal(elements.get('find').disabled,true);
  assert.match(elements.get('availability').textContent,/not published/);
});

test('handshake exposes a bounded helper version without trusting arbitrary text', async () => {
  let receive;
  const port={onMessage:{addListener:fn=>receive=fn},onDisconnect:{addListener(){}},disconnect(){},postMessage(m){
    receive({v:1,id:m.id,ok:true,state:'idle',evidence:'none',capabilities:['hello'],helperVersion:'0.2.0'});
  }};
  const native=new Native(()=>port);
  assert.equal((await native.request('hello')).helperVersion,'0.2.0');
});
