"""Mac previews reopened; production trust gate and historical installer stay closed."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_helper_protocol import ROOT


def load_script(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class PlatformScopeTests(unittest.TestCase):
    def test_mac_production_requires_signing_and_notarization_before_output(self):
        module=load_script('build_helper')
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'output'
            args=SimpleNamespace(extension_id='eoadahoncjfpnennmkjifohclbafjkol',development=False,output=output,sign_app=None,sign_installer=None,notary_profile=None)
            with patch.object(module.sys,'platform','darwin'),patch.object(module.platform,'machine',return_value='arm64'),patch.object(module.subprocess,'run') as run:
                with self.assertRaisesRegex(ValueError,'mac_release_requires_signing_and_notarization'):
                    module.build(args)
                run.assert_not_called()
            self.assertFalse(output.exists())

    def test_mac_development_reaches_freeze_without_release_credentials(self):
        module=load_script('build_helper')
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'output'
            args=SimpleNamespace(extension_id='eoadahoncjfpnennmkjifohclbafjkol',development=True,output=output,sign_app=None,sign_installer=None,notary_profile=None)
            with patch.object(module.sys,'platform','darwin'),patch.object(module.platform,'machine',return_value='arm64'),patch.object(module.subprocess,'run',side_effect=RuntimeError('freeze reached')) as run:
                with self.assertRaisesRegex(RuntimeError,'freeze reached'):
                    module.build(args)
                self.assertIn('PyInstaller',run.call_args.args[0])
            self.assertTrue(output.is_dir())

    def test_mac_terminal_install_redirects_before_reading_build_or_downloading(self):
        module=load_script('macos_setup');error=io.StringIO()
        with patch.object(module.sys,'platform','darwin'),patch.object(module.os,'getuid',return_value=501),patch.object(module,'configure') as configure,contextlib.redirect_stderr(error):
            result=module.main(['--uv','/does-not-exist'])
        self.assertEqual(result,2);configure.assert_not_called()
        self.assertIn('packaged PearPlay Setup.app Mac preview',error.getvalue())

    def test_shell_entry_stops_before_uv_or_network(self):
        result=subprocess.run(['/bin/bash',str(ROOT/'install-macos.sh')],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('packaged PearPlay Setup.app Mac preview',result.stderr)
        self.assertNotIn('Install uv',result.stderr)
