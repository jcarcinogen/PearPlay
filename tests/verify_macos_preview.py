"""Exercise an expanded unsigned Mac preview, without installation or TV access."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess


def run(command):
    result=subprocess.run(command,capture_output=True,text=True,timeout=60)
    return {'command':command,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}


def entries(root):
    result={}
    for path in sorted(root.rglob('*')):
        info=path.lstat();row={'mode':oct(stat.S_IMODE(info.st_mode))}
        if path.is_symlink():row.update(type='symlink',target=str(path.readlink()))
        elif path.is_dir():row.update(type='directory')
        elif path.is_file():row.update(type='file',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=info.st_size)
        else:raise AssertionError('Unexpected package payload type')
        result[path.relative_to(root).as_posix()]=row
    return result


def verify(build,kit):
    build=build.resolve();kit=kit.resolve()
    metadata=json.loads((build/'build-report.json').read_text())
    assert metadata['version']=='0.3.0' and metadata['development'] is True
    assert metadata['extension_id']=='eoadahoncjfpnennmkjifohclbafjkol'
    assert metadata['notarized'] is False
    package=build/metadata['artifacts'][0]['file']
    assert hashlib.sha256(package.read_bytes()).hexdigest()==metadata['artifacts'][0]['sha256']
    expanded=build/'expanded'
    if not expanded.exists():
        extraction=run(['pkgutil','--expand-full',str(package),str(expanded)])
        assert extraction['exit_code']==0,extraction
    payload=expanded/'Payload';assert payload.is_dir()
    staged=entries(build/'stage');packaged=entries(payload)
    assert staged==packaged,'Package payload byte/mode/link inventory differs from stage'
    assert not (expanded/'Scripts').exists(),'Unexpected installer scripts'
    app=payload/'Applications/PearPlay Setup.app';binary=app/'Contents/MacOS/PearPlayHelper'
    plist=plistlib.loads((app/'Contents/Info.plist').read_bytes())
    assert plist['CFBundleIdentifier']=='com.pearplay.helper'
    assert plist['CFBundleVersion']=='0.3.0'
    assert plist['NSLocalNetworkUsageDescription']
    assert plist['NSBonjourServices']==['_airplay._tcp']
    tests={
      'self_test':run([str(binary),'self-test']),
      'codesign_strict_deep':run(['codesign','--verify','--deep','--strict',str(app)]),
      'signature_identity':run(['codesign','-d','--verbose=4',str(app)]),
      'gatekeeper_app':run(['spctl','--assess','--type','execute','--verbose=4',str(app)]),
      'gatekeeper_pkg':run(['spctl','--assess','--type','install','--verbose=4',str(package)]),
      'pkg_signature':run(['pkgutil','--check-signature',str(package)]),
      'binary_arch':run(['lipo','-archs',str(binary)]),
      'binary_uuid':run(['dwarfdump','--uuid',str(binary)]),
    }
    assert tests['self_test']['exit_code']==0
    assert json.loads(tests['self_test']['stdout'])=={'ok':True,'version':'0.3.0','dependencies':'loaded','network':'not used'}
    assert tests['codesign_strict_deep']['exit_code']==0
    assert 'Signature=adhoc' in tests['signature_identity']['stderr']
    assert 'Identifier=com.pearplay.helper' in tests['signature_identity']['stderr']
    assert 'TeamIdentifier=not set' in tests['signature_identity']['stderr']
    assert tests['gatekeeper_app']['exit_code']!=0 and 'rejected' in tests['gatekeeper_app']['stderr']
    assert tests['gatekeeper_pkg']['exit_code']!=0 and 'rejected' in tests['gatekeeper_pkg']['stderr']
    assert 'no signature' in tests['pkg_signature']['stdout']
    assert tests['binary_arch']['stdout'].strip()=='arm64'
    resources=app/'Contents/Resources'
    licenses=resources/'THIRD_PARTY_LICENSES'
    inventory=json.loads((licenses/'inventory.json').read_text())
    assert (resources/'LICENSE').is_file() and (licenses/'Python-LICENSE.txt').is_file()
    for row in inventory['notices']:
        assert hashlib.sha256((licenses/row['file']).read_bytes()).hexdigest()==row['sha256']
    for name in inventory['distributions']:
        assert any(p.is_file() for p in (licenses/name).rglob('*')),f'Missing notice: {name}'
    assert inventory['distributions']['pyatv']=='0.18.0'
    assert inventory['distributions']['pyinstaller']=='6.21.0'
    assert len(inventory['notices'])==sum(1 for p in licenses.rglob('*') if p.is_file())-1
    kit.mkdir(parents=True,exist_ok=True)
    destination=kit/package.name
    if destination.exists():
        assert hashlib.sha256(destination.read_bytes()).hexdigest()==metadata['artifacts'][0]['sha256'],'Do not overwrite different evidence'
    else:shutil.copy2(package,destination)
    assert hashlib.sha256(destination.read_bytes()).hexdigest()==metadata['artifacts'][0]['sha256']
    for filename in ('build-report.json','source-hashes.json','smoke.json'):
        shutil.copy2(build/filename,kit/filename)
    shutil.copy2(licenses/'inventory.json',kit/'license-inventory.json')
    report=dict(package=str(destination),sha256=metadata['artifacts'][0]['sha256'],package_bytes=destination.stat().st_size,
                payload_entries=len(packaged),payload_identity='All entries match stage bytes/modes/symlink targets',
                notice_files=len(inventory['notices']),environment_distributions=len(inventory['distributions']),
                signature='ad-hoc app; unsigned pkg',gatekeeper='Expected rejection observed for app and package',
                installation_performed=False,network_discovery_performed=False,pairing_or_playback_performed=False,
                tests=tests)
    (kit/'runtime-package-report.json').write_text(json.dumps(report,indent=2)+'\n')
    (kit/'payload-inventory.json').write_text(json.dumps(packaged,indent=2)+'\n')
    (kit/'SHA256SUMS').write_text(metadata['artifacts'][0]['sha256']+'  '+package.name+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='tests'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build',type=Path);parser.add_argument('kit',type=Path)
    args=parser.parse_args();verify(args.build,args.kit)
