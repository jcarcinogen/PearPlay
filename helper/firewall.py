"""Bounded UFW guidance/management for PearPlay AirPlay timing (UDP 49170).

Scope is deliberately narrow: one source-scoped UDP rule per receiver, tagged
with an ownership comment. We never enable/disable the firewall, never touch a
rule we did not create, and never claim packet delivery from saved config.

Safety model:
  * inspect() is read-only: it parses /etc/ufw/{ufw.conf,user.rules} and never
    escalates.
  * request_change() runs the fixed installed helper via the fixed pkexec path
    and asks the user to authorise. The user can dismiss the prompt
    (auth_cancelled).
  * privileged_main() is the root entry the helper dispatches to. It validates
    that it is the frozen, root-owned installed binary run by a normal user
    through pkexec before touching ufw.
  * Ownership is tracked by the comment 'PearPlay timing uid=<uid>' on the rule
    we create. No credential files.

Limitation: ufw's `delete` matches a rule by its tuple (proto/port/src), not its
comment. We delete only after re-checking under root that our exact tagged rule
is present and that no identical foreign rule coexists; if both an owned and a
foreign equivalent exist we refuse (ambiguous_rule) rather than risk deleting
the foreign rule. A successful ufw exit is not trusted as proof of persistence:
we re-read user.rules and require the expected saved state before reporting
success.
"""
import asyncio
import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PORT = 49170
PROTO = 'udp'
TAG_PREFIX = 'PearPlay timing uid='
UFW_TIMEOUT = 30
PKEXEC_TIMEOUT = 120
PKEXEC = '/usr/bin/pkexec'
_OUTPUT_LIMIT = 4096

KNOWN_ERRORS = frozenset({
    'invalid_action', 'invalid_host', 'unsupported', 'auth_cancelled',
    'not_root', 'not_frozen', 'untrusted_executable', 'missing_identity',
    'ufw_failed', 'foreign_rule', 'not_present', 'ambiguous_rule',
})

# RFC1918 only — not Python's broader is_private (which also flags loopback,
# link-local, TEST-NET/documentation and unspecified ranges).
_PRIVATE_NETWORKS = (
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
)


def canonical_host(host):
    """Canonical private IPv4 unicast string, or None if not acceptable."""
    try:
        ip = ipaddress.ip_address(str(host))
    except ValueError:
        return None
    if ip.version != 4:
        return None
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return None
    if not any(ip in net for net in _PRIVATE_NETWORKS):
        return None
    return str(ip)


def ownership_tag(uid):
    return TAG_PREFIX + str(uid)


def _tuple_comment_hex(line):
    match = re.search(r'\bcomment=([0-9a-fA-F]+)\b', line)
    return match.group(1).lower() if match else None


def _rule_line_matches(line, host):
    """Conservative match of the iptables-save rule for our exact narrow scope.

    The rule we create is exactly::

        -A ufw-user-input -s <host> -p udp --dport 49170 -j ACCEPT

    Older ufw renders the source as a bare IP and newer as ``<host>/32``; both
    mean the same single host, so either form is accepted. Anything else is not
    ours and must not be claimed: a different source mask, a negated match, a
    destination or interface restriction, an extra module, a port range, or any
    stray token disqualifies the line.
    """
    tokens = line.split()
    if len(tokens) < 2 or tokens[0] != '-A' or tokens[1] != 'ufw-user-input':
        return False
    expected = {
        '-p': PROTO,
        '--dport': str(PORT),
        '-j': 'ACCEPT',
    }
    seen = set()
    seen_src = False
    i = 2
    while i < len(tokens):
        token = tokens[i]
        if token == '!':
            return False
        if token == '-s':
            # Same host only: canonical bare IP or its exact /32 rendering.
            if seen_src or i + 1 >= len(tokens):
                return False
            if tokens[i + 1] not in (host, host + '/32'):
                return False
            seen_src = True
            i += 2
            continue
        if token not in expected:
            return False
        if token in seen or i + 1 >= len(tokens) or tokens[i + 1] != expected[token]:
            return False
        seen.add(token)
        i += 2
    return seen == set(expected) and seen_src


