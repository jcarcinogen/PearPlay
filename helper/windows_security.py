"""Fail-closed Win32 file boundary shared by Windows state and setup.

No chmod fallback. Only fixed local NTFS volumes, non-reparse components,
single-link files, protected owner/SYSTEM DACLs. Directory handles omit
FILE_SHARE_DELETE and remain open throughout each operation, pinning ancestors.
Production paths come from SHGetKnownFolderPath, never LOCALAPPDATA overrides.
Same-user malware, administrators and SYSTEM are outside this boundary.
"""
from contextlib import contextmanager
import ctypes as C
from ctypes import wintypes as W
import ntpath
from pathlib import Path, PureWindowsPath
import sys


class GUID(C.Structure):
    _fields_ = [('a', W.DWORD), ('b', W.WORD), ('c', W.WORD), ('d', C.c_ubyte * 8)]


class FileInfo(C.Structure):
    _fields_ = [('attributes', W.DWORD), ('created', W.FILETIME), ('accessed', W.FILETIME),
                ('written', W.FILETIME), ('volume', W.DWORD), ('size_hi', W.DWORD),
                ('size_lo', W.DWORD), ('links', W.DWORD), ('index_hi', W.DWORD), ('index_lo', W.DWORD)]


class SecurityAttributes(C.Structure):
    _fields_ = [('length', W.DWORD), ('descriptor', W.LPVOID), ('inherit', W.BOOL)]


