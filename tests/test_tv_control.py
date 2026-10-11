import asyncio
import plistlib
from types import SimpleNamespace

import pytest
from helper.tv_control import RateControl
from test_command_transport import module
from test_helper_protocol import load, request


def fixture(timeout=.08):
    writes = []
    wire = SimpleNamespace(closed=False)
    def close(): wire.closed = True
    wire.close = close
    async def send(stage, body, headers):
        writes.append((stage, body, headers))
        return {}
    wire.request = send
    session = module().Session(wire, timeout=timeout)
    events = []
    control = RateControl(session, lambda *args: events.append(args))
    session.on_event({'type': 'playbackState', 'name': 'playing'})
    return session, control, wire, writes, events


def test_rates_exact_headers_events_not_ack_and_natural_end():
    async def check():
        session, control, wire, writes, events = fixture()
        for op, desired, rate in [('pause', 'paused', 0.0), ('resume', 'playing', 1.0)]:
            task = asyncio.create_task(control.set_rate(op))
            await asyncio.sleep(0)
            assert not task.done()  # Accepted HTTP response is not state evidence.
            stage, body, headers = writes[-1]
            assert stage == 'command-resend'
            assert headers == session.headers
            assert plistlib.loads(plistlib.loads(body)['params']['data']) == {'type': 'setRate', 'rate': rate}
            session.on_event({'type': 'playbackState', 'params': {'playbackState': desired}})
            await task
            assert events[-1] == (desired, 'protocol')
        session.on_event({'type': 'playbackState', 'name': 'stopped'})
        assert not control.available
        with pytest.raises(ValueError): await control.set_rate('pause')
        assert len(writes) == 2
    asyncio.run(check())


@pytest.mark.parametrize('cancel', [False, True])
def test_timeout_or_cancel_quarantines_wire_and_prevents_late_write(cancel):
    async def check():
        session, control, wire, writes, events = fixture(.01)
        task = asyncio.create_task(control.set_rate('pause'))
        await asyncio.sleep(0)
        if cancel: task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else TimeoutError): await task
        assert wire.closed and session.finished.is_set() and not control.available
        session.on_event({'type': 'playbackState', 'name': 'paused'})
        with pytest.raises(ValueError): await control.set_rate('resume')
        with pytest.raises(RuntimeError): await session.call('feedback')
        assert len(writes) == 1
    asyncio.run(check())


def test_serialization_against_feedback_and_revalidation_after_wait():
    async def check():
        session, control, wire, writes, _ = fixture()
        entered, release = asyncio.Event(), asyncio.Event()
        async def send(stage, body, headers):
            writes.append(stage)
            if stage == 'feedback':
                entered.set()
                await release.wait()
            return {}
        wire.request = send
        feedback = asyncio.create_task(session.call('feedback'))
        await entered.wait()
        pause = asyncio.create_task(control.set_rate('pause'))
        await asyncio.sleep(0)
        assert writes == ['feedback']
        session.on_event({'type': 'playbackState', 'name': 'stopped'})
        release.set()
        await feedback
        with pytest.raises(ValueError): await pause
        assert writes == ['feedback']
    asyncio.run(check())


def test_stop_during_control_wakes_waiter_without_success():
    async def check():
        session, control, wire, writes, _ = fixture()
        task = asyncio.create_task(control.set_rate('pause'))
        await asyncio.sleep(0)
        control.close()
        with pytest.raises(RuntimeError): await task
        assert len(writes) == 1 and not control.available
    asyncio.run(check())


