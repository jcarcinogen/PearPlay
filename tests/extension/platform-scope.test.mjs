import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {downloadsFor} from '../../extension/setup-model.mjs';
import {mountSetup} from '../../extension/setup.mjs';

const id='eoadahoncjfpnennmkjifohclbafjkol';
const url=format=>`https://github.com/jcarcinogen/PearPlay/releases/download/v0.2.8/helper.${format}`;
const matrix=[['linux','x86-64',['deb','rpm','pkg.tar.zst']],['mac','arm64',['pkg']],['mac','x86-64',['pkg']],['win','x86-64',['exe','zip']]];
function dom(){
  const html=readFileSync(new URL('../../extension/setup.html',import.meta.url),'utf8');
  const nodes=new Map([...html.matchAll(/id="([^"]+)"/g)].map(([,key])=>[key,{textContent:'',value:'',hidden:false,disabled:false,dataset:{},children:[],append(child){this.children.push(child);}}]));
  return {nodes,document:{getElementById(key){assert.ok(nodes.has(key),`setup.html must contain ${key}`);return nodes.get(key);},createElement(tag){return {tag,textContent:''};}}};
}
async function mount(platform,catalog,result={ok:true,helperVersion:'0.2.8',capabilities:['hello','discover','start']}){
  const view=dom(),calls=[];let fetches=0;
  const chrome={runtime:{id,getURL:p=>p,getPlatformInfo:async()=>platform,sendMessage:async m=>{calls.push(m);return m.op==='setupFind'?{ok:true,receivers:[{label:'Example TV'}]}:result;}}};
  await mountSetup(view.document,chrome,async()=>{fetches++;return {json:async()=>catalog};});
  return {...view,calls,fetches};
}
for(const [os,arch,formats] of matrix)test(`download matrix: ${os}/${arch} only accepts its formats`,()=>{
  const entries=['deb','rpm','pkg.tar.zst','pkg','exe','zip','tar.gz'].map(format=>({os,arch,format,url:url(format)}));
  const selected=downloadsFor({extensionId:id,downloads:entries},{os,arch},id);
  assert.deepEqual(selected.map(i=>i.format),formats);
  assert.deepEqual(downloadsFor({extensionId:id,downloads:entries},{os,arch:arch==='arm64'?'x86-64':'arm64'},id),[]);
  assert.deepEqual(downloadsFor({extensionId:'a'.repeat(32),downloads:entries},{os,arch},id),[]);
  assert.deepEqual(downloadsFor({extensionId:'bad',downloads:entries},{os,arch},'bad'),[]);
});
for(const bad of ['http://github.com/jcarcinogen/PearPlay/releases/download/v0.2.8/helper.pkg','https://github.com.evil.test/jcarcinogen/PearPlay/releases/download/v0.2.8/helper.pkg','https://github.com:444/jcarcinogen/PearPlay/releases/download/v0.2.8/helper.pkg','https://user@github.com/jcarcinogen/PearPlay/releases/download/v0.2.8/helper.pkg','https://github.com/other/PearPlay/releases/download/v0.2.8/helper.pkg','https://github.com/jcarcinogen/PearPlay/releases/tag/v0.2.8','https://github.com/jcarcinogen/PearPlay/releases/download/v0.2.8/helper.pkg?redirect=1','https://github.com/jcarcinogen/PearPlay/releases/download/v0.2.8/helper.pkg#download','not a URL'])test(`reject untrusted download: ${bad}`,()=>{
  assert.deepEqual(downloadsFor({extensionId:id,downloads:[{os:'mac',arch:'arm64',format:'pkg',url:bad}]},{os:'mac',arch:'arm64'},id),[]);
});
for(const os of ['linux','mac','win'])test(`mounted ${os} setup checks once; discovery requires a deliberate click`,async()=>{
  const arch=os==='mac'?'arm64':'x86-64',format={linux:'deb',mac:'pkg',win:'exe'}[os];
  const item={os,arch,format,url:url(format)};
  const {nodes,calls,fetches}=await mount({os,arch},{extensionId:id,downloads:[item]});
  assert.equal(fetches,1);assert.deepEqual(calls,[{op:'setupCheck'}]);
  assert.equal(nodes.get('connection').dataset.state,'ready');assert.equal(nodes.get('find').disabled,false);
  assert.equal(nodes.get('downloads').children.length,1);assert.equal(nodes.get('downloads').children[0].href,item.url);
  for(const section of ['linux','mac','win'])assert.equal(nodes.get(section).hidden,section!==os);
  assert.equal(nodes.get('linuxWarning').hidden,os!=='linux');
  await nodes.get('find').onclick();assert.deepEqual(calls,[{op:'setupCheck'},{op:'setupFind'}]);assert.match(nodes.get('receivers').textContent,/Example TV/);
  await nodes.get('check').onclick();assert.deepEqual(calls,[{op:'setupCheck'},{op:'setupFind'},{op:'setupCheck'}]);
});
for(const os of ['mac','win'])test(`unpublished ${os} does not fabricate links or Linux commands`,async()=>{
  const {nodes,calls}=await mount({os,arch:os==='mac'?'arm64':'x86-64'},{extensionId:id,downloads:[]},{ok:false,error:'NATIVE_DISCONNECTED'});
  assert.equal(nodes.get('downloads').children.length,0);assert.match(nodes.get('availability').textContent,/not published/);
  assert.equal(nodes.get('development').hidden,true);assert.equal(nodes.get(os).hidden,false);
  assert.equal(nodes.get('find').disabled,true);await nodes.get('find').onclick();assert.deepEqual(calls,[{op:'setupCheck'}]);
});
test('release catalog selects verified installers by platform, without a rehearsal flag',async()=>{
  const catalog=JSON.parse(readFileSync(new URL('../../extension/releases.json',import.meta.url)));
  assert.equal(catalog.extensionId,id);assert.equal(Object.hasOwn(catalog,'localInstallerTest'),false);
  assert.equal(downloadsFor(catalog,{os:'mac',arch:'arm64'},id)[0].format,'pkg');
  assert.equal(downloadsFor(catalog,{os:'win',arch:'x86-64'},id)[0].format,'exe');
  assert.deepEqual(downloadsFor(catalog,{os:'mac',arch:'x86-64'},id),[]);
  const linux=downloadsFor(catalog,{os:'linux',arch:'x86-64'},id);assert.equal(linux.length,3);
  for(const item of catalog.downloads)assert.match(item.sha256,/^[a-f0-9]{64}$/);
  for(const item of linux) assert.ok(item.url.startsWith(`https://github.com/jcarcinogen/PearPlay/releases/download/v${'0.3.3'}/`));
});
for(const os of ['cros','android','openbsd','unknown'])test(`unsupported OS ${os} cannot fetch catalog or request native/discovery`,async()=>{
  const {nodes,calls,fetches}=await mount({os,arch:'x86-64'},{extensionId:id,downloads:[]});
  assert.equal(fetches,0);assert.deepEqual(calls,[]);assert.equal(nodes.get('installSection').hidden,true);assert.equal(nodes.get('browserSection').hidden,true);
  assert.equal(nodes.get('check').disabled,true);assert.equal(nodes.get('find').disabled,true);
});
for(const os of ['linux','win'])test(`${os} ARM is not offered an incompatible helper`,async()=>{
  const item={os,arch:'arm64',format:os==='linux'?'deb':'exe',url:url('exe')};
  assert.deepEqual(downloadsFor({extensionId:id,downloads:[item]},{os,arch:'arm64'},id),[]);
  const {nodes}=await mount({os,arch:'arm64'},{extensionId:id,downloads:[item],localInstallerTest:true});
  assert.match(nodes.get('availability').textContent,/architecture/);assert.equal(nodes.get('development').hidden,true);assert.equal(nodes.get(os).hidden,true);
});
