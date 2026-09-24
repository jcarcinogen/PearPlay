import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {mountSetup} from '../../extension/setup.mjs';
test('setup action precedes casting steps and remains adjacent to warning',()=>{
 const html=readFileSync(new URL('../../extension/popup.html',import.meta.url),'utf8');
 assert.ok(html.indexOf('id="helperSetup"') < html.indexOf('<section>'));
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
