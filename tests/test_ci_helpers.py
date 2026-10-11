"""Synthetic collector regressions; hosted/native evidence comes from the builders."""
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest


def load():
    path = Path(__file__).resolve().parents[1] / 'scripts/ci_helpers.py'
    spec = importlib.util.spec_from_file_location('ci_helpers_tests', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('platform', ['win32', 'darwin', 'linux'])
@pytest.mark.parametrize('fault', [None, 'source', 'package', 'identity'])
def test_collect_verified_files_or_refuse(tmp_path, monkeypatch, platform, fault):
    ci = load()
    monkeypatch.setattr(ci.sys, 'platform', platform)
    monkeypatch.setattr(ci, 'REPO', tmp_path / 'source')
    ci.REPO.mkdir()
    (ci.REPO / 'fixture.py').write_text('synthetic fixture')
    build = tmp_path / 'build'
    build.mkdir()
    sources = {'fixture.py': ci.digest(ci.REPO / 'fixture.py')}
    (build / 'source-hashes.json').write_text(json.dumps(sources))
    names = {'win32': ['setup.exe', 'maintenance.exe'], 'darwin': ['mac.pkg'],
             'linux': ['linux.deb', 'linux.pkg.tar.zst']}[platform]
    entries = []
    for name in names:
        p = build / name
        p.write_bytes(b'SYNTHETIC, NOT AN INSTALLER')
        entries.append(dict(file=name, sha256=ci.digest(p)))
    report = dict(extension_id=ci.EXTENSION_ID, platform=platform, arch='arm64' if platform == 'darwin' else 'x86_64',
                  development=platform == 'darwin', notarized=False, artifacts=entries,
                  unsigned=True, windows_fixture_tests=True, installed_frozen_payload_tested=True,
                  installer=names[0], sha256=entries[0]['sha256'], maintenance=entries[-1])
    if fault == 'identity': report['extension_id'] = 'a' * 32
    if fault == 'source': (ci.REPO / 'fixture.py').write_text('changed')
    if fault == 'package': (build / names[0]).write_bytes(b'changed')
    (build / 'build-report.json').write_text(json.dumps(report))
    (tmp_path / 'dependencies.txt').write_text('synthetic')
    for key in ('GITHUB_SHA', 'GITHUB_REF', 'GITHUB_REPOSITORY', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'):
        monkeypatch.setenv(key, 'synthetic')
    output = tmp_path / 'artifacts'
    if fault:
        with pytest.raises(ValueError): ci.collect(build, output, tmp_path)
    else:
        ci.collect(build, output, tmp_path)
        rows = (output / 'SHA256SUMS').read_text().splitlines()
        assert len(rows) == len(list(output.iterdir())) - 1
        for row in rows:
            digest, name = row.split('  ', 1)
            assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
