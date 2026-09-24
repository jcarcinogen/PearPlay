import {connectionState,downloadsFor} from './setup-model.mjs';
export async function mountSetup(document,chrome,fetch) {
  const $=id=>document.getElementById(id);
  const platform=await chrome.runtime.getPlatformInfo();
  const supported=platform.os==='linux';
  $('platform').textContent=supported?'For your Linux computer':platform.os==='mac'?'Mac support is coming soon.':'PearPlay currently supports Linux only.';
  if(!supported){
    $('installSection').hidden=true;$('browserSection').hidden=true;
    $('check').disabled=true;$('find').disabled=true;
    return;
  }
  let catalog=null;
  try {catalog=await (await fetch(chrome.runtime.getURL('releases.json'))).json();}catch{}
  const downloads=downloadsFor(catalog,platform,chrome.runtime.id);
  const localTest=supported&&catalog?.localInstallerTest===true&&catalog.extensionId===chrome.runtime.id;
  $('availability').textContent=localTest?'Installer rehearsal — use the development installer supplied with this test. Public downloads are not available yet.':downloads.length?'Choose the installer for your computer.':supported?'Preview installers are not published for this browser and platform yet. See the developer installation guide below.':'PearPlay currently supports Linux only. Mac support is coming soon.';
  for(const item of downloads){
    const link=document.createElement('a');link.href=item.url;link.rel='noopener noreferrer';link.className='button';
    const name={deb:'Ubuntu / Debian',rpm:'Fedora','pkg.tar.zst':'Arch / Omarchy'}[item.format];
    link.textContent=`Download for ${name}`; $('downloads').append(link);
  }
  const preview=!downloads.length&&!localTest;
  $('linux').hidden=preview||platform.os!=='linux';
  $('packagedRepair').hidden=preview;
  $('development').hidden=!preview||platform.os!=='linux';
  const quote=value=>"'"+value.replaceAll("'", "'\"'\"'")+"'";
  const updateCommand=()=>{
    const source=($('sourcePath').value??'').trim();
    const valid=source.startsWith('/')&&!/[\r\n\0]/.test(source)&&/^[a-p]{32}$/.test(chrome.runtime.id);
    $('copyCommand').disabled=!valid;
    $('installCommand').textContent=valid?[
      `cd -- ${quote(source)} &&`,
      'test -f helper/install.py && test -f requirements.txt &&',
      '(test -x "$HOME/.local/share/pearplay/venv/bin/python" || uv venv --python 3.11 "$HOME/.local/share/pearplay/venv") &&',
      'uv pip install --python "$HOME/.local/share/pearplay/venv/bin/python" -r requirements.txt &&',
      `"$HOME/.local/share/pearplay/venv/bin/python" helper/install.py install --extension-id ${quote(chrome.runtime.id)} --browser chrome --config-parent "$HOME/.config" --python "$HOME/.local/share/pearplay/venv/bin/python"`
    ].join('\n'):'Enter the full source-folder path to generate your command.';
  };
  $('sourcePath').oninput=updateCommand;
  $('copyCommand').onclick=async()=>{
    try {await globalThis.navigator.clipboard.writeText($('installCommand').textContent);$('copyStatus').textContent='Copied. Paste into your terminal and review before running.';}
    catch {$('copyStatus').textContent='Could not copy. Select and copy the command above.';}
  };
  updateCommand();
  let ready=false;
  const check=async()=>{
    $('check').disabled=true;$('find').disabled=true;$('connection').textContent='Checking this browser’s connection…';
    try {
      const result=await chrome.runtime.sendMessage({op:'setupCheck'});
      const state=connectionState(result,result?.ok===false?result.error:null);
      ready=state.kind==='ready';$('connection').dataset.state=state.kind;$('connection').textContent=preview&&!ready?'The helper is not connected. Follow the development installation instructions above, then fully quit and reopen Chrome and check again.':state.text;
    } catch {ready=false;$('connection').dataset.state='broken';$('connection').textContent=connectionState(null,'ACTION_FAILED').text;}
    finally {$('check').disabled=false;$('find').disabled=!ready;}
  };
  $('check').onclick=check;
  $('find').onclick=async()=>{
    if(!ready)return;
    $('find').disabled=true;$('receivers').textContent='Looking for AirPlay TVs on your network…';
    try {
      const result=await chrome.runtime.sendMessage({op:'setupFind'});
      if(result?.ok===false)throw Error('discovery_failed');
      const count=result.receivers?.length??0;
      $('receivers').textContent=count?`Found ${count} AirPlay TV${count===1?'':'s'}: ${result.receivers.map(r=>r.label).join('; ')}. Open a video, then click PearPlay in your browser toolbar to choose a TV and send.`:'No video-capable AirPlay TV found. Check that AirPlay is enabled, your TV is awake and on the same network.';
    } catch {$('receivers').textContent='The network search could not finish. Check the helper connection, enable AirPlay on your TV, check that both devices are on the same network, then try again.';}
    finally {$('find').disabled=!ready;}
  };
  if(supported)await check();else {$('check').disabled=true;$('find').disabled=true;}
}
if(globalThis.document&&globalThis.chrome?.runtime?.id)mountSetup(document,chrome,fetch).catch(()=>{document.getElementById('connection').textContent='Setup could not load. Reopen this tab and try again.';});
