"""Consumer installer flow; OS dialogs are mocked, registration uses real files."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from test_helper_protocol import load


class InstallerJourneyTests(unittest.TestCase):
    def test_first_launch_asks_for_browsers_without_a_maintenance_menu(self):
        app = load('app')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            binary = root/'PearPlayHelper'
            binary.write_text('#!/bin/sh\nexit 0\n')
            binary.chmod(0o700)
            with patch.object(app.setup, 'choose_browsers', return_value=['chrome']) as choose, \
                 patch.object(app.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='')) as menu, \
                 patch.object(app, 'dialog') as dialog:
                result = app.gui({'extension_id': 'a'*32, 'development': True}, root/'config', binary)
            self.assertEqual(result, 0)
            choose.assert_called_once()
            menu.assert_not_called()
            path = root/'config'/app.setup.install.browser_dir('chrome')/'NativeMessagingHosts/com.pearplay.helper.json'
            self.assertEqual(json.loads(path.read_text())['path'], str(binary))
            self.assertIn('Development build', dialog.call_args.args[0])
            self.assertIn('Check connection', dialog.call_args.args[0])
            # Opening again offers maintenance, rather than silently changing registration.
            with patch.object(app.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='')) as menu, \
                 patch.object(app.setup, 'choose_browsers') as choose:
                self.assertEqual(app.gui({'extension_id': 'a'*32}, root/'config', binary), 0)
            menu.assert_called_once()
            choose.assert_not_called()
