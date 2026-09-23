import {connectionState,downloadsFor} from './setup-model.mjs';
export async function mountSetup(document,chrome,fetch) {
  const $=id=>document.getElementById(id);
  const platform=await chrome.runtime.getPlatformInfo();
  const supported=['mac','linux'].includes(platform.os);
  $('platform').textContent=platform.os==='mac'?'For your Mac':platform.os==='linux'?'For your Linux computer':'This operating system is not supported';
  $('mac').hidden=platform.os!=='mac'; $('linux').hidden=platform.os!=='linux';
  let catalog=null;
  try {catalog=await (await fetch(chrome.runtime.getURL('releases.json'))).json();}catch{}
  const downloads=downloadsFor(catalog,platform,chrome.runtime.id);
  $('availability').textContent=downloads.length?'Choose the installer for your computer.':supported?'Preview installers are not published for this browser and platform yet. See the developer installation guide below.':'PearPlay Helper is available only for macOS and Linux.';
  for(const item of downloads){
    const link=document.createElement('a');link.href=item.url;link.rel='noopener noreferrer';link.className='button';
    const name={pkg:'Mac',deb:'Ubuntu / Debian',rpm:'Fedora','pkg.tar.zst':'Arch / Omarchy'}[item.format];
    link.textContent=`Download for ${name}`; $('downloads').append(link);
  }
  let ready=false;
  const check=async()=>{
    $('check').disabled=true;$('find').disabled=true;$('connection').textContent='Checking this browser’s connection…';
    try {
      const result=await chrome.runtime.sendMessage({op:'setupCheck'});
      const state=connectionState(result,result?.ok===false?result.error:null);
      ready=state.kind==='ready';$('connection').dataset.state=state.kind;$('connection').textContent=state.text;
    } catch {ready=false;$('connection').dataset.state='broken';$('connection').textContent=connectionState(null,'ACTION_FAILED').text;}
    finally {$('check').disabled=false;$('find').disabled=!ready;}
  };
  $('check').onclick=check;
  $('find').onclick=async()=>{
    if(!ready)return;
    $('find').disabled=true;$('receivers').textContent='Looking for Apple TVs on your network…';
    try {
      const result=await chrome.runtime.sendMessage({op:'setupFind'});
      if(result?.ok===false)throw Error('discovery_failed');
      const count=result.receivers?.length??0;
      $('receivers').textContent=count?`Found ${count} Apple TV${count===1?'':'s'}. Open a video, then click PearPlay in your browser toolbar to choose a TV and send.`:'No Apple TV found. Check that your TV is awake and on the same network. On a Mac, allow PearPlay local-network access in System Settings.';
    } catch {$('receivers').textContent='Could not find your TV. Check the helper connection and try again.';}
    finally {$('find').disabled=!ready;}
  };
  if(supported)await check();else {$('check').disabled=true;$('find').disabled=true;}
}
if(globalThis.document&&globalThis.chrome?.runtime?.id)mountSetup(document,chrome,fetch).catch(()=>{document.getElementById('connection').textContent='Setup could not load. Reopen this tab and try again.';});
