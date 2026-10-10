"""Receipt-based, per-user Chrome installer; no elevation or security bypass.

The frozen setup executable embeds a ZIP of a console-subsystem native host.
Every write is under the known-folder PearPlay/helper tree or this user's HKCU
Chrome NativeMessagingHosts key. Pairing lives separately in PearPlay/state.
"""
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import sys
import zipfile
from helper.windows_security import Win32, safe_path

EXTENSION_ID = 'eoadahoncjfpnennmkjifohclbafjkol'
HOST = 'com.pearplay.helper'
KEY = 'Software\\Google\\Chrome\\NativeMessagingHosts\\' + HOST
MAX_PAYLOAD = 512 * 1024 * 1024
MAX_RECEIPT = 2 * 1024 * 1024


def relative_name(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('unsafe_payload_name')
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix() or any(p in ('.','..') for p in path.parts):
        raise ValueError('unsafe_payload_name')
    safe_path('C:\\payload\\' + value.replace('/', '\\'))
    return value


def manifest(executable):
    return dict(name=HOST, description='PearPlay per-user Chrome helper', path=str(executable),
                type='stdio', allowed_origins=['chrome-extension://' + EXTENSION_ID + '/'])


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode('utf-8')


def payload_files(raw):
    files, seen, total = {}, set(), 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if not 1 <= len(entries) <= 8192:
            raise ValueError('invalid_payload_count')
        for info in entries:
            if info.is_dir():
                raise ValueError('payload_requires_files_only')
            if info.orig_filename != info.filename:
                raise ValueError('normalized_payload_name')
            name = relative_name(info.filename)
            folded = name.casefold()
            if folded in seen or stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1:
                raise ValueError('unsafe_duplicate_or_link')
            seen.add(folded)
            total += info.file_size
            if not 0 <= info.file_size <= MAX_PAYLOAD or total > MAX_PAYLOAD:
                raise ValueError('oversized_payload')
            files[name] = archive.read(info)
    # A file must not also be a parent directory, even with case differences.
    for name in seen:
        if any(parent.as_posix() in seen for parent in PurePosixPath(name).parents if str(parent) != '.'):
            raise ValueError('payload_file_directory_collision')
    if 'PearPlayHelper.exe' not in files or 'build-info.json' not in files:
        raise ValueError('missing_payload_entrypoint')
    config = json.loads(files['build-info.json'])
    if (config.get('extension_id') != EXTENSION_ID or config.get('platform') != 'win32'
            or config.get('development') is not False or not re.fullmatch(r'\d+\.\d+\.\d+', str(config.get('version','')))):
        raise ValueError('invalid_payload_identity')
    return files, config


def receipt(value):
    if (type(value) is not dict or set(value) != {'schema','product','extension_id','version','files'}
            or value['schema'] != 1 or value['product'] != HOST or value['extension_id'] != EXTENSION_ID
            or not re.fullmatch(r'\d+\.\d+\.\d+', str(value['version'])) or type(value['files']) is not dict
            or not 1 <= len(value['files']) <= 8193):
        raise ValueError('invalid_install_receipt')
    seen = set()
    for name, digest in value['files'].items():
        relative_name(name)
        if name != HOST + '.json' and not name.startswith('runtime/'):
            raise ValueError('invalid_owned_path')
        if name.casefold() in seen or not re.fullmatch(r'[0-9a-f]{64}', str(digest)):
            raise ValueError('invalid_receipt_hash')
        seen.add(name.casefold())
    if HOST+'.json' not in value['files'] or 'runtime/PearPlayHelper.exe' not in value['files']:
        raise ValueError('missing_receipt_identity')
    return value


class Registry:
    """Both Chrome registry views; unknown values/subkeys are conflicts."""
    def __init__(self):
        import winreg
        self.reg = winreg
        self.views = (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY)

    def snapshot(self):
        result = []
        r = self.reg
        for view in self.views:
            try:
                key = r.OpenKey(r.HKEY_CURRENT_USER, KEY, 0, r.KEY_READ | view)
            except FileNotFoundError:
                result.append(None)
                continue
            with key:
                children, values, _ = r.QueryInfoKey(key)
                if children or values != 1:
                    raise ValueError('foreign_registry_key')
                value, kind = r.QueryValueEx(key, '')
                if kind != r.REG_SZ or not isinstance(value, str):
                    raise ValueError('foreign_registry_value')
                result.append(value)
        return result

    def apply(self, values):
        r = self.reg
        for view, value in zip(self.views, values):
            if value is None:
                try:
                    r.DeleteKeyEx(r.HKEY_CURRENT_USER, KEY, view, 0)
                except FileNotFoundError:
                    pass
            else:
                with r.CreateKeyEx(r.HKEY_CURRENT_USER, KEY, 0, r.KEY_SET_VALUE | view) as key:
                    r.SetValueEx(key, '', 0, r.REG_SZ, value)
        if self.snapshot() != list(values):
            raise OSError('registry_readback_failed')


class Files:
    """Win32-handle validation at every file/directory access."""
    def __init__(self, api, base):
        self.api, self.base = api, base
        self.root = base / 'helper'

    @contextmanager
    def directory(self, path=None, *, create=True):
        with self.api.directory(path or self.root, private_from=self.base, create=create):
            yield

    def read(self, name, limit=MAX_RECEIPT):
        path = self.root / relative_name(name)
        with self.directory(path.parent, create=False):
            handle = self.api.open(path)
            try:
                self.api.private(handle)
                return self.api.read(handle, limit)
            finally:
                self.api.close(handle)

    def write_new(self, name, raw):
        path = self.root / relative_name(name)
        with self.directory(path.parent):
            handle = self.api.open(path, create='new', write=True, exclusive=True)
            try:
                self.api.private(handle)
                self.api.write(handle, raw)
            finally:
                self.api.close(handle)

    def replace(self, name, raw):
        temporary = '.write-' + secrets.token_hex(12)
        self.write_new(temporary, raw)
        try:
            # Existing file must pass the same hardlink/reparse/ACL checks.
            try:
                self.read(name, MAX_PAYLOAD)
            except FileNotFoundError:
                pass
            path = self.root / relative_name(name)
            with self.directory(path.parent):
                os.replace(self.root / temporary, path)
        finally:
            try:
                os.unlink(self.root / temporary)
            except FileNotFoundError:
                pass

    def inventory(self):
        result = {}
        def walk(directory):
            with self.directory(directory, create=False):
                for entry in os.scandir(directory):
                    path = Path(entry.path)
                    name = path.relative_to(self.root).as_posix()
                    relative_name(name)
                    if entry.is_dir(follow_symlinks=False):
                        walk(path)
                    else:
                        result[name] = hashlib.sha256(self.read(name, MAX_PAYLOAD)).hexdigest()
        walk(self.root)
        return result

    def delete(self, name, digest):
        path = self.root / relative_name(name)
        with self.directory(path.parent, create=False):
            raw = self.read(name, MAX_PAYLOAD)
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('changed_file_preserved')
            os.unlink(path)

    def prune(self, names):
        # Only empty directories inferred from owned paths, never recursive rm.
        parents = {p for name in names for p in (self.root/name).parents if p != self.root and p.is_relative_to(self.root)}
        for parent in sorted(parents, key=lambda p: len(p.parts), reverse=True):
            try:
                with self.directory(parent, create=False):
                    pass
                parent.rmdir()
            except FileNotFoundError:
                pass
            except OSError as error:
                if getattr(error, 'winerror', None) not in (145,):
                    raise


def reconcile(action, files, registry, payload=None):
    """Portable policy, exercised with fixture adapters and separately on Win32.

    Hold Files.directory and the process lease in the caller. A journal refuses
    interrupted transactions rather than guessing ownership after a power loss.
    """
    if action not in ('install','repair','upgrade','connect','disconnect','uninstall'):
        raise ValueError('invalid_setup_action')
    actual = files.inventory()
    if 'transaction.json' in actual:
        raise ValueError('interrupted_transaction_requires_review')
    old = receipt(json.loads(files.read('install-receipt.json'))) if 'install-receipt.json' in actual else None
    before = registry.snapshot()
    target = str(files.root / (HOST + '.json'))
    if any(value not in (None, target) for value in before) or (old is None and any(v is not None for v in before)):
        raise ValueError('foreign_registration')
    if old is None and actual:
        raise ValueError('unreceipted_files_preserved')
    owned = old['files'] if old else {}
    changed = sorted(name for name, digest in owned.items() if name in actual and actual[name] != digest)
    foreign = sorted(set(actual) - set(owned) - {'install-receipt.json'})
    if action in ('connect','disconnect'):
        if old is None:
            raise ValueError('not_installed')
        if action == 'connect' and (changed or foreign or any(name not in actual for name in owned)):
            raise ValueError('repair_required')
        registry.apply([target, target] if action == 'connect' else [None,None])
        return dict(action=action, pairing='preserved', preserved=changed+foreign)
    if action == 'uninstall':
        if old is None:
            return dict(action=action, pairing='preserved', preserved=[])
        # A foreign registration is refused above; matching owned keys only.
        registry.apply([None,None])
        for name, digest in owned.items():
            if name in actual and name not in changed:
                files.delete(name, digest)
        if not changed:
            files.delete('install-receipt.json', actual['install-receipt.json'])
        files.prune(owned)
        return dict(action=action, pairing='preserved', preserved=changed+foreign)
    if changed or foreign:
        raise ValueError('changed_or_foreign_files_preserved')
    if action == 'install' and old is not None:
        raise ValueError('already_installed_use_repair_or_upgrade')
    if action in ('repair','upgrade') and old is None:
        raise ValueError('not_installed')
    contents, config = payload_files(payload)
    new_version = tuple(map(int, config['version'].split('.')))
    if old is not None:
        old_version = tuple(map(int, old['version'].split('.')))
        if new_version < old_version:
            raise ValueError('downgrade_refused')
        if action == 'repair' and new_version != old_version:
            raise ValueError('repair_requires_same_version')
    desired = {'runtime/'+name: data for name,data in contents.items()}
    desired[HOST+'.json'] = encoded(manifest(files.root/'runtime/PearPlayHelper.exe'))
    new = receipt(dict(schema=1, product=HOST, extension_id=EXTENSION_ID, version=config['version'],
                       files={name:hashlib.sha256(data).hexdigest() for name,data in desired.items()}))
    # Missing owned files can be repaired. Changed files are never overwritten.
    backups = {name: files.read(name, MAX_PAYLOAD) for name in owned if name in actual}
    previous_receipt = files.read('install-receipt.json') if old else None
    files.write_new('transaction.json', encoded(dict(action=action, old=old, new=new)))
    touched = []
    try:
        for name, data in desired.items():
            if name in actual and actual[name] == new['files'][name]:
                continue
            files.replace(name, data)
            touched.append(name)
        # Receipt is durable before registration; Chrome never targets an
        # incomplete initial payload. Journal prevents subsequent repair guesses.
        files.replace('install-receipt.json', encoded(new))
        registry.apply([target,target])
        readback = receipt(json.loads(files.read('install-receipt.json')))
        if readback != new or registry.snapshot() != [target,target]:
            raise OSError('install_readback_failed')
        current = files.inventory()
        if any(current.get(name) != digest for name,digest in new['files'].items()):
            raise OSError('payload_readback_failed')
    except BaseException:
        # Ordinary failures roll back. If rollback itself fails, the journal
        # remains and later operations fail closed for explicit review.
        registry.apply(before)
        for name in reversed(touched):
            if name in backups:
                files.replace(name, backups[name])
            else:
                files.delete(name, new['files'][name])
        if previous_receipt is not None:
            files.replace('install-receipt.json', previous_receipt)
        else:
            try:
                files.delete('install-receipt.json', hashlib.sha256(encoded(new)).hexdigest())
            except FileNotFoundError:
                pass
        journal = files.read('transaction.json')
        files.delete('transaction.json', hashlib.sha256(journal).hexdigest())
        files.prune(touched)
        raise
    # Obsolete files are deleted only if unchanged and recorded by the old
    # receipt. Their cleanup precedes journal removal; failures stay fail-closed.
    for name, digest in owned.items():
        if name not in desired and name in actual:
            files.delete(name, digest)
    files.prune(set(owned)-set(desired))
    journal = files.read('transaction.json')
    files.delete('transaction.json', hashlib.sha256(journal).hexdigest())
    return dict(action=action, version=config['version'], pairing='preserved', preserved=[])


def manage(action, payload=None):
    from helper.windows_store import Store, Lease
    api = Win32()
    store = Store(api=api)
    files = Files(api, store.base)
    with Lease(store), files.directory():
        return reconcile(action, files, Registry(), payload)


def message(text, *, question=False):
    import ctypes
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.MessageBoxW.argtypes = [W.HWND, W.LPCWSTR, W.LPCWSTR, W.UINT]
    user.MessageBoxW.restype = C.c_int
    return user.MessageBoxW(None, text, 'PearPlay Setup', 0x24 if question else 0x40) == 6


# Imports for MessageBox only; available as type aliases on non-Windows too.
import ctypes as C
from ctypes import wintypes as W


def helper_main(argv, config):
    from helper import native
    if config.get('extension_id') != EXTENSION_ID or config.get('development') is not False or config.get('platform') != 'win32':
        return 2
    if argv and '://' in argv[0]:
        # Only Chrome's documented optional HWND argument may follow the
        # origin: never let argv override the compiled extension-id option.
        if not native.allowed_origin(EXTENSION_ID, argv[0]): return 2
        if len(argv) not in (1, 2): return 2
        if len(argv) == 2:
            match = re.fullmatch(r'--parent-window=([0-9]{1,20})', argv[1])
            if not match or int(match[1]) >= 2**64: return 2
        return native.main(['native','--extension-id',EXTENSION_ID,*argv])
    if argv == ['self-test']:
        native.Transport()  # imports only: no directory, network or credentials.
        print(json.dumps(dict(ok=True, version=native.VERSION, dependencies='loaded', network='not used')))
        return 0
    if not getattr(sys, 'frozen', False):
        return 2
    if not argv:
        if not message('Connect or repair this installed helper\'s Chrome registration?\n\nNo TV action, firewall change or administrator access is requested.', question=True):
            return 0
        argv = ['connect']
    if argv not in (['connect'], ['disconnect'], ['remove']):
        message('Run the downloaded PearPlay installer with repair, upgrade or uninstall. Saved TV pairing is kept.')
        return 2
    try:
        result = manage('disconnect' if argv in (['disconnect'], ['remove']) else 'connect')
        print(json.dumps(result))
        message('Chrome connection updated. Fully quit and reopen Chrome. Saved TV pairing is kept.')
        return 0
    except Exception:
        message('Connection refused. Run the downloaded installer with repair. Existing files and saved pairing are kept.')
        return 1


def main(argv=None):
    import argparse
    from helper.native import VERSION
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description='Per-user PearPlay Windows setup (no TV actions)')
    parser.add_argument('action', nargs='?', choices=['install','repair','upgrade','connect','disconnect','uninstall','self-test','verify-payload'])
    args = parser.parse_args(argv)
    if sys.platform != 'win32':
        return 2
    if args.action == 'self-test':
        print(json.dumps(dict(ok=True, version=VERSION, platform='win32', network='not used')))
        return 0
    if not getattr(sys, 'frozen', False):
        return 2
    gui = args.action is None
    try:
        if args.action == 'verify-payload':
            raw = (Path(sys._MEIPASS)/'windows-payload.zip').read_bytes()
            contents, config = payload_files(raw)
            print(json.dumps(dict(ok=True, version=config['version'], extension_id=config['extension_id'],
                                  files=len(contents), sha256=hashlib.sha256(raw).hexdigest(), network='not used')))
            return 0
        action = args.action
        if gui:
            text = ('Install or upgrade PearPlay for this Windows user and connect Google Chrome?\n\n'
                    'This preview is unsigned. No administrator rights or firewall changes are requested. '
                    'Fully close casting first. Saved pairing is kept. Choose No to cancel.\n\n'
                    'For repair, disconnect or uninstall, run this installer from a terminal with the named action.')
            if not message(text, question=True):
                return 0
            api = Win32()
            f = Files(api, api.local_appdata()/'PearPlay')
            try:
                with f.directory(create=False):
                    installed = 'install-receipt.json' in f.inventory()
            except FileNotFoundError:
                installed = False
            action = 'upgrade' if installed else 'install'
        payload = None
        if action in ('install','repair','upgrade'):
            payload = (Path(sys._MEIPASS)/'windows-payload.zip').read_bytes()
        result = manage(action, payload)
        print(json.dumps(result))
        if gui:
            message('PearPlay is connected to Chrome. Fully quit and reopen Chrome, then click Check connection in the extension.\n\nNo TV action was taken. Saved pairing is kept.')
        return 0
    except Exception:
        if gui:
            message('Setup refused or failed. Existing/changed files and saved pairing are protected.\n\nUse the command-line action for a sanitized error and consult the Windows guide. No security settings were changed.')
        else:
            # Avoid raw exception messages with filesystem/user data.
            print(json.dumps(dict(ok=False, error='setup_refused_or_failed', pairing='preserved')), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
