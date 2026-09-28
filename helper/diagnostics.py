"""Opt-in development-only sanitized playback trace.

Stdlib-only. Emits a small fixed allowlist of bounded fields to a pre-created,
owner-only, regular file. Never records URLs, hosts, exception text, PINs,
credentials, request bodies, or identifiers. All classification of the selected
media URL happens in memory; only a coarse ``mp4``/``hls``/``other`` kind and an
exact public-fixture tag are written.
"""

import json
import math
import os
import re
import stat
import time

# Exact public fixtures (deterministic sample paths).
PUBLIC_HLS_MASTER = 'https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8'
PUBLIC_MP4 = 'https://media.w3.org/2010/05/bunny/trailer.mp4'

MEDIA_TYPES = ('mp4', 'hls', 'other')
FIXTURES = ('public-hls-master', 'public-mp4', 'other')

# Normalized receiver event type/state (fixed enums only).
EVENT_TYPES = ('playbackState', 'playbackError', 'error',
               'unhandledURLRequest', 'unhandledURLResponse', 'other')
EVENT_STATES = ('playing', 'stopped', 'paused', 'loading', 'interrupted', 'other')

# Recognized Apple error domains; anything else is reported as 'other'.
ERROR_DOMAINS = ('NSURLErrorDomain', 'NSOSStatusErrorDomain', 'AVFoundationErrorDomain',
                 'CoreMediaErrorDomain', 'AirPlayErrorDomain', 'other')

# Raw event-channel decode statuses reported by the pyatv adapter.
CHANNEL_STATUS = ('received', 'decoded', 'ignored', 'parse-error')

# Playback stages (mirrors native.PLAYBACK_STAGES).
STAGES = frozenset((
    'credentials', 'receiver-scan', 'connect', 'timing-bind',
    'authenticate', 'setup-base', 'event-connect', 'info', 'record', 'setup-stream',
    'command', 'await-playing', 'feedback', 'unknown'))

# Final playback outcomes.
OUTCOMES = ('stopped', 'timeout', 'rejected', 'network', 'failed', 'cancelled',
            'pairing_required', 'pairing_failed', 'receiver_unavailable', 'busy')

# Bounded-trace limits.
MAX_ROWS = 256
MAX_UNKNOWN_EVENTS = 32
MAX_LABELS = 16

# Private event-metadata sidecar limits: at most this many rows per file, and
# a finite byte cap on the whole file so a runaway writer cannot grow it.
MAX_METADATA_EVENTS = 64
MAX_METADATA_BYTES = 16384

# Opt-in bounded /playback-info probe. At most two GETs at fixed offsets after
# the command batch, a tight per-request deadline, and a response-body cap so an
# oversized binary plist is never parsed or serialized.
PROBE_STATUS = ('ok', 'rejected', 'timeout', 'invalid', 'unsupported', 'empty')
RATE_KINDS = ('zero', 'one', 'other')
PROBE_ORIGINS = ('origin-mp4', 'origin-hls')
PROBE_DELAYS = (0.5, 2.0)
PROBE_TIMEOUT = 2.0
PROBE_MAX_BODY = 65536


def classify_url(url):
    """Return ``(media_type, fixture)`` without retaining the URL."""
    if not isinstance(url, str):
        return ('other', 'other')
    if url == PUBLIC_HLS_MASTER:
        fixture = 'public-hls-master'
    elif url == PUBLIC_MP4:
        fixture = 'public-mp4'
    else:
        fixture = 'other'
    path = url.split('?', 1)[0].split('#', 1)[0].lower()
    if path.endswith('.m3u8') or path.endswith('.m3u'):
        media = 'hls'
    elif path.endswith('.mp4'):
        media = 'mp4'
    else:
        media = 'other'
    return (media, fixture)


