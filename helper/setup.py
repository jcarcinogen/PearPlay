"""User-scoped browser connections. The OS package manager owns the shared payload."""
import os
from pathlib import Path
import sys
import json
import subprocess
from helper import install

def system_environment():
    """External OS tools must not load PyInstaller's bundled Linux libraries."""
    env = dict(os.environ)
    if sys.platform == 'linux' and getattr(sys, 'frozen', False):
        original = env.get('LD_LIBRARY_PATH_ORIG')
        if original is None:
            env.pop('LD_LIBRARY_PATH', None)
        else:
            env['LD_LIBRARY_PATH'] = original
    return env


def choose_browsers(detected, platform=None, run=subprocess.run):
    platform = sys.platform if platform is None else platform
    if platform == 'darwin':
        # One selectable connection: do not promise independent disconnection.
        groups = {'Google Chrome and Brave (shared connection)': ('chrome', 'brave'),
                  'Chromium': ('chromium',)}
        labels = ','.join(json.dumps(v) for v in groups)
        defaults = ','.join(json.dumps(label) for label, browsers in groups.items() if any(b in detected for b in browsers))
        script = 'choose from list {'+labels+'} with title "PearPlay Setup" with prompt "Chrome and Brave share one connection on Mac. Connecting or disconnecting this item affects both browsers. Choose connections." default items {'+defaults+'} with multiple selections allowed'
        result = run(['/usr/bin/osascript', '-e', script], capture_output=True, text=True)
        if result.returncode or result.stdout.strip() == 'false': return []
        selected = [value.strip() for value in result.stdout.strip().split(',')]
        return [browser for label, browsers in groups.items() if label in selected for browser in browsers]
    if platform != 'linux': raise ValueError('unsupported_platform')
    argv = ['zenity', '--list', '--checklist', '--title=PearPlay Setup', '--text=Choose browsers to connect or disconnect.',
            '--column=Use', '--column=Browser ID', '--column=Browser', '--hide-column=2', '--print-column=2', '--separator=|', '--width=480', '--height=320']
    for browser,label in LABELS.items(): argv += ['TRUE' if browser in detected else 'FALSE', browser, label]
    result = run(argv, capture_output=True, text=True, env=system_environment())
    if result.returncode == 1: return []  # Deliberate Cancel/close.
    if result.returncode:
        raise OSError('linux_setup_dialog_failed')
    return [browser for browser in result.stdout.strip().split('|') if browser in LABELS]


LABELS = {'chrome': 'Google Chrome', 'brave': 'Brave', 'chromium': 'Chromium'}

def config_parent():
    if sys.platform == 'darwin': return Path.home()/'Library/Application Support'
    if sys.platform == 'linux':
        root = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))
        if not root.is_absolute(): raise ValueError('invalid_config_directory')
        return root
    raise ValueError('unsupported_platform')

def detected_browsers(parent, platform=None):
    # Directory existence only: never read browsing history or browser profiles.
    return [browser for browser in LABELS if (Path(parent)/install.browser_dir(browser, platform)).is_dir()]

def manage(action, browsers, *, shared_disconnect=False, **kwargs):
    if action not in ('connect', 'remove') or not browsers or any(b not in LABELS for b in browsers):
        raise ValueError('invalid_setup_arguments')
    result = {}
    platform = kwargs.get('platform') or sys.platform
    shared = platform == 'darwin' and any(b in ('chrome', 'brave') for b in browsers)
    # A grouped Mac selection is explicit consent; CLI callers selecting one
    # browser must explicitly acknowledge the other browser's disconnection.
    if action == 'remove' and shared and not (shared_disconnect or {'chrome', 'brave'}.issubset(browsers)):
        raise ValueError('mac_chrome_brave_disconnect_requires_shared_confirmation')
    if shared:
        browsers = [*browsers, 'chrome', 'brave']
    for browser in dict.fromkeys(browsers):
        try:
            if action == 'connect':
                install.install(browser=browser, **kwargs)
                result[browser] = 'connected'
            else:
                preserved = install.uninstall(browser=browser, shared_disconnect=shared, **kwargs)
                result[browser] = 'preserved' if preserved else 'removed'
        except (OSError, ValueError):
            result[browser] = 'conflict'
    return result
