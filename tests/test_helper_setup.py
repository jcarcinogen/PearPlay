"""Packaged native-host registration, isolated from actual browser profiles."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from test_helper_protocol import load, ROOT

class SetupTests(unittest.TestCase):
    def test_packaged_helper_is_shared_and_repair_preserves_foreign_files(self):
        installer = load('install')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            binary = root/'PearPlayHelper'
            binary.write_text('#!/bin/sh\nexit 0\n')
            binary.chmod(0o700)
            common = dict(extension_id='a'*32, config_parent=root/'config', executable=binary)
            registrations = []
            for browser in ('chrome', 'brave', 'chromium'):
                paths = installer.install(browser=browser, **common)
                registrations.append(paths['manifest'])
                self.assertEqual(set(paths), {'manifest'})
                self.assertEqual(json.loads(paths['manifest'].read_text())['path'], str(binary))
                self.assertEqual(installer.install(browser=browser, **common), paths)
            registrations[0].unlink()
            installer.install(browser='chrome', **common)
            registrations[1].write_text('foreign')
            with self.assertRaises(ValueError): installer.install(browser='brave', **common)
            self.assertEqual(installer.uninstall(browser='brave', **common), ['manifest'])
            for browser in ('chrome', 'chromium'):
                self.assertEqual(installer.uninstall(browser=browser, **common), [])
            self.assertTrue(binary.exists())
            self.assertEqual(registrations[1].read_text(), 'foreign')

    def test_browser_selection_is_user_scoped_and_remove_keeps_other_browsers(self):
        setup = load('setup')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            binary = root/'PearPlayHelper'; binary.write_text('#!/bin/sh\nexit 0\n'); binary.chmod(0o700)
            parent = root/'config'
            (parent/'google-chrome').mkdir(parents=True)
            self.assertEqual(setup.detected_browsers(parent, 'linux'), ['chrome'])
            kwargs = dict(extension_id='a'*32, executable=binary, config_parent=parent, platform='linux')
            result = setup.manage('connect', ['chrome', 'brave'], **kwargs)
            self.assertEqual(result, {'chrome': 'connected', 'brave': 'connected'})
            self.assertEqual(setup.manage('remove', ['chrome'], **kwargs), {'chrome': 'removed'})
            self.assertTrue((parent/'BraveSoftware/Brave-Browser/NativeMessagingHosts/com.pearplay.helper.json').is_file())
            with self.assertRaises(ValueError): setup.manage('connect', ['edge'], **kwargs)
            with self.assertRaises(ValueError): setup.manage('connect', [], **kwargs)

    def test_native_dialogs_use_detected_defaults_and_cancel_without_changes(self):
        setup = load('setup')
        from types import SimpleNamespace
        calls=[]
        def run(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0,stdout='chrome|chromium\n')
        self.assertEqual(setup.choose_browsers(['chrome'],'linux',run), ['chrome','chromium'])
        self.assertIn('--checklist',calls[0])
        self.assertIn('TRUE',calls[0])
        self.assertEqual(setup.choose_browsers([], 'darwin', lambda *a,**k:SimpleNamespace(returncode=1,stdout='')), [])

    def test_app_rejects_unconfigured_store_id_before_registering(self):
        app=load('app')
        self.assertFalse(app.valid_build({'extension_id':None}))
        self.assertTrue(app.valid_build({'extension_id':'a'*32}))
        self.assertFalse(app.valid_build({'extension_id':'A'*32}))
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            result=app.main(['connect','--browsers','chrome','--config-parent',str(root)], config={'extension_id':None})
            self.assertNotEqual(result,0)
            self.assertEqual(list(root.iterdir()),[])

    def test_chromium_registration_on_both_platforms(self):
        installer = load('install')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for platform, folder in [('darwin', 'Chromium'), ('linux', 'chromium')]:
                with self.subTest(platform=platform):
                    args = dict(extension_id='a'*32, browser='chromium', config_parent=root/platform,
                                python=Path(sys.executable), source=ROOT, platform=platform)
                    paths = installer.install(**args)
                    self.assertEqual(paths['manifest'].parent, root/platform/folder/'NativeMessagingHosts')
                    self.assertEqual(installer.uninstall(**args), [])
