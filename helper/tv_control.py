"""Session-local AirPlay rate controls; never open a second receiver connection."""
import asyncio
import plistlib
import math
import time


def media_seconds(value):
    """Decode a finite, nonnegative CMTime; invalid/indefinite is not zero."""
    if not isinstance(value, dict):
        raise ValueError('invalid_media_time')
    numerator, scale = value.get('value'), value.get('timescale')
    flags, epoch = value.get('flags'), value.get('epoch')
    if (type(numerator) is not int or type(scale) is not int or
            type(flags) is not int or flags not in (1, 3) or
            type(epoch) is not int or epoch != 0 or
            not 0 <= numerator <= 2**63 - 1 or not 0 < scale <= 2**31 - 1):
        raise ValueError('invalid_media_time')
    seconds = numerator / scale
    if seconds > 31_536_000:
        raise ValueError('invalid_media_time')
    return seconds


def position_snapshot(info):
    if not isinstance(info, dict):
        raise ValueError('invalid_playback_info')
    position = media_seconds(info.get('position'))
    duration = media_seconds(info['duration']) if info.get('duration') is not None else None
    rate = info.get('rate')
    if type(rate) not in (int, float) or not math.isfinite(rate) or rate not in (0, 1):
        raise ValueError('invalid_rate')
    ranges = info.get('seekableTimeRanges', [])
    if not isinstance(ranges, list) or len(ranges) > 16:
        raise ValueError('invalid_ranges')
    seekable = []
    for item in ranges:
        if not isinstance(item, dict):
            raise ValueError('invalid_range')
        start, length = media_seconds(item.get('start')), media_seconds(item.get('duration'))
        end = start + length
        if end > 31_536_000 or seekable and start < seekable[-1]['end']:
            raise ValueError('invalid_range')
        if length:
            seekable.append({'start': start, 'end': end})
    if duration is not None and position > duration + 1:
        raise ValueError('invalid_position')
    return {'position': position, 'duration': duration, 'rate': rate,
            'seekable': seekable, 'canSeek': False}


class RateControl:
    def __init__(self, session, notify):
        self.session = session
        self.notify = notify
        self.closed = False
        self.state = None
        self._wire_lock = asyncio.Lock()
        self._control_lock = asyncio.Lock()
        self._pending = None
        self._position = None
        self._position_at = 0.0
        self._position_pending = None
        self._position_enabled = True
        self._message_id = 0
        self._call = session.call
        self._on_event = session.on_event
        session.call = self.call
        session.on_event = self.on_event

    @property
    def available(self):
        return not self.closed and self.session.started and not self.session.finished.is_set() and self.state in ('playing', 'paused')

    def close(self):
        if self.closed:
            return
        self.closed = True
        self._position = None
        if self._position_pending is not None:
            future = self._position_pending[1]
            if not future.done():
                future.set_result(None)
        self.session.finished.set()
        if self._pending is not None:
            self._pending[1].set()
        self.session.wire.close()

    async def call(self, stage, body=None):
        # The pinned HTTP transport matches replies FIFO. Never reuse it after
        # an interrupted request whose late reply could satisfy a later call.
        async with self._wire_lock:
            if self.closed:
                raise RuntimeError('control_closed')
            try:
                return await self._call(stage, body)
            except BaseException:
                self.close()
                raise

    def on_event(self, data):
        if self.closed:
            return
        self._on_event(data)
        if isinstance(data, dict) and data.get('kind') == 'response':
            pending = self._position_pending
            if (pending is not None and type(data.get('messageID')) is int and
                    data['messageID'] == pending[0] and not pending[1].done()):
                try:
                    snapshot = position_snapshot(data.get('info'))
                except (ValueError, TypeError, OverflowError):
                    snapshot = None
                pending[1].set_result(snapshot)
            return
        if not isinstance(data, dict) or data.get('type') != 'playbackState':
            return
        params = data.get('params', {})
        state = params.get('playbackState') if isinstance(params, dict) else None
        state = state or data.get('name')
        if state == 'stopped' and self.session.started:
            self.state = 'stopped'
            if self._pending is not None:
                self._pending[1].set()
        elif state in ('playing', 'paused') and self.session.started:
            if state != self.state:
                self._position = None
            self.state = state
            self.notify(state, 'protocol')
            if self._pending is not None and self._pending[0] == state:
                self._pending[1].set()

    def timeline(self):
        age = time.monotonic() - self._position_at
        if not self.available or self._position is None or not 0 <= age <= 10:
            return None
        return {**self._position,
                'seekable': [dict(item) for item in self._position['seekable']],
                'ageMs': int(age * 1000)}

    async def refresh_position(self):
        """Read-only, correlated event response; optional metadata is fail-soft.

        A completed HTTP write with no matching event disables metadata for this
        cast. An interrupted HTTP exchange still closes the ambiguous FIFO wire.
        """
        async with self._control_lock:
            if not self.available or not self._position_enabled:
                return
            if self._position is not None and time.monotonic() - self._position_at < 1:
                return
            self._message_id += 1
            future = asyncio.get_running_loop().create_future()
            self._position_pending = (self._message_id, future)
            command = {'type': 'playbackInfo', 'kind': 'request', 'messageID': self._message_id}
            body = plistlib.dumps({'params': {'data': plistlib.dumps(command, fmt=plistlib.FMT_BINARY)}}, fmt=plistlib.FMT_BINARY)
            try:
                async with self._wire_lock:
                    if not self.available:
                        return
                    try:
                        async with asyncio.timeout(min(self.session.timeout, 3)):
                            await self._call('command-resend', body)
                    except BaseException:
                        self.close()
                        raise
                async with asyncio.timeout(min(self.session.timeout, 3)):
                    snapshot = await future
                if self.available:
                    self._position = snapshot
                    self._position_at = time.monotonic()
                    if snapshot is None:
                        self._position_enabled = False
            except asyncio.CancelledError:
                self._position = None
                self._position_enabled = False
                raise
            except Exception:
                self._position = None
                self._position_enabled = False
            finally:
                self._position_pending = None
                if not future.done():
                    future.cancel()

    async def set_rate(self, op):
        expected, desired, rate = ('playing', 'paused', 0.0) if op == 'pause' else ('paused', 'playing', 1.0)
        if op not in ('pause', 'resume') or not self.available or self.state != expected:
            raise ValueError('control_unavailable')
        async with self._control_lock:
            # Queueing cannot retarget a command to a changed/ended session.
            if not self.available or self.state != expected:
                raise ValueError('control_unavailable')
            event = asyncio.Event()
            body = plistlib.dumps({'params': {'data': plistlib.dumps({'type': 'setRate', 'rate': rate}, fmt=plistlib.FMT_BINARY)}}, fmt=plistlib.FMT_BINARY)
            try:
                async with asyncio.timeout(self.session.timeout):
                    async with self._wire_lock:
                        if not self.available or self.state != expected:
                            raise ValueError('control_unavailable')
                        self._pending = (desired, event)
                        await self._call('command-resend', body)
                    # HTTP 200 is not confirmation that the receiver paused.
                    await event.wait()
                    if self.closed or self.session.finished.is_set() or self.state != desired:
                        raise RuntimeError('control_unconfirmed')
            except BaseException:
                self.close()
                raise
            finally:
                self._pending = None
