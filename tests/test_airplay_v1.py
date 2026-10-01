"""Production no-auth V1: synthetic receivers only, real pinned pyatv sender."""
import asyncio
import ipaddress
import plistlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from test_helper_protocol import load

pytest.importorskip('pyatv')
from pyatv.conf import AppleTV
from pyatv.core import MutableService
from pyatv.const import Protocol
from pyatv.protocols.airplay.utils import update_service_details

ID = 'AA:BB:CC:DD:EE:01'
HOST = '192.0.2.95'
PROPS = dict(features='0x5A7FFFF7,0xE', model='AppleTV3,1', flags='0x44')
URL = 'https://EXAMPLE.org/a%2fb.mp4?a=+&a=%20#exact'


def device(properties=None, *, identifier=ID, host=HOST, port=57000):
    config = AppleTV(ipaddress.ip_address(host), 'Synthetic receiver')
    service = MutableService(identifier, Protocol.AirPlay, port, properties=PROPS if properties is None else properties)
    update_service_details(service)
    config.add_service(service)
    return config


class Connection:
    def __init__(self, code=200):
        self.transport = object()
        self.closed = False
        self.sent = []
        self.code = code
    async def post(self, path, **kwargs):
        self.sent.append((path, plistlib.loads(kwargs['body'])))
        return SimpleNamespace(code=self.code)
    def connection_lost(self, error):
        self.transport = None
    def close(self):
        self.closed = True
        self.connection_lost(None)


def fixture(tmp_path, receiver=None, connection=None):
    m = load()
    store = m.spike().existing().Store()
    store.root = tmp_path/'state'
    conn = connection or Connection()
    scan = AsyncMock(return_value=[receiver or device()])
    connect = AsyncMock(return_value=conn)
    t = m.Transport(api=SimpleNamespace(scan=scan, Protocol=Protocol), store=store,
                    connect=connect, parse=lambda x: x, timeout=.15)
    return m, t, conn


def args():
    return dict(receiver=ID, host=HOST, url=URL)


def test_unpaired_explicit_v1_accepts_once_and_cleans_on_stop(tmp_path):
    async def run():
        m, t, conn = fixture(tmp_path)
        accepted = asyncio.Event()
        notices = []
        def notify(*a, **kw):
            notices.append((a, kw))
            accepted.set()
        submitted = args()
        task = asyncio.create_task(t.run(submitted, notify))
        waiter = asyncio.create_task(accepted.wait())
        try:
            await asyncio.wait([task, waiter], timeout=1, return_when=asyncio.FIRST_COMPLETED)
            if task.done(): await task
            assert accepted.is_set(), 'production path must accept without a PIN or opt-in'
            assert notices == [(('connecting', 'unverified'), {'session': dict(receiver=ID, host=HOST, transport='airplay-v1', delivery='accepted', timingRequired=False)})]
            assert len(conn.sent) == 1 and conn.sent[0][0] == '/play'
            assert conn.sent[0][1]['Content-Location'] == URL
            assert submitted == {}
            assert not task.done()
            with pytest.raises(m.HelperError, match='busy'):
                with m.Lease(t.store): pass
        finally:
            task.cancel(); waiter.cancel()
            await asyncio.gather(task, waiter, return_exceptions=True)
        assert conn.closed
        assert not (t.store.root/'credentials.json').exists()
        with m.Lease(t.store): pass
    asyncio.run(run())


@pytest.mark.parametrize('ending', ['stop', 'peer', 'disconnect'])
def test_host_accepted_metadata_and_lease_lifecycle(tmp_path, ending):
    async def run():
        m, t, conn = fixture(tmp_path)
        events = []
        host = m.Host(lambda: t, events.append)
        host.receivers = [dict(identifier=ID, address=HOST)]
        def request(op, values=None):
            return dict(v=1, id=op, op=op, args=values or {})
        try:
            assert (await host.handle(request('start', args())))['ok']
            for _ in range(100):
                if events or host.task.done(): break
                await asyncio.sleep(.005)
            assert events and events[-1].get('session', {}).get('delivery') == 'accepted'
            for op in ('hello', 'status'):
                response = await host.handle(request(op))
                assert response['session']['receiver'] == ID
            original = host.task
            duplicate = await host.handle(request('start', args()))
            assert duplicate['ok'] and duplicate['session']['delivery'] == 'accepted'
            assert host.task is original and len(conn.sent) == 1
            if ending == 'peer':
                conn.connection_lost(None)
                await asyncio.wait_for(host.task, .5)
            elif ending == 'disconnect':
                await host.close()
            else:
                await host.handle(request('stop'))
            response = await host.handle(request('status'))
            assert 'session' not in response
            assert response['state'] == 'stopped' and response['evidence'] == 'unverified'
            assert conn.closed
            with m.Lease(t.store): pass
            t.connect.return_value = Connection()
            await host.handle(request('start', args()))
            for _ in range(100):
                if host.response('status').get('session'): break
                await asyncio.sleep(.005)
            assert host.response('status')['session']['delivery'] == 'accepted'
        finally:
            await host.close()
    asyncio.run(run())


