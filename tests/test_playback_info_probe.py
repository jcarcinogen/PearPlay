"""Opt-in bounded /playback-info diagnostic probe (stdlib; no pyatv at these boundaries).

Covers the pure field normalization, the fixed-schema sanitize allowlist, the
opt-in resolver gates, the serializing probe wire, and the end-to-end Transport
integration (at most two queries, single-failure disables further probes, no
startup-timeout or success-state changes, clean cancel, non-opt-in untouched).
"""
import asyncio
import importlib.util
import json
import plistlib
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_helper_protocol import load

diag = load('diagnostics')
app = load('app')
native = load('native')


class PlaybackInfoRowTests(unittest.TestCase):
    def test_readiness_and_buffer_booleans_pass_through(self):
        data = {'readyToPlay': True, 'playbackBufferEmpty': False,
                'playbackBufferFull': False, 'playbackLikelyToKeepUp': True}
        self.assertEqual(diag.playback_info_row(data), {
            'readyToPlay': True, 'playbackBufferEmpty': False,
            'playbackBufferFull': False, 'playbackLikelyToKeepUp': True})

    def test_non_bool_values_are_dropped_and_missing_is_absent(self):
        data = {'readyToPlay': 1, 'playbackBufferEmpty': 'false',
                'playbackBufferFull': None, 'playbackLikelyToKeepUp': [True]}
        self.assertEqual(diag.playback_info_row(data), {})
        self.assertEqual(diag.playback_info_row({}), {})

    def test_rate_is_normalized_to_zero_one_other_without_raw_floats(self):
        for value, bucket in ((0.0, 'zero'), (1.0, 'one'), (0.5, 'other'),
                              (2.0, 'other'), (-1.0, 'other'), (0, 'zero'), (1, 'one')):
            self.assertEqual(diag.playback_info_row({'rate': value})['rate'], bucket, value)
        # playbackRate is the AirPlay v2 spelling.
        self.assertEqual(diag.playback_info_row({'playbackRate': 1.0})['rate'], 'one')

    def test_non_finite_and_non_numeric_rate_are_other_or_absent(self):
        self.assertEqual(diag.playback_info_row({'rate': float('nan')})['rate'], 'other')
        self.assertEqual(diag.playback_info_row({'rate': float('inf')})['rate'], 'other')
        for bad in ('1.0', None, True, [1], {'r': 1}):
            self.assertNotIn('rate', diag.playback_info_row({'rate': bad}), bad)

    def test_top_level_error_domain_and_signed_code_only(self):
        data = {'error': {'domain': 'NSURLErrorDomain', 'code': -1004}}
        self.assertEqual(diag.playback_info_row(data),
                         {'domain': 'NSURLErrorDomain', 'code': -1004})

    def test_unknown_domain_is_other_and_bad_code_dropped(self):
        self.assertEqual(diag.playback_info_row(
            {'error': {'domain': 'PrivateVendorDomain', 'code': '1004'}}),
            {'domain': 'other'})

    def test_non_dict_error_is_ignored_and_nested_error_not_scraped(self):
        self.assertEqual(diag.playback_info_row({'error': 'boom'}), {})
        self.assertEqual(diag.playback_info_row(
            {'params': {'error': {'domain': 'NSURLErrorDomain', 'code': 1}}}), {})

    def test_non_dict_data_is_none_and_no_secrets_leak(self):
        self.assertIsNone(diag.playback_info_row(None))
        self.assertIsNone(diag.playback_info_row('readyToPlay'))
        result = diag.playback_info_row({'readyToPlay': True, 'url': 'https://SECRET',
                                         'token': 'PRIVATE', 'duration': 12.34,
                                         'position': 1.5})
        self.assertEqual(result, {'readyToPlay': True})
        for secret in ('SECRET', 'PRIVATE', 'https://', 'duration', 'position'):
            self.assertNotIn(secret, json.dumps(result))


