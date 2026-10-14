import {Sessions,httpURL} from './core.mjs';
import {Native} from './native.mjs';
const KNOWN_ERRORS=['NATIVE_DISCONNECTED','NATIVE_TIMEOUT','INVALID_RESPONSE','busy','pairing_required','pairing_failed','transport_failed','receiver_not_discovered','receiver_unavailable','discovery_failed','VIDEO_CHANGED_OR_UNCONFIRMED','NO_EXACT_VIDEO','VIDEO_NOT_SENDABLE','NO_SEEK_WINDOW','INVALID_CONTROL','PIP_OTHER_VIDEO','BROWSER_CONTROL_BLOCKED','TV_SESSION_ACTIVE','TV_CONTROL_UNAVAILABLE'];
export function createWorker(chrome,native=new Native(()=>chrome.runtime.connectNative('com.pearplay.helper'))) {
 const sessions=new Sessions();let receiver=null;let local=null;let firewall=null;let firewallBusy=false;let pairing=null;let pairingBusy=false;
 let activeCast=null, preferredReceiverId=null, lastStatusPoll=0, statusPoll=null, castStarting=false;
 const casting=tv=>['connecting','playing','paused','stopping'].includes(tv.state)||tv.session?.delivery==='accepted';
 const preferenceReady=Promise.resolve().then(()=>chrome.storage?.local?.get('preferredReceiverId')).then(saved=>{
  if(typeof saved?.preferredReceiverId==='string'&&saved.preferredReceiverId.length<=1024)preferredReceiverId=saved.preferredReceiverId;
 }).catch(()=>{});
 async function rememberReceiver(id){preferredReceiverId=id;try{await chrome.storage?.local?.set({preferredReceiverId:id});}catch{}}
 const sourceAvailable=cast=>!!cast?.source?.videoId&&sessions.current(cast.sourceTabId,cast.source);
 function castView(){
  if(!activeCast)return null;
  const {id,title,receiverId,receiverName,sourceTabId,browserMuted}=activeCast;
  return {id,title,receiverId,receiverName,sourceTabId,browserMuted,sourceAvailable:sourceAvailable(activeCast)};
 }
 let badgeKey='';
 function reflectNative(){
  const tv=native.view();
  if(['idle','stopped','error'].includes(tv.state)&&!castStarting)activeCast=null;
  const text=tv.error?'?':tv.state==='paused'?'Ⅱ':tv.state==='playing'?'TV':casting(tv)?'…':'';
  const title=tv.error?'PearPlay — needs attention':tv.state==='paused'?'PearPlay — TV paused':tv.state==='playing'?'PearPlay — TV reports playing':casting(tv)?'PearPlay — TV session':'PearPlay';
  const key=text+'|'+title;if(key===badgeKey)return;badgeKey=key;
  for(const [method,args] of [['setBadgeText',{text}],['setTitle',{title}],['setBadgeBackgroundColor',{color:'#355b29'}]]){
   try{Promise.resolve(chrome.action?.[method]?.(args)).catch(()=>{});}catch{}
  }
 }
 native.onChange?.(reflectNative);
 async function request(op,args={}){try{return await native.request(op,args);}finally{reflectNative();}}
 async function refreshCast(){
  if(!activeCast||!casting(native.view())||firewallBusy||pairingBusy||castStarting)return;
  if(statusPoll)return statusPoll;
  if(Date.now()-lastStatusPoll<2000)return;
  lastStatusPoll=Date.now();
  statusPoll=request('status').catch(()=>{}).finally(()=>{statusPoll=null;});
  return statusPoll;
 }
 async function checkFirewall(explicit=false){
  const previous=firewall;firewall=null;
  const r=native.view().receivers.find(r=>r.identifier===receiver);
  if(!r||!native.view().firewallSupport||firewallBusy||r.timingRequired===false&&!explicit)return;
  try{const result=await request('firewall',{receiver:r.identifier,host:r.address,action:'check'});
   if(receiver===r.identifier)firewall={...result,...(previous?.receiver===r.identifier&&previous?.host===r.address&&previous.change?{change:previous.change}:{}),receiver:r.identifier,host:r.address};
  }catch{} // Discovery still works if firewall inspection is unavailable.
 }
 async function inject(tabId,documentId){try{await chrome.scripting.executeScript({target:{tabId,documentIds:[documentId]},files:['content.js']});await chrome.tabs.sendMessage(tabId,{op:'rescan'},{documentId});return true;}catch{return false;}}
 async function scan(tabId){const s=sessions.tabs.get(tabId);const revision=s?.revision;const frames=await chrome.webNavigation.getAllFrames({tabId})??[];let scanned=0;if(!s||s!==sessions.tabs.get(tabId)||s.revision!==revision)return {scanned,total:frames.length};for(const f of frames.slice(0,128)){if(f.documentId&&s.frames.size<128&&!s.frames.has(f.frameId)){s.frames.set(f.frameId,f.documentId);s.parents.set(f.frameId,f.parentFrameId??-1);}}for(const f of frames.slice(0,128)){if(!f.documentId||s.frames.get(f.frameId)!==f.documentId)continue;if(await inject(tabId,f.documentId))scanned++;}return {scanned,total:frames.length};}
 async function message(m,sender){
  if(m?.op==='videos'){
   const tabId=sender.tab?.id;const enabled=sessions.view(tabId).enabled;
   const origin={tabId,frameId:sender.frameId,documentId:sender.documentId};
   if(enabled)sessions.resources(origin,m.resources);
   const keepAlive=enabled&&Array.isArray(m.videos)&&sessions.videos(origin,m.videos)===true;
   return {enabled,keepAlive};
  }
  if(sender.url===chrome.runtime.getURL('setup.html')&&sender.frameId===0){
   if(firewallBusy)throw Error('busy');
   if(m?.op==='setupCheck')return request('hello',{});
   if(m?.op==='setupFind')return request('discover',{});
   throw Error('UNAUTHORIZED');
  }
  if(sender.tab||sender.url!==chrome.runtime.getURL('popup.html'))throw Error('UNAUTHORIZED');
  const tabId=m.tabId;
  if((firewallBusy||pairingBusy||castStarting)&&!['view','openSetup'].includes(m.op))throw Error('busy');
  switch(m.op){
   case 'openSetup':await chrome.tabs.create({url:chrome.runtime.getURL('setup.html')});return {ok:true};
   case 'view':{
    await refreshCast();reflectNative();
    try{const tab=await chrome.tabs.get(tabId);sessions.pageTitle(tabId,tab?.title);}catch{}
    return {...sessions.view(tabId),native:native.view(),activeCast:castView(),receiver:activeCast?.receiverId??receiver,pairingReceiver:pairing?.receiver??null,pairingBusy,firewall:native.view().firewallSupport?firewall:null,firewallBusy,localAvailable:!!local};
   }
   case 'enable':{
    // Find again preserves the deliberately selected video in this tab.
    if(!sessions.view(tabId).enabled)sessions.enable(tabId);
    else sessions.tabs.get(tabId).at=sessions.now();
    try{const tab=await chrome.tabs.get(tabId);sessions.pageTitle(tabId,tab?.title);}catch{}
    return scan(tabId,true);
   }
   case 'rescan':if(!sessions.view(tabId).enabled)throw Error('SESSION_EXPIRED');sessions.tabs.get(tabId).at=sessions.now();return scan(tabId);
   case 'disable':sessions.disable(tabId);return {ok:true};
   case 'select':sessions.select(tabId,m.id);return {ok:true};
   case 'receiver':{
    if(activeCast&&casting(native.view()))throw Error('TV_SESSION_ACTIVE');
    await preferenceReady;
    if(!native.view().receivers.some(r=>r.identifier===m.id))throw Error('NO_RECEIVER');
    if(receiver!==m.id)pairing=null;receiver=m.id;await rememberReceiver(receiver);await checkFirewall();return {ok:true};
   }
   case 'firewall':{
    const r=native.view().receivers.find(r=>r.identifier===receiver);
    if(!r||m.receiver!==receiver||!native.view().firewallSupport)throw Error('NO_RECEIVER');
    if(firewallBusy)throw Error('busy');
    if(m.action==='check'){await checkFirewall(true);return {ok:true};}
    if(m.action==='allow'&&r.timingRequired===false)throw Error('UNNEEDED_TIMING_PERMISSION');
    if(!['allow','remove'].includes(m.action)||m.confirmed!==true)throw Error('CONFIRM_FIREWALL_FIRST');
    firewallBusy=true;
    try{const result=await request('firewall',{receiver:r.identifier,host:r.address,action:m.action});
     if(receiver===r.identifier)firewall={...result,receiver:r.identifier,host:r.address};return {ok:true};
    }finally{firewallBusy=false;}
   }
   case 'start':{
    if(native.view().session?.delivery==='accepted')return native.view();
    if(activeCast&&casting(native.view()))throw Error('TV_SESSION_ACTIVE');
    const c=sessions.selected(tabId);
    if(!httpURL(c.url))throw Error('VIDEO_NOT_SENDABLE');
    const r=native.view().receivers.find(r=>r.identifier===receiver);
    if(!r)throw Error('NO_RECEIVER');
    if(c.videoId){
     const result=await chrome.tabs.sendMessage(tabId,{op:'validateVideo',videoId:c.videoId,url:c.url},{documentId:c.documentId});
     if(result?.ok!==true)throw Error('VIDEO_CHANGED_OR_UNCONFIRMED');
    }
    if(!sessions.current(tabId,c)||sessions.selected(tabId)!==c||receiver!==r.identifier)throw Error('VIDEO_CHANGED_OR_UNCONFIRMED');
    if(castStarting||activeCast&&casting(native.view()))throw Error('TV_SESSION_ACTIVE');
    const intent={id:crypto.randomUUID(),title:sessions.view(tabId).candidates.find(item=>item.id===c.id)?.label||'Video sent to TV',receiverId:r.identifier,receiverName:r.label,sourceTabId:tabId,source:{...c},browserMuted:null};
    activeCast=intent;castStarting=true;
    try{const result=await request('start',{receiver:r.identifier,host:r.address,url:c.url});await rememberReceiver(r.identifier);return result;}
    catch(error){if(activeCast===intent)activeCast=null;throw error;}
    finally{castStarting=false;reflectNative();}
   }
   case 'pairBegin':case 'pair':{
    const r=native.view().receivers.find(x=>x.identifier===receiver);if(!r)throw Error('NO_RECEIVER');
    if(m.op==='pair'&&(typeof m.pin!=='string'||!/^\d{4}$/.test(m.pin)))throw Error('INVALID_PIN');
    // Worker-owned, non-secret intent survives popup closure. A reopened popup
    // deliberately starts fresh instead of guessing whether a TV PIN is live.
    const intent={receiver:r.identifier};pairing=intent;pairingBusy=true;
    try{
     const result=await request(m.op==='pair'?'pair':'pair_begin',{receiver:r.identifier,host:r.address,...(m.op==='pair'?{pin:m.pin}:{})});
     if(m.op==='pair'&&pairing===intent)pairing=null;
     return result;
    }finally{pairingBusy=false;}
   }
   case 'castMute':{
    const cast=activeCast;
    if(!cast||m.castId!==cast.id||!casting(native.view())||!sourceAvailable(cast)||typeof m.value!=='boolean')throw Error('VIDEO_CHANGED_OR_UNCONFIRMED');
    const c=cast.source;
    const result=await chrome.tabs.sendMessage(cast.sourceTabId,{op:'browserControl',videoId:c.videoId,url:c.url,action:'mute',value:m.value},{documentId:c.documentId});
    if(activeCast!==cast||!sourceAvailable(cast)||!casting(native.view()))throw Error('VIDEO_CHANGED_OR_UNCONFIRMED');
    if(result?.ok!==true)throw Error('VIDEO_CHANGED_OR_UNCONFIRMED');
    cast.browserMuted=typeof result.muted==='boolean'?result.muted:null;
    return {ok:true};
   }
   case 'browserControl':{
    const tv=native.view();
    if(['connecting','playing','paused','stopping'].includes(tv.state)||tv.session?.delivery==='accepted')throw Error('TV_SESSION_ACTIVE');
    const c=sessions.selected(tabId);
    if(!c.videoId)throw Error('NO_EXACT_VIDEO');
    if(m.id!==c.id)throw Error('VIDEO_CHANGED_OR_UNCONFIRMED');
    if(!['status','play','pause','mute','seek','skip','pip','return'].includes(m.action))throw Error('INVALID_CONTROL');
    const result=await chrome.tabs.sendMessage(tabId,{op:'browserControl',videoId:c.videoId,url:c.url,action:m.action,value:m.value},{documentId:c.documentId});
    if(!sessions.current(tabId,c)||sessions.selected(tabId)!==c)return {ok:false,error:'VIDEO_CHANGED_OR_UNCONFIRMED'};
    return result;
   }
   case 'localPause':{if(m.confirmed!==true)throw Error('CONFIRM_TV_FIRST');const c=sessions.selected(tabId);if(!c.videoId)throw Error('NO_EXACT_VIDEO');const result=await chrome.tabs.sendMessage(tabId,{op:'localPause',confirmed:true,videoId:c.videoId,url:c.url},{documentId:c.documentId});if(!sessions.current(tabId,c))return {ok:false,error:'VIDEO_CHANGED_OR_UNCONFIRMED'};if(result?.ok)local={tabId,...c};return result;}
   case 'localResume':{const c=local;if(!c||!sessions.current(c.tabId,c))throw Error('NO_LOCAL_VIDEO');const result=await chrome.tabs.sendMessage(c.tabId,{op:'localResume',videoId:c.videoId,url:c.url},{documentId:c.documentId});return local===c&&sessions.current(c.tabId,c)?result:{ok:false,error:'VIDEO_CHANGED_OR_UNCONFIRMED'};}
   case 'discover':{
    const ongoing=activeCast&&casting(native.view());
    await preferenceReady;
    const result=await request('discover',m.host?{host:m.host}:{});
    if(ongoing)return result;
    const list=native.view().receivers;
    if(preferredReceiverId&&list.some(r=>r.identifier===preferredReceiverId))receiver=preferredReceiverId;
    else if(list.length===1) receiver=list[0].identifier;
    else if(receiver&&!list.some(r=>r.identifier===receiver)) receiver=null;
    await checkFirewall();return result;}
   case 'stop':{const result=await request('stop',{});pairing=null;activeCast=null;return result;}
   case 'pause':case 'resume':{
    const tv=native.view(),control=tv.tvControl;
    if(!control||control.receiver!==(activeCast?.receiverId??receiver)||m.session!==control.session||!tv.capabilities.includes(m.op)||tv.state!==(m.op==='pause'?'playing':'paused'))throw Error('TV_CONTROL_UNAVAILABLE');
    return request(m.op,{session:control.session});
   }
   case 'hello':case 'status':return request(m.op,{});
   default:throw Error('UNKNOWN_OPERATION');
  }
 }
 const begin=e=>sessions.begin(e);const respond=e=>sessions.response(e);
 const syncNetwork=async()=>{
  const origins=(await chrome.permissions.getAll()).origins?.filter(o=>/^https?:/.test(o))??[];
  chrome.webRequest.onBeforeRequest.removeListener(begin);
  chrome.webRequest.onResponseStarted.removeListener(respond);
  if(!origins.length)return;
  chrome.webRequest.onBeforeRequest.addListener(begin,{urls:origins});
  chrome.webRequest.onResponseStarted.addListener(respond,{urls:origins},['responseHeaders']);
 };
 chrome.permissions.onAdded.addListener(()=>void syncNetwork());
 chrome.permissions.onRemoved.addListener(()=>void syncNetwork());
 void syncNetwork();
 const navigation=e=>{sessions.commit(e);if(local?.tabId===e.tabId&&(e.frameId===0||local.frameId===e.frameId))local=null;if(sessions.view(e.tabId).enabled&&e.documentId)void inject(e.tabId,e.documentId);};
 chrome.webNavigation.onCommitted.addListener(navigation);chrome.webNavigation.onHistoryStateUpdated.addListener(navigation);
 chrome.tabs.onRemoved.addListener(id=>{sessions.disable(id);if(local?.tabId===id)local=null;});
 chrome.alarms.create('expire',{periodInMinutes:1});chrome.alarms.onAlarm.addListener(()=>{sessions.sweep();if(local&&!sessions.view(local.tabId).enabled)local=null;});
 chrome.runtime.onInstalled?.addListener(details=>{if(details.reason==='install')void chrome.tabs.create({url:chrome.runtime.getURL('setup.html')}).catch(()=>{});});
 chrome.runtime.onMessage.addListener((m,sender,reply)=>{message(m,sender).then(reply,error=>reply({ok:false,error:KNOWN_ERRORS.includes(error?.message)?error.message:'ACTION_FAILED'}));return true;});
 return {message};
}
if(globalThis.chrome?.runtime?.id)createWorker(globalThis.chrome);
