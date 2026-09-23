import importlib.util
import plistlib
from pathlib import Path
import tempfile
import unittest
from test_helper_protocol import ROOT

class PackageTests(unittest.TestCase):
    def test_build_identity_and_platform_fail_closed(self):
        path=ROOT/'scripts/build_helper.py'
        self.assertTrue(path.exists(),'packaging pipeline missing')
        spec=importlib.util.spec_from_file_location('build_helper',path)
        build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
        with self.assertRaises(ValueError): build.configuration('a'*31,True,'darwin','arm64')
        with self.assertRaises(ValueError): build.configuration('a'*32,False,'darwin','arm64')
        with self.assertRaises(ValueError): build.configuration('a'*32,True,'win32','AMD64')
        config=build.configuration('a'*32,True,'darwin','arm64')
        self.assertEqual(config['extension_id'],'a'*32)
        self.assertTrue(config['development'])
        self.assertEqual(config['arch'],'arm64')
        command=build.freeze_command(Path('/build/output'),None)
        self.assertIn('--onedir',command)
        self.assertIn('--collect-all',command)
        self.assertIn('pyatv',command)
        self.assertIn('--recursive-copy-metadata',command)
        self.assertIn(str(ROOT/'helper/app.py'),command)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); payload=root/'binary'; payload.mkdir()
            (payload/'PearPlayHelper').write_text('test payload')
            (payload/'_internal').mkdir();(payload/'_internal/libpython.dylib').write_text('runtime')
            staged=build.stage_payload(payload,root/'stage',config)
            info=plistlib.loads((staged/'Applications/PearPlay Setup.app/Contents/Info.plist').read_bytes())
            self.assertEqual(info['CFBundleExecutable'],'PearPlayHelper')
            self.assertIn('NSLocalNetworkUsageDescription',info)
            self.assertTrue((staged/'Applications/PearPlay Setup.app/Contents/Frameworks/libpython.dylib').is_file())
            self.assertTrue((staged/'Applications/PearPlay Setup.app/Contents/MacOS/PearPlayHelper').is_file())
            linux=build.configuration('a'*32,True,'linux','x86_64')
            staged=build.stage_payload(payload,root/'linux',linux)
            self.assertTrue((staged/'opt/pearplay/PearPlayHelper/PearPlayHelper').is_file())
            desktop=(staged/'usr/share/applications/pearplay-setup.desktop').read_text()
            self.assertIn('Exec=/opt/pearplay/PearPlayHelper/PearPlayHelper',desktop)
            self.assertIn('Terminal=false',desktop)
