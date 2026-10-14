// Real Chrome popup -> worker -> content script/source identity; synthetic native transport.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFileSync,writeFileSync,mkdirSync,cpSync} from 'node:fs';
import {join,resolve} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {chromeSession} from '../../scripts/chrome-session.mjs';
const root=resolve(import.meta.dirname,'../..'),output=process.env.PEARPLAY_UI_EVIDENCE;
assert.ok(output);mkdirSync(output,{recursive:true});
const media=readFileSync(process.env.PEARPLAY_TEST_MEDIA);
const server=createServer((req,res)=>{
 if(req.url==='/test.mp4'){const range=/bytes=(\d+)-(\d*)/.exec(req.headers.range??'');if(range){const a=+range[1],b=range[2]?Math.min(+range[2],media.length-1):media.length-1;res.writeHead(206,{'Content-Type':'video/mp4','Content-Range':`bytes ${a}-${b}/${media.length}`,'Content-Length':b-a+1,'Accept-Ranges':'bytes'});res.end(media.subarray(a,b+1));}else{res.writeHead(200,{'Content-Type':'video/mp4','Content-Length':media.length,'Accept-Ranges':'bytes'});res.end(media);}return;}
 res.writeHead(200,{'Content-Type':'text/html'});res.end(`<!doctype html><title>${req.url==='/other'?'Other page':'Original film'}</title><video controls preload="auto" src="/test.mp4"></video>`);
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base=`http://127.0.0.1:${server.address().port}`;
const fixture=`export class FixtureNative {
 constructor(){this.listeners=[];this.state={state:'idle',error:null,evidence:'none',helperVersion:'0.3.3',capabilities:['hello','status','discover','start','stop'],receivers:[{identifier:'fixture-tv',label:'Fixture TV',address:'192.0.2.10'}]};}
 view(){return structuredClone(this.state)}
 onChange(f){this.listeners.push(f)}
 async request(op,args={}){
  if(!['hello','status','discover','start','stop','pause','resume'].includes(op))throw Error('Forbidden fixture operation');
  if(op==='start'){this.state.state='playing';this.state.evidence='protocol';this.state.capabilities=['hello','status','discover','start','stop','pause','resume'];this.state.tvControl={receiver:args.receiver,session:'a'.repeat(32)};this.state.tvTimeline={...this.state.tvControl,position:65,duration:180,ageMs:0,canSeek:false};}
  if(op==='pause')this.state.state='paused';if(op==='resume')this.state.state='playing';
  if(op==='stop'){this.state.state='stopped';this.state.tvControl=null;this.state.tvTimeline=null;}
  this.listeners.forEach(f=>f());return this.view();
 }
}`;
let extension;
const c=await chromeSession({headless:false,prepare:temp=>{
 extension=join(temp,'extension');cpSync(join(root,'extension'),extension,{recursive:true});
 const manifest=JSON.parse(readFileSync(join(extension,'manifest.json')));manifest.key=JSON.parse(readFileSync(join(root,'tests/browser/fixture-key.json'))).key;writeFileSync(join(extension,'manifest.json'),JSON.stringify(manifest));
 const path=join(extension,'worker.mjs'),worker=readFileSync(path,'utf8');
 assert.ok(worker.includes('if(globalThis.chrome?.runtime?.id)createWorker(globalThis.chrome);'));
 writeFileSync(path,`import {FixtureNative} from './fixture-native.mjs';\n`+worker.replace('com.pearplay.helper','com.pearplay.cast_fixture_absent').replace('if(globalThis.chrome?.runtime?.id)createWorker(globalThis.chrome);','if(globalThis.chrome?.runtime?.id)createWorker(globalThis.chrome,new FixtureNative());'));
 writeFileSync(join(extension,'fixture-native.mjs'),fixture);
}});
const report={scope:'Real Chrome/action popup/worker/content script and decoded source video. Native transport is synthetic, no helper or TV contact.',checks:[]};
const attach=async id=>(await c.send('Target.attachToTarget',{targetId:id,flatten:true})).sessionId;
async function wait(s,expr,label){for(let i=0;i<150;i++){if(await c.evaluate(s,expr))return;await delay(70);}throw Error('Timeout '+label);}
try{
 const {id}=await c.send('Extensions.loadUnpacked',{path:extension});
 const ui=await c.send('Target.createTarget',{url:'chrome://extensions'}),us=await attach(ui.targetId);await wait(us,'!!chrome.developerPrivate','permission api');
 for(const host of ['http://*/*','https://*/*'])await c.evaluate(us,`chrome.developerPrivate.addHostPermission(${JSON.stringify(id)},${JSON.stringify(host)}).then(()=>true)`);
 for(const t of (await c.send('Target.getTargets')).targetInfos)if(t.url.startsWith('chrome-extension://')&&t.type==='page')await c.send('Target.closeTarget',{targetId:t.targetId});
 const page=await c.send('Target.createTarget',{url:base+'/original'}),ps=await attach(page.targetId);await c.send('Page.enable',{},ps);await wait(ps,'document.querySelector("video")?.readyState>=2','decoded video');
 async function openPopup(pageSession,url){
  await c.send('Page.bringToFront',{},pageSession);const tab=(await c.send('Target.getTargets',{filter:[{type:'tab'}]})).targetInfos.find(t=>t.url===url);assert.ok(tab);
  await c.send('Extensions.triggerAction',{id,targetId:tab.targetId});let pop;
  for(let i=0;i<100;i++){pop=(await c.send('Target.getTargets')).targetInfos.find(t=>t.url===`chrome-extension://${id}/popup.html`);if(pop)break;await delay(50);}assert.ok(pop);
  const s=await attach(pop.targetId);await wait(s,'!!document.getElementById("enable")?.onclick','popup handlers');return {s,id:pop.targetId};
 }
 let popup=await openPopup(ps,base+'/original'),s=popup.s;
 assert.equal(await c.evaluate(s,"chrome.permissions.request({origins:['http://*/*','https://*/*']})"),true);await wait(s,'!document.getElementById("enable").disabled','Find enabled');await delay(150);
 await c.evaluate(s,'document.getElementById("enable").onclick()');
 await wait(s,'!!document.getElementById("candidate").value','selected source');
 await c.evaluate(s,'document.getElementById("discover").onclick()');await wait(s,'!document.getElementById("start").disabled','Send enabled');
 await c.evaluate(s,'document.getElementById("start").onclick()');await wait(s,'!document.getElementById("pause").hidden && !document.getElementById("tvTimeline").hidden','TV controls');
 assert.equal(await c.evaluate(ps,'document.querySelector("video").muted'),false,'no automatic mute');
 assert.equal(await c.evaluate(s,'chrome.action.getBadgeText({})'),'TV');
 const originalTitle=await c.evaluate(s,'document.getElementById("identity").textContent');
 await c.send('Target.closeTarget',{targetId:popup.id});
 const other=await c.send('Target.createTarget',{url:base+'/other'}),os=await attach(other.targetId);await c.send('Page.enable',{},os);await wait(os,'document.querySelector("video")?.readyState>=2','other video');
 popup=await openPopup(os,base+'/other');s=popup.s;await wait(s,'!document.getElementById("castAudio").hidden','global cast');
 assert.equal(await c.evaluate(s,'document.getElementById("identity").textContent'),originalTitle);
 assert.equal(await c.evaluate(s,'document.getElementById("candidate").hidden'),true);
 await c.evaluate(s,'document.getElementById("castMute").onclick()');
 assert.equal(await c.evaluate(ps,'document.querySelector("video").muted'),true);assert.equal(await c.evaluate(os,'document.querySelector("video").muted'),false);
 report.checks.push('reopened from another tab retains title and mutes only original exact video');
 await c.evaluate(s,'document.getElementById("pause").onclick()');assert.equal(await c.evaluate(s,'chrome.action.getBadgeText({})'),'Ⅱ');await wait(s,'!document.getElementById("resume").hidden','resume visible');
 report.checks.push('synthetic native pause updates actual toolbar badge and capability-gated popup');
 await c.send('Page.navigate',{url:base+'/replacement'},ps);await wait(ps,'location.pathname==="/replacement" && !!document.querySelector("video")','replacement document');
 await wait(s,'document.getElementById("castAudio").hidden','source invalidated');
 assert.equal(await c.evaluate(s,'document.getElementById("resume").hidden'),false);
 assert.equal(await c.evaluate(ps,'document.querySelector("video").muted'),false,'replacement untouched');
 report.checks.push('original tab navigation revokes browser audio but preserves TV remote');
 await c.evaluate(s,'document.getElementById("stop").onclick()');await wait(s,'document.getElementById("sessionControls").hidden','ended');assert.equal(await c.evaluate(s,'chrome.action.getBadgeText({})'),'');
 report.checks.push('ending clears global cast and badge without changing either page audio');
 assert.equal(c.events.filter(e=>e.method==='Runtime.exceptionThrown').length,0);report.browser=c.version;report.passed=true;
}finally{await c.close();await new Promise(r=>server.close(r));writeFileSync(join(output,'cast-context-results.json'),JSON.stringify(report,null,2));}
console.log(JSON.stringify(report,null,2));
