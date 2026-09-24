import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {downloadsFor} from '../../extension/setup-model.mjs';
import {mountSetup} from '../../extension/setup.mjs';

function dom(){
  const nodes=new Map();
  return {nodes,document:{getElementById(id){if(!nodes.has(id))nodes.set(id,{textContent:'',hidden:false,disabled:false,dataset:{},append(){throw Error('Unexpected download');}});return nodes.get(id);},createElement(){return {};}}};
}
test('Mac download entries stay unavailable even in a matching legacy catalog',()=>{
  const catalog={extensionId:'a'.repeat(32),downloads:['pkg','tar.gz'].map(format=>({os:'mac',arch:'arm64',format,url:`https://github.com/jcarcinogen/PearPlay/releases/download/v0.2.3/helper.${format}`}))};
  assert.deepEqual(downloadsFor(catalog,{os:'mac',arch:'arm64'},catalog.extensionId),[]);
});
test('Mac setup shows coming soon without downloads, install steps or native requests',async()=>{
  const {nodes,document}=dom();let fetches=0;const calls=[];
  const chrome={runtime:{id:'a'.repeat(32),getPlatformInfo:async()=>({os:'mac',arch:'arm64'}),getURL:p=>p,sendMessage:async m=>{calls.push(m);return {helperVersion:'0.2.3',capabilities:['hello','discover','start']};}}};
  await mountSetup(document,chrome,async()=>{fetches++;return {json:async()=>({extensionId:chrome.runtime.id,localInstallerTest:true,downloads:[]})};});
  assert.equal(fetches,0);assert.deepEqual(calls,[]);
  assert.match(nodes.get('platform').textContent,/Mac support is coming soon\./);
  assert.equal(nodes.get('installSection').hidden,true);
  assert.equal(nodes.get('browserSection').hidden,true);
  assert.equal(nodes.get('check').disabled,true);assert.equal(nodes.get('find').disabled,true);
});
test('Mac popup does not request site access or connect an old installed helper',async()=>{
  const {nodes,document}=dom();
  const chrome={runtime:{getPlatformInfo:async()=>({os:'mac'}),getURL:p=>p,sendMessage(){throw Error('Native request on Mac');}},tabs:{query(){throw Error('Tab query on Mac');}}};
  const source=readFileSync(new URL('../../extension/popup.js',import.meta.url),'utf8');
  await vm.runInNewContext(source,{document,chrome});
  assert.equal(nodes.get('casting').hidden,true);
  assert.match(nodes.get('platformNotice').textContent,/Mac support is coming soon\./);
});
