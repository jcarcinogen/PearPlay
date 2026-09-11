import importlib.util
import io
import json
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(name='native'):
    path = ROOT / 'helper' / (name + '.py')
    assert path.exists(), 'helper implementation missing'
    spec = importlib.util.spec_from_file_location('pearplay_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def request(op='hello', args=None):
    return dict(v=1, id='r_1', op=op, args={} if args is None else args)

class ProtocolTests(unittest.TestCase):
    def test_partial_writes_emit_one_complete_frame(self):
        m=load()
        class Short(io.BytesIO):
            def write(self,data): return super().write(data[:3])
        output=Short();m.write_frame(output,request())
        self.assertEqual(m.read_frame(io.BytesIO(output.getvalue())),request())

    def test_strict_bounded_framing_and_validation(self):
        m = load()
        good = request('start', dict(receiver='AA:BB:CC:DD:EE:FF', host='127.0.0.1', url='https://EXAMPLE.org/a%2fb?token=A%2B'))
        self.assertEqual(m.validate(good), good)
        invalid = [dict(good, v=True), dict(good, id='é'), dict(good, extra=1), request('hello', {'host':'127.0.0.1'}), request('discover', {'host':'example.org'}), request('start', dict(good['args'], url='https://a/\nsecret')), request('start', dict(good['args'], receiver='secret?url'))]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError): m.validate(value)
        out = io.BytesIO(); m.write_frame(out, good)
        self.assertEqual(m.read_frame(io.BytesIO(out.getvalue())), good)
        self.assertIsNone(m.read_frame(io.BytesIO()))
        for data in [b'x', struct.pack('<I',65537), struct.pack('<I',0), struct.pack('<I',8)+b'{}', struct.pack('<I',13)+b'{"v":1,"v":2}']:
            with self.subTest(data=data), self.assertRaises(ValueError): m.read_frame(io.BytesIO(data))

if __name__ == '__main__': unittest.main()
