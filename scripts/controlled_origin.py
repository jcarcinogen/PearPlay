#!/usr/bin/env python3
"""Controlled media origin for the LG HLS test.

Serves only a fixed, preloaded whitelist (clip.mp4, index.m3u8, segmentNNN.ts)
from memory over a bounded ThreadingHTTPServer. No directory listing,
traversal, symlinks, redirects, or auth. Source-IP ACL maps the receiver,
browser, and bind host to fixed roles; every other address is rejected 403.
Logs a capped, sanitized JSONL stream with fixed enums only.

Usage:
  python3 scripts/controlled_origin.py --bind 192.168.50.69 --port 8123 \\
      --root /path/to/assets --receiver 192.168.50.195 \\
      --browser 192.168.50.104 --log /path/to/precreated-0600.log
"""
import argparse
import http.server
import ipaddress
import json
import os
import re
import stat
import threading
import time
from pathlib import Path

MAX_SEGMENT_INDEX = 99999            # bounded segment count
MAX_TOTAL_BYTES = 64 * 1024 * 1024   # preload memory bound
MAX_FILES = 10000                    # preload entry bound
MAX_LOG_ROWS = 10000                 # log row cap
MAX_SECONDS = 3600                   # lifetime cap (~1 hour)
READ_TIMEOUT = 5.0                   # request read time bound (seconds)

SEGMENT_RE = re.compile(r'^segment(\d{1,5})\.ts$')

CLIP = 'clip.mp4'
PLAYLIST = 'index.m3u8'

MIME = {'mp4': 'video/mp4', 'playlist': 'application/vnd.apple.mpegurl', 'segment': 'video/mp2t'}

RFC1918 = (ipaddress.ip_network('10.0.0.0/8'),
           ipaddress.ip_network('172.16.0.0/12'),
           ipaddress.ip_network('192.168.0.0/16'))


def classify_resource(name):
    """Map a single path component to the fixed resource enum."""
    if name == CLIP:
        return 'mp4'
    if name == PLAYLIST:
        return 'playlist'
    match = SEGMENT_RE.match(name)
    if match and int(match.group(1)) <= MAX_SEGMENT_INDEX:
        return 'segment'
    return 'unknown'


def parse_request_path(raw_path):
    """Return the single path component, or None for anything unsafe/encoded."""
    path = raw_path
    if '?' in path:
        path = path.split('?', 1)[0]
    if not path.startswith('/'):
        return None
    name = path[1:]
    if name == '' or '..' in name or '/' in name or '\\' in name or '%' in name:
        return None
    return name


def parse_range(header, length):
    """Parse a single byte Range header. Returns None (absent), a (start, end)
    inclusive tuple, or 'invalid'/'unsatisfiable'. Multi-range, empty, and
    non-strict-ASCII-digit specs are 'invalid'."""
    if header is None:
        return None
    if not header.startswith('bytes='):
        return 'invalid'
    spec = header[len('bytes='):]
    if ',' in spec or '-' not in spec:
        return 'invalid'
    start_s, end_s = spec.split('-', 1)
    try:
        if start_s == '':
            if not (end_s.isascii() and end_s.isdigit()):
                return 'invalid'
            suffix = int(end_s)
            if suffix <= 0:
                return 'invalid'
            start = max(0, length - suffix)
            end = length - 1
        else:
            if not (start_s.isascii() and start_s.isdigit()):
                return 'invalid'
            start = int(start_s)
            if end_s == '':
                end = length - 1
            else:
                if not (end_s.isascii() and end_s.isdigit()):
                    return 'invalid'
                end = int(end_s)
    except ValueError:
        return 'invalid'
    if start < 0 or end < start or start >= length:
        return 'unsatisfiable'
    return (start, min(end, length - 1))


