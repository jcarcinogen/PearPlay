// Final production UI rendered with safe synthetic responses in owned Chrome.
// Fixture copy excludes the production host; not native/receiver acceptance.
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
 assert.equal(manifest.version,'0.3.1'); // Preserve production identity and catalog for setup links.
 const worker=readFileSync(join(extension,'worker.mjs'),'utf8');
 assert.ok(worker.includes('com.pearplay.helper'));
 writeFileSync(join(extension,'worker.mjs'),worker.replace('com.pearplay.helper','com.pearplay.ui_test_absent'));
}});
const report={scope:'Actual final 0.3.1 popup/setup documents. Synthetic example media, session, platform and connection responses; no receiver actions or personal profile. Production identity/catalog retained; absent host in copied worker only.',captures:[]};
async function page(url,theme,width,height,source){
 const {targetId}=await c.send('Target.createTarget',{url:'about:blank'});
 const {sessionId:s}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 for(const method of ['Page.enable','Runtime.enable','Network.enable','Log.enable'])await c.send(method,{},s);
 await c.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false},s);
 await c.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme},{name:'prefers-reduced-motion',value:'reduce'}]},s);
 await c.send('Page.addScriptToEvaluateOnNewDocument',{source},s);
 await c.send('Page.bringToFront',{},s);
 await c.send('Page.navigate',{url},s);await c.send('Page.bringToFront',{},s);
 for(let i=0;i<120;i++){
  if(await c.evaluate(s,`location.href===${JSON.stringify(url)}&&document.readyState==='complete'`))break;
  assert.notEqual(i,119,'document load timeout');await delay(50);
 }
 return {targetId,s};
}
async function shot(s,name,width,height){
 await c.send('Page.bringToFront',{},s);
 await c.evaluate(s,'document.fonts.ready.then(()=>Promise.all([...document.images].map(i=>i.decode()))).then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))');
 const events=c.events.filter(e=>e.sessionId===s);
 assert.equal(events.filter(e=>e.method==='Runtime.exceptionThrown'||(e.method==='Log.entryAdded'&&e.params.entry.level==='error')).length,0,'page console errors');
 assert.equal(events.filter(e=>e.method==='Network.requestWillBeSent'&&/^https?:/.test(e.params.request.url)).length,0,'external image/request');
 const {data}=await c.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width,height,scale:1}},s);
 writeFileSync(join(output,name),Buffer.from(data,'base64'));
 return Buffer.from(data,'base64');
}
try{
 const {id}=await c.send('Extensions.loadUnpacked',{path:extension});
 // onInstalled opens setup asynchronously; wait for that owned tab before captures.
 for(let i=0;i<100;i++){
  const targets=(await c.send('Target.getTargets')).targetInfos;
  const setup=targets.find(t=>t.url===`chrome-extension://${id}/setup.html`);
  if(setup){await c.send('Target.closeTarget',{targetId:setup.targetId});break;}
  assert.notEqual(i,99,'first-run setup did not open');await delay(50);
 }
 for(const theme of ['light','dark'])for(const mode of ['browser','tv']){
  const {targetId,s}=await page(`chrome-extension://${id}/popup.html`,theme,400,600,readFileSync(join(root,'tests/browser/brand-fixture.js'),'utf8'));
  for(let i=0;i<100;i++){
   if(await c.evaluate(s,"__fixture.calls.some(x=>x.op==='view')&&!document.getElementById('browserControls').hidden"))break;
   assert.notEqual(i,99,'browser UI timeout: '+JSON.stringify(await c.evaluate(s,"({visibility:document.visibilityState,text:document.body.innerText,calls:__fixture.calls,control:!!globalThis.pearplayBrowserControls})")));await delay(50);
  }
  assert.equal(await c.evaluate(s,"__fixture.calls.some(x=>x.op==='discover')"),false);
  if(mode==='tv'){
   await c.evaluate(s,`Object.assign(__fixture.view.native,{state:'playing',evidence:'protocol',capabilities:['hello','status','stop','pause','resume'],tvControl:{session:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',receiver:'example-receiver'}});document.getElementById('status').click()`);
   for(let i=0;i<100;i++){
    if(await c.evaluate(s,"!document.getElementById('pause').hidden&&document.getElementById('browserControls').hidden"))break;
    assert.notEqual(i,99,'TV UI timeout');await delay(50);
   }
  }
  const geometry=await c.evaluate(s,`({width:document.body.scrollWidth,height:document.body.scrollHeight,browserVisible:!document.getElementById('browserControls').hidden,pauseVisible:!document.getElementById('pause').hidden,text:document.body.innerText})`);
  assert.ok(geometry.width<=400&&geometry.height<=600);
  assert.equal(geometry.browserVisible,mode==='browser');
  const name=mode==='browser'?`popup-${theme}-viewport.png`:`popup-tv-${theme}.png`;
  const raw=await shot(s,name,400,geometry.height);
  writeFileSync(join(root,'assets/store',name),raw);
  report.captures.push({name,theme,mode,...geometry});await c.send('Target.closeTarget',{targetId});
 }
 for(const os of ['linux','mac','win'])for(const theme of ['light','dark'])for(const width of [390,900]){
  const source=`chrome.runtime.getPlatformInfo=async()=>({os:${JSON.stringify(os)},arch:${JSON.stringify(os==='mac'?'arm64':'x86-64')}});chrome.runtime.sendMessage=async()=>({ok:false,error:'NATIVE_DISCONNECTED'});`;
  const {targetId,s}=await page(`chrome-extension://${id}/setup.html`,theme,width,900,source);
  for(let i=0;i<100;i++){
   if(await c.evaluate(s,"document.getElementById('connection').dataset.state&&document.getElementById('downloads').children.length"))break;
   assert.notEqual(i,99,'setup UI timeout');await delay(50);
  }
  const geometry=await c.evaluate(s,`({width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,links:[...document.querySelectorAll('.support a')].map(e=>({url:e.href,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height,right:e.getBoundingClientRect().right})),downloads:[...document.querySelectorAll('#downloads a')].map(e=>e.href)})`);
  assert.ok(geometry.width<=width,'setup horizontal overflow');assert.equal(geometry.links.length,2);
  assert.deepEqual(geometry.links.map(x=>x.url),['https://x.com/scottito22','https://ko-fi.com/scottangel']);
  assert.ok(geometry.links.every(x=>x.height>=44&&x.width>0&&x.right<=width));
  const name=`setup-${os}-${theme}-${width}.png`;await shot(s,name,width,geometry.height);
  report.captures.push({name,os,theme,...geometry});await c.send('Target.closeTarget',{targetId});
 }
 report.browser=c.version;report.passed=true;
}finally{await c.close();writeFileSync(join(output,'ui-verification.json'),JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify({passed:report.passed,browser:report.browser,captures:report.captures.map(x=>x.name)},null,2));
