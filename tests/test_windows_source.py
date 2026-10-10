"""Portable Windows source regressions; these are NOT Win32 execution evidence."""
import asyncio
import io
import struct
import threading
from unittest.mock import patch
import pytest
from helper import app, native
from helper.windows_io import PipeReader
from helper.windows_security import safe_path, Win32
from helper.windows_store import validate

ID = 'eoadahoncjfpnennmkjifohclbafjkol'
ORIGIN = 'chrome-extension://' + ID + '/'


@pytest.mark.parametrize('path', [r'C:relative', r'\\server\share\state', r'\\?\C:\state',
    r'C:\a\..\b', r'C:\a\.\b', r'C:\a\b:stream', 'C:\\a\\b.', 'C:\\a\\b ', r'C:\NUL.txt', r'C:\COM1', 'C:/state'])
def test_reject_unsafe_windows_path(path):
    with pytest.raises(ValueError):
        safe_path(path)


def test_valid_paths_and_fail_closed_off_windows():
    assert str(safe_path(r'C:\Users\Test\AppData\Local\PearPlay')) == r'C:\Users\Test\AppData\Local\PearPlay'
    import sys
    if sys.platform != 'win32':
        with pytest.raises(OSError, match='windows_required'):
            Win32()


@pytest.mark.parametrize('value', [{}, {'identifier':'x','credentials':''}, {'identifier':'x','credentials':'a\n'}, {'identifier':'x','credentials':'a','extra':1}])
def test_store_schema(value):
    with pytest.raises(ValueError):
        validate(value)


def test_parent_window_does_not_weaken_origin():
    # Invalid invocations must return before touching inherited descriptors.
    with patch.object(native.sys, 'platform', 'win32'):
        for origin in [ORIGIN[:-1], ORIGIN+'?x', 'https://example.org/', 'chrome-extension://'+'a'*32+'/']:
            assert native.main(['native','--extension-id',ID,origin,'--parent-window=0']) == 2
        for value in ['-1','abc','18446744073709551616']:
            assert native.main(['native','--extension-id',ID,ORIGIN,'--parent-window='+value]) == 2


def test_windows_app_pins_compiled_origin_and_only_accepts_hwnd():
    config = dict(extension_id=ID, development=False, platform='win32')
    with patch.object(native.sys, 'platform', 'win32'), patch.object(native, 'main', return_value=0) as entry:
        assert app.main([ORIGIN,'--parent-window=0'],config) == 0
        assert entry.call_args.args[0] == ['native','--extension-id',ID,ORIGIN,'--parent-window=0']
        entry.reset_mock()
        for argv in [[ORIGIN,'--extension-id='+ID], [ORIGIN,'--parent-window=-1'],
                     [ORIGIN,'--parent-window=18446744073709551616'],
                     ['chrome-extension://'+'a'*32+'/', '--extension-id','a'*32]]:
            assert app.main(argv,config) == 2
        entry.assert_not_called()


def test_windows_firewall_unavailable():
    async def run():
        with patch.object(native.sys, 'platform', 'win32'):
            host = native.Host(lambda: None, lambda _: None)
            assert host.response('test')['firewallSupport'] is False
            result = await host.handle(dict(v=1,id='test',op='firewall',args=dict(receiver='AA:BB:CC:DD:EE:FF',host='192.168.50.2',action='allow')))
            assert result['error'] == 'unsupported'
    asyncio.run(run())


def test_pipe_multiple_frames_binary_eof_and_timeout():
    async def run():
        output = io.BytesIO()
        frames = io.BytesIO()
        for op in ('hello','status','stop'):
            native.write_frame(frames, dict(v=1,id='r',op=op,args={}))
        reader = PipeReader(io.BytesIO(frames.getvalue()))
        try:
            await asyncio.wait_for(native.serve(reader, output), 1)
        finally:
            reader.close()
        output.seek(0)
        assert [native.read_frame(output)['ok'] for _ in range(5)] == [True]*5  # stop emits stopping and stopped events
        assert native.read_frame(output) is None
        reader = PipeReader(io.BytesIO(struct.pack('<I',65537)))
        output = io.BytesIO()
        try:
            await native.serve(reader, output)
        finally:
            reader.close()
        output.seek(0)
        assert native.read_frame(output)['error'] == 'invalid_frame'
    asyncio.run(run())


def test_idle_pipe_keeps_loop_responsive_and_shutdown_nonblocking():
    release = threading.Event()
    class Stalled:
        def read(self, size):
            release.wait()
            return b''
    async def run():
        reader = PipeReader(Stalled())
        assert reader.thread.daemon
        task = asyncio.create_task(reader.read(1))
        await asyncio.sleep(.02)
        assert not task.done()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        reader.close()
    try:
        asyncio.run(run())
    finally:
        release.set()


def test_partial_header_times_out():
    release = threading.Event()
    class Partial:
        first = True
        def read(self, size):
            if self.first:
                self.first = False
                return b'x'
            release.wait()
            return b''
    async def run():
        reader = PipeReader(Partial())
        output = io.BytesIO()
        try:
            await asyncio.wait_for(native.serve(reader, output, frame_timeout=.02), .3)
            output.seek(0)
            assert native.read_frame(output)['error'] == 'invalid_frame'
        finally:
            reader.close()
    try:
        asyncio.run(run())
    finally:
        release.set()
