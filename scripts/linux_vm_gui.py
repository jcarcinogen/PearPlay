#!/usr/bin/env python3
"""Automated installed desktop-entry/Zenity connection on synthetic guest Xvfb.
Run with dbus-run-session -- xvfb-run -a python3 /src/scripts/linux_vm_gui.py.
This is not a graphical package-manager or owner-observed desktop test.
"""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
assert sys.platform=='linux' and os.environ.get('DISPLAY')
parent=Path('/work/gui-config');(parent/'google-chrome').mkdir(parents=True,exist_ok=True)
host=parent/'google-chrome/NativeMessagingHosts/com.pearplay.helper.json'
assert not host.exists(),'Use a fresh dedicated gui-config'
os.environ.update(XDG_CONFIG_HOME=str(parent),GSK_RENDERER='cairo')
desktop='/usr/share/applications/pearplay-setup.desktop'
subprocess.run(['desktop-file-validate',desktop],check=True)
subprocess.run(['gio','launch',desktop],check=True)

def window():
    result=subprocess.run(['xdotool','search','--onlyvisible','--name','^PearPlay Setup$'],capture_output=True,text=True)
    return result.stdout.strip().splitlines()

for _ in range(180):
    ids=window()
    if ids:break
    time.sleep(.25)
else:raise SystemExit('Installed entry produced no visible setup window')
wid=ids[-1]
initial=subprocess.check_output(['xwininfo','-id',wid],text=True)
Path('/work/evidence/gui-first-window.txt').write_text(initial)
# Wait for GTK mapping, focus only this owned window, and invoke its OK mnemonic.
# --window key events used by the first probe were not a reliable GTK4 input path.
time.sleep(2)
subprocess.run(['xdotool','windowfocus','--sync',wid],check=True)
# Google Chrome is preselected because only its synthetic profile directory exists.
subprocess.run(['xdotool','key','alt+o'],check=True)
for _ in range(240):
    if host.exists():break
    time.sleep(.25)
else:raise SystemExit('GUI connection did not create Chrome native manifest')
manifest=json.loads(host.read_text())
assert manifest['allowed_origins']==['chrome-extension://eoadahoncjfpnennmkjifohclbafjkol/']
assert manifest['path']=='/opt/pearplay/PearPlayHelper/PearPlayHelper'
# Dismiss the successful helper information dialog, not an unrelated app.
time.sleep(1)
for wid in window():
    subprocess.run(['xdotool','windowfocus','--sync',wid],check=True)
    subprocess.run(['xdotool','key','alt+o'],check=True)
data={'entry':desktop,'launch':'gio launch','display':'synthetic Xvfb','windows':initial,
      'manifest':manifest,'manifest_mode':oct(stat.S_IMODE(host.stat().st_mode)),
      'manifest_uid':host.stat().st_uid,'gui_connection':True,'graphical_package_manager_tested':False,
      'owner_observed':False}
Path('/work/evidence/gui-setup.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(data,indent=2))