def parse_rules(text, host, uid):
    """Conservative read of ufw user.rules -> (allowance, owned, foreign).

    allowance: 'missing' when no exact-scope rule is present, else 'present'.
    owned: True iff an exact-scope rule carries our ownership comment.
    foreign: True iff an exact-scope rule carries a different (or no) comment.

    A tuple comment only applies to the rule line(s) immediately under that
    tuple; any structural separator (chain declaration, ### marker, comment)
    ends the tuple block so a tag cannot carry into a later orphan rule.
    """
    tag_hex = ownership_tag(uid).encode('utf-8').hex()
    allowance = 'missing'
    owned = False
    foreign = False
    current_tag = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('### tuple ###'):
            current_tag = _tuple_comment_hex(line)
            continue
        if not line:
            continue
        if line[0] in ':#*':
            current_tag = None
            continue
        if _rule_line_matches(line, host):
            allowance = 'present'
            if current_tag == tag_hex:
                owned = True
            else:
                foreign = True
    return allowance, owned, foreign


def parse_enabled(text):
    """Read ENABLED from ufw.conf; None when absent/unknown."""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        if key.strip().upper() == 'ENABLED':
            v = value.strip().lower()
            if v == 'yes':
                return True
            if v == 'no':
                return False
    return None


class Runtime:
    """Every process/filesystem boundary lives here so tests can inject fakes."""

    ufw_paths = ('/usr/sbin/ufw', '/usr/bin/ufw')
    conf_path = '/etc/ufw/ufw.conf'
    rules_path = '/etc/ufw/user.rules'
    installed_executable = '/opt/pearplay/PearPlayHelper/PearPlayHelper'

    def getuid(self):
        return os.getuid()

    def geteuid(self):
        return os.geteuid()

    def is_frozen(self):
        return bool(getattr(sys, 'frozen', False))

    def executable(self):
        return Path(sys.executable).resolve()

    def getenv(self, name):
        return os.environ.get(name)

    def exists(self, path):
        return os.path.exists(path)

    def read_text(self, path):
        return Path(path).read_text()

    def stat(self, path):
        return os.stat(path)

    def ufw(self):
        for path in self.ufw_paths:
            if self.exists(path):
                return path
        return None

    def run(self, argv, timeout):
        return subprocess.run(argv, capture_output=True, timeout=timeout)

    async def run_async(self, argv, timeout):
        proc = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise
        return proc.returncode, out, err


def inspect(host, runtime=None):
    rt = runtime or Runtime()
    if rt.ufw() is None:
        return {'supported': False, 'enabled': None,
                'allowance': 'unknown', 'owned': False}
    result = {'supported': True, 'enabled': None,
              'allowance': 'unknown', 'owned': False}
    try:
        result['enabled'] = parse_enabled(rt.read_text(rt.conf_path))
    except OSError:
        result['enabled'] = None
    canonical = canonical_host(host)
    if canonical is None:
        return result
    try:
        rules = rt.read_text(rt.rules_path)
    except OSError:
        return result
    result['allowance'], result['owned'], _ = parse_rules(rules, canonical, rt.getuid())
    return result


async def request_change(action, host, runtime=None):
    rt = runtime or Runtime()
    if action not in ('allow', 'remove'):
        return {'ok': False, 'error': 'invalid_action'}
    canonical = canonical_host(host)
    if canonical is None:
        return {'ok': False, 'error': 'invalid_host'}
    if rt.ufw() is None:
        return {'ok': False, 'error': 'unsupported'}
    argv = [PKEXEC, rt.installed_executable, 'firewall-privileged', action, canonical]
    try:
        code, out, _ = await rt.run_async(argv, PKEXEC_TIMEOUT)
    except (OSError, asyncio.TimeoutError):
        return {'ok': False, 'error': 'unsupported'}
    if code == 126:
        return {'ok': False, 'error': 'auth_cancelled'}
    if code == 127:
        return {'ok': False, 'error': 'unsupported'}
    parsed = _parse_child_result(code, out)
    if parsed is not None:
        return parsed
    return {'ok': False, 'error': 'ufw_failed'}


