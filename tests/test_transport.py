import asyncio
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / 'spikes/001-airplay/pearplay.py'
if SOURCE.exists():
    spec = importlib.util.spec_from_file_location('pearplay', SOURCE)
    pp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pp)
else:
    pp = SimpleNamespace()

class InputTests(unittest.TestCase):
    def test_default_mp4_uses_reachable_h264_aac_sample(self):
        self.assertEqual(pp.SAMPLES['mp4'], 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4')

    def test_url_message_preserves_signed_url_exactly(self):
        self.assertTrue(hasattr(pp, 'read_url'), 'URL input feature missing')
        url = 'https://EXAMPLE.com:443/a%2fb.mp4?X=A%2Bz&x=2#frag'
        self.assertEqual(pp.read_url(io.StringIO(url + '\n')), url)
        for bad in ('', 'file:///tmp/x', 'ftp://a/x', 'https://u:p@host/x',
                    ' https://host/x', 'https://host/x ', 'https://host/\tx',
                    'https://', 'https://host:bad/x', 'https://host/\\x'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                pp.read_url(io.StringIO(bad + '\n'))

class StoreTests(unittest.TestCase):
    def test_uninstall_removes_only_owned_state_files(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home).resolve()):
            store = pp.Store()
            store.save({'identifier': 'AA:BB:CC:DD:EE:FF', 'credentials': 'SECRET'})
            extra = store.root / 'user-note'
            extra.write_text('keep')
            self.assertEqual(pp.uninstall_state(), {'event': 'uninstalled', 'preserved': ['user-note']})
            self.assertFalse((store.root / 'credentials.json').exists())
            self.assertFalse((store.root / 'control.sock').exists())
            self.assertTrue(extra.exists())
            extra.unlink()
            self.assertEqual(pp.uninstall_state(), {'event': 'uninstalled', 'preserved': []})
            self.assertFalse(store.root.exists())

    def test_state_inside_source_tree_is_rejected(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home).resolve()), patch.object(pp, '__file__', str(Path(home).resolve() / 'spikes/001-airplay/pearplay.py')):
            with self.assertRaises(ValueError):
                pp.Store().save({'identifier': 'receiver', 'credentials': 'SECRET'})
            self.assertFalse((Path(home) / '.local').exists())

    def test_failed_atomic_replace_keeps_previous_credentials(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home).resolve()):
            store = pp.Store()
            value = {'identifier': 'AA:BB:CC:DD:EE:FF', 'credentials': 'OLD'}
            store.save(value)
            with patch.object(os, 'replace', side_effect=OSError('SECRET')):
                with self.assertRaises(OSError):
                    store.save({**value, 'credentials': 'NEW'})
            self.assertEqual(store.load(), value)
            self.assertEqual([p.name for p in store.root.iterdir()], ['credentials.json'])

    def test_atomic_private_credentials_and_reject_unsafe_paths(self):
        self.assertTrue(hasattr(pp, 'Store'), 'credential store missing')
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home).resolve()):
            store = pp.Store()
            value = {'identifier': 'receiver', 'credentials': 'SECRET'}
            store.save(value)
            self.assertEqual(store.load(), value)
            self.assertEqual(stat.S_IMODE(store.root.stat().st_mode), 0o700)
            file = store.root / 'credentials.json'
            self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600)
            store.save({'identifier': 'receiver', 'credentials': 'NEXT'})
            self.assertEqual(store.load()['credentials'], 'NEXT')
            self.assertEqual(sorted(p.name for p in store.root.iterdir()), ['credentials.json'])
            file.chmod(0o644)
            with self.assertRaises(ValueError): store.load()
            with self.assertRaises(ValueError): store.save(value)
            file.unlink()
            file.symlink_to(Path(home) / 'victim')
            with self.assertRaises((ValueError, OSError)): store.save(value)
            file.unlink()
            store.root.chmod(0o755)
            with self.assertRaises(ValueError): store.load()
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home).resolve()):
            (Path(home) / '.local').symlink_to('/tmp', target_is_directory=True)
            with self.assertRaises((ValueError, OSError)): pp.Store().save(value)