class ProbeSanitizeTests(unittest.TestCase):
    def test_allowlisted_probe_fields_pass_through(self):
        fields = {'status': 'ok', 'httpCode': 200, 'readyToPlay': True,
                  'rate': 'one', 'domain': 'NSURLErrorDomain', 'code': -1004}
        self.assertEqual(diag.sanitize('probe', fields),
                         {'k': 'probe', 'status': 'ok', 'httpCode': 200,
                          'readyToPlay': True, 'rate': 'one',
                          'domain': 'NSURLErrorDomain', 'code': -1004})

    def test_unknown_probe_fields_and_secrets_are_dropped(self):
        row = diag.sanitize('probe', {'status': 'ok', 'httpCode': 200, 'url': 'https://SECRET',
                                      'body': 'RAW', 'rate': 'one', 'host': '1.2.3.4'})
        self.assertEqual(row, {'k': 'probe', 'status': 'ok', 'httpCode': 200, 'rate': 'one'})

    def test_bad_status_http_code_and_rate_are_dropped(self):
        self.assertEqual(diag.sanitize('probe', {'status': 'exfiltration'}), {'k': 'probe'})
        self.assertEqual(diag.sanitize('probe', {'status': 'ok', 'httpCode': 999}),
                         {'k': 'probe', 'status': 'ok'})
        self.assertEqual(diag.sanitize('probe', {'status': 'ok', 'rate': 'fast'}),
                         {'k': 'probe', 'status': 'ok'})

    def test_boolean_fields_reject_non_bool(self):
        row = diag.sanitize('probe', {'status': 'ok', 'readyToPlay': 1,
                                      'playbackBufferEmpty': 'true'})
        self.assertEqual(row, {'k': 'probe', 'status': 'ok'})

    def test_probe_is_a_known_schema_kind(self):
        self.assertIn('probe', diag._SCHEMA)

    def test_empty_status_is_allowlisted(self):
        self.assertEqual(diag.sanitize('probe', {'status': 'empty'}),
                         {'k': 'probe', 'status': 'empty'})

    def test_quarantined_bool_is_allowlisted(self):
        self.assertEqual(diag.sanitize('probe', {'status': 'timeout', 'quarantined': True}),
                         {'k': 'probe', 'status': 'timeout', 'quarantined': True})

    def test_quarantined_non_bool_is_dropped(self):
        self.assertEqual(diag.sanitize('probe', {'status': 'timeout', 'quarantined': 1}),
                         {'k': 'probe', 'status': 'timeout'})


