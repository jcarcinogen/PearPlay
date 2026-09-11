"""Linux-only AirPlay transport gate; no browser integration."""
import asyncio
import io
import json
import os
from pathlib import Path
import stat
from urllib.parse import urlsplit


def read_url(source):
    """One newline-delimited URL, without decoding or normalizing signed bytes."""
    value = source.readline(16386)
    if value.endswith('\n'):
        value = value[:-1]
    if not value or len(value) > 16384 or any(ord(c) <= 32 or ord(c) == 127 for c in value) or '\\' in value:
        raise ValueError('invalid URL input')
    parts = urlsplit(value)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username is not None or parts.password is not None:
        raise ValueError('invalid URL input')
    _ = parts.port
    return value


class Store:
    """Single receiver. No env/CLI config-path overrides; never use pyatv FileStorage."""
    def __init__(self):
        self.root = Path.home() / '.local/state/pearplay'
        repository = Path(__file__).resolve().parents[2]
        if self.root.resolve().is_relative_to(repository):
            raise ValueError('state must be outside repository')

    def directory(self):
        # Traverse every component with O_NOFOLLOW, including parent directories.
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in self.root.parts[1:]:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            info = os.fstat(fd)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise ValueError('unsafe state directory')
            return fd
        except BaseException:
            os.close(fd)
            raise

    @staticmethod
    def validate(value):
        if not isinstance(value, dict) or set(value) != {'identifier', 'credentials'}:
            raise ValueError('invalid configuration')
        if any(not isinstance(v, str) or not v or len(v) > 8192 or any(ord(c) < 32 for c in v) for v in value.values()):
            raise ValueError('invalid configuration')
        return value

    @staticmethod
    def check(info):
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
            raise ValueError('unsafe credential file')

    def load(self):
        directory = self.directory()
        try:
            fd = os.open('credentials.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd) as source:
                self.check(os.fstat(source.fileno()))
                raw = source.read(20001)
                if len(raw) > 20000:
                    raise ValueError('oversized configuration')
                return self.validate(json.loads(raw))
        finally:
            os.close(directory)

    def save(self, value):
        import secrets
        self.validate(value)
        directory = self.directory()
        temporary = '.credentials-' + secrets.token_hex(12)
        try:
            try:
                self.check(os.stat('credentials.json', dir_fd=directory, follow_symlinks=False))
            except FileNotFoundError:
                pass
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            with os.fdopen(fd, 'w') as target:
                os.fchmod(target.fileno(), 0o600)
                json.dump(value, target)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, 'credentials.json', src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
            os.close(directory)


OWNED_STATE = ('credentials.json', 'control.sock')


def uninstall_state():
    """Remove only PearPlay-owned files. Preserve unknown files and never rm -rf."""
    store = Store()
    if not store.root.exists():
        return {'event': 'uninstalled', 'preserved': []}
    directory = store.directory()
    try:
        for name in OWNED_STATE:
            try:
                info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if name == 'credentials.json':
                store.check(info)
            elif not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError('unsafe control socket')
            os.unlink(name, dir_fd=directory)
        preserved = sorted(p.name for p in store.root.iterdir())
        if not preserved:
            os.rmdir(store.root)
        return {'event': 'uninstalled', 'preserved': preserved}
    finally:
        os.close(directory)


def emit(output, event, **fields):
    print(json.dumps({'event': event, **fields}, ensure_ascii=True), file=output, flush=True)


SAMPLES = {
    'mp4': 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
    'hls': 'https://devstreaming-cdn.apple.com/videos/streaming/examples/bipbop_4x3/bipbop_4x3_variant.m3u8',
}


def arguments(argv):
    import argparse
    import ipaddress
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError('invalid command arguments')
    parser = Parser(description='Linux AirPlay spike. URLs only via --stdin; output is not visual confirmation.')
    parser.add_argument('command', choices=['scan', 'pair', 'play', 'stop', 'status', 'uninstall'])
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--stdin', action='store_true')
    source.add_argument('--sample', choices=['mp4', 'hls'])
    parser.add_argument('--play-timeout', type=float, default=900)
    parser.add_argument('--identifier')
    parser.add_argument('--host', type=lambda v: str(ipaddress.ip_address(v)))
    parser.add_argument('--timeout', type=float, default=15)
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 3600:
        raise ValueError('invalid timeout')
    if not 0 < args.play_timeout <= 86400 or (args.command == 'play' and not (args.stdin or args.sample)):
        raise ValueError('invalid play input')
    if (args.command != 'play' and (args.stdin or args.sample)) or (args.identifier and args.command != 'pair') or (args.host and args.command in ('stop', 'status', 'uninstall')):
        raise ValueError('inapplicable option')
    return args


async def prepare_connect(api, device):
    """Force AirPlay 1 for play_url. tvOS 26 hangs on AirPlay 2 SETUP before /play."""
    if hasattr(api, 'prepare_connect'):
        return await api.prepare_connect(device)
    from pyatv.storage.memory_storage import MemoryStorage
    from pyatv.settings import AirPlayVersion
    storage = MemoryStorage()
    settings = await storage.get_settings(device)
    settings.protocols.raop.protocol_version = AirPlayVersion.V1
    return {'protocol': api.Protocol.AirPlay, 'storage': storage}


async def run(args, api, output, stage):
    loop = asyncio.get_running_loop()
    def background_error(loop, context):
        try:
            emit(output, 'background-error', stage=stage[0], type='Error')
        except Exception:
            pass  # Never trigger asyncio's raw-context fallback logger.
    loop.set_exception_handler(background_error)
    if args.command in ('stop', 'status'):
        stage[0] = 'control'
        response = await control(args.command, args.timeout)
        emit(output, **response)
        return 1 if response['event'] in ('no-active-session', 'control-failed') else 0
    if args.command == 'uninstall':
        stage[0] = 'uninstall'
        emit(output, **uninstall_state())
        return 0
    saved = None
    if args.command == 'play':
        import sys
        stage[0] = 'input'
        url = SAMPLES[args.sample] if args.sample else read_url(sys.stdin)
        stage[0] = 'credentials-load'
        saved = Store().load()
    stage[0] = 'scan'
    devices = await asyncio.wait_for(api.scan(loop, timeout=min(6, args.timeout),
        protocol=api.Protocol.AirPlay, hosts=[args.host] if args.host else None), args.timeout)
    if args.command == 'play':
        devices = [d for d in devices if d.identifier == saved['identifier']]
        if len(devices) != 1:
            emit(output, 'receiver-selection-failed', count=len(devices))
            return 1
        device = devices[0]
        stage[0] = 'connect'
        if not device.set_credentials(api.Protocol.AirPlay, saved['credentials']):
            raise ValueError('credentials rejected')
        kwargs = await prepare_connect(api, device)
        atv = await asyncio.wait_for(api.connect(device, loop, **kwargs), args.timeout)
        try:
            stage[0] = 'play'
            emit(output, 'play-call-started', acceptance='unknown', evidence='visual-confirmation-required')
            # Public play_url has no request-accepted callback and stays open for media duration.
            stopped = await play_session(atv, url, args)
            if stopped:
                emit(output, 'session-stopped', receiver_playback='unverified')
                return 0
            emit(output, 'play-call-returned', evidence='visual-confirmation-required', note='return-is-not-proof-of-video-or-audio')
            return 0
        finally:
            await asyncio.wait_for(asyncio.gather(*atv.close()), args.timeout)
    if args.command == 'pair':
        if args.identifier:
            devices = [d for d in devices if d.identifier == args.identifier]
        if len(devices) != 1:
            emit(output, 'receiver-selection-failed', count=len(devices))
            return 1
        device = devices[0]
        stage[0] = 'pair'
        service = device.get_service(api.Protocol.AirPlay)
        if service is None or service.pairing.name not in ('Optional', 'Mandatory'):
            emit(output, 'pairing-unavailable')
            return 1
        store = Store()
        os.close(store.directory())
        pairing = await asyncio.wait_for(api.pair(device, api.Protocol.AirPlay, loop), args.timeout)
        try:
            await asyncio.wait_for(pairing.begin(), args.timeout)
            if not pairing.device_provides_pin:
                raise ValueError('unsupported PIN direction')
            import getpass
            import warnings
            # getpass must never fall back to echoed stdin.
            with warnings.catch_warnings():
                warnings.simplefilter('error', getpass.GetPassWarning)
                pin = getpass.getpass('TV PIN (hidden): ')
            if len(pin) != 4 or not pin.isascii() or not pin.isdigit():
                raise ValueError('invalid PIN')
            pairing.pin(pin)
            await asyncio.wait_for(pairing.finish(), args.timeout)
            if not pairing.has_paired:
                emit(output, 'pairing-failed')
                return 1
            stage[0] = 'credentials-save'
            store.save({'identifier': device.identifier, 'credentials': pairing.service.credentials})
            emit(output, 'paired', credentials='stored-outside-repository')
            return 0
        finally:
            await asyncio.wait_for(pairing.close(), args.timeout)
    import ipaddress
    import re
    for device in devices:
        identifier = device.identifier
        # Discovery names/properties are untrusted and may contain URLs. Omit them.
        if not isinstance(identifier, str) or not re.fullmatch(r'[0-9a-fA-F:-]{12,64}', identifier):
            identifier = None
        emit(output, 'receiver', identifier=identifier, address=str(ipaddress.ip_address(device.address)), protocol='AirPlay')
    emit(output, 'scan-complete', count=len(devices))
    return 0


async def control(command, timeout):
    store = Store()
    directory = store.directory()
    try:
        try:
            info = os.stat('control.sock', dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            return {'event': 'no-active-session'}
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError('unsafe control socket')
        reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(str(store.root / 'control.sock')), timeout)
        try:
            if command not in ('status', 'stop'):
                raise ValueError('invalid control command')
            writer.write((command + '\n').encode('ascii'))
            await writer.drain()
            raw = await asyncio.wait_for(reader.readline(), timeout)
            response = json.loads(raw)
            # Never forward arbitrary socket response content into diagnostics.
            permitted = [
                {'event': 'session-status', 'state': 'play-call-pending', 'receiver_playback': 'unverified'},
                {'event': 'stop-request-accepted', 'receiver_playback': 'unverified'},
                {'event': 'control-failed'},
            ]
            if response not in permitted:
                raise ValueError('invalid control response')
            return response
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        os.close(directory)


async def play_session(atv, url, args):
    """Keep pyatv's play coroutine alive; stop/status target this process, not a new connection."""
    import socket
    store = Store()
    directory = store.directory()
    path = store.root / 'control.sock'
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server = None
    task = None
    stopped = False
    clients = set()
    bound = False

    async def client(reader, writer):
        nonlocal stopped
        current = asyncio.current_task()
        clients.add(current)
        try:
            command = await asyncio.wait_for(reader.readline(), args.timeout)
            response = {'event': 'control-failed'}
            if command == b'status\n':
                response = {'event': 'session-status', 'state': 'play-call-pending', 'receiver_playback': 'unverified'}
            elif command == b'stop\n' and task is not None and not task.done():
                stopped = True
                try:
                    await asyncio.wait_for(atv.remote_control.stop(), args.timeout)
                except BaseException:
                    stopped = False
                    raise
                task.cancel()
                response = {'event': 'stop-request-accepted', 'receiver_playback': 'unverified'}
            writer.write(json.dumps(response).encode() + b'\n')
            await writer.drain()
        except Exception:
            writer.write(b'{"event":"control-failed"}\n')
        finally:
            writer.close()
            await writer.wait_closed()
            clients.discard(current)

    try:
        # socket.bind fails on existing files (including stale sockets and symlinks).
        old_umask = os.umask(0o177)
        try:
            sock.bind(str(path))
            bound = True
        finally:
            os.umask(old_umask)
        sock.setblocking(False)
        server = await asyncio.start_unix_server(client, sock=sock, limit=64)
        task = asyncio.create_task(atv.stream.play_url(url))
        try:
            await asyncio.wait_for(task, args.play_timeout)
        except asyncio.CancelledError:
            if not stopped:
                raise
        return stopped
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if server is not None:
            server.close()
            await server.wait_closed()
        sock.close()
        if clients:
            await asyncio.wait_for(asyncio.gather(*clients, return_exceptions=True), args.timeout)
        if bound:
            try:
                os.unlink('control.sock', dir_fd=directory)
            except FileNotFoundError:
                pass  # Python >=3.13 server.close already removes its socket.
        os.close(directory)


def safe_failure(output, stage, error):
    allowed = {'ValueError', 'FileNotFoundError', 'PermissionError', 'OSError',
               'TimeoutError', 'ConnectionError', 'ConnectionRefusedError',
               'AuthenticationError', 'PairingError', 'PlaybackError', 'HttpError',
               'NotSupportedError', 'NoCredentialsError', 'ConnectionLostError',
               'ModuleNotFoundError', 'RuntimeError'}
    name = type(error).__name__
    fields = {'stage': stage, 'type': name if name in allowed else 'Error'}
    code = getattr(error, 'status_code', None)
    if code is None and name == 'AuthenticationError':
        import re
        match = re.fullmatch(r'status code: ([1-5][0-9]{2})', str(error))
        if match:
            code = int(match.group(1))
    if type(code) is int and 100 <= code <= 599:
        fields['http_code'] = code
    emit(output, 'error', **fields)


def main(argv=None, *, api=None, output=None):
    import sys
    import logging
    from contextlib import redirect_stdout, redirect_stderr
    output = output or sys.stdout
    previous = logging.root.manager.disable
    logging.disable(100)
    stage = ['input']
    try:
        args = arguments(argv)
        if api is None and sys.platform != 'linux':
            emit(output, 'linux-required')
            return 1
        stage[0] = 'dependency'
        # Drop upstream prints as well as logs. Never keep secret-containing buffers.
        with open(os.devnull, 'w') as sink, redirect_stdout(sink), redirect_stderr(sink):
            if api is None:
                import pyatv
                from pyatv.const import Protocol
                pyatv.Protocol = Protocol
                api = pyatv
            stage[0] = 'scan'
            return asyncio.run(run(args, api, output, stage))
    except KeyboardInterrupt:
        emit(output, 'interrupted', stage=stage[0], receiver_playback='unverified')
        return 130
    except Exception as error:
        safe_failure(output, stage[0], error)
        return 2 if stage[0] == 'input' else 1
    finally:
        logging.disable(previous)


if __name__ == '__main__':
    raise SystemExit(main())
