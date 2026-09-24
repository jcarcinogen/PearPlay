"""Production store identity is distinct from the browser-test fixture."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_helper_protocol import ROOT

STORE_ID = 'eoadahoncjfpnennmkjifohclbafjkol'


def builder():
    spec = importlib.util.spec_from_file_location('build_store_identity', ROOT/'scripts/build_helper.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StoreIdentityTests(unittest.TestCase):
    def test_manifest_key_catalog_and_production_build_agree(self):
        manifest = json.loads((ROOT/'extension/manifest.json').read_text())
        self.assertIn('key', manifest, 'Production manifest must retain its verified store key')
        digest = hashlib.sha256(base64.b64decode(manifest['key'], validate=True)).hexdigest()[:32]
        derived = ''.join(chr(ord('a') + int(n, 16)) for n in digest)
        self.assertEqual(derived, STORE_ID)
        catalog = json.loads((ROOT/'extension/releases.json').read_text())
        self.assertEqual(catalog['extensionId'], STORE_ID)
        self.assertNotIn('localInstallerTest', catalog)
        fixture = json.loads((ROOT/'tests/browser/fixture-key.json').read_text())
        self.assertNotEqual(fixture['id'], STORE_ID)
        config = builder().configuration(STORE_ID, False, 'linux', 'x86_64')
        self.assertEqual(config['extension_id'], STORE_ID)
        self.assertFalse(config['development'])

    def test_production_builder_rejects_wrong_or_malformed_public_key(self):
        build = builder()
        fixture = json.loads((ROOT/'tests/browser/fixture-key.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            (temporary/'extension').mkdir()
            (temporary/'LICENSE').write_text('MIT test fixture')
            (temporary/'extension/releases.json').write_text(json.dumps({'extensionId': STORE_ID, 'downloads': []}))
            for key in (fixture['key'], '%%%'):
                (temporary/'extension/manifest.json').write_text(json.dumps({'key': key}))
                with patch.object(build, 'ROOT', temporary):
                    with self.assertRaisesRegex(ValueError, 'store_public_key'):
                        build.configuration(STORE_ID, False, 'linux', 'x86_64')

    def test_linux_payload_includes_original_project_license(self):
        build = builder()
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            payload = temporary/'payload'
            payload.mkdir()
            (payload/'PearPlayHelper').write_text('test executable')
            stage = build.stage_payload(payload, temporary/'stage', {'platform': 'linux'})
            license_file = stage/'opt/pearplay/PearPlayHelper/LICENSE'
            self.assertTrue(license_file.is_file(), 'Distributed helper must carry the project MIT notice')
            self.assertEqual(license_file.read_bytes(), (ROOT/'LICENSE').read_bytes())


