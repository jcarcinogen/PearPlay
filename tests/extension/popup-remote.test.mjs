import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const source=await readFile(new URL('../../extension/popup.js',import.meta.url),'utf8');
const html=await readFile(new URL('../../extension/popup.html',import.meta.url),'utf8');
const token='a'.repeat(32);
async function mount(os='mac') {
 const elements=new Map([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],{value:'',textContent:'',dataset:{},replaceChildren(){},append(){},addEventListener(){}}]));
 const view={enabled:true,selected:'other',receiver:'tv',candidates:[{id:'other',label:'Unrelated tab'}],activeCast:{id:'cast-1',title:'Original film',receiverId:'tv',receiverName:'Living Room',sourceTabId:1,sourceAvailable:true,browserMuted:false},native:{state:'playing',evidence:'protocol',helperVersion:'0.3.3',error:null,capabilities:['start','stop','pause','resume'],receivers:[{identifier:'tv',label:'Living Room'}],tvControl:{session:token,receiver:'tv'},tvTimeline:{session:token,receiver:'tv',position:65,duration:180,ageMs:100,canSeek:false}}};
 const calls=[];let tick,failView=false;
 const chrome={tabs:{query:async()=>[{id:99,url:'https://example.test/other'}]},permissions:{getAll:async()=>({origins:['http://*/*','https://*/*']})},runtime:{getPlatformInfo:async()=>({os}),sendMessage:async m=>{calls.push(m);if(m.op==='view'){if(failView)throw Error('Extension gone');return structuredClone(view);}if(m.op==='castMute')view.activeCast.browserMuted=m.value;return {ok:true};}}};
 await vm.runInNewContext(source,{document:{getElementById:id=>elements.get(id),createElement:()=>({})},chrome,URL,setInterval:f=>{tick=f},clearInterval(){}});
 return {view,calls,e:id=>elements.get(id),refresh:()=>tick(),failView:()=>{failView=true}};
}
for(const os of ['mac','win','linux'])test(`${os}: global cast title, read-only progress and deliberate original-source audio`,async()=>{
 const p=await mount(os);
 assert.equal(p.e('identity').textContent,'Original film');
 assert.equal(p.e('candidate').hidden,true);assert.equal(p.e('start').hidden,true);
 assert.equal(p.e('tvTimeline').hidden,false);assert.equal(p.e('tvElapsed').textContent,'1:05');assert.equal(p.e('tvDuration').textContent,'3:00');
 assert.match(html,/<progress id="tvProgress"/);assert.equal(p.e('tvProgress').onchange,undefined);
 assert.equal(p.calls.some(m=>['start','castMute','hello','discover'].includes(m.op)),false);
 await p.e('castMute').onclick();assert.equal(p.calls.find(m=>m.op==='castMute').value,true);assert.equal(p.e('castMute').textContent,'Unmute browser video');
 assert.equal(p.calls.some(m=>m.op==='browserControl'),false);
});
test('timeline rejects stale, wrong-cast, seek-enabled and missing snapshots',async()=>{
 const p=await mount();const original=structuredClone(p.view.native.tvTimeline);
 for(const bad of [null,{...original,ageMs:10001},{...original,session:'b'.repeat(32)},{...original,receiver:'wrong'},{...original,canSeek:true},{...original,position:NaN}]){
 p.view.native.tvTimeline=bad;await p.refresh();assert.equal(p.e('tvTimeline').hidden,true);
 }
 p.view.native.tvTimeline={...original,duration:null};await p.refresh();assert.equal(p.e('tvTimeline').hidden,false);assert.equal(p.e('tvProgress').hidden,true);assert.equal(p.e('tvDuration').textContent,'Duration unavailable');
});
test('missing source disables mute without losing TV controls; ending restores tab selection',async()=>{
 const p=await mount();p.view.activeCast.sourceAvailable=false;await p.refresh();
 assert.equal(p.e('castAudio').hidden,true);assert.equal(p.e('castSourceHint').hidden,false);assert.equal(p.e('pause').hidden,false);
 await p.e('castMute').onclick();assert.equal(p.calls.some(m=>m.op==='castMute'),false);
 p.view.native.state='stopped';p.view.activeCast=null;await p.refresh();assert.equal(p.e('identity').textContent,'Unrelated tab');assert.equal(p.e('candidate').hidden,false);assert.equal(p.e('sessionControls').hidden,true);
});
test('failed worker refresh hides the last timeline and disables stale controls',async()=>{const p=await mount();p.failView();await p.refresh();assert.equal(p.e('tvTimeline').hidden,true);assert.equal(p.e('pause').disabled,true);});
test('helper guidance is version-aware and never disables existing casting',async()=>{
 const p=await mount();
 for(const v of ['0.3.1','0.3.2',null]){p.view.native.helperVersion=v;await p.refresh();assert.equal(p.e('helperCompatibility').hidden,false);assert.match(p.e('helperCompatibility').textContent,/0.3.3 or newer/);assert.equal(p.e('pause').disabled,false);}
 for(const v of ['0.3.3','0.3.10','0.4.0','1.0.0']){p.view.native.helperVersion=v;await p.refresh();assert.equal(p.e('helperCompatibility').hidden,true);}
});
test('recovery offers connection only when needed, with no automatic request',async()=>{
 const p=await mount();p.view.native={state:'error',error:'NATIVE_DISCONNECTED',capabilities:[],receivers:[]};p.view.activeCast=null;await p.refresh();
 assert.equal(p.e('recover').textContent,'Connect helper');assert.equal(p.calls.some(m=>m.op==='hello'),false);await p.e('recover').onclick();assert.equal(p.calls.filter(m=>m.op==='hello').length,1);
});