class ResolveProbeTests(unittest.TestCase):
    def test_production_and_non_frozen_ignore_probe(self):
        env = {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/t',
               'PEARPLAY_DIAGNOSTIC_PROBE_PLAYBACK_INFO': 'origin-mp4'}
        self.assertIsNone(diag.resolve_probe_playback_info(env, frozen=False, development=True))
        self.assertIsNone(diag.resolve_probe_playback_info(env, frozen=True, development=False))

    def test_requires_active_trace(self):
        env = {'PEARPLAY_DIAGNOSTIC_PROBE_PLAYBACK_INFO': 'origin-mp4'}
        self.assertIsNone(diag.resolve_probe_playback_info(env, frozen=True, development=True))

    def test_accepts_only_origin_mp4_and_hls(self):
        base = {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/t'}
        for value in ('origin-mp4', 'origin-hls'):
            self.assertEqual(diag.resolve_probe_playback_info(
                dict(base, PEARPLAY_DIAGNOSTIC_PROBE_PLAYBACK_INFO=value),
                frozen=True, development=True), value)
        for bad in ('hls-master', 'mp4', '', 'origin-mp4 ', None):
            self.assertIsNone(diag.resolve_probe_playback_info(
                dict(base, PEARPLAY_DIAGNOSTIC_PROBE_PLAYBACK_INFO=bad),
                frozen=True, development=True), bad)


class ProbeOptionTests(unittest.TestCase):
    def test_option_resolves_only_with_frozen_development_and_trace(self):
        env = {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/t',
               'PEARPLAY_DIAGNOSTIC_PROBE_PLAYBACK_INFO': 'origin-mp4'}
        self.assertEqual(app.probe_playback_info_option(
            {'development': True}, environ=env, frozen=True), 'origin-mp4')
        self.assertIsNone(app.probe_playback_info_option(
            {'development': True}, environ=env, frozen=False))
        self.assertIsNone(app.probe_playback_info_option(
            {'development': False}, environ=env, frozen=True))
        self.assertIsNone(app.probe_playback_info_option(
            {'development': True}, environ={'PEARPLAY_DIAGNOSTIC_PROBE_PLAYBACK_INFO': 'origin-mp4'},
            frozen=True))


class PlaybackInfoProbeTests(unittest.IsolatedAsyncioTestCase):
    class Connection:
        def __init__(self, response=None):
            self.response = response
            self.gets = []
            # Model the pyatv HttpConnection seam the streaming probe guard depends on.
            self.receive_processor = lambda data: data
            self._buffer = b''
        async def get(self, path, allow_error=False):
            self.gets.append(path)
            if isinstance(self.response, Exception):
                raise self.response
            if self.response is None:
                return SimpleNamespace(code=200, body=b'')
            return self.response

    def make_probe(self, connection, timeout=0.5):
        return native.PlaybackInfoProbe(SimpleNamespace(connection=connection), timeout)

    async def test_ok_response_is_parsed_to_fixed_fields(self):
        import plistlib
        body = plistlib.dumps({'readyToPlay': True, 'rate': 1.0},
                              fmt=plistlib.FMT_BINARY)
        conn = self.Connection(SimpleNamespace(code=200, body=body))
        result = await self.make_probe(conn).probe()
        self.assertEqual(result, {'status': 'ok', 'httpCode': 200, 'readyToPlay': True, 'rate': 'one'})

    async def test_empty_body_is_empty_with_http_code(self):
        conn = self.Connection(SimpleNamespace(code=200, body=b''))
        self.assertEqual(await self.make_probe(conn).probe(), {'status': 'empty', 'httpCode': 200})

    async def test_parsed_dict_without_recognized_fields_is_empty(self):
        body = plistlib.dumps({'unrecognizedKey': 'x'}, fmt=plistlib.FMT_BINARY)
        conn = self.Connection(SimpleNamespace(code=200, body=body))
        self.assertEqual(await self.make_probe(conn).probe(), {'status': 'empty', 'httpCode': 200})

    async def test_non_2xx_is_rejected_with_http_code(self):
        conn = self.Connection(SimpleNamespace(code=404, body=b'ignored'))
        self.assertEqual(await self.make_probe(conn).probe(), {'status': 'rejected', 'httpCode': 404})

    async def test_timeout_is_timeout(self):
        class Never:
            def __init__(self):
                self.receive_processor = lambda data: data
                self._buffer = b''
            async def get(self, path, allow_error=False):
                await asyncio.sleep(10)
        result = await self.make_probe(Never(), timeout=0.01).probe()
        self.assertEqual(result, {'status': 'timeout', 'quarantined': True})

    async def test_unparseable_body_is_invalid(self):
        conn = self.Connection(SimpleNamespace(code=200, body=b'\xff\xfe\x00garbage'))
        result = await self.make_probe(conn).probe()
        self.assertEqual(result, {'status': 'invalid', 'httpCode': 200})

    async def test_oversized_body_is_invalid(self):
        conn = self.Connection(SimpleNamespace(code=200, body=b'x' * (diag.PROBE_MAX_BODY + 1)))
        result = await self.make_probe(conn).probe()
        self.assertEqual(result, {'status': 'invalid', 'httpCode': 200})

    async def test_missing_connection_is_unsupported(self):
        result = await native.PlaybackInfoProbe(SimpleNamespace(), 0.5).probe()
        self.assertEqual(result, {'status': 'unsupported'})

    async def test_get_exception_is_unsupported_and_never_leaks(self):
        class Broken:
            def __init__(self):
                self.receive_processor = lambda data: data
                self._buffer = b''
            async def get(self, path, allow_error=False):
                raise RuntimeError('SECRET')
        self.assertEqual(await self.make_probe(Broken()).probe(),
                         {'status': 'unsupported', 'quarantined': True})

    async def test_probe_serializes_with_request_on_the_same_connection(self):
        # Two concurrent operations must never overlap on the shared control
        # connection; the lock serializes them so at most one is in flight.
        entered = []
        released = []
        class Wire:
            def __init__(self, connection):
                self.connection = connection
            async def request(self, stage, body=None, headers=None):
                entered.append('request')
                await asyncio.sleep(0.01)
                released.append('request')
                return {}
        probe = native.PlaybackInfoProbe(Wire(self.Connection()), 0.5)
        req = asyncio.create_task(probe.request('feedback'))
        await asyncio.sleep(0)
        got = asyncio.create_task(probe.probe())
        await asyncio.gather(req, got)
        # Order is request-enters, request-releases, then probe runs.
        self.assertEqual(entered, ['request'])
        self.assertEqual(released, ['request'])


class TransportProbeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    class Connection:
        def __init__(self):
            self.gets = []
            self.responses = []
            self.closed = False
            # Model the pyatv HttpConnection seam the streaming probe guard depends on.
            self.receive_processor = lambda data: data
            self._buffer = b''
        async def get(self, path, allow_error=False):
            self.gets.append(path)
            fn = self.responses.pop(0) if self.responses else None
            if fn is None:
                body = plistlib.dumps({'readyToPlay': True}, fmt=plistlib.FMT_BINARY)
                return SimpleNamespace(code=200, body=body)
            return await fn()
        def close(self):
            self.closed = True

    def make_backend(self, playing_delay=0.05):
        class Wire:
            def __init__(self, connection, credentials, timeout, report, stage):
                self.connection = connection
                self.report = report
                self.stage = stage
                self.closed = False
                self.timing_port = None
                self.callback = None
            async def timing(self, port):
                self.timing_port = port
            async def request(self, stage, body=None, headers=None):
                if stage == 'setup-base':
                    return {'eventPort': 1234}
                if stage == 'setup-stream':
                    return {'streams': [{'streamID': 1}]}
                if stage == 'command':
                    if playing_delay is not None:
                        loop = asyncio.get_running_loop()
                        def fire():
                            self.callback({'type': 'playbackState', 'name': 'playing'})
                            self.callback({'type': 'playbackState', 'name': 'stopped'})
                        loop.call_later(playing_delay, fire)
                return {}
            async def events(self, port, callback):
                self.callback = callback
            def close(self):
                self.closed = True
        return Wire

    def make_transport(self, m, command, directory, *, probe_playback_info=None,
                       probe_timeout=0.1, probe_delays=(0.01, 0.03), timeout=1.0,
                       startup_timeout=None, playing_delay=0.05):
        device = SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF', address='127.0.0.1',
                                 get_service=lambda _: SimpleNamespace(port=7000))

        async def scan(*a, **k):
            return [device]

        connection = self.Connection()

        async def connect(*a):
            return connection

        store = command.existing().Store()
        store.root = Path(directory).resolve() / 'state'
        store.save(dict(identifier=device.identifier, credentials='private-credential'))
        t = m.Transport(api=SimpleNamespace(scan=scan, Protocol=SimpleNamespace(AirPlay=1)),
                        command=command, store=store, connect=connect, parse=lambda x: x,
                        backend=self.make_backend(playing_delay), timeout=timeout,
                        startup_timeout=startup_timeout,
                        probe_playback_info=probe_playback_info, probe_timeout=probe_timeout,
                        probe_delays=probe_delays)
        return t, device, connection

    def url(self):
        return 'https://example.test/a.mp4'

    async def test_probe_issues_two_queries_during_hold_and_writes_sanitized_rows(self):
        m = load(); command = m.spike()
        records = []
        def trace(kind, **fields):
            records.append((kind, dict(fields)))
        with tempfile.TemporaryDirectory() as directory:
            t, device, connection = self.make_transport(m, command, directory,
                                                        probe_playback_info='origin-mp4')
            t.trace = trace
            await t.run(dict(receiver=device.identifier, host='127.0.0.1', url=self.url()),
                        lambda *x: None)
        self.assertEqual(len(connection.gets), 2)
        self.assertEqual([p for p in connection.gets], ['/playback-info', '/playback-info'])
        probes = [f for k, f in records if k == 'probe']
        self.assertEqual(len(probes), 2)
        self.assertEqual([p['status'] for p in probes], ['ok', 'ok'])

    async def test_timeout_disables_further_probes(self):
        m = load(); command = m.spike()
        with tempfile.TemporaryDirectory() as directory:
            t, device, connection = self.make_transport(m, command, directory,
                                                        probe_playback_info='origin-hls',
                                                        probe_timeout=0.01)

            async def hang():
                await asyncio.sleep(10)
            connection.responses.append(hang)
            await t.run(dict(receiver=device.identifier, host='127.0.0.1', url=self.url()),
                        lambda *x: None)
        self.assertEqual(len(connection.gets), 1)

    async def test_invalid_body_disables_further_probes(self):
        m = load(); command = m.spike()
        with tempfile.TemporaryDirectory() as directory:
            t, device, connection = self.make_transport(m, command, directory,
                                                        probe_playback_info='origin-mp4')

            async def invalid():
                return SimpleNamespace(code=200, body=b'\xff\xfe bad')
            connection.responses.append(invalid)
            await t.run(dict(receiver=device.identifier, host='127.0.0.1', url=self.url()),
                        lambda *x: None)
        self.assertEqual(len(connection.gets), 1)

    async def test_probe_does_not_extend_await_playing_timeout(self):
        m = load(); command = m.spike()
        with tempfile.TemporaryDirectory() as directory:
            # A wire that never fires 'playing'; probe runs concurrently but the
            # await-playing wait still times out on the startup timeout.
            t, device, connection = self.make_transport(m, command, directory,
                                                        probe_playback_info='origin-mp4',
                                                        startup_timeout=0.05, playing_delay=None)
            with self.assertRaises(m.PlaybackError) as ctx:
                await t.run(dict(receiver=device.identifier, host='127.0.0.1', url=self.url()),
                            lambda *x: None)
            self.assertEqual(ctx.exception.diagnostic, {'stage': 'await-playing', 'reason': 'timeout'})
            self.assertTrue(t.wire._wire.closed)

    async def test_probe_does_not_alter_success_state(self):
        m = load(); command = m.spike()
        notices = []
        with tempfile.TemporaryDirectory() as directory:
            t, device, connection = self.make_transport(m, command, directory,
                                                        probe_playback_info='origin-mp4')
            await t.run(dict(receiver=device.identifier, host='127.0.0.1', url=self.url()),
                        lambda *x: notices.append(x))
        self.assertIn(('playing', 'protocol'), notices)
        self.assertEqual(len(connection.gets), 2)

    async def test_non_opt_in_never_probes_or_wraps(self):
        m = load(); command = m.spike()
        with tempfile.TemporaryDirectory() as directory:
            t, device, connection = self.make_transport(m, command, directory)
            await t.run(dict(receiver=device.identifier, host='127.0.0.1', url=self.url()),
                        lambda *x: None)
        self.assertEqual(connection.gets, [])
        self.assertFalse(isinstance(t.wire, m.PlaybackInfoProbe))

    async def test_cancel_leaves_no_probe_task_running(self):
        m = load(); command = m.spike()
        with tempfile.TemporaryDirectory() as directory:
            t, device, connection = self.make_transport(m, command, directory,
                                                        probe_playback_info='origin-mp4',
                                                        playing_delay=None, startup_timeout=0.05)
            with self.assertRaises(m.PlaybackError):
                await t.run(dict(receiver=device.identifier, host='127.0.0.1', url=self.url()),
                             lambda *x: None)
        # After run() returns (even via timeout), no probe task may remain.
        await asyncio.sleep(0.05)
        self.assertFalse([task for task in asyncio.all_tasks()
                          if task is not asyncio.current_task() and not task.done()])


