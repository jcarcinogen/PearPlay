"""Paused Mac entry points fail before downloads, registration or build output."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
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
    def test_mac_package_build_is_paused_before_accessing_output(self):
        module=load_script('build_helper')
        with patch.object(module.sys,'platform','darwin'),patch.object(module.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'Mac support is coming soon'):
                module.build(SimpleNamespace())
            run.assert_not_called()

    def test_mac_terminal_install_is_paused_before_reading_build_or_downloading(self):
        module=load_script('macos_setup');error=io.StringIO()
        with patch.object(module.sys,'platform','darwin'),patch.object(module.os,'getuid',return_value=501),patch.object(module,'configure') as configure,contextlib.redirect_stderr(error):
            result=module.main(['--uv','/does-not-exist'])
        self.assertEqual(result,2);configure.assert_not_called()
        self.assertIn('Mac support is coming soon.',error.getvalue())

    def test_shell_entry_stops_before_uv_or_network(self):
        result=subprocess.run(['/bin/bash',str(ROOT/'install-macos.sh')],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('Mac support is coming soon.',result.stderr)
        self.assertNotIn('Install uv',result.stderr)
