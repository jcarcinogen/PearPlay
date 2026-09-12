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
    return native.state === 'playing' ? 'Helper reports playing (look at the TV to confirm).' : `TV helper: ${native.state}.`;
  };
  async function refresh() {
    try {
      const s = await send('view');
      if (!s.selected && s.candidates.length === 1) {
        await send('select', { id: s.candidates[0].id });
        s.selected = s.candidates[0].id;
      }
      options('candidate', s.candidates, s.selected, 'Choose a video');
      options('receiver', s.native.receivers, s.receiver, 'Choose an Apple TV');
      $('state').textContent = [
        s.enabled ? 'Looking for videos on this page.' : 'Not looking for videos yet.',
        s.candidates.length ? `${s.candidates.length} video${s.candidates.length === 1 ? '' : 's'} found.` : 'No videos found yet.',
        tvStatus(s.native),
      ].join(' ');
      const c = s.candidates.find(item => item.id === s.selected);
      const disconnected = s.native.error === 'NATIVE_DISCONNECTED';
      $('discover').disabled = disconnected;
      $('host').disabled = disconnected;
      $('start').disabled = disconnected || !c || !s.receiver;
      $('confirmTV').disabled = !c?.videoId;
      $('localResume').disabled = !s.localAvailable;
      for (const op of ['pause', 'resume', 'stop']) $(op).disabled = !s.native.capabilities.includes(op);
      const host = $('host').value.trim();
      await memory?.set({ host, receiver: s.receiver ?? '', candidate: s.selected ?? '' });
    } catch {
      notice('Extension unavailable. Reopen this window.');
    }
  }
  const act = fn => async () => {
    try {
      await fn();
      await refresh();
    } catch (error) {
      notice(explain(error));
    }
  };
  for (const op of ['enable', 'disable', 'rescan']) {
    $(op).onclick = act(async () => {
      const r = await send(op);
      notice(r.total !== undefined
        ? (r.scanned ? `Found videos in ${r.scanned} part${r.scanned === 1 ? '' : 's'} of this page.` : 'No videos yet. Press play, allow this website if needed, reload, then look again.')
        : 'Stopped looking on this page.');
    });
  }
  $('candidate').onchange = act(() => send('select', { id: $('candidate').value }));
  $('receiver').onchange = act(() => send('receiver', { id: $('receiver').value }));
  for (const op of ['hello', 'start', 'status', 'stop', 'pause', 'resume', 'localResume']) {
    $(op).onclick = act(() => send(op));
  }
  const findTVs = async () => {
    notice('Looking for Apple TVs…');
    const host = $('host').value.trim();
    const r = await send('discover', host ? { host } : {});
    const n = r.receivers?.length ?? 0;
    notice(n === 1 ? 'Apple TV found and selected. Press Send to Apple TV.' : n ? `Found ${n} Apple TVs. Choose one, then send.` : 'No Apple TVs found on their own. Paste the TV address below, then press Find Apple TVs or Enter.');
  };
  $('discover').onclick = act(findTVs);
  $('host').addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      $('discover').click();
    }
  });
  $('confirmTV').onclick = act(() => send('localPause', { confirmed: true }));
  $('grantAll').onclick = act(async () => {
    const granted = await chrome.permissions.request({ origins: ['http://*/*', 'https://*/*'] });
    notice(granted ? 'Allowed. Find videos, press play, then look again.' : 'Not allowed. PearPlay can only see this page if the site permits it.');
  });
  $('grantSite').onclick = act(async () => {
    const u = new URL(tab.url);
    if (!['http:', 'https:'].includes(u.protocol)) throw Error('UNSUPPORTED_PAGE');
    const granted = await chrome.permissions.request({ origins: [`${u.protocol}//${u.hostname}/*`] });
    notice(granted ? 'This website is allowed. Reload, press play, then find videos.' : 'Not allowed.');
  });
  $('reload').onclick = act(() => chrome.tabs.reload(tab.id));
  const saved = await memory?.get(['host']) ?? {};
  if (saved.host) {
    $('host').value = saved.host;
    $('hostDetails').open = true;
  }
  await refresh();
  try {
    await send('hello');
    await findTVs();
    await refresh();
  } catch (error) {
    notice(explain(error));
  }
  setInterval(refresh, 2000);
})();
