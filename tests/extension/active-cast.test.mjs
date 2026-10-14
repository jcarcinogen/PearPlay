import test from 'node:test';
import assert from 'node:assert/strict';
import {createWorker} from '../../extension/worker.mjs';
const signal=()=>({listeners:[],addListener(f){this.listeners.push(f)},removeListener(){},emit(...a){this.listeners.forEach(f=>f(...a))}});
function harness(preferred=null){
 const calls=[],writes=[],badges=[];let notify=()=>{},muted=false;
 const state={state:'idle',error:null,evidence:'none',capabilities:['start','stop','status'],receivers:[{identifier:'r',address:'192.168.1.5',label:'Living Room'},{identifier:'r2',address:'192.168.1.6',label:'Bedroom'}]};
 const chrome={runtime:{getURL:p=>`chrome-extension://ext/${p}`,onMessage:signal()},storage:{local:{get:async()=>({preferredReceiverId:preferred}),set:async o=>writes.push(o)}},action:{setBadgeText:async o=>badges.push(o.text),setTitle:async()=>{},setBadgeBackgroundColor:async()=>{}},tabs:{onRemoved:signal(),get:async id=>({title:id===1?'Original film':'Other tab'}),sendMessage:async(...args)=>{calls.push({browser:args});const m=args[1];if(m.action==='mute')muted=m.value;return {ok:true,muted};}},webNavigation:{onCommitted:signal(),onHistoryStateUpdated:signal(),getAllFrames:async({tabId})=>[{frameId:0,documentId:`doc${tabId}`}]},webRequest:{onBeforeRequest:signal(),onResponseStarted:signal()},permissions:{getAll:async()=>({origins:[]}),onAdded:signal(),onRemoved:signal()},scripting:{executeScript:async()=>{}},alarms:{create(){},onAlarm:signal()}};
 const native={view:()=>structuredClone(state),onChange:f=>{notify=f},request:async(op,args)=>{calls.push({op,args});if(op==='start'){state.state='playing';state.evidence='protocol';state.capabilities=['start','stop','status','pause','resume'];state.tvControl={receiver:args.receiver,session:'a'.repeat(32)};}if(op==='stop'){state.state='stopped';state.tvControl=null;}if(op==='pause')state.state='paused';if(op==='resume')state.state='playing';notify();return native.view();}};
 const w=createWorker(chrome,native);const sender={url:chrome.runtime.getURL('popup.html')};
 const send=(op,args={})=>w.message({op,tabId:1,...args},sender);
 const setup=async(dom=true)=>{await send('enable');await w.message({op:'videos',videos:[{videoId:'v1',url:'https://example.test/film.mp4',title:'Original film'}]},{tab:{id:1},frameId:0,documentId:'doc1'});if(!dom){chrome.webRequest.onBeforeRequest.listeners.forEach(()=>{});/* network candidate built through resource recovery */await w.message({op:'videos',videos:[],resources:[{url:'https://example.test/live.m3u8',at:Date.now()}]},{tab:{id:1},frameId:0,documentId:'doc1'});}const v=await send('view');await send('select',{id:v.candidates[0].id});await send('receiver',{id:'r'});};
 return {send,setup,chrome,native,state,calls,writes,badges,w,sender,emit:()=>notify()};
}
test('idle reopen never connects or discovers; cast context crosses tabs without URLs',async()=>{
 const h=harness();await h.setup();await h.send('view');assert.equal(h.calls.some(c=>['hello','status','discover'].includes(c.op)),false);
 await h.send('start');const view=await h.send('view',{tabId:99});assert.equal(view.activeCast.title,'Original film');assert.equal(view.activeCast.sourceTabId,1);assert.equal(view.activeCast.receiverId,'r');assert.equal(view.activeCast.sourceAvailable,true);assert.deepEqual(view.candidates,[]);
 assert.equal(JSON.stringify(view.activeCast).includes('https:'),false);assert.equal(JSON.stringify(h.writes).includes('https:'),false);assert.ok(h.badges.includes('TV'));
 const polls=h.calls.filter(c=>c.op==='status').length;await h.send('view');await h.send('view');assert.equal(h.calls.filter(c=>c.op==='status').length,polls);
});
test('mute is deliberate, exact original document/video, and does not restore audio on stop',async()=>{
 const h=harness();await h.setup();await h.send('start');assert.equal(h.calls.some(c=>c.browser?.[1].action==='mute'),false);
 const castId=(await h.send('view')).activeCast.id;await h.send('castMute',{castId,tabId:99,value:true});const call=h.calls.filter(c=>c.browser?.[1].action==='mute').at(-1).browser;
 assert.equal(call[0],1);assert.equal(call[1].videoId,'v1');assert.equal(call[2].documentId,'doc1');assert.equal((await h.send('view',{tabId:99})).activeCast.browserMuted,true);
 await assert.rejects(h.send('browserControl',{id:'c1',action:'play'}),/TV_SESSION_ACTIVE/);
 await assert.rejects(h.send('castMute',{castId,value:'true'}));await assert.rejects(h.send('castMute',{castId:'stale-cast',value:false}));await h.send('stop');assert.equal((await h.send('view')).activeCast,null);
 assert.equal(h.calls.filter(c=>c.browser?.[1].action==='mute').length,1);
});
for(const cause of ['navigation','removed','changed'])test(`${cause} revokes source audio, not the TV session`,async()=>{
 const h=harness();await h.setup();await h.send('start');
 if(cause==='navigation')h.chrome.webNavigation.onCommitted.emit({tabId:1,frameId:0,documentId:'replacement'});
 if(cause==='removed')h.chrome.tabs.onRemoved.emit(1);
 if(cause==='changed')await h.w.message({op:'videos',videos:[{videoId:'v2',url:'https://example.test/new.mp4'}]},{tab:{id:1},frameId:0,documentId:'doc1'});
 const v=await h.send('view',{tabId:99});assert.equal(v.activeCast.title,'Original film');assert.equal(v.activeCast.sourceAvailable,false);
 await assert.rejects(h.send('castMute',{value:true}),/VIDEO_CHANGED/);await h.send('pause',{session:'a'.repeat(32)});assert.equal(h.state.state,'paused');assert.ok(h.badges.includes('Ⅱ'));
});
test('network HLS never becomes an inferred browser video',async()=>{const h=harness();await h.setup(false);await h.send('start');assert.equal((await h.send('view')).activeCast.sourceAvailable,false);await assert.rejects(h.send('castMute',{value:true}));});
test('preferred TV resolves ID to fresh discovery address, absent preference never creates receiver',async()=>{
 const h=harness('r2');await h.send('discover');assert.equal((await h.send('view')).receiver,'r2');h.state.receivers[1].address='192.168.1.99';await h.send('discover');assert.equal((await h.send('view')).native.receivers[1].address,'192.168.1.99');
 h.state.receivers=[{identifier:'a',address:'192.168.1.8'},{identifier:'b',address:'192.168.1.9'}];await h.send('discover');assert.equal((await h.send('view')).receiver,null);assert.equal(h.calls.some(c=>c.op==='start'),false);
});
test('active cast cannot be replaced or retargeted by another popup',async()=>{const h=harness();await h.setup();await h.send('start');await assert.rejects(h.send('receiver',{id:'r2'}),/TV_SESSION_ACTIVE/);await assert.rejects(h.send('start'),/TV_SESSION_ACTIVE/);assert.equal(h.calls.filter(c=>c.op==='start').length,1);});
test('native stop/disconnect events update badge and clear retained source without reopening popup',async()=>{
 const h=harness();await h.setup();await h.send('start');h.state.state='stopped';h.emit();assert.equal(h.badges.at(-1),'');assert.equal((await h.send('view')).activeCast,null);
 await h.send('start');h.state.state='error';h.state.error='NATIVE_DISCONNECTED';h.emit();assert.equal(h.badges.at(-1),'?');assert.equal((await h.send('view')).activeCast,null);
});
test('pending start exposes progress context but blocks all cast mutations',async()=>{
 const h=harness();await h.setup();let release;const gate=new Promise(r=>{release=r});const original=h.native.request;
 h.native.request=async(op,args)=>{if(op==='start')await gate;return original(op,args);};
 const pending=h.send('start');await new Promise(r=>setImmediate(r));
 const context=(await h.send('view',{tabId:99})).activeCast;assert.ok(context.id);
 for(const [op,args] of [['castMute',{castId:context.id,value:true}],['start',{}],['receiver',{id:'r2'}],['pause',{session:'a'.repeat(32)}]])await assert.rejects(h.send(op,args),/busy/);
 assert.equal(h.calls.some(c=>c.browser?.[1].action==='mute'),false);release();await pending;
 assert.equal((await h.send('view')).activeCast.id,context.id);
});
test('page senders cannot mute the cast source',async()=>{const h=harness();await h.setup();await h.send('start');await assert.rejects(h.w.message({op:'castMute',value:true},{tab:{id:1},url:'https://example.test'}),/UNAUTHORIZED/);});
