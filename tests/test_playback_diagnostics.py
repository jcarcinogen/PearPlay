import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from test_helper_protocol import load


class PlaybackDiagnostics(unittest.IsolatedAsyncioTestCase):
    async def test_playback_receiver_lookup_error_reaches_browser_without_raw_text(self):
        m = load()
        for message, expected in (('receiver_unavailable', 'receiver_unavailable'), ('private exception text', 'transport_failed')):
            async def run(*args): raise m.HelperError(message)
            events = []
            host = m.Host(lambda: SimpleNamespace(run=run), events.append)
            await host.playback({})
            self.assertEqual(events[-1]['error'], expected)
            self.assertNotIn('private exception text', json.dumps(events))

    async def test_playback_failure_reports_safe_stage_and_http_code(self):
        m=load(); command=m.spike()
        secret='https://example.test/video?token=PRIVATE pairing-PIN credentials'
        class Wire:
            def __init__(self,connection,credentials,timeout,report,stage):
                self.report=report; self.closed=False
            async def timing(self,port): self.timing_port=port
            async def request(self,stage,body=None,headers=None):
                self.report('stage',stage=stage)
                self.report('http-response',stage=stage,code=403)
                # Ignore unknown fields, raw strings, bool codes, and unknown stages.
                self.report('http-response',stage=stage,code=True,body=secret)
                self.report('stage',stage=secret)
                raise RuntimeError(secret)
            def close(self): self.closed=True
        device=SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF',address='127.0.0.1',get_service=lambda _:SimpleNamespace(port=7000))
        async def scan(*a,**k):return [device]
        async def connect(*a):return SimpleNamespace(close=lambda:None)
        with tempfile.TemporaryDirectory() as directory:
            store=command.existing().Store();store.root=Path(directory).resolve()/'state'
            store.save(dict(identifier=device.identifier,credentials='private-credential'))
            transport=m.Transport(api=SimpleNamespace(scan=scan,Protocol=SimpleNamespace(AirPlay=1)),command=command,store=store,connect=connect,parse=lambda x:x,backend=Wire)
            events=[]; host=m.Host(lambda:transport,events.append)
            await host.playback(dict(receiver=device.identifier,host='127.0.0.1',url=secret))
            result=events[-1]
            self.assertEqual(result['error'],'transport_failed')
            self.assertEqual(result.get('diagnostic'),dict(stage='authenticate',reason='rejected',httpStatus=403))
            self.assertNotIn('PRIVATE',json.dumps(result))
            self.assertNotIn('private-credential',json.dumps(result))
            self.assertTrue(transport.wire.closed)
            self.assertEqual(host.response('status').get('diagnostic'),result['diagnostic'])

    async def test_wait_for_playing_timeout_is_not_reported_as_disconnected(self):
        m=load(); command=m.spike()
        class Wire:
            def __init__(self,*a):self.closed=False
            async def timing(self,port):self.timing_port=port
            async def request(self,stage,body=None,headers=None):
                return {'eventPort':1234} if stage=='setup-base' else {'streams':[{'streamID':1}]} if stage=='setup-stream' else {}
            async def events(self,port,callback):pass
            def close(self):self.closed=True
        device=SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF',address='127.0.0.1',get_service=lambda _:SimpleNamespace(port=7000))
        async def scan(*a,**k):return [device]
        async def connect(*a):return SimpleNamespace(close=lambda:None)
        with tempfile.TemporaryDirectory() as directory:
            store=command.existing().Store();store.root=Path(directory).resolve()/'state'
            store.save(dict(identifier=device.identifier,credentials='test-only'))
            t=m.Transport(api=SimpleNamespace(scan=scan,Protocol=SimpleNamespace(AirPlay=1)),command=command,store=store,connect=connect,parse=lambda x:x,backend=Wire,timeout=.01)
            events=[];host=m.Host(lambda:t,events.append)
            await host.playback(dict(receiver=device.identifier,host='127.0.0.1',url='https://example.test/public.mp4'))
            self.assertEqual(events[-1].get('diagnostic'),dict(stage='await-playing',reason='timeout'))
            self.assertTrue(t.wire.closed)
            host.receivers=[dict(identifier=device.identifier,address='127.0.0.1')]
            result=await host.handle(dict(v=1,id='retry',op='start',args=dict(receiver=device.identifier,host='127.0.0.1',url='https://example.test/public.mp4')))
            self.assertNotIn('diagnostic',result)
            await host.close()


class PlaybackTraceIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_missing_credentials_and_failed_pairing_are_not_empty_traces(self):
        m = load()
        records = []
        def trace(kind, **fields):
            records.append(m.diagnostics().sanitize(kind, fields))
        async def unavailable(*args):
            raise m.HelperError('receiver_unavailable')
        with tempfile.TemporaryDirectory() as directory:
            store = m.spike().existing().Store()
            store.root = Path(directory).resolve()/'state'
            t = m.Transport(api=SimpleNamespace(), store=store, connect=lambda *a: None, parse=lambda x: x, trace=trace)
            with self.assertRaisesRegex(m.HelperError, 'pairing_required'):
                await t.run({'receiver': 'AA:BB:CC:DD:EE:FF', 'host': '127.0.0.1', 'url': 'https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8'}, lambda *a: None)
            self.assertIn({'k': 'input', 'media': 'hls', 'fixture': 'public-hls-master'}, records)
            self.assertIn({'k': 'outcome', 'outcome': 'pairing_required', 'stage': 'credentials'}, records)
            records.clear()
            t.resolve_receiver = unavailable
            with self.assertRaisesRegex(m.HelperError, 'receiver_unavailable'):
                await t.begin_pair('AA:BB:CC:DD:EE:FF', '127.0.0.1')
            self.assertIn({'k': 'pairing', 'phase': 'begin'}, records)
            self.assertIn({'k': 'outcome', 'outcome': 'receiver_unavailable', 'stage': 'receiver-scan'}, records)

    def make_transport(self, m, command, directory, *, trace=None, timeout=10, startup_timeout=None, connect=None, backend=None):
        device=SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF',address='127.0.0.1',get_service=lambda _:SimpleNamespace(port=7000))
        async def scan(*a,**k): return [device]
        if connect is None:
            async def default_connect(*a): return SimpleNamespace(close=lambda:None)
            connect = default_connect
        store=command.existing().Store(); store.root=Path(directory).resolve()/'state'
        store.save(dict(identifier=device.identifier,credentials='private-credential'))
        t=m.Transport(api=SimpleNamespace(scan=scan,Protocol=SimpleNamespace(AirPlay=1)),command=command,store=store,connect=connect,parse=lambda x:x,backend=backend,trace=trace,timeout=timeout,startup_timeout=startup_timeout)
        return t, device

    class PlayingWire:
        def __init__(self,*a): self.closed=False; self.callback=None
        async def timing(self,port): self.timing_port=port
        async def request(self,stage,body=None,headers=None):
            if stage=='setup-base': return {'eventPort':1234}
            if stage=='setup-stream': return {'streams':[{'streamID':1}]}
            if stage=='command':
                def fire():
                    self.callback({'type':'playbackState','name':'playing'})
                    self.callback({'type':'playbackState','name':'stopped'})
                asyncio.get_running_loop().call_later(0.02, fire)
            return {}
        async def events(self,port,callback): self.callback=callback
        def close(self): self.closed=True

    async def test_trace_records_are_sanitized_and_bounded(self):
        m=load(); command=m.spike()
        secret='https://example.test/private.mp4?token=PRIVATE-pairing-PIN'
        records=[]
        def trace(kind, **fields): records.append((kind, dict(fields)))
        with tempfile.TemporaryDirectory() as directory:
            t, device = self.make_transport(m, command, directory, trace=trace, backend=self.PlayingWire)
            await t.run(dict(receiver=device.identifier,host='127.0.0.1',url=secret), lambda *x:None)
        kinds=[k for k,_ in records]
        for expected in ('input','event','startup','outcome','close'):
            self.assertIn(expected, kinds)
        input_rec=next(f for k,f in records if k=='input')
        self.assertEqual(input_rec, {'media':'mp4','fixture':'other'})
        ev=next(f for k,f in records if k=='event')
        self.assertEqual(set(ev), {'type','state'})
        self.assertEqual(ev['state'],'playing')
        out=next(f for k,f in records if k=='outcome')
        self.assertEqual(out['outcome'],'stopped')
        blob=json.dumps(records)
        for leaked in ('private.mp4','PRIVATE','private-credential','127.0.0.1'):
            self.assertNotIn(leaked, blob)

    def test_event_channel_reports_are_traced(self):
        m=load(); command=m.spike()
        records=[]
        def trace(kind, **fields): records.append((kind, dict(fields)))
        t=m.Transport(api=SimpleNamespace(scan=lambda *a:[],Protocol=SimpleNamespace(AirPlay=1)),command=command,connect=lambda *a:None,parse=lambda c:c,trace=trace)
        t.playback_report('event-channel', status='parse-error')
        t.playback_report('event-channel', status='decoded')
        t.playback_report('event-channel', status='arbitrary')
        self.assertEqual(records, [('channel', {'status':'parse-error'}), ('channel', {'status':'decoded'})])

    async def test_startup_override_extends_only_the_playing_wait(self):
        m=load(); command=m.spike()
        async def run_with(startup):
            with tempfile.TemporaryDirectory() as directory:
                t, device = self.make_transport(m, command, directory, timeout=0.01, startup_timeout=startup, backend=self.PlayingWire)
                notices=[]
                try:
                    await t.run(dict(receiver=device.identifier,host='127.0.0.1',url='https://example.test/a.mp4'), lambda *x:notices.append(x))
                    return ('ok', notices)
                except m.PlaybackError as error:
                    return ('error', error.diagnostic)
        self.assertEqual((await run_with(0.2))[0], 'ok')
        result = await run_with(None)
        self.assertEqual(result[0], 'error')
        self.assertEqual(result[1], {'stage':'await-playing','reason':'timeout'})

    async def test_startup_override_does_not_extend_connect(self):
        m=load(); command=m.spike()
        async def slow_connect(*a):
            await asyncio.sleep(0.1); return SimpleNamespace(close=lambda:None)
        with tempfile.TemporaryDirectory() as directory:
            t, device = self.make_transport(m, command, directory, timeout=0.01, startup_timeout=30, connect=slow_connect)
            with self.assertRaises(m.PlaybackError) as ctx:
                await t.run(dict(receiver=device.identifier,host='127.0.0.1',url='https://example.test/a.mp4'), lambda *x:None)
            self.assertEqual(ctx.exception.diagnostic, {'stage':'connect','reason':'timeout'})


