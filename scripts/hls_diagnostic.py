#!/usr/bin/env python3
"""Disposable LG HLS diagnostic. No install, firewall changes, or automatic cast."""
import argparse
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helper.diagnostics import sanitize

ARTIFACT_DIR = Path('/Volumes/IronWolf/Stuff/PearPlay/Investigations')
ARCHIVE_NAME = 'PearPlay-HLS-playback-info-runtime.tar.gz'
EXPECTED_SHA256 = 'c3c6fa256d2da88411ac4cc0af666319245627090b039f0f97969dcca69c024b'
PUBLIC_HLS = 'https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8'
CONTROLS = {
    'hls-master': ('HLS control — exact public master', PUBLIC_HLS),
    'mp4': ('MP4 control — previously working trailer', 'https://media.w3.org/2010/05/bunny/trailer.mp4'),
    'hls-direct': ('HLS control — direct 480p rendition', 'https://test-streams.mux.dev/x36xhzz/url_6/193039199_mp4_h264_aac_hq_7.m3u8'),
}
ORIGIN_SUFFIX = {
    'origin-mp4': '/clip.mp4',
    'origin-hls': '/index.m3u8',
}
ORIGIN_TITLES = {
    'origin-mp4': 'controlled MP4',
    'origin-hls': 'controlled HLS',
}


def _is_rfc1918_ipv4(host):
    """True for a strict dotted-quad RFC1918 literal (no leading zeros)."""
    parts = host.split('.')
    if len(parts) != 4:
        return False
    octets = []
    for part in parts:
        if not re.fullmatch(r'[0-9]+', part):
            return False
        if len(part) > 1 and part[0] == '0':
            return False
        if int(part) > 255:
            return False
        octets.append(int(part))
    a, b = octets[0], octets[1]
    if a == 10:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    return a == 192 and b == 168


def _valid_port(port):
    """True for an exact decimal port 1..65535 (no leading zeros)."""
    if not re.fullmatch(r'[0-9]+', port):
        return False
    if len(port) > 1 and port[0] == '0':
        return False
    return 1 <= int(port) <= 65535


def validate_origin(origin):
    """Return ``origin`` unchanged if it is an exact RFC1918 ``http://IPv4:port``.

    Rejects anything but a lowercase ``http://`` scheme, a strict RFC1918 IPv4
    host, and a decimal port 1..65535, with nothing after the port. Credentials
    (userinfo), query, fragment, path, trailing slash, control/whitespace
    characters, and any normalization are all refused; the accepted string is
    preserved exactly.
    """
    if not isinstance(origin, str):
        return None
    if not origin.startswith('http://'):
        return None
    rest = origin[7:]
    if not rest:
        return None
    if any(ord(ch) < 33 or ord(ch) > 126 for ch in rest):
        return None
    if any(ch in rest for ch in ('@', '?', '#', '/')):
        return None
    if rest.count(':') != 1:
        return None
    host, port = rest.split(':', 1)
    if not _is_rfc1918_ipv4(host) or not _valid_port(port):
        return None
    return origin


def control_source(media, origin=None):
    """Return the exact media URL for ``media``; ``origin`` only for origin-* controls."""
    if media in ORIGIN_SUFFIX:
        if validate_origin(origin) is None:
            raise ValueError('invalid RFC1918 origin')
        return origin + ORIGIN_SUFFIX[media]
    if origin is not None:
        raise ValueError('origin only valid for origin-* media')
    if media not in CONTROLS:
        raise ValueError('invalid control')
    return CONTROLS[media][1]


def safe_rows(raw):
    rows = []
    for line in raw[:1048576].splitlines()[:2048]:
        try:
            source = json.loads(line)
        except ValueError:
            continue
        if not isinstance(source, dict):
            continue
        row = sanitize(source.get('k'), source)
        if row is None:
            continue
        elapsed = source.get('t')
        if type(elapsed) is int and 0 <= elapsed <= 86400000:
            row['t'] = elapsed
        rows.append(row)
    return rows


def capture_environment(environ, labels_path=None, metadata_path=None, probe_playback_info=None):
    """Strip all inherited capture/probe opt-ins; set only the selected values.

    Returns a fresh environment dict with ``PEARPLAY_DIAGNOSTIC_EVENT_LABELS``,
    ``PEARPLAY_DIAGNOSTIC_EVENT_METADATA`` and
    ``PEARPLAY_DIAGNOSTIC_PROBE_PLAYBACK_INFO`` always removed from the inherited
    environment, then re-added only for the explicitly selected path/origin (if
    any). This prevents an inherited opt-in from silently re-enabling capture.
    """
    env = dict(environ)
    env.pop('PEARPLAY_DIAGNOSTIC_EVENT_LABELS', None)
    env.pop('PEARPLAY_DIAGNOSTIC_EVENT_METADATA', None)
    env.pop('PEARPLAY_DIAGNOSTIC_PROBE_PLAYBACK_INFO', None)
    if labels_path is not None:
        env['PEARPLAY_DIAGNOSTIC_EVENT_LABELS'] = str(labels_path)
    if metadata_path is not None:
        env['PEARPLAY_DIAGNOSTIC_EVENT_METADATA'] = str(metadata_path)
    if probe_playback_info is not None:
        env['PEARPLAY_DIAGNOSTIC_PROBE_PLAYBACK_INFO'] = probe_playback_info
    return env


