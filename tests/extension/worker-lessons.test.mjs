import test from 'node:test';
import assert from 'node:assert/strict';
import {createWorker} from '../../extension/worker.mjs';
const signal=()=>({listeners:[],addListener(f){this.listeners.push(f)},removeListener(){},emit(e){this.listeners.forEach(f=>f(e))}});
async function fixture(){
 const calls=[];let respond=async()=>({ok:true});
 const chrome={runtime:{getURL:p=>`chrome-extension://ext/${p}`,onMessage:signal()},tabs:{onRemoved:signal(),sendMessage:async(...args)=>{calls.push(args);return respond(...args)}},webNavigation:{onCommitted:signal(),onHistoryStateUpdated:signal(),getAllFrames:async()=>[{frameId:0,documentId:'doc'}]},webRequest:{onBeforeRequest:signal(),onResponseStarted:signal()},permissions:{getAll:async()=>({origins:[]}),onAdded:signal(),onRemoved:signal()},scripting:{executeScript:async()=>{}},alarms:{create(){},onAlarm:signal()}};
 const native={view:()=>({receivers:[{identifier:'r',address:'192.168.1.5'}],capabilities:['start','stop']}),request:async(op,args)=>{calls.push({op,args});return {ok:true}}};
 const worker=createWorker(chrome,native),send=m=>worker.message({tabId:1,...m},{url:chrome.runtime.getURL('popup.html')});
 const videos=(url='https://example.test/a.mp4',documentId='doc')=>worker.message({op:'videos',videos:[{videoId:'v1',url}]},{tab:{id:1},frameId:0,documentId});
 await send({op:'enable'});await videos();const id=(await send({op:'view'})).candidates[0].id;await send({op:'select',id});await send({op:'receiver',id:'r'});
 return {send,videos,calls,chrome,respond:fn=>{respond=fn},id};
}
test('Find videos and tab switching retain per-tab deliberate selection, not global storage',async()=>{
 const f=await fixture();await f.send({op:'enable'});assert.equal((await f.send({op:'view'})).selected,f.id);
 assert.equal((await f.send({op:'view',tabId:2})).selected,null);assert.equal((await f.send({op:'view'})).selected,f.id);
});
test('Send revalidates exact element/source in exact document without changing helper protocol',async()=>{
 const f=await fixture();await f.send({op:'start'});const check=f.calls.find(c=>Array.isArray(c)&&c[1].op==='validateVideo');
 assert.deepEqual(check,[1,{op:'validateVideo',videoId:'v1',url:'https://example.test/a.mp4'},{documentId:'doc'}]);
 assert.deepEqual(f.calls.at(-1),{op:'start',args:{receiver:'r',host:'192.168.1.5',url:'https://example.test/a.mp4'}});
});
test('changed source check and navigation during Send never dispatch native start',async()=>{
 for(const kind of ['source','navigation']){
  const f=await fixture();f.respond(async(_tab,m)=>{if(m.op!=='validateVideo')return {ok:true};if(kind==='source')return {ok:false};f.chrome.webNavigation.onCommitted.emit({tabId:1,frameId:0,documentId:'new'});return {ok:true}});
  await assert.rejects(f.send({op:'start'}));assert.equal(f.calls.some(c=>c.op==='start'),false);
 }
});
test('late exact local pause reply cannot resurrect a local control after navigation',async()=>{
 const f=await fixture();f.respond(async(_tab,m)=>{if(m.op==='localPause')f.chrome.webNavigation.onCommitted.emit({tabId:1,frameId:0,documentId:'new'});return {ok:true}});
 assert.equal((await f.send({op:'localPause',confirmed:true})).ok,false);assert.equal((await f.send({op:'view'})).localAvailable,false);await assert.rejects(f.send({op:'localResume'}));
});
test('local resume refuses a stale saved source even without navigation',async()=>{
 const f=await fixture();await f.send({op:'localPause',confirmed:true});await f.videos('https://example.test/changed.mp4');const count=f.calls.length;
 await assert.rejects(f.send({op:'localResume'}));assert.equal(f.calls.length,count);
});