def _parse_child_result(code, out):
    """Sanitise the helper's structured stdout; None if not a valid result."""
    try:
        data = json.loads(out[:_OUTPUT_LIMIT])
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get('ok'), bool):
        return None
    if data['ok']:
        # A nonzero exit means the privileged helper did not complete normally;
        # never report success in that case, whatever the stdout claims.
        if code == 0:
            return {'ok': True}
        return {'ok': False, 'error': 'ufw_failed'}
    error = data.get('error')
    if isinstance(error, str) and error in KNOWN_ERRORS:
        return {'ok': False, 'error': error}
    return {'ok': False, 'error': 'ufw_failed'}


def privileged_main(action, host, runtime=None):
    """Root entry: validate trust, then mutate only our own tagged rule."""
    rt = runtime or Runtime()
    result = _privileged(rt, action, host)
    print(json.dumps(result))
    return result


def _privileged(rt, action, host):
    error = _trusted(rt)
    if error:
        return {'ok': False, 'error': error}
    if action not in ('allow', 'remove'):
        return {'ok': False, 'error': 'invalid_action'}
    canonical = canonical_host(host)
    if canonical is None:
        return {'ok': False, 'error': 'invalid_host'}
    if rt.ufw() is None:
        return {'ok': False, 'error': 'unsupported'}
    uid = int(rt.getenv('PKEXEC_UID'))
    try:
        rules = rt.read_text(rt.rules_path)
    except OSError:
        return {'ok': False, 'error': 'ufw_failed'}
    allowance, owned, foreign = parse_rules(rules, canonical, uid)
    if action == 'allow':
        if owned:
            return {'ok': True}
        if allowance == 'present':
            return {'ok': False, 'error': 'foreign_rule'}
        return _mutate_and_verify(rt, 'allow', canonical, uid)
    # remove
    if not owned:
        return {'ok': False, 'error': 'not_present'}
    if foreign:
        return {'ok': False, 'error': 'ambiguous_rule'}
    return _mutate_and_verify(rt, 'remove', canonical, uid)


def _trusted(rt):
    """Validate the root entry's trust boundary; returns an error code or None."""
    if not rt.is_frozen():
        return 'not_frozen'
    if rt.geteuid() != 0:
        return 'not_root'
    uid_s = rt.getenv('PKEXEC_UID')
    if not uid_s or not uid_s.isdigit() or int(uid_s) < 1000:
        return 'missing_identity'
    exe = rt.executable()
    if exe != Path(rt.installed_executable):
        return 'untrusted_executable'
    try:
        st = rt.stat(exe)
    except OSError:
        return 'untrusted_executable'
    if st.st_uid != 0 or (st.st_mode & 0o022):
        return 'untrusted_executable'
    parent = exe.parent
    while True:
        try:
            ps = rt.stat(parent)
        except OSError:
            return 'untrusted_executable'
        if ps.st_uid != 0 or (ps.st_mode & 0o022):
            return 'untrusted_executable'
        if parent == parent.parent:
            break
        parent = parent.parent
    return None


def _mutate_and_verify(rt, action, host, uid):
    """Run ufw for the mutation, then confirm the saved state actually changed.

    A zero exit code is not proof the rule was persisted; re-read user.rules
    and require the expected owned/absent state before reporting success.
    """
    if action == 'allow':
        args = ['allow', 'from', host, 'to', 'any', 'port', str(PORT),
                'proto', PROTO, 'comment', ownership_tag(uid)]
    else:
        args = ['delete', 'allow', 'from', host, 'to', 'any',
                'port', str(PORT), 'proto', PROTO]
    try:
        proc = rt.run([rt.ufw()] + args, UFW_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return {'ok': False, 'error': 'ufw_failed'}
    if proc.returncode != 0:
        return {'ok': False, 'error': 'ufw_failed'}
    try:
        rules = rt.read_text(rt.rules_path)
    except OSError:
        return {'ok': False, 'error': 'ufw_failed'}
    allowance, owned, _foreign = parse_rules(rules, host, uid)
    if action == 'allow' and owned:
        return {'ok': True}
    if action == 'remove' and allowance == 'missing':
        return {'ok': True}
    return {'ok': False, 'error': 'ufw_failed'}
