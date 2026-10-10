import assert from 'node:assert/strict';
import {writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {chromeSession} from './chrome-session.mjs';
const kit='/Volumes/IronWolf/Stuff/PearPlay/Cross-platform Preview';
const c=await chromeSession();
try{
 const {targetId}=await c.send('Target.createTarget',{url:'about:blank'});
 const {sessionId:s}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 await c.send('Runtime.enable',{},s);await c.send('Page.enable',{},s);await c.send('Network.enable',{},s);
 await c.send('Emulation.setDeviceMetricsOverride',{width:1200,height:900,deviceScaleFactor:1,mobile:false},s);
 await c.send('Page.navigate',{url:pathToFileURL(kit+'/TV test checklist.html').href},s);
 for(let i=0;i<80;i++){if(await c.evaluate(s,"!!document.getElementById('download')"))break;await delay(50);}
 const count=await c.evaluate(s,"document.querySelectorAll('input[type=checkbox]').length");assert.ok(count>=25);
 await c.evaluate(s,"document.querySelector('input').click();document.getElementById('notes').value='Synthetic checklist persistence test';document.getElementById('notes').dispatchEvent(new Event('input'))");
 await c.send('Page.reload',{},s);await delay(300);
 assert.equal(await c.evaluate(s,"document.querySelector('input').checked"),true);
 assert.equal(await c.evaluate(s,"document.getElementById('notes').value"),'Synthetic checklist persistence test');
 const copied=await c.evaluate(s,"(async()=>{let result='';Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async t=>{result=t}}});await document.getElementById('copy').onclick();return result})()");
 assert.match(copied,/Synthetic checklist persistence test/);assert.match(copied,/\[x\]/);
 await c.evaluate(s,"localStorage.clear();location.reload()");await delay(300);
 const events=c.events.filter(e=>e.sessionId===s);
 assert.equal(events.filter(e=>e.method==='Runtime.exceptionThrown').length,0);
 assert.equal(events.filter(e=>e.method==='Network.requestWillBeSent'&&/^https?:/.test(e.params.request.url)).length,0);
 await c.send('Page.bringToFront',{},s);
 const image=await c.send('Page.captureScreenshot',{format:'png'},s);
 writeFileSync(kit+'/Evidence/checklist-browser.png',Buffer.from(image.data,'base64'));
 const report={browser:c.version,checkboxes:count,persistence:true,copyBoundaryInjected:true,consoleExceptions:0,remoteRequests:0,scope:'Checklist interface only; no TV observations'};
 writeFileSync(kit+'/Evidence/checklist-browser.json',JSON.stringify(report,null,2));console.log(report);
}finally{await c.close();}
