import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {downloadsFor} from '../../extension/setup-model.mjs';
import {mountSetup} from '../../extension/setup.mjs';

test('published Linux catalog offers the verified production packages without developer setup',async()=>{
  const catalog=JSON.parse(readFileSync(new URL('../../extension/releases.json',import.meta.url),'utf8'));
  const manifest=JSON.parse(readFileSync(new URL('../../extension/manifest.json',import.meta.url),'utf8'));
  const id='eoadahoncjfpnennmkjifohclbafjkol';
  assert.equal(catalog.extensionId,id);
  assert.equal(catalog.localInstallerTest,undefined);
  const downloads=downloadsFor(catalog,{os:'linux',arch:'x86-64'},id);
  assert.deepEqual(downloads.map(item=>item.format),['deb','pkg.tar.zst']);
  for(const item of downloads){
    assert.equal(item.url,`https://github.com/jcarcinogen/PearPlay/releases/download/v${manifest.version}/pearplay-helper-${manifest.version}-linux-x86_64.${item.format}`);
    assert.match(item.sha256,/^[a-f0-9]{64}$/);
  }
  assert.equal(downloadsFor(catalog,{os:'linux',arch:'arm64'},id).length,0);
  assert.equal(downloadsFor(catalog,{os:'mac',arch:'x86-64'},id).length,0);
  assert.equal(downloadsFor(catalog,{os:'linux',arch:'x86-64'},'a'.repeat(32)).length,0);
  const nodes=new Map();
  const document={getElementById(id){if(!nodes.has(id))nodes.set(id,{textContent:'',hidden:false,disabled:false,dataset:{},children:[],append(child){this.children.push(child);}});return nodes.get(id);},createElement(){return {};}};
  const html=readFileSync(new URL('../../extension/setup.html',import.meta.url),'utf8');
  assert.match(html,/Ubuntu 24\.04/);
  assert.match(html,/glibc 2\.44/);
  assert.match(html,/sudo pacman -U/);
  assert.doesNotMatch(html,/Ubuntu\/Debian, Fedora/);
  const calls=[];
  const chrome={runtime:{id,getURL:p=>p,getPlatformInfo:async()=>({os:'linux',arch:'x86-64'}),sendMessage:async message=>{calls.push(message.op);return {ok:false,error:'NATIVE_DISCONNECTED'};}}};
  await mountSetup(document,chrome,async()=>({json:async()=>catalog}));
  assert.deepEqual(calls,['setupCheck']);
  assert.equal(nodes.get('development').hidden,true);
  assert.equal(nodes.get('linux').hidden,false);
  assert.equal(nodes.get('downloads').children.length,2);
  assert.match(nodes.get('availability').textContent,/Choose the installer/);
  assert.equal(nodes.get('find').disabled,true);
});
