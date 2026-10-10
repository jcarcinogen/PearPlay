#!/usr/bin/env python3
"""Disposable guest-only dependency setup. Never run on the macOS host."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import urllib.request

assert sys.platform == 'linux' and platform.machine() == 'x86_64'
assert Path('/src/helper/app.py').is_file() and Path('/work').is_dir()
work=Path('/work'); evidence=work/'evidence'; evidence.mkdir(exist_ok=True)

def run(argv, name):
    with (evidence/(name+'.log')).open('w') as log:
        result=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT)
    print(name, result.returncode, flush=True)
    if result.returncode: raise SystemExit(result.returncode)

def download(url, path):
    urllib.request.urlretrieve(url, path)

nodebase='https://nodejs.org/dist/latest-v24.x/'
sums=work/'node-SHASUMS256.txt'; download(nodebase+'SHASUMS256.txt',sums)
line=next(line for line in sums.read_text().splitlines() if line.endswith('-linux-x64.tar.xz'))
expected,name=line.split(); archive=work/name; download(nodebase+name,archive)
actual=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest(); assert actual==expected
with tarfile.open(archive) as tar: tar.extractall(work,filter='data')
node=work/name.removesuffix('.tar.xz')
if not (work/'node').exists(): (work/'node').symlink_to(node.name)
(evidence/'node-download.json').write_text(json.dumps({'url':nodebase+name,'sha256':actual,'verification':'official HTTPS SHASUMS256.txt; no signature verification'},indent=2))
run(['python3','-m','venv','/work/venv'],'venv')
run(['/work/venv/bin/python','-m','pip','install','pyatv==0.18.0','pyinstaller==6.21.0','pytest'],'pip-install')
run(['/work/venv/bin/python','-m','pip','freeze'],'pip-freeze')
key=work/'google-linux-signing-key.pub'; download('https://dl.google.com/linux/linux_signing_key.pub',key)
run(['gpg','--show-keys','--with-fingerprint',str(key)],'google-key-fingerprints')
run(['gpg','--batch','--yes','--dearmor','--output','/work/google-chrome.gpg',str(key)],'google-key-dearmor')
run(['sudo','install','-m','0644','/work/google-chrome.gpg','/usr/share/keyrings/pearplay-vm-google-chrome.gpg'],'google-key-install')
source=work/'google-chrome.list'
source.write_text('deb [arch=amd64 signed-by=/usr/share/keyrings/pearplay-vm-google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main\n')
run(['sudo','install','-m','0644',str(source),'/etc/apt/sources.list.d/pearplay-vm-google-chrome.list'],'google-source-install')
run(['sudo','apt-get','update'],'google-apt-update')
run(['sudo','env','DEBIAN_FRONTEND=noninteractive','apt-get','install','-y','google-chrome-stable'],'google-apt-install')
run(['sh','-c','uname -a; cat /etc/os-release; ldd --version; python3 --version; /work/node/bin/node --version; google-chrome --version; dpkg-query -W; findmnt /src; sysctl kernel.apparmor_restrict_unprivileged_userns; sudo aa-status'],'guest-environment')
