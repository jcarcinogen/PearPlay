#!/usr/bin/env python3
"""Disposable guest-only package validation. No real credentials or receivers."""
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import stat
import struct
import subprocess
import sys
import tarfile

assert sys.platform=='linux' and platform.machine()=='x86_64'
evidence=Path(sys.argv[2]) if len(sys.argv)>2 else Path('/work/evidence')
package=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/work/build-030/pearplay-helper-0.3.0-linux-x86_64.deb')
evidence.mkdir(parents=True,exist_ok=True)
binary=Path('/opt/pearplay/PearPlayHelper/PearPlayHelper'); parent=Path('/work/lifecycle-profile')
parent.mkdir(exist_ok=True)
results=[]

def run(argv,name):
    result=subprocess.run(argv,capture_output=True,text=True)
    (evidence/(name+'.log')).write_text(result.stdout+result.stderr)
    item={'phase':name,'argv':[str(x) for x in argv],'exit':result.returncode}
    results.append(item);print(json.dumps(item),flush=True)
    if result.returncode: raise RuntimeError(f'{name} failed, see saved log')
    return result.stdout

def sha(path): return hashlib.file_digest(path.open('rb'),'sha256').hexdigest()

def archive_members():
    stream=subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(package)])
    with tarfile.open(fileobj=io.BytesIO(stream)) as tar:
        return list(tar.getmembers())

members=archive_members()

def inspect_payload(phase):
    mismatches=[];inventory=[]
    for member in members:
        name=member.name.removeprefix('./')
        if not name: continue
        path=Path('/')/name
        if not path.exists() and not path.is_symlink():
            mismatches.append({'path':name,'error':'missing'});continue
        info=path.lstat();mode=stat.S_IMODE(info.st_mode)
        item={'path':name,'archive_mode':oct(member.mode),'installed_mode':oct(mode),'uid':info.st_uid,'gid':info.st_gid}
        if member.isdir(): item['type']='directory'
        elif member.issym(): item.update(type='symlink',target=os.readlink(path));assert os.readlink(path)==member.linkname
        elif member.isfile():item.update(type='file',sha256=sha(path))
        else: item['type']='other'
        if member.issym(): valid=stat.S_ISLNK(info.st_mode)
        else: valid=mode==member.mode
        if not valid or (info.st_uid,info.st_gid)!=(0,0):mismatches.append(item)
        inventory.append(item)
    # Compare file bytes separately against the archive stream; no extraction or mode changes.
    with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(package)]))) as tar:
        for member in tar:
            if member.isfile():
                expected=hashlib.sha256(tar.extractfile(member).read()).hexdigest()
                if sha(Path('/')/member.name.removeprefix('./'))!=expected:mismatches.append({'path':member.name,'error':'hash'})
    (evidence/(phase+'-inventory.json')).write_text(json.dumps({'mismatches':mismatches,'entries':inventory},indent=2)+'\n')
    assert not mismatches,mismatches
    run([str(binary),'self-test'],phase+'-normal-user-self-test')

inspect_payload('fresh')
# All bundled ELF objects, not just the launcher.
elf=[];maxversion=(0,0)
for p in binary.parent.rglob('*'):
    if p.is_file() and not p.is_symlink():
        with p.open('rb') as stream: magic=stream.read(4)
        if magic!=b'\x7fELF': continue
        out=subprocess.check_output(['readelf','--version-info',str(p)],text=True)
        versions=[tuple(map(int,v.split('.'))) for v in re.findall(r'GLIBC_(\d+\.\d+(?:\.\d+)?)',out)]
        requirement=max(versions,default=(0,0));maxversion=max(maxversion,requirement)
        elf.append({'path':str(p.relative_to(binary.parent)),'max_glibc':'.'.join(map(str,requirement))})
(evidence/'elf-glibc.json').write_text(json.dumps({'maximum':'.'.join(map(str,maxversion)),'advertised_baseline':'2.39','objects':elf},indent=2)+'\n')
assert maxversion <= (2,39)
licenses=binary.parent/'THIRD_PARTY_LICENSES'
assert (binary.parent/'LICENSE').is_file() and (licenses/'airplay-adapter.md').is_file()
versions=json.loads((binary.parent/'dependency-versions.json').read_text())
assert versions['pyatv']=='0.18.0' and versions['pyinstaller']=='6.21.0'
(evidence/'package-licenses.json').write_text(json.dumps({'project_license_sha256':sha(binary.parent/'LICENSE'),
    'license_files':[str(p.relative_to(binary.parent)) for p in licenses.rglob('*') if p.is_file()],
    'dependency_versions':versions},indent=2)+'\n')
