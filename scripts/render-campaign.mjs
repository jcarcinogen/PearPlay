// Renders artwork from reviewed HTML and real popup captures; never contacts a TV.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync,copyFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {resolve,dirname} from 'node:path';
import {pathToFileURL} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {chromeSession} from './chrome-session.mjs';
const root=resolve(import.meta.dirname,'..');
const output=resolve(process.env.PEARPLAY_ART_OUTPUT||'/Volumes/IronWolf/Stuff/PearPlay/Cross-platform Preview/Artwork');
mkdirSync(output,{recursive:true});
const read=p=>readFileSync(resolve(root,p));
const data=(p,type)=>`data:${type};base64,${read(p).toString('base64')}`;
const substitutions={MARK:data('assets/brand/mark.svg','image/svg+xml'),POPUP_LIGHT:data('assets/store/popup-light-viewport.png','image/png'),POPUP_DARK:data('assets/store/popup-dark-viewport.png','image/png')};
writeFileSync(resolve(root,'docs/index.html'),read('assets/landing/page.html').toString().replace(/\{\{([A-Z_]+)\}\}/g,(_,key)=>{assert.ok(substitutions[key]);return substitutions[key];}));
const specs=[['assets/store/listing-light.html','listing-light.png',1280,800],['assets/store/listing-dark.html','listing-dark.png',1280,800],['assets/store/listing-platforms.html','listing-platforms.png',1280,800],['assets/store/promo-small.html','promo-small-440x280.png',440,280],['assets/store/promo-marquee.html','promo-marquee-1400x560.png',1400,560],['assets/landing/hero.html','hero.png',1280,800],['assets/landing/social-preview.html','social-preview.png',1280,640],['docs/index.html','landing-desktop.png',1440,1000],['docs/index.html','landing-mobile.png',390,844]];
const c=await chromeSession();
const report={browser:c.version,scope:'Local promotional compositions; supplied actual popup captures use example data. No live playback or cross-platform acceptance implied.',images:[]};
try{
 for(const [source,name,width,height] of specs.filter(row=>!process.env.PEARPLAY_ART_FILTER||row[1].includes(process.env.PEARPLAY_ART_FILTER))){ 
  const {targetId}=await c.send('Target.createTarget',{url:'about:blank'});
  const {sessionId:s}=await c.send('Target.attachToTarget',{targetId,flatten:true});
  for(const method of ['Page.enable','Runtime.enable','Network.enable','Log.enable'])await c.send(method,{},s);
  await c.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false},s);
  await c.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:source.includes('light')?'light':'dark'},{name:'prefers-reduced-motion',value:'reduce'}]},s);
  const url=pathToFileURL(resolve(root,source)).href;
  await c.send('Page.navigate',{url},s);
  for(let i=0;i<120;i++){
   if(await c.evaluate(s,`location.href===${JSON.stringify(url)}&&document.readyState==='complete'`))break;
   assert.notEqual(i,119,'page loading timeout');await delay(50);
  }
  await c.send('Page.bringToFront',{},s);
  await c.evaluate(s,'document.fonts.ready.then(()=>Promise.all([...document.images].map(i=>i.decode())))');
  await c.evaluate(s,'new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
  const geometry=await c.evaluate(s,`({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,images:[...document.images].map(e=>({src:e.getAttribute('src').startsWith('data:')?'embedded':e.getAttribute('src'),loaded:e.complete&&e.naturalWidth>0})),overflow:[...document.querySelectorAll('h1,.copy,.product,.platform-card,.foot,header')].map(e=>{const r=e.getBoundingClientRect();return {tag:e.className||e.tagName,x:r.x,y:r.y,right:r.right,bottom:r.bottom}})})`);
  assert.ok(geometry.images.every(i=>i.loaded),`${source}: missing image`);
  assert.ok(geometry.scrollWidth<=width,`${source}: horizontal overflow`);
  if(!source.startsWith('docs/'))for(const e of geometry.overflow)assert.ok(e.x>=0&&e.y>=0&&e.right<=width+.5&&e.bottom<=height+.5,`${source}: ${e.tag} outside canvas`);
  const events=c.events.filter(e=>e.sessionId===s);
  assert.equal(events.filter(e=>e.method==='Runtime.exceptionThrown'||(e.method==='Log.entryAdded'&&e.params.entry.level==='error')).length,0,`${source}: console errors`);
  assert.equal(events.filter(e=>e.method==='Network.requestWillBeSent'&&/^https?:/.test(e.params.request.url)).length,0,`${source}: external request`);
  const shot=await c.send('Page.captureScreenshot',{format:'png',clip:{x:0,y:0,width,height,scale:1}},s);
  const target=resolve(output,name);writeFileSync(target,Buffer.from(shot.data,'base64'));
  // Chrome can emit RGBA. Store upload deliverables must be explicit 24-bit RGB.
  execFileSync('magick',[target,'-background',source.includes('light')?'#f4f3ec':'#101a14','-alpha','remove','-alpha','off','-depth','8',`PNG24:${target}`]);
  const png=readFileSync(target);assert.equal(png.readUInt32BE(16),width);assert.equal(png.readUInt32BE(20),height);assert.equal(png[24],8);assert.equal(png[25],2);
  report.images.push({name,source,width,height,format:'24-bit RGB PNG',...geometry});
  if(source.startsWith('assets/store/'))copyFileSync(target,resolve(root,'assets/store',name));
  if(source.startsWith('assets/landing/'))copyFileSync(target,resolve(root,'assets/landing',name));
  await c.send('Target.closeTarget',{targetId});
 }
 if(report.images.some(i=>i.name==='social-preview.png'))copyFileSync(resolve(output,'social-preview.png'),resolve(root,'docs/social-preview.png'));
 writeFileSync(resolve(output,'render-verification.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({browser:c.version,images:report.images.map(({name,width,height,format})=>({name,width,height,format})),consoleErrors:0,remoteRequests:0},null,2));
}finally{await c.close();}