def test_discovery_advice_is_positive_only_and_saved_pair_keeps_timing(tmp_path):
    async def run():
        m, t, conn = fixture(tmp_path)
        found = await t.discover(HOST)
        assert found[0].get('timingRequired') is False
        t.store.save({'identifier': ID, 'credentials': 'synthetic'})
        assert 'timingRequired' not in (await t.discover(HOST))[0]
        t.store.save({'identifier': 'AA:BB:CC:DD:EE:02', 'credentials': 'synthetic'})
        assert (await t.discover(HOST))[0]['timingRequired'] is False
        t.scan = AsyncMock(return_value=[device({'model': 'AppleTV3,1'})])
        assert 'timingRequired' not in (await t.discover(HOST))[0]
    asyncio.run(run())


@pytest.mark.parametrize('port', [0, -1, 65536, True, '7000'])
def test_resolver_rejects_invalid_port_before_any_send(tmp_path, port):
    async def run():
        m, t, conn = fixture(tmp_path, device(port=port))
        with pytest.raises(m.HelperError, match='receiver_unavailable'):
            await asyncio.wait_for(t.run(args(), lambda *a, **kw: None), .5)
        t.connect.assert_not_awaited()
        assert not conn.sent
    asyncio.run(run())


def test_resolver_rejects_conflicting_pyatv_identity_even_with_one_match(tmp_path):
    async def run():
        m, t, conn = fixture(tmp_path)
        t.scan = AsyncMock(return_value=[device(), device(identifier='AA:BB:CC:DD:EE:02')])
        with pytest.raises(m.HelperError, match='receiver_unavailable'):
            await asyncio.wait_for(t.run(args(), lambda *a, **kw: None), .5)
        t.connect.assert_not_awaited()
    asyncio.run(run())


@pytest.mark.parametrize('changes,issue', [
    ({'features': None}, 'incomplete_advertisement'),
    ({'flags': None}, 'incomplete_advertisement'),
    ({'features': ''}, 'incomplete_advertisement'),
    ({'features': '0x1,garbage'}, 'incomplete_advertisement'),
    ({'ft': '0x1'}, 'incomplete_advertisement'),
    ({'sf': '0x80'}, 'incomplete_advertisement'),
    ({'pw': 'garbage'}, 'incomplete_advertisement'),
    ({'pw': 'true'}, 'unsupported_access'),
    ({'flags': '0xC4'}, 'unsupported_access'),
    ({'flags': '0x244', 'pw': 'true'}, 'unsupported_access'),
    ({'acl': '1'}, 'unsupported_access'),
    ({'acl': '2'}, 'unsupported_access'),
    ({'act': '2'}, 'unsupported_access'),
    ({'act': 'garbage'}, 'unsupported_access'),
    ({'features': '0x80'}, 'unsupported_protocol'),
    ({'features': '0x1,0x40'}, 'unsupported_protocol'),
    ({'features': '0x1,0x10000'}, 'unsupported_protocol'),
    ({'features': '0x1,0x800'}, 'unsupported_access'),
    ({'model': 'Mac14,1'}, 'unsupported_access'),
])
def test_unpaired_negative_advertisement_never_connects(tmp_path, changes, issue):
    async def run():
        properties = dict(PROPS)
        properties.update(changes)
        properties = {k: v for k, v in properties.items() if v is not None}
        # Malformed TXT need not survive pyatv's own updater; test our boundary anyway.
        d = device()
        service = d.get_service(Protocol.AirPlay)
        service.properties.clear(); service.properties.update(properties)
        try: update_service_details(service)
        except (ValueError, TypeError): pass
        m, t, conn = fixture(tmp_path, d)
        with pytest.raises(m.ReceiverError) as caught:
            await asyncio.wait_for(t.run(args(), lambda *a, **kw: None), .5)
        assert caught.value.receiver_issue == issue
        assert str(caught.value) == 'transport_failed'
        t.connect.assert_not_awaited()
        assert not conn.sent
        with m.Lease(t.store): pass
    asyncio.run(run())


@pytest.mark.parametrize('flags', ['0x244', '0x4c'])
def test_explicit_pin_requirement_preserves_masked_pairing_route(tmp_path, flags):
    async def run():
        m, t, conn = fixture(tmp_path, device(dict(PROPS, flags=flags)))
        with pytest.raises(m.HelperError, match='^pairing_required$'):
            await t.run(args(), lambda *a, **kw: None)
        t.connect.assert_not_awaited()
    asyncio.run(run())