@pytest.mark.parametrize('model, supported', [('AppleTV14,1', True), ('LGTV', False)])
def test_transport_only_exposes_owned_apple_command_session_and_cleans(tmp_path, model, supported):
    async def check():
        import sys
        from test_startup_feedback import native_backend
        m = load()
        command = m.spike()
        device = SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF', address='127.0.0.1',
            get_service=lambda _: SimpleNamespace(port=7000, properties={'model': model}))
        if sys.platform == 'win32':
            from helper.windows_store import Store
            store = Store(root=tmp_path / 'owned-store')
        else:
            store = command.existing().Store()
            store.root = tmp_path.resolve() / 'state'
        store.save({'identifier': device.identifier, 'credentials': 'synthetic-test-only'})
        async def scan(*args, **kwargs): return [device]
        async def connect(*args): return SimpleNamespace(close=lambda: None)
        transport = m.Transport(api=SimpleNamespace(scan=scan, Protocol=SimpleNamespace(AirPlay=1)),
            command=command, store=store, connect=connect, parse=lambda value: value,
            backend=native_backend([], None, None), timeout=.2, feedback_interval=.02)
        ready = asyncio.Event()
        class Wire(transport.backend):
            async def events(self, port, callback): self.callback = callback
            async def request(self, stage, body=None, headers=None):
                result = await super().request(stage, body, headers)
                if stage == 'command':
                    self.callback({'type': 'playbackState', 'name': 'playing'})
                    ready.set()
                if stage == 'command-resend' and supported:
                    self.callback({'type': 'playbackState', 'name': 'paused'})
                return result
        transport.backend = Wire
        events = []
        task = asyncio.create_task(transport.run({'receiver': device.identifier, 'host': '127.0.0.1', 'url': 'https://example.org/video.mp4'}, lambda *args: events.append(args)))
        try:
            await asyncio.wait_for(ready.wait(), .5)
            assert (transport.rate_control is not None) == supported
            if supported:
                await transport.rate_control.set_rate('pause')
                assert events[-1] == ('paused', 'protocol')
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        assert transport.rate_control is None and transport.wire.closed
        if supported:
            count = len(events)
            transport.wire.callback({'type': 'playbackState', 'name': 'playing'})
            assert len(events) == count
    asyncio.run(check())


def test_host_capabilities_token_replacement_and_no_session_refusal():
    async def check():
        m = load()
        sessions = []
        class Transport:
            rate_control = None
            async def run(self, args, notify):
                session, control, wire, writes, _ = fixture()
                control.notify = notify
                self.rate_control = control
                sessions.append((session, control, writes))
                notify('playing', 'protocol')
                try: await session.finished.wait()
                finally:
                    self.rate_control = None
                    control.close()
                return 'protocol'
        events = []
        host = m.Host(Transport, events.append)
        host.receivers = [{'identifier': 'AA:BB:CC:DD:EE:FF', 'address': '127.0.0.1'}]
        args = {'receiver': 'AA:BB:CC:DD:EE:FF', 'host': '127.0.0.1', 'url': 'https://example.org/video.mp4'}
        assert (await host.handle(request('pause')))['error'] == 'unsupported'
        await host.handle(request('start', args))
        await asyncio.sleep(0)
        view = await host.handle(request('status'))
        assert {'pause', 'resume'} <= set(view['capabilities'])
        token = view['tvControl']['session']
        assert view['tvControl']['receiver'] == 'AA:BB:CC:DD:EE:FF'
        assert (await host.handle(request('pause', {'session': 'b' * 32})))['error'] == 'unsupported'
        assert (await host.handle(request('pause')))['error'] == 'unsupported'
        assert (await host.handle(request('pause', {'session': 'x' * 32})))['error'] == 'invalid_request'
        task = asyncio.create_task(host.handle(request('pause', {'session': token})))
        await asyncio.sleep(0)
        assert host.state == 'playing'
        sessions[-1][0].on_event({'type': 'playbackState', 'name': 'paused'})
        result = await task
        assert result['state'] == 'paused' and result['ok']
        stopped = await host.handle(request('stop'))
        assert 'tvControl' not in stopped and 'pause' not in stopped['capabilities']
        await host.handle(request('start', args))
        await asyncio.sleep(0)
        new = await host.handle(request('status'))
        assert new['tvControl']['session'] != token
        assert (await host.handle(request('pause', {'session': token})))['error'] == 'unsupported'
        assert not sessions[-1][2]
        await host.close()
        assert 'tvControl' not in host.response('done')
    asyncio.run(check())