def preload(root):
    """Read whitelisted regular files into memory over a bounded nofollow
    descriptor read, skipping symlinks and non-regular entries. Oversized files
    are rejected from st_size before any large read/allocation. Both clip.mp4
    and index.m3u8 must be present or startup fails."""
    root = Path(root)
    data = {}
    total = 0
    scanned = 0
    present = set()
    for entry in sorted(root.iterdir()):
        scanned += 1
        if scanned > MAX_FILES:
            raise RuntimeError('too many entries in media root')
        if entry.is_symlink() or not entry.is_file():
            continue
        resource = classify_resource(entry.name)
        if resource == 'unknown':
            continue
        fd = os.open(entry, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                continue
            size = st.st_size
            remaining = MAX_TOTAL_BYTES - total
            if size > remaining:
                raise RuntimeError('preload total exceeds bound')
            content = os.read(fd, remaining + 1)
            if len(content) != size or len(content) > remaining:
                raise RuntimeError('preload total exceeds bound')
            data[entry.name] = content
            total += len(content)
            present.add(entry.name)
        finally:
            os.close(fd)
    if CLIP not in present or PLAYLIST not in present:
        raise RuntimeError('required media (clip.mp4, index.m3u8) missing')
    return data


def roles_for(receiver, browser, probe):
    """Map the three allowlisted source IPs to fixed roles."""
    return {receiver: 'receiver', browser: 'browser', probe: 'probe'}


def _validate_log_stat(st):
    """Return an error string, or None if the log fd stat is acceptable."""
    if not stat.S_ISREG(st.st_mode):
        return 'log path must be a precreated regular file'
    if st.st_uid != os.getuid():
        return 'log path must be owned by the current user'
    if stat.S_IMODE(st.st_mode) != 0o600:
        return 'log path must be owner-only (0600)'
    return None


class JsonlLogger:
    """Owner-only, capped, sanitized JSONL sink guarded by a small lock."""

    def __init__(self, path, max_rows=MAX_LOG_ROWS):
        self.path = Path(path)
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            raise ValueError('log path must be a precreated regular file')
        try:
            st = os.fstat(fd)
            err = _validate_log_stat(st)
            if err:
                raise ValueError(err)
            self.file = os.fdopen(fd, 'a', encoding='utf-8')
        except BaseException:
            os.close(fd)
            raise
        self.max_rows = max_rows
        self.lock = threading.Lock()
        self.count = 0
        self.closed = False

    def log(self, row):
        with self.lock:
            if self.closed or self.count >= self.max_rows:
                return
            self.file.write(json.dumps(row, sort_keys=True) + '\n')
            self.file.flush()
            self.count += 1

    def close(self):
        with self.lock:
            if not self.closed:
                self.file.flush()
                self.file.close()
                self.closed = True


class ControlledHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'ControlledOrigin/1.0'
    timeout = READ_TIMEOUT

    def log_message(self, *_args):
        pass

    def do_GET(self):
        self._serve(False)

    def do_HEAD(self):
        self._serve(True)

    do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_GET

    def _serve(self, head_only):
        command = self.command
        method = command if command in ('GET', 'HEAD') else 'other'

        name = parse_request_path(self.path)
        resource = classify_resource(name) if name is not None else 'unknown'
        data = self.server.resources.get(name) if name is not None else None
        role = self.server.roles.get(self.client_address[0], 'rejected')

        status = 404
        body = b''
        content_type = None
        content_range = None
        ranged = False

        if method == 'other':
            status = 405
        elif resource == 'unknown' or data is None:
            status = 404
        elif role == 'rejected':
            status = 403
        else:
            content_type = MIME[resource]
            length = len(data)
            range_header = self.headers.get('Range')
            if range_header is not None:
                ranged = True
                result = parse_range(range_header, length)
                if result in ('invalid', 'unsatisfiable'):
                    status = 416
                    content_range = 'bytes */%d' % length
                else:
                    rstart, rend = result
                    status = 206
                    body = data[rstart:rend + 1]
                    content_range = 'bytes %d-%d/%d' % (rstart, rend, length)
            else:
                status = 200
                body = data

        completed = True
        written = 0
        try:
            self._write(status, body, content_type, content_range, head_only)
            if not head_only:
                written = len(body)
        except OSError:
            completed = False
        except Exception:
            completed = False
            raise
        finally:
            elapsed = int((time.monotonic() - self.server.start_time) * 1000)
            self.server.logger.log({
                'resource': resource,
                'method': method,
                'role': role,
                'status': status,
                'bytes': min(written, MAX_TOTAL_BYTES),
                'range': ranged,
                'complete': completed,
                'elapsed_ms': min(max(elapsed, 0), 600000),
            })

    def _write(self, status, body, content_type, content_range, head_only):
        self.send_response(status)
        if content_type:
            self.send_header('Content-Type', content_type)
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Access-Control-Allow-Origin', '*')
        if content_range:
            self.send_header('Content-Range', content_range)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.close_connection = True
        self.end_headers()
        if not head_only and body:
            self.wfile.write(body)


class ControlledHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, resources, roles, logger, max_seconds=MAX_SECONDS):
        self.resources = resources
        self.roles = roles
        self.logger = logger
        self.max_seconds = max_seconds
        self.start_time = time.monotonic()
        super().__init__(addr, ControlledHandler)

    def handle_error(self, request, client_address):
        # Suppress the inherited raw traceback (which prints the client IP and
        # exception text to stderr); requests are already sanitized in _serve.
        pass


