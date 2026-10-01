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

def native_options(config, environ=None, frozen=None):
    """Resolve opt-in diagnostic trace/startup/event-labels/metadata.

    Returns ``(trace, startup_timeout, event_labels, event_metadata)``; all
    are ``None`` in production or when the opt-in environment variables are
    absent. The trace is a ``DiagnosticTrace`` bound to the pre-created
    owner-only file; the event-label sidecar is an ``EventLabelCollector`` and
    the event-metadata sidecar is an ``EventMetadataCollector``, each honored
    only when the trace is also opted in. Startup accepts only ``'10'``/``'30'``
    and only when the trace is opted in.
    """
    from helper.diagnostics import resolve_env, resolve_event_labels, resolve_event_metadata, DiagnosticTrace, EventLabelCollector, EventMetadataCollector
    environ = os.environ if environ is None else environ
    if frozen is None:
        frozen = bool(getattr(sys, 'frozen', False))
    development = bool(config.get('development'))
    path, startup = resolve_env(environ, frozen=frozen, development=development)
    if path is None:
        return (None, None, None, None)
    trace = DiagnosticTrace(path)
    if trace.disabled:
        return (None, None, None, None)
    labels_path = resolve_event_labels(environ, frozen=frozen, development=development)
    labels = EventLabelCollector(labels_path) if labels_path else None
    metadata_path = resolve_event_metadata(environ, frozen=frozen, development=development)
    metadata = EventMetadataCollector(metadata_path) if metadata_path else None
    return (trace, startup, labels, metadata)

def probe_playback_info_option(config, environ=None, frozen=None):
    """Resolve the opt-in playback-info probe origin, or None.

    Kept separate from ``native_options`` so the existing 4-tuple is unchanged;
    the caller gates this on an active trace (``native_options`` returning a
    non-None trace). Accepts only ``'origin-mp4'``/``'origin-hls'`` and only in a
    frozen development build with the trace opted in.
    """
    from helper.diagnostics import resolve_probe_playback_info
    environ = os.environ if environ is None else environ
    if frozen is None:
        frozen = bool(getattr(sys, 'frozen', False))
    development = bool(config.get('development'))
    return resolve_probe_playback_info(environ, frozen=frozen, development=development)

def diagnostic_v1_option(config, environ=None, frozen=None, *, trace_active=False):
    """No production fallback: explicit frozen-development receiver pin only."""
    import ipaddress
    environ = os.environ if environ is None else environ
    frozen = bool(getattr(sys, 'frozen', False)) if frozen is None else frozen
    if not frozen or config.get('development') is not True or not trace_active:
        return None
    value = environ.get('PEARPLAY_DIAGNOSTIC_V1_RECEIVER', '')
    match = re.fullmatch(r'([0-9a-fA-F:-]{12,64})@([0-9.]+)', value)
    if not match:
        return None
    try:
        address = ipaddress.IPv4Address(match[2])
    except ValueError:
        return None
    if not any(address in ipaddress.IPv4Network(net) for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
        return None
    return (match[1], str(address))


def dialog(text):
    if sys.platform == 'darwin':
        subprocess.run(['/usr/bin/osascript','-e','display dialog '+json.dumps(text)+' with title "PearPlay Setup" buttons {"OK"} default button "OK"'],capture_output=True)
    else:
        subprocess.run(['zenity','--info','--no-markup','--title=PearPlay Setup','--text='+text],capture_output=True)

def gui(config, parent, executable):
    # First launch goes straight to browser selection. Any existing registration,
    # including a legacy/unknown one, keeps the explicit repair/removal menu.
    registered = any((parent/setup.install.browser_dir(b)/'NativeMessagingHosts/com.pearplay.helper.json').exists()
                     for b in setup.LABELS)
    choices=list(ACTIONS)
    if not registered:
        action='connect'
    else:
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
    if config.get('development'):
        text='Development build — for testing only, not a signed consumer release.\nUse the matching test extension supplied with this installer.\n\n'+text
    dialog(text)
    return 1 if any(v in ('conflict','preserved') for v in result.values()) else 0

def main(argv=None, config=None):
    argv=sys.argv[1:] if argv is None else argv
    if config is None:
        try: config=json.loads((Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'build.json').read_text())
        except (OSError,ValueError): config={}
    if not valid_build(config): return 2
    if argv and argv[0] == 'firewall-privileged':
        if len(argv) != 3: return 2
        from helper.firewall import privileged_main
        return 0 if privileged_main(argv[1], argv[2])['ok'] else 1
    if len(argv)==1 and '://' in argv[0]:
        trace, startup, labels, metadata = native_options(config)
        probe = probe_playback_info_option(config) if trace is not None else None
        v1 = diagnostic_v1_option(config, trace_active=trace is not None)
        return native.main(['native','--extension-id',config['extension_id'],argv[0]], trace=trace, startup_timeout=startup, event_labels=labels, event_metadata=metadata, probe_playback_info=probe, diagnostic_v1=v1)
    parser=argparse.ArgumentParser(description='PearPlay Helper setup (no TV actions)')
    parser.add_argument('action',nargs='?',choices=['connect','remove','self-test'])
    parser.add_argument('--browsers',nargs='+',choices=list(setup.LABELS))
    parser.add_argument('--config-parent',type=Path)
    args=parser.parse_args(argv)
    if args.action=='self-test':
        native.Transport()  # Imports all transport dependencies, but performs no discovery or playback.
        print(json.dumps({'ok':True,'version':native.VERSION,'dependencies':'loaded','network':'not used'}))
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