@pytest.mark.parametrize('failure', ['credentials', 'connect', 'authenticate', 'command'])
def test_matching_saved_pair_never_downgrades_after_failure(tmp_path, failure):
    async def run():
        m, t, conn = fixture(tmp_path)
        t.store.save({'identifier': ID.lower(), 'credentials': 'synthetic-saved-secret'})
        path = t.store.root/'credentials.json'
        original = path.read_bytes()
        if failure == 'credentials':
            t.parse = lambda _: (_ for _ in ()).throw(ValueError('secret'))
        elif failure == 'connect':
            t.connect.side_effect = OSError('secret')
        else:
            class Wire:
                def __init__(self, *a): self.closed = False
                async def timing(self, port): self.timing_port = port
                async def request(self, stage, *a, **kw):
                    if stage == failure: raise OSError('secret')
                    if stage == 'setup-base': return {'eventPort': 1234}
                    if stage == 'setup-stream': return {'streams': [{'streamID': 1}]}
                    return {}
                async def events(self, *a): pass
                def close(self): self.closed = True
            t.backend = Wire
        with pytest.raises(m.PlaybackError):
            await t.run(args(), lambda *a, **kw: None)
        assert not conn.sent
        assert path.read_bytes() == original and path.stat().st_mode & 0o777 == 0o600
        assert t.connect.await_count <= 1
    asyncio.run(run())


def test_unrelated_saved_pair_is_byte_preserved(tmp_path):
    async def run():
        m, t, conn = fixture(tmp_path)
        t.store.save({'identifier': 'AA:BB:CC:DD:EE:02', 'credentials': 'unrelated-synthetic'})
        path = t.store.root/'credentials.json'
        original = path.read_bytes()
        ready = asyncio.Event()
        task = asyncio.create_task(t.run(args(), lambda *a, **kw: ready.set()))
        try: await asyncio.wait_for(ready.wait(), .5)
        finally:
            task.cancel(); await asyncio.gather(task, return_exceptions=True)
        assert path.read_bytes() == original and path.stat().st_mode & 0o777 == 0o600
    asyncio.run(run())


def test_malformed_saved_state_is_not_absence(tmp_path):
    async def run():
        m, t, conn = fixture(tmp_path)
        t.store.load = lambda: (_ for _ in ()).throw(ValueError('secret-state'))
        with pytest.raises(m.PlaybackError):
            await t.run(args(), lambda *a, **kw: None)
        t.connect.assert_not_awaited()
        t.api.scan.assert_not_awaited()
    asyncio.run(run())


@pytest.mark.parametrize('code', [201, 400, 401, 500])
def test_non200_is_single_sanitized_failure_with_no_metadata(tmp_path, code):
    async def run():
        m, t, conn = fixture(tmp_path, connection=Connection(code))
        events = []
        with pytest.raises(m.PlaybackError) as caught:
            await t.run(args(), lambda *a, **kw: events.append((a, kw)))
        assert caught.value.diagnostic['httpStatus'] == code
        assert not events and len(conn.sent) == 1 and conn.closed
        assert 'EXAMPLE' not in str(caught.value)
        with m.Lease(t.store): pass
    asyncio.run(run())


def test_timed_out_play_closes_and_does_not_retry(tmp_path):
    async def run():
        conn = Connection()
        conn.post = AsyncMock(side_effect=lambda *a, **kw: None)
        async def wait(*a, **kw): await asyncio.Future()
        conn.post.side_effect = wait
        m, t, conn = fixture(tmp_path, connection=conn)
        with pytest.raises(m.PlaybackError) as caught:
            await t.run(args(), lambda *a, **kw: pytest.fail('not accepted'))
        assert caught.value.diagnostic == dict(stage='command', reason='timeout')
        assert conn.post.await_count == 1 and conn.closed
        with m.Lease(t.store): pass
    asyncio.run(run())


def test_unsupported_reason_survives_host_refresh_and_clears_on_new_start(tmp_path):
    async def run():
        m, t, conn = fixture(tmp_path, device(dict(PROPS, pw='true')))
        events = []
        host = m.Host(lambda: t, events.append)
        host.receivers = [dict(identifier=ID, address=HOST)]
        req = dict(v=1, id='start', op='start', args=args())
        await host.handle(req); await host.task
        assert events[-1]['error'] == 'transport_failed'
        assert events[-1]['receiverIssue'] == 'unsupported_access'
        assert 'session' not in events[-1]
        assert host.response('status')['receiverIssue'] == 'unsupported_access'
        t.scan = AsyncMock(return_value=[device()])
        try:
            result = await host.handle(req)
            assert 'receiverIssue' not in result and 'session' not in result
        finally: await host.close()
    asyncio.run(run())


