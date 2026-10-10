#!/usr/bin/env python3
"""Guest-only regression evidence and stable minimal read-only build inputs."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

assert sys.platform=='linux' and platform.machine()=='x86_64'
source=Path('/src'); work=Path('/work')
evidence=Path(os.environ.get('PEARPLAY_VM_EVIDENCE','/work/evidence'))
evidence.mkdir(parents=True,exist_ok=True)
tmp=work/'tmp'; tmp.mkdir(exist_ok=True)
os.environ.update(PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(tmp),PATH='/work/node/bin:'+os.environ['PATH'])
inputs=[*sorted(source.glob('helper/*.py')),source/'scripts/build_helper.py',source/'LICENSE',
        source/'spikes/001-airplay/pearplay.py',source/'spikes/002-command/command.py',
        source/'spikes/002-command/LICENSE.md',source/'extension/manifest.json',
        source/'extension/releases.json',source/'extension/icons/icon128.png']

def hashes(paths): return {str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

outcomes=[]

def recorded(argv,name):
    started=time.monotonic()
    with (evidence/(name+'.log')).open('w') as log:
        result=subprocess.run(argv,cwd=source,stdout=log,stderr=subprocess.STDOUT)
    item={'argv':argv,'exit':result.returncode,'seconds':round(time.monotonic()-started,2)}
    (evidence/(name+'.json')).write_text(json.dumps(item,indent=2)+'\n')
    outcomes.append(result.returncode)
    print(name,json.dumps(item),flush=True)
    return result.returncode

before=hashes(inputs)
recorded(['/work/venv/bin/python','-m','pytest','-q','-p','no:cacheprovider','--junitxml='+str(evidence/'pytest-final.xml'),*[str(p.relative_to(source)) for p in sorted((source/'tests').glob('test_*.py')) if p.name!='test_debian_postinst.py']],'pytest-final')
# Ubuntu denied the unprivileged bwrap network namespace. Do not rerun denied hooks
# or count rejection cases as passing when bwrap itself cannot enter the fixture.
recorded(['/work/venv/bin/python','-m','pytest','-q','-p','no:cacheprovider','tests/test_debian_postinst.py','-k','control'],'debian-control')
recorded(['/work/node/bin/node','--test',*[str(p.relative_to(source)) for p in sorted((source/'tests/extension').glob('*.test.mjs'))]],'node-extension')
recorded(['/work/node/bin/node','--test','tests/brand.test.mjs'],'node-brand')
after=hashes(inputs)
(evidence/'regression-input-hashes.json').write_text(json.dumps({'before':before,'after':after,'unchanged':before==after},indent=2)+'\n')
if os.environ.get('PEARPLAY_VM_TEST_ONLY')=='1': sys.exit(1 if any(outcomes) else 0)
# Snapshot only build inputs, no working checkout. Require stable bytes throughout.
for attempt in range(5):
    before=hashes(inputs); time.sleep(2)
    if before!=hashes(inputs): continue
    snapshot=work/f'input-snapshot-{time.time_ns()}-{attempt}'
    snapshot.mkdir(exist_ok=False)
    for p in inputs:
        dst=snapshot/p.relative_to(source);dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_bytes(p.read_bytes());dst.chmod(0o444)
    copied={str(p.relative_to(snapshot)):hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.rglob('*') if p.is_file()}
    if copied!=before or before!=hashes(inputs):
        shutil.rmtree(snapshot);continue
    for p in sorted(snapshot.rglob('*'),reverse=True):
        if p.is_dir():p.chmod(0o555)
    snapshot.chmod(0o555)
    manifest={'source':str(source),'snapshot':str(snapshot),'sha256':copied,'stable':True,'read_only_modes':True,
              'kind':'minimal packaging inputs only; not a second working checkout'}
    (evidence/'build-input-hashes.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (work/'build-snapshot-path').write_text(str(snapshot)+'\n')
    print('Stable build snapshot',snapshot,flush=True)
    break
else: raise SystemExit('Build source was not stable; no build attempted')
sys.exit(1 if any(outcomes) else 0)
