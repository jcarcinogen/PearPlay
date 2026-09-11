import {connect} from './cdp.mjs';
import fs from 'node:fs';
const root=process.argv[2];const c=await connect(root);const out={};
try{
 const id='gndkmajngklgjkcmbolddaodljgoabma';
 await c.send('Extensions.loadUnpacked',{path:'/home/scott/Projects/PearPlay/extension'});
 for(const t of (await c.send('Target.getTargets')).targetInfos)if(t.type==='page'&&t.url.startsWith('chrome-extension://'))await c.send('Target.closeTarget',{targetId:t.targetId});
 await c.send('Target.createTarget',{url:'about:blank'});const tab=(await c.send('Target.getTargets',{filter:[{type:'tab'}]})).targetInfos.find(t=>t.embedderData?.tabActive);await c.send('Extensions.triggerAction',{id,targetId:tab.targetId});
 let popup;for(let i=0;i<50;i++){popup=(await c.send('Target.getTargets')).targetInfos.find(t=>t.url===`chrome-extension://${id}/popup.html`);if(popup)break;await new Promise(r=>setTimeout(r,100));}if(!popup)throw Error('no actual popup target');
 const {sessionId:s}=await c.send('Target.attachToTarget',{targetId:popup.targetId,flatten:true});
 for(let n=0;n<50;n++){if(await c.eval(s,'!!globalThis.chrome?.runtime?.id'))break;await new Promise(r=>setTimeout(r,100));}
 out.identity=await c.eval(s,'chrome.runtime.id');
 out.native=await c.eval(s,`new Promise(resolve=>{const p=chrome.runtime.connectNative('com.pearplay.helper');const results=[];const ops=['hello','status','pause','resume'];let i=0;p.onDisconnect.addListener(()=>resolve({results,error:chrome.runtime.lastError?.message}));p.onMessage.addListener(m=>{results.push(m);if(++i<ops.length)p.postMessage({v:1,id:'probe_'+i,op:ops[i],args:{}});else{p.disconnect();resolve({results});}});p.postMessage({v:1,id:'probe_0',op:ops[0],args:{}});})`);
 out.worker=await c.eval(s,`(async()=>{const r={};for(const op of ['hello','status','pause','resume'])r[op]=await chrome.runtime.sendMessage({op});r.view=await chrome.runtime.sendMessage({op:'view'});return r;})()`);
 const ui=await c.send('Target.createTarget',{url:'chrome://extensions'});const a=await c.send('Target.attachToTarget',{targetId:ui.targetId,flatten:true});out.ui=await c.eval(a.sessionId,'Object.keys(chrome.developerPrivate)');
 console.log(JSON.stringify(out,null,2));fs.writeFileSync(`${root}/probe.json`,JSON.stringify(out,null,2));
}finally{c.close();}
