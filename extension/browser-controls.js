// These controls operate on the exact selected browser element, never the TV.
(() => {
  const $ = id => document.getElementById(id);
  let selected, state, revision=0, busy=false, closed=false, editing=false, casting=false;
  let tabId, inFlight;
  const active = () => !closed && document.visibilityState !== 'hidden';
  const controls=['browserPlay','browserMute','browserBack','browserForward','browserPip','browserPosition','browserReturn'];
  const time = seconds => {
    if (!Number.isFinite(seconds)) return '—:—';
    const n=Math.max(0,Math.floor(seconds)), h=Math.floor(n/3600), m=Math.floor(n/60)%60;
    return `${h?h+':':''}${h?String(m).padStart(2,'0'):m}:${String(n%60).padStart(2,'0')}`;
  };
  const label = (id, text) => { $(id).setAttribute('aria-label',text); $(id).title=text; };
  const render = () => {
    $('browserControls').hidden=!selected || casting;
    $('tvPlaybackNotice').hidden=!casting;
    const usable=!casting && !!selected?.videoId && !!state;
    const seek=usable && state.ranges?.length>0;
    // Quiet status refresh never temporarily disables a focused button.
    for (const id of controls) $(id).disabled=!usable;
    for (const id of ['browserBack','browserForward','browserPosition']) $(id).disabled=!seek;
    $('browserPip').disabled=!usable || !state.pipAvailable;
    const paused=state?.paused!==false, muted=!!state?.muted;
    label('browserPlay',paused?'Play browser video':'Pause browser video');
    label('browserMute',muted?'Unmute browser video':'Mute browser video');
    label('browserPip',state?.pip?'Leave Picture in Picture':'Picture in Picture');
    $('playGlyph').hidden=!paused; $('pauseGlyph').hidden=paused;
    $('volumeGlyph').hidden=muted; $('mutedGlyph').hidden=!muted;
    $('browserElapsed').textContent=time(state?.time);
    $('browserDuration').textContent=time(state?.duration);
    if (!editing && !busy && seek) {
      $('browserPosition').min=state.ranges[0][0];
      $('browserPosition').max=state.ranges.at(-1)[1];
      $('browserPosition').value=state.time;
    }
    $('browserHint').textContent=!selected?'Choose a video to use playback controls.':!selected.videoId?'This stream has no browser-video controls. Use the page player.':!state?'Browser video unavailable. Find videos and choose again.':!seek?'Browser playback only · no seek window.':selected.sendable===false?'Browser playback only · this video cannot be sent directly to TV.':'Controls the browser video, not the TV.';
  };
  const errors={TV_SESSION_ACTIVE:'Use your TV remote to pause or skip.',VIDEO_CHANGED_OR_UNCONFIRMED:'Video changed. Find videos and choose again.',BROWSER_CONTROL_BLOCKED:'The browser or website blocked this control. Try the page’s player.',NO_SEEK_WINDOW:'This video has no usable seek window.',PIP_OTHER_VIDEO:'Close the other Picture in Picture video first.'};
  async function request(action,value,quiet=false) {
    if (!active() || casting || !selected?.videoId || tabId===undefined) return;
    if (busy) {
      if (quiet) return;
      const rev=revision;
      await inFlight;
      if (!active() || revision!==rev) return;
      return request(action,value,quiet);
    }
    const target=selected.id, rev=revision;
    let finish;
    inFlight=new Promise(resolve=>{finish=resolve;});
    busy=true;
    try {
      const result=await chrome.runtime.sendMessage({op:'browserControl',tabId,id:target,action,value});
      if (!active() || rev!==revision) return;
      if (result?.ok!==true) throw Error(result?.error??'BROWSER_CONTROL_BLOCKED');
      state=result;
      if (!quiet) $('browserError').textContent='';
    } catch(error) {
      if (!active() || rev!==revision) return;
      if (quiet || error.message==='VIDEO_CHANGED_OR_UNCONFIRMED') state=null;
      if (!quiet) $('browserError').textContent=errors[error.message]??'Browser video unavailable. Find videos and choose again.';
    } finally {
      busy=false;
      finish();
      if (active()) render();
    }
  }
  globalThis.pearplayBrowserControls={select(candidate,{casting:nextCasting=false}={}) {
    if (selected?.id===candidate?.id && casting===nextCasting) return;
    revision++;selected=candidate;casting=nextCasting;state=null;editing=false;
    $('browserError').textContent='';render();
    void request('status',undefined,true);
  }};
  $('browserPlay').onclick=()=>request(state?.paused===false?'pause':'play');
  $('browserMute').onclick=()=>request('mute',!state?.muted);
  $('browserBack').onclick=()=>request('skip',-Number($('browserJump').value));
  $('browserForward').onclick=()=>request('skip',Number($('browserJump').value));
  $('browserPip').onclick=()=>request('pip');
  $('browserReturn').onclick=()=>request('return');
  $('browserPosition').oninput=()=>{editing=true;};
  $('browserPosition').onchange=async()=>{const value=Number($('browserPosition').value);editing=false;await request('seek',value);};
  $('browserPosition').addEventListener('pointercancel',()=>{editing=false;render();});
  $('browserPosition').addEventListener('blur',()=>{editing=false;render();});
  const jumpLabels=()=>{
    const n=Number($('browserJump').value);
    if (![5,10,15,30].includes(n)) return;
    $('backSeconds').textContent=String(n);$('forwardSeconds').textContent=String(n);
    label('browserBack',`Jump browser video back ${n} seconds`);label('browserForward',`Jump browser video forward ${n} seconds`);
  };
  $('browserJump').onchange=()=>{jumpLabels();void chrome.storage.session.set({browserJump:Number($('browserJump').value)});};
  const timer=setInterval(()=>{if (!editing) void request('status',undefined,true);},1000);
  const close=()=>{closed=true;revision++;clearInterval(timer);};
  addEventListener('pagehide',close,{once:true});addEventListener('unload',close,{once:true});
  render();jumpLabels();
  void chrome.tabs.query({active:true,currentWindow:true}).then(tabs=>{tabId=tabs[0]?.id;void request('status',undefined,true);});
  void chrome.storage.session.get(['browserJump']).then(saved=>{if (active()&&[5,10,15,30].includes(saved.browserJump)){$('browserJump').value=String(saved.browserJump);jumpLabels();}});
})();
