// Official Mac Chrome + packaged helper, one owned profile, full restarts.
// No pairing/playback, daily profile access, fixture key/catalog changes or security overrides.
// PEARPLAY_LIVE_DISCOVERY=1 opts into one read-only native discovery on the ready phase.
import assert from 'node:assert/strict';
import {spawn,execFileSync} from 'node:child_process';
import {mkdtempSync,realpathSync,mkdirSync,readFileSync,writeFileSync,cpSync,existsSync,rmSync} from 'node:fs';
import {join,resolve} from 'node:path';
import {tmpdir} from 'node:os';
import {createHash} from 'node:crypto';
import {readdirSync} from 'node:fs';
import {setTimeout as delay} from 'node:timers/promises';

assert.equal(process.platform,'darwin');
const binary=resolve(process.argv[2]);const output=resolve(process.argv[3]);
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
assert.ok(existsSync(binary)&&existsSync(chrome));
const root=realpathSync(mkdtempSync(join(tmpdir(),'pp-mac-')));
const parent=join(root,'config');const profile=join(parent,'Google/Chrome');
const extension=join(root,'extension');const id='eoadahoncjfpnennmkjifohclbafjkol';
const extensionSource=resolve(process.env.PEARPLAY_EXTENSION || 'extension');
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
const report={scope:'Real headless official Mac Chrome hello/status and setup page; optional explicitly recorded read-only discovery; no pairing or playback',extensionId:id,version:'0.3.0',extensionHashes:hashes(extension),phases:[]};
let child,ws;
async function stop(){
 if(ws){ws.close();ws=null;}
 if(child&&child.exitCode===null){
  const stopped=new Promise(r=>child.once('exit',r));child.kill('SIGTERM');
  await Promise.race([stopped,delay(5000)]);
  if(child.exitCode===null){child.kill('SIGKILL');await stopped;}
 }
 child=null;
}
async function start(){
 mkdirSync(profile,{recursive:true});
 // Chrome must not inherit an earlier DevToolsActivePort pointer on restart.
 const pointer=join(profile,'DevToolsActivePort');if(existsSync(pointer))rmSync(pointer);
 const args=['--headless=new','--disable-gpu',`--user-data-dir=${profile}`,'--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--enable-unsafe-extension-debugging','--enable-automation','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','about:blank'];
 assert.ok(!args.includes('--no-sandbox'));
 child=spawn(chrome,args,{stdio:['ignore','ignore','ignore'],env:process.env});
 for(let i=0;i<300&&!existsSync(pointer)&&child.exitCode===null;i++)await delay(50);
 assert.ok(existsSync(pointer),'Owned official Chrome did not start');
 const [port,path]=readFileSync(pointer,'utf8').trim().split('\n');
 ws=new WebSocket(`ws://127.0.0.1:${port}${path}`);
 await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 let serial=0;const pending=new Map();
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error(`${p.method} failed`)):p.resolve(m.result);}}};
 const send=(method,params={},sessionId)=>new Promise((r,j)=>{const n=++serial;const timer=setTimeout(()=>{pending.delete(n);j(Error(`${method} timeout`));},method==='Runtime.evaluate'&&process.env.PEARPLAY_LIVE_DISCOVERY==='1'?35000:20000);pending.set(n,{resolve:r,reject:j,timer,method});ws.send(JSON.stringify({id:n,method,params,...(sessionId?{sessionId}:{})}));});
 const evaluate=async(sessionId,expression)=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true,userGesture:true},sessionId);assert.ok(!r.exceptionDetails,'Controlled extension evaluation failed');return r.result.value;};
 const version=await send('Browser.getVersion');report.browser=version.product;
 const command=await send('Browser.getBrowserCommandLine');assert.ok(!command.arguments.includes('--no-sandbox'));report.sandboxDisabled=false;
 const loaded=await send('Extensions.loadUnpacked',{path:extension});assert.equal(loaded.id,id);
 const {targetId}=await send('Target.createTarget',{url:`chrome-extension://${id}/setup.html`});
 const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
 await send('Runtime.enable',{},sessionId);
 await send('Emulation.setDeviceMetricsOverride',{width:900,height:1000,deviceScaleFactor:1,mobile:false},sessionId);
 let state;
 for(let i=0;i<200;i++){
  state=await evaluate(sessionId,"({kind:document.getElementById('connection')?.dataset.state,text:document.getElementById('connection')?.textContent,findDisabled:document.getElementById('find')?.disabled})");
  if(state.kind)break;await delay(100);
 }
 const native=op=>evaluate(sessionId,`new Promise(resolve=>{const p=chrome.runtime.connectNative('com.pearplay.helper');p.onMessage.addListener(m=>{p.disconnect();resolve(m)});p.onDisconnect.addListener(()=>resolve({missing:true,error:chrome.runtime.lastError?.message}));p.postMessage({v:1,id:'mac_preview_${op}',op:${JSON.stringify(op)},args:{}})})`);
 return {state,native,send,evaluate,sessionId};
}
function register(action){
 return JSON.parse(execFileSync(binary,[action,'--browsers','chrome','brave','--config-parent',parent],{encoding:'utf8',timeout:15000}));
}
try{
 for(const phase of ['missing','ready','ready-restart','removed']){
  if(phase==='ready'){
   assert.deepEqual(register('connect'),{chrome:'connected',brave:'connected'});
   assert.deepEqual(register('connect'),{chrome:'connected',brave:'connected'});
   const manifest=JSON.parse(readFileSync(host,'utf8'));
   assert.equal(manifest.path,binary);assert.deepEqual(manifest.allowed_origins,[`chrome-extension://${id}/`]);
   report.registeredPath=binary;report.repairChecked=true;
  }
  if(phase==='removed'){
   assert.deepEqual(register('remove'),{chrome:'removed',brave:'removed'});assert.equal(existsSync(host),false);
  }
  const c=await start();
  const ready=phase.startsWith('ready');assert.equal(c.state.kind,ready?'ready':'missing');
  assert.equal(c.state.findDisabled,!ready);
  const hello=await c.native('hello');
  if(ready){
   assert.equal(hello.ok,true);assert.equal(hello.helperVersion,'0.3.0');
   const status=await c.native('status');assert.equal(status.ok,true);assert.equal(status.state,'idle');
   report.phases.push({phase,setup:c.state.kind,helperVersion:hello.helperVersion,status:status.state});
   if(phase==='ready' && process.env.PEARPLAY_LIVE_DISCOVERY==='1'){
    const discovery=await c.native('discover');
    report.readOnlyChromeDiscovery={ok:discovery.ok===true,receiverCount:Array.isArray(discovery.receivers)?discovery.receivers.length:0,error:['discovery_failed','busy','NATIVE_TIMEOUT'].includes(discovery.error)?discovery.error:discovery.ok?'none':'unclassified',scope:'Native discover through isolated Chrome; no PIN, credentials or media sent'};
   }
  }else{
   assert.equal(hello.missing,true);assert.match(hello.error,/not found/i);
   report.phases.push({phase,setup:c.state.kind,missingHostError:hello.error});
  }
  await stop();
 }
 assert.deepEqual(hashes(extension),report.extensionHashes);
 report.removalVerified=true;report.dailyProfilesUntouched=true;
}finally{
 await stop();
 if(existsSync(host))register('remove');
 rmSync(root,{recursive:true});assert.equal(existsSync(root),false);
 report.ownedProfileRemoved=true;
 mkdirSync(resolve(output,'..'),{recursive:true});writeFileSync(output,JSON.stringify(report,null,2)+'\n');
}
console.log(JSON.stringify(report,null,2));
