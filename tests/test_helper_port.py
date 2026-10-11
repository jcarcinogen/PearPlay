import asyncio
import io
import json
import struct
import sys
import unittest
from test_helper_protocol import load, request

class PortTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_header_times_out_without_waiting_for_disconnect(self):
        m=load(); reader=asyncio.StreamReader(); reader.feed_data(b'x'); output=io.BytesIO()
        await asyncio.wait_for(m.serve(reader,output,frame_timeout=.01),.2)
        output.seek(0)
        self.assertEqual(m.read_frame(output)['error'],'invalid_frame')

    async def test_native_port_multiple_messages_eof_and_rejected_origin(self):
        m=load(); output=io.BytesIO(); reader=asyncio.StreamReader()
        for op in ['hello','status','pause']:
            frame=io.BytesIO(); m.write_frame(frame,request(op)); reader.feed_data(frame.getvalue())
        reader.feed_eof()
        await m.serve(reader,output)
        output.seek(0); results=[]
        while (value:=m.read_frame(output)) is not None: results.append(value)
        self.assertEqual(len(results),3)
        self.assertEqual(results[-1]['error'],'unsupported')
        extension='a'*32
        self.assertTrue(m.allowed_origin(extension,'chrome-extension://'+extension+'/'))
        for origin in ['chrome-extension://'+extension, 'chrome-extension://'+extension+'/?x', 'chrome-extension://'+'b'*32+'/', 'https://'+extension+'/']:
            self.assertFalse(m.allowed_origin(extension,origin))
        self.assertFalse(m.allowed_origin('z'*32,'chrome-extension://'+'z'*32+'/'))
        reader=asyncio.StreamReader();reader.feed_data(struct.pack('<I',65537));reader.feed_eof()
        output=io.BytesIO();await m.serve(reader,output)
        output.seek(0);self.assertEqual(m.read_frame(output)['error'],'invalid_frame')

    async def test_windows_pair_cli_uses_masked_pin_and_always_closes(self):
        from unittest.mock import patch, AsyncMock
        from types import SimpleNamespace
        m=load()
        session=SimpleNamespace(finish=AsyncMock(),close=AsyncMock())
        transport=SimpleNamespace(begin_pair=AsyncMock(return_value=session))
        with patch.object(m.sys,'platform','win32'), patch.object(m,'Transport',return_value=transport), patch('getpass.getpass',return_value='1234'):
            self.assertEqual(await m.pair_cli('AA:BB:CC:DD:EE:FF','127.0.0.1'),0)
        session.finish.assert_awaited_once_with('1234')
        session.close.assert_awaited_once()
        session.finish.reset_mock();session.close.reset_mock()
        with patch.object(m.sys,'platform','win32'), patch.object(m,'Transport',return_value=transport), patch('getpass.getpass',return_value='bad'):
            with self.assertRaisesRegex(ValueError,'invalid_pin'):
                await m.pair_cli('AA:BB:CC:DD:EE:FF','127.0.0.1')
        session.finish.assert_not_awaited();session.close.assert_awaited_once()

    @unittest.skipIf(sys.platform == 'win32', 'POSIX legacy pairing/lease; Windows branch is tested separately')
    async def test_pair_cli_reuses_secure_existing_pairing_and_lease(self):
        m=load(); self.assertTrue(callable(getattr(m,'pair_cli',None)), 'pair CLI missing')
        from unittest.mock import patch
        from types import SimpleNamespace
        import tempfile
        from pathlib import Path
        command=m.spike(); baseline=command.existing(); seen=[]
        with tempfile.TemporaryDirectory() as directory:
            store=baseline.Store();store.root=Path(directory).resolve()/'state'
            async def run(args,api,output,stage):
                seen.append((args.command,args.identifier,args.host))
                with self.assertRaises(m.HelperError):
                    with m.Lease(store): pass
                return 0
            baseline.run=run
            with patch.object(m,'spike',return_value=SimpleNamespace(existing=lambda:baseline)),patch.object(baseline,'Store',return_value=store):
                result=await m.pair_cli('AA:BB:CC:DD:EE:FF','127.0.0.1',api=object(),output=io.StringIO())
            self.assertEqual(result,0)
            self.assertEqual(seen,[('pair','AA:BB:CC:DD:EE:FF','127.0.0.1')])
