import test from 'node:test';
import assert from 'node:assert/strict';
test('navigation, stale documents, TTL and bounded sessions fail closed', async () => {
 const {Sessions}=await load(); let now=0; const s=new Sessions({now:()=>now,ttl:100,maxCandidates:2,maxTabs:2});
 s.enable(1); s.commit({tabId:1,frameId:0,documentId:'a'});
 const event={tabId:1,frameId:0,documentId:'a',type:'media',url:'https://x/1.mp4'};
 s.observe(event); s.select(1,s.view(1).candidates[0].id);
 s.commit({tabId:1,frameId:0,documentId:'b'}); s.observe(event);
 assert.equal(s.view(1).candidates.length,0); assert.throws(()=>s.selected(1));
 for(let i=0;i<4;i++) s.observe({...event,documentId:'b',url:`https://x/${i}.mp4`});
 assert.equal(s.view(1).candidates.length,2);
 now=101; assert.equal(s.view(1).enabled,false);
 s.enable(1);s.enable(2);s.enable(3);assert.equal(s.view(1).enabled,false);
 s.disable(2);assert.equal(s.view(2).enabled,false);
});
test('unknown documents rejected and video snapshots replace stale sources without URL guessing',async()=>{
 const {Sessions}=await load();const s=new Sessions();s.enable(1);
 s.observe({tabId:1,frameId:9,type:'media',url:'https://x/unknown'});assert.equal(s.view(1).candidates.length,0);
 s.commit({tabId:1,frameId:0,documentId:'a'});
 s.observe({tabId:1,frameId:0,documentId:'a',type:'media',url:'https://x/v.mp4'});
 s.videos({tabId:1,frameId:0,documentId:'a'},[{videoId:'v1',url:'https://x/v.mp4'}]);
 assert.equal(s.view(1).candidates.length,2);const video=s.view(1).candidates.find(c=>c.videoId);s.select(1,video.id);
 s.videos({tabId:1,frameId:0,documentId:'a'},[]);assert.throws(()=>s.selected(1));assert.equal(s.view(1).candidates.length,1);
});
test('network responses require same navigation generation and request attribution',async()=>{
 const {Sessions}=await load();const s=new Sessions();s.enable(1);s.commit({tabId:1,frameId:0,documentId:'a'});
 const e={tabId:1,frameId:0,documentId:'a',requestId:'r',type:'media',url:'https://x/v.mp4'};
 s.begin(e);s.commit({tabId:1,frameId:0,documentId:'a'});s.response(e);assert.equal(s.view(1).candidates.length,0);
 s.begin({...e,requestId:'new'});s.response({...e,requestId:'new'});assert.equal(s.view(1).candidates.length,1);
});
test('child navigation invalidates descendant documents and MIME manifests remain candidates only',async()=>{
 const {Sessions}=await load();const s=new Sessions();s.enable(1);
 s.commit({tabId:1,frameId:0,documentId:'a'});s.commit({tabId:1,frameId:2,parentFrameId:0,documentId:'b'});s.commit({tabId:1,frameId:3,parentFrameId:2,documentId:'c'});
 const e={tabId:1,frameId:3,documentId:'c',url:'https://x/opaque?key=%2F',type:'xmlhttprequest',responseHeaders:[{name:'Content-Type',value:'application/vnd.apple.mpegurl; charset=utf-8'}]};
 s.observe(e);assert.equal(s.view(1).candidates.length,1);
 s.observe({...e,url:'https://x/other',responseHeaders:[{name:'Content-Type',value:'video/mp4'}]});assert.equal(s.view(1).candidates.length,2);
 s.commit({tabId:1,frameId:2,parentFrameId:0,documentId:'d'});s.observe(e);assert.equal(s.view(1).candidates.length,0);
});
test('network candidates require HLS or MP4 evidence, never segments or unsupported containers',async()=>{
 const {Sessions}=await load();const s=new Sessions();s.enable(1);s.commit({tabId:1,frameId:0,documentId:'a'});
 const e={tabId:1,frameId:0,documentId:'a',type:'media'};
 for(const [url,mime] of [
  ['https://x/segment.ts','video/mp2t'],['https://x/init.m4s','video/mp4'],
  ['https://x/movie.webm','video/webm'],['https://x/manifest.mpd','application/dash+xml'],
  ['https://x/opaque',''],['https://x/request?file=movie.mp4',''],
  ['https://x/fake.mp4','text/html'],['https://x/segment.ts','video/mp4']
 ]) {s.observe({...e,url,responseHeaders:[{name:'Content-Type',value:mime}]});assert.equal(s.view(1).candidates.length,0,url);}
 for(const [url,mime] of [['https://x/master.m3u8',''],['https://x/movie.mp4','application/octet-stream'],['https://x/hls','Application/X-MpegURL; charset=utf-8'],['https://x/mp4','video/mp4']])
  s.observe({...e,url,type:'xmlhttprequest',responseHeaders:[{name:'Content-Type',value:mime}]});
 assert.equal(s.view(1).candidates.length,4);
 s.videos(e,[{videoId:'v1',url:'https://x/movie.webm'},{videoId:'v2',url:'https://x/segment.ts'},{videoId:'v3',url:'https://x/opaque-video'}]);
 assert.equal(s.view(1).candidates.length,5); // exact opaque currentSrc remains explicitly unverified
});
test('source labels expose only hostname, format and attribution, never signed paths',async()=>{
 const {Sessions}=await load();const s=new Sessions();s.enable(1);const e={tabId:1,frameId:0,documentId:'a'};s.commit(e);
 s.observe({...e,url:'https://cdn.test/private-token/master.m3u8?sig=secret#fragment',type:'xmlhttprequest'});
 s.videos(e,[{videoId:'v1',url:'https://media.test/private/movie.mp4?sig=secret'},{videoId:'v2',url:'https://opaque.test/private?sig=secret'}]);
 const labels=s.view(1).candidates.map(c=>c.label);
 assert.match(labels[0],/cdn\.test.*HLS.*unverified.*frame 0.*network/);
 assert.match(labels[1],/media\.test.*MP4.*unverified.*video element/);
 assert.match(labels[2],/opaque\.test.*Unknown format.*unverified.*video element/);
 assert.doesNotMatch(JSON.stringify(s.view(1)),/private|secret|sig=|fragment|https:/);
});
test('URL validation rejects parser repair while keeping accepted signed strings exact',async()=>{
 const {httpURL,Sessions}=await load();
 for(const url of ['https:///cdn.test/a.mp4','https:////cdn.test/a.mp4','https://@cdn.test/a.mp4',
  'https://cdn.test\\a.mp4','https://cdn.test/a\uD800.mp4','https://cdn.test/a\uDC00.mp4',
  'https://cdn.test/a%.mp4','https://cdn.test/a%2G.mp4','https://cdn.test:99999/a.mp4',
  'https://cdn.test/a\nb.mp4','https://user:pass@cdn.test/a.mp4']) {
  assert.equal(httpURL(url),false,JSON.stringify(url));
 }
 const s=new Sessions();s.enable(1);const e={tabId:1,frameId:0,documentId:'a'};s.commit(e);
 for(const url of ['HTTPS://CDN.test:443/a/../movie.mp4?sig=%2f+X&x=2&x=1#keep','https://cdn.test/😀.mp4?sig=%FF']) {
  assert.equal(httpURL(url),true);s.observe({...e,url});s.select(1,s.view(1).candidates.at(-1).id);assert.equal(s.selected(1).url,url);
 }
});
const load = () => import('../../extension/core.mjs');
test('explicit candidate selection preserves exact URL and hides it in labels', async () => {
  const { Sessions } = await load(); const s = new Sessions();
  s.enable(7); s.commit({tabId:7,frameId:0,documentId:'doc'});
  const url='https://cdn.test/a.m3u8?sig=%2f+X&x=2&x=1';
  s.observe({tabId:7,frameId:0,documentId:'doc',url,type:'xmlhttprequest'});
  const view=s.view(7); assert.equal(view.candidates.length,1);
  assert.equal(JSON.stringify(view).includes('sig'),false);
  assert.throws(()=>s.selected(7));
  s.select(7,view.candidates[0].id); assert.equal(s.selected(7).url,url);
  s.observe({tabId:7,frameId:0,documentId:'doc',url:'blob:https://test/x',type:'media'});
  assert.equal(s.view(7).candidates.length,1);
});