def normalize_event(data):
    """Reduce a raw receiver event to a fixed, secret-free summary.

    Always emits ``type`` (finite allowlist) and ``state`` (finite allowlist),
    matching the pre-existing contract. When an explicit error dict is present
    under ``event['error']`` or ``event['params']['error']`` (fixed keys at
    depth one from the event; no generic unknown-key scraping), additionally
    emits:

      * ``hasError``  bool True — an error dict was present.
      * ``domain``    a recognized Apple error domain, else ``'other'``.
      * ``code``      a signed 32-bit int taken only from the error dict's
                      ``code`` field; any non-int or out-of-range value is
                      dropped, never coerced from str/float/bool.

    When a URL-bearing ``url`` field is present under the event or ``params``,
    emits ``hasUrl`` bool True — presence only; the URL is never emitted.

    Collision precedence (documented): a top-level ``error`` dict wins over
    ``params['error']``; ``params['playbackState']`` wins over a top-level
    ``name`` for ``state``. Extraction is bounded to these fixed keys at depth
    one from the event; deeper structures are never walked. No URL, host, PIN,
    credential, request body, exception text, property name, identifier, raw
    event name, or string hash is ever emitted.
    """
    if not isinstance(data, dict):
        return {'type': 'other', 'state': 'other'}
    etype = data.get('type')
    if not isinstance(etype, str) or etype not in EVENT_TYPES:
        etype = 'other'
    params = data.get('params')
    state = None
    if isinstance(params, dict):
        state = params.get('playbackState')
    if state is None:
        state = data.get('name')
    if not isinstance(state, str) or state not in EVENT_STATES:
        state = 'other'
    result = {}  # type: dict[str, object]
    result['type'] = etype
    result['state'] = state

    error = None
    if isinstance(data.get('error'), dict):
        error = data['error']
    elif isinstance(params, dict) and isinstance(params.get('error'), dict):
        error = params['error']
    if error is not None:
        result['hasError'] = True
        domain = error.get('domain')
        result['domain'] = domain if isinstance(domain, str) and domain in ERROR_DOMAINS else 'other'
        code = _s32(error.get('code'))
        if code is not None:
            result['code'] = code

    if 'url' in data or (isinstance(params, dict) and 'url' in params):
        result['hasUrl'] = True

    return result


def _enum(values, value):
    return value if isinstance(value, str) and value in values else None


def playback_info_row(data):
    """Reduce a decoded ``/playback-info`` plist to fixed, secret-free fields.

    Returns a dict with at most the ``readyToPlay``/``playbackBufferEmpty``/
    ``playbackBufferFull``/``playbackLikelyToKeepUp`` booleans (``type(value) is
    bool`` only, so a missing field is distinct from an explicit false), a
    normalized ``rate`` bucket (``zero``/``one``/``other``; no raw floats), and
    a top-level ``error`` domain/code. Returns ``None`` for non-dict data.
    Never emits raw floats, strings, URLs, or any non-allowlisted value.
    """
    if not isinstance(data, dict):
        return None
    row = {}  # type: dict[str, object]
    for key in ('readyToPlay', 'playbackBufferEmpty', 'playbackBufferFull', 'playbackLikelyToKeepUp'):
        value = data.get(key)
        if type(value) is bool:
            row[key] = value
    rate = data.get('rate')
    if rate is None:
        rate = data.get('playbackRate')
    if type(rate) is int or type(rate) is float:
        if not math.isfinite(rate):
            row['rate'] = 'other'
        elif rate == 0:
            row['rate'] = 'zero'
        elif rate == 1:
            row['rate'] = 'one'
        else:
            row['rate'] = 'other'
    error = data.get('error')
    if isinstance(error, dict):
        domain = error.get('domain')
        row['domain'] = domain if isinstance(domain, str) and domain in ERROR_DOMAINS else 'other'
        code = _s32(error.get('code'))
        if code is not None:
            row['code'] = code
    return row


def _code(value):
    return value if type(value) is int and 100 <= value <= 599 else None


def _small_int(lo, hi, value):
    return value if type(value) is int and lo <= value <= hi else None


def _s32(value):
    """Signed 32-bit int only; reject bool/float/str/None/containers."""
    return value if type(value) is int and -2147483648 <= value <= 2147483647 else None


def _stage(value):
    return value if isinstance(value, str) and value in STAGES else None


