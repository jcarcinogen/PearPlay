"""No-network pairing contract: consumed failures require a fresh begin."""
import unittest
from helper.native import Host, HelperError


class PairingRetryContract(unittest.IsolatedAsyncioTestCase):
    async def test_consumed_failure_repeated_retry_and_success(self):
        attempts = []
        class Pair:
            closed = False
            async def finish(self, pin):
                # No PIN retained, printed, or included in assertion messages.
                self.closed = True
                if len(attempts) < 3:
                    raise HelperError('pairing_failed')
            async def close(self):
                self.closed = True
        class Factory:
            async def begin_pair(self, receiver, host):
                p = Pair()
                attempts.append(p)
                return p
        host = Host(Factory, lambda _: None)
        async def request(op):
            args = {'receiver': 'AA:BB:CC:DD:EE:01', 'host': '192.0.2.1'}
            if op == 'pair': args['pin'] = '0000'
            return await host.handle({'v': 1, 'id': op, 'op': op, 'args': args})
        try:
            for _ in range(2):
                self.assertTrue((await request('pair_begin'))['ok'])
                self.assertEqual((await request('pair'))['error'], 'pairing_failed')
                self.assertIsNone(host.open_pair)
                self.assertEqual((await request('pair'))['error'], 'pairing_required')
            self.assertTrue((await request('pair_begin'))['ok'])
            self.assertTrue((await request('pair'))['ok'])
            self.assertIsNone(host.open_pair)
            self.assertEqual(len(attempts), 3)
            self.assertTrue(all(p.closed for p in attempts))
        finally:
            await host.close()

    async def test_fresh_begin_replaces_abandoned_popup_pair(self):
        pairs = []
        class Pair:
            closed = False
            async def close(self): self.closed = True
        class Factory:
            async def begin_pair(self, receiver, host):
                p = Pair(); pairs.append(p); return p
        host = Host(Factory, lambda _: None)
        request = {'v': 1, 'id': 'begin', 'op': 'pair_begin',
                   'args': {'receiver': 'AA:BB:CC:DD:EE:01', 'host': '192.0.2.1'}}
        try:
            self.assertTrue((await host.handle(request))['ok'])
            self.assertTrue((await host.handle(request))['ok'])
            self.assertTrue(pairs[0].closed)
            self.assertFalse(pairs[1].closed)
        finally:
            await host.close()
        self.assertTrue(pairs[1].closed)
