import test from 'node:test';
import assert from 'node:assert/strict';
import {Native} from '../../extension/native.mjs';
const token='a'.repeat(32);
const timeline={session:token,position:10.5,duration:100,rate:1,seekable:[{start:0,end:100}],canSeek:false,ageMs:500};
const message=t=>({v:1,id:'event',ok:true,state:'playing',evidence:'protocol',capabilities:['pause','resume'],tvControl:{session:token,receiver:'r1'},tvTimeline:t,helperVersion:'0.3.3'});
test('actual helper timeline schema derives receiver from the same authenticated control',()=>{
 const n=new Native(()=>{throw Error('must not connect')},{now:()=>1000});n.receive(message(timeline));
 assert.deepEqual(n.view().tvTimeline,{session:token,receiver:'r1',position:10.5,duration:100,canSeek:false,ageMs:500});
 assert.equal(n.view().helperVersion,'0.3.3');
 n.receive({...message(null),helperVersion:undefined});assert.equal(n.view().helperVersion,null);assert.equal(n.view().tvTimeline,null);
});
test('timeline fails closed for mismatched tokens, invalid values and unsupported seek flag',()=>{
 const n=new Native(()=>{throw Error('must not connect')});
 for(const t of [null,[],{...timeline,session:'b'.repeat(32)},{...timeline,receiver:'wrong'},{...timeline,canSeek:true},{...timeline,canSeek:undefined},{...timeline,position:NaN},{...timeline,position:-1},{...timeline,position:102},{...timeline,duration:Infinity},{...timeline,duration:undefined},{...timeline,ageMs:-1},{...timeline,ageMs:10001},{...timeline,ageMs:1.5}]){
 n.receive(message(t));assert.equal(n.view().tvTimeline,null,JSON.stringify(t));
 }
 for(const change of [{evidence:'unverified'},{state:'stopped'},{capabilities:[]},{tvControl:null},{ok:false,error:'busy'}]){n.receive({...message(timeline),...change});assert.equal(n.view().tvTimeline,null);}
 n.receive(message({...timeline,duration:null,live:true}));assert.equal(n.view().tvTimeline.duration,null);assert.equal(n.view().tvTimeline.live,undefined,'unknown duration does not establish live');
});
test('retained timeline expires without a new event and cannot be changed through view',()=>{
 let now=1000;const n=new Native(()=>{throw Error('must not connect')},{now:()=>now});
 n.receive(message(timeline));now+=500;assert.equal(n.view().tvTimeline.ageMs,1000);
 n.view().tvTimeline.position=99;assert.equal(n.view().tvTimeline.position,10.5);
 now+=9501;assert.equal(n.view().tvTimeline,null);
});
test('native observers receive events and disconnects without affecting request state',()=>{
 const n=new Native(()=>{throw Error('must not connect')});const seen=[];const off=n.onChange(()=>seen.push(n.view().state));
 n.receive(message(timeline));n.fail('NATIVE_DISCONNECTED');assert.deepEqual(seen,['playing','error']);off();n.receive(message(timeline));assert.equal(seen.length,2);
});
