import importlib.util
from pathlib import Path
import tempfile
import unittest


PATH = Path(__file__).resolve().parents[1] / 'scripts/hls_diagnostic.py'


def load():
    spec = importlib.util.spec_from_file_location('hls_launcher', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HLSLauncher(unittest.TestCase):
    def test_control_page_has_exact_master_and_no_other_media(self):
        self.assertTrue(PATH.exists(), 'diagnostic launcher missing')
        m = load()
        page = m.control_page(10)
        self.assertIn('src="https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"', page)
        self.assertEqual(page.count('<video '), 1)
        self.assertNotIn('<script', page)
        self.assertIn('10 seconds', page)
        self.assertIn('30 seconds', m.control_page(30))
        self.assertIn('browser may not play', page)
        self.assertIn('PIN', page)

    def test_controls_select_one_exact_public_source_without_changing_runtime(self):
        m = load()
        self.assertEqual(m.options(['--media', 'mp4']).media, 'mp4')
        self.assertEqual(m.options(['--media', 'hls-direct']).media, 'hls-direct')
        self.assertEqual(m.options([]).media, 'hls-master')
        mp4 = m.control_page(30, 'mp4')
        direct = m.control_page(30, 'hls-direct')
        self.assertIn('src="https://media.w3.org/2010/05/bunny/trailer.mp4"', mp4)
        self.assertNotIn('x36xhzz.m3u8', mp4)
        self.assertIn('src="https://test-streams.mux.dev/x36xhzz/url_6/193039199_mp4_h264_aac_hq_7.m3u8"', direct)
        self.assertNotIn('src="https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"', direct)
        for page in (mp4, direct):
            self.assertEqual(page.count('<video '), 1)
            self.assertNotIn('<script', page)
            self.assertIn('30 seconds', page)
        with self.assertRaises(ValueError):
            m.control_page(30, 'https://untrusted.invalid/')

    def test_report_export_uses_schema_and_never_copies_raw_rows(self):
        import json
        m = load()
        raw = '\n'.join([json.dumps({'k': 'event', 't': 10, 'type': 'playbackState', 'state': 'playing', 'url': 'SECRET'}),
                         json.dumps({'k': 'SECRET', 't': 20, 'state': 'SECRET'}),
                         json.dumps({'k': 'stage', 't': 30, 'stage': 'SECRET', 'code': 200}),
                         'bad SECRET json'])
        self.assertTrue(hasattr(m, 'safe_rows'), 'sanitized report exporter missing')
        rows = m.safe_rows(raw)
        self.assertNotIn('SECRET', json.dumps(rows))
        self.assertEqual(rows[0], {'k': 'event', 't': 10, 'type': 'playbackState', 'state': 'playing'})
        self.assertEqual(len(rows), 2)

    def test_new_safe_fields_survive_safe_rows_while_secrets_drop(self):
        import json
        m = load()
        raw = '\n'.join([
            json.dumps({'k': 'event', 't': 10, 'type': 'playbackError', 'state': 'other',
                        'hasError': True, 'domain': 'NSURLErrorDomain', 'code': -1004, 'hasUrl': True,
                        'url': 'https://SECRET', 'name': 'SECRET', 'token': 'SECRET'}),
            json.dumps({'k': 'event', 't': 20, 'type': 'other', 'state': 'other',
                        'domain': 'SECRET', 'code': 'SECRET', 'hasError': 'yes', 'hasUrl': 1}),
        ])
        rows = m.safe_rows(raw)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {'k': 'event', 't': 10, 'type': 'playbackError', 'state': 'other',
                                   'hasError': True, 'domain': 'NSURLErrorDomain', 'code': -1004, 'hasUrl': True})
        self.assertEqual(rows[1], {'k': 'event', 't': 20, 'type': 'other', 'state': 'other'})
        self.assertNotIn('SECRET', json.dumps(rows))

    def test_trial_options_only_allow_separate_10_and_30_second_runs(self):
        self.assertTrue(PATH.exists(), 'diagnostic launcher missing')
        m = load()
        self.assertEqual(m.options([]).startup_seconds, 10)
        self.assertEqual(m.options(['--startup-seconds', '30']).startup_seconds, 30)
        self.assertTrue(m.options(['--check']).check)
        import contextlib
        import io
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            m.options(['--startup-seconds', '999'])


