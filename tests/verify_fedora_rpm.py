"""Verify a real Fedora RPM; --installed also checks it as an unprivileged user.

Run on Fedora: python3 tests/verify_fedora_rpm.py /absolute/package.rpm [--installed]
This check intentionally pins the Fedora 44 / 0.2.5 rehearsal baseline.
Use only trusted locally built PearPlay RPMs: --installed executes the installed
helper's self-test; it is not a sandbox or a signature/authenticity check.
No installation, registration, discovery, or playback is performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('rpm', type=Path)
parser.add_argument('--installed', action='store_true')
args = parser.parse_args()
package = args.rpm.resolve(strict=True)

def rpm(*options):
    return subprocess.check_output(['rpm', '-qp', *options, str(package)], text=True)

identity = rpm('--qf', '%{NAME} %{VERSION} %{ARCH}').strip()
assert identity == 'pearplay-helper 0.2.5 x86_64', identity
requirements = rpm('--requires').splitlines()
assert {'zenity', 'avahi-tools', 'glibc >= 2.43'} <= set(requirements), requirements
assert not rpm('--scripts').strip(), 'Package must not modify per-user state through scriptlets'
rows = [line.split('\t') for line in rpm('--qf', '[%{FILENAMES}\t%{FILEMODES}\t%{FILEUSERNAME}\t%{FILEGROUPNAME}\n]').splitlines()]
paths = {row[0] for row in rows}
required = {'/opt/pearplay/PearPlayHelper/PearPlayHelper',
            '/opt/pearplay/PearPlayHelper/_internal/build.json',
            '/opt/pearplay/PearPlayHelper/LICENSE',
            '/usr/share/applications/pearplay-setup.desktop',
            '/usr/share/icons/hicolor/128x128/apps/pearplay.png'}
assert required <= paths, required - paths
for name, mode, owner, group in rows:
    mode = int(mode)  # RPM numeric tags are decimal unless :octal is requested.
    assert owner == group == 'root', (name, owner, group)
    assert name == '/opt/pearplay' or name.startswith('/opt/pearplay/') or name in required, name
    # This measured payload contains no links or special files. Fail closed if
    # a later build introduces one; accepting links needs target validation.
    assert stat.S_ISREG(mode) or stat.S_ISDIR(mode), ('unexpected_file_type', name)
    assert not mode & 0o7022, (name, oct(mode))
    permissions = stat.S_IMODE(mode)
    assert permissions in (0o644, 0o755), (name, oct(mode))
    data = (Path(name).name == 'LICENSE' or Path(name).suffix in ('.py', '.json', '.png', '.desktop')
            or Path(name).is_relative_to('/opt/pearplay/PearPlayHelper/THIRD_PARTY_LICENSES'))
    if stat.S_ISDIR(mode):
        assert permissions == 0o755, name
    elif data:
        assert permissions == 0o644, name
    if args.installed:
        path = Path(name)
        info = path.lstat()
        assert info.st_uid == info.st_gid == 0, name
        assert stat.S_IMODE(info.st_mode) == permissions, name
        assert os.access(path, os.R_OK), name
        if stat.S_ISREG(mode):
            with path.open('rb') as stream:
                stream.read(1)

report = dict(identity=identity, files=len(rows), requirements=requirements,
              rootOwned=True, modesChecked=True, scriptlets=False,
              sha256=hashlib.sha256(package.read_bytes()).hexdigest(), installed=args.installed)
subprocess.run(['rpm', '-K', str(package)], check=True, capture_output=True)
if args.installed:
    assert os.getuid() != 0, 'Installed checks must run unprivileged'
    subprocess.run(['rpm', '-V', 'pearplay-helper'], check=True, capture_output=True)
    binary = '/opt/pearplay/PearPlayHelper/PearPlayHelper'
    report['selfTest'] = json.loads(subprocess.check_output([binary, 'self-test'], text=True))
    assert report['selfTest']['ok'] is True
    config = json.loads(Path('/opt/pearplay/PearPlayHelper/_internal/build.json').read_text())
    assert config['extension_id'] == 'eoadahoncjfpnennmkjifohclbafjkol'
    assert config['development'] is False
    source = Path(__file__).resolve().parents[1]
    assert Path('/opt/pearplay/PearPlayHelper/LICENSE').read_bytes() == (source/'LICENSE').read_bytes()
    report['productionIdentity'] = config['extension_id']
print(json.dumps(report, indent=2))
