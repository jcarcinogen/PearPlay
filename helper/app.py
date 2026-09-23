"""Frozen helper entry point: native port for browsers, setup for humans."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import webbrowser
from helper import native, setup

UPDATES = 'https://github.com/jcarcinogen/PearPlay/releases'
ACTIONS = {'Connect or repair browsers': 'connect', 'Disconnect browsers': 'remove', 'Get helper updates': 'update', 'Uninstall helper': 'uninstall'}

def valid_build(config):
    return isinstance(config, dict) and isinstance(config.get('extension_id'), str) and re.fullmatch(r'[a-p]{32}', config['extension_id']) is not None

def dialog(text):
    if sys.platform == 'darwin':
        subprocess.run(['/usr/bin/osascript','-e','display dialog '+json.dumps(text)+' with title "PearPlay Setup" buttons {"OK"} default button "OK"'],capture_output=True)
    else:
        subprocess.run(['zenity','--info','--no-markup','--title=PearPlay Setup','--text='+text],capture_output=True)

def gui(config, parent, executable):
    choices=list(ACTIONS)
    if sys.platform == 'darwin':
        script='choose from list {'+','.join(json.dumps(x) for x in choices)+'} with title "PearPlay Setup" with prompt "One helper for your browsers. End casting before updates or removal."'
        selected=subprocess.run(['/usr/bin/osascript','-e',script],capture_output=True,text=True)
    else:
        selected=subprocess.run(['zenity','--list','--title=PearPlay Setup','--text=One helper for your browsers. End casting before updates or removal.','--column=Action','--width=500','--height=350',*choices],capture_output=True,text=True)
    if selected.returncode or selected.stdout.strip() not in ACTIONS: return 0
    action=ACTIONS[selected.stdout.strip()]
    if action == 'update': webbrowser.open(UPDATES); return 0
    browsers=list(setup.LABELS) if action=='uninstall' else setup.choose_browsers(setup.detected_browsers(parent))
    if not browsers: return 0
    if action=='uninstall':
        # Disconnecting is non-destructive to the package and saved pairing. Package removal remains an OS action.
        action='remove'
    result=setup.manage(action,browsers,extension_id=config['extension_id'],executable=executable,config_parent=parent)
    text='\n'.join(setup.LABELS[b]+': '+{'connected':'connected','removed':'disconnected','preserved':'changed files preserved','conflict':'could not connect; existing files were left alone'}[state] for b,state in result.items())
    if action=='connect': text+='\n\nFully quit and reopen these browsers, then click Check connection in the extension setup tab. Install the extension in each browser.'
    else: text+='\n\nSaved TV pairing is kept. To remove the helper itself, move PearPlay Setup from Applications to Trash on Mac, or remove pearplay-helper with your Linux software manager. Removing the extension alone does not remove the helper.'
    if 'conflict' in result.values() or 'preserved' in result.values(): text+='\n\nA previous developer installation may need its original uninstaller. See the developer guide; do not overwrite unknown files.'
    dialog(text)
    return 1 if any(v in ('conflict','preserved') for v in result.values()) else 0

def main(argv=None, config=None):
    argv=sys.argv[1:] if argv is None else argv
    if config is None:
        try: config=json.loads((Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'build.json').read_text())
        except (OSError,ValueError): config={}
    if not valid_build(config): return 2
    if len(argv)==1 and '://' in argv[0]:
        return native.main(['native','--extension-id',config['extension_id'],argv[0]])
    parser=argparse.ArgumentParser(description='PearPlay Helper setup (no TV actions)')
    parser.add_argument('action',nargs='?',choices=['connect','remove','self-test'])
    parser.add_argument('--browsers',nargs='+',choices=list(setup.LABELS))
    parser.add_argument('--config-parent',type=Path)
    args=parser.parse_args(argv)
    if args.action=='self-test':
        native.Transport()  # Imports all transport dependencies, but performs no discovery or playback.
        print(json.dumps({'ok':True,'version':'0.2.0','dependencies':'loaded','network':'not used'}))
        return 0
    if os.getuid()==0: return 2  # Browser registration always belongs to the signed-in user, never root.
    if not getattr(sys,'frozen',False): return 2  # A system Python executable is not the packaged native host.
    executable=Path(sys.executable).resolve()
    parent=args.config_parent or setup.config_parent()
    if args.action:
        if not args.browsers: return 2
        result=setup.manage(args.action,args.browsers,extension_id=config['extension_id'],executable=executable,config_parent=parent)
        print(json.dumps(result))
        return 1 if any(v in ('conflict','preserved') for v in result.values()) else 0
    try: return gui(config,parent,executable)
    except (OSError,ValueError):
        print('PearPlay Setup could not open. Linux graphical setup requires Zenity. Use the developer guide.',file=sys.stderr)
        return 1

if __name__=='__main__': raise SystemExit(main())
