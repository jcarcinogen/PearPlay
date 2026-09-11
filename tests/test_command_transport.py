import asyncio
import importlib.util
from pathlib import Path
import plistlib
from types import SimpleNamespace

PATH = Path(__file__).resolve().parents[1] / 'spikes/002-command/command.py'

def module():
    assert PATH.exists(), 'experimental adapter missing'
    spec = importlib.util.spec_from_file_location('command_spike', PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_cli_fixed_port_validation_and_sanitized_failures():
    mod = module()
    assert hasattr(mod, 'main'), 'CLI missing'
    import io
    out = io.StringIO()
    assert mod.main(['--host', 'secret?token=SECRET', '--sample', 'mp4'], output=out) == 2
    assert 'SECRET' not in out.getvalue()
    import io as _io
    from unittest.mock import patch
    stdin = _io.StringIO('https://EXAMPLE.com:443/a%2fb.m3u8?X=A%2Bz&x=2#frag\n')
    with patch('sys.stdin', stdin):
        args = mod.arguments(['--host', '127.0.0.1', '--stdin', '--mode', 'command', '--timing-port', '49170'])
    assert args.stdin and args.sample is None
    args = mod.arguments(['--host', '127.0.0.1', '--sample', 'hls', '--mode', 'baseline-v2', '--timing-port', '49170'])
    assert args.timing_port == 49170 and args.mode == 'baseline-v2'
    import pytest
    for extra in [['--timeout', 'nan'], ['--timing-port', '0'], ['--duration', 'inf']]:
        with pytest.raises(ValueError):
            mod.arguments(['--host', '127.0.0.1', '--sample', 'mp4'] + extra)


def test_real_backend_fixed_udp_bind_cleanup_and_version_guard(monkeypatch):
    mod = module()
    assert hasattr(mod, 'Backend'), 'private API backend missing'
    import pytest
    pytest.importorskip('pyatv')
    from importlib import metadata
    monkeypatch.setattr(metadata, 'version', lambda name: '0.19.0')
    with pytest.raises(RuntimeError):
        mod.guard()
    monkeypatch.setattr(metadata, 'version', lambda name: '0.18.0')
    mod.guard()
    async def check():
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        connection = SimpleNamespace(local_ip='127.0.0.1', close=lambda: None)
        wire = mod.Backend(connection, None, .1, lambda *a, **k: None, ['test'])
        await wire.timing(port)
        assert wire.timing_port == port
        wire.close()
        await asyncio.sleep(.001)
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.bind(('127.0.0.1', port))
        probe.close()
    asyncio.run(check())


def test_baseline_v2_uses_existing_port_and_cleans_feedback(monkeypatch):
    mod = module()
    assert hasattr(mod.Backend, 'baseline'), 'baseline missing'
    import pyatv.protocols.raop.protocols.airplayv2 as upstream
    async def check():
        calls = []
        class V2:
            def __init__(self, context, rtsp):
                self._feedback_task = None
            async def play_url(self, port, url):
                calls.append((port, url))
                self._feedback_task = asyncio.create_task(asyncio.sleep(100))
                return SimpleNamespace(code=200)
            def teardown(self):
                self._feedback_task.cancel()
        monkeypatch.setattr(upstream, 'AirPlayV2', V2)
        connection = SimpleNamespace(close=lambda: None)
        wire = mod.Backend(connection, None, .02, lambda *a, **k: None, ['test'])
        wire.timing_port = 49170
        await wire.baseline('https://example.org/a', .005)
        assert calls == [(49170, 'https://example.org/a')]
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    asyncio.run(check())


def test_trial_loads_existing_store_selects_saved_receiver_and_closes(monkeypatch):
    mod = module()
    assert hasattr(mod, 'trial'), 'trial runner missing'
    import pyatv
    import pyatv.support.http as http
    import pyatv.auth.hap_pairing as pairing
    async def check():
        saved = {'identifier': 'saved', 'credentials': 'not-real'}
        monkeypatch.setattr(mod, 'existing', lambda: SimpleNamespace(Store=lambda: SimpleNamespace(load=lambda: saved), SAMPLES={'mp4': 'https://example.org/a'}, read_url=lambda source: source.readline()[:-1]))
        async def scan(*a, **kw):
            assert kw['hosts'] == ['127.0.0.1']
            return [SimpleNamespace(identifier='saved', get_service=lambda p: SimpleNamespace(port=7000))]
        monkeypatch.setattr(pyatv, 'scan', scan)
        monkeypatch.setattr(pairing, 'parse_credentials', lambda value: value)
        closed = []
        async def connect(*a, **kw):
            return SimpleNamespace(local_ip='127.0.0.1', close=lambda: closed.append(True))
        monkeypatch.setattr(http, 'http_connect', connect)
        async def timing(self, port):
            self.timing_port = port
        async def baseline(self, url, hold):
            assert self.credentials == 'not-real' and self.timing_port == 49170
        monkeypatch.setattr(mod.Backend, 'timing', timing)
        monkeypatch.setattr(mod.Backend, 'baseline', baseline)
        args = mod.arguments(['--host', '127.0.0.1', '--sample', 'mp4', '--mode', 'baseline-v2'])
        assert await mod.trial(args, lambda *a, **k: None, ['test']) == 0
        assert closed
        import io as _io
        from unittest.mock import patch
        captured = []
        async def command_run(self, timing_port, url, duration):
            captured.append(url)
        monkeypatch.setattr(mod, 'Session', lambda wire, timeout: SimpleNamespace(run=lambda *a, **k: command_run(None, *a, **k)))
        url = 'https://EXAMPLE.com:443/a%2fb.m3u8?X=A%2Bz&x=2#frag'
        with patch('sys.stdin', _io.StringIO(url + '\n')):
            args = mod.arguments(['--host', '127.0.0.1', '--stdin', '--mode', 'command'])
            assert await mod.trial(args, lambda *a, **k: None, ['test']) == 0
        assert captured == [url]
    asyncio.run(check())


def test_backend_authentication_and_http_errors_are_not_success(monkeypatch):
    mod = module()
    assert hasattr(mod.Backend, 'request'), 'wire dispatch missing'
    import pyatv.protocols.airplay.auth as auth
    import pytest
    async def check():
        verified = []
        async def verify(credentials, connection):
            verified.append(credentials)
            return 'verifier'
        monkeypatch.setattr(auth, 'verify_connection', verify)
        class Connection:
            async def post(self, *a, **kw):
                return SimpleNamespace(code=500, body=b'SECRET')
        wire = mod.Backend(Connection(), 'credential', .01, lambda *a, **k: None, ['test'])
        await wire.request('authenticate')
        assert verified == ['credential'] and wire.verifier == 'verifier'
        with pytest.raises(RuntimeError):
            await wire.request('command', b'payload', {})
    asyncio.run(check())


def test_event_decoder_acknowledges_valid_and_rejects_oversized():
    mod = module()
    assert hasattr(mod, 'event_factory'), 'event channel missing'
    channel_type = mod.event_factory(lambda x: received.append(x))
    from pyatv.support.http import HttpRequest
    received = []
    channel = channel_type(bytes(32), bytes(32))
    sent = []
    channel.send = sent.append
    data = {'type': 'playbackState', 'name': 'playing'}
    request = HttpRequest('POST', '/event', 'HTTP', '1.1', {'CSeq': '3'}, plistlib.dumps({'params': {'data': plistlib.dumps(data)}}))
    channel.buffer = channel.format_request(request)
    channel.handle_received()
    assert received == [data] and b'200 OK' in sent[0]
    channel.buffer = b'x' * (1024 * 1024 + 1)
    channel.handle_received()
    assert channel.buffer == b''


def test_event_connection_retains_upstream_encryption_and_bounds(monkeypatch):
    mod = module()
    assert hasattr(mod.Backend, 'events'), 'event connect missing'
    import pyatv.auth.hap_channel as hap
    import pytest
    async def check():
        calls = []
        async def setup(*args):
            calls.append(args)
            return SimpleNamespace(close=lambda: None), None
        monkeypatch.setattr(hap, 'setup_channel', setup)
        wire = mod.Backend(SimpleNamespace(remote_ip='127.0.0.1'), None, .01, lambda *a, **k: None, ['test'])
        wire.verifier = 'verified'
        await wire.events(12345, lambda x: None)
        assert calls[0][1:] == ('verified', '127.0.0.1', 12345, 'Events-Salt', 'Events-Read-Encryption-Key', 'Events-Write-Encryption-Key')
        with pytest.raises(ValueError):
            await wire.events(0, lambda x: None)
    asyncio.run(check())


def test_receiver_stream_id_cannot_inject_headers():
    mod = module()
    import pytest
    async def check():
        class Bad(Wire):
            async def request(self, stage, body=None, headers=None):
                if stage == 'setup-stream':
                    return {'streams': [{'streamID': '19\r\nSECRET: leak'}]}
                return await super().request(stage, body, headers)
        wire = Bad()
        with pytest.raises(ValueError):
            await mod.Session(wire).start(1234, 'https://example.org/a')
        assert not any(c[0] == 'command' for c in wire.calls)
    asyncio.run(check())


def test_cli_suppresses_upstream_prints_logs_and_exception_secrets(monkeypatch):
    mod = module()
    import io
    import logging
    out = io.StringIO()
    async def unsafe(*args):
        print('SECRET')
        logging.critical('SECRET')
        raise RuntimeError('SECRET')
    monkeypatch.setattr(mod, 'trial', unsafe)
    assert mod.main(['--host', '127.0.0.1', '--sample', 'mp4'], output=out) == 1
    assert 'SECRET' not in out.getvalue()


class Wire:
    def __init__(self):
        self.calls = []
        self.closed = False
    async def request(self, stage, body=None, headers=None):
        self.calls.append((stage, body, headers))
        if stage == 'setup-base':
            return {'eventPort': 12345}
        if stage == 'setup-stream':
            return {'streams': [{'streamID': 19}]}
        return {}
    async def events(self, port, callback):
        self.callback = callback
    def close(self):
        self.closed = True


def test_command_path_authenticates_before_setup_uses_type130_and_unique_ids():
    mod = module()
    async def check():
        wire = Wire()
        session = mod.Session(wire, timeout=.1)
        await session.start(1234, 'https://example.org/video.mp4')
        stages = [c[0] for c in wire.calls]
        assert stages == ['authenticate', 'setup-base', 'info', 'record', 'setup-stream', 'command', 'command', 'command', 'command']
        base = wire.calls[1][1]
        stream = wire.calls[4][1]['streams'][0]
        assert stream['type'] == 130
        assert base['sessionUUID'] == session.headers['X-Apple-Session-ID']
        assert session.headers['X-Apple-StreamID'] == '19'
        commands = [plistlib.loads(plistlib.loads(c[1])['params']['data']) for c in wire.calls if c[0] == 'command']
        assert [c['type'] for c in commands] == ['insertPlayQueueItem', 'setProperty', 'setProperty', 'setRate']
        assert commands[0]['item']['Content-Location'] == 'https://example.org/video.mp4'
        other = mod.Session(Wire(), timeout=.1)
        assert other.headers['X-Apple-Session-ID'] != session.headers['X-Apple-Session-ID']
        assert other.item_id != session.item_id
    asyncio.run(check())


def test_events_require_playing_then_stopped_and_bound_missing_start():
    mod = module()
    assert hasattr(mod.Session, 'on_event'), 'event state tracking missing'
    async def check():
        import pytest
        class Playing(Wire):
            async def request(self, stage, body=None, headers=None):
                result = await super().request(stage, body, headers)
                if stage == 'command':
                    self.callback({'type': 'playbackState', 'name': 'playing'})
                    self.callback({'type': 'playbackState', 'params': {'playbackState': 'stopped'}})
                return result
        wire = Playing()
        session = mod.Session(wire, timeout=.02)
        await session.run(1234, 'https://example.org/a', .1)
        assert session.started and wire.closed
        silent = Wire()
        with pytest.raises(TimeoutError):
            await mod.Session(silent, timeout=.01).run(1234, 'https://example.org/a', .05)
        assert silent.closed
    asyncio.run(check())


def test_timeout_and_cancel_close_transport_without_pending_tasks():
    mod = module()
    assert hasattr(mod.Session, 'run'), 'bounded lifetime missing'
    async def check():
        class Hung(Wire):
            async def request(self, *args):
                await asyncio.Event().wait()
        wire = Hung()
        session = mod.Session(wire, timeout=.01)
        import pytest
        with pytest.raises(TimeoutError):
            await session.run(1234, 'https://example.org/video.mp4', .03)
        assert wire.closed
        wire2 = Hung()
        task = asyncio.create_task(mod.Session(wire2).run(1234, 'https://example.org/video.mp4', 1))
        await asyncio.sleep(.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert wire2.closed
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    asyncio.run(check())
