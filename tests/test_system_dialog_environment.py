"""OS dialogs must use host libraries, not the frozen helper's libraries."""
import subprocess
from types import SimpleNamespace
import pytest
from helper import setup, app


def test_frozen_linux_restores_original_without_mutating_process(monkeypatch):
    monkeypatch.setattr(setup.sys, 'platform', 'linux')
    monkeypatch.setattr(setup.sys, 'frozen', True, raising=False)
    monkeypatch.setenv('LD_LIBRARY_PATH', '/bundled')
    monkeypatch.setenv('LD_LIBRARY_PATH_ORIG', '/host')
    assert setup.system_environment()['LD_LIBRARY_PATH'] == '/host'
    assert setup.os.environ['LD_LIBRARY_PATH'] == '/bundled'
    monkeypatch.delenv('LD_LIBRARY_PATH_ORIG')
    assert 'LD_LIBRARY_PATH' not in setup.system_environment()


@pytest.mark.parametrize('platform,frozen', [('darwin', True), ('win32', True), ('linux', False)])
def test_other_platforms_and_unfrozen_environment_unchanged(monkeypatch, platform, frozen):
    monkeypatch.setattr(setup.sys, 'platform', platform)
    monkeypatch.setattr(setup.sys, 'frozen', frozen, raising=False)
    monkeypatch.setenv('LD_LIBRARY_PATH', '/existing')
    assert setup.system_environment()['LD_LIBRARY_PATH'] == '/existing'


def test_chooser_passes_clean_environment_and_distinguishes_failure(monkeypatch):
    monkeypatch.setattr(setup.sys, 'platform', 'linux')
    monkeypatch.setattr(setup.sys, 'frozen', True, raising=False)
    monkeypatch.setenv('LD_LIBRARY_PATH', '/bundled')
    monkeypatch.delenv('LD_LIBRARY_PATH_ORIG', raising=False)
    def failed(argv, **kwargs):
        assert 'LD_LIBRARY_PATH' not in kwargs['env']
        return SimpleNamespace(returncode=127, stdout='')
    with pytest.raises(OSError, match='linux_setup_dialog_failed'):
        setup.choose_browsers(['chrome'], run=failed)
    assert setup.choose_browsers([], run=lambda *a, **k: SimpleNamespace(returncode=1, stdout='')) == []


def test_confirmation_uses_clean_environment_and_checks_exit(monkeypatch):
    monkeypatch.setattr(setup.sys, 'platform', 'linux')
    monkeypatch.setattr(setup.sys, 'frozen', True, raising=False)
    monkeypatch.setenv('LD_LIBRARY_PATH', '/bundled')
    monkeypatch.delenv('LD_LIBRARY_PATH_ORIG', raising=False)
    def check(argv, **kwargs):
        assert 'LD_LIBRARY_PATH' not in kwargs['env']
        assert kwargs['check'] is True
        return subprocess.CompletedProcess(argv, 0)
    monkeypatch.setattr(app.subprocess, 'run', check)
    app.dialog('Fixture confirmation')