class OriginControls(unittest.TestCase):
    RFC1918 = [
        'http://10.0.0.0:1',
        'http://10.255.255.255:65535',
        'http://172.16.0.0:1',
        'http://172.31.255.255:65535',
        'http://192.168.0.0:1',
        'http://192.168.255.255:65535',
        'http://192.168.50.69:18765',
    ]

    MALFORMED = [
        '192.168.50.69:18765',              # no scheme
        'https://192.168.50.69:18765',      # wrong scheme
        'HTTP://192.168.50.69:18765',       # uppercase scheme
        'http://user@192.168.50.69:18765',  # userinfo
        'http://user:pass@192.168.50.69:18765',
        'http://192.168.50.69:18765?x=1',   # query
        'http://192.168.50.69:18765#frag',  # fragment
        'http://192.168.50.69:18765/path',  # path
        'http://192.168.50.69:18765/',      # trailing slash
        'http://192.168.50.69:18765\n',     # newline
        'http://192.168.50.69:18\n765',
        'http://192.168.50.69:18765"',      # quote
        'http://192.168.50.69:18"765',
        'http://192.168.50.69:18 765',      # space
        'http://8.8.8.8:80',                # public
        'http://1.1.1.1:443',
        'http://100.64.0.1:80',             # CGNAT
        'http://172.15.255.255:80',         # just below 172.16/12
        'http://172.32.0.1:80',             # just above 172.31
        'http://127.0.0.1:80',              # loopback
        'http://169.254.0.1:80',            # link-local
        'http://192.168.50.69:0',           # port 0
        'http://192.168.50.69:65536',       # port too high
        'http://192.168.50.69:',            # empty port
        'http://192.168.50.69',             # no port
        'http://192.168.50.69:80:90',       # extra colon
        'http://192.168.50.999:80',         # octet > 255
        'http://192.168.50:80',             # 3 octets
        'http://192.168.50.69.1:80',        # 5 octets
        'http://192.168.050.69:80',         # leading-zero octet
        'http://192.168.50.69:080',         # leading-zero port
        'http://:80',                       # empty host
    ]

    def _err(self, argv):
        import contextlib
        import io
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            load().options(argv)

    def test_origin_controls_require_origin(self):
        for media in ('origin-mp4', 'origin-hls'):
            self._err(['--media', media])

    def test_origin_controls_accept_and_preserve_rfc1918_origin(self):
        m = load()
        for origin in self.RFC1918:
            for media in ('origin-mp4', 'origin-hls'):
                args = m.options(['--media', media, '--origin', origin])
                self.assertEqual(args.media, media)
                self.assertEqual(args.origin, origin)

    def test_origin_controls_reject_malformed_origin(self):
        for origin in self.MALFORMED:
            for media in ('origin-mp4', 'origin-hls'):
                self._err(['--media', media, '--origin', origin])

    def test_origin_rejected_for_public_controls(self):
        for media in ('hls-master', 'mp4', 'hls-direct'):
            self._err(['--media', media, '--origin', 'http://192.168.50.69:18765'])
        self._err(['--origin', 'http://192.168.50.69:18765'])  # default media

    def test_control_source_returns_exact_origin_url(self):
        m = load()
        self.assertEqual(m.control_source('origin-mp4', 'http://192.168.50.69:18765'),
                         'http://192.168.50.69:18765/clip.mp4')
        self.assertEqual(m.control_source('origin-hls', 'http://10.0.0.1:80'),
                         'http://10.0.0.1:80/index.m3u8')
        self.assertEqual(m.control_source('hls-master'), 'https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8')
        self.assertEqual(m.control_source('mp4'), 'https://media.w3.org/2010/05/bunny/trailer.mp4')

    def test_control_source_rejects_bad_origin_and_origin_for_public(self):
        m = load()
        with self.assertRaises(ValueError):
            m.control_source('origin-mp4')
        with self.assertRaises(ValueError):
            m.control_source('origin-mp4', 'http://8.8.8.8:80')
        with self.assertRaises(ValueError):
            m.control_source('origin-hls', 'http://192.168.50.69:0')
        with self.assertRaises(ValueError):
            m.control_source('mp4', 'http://192.168.50.69:18765')
        with self.assertRaises(ValueError):
            m.control_source('bogus')

    def test_origin_control_page_has_exact_one_video_and_same_clip_claim(self):
        m = load()
        mp4 = m.control_page(10, 'origin-mp4', 'http://192.168.50.69:18765')
        self.assertEqual(mp4.count('<video '), 1)
        self.assertIn('src="http://192.168.50.69:18765/clip.mp4"', mp4)
        self.assertIn('controlled MP4', mp4)
        self.assertIn('same clip', mp4)
        self.assertNotIn('public media source', mp4)
        self.assertNotIn('<script', mp4)
        hls = m.control_page(30, 'origin-hls', 'http://10.0.0.1:80')
        self.assertEqual(hls.count('<video '), 1)
        self.assertIn('src="http://10.0.0.1:80/index.m3u8"', hls)
        self.assertIn('controlled HLS', hls)
        self.assertIn('same clip', hls)
        self.assertNotIn('public media source', hls)
        self.assertNotIn('<script', hls)

    def test_origin_control_page_rejects_invalid_origin(self):
        m = load()
        with self.assertRaises(ValueError):
            m.control_page(10, 'origin-mp4')
        with self.assertRaises(ValueError):
            m.control_page(10, 'origin-mp4', 'http://8.8.8.8:80')
        with self.assertRaises(ValueError):
            m.control_page(10, 'origin-hls', 'http://192.168.50.69:0')

    def test_report_control_identifier_never_embeds_origin(self):
        m = load()
        for media, ident in (('origin-mp4', 'origin-mp4'), ('origin-hls', 'origin-hls')):
            args = m.options(['--media', media, '--origin', 'http://192.168.50.69:18765'])
            self.assertEqual(args.media, ident)
            self.assertNotIn('192.168.50.69', args.media)
            self.assertNotIn('18765', args.media)


