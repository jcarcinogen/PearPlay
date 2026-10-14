import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import {Sessions} from '../../extension/core.mjs';

const code=await readFile(new URL('../../extension/content.js',import.meta.url),'utf8');
const origin={tabId:1,frameId:0,documentId:'doc'};
const stream='https://cdn.test/live/index.m3u8?sig=%2f+X';

test('first Find recovers the already-loaded HLS beside a blob without a reload',async()=>{
 const now=1_800_000_000_000;
 const sessions=new Sessions({now:()=>now});sessions.enable(1);sessions.commit(origin);
 let tick,handler;const sent=[];
 const video={tagName:'VIDEO',currentSrc:'blob:https://site.test/player',isConnected:true};
 const context={document:{title:'Live news',querySelectorAll:()=>[video]},performance:{timeOrigin:now-20_000,now:()=>20_000,getEntriesByType:()=>[{name:stream,startTime:2000,responseEnd:3000,initiatorType:'fetch'}]},
  chrome:{runtime:{onMessage:{addListener:f=>handler=f},sendMessage:async m=>{sent.push(m);if(m.resources)sessions.resources(origin,m.resources);sessions.videos(origin,m.videos);return {enabled:true};}}},
  setInterval:f=>{tick=f;return 1;},clearInterval(){},Date,URL,Map,WeakMap,Promise};
 context.globalThis=context;vm.runInNewContext(code,context);await new Promise(r=>setImmediate(r));
 const view=sessions.view(1);assert.equal(view.candidates.filter(c=>c.sendable).length,1,'missing pre-Find HLS');
 assert.equal(view.candidates.filter(c=>c.sendable===false).length,1);
 sessions.select(1,view.candidates.find(c=>c.sendable).id);assert.equal(sessions.selected(1).url,stream);
 await tick();assert.equal(sent.at(-1).resources,undefined,'quiet scans must not renew historical resources');
 await new Promise(resolve=>handler({op:'rescan'},{},resolve));await new Promise(r=>setImmediate(r));
 assert.equal(sent.at(-1).resources.length,1,'explicit Find can recover again');
});

test('historical resources retain original age, reject unsafe/unsupported and stale documents',()=>{
 let now=1000;const s=new Sessions({now:()=>now,ttl:100});s.enable(1);s.commit(origin);
 const r={url:stream,at:950};
 s.resources({...origin,documentId:'old'},[r]);assert.equal(s.view(1).candidates.length,0);
 s.resources(origin,[{url:stream,at:899},{url:stream,at:1001},{url:'https://u:p@cdn.test/x.m3u8',at:950},{url:'https://cdn.test/a.ts',at:950},{url:'https://cdn.test/x?file=a.m3u8',at:950},{url:stream,at:NaN}]);
 assert.equal(s.view(1).candidates.length,0);
 s.resources(origin,[r]);s.select(1,s.view(1).candidates[0].id);
 now=1020;s.resources(origin,[r]);assert.equal(s.selected(1).at,950);
 s.tabs.get(1).at=1040;now=1051;s.resources(origin,[r]);assert.equal(s.view(1).candidates.length,0);
 assert.equal(s.view(1).selectionLost,true);
});

test('same-document navigation cannot resurrect the previous route manifest',()=>{
 let now=1000;const s=new Sessions({now:()=>now});s.enable(1);s.commit(origin);
 s.resources(origin,[{url:stream,at:950}]);assert.equal(s.view(1).candidates.length,1);
 now=1100;s.commit(origin);s.resources(origin,[{url:stream,at:950}]);assert.equal(s.view(1).candidates.length,0);
 s.resources(origin,[{url:stream,at:1100}]);assert.equal(s.view(1).candidates.length,1);
});

test('parent same-document navigation also invalidates surviving child-frame history',()=>{
 let now=1000;const s=new Sessions({now:()=>now});s.enable(1);s.commit(origin);
 const child={tabId:1,frameId:2,documentId:'child',parentFrameId:0};s.commit(child);
 s.resources(child,[{url:stream,at:950}]);assert.equal(s.view(1).candidates.length,1);
 now=1100;s.commit(origin);
 // getAllFrames may re-register a still-loaded iframe after a route change.
 s.tabs.get(1).frames.set(2,'child');s.tabs.get(1).parents.set(2,0);
 s.resources(child,[{url:stream,at:950}]);assert.equal(s.view(1).candidates.length,0);
 s.resources(child,[{url:stream,at:1100}]);assert.equal(s.view(1).candidates.length,1);
});

test('resource recovery cannot age a newer network observation or retarget a selected blob',()=>{
 const s=new Sessions({now:()=>1000});s.enable(1);s.commit(origin);
 s.videos(origin,[{videoId:'v1',url:'blob:https://site.test/x'}]);s.select(1,s.view(1).candidates[0].id);const id=s.selected(1).id;
 s.observe({...origin,url:stream});s.resources(origin,[{url:stream,at:900}]);
 assert.equal(s.selected(1).id,id);assert.equal(s.tabs.get(1).candidates.find(c=>!c.videoId).at,1000);
});
