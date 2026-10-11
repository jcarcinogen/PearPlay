"""Build an unsigned self-contained Windows preview on Windows x64.

No cross-compilation claim: inventory works on any OS; build requires Windows.
Uses PyInstaller already present in an isolated environment, never installs it.
Outputs windowed native host, maintenance and setup executables; inherited pipes retain native messaging.
"""
import argparse
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sysconfig
from types import SimpleNamespace
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from helper.native import VERSION, read_frame
from helper.windows_setup import EXTENSION_ID, encoded, payload_files
from scripts.build_helper import license_inventory


def collect_licenses(payload, distributions=None, python_license=None):
    """Reuse the Mac collector, with fail-closed Windows destination checks."""
    selected = []
    destinations = set()
    for dist in importlib.metadata.distributions() if distributions is None else distributions:
        name = re.sub(r'[^A-Za-z0-9_.-]', '_', dist.metadata['Name'])
        if name in ('', '.', '..'):
            raise ValueError('unsafe_notice_distribution_name')
        files = []
        for file in dist.files or []:
            relative = Path(str(file))
            if (relative.is_absolute() or '..' in relative.parts
                    or not re.match(r'^(license|copying|notice|authors)(?:$|[._-])', relative.name, re.I)
                    or relative.suffix.lower() in ('.py', '.pyc', '.pyd')):
                continue
            destination = (Path(name)/relative).as_posix().casefold()
            if destination in destinations:
                raise ValueError('notice_destination_collision')
            destinations.add(destination)
            files.append(file)
        selected.append(SimpleNamespace(metadata=dist.metadata, version=dist.version,
                                        files=files, locate_file=dist.locate_file))
    if python_license is None:
        candidates = [Path(sys.base_prefix)/'LICENSE.txt', Path(sysconfig.get_path('stdlib'))/'LICENSE.txt']
        python_license = next((p for p in candidates if p.is_file()), None)
    if python_license is None or not Path(python_license).is_file():
        raise ValueError('missing_python_runtime_license')
    return license_inventory(payload, selected, python_license)


def build_source_snapshot():
    """Capture exact inputs BEFORE freezing, including both builders and tests."""
    paths = [*(p for p in (ROOT/'helper').glob('*.py') if not p.name.startswith('._')),
             *(p for p in (ROOT/'tests').glob('test_windows*.py') if not p.name.startswith('._')),
             ROOT/'scripts/build_windows_helper.py', ROOT/'scripts/build_windows_helper.ps1',
             ROOT/'scripts/build_helper.py', ROOT/'scripts/windows_gui_smoke.py', ROOT/'spikes/001-airplay/pearplay.py',
             ROOT/'spikes/002-command/command.py', ROOT/'spikes/002-command/LICENSE.md',
             ROOT/'spikes/002-command/requirements.txt', ROOT/'requirements.txt', ROOT/'LICENSE',
             ROOT/'assets/store/icon-1024.png', ROOT/'assets/brand/pearplay.ico']
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def environment_snapshot():
    """Hash installed build/test distributions and the Python runtime, not imports.

    Excludes regenerable bytecode; includes wheel metadata, notices, native
    libraries and the base interpreter. No pip/network/install operation.
    """
    paths = {Path(sys.executable).resolve()}
    for dist in importlib.metadata.distributions():
        paths.update(Path(str(dist.locate_file(f))).resolve() for f in dist.files or [])
    base = Path(sys.base_prefix)
    paths.update(p for p in base.rglob('*')
                 if 'site-packages' not in p.parts and '__pycache__' not in p.parts)
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)
            if p.is_file() and p.suffix.lower() not in ('.pyc', '.pyo') and '__pycache__' not in p.parts}


def reject_input_drift(source_hashes, environment_hashes):
    if source_hashes != build_source_snapshot():
        raise ValueError('source_changed_during_build_rebuild_before_acceptance')
    if environment_hashes != environment_snapshot():
        raise ValueError('environment_changed_during_build_rebuild_before_acceptance')


def inventory():
    versions = {}
    for package in ('pyatv','pyinstaller','pytest'):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return dict(platform=sys.platform, machine=platform.machine(), python=platform.python_version(),
                packages=versions, tools={name:shutil.which(name) for name in ('powershell','pwsh','iexpress','signtool')})


