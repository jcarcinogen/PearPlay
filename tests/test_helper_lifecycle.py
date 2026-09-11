import asyncio
import unittest
from test_helper_protocol import load, request

class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_pairing_required_event_has_static_cli_guidance(self):
        m=load(); events=[]
        class Transport:
            async def run(self,args,notify): raise m.HelperError('pairing_required')
        h=m.Host(Transport,events.append)
        await h.playback({})
        self.assertEqual(events[-1]['error'],'pairing_required')
        self.assertEqual(events[-1]['pairing'], 'Run helper/native.py pair --identifier RECEIVER --host IP in a terminal; PIN is hidden.')

    async def test_persistent_start_event_status_stop_restart_and_disconnect(self):
        m = load(); events=[]; instances=[]
        class Transport:
            async def discover(self, host):
                return [{'identifier':'AA:BB:CC:DD:EE:FF','address':'127.0.0.1','label':'Apple TV'}]
            async def run(self, args, notify):
                instances.append(self)
                notify('playing','protocol')
                try: await asyncio.Event().wait()
                finally: self.closed=True
        h=m.Host(Transport, events.append)
        self.assertEqual((await h.handle(request()))['capabilities'], ['hello','discover','start','status','stop'])
        self.assertEqual((await h.handle(request('pause')))['error'], 'unsupported')
        args={'receiver':'AA:BB:CC:DD:EE:FF','host':'127.0.0.1','url':'https://example.org/SECRET'}
        self.assertEqual((await h.handle(request('start',args)))['error'],'receiver_not_discovered')
        await h.handle(request('discover'))
        self.assertEqual((await h.handle(request('start',args)))['state'],'connecting')
        await asyncio.sleep(0)
        self.assertEqual((await h.handle(request('status')))['state'],'playing')
        self.assertEqual(events[-1]['evidence'],'protocol')
        self.assertEqual((await h.handle(request('start',args)))['error'],'busy')
        stopped=await h.handle(request('stop'))
        self.assertEqual((stopped['state'],stopped['evidence']),('stopped','unverified'))
        self.assertTrue(instances[0].closed)
        await h.handle(request('start',args)); await asyncio.sleep(0)
        await h.close(); self.assertTrue(instances[1].closed)
        self.assertNotIn('SECRET',str(events))

    async def test_async_failure_is_static_and_bad_input_preserves_id_only_if_valid(self):
        m=load(); events=[]
        class Transport:
            async def discover(self,host): raise RuntimeError('SECRET')
        h=m.Host(Transport,events.append)
        result=await h.handle(request('discover'))
        self.assertEqual(result['error'],'transport_failed')
        self.assertNotIn('SECRET',str(result))
        result=await h.handle(dict(request(),id='SECRET?'))
        self.assertEqual(result['id'],'event')
        self.assertEqual(result['error'],'invalid_request')
