"""First-Find exact-ZIP test for hosts without Node (existing aiohttp required).
Real browser/popup/worker/content; synthetic TVs only, no native/receiver actions.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import aiohttp

parser = argparse.ArgumentParser()
parser.add_argument('--browser', required=True)
parser.add_argument('--zip', type=Path, required=True)
parser.add_argument('--sha256', required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--live', action='store_true')
args = parser.parse_args()
assert hashlib.sha256(args.zip.read_bytes()).hexdigest() == args.sha256
args.output.mkdir(parents=True, exist_ok=False)
counts = {'manifest': 0}

class Fixture(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == '/index.m3u8':
            counts['manifest'] += 1
            kind, body = 'application/vnd.apple.mpegurl', '#EXTM3U\n'
        else:
            kind = 'text/html'
            body = '''<!doctype html><title>First Find fixture</title><video controls></video>
<script>(async()=>{await(await fetch('/index.m3u8')).text();const v=document.querySelector('video');v.src=URL.createObjectURL(new MediaSource());v.load();})()</script>'''
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.end_headers()
        self.wfile.write(body.encode())

server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
threading.Thread(target=server.serve_forever, daemon=True).start()
url = 'https://www.fox13seattle.com/live' if args.live else f'http://127.0.0.1:{server.server_port}/'
report = {'scope': 'Real isolated browser and unchanged ZIP, synthetic TVs only; no helper/TV playback. Windows SSH Session 0, not owner desktop acceptance.', 'live': args.live, 'exactArtifact': True, 'zipSHA256': args.sha256, 'passed': False, 'checks': []}

async def main():
    with tempfile.TemporaryDirectory(prefix='browser-', dir=args.output) as temp:
        root = Path(temp)
        artifact, profile = root / 'extension', root / 'profile'
        with zipfile.ZipFile(args.zip) as archive:
            for name in archive.namelist():
                assert not name.startswith(('/', '\\')) and '..' not in Path(name).parts
            archive.extractall(artifact)
            assert all((artifact / n).read_bytes() == archive.read(n) for n in archive.namelist())
        original = {str(p.relative_to(artifact)): hashlib.sha256(p.read_bytes()).hexdigest() for p in artifact.rglob('*') if p.is_file()}
        with (args.output / 'browser.log').open('wb') as log:
            proc = subprocess.Popen([args.browser, '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-component-update', '--disable-sync', '--enable-unsafe-extension-debugging', '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0', '--user-data-dir=' + str(profile), 'about:blank'], stdout=log, stderr=log)
            try:
                for _ in range(150):
                    if (profile / 'DevToolsActivePort').exists():
                        break
                    if proc.poll() is not None:
                        raise RuntimeError('owned_browser_exited')
                    await asyncio.sleep(.1)
                port, path = (profile / 'DevToolsActivePort').read_text().splitlines()[:2]
                async with aiohttp.ClientSession() as http, http.ws_connect('http://127.0.0.1:' + port + path) as ws:
                    serial = 0
                    async def call(method, params=None, session=None):
                        nonlocal serial
                        serial += 1
                        payload = {'id': serial, 'method': method, 'params': params or {}}
                        if session:
                            payload['sessionId'] = session
                        await ws.send_json(payload)
                        while True:
                            reply = await asyncio.wait_for(ws.receive_json(), 35)
                            if reply.get('id') == serial:
                                if 'error' in reply:
                                    raise RuntimeError('cdp_' + method)
                                return reply.get('result', {})

                    async def attach(target):
                        return (await call('Target.attachToTarget', {'targetId': target, 'flatten': True}))['sessionId']

                    async def evaluate(session, expression):
                        reply = await call('Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'awaitPromise': True, 'userGesture': True}, session)
                        if 'exceptionDetails' in reply:
                            raise RuntimeError('page_evaluation_failed')
                        return reply.get('result', {}).get('value')

                    async def wait(session, expression, label):
                        for _ in range(300):
                            if await evaluate(session, expression):
                                return
                            await asyncio.sleep(.1)
                        raise RuntimeError('timeout_' + label)

                    report['browser'] = (await call('Browser.getVersion'))['product']
                    page = await call('Target.createTarget', {'url': url})
                    ps = await attach(page['targetId'])
                    await call('Page.enable', session=ps)
                    await wait(ps, "document.querySelector('video')?.currentSrc.startsWith('blob:') && performance.getEntriesByType('resource').some(e=>/\\.m3u8(?:[?#]|$)/i.test(e.name))", 'preexisting_HLS')
                    before = await evaluate(ps, 'performance.timeOrigin')
                    report['brave'] = await evaluate(ps, 'navigator.brave?.isBrave().catch(()=>false) ?? false')
                    report['checks'].append('pre-Find blob and historical HLS')
                    ext = (await call('Extensions.loadUnpacked', {'path': str(artifact)}))['id']
                    ui = await call('Target.createTarget', {'url': 'chrome://extensions'})
                    us = await attach(ui['targetId'])
                    await wait(us, '!!chrome.developerPrivate', 'permission_API')
                    for host in ['http://*/*', 'https://*/*']:
                        await evaluate(us, f'chrome.developerPrivate.addHostPermission({json.dumps(ext)},{json.dumps(host)}).then(()=>true)')
                    await asyncio.sleep(.5)
                    for target in (await call('Target.getTargets'))['targetInfos']:
                        if target['type'] == 'page' and target['url'].startswith('chrome-extension://'):
                            await call('Target.closeTarget', {'targetId': target['targetId']})
                    await call('Page.bringToFront', session=ps)
                    tabs = (await call('Target.getTargets', {'filter': [{'type': 'tab'}]}))['targetInfos']
                    tab = next(t for t in tabs if t['url'] == url)
                    await call('Extensions.triggerAction', {'id': ext, 'targetId': tab['targetId']})
                    popup = None
                    for _ in range(100):
                        popup = next((t for t in (await call('Target.getTargets'))['targetInfos'] if t['url'] == f'chrome-extension://{ext}/popup.html'), None)
                        if popup:
                            break
                        await asyncio.sleep(.1)
                    assert popup
                    s = await attach(popup['targetId'])
                    await wait(s, '!!document.getElementById("enable")?.onclick', 'popup')
                    assert await evaluate(s, "chrome.permissions.request({origins:['http://*/*','https://*/*']})")
                    await evaluate(s, """(()=>{const original=chrome.runtime.sendMessage.bind(chrome.runtime);let receivers=[],receiver=null;chrome.runtime.sendMessage=async m=>{
if(m.op==='discover'){receivers=[{identifier:'fixture-tv',label:'Fixture Apple TV',address:'192.168.1.90'},{identifier:'other',label:'Other fixture TV',address:'192.168.1.91'}];return {receivers};}
if(m.op==='receiver'){receiver=m.id;return {ok:true};}
if(['start','hello','status','pair','pairBegin'].includes(m.op))throw Error('Native operation forbidden');
const result=await original(m);if(m.op==='view'){result.native={state:'idle',error:null,evidence:'none',capabilities:['start','stop'],receivers};result.receiver=receiver;}return result;};})()""")
                    await wait(s, '!document.getElementById("enable").disabled', 'Find_enabled')
                    await asyncio.sleep(.3)
                    await evaluate(s, 'document.getElementById("enable").onclick()')
                    await wait(s, '!!document.getElementById("candidate").value', 'selection')
                    state = await evaluate(s, "(async()=>{const[t]=await chrome.tabs.query({active:true,currentWindow:true});return chrome.runtime.sendMessage({op:'view',tabId:t.id});})()")
                    assert next(c for c in state['candidates'] if c['id'] == state['selected'])['sendable'] is True, 'initial_selection_not_sendable'
                    blob = next(c for c in state['candidates'] if c['sendable'] is False)
                    await evaluate(s, 'document.getElementById("discover").onclick()')
                    await evaluate(s, "(()=>{const e=document.getElementById('receiver');e.value='fixture-tv';return e.onchange();})()")
                    await wait(s, '!document.getElementById("start").disabled', 'Send_enabled')
                    assert await evaluate(ps, 'performance.timeOrigin') == before
                    if not args.live:
                        assert counts['manifest'] == 1
                    report['checks'].append('Find videos -> Find TVs -> select TV enables Send without reload')
                    report['candidates'] = state['candidates']
                    await evaluate(s, f"(()=>{{const e=document.getElementById('candidate');e.value={json.dumps(blob['id'])};return e.onchange();}})()")
                    await evaluate(s, 'document.getElementById("enable").onclick()')
                    await asyncio.sleep(1.5)
                    assert await evaluate(s, 'document.getElementById("candidate").value') == blob['id']
                    assert await evaluate(s, 'document.getElementById("start").disabled') is True
                    report['checks'].append('repeat Find preserves deliberate blob choice and disabled Send')
                    assert all(hashlib.sha256((artifact / n).read_bytes()).hexdigest() == h for n, h in original.items())
                    report['passed'] = True
                    await call('Browser.close')
            finally:
                if proc.poll() is None:
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.terminate()
                        proc.wait(timeout=10)

try:
    asyncio.run(main())
finally:
    server.shutdown()
    server.server_close()
    (args.output / 'first-find-results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