def freeze_command(output, entry, name, *, onefile=False, windowed=True, data=()):
    argv = [sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed' if windowed else '--console',
            '--onefile' if onefile else '--onedir','--noupx','--name',name,
            '--icon',str(ROOT/'assets/brand/pearplay.ico'),
            '--distpath',str(output/'frozen'),'--workpath',str(output/('work-'+name)),
            '--specpath',str(output),'--paths',str(ROOT),'--collect-all','pyatv',
            '--recursive-copy-metadata','pyatv']
    if windowed:
        argv.append('--disable-windowed-traceback')
    data = [*data, (ROOT/'assets/brand/pearplay.ico', 'assets/brand'),
            (ROOT/'assets/store/icon-1024.png', 'assets/store')]
    for source, destination in data:
        argv.extend(['--add-data', str(source) + os.pathsep + destination])
    return argv + [str(entry)]


def icon_frames(raw):
    """Read the committed ICO without adding an image-library build dependency."""
    if len(raw) < 6:
        raise ValueError('invalid_brand_icon')
    reserved, kind, count = struct.unpack_from('<HHH', raw)
    if reserved or kind != 1 or not 1 <= count <= 32 or len(raw) < 6 + 16 * count:
        raise ValueError('invalid_brand_icon')
    frames = []
    for index in range(count):
        width, height, colors, reserved, planes, bits, size, offset = struct.unpack_from('<BBBBHHII', raw, 6 + index * 16)
        if reserved or offset < 6 + 16 * count or not size or offset + size > len(raw):
            raise ValueError('invalid_brand_icon_frame')
        frames.append(((width, height, colors, reserved, planes, bits, size), raw[offset:offset + size]))
    return frames


def verify_executable_icon(executable):
    """Fail the build unless every embedded PE icon frame matches our ICO."""
    import pefile  # Already a PyInstaller dependency on Windows.
    raw = (ROOT/'assets/brand/pearplay.ico').read_bytes()
    expected = icon_frames(raw)
    pe = pefile.PE(str(executable))
    try:
        resources = {entry.id: entry for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries}
        groups = resources[14].directory.entries  # RT_GROUP_ICON
        if len(groups) != 1:
            raise ValueError('unexpected_executable_icon_groups')
        images = {entry.id: entry for entry in resources[3].directory.entries}  # RT_ICON
        def resource_bytes(entry):
            leaves = entry.directory.entries
            if len(leaves) != 1:
                raise ValueError('unexpected_executable_icon_languages')
            data = leaves[0].data.struct
            return pe.get_data(data.OffsetToData, data.Size)
        group = resource_bytes(groups[0])
        if len(group) != 6 + 14 * len(expected) or struct.unpack_from('<HHH', group) != (0, 1, len(expected)):
            raise ValueError('executable_icon_directory_mismatch')
        for index, (metadata, pixels) in enumerate(expected):
            actual = struct.unpack_from('<BBBBHHIH', group, 6 + 14 * index)
            if actual[:-1] != metadata or resource_bytes(images[actual[-1]]) != pixels:
                raise ValueError('executable_icon_pixels_mismatch')
        return dict(ico_sha256=hashlib.sha256(raw).hexdigest(),
                    sizes=[metadata[0] or 256 for metadata, _ in expected],
                    embedded_frames_match=True)
    except (AttributeError, KeyError, struct.error) as error:
        raise ValueError('missing_or_invalid_executable_icon') from error
    finally:
        pe.close()


def verify_windowed(executable):
    import pefile
    with pefile.PE(str(executable)) as pe:
        if pe.OPTIONAL_HEADER.Subsystem != 2:
            raise ValueError('gui_installer_is_not_windowed')


def native_smoke(executable):
    origin = 'chrome-extension://' + EXTENSION_ID + '/'
    frame = encoded(dict(v=1,id='build',op='hello',args={}))
    # 0x0a0d puts CR and LF in the length prefix, exercising CRT binary mode.
    frame += b' ' * (0x0a0d - len(frame))
    packet = struct.pack('<I',len(frame)) + frame
    good = subprocess.run([str(executable),origin,'--parent-window=0'], input=packet, capture_output=True, timeout=30)
    out = io.BytesIO(good.stdout)
    response = read_frame(out)
    if good.returncode or response is None or response.get('helperVersion') != VERSION or response.get('ok') is not True or read_frame(out) is not None or good.stderr:
        raise ValueError('native_smoke_failed')
    # Includes CR/LF and NUL-sensitive payload bytes at framing level; malformed
    # frames produce exactly one bounded sanitized error followed by exit.
    bad = subprocess.run([str(executable),origin,'--parent-window=0'], input=struct.pack('<I',65537), capture_output=True, timeout=30)
    rejected = read_frame(io.BytesIO(bad.stdout))
    if bad.returncode or rejected is None or rejected.get('error') != 'invalid_frame' or bad.stderr:
        raise ValueError('oversize_smoke_failed')
    foreign = subprocess.run([str(executable),'chrome-extension://'+'a'*32+'/', '--parent-window=0'], input=packet, capture_output=True, timeout=30)
    if foreign.returncode != 2 or foreign.stdout or foreign.stderr:
        raise ValueError('origin_smoke_failed')
    override = subprocess.run([str(executable),'chrome-extension://'+'a'*32+'/', '--extension-id', 'a'*32], input=packet, capture_output=True, timeout=30)
    if override.returncode != 2 or override.stdout or override.stderr:
        raise ValueError('compiled_identity_override_smoke_failed')
    return dict(hello=True, binary_crlf_header=True, oversized_frame_rejected=True, foreign_origin_rejected=True, identity_override_rejected=True, eof_exit=True, network='not used')