class FakeAPI:
    Protocol = SimpleNamespace(AirPlay='airplay')
    def __init__(self):
        self.events = []
        self.service = SimpleNamespace(pairing=SimpleNamespace(name='Mandatory'), credentials=None)
        self.device = SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF', address='192.0.2.4',
                                      get_service=lambda p: self.service,
                                      set_credentials=self.set_credentials)
        self.devices = [self.device]
    async def prepare_connect(self, device):
        return {'protocol': self.Protocol.AirPlay, 'storage': 'memory'}
    def set_credentials(self, protocol, credentials):
        self.events.append(('credentials', credentials))
        return True
    async def scan(self, loop, **kw):
        self.events.append('scan')
        return self.devices
    async def pair(self, config, protocol, loop):
        api = self
        class Pair:
            service = api.service
            device_provides_pin = True
            has_paired = False
            async def begin(self): api.events.append('begin')
            def pin(self, value): api.events.append(('pin', value))
            async def finish(self):
                self.has_paired = True
                self.service.credentials = 'SECRET'
            async def close(self): api.events.append('pair-close')
        return Pair()

class PairTests(unittest.TestCase):
    def test_pair_failure_closes_without_saving(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home).resolve()), patch('getpass.getpass', return_value='1234'):
            api = FakeAPI()
            original_pair = api.pair
            async def pair(*a, **kw):
                handler = await original_pair(*a, **kw)
                async def finish(): handler.has_paired = False
                handler.finish = finish
                return handler
            api.pair = pair
            out = io.StringIO()
            self.assertEqual(pp.main(['pair'], api=api, output=out), 1)
            self.assertIn('pairing-failed', out.getvalue())
            self.assertEqual(api.events[-1], 'pair-close')
            self.assertFalse((pp.Store().root / 'credentials.json').exists())

    def test_pair_hidden_pin_persists_then_closes(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home).resolve()), patch('getpass.getpass', return_value='0123') as pin:
            api = FakeAPI()
            out = io.StringIO()
            result = pp.main(['pair', '--host', '192.0.2.4'], api=api, output=out)
            self.assertEqual(result, 0, out.getvalue())
            pin.assert_called_once()
            self.assertIn(('pin', '0123'), api.events)
            self.assertEqual(api.events[-1], 'pair-close')
            self.assertEqual(pp.Store().load()['credentials'], 'SECRET')
            self.assertNotIn('SECRET', out.getvalue())

