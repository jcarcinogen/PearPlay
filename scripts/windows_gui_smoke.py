"""Hosted Windows frozen UI probe: observe owned windows, never click an action."""
import ctypes as C
from ctypes import wintypes as W
import json
import struct
import subprocess
import time
import zlib
from pathlib import Path


def probe(executable, output):
    user = C.WinDLL('user32', use_last_error=True)
    kernel = C.WinDLL('kernel32', use_last_error=True)
    gdi = C.WinDLL('gdi32', use_last_error=True)
    callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    user.EnumWindows.argtypes = [callback_type, W.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
    user.IsWindowVisible.argtypes = [W.HWND]
    user.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
    user.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
    user.SendMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    user.SendMessageW.restype = C.c_ssize_t
    user.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
    kernel.OpenProcess.restype = W.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
    kernel.CloseHandle.argtypes = [W.HANDLE]
    expected = str(Path(executable).resolve()).casefold()
    process = subprocess.Popen([str(executable)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    window = None
    try:
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            owned = []
            @callback_type
            def visit(hwnd, _):
                if not user.IsWindowVisible(hwnd): return True
                pid = W.DWORD()
                user.GetWindowThreadProcessId(hwnd, C.byref(pid))
                handle = kernel.OpenProcess(0x1000, False, pid.value)
                if not handle: return True
                try:
                    name, length = C.create_unicode_buffer(32768), W.DWORD(32768)
                    if not kernel.QueryFullProcessImageNameW(handle, 0, name, C.byref(length)) or name.value.casefold() != expected:
                        return True
                finally:
                    kernel.CloseHandle(handle)
                title, kind = C.create_unicode_buffer(256), C.create_unicode_buffer(256)
                user.GetWindowTextW(hwnd, title, 256)
                user.GetClassNameW(hwnd, kind, 256)
                owned.append((hwnd, title.value, kind.value))
                return True
            user.EnumWindows(visit, 0)
            if owned:
                if len(owned) != 1 or owned[0][1] != 'PearPlay Setup' or owned[0][2] != 'TkTopLevel':
                    raise ValueError('unexpected_frozen_window: ' + repr(owned))
                window = owned[0][0]
                break
            if process.poll() is not None:
                raise ValueError('frozen_gui_exited_before_window')
            time.sleep(.15)
        if window is None:
            raise ValueError('frozen_gui_window_timeout')
        if not user.SendMessageW(window, 0x7f, 1, 0):  # WM_GETICON / ICON_BIG
            raise ValueError('frozen_gui_missing_window_icon')
        # Print only this owned window; no desktop/other-window screenshot.
        time.sleep(.3)
        capture(user, gdi, window, output)
        user.PostMessageW(window, 0x10, 0, 0)  # WM_CLOSE while idle: cancel, no writes.
        process.wait(timeout=20)
        if process.returncode:
            raise ValueError('frozen_gui_cancel_failed')
        return dict(title='PearPlay Setup', window_class='TkTopLevel', window_icon=True,
                    cancel_exit=0, screenshot=Path(output).name,
                    scope='Hosted frozen initial window and cancel; no installation or owner-policy acceptance')
    finally:
        if process.poll() is None:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=15)
            process.wait(timeout=15)


def capture(user, gdi, hwnd, output):
    user.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
    user.GetWindowDC.argtypes = [W.HWND]
    user.GetWindowDC.restype = W.HDC
    user.ReleaseDC.argtypes = [W.HWND, W.HDC]
    user.PrintWindow.argtypes = [W.HWND, W.HDC, W.UINT]
    gdi.CreateCompatibleDC.argtypes = [W.HDC]
    gdi.CreateCompatibleDC.restype = W.HDC
    gdi.CreateCompatibleBitmap.argtypes = [W.HDC, C.c_int, C.c_int]
    gdi.CreateCompatibleBitmap.restype = W.HBITMAP
    gdi.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
    gdi.SelectObject.restype = W.HGDIOBJ
    gdi.DeleteObject.argtypes = [W.HGDIOBJ]
    gdi.DeleteDC.argtypes = [W.HDC]
    gdi.GetDIBits.argtypes = [W.HDC, W.HBITMAP, W.UINT, W.UINT, C.c_void_p, C.c_void_p, W.UINT]
    rect = W.RECT()
    if not user.GetWindowRect(hwnd, C.byref(rect)): raise OSError('window_rect_failed')
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if not 100 <= width <= 4000 or not 100 <= height <= 4000: raise ValueError('window_size_invalid')
    dc = user.GetWindowDC(hwnd)
    memory = gdi.CreateCompatibleDC(dc)
    bitmap = gdi.CreateCompatibleBitmap(dc, width, height)
    previous = gdi.SelectObject(memory, bitmap)
    try:
        if not user.PrintWindow(hwnd, memory, 2): raise OSError('window_capture_failed')
        gdi.SelectObject(memory, previous)
        header = C.create_string_buffer(struct.pack('<IiiHHIIiiII', 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0))
        buffer = C.create_string_buffer(width * height * 4)
        if gdi.GetDIBits(memory, bitmap, 0, height, buffer, header, 0) != height: raise OSError('window_pixels_failed')
        raw = buffer.raw
        rows = bytearray()
        for y in range(height):
            rows.append(0)
            for x in range(width):
                i = (y * width + x) * 4
                rows.extend((raw[i+2], raw[i+1], raw[i]))
        def chunk(kind, data):
            return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
        Path(output).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', width, height, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))
    finally:
        gdi.SelectObject(memory, previous)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(memory)
        user.ReleaseDC(hwnd, dc)