class CaptureEventLabelsOptions(unittest.TestCase):
    def test_environment_cannot_enable_capture_without_explicit_path(self):
        m = load()
        source = {'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': '/unapproved', 'KEEP': 'yes'}
        self.assertEqual(m.event_labels_environment(source, None), {'KEEP': 'yes'})
        self.assertEqual(m.event_labels_environment(source, Path('/approved')),
                         {'KEEP': 'yes', 'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': '/approved'})
        self.assertEqual(source['PEARPLAY_DIAGNOSTIC_EVENT_LABELS'], '/unapproved')

    def _err(self, argv):
        import contextlib
        import io
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            load().options(argv)

    def test_flag_defaults_false(self):
        self.assertFalse(load().options([]).capture_event_labels)

    def test_flag_requires_origin_media(self):
        for media in ('hls-master', 'mp4', 'hls-direct'):
            self._err(['--media', media, '--capture-event-labels'])
        self._err(['--capture-event-labels'])  # default media

    def test_flag_accepted_with_origin_media(self):
        m = load()
        for media in ('origin-mp4', 'origin-hls'):
            args = m.options(['--media', media, '--origin', 'http://192.168.50.69:18765', '--capture-event-labels'])
            self.assertTrue(args.capture_event_labels)


class CaptureEventLabelsPathTests(unittest.TestCase):
    def test_creates_owner_only_regular_file(self):
        import os
        import stat
        with tempfile.TemporaryDirectory() as home:
            path = load().capture_event_labels_path(Path(home))
            self.assertIsNotNone(path)
            self.assertTrue(path.exists())
            info = path.stat()
            self.assertTrue(stat.S_ISREG(info.st_mode))
            self.assertEqual(info.st_mode & 0o777, 0o600)
            self.assertEqual(info.st_uid, os.geteuid())
            self.assertIn('event-labels-', path.name)
            self.assertEqual(path.parent, Path(home) / '.cache' / 'pearplay-diagnostics')

    def test_symlink_parent_is_refused(self):
        with tempfile.TemporaryDirectory() as home:
            real = Path(home) / 'real-dir'; real.mkdir(mode=0o700)
            link = Path(home) / '.cache'; link.symlink_to(home, target_is_directory=True)
            self.assertIsNone(load().capture_event_labels_path(Path(home)))

    def test_group_or_world_readable_parent_is_refused(self):
        with tempfile.TemporaryDirectory() as home:
            cache = Path(home) / '.cache' / 'pearplay-diagnostics'
            cache.mkdir(parents=True, mode=0o755)
            self.assertIsNone(load().capture_event_labels_path(Path(home)))

    def test_missing_parent_is_created_then_file_written(self):
        with tempfile.TemporaryDirectory() as home:
            path = load().capture_event_labels_path(Path(home))
            self.assertIsNotNone(path)
            self.assertTrue(path.parent.is_dir())


