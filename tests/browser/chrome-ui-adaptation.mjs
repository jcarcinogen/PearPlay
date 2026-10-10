// Real installed Chrome, owned disposable profile. Actual popup HTML/JS are unchanged.
// Synthetic replies are explicitly labeled; no helper installation or LAN/TV calls.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {readFileSync,writeFileSync,mkdirSync,cpSync} from 'node:fs';
import {join,resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {chromeSession} from '../../scripts/chrome-session.mjs';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const output=process.env.PEARPLAY_UI_EVIDENCE||'/Volumes/IronWolf/Stuff/PearPlay/Cross-platform Preview/UI';
mkdirSync(output,{recursive:true});
let extension;
const c=await chromeSession({headless:false,prepare:temp=>{
 extension=join(temp,'extension');cpSync(join(root,'extension'),extension,{recursive:true});
 const manifest=JSON.parse(readFileSync(join(extension,'manifest.json')));manifest.key=JSON.parse(readFileSync(join(root,'tests/browser/fixture-key.json'))).key;
 writeFileSync(join(extension,'manifest.json'),JSON.stringify(manifest));
 // Missing-host negative control: avoid invoking Scott's installed production host.
 const worker=readFileSync(join(extension,'worker.mjs'),'utf8');
 writeFileSync(join(extension,'worker.mjs'),worker.replace('com.pearplay.helper','com.pearplay.ui_test_absent'));
}});
const evidence={browser:c.version,scope:'Actual isolated action popup + missing-host negative control; synthetic UI/handler states, NOT native helper/TV or Linux/Windows runtime acceptance',states:[],actions:[]};
evidence.sourceHashes={};
for(const file of ['popup.html','popup.js','content.js','core.mjs','native.mjs']){
 const canonical=readFileSync(join(root,'extension',file));const installed=readFileSync(join(extension,file));assert.deepEqual(installed,canonical,file+' installed bytes');
 evidence.sourceHashes[file]=createHash('sha256').update(installed).digest('hex');
}
evidence.isolationChanges=['Disposable manifest uses dedicated public fixture key','Disposable worker native-host name is com.pearplay.ui_test_absent (deliberately unregistered)','Popup HTML/JS, content/core and native protocol module are byte-identical to source'];
async function attach(targetId){const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});await c.send('Runtime.enable',{},sessionId);await c.send('Page.enable',{},sessionId);return sessionId;}
async function wait(s,expression){for(let i=0;i<150;i++){if(await c.evaluate(s,expression))return;await delay(40)}throw Error('Timed out waiting for '+expression);}
async function click(s,id){const p=await c.evaluate(s,`(()=>{const r=document.getElementById('${id}').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);await c.send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...p},s);await c.send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...p},s);}
async function capture(s,name){await c.evaluate(s,`Promise.all([...document.images].map(i=>i.decode().catch(()=>{}))).then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))`);const m=await c.evaluate(s,`({width:document.body.scrollWidth,height:document.body.scrollHeight,viewportWidth:innerWidth,viewportHeight:innerHeight,sendBottom:document.getElementById('start').getBoundingClientRect().bottom,sendDisabled:document.getElementById('start').disabled,phase:document.getElementById('phase').textContent,helpOpen:document.getElementById('helpDetails').open,logo:{width:document.querySelector('header img').width,filter:getComputedStyle(document.querySelector('header img')).filter}})`);const {data}=await c.send('Page.captureScreenshot',{format:'png',clip:{x:0,y:0,width:400,height:Math.min(m.height,600),scale:1}},s);writeFileSync(join(output,name+'.png'),Buffer.from(data,'base64'));return m;}
try{
 const {id}=await c.send('Extensions.loadUnpacked',{path:extension});evidence.fixtureExtensionId=id;
 // Diagnostic only: chrome://sandbox is not supported on every platform.
 const {targetId:sandbox}=await c.send('Target.createTarget',{url:'chrome://sandbox'});const sb=await attach(sandbox);await wait(sb,`document.readyState==='complete'`);evidence.sandbox=await c.evaluate(sb,`document.body.innerText`);await c.send('Target.closeTarget',{targetId:sandbox});
 // Real toolbar action target, no API substitutions.
 const {targetId:tab}=await c.send('Target.createTarget',{url:'https://example.invalid/pearplay-ui'});const ts=await attach(tab);await c.send('Page.bringToFront',{},ts);
 const tabs=(await c.send('Target.getTargets',{filter:[{type:'tab'}]})).targetInfos;const tabTarget=tabs.find(t=>t.targetId===tab)||tabs.find(t=>t.url==='https://example.invalid/pearplay-ui');
 assert.ok(tabTarget,'actual browser tab target');
 await c.send('Extensions.triggerAction',{id,targetId:tabTarget.targetId});
 let popup;
 for(let i=0;i<100;i++){popup=(await c.send('Target.getTargets')).targetInfos.find(t=>t.url===`chrome-extension://${id}/popup.html`);if(popup)break;await delay(50)}
 assert.ok(popup,'toolbar action popup target exists');const ps=await attach(popup.targetId);
 await c.send('Page.bringToFront',{},ps);
 evidence.actionStartup=await c.evaluate(ps,`(async()=>({visibility:document.visibilityState,ready:document.readyState,phase:document.getElementById('phase')?.textContent,setup:document.getElementById('helperSetup')?.textContent,platform:await chrome.runtime.getPlatformInfo()}))()`);
 await wait(ps,`document.readyState==='complete'&&document.getElementById('helperSetup').textContent==='Finish setup'`);
 evidence.actualAction=await capture(ps,'actual-action-missing-helper');assert.equal(evidence.actualAction.width,400);assert.ok(evidence.actualAction.height<=600);assert.ok(evidence.actualAction.viewportWidth<=400&&evidence.actualAction.viewportHeight<=600);assert.equal(evidence.actualAction.sendDisabled,true);
 await click(ps,'helperSetup');await delay(200);
 evidence.actualSetupOpened=(await c.send('Target.getTargets')).targetInfos.some(t=>t.url===`chrome-extension://${id}/setup.html`);assert.equal(evidence.actualSetupOpened,true);
 await c.send('Target.closeTarget',{targetId:popup.targetId}).catch(()=>{});
 // Synthetic boundaries from here: actual installed popup HTML/JS in an extension tab.
 const {targetId}=await c.send('Target.createTarget',{url:'about:blank'});const s=await attach(targetId);
 await c.send('Emulation.setDeviceMetricsOverride',{width:400,height:600,deviceScaleFactor:1,mobile:false},s);
 const fixture=readFileSync(join(root,'tests/browser/brand-fixture.js'),'utf8')+`\n(()=>{
 const f=__fixture;f.dispatches=[];f.requests=[];f.gates={};f.releases={};f.failNext={};
 f.holdOp=op=>{f.gates[op]=new Promise(r=>f.releases[op]=r)};
 f.releaseOp=op=>{delete f.gates[op];f.releases[op]();delete f.releases[op]};
 chrome.runtime.getPlatformInfo=async()=>({os:'mac',arch:'arm64'});
 const real=chrome.runtime.sendMessage;
 chrome.runtime.sendMessage=async m=>{
  // Count requests at entry, separately from deferred fixture processing.
  f.requests.push(m.op==='pair'?{op:'pair'}:structuredClone(m));
  const snapshot=m.op==='view'?structuredClone(f.view):null;
  if(m.op==='view'&&f.holdView){f.calls.push({op:'view-held'});await new Promise(r=>f.releaseView=r)}
  if(f.gates[m.op]){f.calls.push({op:m.op+'-held'});await f.gates[m.op]}
  const failure=f.failNext[m.op];delete f.failNext[m.op];
  if(failure==='before'){f.calls.push(structuredClone(m));return {ok:false,error:'ACTION_FAILED'}}
  if(m.op==='start')f.dispatches.push({selected:f.view.selected,receiver:f.view.receiver,url:f.view.candidates.find(c=>c.id===f.view.selected)?.url});
  const reply=await real(m);
  if(failure==='after')throw Error('NATIVE_DISCONNECTED');
  return m.op==='view'?snapshot:reply;
 };
 chrome.permissions.request=async args=>{f.calls.push({op:'grant',...args});if(f.denyGrant)return false;f.allowed=true;return true};
 })();`;
 await c.send('Page.addScriptToEvaluateOnNewDocument',{source:fixture},s);
 async function ready(state,scheme){await c.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},s);await c.send('Page.navigate',{url:`chrome-extension://${id}/popup.html?ui=${state}-${scheme}`},s);await c.send('Page.bringToFront',{},s);await wait(s,`location.search==='?ui=${state}-${scheme}'&&document.readyState==='complete'&&!!window.__fixture?.calls.some(x=>x.op==='discover')`);await delay(80);}
 const scenarios={ready:'',missing:`__fixture.view.native.error='NATIVE_DISCONNECTED';__fixture.view.native.capabilities=[]`,permission:`__fixture.allowed=false`,pin:`__fixture.view.native.error='pairing_required'`,error:`Object.assign(__fixture.view.native,{state:'error',error:'transport_failed',diagnostic:{stage:'await-playing',reason:'timeout'}})`,sent:`Object.assign(__fixture.view.native,{state:'connecting',evidence:'unverified',session:{delivery:'accepted',timingRequired:false}})`,playing:`__fixture.view.native.state='playing'`,empty:`__fixture.view.candidates=[];__fixture.view.selected=null`,changed:`__fixture.view.selected=null;__fixture.view.selectionLost=true;__fixture.view.candidates=[{id:'replacement',label:'Another video'}]`};
 for(const scheme of ['light','dark'])for(const [state,setup]of Object.entries(scenarios)){
  await ready(state,scheme);if(setup){await c.evaluate(s,setup);await delay(2150)}
  if(state==='pin'){await click(s,'pairRestart');await wait(s,`!document.getElementById('pairBox').hidden`);}
  const m=await capture(s,`${state==='missing'?'missing-helper':state==='permission'?'no-permission':state}-${scheme}`);
  assert.equal(m.width,400,state+' width');assert.ok(m.height<=600,state+' height '+m.height);assert.ok(m.sendBottom<=600,state+' send visibility');assert.equal(m.helpOpen,false,state+' collapsed help');assert.deepEqual(m.logo,{width:32,filter:'none'});
  if(state==='pin')assert.equal(await c.evaluate(s,`document.getElementById('pairBox').hidden`),false);
  if(state==='changed')assert.equal(await c.evaluate(s,`__fixture.calls.some(m=>m.op==='select')`),false);
  evidence.states.push({state,scheme,...m});
 }
 // Explicit failed-session fixture, actual controls and mouse events. No TV.
 await ready('pair-retry','light');
 await c.evaluate(s,`(()=>{const original=chrome.runtime.sendMessage;const f=__fixture;f.openPair=false;f.pairSuccess=false;f.begins=0;chrome.runtime.sendMessage=async m=>{
 if(m.op==='pairBegin'){f.begins++;f.openPair=true;f.view.native.error=null;return {ok:true};}
 if(m.op==='pair'){const error=!f.openPair?'pairing_required':f.pairSuccess?null:'pairing_failed';f.openPair=false;f.view.native.error=error;return error?{ok:false,error}:{ok:true};}
 return original(m);};f.view.native.error='pairing_required';})()`);
 await wait(s,`!document.getElementById('pairRestart').hidden`);
 assert.equal(await c.evaluate(s,`__fixture.begins`),0);
 for(let attempt=0;attempt<2;attempt++){
  await click(s,'pairRestart');await wait(s,`!document.getElementById('pairBox').hidden`);
  await c.evaluate(s,`document.getElementById('pin').value='0000'`);await click(s,'pair');
  await wait(s,`document.getElementById('pairBox').hidden&&!document.getElementById('pairRestart').hidden`);
  assert.equal(await c.evaluate(s,`document.getElementById('pin').value`),'');
  await delay(2150);assert.equal(await c.evaluate(s,`__fixture.begins`),attempt+1);
 }
 for(const scheme of ['light','dark']){
  await c.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},s);
  const m=await capture(s,`pair-retry-${scheme}`);assert.ok(m.height<=600);
 }
 await c.evaluate(s,`__fixture.pairSuccess=true`);await click(s,'pairRestart');await wait(s,`!document.getElementById('pairBox').hidden`);
 await c.evaluate(s,`document.getElementById('pin').value='0000'`);await click(s,'pair');
 await wait(s,`!document.getElementById('start').hidden`);assert.equal(await c.evaluate(s,`__fixture.begins`),3);
 assert.equal(await c.evaluate(s,`__fixture.calls.some(m=>m.op==='start')`),false);
 evidence.actions.push('Failed PIN → deliberate new PIN → repeated failure → deliberate new PIN → success; masked input cleared, no automatic begin or Send (synthetic replies, real mouse controls)');
 // Real CDP click goes through production handler, no onclick invocation.
 await ready('actions','light');await click(s,'start');await wait(s,`__fixture.calls.some(m=>m.op==='start')&&document.getElementById('phase').dataset.state==='playing'`);await click(s,'stop');await wait(s,`__fixture.calls.some(m=>m.op==='stop')&&document.getElementById('sessionControls').hidden`);evidence.actions.push('Send and End helper session via CDP mouse events (synthetic helper replies)');
 await c.evaluate(s,`__fixture.allowed=false;__fixture.denyGrant=true`);await delay(2150);await click(s,'grantAll');await delay(100);assert.equal(await c.evaluate(s,`document.getElementById('enable').disabled`),true);await c.evaluate(s,`__fixture.denyGrant=false`);await click(s,'grantAll');await wait(s,`document.getElementById('permissionBox').hidden`);evidence.actions.push('Permission denial then retry through real grant handler (synthetic permission replies)');
 await ready('focus','light');await click(s,'discover');await wait(s,`document.getElementById('phase').dataset.state==='idle'`);assert.equal(await c.evaluate(s,`document.activeElement.id`),'discover');await delay(4300);assert.equal(await c.evaluate(s,`document.activeElement.id`),'discover');
 await c.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},s);await c.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},s);assert.equal(await c.evaluate(s,`document.activeElement.id`),'receiver');evidence.actions.push('Focus retained over two real 2s polling ticks, then Tab reaches receiver');
 await c.evaluate(s,`__fixture.holdView=true`);await wait(s,`!!__fixture.releaseView`);const n=await c.evaluate(s,`__fixture.calls.filter(m=>m.op==='view-held').length`);await delay(2200);assert.equal(await c.evaluate(s,`__fixture.calls.filter(m=>m.op==='view-held').length`),n);await click(s,'start');assert.equal(await c.evaluate(s,`__fixture.calls.some(m=>m.op==='start')`),false);await c.evaluate(s,`__fixture.holdView=false;__fixture.releaseView()`);await delay(100);await click(s,'start');await wait(s,`__fixture.calls.some(m=>m.op==='start')`);evidence.actions.push('Pending poll does not overlap; racing Send blocked, subsequent Send works');
 // Selection/consent regression: actual select DOM/change and production handler;
 // dispatch records are synthetic worker truth, never native sends.
 evidence.selectionRegressions=[];
 async function choiceFixture(name){
  await ready(name,'light');
  await c.evaluate(s,`__fixture.view.candidates=[{id:'c1',label:'First film',url:'https://example.test/one.mp4'},{id:'c2',label:'Second film',url:'https://example.test/two.mp4'},{id:'c3',label:'Third film',url:'https://example.test/three.mp4'}];__fixture.view.selected='c1';__fixture.view.native.receivers=[{identifier:'r1',label:'First TV',address:'192.0.2.10'},{identifier:'r2',label:'Second TV',address:'192.0.2.11'}];__fixture.view.receiver='r1'`);
  await wait(s,`document.getElementById('candidate').value==='c1'&&document.getElementById('receiver').value==='r1'`);
 }
 async function choice(field,value){await c.evaluate(s,`(()=>{const e=document.getElementById(${JSON.stringify(field)});e.focus();e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('change',{bubbles:true}))})()`);}
 async function assertPending(){assert.equal(await c.evaluate(s,`document.getElementById('start').disabled`),true);await click(s,'start');assert.equal(await c.evaluate(s,`__fixture.dispatches.length`),0);}
 async function assertChoice(selected,receiver){await wait(s,`!document.getElementById('start').disabled`);assert.deepEqual(await c.evaluate(s,`({visible:[document.getElementById('candidate').value,document.getElementById('receiver').value],committed:[__fixture.view.selected,__fixture.view.receiver]})`),{visible:[selected,receiver],committed:[selected,receiver]});}
 async function assertDispatch(selected,receiver){await click(s,'start');await wait(s,`__fixture.dispatches.length===1`);const dispatch=await c.evaluate(s,`__fixture.dispatches[0]`);assert.deepEqual(dispatch,{selected,receiver,url:`https://example.test/${{c1:'one',c2:'two',c3:'three'}[selected]}.mp4`});assert.deepEqual(await c.evaluate(s,`__fixture.calls.find(m=>m.op==='start')`),{op:'start',tabId:1});return dispatch;}
 for(const order of [['candidate','receiver'],['receiver','candidate']]){
  await choiceFixture('race-'+order.join('-'));await c.evaluate(s,`__fixture.holdView=true`);await wait(s,`!!__fixture.releaseView`);
  for(const field of order)await choice(field,field==='candidate'?'c2':'r2');await assertPending();
  // A mouse click on disabled Send legitimately blurs the select. Re-focus it
  // before releasing the snapshot to isolate production refresh focus safety.
  await c.evaluate(s,`document.getElementById(${JSON.stringify(order.at(-1))}).focus()`);
  await c.evaluate(s,`__fixture.holdView=false;__fixture.releaseView()`);await assertChoice('c2','r2');
  assert.equal(await c.evaluate(s,`document.activeElement.id`),order.at(-1));
  evidence.selectionRegressions.push({case:order.join(' then '),dispatch:await assertDispatch('c2','r2')});
 }
 await choiceFixture('rapid');await c.evaluate(s,`__fixture.holdOp('select')`);await choice('candidate','c2');await wait(s,`__fixture.calls.some(m=>m.op==='select-held')`);
 await choice('receiver','r2');await choice('candidate','c3');await assertPending();const views=await c.evaluate(s,`__fixture.calls.filter(m=>m.op==='view').length`);await delay(2200);assert.equal(await c.evaluate(s,`__fixture.calls.filter(m=>m.op==='view').length`),views);
 await c.evaluate(s,`__fixture.releaseOp('select')`);await assertChoice('c3','r2');evidence.selectionRegressions.push({case:'same-field replacement during delayed commit retains TV; polling has no retry',dispatch:await assertDispatch('c3','r2')});
 for(const when of ['before','after']){
  await choiceFixture('failed-'+when);await c.evaluate(s,`__fixture.holdOp('select');__fixture.failNext.select='${when}'`);await choice('candidate','c2');await wait(s,`__fixture.calls.some(m=>m.op==='select-held')`);await assertPending();
  await c.evaluate(s,`__fixture.releaseOp('select')`);const selected=when==='before'?'c1':'c2';await assertChoice(selected,'r1');await delay(2200);assert.equal(await c.evaluate(s,`__fixture.calls.filter(m=>m.op==='select').length`),1);
  evidence.selectionRegressions.push({case:'failed commit '+when+' mutation reconciles without retry',dispatch:await assertDispatch(selected,'r1')});
 }
 await choiceFixture('action-pending');await c.evaluate(s,`__fixture.holdOp('status')`);await c.evaluate(s,`document.getElementById('status').click()`);await wait(s,`__fixture.calls.some(m=>m.op==='status-held')`);await choice('candidate','c2');await choice('receiver','r2');await assertPending();assert.equal(await c.evaluate(s,`__fixture.calls.some(m=>m.op==='select'||m.op==='receiver')`),false);
 await c.evaluate(s,`__fixture.releaseOp('status')`);await assertChoice('c2','r2');evidence.selectionRegressions.push({case:'choices during pending action',dispatch:await assertDispatch('c2','r2')});
 await choiceFixture('closed-pending');await c.evaluate(s,`__fixture.holdView=true`);await wait(s,`!!__fixture.releaseView`);await choice('candidate','c2');await choice('receiver','r2');await assertPending();const count=await c.evaluate(s,`__fixture.requests.length`);
 await c.evaluate(s,`dispatchEvent(new PageTransitionEvent('pagehide'));__fixture.holdView=false;__fixture.releaseView()`);await delay(100);assert.equal(await c.evaluate(s,`__fixture.requests.length`),count);assert.equal(await c.evaluate(s,`__fixture.dispatches.length`),0);evidence.selectionRegressions.push({case:'synthetic pagehide lifecycle during held view',additionalCalls:0,dispatches:0});
 // Key fixtures in a genuine toolbar action document, without viewport emulation.
 // Reload injects only the API seam; popup HTML/JS stay byte-identical.
 await c.send('Page.bringToFront',{},ts);await c.send('Extensions.triggerAction',{id,targetId:tabTarget.targetId});
 let toolbar;for(let i=0;i<100;i++){toolbar=(await c.send('Target.getTargets')).targetInfos.find(t=>t.url===`chrome-extension://${id}/popup.html`);if(toolbar)break;await delay(50)}assert.ok(toolbar,'second toolbar action exists');
 const actionSession=await attach(toolbar.targetId);await c.send('Page.bringToFront',{},actionSession);await c.send('Page.addScriptToEvaluateOnNewDocument',{source:fixture},actionSession);
 evidence.toolbarFixtures=[];evidence.toolbarTarget=toolbar;
 for(const [state,scheme] of [['ready','light'],['ready','dark'],['permission','light'],['pin','light'],['error','light'],['sent','light']]){
  await c.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},actionSession);await c.send('Page.reload',{},actionSession);await wait(actionSession,`document.readyState==='complete'&&!!window.__fixture?.calls.some(x=>x.op==='discover')`);await delay(100);
  if(scenarios[state]){await c.evaluate(actionSession,scenarios[state]);await delay(2150)}
  if(state==='pin'){await click(actionSession,'pairRestart');await wait(actionSession,`!document.getElementById('pairBox').hidden`);}
  const m=await capture(actionSession,`toolbar-${state}-${scheme}`);assert.ok(m.width<=400&&m.viewportWidth<=400,state+' toolbar width');assert.ok(m.height<=600&&m.viewportHeight<=600,state+' toolbar height');assert.ok(m.sendBottom<=m.viewportHeight,state+' toolbar Send within viewport');
  evidence.toolbarFixtures.push({state,scheme,...m});
  if(state==='pin')assert.equal(await c.evaluate(actionSession,`!document.getElementById('pairBox').hidden&&document.getElementById('pair').getBoundingClientRect().bottom<=innerHeight`),true,'toolbar PIN action visible');
 }
 // Focus safety in the real toolbar context over two polling ticks.
 await c.send('Page.reload',{},actionSession);await wait(actionSession,`!!window.__fixture?.calls.some(x=>x.op==='discover')`);await delay(100);await click(actionSession,'discover');await wait(actionSession,`document.getElementById('phase').dataset.state==='idle'`);assert.equal(await c.evaluate(actionSession,`document.activeElement.id`),'discover');await delay(4300);assert.equal(await c.evaluate(actionSession,`document.activeElement.id`),'discover');evidence.actions.push('Actual toolbar focus retained across two polling ticks (synthetic APIs)');
 // Inspect only this disposable Chrome instance's process IDs, not daily Chrome.
 const {processInfo}=await c.send('SystemInfo.getProcessInfo');
 evidence.sandboxProcesses=processInfo.filter(p=>['browser','renderer'].includes(p.type)).map(p=>({type:p.type,pid:p.id,command:execFileSync('/bin/ps',['-ww','-p',String(p.id),'-o','command='],{encoding:'utf8'}).trim()}));
 assert.ok(evidence.sandboxProcesses.some(p=>p.type==='renderer'));
 assert.ok(evidence.sandboxProcesses.every(p=>!p.command.includes('--no-sandbox')));
 if(process.platform==='darwin')assert.ok(evidence.sandboxProcesses.filter(p=>p.type==='renderer').every(p=>p.command.includes('--seatbelt-client=')),'Mac Chrome renderer seatbelt launch');
 evidence.sandboxScope='Observed owned process launch flags: no --no-sandbox; Mac renderers use --seatbelt-client. This is launch/runtime process evidence, not a sandbox escape audit. chrome://sandbox diagnostic above may be unavailable on Mac.';
 await c.send('Target.closeTarget',{targetId:toolbar.targetId});
 evidence.exceptions=c.events.filter(e=>e.method==='Runtime.exceptionThrown').length;assert.equal(evidence.exceptions,0);
 evidence.consoleErrors=c.events.filter(e=>e.method==='Runtime.consoleAPICalled'&&e.params.type==='error').length;assert.equal(evidence.consoleErrors,0);
 writeFileSync(join(output,'chrome-ui-adaptation.mjs.txt'),readFileSync(fileURLToPath(import.meta.url)));
 writeFileSync(join(output,'browser-evidence.json'),JSON.stringify(evidence,null,2));
 console.log(JSON.stringify(evidence,null,2));
}catch(error){evidence.failure=error.message;writeFileSync(join(output,'browser-evidence.json'),JSON.stringify(evidence,null,2));throw error;}finally{await c.close()}
