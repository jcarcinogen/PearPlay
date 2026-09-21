import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from test_helper_protocol import load, ROOT

class InstallerTests(unittest.TestCase):
    def test_uninstall_does_not_require_runtime_still_present(self):
        m=load('install')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); source=root/'source'
            (source/'helper').mkdir(parents=True);(source/'helper/native.py').write_text('pass')
            (source/'spikes/002-command').mkdir(parents=True);(source/'spikes/002-command/command.py').write_text('pass')
            kwargs=dict(extension_id='a'*32,browser='chrome',config_parent=root/'config',python=Path(sys.executable),source=source)
            paths=m.install(**kwargs)
            (source/'helper/native.py').unlink()
            self.assertEqual(m.uninstall(**kwargs),[])
            self.assertFalse(paths['launcher'].exists())

    def test_cli_installs_executable_launcher_with_persistent_origin_checked_port(self):
        import subprocess
        from test_helper_protocol import request
        import io
        m=load(); installer=load('install')
        with tempfile.TemporaryDirectory() as temporary:
            parent=Path(temporary).resolve()/'isolated'
            args=[sys.executable,str(ROOT/'helper/install.py'),'install','--extension-id','a'*32,'--browser','chrome','--config-parent',str(parent),'--python',sys.executable]
            result=subprocess.run(args,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            launcher=parent/('Google/Chrome' if sys.platform=='darwin' else 'google-chrome')/'NativeMessagingHosts/com.pearplay.helper.launcher'
            self.assertTrue(launcher.exists(),'CLI did not install launcher')
            frames=io.BytesIO()
            m.write_frame(frames,request());m.write_frame(frames,request('status'))
            result=subprocess.run([str(launcher),'chrome-extension://'+'a'*32+'/'],input=frames.getvalue(),capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stderr,b'')
            output=io.BytesIO(result.stdout)
            self.assertTrue(m.read_frame(output)['ok']);self.assertEqual(m.read_frame(output)['state'],'idle')
            self.assertIsNone(m.read_frame(output))
            result=subprocess.run([str(launcher),'chrome-extension://'+'b'*32+'/'],input=frames.getvalue(),capture_output=True,timeout=10)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(result.stdout+result.stderr,b'')
            args[2]='uninstall'
            result=subprocess.run(args,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0)
            self.assertFalse(launcher.exists())

    def test_exact_scoped_install_idempotence_and_preserving_uninstall(self):
        m=load('install')
        with tempfile.TemporaryDirectory() as temporary:
            parent=Path(temporary).resolve()/'isolated'
            kwargs=dict(extension_id='a'*32,browser='chrome',config_parent=parent,python=Path(sys.executable),source=ROOT)
            paths=m.install(**kwargs)
            manifest=json.loads(paths['manifest'].read_text())
            self.assertEqual(manifest['name'],'com.pearplay.helper')
            self.assertEqual(manifest['allowed_origins'],['chrome-extension://'+'a'*32+'/'])
            self.assertEqual(manifest['path'],str(paths['launcher']))
            self.assertEqual(m.install(**kwargs),paths)
            unknown=paths['manifest'].parent/'unknown';unknown.write_text('keep')
            paths['launcher'].write_text('user-modified')
            preserved=m.uninstall(**kwargs)
            self.assertIn('launcher',preserved)
            self.assertFalse(paths['manifest'].exists())
            self.assertEqual(paths['launcher'].read_text(),'user-modified')
            self.assertTrue(unknown.exists())
            self.assertTrue((ROOT/'spikes/002-command/command.py').exists())

    def test_invalid_ids_browsers_symlinks_and_foreign_files_fail_closed(self):
        m=load('install')
        with tempfile.TemporaryDirectory() as temporary:
            parent=Path(temporary).resolve()/'config'
            kwargs=dict(extension_id='a'*32,browser='brave',config_parent=parent,python=Path(sys.executable),source=ROOT)
            for change in [dict(extension_id='A'*32),dict(extension_id='a'*31),dict(browser='chromium')]:
                with self.assertRaises(ValueError): m.install(**(kwargs|change))
            parent.symlink_to(Path(temporary).resolve())
            with self.assertRaises((ValueError,OSError)): m.install(**kwargs)
            parent.unlink()
            paths=m.install(**kwargs)
            paths['manifest'].write_text('foreign')
            with self.assertRaises(ValueError): m.install(**kwargs)
            m.uninstall(**kwargs)
            self.assertEqual(paths['manifest'].read_text(),'foreign')

    def test_darwin_chrome_installs_google_chrome_host_and_uninstalls_owned_files(self):
        m=load('install')
        with tempfile.TemporaryDirectory() as temporary:
            parent=Path(temporary).resolve()/'Application Support'
            kwargs=dict(extension_id='a'*32,browser='chrome',config_parent=parent,python=Path(sys.executable),source=ROOT,platform='darwin')
            paths=m.install(**kwargs)
            folder=parent/'Google/Chrome/NativeMessagingHosts'
            self.assertEqual(paths['manifest'],folder/'com.pearplay.helper.json')
            self.assertEqual(paths['launcher'],folder/'com.pearplay.helper.launcher')
            self.assertNotIn('google-chrome',str(paths['manifest']))
            manifest=json.loads(paths['manifest'].read_text())
            self.assertEqual(manifest['allowed_origins'],['chrome-extension://'+'a'*32+'/'])
            self.assertEqual(manifest['path'],str(paths['launcher']))
            self.assertEqual(stat.S_IMODE(paths['manifest'].stat().st_mode),0o600)
            self.assertEqual(stat.S_IMODE(paths['launcher'].stat().st_mode),0o700)
            self.assertEqual(stat.S_IMODE(folder.stat().st_mode),0o700)
            self.assertEqual(m.uninstall(**kwargs),[])
            self.assertFalse(paths['manifest'].exists())
            self.assertFalse(paths['launcher'].exists())
            self.assertTrue((ROOT/'spikes/002-command/command.py').exists())

    def test_linux_chrome_layout_stays_google_chrome(self):
        m=load('install')
        with tempfile.TemporaryDirectory() as temporary:
            parent=Path(temporary).resolve()/'config'
            kwargs=dict(extension_id='b'*32,browser='chrome',config_parent=parent,python=Path(sys.executable),source=ROOT,platform='linux')
            paths=m.install(**kwargs)
            self.assertEqual(paths['manifest'],parent/'google-chrome/NativeMessagingHosts/com.pearplay.helper.json')
            self.assertEqual(paths['launcher'],parent/'google-chrome/NativeMessagingHosts/com.pearplay.helper.launcher')
            self.assertEqual(stat.S_IMODE(paths['manifest'].stat().st_mode),0o600)
            self.assertEqual(stat.S_IMODE(paths['launcher'].stat().st_mode),0o700)
            self.assertEqual(m.uninstall(**kwargs),[])
            self.assertFalse(paths['manifest'].exists())
            self.assertFalse(paths['launcher'].exists())

    def test_brave_folder_unchanged_on_darwin(self):
        m=load('install')
        parent=Path('/private/tmp')
        paths,_=m.plan(extension_id='c'*32,browser='brave',config_parent=parent,python=Path(sys.executable),source=ROOT,require_runtime=False,platform='darwin')
        self.assertEqual(paths['manifest'],parent/'BraveSoftware/Brave-Browser/NativeMessagingHosts/com.pearplay.helper.json')
