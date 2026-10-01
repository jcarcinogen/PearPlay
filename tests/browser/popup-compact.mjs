// Real Chrome rendering of the actual popup with synthetic API responses only.
// No helper, receiver, PIN, website media, or daily browser profile is accessed.
import assert from 'node:assert/strict';
import {readFileSync, writeFileSync, mkdirSync, cpSync} from 'node:fs';
import {resolve, dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {chromeSession} from '../../scripts/chrome-session.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const output = resolve(process.env.PEARPLAY_UI_EVIDENCE || join(process.env.TMPDIR || root, 'pearplay-compact-evidence'));
mkdirSync(output, {recursive:true});
let extension;
const c = await chromeSession({prepare: temp => {
  extension = join(temp, 'extension');
  cpSync(join(root, 'extension'), extension, {recursive:true});
  const manifest = JSON.parse(readFileSync(join(extension, 'manifest.json')));
  manifest.key = JSON.parse(readFileSync(join(root, 'tests/browser/fixture-key.json'))).key;
  writeFileSync(join(extension, 'manifest.json'), JSON.stringify(manifest));
}});
const results = [];
try {
  const {id} = await c.send('Extensions.loadUnpacked', {path:extension});
  const {targetId} = await c.send('Target.createTarget', {url:'about:blank'});
  const {sessionId} = await c.send('Target.attachToTarget', {targetId, flatten:true});
  await c.send('Page.enable', {}, sessionId);
  await c.send('Runtime.enable', {}, sessionId);
  await c.send('Emulation.setDeviceMetricsOverride', {width:400,height:600,deviceScaleFactor:1,mobile:false}, sessionId);
  await c.send('Page.addScriptToEvaluateOnNewDocument', {source:readFileSync(join(root, 'tests/browser/brand-fixture.js'), 'utf8')}, sessionId);
  await c.send('Page.navigate', {url:`chrome-extension://${id}/popup.html`}, sessionId);
  for (let i=0; i<100; i++) {
    if (await c.evaluate(sessionId, `document.readyState==='complete' && window.__fixture?.calls.some(x=>x.op==='discover')`)) break;
    await delay(50);
  }
  await c.send('Page.bringToFront', {}, sessionId);
  await c.evaluate(sessionId, `Promise.all([...document.images].map(i=>i.decode().catch(()=>{}))).then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))`);
  const metrics = await c.evaluate(sessionId, `(()=>{const b=document.body;const r=document.getElementById('start').getBoundingClientRect();return {height:b.scrollHeight,width:b.scrollWidth,sendBottom:r.bottom,sendEnabled:!document.getElementById('start').disabled,permissionHidden:document.getElementById('permissionBox')?.hidden===true,stopHidden:document.getElementById('sessionControls')?.hidden===true,helpClosed:document.getElementById('helpDetails')?.open===false}})()`);
  const {data} = await c.send('Page.captureScreenshot', {format:'png',clip:{x:0,y:0,width:400,height:Math.min(metrics.height,600),scale:1}}, sessionId);
  writeFileSync(join(output,'ready.png'), Buffer.from(data,'base64'));
  results.push({state:'ready',...metrics});
  writeFileSync(join(output,'results.json'), JSON.stringify({browser:c.version,scope:'Synthetic UI rendering, not native transport or playback evidence',results},null,2));
  assert.ok(metrics.height<=600, `normal casting view needs scrolling: ${metrics.height}px`);
  assert.ok(metrics.width<=400, 'horizontal overflow');
  assert.ok(metrics.sendBottom<=600 && metrics.sendEnabled, 'Send must be visible and enabled');
  assert.equal(metrics.permissionHidden,true, 'granted website permission should not occupy the normal view');
  assert.equal(metrics.stopHidden,true, 'idle view should not offer an active-session control');
  assert.equal(metrics.helpClosed,true, 'advanced controls start collapsed');
  const scenarios = [
    ['permission', `__fixture.allowed=false`, 'permissionBox', false],
    ['empty', `__fixture.view.candidates=[]`, 'videoHint', false],
    ['playing', `__fixture.view.native.state='playing';__fixture.view.native.evidence='protocol'`, 'sessionControls', false],
    ['error', `__fixture.view.native.state='error';__fixture.view.native.error='receiver_unavailable'`, 'pairBox', true],
    ['pin', `__fixture.view.native.error='pairing_required'`, 'pairBox', false],
    ['firewall', `__fixture.view.firewallBusy=true`, 'firewallReview', false],
    ['sent', `Object.assign(__fixture.view.native,{state:'connecting',evidence:'unverified',session:{receiver:'example-receiver',host:'192.0.2.10',transport:'airplay-v1',delivery:'accepted',timingRequired:false}})`, 'sessionControls', false],
    ...['unsupported_access','incomplete_advertisement','unsupported_protocol'].map(reason => [reason, `Object.assign(__fixture.view.native,{state:'error',evidence:'unverified',error:'transport_failed',receiverIssue:'${reason}'})`, 'pairBox', true]),
    ['reset', `Object.assign(__fixture.view.native,{state:'stopped',evidence:'unverified',session:null})`, 'sessionControls', true],
  ];
  for (const [state, setup, control, hidden] of scenarios) {
    // New document per case: PIN/action lexical state must not leak between fixtures.
    await c.send('Page.navigate',{url:`chrome-extension://${id}/popup.html?case=${state}`},sessionId);
    for(let i=0;i<100;i++) {
      if(await c.evaluate(sessionId,`location.search==='?case=${state}' && document.readyState==='complete' && !!__fixture?.calls.some(x=>x.op==='discover')`)) break;
      await delay(50);
    }
    await c.evaluate(sessionId, setup);
    await delay(2200); // Production refresh interval, no synthetic click bypass.
    const m = await c.evaluate(sessionId, `(()=>{const e=document.getElementById(${JSON.stringify(control)});return {height:document.body.scrollHeight,width:document.body.scrollWidth,hidden:e.hidden,sendBottom:document.getElementById('start').getBoundingClientRect().bottom,helpOpen:document.getElementById('helpDetails').open,firewallOpen:document.getElementById('firewallBox').open}})()`);
    if (state==='sent' || state.startsWith('unsupported_') || state==='incomplete_advertisement' || state==='reset') {
      const status = await c.evaluate(sessionId, `({badge:document.getElementById('phase').textContent,text:document.getElementById('tvStatus').textContent,disabled:document.getElementById('start').disabled,pinCalls:__fixture.calls.filter(x=>x.op==='pairBegin').length})`);
      assert.equal(status.pinCalls,0,state+' must not auto-pair');
      if(state==='sent') {assert.match(status.badge,/^Sent\b/);assert.match(status.text,/check the picture and sound/i);assert.equal(status.disabled,true);}
      else if(state==='reset') assert.notEqual(status.badge,'Sent');
      else {assert.equal(status.badge,'Needs attention');assert.doesNotMatch(status.text,/4 digits|firewall/i);}
    }
    assert.equal(m.hidden, hidden, state+' conditional control');
    assert.ok(m.width<=400, state+' horizontal overflow');
    if (state!=='firewall') {
      assert.ok(m.height<=600, state+' normal flow exceeds popup height: '+m.height);
      assert.ok(m.sendBottom<=600, state+' Send is below fold');
    } else {
      assert.equal(m.helpOpen,true,'pending approval must surface even inside collapsed help');
      assert.equal(m.firewallOpen,true);
    }
    const {data} = await c.send('Page.captureScreenshot', {format:'png',clip:{x:0,y:0,width:400,height:Math.min(m.height,600),scale:1}}, sessionId);
    writeFileSync(join(output,state+'.png'),Buffer.from(data,'base64'));
    results.push({state,...m});
  }
  await c.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:'dark'}]},sessionId);
  const {data:dark} = await c.send('Page.captureScreenshot',{format:'png'},sessionId);
  writeFileSync(join(output,'dark.png'),Buffer.from(dark,'base64'));
  writeFileSync(join(output,'results.json'), JSON.stringify({browser:c.version,scope:'Synthetic UI rendering, not native transport or playback evidence',results},null,2));
  assert.equal(c.events.filter(e=>e.sessionId===sessionId && e.method==='Runtime.exceptionThrown').length,0);
} finally { await c.close(); }
console.log(JSON.stringify({browser:c.version,results,output},null,2));
