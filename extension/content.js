(() => {
  if (globalThis.__pearplay) { globalThis.__pearplay.scan(true); return; }
  const ids = new WeakMap();
  const epochs = new WeakMap();
  let serial = 0;
  let live = new Map();
  let until = Date.now() + 600000;
  let timer;
  // Recover manifests fetched before Find videos began observing requests.
  // Only deliberate scans read history; quiet polling must not renew old URLs.
  function resources() {
    const perf = globalThis.performance;
    if (!perf?.getEntriesByType) return [];
    const now = perf.now();
    return perf.getEntriesByType('resource').slice(-2000).filter(e =>
      typeof e.name === 'string' && e.name.length <= 16384 &&
      /^https?:\/\/[^?#]+\.m3u8(?:[?#]|$)/i.test(e.name) &&
      Number.isFinite(e.startTime) && e.startTime >= 0 &&
      now >= e.startTime && now - e.startTime < 600000
    ).slice(0, 100).map(e => ({url:e.name, at:perf.timeOrigin + e.startTime}));
  }
  async function scan(recover = false) {
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
        if (typeof url === 'string' && /^(?:https?:\/\/|blob:https?:\/\/)/i.test(url) && url.length <= 16384) {
          const title = [el.title, el.getAttribute?.('aria-label'), el.getAttribute?.('title'), document.title].find(t => typeof t === 'string' && t.trim());
          videos.push({videoId, url, title: typeof title === 'string' ? title.trim().slice(0, 80) : ''});
        }
      }
    }
    try {
      const result = await chrome.runtime.sendMessage({op: 'videos', videos, ...(recover ? {resources:resources()} : {})});
      if (!result?.enabled) { clearInterval(timer); live.clear(); }
      else if (result.keepAlive === true) until = Date.now() + 600000;
    } catch { clearInterval(timer); live.clear(); }
  }
  chrome.runtime.onMessage.addListener((m, _sender, reply) => {
    if (m.op === 'rescan') {
      until = Date.now() + 600000;
      clearInterval(timer); timer = setInterval(scan, 1500); scan(true); reply({ok: true}); return;
    }
    if (!['validateVideo', 'localPause', 'localResume', 'browserControl'].includes(m.op)) return;
    const el = live.get(m.videoId);
    if (!el?.isConnected || el.currentSrc !== m.url || (m.op === 'localPause' && m.confirmed !== true)) {
      reply({ok: false, error: 'VIDEO_CHANGED_OR_UNCONFIRMED'}); return;
    }
    if (m.op === 'browserControl') {
      const epoch = epochs.get(el);
      const current = () => el.isConnected && live.get(m.videoId) === el && el.currentSrc === m.url && epochs.get(el) === epoch;
      const windowRange = () => {
        const ranges = Array.from({length: Math.min(el.seekable?.length ?? 0, 100)}, (_, i) => [el.seekable.start(i), el.seekable.end(i)]);
        return ranges.filter(([a,b]) => Number.isFinite(a) && Number.isFinite(b) && b > a);
      };
      const snapshot = () => {
        const ranges = windowRange();
        return {ok:true, paused:!!el.paused, muted:!!el.muted, time:Number.isFinite(el.currentTime)?el.currentTime:0,
          duration:Number.isFinite(el.duration)?el.duration:null, ranges, pip:document.pictureInPictureElement === el,
          pipAvailable:!!document.pictureInPictureEnabled && !el.disablePictureInPicture && typeof el.requestPictureInPicture === 'function'};
      };
      (async () => {
        try {
          switch (m.action) {
            case 'status': break;
            case 'play': await el.play(); break;
            case 'pause': el.pause(); break;
            case 'mute': if (typeof m.value !== 'boolean') throw Error('INVALID_CONTROL'); el.muted=m.value; break;
            case 'seek': case 'skip': {
              if (!Number.isFinite(m.value) || m.action==='skip' && ![-30,-15,-10,-5,5,10,15,30].includes(m.value)) throw Error('INVALID_CONTROL');
              const ranges=windowRange(); if (!ranges.length) throw Error('NO_SEEK_WINDOW');
              const target=m.action==='skip'?el.currentTime+m.value:m.value;
              const nearest=ranges.flatMap(([a,b]) => [a,b]).reduce((best,n)=>Math.abs(n-target)<Math.abs(best-target)?n:best);
              el.currentTime=ranges.some(([a,b])=>target>=a&&target<=b)?target:nearest; break;
            }
            case 'pip':
              if (document.pictureInPictureElement === el) await document.exitPictureInPicture();
              else if (document.pictureInPictureElement) throw Error('PIP_OTHER_VIDEO');
              else await el.requestPictureInPicture();
              break;
            case 'return': el.scrollIntoView({block:'center',behavior:'instant'}); break;
            default: throw Error('INVALID_CONTROL');
          }
          reply(current()?snapshot():{ok:false,error:'VIDEO_CHANGED_OR_UNCONFIRMED'});
        } catch (error) {
          const known=['NO_SEEK_WINDOW','INVALID_CONTROL','PIP_OTHER_VIDEO'];
          reply({ok:false,error:!current()?'VIDEO_CHANGED_OR_UNCONFIRMED':known.includes(error.message)?error.message:'BROWSER_CONTROL_BLOCKED'});
        }
      })();
      return true;
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
  globalThis.__pearplay = {scan}; timer = setInterval(scan, 1500); scan(true);
})();