class ProbeSchedulingTests(unittest.IsolatedAsyncioTestCase):
    """The bounded schedule behind ``Transport._probe_playback_info``."""

    def transport_with(self, wire, trace=None):
        t = native.Transport.__new__(native.Transport)
        t.wire = wire
        t.trace = trace
        return t

    async def test_caps_at_two_probes_even_with_long_delays(self):
        calls = []
        class Wire:
            async def probe(self):
                calls.append(1)
                return {'status': 'ok'}
        t = self.transport_with(Wire())
        await t._probe_playback_info((0.001, 0.002, 0.003, 0.004))
        self.assertEqual(len(calls), 2)

    async def test_monotonic_absolute_targets_not_relative_sleep(self):
        # The first GET overruns the gap to the second target. Absolute targets
        # fire the second probe at start+delays[1], not delayed by the GET time.
        loop = asyncio.get_running_loop()
        start = loop.time()
        call_times = []
        class Wire:
            async def probe(self):
                call_times.append(loop.time() - start)
                if len(call_times) == 1:
                    await asyncio.sleep(0.10)  # first GET runs long
                return {'status': 'ok'}
        t = self.transport_with(Wire())
        await t._probe_playback_info((0.02, 0.30))
        self.assertEqual(len(call_times), 2)
        # Second probe at ~0.30 (absolute), not ~0.40 (relative sleep).
        self.assertAlmostEqual(call_times[1], 0.30, delta=0.04)


