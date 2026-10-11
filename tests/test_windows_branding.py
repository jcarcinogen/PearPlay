"""Portable UI policy and native Windows Tk tests; no real setup transactions."""
import sys
import threading
import time
from pathlib import Path

import pytest
from helper import windows_gui as gui, windows_setup as setup


@pytest.mark.parametrize('action', ['install', 'upgrade', 'repair', 'connect', 'disconnect', 'uninstall'])
def test_results_are_action_specific_and_pairing_preserved(action):
    text = gui.result_text(dict(action=action, preserved=[]))
    assert 'Saved TV pairing is kept' in text
    assert 'is connected to Chrome' not in text  # Registration is not a handshake.
    if action in ('disconnect', 'uninstall'):
        assert 'disconnected' in text
    else:
        assert 'Check connection' in text


def test_preserved_files_never_report_complete_removal_or_leak_paths():
    text = gui.result_text(dict(action='uninstall', preserved=['C:/private/person.txt']))
    assert 'removal may be incomplete' in text
    assert 'private' not in text and 'person' not in text
    with pytest.raises(ValueError):
        gui.result_text({'ok': True})


def test_installed_host_does_not_offer_missing_embedded_payload():
    assert gui.PearPlayGUI(installed_host=True).actions == ('connect', 'disconnect')
    assert set(gui.PearPlayGUI().actions) == {'auto', 'repair', 'connect', 'disconnect', 'uninstall'}


@pytest.mark.parametrize('redirected', [True, False])
def test_no_argument_setup_always_requires_branded_confirmation(monkeypatch, redirected):
    from helper import windows_io
    calls = []
    monkeypatch.setattr(setup.sys, 'platform', 'win32')
    monkeypatch.setattr(setup.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(windows_io, 'restore_stdio', lambda: redirected)
    monkeypatch.setattr(gui, 'show_setup', lambda **kw: calls.append(kw) or 0)
    monkeypatch.setattr(setup, 'manage', lambda *a: pytest.fail('must not mutate on open'))
    assert setup.main([]) == 0
    assert len(calls) == 1


def test_explicit_redirected_action_keeps_automation(monkeypatch, capsys):
    from helper import windows_io
    monkeypatch.setattr(setup.sys, 'platform', 'win32')
    monkeypatch.setattr(setup.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(windows_io, 'restore_stdio', lambda: True)
    monkeypatch.setattr(gui, 'show_setup', lambda **kw: pytest.fail('no GUI for explicit captured automation'))
    monkeypatch.setattr(setup, 'manage', lambda action, payload: {'action': action})
    assert setup.main(['disconnect']) == 0
    assert 'disconnect' in capsys.readouterr().out


def test_source_has_no_legacy_dialog_or_console_allocation():
    root = Path(__file__).resolve().parents[1]
    for name in ('windows_setup.py', 'windows_gui.py', 'windows_io.py'):
        text = (root / 'helper' / name).read_text()
        for forbidden in ('MessageBoxW', 'AllocConsole(', 'AttachConsole(', 'ShowWindow('):
            assert forbidden not in text


@pytest.mark.skipif(sys.platform != 'win32', reason='requires native Windows Tk rendering')
@pytest.mark.parametrize('action,outcome', [('auto', 'install'), ('repair', 'repair'), ('connect', 'connect'), ('disconnect', 'disconnect'), ('uninstall', 'uninstall'), ('auto', 'error')])
def test_native_tk_confirmation_busy_success_and_failure(action, outcome):
    gate = threading.Event()
    calls = []
    def operation():
        calls.append(action)
        if not gate.wait(5):
            raise RuntimeError('test_wait_timeout')
        if outcome == 'error':
            raise RuntimeError('C:/private/raw-secret')
        return dict(action=outcome, preserved=['private'] if outcome == 'uninstall' else [])
    window = gui.PearPlayGUI(run_operation=operation, initial_action=action)
    window.root = window._create_window()
    try:
        window._build_ui(window.root)
        window.root.update()
        assert window.root.title() == 'PearPlay Setup'
        assert window.logo.width() > 0
        assert window.install_btn.winfo_rooty() + window.install_btn.winfo_height() <= window.root.winfo_rooty() + window.root.winfo_height()
        window.install_btn.invoke()
        assert window.confirming and not window.busy and not calls
        assert 'Confirm:' in window.status_var.get()
        window.install_btn.invoke()
        assert window.busy
        window._close()
        assert window.root.winfo_exists()
        assert str(window.close_btn['state']) == 'disabled'
        assert all(str(b['state']) == 'disabled' for b in window.action_buttons)
        gate.set()
        deadline = time.monotonic() + 8
        while window.busy and time.monotonic() < deadline:
            window.root.update()
            time.sleep(.02)
        assert not window.busy and calls == [action]
        text = window.status_var.get()
        assert 'private' not in text and 'raw-secret' not in text
        assert ('could not complete' in text) == (outcome == 'error')
        if outcome == 'uninstall':
            assert 'removal may be incomplete' in text
        assert str(window.close_btn['state']) == 'normal'
    finally:
        gate.set()
        if window._thread:
            window._thread.join(timeout=6)
        window.root.destroy()