def test_pair_begin_rejects_noauth_or_unsupported_before_pairing(tmp_path):
    async def run():
        for properties in (PROPS, dict(PROPS, pw='true'), {'model': 'AppleTV3,1'}):
            m, t, conn = fixture(tmp_path, device(properties))
            t.api.pair = AsyncMock(side_effect=AssertionError('must not initiate PIN'))
            with pytest.raises(m.ReceiverError):
                await t.begin_pair(ID, HOST)
            t.api.pair.assert_not_awaited()
            with m.Lease(t.store): pass
    asyncio.run(run())


@pytest.mark.parametrize('change', ['disabled', 'service_identity'])
def test_inconsistent_service_cannot_send(tmp_path, change):
    async def run():
        d = device()
        if change == 'disabled': d.get_service(Protocol.AirPlay).enabled = False
        else: d.get_service(Protocol.AirPlay)._identifier = 'AA:BB:CC:DD:EE:02'
        m, t, conn = fixture(tmp_path, d)
        if change == 'service_identity':
            # A conflicting primary identity must not authorize this service.
            t.scan = AsyncMock(return_value=[SimpleNamespace(identifier=ID, address=d.address, get_service=d.get_service)])
        with pytest.raises(m.HelperError):
            await asyncio.wait_for(t.run(args(), lambda *a, **kw: None), .5)
        t.connect.assert_not_awaited()
    asyncio.run(run())


def test_actual_pyatv_http_connection_wakes_on_peer_close(tmp_path):
    async def run():
        from pyatv.support.http import http_connect
        accepted = asyncio.Event()
        close_peer = asyncio.Event()
        server_done = asyncio.Event()
        requests = []
        async def peer(reader, writer):
            try:
                header = await reader.readuntil(b'\r\n\r\n')
                length = int(next(line.split(b':', 1)[1] for line in header.split(b'\r\n') if line.lower().startswith(b'content-length:')))
                body = await reader.readexactly(length)
                requests.append((header.split(b'\r\n')[0], plistlib.loads(body)))
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n')
                await writer.drain()
                await close_peer.wait()
            finally:
                writer.close(); await writer.wait_closed(); server_done.set()
        server = await asyncio.start_server(peer, '127.0.0.1', 0)
        port = server.sockets[0].getsockname()[1]
        d = device(host='127.0.0.1', port=port)
        m, t, unused = fixture(tmp_path, d)
        t.connect = http_connect
        t.timeout = 1
        task = asyncio.create_task(t.run(dict(args(), host='127.0.0.1'), lambda *a, **kw: accepted.set()))
        try:
            await asyncio.wait_for(accepted.wait(), 2)
            assert not task.done()
            close_peer.set()
            assert await asyncio.wait_for(task, 2) == 'unverified'
            await asyncio.wait_for(server_done.wait(), 2)
            assert len(requests) == 1 and requests[0][0] == b'POST /play HTTP/1.1'
            assert requests[0][1]['Content-Location'] == URL
            with m.Lease(t.store): pass
        finally:
            close_peer.set(); task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            server.close(); await server.wait_closed()
    asyncio.run(run())


@pytest.mark.parametrize('properties', [
    dict(PROPS, ft=PROPS['features'], sf='44'),
    dict(ft=PROPS['features'], sf='0x44'),
    dict(features='0x1', flags='0x0', pw='FALSE'),
])
def test_consistent_explicit_aliases_admit_v1(properties):
    from helper.airplay_v1 import route
    assert route(device(properties).get_service(Protocol.AirPlay)) == 'v1'


def test_fresh_resolution_uses_new_valid_port_and_clears_advisory_auth(tmp_path):
    async def run():
        m, t, conn = fixture(tmp_path)
        assert (await t.discover(HOST))[0]['timingRequired'] is False
        t.scan = AsyncMock(return_value=[device(dict(PROPS, pw='true'), port=58000)])
        with pytest.raises(m.ReceiverError):
            await t.run(args(), lambda *a, **kw: None)
        t.connect.assert_not_awaited()
        t.scan = AsyncMock(return_value=[device(port=58000)])
        ready = asyncio.Event()
        task = asyncio.create_task(t.run(args(), lambda *a, **kw: ready.set()))
        try:
            await asyncio.wait_for(ready.wait(), .5)
            t.connect.assert_awaited_once_with(HOST, 58000)
        finally:
            task.cancel(); await asyncio.gather(task, return_exceptions=True)
    asyncio.run(run())
