import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from test_helper_protocol import load

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
        device=SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF', address='127.0.0.1', name='SECRET',get_service=lambda p:SimpleNamespace(port=7000))
        async def scan(*a,**kw): return [device]
        async def connect(*a): return SimpleNamespace(close=lambda:None)
        api=SimpleNamespace(scan=scan,Protocol=SimpleNamespace(AirPlay=1))
        with tempfile.TemporaryDirectory() as directory:
            store=command.existing().Store(); store.root=Path(directory).resolve()/'state'
            store.save({'identifier':device.identifier,'credentials':'fake'})
            transport=m.Transport(api=api, command=command, store=store, connect=connect, parse=lambda c:c, backend=Wire, timeout=.1)
            receivers=await transport.discover(None)
            self.assertEqual(receivers,[{'identifier':device.identifier,'address':'127.0.0.1','label':'Apple TV'}])
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
        device=SimpleNamespace(identifier='AA:BB:CC:DD:EE:FF', address='10.0.0.8', name='SECRET',get_service=lambda p:SimpleNamespace(port=7000))
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
        self.assertEqual(receivers,[{'identifier':device.identifier,'address':'10.0.0.8','label':'Apple TV'}])

    def test_avahi_parse_uses_resolved_ipv4_apple_tv_only(self):
        m=load()
        text='\n'.join([
            '+;wlan0;IPv4;Living Room;_airplay._tcp;local',
            '=;wlan0;IPv4;Living Room;_airplay._tcp;local;x.local;10.0.0.8;7000;"model=AppleTV14,1"',
            '=;wlan0;IPv4;Speaker;_airplay._tcp;local;s.local;10.0.0.20;7000;"model=Move"',
            '=;wlan0;IPv6;Living Room;_airplay._tcp;local;x.local;10.0.0.8;7000;"model=AppleTV14,1"',
        ])
        self.assertEqual(m.parse_avahi_hosts(text),['10.0.0.8'])

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
