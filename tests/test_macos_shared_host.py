"""Mac Chrome/Brave host sharing without daily profile or TV access."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
from helper import install, setup
import pytest

ID='eoadahoncjfpnennmkjifohclbafjkol'

@pytest.fixture
def config(tmp_path):
    binary=tmp_path/'PearPlayHelper'
    binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o700)
    return dict(extension_id=ID,config_parent=tmp_path/'config',executable=binary,platform='darwin')


def test_mac_shared_install_repair_and_guarded_removal(config):
    chrome=install.install(browser='chrome',**config)
    brave=install.install(browser='brave',**config)
    assert chrome == brave
    assert json.loads(chrome['manifest'].read_text())['allowed_origins']==['chrome-extension://'+ID+'/']
    for browser in ('chrome','brave'):
        with pytest.raises(ValueError,match='shared_confirmation'):
            install.uninstall(browser=browser,**config)
        assert chrome['manifest'].is_file()
        with pytest.raises(ValueError,match='shared_confirmation'):
            setup.manage('remove',[browser],**config)
    # Report both affected browsers even if only one was requested.
    assert setup.manage('connect',['brave'],**config)=={'brave':'connected','chrome':'connected'}
    assert setup.manage('remove',['chrome','brave'],**config)=={'chrome':'removed','brave':'removed'}
    assert not chrome['manifest'].exists()
    assert config['executable'].is_file()
    assert setup.manage('connect',['chrome','brave'],**config)=={'chrome':'connected','brave':'connected'}
    assert setup.manage('remove',['brave'],shared_disconnect=True,**config)=={'brave':'removed','chrome':'removed'}


def test_foreign_shared_manifest_is_preserved_from_either_browser(config):
    host=install.install(browser='brave',**config)['manifest']
    foreign=b'{"foreign":"keep"}\n';host.write_bytes(foreign)
    assert setup.manage('connect',['chrome'],**config)=={'chrome':'conflict','brave':'conflict'}
    assert setup.manage('remove',['chrome','brave'],**config)=={'chrome':'preserved','brave':'preserved'}
    assert host.read_bytes()==foreign


def test_shared_disconnect_keeps_chromium_and_unrelated_pairing(config):
    parent=config['config_parent']
    pairing=parent/'unrelated-state/credentials.json';pairing.parent.mkdir(parents=True)
    pairing.write_bytes(b'fixture private state');pairing.chmod(0o600)
    setup.manage('connect',['chrome','brave','chromium'],**config)
    chromium=install.plan(browser='chromium',**config)[0]['manifest']
    before=chromium.read_bytes()
    setup.manage('remove',['chrome','brave'],**config)
    assert chromium.read_bytes()==before
    assert pairing.read_bytes()==b'fixture private state'
    assert pairing.stat().st_mode & 0o777==0o600


def test_profile_detection_does_not_alias_brave_to_chrome(config):
    parent=config['config_parent']
    (parent/'BraveSoftware/Brave-Browser').mkdir(parents=True)
    assert setup.detected_browsers(parent,'darwin')==['brave']
    (parent/'Google/Chrome').mkdir(parents=True)
    assert setup.detected_browsers(parent,'darwin')==['chrome','brave']
    assert install.host_dir('brave','linux')=='BraveSoftware/Brave-Browser'


def test_mac_dialog_group_is_explicit_and_returns_both():
    calls=[]
    def run(argv,**kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0,stdout='Google Chrome and Brave (shared connection)\n')
    assert setup.choose_browsers(['brave'],'darwin',run)==['chrome','brave']
    script=calls[0][-1]
    assert 'Connecting or disconnecting this item affects both browsers' in script
    assert 'default items {"Google Chrome and Brave (shared connection)"}' in script
    assert setup.choose_browsers(['chrome'],'darwin',lambda *a,**k:SimpleNamespace(returncode=0,stdout='false'))==[]


def test_mac_shared_symlink_is_not_followed(config):
    paths,_=install.plan(browser='chrome',**config)
    host=paths['manifest'];host.parent.mkdir(parents=True, mode=0o700)
    foreign=config['config_parent']/'foreign';foreign.write_text('keep')
    host.symlink_to(foreign)
    assert setup.manage('connect',['brave'],**config)=={'brave':'conflict','chrome':'conflict'}
    assert setup.manage('remove',['chrome','brave'],**config)=={'chrome':'preserved','brave':'preserved'}
    assert host.is_symlink() and foreign.read_text()=='keep'