class PlayTests(unittest.TestCase):
    def test_prepare_connect_forces_airplay_v1_memory_storage(self):
        from unittest.mock import patch
        class Version:
            V1 = '1'
        settings = SimpleNamespace(protocols=SimpleNamespace(raop=SimpleNamespace(protocol_version='auto')))
        class MemoryStorage:
            async def get_settings(self, config):
                self.config = config
                return settings
        fake_storage = SimpleNamespace(MemoryStorage=MemoryStorage)
        fake_settings = SimpleNamespace(AirPlayVersion=Version)
        api = SimpleNamespace(Protocol=SimpleNamespace(AirPlay='airplay'))
        device = SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF')
        with patch.dict('sys.modules', {
            'pyatv.storage.memory_storage': fake_storage,
            'pyatv.settings': fake_settings,
        }):
            kwargs = asyncio.run(pp.prepare_connect(api, device))
        self.assertEqual(settings.protocols.raop.protocol_version, '1')
        self.assertIsInstance(kwargs['storage'], MemoryStorage)
        self.assertEqual(kwargs['protocol'], 'airplay')
        self.assertIs(kwargs['storage'].config, device)

    def test_status_and_stop_control_active_session_without_reconnecting(self):
        self.assertTrue(hasattr(pp, 'control'), 'local session control missing')
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home).resolve()):
            pp.Store().save({'identifier': 'AA:BB:CC:DD:EE:FF', 'credentials': 'SECRET'})
            async def scenario():
                api = FakeAPI()
                started = asyncio.Event()
                async def play_url(url):
                    started.set()
                    await asyncio.Event().wait()
                async def stop(): api.events.append('stop')
                def close():
                    api.events.append('close')
                    return set()
                async def connect(*a, **kw):
                    return SimpleNamespace(stream=SimpleNamespace(play_url=play_url), close=close,
                                           remote_control=SimpleNamespace(stop=stop))
                api.connect = connect
                out = io.StringIO()
                task = asyncio.create_task(pp.run(pp.arguments(['play', '--sample', 'mp4']), api, out, ['input']))
                await asyncio.wait_for(started.wait(), 2)
                status = await pp.control('status', 2)
                self.assertEqual(status, {'event': 'session-status', 'state': 'play-call-pending', 'receiver_playback': 'unverified'})
                self.assertEqual(stat.S_IMODE((pp.Store().root / 'control.sock').stat().st_mode), 0o600)
                response = await pp.control('stop', 2)
                self.assertEqual(response['event'], 'stop-request-accepted')
                self.assertEqual(await asyncio.wait_for(task, 2), 0)
                self.assertIn('stop', api.events)
                self.assertEqual(api.events[-1], 'close')
                self.assertFalse((pp.Store().root / 'control.sock').exists())
                self.assertEqual((await pp.control('status', 2))['event'], 'no-active-session')
            asyncio.run(scenario())

    def test_public_samples_timeout_is_not_success_and_closes(self):
        from unittest.mock import patch
        for sample in ('mp4', 'hls'):
            with self.subTest(sample=sample), tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home).resolve()):
                pp.Store().save({'identifier': 'AA:BB:CC:DD:EE:FF', 'credentials': 'SECRET'})
                api = FakeAPI()
                async def play_url(url):
                    api.events.append(url)
                    await asyncio.Event().wait()
                def close():
                    api.events.append('close')
                    return set()
                async def connect(*a, **kw):
                    return SimpleNamespace(stream=SimpleNamespace(play_url=play_url), close=close)
                api.connect = connect
                out = io.StringIO()
                code = pp.main(['play', '--sample', sample, '--play-timeout', '0.01'], api=api, output=out)
                self.assertEqual(code, 1, out.getvalue())
                self.assertIn('TimeoutError', out.getvalue())
                self.assertIn('"stage": "play"', out.getvalue())
                self.assertNotIn('play-call-returned', out.getvalue())
                self.assertEqual(api.events[-1], 'close')
                self.assertIn(pp.SAMPLES[sample], api.events)

    def test_reconnect_awaits_full_play_lifecycle_and_closes(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home).resolve()):
            pp.Store().save({'identifier': 'AA:BB:CC:DD:EE:FF', 'credentials': 'SECRET'})
            api = FakeAPI()
            async def play_url(url):
                api.events.append(('url', url))
                await asyncio.sleep(0.01)
                api.events.append('returned')
            def close():
                api.events.append('close')
                async def cleanup(): api.events.append('cleaned')
                return {asyncio.create_task(cleanup())}
            async def connect(config, loop, **kw):
                api.events.append(('connect', kw.get('protocol'), kw.get('storage')))
                return SimpleNamespace(stream=SimpleNamespace(play_url=play_url), close=close)
            api.connect = connect
            out = io.StringIO()
            url = 'https://EXAMPLE.com/a%2fb?token=SECRET&b=2'
            with patch('sys.stdin', io.StringIO(url + '\n')):
                code = pp.main(['play', '--stdin', '--host', '192.0.2.4'], api=api, output=out)
            self.assertEqual(code, 0, out.getvalue())
            self.assertIn(('credentials', 'SECRET'), api.events)
            self.assertIn(('connect', 'airplay', 'memory'), api.events)
            self.assertIn(('url', url), api.events)
            self.assertEqual(api.events[-3:], ['returned', 'close', 'cleaned'])
            self.assertNotIn('SECRET', out.getvalue())
            self.assertIn('visual-confirmation-required', out.getvalue())
            self.assertIn('play-call-returned', out.getvalue())