_SCHEMA = ('input', 'stage', 'event', 'channel', 'startup', 'outcome', 'close', 'pairing', 'probe')


def sanitize(kind, fields):
    """Keep only allowlisted fields for ``kind``; return ``None`` if unusable."""
    if kind not in _SCHEMA or not isinstance(fields, dict):
        return None
    row = {}  # type: dict[str, object]
    row['k'] = kind
    if kind == 'input':
        media = _enum(MEDIA_TYPES, fields.get('media'))
        fixture = _enum(FIXTURES, fields.get('fixture'))
        if media is not None:
            row['media'] = media
        if fixture is not None:
            row['fixture'] = fixture
    elif kind == 'stage':
        stage = _stage(fields.get('stage'))
        if stage is not None:
            row['stage'] = stage
        code = _code(fields.get('code'))
        if code is not None:
            row['code'] = code
    elif kind == 'event':
        etype = _enum(EVENT_TYPES, fields.get('type'))
        state = _enum(EVENT_STATES, fields.get('state'))
        domain = _enum(ERROR_DOMAINS, fields.get('domain'))
        code = _s32(fields.get('code'))
        has_error = fields.get('hasError')
        has_url = fields.get('hasUrl')
        if etype is not None:
            row['type'] = etype
        if state is not None:
            row['state'] = state
        if domain is not None:
            row['domain'] = domain
        if code is not None:
            row['code'] = code
        if type(has_error) is bool:
            row['hasError'] = has_error
        if type(has_url) is bool:
            row['hasUrl'] = has_url
    elif kind == 'pairing':
        phase = _enum(('begin', 'ready', 'failed'), fields.get('phase'))
        if phase is not None:
            row['phase'] = phase
    elif kind == 'channel':
        status = _enum(CHANNEL_STATUS, fields.get('status'))
        if status is not None:
            row['status'] = status
    elif kind == 'startup':
        timeout_ms = _small_int(0, 60000, fields.get('timeout_ms'))
        if timeout_ms is not None:
            row['timeout_ms'] = timeout_ms
    elif kind == 'outcome':
        outcome = _enum(OUTCOMES, fields.get('outcome'))
        if outcome is not None:
            row['outcome'] = outcome
        stage = _stage(fields.get('stage'))
        if stage is not None:
            row['stage'] = stage
    elif kind == 'close':
        stage = _stage(fields.get('stage'))
        if stage is not None:
            row['stage'] = stage
    elif kind == 'probe':
        status = _enum(PROBE_STATUS, fields.get('status'))
        if status is not None:
            row['status'] = status
        code = _code(fields.get('httpCode'))
        if code is not None:
            row['httpCode'] = code
        if type(fields.get('quarantined')) is bool:
            row['quarantined'] = fields['quarantined']
        for key in ('readyToPlay', 'playbackBufferEmpty', 'playbackBufferFull', 'playbackLikelyToKeepUp'):
            value = fields.get(key)
            if type(value) is bool:
                row[key] = value
        rate = _enum(RATE_KINDS, fields.get('rate'))
        if rate is not None:
            row['rate'] = rate
        domain = _enum(ERROR_DOMAINS, fields.get('domain'))
        if domain is not None:
            row['domain'] = domain
        code = _s32(fields.get('code'))
        if code is not None:
            row['code'] = code
    return row


def resolve_env(environ, *, frozen, development):
    """Return ``(trace_path, startup_seconds)`` or ``(None, None)``.

    Both variables are honored only in a frozen development build. ``startup``
    accepts only ``'10'`` and ``'30'`` and is valid only when the trace path is
    opted in; production ignores both.
    """
    if not frozen or not development:
        return (None, None)
    path = environ.get('PEARPLAY_DIAGNOSTIC_TRACE')
    if not isinstance(path, str) or not path:
        return (None, None)
    startup = None
    raw = environ.get('PEARPLAY_DIAGNOSTIC_STARTUP_SECONDS')
    if raw in ('10', '30'):
        startup = int(raw)
    return (path, startup)


