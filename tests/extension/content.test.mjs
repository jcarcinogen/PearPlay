import test from 'node:test';import assert from 'node:assert/strict';import vm from 'node:vm';import {readFile} from 'node:fs/promises';
test('injected discovery scans dynamic open shadows and only confirmed exact video pauses',async()=>{
 let handler,tick;const sent=[];const video={tagName:'VIDEO',currentSrc:'https://x/v?sig=%2F',isConnected:true,paused:false,pause(){this.paused=true;},async play(){this.paused=false;}};
 const root={querySelectorAll:()=>[video]};const doc={querySelectorAll:()=>[{shadowRoot:root}]};
 const context={document:doc,chrome:{runtime:{sendMessage:async m=>{sent.push(m);return {enabled:true};},onMessage:{addListener:f=>handler=f}}},setInterval:f=>{tick=f;return 1;},clearInterval(){},setTimeout,Date,Map,WeakMap,Promise};context.globalThis=context;
 await vm.runInNewContext(await readFile(new URL('../../extension/content.js',import.meta.url),'utf8'),context);
 await tick();assert.equal(sent.at(-1).videos[0].url,video.currentSrc);const videoId=sent.at(-1).videos[0].videoId;
 const message=m=>new Promise(resolve=>handler(m,{},resolve));
 assert.equal((await message({op:'localPause',videoId,url:video.currentSrc})).ok,false);assert.equal(video.paused,false);
 assert.equal((await message({op:'localPause',videoId,url:video.currentSrc,confirmed:true})).ok,true);assert.equal(video.paused,true);
 await message({op:'localResume',videoId,url:video.currentSrc});assert.equal(video.paused,false);
 video.currentSrc='blob:x';await tick();assert.equal(sent.at(-1).videos.length,0);
 video.currentSrc='https://x/new';await tick();assert.equal((await message({op:'localPause',videoId,url:'https://x/old',confirmed:true})).ok,false);
 root.querySelectorAll=()=>Array.from({length:150},()=>({...video}));await tick();assert.equal(sent.at(-1).videos.length,100);
});
