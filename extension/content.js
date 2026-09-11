(() => {
 if(globalThis.__pearplay){globalThis.__pearplay.scan();return;}
 const ids=new WeakMap();let serial=0;let live=new Map();let until=Date.now()+600000;let timer;
 async function scan(){
  if(Date.now()>until){clearInterval(timer);live.clear();return;}
  const videos=[];live=new Map();const roots=[document];let budget=20000;
  while(roots.length && budget>0 && videos.length<100){const root=roots.pop();for(const el of root.querySelectorAll('*')){if(--budget<=0||videos.length>=100)break;if(el.shadowRoot)roots.push(el.shadowRoot);if(el.tagName!=='VIDEO')continue;if(!ids.has(el))ids.set(el,`v${++serial}`);const videoId=ids.get(el);live.set(videoId,el);const url=el.currentSrc;if(typeof url==='string'&&/^https?:\/\//i.test(url)&&url.length<=16384)videos.push({videoId,url});}}
  try{const result=await chrome.runtime.sendMessage({op:'videos',videos});if(!result?.enabled){clearInterval(timer);live.clear();}}catch{clearInterval(timer);live.clear();}
 }
 chrome.runtime.onMessage.addListener((m,_sender,reply)=>{
  if(m.op==='rescan'){until=Date.now()+600000;clearInterval(timer);timer=setInterval(scan,1500);scan();reply({ok:true});return;}
  if(!['localPause','localResume'].includes(m.op))return;
  const el=live.get(m.videoId);
  if(!el?.isConnected||el.currentSrc!==m.url||(m.op==='localPause'&&m.confirmed!==true)){reply({ok:false,error:'VIDEO_CHANGED_OR_UNCONFIRMED'});return;}
  if(m.op==='localPause'){el.pause();reply({ok:true});return;}
  el.play().then(()=>reply({ok:true}),()=>reply({ok:false,error:'LOCAL_PLAY_BLOCKED'}));return true;
 });
 globalThis.__pearplay={scan};timer=setInterval(scan,1500);scan();
})();