class EventLabelRedactionTests(unittest.TestCase):
    def test_event_type_labels_never_exported_in_report(self):
        import json
        m = load()
        raw = '\n'.join([
            json.dumps({'k': 'event', 't': 10, 'type': 'other', 'state': 'other', 'eventType': 'SomeUnknownLabel'}),
            json.dumps({'k': 'event', 't': 20, 'type': 'other', 'state': 'other', 'eventType': 'Another'}),
        ])
        rows = m.safe_rows(raw)
        self.assertEqual(len(rows), 2)
        self.assertNotIn('eventType', json.dumps(rows))
        self.assertNotIn('SomeUnknownLabel', json.dumps(rows))
        self.assertNotIn('Another', json.dumps(rows))
        self.assertEqual(rows[0], {'k': 'event', 't': 10, 'type': 'other', 'state': 'other'})


class CaptureEventMetadataOptions(unittest.TestCase):
    def _err(self, argv):
        import contextlib
        import io
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            load().options(argv)

    def test_flag_defaults_false(self):
        self.assertFalse(load().options([]).capture_event_metadata)

    def test_flag_requires_origin_media(self):
        for media in ('hls-master', 'mp4', 'hls-direct'):
            self._err(['--media', media, '--capture-event-metadata'])
        self._err(['--capture-event-metadata'])

    def test_flag_accepted_with_origin_media(self):
        m = load()
        for media in ('origin-mp4', 'origin-hls'):
            args = m.options(['--media', media, '--origin', 'http://192.168.50.69:18765', '--capture-event-metadata'])
            self.assertTrue(args.capture_event_metadata)
            self.assertFalse(args.capture_event_labels)

    def test_flags_are_mutually_exclusive(self):
        self._err(['--media', 'origin-hls', '--origin', 'http://192.168.50.69:18765',
                   '--capture-event-labels', '--capture-event-metadata'])


class CaptureEnvironmentTests(unittest.TestCase):
    def test_capture_environment_strips_both_opt_ins(self):
        m = load()
        source = {'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': '/unapproved-l',
                  'PEARPLAY_DIAGNOSTIC_EVENT_METADATA': '/unapproved-m', 'KEEP': 'yes'}
        self.assertEqual(m.capture_environment(source), {'KEEP': 'yes'})
        self.assertEqual(m.capture_environment(source, labels_path=Path('/l')),
                         {'KEEP': 'yes', 'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': '/l'})
        self.assertEqual(m.capture_environment(source, metadata_path=Path('/m')),
                         {'KEEP': 'yes', 'PEARPLAY_DIAGNOSTIC_EVENT_METADATA': '/m'})
        self.assertEqual(source['PEARPLAY_DIAGNOSTIC_EVENT_LABELS'], '/unapproved-l')
        self.assertEqual(source['PEARPLAY_DIAGNOSTIC_EVENT_METADATA'], '/unapproved-m')

    def test_event_labels_environment_also_strips_metadata(self):
        m = load()
        source = {'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': '/unapproved-l',
                  'PEARPLAY_DIAGNOSTIC_EVENT_METADATA': '/unapproved-m', 'KEEP': 'yes'}
        self.assertEqual(m.event_labels_environment(source, None), {'KEEP': 'yes'})
        self.assertEqual(m.event_labels_environment(source, Path('/approved')),
                         {'KEEP': 'yes', 'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': '/approved'})


