import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import {Sessions} from '../../extension/core.mjs';
import {createWorker} from '../../extension/worker.mjs';
const code=await readFile(new URL('../../extension/content.js',import.meta.url),'utf8');
async function fixture(keepAlive=false) {
 let listener,tick,serial,now=0;
 const events=new Map();
 const video={tagName:'VIDEO',currentSrc:'https://example.test/video.mp4',isConnected:true,currentTime:40,duration:90,paused:true,muted:false,seekable:{length:2,start:i=>i?30:0,end:i=>i?90:20},addEventListener:(name,fn)=>events.set(name,fn),getAttribute:()=>'',pause(){this.paused=true;},async play(){this.paused=false;},scrollIntoView(){this.scrolled=true;},async requestPictureInPicture(){doc.pictureInPictureElement=this;}};
 const doc={pictureInPictureEnabled:true,pictureInPictureElement:null,querySelectorAll:()=>[video],async exitPictureInPicture(){this.pictureInPictureElement=null;}};
 const context={document:doc,chrome:{runtime:{sendMessage:async m=>{serial=m.videos[0]?.videoId;return {enabled:true,keepAlive};},onMessage:{addListener:f=>listener=f}}},setInterval:f=>{tick=f;},clearInterval(){},Date:{now:()=>now}};
 vm.runInNewContext(code,context);await tick();
 return {video,doc,events,tick,advance:ms=>{now+=ms;},send:(action,value,url=video.currentSrc)=>new Promise(reply=>listener({op:'browserControl',videoId:serial,url,action,value},{},reply))};
}
test('content collection renews only a worker-validated selected video and still expires after silence',async()=>{
 const active=await fixture(true);
 for(let i=0;i<4;i++){active.advance(300000);await active.tick();assert.equal((await active.send('status')).ok,true);}
 active.advance(600001);await active.tick();assert.equal((await active.send('status')).ok,false);
 const inactive=await fixture(false);inactive.advance(600001);await inactive.tick();assert.equal((await inactive.send('status')).ok,false);
});
test('exact browser controls cover transport, mute, gapped seeks, bounded skips and PiP',async()=>{
 const f=await fixture();
 assert.equal((await f.send('play')).paused,false);assert.equal((await f.send('pause')).paused,true);
 assert.equal((await f.send('mute',true)).muted,true);assert.equal((await f.send('mute',false)).muted,false);
 for(const n of [5,10,15,30]){f.video.currentTime=40;await f.send('skip',n);assert.equal(f.video.currentTime,40+n);await f.send('skip',-n);assert.equal(f.video.currentTime,40);}
 await f.send('seek',26);assert.equal(f.video.currentTime,30);await f.send('seek',999);assert.equal(f.video.currentTime,90);
 assert.equal((await f.send('seek',NaN)).ok,false);assert.equal((await f.send('skip',999)).ok,false);
 await f.send('pip');assert.equal(f.doc.pictureInPictureElement,f.video);await f.send('pip');assert.equal(f.doc.pictureInPictureElement,null);
 await f.send('return');assert.equal(f.video.scrolled,true);
 f.video.seekable.length=0;assert.equal((await f.send('seek',1)).error,'NO_SEEK_WINDOW');
 assert.equal((await f.send('pause',undefined,'https://example.test/stale.mp4')).error,'VIDEO_CHANGED_OR_UNCONFIRMED');
});
test('late play cannot report success after a source epoch changes and returns',async()=>{
 const f=await fixture();let resolve;
 f.video.play=()=>new Promise(r=>resolve=r);
 const pending=f.send('play');f.events.get('loadstart')();await f.tick();resolve();
 assert.equal((await pending).error,'VIDEO_CHANGED_OR_UNCONFIRMED');
});
test('blob DOM candidates are controllable but never TV-fetchable or network-inferred',()=>{
 const s=new Sessions();s.enable(1);s.commit({tabId:1,frameId:0,documentId:'d'});
 s.videos({tabId:1,frameId:0,documentId:'d'},[{videoId:'v1',url:'blob:https://example.test/uuid'}]);
 assert.equal(s.view(1).candidates.length,1);assert.equal(s.view(1).candidates[0].sendable,false);
 s.observe({tabId:1,frameId:0,documentId:'d',url:'blob:https://example.test/another'});assert.equal(s.view(1).candidates.length,1);
});
const signal=()=>({addListener(){},removeListener(){}});
test('worker browser control authorization, selected identity and stale completion fail closed',async()=>{
 let resolve;const calls=[];
 const chrome={runtime:{getURL:p=>'chrome-extension://ext/'+p,onMessage:signal()},tabs:{onRemoved:signal(),sendMessage:async(...args)=>{calls.push(args);if(args[1].op==='browserControl')return new Promise(r=>resolve=r);return {ok:true};}},permissions:{getAll:async()=>({origins:[]}),onAdded:signal(),onRemoved:signal()},webNavigation:{onCommitted:signal(),onHistoryStateUpdated:signal(),getAllFrames:async()=>[{frameId:0,documentId:'d'}]},webRequest:{onBeforeRequest:signal(),onResponseStarted:signal()},scripting:{executeScript:async()=>{}},alarms:{create(){},onAlarm:signal()}};
 const nativeState={receivers:[]};
 const w=createWorker(chrome,{view:()=>nativeState,request:async op=>{calls.push(op);return {};}});
 const sender={url:chrome.runtime.getURL('popup.html')};const send=m=>w.message({tabId:1,...m},sender);
 await send({op:'enable'});await w.message({op:'videos',videos:[{videoId:'v1',url:'blob:https://example.test/a'},{videoId:'v2',url:'https://example.test/b.mp4'}]},{tab:{id:1},frameId:0,documentId:'d'});
 const v=await send({op:'view'});const [a,b]=v.candidates;await send({op:'select',id:a.id});
 for(const state of ['connecting','playing','paused','stopping']){
  nativeState.state=state;const n=calls.length;
  await assert.rejects(send({op:'browserControl',id:a.id,action:'skip',value:10}),/TV_SESSION_ACTIVE/);
  assert.equal(calls.length,n,'never sends a browser seek during a TV session');
 }
 nativeState.state='stopped';
 await assert.rejects(send({op:'start'}),/VIDEO_NOT_SENDABLE/);
 await assert.rejects(w.message({op:'browserControl',id:a.id},{url:'https://evil.test',tab:{id:1}}),/UNAUTHORIZED/);
 await assert.rejects(send({op:'browserControl',id:b.id,action:'play'}),/VIDEO_CHANGED/);
 const pending=send({op:'browserControl',id:a.id,action:'play'});
 assert.equal(calls.at(-1)[2].documentId,'d');assert.equal(calls.at(-1)[1].url,'blob:https://example.test/a');
 await send({op:'select',id:b.id});resolve({ok:true});assert.equal((await pending).error,'VIDEO_CHANGED_OR_UNCONFIRMED');
 assert.equal(calls.includes('start'),false);
});
