import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
const script=await readFile(new URL('../../extension/browser-controls.js',import.meta.url),'utf8');
const html=await readFile(new URL('../../extension/popup.html',import.meta.url),'utf8');
const flush=()=>new Promise(r=>setImmediate(r));
test('active TV session hides browser timeline and rejects queued and direct browser actions',async()=>{
 const f=await fixture();f.hold();f.tick();await flush();const pending=f.nodes.get('browserPlay').onclick();
 f.context.pearplayBrowserControls.select({id:'c1',videoId:'v1'},{casting:true});
 assert.equal(f.nodes.get('browserControls').hidden,true);
 assert.equal(f.nodes.get('tvPlaybackNotice').hidden,false);
 f.release();await pending;const count=f.calls.length;
 await f.nodes.get('browserForward').onclick();f.tick();await flush();assert.equal(f.calls.length,count);
 f.context.pearplayBrowserControls.select({id:'c1',videoId:'v1'},{casting:false});await flush();
 assert.equal(f.nodes.get('browserControls').hidden,false);assert.equal(f.nodes.get('tvPlaybackNotice').hidden,true);
 assert.equal(f.nodes.get('browserPlay').disabled,false);
});
async function fixture(){
 const nodes=new Map([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],{value:m[1]==='browserJump'?'10':'',disabled:false,hidden:false,setAttribute(){},addEventListener(){}}]));
 let tick,hold=false,resolve;const calls=[];const listeners={};
 const state={ok:true,paused:true,muted:false,time:40,duration:90,ranges:[[0,90]],pipAvailable:true,pip:false};
 const context={document:{visibilityState:'visible',getElementById:id=>nodes.get(id)},setInterval:f=>{tick=f;return 1;},clearInterval(){},addEventListener:(name,f)=>listeners[name]=f,chrome:{tabs:{query:async()=>[{id:1}]},storage:{session:{get:async()=>({}),set:async()=>{}}},runtime:{sendMessage:async m=>{calls.push(m);if(hold)await new Promise(r=>resolve=r);return structuredClone(state);}}}};
 vm.runInNewContext(script,context);await flush();context.pearplayBrowserControls.select({id:'c1',videoId:'v1'});await flush();
 return {nodes,context,calls,tick,listeners,hold(){hold=true;},release(){hold=false;resolve();}};
}
test('a user click queues behind quiet polling without disabling or losing its target',async()=>{
 const f=await fixture();assert.equal(f.nodes.get('browserPlay').disabled,false);
 f.hold();f.tick();await flush();const pending=f.nodes.get('browserPlay').onclick();assert.equal(f.nodes.get('browserPlay').disabled,false);assert.equal(f.calls.at(-1).action,'status');
 f.release();await pending;assert.equal(f.calls.at(-1).action,'play');assert.equal(f.calls.at(-1).id,'c1');
});
test('queued control and stale poll are discarded on selection change; hidden popup does not poll',async()=>{
 const f=await fixture();f.hold();f.tick();await flush();const pending=f.nodes.get('browserPlay').onclick();
 f.context.pearplayBrowserControls.select({id:'c2',videoId:'v2'});f.release();await pending;assert.equal(f.calls.some(c=>c.action==='play'),false);assert.equal(f.nodes.get('browserPlay').disabled,true);
 const count=f.calls.length;f.context.document.visibilityState='hidden';f.tick();await flush();assert.equal(f.calls.length,count);
 f.listeners.pagehide();f.context.document.visibilityState='visible';f.tick();await flush();assert.equal(f.calls.length,count);
});
test('timeline input is not committed until change and network-only controls stay disabled',async()=>{
 const f=await fixture();const range=f.nodes.get('browserPosition');range.value='60';range.oninput();const n=f.calls.length;f.tick();await flush();assert.equal(f.calls.length,n);
 await range.onchange();assert.equal(f.calls.at(-1).action,'seek');assert.equal(f.calls.at(-1).value,60);
 f.context.pearplayBrowserControls.select({id:'network',videoId:null});assert.equal(f.nodes.get('browserPlay').disabled,true);assert.match(f.nodes.get('browserHint').textContent,/no browser-video controls/);
});
