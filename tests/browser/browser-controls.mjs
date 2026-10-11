// Real decoded local MP4 + real popup/worker/content messaging. No TV/native host.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFileSync,writeFileSync,mkdirSync,cpSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {chromeSession} from '../../scripts/chrome-session.mjs';
const root=resolve(import.meta.dirname,'../..');
const output=resolve(process.env.PEARPLAY_UI_EVIDENCE);
mkdirSync(output,{recursive:true});
const media=readFileSync(process.env.PEARPLAY_TEST_MEDIA);
const server=createServer((req,res)=>{
 if(req.url==='/test.mp4'){
  const range=/bytes=(\d+)-(\d*)/.exec(req.headers.range??'');
  if(range){const a=Number(range[1]),b=range[2]?Math.min(Number(range[2]),media.length-1):media.length-1;res.writeHead(206,{'Content-Type':'video/mp4','Content-Range':`bytes ${a}-${b}/${media.length}`,'Accept-Ranges':'bytes','Content-Length':b-a+1});res.end(media.subarray(a,b+1));}
  else{res.writeHead(200,{'Content-Type':'video/mp4','Content-Length':media.length,'Accept-Ranges':'bytes'});res.end(media);}return;
 }
 res.writeHead(200,{'Content-Type':'text/html'});res.end('<!doctype html><title>PearPlay local playback test</title><h1>Local browser playback test</h1><video controls preload="auto" width="640" src="/test.mp4"></video>');
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const directMedia=process.env.PEARPLAY_DIRECT_MEDIA==='1';
const url=`http://127.0.0.1:${server.address().port}/${directMedia?'test.mp4':''}`;
let extension;
const c=await chromeSession({headless:false,prepare:temp=>{
 extension=join(temp,'extension');cpSync(join(root,'extension'),extension,{recursive:true});
 const manifest=JSON.parse(readFileSync(join(extension,'manifest.json')));manifest.key=JSON.parse(readFileSync(join(root,'tests/browser/fixture-key.json'))).key;writeFileSync(join(extension,'manifest.json'),JSON.stringify(manifest));
 const worker=readFileSync(join(extension,'worker.mjs'),'utf8');writeFileSync(join(extension,'worker.mjs'),worker.replace('com.pearplay.helper','com.pearplay.controls_test_absent'));
}});
const report={scope:'Real local generated MP4 decoded by installed Chrome; actual action popup, worker and content script. No real helper, TV, native playback or audible-sound owner claim.',checks:[]};
const attach=async targetId=>(await c.send('Target.attachToTarget',{targetId,flatten:true})).sessionId;
async function wait(s,expression,label){for(let i=0;i<120;i++){if(await c.evaluate(s,expression))return;await delay(50);}throw Error('Timeout: '+label+' '+JSON.stringify(await c.evaluate(s,"({url:location.href,text:document.body?.innerText})")));}
try{
 const {id}=await c.send('Extensions.loadUnpacked',{path:extension});
 const ui=await c.send('Target.createTarget',{url:'chrome://extensions'});const us=await attach(ui.targetId);await wait(us,'!!chrome.developerPrivate','extensions API');
 for(const host of ['http://*/*','https://*/*'])await c.evaluate(us,`chrome.developerPrivate.addHostPermission(${JSON.stringify(id)},${JSON.stringify(host)}).then(()=>true)`);
 for(const t of (await c.send('Target.getTargets')).targetInfos)if(t.type==='page'&&t.url.startsWith('chrome-extension://'))await c.send('Target.closeTarget',{targetId:t.targetId});
 const page=await c.send('Target.createTarget',{url});const ps=await attach(page.targetId);await c.send('Page.enable',{},ps);await wait(ps,'document.querySelector("video")?.readyState>=2 && document.querySelector("video").seekable.length>0','decoded MP4');
 // Chrome's generated direct-media document autoplays; normalize fixture state.
 await c.evaluate(ps,'(()=>{const v=document.querySelector("video");v.autoplay=false;v.removeAttribute("autoplay");v.pause();})()');
 await c.send('Page.bringToFront',{},ps);
 const videoTab=(await c.send('Target.getTargets',{filter:[{type:'tab'}]})).targetInfos.find(t=>t.url===url);
 await c.send('Extensions.triggerAction',{id,targetId:videoTab.targetId});
 let popup;for(let i=0;i<100;i++){popup=(await c.send('Target.getTargets')).targetInfos.find(t=>t.url===`chrome-extension://${id}/popup.html`);if(popup)break;await delay(50);}assert.ok(popup);
 const s=await attach(popup.targetId);await c.send('Page.enable',{},s);await wait(s,'document.readyState==="complete" && !!document.getElementById("enable").onclick','popup');
 const permissions=await c.evaluate(s,"chrome.permissions.request({origins:['http://*/*','https://*/*']})");assert.equal(permissions,true);
 await wait(s,'!document.getElementById("enable").disabled','Find enabled');
 await delay(300);
 await c.evaluate(s,'document.getElementById("enable").onclick()');
 await wait(s,'!document.getElementById("browserPlay").disabled','browser controls ready');
 const local=()=>c.evaluate(ps,'(()=>{const v=document.querySelector("video");return {paused:v.paused,muted:v.muted,time:v.currentTime,duration:v.duration,pip:document.pictureInPictureElement===v,frames:v.getVideoPlaybackQuality().totalVideoFrames}})()');
 const click=async name=>{assert.equal(await c.evaluate(s,`(()=>{const e=document.getElementById(${JSON.stringify(name)});if(e.disabled)return false;e.click();return true;})()`),true,name+' enabled');await delay(250);};
 await click('browserPlay');await wait(ps,'!document.querySelector("video").paused','play');const before=await local();await delay(700);const after=await local();assert.ok(after.time>before.time);assert.ok(after.frames>before.frames);report.checks.push({name:'play decoded advancing frames',before,after});
 await click('browserPlay');await wait(ps,'document.querySelector("video").paused','pause');const paused=await local();await delay(400);assert.equal((await local()).time,paused.time);report.checks.push({name:'pause',state:paused});
 await click('browserMute');assert.equal((await local()).muted,true);await click('browserMute');assert.equal((await local()).muted,false);report.checks.push({name:'mute and unmute',passed:true});
 async function seek(n){await c.evaluate(s,`(()=>{const e=document.getElementById('browserPosition');e.value=${n};e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));})()`);await wait(ps,`Math.abs(document.querySelector('video').currentTime-${n})<0.3`,'seek '+n);}
 await seek(40);report.checks.push({name:'timeline change commit',state:await local()});
 for(const n of [5,10,15,30]){
  await c.evaluate(s,`document.getElementById('browserJump').value='${n}';document.getElementById('browserJump').dispatchEvent(new Event('change'))`);
  await seek(40);await click('browserForward');assert.ok(Math.abs((await local()).time-(40+n))<.3);await click('browserBack');assert.ok(Math.abs((await local()).time-40)<.3);
  report.checks.push({name:'skip '+n+' both directions',passed:true});
 }
 await c.evaluate(s,"document.getElementById('browserPosition').focus()");const keyBefore=(await local()).time;await c.send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39},s);await c.send('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39},s);await delay(300);assert.ok((await local()).time>keyBefore);report.checks.push({name:'native slider keyboard seek',passed:true});
 const range=await c.evaluate(s,"document.getElementById('browserPosition').getBoundingClientRect().toJSON()");
 await c.send('Input.dispatchMouseEvent',{type:'mousePressed',x:range.x+range.width*.5,y:range.y+range.height/2,button:'left',clickCount:1},s);
 await c.send('Input.dispatchMouseEvent',{type:'mouseMoved',x:range.x+range.width*.7,y:range.y+range.height/2,button:'left',buttons:1},s);
 await c.send('Input.dispatchMouseEvent',{type:'mouseReleased',x:range.x+range.width*.7,y:range.y+range.height/2,button:'left',clickCount:1},s);
 await delay(300);assert.ok((await local()).time>55 && (await local()).time<70);report.checks.push({name:'native pointer timeline drag',state:await local()});
 await c.evaluate(ps,"document.querySelector('video').style.marginTop='2000px'");await click('browserReturn');assert.ok(await c.evaluate(ps,"document.querySelector('video').getBoundingClientRect().top<innerHeight"));report.checks.push({name:'return scrolls selected video into view',passed:true});
 await c.evaluate(s,"document.getElementById('browserPlay').focus()");await delay(2300);assert.equal(await c.evaluate(s,'document.activeElement.id'),'browserPlay');report.checks.push({name:'quiet polling preserves focus',passed:true});
 await click('browserPip');const pip=await local();const pipError=await c.evaluate(s,"document.getElementById('browserError').textContent");report.checks.push({name:'actual PiP entry',state:pip,error:pipError});assert.equal(pip.pip,true,'PiP must really enter');
 await click('browserPip');assert.equal((await local()).pip,false);report.checks.push({name:'PiP exit',passed:true});
 for(const theme of ['light','dark']){
  await c.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme}]},s);
  const geometry=await c.evaluate(s,'({width:document.body.scrollWidth,height:document.body.scrollHeight,viewport:innerWidth,body:document.body.getBoundingClientRect().toJSON(),html:document.documentElement.getBoundingClientRect().toJSON()})');assert.equal(geometry.viewport,400);assert.ok(geometry.width<=400);assert.ok(geometry.height<=600);
  const {data}=await c.send('Page.captureScreenshot',{format:'png'},s);writeFileSync(join(output,`actual-popup-${theme}.png`),Buffer.from(data,'base64'));report.checks.push({name:theme+' actual popup geometry',...geometry});
 }
 // Natural browser EOF must leave the same selected source usable for replay.
 const selectedBeforeEnd=await c.evaluate(s,"document.getElementById('candidate').value");
 assert.ok(selectedBeforeEnd);
 await seek((await local()).duration-1);await click('browserPlay');
 await wait(ps,"document.querySelector('video').ended",'natural media end');
 await delay(2300);
 assert.equal(await c.evaluate(s,"document.getElementById('candidate').value"),selectedBeforeEnd);
 assert.equal(await c.evaluate(s,"document.getElementById('browserPlay').getAttribute('aria-label')"),'Play browser video');
 await click('browserPlay');await wait(ps,"!document.querySelector('video').paused && document.querySelector('video').currentTime<5",'replay after end');
 await click('browserPlay');report.checks.push({name:'natural EOF keeps selection and permits replay',passed:true,directMedia});
 // Replace with a real Blob-backed MP4; browser controls must work but start must stay disabled.
 await c.evaluate(ps,"(async()=>{const v=document.querySelector('video');v.src=URL.createObjectURL(await (await fetch('/test.mp4')).blob());v.load();})()");
 await wait(ps,"document.querySelector('video').currentSrc.startsWith('blob:')&&document.querySelector('video').readyState>=2",'blob loaded');
 await c.evaluate(s,"document.getElementById('enable').click()");await delay(500);
 await c.evaluate(s,"(async()=>{const [tab]=await chrome.tabs.query({active:true,currentWindow:true});const view=await chrome.runtime.sendMessage({op:'view',tabId:tab.id});const e=document.getElementById('candidate');e.value=view.candidates.find(c=>c.videoId&&c.sendable===false)?.id??'';e.dispatchEvent(new Event('change'));})()");
 await wait(s,"!document.getElementById('browserPlay').disabled",'blob controls');await click('browserPlay');await wait(ps,"!document.querySelector('video').paused",'blob play');assert.equal(await c.evaluate(s,"document.getElementById('start').disabled"),true);report.checks.push({name:'real Blob playback',state:await local(),tvSendDisabled:true});
 // Synthetic native state into the real popup renderer; not receiver evidence.
 await c.evaluate(s,`(()=>{const original=chrome.runtime.sendMessage.bind(chrome.runtime);globalThis.testTVState='playing';chrome.runtime.sendMessage=async(...args)=>{const result=await original(...args);if(args[0]?.op==='view')result.native={...result.native,state:globalThis.testTVState,capabilities:['hello','status','stop']};return result;};})()`);
 await wait(s,"document.getElementById('browserControls').hidden && !document.getElementById('tvPlaybackNotice').hidden",'TV session notice instead of browser timeline');
 const tvGeometry=await c.evaluate(s,"({width:document.body.scrollWidth,height:document.body.scrollHeight,notice:document.getElementById('tvPlaybackNotice').textContent})");
 assert.ok(tvGeometry.width<=400&&tvGeometry.height<=600);assert.match(tvGeometry.notice,/TV remote/);
 const shot=await c.send('Page.captureScreenshot',{format:'png'},s);writeFileSync(join(output,'synthetic-tv-state.png'),Buffer.from(shot.data,'base64'));
 await c.evaluate(s,"globalThis.testTVState='stopped'");
 await wait(s,"!document.getElementById('browserControls').hidden && document.getElementById('tvPlaybackNotice').hidden",'browser controls return after session');
 report.checks.push({name:'synthetic TV state hides misleading browser timeline; stopped restores it',scope:'UI only, no real TV',...tvGeometry});
 assert.equal(c.events.filter(e=>e.method==='Runtime.exceptionThrown').length,0);report.browser=c.version;report.passed=true;
}finally{await c.close();await new Promise(r=>server.close(r));writeFileSync(join(output,'local-playback-results.json'),JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify(report,null,2));
