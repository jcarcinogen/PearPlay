import test from 'node:test';import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';import vm from 'node:vm';
const read=p=>readFile(new URL(`../../extension/${p}`,import.meta.url),'utf8');
test('local-only stop is not labeled as confirmed TV control',async()=>{
 const html=await read('popup.html');
 assert.match(html,/<button id="stop">End helper session<\/button>/);
 assert.match(html,/does not confirm that the TV stopped/i);
 assert.match(html,/physical remote/i);
});
test('MV3 popup requests optional access on clicks, never renders URLs, explicit candidate and receiver',async()=>{
 const manifest=JSON.parse(await read('manifest.json'));assert.equal(manifest.manifest_version,3);assert.equal(manifest.background.service_worker,'worker.mjs');assert.equal(manifest.background.type,'module');assert.deepEqual(manifest.optional_host_permissions,['http://*/*','https://*/*']);assert.ok(!manifest.host_permissions);for(const p of ['activeTab','scripting','webNavigation','webRequest','nativeMessaging','alarms','storage'])assert.ok(manifest.permissions.includes(p));
 const html=await read(manifest.action.default_popup);assert.match(html,/popup.js/);assert.match(html,/Find videos/);assert.match(html,/Find Apple TVs/);assert.match(html,/Send to Apple TV/);assert.match(html,/Choose a video/);assert.match(html,/Choose an Apple TV/);assert.match(html,/Connect helper/);assert.match(html,/cannot find your Apple TV/i);assert.match(html,/id="banner"/);assert.match(html,/id="tvStatus"/);assert.ok(html.indexOf('id="discover"')<html.indexOf('id="tvStatus"')&&html.indexOf('id="tvStatus"')<html.indexOf('id="hostDetails"'));assert.doesNotMatch(html,/>Candidate</);assert.match(html,/reload/i);assert.match(html,/TV video and audio/i);assert.ok(html.indexOf('id="grantAll"')<html.indexOf('id="enable"'));assert.match(html,/1\. Allow all websites/);assert.match(html,/2\. Find videos/);
 const elements=new Map([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],{value:'',textContent:'',disabled:false,replaceChildren(){},append(){},addEventListener(){}}]));const actions=[];let requests=0;
 const document={getElementById:id=>elements.get(id),createElement:()=>({})};
 const chrome={tabs:{query:async()=>[{id:1,url:'https://site.test/path?secret=x'}],reload:async()=>actions.push('reload')},permissions:{request:async opts=>{requests++;actions.push(opts);return true;}},runtime:{sendMessage:async m=>{actions.push(m);if(m.op==='view')return {enabled:true,candidates:[{id:'c1',label:'Candidate c1'}],native:{state:'idle',evidence:'none',receivers:[],capabilities:[]}};return {scanned:1,total:2};}}};
 await vm.runInNewContext(await read('popup.js'),{document,chrome,URL,setInterval(){},clearInterval(){}});await new Promise(r=>setImmediate(r));assert.equal(requests,0);
 await elements.get('grantAll').onclick();assert.equal(requests,1);assert.deepEqual(Array.from(actions.find(a=>a.origins).origins),['http://*/*','https://*/*']);
 assert.equal(elements.get('candidate').value,'c1');assert.equal(elements.get('receiver').value,'');
 await elements.get('confirmTV').onclick();assert.ok(actions.some(a=>a.op==='localPause'&&a.confirmed===true));
 assert.equal([...elements.values()].some(e=>String(e.textContent).includes('secret')),false);
});
