import contextlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import time
import types
import unittest
from unittest import mock


PATH = Path(__file__).resolve().parents[1] / 'scripts/controlled_origin.py'


def load():
    spec = importlib.util.spec_from_file_location('controlled_origin', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLIP = b'0123456789'            # 10 bytes
PLAYLIST = b'#EXTM3U\nsegment000.ts\nsegment001.ts\n'
SEG0 = b'A' * 11
SEG1 = b'B' * 13
SECRET = b'SECRETDATA'


class _FakeHeaders:
    def get(self, _name, default=None):
        return default


class _FailingWfile:
    def write(self, _data):
        raise BrokenPipeError('client disconnected')

    def flush(self):
        pass


class ControlledOrigin(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PATH.exists(), 'controlled_origin.py missing')
        self.m = load()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'clip.mp4').write_bytes(CLIP)
        (self.root / 'index.m3u8').write_bytes(PLAYLIST)
        (self.root / 'segment000.ts').write_bytes(SEG0)
        (self.root / 'segment001.ts').write_bytes(SEG1)
        (self.root / 'secret.txt').write_bytes(SECRET)
        self.log = self.root / 'origin.log'
        self.log.touch()
        os.chmod(self.log, 0o600)
        self.server = None
        self.port = None

    def tearDown(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server.logger.close()
        self.tmp.cleanup()

    def _start(self, roles=None, max_rows=None):
        kwargs = {}
        if max_rows is not None:
            kwargs['max_rows'] = max_rows
        server = self.m.build_server(
            ('127.0.0.1', 0), str(self.root),
            roles or self.m.roles_for('10.0.0.1', '10.0.0.2', '127.0.0.1'),
            str(self.log), **kwargs)
        self.server = server
        self.port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def _request(self, method, path, headers=None, body=None):
        logger = self.server.logger
        with logger.lock:
            expected_rows = min(logger.count + 1, logger.max_rows)
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            data = resp.read()
            # The client can finish reading before the handler flushes its log.
            # Synchronize the test with that distinct event, without changing
            # response-before-log ordering in the server under test.
            deadline = time.monotonic() + 2
            while True:
                with logger.lock:
                    if logger.count >= expected_rows:
                        break
                self.assertLess(time.monotonic(), deadline, 'request log not flushed')
                time.sleep(0.005)
            return resp.status, dict(resp.getheaders()), data
        finally:
            conn.close()

    def _log_rows(self):
        return [json.loads(line) for line in self.log.read_text().splitlines() if line.strip()]

    def test_get_200_with_mime_length_accept_ranges_and_body(self):
        self._start()
        status, headers, body = self._request('GET', '/clip.mp4')
        self.assertEqual(status, 200)
        self.assertEqual(headers.get('Content-Type'), 'video/mp4')
        self.assertEqual(headers.get('Content-Length'), str(len(CLIP)))
        self.assertEqual(headers.get('Accept-Ranges'), 'bytes')
        self.assertEqual(body, CLIP)

        status, headers, body = self._request('GET', '/index.m3u8')
        self.assertEqual(status, 200)
        self.assertEqual(headers.get('Content-Type'), 'application/vnd.apple.mpegurl')
        self.assertEqual(body, PLAYLIST)

        status, headers, body = self._request('GET', '/segment000.ts')
        self.assertEqual(status, 200)
        self.assertEqual(headers.get('Content-Type'), 'video/mp2t')
        self.assertEqual(body, SEG0)

    def test_head_returns_headers_without_body(self):
        self._start()
        status, headers, body = self._request('HEAD', '/clip.mp4')
        self.assertEqual(status, 200)
        self.assertEqual(headers.get('Content-Length'), str(len(CLIP)))
        self.assertEqual(headers.get('Content-Type'), 'video/mp4')
        self.assertEqual(body, b'')

    def test_single_byte_range_206(self):
        self._start()
        status, headers, body = self._request('GET', '/clip.mp4', headers={'Range': 'bytes=0-0'})
        self.assertEqual(status, 206)
        self.assertEqual(headers.get('Content-Range'), 'bytes 0-0/10')
        self.assertEqual(headers.get('Content-Length'), '1')
        self.assertEqual(body, b'0')

    def test_open_ended_and_suffix_range_206(self):
        self._start()
        status, headers, body = self._request('GET', '/clip.mp4', headers={'Range': 'bytes=5-'})
        self.assertEqual(status, 206)
        self.assertEqual(headers.get('Content-Range'), 'bytes 5-9/10')
        self.assertEqual(body, b'56789')

        status, headers, body = self._request('GET', '/clip.mp4', headers={'Range': 'bytes=-3'})
        self.assertEqual(status, 206)
        self.assertEqual(headers.get('Content-Range'), 'bytes 7-9/10')
        self.assertEqual(body, b'789')

    def test_unsatisfiable_invalid_and_multirange_416(self):
        self._start()
        for bad in ('bytes=100-', 'bytes=abc', 'bytes=0-1,3-4', 'bytes=-0', 'bytes=8-5'):
            status, headers, body = self._request('GET', '/clip.mp4', headers={'Range': bad})
            self.assertEqual(status, 416, bad)
            self.assertEqual(headers.get('Content-Range'), 'bytes */10', bad)
            self.assertEqual(body, b'', bad)

    def test_unknown_traversal_encoded_and_directory_404(self):
        self._start()
        for path in ('/other.mp4', '/', '/secret.txt', '/clip.mp4/',
                     '/../secret.txt', '/../../etc/passwd', '/%2e%2e/secret.txt',
                     '/.hidden', '/clip.mp4%00'):
            status, _headers, body = self._request('GET', path)
            self.assertEqual(status, 404, path)
            self.assertNotEqual(body, SECRET, path)

    def test_symlink_and_other_static_files_not_served(self):
        os.symlink(self.root / 'secret.txt', self.root / 'segment999.ts')
        self._start()
        status, _h, body = self._request('GET', '/segment999.ts')
        self.assertEqual(status, 404)
        self.assertEqual(body, b'')
        status, _h, body = self._request('GET', '/secret.txt')
        self.assertEqual(status, 404)
        self.assertEqual(body, b'')

    def test_acl_rejects_unknown_source_403(self):
        server = self._start(roles=self.m.roles_for('10.0.0.1', '10.0.0.2', '10.0.0.3'))
        status, _h, body = self._request('GET', '/clip.mp4')
        self.assertEqual(status, 403)
        self.assertEqual(body, b'')
        server.shutdown()
        server.server_close()
        server.logger.close()
        self.server = None

    def test_roles_labeled_in_log(self):
        self._start(roles=self.m.roles_for('127.0.0.1', '10.0.0.2', '10.0.0.3'))
        self._request('GET', '/clip.mp4')
        rows = self._log_rows()
        self.assertEqual(rows[0]['role'], 'receiver')

    def test_log_schema_fixed_and_never_leaks_path_query_or_address(self):
        self._start()
        self._request('GET', '/clip.mp4?token=SECRET')
        self._request('HEAD', '/segment001.ts')
        rows = self._log_rows()
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(set(row), {'resource', 'method', 'role', 'status',
                                        'bytes', 'range', 'complete', 'elapsed_ms'})
            self.assertIn(row['resource'], ('mp4', 'playlist', 'segment', 'unknown'))
            self.assertIn(row['method'], ('GET', 'HEAD', 'other'))
            self.assertIn(row['role'], ('receiver', 'browser', 'probe', 'rejected'))
            self.assertIsInstance(row['status'], int)
            self.assertIsInstance(row['bytes'], int)
            self.assertIsInstance(row['range'], bool)
            self.assertIsInstance(row['complete'], bool)
            self.assertIsInstance(row['elapsed_ms'], int)
        raw = self.log.read_text()
        self.assertNotIn('SECRET', raw)
        self.assertNotIn('clip.mp4', raw)
        self.assertNotIn('token', raw)
        self.assertNotIn('127.0.0.1', raw)

    def test_log_row_cap(self):
        self._start(max_rows=3)
        for _ in range(8):
            self._request('GET', '/clip.mp4')
        rows = self._log_rows()
        self.assertEqual(len(rows), 3)

    def test_other_method_405(self):
        self._start()
        status, _h, body = self._request('POST', '/clip.mp4', body=b'x')
        self.assertEqual(status, 405)
        self.assertEqual(body, b'')
        rows = self._log_rows()
        self.assertEqual(rows[0]['method'], 'other')

    def test_cli_bind_requires_rfc1918_and_rejects_unsafe(self):
        def argv(bind):
            return ['--bind', bind, '--port', '8123', '--root', str(self.root),
                    '--receiver', '192.168.50.195', '--browser', '192.168.50.104',
                    '--log', str(self.log)]
        args = self.m.options(argv('192.168.50.69'))
        self.assertEqual(args.bind, '192.168.50.69')
        for bad in ('0.0.0.0', '127.0.0.1', '8.8.8.8', '::1', 'not-an-ip'):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                self.m.options(argv(bad))
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.m.options(argv('192.168.50.69')[:2] + ['--port', '70000'] + argv('192.168.50.69')[4:])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.m.options(argv('192.168.50.69')[:6] + ['--max-seconds', '99999'] + argv('192.168.50.69')[8:])

    def test_classify_and_parse_range_units(self):
        m = self.m
        self.assertEqual(m.classify_resource('clip.mp4'), 'mp4')
        self.assertEqual(m.classify_resource('index.m3u8'), 'playlist')
        self.assertEqual(m.classify_resource('segment000.ts'), 'segment')
        self.assertEqual(m.classify_resource('segment99999.ts'), 'segment')
        self.assertEqual(m.classify_resource('segment100000.ts'), 'unknown')
        self.assertEqual(m.classify_resource('secret.txt'), 'unknown')
        self.assertIsNone(m.parse_range(None, 10))
        self.assertEqual(m.parse_range('bytes=0-0', 10), (0, 0))
        self.assertEqual(m.parse_range('bytes=5-', 10), (5, 9))
        self.assertEqual(m.parse_range('bytes=-3', 10), (7, 9))
        self.assertEqual(m.parse_range('bytes=100-', 10), 'unsatisfiable')
        self.assertEqual(m.parse_range('bytes=0-1,3-4', 10), 'invalid')

    # --- Logger hardening ---

    def test_logger_rejects_symlink_missing_and_wrong_mode(self):
        m = self.m
        link = self.root / 'link.log'
        os.symlink(self.log, link)
        with self.assertRaises(ValueError):
            m.JsonlLogger(str(link))

        missing = self.root / 'missing.log'
        with self.assertRaises(ValueError):
            m.JsonlLogger(str(missing))
        self.assertFalse(missing.exists(), 'logger must not create the file')

        os.chmod(self.log, 0o644)
        with self.assertRaises(ValueError):
            m.JsonlLogger(str(self.log))
        os.chmod(self.log, 0o600)

    def test_logger_validates_owner_uid_and_mode(self):
        m = self.m
        good = types.SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=os.getuid())
        self.assertIsNone(m._validate_log_stat(good))
        wrong_owner = types.SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=os.getuid() + 1)
        self.assertIsNotNone(m._validate_log_stat(wrong_owner))
        wrong_mode = types.SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=os.getuid())
        self.assertIsNotNone(m._validate_log_stat(wrong_mode))
        non_regular = types.SimpleNamespace(st_mode=stat.S_IFLNK | 0o600, st_uid=os.getuid())
        self.assertIsNotNone(m._validate_log_stat(non_regular))

    # --- Preload hardening ---

    def test_preload_requires_clip_and_playlist(self):
        m = self.m
        (self.root / 'clip.mp4').unlink()
        with self.assertRaises(RuntimeError):
            m.preload(str(self.root))
        (self.root / 'clip.mp4').write_bytes(CLIP)
        (self.root / 'index.m3u8').unlink()
        with self.assertRaises(RuntimeError):
            m.preload(str(self.root))

    def test_preload_rejects_oversize_without_reading_whole_file(self):
        m = self.m
        bound = 64
        old = m.MAX_TOTAL_BYTES
        m.MAX_TOTAL_BYTES = bound
        big = self.root / 'segment999.ts'
        with open(big, 'wb') as f:
            f.truncate(1_000_000)  # sparse, cheap to create, far over budget
        counts = []
        real_read = os.read
        def spy(fd, n):
            counts.append(n)
            return real_read(fd, n)
        try:
            with mock.patch.object(m.os, 'read', spy):
                with self.assertRaises(RuntimeError):
                    m.preload(str(self.root))
        finally:
            m.MAX_TOTAL_BYTES = old
        # Reads must be bounded to remaining+1 (<= bound+1): the oversized file
        # is rejected via st_size before any large read/allocation.
        self.assertTrue(counts, 'expected at least the small files to be read')
        self.assertTrue(all(n <= bound + 1 for n in counts), counts)

    def test_preload_limits_scan_entries(self):
        m = self.m
        old = m.MAX_FILES
        m.MAX_FILES = 4  # setUp dir has clip, index, log, secret, seg0, seg1 = 6 entries
        try:
            with self.assertRaises(RuntimeError):
                m.preload(str(self.root))
        finally:
            m.MAX_FILES = old

    def test_preload_skips_symlinked_resource(self):
        m = self.m
        os.symlink(self.root / 'secret.txt', self.root / 'segment999.ts')
        data = m.preload(str(self.root))
        self.assertNotIn('segment999.ts', data)
        self.assertIn('clip.mp4', data)

    # --- Range parsing ---

    def test_parse_range_empty_and_strict_ascii_digits(self):
        m = self.m
        self.assertEqual(m.parse_range('', 10), 'invalid')
        for bad in ('bytes=+1-', 'bytes= 1-', 'bytes=1_0-', 'bytes=0x1-',
                    'bytes=--', 'bytes=-+3', 'bytes=１２-', 'bytes=1-２'):
            self.assertEqual(m.parse_range(bad, 10), 'invalid', bad)

    def test_empty_range_header_416(self):
        self._start()
        status, headers, body = self._request('GET', '/clip.mp4', headers={'Range': ''})
        self.assertEqual(status, 416)
        self.assertEqual(headers.get('Content-Range'), 'bytes */10')
        self.assertEqual(body, b'')

    def test_suffix_range_on_empty_file_416(self):
        (self.root / 'segment002.ts').write_bytes(b'')
        self._start()
        status, headers, body = self._request('GET', '/segment002.ts', headers={'Range': 'bytes=-1'})
        self.assertEqual(status, 416)
        self.assertEqual(headers.get('Content-Range'), 'bytes */0')
        self.assertEqual(body, b'')

    # --- Write-failure logging ---

    def test_write_failure_logs_complete_false_no_traceback(self):
        m = self.m
        server = m.build_server(
            ('127.0.0.1', 0), str(self.root),
            m.roles_for('10.0.0.1', '10.0.0.2', '127.0.0.1'), str(self.log))
        handler = m.ControlledHandler.__new__(m.ControlledHandler)
        handler.server = server
        handler.client_address = ('127.0.0.1', 12345)
        handler.command = 'GET'
        handler.path = '/clip.mp4'
        handler.request_version = 'HTTP/1.1'
        handler.requestline = 'GET /clip.mp4 HTTP/1.1'
        handler.headers = _FakeHeaders()
        handler.wfile = _FailingWfile()
        handler.rfile = io.BytesIO(b'')
        handler._headers_buffer = []
        handler.close_connection = False
        logged = []
        server.logger.log = lambda row: logged.append(row)
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                handler._serve(False)
        finally:
            server.logger.close()
            server.server_close()
        self.assertEqual(len(logged), 1, 'request must be logged even on write failure')
        row = logged[0]
        self.assertEqual(row['status'], 200)
        self.assertFalse(row['complete'])
        self.assertEqual(row['bytes'], 0)
        self.assertNotIn('Traceback', err.getvalue())

    def test_server_handle_error_suppresses_traceback(self):
        server = self._start()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            server.handle_error(None, ('192.168.50.195', 45678))
        self.assertNotIn('Traceback', err.getvalue())
        self.assertNotIn('192.168.50.195', err.getvalue())

    # --- Origin timeline + startup message ---

    def test_elapsed_ms_is_origin_timeline(self):
        self._start()
        self._request('GET', '/clip.mp4')
        time.sleep(0.2)
        self._request('GET', '/clip.mp4')
        rows = self._log_rows()
        self.assertGreaterEqual(rows[1]['elapsed_ms'], rows[0]['elapsed_ms'])
        self.assertGreater(rows[1]['elapsed_ms'] - rows[0]['elapsed_ms'], 100)

    def test_startup_prints_static_readiness_message(self):
        m = self.m
        out = io.StringIO()
        argv = ['--bind', '192.168.50.69', '--port', '8123', '--root', str(self.root),
                '--receiver', '192.168.50.195', '--browser', '192.168.50.104',
                '--log', str(self.log)]
        with contextlib.redirect_stdout(out), \
                mock.patch.object(m, 'build_server', return_value=mock.Mock()), \
                mock.patch.object(m, 'serve', return_value=None):
            self.assertEqual(m.main(argv), 0)
        msg = out.getvalue()
        self.assertTrue(msg.strip())
        self.assertNotIn('192.168.50.69', msg)
        self.assertNotIn('192.168.50.195', msg)
        self.assertNotIn('192.168.50.104', msg)
        self.assertNotIn(str(self.root), msg)


if __name__ == '__main__':
    unittest.main()
