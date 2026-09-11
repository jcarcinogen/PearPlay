// Live harness: never print CDP errors, URLs, page text, or raw exceptions.
import fs from 'node:fs';
const root=process.argv[2],op=process.argv[3]||'prepare';
let ws;let stage='connect';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
try{
const [port,path]=fs.readFileSync(`${root}/browser/google-chrome/DevToolsActivePort`,'utf8').trim().split('\n');
ws=new WebSocket(`ws://127.0.0.1:${port}${path}`);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=()=>j(Error('CONNECT'));});
let serial=0;const pending=new Map();ws.onmessage=e=>{try{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error('CDP')):p.resolve(m.result);}}catch{}};
const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>{pending.delete(id);reject(Error('TIMEOUT'));},25000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));});
const ev=async(s,expression)=>{const r=await send('Runtime.evaluate',{expression:`(async()=>{try{return await (${expression});}catch{return {safeError:true};}})()`,awaitPromise:true,returnByValue:true,userGesture:true},s);if(r.exceptionDetails)throw Error('EVALUATION');return r.result?.value;};
const attach=async id=>(await send('Target.attachToTarget',{targetId:id,flatten:true})).sessionId;
const targets=async()=>(await send('Target.getTargets')).targetInfos;
let id='gndkmajngklgjkcmbolddaodljgoabma';
if(op==='load'){console.log(JSON.stringify(await send('Extensions.loadUnpacked',{path:'/home/scott/Projects/PearPlay/extension'})));}
else{
let page=(await targets()).find(t=>t.type==='page'&&t.url==='https://www.fox13seattle.com/live');
if(op==='prepare'){
stage='sandbox';const check=await send('Target.createTarget',{url:'chrome://sandbox'});const cs=await attach(check.targetId);await sleep(500);console.log(JSON.stringify({sandbox:await ev(cs,`document.body.innerText.includes('adequately sandboxed')`)}));await send('Target.closeTarget',{targetId:check.targetId});
stage='permissions';const ui=await send('Target.createTarget',{url:'chrome://extensions'});const us=await attach(ui.targetId);await sleep(500);for(const host of ['http://*/*','https://*/*']){const ok=await ev(us,`chrome.developerPrivate.addHostPermission('${id}','${host}').then(()=>true)`);if(ok!==true)throw Error('PERMISSIONS');}await send('Target.closeTarget',{targetId:ui.targetId});
stage='page';const p=await send('Target.createTarget',{url:'https://www.fox13seattle.com/live'});page={targetId:p.targetId};
}
if(!page)throw Error('NO_PAGE');
const ps=await attach(page.targetId);await send('Network.enable',{},ps);await send('Network.setCacheDisabled',{cacheDisabled:true},ps);
let popup=(await targets()).find(t=>t.url===`chrome-extension://${id}/popup.html`);
if(!popup){const tab=(await send('Target.getTargets',{filter:[{type:'tab'}]})).targetInfos.find(t=>t.url==='https://www.fox13seattle.com/live');if(!tab)throw Error('NO_TAB');await send('Extensions.triggerAction',{id,targetId:tab.targetId});for(let i=0;i<30;i++){popup=(await targets()).find(t=>t.url===`chrome-extension://${id}/popup.html`);if(popup)break;await sleep(100);}}
if(!popup)throw Error('NO_POPUP');const s=await attach(popup.targetId);await sleep(200);
const tabId=await ev(s,`chrome.tabs.query({url:'https://www.fox13seattle.com/live'}).then(t=>t[0].id)`);if(!Number.isInteger(tabId))throw Error('TAB_ID');
const msg=(operation,args={})=>ev(s,`chrome.runtime.sendMessage(${JSON.stringify({op:operation,tabId,...args})})`);
const view=async()=>ev(s,`chrome.runtime.sendMessage({op:'view',tabId:${tabId}}).then(v=>({enabled:v.enabled,selected:v.selected,candidates:v.candidates,native:v.native,receiver:v.receiver}))`);
if(op==='prepare'){
const granted=await ev(s,`chrome.permissions.request({origins:['http://*/*','https://*/*']})`);if(granted!==true)throw Error('GRANT');console.log(JSON.stringify({permissions:await ev(s,'chrome.permissions.getAll()'),enable:await msg('enable'),hello:await msg('hello')}));
stage='reload';await send('Page.reload',{},ps);await sleep(12000);
}
if(op==='prepare'||op==='inspect'){
stage='inspect';console.log(JSON.stringify({player:await ev(ps,`({videos:[...document.querySelectorAll('video')].map(v=>({paused:v.paused,readyState:v.readyState,muted:v.muted})),playButtons:[...document.querySelectorAll('button,[role="button"]')].filter(b=>/play/i.test(b.getAttribute('aria-label')||b.textContent||'')).map(b=>({label:(b.getAttribute('aria-label')||b.textContent||'').slice(0,60)})).slice(0,15)})`)}));await msg('rescan');console.log(JSON.stringify(await view()));
}else if(op==='play'){
console.log(JSON.stringify({play:await ev(ps,`(async()=>{const b=[...document.querySelectorAll('button,[role="button"]')].find(b=>/^(play|play video)$/i.test((b.getAttribute('aria-label')||b.textContent||'').trim()));if(b){b.click();return 'button';}const v=document.querySelector('video');if(v){await v.play();return 'video';}return 'no-player';})()`)}));await sleep(10000);await msg('rescan');console.log(JSON.stringify(await view()));
}else if(op==='discover'){console.log(JSON.stringify(await msg('discover',{host:'192.168.50.92'})));}
else if(op==='start'){const candidate=process.argv[4],receiver=process.argv[5];if(!/^c\d+$/.test(candidate)||!receiver)throw Error('SELECTION');console.log(JSON.stringify({receiver:await msg('receiver',{id:receiver}),select:await msg('select',{id:candidate}),start:await msg('start')}));await sleep(3000);console.log(JSON.stringify(await msg('status')));}
else if(op==='status'||op==='stop'){console.log(JSON.stringify(await msg(op)));}
}
}catch{console.log(JSON.stringify({safeError:true,stage}));process.exitCode=1;}finally{ws?.close();}
