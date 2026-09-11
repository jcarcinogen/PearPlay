// Sensitive playlist data stays in memory; output is a strict safe summary only.
import fs from 'node:fs';
let ws,stage='connect';const sleep=ms=>new Promise(r=>setTimeout(r,ms));
try{
 const root=process.argv[2];const [port,path]=fs.readFileSync(`${root}/browser/google-chrome/DevToolsActivePort`,'utf8').trim().split('\n');
 ws=new WebSocket(`ws://127.0.0.1:${port}${path}`);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=()=>j(Error());});
 let n=0;const pending=new Map(),listeners=[];
 ws.onmessage=e=>{try{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.t);m.error?p.j(Error()):p.r(m.result);}else for(const f of listeners)f(m);}catch{}};
 const send=(method,params={},sessionId)=>new Promise((r,j)=>{const id=++n,t=setTimeout(()=>{pending.delete(id);j(Error());},25000);pending.set(id,{r,j,t});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));});
 const ev=async(s,expression)=>{const r=await send('Runtime.evaluate',{expression:`(async()=>{try{return await (${expression});}catch{return {safeError:true};}})()`,awaitPromise:true,returnByValue:true,userGesture:true},s);if(r.exceptionDetails)throw Error();return r.result?.value;};
 const targets=async()=>(await send('Target.getTargets')).targetInfos;const attach=async id=>(await send('Target.attachToTarget',{targetId:id,flatten:true})).sessionId;
 const ext='gndkmajngklgjkcmbolddaodljgoabma';const page=(await targets()).find(t=>t.type==='page'&&t.url==='https://www.fox13seattle.com/live');if(!page)throw Error();const ps=await attach(page.targetId);
 let popup=(await targets()).find(t=>t.url===`chrome-extension://${ext}/popup.html`);
 if(!popup){const tab=(await send('Target.getTargets',{filter:[{type:'tab'}]})).targetInfos.find(t=>t.url===page.url);await send('Extensions.triggerAction',{id:ext,targetId:tab.targetId});for(let i=0;i<30&&!popup;i++){await sleep(100);popup=(await targets()).find(t=>t.url===`chrome-extension://${ext}/popup.html`);}}
 if(!popup)throw Error();const s=await attach(popup.targetId);const tabId=await ev(s,`chrome.tabs.query({url:'https://www.fox13seattle.com/live'}).then(t=>t[0].id)`);
 const view=()=>ev(s,`chrome.runtime.sendMessage({op:'view',tabId:${tabId}})`);const click=id=>ev(s,`(()=>{const e=document.getElementById(${JSON.stringify(id)});if(!e||e.disabled)return false;e.click();return true;})()`);
 stage='fresh-collection';const before=await view();console.log(JSON.stringify({collectionExpired:!before.enabled,refreshing:true}));await click('enable');await sleep(300);
 const frame=(await send('Page.getFrameTree',{},ps)).frameTree.frame.id;
 await send('Network.enable',{maxTotalBufferSize:10000000,maxResourceBufferSize:2000000},ps);await send('Network.setCacheDisabled',{cacheDisabled:true},ps);
 const records=[],byRequest=new Map();let active=false;
 listeners.push(m=>{if(m.sessionId!==ps||!active)return;const p=m.params;
 if(m.method==='Network.responseReceived'&&p.frameId===frame){const r=p.response;let u;try{u=new URL(r.url);}catch{return;}if(!(/mpegurl/i.test(r.mimeType)||/\.m3u8$/i.test(u.pathname)))return;if(records.some(x=>x.url===r.url))return;const rec={url:r.url,requestId:p.requestId,host:u.hostname,body:null};records.push(rec);byRequest.set(p.requestId,rec);}
 if(m.method==='Network.loadingFinished'&&byRequest.has(p.requestId)){const rec=byRequest.get(p.requestId);send('Network.getResponseBody',{requestId:p.requestId},ps).then(r=>{rec.body=r.base64Encoded?Buffer.from(r.body,'base64').toString():r.body;}).catch(()=>{});}
 });
 active=true;await send('Page.reload',{},ps);await sleep(18000);
 await ev(ps,`(async()=>{const v=document.querySelector('video');if(v&&v.paused){try{await v.play();}catch{}}return true;})()`);await sleep(5000);active=false;
 stage='classify';const v=await view();
 if(!v.enabled||!records.length||v.candidates.length!==records.length||v.candidates.some((c,i)=>c.videoId||!c.label.includes('frame 0')||!c.label.startsWith(records[i].host+' · HLS '))){console.log(JSON.stringify({mappingVerified:false,enabled:v.enabled,candidateIds:v.candidates.map(c=>c.id),responseCount:records.length}));throw Error();}stage='playlist-body';
 for(let i=0;i<records.length;i++){const r=records[i];r.id=v.candidates[i].id;if(!r.body){r.body=await ev(ps,`fetch(${JSON.stringify(r.url)},{credentials:'include',cache:'no-store'}).then(r=>r.ok?r.text():null)`);}if(typeof r.body!=='string'||!r.body.startsWith('#EXTM3U'))throw Error();r.kind=/#EXT-X-STREAM-INF:/.test(r.body)?'master':/#EXTINF:/.test(r.body)?'media':'unknown';}
 const masters=records.filter(r=>r.kind==='master');
 const roles=new Map();
 function summarize(body,base){const lines=body.split(/\r?\n/);let variants=0,audio=0,iframe=0;const resolutions=[],bandwidths=[];for(let i=0;i<lines.length;i++){const line=lines[i];if(line.startsWith('#EXT-X-STREAM-INF:')){variants++;const res=/RESOLUTION=(\d+x\d+)/.exec(line)?.[1];if(res)resolutions.push(res);const bw=/BANDWIDTH=(\d+)/.exec(line)?.[1];if(bw)bandwidths.push(Number(bw));const next=lines.slice(i+1).find(l=>l.trim()&&!l.startsWith('#'));if(next)roles.set(new URL(next,base).href,'video variant');}if(line.startsWith('#EXT-X-I-FRAME-STREAM-INF'))iframe++;if(line.startsWith('#EXT-X-MEDIA:')&&/TYPE=AUDIO/.test(line)){audio++;const uri=/URI="([^"]+)"/.exec(line)?.[1];if(uri)roles.set(new URL(uri,base).href,'audio rendition');}}return {variants,audioRenditions:audio,iframeStreams:iframe,endlist:/#EXT-X-ENDLIST/.test(body),programDateTime:/#EXT-X-PROGRAM-DATE-TIME:/.test(body),resolutions:[...new Set(resolutions)],bandwidths};}
 for(const master of masters)master.summary=summarize(master.body,master.url);
 for(const r of records)if(r.kind==='media'){r.role=roles.get(r.url);if(!r.role){const u=new URL(r.url);const matches=[...roles].filter(([url])=>{const p=new URL(url);return p.origin===u.origin&&p.pathname===u.pathname;});if(matches.length===1)r.role=matches[0][1];}r.role??='unlinked media';}
 const program=masters.filter(m=>m.summary.variants>0&&!m.summary.endlist);
 const pathOnly=u=>{const x=new URL(u);return x.origin+x.pathname;};
 const ladder=m=>JSON.stringify({r:m.summary.resolutions,b:m.summary.bandwidths,v:m.summary.variants,e:m.summary.endlist});
 const equivalent=program.length===2&&(program[0].body===program[1].body||pathOnly(program[0].url)===pathOnly(program[1].url)||ladder(program[0])===ladder(program[1]));
 const chosen=program.length===1?program[0]:equivalent?program[0]:null;
 console.log(JSON.stringify({candidates:records.map(r=>({id:r.id,classification:r.role||r.kind,...(r.summary||{})})),mapping:'fresh main-frame response insertion order',uniqueMaster:masters.length===1,uniqueLiveProgramMaster:program.length===1,equivalentLiveProgramMasters:equivalent,programMasterId:chosen?chosen.id:null}));
 if(!chosen||records.some(r=>r.kind!=='master'&&!['video variant','audio rendition'].includes(r.role)))throw Error();
 if(process.argv[3]!=='cast')throw Error();
 stage='saved-identity';const credentialPath='/home/scott/.local/state/pearplay/credentials.json';const stat=fs.lstatSync(credentialPath);if(!stat.isFile()||(stat.mode&0o777)!==0o600||stat.uid!==process.getuid()||stat.nlink!==1)throw Error();const saved=JSON.parse(fs.readFileSync(credentialPath,'utf8'));if(Object.keys(saved).sort().join(',')!=='credentials,identifier'||typeof saved.identifier!=='string'||!saved.identifier)throw Error();
 stage='discover';await ev(s,`(()=>{document.getElementById('host').value='192.168.50.92';return true;})()`);await click('discover');let found;for(let i=0;i<25;i++){await sleep(1000);found=(await view()).native.receivers.find(r=>r.identifier===saved.identifier&&r.address==='192.168.50.92');if(found)break;}if(!found)throw Error();console.log(JSON.stringify({savedReceiverMatched:true}));
 stage='select';await sleep(2200);for(const [id,value]of [['candidate',chosen.id],['receiver',found.identifier]]){const ok=await ev(s,`(()=>{const e=document.getElementById(${JSON.stringify(id)});e.value=${JSON.stringify(value)};if(e.value!==${JSON.stringify(value)})return false;e.dispatchEvent(new Event('change',{bubbles:true}));return true;})()`);if(!ok)throw Error();await sleep(500);}
 const selected=await view();if(selected.selected!==chosen.id||selected.receiver!==found.identifier)throw Error();stage='start';await sleep(2200);if(!await click('start'))throw Error();await sleep(5000);await click('status');await sleep(2000);const after=await view();console.log(JSON.stringify({selected:after.selected,state:after.native.state,evidence:after.native.evidence,error:after.native.error,chromeAndNativeLeftOpen:true}));
}catch{console.log(JSON.stringify({safeError:true,stage}));process.exitCode=1;}finally{ws?.close();}
