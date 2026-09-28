"""Diagnostic event reports must not alter the encrypted event decoder."""
import importlib.util
import json
import plistlib
import unittest
from test_command_transport import module


@unittest.skipUnless(importlib.util.find_spec('pyatv'), 'Run decoder tests in Acer diagnostic venv with real pyatv')
class EventDiagnostics(unittest.TestCase):
    def test_event_decode_reports_only_fixed_status_without_payload(self):
        from pyatv.support.http import HttpRequest
        adapter = module()
        reports, received = [], []
        channel = adapter.event_factory(received.append, lambda event, **fields: reports.append((event, fields)))(bytes(32), bytes(32))
        sent = []
        channel.send = sent.append
        data = {'type': 'playbackState', 'name': 'playing', 'url': 'https://private.test/?PIN=SECRET'}
        body = plistlib.dumps({'params': {'data': plistlib.dumps(data)}})
        request = HttpRequest('POST', '/event', 'HTTP', '1.1', {'CSeq': '3'}, body)
        channel.buffer = channel.format_request(request)
        channel.handle_received()
        self.assertEqual(received, [data])
        self.assertIn(b'200 OK', sent[0])
        self.assertEqual(reports, [('event-channel', {'status': 'received'}), ('event-channel', {'status': 'decoded'})])
        self.assertNotIn('SECRET', json.dumps(reports))
        channel.buffer = b'x' * (1024 * 1024 + 1)
        channel.handle_received()
        self.assertEqual(reports[-1], ('event-channel', {'status': 'parse-error'}))
        self.assertEqual(channel.buffer, b'')

    def test_ignored_envelope_and_failed_reporter_do_not_change_delivery(self):
        from pyatv.support.http import HttpRequest
        adapter = module()
        reports = []
        channel = adapter.event_factory(lambda data: None, lambda event, **fields: reports.append((event, fields)))(bytes(32), bytes(32))
        channel.send = lambda data: None
        body = plistlib.dumps({'params': {'data': 'SECRET'}})
        channel.buffer = channel.format_request(HttpRequest('POST', '/event', 'HTTP', '1.1', {}, body))
        channel.handle_received()
        self.assertEqual(reports[-1], ('event-channel', {'status': 'ignored'}))
        received = []
        def unavailable(*args, **kwargs):
            raise OSError('SECRET')
        channel = adapter.event_factory(received.append, unavailable)(bytes(32), bytes(32))
        channel.send = lambda data: None
        body = plistlib.dumps({'params': {'data': plistlib.dumps({'type': 'playbackState', 'name': 'playing'})}})
        channel.buffer = channel.format_request(HttpRequest('POST', '/event', 'HTTP', '1.1', {}, body))
        channel.handle_received()
        self.assertEqual(received, [{'type': 'playbackState', 'name': 'playing'}])

    def test_decoded_error_event_normalizes_without_leaking_payload(self):
        from pyatv.support.http import HttpRequest
        from test_helper_protocol import load
        diag = load('diagnostics')
        adapter = module()
        received = []
        channel = adapter.event_factory(received.append, lambda event, **fields: None)(bytes(32), bytes(32))
        channel.send = lambda data: None
        data = {'type': 'playbackError', 'error': {'domain': 'NSURLErrorDomain', 'code': -1004},
                'url': 'https://private.test/stream?PIN=SECRET', 'token': 'PRIVATE'}
        body = plistlib.dumps({'params': {'data': plistlib.dumps(data)}})
        request = HttpRequest('POST', '/event', 'HTTP', '1.1', {'CSeq': '3'}, body)
        channel.buffer = channel.format_request(request)
        channel.handle_received()
        self.assertEqual(received, [data])
        normalized = diag.normalize_event(received[0])
        self.assertEqual(normalized, {'type': 'playbackError', 'state': 'other', 'hasError': True,
                                      'domain': 'NSURLErrorDomain', 'code': -1004, 'hasUrl': True})
        self.assertNotIn('url', normalized)  # no raw url key; only the hasUrl presence bool
        text = json.dumps(normalized)
        for secret in ('SECRET', 'PRIVATE', 'private.test', 'token'):
            self.assertNotIn(secret, text)
