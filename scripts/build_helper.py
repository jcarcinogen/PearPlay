"""Build Linux helpers on Linux. Mac support is coming soon; Mac internals are archived."""
import argparse
import base64
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from helper.native import VERSION

def stage_payload(payload, stage, config):
    stage=Path(stage);stage.mkdir(parents=True,exist_ok=False)
    if config['platform']=='darwin':
        app=stage/'Applications/PearPlay Setup.app'
        # Let PyInstaller BUNDLE separate code/data and preserve its cross-links.
        # Hand-wrapping onedir puts dist-info/licenses in signing code directories.
        shutil.copytree(Path(payload).parent/'PearPlay Setup.app',app,symlinks=True)
        resources=app/'Contents/Resources'
        shutil.copytree(payload/'THIRD_PARTY_LICENSES',resources/'THIRD_PARTY_LICENSES')
        shutil.copy2(payload/'dependency-versions.json',resources/'dependency-versions.json')
    else:
        shutil.copytree(payload,stage/'opt/pearplay/PearPlayHelper',symlinks=True)
        shutil.copy2(ROOT/'LICENSE',stage/'opt/pearplay/PearPlayHelper/LICENSE')
        desktop=stage/'usr/share/applications/pearplay-setup.desktop';desktop.parent.mkdir(parents=True)
        desktop.write_text('[Desktop Entry]\nType=Application\nName=PearPlay Setup\nComment=Connect browsers to PearPlay Helper\nExec=/opt/pearplay/PearPlayHelper/PearPlayHelper\nIcon=pearplay\nTerminal=false\nCategories=AudioVideo;Settings;\n')
        icon=stage/'usr/share/icons/hicolor/128x128/apps/pearplay.png';icon.parent.mkdir(parents=True)
        shutil.copy2(ROOT/'extension/icons/icon128.png',icon)
        # System packages become root-owned: build umask must not hide the runtime.
        # Change only staged objects, never symlink targets or the source payload.
        for path in [stage, *stage.rglob('*')]:
            if not path.is_symlink():
                path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)
    return stage


def freeze_command(output, identity):
    argv=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--name','PearPlayHelper',
          '--distpath',str(output/'frozen'),'--workpath',str(output/'work'),'--specpath',str(output),
          '--paths',str(ROOT),'--collect-all','pyatv','--recursive-copy-metadata','pyatv',
          '--add-data',str(ROOT/'spikes/001-airplay/pearplay.py')+':spikes/001-airplay',
          '--add-data',str(ROOT/'spikes/002-command/command.py')+':spikes/002-command',
          '--add-data',str(output/'build.json')+':.']
    if identity: argv += ['--codesign-identity',identity]
    return argv+[str(ROOT/'helper/app.py')]


def macos_bundle_spec():
    info=dict(CFBundleDisplayName='PearPlay Setup', CFBundleVersion=VERSION,
              NSLocalNetworkUsageDescription='PearPlay finds and connects to AirPlay TVs on your local network.',
              NSBonjourServices=['_airplay._tcp'], LSMinimumSystemVersion='12.0')
    # Keep the console bootloader: native messaging requires inherited stdin/stdout.
    return f"\napp = BUNDLE(coll, name='PearPlay Setup.app', bundle_identifier='com.pearplay.helper', version={VERSION!r}, info_plist={info!r})\n"


def configuration(extension_id, development, target, machine):
    if not isinstance(extension_id,str) or not re.fullmatch(r'[a-p]{32}',extension_id): raise ValueError('invalid_extension_id')
    if target not in ('darwin','linux') or machine not in ('arm64','aarch64','x86_64'): raise ValueError('unsupported_build_host')
    if not development:
        catalog=json.loads((ROOT/'extension/releases.json').read_text())
        if catalog.get('extensionId')!=extension_id or not (ROOT/'LICENSE').is_file():
            raise ValueError('release_requires_store_id_and_project_license')
        try:
            key=json.loads((ROOT/'extension/manifest.json').read_text())['key']
            digest=hashlib.sha256(base64.b64decode(key,validate=True)).hexdigest()[:32]
        except (KeyError,TypeError,ValueError) as error:
            raise ValueError('invalid_store_public_key') from error
        derived=''.join(chr(ord('a')+int(n,16)) for n in digest)
        if derived!=extension_id:
            raise ValueError('store_public_key_id_mismatch')
    return dict(extension_id=extension_id,development=development,version=VERSION,platform=target,arch='arm64' if machine in ('arm64','aarch64') else 'x86_64')


