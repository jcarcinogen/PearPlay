"""Startup-feedback experiment: periodic keep-alive feedback during the loading
phase (after stream setup, before/while awaiting ``playing``) must not disturb
stage attribution, startup timeouts, or cleanup.

These tests use the real ``Session`` (standalone) and real ``Transport`` (native)
against fake wires. No network access; no pyatv required at the injected boundaries.
"""
import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_helper_protocol import load

IDENTIFIER = 'AA:BB:CC:DD:EE:FF'


def _fire(wire_log, callback, name):
    loop = asyncio.get_running_loop()
    wire_log.append((name, loop.time()))
    callback({'type': 'playbackState', 'name': name})


class StandaloneWire:
    """Fake wire for the standalone ``Session`` path (no shared stage)."""
    def __init__(self, log, playing_delay, feedback_error=None):
        self.log = log
        self.playing_delay = playing_delay
        self.feedback_error = feedback_error
        self.closed = False
        self.timing_port = None

    async def timing(self, port):
        self.timing_port = port

    async def request(self, stage, body=None, headers=None):
        if stage == 'setup-base':
            return {'eventPort': 1234}
        if stage == 'setup-stream':
            return {'streams': [{'streamID': 1}]}
        if stage == 'feedback':
            loop = asyncio.get_running_loop()
            self.log.append(('feedback', loop.time()))
            if self.feedback_error is not None:
                raise self.feedback_error
        return {}

    async def events(self, port, callback):
        if self.playing_delay is None:
            return
        loop = asyncio.get_running_loop()
        loop.call_later(self.playing_delay, lambda: _fire(self.log, callback, 'playing'))
        loop.call_later(self.playing_delay + 0.01, lambda: _fire(self.log, callback, 'stopped'))

    def close(self):
        self.closed = True


def native_backend(log, playing_delay, feedback_error=None):
    """Fake native backend mirroring Backend's shared-stage contract.

    For non-exempt stages it mutates the shared stage list and reports, exactly
    like the real ``Backend.request``; feedback and rate re-sends only report
    the HTTP response (the real backend must not clobber the shared stage on a
    heartbeat or a re-send).
    """
    class Wire:
        def __init__(self, connection, credentials, timeout, report, stage):
            self.report = report
            self.stage = stage
            self.log = log
            self.playing_delay = playing_delay
            self.feedback_error = feedback_error
            self.closed = False
            self.timing_port = None

        async def timing(self, port):
            self.timing_port = port

        async def request(self, stage, body=None, headers=None):
            if stage not in ('feedback', 'command-resend'):
                self.stage[0] = stage
                self.report('stage', stage=stage)
            if stage == 'setup-base':
                return {'eventPort': 1234}
            if stage == 'setup-stream':
                return {'streams': [{'streamID': 1}]}
            if stage == 'feedback':
                loop = asyncio.get_running_loop()
                self.log.append(('feedback', loop.time()))
                if self.feedback_error is not None:
                    raise self.feedback_error
                self.report('http-response', stage='feedback', code=200)
            return {}

        async def events(self, port, callback):
            if self.playing_delay is None:
                return
            loop = asyncio.get_running_loop()
            loop.call_later(self.playing_delay, lambda: _fire(self.log, callback, 'playing'))
            loop.call_later(self.playing_delay + 0.01, lambda: _fire(self.log, callback, 'stopped'))

        def close(self):
            self.closed = True
    return Wire


