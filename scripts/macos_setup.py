"""Paused Mac installer internals; receipt-guarded removal remains available."""
import hashlib
import json
import os
from pathlib import Path
import sys
import argparse
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from helper import install

PAYLOAD = ('helper/native.py', 'helper/install.py', 'spikes/001-airplay/pearplay.py',
           'spikes/002-command/command.py', 'spikes/002-command/LICENSE.md', 'requirements.txt',
           'scripts/macos_setup.py', 'install-macos.sh')


def stage(source, destination):
    """Copy only distribution files; reuse only exact, previously recorded bytes."""
    source, destination = Path(source), Path(destination)
    files = {name: (source/name).read_bytes() for name in (*PAYLOAD, 'terminal-build.json')}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    receipt = destination/'.pearplay-source.json'
    fd = install.directory(destination.parent, True)
    os.close(fd)
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or receipt.is_symlink() or not receipt.is_file():
            raise ValueError('existing_payload_not_owned')
        if json.loads(receipt.read_text()) != hashes:
            raise ValueError('existing_payload_not_owned')
        for name, digest in hashes.items():
            path = destination/name
            if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError('modified_payload_preserved')
        return
    destination.mkdir(mode=0o700)
    for name, data in files.items():
        path = destination/name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with path.open('xb') as output:
            output.write(data)
        path.chmod(0o600)
    with receipt.open('x') as output:
        json.dump(hashes, output, sort_keys=True)
    receipt.chmod(0o600)


def configure(config, source, data_home, parent, uv, action, run=subprocess.run):
    version=config.get('version')
    if action not in ('install', 'remove') or not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('invalid_terminal_build')
    root=Path(data_home)/version
    python=root/'venv/bin/python'
    kwargs=dict(extension_id=config.get('extension_id'), browser='chrome', config_parent=Path(parent),
                python=python, source=root/'source', platform='darwin')
    paths, payloads=install.plan(**kwargs, require_runtime=False)
    if action=='remove':
        if install.uninstall(**kwargs):
            raise ValueError('modified_registration_preserved')
        return {'ok': True, 'action':'removed', 'pairing':'preserved', 'runtime':'preserved'}
    # Refuse old/foreign registrations before installing any runtime or dependencies.
    try:
        fd=install.directory(paths['manifest'].parent, False)
    except FileNotFoundError:
        fd=None
    if fd is not None:
        try:
            if any(install.matches(fd, path.name, *payloads[key]) is False for key, path in paths.items()):
                raise ValueError('existing_registration_preserved')
        finally:
            os.close(fd)
    marker=root/'.pearplay-runtime.json'
    identity={'version':version, 'extension_id':config['extension_id']}
    if root.exists() or root.is_symlink():
        if root.is_symlink() or marker.is_symlink() or not marker.is_file() or json.loads(marker.read_text()) != identity:
            raise ValueError('existing_runtime_not_owned')
    else:
        fd=install.directory(root, True); os.close(fd)
        with marker.open('x') as output: json.dump(identity, output)
        marker.chmod(0o600)
    if (root/'venv').is_symlink() or (root/'venv/bin').is_symlink():
        raise ValueError('symlinked_runtime_preserved')
    stage(source, root/'source')
    if not python.exists():
        if (root/'venv').exists(): raise ValueError('incomplete_runtime_preserved')
        run([str(uv), '--no-config', 'venv', '--python', '3.11', str(root/'venv')], check=True)
    run([str(uv), '--no-config', 'pip', 'install', '--python', str(python), '-r', str(root/'source/requirements.txt')], check=True)
    run([str(python), '-c', 'import sys; sys.path.insert(0,sys.argv[1]); from helper.native import Transport; Transport()', str(root/'source')], check=True)
    install.install(**kwargs)
    return {'ok': True, 'action':'connected', 'version':version, 'network':'not used'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='install', choices=['install','remove'])
    parser.add_argument('--uv', required=True, type=Path)
    parser.add_argument('--data-home', type=Path, default=Path.home()/'.local/share/pearplay-terminal')
    parser.add_argument('--config-parent', type=Path, default=Path.home()/'Library/Application Support')
    args=parser.parse_args(argv)
    if args.action=='install':
        print('PearPlay is Linux only. Mac support is coming soon.', file=sys.stderr)
        return 2
    if sys.platform != 'darwin' or os.getuid()==0:
        print('Run this in your normal Mac account, without sudo.', file=sys.stderr)
        return 2
    try:
        config=json.loads((ROOT/'terminal-build.json').read_text())
        result=configure(config,ROOT,args.data_home,args.config_parent,args.uv,args.action)
    except PermissionError as error:
        print(f'Setup stopped: filesystem permission denied (errno={error.errno}). '
              'If macOS blocked access to Chrome data, review Terminal’s App Data permission in '
              'System Settings → Privacy & Security. Do not use sudo or delete registrations '
              'to resolve a permission denial.', file=sys.stderr)
        return 1
    except (OSError, ValueError, subprocess.CalledProcessError):
        print('Setup stopped. Existing or changed files were preserved. If another helper is connected, use its original uninstaller first. Check the runtime/download error above before retrying.', file=sys.stderr)
        return 1
    print(json.dumps(result))
    if args.action=='install':
        print('Fully quit and reopen Chrome, then open PearPlay → Helper setup → Check connection. Allow Local Network access if macOS asks. No discovery or playback was performed.')
    else:
        print('Chrome disconnected. Saved pairing and the downloaded runtime are kept.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
