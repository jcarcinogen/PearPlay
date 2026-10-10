(() => {
  if (globalThis.__pearplay) { globalThis.__pearplay.scan(); return; }
  const ids = new WeakMap();
  const epochs = new WeakMap();
  let serial = 0;
  let live = new Map();
  let until = Date.now() + 600000;
  let timer;
  async function scan() {
    if (Date.now() > until) { clearInterval(timer); live.clear(); return; }
    const videos = [];
    live = new Map();
    const roots = [document];
    let budget = 20000;
    while (roots.length && budget > 0 && videos.length < 100) {
      const root = roots.pop();
      for (const el of root.querySelectorAll('*')) {
        if (--budget <= 0 || videos.length >= 100) break;
        if (el.shadowRoot) roots.push(el.shadowRoot);
        if (el.tagName !== 'VIDEO') continue;
        if (!epochs.has(el)) {
          epochs.set(el, 0);
          const invalidate = () => {
            epochs.set(el, epochs.get(el) + 1);
            live.delete(ids.get(el));
            ids.delete(el);
          };
          for (const event of ['emptied', 'loadstart']) el.addEventListener?.(event, invalidate);
        }
        if (!ids.has(el)) ids.set(el, `v${++serial}`);
        const videoId = ids.get(el);
        live.set(videoId, el);
        const url = el.currentSrc;
        if (typeof url === 'string' && /^https?:\/\//i.test(url) && url.length <= 16384) {
          const title = [el.title, el.getAttribute?.('aria-label'), el.getAttribute?.('title'), document.title].find(t => typeof t === 'string' && t.trim());
          videos.push({videoId, url, title: typeof title === 'string' ? title.trim().slice(0, 80) : ''});
        }
      }
    }
    try {
      const result = await chrome.runtime.sendMessage({op: 'videos', videos});
      if (!result?.enabled) { clearInterval(timer); live.clear(); }
    } catch { clearInterval(timer); live.clear(); }
  }
  chrome.runtime.onMessage.addListener((m, _sender, reply) => {
    if (m.op === 'rescan') {
      until = Date.now() + 600000;
      clearInterval(timer); timer = setInterval(scan, 1500); scan(); reply({ok: true}); return;
    }
    if (!['validateVideo', 'localPause', 'localResume'].includes(m.op)) return;
    const el = live.get(m.videoId);
    if (!el?.isConnected || el.currentSrc !== m.url || (m.op === 'localPause' && m.confirmed !== true)) {
      reply({ok: false, error: 'VIDEO_CHANGED_OR_UNCONFIRMED'}); return;
    }
    if (m.op === 'validateVideo') { reply({ok:true}); return; }
    if (m.op === 'localPause') { el.pause(); reply({ok: true}); return; }
    const epoch = epochs.get(el);
    const current = () => el.isConnected && live.get(m.videoId) === el && el.currentSrc === m.url && epochs.get(el) === epoch;
    // Never report success (or an autoplay error) for a different element/source.
    // No corrective pause or retarget is sent to the changed video.
    el.play().then(
      () => reply(current() ? {ok: true} : {ok: false, error: 'VIDEO_CHANGED_OR_UNCONFIRMED'}),
      () => reply({ok: false, error: current() ? 'LOCAL_PLAY_BLOCKED' : 'VIDEO_CHANGED_OR_UNCONFIRMED'})
    );
    return true;
  });
  globalThis.__pearplay = {scan}; timer = setInterval(scan, 1500); scan();
})();
