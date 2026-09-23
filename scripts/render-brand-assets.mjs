import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {readFileSync,writeFileSync,mkdirSync,copyFileSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {chromeSession} from './chrome-session.mjs';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const file=p=>resolve(root,p);
const read=p=>readFileSync(file(p),'utf8');
const save=(p,data)=>{mkdirSync(dirname(file(p)),{recursive:true});writeFileSync(file(p),data);};
const raster=(source,target,size)=>{
  mkdirSync(dirname(file(target)),{recursive:true});
  execFileSync(process.env.RSVG_CONVERT||'rsvg-convert',['-w',String(size),'-h',String(size),'-o',file(target),file(source)]);
};
for(const size of [16,32,48,128,1024]) raster(size===16?'assets/brand/mark-small.svg':'assets/brand/app-icon.svg',size===1024?'extension/icons/icon.png':`extension/icons/icon${size}.png`,size);
mkdirSync(file('assets/store'),{recursive:true});
copyFileSync(file('extension/icons/icon.png'),file('assets/store/icon-1024.png'));
execFileSync(process.env.RSVG_CONVERT||'rsvg-convert',['-o',file('assets/landing/feature-direct.png'),file('assets/landing/feature-direct.svg')]);

const c=await chromeSession();
const evidence={browser:c.version,scope:'Actual unpacked extension popup.html, synthetic browser/native responses injected before its script. No live receiver, PIN, credentials or playback. Mac headless Chrome; not macOS playback evidence.',controls:[],captures:[],pages:[]};
try {
  const {id}=await c.send('Extensions.loadUnpacked',{path:file('extension')});
  async function page(url,width,height,theme='dark',fixture=false) {
    const {targetId}=await c.send('Target.createTarget',{url:'about:blank'});
    const {sessionId:s}=await c.send('Target.attachToTarget',{targetId,flatten:true});
    for(const method of ['Page.enable','Runtime.enable','Log.enable','Network.enable']) await c.send(method,{},s);
    await c.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false},s);
    await c.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme},{name:'prefers-reduced-motion',value:'reduce'}]},s);
    if(fixture) await c.send('Page.addScriptToEvaluateOnNewDocument',{source:read('tests/browser/brand-fixture.js')},s);
    await c.send('Page.navigate',{url},s);
    for(let i=0;i<100;i++){
      if(await c.evaluate(s,`location.href===${JSON.stringify(url)} && document.readyState==='complete' && ${fixture?"!!document.getElementById('candidate')?.options.length":"true"}`))break;
      if(i===99)throw Error('Page did not finish loading');
      await delay(50);
    }
    await c.evaluate(s,'document.fonts.ready.then(()=>Promise.all([...document.images].map(i=>i.decode().catch(()=>{}))))');
    return {s,targetId};
  }
  async function capture(s,path,width,height,full=false){
    await c.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false},s);
    // First-run setup can open another tab; background tabs may suspend animation frames.
    await c.send('Page.bringToFront',{},s);
    // Let layout and the compositor settle after emulation/decoded image updates.
    await c.evaluate(s,'new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
    const h=full?await c.evaluate(s,'Math.ceil(Math.max(document.documentElement.scrollHeight,document.body.scrollHeight))'):height;
    const image=await c.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:full,clip:{x:0,y:0,width,height:h,scale:1}},s);
    save(path,Buffer.from(image.data,'base64'));
    evidence.captures.push({file:path,width,height:h});
  }
  async function checkPage(s,label){
    const refs=await c.evaluate(s,`({resources:[...document.querySelectorAll('[src],link[href],source[srcset]')].map(e=>({tag:e.tagName,ref:(e.getAttribute('src')||e.getAttribute('href')||e.getAttribute('srcset')).replace(/^data:[^,]+,.*/, 'data:embedded')})),navigation:[...document.querySelectorAll('a[href]')].map(e=>e.getAttribute('href')),metadata:[...document.querySelectorAll('meta[property="og:image"]')].map(e=>e.content),width:innerWidth,scrollWidth:document.documentElement.scrollWidth,imagesOK:[...document.images].every(i=>i.complete&&i.naturalWidth>0)})`);
    assert.ok(refs.imagesOK,`${label}: broken image`);
    assert.ok(refs.scrollWidth<=refs.width,`${label}: horizontal overflow`);
    const related=c.events.filter(e=>e.sessionId===s);
    const errors=related.filter(e=>e.method==='Runtime.exceptionThrown'||(e.method==='Log.entryAdded'&&e.params.entry.level==='error')||(e.method==='Runtime.consoleAPICalled'&&e.params.type==='error'));
    assert.equal(errors.length,0,`${label}: browser console errors`);
    const external=related.filter(e=>e.method==='Network.requestWillBeSent'&&/^https?:/.test(e.params.request.url)).map(e=>new URL(e.params.request.url).origin);
    assert.equal(external.length,0,`${label}: remote resource request`);
    evidence.pages.push({page:label,...refs,consoleErrors:errors.length,remoteRequests:external});
  }
  for(const theme of ['light','dark']){
    const {s,targetId}=await page(`chrome-extension://${id}/popup.html`,360,600,theme,true);
    await capture(s,`assets/store/popup-${theme}.png`,360,600,true);
    await capture(s,`assets/store/popup-${theme}-viewport.png`,360,600);
    await checkPage(s,`popup-${theme}`);
    if(theme==='dark') {
      await c.evaluate(s,"document.querySelectorAll('details').forEach(d=>d.open=true)");
      const keyboard=await c.evaluate(s,`(()=>{const items=[...document.querySelectorAll('button,select,input,summary')].filter(e=>!e.disabled&&e.tabIndex>=0&&e.getClientRects().length);items[0].focus();return items.map(e=>e.id||e.textContent.trim())})()`);
      const reached=new Set();
      for(let i=0;i<keyboard.length+2;i++){
        reached.add(await c.evaluate(s,"document.activeElement.id||document.activeElement.textContent.trim()"));
        await c.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},s);
        await c.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},s);
      }
      assert.ok(keyboard.every(label=>reached.has(label)),'Every enabled control must be keyboard reachable');
      evidence.keyboardControls=keyboard;
      const focus=await c.evaluate(s,"document.getElementById('enable').focus();({style:getComputedStyle(document.getElementById('enable')).outlineStyle,width:getComputedStyle(document.getElementById('enable')).outlineWidth})");
      assert.equal(focus.style,'solid');assert.equal(focus.width,'3px');
      await c.evaluate(s,"document.activeElement.blur();document.querySelectorAll('details').forEach(d=>d.open=false)");
      const click=async id=>c.evaluate(s,`(async()=>{const el=document.getElementById(${JSON.stringify(id)});if(el.disabled)throw Error('disabled control');await el.onclick();return true})()`);
      const called=async op=>c.evaluate(s,`__fixture.calls.some(c=>c.op===${JSON.stringify(op)})`);
      for(const [button,op] of [['grantAll','grant'],['grantSite','grant'],['enable','enable'],['disable','disable'],['enable','enable'],['rescan','rescan'],['reload','reload'],['hello','hello'],['discover','discover'],['status','status']]){
        // The initially allowed fixture disables grantAll; exercise its click from an ungranted state.
        if(button==='grantAll'){await c.evaluate(s,"__fixture.allowed=false;document.getElementById('status').click()");await delay(100);}
        await click(button);assert.ok(await called(op));evidence.controls.push(button);
      }
      await c.evaluate(s,"(async()=>{document.getElementById('candidate').value='example-video';await document.getElementById('candidate').onchange();document.getElementById('receiver').value='example-receiver';await document.getElementById('receiver').onchange()})()");
      assert.ok(await called('select'));assert.ok(await called('receiver'));evidence.controls.push('candidate','receiver');
      assert.equal(await called('localPause'),false,'local video must never pause automatically');
      await click('start');assert.ok(await called('start'));evidence.controls.push('start');
      await capture(s,'assets/evidence/popup-playing.png',360,600,true);
      assert.match(await c.evaluate(s,'document.body.innerText'),/confirm/i);
      assert.equal(await c.evaluate(s,"!!document.getElementById('confirmTV')||!!document.getElementById('localResume')"),false);
      assert.equal(await called('localPause'),false);assert.equal(await called('localResume'),false);
      await click('stop');assert.ok(await called('stop'));evidence.controls.push('stop');
      // Pairing UI exercised without a code: the transport boundary is synthetic and records no PIN.
      await c.evaluate(s,"__fixture.view.native.error='pairing_required';document.getElementById('status').click()");await delay(100);
      assert.equal(await c.evaluate(s,"document.getElementById('pairBox').hidden"),false);
      assert.equal(await c.evaluate(s,"document.getElementById('pin').type"),'password');
      await click('pair');assert.ok(await called('pair'));assert.equal(await c.evaluate(s,"document.getElementById('pin').value"),'');evidence.controls.push('pair');
      await c.evaluate(s,"__fixture.calls=[];document.getElementById('host').value='192.0.2.10';document.getElementById('host').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))");await delay(100);
      assert.ok(await c.evaluate(s,"__fixture.calls.some(c=>c.op==='discover'&&c.host==='192.0.2.10')"));evidence.controls.push('host Enter');
      await c.evaluate(s,"__fixture.hold=true;document.getElementById('discover').click()");await delay(60);
      await capture(s,'assets/evidence/popup-working.png',360,600,true);
      await c.evaluate(s,'__fixture.hold=null;__fixture.release()');await delay(100);
      await c.evaluate(s,"__fixture.view.candidates=[];__fixture.view.selected=null;__fixture.view.native.receivers=[];__fixture.view.receiver=null;document.getElementById('status').click()");await delay(100);
      assert.equal(await c.evaluate(s,"document.getElementById('start').disabled"),true);
      await capture(s,'assets/evidence/popup-empty.png',360,600,true);
      await c.evaluate(s,"__fixture.fail=true;__fixture.view.native.error='NATIVE_DISCONNECTED';document.getElementById('hello').click()");await delay(100);
      await capture(s,'assets/evidence/popup-error.png',360,600,true);
      await checkPage(s,'popup-all-controls-and-states');
    }
    await c.send('Target.closeTarget',{targetId});
  }
  const data=(p,mime)=>`data:${mime};base64,${readFileSync(file(p)).toString('base64')}`;
  const replacements={MARK:data('assets/brand/mark.svg','image/svg+xml'),POPUP_LIGHT:data('assets/store/popup-light-viewport.png','image/png'),POPUP_DARK:data('assets/store/popup-dark-viewport.png','image/png')};
  save('docs/index.html',read('assets/landing/page.html').replace(/\{\{([A-Z_]+)\}\}/g,(_,key)=>{assert.ok(replacements[key]);return replacements[key];}));
  save('docs/.nojekyll','');
  // Local Markdown rendering, not a fabricated GitHub screenshot; no network or GitHub API.
  const html=execFileSync(process.env.PYTHON||'python3.11',['-c','import markdown,sys; print(markdown.markdown(sys.stdin.read(), extensions=["fenced_code","tables"]))'],{input:read('README.md'),encoding:'utf8'});
  save('assets/landing/readme.html',`<!doctype html><html lang="en"><meta charset="utf-8"><base href="../../"><title>PearPlay README · local Markdown render</title><style>body{margin:0;background:#fff;color:#1f2328;font:16px/1.6 system-ui,sans-serif}main{max-width:980px;margin:auto;padding:40px}h1{font-size:34px;border-bottom:1px solid #d1d9e0}h2{margin-top:32px;border-bottom:1px solid #d1d9e0}a{color:#0969da}img{max-width:100%}pre{background:#f6f8fa;padding:16px;overflow:auto;border-radius:6px;font-size:13px}table{border-collapse:collapse}td,th{border:1px solid #d1d9e0;padding:8px}blockquote{margin:0;padding:0 18px;border-left:4px solid #d1d9e0}</style><main>${html}</main></html>`);
  const art=[['assets/brand/icon-legibility.html','assets/brand/icon-legibility.png',1440,900,true],['assets/landing/hero.html','assets/landing/hero.png',1280,800,false],['assets/landing/social-preview.html','assets/landing/social-preview.png',1280,640,false],['assets/store/listing-light.html','assets/store/listing-light.png',1280,800,false],['assets/store/listing-dark.html','assets/store/listing-dark.png',1280,800,false],['docs/index.html','assets/evidence/landing.png',1440,1000,true],['docs/index.html','assets/evidence/landing-first-screen.png',1440,1000,false],['assets/landing/readme.html','assets/evidence/readme.png',1280,900,false]];
  for(const [source,target,width,height,full] of art){
    const {s,targetId}=await page(pathToFileURL(file(source)).href,width,height,'dark');
    await capture(s,target,width,height,full);await checkPage(s,source);
    if(source==='docs/index.html'){
      const copy=await c.evaluate(s,`(async()=>{let text='';Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async t=>{text=t}}});document.querySelector('[data-copy="linux"]').click();await new Promise(r=>setTimeout(r,20));return {text,expected:document.getElementById('linux').textContent,status:document.getElementById('copy-status').textContent}})()`);
      assert.equal(copy.text,copy.expected);assert.match(copy.status,/Copied/);
      const fallback=await c.evaluate(s,`(async()=>{navigator.clipboard.writeText=async()=>{throw Error('denied')};document.querySelector('[data-copy="mac"]').click();await new Promise(r=>setTimeout(r,20));return {selection:getSelection().toString(),expected:document.getElementById('mac').textContent,status:document.getElementById('copy-status').textContent}})()`);
      assert.equal(fallback.selection,fallback.expected);assert.match(fallback.status,/selected/);
      evidence.clipboard='Exact-command copy and denied-permission selection fallback passed (clipboard boundary injected).';
    }
    await c.send('Target.closeTarget',{targetId});
  }
  for(const theme of ['light','dark']){
    const {s,targetId}=await page(pathToFileURL(file('docs/index.html')).href,390,844,theme);
    await capture(s,`assets/evidence/landing-mobile-${theme}.png`,390,844,true);await checkPage(s,`landing-mobile-${theme}`);
    await c.send('Target.closeTarget',{targetId});
  }
  copyFileSync(file('assets/landing/social-preview.png'),file('docs/social-preview.png'));
  assert.ok(readFileSync(file('assets/landing/social-preview.png')).length<1_000_000);
  await c.send('Extensions.uninstall',{id});
  const extensions=await c.send('Extensions.getExtensions');
  assert.equal(extensions.extensions.length,0);
  evidence.cleanup='Unpacked extension uninstalled; owned browser closed and disposable profile removed by finally.';
  save('assets/evidence/render-verification.json',JSON.stringify(evidence,null,2)+'\n');
  console.log(JSON.stringify({browser:c.version,controls:evidence.controls,captures:evidence.captures.length,pages:evidence.pages.length,consoleErrors:0,remotePageRequests:0},null,2));
} finally {await c.close();}