def event_labels_environment(environ, path):
    return capture_environment(environ, labels_path=path)


def _capture_sidecar_path(base, prefix):
    """Create an exclusive owner-only ``<prefix>-<id>.jsonl`` sidecar.

    ``base`` is the home directory (defaults to ``Path.home()``); the sidecar
    is created under ``<base>/.cache/pearplay-diagnostics``, outside any
    disposable trial directory, so it persists after the run. Creates the
    directory if missing, then exclusively creates (O_EXCL) a fresh file with
    mode 0600. Refuses a symlinked cache or parent, a non-directory or
    group/world-accessible cache, or one not owned by the current user.
    Returns the created path, or None on any unsafe condition so the launcher
    disables capture silently.
    """
    cache = (Path.home() if base is None else Path(base)) / '.cache/pearplay-diagnostics'
    if cache.is_symlink() or cache.parent.is_symlink():
        return None
    try:
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError:
        return None
    try:
        info = cache.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or (info.st_mode & 0o077):
            return None
    except OSError:
        return None
    path = cache / f'{prefix}-{uuid4().hex[:12]}.jsonl'
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except OSError:
        return None
    os.close(fd)
    return path


def capture_event_labels_path(base=None):
    """Create an exclusive owner-only event-label sidecar under the cache."""
    return _capture_sidecar_path(base, 'event-labels')


def capture_event_metadata_path(base=None):
    """Create an exclusive owner-only event-metadata sidecar under the cache."""
    return _capture_sidecar_path(base, 'event-metadata')


