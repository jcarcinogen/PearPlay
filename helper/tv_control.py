"""Session-local AirPlay rate controls; never open a second receiver connection."""
import asyncio
import plistlib


class RateControl:
    def __init__(self, session, notify):
        self.session = session
        self.notify = notify
        self.closed = False
        self.state = None
        self._wire_lock = asyncio.Lock()
        self._control_lock = asyncio.Lock()
        self._pending = None
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
            self.state = state
            self.notify(state, 'protocol')
            if self._pending is not None and self._pending[0] == state:
                self._pending[1].set()

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
