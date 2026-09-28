"""Bounded UFW guidance/management tests for PearPlay timing (UDP 49170).

Read-only inspection never escalates; mutation goes through the fixed pkexec
path into a validated root entry. Ownership is tracked by a comment on the rule
we create. All process/filesystem boundaries are injected via a fake runtime,
which simulates ufw persisting mutations to user.rules so the module's
save-state verification can be exercised.
"""
import asyncio
import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / 'helper' / 'firewall.py'
    assert path.exists(), 'helper/firewall.py missing'
    spec = importlib.util.spec_from_file_location('pearplay_firewall', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load()

UID = 1000
HOST = '192.168.1.50'
TAG = 'PearPlay timing uid=1000'
INSTALLED = '/opt/pearplay/PearPlayHelper/PearPlayHelper'
PKEXEC = '/usr/bin/pkexec'
RULE_LINE = '-A ufw-user-input -s %s/32 -p udp --dport 49170 -j ACCEPT'
BARE_RULE_LINE = '-A ufw-user-input -s %s -p udp --dport 49170 -j ACCEPT'


def owned_rule(host=HOST, uid=UID):
    # Real ufw tuple shape: <action> <proto> <dport> <dst> <dir> <src> <dir>.
    return ('### tuple ### allow udp 49170 0.0.0.0/0 any %s in '
            'comment=%s\n' % (host, ('PearPlay timing uid=' + str(uid)).encode().hex())
            + BARE_RULE_LINE % host)


def foreign_rule(host=HOST, comment=None):
    base = '### tuple ### allow udp 49170 0.0.0.0/0 any %s in' % host
    if comment:
        base += ' comment=' + comment.encode().hex()
    return base + '\n' + BARE_RULE_LINE % host


def rules_file(*blocks):
    return ('*filter\n:ufw-user-input - [0:0]\n:ufw-user-output - [0:0]\n'
            '### END RULES ###\n' + '\n'.join(blocks) + '\n')


def _split_blocks(text):
    """Split a user.rules text into block strings (tuple line + rule lines)."""
    blocks = []
    cur = None
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith('### tuple ###'):
            if cur is not None:
                blocks.append(cur)
            cur = raw
        elif s.startswith('-A') and cur is not None:
            cur += '\n' + raw
    if cur is not None:
        blocks.append(cur)
    return blocks


class FakeRuntime:
    conf_path = '/etc/ufw/ufw.conf'
    rules_path = '/etc/ufw/user.rules'
    installed_executable = INSTALLED

    def __init__(self, **kw):
        self.files = {self.rules_path: rules_file(), self.conf_path: 'ENABLED=yes\n'}
        self.ufw_path = '/usr/sbin/ufw'
        self.uid = UID
        self.euid = 0
        self.frozen = True
        self.executable_path = INSTALLED
        self.pkexec_uid = str(UID)
        self.stats = {}
        self.sync_results = []
        self.async_results = []
        self.run_calls = []
        self.async_calls = []
        self.persist_mutations = True
        for k, v in kw.items():
            setattr(self, k, v)

    def getuid(self):
        return self.uid

    def geteuid(self):
        return self.euid

    def is_frozen(self):
        return self.frozen

    def executable(self):
        return Path(self.executable_path)

    def getenv(self, name):
        return self.pkexec_uid if name == 'PKEXEC_UID' else None

    def exists(self, path):
        return path in self.files or (self.ufw_path is not None and path == self.ufw_path)

    def read_text(self, path):
        if path in self.files:
            return self.files[path]
        raise OSError('no such file: %s' % path)

    def stat(self, path):
        key = str(path)
        if key in self.stats:
            return self.stats[key]
        return SimpleNamespace(st_uid=0, st_mode=0o755)

    def ufw(self):
        return self.ufw_path

    def run(self, argv, timeout):
        self.run_calls.append(list(argv))
        code, out, err = self.sync_results.pop(0) if self.sync_results else (0, b'', b'')
        if code == 0 and self.persist_mutations:
            self._apply_mutation(argv)
        return SimpleNamespace(returncode=code, stdout=out, stderr=err)

    def _apply_mutation(self, argv):
        """Simulate ufw persisting an allow/delete to user.rules."""
        if not argv or argv[0] != self.ufw_path or len(argv) < 2:
            return
        verb = argv[1]
        blocks = _split_blocks(self.files.get(self.rules_path, rules_file()))
        if verb == 'allow':
            host = argv[3]
            blocks = [b for b in blocks if not any(m._rule_line_matches(r, host)
                                                   for r in b.splitlines())]
            blocks.append(owned_rule(host, self.uid))
        elif verb == 'delete':
            host = argv[4]
            blocks = [b for b in blocks if not any(m._rule_line_matches(r, host)
                                                   for r in b.splitlines())]
        self.files[self.rules_path] = rules_file(*blocks)

    async def run_async(self, argv, timeout):
        self.async_calls.append(list(argv))
        code, out, err = self.async_results.pop(0) if self.async_results else (0, b'', b'')
        return code, out, err


class CanonicalHostTests(unittest.TestCase):
    def test_accepts_private_unicast(self):
        for host in ['192.168.1.50', '10.0.0.7', '172.16.0.1', '172.31.255.254']:
            self.assertEqual(m.canonical_host(host), host)

    def test_rejects_non_private_and_special(self):
        for host in ['127.0.0.1', '169.254.1.1', '224.0.0.1', '0.0.0.0',
                     '8.8.8.8', '192.0.2.10', '::1', 'fe80::1', 'not-an-ip',
                     '192.168.1.999', None]:
            self.assertIsNone(m.canonical_host(host))


class RuleLineMatchTests(unittest.TestCase):
    def test_exact_rule_matches(self):
        self.assertTrue(m._rule_line_matches(RULE_LINE % HOST, HOST))

    def test_bare_ip_rule_matches(self):
        # The real Acer saved line uses a bare source IP (no /32).
        self.assertTrue(m._rule_line_matches(BARE_RULE_LINE % HOST, HOST))

    def test_real_acer_bare_ip_order_matches(self):
        self.assertTrue(m._rule_line_matches(
            '-A ufw-user-input -p udp --dport 49170 -s %s -j ACCEPT' % HOST, HOST))

    def test_bare_ip_wrong_host_is_not_claimed(self):
        self.assertFalse(m._rule_line_matches(
            '-A ufw-user-input -s 10.0.0.1 -p udp --dport 49170 -j ACCEPT', HOST))

    def test_source_mask_is_preserved(self):
        # a broader /24 source is not our exact /32 rule
        self.assertFalse(m._rule_line_matches(
            '-A ufw-user-input -s %s/24 -p udp --dport 49170 -j ACCEPT' % HOST, HOST))

    def test_negated_source_is_not_claimed(self):
        self.assertFalse(m._rule_line_matches(
            '-A ufw-user-input ! -s %s/32 -p udp --dport 49170 -j ACCEPT' % HOST, HOST))

    def test_destination_restriction_is_not_claimed(self):
        self.assertFalse(m._rule_line_matches(
            '-A ufw-user-input -s %s/32 -d 10.0.0.1/32 -p udp --dport 49170 -j ACCEPT' % HOST,
            HOST))

    def test_interface_restriction_is_not_claimed(self):
        self.assertFalse(m._rule_line_matches(
            '-A ufw-user-input -s %s/32 -i eth0 -p udp --dport 49170 -j ACCEPT' % HOST, HOST))

    def test_port_range_is_not_claimed(self):
        self.assertFalse(m._rule_line_matches(
            '-A ufw-user-input -s %s/32 -p udp --dport 49170:49180 -j ACCEPT' % HOST, HOST))


class InspectTests(unittest.TestCase):
    def test_unavailable_ufw_is_unsupported(self):
        rt = FakeRuntime(ufw_path=None)
        self.assertEqual(m.inspect(HOST, rt), {
            'supported': False, 'enabled': None,
            'allowance': 'unknown', 'owned': False})

    def test_enabled_and_empty_rules(self):
        rt = FakeRuntime()
        result = m.inspect(HOST, rt)
        self.assertEqual(result, {
            'supported': True, 'enabled': True,
            'allowance': 'missing', 'owned': False})

    def test_disabled_and_unknown_config(self):
        rt = FakeRuntime()
        rt.files[rt.conf_path] = 'ENABLED=no\n'
        self.assertEqual(m.inspect(HOST, rt)['enabled'], False)
        del rt.files[rt.conf_path]
        self.assertIsNone(m.inspect(HOST, rt)['enabled'])
        rt.files[rt.conf_path] = '# no enabled key\n'
        self.assertIsNone(m.inspect(HOST, rt)['enabled'])

    def test_owned_rule_is_reported(self):
        rt = FakeRuntime()
        rt.files[rt.rules_path] = rules_file(owned_rule())
        self.assertEqual(m.inspect(HOST, rt), {
            'supported': True, 'enabled': True,
            'allowance': 'present', 'owned': True})

    def test_foreign_rule_with_other_comment_is_not_owned(self):
        rt = FakeRuntime()
        rt.files[rt.rules_path] = rules_file(foreign_rule(comment='someone else'))
        self.assertEqual(m.inspect(HOST, rt)['allowance'], 'present')
        self.assertFalse(m.inspect(HOST, rt)['owned'])

    def test_foreign_rule_without_comment_is_not_owned(self):
        rt = FakeRuntime()
        rt.files[rt.rules_path] = rules_file(foreign_rule())
        self.assertEqual(m.inspect(HOST, rt)['allowance'], 'present')
        self.assertFalse(m.inspect(HOST, rt)['owned'])

    def test_broader_or_different_scope_is_not_claimed(self):
        rt = FakeRuntime()
        # subnet, different port, and tcp are not our exact narrow rule
        rt.files[rt.rules_path] = rules_file(
            '-A ufw-user-input -s 192.168.1.0/24 -p udp --dport 49170 -j ACCEPT',
            '-A ufw-user-input -s 192.168.1.50/32 -p udp --dport 49171 -j ACCEPT',
            '-A ufw-user-input -s 192.168.1.50/32 -p tcp --dport 49170 -j ACCEPT')
        self.assertEqual(m.inspect(HOST, rt)['allowance'], 'missing')

    def test_tuple_comment_does_not_carry_past_separator(self):
        rt = FakeRuntime()
        # A tuple carrying OUR tag whose rule is for a *different* host, then an
        # END RULES separator, then an orphan rule matching HOST. The orphan must
        # be foreign, not owned.
        other = owned_rule(host='10.0.0.1', uid=UID)
        stray = RULE_LINE % HOST
        rt.files[rt.rules_path] = ('*filter\n' + other + '\n### END RULES ###\n'
                                   + stray + '\n')
        result = m.inspect(HOST, rt)
        self.assertEqual(result['allowance'], 'present')
        self.assertFalse(result['owned'])

    def test_malformed_host_reports_unknown_allowance(self):
        rt = FakeRuntime()
        result = m.inspect('not-an-ip', rt)
        self.assertTrue(result['supported'])
        self.assertEqual(result['allowance'], 'unknown')
        self.assertFalse(result['owned'])

    def test_missing_rules_file_is_unknown(self):
        rt = FakeRuntime()
        del rt.files[rt.rules_path]
        result = m.inspect(HOST, rt)
        self.assertEqual(result['allowance'], 'unknown')
        self.assertFalse(result['owned'])

    def test_actual_tuple_shape_preserves_ownership(self):
        rt = FakeRuntime()
        tag = ('PearPlay timing uid=' + str(UID)).encode().hex()
        rt.files[rt.rules_path] = rules_file(
            '### tuple ### allow udp 49170 0.0.0.0/0 any %s in comment=%s\n'
            % (HOST, tag)
            + '-A ufw-user-input -p udp --dport 49170 -s %s -j ACCEPT' % HOST)
        result = m.inspect(HOST, rt)
        self.assertEqual(result['allowance'], 'present')
        self.assertTrue(result['owned'])


class RequestChangeTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_action_and_host(self):
        self.assertEqual(await m.request_change('bogus', HOST, FakeRuntime()),
                         {'ok': False, 'error': 'invalid_action'})
        self.assertEqual(await m.request_change('allow', '8.8.8.8', FakeRuntime()),
                         {'ok': False, 'error': 'invalid_host'})

    async def test_unsupported_when_no_ufw(self):
        rt = FakeRuntime(ufw_path=None)
        self.assertEqual(await m.request_change('allow', HOST, rt),
                         {'ok': False, 'error': 'unsupported'})
        self.assertEqual(rt.async_calls, [])

    async def test_invokes_fixed_pkexec_with_installed_helper(self):
        rt = FakeRuntime()
        rt.async_results = [(0, b'{"ok": true}', b'')]
        result = await m.request_change('allow', HOST, rt)
        self.assertEqual(result, {'ok': True})
        self.assertEqual(rt.async_calls,
                         [[PKEXEC, INSTALLED, 'firewall-privileged', 'allow', HOST]])

    async def test_auth_cancelled_on_dismiss(self):
        rt = FakeRuntime()
        rt.async_results = [(126, b'', b'')]
        self.assertEqual(await m.request_change('allow', HOST, rt),
                         {'ok': False, 'error': 'auth_cancelled'})

    async def test_forwards_child_error_code(self):
        rt = FakeRuntime()
        rt.async_results = [(1, b'{"ok": false, "error": "foreign_rule"}', b'')]
        self.assertEqual(await m.request_change('allow', HOST, rt),
                         {'ok': False, 'error': 'foreign_rule'})

    async def test_nonzero_exit_never_yields_ok_true(self):
        rt = FakeRuntime()
        rt.async_results = [(1, b'{"ok": true}', b'')]
        self.assertEqual(await m.request_change('allow', HOST, rt),
                         {'ok': False, 'error': 'ufw_failed'})

    async def test_unhashable_error_fails_closed(self):
        rt = FakeRuntime()
        rt.async_results = [(0, b'{"ok": false, "error": ["list", "items"]}', b'')]
        self.assertEqual(await m.request_change('allow', HOST, rt),
                         {'ok': False, 'error': 'ufw_failed'})

    async def test_malformed_or_unknown_child_output_fails_closed(self):
        rt = FakeRuntime()
        rt.async_results = [(0, b'not json', b'')]
        self.assertEqual(await m.request_change('allow', HOST, rt),
                         {'ok': False, 'error': 'ufw_failed'})
        rt.async_results = [(0, b'{"ok": false, "error": "secret detail"}', b'')]
        self.assertEqual(await m.request_change('allow', HOST, rt),
                         {'ok': False, 'error': 'ufw_failed'})
        rt.async_results = [(3, b'', b'raw stderr here')]
        self.assertEqual(await m.request_change('allow', HOST, rt),
                         {'ok': False, 'error': 'ufw_failed'})


class PrivilegedTrustTests(unittest.TestCase):
    def run_priv(self, rt, action='allow', host=HOST):
        with contextlib.redirect_stdout(io.StringIO()):
            return m.privileged_main(action, host, rt)

    def test_requires_frozen(self):
        rt = FakeRuntime(frozen=False)
        self.assertEqual(self.run_priv(rt), {'ok': False, 'error': 'not_frozen'})
        self.assertEqual(rt.run_calls, [])

    def test_requires_root(self):
        rt = FakeRuntime(euid=501)
        self.assertEqual(self.run_priv(rt), {'ok': False, 'error': 'not_root'})

    def test_requires_normal_pkexec_uid(self):
        for bad in [None, '', '0', 'root', '-1', '500']:
            rt = FakeRuntime(pkexec_uid=bad)
            self.assertEqual(self.run_priv(rt),
                             {'ok': False, 'error': 'missing_identity'}, bad)

    def test_requires_installed_executable_path(self):
        rt = FakeRuntime(executable_path='/tmp/evil-helper')
        self.assertEqual(self.run_priv(rt),
                         {'ok': False, 'error': 'untrusted_executable'})

    def test_requires_root_owned_executable(self):
        rt = FakeRuntime()
        rt.stats[INSTALLED] = SimpleNamespace(st_uid=1000, st_mode=0o755)
        self.assertEqual(self.run_priv(rt),
                         {'ok': False, 'error': 'untrusted_executable'})

    def test_requires_non_writable_executable(self):
        rt = FakeRuntime()
        rt.stats[INSTALLED] = SimpleNamespace(st_uid=0, st_mode=0o777)
        self.assertEqual(self.run_priv(rt),
                         {'ok': False, 'error': 'untrusted_executable'})

    def test_requires_non_writable_parents(self):
        rt = FakeRuntime()
        rt.stats['/opt/pearplay/PearPlayHelper'] = SimpleNamespace(st_uid=0, st_mode=0o777)
        self.assertEqual(self.run_priv(rt),
                         {'ok': False, 'error': 'untrusted_executable'})

    def test_invalid_action_and_host_rejected(self):
        rt = FakeRuntime()
        self.assertEqual(self.run_priv(rt, action='bogus'),
                         {'ok': False, 'error': 'invalid_action'})
        self.assertEqual(self.run_priv(rt, host='8.8.8.8'),
                         {'ok': False, 'error': 'invalid_host'})


class PrivilegedMutationTests(unittest.TestCase):
    def run_priv(self, rt, action='allow', host=HOST):
        with contextlib.redirect_stdout(io.StringIO()):
            return m.privileged_main(action, host, rt)

    def allow_argv(self, host=HOST):
        return ['/usr/sbin/ufw', 'allow', 'from', host, 'to', 'any',
                'port', '49170', 'proto', 'udp', 'comment', TAG]

    def delete_argv(self, host=HOST):
        return ['/usr/sbin/ufw', 'delete', 'allow', 'from', host, 'to', 'any',
                'port', '49170', 'proto', 'udp']

    def test_allow_adds_exact_tagged_rule(self):
        rt = FakeRuntime()
        rt.sync_results = [(0, b'', b'')]
        self.assertEqual(self.run_priv(rt, 'allow'), {'ok': True})
        self.assertEqual(rt.run_calls, [self.allow_argv()])

    def test_allow_is_idempotent_when_owned(self):
        rt = FakeRuntime()
        rt.files[rt.rules_path] = rules_file(owned_rule())
        self.assertEqual(self.run_priv(rt, 'allow'), {'ok': True})
        self.assertEqual(rt.run_calls, [])

    def test_allow_refuses_foreign_equivalent_rule(self):
        rt = FakeRuntime()
        rt.files[rt.rules_path] = rules_file(foreign_rule(comment='other'))
        self.assertEqual(self.run_priv(rt, 'allow'),
                         {'ok': False, 'error': 'foreign_rule'})
        self.assertEqual(rt.run_calls, [])

    def test_allow_requires_persisted_state(self):
        # ufw reports success but nothing is written -> must not claim success
        rt = FakeRuntime(persist_mutations=False)
        rt.sync_results = [(0, b'', b'')]
        self.assertEqual(self.run_priv(rt, 'allow'),
                         {'ok': False, 'error': 'ufw_failed'})

    def test_remove_deletes_only_owned_rule(self):
        rt = FakeRuntime()
        rt.files[rt.rules_path] = rules_file(owned_rule())
        rt.sync_results = [(0, b'', b'')]
        self.assertEqual(self.run_priv(rt, 'remove'), {'ok': True})
        self.assertEqual(rt.run_calls, [self.delete_argv()])

    def test_remove_preserves_foreign_rule(self):
        rt = FakeRuntime()
        rt.files[rt.rules_path] = rules_file(foreign_rule(comment='other'))
        self.assertEqual(self.run_priv(rt, 'remove'),
                         {'ok': False, 'error': 'not_present'})
        self.assertEqual(rt.run_calls, [])

    def test_remove_refuses_ambiguous_owned_and_foreign(self):
        rt = FakeRuntime()
        rt.files[rt.rules_path] = rules_file(owned_rule(), foreign_rule(comment='other'))
        self.assertEqual(self.run_priv(rt, 'remove'),
                         {'ok': False, 'error': 'ambiguous_rule'})
        self.assertEqual(rt.run_calls, [])

    def test_remove_absent_rule_is_not_present(self):
        rt = FakeRuntime()
        self.assertEqual(self.run_priv(rt, 'remove'),
                         {'ok': False, 'error': 'not_present'})
        self.assertEqual(rt.run_calls, [])

    def test_remove_requires_persisted_state(self):
        # ufw reports success but the rule is still present -> must not claim success
        rt = FakeRuntime(persist_mutations=False)
        rt.files[rt.rules_path] = rules_file(owned_rule())
        rt.sync_results = [(0, b'', b'')]
        self.assertEqual(self.run_priv(rt, 'remove'),
                         {'ok': False, 'error': 'ufw_failed'})

    def test_ufw_failure_reports_static_error(self):
        rt = FakeRuntime()
        rt.sync_results = [(1, b'', b'private stderr detail')]
        self.assertEqual(self.run_priv(rt, 'allow'),
                         {'ok': False, 'error': 'ufw_failed'})
        # raw stderr never leaks into the result
        self.assertNotIn('private', json.dumps(self.run_priv(rt, 'allow')))


if __name__ == '__main__':
    unittest.main()