def build_server(addr, root, roles, log_path, max_seconds=MAX_SECONDS, max_rows=MAX_LOG_ROWS):
    """Constructor seam: build (not start) the server. addr may be any
    (host, port); the CLI enforces RFC1918 on its --bind."""
    resources = preload(root)
    logger = JsonlLogger(log_path, max_rows=max_rows)
    return ControlledHTTPServer(addr, resources, roles, logger, max_seconds)


def serve(server, max_seconds):
    timer = threading.Timer(max_seconds, server.shutdown)
    timer.daemon = True
    timer.start()
    try:
        server.serve_forever()
    finally:
        timer.cancel()
        server.server_close()
        server.logger.close()


def _rfc1918_bind(text):
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        raise argparse.ArgumentTypeError('bind must be an IPv4 address')
    if ip.version != 4 or ip.is_unspecified or ip.is_loopback or not any(ip in net for net in RFC1918):
        raise argparse.ArgumentTypeError('bind must be an RFC1918 IPv4 address (not 0.0.0.0 or loopback)')
    return str(ip)


def _ipv4(text):
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        raise argparse.ArgumentTypeError('must be an IPv4 address')
    if ip.version != 4 or ip.is_unspecified:
        raise argparse.ArgumentTypeError('must be a non-unspecified IPv4 address')
    return str(ip)


def _port(text):
    value = int(text)
    if not (1 <= value <= 65535):
        raise argparse.ArgumentTypeError('port must be 1-65535')
    return value


def _max_seconds(text):
    value = int(text)
    if not (1 <= value <= MAX_SECONDS):
        raise argparse.ArgumentTypeError('max-seconds must be 1-%d' % MAX_SECONDS)
    return value


def options(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', required=True, type=_rfc1918_bind)
    parser.add_argument('--port', required=True, type=_port)
    parser.add_argument('--root', required=True)
    parser.add_argument('--receiver', required=True, type=_ipv4)
    parser.add_argument('--browser', required=True, type=_ipv4)
    parser.add_argument('--log', required=True)
    parser.add_argument('--max-seconds', type=_max_seconds, default=MAX_SECONDS)
    return parser.parse_args(argv)


def main(argv=None):
    args = options(argv)
    roles = roles_for(args.receiver, args.browser, args.bind)
    server = build_server((args.bind, args.port), args.root, roles, args.log,
                          max_seconds=args.max_seconds)
    print('controlled origin ready', flush=True)
    serve(server, args.max_seconds)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