def macos_components(output):
    # Native manifests use /Applications. Never relocate an update to a stray
    # extracted test bundle or merge obsolete runtime files into the new app.
    path = Path(output)/'components.plist'
    path.write_bytes(plistlib.dumps([dict(
        RootRelativeBundlePath='Applications/PearPlay Setup.app',
        BundleIsRelocatable=False, BundleIsVersionChecked=True,
        BundleHasStrictIdentifier=True, BundleOverwriteAction='upgrade')]))
    return path


def linux_dependencies(format, libc):
    if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', libc):
        raise ValueError('unknown_glibc_baseline')
    return {'deb': f'zenity, avahi-utils, libc6 (>= {libc})',
            'arch': f"'glibc>={libc}' 'zenity' 'avahi'",
            'rpm': f'zenity, avahi-tools, glibc >= {libc}'}[format]


def build(args):
    if sys.platform != 'linux':
        raise ValueError('PearPlay is Linux only. Mac support is coming soon.')
    config=configuration(args.extension_id,args.development,sys.platform,platform.machine())
    output=args.output.expanduser().absolute()
    if output.is_relative_to(ROOT) or '%' in str(output) or '\n' in str(output): raise ValueError('use_machine_local_build_output')
    if not args.development and sys.platform=='darwin' and not all((args.sign_app,args.sign_installer,args.notary_profile)):
        raise ValueError('mac_release_requires_signing_and_notarization')
    output.mkdir(parents=True,exist_ok=False)
    (output/'build.json').write_text(json.dumps(config))
    subprocess.run(freeze_command(output,args.sign_app),check=True,cwd=output)
    if sys.platform=='darwin':
        spec=output/'PearPlayHelper.spec'
        spec.write_text(spec.read_text()+macos_bundle_spec())
        # Reuse the completed analysis/EXE; BUNDLE supplies Apple's code/data layout.
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm',
                        '--distpath',str(output/'frozen'),'--workpath',str(output/'work'),
                        str(spec)],check=True,cwd=output)
    payload=output/'frozen/PearPlayHelper'
    licenses=payload/'THIRD_PARTY_LICENSES';licenses.mkdir()
    versions={}
    for dist in importlib.metadata.distributions():
        name=dist.metadata['Name'];versions[name]=dist.version
        for file in dist.files or []:
            if any(part.lower().startswith(('license','copying')) for part in file.parts):
                source=Path(dist.locate_file(file))
                if source.is_file():
                    destination=licenses/re.sub(r'[^A-Za-z0-9_.-]','_',name)/Path(file).name
                    destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
    shutil.copy2(ROOT/'spikes/002-command/LICENSE.md',licenses/'airplay-adapter.md')
    (payload/'dependency-versions.json').write_text(json.dumps(versions,indent=2)+'\n')
    smoke=subprocess.run([str(payload/'PearPlayHelper'),'self-test'],check=True,capture_output=True,text=True)
    (output/'smoke.json').write_text(smoke.stdout)
    stage=stage_payload(payload,output/'stage',config)
    staged_binary=stage/('Applications/PearPlay Setup.app/Contents/MacOS/PearPlayHelper' if sys.platform=='darwin' else 'opt/pearplay/PearPlayHelper/PearPlayHelper')
    subprocess.run([str(staged_binary),'self-test'],check=True,capture_output=True,text=True)
    label=f"pearplay-helper-{VERSION}-{config['platform']}-{config['arch']}"+('-development' if args.development else '')
    artifacts=[];unavailable=[]
    if sys.platform=='darwin':
        app=stage/'Applications/PearPlay Setup.app'
        # Seal Info.plist and the added license resources even in local test builds.
        # Ad-hoc is local development only; release credentials are required above.
        sign=['codesign','--force','--sign',args.sign_app or '-','--identifier','com.pearplay.helper']
        if args.sign_app: sign += ['--options','runtime','--timestamp']
        subprocess.run(sign+[str(app)],check=True)
        subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
        subprocess.run([str(staged_binary),'self-test'],check=True,capture_output=True,text=True)
        target=output/(label+'.pkg')
        cmd=['pkgbuild','--root',str(stage),'--component-plist',str(macos_components(output)),'--identifier','com.pearplay.helper'+('.development' if args.development else ''),'--version',VERSION,'--install-location','/']
        if args.sign_installer: cmd += ['--sign',args.sign_installer]
        subprocess.run(cmd+[str(target)],check=True)
        if args.notary_profile:
            subprocess.run(['xcrun','notarytool','submit',str(target),'--keychain-profile',args.notary_profile,'--wait'],check=True)
            subprocess.run(['xcrun','stapler','staple',str(target)],check=True)
            subprocess.run(['xcrun','stapler','validate',str(target)],check=True)
            subprocess.run(['spctl','--assess','--type','install',str(target)],check=True)
        artifacts.append(target)
    else:
        # Build with native package tools; unavailable formats remain explicit release gates.
        if shutil.which('dpkg-deb'):
            control=stage/'DEBIAN';control.mkdir()
            arch='arm64' if config['arch']=='arm64' else 'amd64'
            libc=platform.libc_ver()[1]
            (control/'control').write_text(f'Package: pearplay-helper\nVersion: {VERSION}\nArchitecture: {arch}\nMaintainer: PearPlay project\nDepends: {linux_dependencies("deb", libc)}\nDescription: PearPlay native helper and browser setup\n')
            target=output/(label+'.deb')
            subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(target)],check=True)
            artifacts.append(target);shutil.rmtree(control)
        else: unavailable.append('deb: dpkg-deb unavailable; build on supported Debian/Ubuntu baseline')
        if shutil.which('makepkg'):
            work=output/'arch';work.mkdir()
            arch='aarch64' if config['arch']=='arm64' else 'x86_64'
            (work/'PKGBUILD').write_text(f"pkgname=pearplay-helper\npkgver={VERSION}\npkgrel=1\npkgdesc='PearPlay helper and browser setup'\narch=('{arch}')\nurl='https://github.com/jcarcinogen/PearPlay'\nlicense=('MIT')\ndepends=({linux_dependencies('arch', platform.libc_ver()[1])})\noptions=('!strip' '!debug')\npackage() {{ cp -a \"$startdir/../stage/.\" \"$pkgdir/\"; }}\n")
            subprocess.run(['makepkg','--nodeps','--noconfirm'],check=True,cwd=work)
            for package in work.glob('*.pkg.tar.zst'):
                target=output/(label+'.pkg.tar.zst');shutil.copy2(package,target);artifacts.append(target)
        else: unavailable.append('arch: makepkg unavailable')
        if shutil.which('rpmbuild'):
            top=output/'rpm'
            for folder in ('BUILD','BUILDROOT','RPMS','SOURCES','SPECS','SRPMS'): (top/folder).mkdir(parents=True,exist_ok=True)
            spec=top/'SPECS/pearplay.spec'
            spec.write_text(f'Name: pearplay-helper\nVersion: {VERSION}\nRelease: 1\nSummary: PearPlay helper and browser setup\nLicense: MIT\nRequires: {linux_dependencies("rpm", platform.libc_ver()[1])}\nAutoReqProv: no\n%description\nPearPlay native helper. Connect browsers by opening PearPlay Setup.\n%install\nmkdir -p "%{{buildroot}}"\ncp -a "{stage}/." "%{{buildroot}}/"\n%files\n/opt/pearplay\n/usr/share/applications/pearplay-setup.desktop\n/usr/share/icons/hicolor/128x128/apps/pearplay.png\n')
            subprocess.run(['rpmbuild','--define',f'_topdir {top}','--define','__os_install_post %{nil}','-bb',str(spec)],check=True)
            for package in (top/'RPMS').rglob('*.rpm'):
                target=output/(label+'.rpm');shutil.copy2(package,target);artifacts.append(target)
        else: unavailable.append('rpm: rpmbuild unavailable; build on supported Fedora baseline')
    report=dict(config,artifacts=[dict(file=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in artifacts],unavailable=unavailable,notarized=bool(args.notary_profile),network_tested=False)
    (output/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if artifacts else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extension-id',required=True)
    parser.add_argument('--development',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--sign-app')
    parser.add_argument('--sign-installer')
    parser.add_argument('--notary-profile')
    args=parser.parse_args()
    try:
        return build(args)
    except ValueError as error:
        parser.exit(2, str(error)+'\n')

if __name__=='__main__': raise SystemExit(main())
