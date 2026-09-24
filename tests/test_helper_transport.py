import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from test_helper_protocol import load

async def no_mdns(): return []

class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_command_session_discovery_identity_and_cleanup(self):
        m=load(); command=m.spike(); calls=[]; notices=[]
        class Wire:
            def __init__(self,*args): self.timing_port=None; self.closed=False
            async def timing(self, port): self.timing_port=port
            async def request(self,stage,body=None,headers=None):
                calls.append((stage,body))
                if stage=='setup-base': return {'eventPort':1234}
                if stage=='setup-stream': return {'streams':[{'streamID':19}]}
                if stage=='command':
                    self.callback({'type':'playbackState','name':'playing'})
                    self.callback({'type':'playbackState','name':'stopped'})
                return {}
            async def events(self,port,callback): self.callback=callback
            def close(self): self.closed=True
        device=SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF', address='127.0.0.1', name='SECRET',get_service=lambda p:SimpleNamespace(port=7000, properties={'model':'AppleTV14,1'}))
        async def scan(*a,**kw): return [device]
        async def connect(*a): return SimpleNamespace(close=lambda:None)
        api=SimpleNamespace(scan=scan,Protocol=SimpleNamespace(AirPlay=1))
        with tempfile.TemporaryDirectory() as directory:
            store=command.existing().Store(); store.root=Path(directory).resolve()/'state'
            store.save({'identifier':device.identifier,'credentials':'fake'})
            transport=m.Transport(api=api, command=command, store=store, connect=connect, parse=lambda c:c, backend=Wire, timeout=.1, mdns=no_mdns)
            receivers=await transport.discover(None)
            self.assertEqual(receivers,[{'identifier':device.identifier,'address':'127.0.0.1','label':'Apple TV','kind':'apple-tv'}])
            await transport.run(dict(receiver=device.identifier,host='127.0.0.1',url='https://EXAMPLE.org/a%2fb?SECRET'),lambda *x:notices.append(x))
            self.assertIn(('playing','protocol'),notices)
            self.assertTrue(transport.wire.closed)
            self.assertEqual(calls[0][0],'authenticate')
            import plistlib
            payload=next(body for stage,body in calls if stage=='command')
            self.assertEqual(plistlib.loads(plistlib.loads(payload)['params']['data'])['item']['Content-Location'],'https://EXAMPLE.org/a%2fb?SECRET')
            with self.assertRaisesRegex(m.HelperError,'pairing_required'):
                await transport.run(dict(receiver='11:22:33:44:55:66',host='127.0.0.1',url='https://a/'),lambda *x:None)

    async def test_empty_discover_uses_mdns_hosts_when_multicast_scan_is_empty(self):
        m=load(); command=m.spike()
        device=SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF', address='10.0.0.8', name='SECRET',get_service=lambda p:SimpleNamespace(port=7000, properties={'model':'AppleTV14,1'}))
        scanned=[]
        async def scan(*a,**kw):
            hosts=kw.get('hosts')
            scanned.append(hosts)
            return [device] if hosts==['10.0.0.8'] else []
        api=SimpleNamespace(scan=scan,Protocol=SimpleNamespace(AirPlay=1))
        async def mdns(): return ['10.0.0.8']
        transport=m.Transport(api=api, command=command, mdns=mdns, connect=lambda *a: None, parse=lambda c:c, timeout=.1)
        receivers=await transport.discover(None)
        self.assertEqual(scanned,[None,['10.0.0.8']])
        self.assertEqual(receivers,[{'identifier':device.identifier,'address':'10.0.0.8','label':'Apple TV','kind':'apple-tv'}])

    async def test_discover_keeps_classified_apple_tv_and_drops_unknown(self):
        m=load(); command=m.spike()
        apple=SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF', address='192.0.2.10', device_info=SimpleNamespace(model=SimpleNamespace(name='AppleTV4KGen3')))
        other=SimpleNamespace(identifier='11:22:33:44:55:66', address='192.0.2.20', device_info=SimpleNamespace(model=SimpleNamespace(name='Unknown')))
        async def scan(*a, **kw):
            return [apple, other]
        api=SimpleNamespace(scan=scan, Protocol=SimpleNamespace(AirPlay=1))
        transport=m.Transport(api=api, command=command, connect=lambda *a: None, parse=lambda c:c, timeout=.1, mdns=no_mdns)
        receivers=await transport.discover(None)
        self.assertEqual([item['address'] for item in receivers], ['192.0.2.10'])

    def test_avahi_parse_uses_resolved_ipv4_apple_tv_only(self):
        m=load()
        text='\n'.join([
            '+;wlan0;IPv4;Living Room;_airplay._tcp;local',
            '=;wlan0;IPv4;Living Room;_airplay._tcp;local;x.local;10.0.0.8;7000;"model=AppleTV14,1"',
            '=;wlan0;IPv4;Speaker;_airplay._tcp;local;s.local;10.0.0.20;7000;"model=Move"',
            '=;wlan0;IPv6;Living Room;_airplay._tcp;local;x.local;10.0.0.8;7000;"model=AppleTV14,1"',
        ])
        self.assertEqual(m.parse_avahi_hosts(text),['10.0.0.8'])

    async def test_avahi_absent_falls_back_to_dns_sd_apple_tv_ipv4_only(self):
        import unittest.mock
        m=load(); command=m.spike()
        device=SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF', address='192.0.2.10', name='SECRET', get_service=lambda p: SimpleNamespace(port=7000, properties={'model':'AppleTV14,1'}))
        scanned=[]
        async def scan(*a, **kw):
            hosts=kw.get('hosts')
            scanned.append(hosts)
            return [device] if hosts==['192.0.2.10'] else []
        api=SimpleNamespace(scan=scan, Protocol=SimpleNamespace(AirPlay=1))
        calls=[]
        browse='\n'.join([
            'Browsing for _airplay._tcp.local.',
            '12:27:40.146  Add        3  11 local.               _airplay._tcp.       Living Room',
            '12:27:40.146  Add        2  11 local.               _airplay._tcp.       Speaker',
            '12:27:40.147  Add        3  18 local.               _airplay._tcp.       Living Room',
        ])
        lookups={
            'Living Room':'12:28:01.056  Living\\032Room._airplay._tcp.local. can be reached at Living-Room.local.:7000 (interface 11)\n model=AppleTV14,1\n',
            'Speaker':'12:28:01.056  Speaker._airplay._tcp.local. can be reached at Speaker.local.:7000 (interface 11)\n model=Move\n',
        }
        address='\n'.join([
            '12:28:03.565  Add  40000002      18  Living-Room.local.                      192.0.2.10                                   120',
            '12:28:03.566  Add  40000003       8  Living-Room.local.                      192.0.2.10                                   120',
        ])
        class Proc:
            def __init__(self, text):
                self.text, self.killed = text, False
            async def communicate(self):
                if not self.killed: await asyncio.sleep(2)
                return self.text.encode(), b''
            def kill(self): self.killed=True
        async def fake_exec(*argv, **kw):
            calls.append(argv)
            if argv[0]=='avahi-browse': raise FileNotFoundError(argv[0])
            if argv[:2]==('dns-sd','-B'): return Proc(browse)
            if argv[:2]==('dns-sd','-L'): return Proc(lookups.get(argv[2],''))
            if argv[:3]==('dns-sd','-G','v4'): return Proc(address if str(argv[3]).startswith('Living-Room') else '')
            raise AssertionError(argv)
        transport=m.Transport(api=api, command=command, connect=lambda *a: None, parse=lambda c:c, timeout=.1)
        with unittest.mock.patch('asyncio.create_subprocess_exec', fake_exec):
            receivers=await transport.discover(None)
        self.assertEqual(receivers,[{'identifier':device.identifier,'address':'192.0.2.10','label':'Apple TV','kind':'apple-tv'}])
        self.assertEqual(scanned,[None,['192.0.2.10']])
        self.assertTrue(any(c[0]=='avahi-browse' for c in calls))
        self.assertEqual([c[2] for c in calls if c[:2]==('dns-sd','-L')],['Living Room','Speaker'])
        self.assertFalse(any(len(c)>3 and c[:3]==('dns-sd','-G','v4') and not str(c[3]).startswith('Living-Room') for c in calls))
        self.assertTrue(any(c[:3]==('dns-sd','-G','v4') and str(c[3]).startswith('Living-Room') for c in calls))

    async def test_paste_ip_discover_does_not_browse(self):
        import unittest.mock
        m=load(); command=m.spike(); calls=[]
        async def scan(*a, **kw):
            return []
        async def fake_exec(*argv, **kw):
            calls.append(argv)
            raise AssertionError(argv)
        api=SimpleNamespace(scan=scan, Protocol=SimpleNamespace(AirPlay=1))
        transport=m.Transport(api=api, command=command, connect=lambda *a: None, parse=lambda c:c, timeout=.1)
        with unittest.mock.patch('asyncio.create_subprocess_exec', fake_exec):
            pasted=await transport.discover('192.0.2.8')
        self.assertEqual(pasted,[])
        self.assertEqual(calls,[])


    async def test_pairing_holds_shared_lease_until_cancel_or_finish(self):
        m=load(); command=m.spike()
        device=SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF')
        async def scan(*args, **kwargs): return [device]
        class Pair:
            device_provides_pin=True; has_paired=True
            service=SimpleNamespace(credentials='test-only')
            async def begin(self): pass
            def pin(self, value): pass
            async def finish(self): pass
            async def close(self): pass
        async def pair(*args): return Pair()
        api=SimpleNamespace(scan=scan,pair=pair,Protocol=SimpleNamespace(AirPlay=1))
        with tempfile.TemporaryDirectory() as directory:
            store=command.existing().Store(); store.root=Path(directory).resolve()/'state'
            transport=m.Transport(api=api,command=command,store=store,connect=lambda *a:None,parse=lambda c:c)
            opened=await transport.begin_pair(device.identifier,'127.0.0.1')
            try:
                with self.assertRaisesRegex(m.HelperError,'busy'):
                    with m.Lease(store): pass
            finally: await opened.close()
            with m.Lease(store): pass
            opened=await transport.begin_pair(device.identifier,'127.0.0.1')
            await opened.finish('1234')
            with m.Lease(store): pass
            self.assertEqual(store.load()['identifier'],device.identifier)

    async def test_lock_is_exclusive_reusable_and_rejects_symlink(self):
        m=load()
        with tempfile.TemporaryDirectory() as directory:
            store=m.spike().existing().Store(); store.root=Path(directory).resolve()/'state'
            with m.Lease(store):
                with self.assertRaisesRegex(m.HelperError,'busy'):
                    with m.Lease(store): pass
            with m.Lease(store): pass
            (store.root/'helper.lock').unlink()
            (store.root/'helper.lock').symlink_to(Path(directory)/'elsewhere')
            with self.assertRaises(OSError):
                with m.Lease(store): pass
