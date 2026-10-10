"""Per-user DPAPI pairing store and exclusive Windows process lease."""
from contextlib import contextmanager
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import secrets
from helper.windows_security import Win32

MAX_PLAINTEXT = 20000
MAX_CIPHERTEXT = 65536
ENTROPY = b'PearPlay pairing v1'  # Application binding, not a secret.


class Blob(C.Structure):
    _fields_ = [('size', W.DWORD), ('data', C.POINTER(C.c_ubyte))]


class DPAPI:
    def __init__(self, api):
        self.api = api
        for name in ('CryptProtectData', 'CryptUnprotectData'):
            # second argument differs (description vs returned description).
            api.bind(api.crypt, name, W.BOOL, C.POINTER(Blob), W.LPVOID,
                     C.POINTER(Blob), W.LPVOID, W.LPVOID, W.DWORD, C.POINTER(Blob))

    def transform(self, raw, *, decrypt=False):
        if not isinstance(raw, bytes) or not 0 < len(raw) <= (MAX_CIPHERTEXT if decrypt else MAX_PLAINTEXT):
            raise ValueError('invalid_dpapi_input')
        buffer = (C.c_ubyte * len(raw)).from_buffer_copy(raw)
        entropy = (C.c_ubyte * len(ENTROPY)).from_buffer_copy(ENTROPY)
        source, binding, result = Blob(len(raw), buffer), Blob(len(ENTROPY), entropy), Blob()
        fn = self.api.crypt.CryptUnprotectData if decrypt else self.api.crypt.CryptProtectData
        try:
            # CRYPTPROTECT_UI_FORBIDDEN; deliberately NOT LOCAL_MACHINE.
            self.api.require(fn(C.byref(source), None, C.byref(binding), None, None, 1, C.byref(result)))
            limit = MAX_PLAINTEXT if decrypt else MAX_CIPHERTEXT
            if not 0 < result.size <= limit:
                raise ValueError('oversized_dpapi_result')
            return C.string_at(result.data, result.size)
        finally:
            C.memset(buffer, 0, len(raw))
            if result.data:
                C.memset(result.data, 0, result.size)
                self.api.kernel.LocalFree(C.cast(result.data, W.HANDLE))


def validate(value):
    if type(value) is not dict or set(value) != {'identifier', 'credentials'}:
        raise ValueError('invalid_configuration')
    if any(not isinstance(v, str) or not v or len(v) > 8192 or any(ord(c) < 32 for c in v) for v in value.values()):
        raise ValueError('invalid_configuration')
    return value


class Store:
    def __init__(self, *, api=None, root=None):
        self.api = api or Win32()
        # root injection exists only for explicit test construction, never env/CLI.
        self.base = Path(root) if root is not None else self.api.local_appdata() / 'PearPlay'
        self.root = self.base / 'state'
        self.dpapi = DPAPI(self.api)

    @contextmanager
    def directory(self):
        with self.api.directory(self.root, private_from=self.base) as handle:
            yield handle

    @contextmanager
    def file(self, name, *, create=False, exclusive=False, write=False):
        if name != 'credentials.dpapi' and name != 'helper.lock' and not name.startswith('.credentials-'):
            raise ValueError('invalid_state_name')
        with self.directory():
            handle = self.api.open(self.root / name, create=create, exclusive=exclusive, write=write)
            try:
                self.api.private(handle)
                yield handle
            finally:
                self.api.close(handle)

    def load(self):
        with self.file('credentials.dpapi') as handle:
            raw = self.api.read(handle, MAX_CIPHERTEXT)
        # No plaintext legacy fallback: corrupt/foreign DPAPI data fails closed.
        return validate(json.loads(self.dpapi.transform(raw, decrypt=True).decode('utf-8')))

    def save(self, value):
        raw = json.dumps(validate(value), ensure_ascii=True, separators=(',', ':')).encode('utf-8')
        encrypted = self.dpapi.transform(raw)
        temporary = '.credentials-' + secrets.token_hex(12)
        with self.directory():
            try:
                try:
                    with self.file('credentials.dpapi'):
                        pass
                except FileNotFoundError:
                    pass
                with self.file(temporary, create='new', exclusive=True, write=True) as handle:
                    self.api.write(handle, encrypted)
                os.replace(self.root / temporary, self.root / 'credentials.dpapi')
            finally:
                try:
                    os.unlink(self.root / temporary)
                except FileNotFoundError:
                    pass


class Lease:
    """A share-mode-zero handle, held for the entire pairing/playback lifetime.

    The inode-equivalent is never removed. A second process receives Win32
    ERROR_SHARING_VIOLATION. Process death releases the kernel lease.
    """
    def __init__(self, store):
        self.store, self.context = store, None

    def __enter__(self):
        from helper.native import HelperError
        self.context = self.store.file('helper.lock', create=True, exclusive=True, write=True)
        try:
            self.context.__enter__()
        except OSError as error:
            self.context = None
            if getattr(error, 'winerror', None) in (32, 33):
                raise HelperError('busy') from None
            raise
        return self

    def __exit__(self, *args):
        if self.context is not None:
            context, self.context = self.context, None
            context.__exit__(*args)
