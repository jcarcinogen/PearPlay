import asyncio
import unittest
from types import SimpleNamespace
from test_helper_protocol import load


def device(address, identifier, model, features):
    return SimpleNamespace(address=address, identifier=identifier,
        device_info=SimpleNamespace(model=SimpleNamespace(name='Unknown')),
        get_service=lambda _: SimpleNamespace(properties={'model':model,'features':features}))


class DiscoveryRegression(unittest.IsolatedAsyncioTestCase):
    async def test_advertised_lg_survives_silent_unicast_and_speakers_are_excluded(self):
        m=load()
        text='\n'.join([
            '=;wlan0;IPv4;TV;_airplay._tcp;local;tv.local;192.0.2.20;7000;"model=OLED-TV" "features=0x7F8AD0,0xB8BCF46" "deviceid=11:22:33:44:55:66"',
            '=;wlan0;IPv4;Speaker;_airplay._tcp;local;s.local;192.0.2.30;7000;"model=Move" "features=0x445F8A00,0x801C340" "deviceid=22:33:44:55:66:77"',
        ])
        async def scan(*a,**kw): return []
        async def output(*a): return text
        t=m.Transport(api=SimpleNamespace(scan=scan,Protocol=SimpleNamespace(AirPlay=1)),connect=lambda *a:None,parse=lambda x:x)
        t._exec_text=output
        result=await t.discover(None)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['address'],'192.0.2.20')
        self.assertEqual(result[0]['kind'],'airplay-video')
        self.assertIn('unverified',result[0]['label'])

    async def test_combined_discovery_keeps_receiver_limit(self):
        m=load()
        extra=device('192.0.2.200','AA:BB:CC:DD:EE:FF','AppleTV14,1','0x1')
        async def scan(*a,**kw): return [extra]
        async def mdns():
            t.advertised=[dict(identifier=f'00:00:00:00:00:{i:02x}',address=f'192.0.2.{i+1}',kind='apple-tv',label='Apple TV') for i in range(64)]
            return []
        t=m.Transport(api=SimpleNamespace(scan=scan,Protocol=SimpleNamespace(AirPlay=1)),mdns=mdns,connect=lambda *a:None,parse=lambda x:x)
        self.assertEqual(len(await t.discover(None)),64)

    async def test_failed_scans_are_not_reported_as_no_tvs(self):
        m=load()
        async def scan(*a,**kw): raise OSError('private diagnostic')
        async def mdns(): return []
        t=m.Transport(api=SimpleNamespace(scan=scan,Protocol=SimpleNamespace(AirPlay=1)),mdns=mdns,connect=lambda *a:None,parse=lambda x:x)
        with self.assertRaisesRegex(m.HelperError,'discovery_failed'):
            await t.discover(None)

    async def test_browse_timeout_retains_resolved_output(self):
        import sys
        m=load()
        t=m.Transport(api=SimpleNamespace(),connect=lambda *a:None,parse=lambda x:x)
        text=await t._exec_text([sys.executable,'-c','import time; print("resolved",flush=True); time.sleep(10)'],.2,False)
        self.assertEqual(text.strip(),'resolved')

    async def test_partial_multicast_still_resolves_missing_apple_tv(self):
        m=load()
        lg=device('192.0.2.20','11:22:33:44:55:66','OLED-TV','0x7F8AD0,0xB8BCF46')
        apple=device('192.0.2.10','AA:BB:CC:DD:EE:FF','AppleTV14,1','0x1')
        calls=[]
        async def scan(*args,**kwargs):
            calls.append(kwargs['hosts'])
            return [lg] if kwargs['hosts'] is None else [apple]
        async def mdns(): return ['192.0.2.10']
        t=m.Transport(api=SimpleNamespace(scan=scan,Protocol=SimpleNamespace(AirPlay=1)),mdns=mdns,connect=lambda *a:None,parse=lambda x:x)
        receivers=await t.discover(None)
        self.assertEqual({r['address'] for r in receivers},{'192.0.2.10','192.0.2.20'})
        self.assertIn(['192.0.2.10'],calls)
        self.assertEqual(next(r for r in receivers if r['address']=='192.0.2.20')['kind'],'airplay-video')