class StartupFeedbackTests(unittest.IsolatedAsyncioTestCase):
    def make_transport(self, m, command, directory, *, timeout=10.0, startup_timeout=None,
                       feedback_interval=0.02, log=None, playing_delay=None, feedback_error=None):
        device = SimpleNamespace(identifier=IDENTIFIER, address='127.0.0.1',
                                 get_service=lambda _: SimpleNamespace(port=7000))

        async def scan(*a, **k):
            return [device]

        async def connect(*a):
            return SimpleNamespace(close=lambda: None)

        store = command.existing().Store()
        store.root = Path(directory).resolve() / 'state'
        store.save(dict(identifier=device.identifier, credentials='private-credential'))
        backend = native_backend(log, playing_delay, feedback_error)
        t = m.Transport(api=SimpleNamespace(scan=scan, Protocol=SimpleNamespace(AirPlay=1)),
                        command=command, store=store, connect=connect, parse=lambda x: x,
                        backend=backend, timeout=timeout, startup_timeout=startup_timeout,
                        feedback_interval=feedback_interval)
        return t, device

    async def test_immediate_feedback_precedes_info_after_event_channel(self):
        m = load(); command = m.spike()
        order = []

        class OrderingWire(StandaloneWire):
            async def request(self, stage, body=None, headers=None):
                order.append(stage)
                return await super().request(stage, body, headers)

            async def events(self, port, callback):
                order.append('events')
                return await super().events(port, callback)

        wire = OrderingWire([], playing_delay=0.05)
        session = command.Session(wire, timeout=1.0, feedback_interval=0.5)
        await session.run(49170, 'https://example.org/a.mp4', 2.0)
        self.assertLess(order.index('events'), order.index('feedback'))
        self.assertLess(order.index('feedback'), order.index('info'))

    async def test_standalone_session_sends_feedback_before_playing(self):
        m = load(); command = m.spike()
        log = []
        wire = StandaloneWire(log, playing_delay=0.08)
        session = command.Session(wire, timeout=1.0, feedback_interval=0.02)
        await session.run(49170, 'https://example.org/a.mp4', 2.0)
        kinds = [kind for kind, _ in log]
        self.assertIn('feedback', kinds)
        self.assertLess(kinds.index('feedback'), kinds.index('playing'))
        self.assertTrue(wire.closed)

    async def test_feedback_repeats_at_intervals_during_loading(self):
        m = load(); command = m.spike()
        log = []
        wire = StandaloneWire(log, playing_delay=0.10)
        session = command.Session(wire, timeout=1.0, feedback_interval=0.02)
        await session.run(49170, 'https://example.org/a.mp4', 2.0)
        feedbacks = [k for k, _ in log if k == 'feedback']
        self.assertGreaterEqual(len(feedbacks), 2)

    async def test_native_transport_sends_feedback_before_playing(self):
        m = load(); command = m.spike()
        log = []
        with tempfile.TemporaryDirectory() as directory:
            t, device = self.make_transport(m, command, directory, timeout=1.0,
                                            feedback_interval=0.02, log=log, playing_delay=0.08)
            await t.run(dict(receiver=device.identifier, host='127.0.0.1', url='https://example.org/a.mp4'),
                        lambda *x: None)
        kinds = [kind for kind, _ in log]
        self.assertIn('feedback', kinds)
        self.assertLess(kinds.index('feedback'), kinds.index('playing'))
        self.assertTrue(t.wire.closed)

    async def test_cancel_during_loading_awaits_feedback_and_closes_wire(self):
        m = load(); command = m.spike()
        log = []
        wire = StandaloneWire(log, playing_delay=None)
        session = command.Session(wire, timeout=1.0, feedback_interval=0.02)
        task = asyncio.create_task(session.run(49170, 'https://example.org/a.mp4', 10.0))
        await asyncio.sleep(0.06)
        feedback = session._feedback_task
        self.assertIsNotNone(feedback)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(task.cancelled())
        self.assertTrue(feedback.cancelled())
        self.assertTrue(wire.closed)
        self.assertIsNone(session._feedback_task)
        self.assertFalse([t for t in asyncio.all_tasks() if t is not asyncio.current_task()])

    async def assert_cancelled_promptly(self, task):
        # asyncio.wait does not cancel the task when this test guard expires.
        # Rescue only after recording failure, so a swallowed cancel stays red.
        done, _ = await asyncio.wait({task}, timeout=0.1)
        try:
            self.assertIn(task, done, 'cancellation was swallowed at completion')
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(task.cancelled())
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_feedback_cancel_at_request_completion_is_not_swallowed(self):
        for boundary in ('command-resend', 'feedback'):
            with self.subTest(boundary=boundary):
                command = load().spike()
                task = None

                class CompletionWire(StandaloneWire):
                    async def request(self, stage, body=None, headers=None):
                        result = await super().request(stage, body, headers)
                        if stage == boundary:
                            # Complete the child in the same turn as cancelling
                            # its owner: the Python 3.11 wait_for race.
                            assert task is not None
                            task.cancel()
                        return result

                wire = CompletionWire([], playing_delay=None)
                session = command.Session(wire, timeout=1.0, feedback_interval=0.02)
                task = asyncio.create_task(session._feedback_loop())
                await self.assert_cancelled_promptly(task)
                self.assertFalse([t for t in asyncio.all_tasks()
                                  if t is not asyncio.current_task()])

    async def test_run_cancel_at_startup_completion_is_not_swallowed(self):
        for boundary in ('authenticate', 'events', 'playing'):
            with self.subTest(boundary=boundary):
                command = load().spike()
                task = None

                class CompletionWire(StandaloneWire):
                    async def request(self, stage, body=None, headers=None):
                        result = await super().request(stage, body, headers)
                        if stage == boundary:
                            assert task is not None
                            task.cancel()
                        return result

                    async def events(self, port, callback):
                        if boundary == 'events':
                            assert task is not None
                            task.cancel()

                class CompletionEvent(asyncio.Event):
                    async def wait(self):
                        result = await super().wait()
                        assert task is not None
                        task.cancel()
                        return result

                wire = CompletionWire([], playing_delay=None)
                session = command.Session(wire, timeout=1.0, feedback_interval=0.02)
                if boundary == 'playing':
                    session.playing = CompletionEvent()
                    session.playing.set()
                task = asyncio.create_task(session.run(49170, 'https://example.org/a.mp4', 10.0))
                await self.assert_cancelled_promptly(task)
                self.assertTrue(wire.closed)
                self.assertIsNone(session._feedback_task)
                self.assertFalse([t for t in asyncio.all_tasks()
                                  if t is not asyncio.current_task()])

    async def test_repeated_cancel_waits_for_feedback_cleanup_before_closing(self):
        for outcome in ('cancel', 'complete-then-cancel', 'deadline'):
            with self.subTest(outcome=outcome):
                command = load().spike()
                entered = asyncio.Event()
                cleaning = asyncio.Event()
                release = asyncio.Event()
                cleaned = asyncio.Event()

                class CleanupWire(StandaloneWire):
                    async def request(self, stage, body=None, headers=None):
                        if stage == 'command-resend':
                            entered.set()
                            try:
                                await asyncio.Event().wait()
                            finally:
                                cleaning.set()
                                await release.wait()
                                cleaned.set()
                        return await super().request(stage, body, headers)

                wire = CleanupWire([], playing_delay=None)
                session = command.Session(wire, timeout=1.0, feedback_interval=0.02)
                duration = 0.05 if outcome == 'deadline' else 10.0
                task = asyncio.create_task(session.run(49170, 'https://example.org/a.mp4', duration))
                try:
                    await asyncio.wait_for(entered.wait(), 0.1)
                    feedback = session._feedback_task
                    if outcome != 'cancel':
                        session.playing.set()
                        session.finished.set()
                    else:
                        task.cancel()
                    await asyncio.wait_for(cleaning.wait(), 0.1)
                    if outcome == 'deadline':
                        # Let run's original deadline interrupt normal cleanup.
                        await asyncio.sleep(0.06)
                        self.assertGreaterEqual(task.cancelling(), 1)
                    else:
                        for _ in range(2):
                            task.cancel()
                            await asyncio.sleep(0)
                    self.assertFalse(task.done())
                    self.assertFalse(feedback.done())
                    self.assertFalse(wire.closed)
                    release.set()
                    if outcome == 'deadline':
                        done, _ = await asyncio.wait({task}, timeout=0.1)
                        self.assertIn(task, done)
                        with self.assertRaises(TimeoutError):
                            await task
                    else:
                        await self.assert_cancelled_promptly(task)
                    self.assertTrue(cleaned.is_set())
                    self.assertTrue(feedback.cancelled())
                    self.assertTrue(wire.closed)
                    self.assertIsNone(session._feedback_task)
                finally:
                    release.set()
                    if not task.done():
                        task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                self.assertFalse([t for t in asyncio.all_tasks()
                                  if t is not asyncio.current_task()])

    async def test_native_cancel_during_feedback_request_closes_without_pending_tasks(self):
        m = load(); command = m.spike()
        entered = asyncio.Event()
        cleaned = asyncio.Event()
        base = native_backend([], playing_delay=None)

        class CleanupWire(base):
            async def request(self, stage, body=None, headers=None):
                if stage == 'command-resend':
                    entered.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        cleaned.set()
                return await super().request(stage, body, headers)

        with tempfile.TemporaryDirectory() as directory:
            transport, device = self.make_transport(m, command, directory, timeout=1.0,
                                                     feedback_interval=0.02, log=[])
            transport.backend = CleanupWire
            task = asyncio.create_task(transport.run(
                dict(receiver=device.identifier, host='127.0.0.1', url='https://example.org/a.mp4'),
                lambda *x: None))
            try:
                await asyncio.wait_for(entered.wait(), 0.1)
                task.cancel()
                await self.assert_cancelled_promptly(task)
                self.assertTrue(cleaned.is_set())
                self.assertTrue(transport.wire.closed)
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        self.assertFalse([t for t in asyncio.all_tasks()
                          if t is not asyncio.current_task()])

    async def test_feedback_failure_does_not_leak_or_hide_completion(self):
        m = load(); command = m.spike()
        log = []
        wire = StandaloneWire(log, playing_delay=0.04, feedback_error=RuntimeError('boom'))
        session = command.Session(wire, timeout=1.0, feedback_interval=0.01)
        await session.run(49170, 'https://example.org/a.mp4', 2.0)
        self.assertTrue(session.started)
        self.assertTrue(wire.closed)

    async def test_concurrent_feedback_does_not_corrupt_or_reset_await_playing_timeout(self):
        m = load(); command = m.spike()
        log = []
        with tempfile.TemporaryDirectory() as directory:
            t, device = self.make_transport(m, command, directory, timeout=0.03,
                                            startup_timeout=0.03, feedback_interval=0.005,
                                            log=log, playing_delay=None)
            with self.assertRaises(m.PlaybackError) as ctx:
                await t.run(dict(receiver=device.identifier, host='127.0.0.1', url='https://example.org/a.mp4'),
                            lambda *x: None)
            self.assertEqual(ctx.exception.diagnostic, {'stage': 'await-playing', 'reason': 'timeout'})
            self.assertTrue(t.wire.closed)
        # Feedback heartbeats fired during the loading wait but never reset it.
        self.assertGreaterEqual(sum(1 for k, _ in log if k == 'feedback'), 1)

    async def test_feedback_request_does_not_disturb_shared_stage(self):
        command = load().spike()
        stage = ['await-playing']
        reports = []
        wire = command.Backend.__new__(command.Backend)
        wire.stage = stage
        wire.report = lambda event, **fields: reports.append((event, fields))
        wire.rtsp = SimpleNamespace()

        async def feedback():
            return SimpleNamespace(code=200)

        async def record():
            return SimpleNamespace(code=200)

        wire.rtsp.feedback = feedback
        wire.rtsp.record = record

        async def post(*args, **kwargs):
            return SimpleNamespace(code=200)

        wire.connection = SimpleNamespace(post=post)
        await wire.request('feedback')
        self.assertEqual(stage[0], 'await-playing')
        await wire.request('command-resend', b'payload', {})
        self.assertEqual(stage[0], 'await-playing')
        await wire.request('record')
        self.assertEqual(stage[0], 'record')


if __name__ == '__main__':
    unittest.main()