def _open_owner_only_append(path, *, readable=False):
    """Open a pre-created owner-only regular file for append, or return None.

    Rejects relative paths, symlinks (O_NOFOLLOW), non-regular files, files
    not owned by the current UID, and any group/other permission bit. Any
    failure returns None so the caller disables silently; nothing is created
    and secrets are never written.
    """
    if not os.path.isabs(path):
        return None
    try:
        access = os.O_RDWR if readable else os.O_WRONLY
        fd = os.open(os.fspath(path), access | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise OSError('not a regular file')
        if info.st_uid != os.geteuid():
            raise OSError('not owned by caller')
        if info.st_mode & 0o077:
            raise OSError('not owner-only')
    except OSError:
        try:
            os.close(fd)
        except OSError:
            pass
        return None
    return fd


class DiagnosticTrace:
    """Best-effort JSON-lines trace to a pre-created owner-only regular file."""

    def __init__(self, path):
        self.disabled = True
        self.rows = 0
        self._fd = None
        self._unknown_events = 0
        self._start = time.monotonic()
        self._open(path)

    def _open(self, path):
        self._fd = _open_owner_only_append(path)
        self.disabled = self._fd is None

    def __call__(self, kind, **fields):
        if self.disabled or self._fd is None or self.rows >= MAX_ROWS:
            return
        row = sanitize(kind, fields)
        if row is None:
            return
        # Cap the stream of unknown-shaped events so a noisy receiver cannot
        # fill the trace; known events still record afterwards.
        if kind == 'event' and row.get('type') == 'other':
            self._unknown_events += 1
            if self._unknown_events > MAX_UNKNOWN_EVENTS:
                return
        row['t'] = int((time.monotonic() - self._start) * 1000)
        try:
            os.write(self._fd, (json.dumps(row, separators=(',', ':'), ensure_ascii=True) + '\n').encode('utf-8'))
            self.rows += 1
        except OSError:
            self.disabled = True


def event_label(data):
    """Return a safe unknown event-type label from a decoded event, or None.

    Accepts only the top-level ``type`` string when it is not one of the known
    ``EVENT_TYPES`` and matches ASCII letters only (``[A-Za-z]{1,48}``).
    Returns None for anything else: non-dict data, non-string types, known
    types, and any value containing digits, punctuation, whitespace, non-ASCII
    characters, or exceeding 48 characters. No other field is ever read.
    """
    if not isinstance(data, dict):
        return None
    etype = data.get('type')
    if not isinstance(etype, str):
        return None
    if etype in EVENT_TYPES:
        return None
    if re.fullmatch(r'[A-Za-z]{1,48}', etype) is None:
        return None
    return etype


# Name/kind status markers emitted so an absent field is never confused with
# a present-but-unusable one. ``captured`` is not a literal marker: a captured
# value is written as the label itself.
NAME_KIND_MARKERS = ('missing', 'invalid', 'filtered')


def _name_kind(data, key):
    """Return a captured label or a status marker for a top-level name/kind.

    ``missing`` means the key is absent; ``invalid`` means it is present but
    not a string; ``filtered`` means it is a string that fails the ASCII
    letters ``[A-Za-z]{1,48}`` allowlist. A matching label is returned as-is.
    No other field is read and nothing else is ever emitted.
    """
    if key not in data:
        return 'missing'
    value = data[key]
    if not isinstance(value, str):
        return 'invalid'
    if re.fullmatch(r'[A-Za-z]{1,48}', value) is None:
        return 'filtered'
    return value


def event_metadata(data):
    """Reduce a top-level ``notification`` event to a private, secret-free row.

    Returns None unless ``data`` is a dict whose top-level ``type`` is exactly
    ``'notification'``; every other event is filtered out by the caller. For a
    notification, always emits ``name`` and ``kind``, each either a captured
    ``[A-Za-z]{1,48}`` label or one of the ``missing``/``invalid``/``filtered``
    markers, so an absent field is distinguishable from a present-but-unusable
    one. When an explicit error dict is present under ``event['error']`` or
    ``event['params']['error']`` (fixed keys, no generic scraping), also emits
    ``domain`` (a recognized Apple error domain, else ``'other'``) and, when
    the error's ``code`` is a signed 32-bit int, ``code``. No URL, host, body,
    identifier, PIN, credential, session key, request body, or other value is
    ever emitted.
    """
    if not isinstance(data, dict) or data.get('type') != 'notification':
        return None
    result = {}  # type: dict[str, object]
    result['name'] = _name_kind(data, 'name')
    result['kind'] = _name_kind(data, 'kind')

    params = data.get('params')
    error = None
    if isinstance(data.get('error'), dict):
        error = data['error']
    elif isinstance(params, dict) and isinstance(params.get('error'), dict):
        error = params['error']
    if error is not None:
        domain = error.get('domain')
        result['domain'] = domain if isinstance(domain, str) and domain in ERROR_DOMAINS else 'other'
        code = _s32(error.get('code'))
        if code is not None:
            result['code'] = code

    return result


def _valid_name_kind(value):
    """True for a captured label or a status marker (never anything else)."""
    return isinstance(value, str) and (
        value in NAME_KIND_MARKERS or re.fullmatch(r'[A-Za-z]{1,48}', value) is not None)


def _valid_metadata_row(row):
    """True when ``row`` is exactly one valid event-metadata sidecar row."""
    if not isinstance(row, dict):
        return False
    if not {'seq', 't', 'name', 'kind'} <= set(row) or not set(row) <= {'seq', 't', 'name', 'kind', 'domain', 'code'}:
        return False
    if not isinstance(row['seq'], int) or row['seq'] < 0:
        return False
    if not isinstance(row['t'], int) or row['t'] < 0:
        return False
    if not _valid_name_kind(row['name']) or not _valid_name_kind(row['kind']):
        return False
    if 'domain' in row and row['domain'] not in ERROR_DOMAINS:
        return False
    if 'code' in row and _s32(row['code']) is None:
        return False
    return True


def resolve_event_metadata(environ, *, frozen, development):
    """Return the opt-in event-metadata sidecar path, or None.

    Honored only when the frozen development gate passes AND the normal
    diagnostic trace is also opted in, so the sidecar is never written in
    production or when the trace is absent. Returns the raw path string for
    the caller to open securely, or None.
    """
    if not frozen or not development:
        return None
    if resolve_env(environ, frozen=frozen, development=development)[0] is None:
        return None
    path = environ.get('PEARPLAY_DIAGNOSTIC_EVENT_METADATA')
    if not isinstance(path, str) or not path:
        return None
    return path


def resolve_event_labels(environ, *, frozen, development):
    """Return the opt-in event-label sidecar path, or None.

    Honored only when the frozen development gate passes AND the normal
    diagnostic trace is also opted in, so the sidecar is never written in
    production or when the trace is absent. Returns the raw path string for
    the caller to open securely, or None.
    """
    if not frozen or not development:
        return None
    if resolve_env(environ, frozen=frozen, development=development)[0] is None:
        return None
    path = environ.get('PEARPLAY_DIAGNOSTIC_EVENT_LABELS')
    if not isinstance(path, str) or not path:
        return None
    return path


def resolve_probe_playback_info(environ, *, frozen, development):
    """Return the opt-in playback-info probe origin, or None.

    Honored only when the frozen development gate passes AND the normal
    diagnostic trace is opted in, so the probe never runs in production or when
    the trace is absent. Accepts only ``'origin-mp4'``/``'origin-hls'``; any
    other value is ignored.
    """
    if not frozen or not development:
        return None
    if resolve_env(environ, frozen=frozen, development=development)[0] is None:
        return None
    value = environ.get('PEARPLAY_DIAGNOSTIC_PROBE_PLAYBACK_INFO')
    if value in PROBE_ORIGINS:
        return value
    return None


class EventLabelCollector:
    """Best-effort writer of unique unknown event-type labels.

    Appends at most ``MAX_LABELS`` distinct labels, each as a single
    ``eventType`` field per JSON line, to a pre-created owner-only regular
    file. Reuses the same no-follow owner-only append-only opening as
    ``DiagnosticTrace``; any failure disables silently and never alters
    playback or the normal trace.
    """

    def __init__(self, path):
        self.disabled = True
        self.count = 0
        self._fd = None
        self._seen = set()
        self._open(path)

    def _open(self, path):
        self._fd = _open_owner_only_append(path, readable=True)
        self.disabled = self._fd is None

    def __call__(self, data):
        if self.disabled or self._fd is None or self.count >= MAX_LABELS:
            return
        label = event_label(data)
        if label is None or label in self._seen:
            return
        row = {'eventType': label}
        import fcntl
        locked = False
        try:
            # Bound/deduplicate the file across native hosts; never wait on a writer.
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            os.lseek(self._fd, 0, os.SEEK_SET)
            raw = os.read(self._fd, 2049)
            if len(raw) > 2048:
                self.disabled = True
                return
            existing = [json.loads(line) for line in raw.splitlines()]
            if any(not isinstance(r, dict) or set(r) != {'eventType'} or
                   event_label({'type': r['eventType']}) is None for r in existing):
                self.disabled = True
                return
            self._seen = {r['eventType'] for r in existing}
            self.count = len(existing)
            if self.count >= MAX_LABELS or label in self._seen:
                return
            payload = (json.dumps(row, separators=(',', ':'), ensure_ascii=True) + '\n').encode('utf-8')
            if os.write(self._fd, payload) != len(payload):
                self.disabled = True
                return
            self._seen.add(label)
            self.count += 1
        except (OSError, ValueError):
            self.disabled = True
        finally:
            if locked:
                try: fcntl.flock(self._fd, fcntl.LOCK_UN)
                except OSError: self.disabled = True


class EventMetadataCollector:
    """Best-effort writer of private notification event metadata.

    Appends at most ``MAX_METADATA_EVENTS`` rows to a pre-created owner-only
    regular file, one JSON line each. Only top-level ``notification`` events
    produce a row; every row carries a global ``seq`` (the count of existing
    rows, so ordering survives across helper processes without any process
    identifier) and a per-collector relative ``t`` (milliseconds since this
    collector started). Reuses the no-follow owner-only append opening, a
    nonblocking flock, and strict validation of every pre-existing row before
    appending; any failure disables silently and never alters playback or the
    normal trace. A finite byte cap bounds the whole file across processes.
    """

    def __init__(self, path):
        self.disabled = True
        self.count = 0
        self._fd = None
        self._start = time.monotonic()
        self._open(path)

    def _open(self, path):
        self._fd = _open_owner_only_append(path, readable=True)
        self.disabled = self._fd is None

    def __call__(self, data):
        if self.disabled or self._fd is None or self.count >= MAX_METADATA_EVENTS:
            return
        row = event_metadata(data)
        if row is None:
            return
        import fcntl
        locked = False
        try:
            # Bound/sequence the file across native hosts; never wait on a writer.
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            os.lseek(self._fd, 0, os.SEEK_SET)
            raw = os.read(self._fd, MAX_METADATA_BYTES + 1)
            if len(raw) > MAX_METADATA_BYTES:
                self.disabled = True
                return
            existing = [json.loads(line) for line in raw.splitlines() if line]
            if len(existing) > MAX_METADATA_EVENTS:
                self.disabled = True
                return
            for index, entry in enumerate(existing):
                if not _valid_metadata_row(entry) or entry['seq'] != index:
                    self.disabled = True
                    return
            seq = len(existing)
            self.count = seq
            if seq >= MAX_METADATA_EVENTS:
                return
            out = dict(row)
            out['seq'] = seq
            out['t'] = int((time.monotonic() - self._start) * 1000)
            payload = (json.dumps(out, separators=(',', ':'), ensure_ascii=True) + '\n').encode('utf-8')
            if len(raw) + len(payload) > MAX_METADATA_BYTES:
                self.disabled = True
                return
            if os.write(self._fd, payload) != len(payload):
                self.disabled = True
                return
            self.count += 1
        except (OSError, ValueError):
            self.disabled = True
        finally:
            if locked:
                try: fcntl.flock(self._fd, fcntl.LOCK_UN)
                except OSError: self.disabled = True
