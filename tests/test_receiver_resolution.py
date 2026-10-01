import asyncio
import importlib.util
import ipaddress
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from test_helper_protocol import load

HOST = '192.0.2.20'
IDENTIFIER = '11:22:33:44:55:66'
ROW = '=;wlan0;IPv6;TV;_airplay._tcp;local;tv.local;192.0.2.20;7000;"model=OLED-TV" "features=0x7F8AD0,0xB8BCF46" "deviceid=11:22:33:44:55:66" "srcvers=377.40.00"'


class ReceiverResolution(unittest.IsolatedAsyncioTestCase):
    async def test_pairing_and_playback_both_use_shared_resolution(self):
        m = load()
        try: from pyatv.const import PairingRequirement
        except ImportError: self.skipTest('real pairing classification runs on Acer')
        service = SimpleNamespace(port=7000, properties={'features':'0x1', 'flags':'0x200'}, requires_password=False, pairing=PairingRequirement.Mandatory)
        device = SimpleNamespace(identifier=IDENTIFIER, address=ipaddress.IPv4Address(HOST), get_service=lambda _: service)
        calls = []
        async def resolved(identifier, host):
            calls.append((identifier, host))
            return device
        async def forbidden(*args, **kwargs):
            self.fail('pair/play must use the shared resolver, not another raw scan')
        async def noop(): pass
        pairing = SimpleNamespace(begin=noop, close=noop, device_provides_pin=True)
        async def pair(config, *args):
            self.assertIs(config, device)
            return pairing
        class Wire:
            def __init__(self, *args): self.closed = False
            async def timing(self, port): self.timing_port = port
            async def request(self, *args): raise RuntimeError('synthetic boundary stop before any network request')
            def close(self): self.closed = True
        async def connect(*args): return SimpleNamespace(close=lambda: None)
        with tempfile.TemporaryDirectory() as directory:
            store = m.spike().existing().Store()
            store.root = Path(directory).resolve()/'state'
            store.save({'identifier': IDENTIFIER, 'credentials': 'synthetic-test-only'})
            t = m.Transport(api=SimpleNamespace(pair=pair, scan=forbidden, Protocol=SimpleNamespace(AirPlay=1)), store=store, connect=connect, parse=lambda x: x, backend=Wire)
            t.resolve_receiver = resolved
            session = await t.begin_pair(IDENTIFIER, HOST)
            await session.close()
            with self.assertRaises(m.PlaybackError):
                await t.run({'receiver': IDENTIFIER, 'host': HOST, 'url': 'https://example.test/test.mp4'}, lambda *a: None)
            self.assertEqual(calls, [(IDENTIFIER, HOST), (IDENTIFIER, HOST)])
            self.assertTrue(t.wire.closed)

    async def test_silent_pyatv_uses_fresh_matching_avahi_service(self):
        m = load()
        t = m.Transport(api=SimpleNamespace(Protocol=SimpleNamespace(AirPlay=1)), connect=lambda *a: None, parse=lambda x: x)
        self.assertTrue(hasattr(t, 'resolve_receiver'), 'shared pair/play resolution missing')
        calls = []
        async def scan(host):
            calls.append(('scan', host))
            return []
        async def text(argv, timeout, kill):
            calls.append(('browse', argv))
            return ROW
        t.scan = scan
        t._exec_text = text
        m.avahi_config = lambda service: service
        selected = await t.resolve_receiver(IDENTIFIER, HOST)
        self.assertEqual(selected['identifier'], IDENTIFIER)
        self.assertEqual(selected['address'], HOST)
        self.assertEqual(selected['port'], 7000)
        self.assertEqual(selected['properties']['srcvers'], '377.40.00')
        self.assertEqual(calls[0], ('scan', HOST))
        self.assertEqual(calls[1], ('browse', ['avahi-browse', '-prtk', '_airplay._tcp']))
        # Resolve again instead of trusting the earlier cached advertisement.
        await t.resolve_receiver(IDENTIFIER, HOST)
        self.assertEqual(len(calls), 4)

    async def test_ambiguous_changed_or_nonvideo_avahi_fails_closed(self):
        m = load()
        for text in ('', ROW.replace(IDENTIFIER, '22:33:44:55:66:77'), ROW.replace(HOST, '192.0.2.21'),
                     ROW.replace(';7000;', ';0;'), ROW.replace('_airplay._tcp', '_ssh._tcp'),
                     ROW.replace('0x7F8AD0,0xB8BCF46', '0x80'),
                     ROW+'\n'+ROW.replace(';7000;', ';7001;'),
                     ROW+'\n'+ROW.replace(IDENTIFIER, '22:33:44:55:66:77')):
            with self.subTest(shape=text):
                t = m.Transport(api=SimpleNamespace(Protocol=SimpleNamespace(AirPlay=1)), connect=lambda *a: None, parse=lambda x: x)
                self.assertTrue(hasattr(t, 'resolve_receiver'), 'shared pair/play resolution missing')
                async def scan(host): return []
                async def output(*args): return text
                t.scan, t._exec_text = scan, output
                m.avahi_config = lambda service: self.fail('must not build unsafe configuration')
                with self.assertRaisesRegex(m.HelperError, '^receiver_unavailable$'):
                    await t.resolve_receiver(IDENTIFIER, HOST)

    async def test_valid_pyatv_result_does_not_browse_again(self):
        m = load()
        device = SimpleNamespace(identifier=IDENTIFIER, address=ipaddress.IPv4Address(HOST), get_service=lambda _: SimpleNamespace(port=7000))
        t = m.Transport(api=SimpleNamespace(Protocol=SimpleNamespace(AirPlay=1)), connect=lambda *a: None, parse=lambda x: x)
        self.assertTrue(hasattr(t, 'resolve_receiver'), 'shared pair/play resolution missing')
        async def scan(host): return [device]
        async def unexpected(*args): self.fail('successful pyatv lookup must not use fallback')
        t.scan, t._exec_text = scan, unexpected
        self.assertIs(await t.resolve_receiver(IDENTIFIER, HOST), device)

    @unittest.skipUnless(importlib.util.find_spec('pyatv'), 'real pyatv config verification runs on Acer')
    async def test_real_pyatv_config_preserves_advertised_identity_port_and_properties(self):
        m = load()
        self.assertTrue(hasattr(m, 'parse_avahi_services'), 'service parser missing')
        from pyatv.const import Protocol
        device = m.avahi_config(m.parse_avahi_services(ROW)[0])
        self.assertEqual(device.identifier, IDENTIFIER)
        self.assertEqual(str(device.address), HOST)
        service = device.get_service(Protocol.AirPlay)
        self.assertEqual(service.port, 7000)
        self.assertEqual(service.properties['features'], '0x7F8AD0,0xB8BCF46')
        self.assertIn(service.pairing.name, ('Mandatory', 'Optional', 'NotNeeded'))
