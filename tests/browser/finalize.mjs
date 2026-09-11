import {connect} from './cdp.mjs';import fs from 'node:fs';import assert from 'node:assert/strict';
const root=process.argv[2],c=await connect(root),out={};
try{
 out.version=await c.send('Browser.getVersion');out.extensions=await c.send('Extensions.getExtensions');
 const {targetId}=await c.send('Target.createTarget',{url:'chrome-extension://gndkmajngklgjkcmbolddaodljgoabma/popup.html'});const {sessionId:s}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 for(let i=0;i<50;i++){if(await c.eval(s,'!!chrome.runtime?.id'))break;await new Promise(r=>setTimeout(r,100));}
 out.afterUninstall=await c.eval(s,`new Promise(resolve=>{const p=chrome.runtime.connectNative('com.pearplay.helper');p.onDisconnect.addListener(()=>resolve(chrome.runtime.lastError?.message));p.onMessage.addListener(m=>resolve(m));p.postMessage({v:1,id:'after_uninstall',op:'hello',args:{}});})`);assert.equal(out.afterUninstall,'Specified native messaging host not found.');
 const sandbox=await c.send('Target.createTarget',{url:'chrome://sandbox'});const a=await c.send('Target.attachToTarget',{targetId:sandbox.targetId,flatten:true});for(let i=0;i<50;i++){out.sandbox=await c.eval(a.sessionId,'document.body?.innerText');if(out.sandbox?.includes('Sandbox'))break;await new Promise(r=>setTimeout(r,100));}
 await c.send('Extensions.uninstall',{id:'gndkmajngklgjkcmbolddaodljgoabma'});out.extensionsAfter=await c.send('Extensions.getExtensions');assert.equal(out.extensionsAfter.extensions.length,0);
 console.log(JSON.stringify(out,null,2));fs.writeFileSync(`${root}/final.json`,JSON.stringify(out,null,2));await c.send('Browser.close');
}finally{c.close();}
