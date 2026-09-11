(async () => {
 const $=id=>document.getElementById(id);const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
 const notice=text=>{$('notice').textContent=text;};
 const send=async(op,args={})=>{const r=await chrome.runtime.sendMessage({op,tabId:tab?.id,...args});if(r?.ok===false)throw Error('ACTION_FAILED');return r;};
 const options=(id,items,selected)=>{const el=$(id);el.replaceChildren();const blank=document.createElement('option');blank.value='';blank.textContent='Choose explicitly';el.append(blank);for(const item of items){const o=document.createElement('option');o.value=item.id??item.identifier;o.textContent=item.label;el.append(o);}el.value=selected??'';};
 async function refresh(){try{const s=await send('view');options('candidate',s.candidates,s.selected);options('receiver',s.native.receivers,s.receiver);$('state').textContent=`Collection: ${s.enabled?'enabled':'off / expired'}; TV: ${s.native.state}; evidence: ${s.native.evidence}. ${s.native.error??''}`;const c=s.candidates.find(c=>c.id===s.selected);$('start').disabled=!c||!s.receiver;$('confirmTV').disabled=!c?.videoId;$('localResume').disabled=!s.localAvailable;for(const op of ['pause','resume','stop'])$(op).disabled=!s.native.capabilities.includes(op);}catch{notice('Extension unavailable. Reopen popup.');}}
 const act=fn=>async()=>{try{await fn();await refresh();}catch{notice('Action failed. Check helper installation/pairing, permissions, selection, or expired session; rescan after reload.');}};
 for(const op of ['enable','disable','rescan'])$(op).onclick=act(async()=>{const r=await send(op);notice(r.total!==undefined?`Scanned ${r.scanned} of ${r.total} frames. Missing frames need access or are restricted.`:'Collection ended.');});
 $('candidate').onchange=act(()=>send('select',{id:$('candidate').value}));$('receiver').onchange=act(()=>send('receiver',{id:$('receiver').value}));
 for(const op of ['hello','start','status','stop','pause','resume','localResume'])$(op).onclick=act(()=>send(op));
 $('discover').onclick=act(()=>send('discover',{host:$('host').value}));$('confirmTV').onclick=act(()=>send('localPause',{confirmed:true}));
 // Call permission requests directly in the user gesture, before any awaited work.
 $('grantAll').onclick=act(async()=>{const granted=await chrome.permissions.request({origins:['http://*/*','https://*/*']});notice(granted?'Access granted. Enable collection, reload/play and rescan; earlier requests cannot be recovered.':'Access denied. Only permitted frames can be scanned.');});
 $('grantSite').onclick=act(async()=>{const u=new URL(tab.url);if(!['http:','https:'].includes(u.protocol))throw Error('UNSUPPORTED_PAGE');const granted=await chrome.permissions.request({origins:[`${u.protocol}//${u.hostname}/*`]});notice(granted?'Site access granted; other-origin frames/CDNs still need access. Enable, reload/play and rescan.':'Access denied.');});
 $('reload').onclick=act(()=>chrome.tabs.reload(tab.id));await refresh();setInterval(refresh,2000);
})();