class CaptureEventMetadataPathTests(unittest.TestCase):
    def test_creates_owner_only_regular_file(self):
        import os
        import stat
        with tempfile.TemporaryDirectory() as home:
            path = load().capture_event_metadata_path(Path(home))
            self.assertIsNotNone(path)
            self.assertTrue(path.exists())
            info = path.stat()
            self.assertTrue(stat.S_ISREG(info.st_mode))
            self.assertEqual(info.st_mode & 0o777, 0o600)
            self.assertEqual(info.st_uid, os.geteuid())
            self.assertIn('event-metadata-', path.name)
            self.assertEqual(path.parent, Path(home) / '.cache' / 'pearplay-diagnostics')

    def test_symlink_parent_is_refused(self):
        with tempfile.TemporaryDirectory() as home:
            real = Path(home) / 'real-dir'; real.mkdir(mode=0o700)
            link = Path(home) / '.cache'; link.symlink_to(home, target_is_directory=True)
            self.assertIsNone(load().capture_event_metadata_path(Path(home)))

    def test_group_or_world_readable_parent_is_refused(self):
        with tempfile.TemporaryDirectory() as home:
            cache = Path(home) / '.cache' / 'pearplay-diagnostics'
            cache.mkdir(parents=True, mode=0o755)
            self.assertIsNone(load().capture_event_metadata_path(Path(home)))


class ProbePlaybackInfoOptions(unittest.TestCase):
    def _err(self, argv):
        import contextlib
        import io
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            load().options(argv)

    def test_flag_defaults_false(self):
        self.assertFalse(load().options([]).probe_playback_info)

    def test_flag_requires_origin_media(self):
        for media in ('hls-master', 'mp4', 'hls-direct'):
            self._err(['--media', media, '--probe-playback-info'])
        self._err(['--probe-playback-info'])  # default media

    def test_flag_accepted_with_origin_media(self):
        m = load()
        for media in ('origin-mp4', 'origin-hls'):
            args = m.options(['--media', media, '--origin', 'http://192.168.50.69:18765',
                              '--probe-playback-info'])
            self.assertTrue(args.probe_playback_info)
            self.assertEqual(args.media, media)


class CaptureProbeEnvironmentTests(unittest.TestCase):
    def test_capture_environment_strips_inherited_probe_opt_in(self):
        m = load()
        source = {'PEARPLAY_DIAGNOSTIC_PROBE_PLAYBACK_INFO': 'origin-mp4',
                  'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': '/unapproved',
                  'KEEP': 'yes'}
        self.assertEqual(m.capture_environment(source), {'KEEP': 'yes'})
        self.assertEqual(m.capture_environment(source, probe_playback_info='origin-hls'),
                         {'KEEP': 'yes', 'PEARPLAY_DIAGNOSTIC_PROBE_PLAYBACK_INFO': 'origin-hls'})
        self.assertEqual(source['PEARPLAY_DIAGNOSTIC_PROBE_PLAYBACK_INFO'], 'origin-mp4')

    def test_probe_env_never_readded_without_explicit_value(self):
        m = load()
        source = {'PEARPLAY_DIAGNOSTIC_PROBE_PLAYBACK_INFO': 'origin-mp4', 'KEEP': 'yes'}
        self.assertEqual(m.capture_environment(source, labels_path=Path('/l')),
                         {'KEEP': 'yes', 'PEARPLAY_DIAGNOSTIC_EVENT_LABELS': '/l'})


class ProbeReportExportTests(unittest.TestCase):
    def test_probe_rows_survive_safe_rows_while_secret_bait_drops(self):
        import json
        m = load()
        raw = '\n'.join([
            json.dumps({'k': 'probe', 't': 10, 'status': 'ok', 'httpCode': 200,
                        'readyToPlay': True, 'rate': 'one',
                        'url': 'https://SECRET', 'body': 'RAW', 'host': '192.168.50.69'}),
            json.dumps({'k': 'probe', 't': 20, 'status': 'exfiltration',
                        'domain': 'SECRET-DOMAIN', 'code': 'SECRET-CODE'}),
        ])
        rows = m.safe_rows(raw)
        self.assertEqual(rows, [
            {'k': 'probe', 't': 10, 'status': 'ok', 'httpCode': 200,
             'readyToPlay': True, 'rate': 'one'},
            {'k': 'probe', 't': 20},
        ])
        self.assertNotIn('SECRET', json.dumps(rows))
        self.assertNotIn('192.168.50.69', json.dumps(rows))
