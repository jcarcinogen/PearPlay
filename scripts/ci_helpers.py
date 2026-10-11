"""Hosted helper build gates; never publishes or changes owner installations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
EXTENSION_ID = 'eoadahoncjfpnennmkjifohclbafjkol'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, log):
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run(argv, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, timeout=1800)
    print(log.read_text(encoding='utf-8', errors='replace'), flush=True)
    result.check_returncode()


def collect(build, output, root):
    report = json.loads((build / 'build-report.json').read_text())
    if report['extension_id'] != EXTENSION_ID or report['platform'] != sys.platform:
        raise ValueError('wrong_build_identity_or_platform')
    sources = json.loads((build / 'source-hashes.json').read_text())
    for name, expected in sources.items():
        if digest(REPO / name) != expected:
            raise ValueError('source_changed: ' + name)
    if sys.platform == 'win32':
        if not all(report.get(k) is True for k in ('unsigned', 'windows_fixture_tests', 'installed_frozen_payload_tested')):
            raise ValueError('windows_acceptance_missing')
        entries = [dict(file=report['installer'], sha256=report['sha256']), report['maintenance']]
    else:
        entries = report['artifacts']
        if not entries:
            raise ValueError('missing_packages')
        suffixes = {Path(e['file']).suffix for e in entries}
        if sys.platform == 'darwin':
            if report['arch'] != 'arm64' or report['development'] is not True or report['notarized'] is not False or '.pkg' not in suffixes:
                raise ValueError('expected_unsigned_arm64_mac')
        elif '.deb' not in suffixes or not any(e['file'].endswith('.pkg.tar.zst') for e in entries):
            raise ValueError('expected_debian_and_arch_packages')
    output.mkdir(exist_ok=False)
    for entry in entries:
        name = entry['file']
        if Path(name).name != name or digest(build / name) != entry['sha256']:
            raise ValueError('invalid_artifact: ' + name)
        shutil.copy2(build / name, output / name)
    for name in ('build-report.json', 'source-hashes.json', 'smoke.json', 'environment-inputs.json', 'native-tests.txt'):
        if (build / name).is_file():
            shutil.copy2(build / name, output / name)
    for path in root.glob('*.log'):
        shutil.copy2(path, output / path.name)
    shutil.copy2(root / 'dependencies.txt', output / 'dependencies.txt')
    provenance = {key: os.environ[key] for key in ('GITHUB_SHA', 'GITHUB_REF', 'GITHUB_REPOSITORY', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT')}
    provenance.update(machine=platform.machine(), python=sys.version, system=platform.platform(),
                      acceptance='Engineering build/native tests only; no owner GUI, Chrome, TV, or security-policy acceptance.')
    (output / 'ci-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    (output / 'SHA256SUMS').write_text(''.join(digest(p) + '  ' + p.name + '\n' for p in sorted(output.iterdir()) if p.is_file()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    root = parser.parse_args().root.resolve()
    if root.is_relative_to(REPO):
        raise ValueError('build_outside_checkout_required')
    build = root / 'build'
    # Security tests deliberately reject symlinked ancestors (including macOS
    # /var -> /private/var). Use a resolved, job-owned temporary directory.
    temporary = root / 'tmp'
    temporary.mkdir(exist_ok=False)
    for key in ('TMPDIR', 'TMP', 'TEMP'):
        os.environ[key] = str(temporary)
    # Windows builder already runs all Windows source/fixture tests against the
    # actual frozen payload. POSIX suite includes platform skips explicitly.
    if sys.platform != 'win32':
        tests = sorted(str(p) for p in (REPO / 'tests').glob('test_*.py') if not p.name.startswith('._'))
        run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *tests,
             '--basetemp=' + str(root / 'pytest')], root / 'tests.log')
    argv = [sys.executable, '-B', str(REPO / 'scripts' / ('build_windows_helper.py' if sys.platform == 'win32' else 'build_helper.py')),
            '--output', str(build)]
    if sys.platform != 'win32':
        argv += ['--extension-id', EXTENSION_ID]
        if sys.platform == 'darwin':
            argv += ['--development']
    run(argv, root / 'build-driver.log')
    collect(build, root / 'artifacts', root)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
