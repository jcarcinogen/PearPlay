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


def package_arch(build, root):
    # Freeze on Ubuntu's older libc; package those exact bytes with native
    # makepkg in a pinned disposable Arch container, without a network at build.
    sys.path.insert(0, str(REPO))
    from scripts.build_helper import linux_dependencies
    config = json.loads((build / 'build-report.json').read_text())
    work = build / 'arch-ci'
    work.mkdir()
    recipe = (f"pkgname=pearplay-helper\npkgver={config['version']}\npkgrel=1\n"
              "pkgdesc='PearPlay helper and browser setup'\narch=('x86_64')\n"
              "url='https://github.com/jcarcinogen/PearPlay'\nlicense=('MIT')\n"
              f"depends=({linux_dependencies('arch', platform.libc_ver()[1])})\n"
              "options=('!strip' '!debug')\npackage() { cp -a /stage/. \"$pkgdir/\"; }\n")
    (work / 'PKGBUILD').write_text(recipe)
    image = 'archlinux@sha256:99e98cdd1c714023ca481b4959c9214415323129530bfc101da2ff50dd9a6106'
    run(['docker', 'pull', image], root / 'arch-image.log')
    run(['docker', 'run', '--rm', '--network', 'none', '-v', str(build / 'stage') + ':/stage:ro',
         '-v', str(work) + ':/work', image, 'bash', '-ec',
         'useradd --uid "$1" --no-create-home builder; cd /work; exec runuser -u builder -- makepkg --nodeps --noconfirm',
         'pearplay', str(os.getuid())], root / 'arch-package.log')
    packages = list(work.glob('*.pkg.tar.zst'))
    if len(packages) != 1:
        raise ValueError('expected_one_arch_package')
    target = build / f"pearplay-helper-{config['version']}-linux-x86_64.pkg.tar.zst"
    shutil.copy2(packages[0], target)
    (build / 'arch-report.json').write_text(json.dumps(dict(file=target.name, sha256=digest(target),
        image=image, scope='Arch packaging of the same Ubuntu-frozen stage; not a system install'), indent=2) + '\n')


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
        entries = list(report['artifacts'])
        if sys.platform == 'linux' and (build / 'arch-report.json').is_file():
            entries.append(json.loads((build / 'arch-report.json').read_text()))
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
    for name in ('arch-report.json', 'build-report.json', 'source-hashes.json', 'smoke.json', 'environment-inputs.json', 'native-tests.txt'):
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
    if sys.platform == 'linux':
        package_arch(build, root)
    collect(build, root / 'artifacts', root)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