class EventLabelInstrumentation(unittest.IsolatedAsyncioTestCase):
    def make_transport(self, m, command, directory, *, event_labels=None, backend=None):
        device=SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF',address='127.0.0.1',get_service=lambda _:SimpleNamespace(port=7000))
        async def scan(*a,**k): return [device]
        async def connect(*a): return SimpleNamespace(close=lambda:None)
        store=command.existing().Store(); store.root=Path(directory).resolve()/'state'
        store.save(dict(identifier=device.identifier,credentials='private-credential'))
        t=m.Transport(api=SimpleNamespace(scan=scan,Protocol=SimpleNamespace(AirPlay=1)),command=command,store=store,connect=connect,parse=lambda x:x,backend=backend,event_labels=event_labels)
        return t, device

    class PlayingWire:
        def __init__(self,*a): self.closed=False; self.callback=None
        async def timing(self,port): self.timing_port=port
        async def request(self,stage,body=None,headers=None):
            if stage=='setup-base': return {'eventPort':1234}
            if stage=='setup-stream': return {'streams':[{'streamID':1}]}
            if stage=='command':
                def fire():
                    self.callback({'type':'playbackState','name':'playing'})
                    self.callback({'type':'playbackState','name':'stopped'})
                asyncio.get_running_loop().call_later(0.02, fire)
            return {}
        async def events(self,port,callback): self.callback=callback
        def close(self): self.closed=True

    class UnknownTypeWire(PlayingWire):
        async def request(self,stage,body=None,headers=None):
            if stage=='command':
                def fire():
                    self.callback({'type':'playbackState','name':'playing'})
                    self.callback({'type':'mediaItemChanged','name':'playing'})
                    self.callback({'type':'playbackState','name':'stopped'})
                asyncio.get_running_loop().call_later(0.02, fire)
                return {}
            return await super().request(stage,body,headers)

    async def test_failing_collector_does_not_alter_event_delivery(self):
        m=load(); command=m.spike()
        class Boom:
            def __call__(self, data):
                raise OSError('SECRET')
        with tempfile.TemporaryDirectory() as directory:
            t, device = self.make_transport(m, command, directory, event_labels=Boom(), backend=self.PlayingWire)
            notices=[]
            await t.run(dict(receiver=device.identifier,host='127.0.0.1',url='https://example.test/a.mp4'), lambda *x:notices.append(x))
            self.assertIn(('playing','protocol'), notices)

    async def test_collector_writes_only_unknown_labels_end_to_end(self):
        m=load(); command=m.spike()
        diag=load('diagnostics')
        with tempfile.TemporaryDirectory() as directory:
            labels_path=Path(directory)/'labels.jsonl'; labels_path.write_text(''); labels_path.chmod(0o600)
            collector=diag.EventLabelCollector(str(labels_path))
            t, device = self.make_transport(m, command, directory, event_labels=collector, backend=self.UnknownTypeWire)
            await t.run(dict(receiver=device.identifier,host='127.0.0.1',url='https://example.test/a.mp4'), lambda *x:None)
            rows=[json.loads(l) for l in labels_path.read_text().splitlines() if l]
            self.assertEqual(rows, [{'eventType':'mediaItemChanged'}])