def safe_path(path):
    """Reject UNC/device/relative paths, ADS, traversal and Win32 aliases."""
    value = str(path)
    pure = PureWindowsPath(value)
    if (not pure.is_absolute() or len(pure.drive) != 2 or pure.drive[1] != ':'
            or value.startswith(('\\\\', '//')) or '/' in value):
        raise ValueError('unsafe_windows_path')
    for part in pure.parts[1:]:
        if (part in ('.', '..') or part.endswith(('.', ' ')) or ':' in part
                or any(ord(c) < 32 or c in '<>"|?*' for c in part)
                or part.split('.')[0].upper() in {'CON','PRN','AUX','NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}):
            raise ValueError('unsafe_windows_path')
    # PureWindowsPath erases '.', so require a canonical lexical spelling.
    if ntpath.normpath(value) != value:
        raise ValueError('unsafe_windows_path')
    return pure


class Win32:
    def __init__(self):
        if sys.platform != 'win32':
            raise OSError('windows_required')
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        self.advapi = C.WinDLL('advapi32', use_last_error=True)
        self.crypt = C.WinDLL('crypt32', use_last_error=True)
        self.shell = C.WinDLL('shell32', use_last_error=True)
        self.ole = C.WinDLL('ole32', use_last_error=True)
        # Explicit signatures are essential: default c_int truncates x64 handles.
        self.bind(self.kernel, 'CreateFileW', W.HANDLE, W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID, W.DWORD, W.DWORD, W.HANDLE)
        self.bind(self.kernel, 'CloseHandle', W.BOOL, W.HANDLE)
        self.bind(self.kernel, 'GetFileInformationByHandle', W.BOOL, W.HANDLE, C.POINTER(FileInfo))
        self.bind(self.kernel, 'ReadFile', W.BOOL, W.HANDLE, W.LPVOID, W.DWORD, C.POINTER(W.DWORD), W.LPVOID)
        self.bind(self.kernel, 'WriteFile', W.BOOL, W.HANDLE, W.LPVOID, W.DWORD, C.POINTER(W.DWORD), W.LPVOID)
        self.bind(self.kernel, 'FlushFileBuffers', W.BOOL, W.HANDLE)
        self.bind(self.kernel, 'CreateDirectoryW', W.BOOL, W.LPCWSTR, C.POINTER(SecurityAttributes))
        self.bind(self.kernel, 'LocalFree', W.HANDLE, W.HANDLE)
        self.bind(self.kernel, 'GetCurrentProcess', W.HANDLE)
        self.bind(self.kernel, 'GetDriveTypeW', W.UINT, W.LPCWSTR)
        self.bind(self.kernel, 'GetVolumeInformationW', W.BOOL, W.LPCWSTR, W.LPWSTR, W.DWORD, C.POINTER(W.DWORD), C.POINTER(W.DWORD), C.POINTER(W.DWORD), W.LPWSTR, W.DWORD)
        self.bind(self.advapi, 'OpenProcessToken', W.BOOL, W.HANDLE, W.DWORD, C.POINTER(W.HANDLE))
        self.bind(self.advapi, 'GetTokenInformation', W.BOOL, W.HANDLE, W.DWORD, W.LPVOID, W.DWORD, C.POINTER(W.DWORD))
        self.bind(self.advapi, 'ConvertSidToStringSidW', W.BOOL, W.LPVOID, C.POINTER(W.LPWSTR))
        self.bind(self.advapi, 'ConvertStringSecurityDescriptorToSecurityDescriptorW', W.BOOL, W.LPCWSTR, W.DWORD, C.POINTER(W.LPVOID), W.LPVOID)
        self.bind(self.advapi, 'ConvertSecurityDescriptorToStringSecurityDescriptorW', W.BOOL, W.LPVOID, W.DWORD, W.DWORD, C.POINTER(W.LPWSTR), W.LPVOID)
        self.bind(self.advapi, 'GetSecurityInfo', W.DWORD, W.HANDLE, W.DWORD, W.DWORD, W.LPVOID, W.LPVOID, W.LPVOID, W.LPVOID, C.POINTER(W.LPVOID))
        self.bind(self.shell, 'SHGetKnownFolderPath', C.c_long, C.POINTER(GUID), W.DWORD, W.HANDLE, C.POINTER(W.LPWSTR))
        self.bind(self.ole, 'CoTaskMemFree', None, W.LPVOID)
        self.sid = self.user_sid()
        self.sddl = f'O:{self.sid}D:P(A;;FA;;;{self.sid})(A;;FA;;;SY)'
        # Windows serializes well-known account SIDs as aliases (for example
        # RID 500 becomes LA). Canonicalize our exact expected descriptor with
        # the same API used by private(); do not relax owner/DACL comparison.
        text = W.LPWSTR()
        with self.attributes() as attrs:
            try:
                self.require(self.advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW(
                    attrs.descriptor, 1, 1 | 4, C.byref(text), None))
                self.sddl = text.value
            finally:
                if text:
                    self.kernel.LocalFree(C.cast(text, W.HANDLE))

    @staticmethod
    def bind(dll, name, result, *args):
        fn = getattr(dll, name)
        fn.restype, fn.argtypes = result, list(args)

    @staticmethod
    def require(ok):
        if not ok:
            raise C.WinError(C.get_last_error())

    def close(self, handle):
        self.require(self.kernel.CloseHandle(handle))

    def user_sid(self):
        token = W.HANDLE()
        self.require(self.advapi.OpenProcessToken(self.kernel.GetCurrentProcess(), 8, C.byref(token)))
        try:
            size = W.DWORD()
            self.advapi.GetTokenInformation(token, 1, None, 0, C.byref(size))
            if not 0 < size.value < 65536:
                raise ValueError('invalid_token')
            buffer = C.create_string_buffer(size.value)
            self.require(self.advapi.GetTokenInformation(token, 1, buffer, size, C.byref(size)))
            sid = C.cast(buffer, C.POINTER(W.LPVOID))[0]
            text = W.LPWSTR()
            self.require(self.advapi.ConvertSidToStringSidW(sid, C.byref(text)))
            try:
                return text.value
            finally:
                self.kernel.LocalFree(C.cast(text, W.HANDLE))
        finally:
            self.close(token)

    def local_appdata(self):
        # FOLDERID_LocalAppData {F1B32785-6FBA-4FCF-9D55-7B8E7F157091}
        guid = GUID(0xF1B32785, 0x6FBA, 0x4FCF, (C.c_ubyte*8)(0x9D,0x55,0x7B,0x8E,0x7F,0x15,0x70,0x91))
        value = W.LPWSTR()
        if self.shell.SHGetKnownFolderPath(C.byref(guid), 0, None, C.byref(value)) != 0:
            raise OSError('local_appdata_unavailable')
        try:
            return Path(value.value)
        finally:
            self.ole.CoTaskMemFree(C.cast(value, W.LPVOID))

    @contextmanager
    def attributes(self):
        descriptor = W.LPVOID()
        self.require(self.advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(self.sddl, 1, C.byref(descriptor), None))
        try:
            yield SecurityAttributes(C.sizeof(SecurityAttributes), descriptor, False)
        finally:
            self.kernel.LocalFree(descriptor)

    def open(self, path, *, directory=False, create=False, exclusive=False, write=False):
        safe_path(path)
        access = 0x80000000 | 0x20000  # GENERIC_READ | READ_CONTROL
        if write:
            access |= 0x40000000
        flags = 0x00200000 | (0x02000000 if directory else 0)  # OPEN_REPARSE_POINT / BACKUP_SEMANTICS
        share = 0 if exclusive else (3 if directory else 1)  # Never share deletion.
        with self.attributes() as attrs:
            handle = self.kernel.CreateFileW(str(path), access, share, C.byref(attrs), 1 if create == 'new' else 4 if create else 3, flags, None)
        if handle == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        try:
            info = FileInfo()
            self.require(self.kernel.GetFileInformationByHandle(handle, C.byref(info)))
            if info.attributes & 0x400 or bool(info.attributes & 0x10) != directory:
                raise ValueError('unsafe_reparse_or_type')
            if not directory and info.links != 1:
                raise ValueError('unsafe_hardlink')
            return handle
        except BaseException:
            self.close(handle)
            raise

    def private(self, handle):
        descriptor = W.LPVOID()
        code = self.advapi.GetSecurityInfo(handle, 1, 1 | 4, None, None, None, None, C.byref(descriptor))
        if code:
            raise C.WinError(code)
        text = W.LPWSTR()
        try:
            self.require(self.advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor, 1, 1 | 4, C.byref(text), None))
            # Exact protected DACL and owner, no inherited/extra grants accepted.
            if text.value != self.sddl:
                raise ValueError('unsafe_windows_acl')
        finally:
            if text:
                self.kernel.LocalFree(C.cast(text, W.HANDLE))
            self.kernel.LocalFree(descriptor)

    def fixed_ntfs(self, anchor):
        if self.kernel.GetDriveTypeW(anchor) != 3:
            raise ValueError('local_fixed_volume_required')
        fs = C.create_unicode_buffer(32)
        self.require(self.kernel.GetVolumeInformationW(anchor, None, 0, None, None, None, fs, 32))
        if fs.value != 'NTFS':
            raise ValueError('ntfs_required')

    @contextmanager
    def directory(self, path, *, private_from=None, create=True):
        pure = safe_path(path)
        self.fixed_ntfs(pure.anchor)
        handles = []
        current = Path(pure.anchor)
        try:
            handles.append(self.open(current, directory=True))
            for part in pure.parts[1:]:
                current /= part
                private = private_from is not None and (current == private_from or current.is_relative_to(private_from))
                if private and create:
                    with self.attributes() as attrs:
                        if not self.kernel.CreateDirectoryW(str(current), C.byref(attrs)) and C.get_last_error() != 183:
                            raise C.WinError(C.get_last_error())
                handle = self.open(current, directory=True)
                handles.append(handle)
                if private:
                    self.private(handle)
            yield handles[-1]
        finally:
            for handle in reversed(handles):
                self.close(handle)

    def read(self, handle, limit):
        chunks = bytearray()
        while len(chunks) <= limit:
            buffer = C.create_string_buffer(min(65536, limit + 1 - len(chunks)))
            count = W.DWORD()
            self.require(self.kernel.ReadFile(handle, buffer, len(buffer), C.byref(count), None))
            if not count.value:
                return bytes(chunks)
            chunks.extend(buffer.raw[:count.value])
        raise ValueError('oversized_file')

    def write(self, handle, raw):
        offset = 0
        while offset < len(raw):
            chunk = raw[offset:offset+65536]
            buffer = C.create_string_buffer(chunk)
            count = W.DWORD()
            self.require(self.kernel.WriteFile(handle, buffer, len(chunk), C.byref(count), None))
            if not count.value:
                raise OSError('short_write')
            offset += count.value
        self.require(self.kernel.FlushFileBuffers(handle))
