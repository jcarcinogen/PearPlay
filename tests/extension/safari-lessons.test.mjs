import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import {Sessions} from '../../extension/core.mjs';
const content=await readFile(new URL('../../extension/content.js',import.meta.url),'utf8');
async function media() {
  let handler,tick,resolve,reject;
  const events={};
  const video={tagName:'VIDEO',currentSrc:'https://example.test/film.mp4',isConnected:true,title:'Example film',getAttribute(){},addEventListener(name,fn){events[name]=fn;},pause(){},play(){return new Promise((a,b)=>{resolve=a;reject=b;});}};
  let nodes=[video];
  const context={document:{querySelectorAll:()=>nodes},chrome:{runtime:{sendMessage:async()=>({enabled:true}),onMessage:{addListener:f=>handler=f}}},setInterval:f=>{tick=f},clearInterval(){},Date};
  vm.runInNewContext(content,context);await tick();
  return {video,events,scan:tick,replace:()=>{nodes=[{...video}]},resolve:()=>resolve(),reject:()=>reject(Error('blocked')),message:()=>new Promise(r=>handler({op:'localResume',videoId:'v1',url:'https://example.test/film.mp4'},{},r))};
}
for(const kind of ['source','detached','replaced','source-restored']) test(`async browser resume fails closed after ${kind}`,async()=>{
  const m=await media();const pending=m.message();
  if(kind==='source')m.video.currentSrc='https://example.test/new.mp4';
  if(kind==='detached')m.video.isConnected=false;
  if(kind==='replaced'){m.replace();await m.scan();}
  if(kind==='source-restored')m.events.emptied?.();
  m.resolve();const result=await pending;
  assert.equal(result.ok,false);assert.equal(result.error,'VIDEO_CHANGED_OR_UNCONFIRMED');
});
test('async rejected resume does not report permission failure for a changed source',async()=>{
 const m=await media();const pending=m.message();m.video.currentSrc='https://example.test/new.mp4';m.reject();assert.equal((await pending).error,'VIDEO_CHANGED_OR_UNCONFIRMED');
});
test('rescan preserves exact selected video, replacement leaves a deliberate-selection tombstone',()=>{
 const s=new Sessions();s.enable(1);s.commit({tabId:1,frameId:0,documentId:'doc'});
 const sender={tabId:1,frameId:0,documentId:'doc'};
 s.videos(sender,[{videoId:'v1',url:'https://example.test/film.mp4'}]);s.select(1,s.view(1).candidates[0].id);
 s.videos(sender,[{videoId:'v1',url:'https://example.test/film.mp4'}]);assert.ok(s.view(1).selected);
 s.videos(sender,[{videoId:'v2',url:'https://example.test/new.mp4'}]);assert.equal(s.view(1).selected,null);assert.equal(s.view(1).selectionLost,true);
 assert.throws(()=>s.selected(1));s.select(1,s.view(1).candidates[0].id);assert.equal(s.view(1).selectionLost,false);
});
test('unrelated frame navigation does not discard deliberate selection in original document',()=>{
 const s=new Sessions();s.enable(1);s.commit({tabId:1,frameId:0,documentId:'doc'});
 s.videos({tabId:1,frameId:0,documentId:'doc'},[{videoId:'v1',url:'https://example.test/film.mp4'}]);s.select(1,s.view(1).candidates[0].id);
 const id=s.view(1).selected;s.commit({tabId:1,frameId:2,documentId:'other'});assert.equal(s.view(1).selected,id);
});
