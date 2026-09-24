"""Mac terminal installer: real files; no default user-profile writes."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from test_helper_protocol import ROOT


def module():
    path = ROOT/'scripts/macos_setup.py'
    spec = importlib.util.spec_from_file_location('macos_setup', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class MacTerminalTests(unittest.TestCase):
    def test_registration_preflight_refuses_foreign_host_before_downloading(self):
        m=module()
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            parent=root/'config'
            host=parent/'Google/Chrome/NativeMessagingHosts/com.pearplay.helper.json'
            host.parent.mkdir(parents=True)
            host.write_text('foreign registration')
            run=Mock()
            with self.assertRaises(ValueError):
                m.configure({'extension_id':'a'*32,'version':'0.2.3'}, root/'download', root/'data', parent, '/uv', 'install', run)
            run.assert_not_called()
            self.assertFalse((root/'data').exists())
            self.assertEqual(host.read_text(), 'foreign registration')

    def test_symlinked_runtime_is_never_modified(self):
        m=module()
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); source=root/'download'; source.mkdir()
            config={'extension_id':'a'*32,'version':'0.2.3'}
            (source/'terminal-build.json').write_text(json.dumps(config))
            for name in m.PAYLOAD:
                p=source/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('fixture')
            runtime=root/'data/0.2.3'; runtime.mkdir(parents=True)
            (runtime/'.pearplay-runtime.json').write_text(json.dumps(config))
            foreign=root/'foreign'; (foreign/'bin').mkdir(parents=True)
            (foreign/'bin/python').write_text('#!/bin/sh\nexit 0\n'); (foreign/'bin/python').chmod(0o700)
            (runtime/'venv').symlink_to(foreign, target_is_directory=True)
            run=Mock()
            with self.assertRaises(ValueError):
                m.configure(config,source,root/'data',root/'config','/uv','install',run)
            run.assert_not_called()

    def test_payload_staging_is_repeatable_and_preserves_changed_files(self):
        self.assertTrue((ROOT/'scripts/macos_setup.py').exists(), 'terminal setup is missing')
        m = module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root/'download'; source.mkdir()
            (source/'terminal-build.json').write_text(json.dumps({'extension_id':'a'*32, 'version':'0.2.3', 'development':True}))
            for name in m.PAYLOAD:
                path=source/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('fixture')
            destination = root/'installed'
            m.stage(source, destination)
            m.stage(source, destination)
            changed = destination/'helper/native.py'
            changed.write_text('user changes')
            with self.assertRaises(ValueError): m.stage(source, destination)
            self.assertEqual(changed.read_text(), 'user changes')
            other = root/'foreign'; other.mkdir(); (other/'keep').write_text('untouched')
            with self.assertRaises(ValueError): m.stage(source, other)
            self.assertEqual((other/'keep').read_text(), 'untouched')

    def test_main_reports_browser_data_permission_denial_without_claiming_conflict(self):
        m=module()
        import contextlib
        import io
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            (root/'terminal-build.json').write_text(json.dumps({'extension_id':'a'*32,'version':'0.2.3'}))
            err=io.StringIO()
            with patch.object(m, 'ROOT', root), patch.object(m.sys, 'platform', 'darwin'), patch.object(m.os, 'getuid', return_value=501), patch.object(m.install, 'directory', side_effect=PermissionError(1, 'Operation not permitted', 'private-filename')), contextlib.redirect_stderr(err):
                code=m.main(['remove','--uv','/uv','--data-home',str(root/'runtime'),'--config-parent',str(root/'browser')])
            self.assertEqual(code, 1)
            self.assertIn('permission',err.getvalue().lower())
            self.assertIn('errno=1',err.getvalue())
            self.assertIn('App Data',err.getvalue())
            self.assertNotIn('another helper',err.getvalue())
            self.assertNotIn('private-filename',err.getvalue())
            self.assertFalse((root/'runtime').exists())
