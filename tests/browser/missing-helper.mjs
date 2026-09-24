import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {chromeSession} from '../../scripts/chrome-session.mjs';
const c=await chromeSession({isolateHome:true,profileDirectory:'profile'});
try {
 const {id}=await c.send('Extensions.loadUnpacked',{path:resolve('extension')});
 // Document test: triggerAction currently stalls CDP on installed Chrome.
 // This does not claim real action-popup authorization coverage.
 await c.send('Target.createTarget',{url:`chrome-extension://${id}/popup.html`});
 let popup;
 for(let i=0;i<60;i++) {popup=(await c.send('Target.getTargets')).targetInfos.find(t=>t.url===`chrome-extension://${id}/popup.html`);if(popup)break;await delay(100);}
 assert.ok(popup,'popup document opens');
 const {sessionId:s}=await c.send('Target.attachToTarget',{targetId:popup.targetId,flatten:true});
 await c.send('Runtime.enable',{},s);
 let state;
 for(let i=0;i<100;i++) {state=await c.evaluate(s,`(()=>{const b=document.getElementById('helperSetup');return {text:b?.textContent,bottom:b?.getBoundingClientRect().bottom,height:innerHeight,warning:document.getElementById('banner')?.textContent}})()`);if(state.warning?.includes('cannot connect'))break;await delay(100);}
 assert.equal(state.text,'Helper setup');assert.ok(state.bottom<=state.height,JSON.stringify(state));
 await c.send('Target.createTarget',{url:`chrome-extension://${id}/setup.html`});
 let setup;
 for(let i=0;i<60;i++){setup=(await c.send('Target.getTargets')).targetInfos.find(t=>t.url===`chrome-extension://${id}/setup.html`);if(setup)break;await delay(100);}
 assert.ok(setup,'setup target exists');
 const {sessionId:t}=await c.send('Target.attachToTarget',{targetId:setup.targetId,flatten:true});
 await c.send('Runtime.enable',{},t);
 let kind;
 for(let i=0;i<100;i++){kind=await c.evaluate(t,"document.getElementById('connection')?.dataset.state");if(kind)break;await delay(100);}
 assert.equal(kind,'missing');
 const result=await c.evaluate(t,`(()=>{const p=document.getElementById('sourcePath');p.value="/home/test/Pear's folder";p.dispatchEvent(new Event('input'));return {command:document.getElementById('installCommand').textContent,hidden:document.getElementById('development').hidden,repairHidden:document.getElementById('packagedRepair').hidden,downloads:document.getElementById('downloads').children.length,copyDisabled:document.getElementById('copyCommand').disabled}})()`);
 assert.ok(result.command.includes(id));assert.equal(result.repairHidden,true);assert.equal(result.downloads,0);assert.equal(result.copyDisabled,false);
 if(process.platform==='linux')assert.equal(result.hidden,false);
 assert.equal(c.events.filter(e=>e.method==='Runtime.exceptionThrown').length,0);
 console.log(JSON.stringify({browser:c.version,popupDocumentOnly:true,setupButtonVisible:true,missingHelper:kind,runtimeIdInCommand:true,noDownloads:true,platform:process.platform}));
} finally {await c.close();}
