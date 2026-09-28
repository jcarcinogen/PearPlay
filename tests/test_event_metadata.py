"""Observation-only private receiver event-metadata capture (stdlib, no pyatv)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from test_helper_protocol import load

m = load('diagnostics')


class EventMetadataNormalizationTests(unittest.TestCase):
    def test_only_notification_events_are_captured(self):
        self.assertIsNone(m.event_metadata({'type': 'playbackState', 'name': 'playing'}))
        self.assertIsNone(m.event_metadata({'type': 'error', 'error': {'code': 1}}))
        self.assertIsNone(m.event_metadata({'name': 'playing'}))
        self.assertIsNone(m.event_metadata(None))
        self.assertIsNone(m.event_metadata('notification'))
        self.assertIsNone(m.event_metadata(['notification']))
        self.assertIsNotNone(m.event_metadata({'type': 'notification', 'name': 'playing'}))

    def test_name_and_kind_captured_when_alphabetic(self):
        self.assertEqual(m.event_metadata({'type': 'notification', 'name': 'playing', 'kind': 'media'}),
                         {'name': 'playing', 'kind': 'media'})

    def test_missing_name_and_kind_are_marked_not_omitted(self):
        self.assertEqual(m.event_metadata({'type': 'notification'}), {'name': 'missing', 'kind': 'missing'})
        self.assertEqual(m.event_metadata({'type': 'notification', 'kind': 'media'}),
                         {'name': 'missing', 'kind': 'media'})

    def test_non_string_name_kind_are_marked_invalid(self):
        self.assertEqual(m.event_metadata({'type': 'notification', 'name': 42, 'kind': None}),
                         {'name': 'invalid', 'kind': 'invalid'})
        self.assertEqual(m.event_metadata({'type': 'notification', 'name': ['x'], 'kind': {'k': 1}}),
                         {'name': 'invalid', 'kind': 'invalid'})

    def test_non_alphabetic_name_kind_are_marked_filtered(self):
        for bad in ('play-ing', 'play_ing', 'Play Ing', 'café', '', 'A' * 49, 'playback2', 'play.back'):
            self.assertEqual(m.event_metadata({'type': 'notification', 'name': bad})['name'], 'filtered', bad)

    def test_max_length_48_boundary(self):
        self.assertEqual(m.event_metadata({'type': 'notification', 'name': 'A' * 48})['name'], 'A' * 48)
        self.assertEqual(m.event_metadata({'type': 'notification', 'name': 'A' * 49})['name'], 'filtered')

    def test_error_domain_and_signed_code_extracted(self):
        self.assertEqual(m.event_metadata({'type': 'notification',
                                           'error': {'domain': 'NSURLErrorDomain', 'code': -1004}}),
                         {'name': 'missing', 'kind': 'missing',
                          'domain': 'NSURLErrorDomain', 'code': -1004})
        self.assertEqual(m.event_metadata({'type': 'notification',
                                           'params': {'error': {'domain': 'AVFoundationErrorDomain', 'code': 11800}}}),
                         {'name': 'missing', 'kind': 'missing',
                          'domain': 'AVFoundationErrorDomain', 'code': 11800})

    def test_unknown_domain_is_other_and_bad_code_is_dropped(self):
        result = m.event_metadata({'type': 'notification',
                                   'error': {'domain': 'PrivateVendorDomain', 'code': '1004'}})
        self.assertEqual(result['domain'], 'other')
        self.assertNotIn('code', result)

    def test_code_outside_signed_32_bit_is_dropped(self):
        for code in (2**31, -2**31 - 1, 10**20, 1.5, True):
            result = m.event_metadata({'type': 'notification',
                                       'error': {'domain': 'NSURLErrorDomain', 'code': code}})
            self.assertNotIn('code', result, code)
        self.assertEqual(m.event_metadata({'type': 'notification',
                                           'error': {'code': 2**31 - 1}})['code'], 2**31 - 1)

    def test_top_level_error_wins_over_params_error(self):
        result = m.event_metadata({'type': 'notification',
                                   'error': {'domain': 'NSURLErrorDomain', 'code': -1004},
                                   'params': {'error': {'domain': 'AVFoundationErrorDomain', 'code': 11800}}})
        self.assertEqual(result['domain'], 'NSURLErrorDomain')
        self.assertEqual(result['code'], -1004)

    def test_no_raw_values_or_secrets_leak(self):
        data = {'type': 'notification', 'name': 'playing', 'kind': 'media',
                'url': 'https://SECRET', 'token': 'PRIVATE',
                'params': {'url': 'http://evil', 'body': 'BODY', 'credentials': 'CRED'}}
        result = m.event_metadata(data)
        text = json.dumps(result)
        for secret in ('SECRET', 'PRIVATE', 'http://evil', 'BODY', 'CRED',
                       'url', 'token', 'body', 'credentials', 'params'):
            self.assertNotIn(secret, text)
        self.assertEqual(set(result), {'name', 'kind'})


class EventMetadataCollectorTests(unittest.TestCase):
    def write_rows(self, path, *events):
        collector = m.EventMetadataCollector(str(path))
        for data in events:
            collector(data)
        return collector

    def test_owner_only_regular_file_is_accepted_and_row_written(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meta.jsonl'
            path.write_text(''); path.chmod(0o600)
            collector = self.write_rows(path, {'type': 'notification', 'name': 'playing', 'kind': 'media'})
            self.assertFalse(collector.disabled)
            rows = [json.loads(l) for l in path.read_text().splitlines() if l]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['seq'], 0)
            self.assertEqual(rows[0]['name'], 'playing')
            self.assertEqual(rows[0]['kind'], 'media')
            self.assertIsInstance(rows[0]['t'], int)
            self.assertGreaterEqual(rows[0]['t'], 0)

    def test_non_notification_events_never_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meta.jsonl'; path.write_text(''); path.chmod(0o600)
            collector = self.write_rows(path,
                {'type': 'playbackState', 'name': 'playing'},
                {'type': 'mediaItemChanged', 'name': 'playing'},
                'not-a-dict', None, {'name': 'playing'})
            self.assertEqual(path.read_text(), '')

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            real = Path(directory) / 'real'; real.write_text(''); real.chmod(0o600)
            link = Path(directory) / 'link'; link.symlink_to(real)
            collector = m.EventMetadataCollector(str(link))
            self.assertTrue(collector.disabled)
            collector({'type': 'notification', 'name': 'playing', 'kind': 'media'})
            self.assertEqual(real.read_text(), '')

    def test_world_readable_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meta.jsonl'; path.write_text(''); path.chmod(0o644)
            collector = self.write_rows(path, {'type': 'notification', 'name': 'playing', 'kind': 'media'})
            self.assertTrue(collector.disabled)
            self.assertEqual(path.read_text(), '')

    def test_missing_path_disables_without_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'nope.jsonl'
            collector = m.EventMetadataCollector(str(path))
            self.assertTrue(collector.disabled)
            collector({'type': 'notification', 'name': 'playing', 'kind': 'media'})
            self.assertFalse(path.exists())

    def test_relative_path_disables_without_opening(self):
        from unittest.mock import patch
        with patch.object(m.os, 'open') as opened:
            collector = m.EventMetadataCollector('relative-meta')
        self.assertTrue(collector.disabled)
        opened.assert_not_called()

    def test_file_cap_is_max_events(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meta.jsonl'; path.write_text(''); path.chmod(0o600)
            collector = m.EventMetadataCollector(str(path))
            for _ in range(200):
                collector({'type': 'notification', 'name': 'event', 'kind': 'media'})
            rows = [json.loads(l) for l in path.read_text().splitlines() if l]
            self.assertEqual(len(rows), m.MAX_METADATA_EVENTS)
            self.assertEqual(rows[-1]['seq'], m.MAX_METADATA_EVENTS - 1)

    def test_seq_is_global_across_collectors_and_t_is_relative(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meta.jsonl'; path.write_text(''); path.chmod(0o600)
            a = m.EventMetadataCollector(str(path))
            b = m.EventMetadataCollector(str(path))
            try:
                a({'type': 'notification', 'name': 'one', 'kind': 'media'})
                b({'type': 'notification', 'name': 'two', 'kind': 'media'})
                a({'type': 'notification', 'name': 'three', 'kind': 'media'})
                rows = [json.loads(l) for l in path.read_text().splitlines() if l]
                self.assertEqual([r['seq'] for r in rows], [0, 1, 2])
                self.assertEqual([r['name'] for r in rows], ['one', 'two', 'three'])
                for r in rows:
                    self.assertGreaterEqual(r['t'], 0)
            finally:
                for c in (a, b):
                    if c._fd is not None:
                        os.close(c._fd)

    def test_preexisting_invalid_row_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meta.jsonl'
            path.write_text(json.dumps({'seq': 0, 't': 0, 'name': 'SECRET-VALUE', 'kind': 'media'}) + '\n')
            path.chmod(0o600)
            collector = m.EventMetadataCollector(str(path))
            self.assertFalse(collector.disabled)
            collector({'type': 'notification', 'name': 'good', 'kind': 'media'})
            self.assertTrue(collector.disabled)
            self.assertIn('SECRET-VALUE', path.read_text())

    def test_preexisting_extra_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meta.jsonl'
            path.write_text(json.dumps({'seq': 0, 't': 0, 'name': 'good', 'kind': 'media', 'pid': 9999}) + '\n')
            path.chmod(0o600)
            collector = m.EventMetadataCollector(str(path))
            collector({'type': 'notification', 'name': 'good', 'kind': 'media'})
            self.assertTrue(collector.disabled)

    def test_oversized_file_disables_on_byte_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meta.jsonl'
            path.write_bytes(b' ' * (m.MAX_METADATA_BYTES + 100))
            path.chmod(0o600)
            collector = m.EventMetadataCollector(str(path))
            collector({'type': 'notification', 'name': 'x', 'kind': 'y'})
            self.assertTrue(collector.disabled)

    def test_append_cannot_cross_byte_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meta.jsonl'
            row = json.dumps({'seq': 0, 't': 0, 'name': 'good', 'kind': 'media'})
            content = row + ' ' * (m.MAX_METADATA_BYTES - len(row) - 2) + '\n'
            path.write_text(content); path.chmod(0o600)
            collector = m.EventMetadataCollector(str(path))
            try:
                collector({'type': 'notification', 'name': 'next', 'kind': 'media'})
                self.assertLessEqual(path.stat().st_size, m.MAX_METADATA_BYTES)
                self.assertEqual(path.read_text(), content)
                self.assertTrue(collector.disabled)
            finally:
                if collector._fd is not None:
                    os.close(collector._fd)

    def test_rows_contain_no_process_identifiers_or_raw_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meta.jsonl'; path.write_text(''); path.chmod(0o600)
            collector = m.EventMetadataCollector(str(path))
            collector({'type': 'notification', 'name': 'playing', 'kind': 'media',
                       'url': 'https://SECRET', 'pid': 1234, 'session': 'KEY', 'token': 'PRIVATE'})
            text = path.read_text()
            for secret in ('SECRET', 'PRIVATE', 'KEY', 'url', 'pid', 'session', 'token'):
                self.assertNotIn(secret, text)
            row = json.loads(text)
            self.assertEqual(set(row), {'seq', 't', 'name', 'kind'})

    def test_collector_writes_only_notification_error_rows_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meta.jsonl'; path.write_text(''); path.chmod(0o600)
            collector = self.write_rows(path,
                {'type': 'notification', 'name': 'playing', 'kind': 'media',
                 'error': {'domain': 'NSURLErrorDomain', 'code': -1004}})
            row = json.loads(path.read_text())
            self.assertEqual(row['domain'], 'NSURLErrorDomain')
            self.assertEqual(row['code'], -1004)


class ResolveEventMetadataTests(unittest.TestCase):
    def test_production_and_non_frozen_ignore_metadata(self):
        env = {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/t', 'PEARPLAY_DIAGNOSTIC_EVENT_METADATA': '/tmp/m'}
        self.assertIsNone(m.resolve_event_metadata(env, frozen=False, development=True))
        self.assertIsNone(m.resolve_event_metadata(env, frozen=True, development=False))
        self.assertIsNone(m.resolve_event_metadata(env, frozen=False, development=False))

    def test_requires_active_trace(self):
        env = {'PEARPLAY_DIAGNOSTIC_EVENT_METADATA': '/tmp/m'}
        self.assertIsNone(m.resolve_event_metadata(env, frozen=True, development=True))

    def test_development_frozen_with_trace_returns_metadata_path(self):
        env = {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/t', 'PEARPLAY_DIAGNOSTIC_EVENT_METADATA': '/tmp/m'}
        self.assertEqual(m.resolve_event_metadata(env, frozen=True, development=True), '/tmp/m')

    def test_empty_or_missing_metadata_env_is_none(self):
        self.assertIsNone(m.resolve_event_metadata(
            {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/t', 'PEARPLAY_DIAGNOSTIC_EVENT_METADATA': ''},
            frozen=True, development=True))
        self.assertIsNone(m.resolve_event_metadata(
            {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/t'}, frozen=True, development=True))


class EventMetadataNativeOptionsTests(unittest.TestCase):
    def test_development_frozen_resolves_metadata_when_sidecar_present(self):
        app = load('app')
        with tempfile.TemporaryDirectory() as directory:
            trace_path = Path(directory) / 'trace.jsonl'; trace_path.write_text(''); trace_path.chmod(0o600)
            meta_path = Path(directory) / 'meta.jsonl'; meta_path.write_text(''); meta_path.chmod(0o600)
            trace, startup, labels, metadata = app.native_options(
                {'development': True, 'extension_id': 'a' * 32},
                environ={'PEARPLAY_DIAGNOSTIC_TRACE': str(trace_path),
                         'PEARPLAY_DIAGNOSTIC_EVENT_METADATA': str(meta_path)}, frozen=True)
            self.assertIsNotNone(trace)
            self.assertIsNone(labels)
            self.assertIsNotNone(metadata)
            self.assertFalse(metadata.disabled)

    def test_metadata_requires_active_trace(self):
        app = load('app')
        env = {'PEARPLAY_DIAGNOSTIC_EVENT_METADATA': '/tmp/m'}
        self.assertEqual(app.native_options({'development': True, 'extension_id': 'a' * 32},
                                            environ=env, frozen=True), (None, None, None, None))

    def test_production_never_resolves_metadata(self):
        app = load('app')
        env = {'PEARPLAY_DIAGNOSTIC_TRACE': '/tmp/x', 'PEARPLAY_DIAGNOSTIC_EVENT_METADATA': '/tmp/m'}
        self.assertEqual(app.native_options({'extension_id': 'a' * 32}, environ=env, frozen=False),
                         (None, None, None, None))


if __name__ == '__main__':
    unittest.main()
