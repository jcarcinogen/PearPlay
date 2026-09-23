"""User-scoped browser connections. The OS package manager owns the shared payload."""
import os
from pathlib import Path
import sys
import json
import subprocess
from helper import install

def choose_browsers(detected, platform=None, run=subprocess.run):
    platform = sys.platform if platform is None else platform
    if platform == 'darwin':
        labels = ','.join(json.dumps(v) for v in LABELS.values())
        defaults = ','.join(json.dumps(LABELS[b]) for b in detected if b in LABELS)
        script = 'choose from list {'+labels+'} with title "PearPlay Setup" with prompt "Choose browsers to connect or disconnect." default items {'+defaults+'} with multiple selections allowed'
        result = run(['/usr/bin/osascript', '-e', script], capture_output=True, text=True)
        if result.returncode or result.stdout.strip() == 'false': return []
        selected = [value.strip() for value in result.stdout.strip().split(',')]
        return [browser for browser,label in LABELS.items() if label in selected]
    if platform != 'linux': raise ValueError('unsupported_platform')
    argv = ['zenity', '--list', '--checklist', '--title=PearPlay Setup', '--text=Choose browsers to connect or disconnect.',
            '--column=Use', '--column=Browser ID', '--column=Browser', '--hide-column=2', '--print-column=2', '--separator=|', '--width=480', '--height=320']
    for browser,label in LABELS.items(): argv += ['TRUE' if browser in detected else 'FALSE', browser, label]
    result = run(argv, capture_output=True, text=True)
    if result.returncode: return []
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

def manage(action, browsers, **kwargs):
    if action not in ('connect', 'remove') or not browsers or any(b not in LABELS for b in browsers):
        raise ValueError('invalid_setup_arguments')
    result = {}
    for browser in dict.fromkeys(browsers):
        try:
            if action == 'connect':
                install.install(browser=browser, **kwargs)
                result[browser] = 'connected'
            else:
                preserved = install.uninstall(browser=browser, **kwargs)
                result[browser] = 'preserved' if preserved else 'removed'
        except (OSError, ValueError):
            result[browser] = 'conflict'
    return result
