"""Integrated Mac setup copy and shared-removal CLI; no native dialogs/TVs."""
import json
import os
from helper import app, setup
import pytest

pytestmark=pytest.mark.skipif(os.name=='nt',reason='Mac/POSIX setup branch')

ID='eoadahoncjfpnennmkjifohclbafjkol'

@pytest.fixture
def preview(tmp_path,monkeypatch):
    monkeypatch.setattr(app.sys,'platform','darwin')
    monkeypatch.setattr(app.sys,'frozen',True,raising=False)
    executable=tmp_path/'PearPlayHelper'
    executable.write_text('#!/bin/sh\nexit 0\n');executable.chmod(0o700)
    monkeypatch.setattr(app.sys,'executable',str(executable))
    return {'extension_id':ID,'development':True},tmp_path/'config',executable

def test_shared_remove_requires_explicit_acknowledgment(preview,capsys):
    config,parent,binary=preview
    setup.manage('connect',['chrome'],extension_id=ID,executable=binary,config_parent=parent)
    args=['remove','--browsers','chrome','--config-parent',str(parent)]
    assert app.main(args,config)==1
    assert 'both Chrome and Brave' in capsys.readouterr().err
    host=parent/'Google/Chrome/NativeMessagingHosts/com.pearplay.helper.json'
    assert host.is_file()
    assert app.main(args+['--shared-disconnect'],config)==0
    assert json.loads(capsys.readouterr().out)=={'chrome':'removed','brave':'removed'}
    assert not host.exists()

def test_preview_dialog_explains_shared_connection_and_real_extension(preview,monkeypatch):
    config,parent,binary=preview
    messages=[];lookups=[]
    original=setup.install.host_dir
    def host_dir(browser,platform=None):
        lookups.append(browser)
        return original(browser,platform)
    monkeypatch.setattr(setup.install,'host_dir',host_dir)
    monkeypatch.setattr(setup,'choose_browsers',lambda _:['chrome','brave'])
    monkeypatch.setattr(app,'dialog',messages.append)
    assert app.gui(config,parent,binary)==0
    assert lookups
    assert 'Unsigned preview' in messages[0]
    assert 'Chrome and Brave share' in messages[0]
    assert 'matching test extension' not in messages[0]
    assert 'Fully quit and reopen' in messages[0]
