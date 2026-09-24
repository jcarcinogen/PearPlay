import importlib.util
import plistlib
from pathlib import Path
import tempfile
import unittest
from test_helper_protocol import ROOT

class PackageTests(unittest.TestCase):
    def test_linux_stage_has_public_readonly_modes_under_restrictive_umask(self):
        import os
        import stat
        spec=importlib.util.spec_from_file_location('build_helper',ROOT/'scripts/build_helper.py')
        assert spec is not None and spec.loader is not None
        build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            previous=os.umask(0o077)
            try:
                payload=root/'payload';payload.mkdir()
                binary=payload/'PearPlayHelper';binary.write_text('executable');binary.chmod(0o700)
                internal=payload/'_internal';internal.mkdir()
                (internal/'build.json').write_text('{}')
                outside=root/'outside';outside.write_text('untouched');outside.chmod(0o600)
                (internal/'link').symlink_to(outside)
                stage=build.stage_payload(payload,root/'stage',{'platform':'linux'})
            finally:
                os.umask(previous)
            for path in [stage,*stage.rglob('*')]:
                if path.is_symlink(): continue
                expected=0o755 if path.is_dir() or path.name=='PearPlayHelper' else 0o644
                self.assertEqual(stat.S_IMODE(path.stat().st_mode),expected,str(path.relative_to(stage)))
            self.assertEqual(stat.S_IMODE(outside.stat().st_mode),0o600)
            self.assertEqual(stat.S_IMODE(binary.stat().st_mode),0o700)

    def test_macos_stage_keeps_native_bundle_resources_out_of_code_directories(self):
        spec=importlib.util.spec_from_file_location('build_helper',ROOT/'scripts/build_helper.py')
        assert spec is not None and spec.loader is not None
        build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            payload=root/'PearPlayHelper';payload.mkdir()
            (payload/'PearPlayHelper').write_text('executable')
            (payload/'_internal').mkdir()
            (payload/'THIRD_PARTY_LICENSES').mkdir()
            (payload/'THIRD_PARTY_LICENSES/LICENSE').write_text('license')
            (payload/'dependency-versions.json').write_text('{}')
            native=root/'PearPlay Setup.app/Contents'
            (native/'MacOS').mkdir(parents=True)
            (native/'MacOS/PearPlayHelper').write_text('executable')
            (native/'Resources').mkdir()
            (native/'Resources/build.json').write_text('{}')
            (native/'Frameworks').mkdir()
            (native/'Frameworks/build.json').symlink_to('../Resources/build.json')
            (native/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'com.pearplay.helper'}))
            stage=build.stage_payload(payload,root/'stage',{'platform':'darwin'})
            contents=stage/'Applications/PearPlay Setup.app/Contents'
            self.assertTrue((contents/'Resources/THIRD_PARTY_LICENSES/LICENSE').is_file(),
                            'License/data files belong in Resources, not code-signing directories')
            self.assertFalse((contents/'MacOS/THIRD_PARTY_LICENSES').exists())
            self.assertTrue((contents/'Frameworks/build.json').is_symlink())
            self.assertEqual((contents/'Frameworks/build.json').read_text(),'{}')
            self.assertEqual(plistlib.loads((contents/'Info.plist').read_bytes()),
                             {'CFBundleIdentifier':'com.pearplay.helper'})

    def test_build_identity_and_platform_fail_closed(self):
        path=ROOT/'scripts/build_helper.py'
        self.assertTrue(path.exists(),'packaging pipeline missing')
        spec=importlib.util.spec_from_file_location('build_helper',path)
        assert spec is not None and spec.loader is not None
        build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
        with self.assertRaises(ValueError): build.configuration('a'*31,True,'darwin','arm64')
        with self.assertRaises(ValueError): build.configuration('a'*32,False,'darwin','arm64')
        with self.assertRaises(ValueError): build.configuration('a'*32,True,'win32','AMD64')
        config=build.configuration('a'*32,True,'darwin','arm64')
        self.assertEqual(config['extension_id'],'a'*32)
        self.assertTrue(config['development'])
        self.assertEqual(config['arch'],'arm64')
        self.assertEqual(build.linux_dependencies('deb', '2.39'), 'zenity, avahi-utils, libc6 (>= 2.39)')
        self.assertEqual(build.linux_dependencies('arch', '2.44'), "'glibc>=2.44' 'zenity' 'avahi'")
        self.assertEqual(build.linux_dependencies('rpm', '2.39'), 'zenity, avahi-tools, glibc >= 2.39')
        with self.assertRaises(ValueError): build.linux_dependencies('deb', '')
        command=build.freeze_command(Path('/build/output'),None)
        self.assertIn('--onedir',command)
        self.assertIn('--collect-all',command)
        self.assertIn('pyatv',command)
        self.assertIn('--recursive-copy-metadata',command)
        self.assertIn(str(ROOT/'helper/app.py'),command)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            components=build.macos_components(root)
            entry=plistlib.loads(components.read_bytes())[0]
            self.assertEqual(entry['RootRelativeBundlePath'], 'Applications/PearPlay Setup.app')
            self.assertFalse(entry['BundleIsRelocatable'])
            self.assertEqual(entry['BundleOverwriteAction'], 'upgrade')
            payload=root/'binary'; payload.mkdir()
            (payload/'PearPlayHelper').write_text('test payload')
            (payload/'_internal').mkdir();(payload/'_internal/libpython.dylib').write_text('runtime')
            bundles=[]
            def bundle(coll, **options):
                bundles.append(options)
            exec(build.macos_bundle_spec(),{'coll':object(),'BUNDLE':bundle})
            self.assertEqual(bundles[0]['bundle_identifier'],'com.pearplay.helper')
            self.assertEqual(bundles[0]['name'],'PearPlay Setup.app')
            self.assertIn('NSLocalNetworkUsageDescription',bundles[0]['info_plist'])
            self.assertEqual(bundles[0]['info_plist']['NSBonjourServices'],['_airplay._tcp'])
            self.assertEqual(bundles[0]['info_plist']['CFBundleVersion'],build.VERSION)
            linux=build.configuration('a'*32,True,'linux','x86_64')
            staged=build.stage_payload(payload,root/'linux',linux)
            self.assertTrue((staged/'opt/pearplay/PearPlayHelper/PearPlayHelper').is_file())
            desktop=(staged/'usr/share/applications/pearplay-setup.desktop').read_text()
            self.assertIn('Exec=/opt/pearplay/PearPlayHelper/PearPlayHelper',desktop)
            self.assertIn('Terminal=false',desktop)
