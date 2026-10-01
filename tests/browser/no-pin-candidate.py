"""Exact candidate + sandboxed Chrome; discovery only, never pair/send/firewall writes.
Run on Linux with --archive PATH --sha256 SHA --chrome PATH --output PATH.
Synthetic action-popup states are labeled separately from real-native evidence.
"""
import argparse, asyncio, base64, functools, hashlib, json, os, subprocess, tempfile, tarfile, threading
from http import server as httpserver
from pathlib import Path
import aiohttp
ROOT = Path('/Volumes/IronWolf/Projects/PearPlay')
parser=argparse.ArgumentParser()
parser.add_argument('--archive',type=Path,required=True)
parser.add_argument('--sha256',required=True)
parser.add_argument('--chrome',required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
ARCHIVE=args.archive
SHA=args.sha256
ID='eoadahoncjfpnennmkjifohclbafjkol'
CACHE=Path.home()/'.cache/pearplay-investigation'
assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()==SHA
TEMP_ROOTS=[]

async def trial(installed):
    with tempfile.TemporaryDirectory(prefix='candidate028-',dir=CACHE) as directory:
        base=Path(directory); TEMP_ROOTS.append(base); profile=base/'google-chrome'; profile.mkdir()
        for name in ('home','state','tmp','extension'): (base/name).mkdir()
        artifact=base/'extension'
        with tarfile.open(ARCHIVE) as archive:
            archive.extractall(base,filter='data')
        original={str(p.relative_to(artifact)):p.read_bytes() for p in artifact.rglob('*') if p.is_file()}
        BINARY=str(base/'PearPlayHelper/PearPlayHelper')
        config=json.loads((base/'PearPlayHelper/_internal/build.json').read_text())
        assert config['development'] is False and config['extension_id']==ID and config['version']=='0.2.8'
        manifest=json.loads((artifact/'manifest.json').read_text())
        assert manifest['version']=='0.2.8'
        derived=''.join(chr(97+int(c,16)) for c in hashlib.sha256(base64.b64decode(manifest['key'])).hexdigest()[:32])
        assert derived==ID
        env={k:v for k,v in os.environ.items() if not k.startswith('PEARPLAY_')}
        env.update(HOME=str(base/'home'),XDG_CONFIG_HOME=str(base/'xdg'),XDG_STATE_HOME=str(base/'state'),TMPDIR=str(CACHE/'tmp'))
        def register(action):
            r=subprocess.run([BINARY,action,'--browsers','chrome','--config-parent',str(base)],env=env,capture_output=True,text=True,timeout=20,check=True)
            return json.loads(r.stdout)['chrome']
        host=profile/'NativeMessagingHosts/com.pearplay.helper.json'
        if installed:
            assert register('connect')=='connected'
            first=host.read_bytes()
            assert register('connect')=='connected' and host.read_bytes()==first
            h=json.loads(first); assert h['path']==BINARY
            assert h['allowed_origins']==['chrome-extension://'+ID+'/']
        exceptions=[]
        with (base/'browser.log').open('wb') as log:
            proc=subprocess.Popen([args.chrome,'--headless=new','--no-first-run','--no-default-browser-check','--enable-unsafe-extension-debugging','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+str(profile),'about:blank'],env=env,stdout=log,stderr=log)
            try:
                for _ in range(100):
                    if (profile/'DevToolsActivePort').exists():break
                    if proc.poll() is not None:
                        raise RuntimeError('browser_exited')
                    await asyncio.sleep(.1)
                lines=(profile/'DevToolsActivePort').read_text().splitlines()
                async with aiohttp.ClientSession() as http:
                    async with http.ws_connect('http://127.0.0.1:'+lines[0]+lines[1]) as ws:
                        serial=0
                        async def call(method,params=None,session=None):
                            nonlocal serial
                            serial+=1; msg={'id':serial,'method':method,'params':params or {}}
                            if session:msg['sessionId']=session
                            await ws.send_json(msg)
                            while True:
                                r=await asyncio.wait_for(ws.receive_json(),30)
                                if r.get('method')=='Runtime.exceptionThrown':exceptions.append('page_exception')
                                if r.get('id')==serial:
                                    assert 'error' not in r,'cdp_'+method
                                    return r.get('result',{})
                        async def page(url):
                            t=await call('Target.createTarget',{'url':url})
                            s=(await call('Target.attachToTarget',{'targetId':t['targetId'],'flatten':True}))['sessionId']
                            await call('Runtime.enable',{},s)
                            return s
                        async def evaluate(s,expression):
                            r=await call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True,'userGesture':True},s)
                            if 'exceptionDetails' in r:
                                # Test-only public fixture; still scrub URLs from error diagnostics.
                                import re
                                message=r['exceptionDetails'].get('exception',{}).get('description',r['exceptionDetails'].get('text',''))
                                print(json.dumps({'cdpFailure':re.sub(r'(?:https?|file|chrome-extension)://\S+','[url]',message.splitlines()[0])[:180]}),flush=True)
                                raise AssertionError('eval_failed')
                            return r.get('result',{}).get('value')
                        version=await call('Browser.getVersion')
                        sandbox=await page('chrome://sandbox')
                        for _ in range(50):
                            text=await evaluate(sandbox,'document.body?.innerText || ""')
                            if 'Seccomp' in text:break
                            await asyncio.sleep(.1)
                        assert 'Layer 1 Sandbox\tNamespace' in text and 'PID namespaces\tYes' in text and 'Network namespaces\tYes' in text, 'sandbox_not_active'
                        assert 'Seccomp-BPF sandbox\tYes' in text, 'seccomp_not_active'
                        loaded=await call('Extensions.loadUnpacked',{'path':str(artifact)})
                        assert loaded['id']==ID
                        s=await page('chrome-extension://'+ID+'/setup.html')
                        for _ in range(100):
                            state=await evaluate(s,"document.getElementById('connection')?.dataset.state")
                            if state in ('ready','missing'):break
                            await asyncio.sleep(.1)
                        assert state==('ready' if installed else 'missing'),state
                        downloads=await evaluate(s,"[...document.querySelectorAll('a[href]')].filter(a=>a.href.includes('/releases/download/')).map(a=>a.href)")
                        expected=[x['url'] for x in json.loads(original['releases.json'])['downloads']]
                        assert sorted(downloads)==sorted(expected),'catalog_links'
                        actual=await evaluate(s,'chrome.runtime.getManifest().version');assert actual=='0.2.8'
                        row={'browser':version['product'],'variant':'Google Chrome for Testing (official linux64 Stable), temporary unpacked bundle','extensionId':ID,'extensionVersion':actual,'connection':state,'exactExtractedCandidate':True,'sandbox':True,'downloads':downloads}
                        if installed:
                            native=await evaluate(s,"(async()=>{const {Native}=await import('./native.mjs');const n=new Native(()=>chrome.runtime.connectNative('com.pearplay.helper'));try{const h=await n.request('hello');return {ok:h.state==='idle',helperVersion:h.helperVersion,firewallSupport:h.firewallSupport,diagnostic:h.diagnostic,capabilities:h.capabilities}}finally{n.port?.disconnect()}})()")
                            assert native['ok'] and native['helperVersion']=='0.2.8'
                            assert native['diagnostic'] is None
                            assert 'firewall' not in native['capabilities']
                            row['hello']=native;row['repeatRepairRegistrationUnchanged']=True
                            await evaluate(s,"document.getElementById('find').click()")
                            for _ in range(300):
                                discovery=await evaluate(s,"({busy:document.getElementById('find').disabled,text:document.getElementById('receivers').textContent})")
                                if not discovery['busy']:break
                                await asyncio.sleep(.1)
                            assert not discovery['busy'] and 'Apple TV (' in discovery['text'],'real_discovery'
                            row['realDiscovery']=True
                            class Quiet(httpserver.SimpleHTTPRequestHandler):
                                def log_message(self,*a):pass
                            fixture=base/'fixture';fixture.mkdir()
                            public='https://media.w3.org/2010/05/bunny/trailer.mp4'
                            (fixture/'index.html').write_text('<!doctype html><title>Public sample</title><video preload="none" title="Public sample" src="'+public+'"></video>')
                            server=httpserver.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(fixture)))
                            threading.Thread(target=server.serve_forever,daemon=True).start()
                            page_url='http://127.0.0.1:'+str(server.server_port)+'/'
                            try:
                                ui=await page('chrome://extensions')
                                for _ in range(50):
                                    if await evaluate(ui,"typeof chrome.developerPrivate?.addHostPermission === 'function'"):break
                                    await asyncio.sleep(.1)
                                for origin in ('http://*/*','https://*/*'):
                                    assert await evaluate(ui,'chrome.developerPrivate.addHostPermission('+json.dumps(ID)+','+json.dumps(origin)+').then(()=>true)')
                                ps=await page(page_url)
                                for _ in range(50):
                                    if await evaluate(ps,"document.querySelector('video')?.currentSrc==="+json.dumps(public)):break
                                    await asyncio.sleep(.1)
                                assert await evaluate(ps,"document.querySelector('video')?.currentSrc==="+json.dumps(public))
                                await call('Page.bringToFront',{},ps)
                                tabs=(await call('Target.getTargets',{'filter':[{'type':'tab'}]}))['targetInfos']
                                tab=next(t for t in tabs if t['url']==page_url)
                                await call('Extensions.triggerAction',{'id':ID,'targetId':tab['targetId']})
                                for _ in range(50):
                                    targets=(await call('Target.getTargets'))['targetInfos']
                                    popup=next((t for t in targets if t['url']=='chrome-extension://'+ID+'/popup.html'),None)
                                    if popup:break
                                    await asyncio.sleep(.1)
                                assert popup,'actual_action_popup_missing'
                                pop=(await call('Target.attachToTarget',{'targetId':popup['targetId'],'flatten':True}))['sessionId']
                                await call('Runtime.enable',{},pop)
                                for _ in range(100):
                                    if await evaluate(pop,"document.readyState==='complete' && typeof chrome.permissions?.request==='function' && typeof document.getElementById('enable')?.onclick==='function'"):break
                                    await asyncio.sleep(.05)
                                assert await evaluate(pop,"chrome.permissions.request({origins:['http://*/*','https://*/*']})")
                                for _ in range(300):
                                    if await evaluate(pop,"!document.getElementById('enable').disabled"):break
                                    await asyncio.sleep(.1)
                                assert await evaluate(pop,"!document.getElementById('enable').disabled"),'find_videos_not_ready'
                                print(json.dumps(dict(check='active-tab',matches=await evaluate(pop,'chrome.tabs.query({active:true,currentWindow:true}).then(t=>t[0]?.url==='+json.dumps(page_url)+')'),bound=await evaluate(pop,"typeof document.getElementById('enable').onclick==='function'"))),flush=True)
                                await evaluate(pop,"document.getElementById('enable').click()")
                                for _ in range(200):
                                    view=await evaluate(pop,"chrome.tabs.query({url:"+json.dumps(page_url)+"}).then(t=>chrome.runtime.sendMessage({op:'view',tabId:t[0].id})).then(v=>({enabled:v.enabled,candidates:v.candidates,receivers:v.native.receivers,state:v.native.state,session:v.native.session}))")
                                    if view.get('candidates') and view.get('receivers'):break
                                    await asyncio.sleep(.1)
                                print(json.dumps(dict(check='DOM',enabled=view['enabled'],count=len(view['candidates']),dom=[bool(c.get('videoId')) for c in view['candidates']])),flush=True)
                                assert view['enabled'] and len(view['candidates'])==1 and view['candidates'][0].get('videoId'),'single_DOM_candidate'
                                assert view['state']=='idle' and view.get('session') is None,'never_sent'
                                row['singlePublicDomCandidate']=True
                                row['receiverCount']=len(view['receivers'])
                                row['noTimingReceiverCount']=sum(r.get('timingRequired') is False for r in view['receivers'])
                                for _ in range(60):
                                    layout=await evaluate(pop,"({width:document.body.scrollWidth,height:document.body.scrollHeight,sendBottom:document.getElementById('start').getBoundingClientRect().bottom,permissionHidden:document.getElementById('permissionBox').hidden})")
                                    if layout['permissionHidden']:break
                                    await asyncio.sleep(.1)
                                assert layout['permissionHidden'] and layout['width']<=400 and layout['height']<=600 and layout['sendBottom']<=600
                                row['actualPopupLayout']=layout
                                # From here only synthetic API responses, inside the same actual action target.
                                # No manifest/catalog/source rewrites and no receiver pairing or send.
                                await call('Page.enable',{},pop)
                                await call('Page.addScriptToEvaluateOnNewDocument',{'source':(ROOT/'tests/browser/brand-fixture.js').read_text()},pop)
                                states={
                                    'sent':"Object.assign(__fixture.view.native,{state:'connecting',evidence:'unverified',session:{receiver:'example-receiver',host:'192.0.2.10',transport:'airplay-v1',delivery:'accepted',timingRequired:false}})",
                                    'unsupported_access':"Object.assign(__fixture.view.native,{state:'error',error:'transport_failed',receiverIssue:'unsupported_access'})",
                                    'incomplete_advertisement':"Object.assign(__fixture.view.native,{state:'error',error:'transport_failed',receiverIssue:'incomplete_advertisement'})",
                                    'unsupported_protocol':"Object.assign(__fixture.view.native,{state:'error',error:'transport_failed',receiverIssue:'unsupported_protocol'})",
                                    'pin':"__fixture.view.native.error='pairing_required'",
                                    'reset':"Object.assign(__fixture.view.native,{state:'stopped',evidence:'unverified',session:null})",
                                }
                                rendered=[]
                                for name,setup in states.items():
                                    await evaluate(pop,"delete window.__fixture")
                                    await call('Page.reload',{},pop)
                                    for _ in range(80):
                                        if await evaluate(pop,"document.readyState==='complete' && !!window.__fixture?.calls.some(x=>x.op==='discover')"):break
                                        await asyncio.sleep(.05)
                                    await evaluate(pop,setup)
                                    await asyncio.sleep(2.2)
                                    metrics=await evaluate(pop,"({width:document.body.scrollWidth,height:document.body.scrollHeight,sendBottom:document.getElementById('start').getBoundingClientRect().bottom,phase:document.getElementById('phase').dataset.state,pinHidden:document.getElementById('pairBox').hidden,pinType:document.getElementById('pin').type,sendDisabled:document.getElementById('start').disabled,pinCalls:__fixture.calls.filter(x=>x.op==='pairBegin').length})")
                                    print(json.dumps(dict(check='synthetic-action-layout',state=name,**metrics)),flush=True)
                                    assert metrics['width']<=400 and metrics['height']<=600 and metrics['sendBottom']<=600,name+'_layout'
                                    if name=='sent':assert metrics['phase']=='sent' and metrics['sendDisabled'] and metrics['pinCalls']==0
                                    elif name=='pin':assert not metrics['pinHidden'] and metrics['pinType']=='password' and metrics['pinCalls']==1
                                    elif name=='reset':assert metrics['phase']=='idle'
                                    else:assert metrics['phase']=='error' and metrics['pinHidden'] and metrics['pinCalls']==0
                                    rendered.append(dict(state=name,**metrics))
                                row['syntheticActionPopupStates']=rendered
                                row['castAttempted']=False
                            finally:
                                server.shutdown();server.server_close()
                            assert register('remove')=='removed' and not host.exists()
                            missing=await evaluate(s,"new Promise(resolve=>{const p=chrome.runtime.connectNative('com.pearplay.helper');p.onDisconnect.addListener(()=>resolve({missing:!!chrome.runtime.lastError}));p.onMessage.addListener(()=>{p.disconnect();resolve({missing:false})});p.postMessage({v:1,id:'after_remove',op:'hello',args:{}})})")
                            assert missing['missing'];row['removedAndFreshPortMissing']=True
                        assert not exceptions
                        assert all((artifact/name).read_bytes()==data for name,data in original.items()),'artifact_mutated'
                        row.update(consoleExceptions=0,allExtractedEntriesUnchanged=True,pairingOrSend=False,firewallMutations=False)
                        print(json.dumps(row),flush=True)
                        await call('Browser.close')
            finally:
                if proc.poll() is None:proc.terminate()
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
                if host.exists():assert register('remove')=='removed'
        assert not host.exists()
        assert not list((base/'home').rglob('credentials.json'))
        assert not list((base/'state').rglob('credentials.json'))
        return row

async def main():
    rows=[await trial(False),await trial(True)]
    assert all(not p.exists() for p in TEMP_ROOTS)
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()==SHA
    result=dict(archiveSha256=SHA,results=rows,temporaryProfilesRemoved=True,
                scope='Exact production-policy candidate, real sandboxed Linux Google Chrome. Real hello/discovery/DOM/action-popup; labeled synthetic error/PIN/Sent layout. No pairing/send/firewall mutation or installed-helper changes. Not watched playback acceptance.')
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print('PASS exact candidate browser acceptance; evidence: '+str(args.output))

try:asyncio.run(main())
except Exception as error:
    import traceback
    print(json.dumps({'failed':type(error).__name__,'frames':[(f.name,f.lineno) for f in traceback.extract_tb(error.__traceback__)]}))
    raise SystemExit(1)