def build(output):
    tools = inventory()
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64','x86_64'):
        raise ValueError('build_requires_native_windows_x64')
    if tools['packages'].get('pyatv') != '0.18.0' or tools['packages'].get('pyinstaller') != '6.21.0':
        raise ValueError('requires_pyatv_0.18.0_and_pyinstaller_6.21.0_in_isolated_environment')
    output = output.expanduser().resolve()
    if output.is_relative_to(ROOT) or output.exists():
        raise ValueError('use_new_output_directory_outside_source')
    output.mkdir(parents=True)
    (output/'inventory.json').write_bytes(encoded(tools))
    source_hashes = build_source_snapshot()
    environment_hashes = environment_snapshot()
    (output/'source-hashes.json').write_bytes(encoded(source_hashes))
    environment_inputs = dict(scope='Installed build/test environment and Python runtime; not a frozen import inventory',
                              files=environment_hashes)
    (output/'environment-inputs.json').write_bytes(encoded(environment_inputs))
    notices = output/'notices'
    notices.mkdir()
    license_inputs = collect_licenses(notices)
    reject_input_drift(source_hashes, environment_hashes)
    binding = dict(source_manifest_sha256=hashlib.sha256((output/'source-hashes.json').read_bytes()).hexdigest(),
                   environment_manifest_sha256=hashlib.sha256((output/'environment-inputs.json').read_bytes()).hexdigest(),
                   notice_inventory_sha256=hashlib.sha256((notices/'THIRD_PARTY_LICENSES/inventory.json').read_bytes()).hexdigest())
    config = dict(extension_id=EXTENSION_ID, development=False, platform='win32', arch='x86_64', version=VERSION)
    config['build_inputs'] = binding
    (output/'build.json').write_bytes(encoded(config))
    common = [(ROOT/'spikes/001-airplay/pearplay.py','spikes/001-airplay'),
              (ROOT/'spikes/002-command/command.py','spikes/002-command'), (output/'build.json','.')]
    with (output/'helper-freeze.log').open('w', encoding='utf-8') as log:
        subprocess.run(freeze_command(output,ROOT/'helper/app.py','PearPlayHelper',data=common), stdout=log, stderr=subprocess.STDOUT, check=True)
    reject_input_drift(source_hashes, environment_hashes)
    payload = output/'frozen/PearPlayHelper'
    shutil.copytree(notices/'THIRD_PARTY_LICENSES', payload/'THIRD_PARTY_LICENSES')
    shutil.copy2(notices/'dependency-versions.json', payload/'dependency-versions.json')
    shutil.copy2(output/'source-hashes.json', payload/'source-hashes.json')
    shutil.copy2(output/'environment-inputs.json', payload/'environment-inputs.json')
    shutil.copy2(ROOT/'LICENSE',payload/'LICENSE')
    (payload/'build-info.json').write_bytes(encoded(config))
    executable = payload/'PearPlayHelper.exe'
    helper_icon = verify_executable_icon(executable)
    verify_windowed(executable)
    smoke = subprocess.run([str(executable),'self-test'], capture_output=True, text=True, check=True, timeout=60)
    dependency_smoke = json.loads(smoke.stdout)
    if dependency_smoke.get('ok') is not True or dependency_smoke.get('version') != VERSION or smoke.stderr:
        raise ValueError('dependency_smoke_failed')
    protocol_smoke = native_smoke(executable)
    archive_path = output/'windows-payload.zip'
    with zipfile.ZipFile(archive_path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(payload.rglob('*')):
            if source.is_symlink():
                raise ValueError('symlink_in_frozen_payload')
            if source.is_file():
                archive.write(source,source.relative_to(payload).as_posix())
    payload_files(archive_path.read_bytes())
    with (output/'setup-freeze.log').open('w', encoding='utf-8') as log:
        subprocess.run(freeze_command(output,ROOT/'helper/windows_setup.py','PearPlaySetup',onefile=True,
                                     data=[(archive_path,'.')]), stdout=log, stderr=subprocess.STDOUT, check=True)
    reject_input_drift(source_hashes, environment_hashes)
    installer = output/f'pearplay-helper-{VERSION}-windows-x86_64-maintenance.exe'
    shutil.copy2(output/'frozen/PearPlaySetup.exe',installer)
    installer_icon = verify_executable_icon(installer)
    verify_windowed(installer)
    setup_smoke = subprocess.run([str(installer),'self-test'], capture_output=True, text=True, check=True, timeout=60)
    if json.loads(setup_smoke.stdout).get('ok') is not True or setup_smoke.stderr:
        raise ValueError('installer_smoke_failed')
    verify = subprocess.run([str(installer),'verify-payload'], capture_output=True, text=True, check=True, timeout=60)
    embedded = json.loads(verify.stdout)
    if embedded.get('sha256') != hashlib.sha256(archive_path.read_bytes()).hexdigest() or embedded.get('version') != VERSION or verify.stderr:
        raise ValueError('embedded_installer_payload_smoke_failed')
    # Both download names use the same branded windowed routing; no console surfaces.
    with (output/'gui-freeze.log').open('w', encoding='utf-8') as log:
        subprocess.run(freeze_command(output, ROOT/'helper/windows_gui.py', 'PearPlaySetupGUI',
                         onefile=True, windowed=True, data=[(archive_path, '.')]),
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    gui_installer = output/f'pearplay-helper-{VERSION}-windows-x86_64-unsigned.exe'
    shutil.copy2(output/'frozen/PearPlaySetupGUI.exe', gui_installer)
    gui_icon = verify_executable_icon(gui_installer)
    verify_windowed(gui_installer)
    reject_input_drift(source_hashes, environment_hashes)
    # Native fixture tests verify DPAPI/ACLs, sharing lease and setup readbacks.
    environment = dict(os.environ, PEARPLAY_TEST_PAYLOAD=str(archive_path), PEARPLAY_TEST_INSTALLER=str(gui_installer))
    result = subprocess.run([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',
                             *(str(ROOT/'tests'/name) for name in ('test_windows_native.py', 'test_windows_source.py',
                                                                  'test_windows_installer.py', 'test_windows_builder.py', 'test_windows_branding.py')),
                             '--basetemp='+str(output/'test-fixtures')],
                            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=600)
    (output/'native-tests.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
    reject_input_drift(source_hashes, environment_hashes)
    if result.returncode:
        raise ValueError('windows_native_fixture_tests_failed')
    from scripts.windows_gui_smoke import probe
    gui_windows = {name: probe(path, output / ('gui-' + name + '.png'))
                   for name, path in [('native', executable), ('maintenance', installer), ('setup', gui_installer)]}
    reject_input_drift(source_hashes, environment_hashes)
    report = dict(config, source_hashes=source_hashes, input_drift_checks=['before-freeze', 'after-helper-freeze', 'after-setup-freeze', 'after-tests'],
                  licenses=license_inputs, unsigned=True, installer=gui_installer.name, sha256=hashlib.sha256(gui_installer.read_bytes()).hexdigest(),
                  maintenance=dict(file=installer.name, sha256=hashlib.sha256(installer.read_bytes()).hexdigest()),
                  gui=dict(windowed=True, hosted_initial_windows=gui_windows, owner_runtime_tested=False, icon=gui_icon),
                  dependencies=dependency_smoke, native=protocol_smoke, embedded_payload=embedded, windows_fixture_tests=True, installed_frozen_payload_tested=True,
                  icons=dict(helper=helper_icon, installer=installer_icon),
                  chrome_tested=False, receiver_tested=False, security_settings_changed=False)
    (output/'build-report.json').write_bytes(encoded(report))
    print(json.dumps(report,indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',action='store_true')
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    if args.inventory:
        print(json.dumps(inventory(),indent=2))
        return 0
    if args.output is None:
        parser.error('--output is required for a build')
    try:
        return build(args.output)
    except (ValueError,subprocess.SubprocessError) as error:
        print(str(error),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
