#!/usr/bin/env python3
"""Owned PearPlay Ubuntu amd64 TCG VM; loopback-only NAT, immutable base, RO source.
Guest is disposable and has passwordless sudo, not a hardened desktop template.
No source checkout is copied. Keys are dedicated; no SSH agent forwarding.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path('/Volumes/IronWolf/Projects/PearPlay')
CACHE = Path('/Volumes/IronWolf/Cache/Hermes/PearPlay/linux-vm')
PRIVATE = Path.home()/'.local/state/pearplay-linux-vm'
SSH_PORT, VNC_DISPLAY, SEED_PORT = 22337, 37, 18337
QMP = CACHE/'qmp.sock'


def run(argv, **kwargs):
    return subprocess.run([str(a) for a in argv], check=True, **kwargs)


def require_mount():
    result = subprocess.check_output(['mount'], text=True)
    if ' on /Volumes/IronWolf (' not in result or not ROOT.is_dir():
        raise SystemExit('IronWolf must be mounted; refusing substitute directory')


def qmp(command):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(10)
        sock.connect(str(QMP))
        f = sock.makefile('rwb')
        json.loads(f.readline())
        def send(name):
            f.write((json.dumps({'execute': name})+'\n').encode()); f.flush()
            while True:
                reply = json.loads(f.readline())
                if 'return' in reply: return reply['return']
                if 'error' in reply: raise RuntimeError(reply['error'])
        send('qmp_capabilities')
        if send('query-name').get('name') != 'pearplay-linux-vm':
            raise RuntimeError('Unexpected QMP guest identity; refusing command')
        return send(command)


def ssh_argv():
    return ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
            '-o', 'ForwardAgent=no', '-o', 'StrictHostKeyChecking=yes',
            '-o', f'UserKnownHostsFile={PRIVATE}/known_hosts', '-o', 'ConnectTimeout=10',
            '-i', str(PRIVATE/'client'), '-p', str(SSH_PORT), 'vmtest@127.0.0.1']


def prepare():
    CACHE.mkdir(parents=True, exist_ok=True)
    PRIVATE.mkdir(parents=True, exist_ok=True); PRIVATE.chmod(0o700)
    seed = CACHE/'seed'; seed.mkdir(exist_ok=True); seed.chmod(0o700)
    base = CACHE/'images/noble-server-cloudimg-amd64.img'
    expected = next(line.split()[0] for line in (base.parent/'SHA256SUMS').read_text().splitlines()
                    if line.split()[-1].lstrip('*') == base.name)
    digest = hashlib.sha256()
    with base.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): digest.update(block)
    if digest.hexdigest() != expected: raise SystemExit('Ubuntu image checksum mismatch')
    base.chmod(0o444)
    for key in (PRIVATE/'client', seed/'guest_host'):
        if not key.exists():
            run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'pearplay-disposable-vm', '-f', key])
        key.chmod(0o600)
    hostpub = (seed/'guest_host.pub').read_text().split()
    (PRIVATE/'known_hosts').write_text(f'[127.0.0.1]:{SSH_PORT} {hostpub[0]} {hostpub[1]}\n')
    (PRIVATE/'known_hosts').chmod(0o600)
    data = {'users': [{'name': 'vmtest', 'shell': '/bin/bash', 'sudo': 'ALL=(ALL) NOPASSWD:ALL',
                       'lock_passwd': True, 'ssh_authorized_keys': [(PRIVATE/'client.pub').read_text().strip()]}],
            'ssh_pwauth': False, 'disable_root': True,
            'ssh_keys': {'ed25519_private': (seed/'guest_host').read_text(),
                         'ed25519_public': (seed/'guest_host.pub').read_text().strip()},
            'runcmd': [['mkdir', '-p', '/src', '/work'], ['chown', 'vmtest:vmtest', '/work'],
                      ['sh', '-c', 'echo "pearplay /src 9p trans=virtio,version=9p2000.L,ro,nofail 0 0" >> /etc/fstab'],
                      ['mount', '/src']]}
    # JSON is YAML-compatible; first-line header identifies cloud-config.
    (seed/'user-data').write_text('#cloud-config\n'+json.dumps(data, indent=2)+'\n')
    (seed/'meta-data').write_text('instance-id: pearplay-linux-amd64-20261009\nlocal-hostname: pearplay-vm\n')
    (seed/'vendor-data').write_text('#cloud-config\n{}\n')
    overlay = CACHE/'overlay.qcow2'
    if not overlay.exists():
        run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', base, overlay, '36G'])
    (CACHE/'image-verification.json').write_text(json.dumps({'url': 'https://cloud-images.ubuntu.com/noble/current/'+base.name,
               'sha256': expected, 'verification': 'official HTTPS SHA256SUMS; no signature verification',
               'base_readonly': True}, indent=2)+'\n')


def stop_seed():
    pidfile = CACHE/'seed.pid'
    if pidfile.exists():
        pid = int(pidfile.read_text())
        command = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True).stdout
        if f'http.server {SEED_PORT}' in command and str(CACHE/'seed') in command:
            os.kill(pid, 15)
        pidfile.unlink()


def start():
    try:
        print(json.dumps(qmp('query-status'))); return
    except (OSError, ValueError): pass
    prepare()
    for port in (SSH_PORT, 5900+VNC_DISPLAY, SEED_PORT):
        with socket.socket() as sock: sock.bind(('127.0.0.1', port))
    seed_log = (CACHE/'seed.log').open('ab')
    seed = subprocess.Popen([sys.executable, '-m', 'http.server', str(SEED_PORT), '--bind', '127.0.0.1',
                             '--directory', str(CACHE/'seed')], stdin=subprocess.DEVNULL,
                            stdout=seed_log, stderr=seed_log, start_new_session=True)
    (CACHE/'seed.pid').write_text(str(seed.pid))
    argv = [shutil.which('qemu-system-x86_64'), '-name', 'pearplay-linux-vm', '-machine', 'q35',
            '-accel', 'tcg,thread=multi', '-cpu', 'max', '-smp', '4', '-m', '6144',
            '-drive', f'file={CACHE}/overlay.qcow2,format=qcow2,if=virtio',
            '-netdev', f'user,id=net0,hostfwd=tcp:127.0.0.1:{SSH_PORT}-:22',
            '-device', 'virtio-net-pci,netdev=net0',
            '-fsdev', f'local,id=source,path={ROOT},security_model=none,readonly=on',
            '-device', 'virtio-9p-pci,fsdev=source,mount_tag=pearplay',
            '-smbios', f'type=1,serial=ds=nocloud;s=http://10.0.2.2:{SEED_PORT}/',
            '-qmp', f'unix:{QMP},server=on,wait=off', '-vnc', f'127.0.0.1:{VNC_DISPLAY}',
            '-display', 'none', '-serial', f'file:{CACHE}/serial.log', '-daemonize', '-pidfile', str(CACHE/'qemu.pid')]
    (CACHE/'qemu-argv.json').write_text(json.dumps(argv, indent=2)+'\n')
    try: run(argv)
    except BaseException: stop_seed(); raise
    print(json.dumps(qmp('query-status')))


def ready():
    deadline = time.monotonic()+900
    while time.monotonic() < deadline:
        result = subprocess.run(ssh_argv()+['cloud-init status --wait; findmnt -no SOURCE,OPTIONS /src; uname -m'],
                                capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print(result.stdout); stop_seed(); return
        time.sleep(5)
    raise SystemExit('Guest boot readiness timed out; see serial.log')


def shutdown():
    try:
        print(json.dumps(qmp('query-status')))
    except OSError:
        stop_seed(); print('VM already stopped'); return
    result = subprocess.run(ssh_argv()+['sudo poweroff'], timeout=30)
    if result.returncode not in (0, 255): raise SystemExit('Guest shutdown command failed')
    for _ in range(120):
        try: qmp('query-status')
        except OSError:
            stop_seed(); print('Owned VM shut down; QMP unavailable'); return
        time.sleep(1)
    raise SystemExit('Graceful shutdown timed out; VM left running, no force kill')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'start', 'ready', 'ssh', 'shutdown', 'status'])
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(); require_mount()
    if args.action == 'ssh': return subprocess.call(ssh_argv()+args.command)
    if args.action == 'status':
        try: print(json.dumps(qmp('query-status')))
        except OSError: print('VM stopped')
        return 0
    globals()[args.action](); return 0

if __name__ == '__main__': sys.exit(main())
