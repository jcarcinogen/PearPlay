"""Opt-in development-only sanitized playback trace (stdlib, no pyatv)."""
import json
import tempfile
import unittest
from pathlib import Path
from test_helper_protocol import load

m = load('diagnostics')

HLS = 'https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8'
MP4 = 'https://media.w3.org/2010/05/bunny/trailer.mp4'


class EventLabelCrossInstanceTests(unittest.TestCase):
    def test_two_collectors_share_file_cap_and_dedup(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'labels'; path.touch(mode=0o600)
            a = m.EventLabelCollector(str(path)); b = m.EventLabelCollector(str(path))
            try:
                for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                    a({'type': 'Unknown' + letter})
                    b({'type': 'Unknown' + letter})
                rows = [json.loads(s) for s in path.read_text().splitlines()]
                self.assertEqual(len(rows), 16)
                self.assertEqual(len({r['eventType'] for r in rows}), 16)
            finally:
                for c in (a, b):
                    if c._fd is not None: os.close(c._fd)


class ClassifyUrlTests(unittest.TestCase):
    def test_exact_public_fixtures_are_classified(self):
        self.assertEqual(m.classify_url(HLS), ('hls', 'public-hls-master'))
        self.assertEqual(m.classify_url(MP4), ('mp4', 'public-mp4'))

    def test_non_fixture_urls_are_coarse_classified_only(self):
        self.assertEqual(m.classify_url('https://example.test/a.mp4'), ('mp4', 'other'))
        self.assertEqual(m.classify_url('https://example.test/a.m3u8'), ('hls', 'other'))
        self.assertEqual(m.classify_url('https://example.test/a.m3u'), ('hls', 'other'))
        self.assertEqual(m.classify_url('https://example.test/stream'), ('other', 'other'))

    def test_query_and_fragment_do_not_break_coarse_type(self):
        self.assertEqual(m.classify_url('https://example.test/a.mp4?token=SECRET'), ('mp4', 'other'))
        self.assertEqual(m.classify_url('https://example.test/a.m3u8#frag'), ('hls', 'other'))

    def test_non_string_url_is_other(self):
        self.assertEqual(m.classify_url(None), ('other', 'other'))
        self.assertEqual(m.classify_url(42), ('other', 'other'))


class NormalizeEventTests(unittest.TestCase):
    def test_known_playing_event_is_normalized(self):
        data = {'type': 'playbackState', 'name': 'playing'}
        self.assertEqual(m.normalize_event(data), {'type': 'playbackState', 'state': 'playing'})

    def test_params_playback_state_is_read(self):
        data = {'type': 'playbackState', 'params': {'playbackState': 'stopped'}}
        self.assertEqual(m.normalize_event(data), {'type': 'playbackState', 'state': 'stopped'})

    def test_unknown_event_shape_is_summarized_not_leaked(self):
        data = {'type': 'secretType', 'name': 'playing', 'token': 'PRIVATE',
                'params': {'playbackState': 'playing', 'url': 'http://evil/secret'}}
        result = m.normalize_event(data)
        self.assertEqual(result, {'type': 'other', 'state': 'playing', 'hasUrl': True})
        text = json.dumps(result)
        for secret in ('PRIVATE', 'http://evil', 'secretType', 'token'):
            self.assertNotIn(secret, text)

    def test_non_dict_event_is_safe(self):
        self.assertEqual(m.normalize_event(None), {'type': 'other', 'state': 'other'})
        self.assertEqual(m.normalize_event('playbackState'), {'type': 'other', 'state': 'other'})

    def test_unhashable_type_and_state_values_do_not_raise(self):
        self.assertEqual(m.normalize_event({'type': {'x': 1}})['type'], 'other')
        self.assertEqual(m.normalize_event({'name': ['playing']})['state'], 'other')


class SanitizeTests(unittest.TestCase):
    def test_allowlisted_fields_pass_through(self):
        row = m.sanitize('stage', {'stage': 'connect', 'code': 200})
        self.assertEqual(row, {'k': 'stage', 'stage': 'connect', 'code': 200})

    def test_unknown_fields_are_dropped(self):
        row = m.sanitize('input', {'media': 'mp4', 'fixture': 'other', 'url': 'https://secret', 'host': '1.2.3.4'})
        self.assertEqual(row, {'k': 'input', 'media': 'mp4', 'fixture': 'other'})
        self.assertNotIn('https://secret', json.dumps(row))

    def test_channel_status_is_allowlisted(self):
        self.assertEqual(m.sanitize('channel', {'status': 'parse-error'}), {'k': 'channel', 'status': 'parse-error'})
        self.assertEqual(m.sanitize('channel', {'status': 'arbitrary-string'}), {'k': 'channel'})

    def test_unknown_kind_returns_none(self):
        self.assertIsNone(m.sanitize('exfiltration', {'stage': 'connect'}))
        self.assertIsNone(m.sanitize('stage', 'not-a-dict'))

    def test_out_of_range_values_are_dropped(self):
        self.assertEqual(m.sanitize('stage', {'stage': 'connect', 'code': 9999}), {'k': 'stage', 'stage': 'connect'})
        self.assertEqual(m.sanitize('outcome', {'outcome': 'arbitrary-string'}), {'k': 'outcome'})


class ResolveEnvTests(unittest.TestCase):
    def test_production_ignores_both_variables(self):
        env = {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/trace', 'PEARPLAY_DIAGNOSTIC_STARTUP_SECONDS': '30'}
        self.assertEqual(m.resolve_env(env, frozen=False, development=True), (None, None))
        self.assertEqual(m.resolve_env(env, frozen=True, development=False), (None, None))
        self.assertEqual(m.resolve_env(env, frozen=False, development=False), (None, None))

    def test_development_frozen_requires_trace_path(self):
        self.assertEqual(m.resolve_env({}, frozen=True, development=True), (None, None))
        self.assertEqual(m.resolve_env({'PEARPLAY_DIAGNOSTIC_TRACE': ''}, frozen=True, development=True), (None, None))

    def test_startup_seconds_accepts_only_10_and_30(self):
        env = {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/trace'}
        self.assertEqual(m.resolve_env(dict(env, PEARPLAY_DIAGNOSTIC_STARTUP_SECONDS='10'), frozen=True, development=True),
                         ('/tmp/trace', 10))
        self.assertEqual(m.resolve_env(dict(env, PEARPLAY_DIAGNOSTIC_STARTUP_SECONDS='30'), frozen=True, development=True),
                         ('/tmp/trace', 30))
        for bad in ('5', '100', 'abc', '', '10.0', ' 10'):
            self.assertEqual(m.resolve_env(dict(env, PEARPLAY_DIAGNOSTIC_STARTUP_SECONDS=bad), frozen=True, development=True),
                             ('/tmp/trace', None))

    def test_startup_seconds_ignored_without_trace(self):
        env = {'PEARPLAY_DIAGNOSTIC_STARTUP_SECONDS': '30'}
        self.assertEqual(m.resolve_env(env, frozen=True, development=True), (None, None))


class DiagnosticTraceFileTests(unittest.TestCase):
    def write_rows(self, path, *calls):
        trace = m.DiagnosticTrace(path)
        for kind, fields in calls:
            trace(kind, **fields)
        return trace

    def test_owner_only_regular_file_is_accepted_and_appended(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.jsonl'
            path.write_text('')
            path.chmod(0o600)
            trace = self.write_rows(str(path), ('stage', {'stage': 'connect'}))
            self.assertFalse(trace.disabled)
            rows = [json.loads(line) for line in path.read_text().splitlines() if line]
            self.assertEqual(rows[0]['k'], 'stage')
            self.assertEqual(rows[0]['stage'], 'connect')
            self.assertIsInstance(rows[0]['t'], int)
            self.assertGreaterEqual(rows[0]['t'], 0)

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            real = Path(directory) / 'real'; real.write_text(''); real.chmod(0o600)
            link = Path(directory) / 'link'; link.symlink_to(real)
            trace = m.DiagnosticTrace(str(link))
            self.assertTrue(trace.disabled)
            trace('stage', stage='connect')
            self.assertEqual(real.read_text(), '')

    def test_world_readable_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.jsonl'
            path.write_text(''); path.chmod(0o644)
            trace = self.write_rows(str(path), ('stage', {'stage': 'connect'}))
            self.assertTrue(trace.disabled)
            self.assertEqual(path.read_text(), '')

    def test_missing_or_unopenable_path_disables_without_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'nope.jsonl'
            trace = m.DiagnosticTrace(str(path))
            self.assertTrue(trace.disabled)
            # No exception, and secret-laden fields never touch a file.
            trace('input', media='mp4', fixture='other', url='https://secret', host='1.2.3.4')
            self.assertFalse(path.exists())

    def test_elapsed_ms_is_monotonic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.jsonl'; path.write_text(''); path.chmod(0o600)
            trace = m.DiagnosticTrace(str(path))
            trace('stage', stage='connect')
            trace('stage', stage='await-playing')
            rows = [json.loads(l) for l in path.read_text().splitlines() if l]
            self.assertEqual(len(rows), 2)
            self.assertGreaterEqual(rows[1]['t'], rows[0]['t'])


class DiagnosticTraceCapTests(unittest.TestCase):
    def test_row_cap_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.jsonl'; path.write_text(''); path.chmod(0o600)
            trace = m.DiagnosticTrace(str(path))
            for _ in range(1000):
                trace('stage', stage='feedback')
            rows = path.read_text().splitlines()
            self.assertEqual(len(rows), m.MAX_ROWS)
            self.assertEqual(trace.rows, m.MAX_ROWS)

    def test_unknown_event_storm_is_capped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.jsonl'; path.write_text(''); path.chmod(0o600)
            trace = m.DiagnosticTrace(str(path))
            for _ in range(100):
                trace('event', type='other', state='other')
            rows = [json.loads(l) for l in path.read_text().splitlines() if l]
            self.assertEqual(len(rows), m.MAX_UNKNOWN_EVENTS)
            # Known events are still recorded after the unknown storm.
            trace('event', type='playbackState', state='playing')
            rows = [json.loads(l) for l in path.read_text().splitlines() if l]
            self.assertEqual(rows[-1]['type'], 'playbackState')


class NativeOptionsTests(unittest.TestCase):
    def test_disabled_trace_cannot_enable_startup_override(self):
        app = load('app')
        with tempfile.TemporaryDirectory() as directory:
            options = app.native_options({'development': True}, frozen=True,
                environ={'PEARPLAY_DIAGNOSTIC_TRACE': str(Path(directory)/'missing'),
                         'PEARPLAY_DIAGNOSTIC_STARTUP_SECONDS': '30'})
            self.assertEqual(options, (None, None, None, None))

    def test_frozen_package_does_not_require_loose_python_source(self):
        native = load()
        native.__package__ = 'helper'
        native.__file__ = '/nonexistent-frozen-source/helper/native.py'
        from helper import diagnostics
        self.assertIs(native.diagnostics(), diagnostics)

    def test_trace_path_must_be_absolute(self):
        from unittest.mock import patch
        with patch.object(m.os, 'open') as opened:
            trace = m.DiagnosticTrace('relative-trace')
        self.assertTrue(trace.disabled)
        opened.assert_not_called()

    def test_production_and_non_frozen_are_disabled(self):
        app = load('app')
        env = {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/x', 'PEARPLAY_DIAGNOSTIC_STARTUP_SECONDS': '30'}
        self.assertEqual(app.native_options({'extension_id': 'a' * 32}, environ=env, frozen=False), (None, None, None, None))
        self.assertEqual(app.native_options({'extension_id': 'a' * 32, 'development': False}, environ=env, frozen=True), (None, None, None, None))

    def test_development_frozen_enables_trace_and_validated_startup(self):
        app = load('app')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.jsonl'; path.write_text(''); path.chmod(0o600)
            trace, startup, labels, metadata = app.native_options({'development': True, 'extension_id': 'a' * 32},
                                                environ={'PEARPLAY_DIAGNOSTIC_TRACE': str(path),
                                                         'PEARPLAY_DIAGNOSTIC_STARTUP_SECONDS': '30'}, frozen=True)
            self.assertIsNotNone(trace)
            self.assertFalse(trace.disabled)
            self.assertEqual(startup, 30)
            self.assertIsNone(labels)
            self.assertIsNone(metadata)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.jsonl'; path.write_text(''); path.chmod(0o600)
            trace, startup, labels, metadata = app.native_options({'development': True, 'extension_id': 'a' * 32},
                                                environ={'PEARPLAY_DIAGNOSTIC_TRACE': str(path),
                                                         'PEARPLAY_DIAGNOSTIC_STARTUP_SECONDS': '99'}, frozen=True)
            self.assertIsNotNone(trace)
            self.assertEqual(startup, None)
            self.assertIsNone(labels)
            self.assertIsNone(metadata)


class EventErrorNormalizeTests(unittest.TestCase):
    def test_error_event_yields_domain_and_signed_code(self):
        data = {'type': 'playbackError', 'error': {'domain': 'NSURLErrorDomain', 'code': -1004}}
        self.assertEqual(m.normalize_event(data),
                         {'type': 'playbackError', 'state': 'other', 'hasError': True,
                          'domain': 'NSURLErrorDomain', 'code': -1004})

    def test_error_in_params_is_extracted(self):
        data = {'type': 'error', 'params': {'error': {'domain': 'AVFoundationErrorDomain', 'code': 11800}}}
        self.assertEqual(m.normalize_event(data),
                         {'type': 'error', 'state': 'other', 'hasError': True,
                          'domain': 'AVFoundationErrorDomain', 'code': 11800})

    def test_unknown_domain_is_other_and_unrecognized_type_falls_back(self):
        data = {'type': 'secretErrorType', 'error': {'domain': 'PrivateVendorDomain', 'code': -1}}
        self.assertEqual(m.normalize_event(data),
                         {'type': 'other', 'state': 'other', 'hasError': True, 'domain': 'other', 'code': -1})

    def test_non_integer_code_is_dropped_not_coerced(self):
        for code in ('1004', 1.5, True, None, [1], {'c': 1}):
            with self.subTest(code=code):
                result = m.normalize_event({'type': 'error', 'error': {'domain': 'NSURLErrorDomain', 'code': code}})
                self.assertNotIn('code', result)
                self.assertEqual(result['domain'], 'NSURLErrorDomain')
                self.assertEqual(result['hasError'], True)

    def test_code_outside_signed_32_bit_is_dropped(self):
        for code in (2**31, -2**31 - 1, 10**20):
            result = m.normalize_event({'type': 'error', 'error': {'code': code}})
            self.assertNotIn('code', result)
        self.assertIn('code', m.normalize_event({'type': 'error', 'error': {'code': 2**31 - 1}}))
        self.assertIn('code', m.normalize_event({'type': 'error', 'error': {'code': -2**31}}))

    def test_url_request_field_sets_has_url_without_emitting_url(self):
        data = {'type': 'unhandledURLRequest', 'url': 'https://secret.test/a.m3u8?PIN=SECRET'}
        result = m.normalize_event(data)
        self.assertEqual(result['type'], 'unhandledURLRequest')
        self.assertTrue(result['hasUrl'])
        text = json.dumps(result)
        self.assertNotIn('SECRET', text)
        self.assertNotIn('secret.test', text)
        self.assertNotIn('url', result)

    def test_plain_event_stays_backward_compatible(self):
        data = {'type': 'playbackState', 'name': 'playing'}
        self.assertEqual(m.normalize_event(data), {'type': 'playbackState', 'state': 'playing'})

    def test_error_dict_presence_is_flagged_even_without_valid_domain_or_code(self):
        result = m.normalize_event({'type': 'playbackError', 'error': {'message': 'SECRET traceback text'}})
        self.assertEqual(result['type'], 'playbackError')
        self.assertEqual(result['hasError'], True)
        self.assertEqual(result['domain'], 'other')
        self.assertNotIn('code', result)
        self.assertNotIn('message', result)
        self.assertNotIn('SECRET', json.dumps(result))

    def test_deep_list_and_unhashable_error_values_do_not_leak_or_raise(self):
        data = {'type': ['playbackError'], 'error': {'domain': ['NSURLErrorDomain'], 'code': {'c': 1}},
                'params': {'error': {'domain': {'x': 1}, 'code': [1, 2]}}}
        result = m.normalize_event(data)
        self.assertEqual(result['type'], 'other')
        self.assertEqual(result['state'], 'other')
        self.assertEqual(result['hasError'], True)
        self.assertEqual(result['domain'], 'other')
        self.assertNotIn('code', result)

    def test_top_level_error_wins_over_params_error(self):
        data = {'type': 'error',
                'error': {'domain': 'NSURLErrorDomain', 'code': -1004},
                'params': {'error': {'domain': 'AVFoundationErrorDomain', 'code': 11800}}}
        result = m.normalize_event(data)
        self.assertEqual(result['domain'], 'NSURLErrorDomain')
        self.assertEqual(result['code'], -1004)


class AdversarialSanitizeTests(unittest.TestCase):
    def test_new_event_fields_survive_sanitize_independently(self):
        fields = {'type': 'playbackError', 'state': 'interrupted', 'hasError': True,
                  'domain': 'NSURLErrorDomain', 'code': -1004, 'hasUrl': True}
        self.assertEqual(m.sanitize('event', fields),
                         {'k': 'event', 'type': 'playbackError', 'state': 'interrupted',
                          'hasError': True, 'domain': 'NSURLErrorDomain', 'code': -1004, 'hasUrl': True})

    def test_unknown_event_fields_and_secrets_drop_from_sanitize(self):
        row = m.sanitize('event', {'type': 'other', 'state': 'other', 'domain': 'SECRET',
                                   'code': 'SECRET', 'hasError': 'yes', 'hasUrl': 1,
                                   'url': 'https://SECRET', 'name': 'SECRET'})
        self.assertEqual(row, {'k': 'event', 'type': 'other', 'state': 'other'})
        self.assertNotIn('SECRET', json.dumps(row))

    def test_boolean_fields_reject_non_bool(self):
        self.assertNotIn('hasError', m.sanitize('event', {'type': 'other', 'state': 'other', 'hasError': 1}))
        self.assertNotIn('hasUrl', m.sanitize('event', {'type': 'other', 'state': 'other', 'hasUrl': 'true'}))
        self.assertNotIn('hasError', m.sanitize('event', {'type': 'other', 'state': 'other', 'hasError': None}))
        self.assertEqual(m.sanitize('event', {'hasError': True, 'hasUrl': False}),
                         {'k': 'event', 'hasError': True, 'hasUrl': False})

    def test_sanitize_round_trip_is_idempotent(self):
        fields = {'type': 'playbackError', 'state': 'other', 'hasError': True,
                  'domain': 'AirPlayErrorDomain', 'code': -2**31, 'hasUrl': False}
        once = m.sanitize('event', fields)
        twice = m.sanitize('event', once)
        self.assertEqual(once, twice)

    def test_recognized_error_type_is_not_capped_as_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.jsonl'; path.write_text(''); path.chmod(0o600)
            trace = m.DiagnosticTrace(str(path))
            for _ in range(50):
                trace('event', type='playbackError', state='other', hasError=True,
                      domain='NSURLErrorDomain', code=-1004)
            rows = [json.loads(l) for l in path.read_text().splitlines() if l]
            self.assertEqual(len(rows), 50)
            self.assertEqual(rows[0]['domain'], 'NSURLErrorDomain')
            self.assertEqual(rows[0]['code'], -1004)


class EventLabelTests(unittest.TestCase):
    def test_unknown_alphabetic_label_is_extracted(self):
        self.assertEqual(m.event_label({'type': 'mediaItemChanged'}), 'mediaItemChanged')
        self.assertEqual(m.event_label({'type': 'rateChange'}), 'rateChange')

    def test_known_event_types_are_rejected(self):
        for known in m.EVENT_TYPES:
            self.assertIsNone(m.event_label({'type': known}))

    def test_non_string_type_is_rejected(self):
        for bad in (None, 42, True, ['x'], {'x': 1}):
            self.assertIsNone(m.event_label({'type': bad}))

    def test_non_dict_data_is_rejected(self):
        for bad in (None, 'playbackState', 42, ['x']):
            self.assertIsNone(m.event_label(bad))

    def test_digits_punct_whitespace_unicode_and_overlength_are_rejected(self):
        for bad in ('playbackState2', 'playback-state', 'Playback State', 'playback_state',
                    'café', 'é', '', ' ' * 5, 'A' * 49):
            self.assertIsNone(m.event_label({'type': bad}))

    def test_max_length_48_is_accepted(self):
        self.assertEqual(m.event_label({'type': 'A' * 48}), 'A' * 48)
        self.assertIsNone(m.event_label({'type': 'A' * 49}))

    def test_uppercase_and_lowercase_letters_are_accepted(self):
        self.assertEqual(m.event_label({'type': 'aBcDeF'}), 'aBcDeF')


class EventLabelCollectorTests(unittest.TestCase):
    def write_labels(self, path, *events):
        collector = m.EventLabelCollector(str(path))
        for data in events:
            collector(data)
        return collector

    def test_owner_only_regular_file_is_accepted_and_single_field_rows_written(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'labels.jsonl'
            path.write_text(''); path.chmod(0o600)
            collector = self.write_labels(path, {'type': 'mediaItemChanged'})
            self.assertFalse(collector.disabled)
            rows = [json.loads(l) for l in path.read_text().splitlines() if l]
            self.assertEqual(rows, [{'eventType': 'mediaItemChanged'}])
            self.assertEqual(set(rows[0]), {'eventType'})

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            real = Path(directory) / 'real'; real.write_text(''); real.chmod(0o600)
            link = Path(directory) / 'link'; link.symlink_to(real)
            collector = m.EventLabelCollector(str(link))
            self.assertTrue(collector.disabled)
            collector({'type': 'mediaItemChanged'})
            self.assertEqual(real.read_text(), '')

    def test_world_readable_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'labels.jsonl'
            path.write_text(''); path.chmod(0o644)
            collector = self.write_labels(path, {'type': 'mediaItemChanged'})
            self.assertTrue(collector.disabled)
            self.assertEqual(path.read_text(), '')

    def test_missing_or_unopenable_path_disables_without_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'nope.jsonl'
            collector = m.EventLabelCollector(str(path))
            self.assertTrue(collector.disabled)
            collector({'type': 'mediaItemChanged'})
            self.assertFalse(path.exists())

    def test_relative_path_disables_without_opening(self):
        from unittest.mock import patch
        with patch.object(m.os, 'open') as opened:
            collector = m.EventLabelCollector('relative-labels')
        self.assertTrue(collector.disabled)
        opened.assert_not_called()

    def test_labels_are_deduplicated_and_capped_at_16(self):
        def alpha(n):
            out = ''
            n += 1
            while n:
                n, r = divmod(n - 1, 26)
                out = chr(ord('A') + r) + out
            return out
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'labels.jsonl'; path.write_text(''); path.chmod(0o600)
            collector = m.EventLabelCollector(str(path))
            labels = [alpha(i) for i in range(30)]
            for lab in labels:
                collector({'type': lab})
            rows = [json.loads(l) for l in path.read_text().splitlines() if l]
            self.assertEqual(len(rows), m.MAX_LABELS)
            self.assertEqual([r['eventType'] for r in rows], labels[:16])
            self.assertEqual(collector.count, m.MAX_LABELS)

    def test_duplicate_labels_are_written_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'labels.jsonl'; path.write_text(''); path.chmod(0o600)
            collector = self.write_labels(path, {'type': 'MediaItemChanged'}, {'type': 'MediaItemChanged'})
            rows = [json.loads(l) for l in path.read_text().splitlines() if l]
            self.assertEqual([r['eventType'] for r in rows], ['MediaItemChanged'])

    def test_known_types_and_bad_values_never_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'labels.jsonl'; path.write_text(''); path.chmod(0o600)
            collector = self.write_labels(path,
                {'type': 'playbackState'}, {'type': 'other'}, {'type': 'error'},
                {'type': 'bad-label'}, {'type': '123'}, {'type': None}, {'type': 'café'},
                {'name': 'playing'}, 'not-a-dict', None)
            self.assertEqual(path.read_text(), '')
            self.assertEqual(collector.count, 0)

    def test_no_raw_values_leak_into_label_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'labels.jsonl'; path.write_text(''); path.chmod(0o600)
            collector = self.write_labels(path,
                {'type': 'mediaItemChanged', 'name': 'playing', 'url': 'https://SECRET',
                 'params': {'playbackState': 'playing', 'url': 'http://evil/secret'},
                 'token': 'PRIVATE'})
            text = path.read_text()
            self.assertIn('mediaItemChanged', text)
            for secret in ('SECRET', 'PRIVATE', 'http://evil', 'playing', 'url', 'token', 'params'):
                self.assertNotIn(secret, text)


class ResolveEventLabelsTests(unittest.TestCase):
    def test_production_and_non_frozen_ignore_labels(self):
        env = {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/t', 'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': '/tmp/l'}
        self.assertIsNone(m.resolve_event_labels(env, frozen=False, development=True))
        self.assertIsNone(m.resolve_event_labels(env, frozen=True, development=False))
        self.assertIsNone(m.resolve_event_labels(env, frozen=False, development=False))

    def test_requires_active_trace(self):
        env = {'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': '/tmp/l'}
        self.assertIsNone(m.resolve_event_labels(env, frozen=True, development=True))

    def test_development_frozen_with_trace_returns_labels_path(self):
        env = {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/t', 'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': '/tmp/l'}
        self.assertEqual(m.resolve_event_labels(env, frozen=True, development=True), '/tmp/l')

    def test_empty_or_missing_labels_env_is_none(self):
        self.assertIsNone(m.resolve_event_labels(
            {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/t', 'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': ''},
            frozen=True, development=True))
        self.assertIsNone(m.resolve_event_labels(
            {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/t'}, frozen=True, development=True))


class EventLabelNativeOptionsTests(unittest.TestCase):
    def test_development_frozen_resolves_labels_when_sidecar_present(self):
        app = load('app')
        with tempfile.TemporaryDirectory() as directory:
            trace_path = Path(directory) / 'trace.jsonl'; trace_path.write_text(''); trace_path.chmod(0o600)
            labels_path = Path(directory) / 'labels.jsonl'; labels_path.write_text(''); labels_path.chmod(0o600)
            trace, startup, labels, metadata = app.native_options({'development': True, 'extension_id': 'a' * 32},
                environ={'PEARPLAY_DIAGNOSTIC_TRACE': str(trace_path),
                         'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': str(labels_path)}, frozen=True)
            self.assertIsNotNone(trace)
            self.assertIsNotNone(labels)
            self.assertFalse(labels.disabled)
            self.assertIsNone(metadata)

    def test_production_never_resolves_labels(self):
        app = load('app')
        env = {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/x', 'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': '/tmp/l'}
        self.assertEqual(app.native_options({'extension_id': 'a' * 32}, environ=env, frozen=False), (None, None, None, None))

    def test_labels_require_active_trace(self):
        app = load('app')
        env = {'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': '/tmp/l'}
        self.assertEqual(app.native_options({'development': True, 'extension_id': 'a' * 32},
                                            environ=env, frozen=True), (None, None, None, None))


if __name__ == '__main__':
    unittest.main()
