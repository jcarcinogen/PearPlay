export function httpURL(url) {
  if (typeof url !== 'string' || url.length > 16384 || /[\\\s\u0000-\u001f\u007f\uD800-\uDFFF]/u.test(url) || /%(?![\da-f]{2})/i.test(url)) return false;
  const authority = /^https?:\/\/([^/?#]+)/i.exec(url)?.[1];
  if (!authority || authority.includes('@')) return false;
  try { const u = new URL(url); return !!u.hostname && !u.username && !u.password; } catch { return false; }
}
// Blob sources are browser-controllable, never directly fetchable by a TV.
function browserURL(url) { return typeof url === 'string' && url.startsWith('blob:') && httpURL(url.slice(5)); }
export function safeTitle(text) {
  if (typeof text !== 'string') return '';
  const t = text.replace(/\s+/g, ' ').trim().slice(0, 80);
  if (!t || /https?:\/\//i.test(t) || /\bwww\./i.test(t) || /[?#]/.test(t)) return '';
  return t;
}
// Evidence of a plausible source, not a codec/DRM/receiver compatibility claim.
function sourceType(e) {
  const path = new URL(e.url).pathname;
  if (/\.(?:ts|m4s|mpd|webm)(?:$)/i.test(path)) return null;
  const mime = (e.responseHeaders?.find(h=>h.name.toLowerCase()==='content-type')?.value??'').split(';')[0].trim().toLowerCase();
  if (['application/vnd.apple.mpegurl','application/x-mpegurl','audio/mpegurl','audio/x-mpegurl'].includes(mime)) return 'HLS';
  if (mime === 'video/mp4') return 'MP4';
  if (mime && mime !== 'application/octet-stream') return null;
  if (/\.m3u8$/i.test(path)) return 'HLS';
  if (/\.(?:mp4|m4v)$/i.test(path)) return 'MP4';
  return e.videoId ? 'Unknown format' : null;
}
export class Sessions {
  constructor({now=()=>Date.now(),ttl=600000,maxCandidates=100,maxTabs=8}={}) { Object.assign(this,{now,ttl,maxCandidates,maxTabs}); this.tabs = new Map(); this.next = 0; }
  sweep() {
    const now=this.now();
    for(const [id,s] of this.tabs) {
      if(now-s.at>=this.ttl){this.tabs.delete(id);continue;}
      s.candidates=s.candidates.filter(c=>now-c.at<this.ttl);
      if(s.selected&&!s.candidates.some(c=>c.id===s.selected)){s.selected=null;s.selectionLost=true;}
    }
  }
  disable(id) { this.tabs.delete(id); }
  enable(tabId) { this.sweep(); this.tabs.delete(tabId); if(this.tabs.size>=this.maxTabs) this.tabs.delete(this.tabs.keys().next().value); this.tabs.set(tabId, {revision:0,at:this.now(),requests:new Map(),parents:new Map(),frames:new Map(), candidates:[], selected:null, pageTitle:''}); }
  pageTitle(tabId, text) { const s=this.tabs.get(tabId); if(s) s.pageTitle=safeTitle(text); }
  commit({tabId, frameId, documentId, parentFrameId=-1}) {
    this.sweep();const s=this.tabs.get(tabId);if(!s||!documentId)return;s.revision++;s.requests.clear();
    if(frameId===0){s.frames.clear();s.parents.clear();s.candidates=[];}
    else {const removed=new Set([frameId]);let changed=true;while(changed){changed=false;for(const [id,parent] of s.parents)if(removed.has(parent)&&!removed.has(id)){removed.add(id);changed=true;}}
      for(const id of removed){s.frames.delete(id);s.parents.delete(id);}s.candidates=s.candidates.filter(c=>!removed.has(c.frameId));}
    if(s.selected&&!s.candidates.some(c=>c.id===s.selected)){s.selected=null;s.selectionLost=true;}if(s.frames.size<128){s.frames.set(frameId,documentId);s.parents.set(frameId,parentFrameId);}
  }
  begin(e) {
    this.sweep();const s=this.tabs.get(e.tabId);if(!s||!e.documentId||s.frames.get(e.frameId)!==e.documentId)return;
    if(s.requests.size>=256)s.requests.delete(s.requests.keys().next().value);
    s.requests.set(e.requestId,{frameId:e.frameId,documentId:e.documentId});
  }
  response(e) {
    this.sweep();const s=this.tabs.get(e.tabId);const r=s?.requests.get(e.requestId);s?.requests.delete(e.requestId);
    if(r&&r.frameId===e.frameId&&r.documentId===e.documentId)this.observe(e);
  }
  videos(e,items) {
    this.sweep();const s=this.tabs.get(e.tabId);if(!s||!e.documentId||s.frames.get(e.frameId)!==e.documentId)return;
    const safe=items.slice(0,100).filter(v=>typeof v.videoId==='string'&&/^v\d{1,10}$/.test(v.videoId)&&(httpURL(v.url)||browserURL(v.url)));
    const chosen=s.candidates.find(c=>c.id===s.selected);
    const keepAlive=!!chosen?.videoId && chosen.frameId===e.frameId && chosen.documentId===e.documentId && safe.some(v=>v.videoId===chosen.videoId&&v.url===chosen.url);
    // Renew only a still-present, exact, deliberately selected DOM source.
    // EOF does not revoke it; navigation, source epochs and missing snapshots do.
    if(keepAlive)s.at=this.now();
    s.candidates=s.candidates.filter(c=>c.frameId!==e.frameId||!c.videoId||safe.some(v=>v.videoId===c.videoId&&v.url===c.url));
    for(const v of safe)this.observe({...e,videoId:v.videoId,url:v.url,title:v.title,type:'media'});
    if(s.selected&&!s.candidates.some(c=>c.id===s.selected)){s.selected=null;s.selectionLost=true;}
    return keepAlive;
  }
  observe(e) {
    this.sweep(); const s=this.tabs.get(e.tabId);
    if (!s || typeof e.documentId!=='string' || !s.frames.has(e.frameId) || !(httpURL(e.url)||e.videoId&&browserURL(e.url)) || s.frames.get(e.frameId)!==e.documentId) return;
    const format=browserURL(e.url)?'Browser video':sourceType(e);
    if (!format) return;
    const existing=s.candidates.find(c=>c.url===e.url && c.frameId===e.frameId && c.videoId===(e.videoId??null));
    if(existing){existing.at=this.now();return;}
    if (!e.videoId && format==='HLS' && s.candidates.some(c=>!c.videoId && c.format==='HLS' && new URL(c.url).hostname===new URL(e.url).hostname)) return;
    s.candidates.push({at:this.now(),format,url:e.url,frameId:e.frameId,documentId:e.documentId,videoId:e.videoId??null,title:safeTitle(e.title),id:`c${++this.next}`});
    if(s.candidates.length>this.maxCandidates) s.candidates.shift();
    if(s.selected&&!s.candidates.some(c=>c.id===s.selected)){s.selected=null;s.selectionLost=true;}
  }
  view(tabId) {
    this.sweep();
    const s=this.tabs.get(tabId);
    return {
      enabled:!!s,
      selected:s?.selected??null,
      selectionLost:!!s?.selectionLost,
      candidates:(s?.candidates??[]).map((c,i,all)=>{
        const name=c.title||s.pageTitle||'';
        const used=all.map(x=>x.title||s.pageTitle||'');
        let label=name;
        if(!label) label=all.length===1?"This page's video":`Video ${i+1}`;
        else if(used.filter(t=>t===name).length>1) label=`${name} · ${used.slice(0,i+1).filter(t=>t===name).length}`;
        return {id:c.id,label,videoId:c.videoId??null,sendable:httpURL(c.url)};
      })
    };
  }
  select(tabId,id) { this.sweep(); const s=this.tabs.get(tabId); if (!s?.candidates.some(c=>c.id===id)) throw Error('NO_CANDIDATE'); s.selected=id;s.selectionLost=false; }
  current(tabId,c) { this.sweep();const s=this.tabs.get(tabId);return !!s&&s.frames.get(c.frameId)===c.documentId&&s.candidates.some(item=>item.id===c.id&&item.videoId===c.videoId&&item.url===c.url&&item.documentId===c.documentId); }
  selected(tabId) { this.sweep(); const s=this.tabs.get(tabId); const c=s?.candidates.find(c=>c.id===s.selected); if(!c) throw Error('NO_CANDIDATE'); return c; }
}
