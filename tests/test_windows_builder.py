"""Packaging repairs: portable reproductions plus actual bounded PowerShell tests.

Synthetic freezes below exercise builder rejection, not native artifact evidence.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def builder():
    spec = importlib.util.spec_from_file_location('windows_builder_tests', ROOT/'scripts/build_windows_helper.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def distribution(wheel, name='fixture'):
    paths = ['pkg.dist-info/licenses/LICENSE', 'pkg.dist-info/licenses/vendor/LICENSE',
             'pkg/NOTICE', 'COPYING', 'pkg/licenses/__init__.py', 'pkg/licenses.py']
    for n, relative in enumerate(paths):
        path = wheel/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('notice '+str(n))
    return SimpleNamespace(metadata={'Name': name}, version='1.0',
                           files=[Path(p) for p in paths], locate_file=lambda p: wheel/p)


def test_relative_notices_standalone_and_runtime(tmp_path):
    build = builder()
    dist = distribution(tmp_path/'wheel')
    python = tmp_path/'LICENSE.txt'
    python.write_text('Python runtime notice')
    payload = tmp_path/'payload'
    payload.mkdir()
    inventory = build.collect_licenses(payload, [dist], python)
    notices = payload/'THIRD_PARTY_LICENSES'
    for n, relative in enumerate(['pkg.dist-info/licenses/LICENSE',
                                 'pkg.dist-info/licenses/vendor/LICENSE', 'pkg/NOTICE', 'COPYING']):
        assert (notices/'fixture'/relative).read_text() == 'notice '+str(n)
    assert not list(notices.rglob('*.py'))
    assert (notices/'Python-LICENSE.txt').read_text() == 'Python runtime notice'
    assert 'Build environment' in inventory['scope']
    for row in inventory['notices']:
        assert hashlib.sha256((notices/row['file']).read_bytes()).hexdigest() == row['sha256']


def test_distribution_destination_collision_fails_closed(tmp_path):
    build = builder()
    one = distribution(tmp_path/'one', 'a+b')
    two = distribution(tmp_path/'two', 'a_b')
    with pytest.raises(ValueError, match='notice_destination_collision'):
        build.collect_licenses(tmp_path, [one, two], tmp_path/'missing')


def test_missing_python_license_fails_closed(tmp_path):
    with pytest.raises(ValueError, match='missing_python_runtime_license'):
        builder().collect_licenses(tmp_path, [], tmp_path/'missing')


def test_source_snapshot_covers_runtime_setup_build_licenses_and_tests():
    snapshot = builder().build_source_snapshot()
    for relative in ['helper/app.py', 'helper/windows_setup.py', 'helper/native.py',
                     'scripts/build_windows_helper.py', 'scripts/build_windows_helper.ps1',
                     'scripts/build_helper.py', 'spikes/002-command/LICENSE.md', 'LICENSE',
                     'requirements.txt', 'tests/test_windows_native.py', 'tests/test_windows_builder.py',
                     'assets/store/icon-1024.png', 'assets/brand/pearplay.ico']:
        assert snapshot[relative] == hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()


@pytest.mark.parametrize('stage', ['helper', 'setup', 'tests'])
def test_build_rejects_source_changed_after_each_stage(tmp_path, monkeypatch, stage):
    build = builder()
    source = tmp_path/'source'
    for relative in build.build_source_snapshot():
        path = source/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT/relative).read_bytes())
    monkeypatch.setattr(build, 'ROOT', source)
    monkeypatch.setattr(build.sys, 'platform', 'win32')
    monkeypatch.setattr(build.platform, 'machine', lambda: 'AMD64')
    monkeypatch.setattr(build, 'inventory', lambda: {'packages': {'pyatv': '0.18.0', 'pyinstaller': '6.21.0'}})
    monkeypatch.setattr(build, 'environment_snapshot', lambda: {'fixture': 'unchanged'})
    def notices(payload):
        path = payload/'THIRD_PARTY_LICENSES'
        path.mkdir()
        (path/'fixture.txt').write_text('notice')
        (path/'inventory.json').write_text('{}')
        (payload/'dependency-versions.json').write_text('{}')
        return {'scope': 'fixture', 'notices': []}
    monkeypatch.setattr(build, 'collect_licenses', notices)
    monkeypatch.setattr(build, 'native_smoke', lambda _: {})
    monkeypatch.setattr(build, 'verify_executable_icon', lambda _: {'scope': 'synthetic freeze'})
    monkeypatch.setattr(build, 'verify_windowed', lambda _: None)
    monkeypatch.setattr(build, 'payload_files', lambda _: {})
    output = tmp_path/'output'
    calls = []
    def run(argv, **kwargs):
        if 'PyInstaller' in argv:
            name = argv[argv.index('--name')+1]
            current = 'helper' if name == 'PearPlayHelper' else 'setup'
            dest = output/'frozen'/('PearPlayHelper/PearPlayHelper.exe' if current == 'helper' else name+'.exe')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b'synthetic fixture executable')
        elif 'pytest' in argv:
            current = 'tests'
        else:
            current = 'smoke'
        calls.append(current)
        if current == stage:
            with (source/'helper/native.py').open('a') as stream:
                stream.write('\n# simulated concurrent source edit\n')
        if argv[-1] == 'verify-payload':
            stdout = json.dumps({'sha256': hashlib.sha256((output/'windows-payload.zip').read_bytes()).hexdigest(), 'version': build.VERSION})
        else:
            stdout = json.dumps({'ok': True, 'version': build.VERSION})
        return SimpleNamespace(returncode=0, stdout=stdout, stderr='')
    monkeypatch.setattr(build.subprocess, 'run', run)
    with pytest.raises(ValueError, match='source_changed_during_build'):
        build.build(output)
    assert not (output/'build-report.json').exists()
    manifest = json.loads((output/'source-hashes.json').read_text())
    assert manifest['helper/native.py'] != hashlib.sha256((source/'helper/native.py').read_bytes()).hexdigest()
    assert calls[-1] == stage


@pytest.mark.parametrize('name,onefile', [('PearPlayHelper', False), ('PearPlaySetup', True)])
def test_both_windows_executables_embed_pearplay_icon(tmp_path, name, onefile):
    build = builder()
    argv = build.freeze_command(tmp_path, ROOT/'helper/app.py', name, onefile=onefile)
    assert argv[argv.index('--icon') + 1] == str(ROOT/'assets/brand/pearplay.ico')
    assert '--console' in argv and '--windowed' not in argv  # preserve native stdio


def test_windows_icon_contains_all_shell_sizes():
    frames = builder().icon_frames((ROOT/'assets/brand/pearplay.ico').read_bytes())
    assert [row[0] or 256 for row, _ in frames] == [256, 128, 64, 48, 32, 24, 16]
    assert all(row[0] == row[1] and row[5] == 32 and pixels for row, pixels in frames)


@pytest.mark.parametrize('raw', [b'', b'not an icon', b'\x00\x00\x01\x00\x01\x00'])
def test_invalid_brand_icon_is_refused(raw):
    with pytest.raises(ValueError, match='invalid_brand_icon'):
        builder().icon_frames(raw)


def test_environment_drift_rejected(tmp_path, monkeypatch):
    build = builder()
    baseline = {'fixture': 'original'}
    monkeypatch.setattr(build, 'environment_snapshot', lambda: dict(baseline, fixture='changed'))
    with pytest.raises(ValueError, match='environment_changed_during_build'):
        build.reject_input_drift(build.build_source_snapshot(), baseline)


def test_environment_snapshot_hashes_runtime_distribution_and_notice(tmp_path, monkeypatch):
    build = builder()
    base = tmp_path/'python'
    base.mkdir()
    executable = base/'python.exe'
    executable.write_bytes(b'fixture interpreter')
    (base/'LICENSE.txt').write_bytes(b'fixture runtime notice')
    (base/'cache.pyc').write_bytes(b'excluded regenerable bytecode')
    dist = distribution(tmp_path/'wheel')
    monkeypatch.setattr(build.sys, 'executable', str(executable))
    monkeypatch.setattr(build.sys, 'base_prefix', str(base))
    monkeypatch.setattr(build.importlib.metadata, 'distributions', lambda: [dist])
    snapshot = build.environment_snapshot()
    assert snapshot[str(executable)] == hashlib.sha256(executable.read_bytes()).hexdigest()
    assert str(base/'LICENSE.txt') in snapshot
    assert str(tmp_path/'wheel'/'pkg/NOTICE') in snapshot
    assert not any(p.endswith('.pyc') for p in snapshot)


@pytest.mark.skipif(sys.platform != 'win32', reason='requires real PowerShell and local NTFS')
@pytest.mark.parametrize('case', ['equal', 'descendant', 'sibling', 'prefix-sibling', 'junction', 'junction-ancestor', 'source-junction'])
def test_powershell_workspace_preflight_no_writes(tmp_path, case):
    # Execute only the exact preflight segment, not the wrapper/install/build.
    # No ExecutionPolicy flag or .ps1 execution-policy workaround is used.
    script = (ROOT/'scripts/build_windows_helper.ps1').read_text()
    preflight = script[script.index('$ErrorActionPreference'):script.index('$Inventory =')]
    source = tmp_path/'source'
    (source/'scripts').mkdir(parents=True)
    sibling = tmp_path/'work'
    work = source if case == 'equal' else source/'missing' if case == 'descendant' else sibling
    alias = tmp_path/'alias'
    if case.startswith('junction') or case == 'source-junction':
        result = subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(alias), str(source)], capture_output=True, timeout=20)
        assert result.returncode == 0, result.stderr
        work = alias if case == 'junction' else alias/'missing' if case == 'junction-ancestor' else sibling
    if case == 'prefix-sibling':
        work = tmp_path/'source-other'
    psroot = alias/'scripts' if case == 'source-junction' else source/'scripts'
    def literal(value):
        return "'"+str(value).replace("'", "''")+"'"
    command = ('$PSScriptRoot='+literal(psroot)+'; $WorkRoot='+literal(work)+'; '+preflight+"; Write-Output 'PREFLIGHT_ACCEPTED'")
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*'))
    try:
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', command], capture_output=True, text=True, timeout=30)
        if case in ('sibling', 'prefix-sibling'):
            assert result.returncode == 0, result.stderr
            assert 'PREFLIGHT_ACCEPTED' in result.stdout
        else:
            assert result.returncode != 0
            assert 'outside source' in result.stderr if case in ('equal', 'descendant') else 'reparse' in result.stderr.lower()
        assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*')) == before
        assert not sibling.exists()
    finally:
        if alias.exists():
            os.rmdir(alias)
