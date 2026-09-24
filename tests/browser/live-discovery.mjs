// Opt-in real LAN discovery only: no pairing, playback, or daily-profile changes.
import assert from 'node:assert/strict';
import {cpSync,readFileSync,writeFileSync} from 'node:fs';
import {join,resolve} from 'node:path';
import {execFileSync} from 'node:child_process';
import {setTimeout as delay} from 'node:timers/promises';
import {chromeSession} from '../../scripts/chrome-session.mjs';
assert.equal(process.env.PEARPLAY_LIVE_DISCOVERY,'1','Explicit LAN-discovery opt-in required');
assert.equal(process.platform,'linux','Linux integration harness');
const python=process.env.PEARPLAY_PYTHON;
assert.ok(python,'PEARPLAY_PYTHON must name the machine-local helper Python');
const fixture=JSON.parse(readFileSync(new URL('./fixture-key.json',import.meta.url),'utf8'));
let artifact;
const c=await chromeSession({isolateHome:true,profileDirectory:'google-chrome',prepare:root=>{
 artifact=join(root,'extension');cpSync(resolve('extension'),artifact,{recursive:true});
 const manifest=JSON.parse(readFileSync(join(artifact,'manifest.json'),'utf8'));manifest.key=fixture.key;
 writeFileSync(join(artifact,'manifest.json'),JSON.stringify(manifest));
 const result=JSON.parse(execFileSync(python,['helper/install.py','install','--extension-id',fixture.id,'--browser','chrome','--config-parent',root,'--python',python],{encoding:'utf8'}));
 assert.equal(result.ok,true);
}});
try {
 const {id}=await c.send('Extensions.loadUnpacked',{path:artifact});assert.equal(id,fixture.id);
 const {targetId}=await c.send('Target.createTarget',{url:`chrome-extension://${id}/setup.html`});
 const {sessionId:s}=await c.send('Target.attachToTarget',{targetId,flatten:true});await c.send('Runtime.enable',{},s);
 let kind;
 for(let i=0;i<100;i++){kind=await c.evaluate(s,"document.getElementById('connection')?.dataset.state");if(kind)break;await delay(100);}
 assert.equal(kind,'ready');
 const rounds=[];
 for(let round=0;round<3;round++){
  const start=Date.now();
  await c.evaluate(s,"document.getElementById('find').click()");
  let result;
  for(let i=0;i<280;i++){
   result=await c.evaluate(s,"({busy:document.getElementById('find').disabled,text:document.getElementById('receivers').textContent})");
   if(!result.busy)break;await delay(100);
  }
  assert.equal(result.busy,false);assert.match(result.text,/Found \d+ AirPlay TVs?/);
  assert.match(result.text,/Apple TV \(/);assert.match(result.text,/compatibility unverified/);
  assert.doesNotMatch(result.text,/undefined|Sonos/);
  rounds.push({seconds:Math.round((Date.now()-start)/10)/100,appleTV:true,otherVideoReceiver:true,unverifiedLabel:true});
 }
 assert.equal(c.events.filter(e=>e.method==='Runtime.exceptionThrown').length,0);
 console.log(JSON.stringify({browser:c.version,realSetupFind:true,rounds,paired:false,played:false}));
} finally {await c.close();}
