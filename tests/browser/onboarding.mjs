// Real isolated browser + packaged native host. No discovery, pairing, or casting.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {writeFileSync,mkdirSync,existsSync,readFileSync,cpSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {chromeSession} from '../../scripts/chrome-session.mjs';

const binary=process.env.PEARPLAY_BINARY;
assert.ok(binary&&existsSync(binary),'Set PEARPLAY_BINARY to the packaged helper executable');
const browser=process.env.PEARPLAY_BROWSER??'chrome';
const folders=process.platform==='darwin'?{chrome:'Google/Chrome',brave:'BraveSoftware/Brave-Browser',chromium:'Chromium'}:{chrome:'google-chrome',brave:'BraveSoftware/Brave-Browser',chromium:'chromium'};
assert.ok(folders[browser]);
const fixture=JSON.parse(readFileSync(new URL('./fixture-key.json',import.meta.url),'utf8'));
const id=fixture.id; // Public test key only. Never authorize this ID in a production helper.
const results=[];
for(const installed of [false,true]){
  let parent;
  const c=await chromeSession({isolateHome:true,profileDirectory:folders[browser],prepare:root=>{
    parent=root;
    // Disposable build artifact, not a second working checkout; isolates us from daily native-host allowlists.
    cpSync(resolve('extension'),join(root,'extension'),{recursive:true});
    const manifest=JSON.parse(readFileSync(join(root,'extension/manifest.json'),'utf8'));
    manifest.key=fixture.key;writeFileSync(join(root,'extension/manifest.json'),JSON.stringify(manifest));
    if(installed){const result=JSON.parse(execFileSync(binary,['connect','--browsers',browser,'--config-parent',root],{encoding:'utf8'}));assert.equal(result[browser],'connected');}
  }});
  try{
    const extension=await c.send('Extensions.loadUnpacked',{path:join(parent,'extension')});
    assert.equal(extension.id,id,'Rebuild the development helper for the actual unpacked extension ID');
    const {targetId}=await c.send('Target.createTarget',{url:`chrome-extension://${id}/setup.html`});
    const {sessionId:s}=await c.send('Target.attachToTarget',{targetId,flatten:true});
    await c.send('Runtime.enable',{},s);await c.send('Page.enable',{},s);
    await c.send('Emulation.setDeviceMetricsOverride',{width:900,height:1000,deviceScaleFactor:1,mobile:false},s);
    let state;
    for(let i=0;i<160;i++){
      state=await c.evaluate(s,"({kind:document.getElementById('connection')?.dataset.state,text:document.getElementById('connection')?.textContent,findDisabled:document.getElementById('find')?.disabled,overflow:document.documentElement.scrollWidth>innerWidth})");
      if(state.kind)break;await delay(100);
    }
    assert.equal(state.kind,installed?'ready':'missing',JSON.stringify(state));
    assert.equal(state.findDisabled,!installed);assert.equal(state.overflow,false,JSON.stringify(await c.evaluate(s,"({width:innerWidth,scroll:document.documentElement.scrollWidth,offenders:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth).map(e=>({tag:e.tagName,width:e.getBoundingClientRect().width}))})")));
    if(installed){
      // A separate port proves status without using a fixture or contacting any receiver.
      const response=await c.evaluate(s,`new Promise(resolve=>{const port=chrome.runtime.connectNative('com.pearplay.helper');port.onMessage.addListener(m=>{port.disconnect();resolve(m)});port.onDisconnect.addListener(()=>{void chrome.runtime.lastError;resolve({ok:false})});port.postMessage({v:1,id:'status_test',op:'status',args:{}})})`);
      assert.equal(response.helperVersion,'0.2.0');assert.equal(response.state,'idle');assert.equal(response.ok,true);
      const manifest=join(parent,folders[browser],'NativeMessagingHosts/com.pearplay.helper.json');assert.ok(existsSync(manifest));
      const removed=JSON.parse(execFileSync(binary,['remove','--browsers',browser,'--config-parent',parent],{encoding:'utf8'}));assert.equal(removed[browser],'removed');assert.equal(existsSync(manifest),false);
      const absent=await c.evaluate(s,`new Promise(resolve=>{const port=chrome.runtime.connectNative('com.pearplay.helper');port.onDisconnect.addListener(()=>resolve({missing:!!chrome.runtime.lastError}));port.onMessage.addListener(()=>{port.disconnect();resolve({missing:false})});port.postMessage({v:1,id:'after_remove',op:'hello',args:{}})})`);
      assert.equal(absent.missing,true);
    }
    if(process.env.PEARPLAY_EVIDENCE){
      const dir=resolve(process.env.PEARPLAY_EVIDENCE);mkdirSync(dir,{recursive:true});
      await c.send('Emulation.setDeviceMetricsOverride',{width:900,height:1000,deviceScaleFactor:1,mobile:false},s);
      const image=await c.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true},s);
      writeFileSync(join(dir,`setup-${browser}-${installed?'connected':'missing'}.png`),Buffer.from(image.data,'base64'));
    }
    const errors=c.events.filter(e=>e.sessionId===s&&e.method==='Runtime.exceptionThrown');assert.equal(errors.length,0);
    results.push({browser:c.version,variant:browser,installed,connection:state.kind,uninstallChecked:installed,scope:'Real setup page and packaged hello/status; no network discovery or playback'});
  }finally{await c.close();}
}
console.log(JSON.stringify(results,null,2));
