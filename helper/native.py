"""Bounded native messaging protocol. Never echo untrusted error text."""
import asyncio
import importlib.util
import ipaddress
import io
import json
from pathlib import Path
import re
import struct

async def native_stdio(output):
    import sys
    loop=asyncio.get_running_loop()
    reader=asyncio.StreamReader(limit=MAX_FRAME + 4)
    protocol=asyncio.StreamReaderProtocol(reader)
    transport,_=await loop.connect_read_pipe(lambda:protocol,sys.stdin.buffer)
    try: await serve(reader,output)
    finally: transport.close()

def main(argv=None):
    import sys
    import os
    import logging
    import argparse
    from contextlib import redirect_stdout, redirect_stderr
    argv = sys.argv[1:] if argv is None else argv
    class Parser(argparse.ArgumentParser):
        def error(self, message): raise ValueError('invalid_arguments')
    parser=Parser(add_help=False)
    parser.add_argument('mode',choices=['native','pair','discover'])
    parser.add_argument('--extension-id')
    parser.add_argument('--identifier')
    parser.add_argument('--host')
    parser.add_argument('origin',nargs='?')
    try:
        args=parser.parse_intermixed_args(argv)
        if args.mode=='native':
            if not allowed_origin(args.extension_id,args.origin) or args.identifier or args.host: return 2
        elif args.origin or args.extension_id:
            return 2
        elif args.mode=='pair':
            if not args.identifier or not args.host: return 2
        elif args.identifier: return 2
        if args.host:
            if '%' in args.host: return 2
            ipaddress.ip_address(args.host)
    except BaseException:
        return 2
    # Retain only the protocol descriptor. Suppress Python and native dependency output.
    output=os.fdopen(os.dup(sys.stdout.fileno()),'wb',buffering=0)
    with open(os.devnull,'w') as sink:
        os.dup2(sink.fileno(),1);os.dup2(sink.fileno(),2)
        logging.disable(100)
        with redirect_stdout(sink), redirect_stderr(sink):
            try:
                if args.mode=='native': asyncio.run(native_stdio(output))
                elif args.mode=='pair':
                    text=io.TextIOWrapper(output,encoding='utf-8',write_through=True)
                    return asyncio.run(pair_cli(args.identifier,args.host,output=text))
                else:
                    async def discover(): return await Transport().discover(args.host)
                    output.write((json.dumps({'receivers':asyncio.run(discover())})+'\n').encode())
                return 0
            except KeyboardInterrupt: return 130
            except Exception:
                if args.mode!='native': output.write(b'{"ok":false,"error":"helper_failed"}\n')
                return 1
            finally: output.close()

MAX_FRAME = 65536
OPS = ('hello', 'discover', 'start', 'status', 'stop', 'pause', 'resume')
IDENTIFIER = r'[0-9a-fA-F:-]{12,64}'

