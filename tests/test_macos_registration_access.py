"""Native-host ancestors need traversal, not browser-profile read access.

The denial seam models macOS 27 protected browser data. It does not claim
native TCC acceptance; that remains a separately owner-observed gate.
"""
import errno
import os
from pathlib import Path
import sys

import pytest

from helper import install, setup

pytestmark = pytest.mark.skipif(sys.platform != 'darwin', reason='macOS O_SEARCH filesystem behavior')


def test_connect_and_remove_without_reading_browser_ancestors(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    parent = root/'Application Support'
    protected = parent/'Google/Chrome'
    folder = protected/'NativeMessagingHosts'
    real_open = os.open
    calls = []

    def guarded_open(path, flags, *args, **kwargs):
        calls.append((str(path), flags))
        if str(path) == 'Chrome' and not (flags & os.O_SEARCH) == os.O_SEARCH:
            raise PermissionError(errno.EPERM, 'synthetic protected browser directory')
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(install.os, 'open', guarded_open)
    kwargs = dict(extension_id='a'*32, executable=Path(sys.executable), config_parent=parent, platform='darwin')
    result = setup.manage('connect', ['chrome', 'brave'], **kwargs)
    assert result == {'chrome': 'connected', 'brave': 'connected'}
    manifest = folder/'com.pearplay.helper.json'
    assert manifest.is_file()
    assert any(path == 'Chrome' and (flags & os.O_SEARCH) == os.O_SEARCH for path, flags in calls)
    assert all((flags & os.O_SEARCH) == os.O_SEARCH for path, flags in calls if path == 'Chrome')
    # The exempt destination still needs a readable fd for fsync/file work.
    leaf_flags = [flags for path, flags in calls if path == 'NativeMessagingHosts']
    assert leaf_flags and all(not (flags & os.O_SEARCH) == os.O_SEARCH for flags in leaf_flags)
    assert setup.manage('remove', ['chrome', 'brave'], **kwargs) == {'chrome': 'removed', 'brave': 'removed'}
    assert not manifest.exists()


def test_search_only_traversal_still_rejects_ancestor_symlink(tmp_path):
    root = tmp_path.resolve()
    actual = root/'actual'
    actual.mkdir()
    linked = root/'linked'
    linked.symlink_to(actual, target_is_directory=True)
    with pytest.raises(OSError):
        install.directory(linked/'NativeMessagingHosts', True)
    assert not (actual/'NativeMessagingHosts').exists()


def test_leaf_directory_denial_is_not_bypassed(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    real_open = os.open

    def denied_leaf(path, flags, *args, **kwargs):
        if str(path) == 'NativeMessagingHosts':
            raise PermissionError(errno.EPERM, 'synthetic destination denied')
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(install.os, 'open', denied_leaf)
    kwargs = dict(extension_id='a'*32, executable=Path(sys.executable), config_parent=root, platform='darwin')
    assert setup.manage('connect', ['chrome'], **kwargs) == {'chrome': 'conflict', 'brave': 'conflict'}
    assert not (root/'Google/Chrome/NativeMessagingHosts/com.pearplay.helper.json').exists()