def options(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--media', choices=tuple(CONTROLS) + ('origin-mp4', 'origin-hls'), default='hls-master')
    parser.add_argument('--origin', help='RFC1918 http://IPv4:port origin for origin-* media')
    parser.add_argument('--startup-seconds', type=int, choices=(10, 30), default=10)
    parser.add_argument('--check', action='store_true', help='Verify runtime and isolated registration only; no browser or TV action')
    parser.add_argument('--capture-event-labels', action='store_true',
                        help='Capture unique unknown receiver event-type labels to a local sidecar file')
    parser.add_argument('--capture-event-metadata', action='store_true',
                        help='Capture private notification event name/kind/error metadata to a local sidecar file')
    parser.add_argument('--probe-playback-info', action='store_true',
                        help='Probe GET /playback-info on the control session during the hold (origin-* media only)')
    args = parser.parse_args(argv)
    if args.media in ORIGIN_SUFFIX:
        if args.origin is None:
            parser.error(f'--media {args.media} requires --origin http://<RFC1918-IPv4>:<port>')
        if validate_origin(args.origin) is None:
            parser.error('--origin must be an exact RFC1918 http://IPv4:port with port 1..65535')
    elif args.origin is not None:
        parser.error('--origin is only valid with --media origin-mp4 or origin-hls')
    if args.capture_event_labels and args.media not in ORIGIN_SUFFIX:
        parser.error('--capture-event-labels is only valid with --media origin-mp4 or origin-hls')
    if args.capture_event_metadata and args.media not in ORIGIN_SUFFIX:
        parser.error('--capture-event-metadata is only valid with --media origin-mp4 or origin-hls')
    if args.capture_event_labels and args.capture_event_metadata:
        parser.error('--capture-event-labels and --capture-event-metadata are mutually exclusive')
    if args.probe_playback_info and args.media not in ORIGIN_SUFFIX:
        parser.error('--probe-playback-info is only valid with --media origin-mp4 or origin-hls')
    return args


def control_page(seconds, media='hls-master', origin=None):
    if seconds not in (10, 30):
        raise ValueError('invalid startup deadline')
    url = control_source(media, origin)
    if media in ORIGIN_TITLES:
        title = ORIGIN_TITLES[media]
        intro = 'This sends the same clip from your controlled origin media server, not a generic public CDN.'
    else:
        title, _url = CONTROLS[media]
        intro = 'This sends one exact public media source.'
    if media in ('mp4', 'origin-mp4'):
        hint = 'You do not need to play it here.'
    else:
        hint = 'This browser may not play it locally; that is expected. You do not need to play it here.'
    return f'''<!doctype html><meta charset="utf-8"><title>PearPlay HLS diagnostic</title>
<style>body{{font:18px system-ui;max-width:800px;margin:40px auto;padding:20px}}video{{width:100%}}</style>
<h1>{title} — {seconds} seconds</h1>
<p>{intro} {hint}</p>
<ol><li>Open PearPlay from the puzzle-piece Extensions menu.</li>
<li>Allow website access, reload this page, and choose Find videos.</li>
<li>Choose the control video, then the LG and Send. Enter a PIN only in PearPlay's masked field if requested, then Send again.</li>
<li>Watch for moving video and listen for sound. Note whether the TV shows a spinner, an error, or actual playback—even if PearPlay reports a timeout.</li>
<li>Once the result is clear, close all windows of this test browser. The terminal prints the sanitized report location.</li></ol>
<video controls preload="metadata" title="{title}" src="{url}"></video>
<p>Only the startup wait is {seconds} seconds; command/network timeouts are unchanged. No firewall or installed-helper change.</p>'''


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main(argv=None):
    args = options(argv)
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise RuntimeError('Use the Acer as your normal user, without sudo.')
    if not shutil.which('chromium'):
        raise RuntimeError('Native Chromium is required.')
    archive = ARTIFACT_DIR / ARCHIVE_NAME
    with archive.open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != EXPECTED_SHA256:
            raise RuntimeError('Diagnostic archive checksum mismatch.')
    os.umask(0o077)
    cache = Path.home() / '.cache/pearplay-diagnostics'
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    labels_path = capture_event_labels_path() if args.capture_event_labels else None
    metadata_path = capture_event_metadata_path() if args.capture_event_metadata else None
    with tempfile.TemporaryDirectory(prefix='hls-', dir=cache) as directory:
        base = Path(directory)
        with tarfile.open(archive) as bundle:
            bundle.extractall(base, filter='data')
        binary = base / 'PearPlayHelper/PearPlayHelper'
        extension = base / 'extension'
        profile = base / 'browser/chromium'
        for folder in (profile, base/'home', base/'state', base/'tmp', base/'page'):
            folder.mkdir(parents=True, exist_ok=True)
        trace = base/'trace.jsonl'
        trace.touch(mode=0o600, exist_ok=False)
        env = dict(capture_environment(os.environ, labels_path, metadata_path,
                                        args.media if args.probe_playback_info else None),
                   HOME=str(base/'home'), XDG_CONFIG_HOME=str(base/'browser'),
                   XDG_STATE_HOME=str(base/'state'), TMPDIR=str(base/'tmp'),
                   PEARPLAY_DIAGNOSTIC_TRACE=str(trace),
                   PEARPLAY_DIAGNOSTIC_STARTUP_SECONDS=str(args.startup_seconds))
        subprocess.run([str(binary), 'self-test'], env=env, check=True, timeout=20,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def registration(action):
            result = subprocess.run([str(binary), action, '--browsers', 'chromium', '--config-parent', str(base/'browser')],
                env=env, capture_output=True, text=True, check=True, timeout=20)
            return json.loads(result.stdout).get('chromium')
        if registration('connect') != 'connected':
            raise RuntimeError('Isolated registration failed.')
        manifest = profile/'NativeMessagingHosts/com.pearplay.helper.json'
        if json.loads(manifest.read_text())['path'] != str(binary):
            raise RuntimeError('Wrong diagnostic registration.')
        try:
            if args.check:
                print('PASS: checksum, frozen runtime and isolated Chromium registration. No browser or TV action.')
            else:
                (base/'page/index.html').write_text(control_page(args.startup_seconds, args.media, args.origin))
                server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(base/'page')))
                threading.Thread(target=server.serve_forever, daemon=True).start()
                print(f'Opening isolated {args.media} {args.startup_seconds}-second trial. Keep this terminal open; close every test-browser window when finished.', flush=True)
                try:
                    subprocess.run(['chromium', '--no-first-run', '--no-default-browser-check', '--password-store=basic',
                        '--user-data-dir='+str(profile), '--load-extension='+str(extension),
                        f'http://127.0.0.1:{server.server_port}/'], env=env, check=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                finally:
                    server.shutdown()
                    server.server_close()
                    with trace.open() as source:
                        rows = safe_rows(source.read(1048576))
                    reports = ARTIFACT_DIR/'HLS reports'
                    reports.mkdir(exist_ok=True)
                    report = reports/f'trial-{args.media}-{args.startup_seconds}s-{uuid4().hex[:12]}.json'
                    with report.open('x') as target:
                        json.dump({'control': args.media, 'startup_seconds': args.startup_seconds, 'build_sha256': EXPECTED_SHA256,
                                   'rows': rows, 'human_playback': 'not-recorded'}, target, indent=2)
                    print(f'Sanitized report ({len(rows)} rows): {report}', flush=True)
                    if labels_path is not None:
                        print(f'Event-type label sidecar: {labels_path}', flush=True)
                    if metadata_path is not None:
                        print(f'Event-metadata sidecar: {metadata_path}', flush=True)
        finally:
            if registration('remove') != 'removed' or manifest.exists():
                raise RuntimeError('Isolated registration cleanup failed.')
    print('Disposable browser profile and pairing removed. Installed helper and firewall unchanged.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        print('Diagnostic trial failed; no installed-helper or firewall change was requested. Check the mounted diagnostic files.', file=sys.stderr)
        raise SystemExit(1)
