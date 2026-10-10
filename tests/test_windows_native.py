"""Real Win32 fixture tests. Skipped off Windows; no TV or production state.

Build pipeline requires these to pass on Windows. The installer policy suite
is separate. Registry tests use a unique HKCU PearPlayTest key, NOT Chrome.
"""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='requires actual Windows Win32/DPAPI/registry')


@pytest.fixture
def boundary():
    from helper.windows_security import Win32
    from helper.windows_store import Store
    api = Win32()
    base = api.local_appdata() / ('PearPlayTest-' + secrets.token_hex(12))
    store = Store(api=api, root=base)
    with store.directory():
        pass
    try:
        yield api, store
    finally:
        # Only this test-created random directory, never live PearPlay state.
        assert base.name.startswith('PearPlayTest-')
        shutil.rmtree(base)


def test_dpapi_roundtrip_and_plaintext_never_on_disk(boundary):
    _, store = boundary
    value = dict(identifier='AA:BB:CC:DD:EE:FF', credentials='fixture-secret-only')
    store.save(value)
    assert store.load() == value
    assert b'fixture-secret-only' not in (store.root/'credentials.dpapi').read_bytes()
    assert not (store.root/'credentials.json').exists()
    store.save(dict(value,credentials='fixture-new'))
    assert store.load()['credentials'] == 'fixture-new'
    assert not list(store.root.glob('.credentials-*'))


def test_hardlink_and_inherited_acl_rejected(boundary):
    _, store = boundary
    value = dict(identifier='AA:BB:CC:DD:EE:FF', credentials='fixture')
    store.save(value)
    link = store.root/'foreign-hardlink'
    os.link(store.root/'credentials.dpapi',link)
    try:
        with pytest.raises(ValueError,match='hardlink'):
            store.load()
        with pytest.raises(ValueError,match='hardlink'):
            store.save(value)
    finally:
        link.unlink()
    (store.root/'credentials.dpapi').unlink()
    # Default creation inherits the parent's DACL (not protected), and must
    # not be accepted just because the plaintext has an otherwise valid schema.
    (store.root/'credentials.dpapi').write_bytes(b'fixture')
    with pytest.raises(ValueError,match='acl'):
        store.load()


def test_tampered_dpapi_data_fails_closed(boundary):
    api, store = boundary
    with store.file('credentials.dpapi', create='new', exclusive=True, write=True) as handle:
        api.write(handle,b'not a DPAPI blob')
    with pytest.raises(OSError):
        store.load()


def test_exclusive_lease_cross_process_and_release(boundary):
    from helper.windows_store import Lease
    api, store = boundary
    from helper.native import HelperError
    code = ('from helper.windows_store import Store,Lease; import sys; '
            's=Store(root=sys.argv[1]); '
            'lease=Lease(s); lease.__enter__(); lease.__exit__(None,None,None)')
    root = Path(__file__).resolve().parents[1]
    with Lease(store):
        with pytest.raises(HelperError,match='busy'):
            with Lease(store):
                pass
        result = subprocess.run([sys.executable,'-c',code,str(store.base)],cwd=root,capture_output=True,timeout=20)
        assert result.returncode != 0
        assert b'busy' in result.stderr
    result = subprocess.run([sys.executable,'-c',code,str(store.base)],cwd=root,capture_output=True,timeout=20)
    assert result.returncode == 0, result.stderr


def test_junction_parent_and_leaf_rejected(boundary):
    _, store = boundary
    target = store.base/'target'
    target.mkdir()
    junction = store.base/'junction'
    created = subprocess.run(['cmd','/d','/c','mklink','/J',str(junction),str(target)],capture_output=True,timeout=20)
    assert created.returncode == 0, created.stderr
    try:
        from helper.windows_store import Store
        with pytest.raises(ValueError,match='reparse'):
            with Store(root=junction).directory():
                pass
        # All ancestors are inspected even if the final child is missing.
    finally:
        os.rmdir(junction)  # unlink junction, never target recursively


def test_native_file_and_registry_install_repair_uninstall(boundary, monkeypatch):
    from helper import windows_setup as setup
    from test_windows_installer import payload
    api, store = boundary
    fixture_key = 'Software\\PearPlayTest\\' + secrets.token_hex(12)
    monkeypatch.setattr(setup,'KEY',fixture_key)
    files, registry = setup.Files(api,store.base), setup.Registry()
    try:
        with files.directory():
            setup.reconcile('install',files,registry,payload())
            assert registry.snapshot() == [str(files.root/(setup.HOST+'.json'))]*2
            (files.root/'runtime/PearPlayHelper.exe').unlink()
            setup.reconcile('repair',files,registry,payload())
            # Foreign file gets a protected test-created ACL but no receipt.
            files.write_new('notes.txt',b'fixture foreign')
            result = setup.reconcile('uninstall',files,registry)
            assert result['preserved'] == ['notes.txt']
            assert files.read('notes.txt') == b'fixture foreign'
            assert registry.snapshot() == [None,None]
    finally:
        registry.apply([None,None])


def test_frozen_payload_fixture_install_repair_and_uninstall(boundary, monkeypatch):
    archive = os.environ.get('PEARPLAY_TEST_PAYLOAD')
    if not archive:
        pytest.skip('set by builder after actual freezing')
    from helper import windows_setup as setup
    from scripts.build_windows_helper import native_smoke
    from helper.windows_store import Lease
    api, store = boundary
    fixture_key = 'Software\\PearPlayTest\\' + secrets.token_hex(12)
    monkeypatch.setattr(setup, 'KEY', fixture_key)
    files, registry = setup.Files(api, store.base), setup.Registry()
    raw = Path(archive).read_bytes()
    saved = dict(identifier='AA:BB:CC:DD:EE:FF', credentials='fixture-pairing-kept')
    store.save(saved)
    try:
        with Lease(store), files.directory():
            setup.reconcile('install', files, registry, raw)
            executable = files.root/'runtime/PearPlayHelper.exe'
            assert native_smoke(executable)['binary_crlf_header']
            executable.unlink()
            setup.reconcile('repair', files, registry, raw)
            assert native_smoke(executable)['identity_override_rejected']
            setup.reconcile('upgrade', files, registry, raw)
            result = setup.reconcile('uninstall', files, registry)
            assert result['preserved'] == []
            assert files.inventory() == {}
            assert store.load() == saved
            assert registry.snapshot() == [None,None]
    finally:
        registry.apply([None,None])


def test_pinned_parent_prevents_rename(boundary):
    api, store = boundary
    with store.directory():
        with pytest.raises(OSError):
            os.rename(store.base,store.base.with_name(store.base.name+'-moved'))