def spike():
    path = Path(__file__).resolve().parents[1] / 'spikes/002-command/command.py'
    spec = importlib.util.spec_from_file_location('pearplay_command', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def validate(value):
    if type(value) is not dict or set(value) != {'v','id','op','args'}:
        raise ValueError('invalid_request')
    if type(value['v']) is not int or value['v'] != 1 or not isinstance(value['id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value['id']):
        raise ValueError('invalid_request')
    op, args = value['op'], value['args']
    if not isinstance(op, str) or op not in OPS or type(args) is not dict:
        raise ValueError('invalid_request')
    keys = set(args)
    if op == 'start':
        if keys != {'receiver','host','url'} or not isinstance(args['receiver'], str) or not re.fullmatch(IDENTIFIER,args['receiver']):
            raise ValueError('invalid_request')
        url = args['url']
        if not isinstance(url, str) or any(0xD800 <= ord(c) <= 0xDFFF for c in url):
            raise ValueError('invalid_request')
        if spike().existing().read_url(io.StringIO(url)) != url:
            raise ValueError('invalid_request')
    elif op == 'discover':
        if keys not in (set(), {'host'}): raise ValueError('invalid_request')
    elif keys:
        raise ValueError('invalid_request')
    if 'host' in args:
        if not isinstance(args['host'], str) or '%' in args['host']: raise ValueError('invalid_request')
        ipaddress.ip_address(args['host'])
    return value

def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('invalid_frame')
        result[key] = value
    return result

def read_frame(source):
    def exact(size):
        result = b''
        while len(result) < size:
            chunk = source.read(size-len(result))
            if not chunk: break
            result += chunk
        return result
    header = exact(4)
    if not header: return None
    if len(header) != 4: raise ValueError('invalid_frame')
    size, = struct.unpack('<I', header)
    if not 0 < size <= MAX_FRAME: raise ValueError('invalid_frame')
    raw = exact(size)
    if len(raw) != size: raise ValueError('invalid_frame')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid_frame')))
    except (UnicodeError, RecursionError) as error:
        raise ValueError('invalid_frame') from error

def write_frame(target, value):
    raw = json.dumps(value, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(raw) > MAX_FRAME: raise ValueError('invalid_frame')
    frame = memoryview(struct.pack('<I', len(raw)) + raw)
    while frame:
        written = target.write(frame)
        if not written: raise BrokenPipeError('output_closed')
        frame = frame[written:]
    target.flush()

def allowed_origin(extension_id, origin):
    return isinstance(extension_id, str) and re.fullmatch(r'[a-p]{32}', extension_id) is not None and origin == 'chrome-extension://' + extension_id + '/'

async def serve(reader, output, factory=None, frame_timeout=10):
    host = Host(factory or Transport, lambda value: write_frame(output, value))
    asyncio.get_running_loop().set_exception_handler(lambda loop, context: None)
    try:
        while True:
            first = await reader.read(1)
            if not first: break
            try:
                header = first + await asyncio.wait_for(reader.readexactly(3), frame_timeout)
                size, = struct.unpack('<I', header)
                if not 0 < size <= MAX_FRAME: raise ValueError('invalid_frame')
                raw = await asyncio.wait_for(reader.readexactly(size), frame_timeout)
                value = read_frame(io.BytesIO(header + raw))
            except (ValueError, asyncio.IncompleteReadError, TimeoutError):
                write_frame(output, host.response('event', 'invalid_frame'))
                break
            write_frame(output, await host.handle(value))
            value = None
    finally:
        await host.close()

async def pair_cli(identifier, host, *, api=None, output=None):
    baseline = spike().existing()
    args = baseline.arguments(['pair', '--identifier', identifier, '--host', host])
    if not re.fullmatch(IDENTIFIER, identifier): raise ValueError('invalid_request')
    if api is None:
        import pyatv
        from pyatv.const import Protocol
        from types import SimpleNamespace
        api = SimpleNamespace(scan=pyatv.scan, pair=pyatv.pair, Protocol=Protocol)
    with Lease(baseline.Store()):
        return await baseline.run(args, api, output, ['pair'])

class Lease:
    """One active helper transport/pairing per user; lock inode is never unlinked."""
    def __init__(self, store):
        self.store, self.fd = store, None

    def __enter__(self):
        import os
        import fcntl
        directory = self.store.directory()
        try:
            self.fd = os.open('helper.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=directory)
            self.store.check(os.fstat(self.fd))
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise HelperError('busy') from None
            return self
        except BaseException:
            if self.fd is not None: os.close(self.fd); self.fd = None
            raise
        finally:
            os.close(directory)

    def __exit__(self, *args):
        import os
        if self.fd is not None: os.close(self.fd); self.fd = None

class Transport:
    def __init__(self, *, api=None, command=None, store=None, connect=None, parse=None, backend=None, timeout=10):
        self.command = command or spike()
        if api is None:
            self.command.guard()
            import pyatv
            from pyatv.const import Protocol
            from types import SimpleNamespace
            api = SimpleNamespace(scan=pyatv.scan, pair=pyatv.pair, Protocol=Protocol)
        if connect is None:
            from pyatv.support.http import http_connect
            connect = http_connect
        if parse is None:
            from pyatv.auth.hap_pairing import parse_credentials
            parse = parse_credentials
        self.api, self.connect, self.parse = api, connect, parse
        self.store = store or self.command.existing().Store()
        self.backend = backend or self.command.Backend
        self.timeout = timeout
        self.wire = None

    async def scan(self, host):
        return await asyncio.wait_for(self.api.scan(asyncio.get_running_loop(), timeout=min(5,self.timeout), protocol=self.api.Protocol.AirPlay, hosts=[host] if host else None), self.timeout)

    async def discover(self, host):
        result = []
        for device in (await self.scan(host))[:256]:
            identifier = device.identifier
            if not isinstance(identifier, str) or not re.fullmatch(IDENTIFIER, identifier): continue
            try: address = str(ipaddress.ip_address(device.address))
            except ValueError: continue
            receiver = dict(identifier=identifier, address=address, label='Apple TV')
            if receiver not in result: result.append(receiver)
            if len(result) == 64: break
        return result

    async def run(self, args, notify):
        with Lease(self.store):
            try: saved = self.store.load()
            except FileNotFoundError: raise HelperError('pairing_required') from None
            if saved['identifier'] != args['receiver']: raise HelperError('pairing_required')
            devices = [d for d in await self.scan(args['host']) if d.identifier == saved['identifier'] and ipaddress.ip_address(d.address) == ipaddress.ip_address(args['host'])]
            if len(devices) != 1: raise HelperError('receiver_unavailable')
            service = devices[0].get_service(self.api.Protocol.AirPlay)
            credentials = self.parse(saved['credentials'])
            connection = await asyncio.wait_for(self.connect(args['host'], service.port), self.timeout)
            try:
                self.wire = self.backend(connection, credentials, self.timeout, lambda *a, **k: None, ['connect'])
                await self.wire.timing(49170)
                session = self.command.Session(self.wire, self.timeout)
                original = session.on_event
                def event(data):
                    was_playing = session.started
                    original(data)
                    if session.started and not was_playing: notify('playing', 'protocol')
                session.on_event = event
                await session.start(self.wire.timing_port, args['url'])
                # Release the URL after submission; the native connection owns the session lifetime.
                args.clear()
                await asyncio.wait_for(session.playing.wait(), self.timeout)
                while not session.finished.is_set():
                    try: await asyncio.wait_for(session.finished.wait(), 2)
                    except TimeoutError: await session.call('feedback')
            finally:
                if self.wire is not None: self.wire.close()
                else: connection.close()

class HelperError(Exception):
    pass

class Host:
    capabilities = ['hello', 'discover', 'start', 'status', 'stop']

    def __init__(self, factory, emit):
        self.factory, self.emit = factory, emit
        self.state, self.evidence = 'idle', 'none'
        self.receivers = []
        self.task = None

    def response(self, identifier, error=None, **fields):
        result = dict(v=1, id=identifier, ok=error is None, state=self.state,
                      evidence=self.evidence, capabilities=list(self.capabilities), **fields)
        if error: result['error'] = error
        if error == 'pairing_required':
            result['pairing'] = 'Run helper/native.py pair --identifier RECEIVER --host IP in a terminal; PIN is hidden.'
        return result

    def changed(self, state, evidence):
        self.state, self.evidence = state, evidence
        self.emit(self.response('event'))

    async def playback(self, args):
        try:
            await self.factory().run(args, self.changed)
            self.changed('stopped', 'protocol')
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.state, self.evidence = 'error', 'unverified'
            code = str(error) if isinstance(error, HelperError) and str(error) in ('pairing_required','busy') else 'transport_failed'
            self.emit(self.response('event', code))

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None

    async def handle(self, value):
        identifier = value.get('id') if isinstance(value, dict) else None
        if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',identifier): identifier = 'event'
        try:
            validate(value)
        except Exception:
            return self.response(identifier, 'invalid_request')
        op, args = value['op'], value['args']
        if op not in self.capabilities: return self.response(identifier, 'unsupported')
        try:
            if op == 'discover':
                self.receivers = await asyncio.wait_for(self.factory().discover(args.get('host')), 10)
                return self.response(identifier, receivers=self.receivers)
            if op == 'start':
                if self.task and not self.task.done(): return self.response(identifier, 'busy')
                if not any(r['identifier'] == args['receiver'] and ipaddress.ip_address(r['address']) == ipaddress.ip_address(args['host']) for r in self.receivers):
                    return self.response(identifier, 'receiver_not_discovered')
                self.state, self.evidence = 'connecting', 'none'
                self.task = asyncio.create_task(self.playback(dict(args)))
            elif op == 'stop':
                self.changed('stopping', 'unverified')
                await self.close()
                self.changed('stopped', 'unverified')
            return self.response(identifier)
        except Exception:
            return self.response(identifier, 'transport_failed')

if __name__ == '__main__':
    raise SystemExit(main())