class _FakeTransport:
    def __init__(self):
        self.sent = []
        self.closed = False
    def write(self, data):
        self.sent.append(data)
    def close(self):
        self.closed = True


@unittest.skipUnless(importlib.util.find_spec('pyatv'), 'Run in the Acer diagnostic venv with real pyatv')
class PlaybackInfoProbeRealHttpTests(unittest.IsolatedAsyncioTestCase):
    """Probe safety against the real pyatv ``HttpConnection`` (no network).

    Exercises fragmented delivery, oversized bodies, and the late-response path
    after a timeout so the probe never desyncs or leaves a pending request.
    """
    def make_connection(self):
        from pyatv.support.http import HttpConnection
        connection = HttpConnection()
        connection.transport = _FakeTransport()
        return connection

    def response_bytes(self, code, body):
        from pyatv.support.http import HttpResponse, format_response
        headers = {'Content-Type': 'application/x-apple-binary-plist'}
        return format_response(HttpResponse('HTTP', '1.1', code, 'OK', headers, body))

    async def _wait_for_request(self, connection):
        """Yield until the probe's GET has registered in the connection queue."""
        for _ in range(500):
            if connection._requests:
                return
            await asyncio.sleep(0.001)
        raise AssertionError('probe request never registered')

    async def test_fragmented_response_is_assembled_and_parsed(self):
        connection = self.make_connection()
        body = plistlib.dumps({'readyToPlay': True, 'rate': 1.0}, fmt=plistlib.FMT_BINARY)
        raw = self.response_bytes(200, body)
        probe = native.PlaybackInfoProbe(SimpleNamespace(connection=connection), 0.5)
        task = asyncio.create_task(probe.probe())
        await self._wait_for_request(connection)
        connection.data_received(raw[:3])
        connection.data_received(raw[3:])
        result = await task
        self.assertEqual(result, {'status': 'ok', 'httpCode': 200, 'readyToPlay': True, 'rate': 'one'})

    async def test_oversized_body_is_invalid(self):
        connection = self.make_connection()
        raw = self.response_bytes(200, b'x' * (diag.PROBE_MAX_BODY + 1))
        probe = native.PlaybackInfoProbe(SimpleNamespace(connection=connection), 0.5)
        task = asyncio.create_task(probe.probe())
        await asyncio.sleep(0)
        connection.data_received(raw)
        result = await task
        self.assertEqual(result, {'status': 'invalid', 'quarantined': True})

    async def test_size_guard_rejects_header_before_large_body_arrives(self):
        connection = self.make_connection()
        probe = native.PlaybackInfoProbe(SimpleNamespace(connection=connection), 0.1)
        task = asyncio.create_task(probe.probe())
        await asyncio.sleep(0.005)
        connection.data_received(b'HTTP/1.1 200 OK\r\nContent-Length: 99999999\r\n\r\n')
        result = await task
        self.assertEqual(result['status'], 'invalid')
        self.assertTrue(result['quarantined'])
        self.assertEqual(connection._buffer, b'')

    async def test_timeout_quarantines_followup_and_late_fragmented_reply(self):
        connection = self.make_connection()
        class Wire:
            async def request(self, *args):
                return await connection.get('/feedback')
        wire = Wire(); wire.connection = connection
        probe = native.PlaybackInfoProbe(wire, 0.01)
        result = await probe.probe()
        self.assertTrue(result['quarantined'])
        sent = len(connection.transport.sent)
        with self.assertRaises(RuntimeError):
            await probe.request('feedback')
        connection.data_received(b'HTTP/1.1 200 OK\r\nContent-Length: 99999\r\n\r\nlate')
        connection.data_received(b'x' * 100000)
        self.assertEqual(len(connection.transport.sent), sent)
        self.assertEqual(connection._buffer, b'')
        self.assertEqual(len(connection._requests), 0)

    async def test_healthy_probe_restores_exact_receive_processor(self):
        import plistlib
        connection = self.make_connection()
        original = connection.receive_processor
        probe = native.PlaybackInfoProbe(SimpleNamespace(connection=connection), 0.1)
        task = asyncio.create_task(probe.probe())
        await asyncio.sleep(0.005)
        connection.data_received(self.response_bytes(200, plistlib.dumps({'readyToPlay': False})))
        result = await task
        self.assertEqual(result['readyToPlay'], False)
        self.assertIs(connection.receive_processor, original)

    async def test_timeout_leaves_no_pending_request_and_late_response_is_safe(self):
        connection = self.make_connection()
        probe = native.PlaybackInfoProbe(SimpleNamespace(connection=connection), 0.01)
        result = await probe.probe()
        self.assertEqual(result, {'status': 'timeout', 'quarantined': True})
        # The cancelled request is removed from the connection's queue.
        self.assertEqual(len(connection._requests), 0)
        # A late response arriving afterwards is discarded, never misattributed.
        body = plistlib.dumps({'readyToPlay': True}, fmt=plistlib.FMT_BINARY)
        connection.data_received(self.response_bytes(200, body))
        self.assertEqual(len(connection._requests), 0)

    async def test_cancel_quarantines_and_keeps_guard(self):
        connection = self.make_connection()
        original = connection.receive_processor
        probe = native.PlaybackInfoProbe(SimpleNamespace(connection=connection), 1.0)
        task = asyncio.create_task(probe.probe())
        await self._wait_for_request(connection)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        # Quarantined: the guard processor is not restored to the original and
        # no pending request survives, so a late reply cannot be misattributed.
        self.assertIsNot(connection.receive_processor, original)
        self.assertEqual(connection._buffer, b'')
        self.assertEqual(len(connection._requests), 0)
        # A subsequent probe reports the quarantine without issuing a request.
        result = await probe.probe()
        self.assertTrue(result['quarantined'])
        self.assertEqual(len(connection._requests), 0)


if __name__ == '__main__':
    unittest.main()