# Fresh package tested above; now a real cross-version baseline.
run(['sudo','apt-get','remove','-y','pearplay-helper'],'remove-before-legacy')
assert not binary.exists()
legacy=Path('/work/pearplay-helper-0.2.5-linux-x86_64.deb')
if not legacy.exists():
    run(['curl','-fsSL','--retry','3','https://github.com/jcarcinogen/PearPlay/releases/download/v0.2.5/'+legacy.name,'-o',str(legacy)],'legacy-download')
expected='9d53f65b38724750f8f428ead0f7fe976cc4ec0253fea2c73da0459ef90b0b5f'
assert sha(legacy)==expected
(evidence/'legacy-download.json').write_text(json.dumps({'url':'https://github.com/jcarcinogen/PearPlay/releases/download/v0.2.5/'+legacy.name,'sha256':expected,'verified_against':'canonical recorded public v0.2.5 release hash'},indent=2)+'\n')
run(['sudo','env','DEBIAN_FRONTEND=noninteractive','apt-get','install','-y',str(legacy)],'legacy-install')
run([str(binary),'self-test'],'legacy-normal-user-self-test')
run([str(binary),'connect','--browsers','chrome','--config-parent',str(parent)],'legacy-registration')
host=parent/'google-chrome/NativeMessagingHosts/com.pearplay.helper.json'
manifest=host.read_bytes();assert json.loads(manifest)['allowed_origins']==['chrome-extension://eoadahoncjfpnennmkjifohclbafjkol/']
sentinel=Path.home()/'.local/state/pearplay/lifecycle-sentinel.txt'
sentinel.parent.mkdir(parents=True,exist_ok=True);sentinel.write_text('synthetic lifecycle sentinel, NOT pairing credentials\n');sentinel.chmod(0o600)
sentinel_hash=sha(sentinel)
legacy_modes=[{'path':str(p),'mode':oct(stat.S_IMODE(p.stat().st_mode))} for p in [binary.parent.parent,binary.parent,binary.parent/'_internal']]
(evidence/'legacy-baseline-modes.json').write_text(json.dumps(legacy_modes,indent=2)+'\n')
run(['sudo','env','DEBIAN_FRONTEND=noninteractive','apt-get','install','-y',str(package)],'upgrade-025-to-030')
assert host.read_bytes()==manifest and sha(sentinel)==sentinel_hash
inspect_payload('upgrade')
run(['sudo','env','DEBIAN_FRONTEND=noninteractive','apt-get','install','--reinstall','-y',str(package)],'reinstall-030')
assert host.read_bytes()==manifest and sha(sentinel)==sentinel_hash
inspect_payload('reinstall')
run(['sudo','apt-get','remove','-y','pearplay-helper'],'package-remove-030')
assert not binary.exists() and host.read_bytes()==manifest and sha(sentinel)==sentinel_hash
run(['sudo','env','DEBIAN_FRONTEND=noninteractive','apt-get','install','-y',str(package)],'package-reinstall-after-remove')
assert host.read_bytes()==manifest and sha(sentinel)==sentinel_hash
inspect_payload('reinstalled-after-remove')
# Real frozen native stdio frame through preserved legacy launcher.
launcher=json.loads(manifest)['path']
frames=b''.join(struct.pack('<I',len(payload))+payload for payload in
    [json.dumps({'v':1,'id':op,'op':op,'args':{}}).encode() for op in ['hello','status']])
reply=subprocess.run([launcher,'chrome-extension://eoadahoncjfpnennmkjifohclbafjkol/'],input=frames,capture_output=True,timeout=30)
assert reply.returncode==0,reply.stderr.decode()
stream=io.BytesIO(reply.stdout);messages=[]
while True:
    size=stream.read(4)
    if not size:break
    assert len(size)==4
    messages.append(json.loads(stream.read(struct.unpack('<I',size)[0])))
assert len(messages)==2 and all(m['ok'] and m['helperVersion']=='0.3.0' for m in messages)
(evidence/'preserved-launcher-native.json').write_text(json.dumps(messages,indent=2)+'\n')
run([str(binary),'remove','--browsers','chrome','--config-parent',str(parent)],'remove-preserved-registration')
assert not host.exists() and sha(sentinel)==sentinel_hash
report={'package_sha256':sha(package),'version':'0.3.0','arch':'amd64','glibc_baseline':'2.39',
        'maximum_bundled_glibc':'.'.join(map(str,maxversion)), 'phases':results,
        'registration_preserved_on_upgrade_reinstall_and_package_remove':True,
        'synthetic_state_preserved':True,'actual_pairing_tested':False,'network_tested':False}
(evidence/'lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
