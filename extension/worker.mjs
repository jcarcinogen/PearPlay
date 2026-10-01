import {Sessions} from './core.mjs';
import {Native} from './native.mjs';
const KNOWN_ERRORS=['NATIVE_DISCONNECTED','NATIVE_TIMEOUT','INVALID_RESPONSE','busy','pairing_required','pairing_failed','transport_failed','receiver_not_discovered','receiver_unavailable','discovery_failed'];
export function createWorker(chrome,native=new Native(()=>chrome.runtime.connectNative('com.pearplay.helper'))) {
 const sessions=new Sessions();let receiver=null;let local=null;let firewall=null;let firewallBusy=false;
 async function checkFirewall(explicit=false){
  const previous=firewall;firewall=null;
  const r=native.view().receivers.find(r=>r.identifier===receiver);
  if(!r||!native.view().firewallSupport||firewallBusy||r.timingRequired===false&&!explicit)return;
  try{const result=await native.request('firewall',{receiver:r.identifier,host:r.address,action:'check'});
   if(receiver===r.identifier)firewall={...result,...(previous?.receiver===r.identifier&&previous?.host===r.address&&previous.change?{change:previous.change}:{}),receiver:r.identifier,host:r.address};
  }catch{} // Discovery still works if firewall inspection is unavailable.
 }
 async function inject(tabId,documentId){try{await chrome.scripting.executeScript({target:{tabId,documentIds:[documentId]},files:['content.js']});await chrome.tabs.sendMessage(tabId,{op:'rescan'},{documentId});return true;}catch{return false;}}
 async function scan(tabId){const s=sessions.tabs.get(tabId);const revision=s?.revision;const frames=await chrome.webNavigation.getAllFrames({tabId})??[];let scanned=0;if(!s||s!==sessions.tabs.get(tabId)||s.revision!==revision)return {scanned,total:frames.length};for(const f of frames.slice(0,128)){if(f.documentId&&s.frames.size<128&&!s.frames.has(f.frameId)){s.frames.set(f.frameId,f.documentId);s.parents.set(f.frameId,f.parentFrameId??-1);}}for(const f of frames.slice(0,128)){if(!f.documentId||s.frames.get(f.frameId)!==f.documentId)continue;if(await inject(tabId,f.documentId))scanned++;}return {scanned,total:frames.length};}
 async function message(m,sender){
  if(m?.op==='videos'){
   const tabId=sender.tab?.id;const enabled=sessions.view(tabId).enabled;
   if(enabled&&Array.isArray(m.videos)) sessions.videos({tabId,frameId:sender.frameId,documentId:sender.documentId},m.videos);
   return {enabled};
  }
  if(sender.url===chrome.runtime.getURL('setup.html')&&sender.frameId===0){
   if(firewallBusy)throw Error('busy');
   if(m?.op==='setupCheck')return native.request('hello',{});
   if(m?.op==='setupFind')return native.request('discover',{});
   throw Error('UNAUTHORIZED');
  }
  if(sender.tab||sender.url!==chrome.runtime.getURL('popup.html'))throw Error('UNAUTHORIZED');
  const tabId=m.tabId;
  if(firewallBusy&&!['view','openSetup'].includes(m.op))throw Error('busy');
  switch(m.op){
   case 'openSetup':await chrome.tabs.create({url:chrome.runtime.getURL('setup.html')});return {ok:true};
   case 'view':{
    try{const tab=await chrome.tabs.get(tabId);sessions.pageTitle(tabId,tab?.title);}catch{}
    return {...sessions.view(tabId),native:native.view(),receiver,firewall:native.view().firewallSupport?firewall:null,firewallBusy,localAvailable:!!local};
   }
   case 'enable':{
    sessions.enable(tabId);
    try{const tab=await chrome.tabs.get(tabId);sessions.pageTitle(tabId,tab?.title);}catch{}
    return scan(tabId,true);
   }
   case 'rescan':if(!sessions.view(tabId).enabled)throw Error('SESSION_EXPIRED');return scan(tabId);
   case 'disable':sessions.disable(tabId);return {ok:true};
   case 'select':sessions.select(tabId,m.id);return {ok:true};
   case 'receiver':if(!native.view().receivers.some(r=>r.identifier===m.id))throw Error('NO_RECEIVER');receiver=m.id;await checkFirewall();return {ok:true};
   case 'firewall':{
    const r=native.view().receivers.find(r=>r.identifier===receiver);
    if(!r||m.receiver!==receiver||!native.view().firewallSupport)throw Error('NO_RECEIVER');
    if(firewallBusy)throw Error('busy');
    if(m.action==='check'){await checkFirewall(true);return {ok:true};}
    if(m.action==='allow'&&r.timingRequired===false)throw Error('UNNEEDED_TIMING_PERMISSION');
    if(!['allow','remove'].includes(m.action)||m.confirmed!==true)throw Error('CONFIRM_FIREWALL_FIRST');
    firewallBusy=true;
    try{const result=await native.request('firewall',{receiver:r.identifier,host:r.address,action:m.action});
     if(receiver===r.identifier)firewall={...result,receiver:r.identifier,host:r.address};return {ok:true};
    }finally{firewallBusy=false;}
   }
   case 'start':{if(native.view().session?.delivery==='accepted')return native.view();const c=sessions.selected(tabId);const r=native.view().receivers.find(r=>r.identifier===receiver);if(!r)throw Error('NO_RECEIVER');return native.request('start',{receiver:r.identifier,host:r.address,url:c.url});}
   case 'pairBegin':{const r=native.view().receivers.find(x=>x.identifier===receiver);if(!r)throw Error('NO_RECEIVER');return native.request('pair_begin',{receiver:r.identifier,host:r.address});}
   case 'pair':{const r=native.view().receivers.find(x=>x.identifier===receiver);if(!r)throw Error('NO_RECEIVER');if(typeof m.pin!=='string'||!/^\d{4}$/.test(m.pin))throw Error('INVALID_PIN');return native.request('pair',{receiver:r.identifier,host:r.address,pin:m.pin});}
   case 'localPause':{if(m.confirmed!==true)throw Error('CONFIRM_TV_FIRST');const c=sessions.selected(tabId);if(!c.videoId)throw Error('NO_EXACT_VIDEO');const result=await chrome.tabs.sendMessage(tabId,{op:'localPause',confirmed:true,videoId:c.videoId,url:c.url},{documentId:c.documentId});if(result?.ok)local={tabId,...c};return result;}
   case 'localResume':{if(!local)throw Error('NO_LOCAL_VIDEO');return chrome.tabs.sendMessage(local.tabId,{op:'localResume',videoId:local.videoId,url:local.url},{documentId:local.documentId});}
   case 'discover':{
    const result=await native.request('discover',m.host?{host:m.host}:{});
    const list=native.view().receivers;
    if(list.length===1) receiver=list[0].identifier;
    else if(receiver&&!list.some(r=>r.identifier===receiver)) receiver=null;
    await checkFirewall();return result;}
   case 'hello':case 'status':case 'pause':case 'resume':case 'stop':return native.request(m.op,{});
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
