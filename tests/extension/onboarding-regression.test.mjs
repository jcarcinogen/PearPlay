import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {mountSetup} from '../../extension/setup.mjs';
test('setup retains platform security and separate connection/playback qualifications',()=>{
 const html=readFileSync(new URL('../../extension/setup.html',import.meta.url),'utf8');
 assert.match(html,/do not disable Gatekeeper or remove quarantine/i);
 assert.match(html,/do not disable SmartScreen or Defender/);
 assert.match(html,/do not disable package-signature checks/);
 assert.match(html,/connection check does not establish Mac TV playback/);
 assert.match(html,/connection check does not establish Windows TV playback/);
 assert.match(html,/Chrome and Brave share the Mac native-host registration/);
 assert.match(html,/DPAPI/);
});
test('unpublished Linux setup supplies actual runtime ID and no nonexistent app directions',async()=>{
 const nodes=new Map();
 const document={getElementById(id){if(!nodes.has(id)) nodes.set(id,{value:'/home/test/PearPlay',textContent:'',hidden:false,dataset:{},append(){}}); return nodes.get(id);},createElement(){return {};}};
 const chrome={runtime:{id:'b'.repeat(32),getURL:p=>p,getPlatformInfo:async()=>({os:'linux',arch:'x86-64'}),sendMessage:async()=>({ok:false,error:'NATIVE_DISCONNECTED'})}};
 await mountSetup(document,chrome,async()=>({json:async()=>({extensionId:null,downloads:[]})}));
 assert.equal(nodes.get('linux').hidden,true);
 assert.match(nodes.get('installCommand').textContent,/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/);
 assert.match(nodes.get('installCommand').textContent,/helper\/install.py/);
 assert.equal(nodes.get('packagedRepair').hidden,true);
 assert.doesNotMatch(nodes.get('connection').textContent,/open PearPlay Setup/);
});
