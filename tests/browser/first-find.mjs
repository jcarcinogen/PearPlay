// Real first-use action popup/worker/content/resource history; synthetic TVs only.
// PEARPLAY_FIRST_FIND_LIVE=1 uses FOX13 instead of the deterministic local fixture.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {cpSync,readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {join,resolve} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {chromeSession} from '../../scripts/chrome-session.mjs';
const root=resolve(import.meta.dirname,'../..');
const output=process.env.PEARPLAY_UI_EVIDENCE;
assert.ok(output,'PEARPLAY_UI_EVIDENCE required');mkdirSync(output,{recursive:true});
const live=process.env.PEARPLAY_FIRST_FIND_LIVE==='1';
let pageRequests=0,manifestRequests=0;
const server=createServer((req,res)=>{
 if(req.url==='/index.m3u8'){manifestRequests++;res.writeHead(200,{'Content-Type':'application/vnd.apple.mpegurl'});res.end('#EXTM3U\n#EXT-X-VERSION:3\n');return;}
 pageRequests++;res.writeHead(200,{'Content-Type':'text/html'});res.end(`<!doctype html><title>First Find fixture</title><video controls></video><script>(async()=>{await (await fetch('/index.m3u8')).text();const v=document.querySelector('video');v.src=URL.createObjectURL(new MediaSource());v.load();window.fixtureReady=true;})()</script>`);
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const url=live?'https://www.fox13seattle.com/live':`http://127.0.0.1:${server.address().port}/`;
let extension;
const c=await chromeSession({headless:false,prepare:temp=>{
 extension=join(temp,'extension');cpSync(process.env.PEARPLAY_TEST_EXTENSION||join(root,'extension'),extension,{recursive:true});
 // Default to an absent host. Exact-artifact mode preserves every byte;
 // its popup interception below refuses native operations before any action.
 if(process.env.PEARPLAY_EXACT_ARTIFACT!=='1') {
  const p=join(extension,'worker.mjs');writeFileSync(p,readFileSync(p,'utf8').replace('com.pearplay.helper','com.pearplay.first_find_absent'));
 }
}});
const report={scope:'Actual isolated browser action popup, worker, content script and ResourceTiming. Synthetic TV discovery/selection only; no native helper or TV playback.',live,browser:c.version,exactArtifact:process.env.PEARPLAY_EXACT_ARTIFACT==='1',checks:[]};
const attach=async id=>(await c.send('Target.attachToTarget',{targetId:id,flatten:true})).sessionId;
async function wait(s,expr,label){for(let i=0;i<300;i++){if(await c.evaluate(s,expr))return;await delay(100);}throw Error('Timeout: '+label);}
try{
 // Stream is requested before the extension is even loaded.
 const page=await c.send('Target.createTarget',{url});const ps=await attach(page.targetId);await c.send('Page.enable',{},ps);
 await wait(ps,`document.querySelector('video')?.currentSrc.startsWith('blob:') && performance.getEntriesByType('resource').some(e=>/\\.m3u8(?:[?#]|$)/i.test(e.name))`,'pre-existing blob and HLS');
 report.brave=await c.evaluate(ps,'navigator.brave?.isBrave().catch(()=>false) ?? false');
 const timeOrigin=await c.evaluate(ps,'performance.timeOrigin');
 report.checks.push({name:'pre-Find blob and historical HLS',passed:true});
 const {id}=await c.send('Extensions.loadUnpacked',{path:extension});
 const ui=await c.send('Target.createTarget',{url:'chrome://extensions'});const us=await attach(ui.targetId);await wait(us,'!!chrome.developerPrivate','permission API');
 for(const host of ['http://*/*','https://*/*'])await c.evaluate(us,`chrome.developerPrivate.addHostPermission(${JSON.stringify(id)},${JSON.stringify(host)}).then(()=>true)`);
 await delay(500);
 for(const t of (await c.send('Target.getTargets')).targetInfos)if(t.type==='page'&&t.url.startsWith('chrome-extension://'))await c.send('Target.closeTarget',{targetId:t.targetId});
 await c.send('Page.bringToFront',{},ps);
 const tab=(await c.send('Target.getTargets',{filter:[{type:'tab'}]})).targetInfos.find(t=>t.url===url);assert.ok(tab);
 await c.send('Extensions.triggerAction',{id,targetId:tab.targetId});
 let popup;for(let i=0;i<100;i++){popup=(await c.send('Target.getTargets')).targetInfos.find(t=>t.url===`chrome-extension://${id}/popup.html`);if(popup)break;await delay(50);}assert.ok(popup);
 const s=await attach(popup.targetId);await c.send('Page.enable',{},s);await wait(s,'!!document.getElementById("enable")?.onclick','popup initialization');
 assert.equal(await c.evaluate(s,"chrome.permissions.request({origins:['http://*/*','https://*/*']})"),true);
 // Leave discovery/selection synthetic; actual candidate discovery and popup
 // Send gating still run unchanged. Never dispatch start/native work.
 await c.evaluate(s,`(()=>{const original=chrome.runtime.sendMessage.bind(chrome.runtime);let receivers=[],receiver=null;chrome.runtime.sendMessage=async m=>{
 if(m.op==='discover'){receivers=[{identifier:'fixture-tv',label:'Fixture Apple TV',address:'192.168.1.90'},{identifier:'fixture-other',label:'Other fixture TV',address:'192.168.1.91'}];return {receivers};}
 if(m.op==='receiver'){receiver=m.id;return {ok:true};}
 if(['start','hello','status','pair','pairBegin'].includes(m.op))throw Error('Native operation forbidden in this test');
 const result=await original(m);if(m.op==='view'){result.native={state:'idle',error:null,evidence:'none',capabilities:['start','stop'],receivers};result.receiver=receiver;}return result;};})()`);
 await wait(s,'!document.getElementById("enable").disabled','permission refresh');await delay(300);
 await c.evaluate(s,'document.getElementById("enable").onclick()');
 await wait(s,`!!document.getElementById('candidate').value`,'initial video selection');
 const state=await c.evaluate(s,`(async()=>{const [t]=await chrome.tabs.query({active:true,currentWindow:true});return chrome.runtime.sendMessage({op:'view',tabId:t.id});})()`);
 assert.equal(state.candidates.find(x=>x.id===state.selected)?.sendable,true,'first selected candidate must be TV-sendable');
 assert.ok(state.candidates.some(x=>x.sendable===false),'blob remains available separately');
 await c.evaluate(s,'document.getElementById("discover").onclick()');
 await c.evaluate(s,`(()=>{const e=document.getElementById('receiver');e.value='fixture-tv';return e.onchange();})()`);
 await wait(s,'!document.getElementById("start").disabled','Send enabled without page refresh');
 assert.equal(await c.evaluate(ps,'performance.timeOrigin'),timeOrigin,'must not reload page');
 if(!live)assert.equal(manifestRequests,1,'no second fetch needed to detect manifest');
 report.checks.push({name:'Find videos → Find TVs → select TV enables Send without reload',passed:true,candidates:state.candidates});
 // A deliberately selected browser-only source must never be silently switched.
 const blob=state.candidates.find(x=>x.sendable===false);
 await c.evaluate(s,`(()=>{const e=document.getElementById('candidate');e.value=${JSON.stringify(blob.id)};return e.onchange();})()`);
 await c.evaluate(s,'document.getElementById("enable").onclick()');await delay(1500);
 assert.equal(await c.evaluate(s,'document.getElementById("candidate").value'),blob.id);
 assert.equal(await c.evaluate(s,'document.getElementById("start").disabled'),true);
 report.checks.push({name:'repeat Find preserves deliberate browser-only selection and blocked Send',passed:true});
 report.passed=true;
}finally{
 await c.close();await new Promise(r=>server.close(r));
 writeFileSync(join(output,'first-find-results.json'),JSON.stringify(report,null,2)+'\n');
}
console.log(JSON.stringify(report,null,2));
