// Store captures: real popup DOM with synthetic selections/session; no TV actions.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync,cpSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {chromeSession} from './chrome-session.mjs';
const root=resolve(import.meta.dirname,'..');
const output=resolve(process.env.PEARPLAY_UI_OUTPUT);
mkdirSync(output,{recursive:true});
let extension;
const c=await chromeSession({prepare:temp=>{
 extension=join(temp,'extension');cpSync(join(root,'extension'),extension,{recursive:true});
 const manifest=JSON.parse(readFileSync(join(extension,'manifest.json')));
 manifest.key=JSON.parse(readFileSync(join(root,'tests/browser/fixture-key.json'))).key;
 writeFileSync(join(extension,'manifest.json'),JSON.stringify(manifest));
 const worker=readFileSync(join(extension,'worker.mjs'),'utf8');
 assert.ok(worker.includes('com.pearplay.helper'));
 writeFileSync(join(extension,'worker.mjs'),worker.replace('com.pearplay.helper','com.pearplay.ui_test_absent'));
}});
const report={scope:'Actual 0.3.0 popup DOM; synthetic example selections and accepted-session state. No receiver/playback evidence. Dedicated isolated profile; production native host excluded.',captures:[]};
try{
 const {id}=await c.send('Extensions.loadUnpacked',{path:extension});
 for(const theme of ['light','dark']){
  const {targetId}=await c.send('Target.createTarget',{url:'about:blank'});
  const {sessionId:s}=await c.send('Target.attachToTarget',{targetId,flatten:true});
  await c.send('Page.enable',{},s);await c.send('Runtime.enable',{},s);
  await c.send('Emulation.setDeviceMetricsOverride',{width:400,height:600,deviceScaleFactor:1,mobile:false},s);
  await c.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme},{name:'prefers-reduced-motion',value:'reduce'}]},s);
  await c.send('Page.addScriptToEvaluateOnNewDocument',{source:readFileSync(join(root,'tests/browser/brand-fixture.js'),'utf8')},s);
  const url=`chrome-extension://${id}/popup.html`;
  await c.send('Page.navigate',{url},s);await c.send('Page.bringToFront',{},s);
  for(let i=0;i<120;i++){
   if(await c.evaluate(s,`location.href===${JSON.stringify(url)}&&document.readyState==='complete'&&!!__fixture?.calls.some(x=>x.op==='discover')`))break;
   assert.notEqual(i,119,'popup load timeout');await delay(50);
  }
  await c.send('Page.bringToFront',{},s);
  await c.evaluate(s,`Object.assign(__fixture.view.native,{state:'connecting',evidence:'unverified',session:{receiver:'example-receiver',host:'192.0.2.10',transport:'airplay-v1',delivery:'accepted',timingRequired:false}});document.getElementById('status').click()`);
  for(let i=0;i<100;i++){
   if(await c.evaluate(s,"!document.getElementById('sessionControls').hidden&&document.getElementById('phase').textContent.startsWith('Sent')"))break;
   assert.notEqual(i,99,'session controls did not appear: '+JSON.stringify(await c.evaluate(s,"({phase:document.getElementById('phase').textContent,text:document.getElementById('tvStatus').textContent,sessionHidden:document.getElementById('sessionControls').hidden,view:__fixture.view.native})")));await delay(50);
  }
  await c.send('Page.bringToFront',{},s);
  await c.evaluate(s,'document.fonts.ready.then(()=>Promise.all([...document.images].map(i=>i.decode()))).then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))');
  const geometry=await c.evaluate(s,`({width:document.body.scrollWidth,height:document.body.scrollHeight,controls:['start','stop'].map(id=>{const e=document.getElementById(id),r=e.getBoundingClientRect();return {id,text:e.textContent,visible:!!e.getClientRects().length,bottom:r.bottom};}),phase:document.getElementById('phase').textContent})`);
  assert.ok(geometry.width<=400&&geometry.height<=600);
  assert.deepEqual(geometry.controls.map(e=>e.text),['Send to TV','End helper session']);
  assert.ok(geometry.controls.every(e=>e.visible&&e.bottom<=600));
  const {data}=await c.send('Page.captureScreenshot',{format:'png',clip:{x:0,y:0,width:400,height:geometry.height,scale:1}},s);
  const name=`popup-${theme}-viewport.png`;
  writeFileSync(join(root,'assets/store',name),Buffer.from(data,'base64'));
  writeFileSync(join(output,name),Buffer.from(data,'base64'));
  report.captures.push({name,theme,...geometry});
  await c.send('Target.closeTarget',{targetId});
 }
 report.browser=c.version;report.passed=true;
}finally{await c.close();writeFileSync(join(output,'popup-capture-verification.json'),JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify(report,null,2));