class CliTests(unittest.TestCase):
    def test_missing_receiver_and_invalid_config_never_connect(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home).resolve()):
            store = pp.Store()
            store.save({'identifier': 'AA:BB:CC:DD:EE:FF', 'credentials': 'SECRET'})
            api = FakeAPI()
            api.devices = []
            out = io.StringIO()
            self.assertEqual(pp.main(['play', '--sample', 'mp4'], api=api, output=out), 1)
            self.assertIn('receiver-selection-failed', out.getvalue())
            file = store.root / 'credentials.json'
            file.write_text('{"credentials":"SECRET","identifier":"x","unknown":"SECRET"}')
            out = io.StringIO()
            api.events.clear()
            self.assertEqual(pp.main(['play', '--sample', 'mp4'], api=api, output=out), 1)
            self.assertEqual(api.events, [])
            self.assertIn('credentials-load', out.getvalue())
            self.assertNotIn('SECRET', out.getvalue())

    def test_background_handler_never_raises_on_closed_output(self):
        async def scenario():
            out = io.StringIO()
            await pp.run(pp.arguments(['scan']), FakeAPI(), out, ['scan'])
            out.close()
            handler = asyncio.get_running_loop().get_exception_handler()
            try:
                handler(asyncio.get_running_loop(), {'exception': RuntimeError('SECRET')})
            except Exception:
                self.fail('unsafe handler can trigger raw asyncio fallback logging')
        asyncio.run(scenario())

    def test_control_failure_exits_nonzero(self):
        from unittest.mock import patch
        async def failed(*a): return {'event': 'control-failed'}
        with patch.object(pp, 'control', failed):
            self.assertEqual(pp.main(['stop'], api=FakeAPI(), output=io.StringIO()), 1)

    def test_rejects_ignored_options_and_non_linux_live_execution(self):
        from unittest.mock import patch
        for argv in (['scan', '--stdin'], ['play', '--sample', 'mp4', '--identifier', 'SECRET'], ['status', '--host', '192.0.2.4']):
            out = io.StringIO()
            self.assertEqual(pp.main(argv, api=FakeAPI(), output=out), 2, out.getvalue())
            self.assertNotIn('SECRET', out.getvalue())
        with patch('sys.platform', 'darwin'):
            out = io.StringIO()
            self.assertEqual(pp.main(['scan'], output=out), 1)
            self.assertIn('linux-required', out.getvalue())

    def test_keyboard_interrupt_is_sanitized(self):
        api = FakeAPI()
        async def scan(*a, **kw): raise KeyboardInterrupt('SECRET')
        api.scan = scan
        out = io.StringIO()
        try:
            code = pp.main(['scan'], api=api, output=out)
        except KeyboardInterrupt:
            self.fail('interrupt escaped safe boundary')
        self.assertEqual(code, 130)
        self.assertNotIn('SECRET', out.getvalue())
        self.assertIn('interrupted', out.getvalue())

    def test_airplay_authentication_http_status_is_extracted_only_from_exact_shape(self):
        class AuthenticationError(Exception): pass
        out = io.StringIO()
        pp.safe_failure(out, 'play', AuthenticationError('status code: 403'))
        self.assertEqual(json.loads(out.getvalue()).get('http_code'), 403)
        out = io.StringIO()
        pp.safe_failure(out, 'play', AuthenticationError('https://SECRET/status code: 403'))
        self.assertNotIn('http_code', out.getvalue())
        self.assertNotIn('SECRET', out.getvalue())

    def test_safe_upstream_failure_including_http_code_and_logs(self):
        class HttpError(Exception):
            status_code = 403
        class API:
            Protocol = SimpleNamespace(AirPlay='airplay')
            async def scan(self, *a, **kw):
                import logging
                logging.critical('SECRET https://secret')
                print('SECRET raw upstream')
                raise HttpError('SECRET https://secret')
        out = io.StringIO()
        from contextlib import redirect_stdout, redirect_stderr
        raw = io.StringIO()
        with redirect_stdout(raw), redirect_stderr(raw):
            code = pp.main(['scan'], api=API(), output=out)
        self.assertEqual(code, 1)
        self.assertNotIn('SECRET', out.getvalue() + raw.getvalue())
        self.assertEqual(json.loads(out.getvalue()), {'event': 'error', 'stage': 'scan', 'type': 'HttpError', 'http_code': 403})

    def test_scan_unicast_sanitizes_discovery_and_argument_errors(self):
        self.assertTrue(hasattr(pp, 'main'), 'CLI scan missing')
        class API:
            Protocol = SimpleNamespace(AirPlay='airplay')
            async def scan(self, loop, **kw):
                self.kw = kw
                return [SimpleNamespace(name='SECRET http://s/?token=SECRET', address='192.0.2.4',
                                        identifier='AA:BB:CC:DD:EE:FF',
                                        get_service=lambda p: SimpleNamespace(pairing=SimpleNamespace(name='Mandatory')))]
        api = API()
        out = io.StringIO()
        self.assertEqual(pp.main(['scan', '--host', '192.0.2.4'], api=api, output=out), 0)
        self.assertEqual(api.kw['hosts'], ['192.0.2.4'])
        self.assertNotIn('SECRET', out.getvalue())
        self.assertIn('192.0.2.4', out.getvalue())
        self.assertIn('AA:BB:CC:DD:EE:FF', out.getvalue())
        out = io.StringIO()
        self.assertEqual(pp.main(['play', '--url', 'https://SECRET'], api=api, output=out), 2)
        self.assertNotIn('SECRET', out.getvalue())

if __name__ == '__main__':
    unittest.main()
