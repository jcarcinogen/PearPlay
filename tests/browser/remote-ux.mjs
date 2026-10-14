// Actual Chrome action popup and production UI scripts, synthetic API responses.
// Fixture-only native host name prevents touching a real helper or sleeping TV.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync,cpSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {chromeSession} from '../../scripts/chrome-session.mjs';
const root=resolve(import.meta.dirname,'../..');
const output=process.env.PEARPLAY_UI_EVIDENCE;
if(!output)throw Error('PEARPLAY_UI_EVIDENCE must name an owned evidence directory');
mkdirSync(output,{recursive:true});
let extension;
const c=await chromeSession({headless:false,prepare:temp=>{
 extension=join(temp,'extension');cpSync(join(root,'extension'),extension,{recursive:true});
 const manifest=JSON.parse(readFileSync(join(extension,'manifest.json')));
 manifest.key=JSON.parse(readFileSync(join(root,'tests/browser/fixture-key.json'))).key;
 writeFileSync(join(extension,'manifest.json'),JSON.stringify(manifest));
 const worker=readFileSync(join(extension,'worker.mjs'),'utf8');
 assert.ok(worker.includes('com.pearplay.helper'));
 writeFileSync(join(extension,'worker.mjs'),worker.replace('com.pearplay.helper','com.pearplay.remote_ux_absent'));
 writeFileSync(join(extension,'fixture.js'),readFileSync(join(root,'tests/browser/brand-fixture.js'),'utf8'));
 const html=readFileSync(join(extension,'popup.html'),'utf8');
 writeFileSync(join(extension,'popup.html'),html.replace('<script src="browser-controls.js">','<script src="fixture.js"></script>\n<script src="browser-controls.js">'));
}});
const results=[];
try{
 const {id}=await c.send('Extensions.loadUnpacked',{path:extension});
 // Let the owned install/setup target appear before choosing the target tab.
 for(let i=0;i<60;i++){
  const all=(await c.send('Target.getTargets')).targetInfos;
  const setup=all.find(t=>t.url===`chrome-extension://${id}/setup.html`);
  if(setup){await c.send('Target.closeTarget',{targetId:setup.targetId});break;}
  await delay(50);
 }
 const {targetId}=await c.send('Target.createTarget',{url:'about:blank'});
 await c.send('Target.activateTarget',{targetId});
 const tabs=(await c.send('Target.getTargets',{filter:[{type:'tab'}]})).targetInfos;
 const tab=tabs.find(t=>t.url==='about:blank')??tabs.at(-1);assert.ok(tab);
 await c.send('Extensions.triggerAction',{id,targetId:tab.targetId});
 let popup;
 for(let i=0;i<100&&!popup;i++){
  popup=(await c.send('Target.getTargets')).targetInfos.find(t=>t.url===`chrome-extension://${id}/popup.html`);if(!popup)await delay(50);
 }
 assert.ok(popup,'actual action popup target');
 const {sessionId}=await c.send('Target.attachToTarget',{targetId:popup.targetId,flatten:true});
 await c.send('Runtime.enable',{},sessionId);await c.send('Page.enable',{},sessionId);
 for(let i=0;i<100;i++){
  if(await c.evaluate(sessionId,`!!window.__fixture && document.getElementById('phase')?.textContent==='Ready'`))break;
  await delay(50);
 }
 const initial=await c.evaluate(sessionId,`({view:__fixture.view,calls:__fixture.calls})`);
 assert.ok(initial.calls.some(m=>m.op==='view'));assert.equal(initial.calls.some(m=>['hello','discover'].includes(m.op)),false);
 const baseline=initial.view;
 baseline.native.helperVersion='0.3.3';
 const token='a'.repeat(32);
 const scenarios=[
 ['ready',{}],
 ['playing',{native:{state:'playing',evidence:'protocol',capabilities:['start','stop','pause','resume'],tvControl:{session:token,receiver:'example-receiver'},tvTimeline:{session:token,receiver:'example-receiver',position:65,duration:180,ageMs:20,canSeek:false}},activeCast:{title:'Original film on TV',receiverId:'example-receiver',receiverName:'Living Room',sourceAvailable:true,browserMuted:false}}],
 ['paused',{native:{state:'paused',evidence:'protocol',capabilities:['start','stop','pause','resume'],tvControl:{session:token,receiver:'example-receiver'},tvTimeline:{session:token,receiver:'example-receiver',position:65,duration:180,ageMs:20,canSeek:false}},activeCast:{title:'Original film on TV',receiverId:'example-receiver',receiverName:'Living Room',sourceAvailable:true,browserMuted:true}}],
 ['unknown-duration',{native:{state:'playing',evidence:'protocol',capabilities:['start','stop','pause','resume'],tvControl:{session:token,receiver:'example-receiver'},tvTimeline:{session:token,receiver:'example-receiver',position:200,duration:null,ageMs:20,canSeek:false}},activeCast:{title:'Live video',sourceAvailable:false}}],
 ['old-helper',{native:{helperVersion:'0.3.1'}}],
 ['disconnected',{native:{state:'error',error:'NATIVE_DISCONNECTED',capabilities:[]}}],
 ['permission',{allowed:false}],
 ['empty',{candidates:[],selected:null}],
 ['error',{native:{state:'error',error:'transport_failed',diagnostic:{stage:'await-playing',reason:'timeout'}}}],
 ];
 for(const palette of ['light','dark']){
  await c.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:palette}]},sessionId);
  for(const [name,delta]of scenarios){
   const state={...structuredClone(baseline),...delta,native:{...baseline.native,...delta.native}};
   await c.evaluate(sessionId,`__fixture.view=${JSON.stringify(state)};__fixture.allowed=${delta.allowed!==false};window.__before=__fixture.calls.filter(x=>x.op==='view').length`);
   for(let i=0;i<100;i++){
    if(await c.evaluate(sessionId,`__fixture.calls.filter(x=>x.op==='view').length>__before`))break;
    await delay(50);
   }
   await delay(60);
   const metrics=await c.evaluate(sessionId,`(()=>{const e=id=>document.getElementById(id);return {width:innerWidth,htmlWidth:document.documentElement.scrollWidth,bodyWidth:document.body.scrollWidth,height:document.body.scrollHeight,phase:e('phase').textContent,title:e('identity').textContent,timelineHidden:e('tvTimeline').hidden,pauseHidden:e('pause').hidden,resumeHidden:e('resume').hidden,progressTag:e('tvProgress').tagName,sendHidden:e('start').hidden,muteHidden:e('castAudio').hidden,helperHint:e('helperCompatibility').hidden,recover:e('recover').textContent}})()`);
   results.push({name,palette,...metrics});
   writeFileSync(join(output,'attempt.json'),JSON.stringify({browser:c.version,results},null,2));
   if(metrics.width!==400 || metrics.height>600){const shot=await c.send('Page.captureScreenshot',{format:'png'},sessionId);writeFileSync(join(output,'layout-failure.png'),Buffer.from(shot.data,'base64'));}
   assert.equal(metrics.width,400);assert.equal(metrics.htmlWidth,400);assert.equal(metrics.bodyWidth,400);assert.ok(metrics.height<=600,`${name} exceeds 600px: ${metrics.height}`);
   if(['playing','paused'].includes(name)){
    assert.equal(metrics.title,'Original film on TV');assert.equal(metrics.timelineHidden,false);assert.equal(metrics.progressTag,'PROGRESS');assert.equal(metrics.sendHidden,true);assert.equal(metrics.muteHidden,false);
    assert.equal(metrics.pauseHidden,name==='paused');assert.equal(metrics.resumeHidden,name==='playing');
   }
   if(name==='old-helper')assert.equal(metrics.helperHint,false);
   if(name==='playing'){
    await c.evaluate(sessionId,`document.getElementById('pause').focus()`);
    await delay(2200);assert.equal(await c.evaluate(sessionId,`document.activeElement.id`),'pause','quiet polling retains focus');
    await c.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},sessionId);
    await c.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},sessionId);
    assert.equal(await c.evaluate(sessionId,`document.activeElement.id`),'stop');
   }
   const {data}=await c.send('Page.captureScreenshot',{format:'png'},sessionId);
   writeFileSync(join(output,`${name}-${palette}.png`),Buffer.from(data,'base64'));
  }
 }
 const errors=c.events.filter(e=>e.method==='Runtime.exceptionThrown');assert.equal(errors.length,0);
 writeFileSync(join(output,'results.json'),JSON.stringify({passed:true,browser:c.version,scope:'Real action popup geometry/keyboard and production scripts; synthetic API responses, not receiver or helper evidence',results},null,2));
 console.log(JSON.stringify({passed:true,browser:c.version,scenarios:results.length,output}));
}finally{await c.close();}