class EventMetadataInstrumentation(unittest.IsolatedAsyncioTestCase):
    def make_transport(self, m, command, directory, *, event_metadata=None, backend=None):
        device=SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF',address='127.0.0.1',get_service=lambda _:SimpleNamespace(port=7000))
        async def scan(*a,**k): return [device]
        async def connect(*a): return SimpleNamespace(close=lambda:None)
        store=command.existing().Store(); store.root=Path(directory).resolve()/'state'
        store.save(dict(identifier=device.identifier,credentials='private-credential'))
        t=m.Transport(api=SimpleNamespace(scan=scan,Protocol=SimpleNamespace(AirPlay=1)),command=command,store=store,connect=connect,parse=lambda x:x,backend=backend,event_metadata=event_metadata)
        return t, device

    class NotificationWire:
        def __init__(self,*a): self.closed=False; self.callback=None; self.fired=False
        async def timing(self,port): self.timing_port=port
        async def request(self,stage,body=None,headers=None):
            if stage=='setup-base': return {'eventPort':1234}
            if stage=='setup-stream': return {'streams':[{'streamID':1}]}
            if stage=='command':
                def fire():
                    if self.fired: return
                    self.fired=True
                    self.callback({'type':'playbackState','name':'playing'})
                    self.callback({'type':'notification','name':'playing','kind':'media'})
                    self.callback({'type':'playbackState','name':'stopped'})
                asyncio.get_running_loop().call_later(0.02, fire)
            return {}
        async def events(self,port,callback): self.callback=callback
        def close(self): self.closed=True

    async def test_collector_writes_only_notification_metadata_end_to_end(self):
        m=load(); command=m.spike(); diag=load('diagnostics')
        with tempfile.TemporaryDirectory() as directory:
            meta_path=Path(directory)/'meta.jsonl'; meta_path.write_text(''); meta_path.chmod(0o600)
            collector=diag.EventMetadataCollector(str(meta_path))
            t, device = self.make_transport(m, command, directory, event_metadata=collector, backend=self.NotificationWire)
            await t.run(dict(receiver=device.identifier,host='127.0.0.1',url='https://example.test/a.mp4'), lambda *x:None)
            rows=[json.loads(l) for l in meta_path.read_text().splitlines() if l]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['name'], 'playing')
            self.assertEqual(rows[0]['kind'], 'media')

    async def test_failing_metadata_collector_does_not_alter_event_delivery(self):
        m=load(); command=m.spike()
        class Boom:
            def __call__(self, data): raise OSError('SECRET')
        with tempfile.TemporaryDirectory() as directory:
            t, device = self.make_transport(m, command, directory, event_metadata=Boom(), backend=self.NotificationWire)
            notices=[]
            await t.run(dict(receiver=device.identifier,host='127.0.0.1',url='https://example.test/a.mp4'), lambda *x:notices.append(x))
            self.assertIn(('playing','protocol'), notices)
