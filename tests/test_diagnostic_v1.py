"""Diagnostic-only no-PIN V1 transport; all receiver traffic is fake."""
import asyncio
import ipaddress
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from test_helper_protocol import load

pyatv = pytest.importorskip('pyatv')
from pyatv.conf import AppleTV
from pyatv.core import MutableService
from pyatv.const import Protocol
from pyatv.protocols.airplay.utils import update_service_details, AirPlayFlags

IDENTIFIER = 'AA:BB:CC:DD:EE:01'
ADDRESS = '192.168.1.95'
PROPERTIES = dict(features='0x5A7FFFF7,0xE', model='AppleTV3,1', srcvers='220.68', vv='2', flags='0x44')


def device(properties=None):
    config = AppleTV(ipaddress.ip_address(ADDRESS), 'Synthetic receiver')
    service = MutableService(IDENTIFIER, Protocol.AirPlay, 57000, properties=properties or PROPERTIES)
    update_service_details(service)
    config.add_service(service)
    return config


def test_explicit_v1_trial_sends_without_credentials_and_closes_on_cancel():
    async def run():
        m = load()
        sent = asyncio.Event()
        class Connection:
            closed = False
            async def post(self, path, **kwargs):
                assert path == '/play'
                import plistlib
                body = plistlib.loads(kwargs['body'])
                assert body['Content-Location'] == 'https://example.org/control.mp4'
                sent.set()
                return SimpleNamespace(code=200)
            def close(self): self.closed = True
        connection = Connection()
        async def scan(*args, **kwargs): return [device()]
        async def connect(*args): return connection
        with tempfile.TemporaryDirectory() as tmp:
            store = m.spike().existing().Store(); store.root = Path(tmp)/'state'
            store.load = lambda: (_ for _ in ()).throw(AssertionError('pairing store must not be read'))
            t = m.Transport(api=SimpleNamespace(scan=scan, Protocol=Protocol), store=store,
                            connect=connect, parse=lambda value: value)
            # This attribute is ignored by the old transport: RED at credentials.
            t.diagnostic_v1 = (IDENTIFIER, ADDRESS)
            task = asyncio.create_task(t.run(dict(receiver=IDENTIFIER, host=ADDRESS,
                url='https://example.org/control.mp4'), lambda *args: None))
            try:
                done, _ = await asyncio.wait([task, asyncio.create_task(sent.wait())], timeout=1, return_when=asyncio.FIRST_COMPLETED)
                if task in done:
                    await task
                assert sent.is_set(), 'diagnostic V1 /play was not sent'
                assert not task.done(), 'accepted POST must hold connection for human verdict'
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            assert connection.closed
    asyncio.run(run())


def test_v1_option_requires_frozen_development_active_trace_and_valid_pin():
    from helper import app
    option = getattr(app, 'diagnostic_v1_option', None)
    assert callable(option), 'missing diagnostic-only gate'
    value = IDENTIFIER + '@' + ADDRESS
    env = {'PEARPLAY_DIAGNOSTIC_V1_RECEIVER': value}
    assert option({'development': True}, env, frozen=True, trace_active=True) == (IDENTIFIER, ADDRESS)
    for frozen, development, trace in [(False, True, True), (True, False, True), (True, True, False)]:
        assert option({'development': development}, env, frozen=frozen, trace_active=trace) is None
    for invalid in ['', 'bad', IDENTIFIER+'@example.org', IDENTIFIER+'@8.8.8.8', IDENTIFIER+'@192.168.001.95', value+'\n']:
        assert option({'development': True}, {'PEARPLAY_DIAGNOSTIC_V1_RECEIVER': invalid}, frozen=True, trace_active=True) is None


@pytest.mark.parametrize('enabled,selected', [(False, True), (True, False)])
def test_non_trial_receivers_keep_pairing_requirement(enabled, selected):
    async def run():
        m = load()
        with tempfile.TemporaryDirectory() as tmp:
            store = m.spike().existing().Store(); store.root = Path(tmp)/'state'
            selected_id = IDENTIFIER if selected else 'AA:BB:CC:DD:EE:02'
            receiver = device(dict(PROPERTIES, flags='0x244'))
            receiver.get_service(Protocol.AirPlay)._identifier = selected_id
            api = SimpleNamespace(Protocol=Protocol, scan=AsyncMock(return_value=[receiver]))
            t = m.Transport(api=api, store=store, connect=AsyncMock(side_effect=AssertionError('must not connect')), parse=lambda x: x)
            if enabled: t.diagnostic_v1 = (IDENTIFIER, ADDRESS)
            with pytest.raises(m.HelperError, match='pairing_required'):
                await t.run(dict(receiver=IDENTIFIER if selected else 'AA:BB:CC:DD:EE:02', host=ADDRESS, url='https://example.org/a.mp4'), lambda *a: None)
    asyncio.run(run())


@pytest.mark.parametrize('flags,features', [('0x244', PROPERTIES['features']), ('0xC4', PROPERTIES['features']), ('0x44', hex(AirPlayFlags.SupportsCoreUtilsPairingAndEncryption.value))])
def test_changed_receiver_auth_is_rejected_before_connect(flags, features):
    async def run():
        m = load()
        d = device(dict(PROPERTIES, flags=flags, features=features))
        async def scan(*a, **kw): return [d]
        with tempfile.TemporaryDirectory() as tmp:
            store = m.spike().existing().Store(); store.root = Path(tmp)/'state'
            connect = AsyncMock(side_effect=AssertionError('must not connect'))
            t = m.Transport(api=SimpleNamespace(Protocol=Protocol, scan=scan), store=store, connect=connect, parse=lambda x: x)
            t.diagnostic_v1 = (IDENTIFIER, ADDRESS)
            with pytest.raises(m.PlaybackError):
                await t.run(dict(receiver=IDENTIFIER, host=ADDRESS, url='https://example.org/a.mp4'), lambda *a: None)
            connect.assert_not_awaited()
    asyncio.run(run())
