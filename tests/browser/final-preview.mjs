// Official Mac/Linux Chrome + exact extracted candidate ZIP, one owned profile, full restarts.
// No pairing/playback, daily profile access, fixture key/catalog changes or security overrides.
// PEARPLAY_EXTENSION must name a previously verified unchanged ZIP extraction. No fixture substitution.
import assert from 'node:assert/strict';
import {spawn,execFileSync} from 'node:child_process';
import {mkdtempSync,realpathSync,mkdirSync,readFileSync,writeFileSync,cpSync,existsSync,rmSync} from 'node:fs';
import {join,resolve} from 'node:path';
import {tmpdir} from 'node:os';
import {createHash} from 'node:crypto';
import {readdirSync} from 'node:fs';
import {setTimeout as delay} from 'node:timers/promises';

assert.ok(['darwin','linux'].includes(process.platform));
assert.ok(process.env.PEARPLAY_EXTENSION,'Set PEARPLAY_EXTENSION to the checksum-verified ZIP extraction; source fallback is forbidden');
const mac=process.platform==='darwin';
const binary=resolve(process.argv[2]);const output=resolve(process.argv[3]);
const chrome=mac?'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome':'/usr/bin/google-chrome-stable';
assert.ok(existsSync(binary)&&existsSync(chrome));
const root=realpathSync(mkdtempSync(join(tmpdir(),'pp-final-')));
const parent=join(root,'config');const profile=join(parent,mac?'Google/Chrome':'google-chrome');
const extension=join(root,'extension');const id='eoadahoncjfpnennmkjifohclbafjkol';
const extensionSource=resolve(process.env.PEARPLAY_EXTENSION);
cpSync(extensionSource,extension,{recursive:true});
assert.equal(JSON.parse(readFileSync(join(extension,'manifest.json'))).version,'0.3.0');
assert.equal(JSON.parse(readFileSync(join(extension,'releases.json'))).extensionId,id);
const host=join(profile,'NativeMessagingHosts/com.pearplay.helper.json');
function hashes(folder,prefix=''){
 const result={};
 for(const entry of readdirSync(folder,{withFileTypes:true})){
  const relative=prefix+entry.name;
  if(entry.isDirectory())Object.assign(result,hashes(join(folder,entry.name),relative+'/'));
  else if(entry.isFile())result[relative]=createHash('sha256').update(readFileSync(join(folder,entry.name))).digest('hex');
  else throw Error('Unexpected extension entry');
 }
 return result;
}
const report={scope:'Real headless official Chrome, unchanged exact-ZIP extraction, hello/status and setup page; no discovery, pairing or playback',extensionId:id,version:'0.3.0',extensionHashes:hashes(extension),helperBinarySha256:createHash('sha256').update(readFileSync(binary)).digest('hex'),phases:[]};
let child,ws;
async function stop(){
 const stopped=child&&child.exitCode===null?new Promise(r=>child.once('exit',r)):Promise.resolve();
 // Let Chrome flush and shut its owned children down before profile removal.
 if(ws){if(ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify({id:2147483000,method:'Browser.close'}));}
 if(child&&child.exitCode===null){
  await Promise.race([stopped,delay(5000)]);
  if(child.exitCode===null){child.kill('SIGTERM');await Promise.race([stopped,delay(5000)]);}
  if(child.exitCode===null){child.kill('SIGKILL');await stopped;}
 }
 if(ws){ws.close();ws=null;}
 child=null;
}
async function start(){
 mkdirSync(profile,{recursive:true});
 // Chrome must not inherit an earlier DevToolsActivePort pointer on restart.
 const pointer=join(profile,'DevToolsActivePort');if(existsSync(pointer))rmSync(pointer);
 const args=['--headless=new','--disable-gpu',`--user-data-dir=${profile}`,'--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--enable-unsafe-extension-debugging','--enable-automation','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','about:blank'];
 assert.ok(!args.includes('--no-sandbox'));
 child=spawn(chrome,args,{stdio:['ignore','ignore','ignore'],env:mac?process.env:{...process.env,HOME:join(root,'home'),XDG_CONFIG_HOME:join(root,'home/.config')}});
 for(let i=0;i<1800&&!existsSync(pointer)&&child.exitCode===null;i++)await delay(50);
 assert.ok(existsSync(pointer),'Owned official Chrome did not start');
 const [port,path]=readFileSync(pointer,'utf8').trim().split('\n');
 ws=new WebSocket(`ws://127.0.0.1:${port}${path}`);
 await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 let serial=0;const pending=new Map();
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error(`${p.method} failed`)):p.resolve(m.result);}}};
 const send=(method,params={},sessionId)=>new Promise((r,j)=>{const n=++serial;const timer=setTimeout(()=>{pending.delete(n);j(Error(`${method} timeout`));},60000);pending.set(n,{resolve:r,reject:j,timer,method});ws.send(JSON.stringify({id:n,method,params,...(sessionId?{sessionId}:{})}));});
 const evaluate=async(sessionId,expression)=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true,userGesture:true},sessionId);assert.ok(!r.exceptionDetails,'Controlled extension evaluation failed');return r.result.value;};
 const version=await send('Browser.getVersion');report.browser=version.product;
 const command=await send('Browser.getBrowserCommandLine');assert.ok(!command.arguments.includes('--no-sandbox'));report.sandboxDisabled=false;
 const loaded=await send('Extensions.loadUnpacked',{path:extension});assert.equal(loaded.id,id);
 if(!mac){
  const sandbox=await send('Target.createTarget',{url:'chrome://sandbox'});
  const attached=await send('Target.attachToTarget',{targetId:sandbox.targetId,flatten:true});
  let text='';for(let i=0;i<100;i++){text=await evaluate(attached.sessionId,'document.body?.innerText ?? ""');if(text.includes('Seccomp'))break;await delay(100);}
  assert.match(text,/Layer 1 Sandbox\s+Namespace/i);assert.match(text,/Seccomp-BPF sandbox\s+Yes/i);report.sandboxPage=text;
  await send('Target.closeTarget',{targetId:sandbox.targetId});
 }
 const {targetId}=await send('Target.createTarget',{url:`chrome-extension://${id}/setup.html`});
 const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
 await send('Runtime.enable',{},sessionId);
 await send('Emulation.setDeviceMetricsOverride',{width:900,height:1000,deviceScaleFactor:1,mobile:false},sessionId);
 let state;
 for(let i=0;i<600;i++){
  state=await evaluate(sessionId,"({kind:document.getElementById('connection')?.dataset.state,text:document.getElementById('connection')?.textContent,findDisabled:document.getElementById('find')?.disabled})");
  if(state.kind)break;await delay(100);
 }
 const links=await evaluate(sessionId,"[...document.querySelectorAll('#downloads a')].map(a=>a.href)");
 const catalog=JSON.parse(readFileSync(join(extension,'releases.json')));
 assert.notEqual(catalog.localInstallerTest,true);
 assert.ok(links.length>0);for(const link of links)assert.ok(JSON.stringify(catalog).includes(link));
 if(mac){assert.equal(links.length,1);assert.match(links[0],/pearplay-helper-0\.3\.1-darwin-arm64-development\.pkg$/);}
 report.renderedDownloads=links;
 const native=op=>evaluate(sessionId,`new Promise(resolve=>{const p=chrome.runtime.connectNative('com.pearplay.helper');p.onMessage.addListener(m=>{p.disconnect();resolve(m)});p.onDisconnect.addListener(()=>resolve({missing:true,error:chrome.runtime.lastError?.message}));p.postMessage({v:1,id:'mac_preview_${op}',op:${JSON.stringify(op)},args:{}})})`);
 return {state,native,send,evaluate,sessionId};
}
function register(action){
 return JSON.parse(execFileSync(binary,[action,'--browsers',...(mac?['chrome','brave']:['chrome']),'--config-parent',parent],{encoding:'utf8',timeout:15000}));
}
try{
 for(const phase of ['missing','ready','ready-restart','removed']){
  if(phase==='ready'){
   assert.deepEqual(register('connect'),mac?{chrome:'connected',brave:'connected'}:{chrome:'connected'});
   assert.deepEqual(register('connect'),mac?{chrome:'connected',brave:'connected'}:{chrome:'connected'});
   const manifest=JSON.parse(readFileSync(host,'utf8'));
   assert.equal(manifest.path,binary);assert.deepEqual(manifest.allowed_origins,[`chrome-extension://${id}/`]);
   report.registeredPath=binary;report.repairChecked=true;
  }
  if(phase==='removed'){
   assert.deepEqual(register('remove'),mac?{chrome:'removed',brave:'removed'}:{chrome:'removed'});assert.equal(existsSync(host),false);
  }
  const c=await start();
  const ready=phase.startsWith('ready');assert.equal(c.state.kind,ready?'ready':'missing');
  assert.equal(c.state.findDisabled,!ready);
  const hello=await c.native('hello');
  if(ready){
   assert.equal(hello.ok,true);assert.equal(hello.helperVersion,'0.3.0');
   const status=await c.native('status');assert.equal(status.ok,true);assert.equal(status.state,'idle');
   report.phases.push({phase,setup:c.state.kind,helperVersion:hello.helperVersion,status:status.state});

  }else{
   assert.equal(hello.missing,true);assert.match(hello.error,/not found/i);
   report.phases.push({phase,setup:c.state.kind,missingHostError:hello.error});
  }
  await stop();
 }
 assert.deepEqual(hashes(extension),report.extensionHashes);
 assert.deepEqual(hashes(extensionSource),report.extensionHashes);
 report.removalVerified=true;report.dailyProfilesUntouched=true;report.passed=true;
}finally{
 await stop();
 if(existsSync(host))register('remove');
 rmSync(root,{recursive:true});assert.equal(existsSync(root),false);
 report.ownedProfileRemoved=true;
 mkdirSync(resolve(output,'..'),{recursive:true});writeFileSync(output,JSON.stringify(report,null,2)+'\n');
}
console.log(JSON.stringify(report,null,2));
