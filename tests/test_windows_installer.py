"""Portable installer policy tests using explicit in-memory fixture adapters.

These tests intentionally do not imply Windows ACL/registry execution evidence.
"""
import hashlib
import io
import json
from pathlib import PureWindowsPath
import zipfile
import pytest
from helper.windows_setup import EXTENSION_ID, HOST, encoded, manifest, payload_files, receipt, reconcile


class FixtureFiles:
    root = PureWindowsPath(r'C:\Users\Fixture\AppData\Local\PearPlay\helper')
    def __init__(self):
        self.data = {}
    def inventory(self):
        return {name:hashlib.sha256(raw).hexdigest() for name,raw in self.data.items()}
    def read(self, name, limit=None):
        if name not in self.data:
            raise FileNotFoundError(name)
        return self.data[name]
    def write_new(self, name, raw):
        if name in self.data:
            raise FileExistsError(name)
        self.data[name] = raw
    def replace(self, name, raw):
        self.data[name] = raw
    def delete(self, name, digest):
        if name not in self.data:
            raise FileNotFoundError(name)
        assert hashlib.sha256(self.data[name]).hexdigest() == digest
        del self.data[name]
    def prune(self, names):
        pass


class FixtureRegistry:
    def __init__(self):
        self.values = [None,None]
        self.fail_once = False
    def snapshot(self):
        return list(self.values)
    def apply(self, values):
        if self.fail_once:
            self.fail_once = False
            self.values[0] = values[0]  # simulate failure after partial update
            raise OSError('fixture_failure')
        self.values = list(values)


def payload(version='0.3.0', extra=None):
    files = {'PearPlayHelper.exe':b'fixture only, not an executable',
             'build-info.json':encoded(dict(extension_id=EXTENSION_ID,development=False,platform='win32',version=version))}
    files.update(extra or {})
    output = io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        for name,raw in files.items():
            info = zipfile.ZipInfo(name)
            # Windows ZipInfo canonicalizes os.sep. Force the malicious spelling
            # so the test exercises our parser, not stdlib ZIP normalization.
            info.filename = name
            archive.writestr(info,raw)
    return output.getvalue()


def test_install_repair_upgrade_disconnect_uninstall_readbacks():
    files, registry = FixtureFiles(), FixtureRegistry()
    result = reconcile('install',files,registry,payload(extra={'_internal/old.dll':b'old'}))
    assert result['version'] == '0.3.0'
    assert registry.values == [str(files.root/(HOST+'.json'))]*2
    m = json.loads(files.data[HOST+'.json'])
    assert m == manifest(files.root/'runtime/PearPlayHelper.exe')
    assert m['allowed_origins'] == ['chrome-extension://'+EXTENSION_ID+'/']
    del files.data['runtime/PearPlayHelper.exe']
    reconcile('repair',files,registry,payload(extra={'_internal/old.dll':b'old'}))
    reconcile('upgrade',files,registry,payload('0.3.1', {'_internal/new.dll':b'new'}))
    assert 'runtime/_internal/old.dll' not in files.data
    assert 'runtime/_internal/new.dll' in files.data
    assert receipt(json.loads(files.data['install-receipt.json']))['version'] == '0.3.1'
    reconcile('disconnect',files,registry)
    assert registry.values == [None,None]
    reconcile('connect',files,registry)
    assert all(registry.values)
    result = reconcile('uninstall',files,registry)
    assert result['pairing'] == 'preserved'
    assert files.data == {}
    assert registry.values == [None,None]


def test_preserve_changed_and_foreign_files_uninstall():
    files, registry = FixtureFiles(), FixtureRegistry()
    reconcile('install',files,registry,payload())
    files.data['runtime/PearPlayHelper.exe'] = b'changed foreign bytes'
    files.data['notes.txt'] = b'foreign'
    snapshot = dict(files.data)
    for action in ['repair','upgrade','connect']:
        with pytest.raises(ValueError):
            reconcile(action,files,registry,payload('0.3.1'))
        assert files.data == snapshot
    result = reconcile('uninstall',files,registry)
    assert set(result['preserved']) == {'runtime/PearPlayHelper.exe','notes.txt'}
    assert files.data['notes.txt'] == b'foreign'
    assert files.data['runtime/PearPlayHelper.exe'] == b'changed foreign bytes'
    assert 'install-receipt.json' in files.data


def test_foreign_registry_unreceipted_files_and_downgrade_refused():
    files, registry = FixtureFiles(), FixtureRegistry()
    registry.values = ['C:\\foreign.json',None]
    with pytest.raises(ValueError,match='foreign_registration'):
        reconcile('install',files,registry,payload())
    assert not files.data
    registry.values = [None,None]
    files.data['notes.txt'] = b'foreign'
    with pytest.raises(ValueError,match='unreceipted'):
        reconcile('install',files,registry,payload())
    files.data.clear()
    reconcile('install',files,registry,payload())
    with pytest.raises(ValueError,match='downgrade'):
        reconcile('upgrade',files,registry,payload('0.2.9'))
    with pytest.raises(ValueError,match='same_version'):
        reconcile('repair',files,registry,payload('0.3.1'))


def test_partial_registry_failure_rolls_back_exactly():
    files, registry = FixtureFiles(), FixtureRegistry()
    registry.fail_once = True
    with pytest.raises(OSError):
        reconcile('install',files,registry,payload())
    assert registry.values == [None,None]
    assert files.data == {}
    reconcile('install',files,registry,payload())
    snapshot = dict(files.data)
    before = registry.snapshot()
    registry.fail_once = True
    with pytest.raises(OSError):
        reconcile('upgrade',files,registry,payload('0.3.1'))
    assert files.data == snapshot
    assert registry.snapshot() == before


def test_interrupted_transaction_fails_closed():
    files, registry = FixtureFiles(), FixtureRegistry()
    files.data['transaction.json'] = b'fixture'
    with pytest.raises(ValueError,match='interrupted_transaction'):
        reconcile('repair',files,registry,payload())
    assert files.data == {'transaction.json':b'fixture'}


@pytest.mark.parametrize('name', ['../evil','/evil','a/../evil','a\\evil','NUL.txt','a:stream','a.','a ','./a'])
def test_payload_rejects_unsafe_paths(name):
    with pytest.raises(ValueError):
        payload_files(payload(extra={name:b'bad'}))


def test_payload_case_collision_file_directory_collision_and_receipt_paths():
    for extra in [{'pearplayhelper.EXE':b'bad'}, {'a':b'file','a/b':b'child'}]:
        with pytest.raises(ValueError):
            payload_files(payload(extra=extra))
    files, registry = FixtureFiles(), FixtureRegistry()
    reconcile('install',files,registry,payload())
    r = json.loads(files.data['install-receipt.json'])
    r['files']['../../state/credentials.dpapi'] = 'a'*64
    with pytest.raises(ValueError):
        receipt(r)
