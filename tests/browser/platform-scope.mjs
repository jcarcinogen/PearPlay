// Opt-in Mac negative control: current extension must offer no install/cast flow.
// No native host, daily browser profile, discovery, pairing or TV playback is used.
import assert from 'node:assert/strict';
import {mkdirSync,writeFileSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {chromeSession} from '../../scripts/chrome-session.mjs';

if(process.platform!=='darwin')throw Error('This negative-control test requires Mac Chrome; Linux UI regression uses the regular suite.');
const root=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const c=await chromeSession();
const results=[];
try{
  const {id}=await c.send('Extensions.loadUnpacked',{path:resolve(root,'extension')});
  for(const name of ['popup.html','setup.html']){
    const {targetId}=await c.send('Target.createTarget',{url:'about:blank'});
    const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
    await c.send('Page.enable',{},sessionId);await c.send('Runtime.enable',{},sessionId);
    await c.send('Page.addScriptToEvaluateOnNewDocument',{source:`globalThis.__scopeCalls=[];chrome.runtime.sendMessage=async m=>{__scopeCalls.push('message');throw Error('Unexpected helper request');};globalThis.fetch=async()=>{__scopeCalls.push('fetch');throw Error('Unexpected download lookup');};`},sessionId);
    await c.send('Page.navigate',{url:`chrome-extension://${id}/${name}`},sessionId);
    let state;
    for(let attempt=0;attempt<100;attempt++){
      state=await c.evaluate(sessionId,`(async()=>({ready:document.readyState==='complete',os:(await chrome.runtime.getPlatformInfo()).os,text:document.body.innerText,hidden:${name==='popup.html'?"!!document.getElementById('casting')?.hidden":"!!document.getElementById('installSection')?.hidden&&!!document.getElementById('browserSection')?.hidden"},calls:globalThis.__scopeCalls}))()`);
      if(state.ready&&state.hidden)break;
      await delay(50);
    }
    assert.equal(state.os,'mac');assert.equal(state.hidden,true);
    assert.match(state.text,/Mac support is coming soon\./);assert.deepEqual(state.calls,[]);
    const errors=c.events.filter(e=>e.sessionId===sessionId&&e.method==='Runtime.exceptionThrown');
    assert.equal(errors.length,0);
    results.push({page:name,actualPlatform:state.os,installOrCastingHidden:state.hidden,helperOrDownloadRequests:state.calls.length,consoleErrors:errors.length});
    await c.send('Target.closeTarget',{targetId});
  }
  await c.send('Extensions.uninstall',{id});
}finally{await c.close();}
const report={scope:'Actual isolated Mac Chrome platform detection and unsupported-platform UI; no native-helper or TV acceptance claim.',browser:c.version,results,cleanup:'Owned browser and disposable profile closed/removed; no daily registration changed.'};
mkdirSync(resolve(root,'assets/evidence'),{recursive:true});
writeFileSync(resolve(root,'assets/evidence/linux-only-platform.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
