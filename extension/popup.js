(async () => {
  const $ = id => document.getElementById(id);
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const memory = chrome.storage?.session;
  const notice = text => {
    $('notice').textContent = text;
    $('banner').textContent = text;
  };
  const explain = error => {
    const code = error?.message;
    if (code === 'NATIVE_DISCONNECTED' || code === 'NATIVE_TIMEOUT') return 'Connect the PearPlay helper first. Until that works, Find Apple TVs and typing the TV address will not work.';
    if (code === 'pairing_required') return 'Look at the Apple TV. Type the 4 digits it shows in step 4. They stay hidden.';
    if (code === 'ACTION_FAILED') return 'Connect the helper first if it still says not connected. Then choose the video and an Apple TV.';
    return 'Connect the helper, find videos, find Apple TVs, then send.';
  };
  const send = async (op, args = {}) => {
    const r = await chrome.runtime.sendMessage({ op, tabId: tab?.id, ...args });
    if (r?.ok === false) throw Error('ACTION_FAILED');
    return r;
  };
  const options = (id, items, selected, blank) => {
    const el = $(id);
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
  const tvStatus = native => {
    if (native.error === 'NATIVE_DISCONNECTED') return 'Helper not connected — Find Apple TVs and the address box cannot work yet. Click Connect helper.';
    if (!native.receivers?.length) return 'No Apple TVs yet. Click Find Apple TVs.';
    return ({ idle: 'Helper connected. Choose your Apple TV.', connecting: 'Connecting to your Apple TV…', playing: 'Helper reports playing (look at the TV to confirm).', stopped: 'Helper session ended. Check the TV.', stopping: 'Ending the helper session…', error: 'Helper needs attention. Reconnect and try again.' })[native.state] ?? 'Check the TV and refresh its status.';
  };
  let currentView;
  let pendingActions = 0;
  let actionError = false;
  const updatePhase = () => {
    const s = currentView;
    const state = actionError || s?.native.error ? 'error'
      : pendingActions || ['connecting', 'stopping'].includes(s?.native.state) ? 'working'
      : s?.native.state === 'playing' ? 'playing'
      : s?.enabled && !s.candidates.length ? 'empty' : 'idle';
    const labels = { idle: 'Ready', working: 'Working…', empty: 'No video found yet', error: 'Needs attention', playing: 'Helper reports playing — check the TV' };
    $('phase').dataset.state = state;
    $('phase').textContent = labels[state];
  };
  async function refresh() {
    try {
      const s = await send('view');
      const nativeChanged = currentView?.native.state !== s.native.state || currentView?.native.error !== s.native.error;
      if (!s.selected && s.candidates.length === 1) {
        await send('select', { id: s.candidates[0].id });
        s.selected = s.candidates[0].id;
      }
      options('candidate', s.candidates, s.selected, 'Choose a video');
      options('receiver', s.native.receivers, s.receiver, 'Choose an Apple TV');
      const stateText = [
        s.enabled ? 'Looking for videos on this page.' : 'Not looking for videos yet.',
        s.candidates.length ? `${s.candidates.length} video${s.candidates.length === 1 ? '' : 's'} found.` : 'No videos found yet.',
        tvStatus(s.native),
      ].join(' ');
      $('state').textContent = stateText;
      currentView = s;
      updatePhase();
      const c = s.candidates.find(item => item.id === s.selected);
      const disconnected = s.native.error === 'NATIVE_DISCONNECTED';
      $('discover').disabled = disconnected;
      $('host').disabled = disconnected;
      $('start').disabled = disconnected || !c || !s.receiver;
      const allowed = await allWebsitesAllowed();
      $('grantAll').disabled = allowed;
      $('enable').disabled = !allowed;
      $('rescan').disabled = !allowed;
      $('accessState').textContent = allowed
        ? 'All websites allowed. Next: press Find videos.'
        : 'Allow all websites first. Find videos stays off until you do.';
      const needsPin = s.native.error === 'pairing_required';
      if (needsPin && !pinStarted) {
        pinStarted = true;
        $('pairBox').hidden = true;
        showTVs('Starting pairing. Look at the Apple TV for a 4-digit PIN.');
        send('pairBegin').then(() => {
          pinReady = true;
          $('pairBox').hidden = false;
          showTVs('The PIN is on the Apple TV. Type those 4 digits below. They stay hidden.');
        }).catch(() => {
          pinStarted = false;
          showTVs('Could not start pairing. Press Send to Apple TV again.');
        });
      } else if (pinReady) $('pairBox').hidden = false;
      else $('pairBox').hidden = true;
      if (!needsPin && !pinReady && (!tvMessage || nativeChanged)) showTVs(tvStatus(s.native));
      $('confirmTV').disabled = !c?.videoId;
      $('localResume').disabled = !s.localAvailable;
      for (const op of ['pause', 'resume', 'stop']) $(op).disabled = !s.native.capabilities.includes(op);
      const host = $('host').value.trim();
      await memory?.set({ host, receiver: s.receiver ?? '', candidate: s.selected ?? '' });
    } catch {
      notice('Extension unavailable. Reopen this window.');
      actionError = true;
      updatePhase();
    }
  }
  const act = fn => async () => {
    pendingActions++;
    actionError = false;
    updatePhase();
    try {
      await fn();
      await refresh();
    } catch (error) {
      const text = explain(error);
      notice(text);
      if (fn === findTVs) showTVs(text);
      actionError = true;
    } finally {
      pendingActions--;
      updatePhase();
    }
  };
  for (const op of ['enable', 'disable', 'rescan']) {
    $(op).onclick = act(async () => {
      const r = await send(op);
      notice(r.total !== undefined
        ? (r.scanned ? 'Search complete. Choose a video if one appears below.' : 'No videos yet. Allow all websites, reload this page, press play, then Find videos.')
        : 'Stopped looking on this page.');
    });
  }
  $('candidate').onchange = act(() => send('select', { id: $('candidate').value }));
  $('receiver').onchange = act(() => send('receiver', { id: $('receiver').value }));
  for (const op of ['hello', 'start', 'status', 'stop', 'pause', 'resume', 'localResume']) {
    $(op).onclick = act(() => send(op));
  }
  let tvMessage = '';
  let pinStarted = false;
  let pinReady = false;
  const showTVs = text => {
    tvMessage = text;
    $('tvStatus').textContent = text;
  };
  const findTVs = async () => {
    showTVs('Looking for Apple TVs…');
    const host = $('host').value.trim();
    const r = await send('discover', host ? { host } : {});
    const n = r.receivers?.length ?? 0;
    showTVs(n === 1 ? 'Apple TV found and selected. Press Send to Apple TV.' : n ? `Found ${n} Apple TVs. Choose one, then send.` : 'No Apple TV found on the network. Leave the address blank and press Find Apple TVs again.');
  };
  $('discover').onclick = act(findTVs);
  $('pair').onclick = async () => {
    const pin = $('pin').value;
    $('pin').value = '';
    try {
      await send('pair', { pin });
      pinReady = false;
      pinStarted = false;
      showTVs('Paired. Press Send to Apple TV.');
      $('pairBox').hidden = true;
      await refresh();
    } catch {
      showTVs('Pairing did not finish. Check the PIN on the TV and try again.');
    }
  };
  $('host').addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      $('discover').click();
    }
  });
  $('confirmTV').onclick = act(() => send('localPause', { confirmed: true }));
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
  if (saved.host) {
    $('host').value = saved.host;
    $('hostDetails').open = true;
  }
  await refresh();
  pendingActions++;
  updatePhase();
  try {
    await send('hello');
    await findTVs();
    await refresh();
  } catch (error) {
    const text = explain(error);
    showTVs(text);
    notice(text);
    actionError = true;
  } finally {
    pendingActions--;
    updatePhase();
  }
  setInterval(refresh, 2000);
})();