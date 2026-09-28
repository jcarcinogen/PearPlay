"""Native firewall requests are selected-receiver scoped and opt-in."""
import unittest
from unittest.mock import patch, AsyncMock
from test_helper_protocol import load, request

HOST = '192.168.1.50'
ID = 'AA:BB:CC:DD:EE:FF'

class FirewallIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_check_is_read_only_and_mutation_needs_discovered_receiver(self):
        m = load()
        host = m.Host(lambda: None, lambda event: None)
        args = dict(receiver=ID, host=HOST, action='check')
        with patch('helper.firewall.inspect', return_value={'supported': True, 'enabled': True, 'allowance': 'missing', 'owned': False}) as inspect, patch('helper.firewall.request_change', new_callable=AsyncMock) as change:
            result = await host.handle(request('firewall', args))
            self.assertEqual(result.get('error'), 'receiver_not_discovered')
            inspect.assert_not_called()
            host.receivers = [dict(identifier=ID, address=HOST)]
            result = await host.handle(request('firewall', args))
            self.assertTrue(result['ok'])
            self.assertEqual(result['firewall']['allowance'], 'missing')
            change.assert_not_called()
            change.return_value = {'ok': False, 'error': 'auth_cancelled'}
            result = await host.handle(request('firewall', dict(args, action='allow')))
            self.assertTrue(result['ok'], 'firewall refusal must not overwrite playback state')
            self.assertEqual(result['firewall']['change'], {'ok': False, 'error': 'auth_cancelled'})
            change.assert_awaited_once_with('allow', HOST)
            self.assertEqual(host.state, 'idle')

    async def test_legacy_capability_list_and_strict_arguments(self):
        m = load()
        host = m.Host(lambda: None, lambda event: None)
        hello = await host.handle(request())
        self.assertTrue(hello.get('firewallSupport'))
        self.assertNotIn('firewall', hello['capabilities'], 'old Store clients reject unknown capabilities')
        good = dict(receiver=ID, host=HOST, action='check')
        m.validate(request('firewall', good))
        for args in [dict(good, action='disable'), dict(good, confirmed=True), dict(good, host='8.8.8.8')]:
            with self.assertRaises(ValueError): m.validate(request('firewall', args))

class FirewallCLI(unittest.TestCase):
    def test_fixed_root_entry_dispatches_only_exact_arguments(self):
        app = load('app')
        with patch('helper.firewall.privileged_main', return_value={'ok': False, 'error': 'not_frozen'}) as entry:
            self.assertEqual(app.main(['firewall-privileged','allow', HOST], config={'extension_id':'a'*32}), 1)
            entry.assert_called_once_with('allow', HOST)
            entry.reset_mock()
            self.assertEqual(app.main(['firewall-privileged','allow',HOST,'extra'], config={'extension_id':'a'*32}), 2)
            entry.assert_not_called()
