import {connect} from './cdp.mjs';
import http from 'node:http';import fs from 'node:fs';import assert from 'node:assert/strict';
const root=process.argv[2],c=await connect(root),id='gndkmajngklgjkcmbolddaodljgoabma',out={requests:[]};
const server=http.createServer((req,res)=>{out.requests.push(req.url);if(req.url==='/'){res.setHeader('Content-Type','text/html');res.end('<!doctype html><title>PearPlay synthetic only</title><video preload="metadata" src="/dom.mp4"></video>');}else if(req.url==='/network.m3u8'){res.setHeader('Content-Type','application/vnd.apple.mpegurl');res.end('#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-ENDLIST\n');}else{res.setHeader('Content-Type','video/mp4');res.end('synthetic candidate fixture, not playable media');}});await new Promise(r=>server.listen(0,'127.0.0.1',r));const url=`http://127.0.0.1:${server.address().port}/`;
const attach=async targetId=>(await c.send('Target.attachToTarget',{targetId,flatten:true})).sessionId;
async function ready(s,expr){for(let n=0;n<50;n++){if(await c.eval(s,expr))return;await new Promise(r=>setTimeout(r,100));}throw Error('not ready '+expr);}
try{
 const ui=await c.send('Target.createTarget',{url:'chrome://extensions'});const us=await attach(ui.targetId);await ready(us,'!!chrome.developerPrivate');
 try{out.grant=await c.eval(us,`chrome.developerPrivate.addHostPermission('${id}','http://127.0.0.1/*').then(()=>true)`);}catch(e){out.grantError=String(e);}
 const page=await c.send('Target.createTarget',{url});const ps=await attach(page.targetId);await ready(ps,'document.title==="PearPlay synthetic only"');
 const t=(await c.send('Target.getTargets',{filter:[{type:'tab'}]})).targetInfos.find(t=>t.url===url);await c.send('Extensions.triggerAction',{id,targetId:t.targetId});
 let popup;for(let n=0;n<50;n++){popup=(await c.send('Target.getTargets')).targetInfos.find(t=>t.url===`chrome-extension://${id}/popup.html`);if(popup)break;await new Promise(r=>setTimeout(r,100));}const s=await attach(popup.targetId);await ready(s,'!!chrome.runtime?.id');
 const tabId=await c.eval(s,`chrome.tabs.query({url:'${url}'}).then(t=>t[0].id)`);const msg=(op)=>c.eval(s,`chrome.runtime.sendMessage({op:'${op}',tabId:${tabId}})`);
 out.optionalRequest=await c.eval(s,`chrome.permissions.request({origins:['http://127.0.0.1/*']})`);
 out.permissions=await c.eval(s,'chrome.permissions.getAll()');out.before=await msg('view');out.enable=await msg('enable');
 await ready(ps,'document.querySelector("video").currentSrc.endsWith("/dom.mp4")');out.currentSrc=await c.eval(ps,'document.querySelector("video").currentSrc');
 await msg('rescan');out.dom=await msg('view');
 out.fetchHls=await c.eval(ps,'fetch("/network.m3u8").then(r=>r.status)');await new Promise(r=>setTimeout(r,200));out.hls=await msg('view');
 out.fetchMp4=await c.eval(ps,'fetch("/network.mp4").then(r=>r.status)');await new Promise(r=>setTimeout(r,200));out.mp4=await msg('view');
 out.disable=await msg('disable');out.after=await msg('view');
 assert(out.dom.candidates.some(x=>x.videoId));assert(out.hls.candidates.length>out.dom.candidates.length);assert(out.mp4.candidates.length>out.hls.candidates.length);assert.equal(out.after.candidates.length,0);out.passed=true;
}catch(e){out.error=String(e);process.exitCode=1;}finally{fs.writeFileSync(`${root}/candidates.json`,JSON.stringify(out,null,2));console.log(JSON.stringify(out,null,2));server.close();c.close();}
