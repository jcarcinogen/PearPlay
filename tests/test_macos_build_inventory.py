"""Notice and provenance regressions for native packaging."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]

def builder():
    spec=importlib.util.spec_from_file_location('mac_inventory_builder',ROOT/'scripts/build_helper.py')
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_notices_preserve_vendor_paths_and_do_not_copy_license_module_code(tmp_path):
    build=builder()
    wheel=tmp_path/'wheel';wheel.mkdir()
    paths=['pkg.dist-info/licenses/LICENSE','pkg.dist-info/licenses/vendor/LICENSE','pkg.dist-info/licenses/NOTICE','pkg/licenses/__init__.py']
    for n,path in enumerate(paths):
        p=wheel/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('notice '+str(n))
    dist=SimpleNamespace(metadata={'Name':'pkg'},version='1.0',files=[Path(p) for p in paths],locate_file=lambda path:wheel/path)
    python=tmp_path/'Python-LICENSE.txt';python.write_text('Python notice')
    payload=tmp_path/'payload';payload.mkdir()
    inventory=build.license_inventory(payload,[dist],python)
    notices=payload/'THIRD_PARTY_LICENSES'
    assert (notices/'pkg/pkg.dist-info/licenses/LICENSE').read_text()=='notice 0'
    assert (notices/'pkg/pkg.dist-info/licenses/vendor/LICENSE').read_text()=='notice 1'
    assert (notices/'pkg/pkg.dist-info/licenses/NOTICE').read_text()=='notice 2'
    assert not (notices/'pkg/pkg/licenses/__init__.py').exists()
    assert (notices/'Python-LICENSE.txt').read_text()=='Python notice'
    assert 'Build environment' in inventory['scope']
    for row in inventory['notices']:
        assert hashlib.sha256((notices/row['file']).read_bytes()).hexdigest()==row['sha256']
    assert json.loads((payload/'dependency-versions.json').read_text())=={'pkg':'1.0'}


def test_build_snapshot_covers_runtime_and_builder():
    build=builder();snapshot=build.build_source_snapshot()
    for path in ('helper/app.py','helper/native.py','helper/install.py','helper/setup.py','scripts/build_helper.py','spikes/002-command/command.py','LICENSE','assets/store/icon-1024.png','assets/brand/pearplay.icns'):
        assert snapshot[path]==hashlib.sha256((ROOT/path).read_bytes()).hexdigest()


def test_macos_bundle_uses_valid_branded_icon():
    build = builder()
    bundles = []
    exec(build.macos_bundle_spec(), {'coll': object(), 'BUNDLE': lambda coll, **options: bundles.append(options)})
    icon = Path(bundles[0]['icon'])
    assert icon == ROOT/'assets/brand/pearplay.icns'
    data = icon.read_bytes()
    assert data[:4] == b'icns'
    assert int.from_bytes(data[4:8], 'big') == len(data)
    offset = 8
    types = set()
    while offset < len(data):
        kind = data[offset:offset+4]
        length = int.from_bytes(data[offset+4:offset+8], 'big')
        assert length > 8 and offset + length <= len(data)
        types.add(kind)
        offset += length
    assert offset == len(data)
    assert {b'ic07', b'ic08', b'ic09', b'ic10'} <= types
    assert bundles[0]['bundle_identifier'] == 'com.pearplay.helper'
