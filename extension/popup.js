(async () => {
  const $ = id => document.getElementById(id);
  let closed = false;
  let timer;
  let resumeInitialization;
  let resumeAction;
  const active = () => !closed && document.visibilityState !== 'hidden';
  const close = () => { closed = true; clearInterval(timer); resumeInitialization?.(); resumeAction?.(); };
  globalThis.addEventListener?.('pagehide', close, {once:true});
  globalThis.addEventListener?.('unload', close, {once:true});
  // Chrome can construct an action document before making it visible. Wait;
  // do not abandon initialization or start helper work in the hidden document.
  if (document.visibilityState === 'hidden') {
    await new Promise(resolve => {
      resumeInitialization = resolve;
      const wake = () => {
        if (document.visibilityState === 'hidden' && !closed) return;
        document.removeEventListener('visibilitychange', wake);
        resolve();
      };
      document.addEventListener('visibilitychange', wake);
    });
  }
  if (closed) return;
  const platform = await chrome.runtime.getPlatformInfo();
  if (!active()) return;
  if (!['linux', 'mac', 'win'].includes(platform.os)) {
    $('casting').hidden = true;
    $('platformNotice').hidden = false;
    $('platformNotice').textContent = 'PearPlay supports Chrome on Linux, Mac and Windows. This computer is not supported.';
    $('phase').textContent = 'Not available on this computer';
    $('phase').dataset.state = 'unsupported';
    $('helperSetup').textContent = 'Compatibility information';
    $('helperSetup').onclick = () => chrome.tabs.create({url: chrome.runtime.getURL('setup.html')});
    return;
  }
  $('platformNotice').hidden = true;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!active()) return;
  const memory = chrome.storage?.session;
  const notice = text => showTVs(text);
  const explain = error => {
    const code = error?.message;
    if (code === 'TV_CONTROL_UNAVAILABLE') return 'TV controls are no longer available for this session. Check the TV or reopen PearPlay.';
    if (code === 'NATIVE_DISCONNECTED' || code === 'NATIVE_TIMEOUT') return 'This browser cannot connect to PearPlay Helper. Click Finish setup for installation and browser connection instructions.';
    if (code === 'discovery_failed') return 'The network search could not finish. Check that your TV is awake, AirPlay is enabled, and both devices are on the same network; then try Find TVs again.';
    if (code === 'busy') return 'PearPlay is busy in another browser or pairing window. End that helper session there, then try again.';
    if (code === 'pairing_required') return 'Press Show a new PIN, then enter the 4 digits shown on your TV.';
    if (code === 'pairing_failed') return 'Pairing did not finish. Press Show a new PIN to start again.';
    if (code === 'VIDEO_CHANGED_OR_UNCONFIRMED') return 'The video changed. Press Find videos and choose it again before sending.';
    if (code === 'receiver_unavailable') return 'This TV was found, but pairing or playback could not start. Press Find TVs and try again.';
    if (code === 'ACTION_FAILED') return 'Connect the helper first if it still says not connected. Then choose the video and an AirPlay TV.';
    return 'Connect the helper, find videos, find Apple TVs, then send.';
  };
  const send = async (op, args = {}) => {
    if (!active()) throw Error('POPUP_CLOSED');
    const r = await chrome.runtime.sendMessage({ op, tabId: tab?.id, ...args });
    if (r?.ok === false) throw Error(r.error ?? 'ACTION_FAILED');
    return r;
  };
  const options = (id, items, selected, blank) => {
    const el = $(id);
    const key = JSON.stringify([items.map(item => [item.id ?? item.identifier, item.label]), selected ?? '']);
    if (el.dataset.options === key) {
      // User edits change value without changing our cached option DOM.
      el.value = selected ?? '';
      return;
    }
    el.dataset.options = key;
    el.replaceChildren();
    const empty = document.createElement('option');
    empty.value = '';
    empty.textContent = blank;
    el.append(empty);
    for (const item of items) {
      const o = document.createElement('option');
      o.value = item.id ?? item.identifier;
      o.textContent = item.label;
      el.append(o);
    }
    el.value = selected ?? '';
  };
  const accepted = native => native?.state === 'connecting' && native.evidence === 'unverified' && native.session?.delivery === 'accepted';
  const isActiveCast = native => ['connecting','playing','paused','stopping'].includes(native?.state) || accepted(native);
  const tvStatus = native => {
    if (native.receiverIssue) return ({unsupported_access: 'This TV’s access settings are not supported by PearPlay. Check its AirPlay settings or choose another TV.', incomplete_advertisement: 'This TV did not provide enough consistent connection information. Press Find TVs and try again.', unsupported_protocol: 'PearPlay does not support this TV’s connection mode yet. Choose another TV.'})[native.receiverIssue];
    if (native.error === 'busy') return 'PearPlay is busy in another browser or pairing window. End that helper session there before trying again.';
    if (native.error === 'transport_failed' || native.state === 'error' && native.diagnostic) {
      const d = native.diagnostic;
      const message = d?.stage === 'await-playing' ? 'The TV did not confirm playback.' : 'Playback failed between PearPlay and the TV.';
      return message + ' Try a different video or review Settings & help.';
    }
    if (native.error === 'NATIVE_DISCONNECTED') return 'Helper not connected. Click Finish setup for installation and browser connection instructions.';
    if (native.error === 'receiver_unavailable') return 'This TV was found, but pairing or playback could not start. Press Find TVs and try again.';
    if (native.error === 'pairing_failed') return 'Pairing did not finish. Press Show a new PIN to start again.';
    if (native.error === 'pairing_required') return 'Pairing is required. Press Show a new PIN, then enter the 4 digits shown on your TV.';
    if (accepted(native)) return 'Sent to TV — check the picture and sound. End the helper session before sending again.';
    if (!native.receivers?.length) return 'No AirPlay TVs yet. Click Find TVs.';
    return ({ idle: 'Helper connected. Choose your TV.', connecting: 'Connecting to your TV…', playing: 'TV reports playing. Check the picture and sound.', paused: 'TV reports paused.', stopped: 'Helper session ended. Check the TV.', stopping: 'Ending the helper session…', error: 'Helper needs attention. Reconnect and try again.' })[native.state] ?? 'Check the TV and refresh its status.';
  };
  const rfc1918 = ip => {
    if (typeof ip !== 'string') return false;
    const parts = ip.split('.');
    if (parts.length !== 4) return false;
    const a = Number(parts[0]);
    const b = Number(parts[1]);
    if (!Number.isInteger(a) || !Number.isInteger(b) || a < 0 || a > 255 || b < 0 || b > 255) return false;
    return a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168);
  };
  const openFirewall = () => {
    $('helpDetails').open = true;
    $('firewallBox').open = true;
  };
  const renderFirewall = s => {
    const linux = platform.os === 'linux';
    const r = s.native.receivers?.find(r => r.identifier === s.receiver);
    const f = s.firewall?.receiver === s.receiver && s.firewall?.host === r?.address ? s.firewall : null;
    const noTiming = r?.timingRequired === false || !!(s.native.session?.receiver === r?.identifier && s.native.session?.host === r?.address && s.native.session?.timingRequired === false);
    const key = `${s.receiver ?? ''}/${r?.address ?? ''}`;
    if ($('firewallBox').dataset.target !== key) $('firewallConsent').checked = false;
    $('firewallBox').dataset.target = key;
    $('firewallScope').textContent = r?.address ? `Only ${r.address} → this computer, UDP 49170 (AirPlay timing). No other ports or TVs.` : 'Choose a TV first.';
    const privateIPv4 = rfc1918(r?.address);
    let text = !linux ? 'Automatic firewall checks and changes are Linux UFW only. Review this computer’s firewall settings manually if the TV only buffers. No settings were changed.' : noTiming ? 'This TV does not need the extra timing-port permission. Check saved rules only if you want to remove an old PearPlay permission.' : !s.native.firewallSupport ? 'Automatic firewall checks need a newer helper. Firewall settings may matter if a TV only buffers.'
      : !r ? 'Choose a TV to check its firewall permission.'
      : !f ? 'Firewall permission could not be checked. Use Check again; no settings were changed.'
      : !f.supported ? 'Automatic firewall checks support UFW only. No settings were changed.'
      : f.enabled === false ? 'UFW is disabled in its saved settings. Other firewall tools may still be active.'
      : f.allowance === 'present' ? 'A permission for this TV is saved in UFW. This does not prove playback traffic reaches the helper.'
      : f.allowance === 'missing' && f.enabled === true ? 'UFW is enabled in its saved settings, but no exact permission for this TV was found. If it only buffers, review TV firewall permission below.'
      : f.allowance === 'unknown' && privateIPv4 ? 'Saved firewall rules could not be read on this computer, so PearPlay cannot confirm whether a permission for this TV already exists. That is not proof that none exists, and PearPlay will not remove administrator or other rules it did not create.'
      : f.allowance === 'unknown' ? 'Firewall permission could not be checked for this TV address. No permission is assumed and none was changed.'
      : 'UFW settings could not be fully checked. No permission is assumed.';
    if (f?.change) text = (f.change.ok ? 'Last requested firewall change was verified in saved rules. ' : f.change.error === 'auth_cancelled' ? 'Administrator approval was cancelled. ' : f.change.error === 'ambiguous_rule' ? 'Removal was refused because both a PearPlay rule and another identical rule are present. PearPlay will not remove a rule it did not create. ' : 'Firewall change was not verified. No broader permission was attempted. ') + text;
    $('firewallStatus').textContent = s.firewallBusy ? 'Waiting for administrator approval on the desktop…' : text;
    const attention = linux && (s.firewallBusy || f?.change || !noTiming && !s.native.receiverIssue && (f?.supported && f.enabled === true && f.allowance === 'missing' || s.native.error === 'transport_failed'));
    $('firewallReview').hidden = !attention;
    $('firewallReview').textContent = s.firewallBusy ? 'Waiting for administrator approval…' : f?.change ? 'Firewall change result — view details' : 'Review TV firewall permission';
    const notification = `${key}/${!!s.firewallBusy}/${f?.change?.ok ?? ''}/${f?.change?.error ?? ''}`;
    if (linux && $('firewallBox').dataset.notification !== notification && (s.firewallBusy || f?.change?.ok === false)) openFirewall();
    $('firewallBox').dataset.notification = notification;
    $('firewallCheck').disabled = !linux || !r || !s.native.firewallSupport || s.firewallBusy;
    $('firewallAllow').hidden = !linux || noTiming || !(f?.supported && f.enabled === true && f.allowance === 'missing');
    $('firewallRemove').hidden = !linux || !f?.owned;
    $('firewallRemoveIfPresent').hidden = !linux || !(f?.supported && f.allowance === 'unknown' && privateIPv4);
    $('firewallConsent').hidden = !linux;
    for (const id of ['firewallAllow','firewallRemove','firewallRemoveIfPresent','firewallConsent']) $(id).disabled = !!s.firewallBusy;
  };
  const time = seconds => {
    if (!Number.isFinite(seconds) || seconds < 0) return '—:—';
    const n = Math.floor(seconds), h = Math.floor(n / 3600), m = Math.floor(n / 60) % 60;
    return `${h ? h + ':' : ''}${h ? String(m).padStart(2, '0') : m}:${String(n % 60).padStart(2, '0')}`;
  };
  const renderRemote = (s, disconnected) => {
    const casting = isActiveCast(s.native), t = s.native.tvTimeline, control = s.native.tvControl;
    const fresh = casting && control && t && t.session === control.session && t.receiver === control.receiver && t.canSeek === false && Number.isFinite(t.position) && t.position >= 0 && Number.isFinite(t.ageMs) && t.ageMs >= 0 && t.ageMs <= 10000;
    $('tvTimeline').hidden = !fresh;
    if (fresh) {
      const bounded = Number.isFinite(t.duration) && t.duration > 0;
      $('tvProgress').hidden = !bounded;
      $('tvProgress').max = bounded ? t.duration : 1;
      $('tvProgress').value = bounded ? Math.min(t.position, t.duration) : 0;
      $('tvElapsed').textContent = time(t.position);
      $('tvDuration').textContent = bounded ? time(t.duration) : 'Duration unavailable';
    }
    $('castAudio').hidden = !casting || !s.activeCast?.sourceAvailable;
    $('castMute').textContent = s.activeCast?.browserMuted === true ? 'Unmute browser video' : 'Mute browser video';
    $('castSourceHint').hidden = !casting || !!s.activeCast?.sourceAvailable;
    const version = s.native.helperVersion;
    const parts = typeof version === 'string' && /^\d+\.\d+\.\d+$/.test(version) ? version.split('.').map(Number) : null;
    const current = parts && (parts[0] > 0 || parts[1] > 3 || parts[1] === 3 && parts[2] >= 3);
    $('helperCompatibility').hidden = disconnected || !!current;
    $('helperCompatibility').textContent = `${version ? 'Helper ' + version : 'Unknown helper'} · TV progress needs 0.3.3 or newer. See Setup.`;
    $('recover').hidden = !disconnected && !s.native.error;
    $('recover').textContent = disconnected ? 'Connect helper' : s.native.error === 'discovery_failed' || s.native.error === 'receiver_unavailable' ? 'Find TVs again' : 'View connection help';
    const d = s.native.diagnostic;
    $('diagnostic').hidden = !d;
    $('diagnostic').textContent = d ? `Details: ${d.stage} / ${d.reason}${d.httpStatus ? ' / HTTP ' + d.httpStatus : ''}` : '';
  };
  let currentView;
  let pendingActions = 0;
  let actionError = false;
  const choices = new Map();
  let choiceDrain;
  let sendReady = false;
  let viewConfirmed = false;
  const updatePhase = () => {
    if (!active()) return;
    const s = currentView;
    const blocked = !!s?.pairingBusy || !viewConfirmed || !!pendingActions || !!choiceDrain || !!choices.size;
    $('pairRestart').disabled = blocked || !s?.receiver || pinReady;
    $('pair').disabled = blocked || !pinReady;
    $('start').disabled = !!s?.pairingBusy || !sendReady || !viewConfirmed || !!pendingActions || !!choiceDrain || !!choices.size || pinReady;
    const state = actionError || s?.native.error ? 'error'
      : pendingActions || choiceDrain || choices.size ? 'working'
      : accepted(s?.native) ? 'sent'
      : ['connecting', 'stopping'].includes(s?.native.state) ? 'working'
      : ['playing','paused'].includes(s?.native.state) ? s.native.state
      : s?.enabled && !s.candidates.length ? 'empty' : 'idle';
    const labels = { sent: 'Sent — check the TV', idle: 'Ready', working: 'Working…', empty: 'No video found yet', error: 'Needs attention', playing: 'Playing on TV', paused: 'TV paused' };
    $('phase').dataset.state = state;
    $('phase').textContent = labels[state];
    $('tvStatus').classList?.toggle('error', state === 'error');
    const control=s?.native.tvControl;
    const canControl=!!control && control.receiver===s?.receiver && /^[0-9a-f]{32}$/.test(control.session) && ['playing','paused'].includes(s?.native.state) && ['pause','resume'].every(op=>s.native.capabilities.includes(op)) && !s.native.error;
    $('tvTransport').hidden=!canControl;
    $('stop').disabled=blocked || !s?.native.capabilities.includes('stop');
    $('castMute').disabled=blocked || !s?.activeCast?.sourceAvailable;
    for(const op of ['pause','resume']) {
      $(op).hidden=!canControl || s.native.state!==(op==='pause'?'playing':'paused');
      $(op).disabled=blocked || !canControl || $(op).hidden;
    }
  };
  let refreshing;
  function refresh() {
    if (!active()) return Promise.resolve();
    if (refreshing) return refreshing;
    refreshing = renderView().finally(() => { refreshing = null; });
    return refreshing;
  }
  async function renderView() {
    try {
      const s = await send('view');
      if (!active()) return;
      const allowed = await allWebsitesAllowed();
      if (!active()) return;
      const nativeChanged = currentView?.native.state !== s.native.state || currentView?.native.error !== s.native.error || currentView?.native.session?.delivery !== s.native.session?.delivery || currentView?.native.receiverIssue !== s.native.receiverIssue;
      const sendable = s.candidates.filter(c => c.sendable !== false);
      const initial = s.candidates.length === 1 ? s.candidates[0] : sendable.length === 1 ? sendable[0] : null;
      if (!isActiveCast(s.native) && !choices.has('candidate') && !s.selected && !s.selectionLost && initial) {
        await send('select', { id: initial.id });
        if (!active()) return;
        s.selected = initial.id;
      }
      options('candidate', s.candidates, choices.get('candidate')?.id ?? s.selected, 'Choose a video');
      options('receiver', s.native.receivers, choices.get('receiver')?.id ?? s.receiver, 'Choose an AirPlay TV');
      const stateText = [
        s.enabled ? 'Looking for videos on this page.' : 'Not looking for videos yet.',
        s.candidates.length ? `${s.candidates.length} video${s.candidates.length === 1 ? '' : 's'} found.` : 'No videos found yet.',
        tvStatus(s.native),
      ].join(' ');
      $('state').textContent = stateText;
      renderFirewall(s);
      currentView = s;
      updatePhase();
      const c = s.candidates.find(item => item.id === s.selected);
      const casting = isActiveCast(s.native);
      $('selectedVideo').hidden = !casting && !c && !s.selectionLost;
      $('videoContext').textContent = casting ? 'TV session' : 'Selected video';
      const title = casting ? s.activeCast?.title || 'Video sent to TV' : c?.label ?? (s.selectionLost ? 'Video changed — choose again' : 'Choose a video');
      $('identity').textContent = title;
      $('identityFull').textContent = casting ? title : c?.label ?? (s.selectionLost ? 'Your previous video is no longer available. Choose a video deliberately before sending again.' : 'No video selected.');
      const disconnected = ['NATIVE_DISCONNECTED','NATIVE_TIMEOUT','INVALID_RESPONSE'].includes(s.native.error) || !s.native.capabilities.length;
      document.body?.toggleAttribute('data-disconnected', disconnected);
      document.body?.toggleAttribute('data-recovery', !disconnected && !!s.native.error);
      $('helperSetup').textContent = disconnected ? 'Finish setup' : 'Setup';
      $('videoHint').hidden = casting || !!s.candidates.length || !allowed;
      $('discover').disabled = disconnected;
      $('host').disabled = disconnected;
      globalThis.pearplayBrowserControls?.select(allowed ? c : null, {casting:['connecting','playing','paused','stopping'].includes(s.native.state) || accepted(s.native)});
      renderRemote(s, disconnected);
      sendReady = allowed && !disconnected && !!c && c.sendable !== false && s.native.receivers.some(r => r.identifier === s.receiver) && !casting;
      $('permissionBox').hidden = allowed || casting;
      $('grantAll').disabled = allowed;
      $('enable').disabled = !allowed;
      $('rescan').disabled = !allowed;
      $('accessState').textContent = allowed
        ? 'All websites allowed. Next: press Find videos.'
        : 'Allow all websites before finding videos.';
      const needsPin = !!s.receiver && (s.pairingReceiver === s.receiver || ['pairing_required', 'pairing_failed'].includes(s.native.error));
      pinNeeded = needsPin || pinStarted;
      const pairingTarget = s.receiver ?? '';
      if (pinTarget !== pairingTarget) {
        pinRevision++;
        pinTarget = pairingTarget;
        pinStarted = false;
        pinReady = false;
        $('pin').value = '';
      }
      renderPairVisibility();
      if (!pinReady && (!tvMessage || nativeChanged || (isActiveCast(s.native) && !actionError))) showTVs(tvStatus(s.native));
      const tvSession = ['connecting','playing','paused','stopping'].includes(s.native.state);
      $('sessionControls').hidden = !(tvSession || pinStarted || pinReady);
      $('receiverSection').hidden = tvSession && !pinReady;
      $('chosenTV').hidden = !tvSession || pinReady;
      $('chosenTV').textContent = 'AirPlay TV · ' + (s.activeCast?.receiverName ?? s.native.receivers.find(r => r.identifier === s.receiver)?.label ?? 'Selected TV');
      for (const op of ['pause', 'resume', 'stop']) $(op).disabled = !s.native.capabilities.includes(op);
      viewConfirmed = true;
      updatePhase();
    } catch {
      if (!active()) return;
      viewConfirmed = false;
      $('tvTimeline').hidden = true;
      notice('Extension unavailable. Reopen this window.');
      actionError = true;
      updatePhase();
    }
  }
  const act = (fn, requiresSendReady = false) => async () => {
    // Quiet polling leaves focus alone, but actions never race its snapshot.
    if (!active() || currentView?.pairingBusy || pendingActions || refreshing || choiceDrain || choices.size || requiresSendReady && $('start').disabled) return;
    pendingActions++;
    actionError = false;
    updatePhase();
    try {
      await fn();
      if (!active()) return;
      await refresh();
    } catch (error) {
      if (!active()) return;
      const text = explain(error);
      notice(text);
      if (fn === findTVs) showTVs(text);
      actionError = true;
    } finally {
      pendingActions--;
      resumeAction?.();
      updatePhase();
    }
  };
  for (const op of ['enable', 'disable', 'rescan']) {
    $(op).onclick = act(async () => {
      const r = await send(op);
      notice(r.total !== undefined
        ? (r.scanned ? 'Search complete. Choose a video from the list.' : 'No videos yet. Allow all websites, reload this page, press play, then Find videos.')
        : 'Stopped looking on this page.');
    });
  }
  $('firewallReview').onclick = openFirewall;
  $('firewallCheck').onclick = act(() => send('firewall', { action: 'check', receiver: currentView?.receiver }));
  for (const [id, action] of [['firewallAllow','allow'],['firewallRemove','remove'],['firewallRemoveIfPresent','remove']]) {
    $(id).onclick = act(async () => {
      if (!$('firewallConsent').checked) { notice('Review the selected TV and tick the approval box first.'); return; }
      const receiver = currentView?.receiver;
      $('firewallConsent').checked = false;
      await send('firewall', { action, receiver, confirmed: true });
    });
  }
  const choose = (op, field) => () => {
    if (!active()) return Promise.resolve();
    // Coalesce only the same field. A newer video never cancels a TV choice.
    if (field === 'receiver') {
      pinRevision++;
      pinStarted = pinReady = pinNeeded = false;
      $('pin').value = '';
      renderPairVisibility();
    }
    if (field === 'candidate') globalThis.pearplayBrowserControls?.select(null);
    choices.set(field, {op, id: $(field).value});
    if (!choiceDrain) choiceDrain = Promise.resolve().then(async () => {
      while (active() && choices.size) {
        if (refreshing) await refreshing;
        if (pendingActions && active()) await new Promise(resolve => { resumeAction = resolve; });
        resumeAction = null;
        if (!active()) break;
        const [target, intent] = choices.entries().next().value;
        actionError = false;
        // Invalidate readiness before dispatch, including ambiguous failures.
        viewConfirmed = false;
        try {
          await send(intent.op, {id: intent.id});
        } catch (error) {
          if (!active()) break;
          actionError = true;
          notice(explain(error));
        }
        if (!active()) break;
        if (choices.get(target) === intent) choices.delete(target);
        // Never retry a failed selection from polling. Read worker truth on both
        // success and failure, while retaining any newer independent intent.
        await refresh();
      }
    }).finally(() => {
      if (!active()) choices.clear();
      choiceDrain = null;
      updatePhase();
    });
    updatePhase();
    return choiceDrain;
  };
  $('candidate').onchange = choose('select', 'candidate');
  $('receiver').onchange = choose('receiver', 'receiver');
  for (const op of ['hello', 'status']) {
    $(op).onclick = act(() => send(op));
  }
  for (const op of ['pause','resume']) {
    $(op).onclick = act(() => {
      const control=currentView?.native.tvControl;
      if($(op).hidden || !control || control.receiver!==currentView.receiver) throw Error('TV_CONTROL_UNAVAILABLE');
      return send(op,{session:control.session});
    });
  }
  $('stop').onclick = act(async () => {
    pinRevision++;
    await send('stop');
    if (!active()) return;
    pinStarted = false;
    pinReady = false;
    $('pin').value = '';
  });
  $('start').onclick = act(async () => {
    pinRevision++;
    pinStarted = false;
    pinReady = false;
    await send('start');
  }, true);
  $('helperSetup').onclick = () => send('openSetup').catch(() => notice('Could not open setup. Reopen the popup and try again.'));
  let tvMessage = '';
  let pinNeeded = false;
  let pinStarted = false;
  let pinReady = false;
  let pinTarget = '';
  let pinRevision = 0;
  const renderPairVisibility = () => {
    // Pairing is a separate step: keep the chosen title, remove redundant
    // selection/Send controls until the PIN has been handled.
    if (pinReady) globalThis.pearplayBrowserControls?.select(null);
    const casting = isActiveCast(currentView?.native);
    $('videoNavigation').hidden = pinReady || casting;
    $('candidate').hidden = pinReady || casting;
    $('start').hidden = pinNeeded || pinReady || casting;
    $('pairRestart').hidden = !pinNeeded || pinReady;
    $('pairBox').hidden = !pinReady;
  };
  const showTVs = text => {
    if (!active()) return;
    tvMessage = text;
    $('tvStatus').textContent = text;
  };
  const findTVs = async () => {
    showTVs('Looking for AirPlay TVs…');
    const host = $('host').value.trim();
    if (memory) await memory.set({host});
    if (!active()) return;
    const r = await send('discover', host ? { host } : {});
    const n = r.receivers?.length ?? 0;
    showTVs(n === 1 ? 'TV found and selected. Choose a video, then send.' : n ? `Found ${n} AirPlay TVs. Choose one, then send.` : 'No video-capable AirPlay TV found. Check that AirPlay is enabled, the TV is awake, and both devices are on the same network. Then try Find TVs again.');
  };
  $('discover').onclick = act(findTVs);
  $('castMute').onclick = act(() => {
    if (!currentView?.activeCast?.sourceAvailable) throw Error('VIDEO_CHANGED_OR_UNCONFIRMED');
    return send('castMute', {castId: currentView.activeCast.id, value: currentView.activeCast.browserMuted !== true});
  });
  $('recover').onclick = act(async () => {
    const n = currentView?.native;
    if (!n?.capabilities.length || ['NATIVE_DISCONNECTED','NATIVE_TIMEOUT','INVALID_RESPONSE'].includes(n.error)) return send('hello');
    if (['discovery_failed','receiver_unavailable'].includes(n.error)) return findTVs();
    $('helpDetails').open = true;
    $('hostDetails').open = true;
  });
  $('pairRestart').onclick = act(async () => {
    if (!currentView?.receiver || !pinNeeded || pinReady) return;
    const revision = ++pinRevision;
    pinStarted = true;
    $('pin').value = '';
    showTVs('Starting pairing. Look at the TV for a new 4-digit PIN.');
    try {
      await send('pairBegin');
      if (!active() || revision !== pinRevision) return;
      pinReady = true;
      showTVs('The new PIN is on the TV. Enter it below. It stays hidden.');
    } catch (error) {
      if (!active() || revision !== pinRevision) return;
      pinReady = false;
      showTVs(explain(error));
    }
    renderPairVisibility();
  });
  $('pair').onclick = act(async () => {
    if (!pinReady) return;
    const revision = pinRevision;
    const pin = $('pin').value;
    $('pin').value = '';
    try {
      await send('pair', { pin });
      if (!active() || revision !== pinRevision) return;
      pinRevision++;
      pinReady = pinStarted = pinNeeded = false;
      showTVs('Paired. Press Send to TV.');
    } catch {
      if (!active() || revision !== pinRevision) return;
      // The helper consumes failed sessions. Never resubmit to the old session
      // or start another from polling: require the separate deliberate button.
      pinRevision++;
      pinReady = false;
      pinStarted = pinNeeded = true;
      showTVs('Pairing did not finish. Press Show a new PIN to start again.');
    }
    renderPairVisibility();
  });
  $('host').addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      $('discover').click();
    }
  });
  $('grantAll').onclick = act(async () => {
    const granted = await chrome.permissions.request({ origins: ['http://*/*', 'https://*/*'] });
    notice(granted ? 'All websites allowed. Reload this page, press play, then press Find videos.' : 'Not allowed. PearPlay cannot see the video until you allow all websites.');
  });
  $('grantSite').onclick = act(async () => {
    const u = new URL(tab.url);
    if (!['http:', 'https:'].includes(u.protocol)) throw Error('UNSUPPORTED_PAGE');
    const granted = await chrome.permissions.request({ origins: [`${u.protocol}//${u.hostname}/*`] });
    notice(granted ? 'This website is allowed. This version still needs all-sites access to enable Find videos.' : 'Not allowed.');
  });
  $('reload').onclick = act(() => chrome.tabs.reload(tab.id));
  async function allWebsitesAllowed() {
    const got = await chrome.permissions.getAll?.();
    const origins = got?.origins ?? [];
    return origins.includes('http://*/*') && origins.includes('https://*/*');
  }
  const saved = await memory?.get(['host']) ?? {};
  if (!active()) return;
  if (saved.host) {
    $('host').value = saved.host;
    // Preserve the saved address without expanding the normal casting view.
  }
  await refresh();
  // Opening the popup reads the worker's retained receiver list. Searching
  // the network is a deliberate Find TVs action, never a startup side effect.
  if (active()) timer = setInterval(() => pendingActions || choiceDrain || choices.size ? undefined : refresh(), 2000);
})();