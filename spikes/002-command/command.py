"""Experimental pyatv 0.18.0 private-API adapter; see README and LICENSE.md.
Protocol payloads adapted from postlund/pyatv PR2846 (MIT, Pierre Ståhl).
"""
import asyncio
import plistlib
from uuid import uuid4


def arguments(argv):
    import argparse
    import ipaddress
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError('invalid arguments')
    parser = Parser(description='Experimental manual TV trial; no visual-success inference.')
    parser.add_argument('--host', required=True, type=lambda x: str(ipaddress.ip_address(x)))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--sample', choices=['mp4', 'hls'])
    source.add_argument('--stdin', action='store_true')
    parser.add_argument('--mode', choices=['command', 'baseline-v2'], default='command')
    parser.add_argument('--timing-port', type=int, default=49170)
    parser.add_argument('--timeout', type=float, default=10)
    parser.add_argument('--duration', type=float, default=60)
    args = parser.parse_args(argv)
    if not 1024 <= args.timing_port <= 65535 or not 0 < args.timeout <= 60 or not 0 < args.duration <= 900:
        raise ValueError('invalid bounds')
    return args


def main(argv=None, *, output=None):
    import sys
    import os
    import json
    import logging
    from contextlib import redirect_stdout, redirect_stderr
    output = output or sys.stdout
    stage = ['input']
    def report(event, **fields):
        print(json.dumps({'event': event, **fields}), file=output, flush=True)
    old = logging.root.manager.disable
    logging.disable(100)
    try:
        args = arguments(argv)
        stage[0] = 'dependency'
        with open(os.devnull, 'w') as sink, redirect_stdout(sink), redirect_stderr(sink):
            return asyncio.run(trial(args, report, stage))
    except KeyboardInterrupt:
        report('interrupted', stage=stage[0], receiver_playback='unverified')
        return 130
    except Exception as error:
        kind = 'TimeoutError' if isinstance(error, TimeoutError) else 'Error'
        report('error', stage=stage[0], type=kind, receiver_playback='unverified')
        return 2 if stage[0] == 'input' else 1
    finally:
        logging.disable(old)


def existing():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / '001-airplay/pearplay.py'
    spec = importlib.util.spec_from_file_location('pearplay_store', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def trial(args, report, stage):
    guard()
    import pyatv
    from pyatv.const import Protocol
    from pyatv.support.http import http_connect
    from pyatv.auth.hap_pairing import parse_credentials
    loop = asyncio.get_running_loop()
    def background_error(loop, context):
        try:
            report('background-error', type='Error')
        except Exception:
            pass
    loop.set_exception_handler(background_error)
    stage[0] = 'credentials-load'
    baseline = existing()
    saved = baseline.Store().load()
    stage[0] = 'scan'
    devices = await asyncio.wait_for(pyatv.scan(loop, timeout=min(5, args.timeout),
        protocol=Protocol.AirPlay, hosts=[args.host]), args.timeout)
    devices = [d for d in devices if d.identifier == saved['identifier']]
    if len(devices) != 1:
        raise RuntimeError('receiver selection failed')
    service = devices[0].get_service(Protocol.AirPlay)
    credentials = parse_credentials(saved['credentials'])
    stage[0] = 'connect'
    connection = await asyncio.wait_for(http_connect(args.host, service.port), args.timeout)
    wire = Backend(connection, credentials, args.timeout, report, stage)
    try:
        stage[0] = 'timing-bind'
        await wire.timing(args.timing_port)
        if args.stdin:
            import sys
            url = baseline.read_url(sys.stdin)
        else:
            url = baseline.SAMPLES[args.sample]
        if args.mode == 'baseline-v2':
            await wire.baseline(url, args.duration)
        else:
            await Session(wire, args.timeout).run(wire.timing_port, url, args.duration)
        report('trial-returned', receiver_playback='unverified')
        return 0
    finally:
        wire.close()


def guard():
    from importlib.metadata import version
    if version('pyatv') != '0.18.0':
        raise RuntimeError('requires unmodified pyatv 0.18.0')


def event_factory(callback):
    from pyatv.protocols.airplay.channels import BaseEventChannel
    from pyatv.support.http import HttpResponse
    class Events(BaseEventChannel):
        def handle_received(self):
            try:
                if len(self.buffer) > 1024 * 1024:
                    raise ValueError('oversized event')
                while self.buffer:
                    request, _, remaining = self.parse_request(self.buffer)
                    if request is None:
                        return
                    self.buffer = remaining
                    headers = {'Content-Length': '0', 'Audio-Latency': '0'}
                    cseq = str(request.headers.get('CSeq', ''))
                    if cseq.isascii() and cseq.isdigit() and len(cseq) <= 10:
                        headers['CSeq'] = cseq
                    self.send(self.format_response(HttpResponse(request.protocol, request.version, 200, 'OK', headers, b'')))
                    raw = request.body.encode('utf-8') if isinstance(request.body, str) else request.body
                    outer = plistlib.loads(raw)
                    data = outer.get('params', {}).get('data')
                    if isinstance(data, bytes):
                        callback(plistlib.loads(data))
            except Exception:
                self.buffer = b''
                self.close()
    return Events


class Backend:
    def __init__(self, connection, credentials, timeout, report, stage):
        from pyatv.support.rtsp import RtspSession
        self.connection = connection
        self.rtsp = RtspSession(connection)
        self.credentials = credentials
        self.timeout = timeout
        self.report = report
        self.stage = stage
        self.timing_transport = None
        self.event_transport = None
        self.verifier = None
        self.timing_port = None

    async def timing(self, port):
        from pyatv.protocols.raop.protocols import TimingServer
        self.timing_transport, server = await asyncio.wait_for(
            asyncio.get_running_loop().create_datagram_endpoint(
                TimingServer, local_addr=(self.connection.local_ip, port)), self.timeout)
        self.timing_port = server.port
        self.report('timing-bound', udp_port=self.timing_port)

    async def request(self, stage, body=None, headers=None):
        from pyatv.protocols.airplay.auth import verify_connection
        self.stage[0] = stage
        self.report('stage', stage=stage)
        if stage == 'authenticate':
            self.verifier = await verify_connection(self.credentials, self.connection)
            self.report('authenticated', control_encryption='upstream-HAP')
            return {}
        if stage in ('setup-base', 'setup-stream'):
            response = await self.rtsp.setup(body=body)
        elif stage == 'command':
            response = await self.connection.post('/command', headers=headers, body=body, allow_error=True)
        elif stage == 'info':
            return await self.rtsp.info()
        elif stage == 'record':
            response = await self.rtsp.record()
        elif stage == 'feedback':
            response = await self.rtsp.feedback()
        else:
            raise ValueError('unknown stage')
        code = response.code
        if type(code) is int and 100 <= code <= 599:
            self.report('http-response', stage=stage, code=code)
        if code != 200:
            raise RuntimeError('request rejected')
        if stage in ('setup-base', 'setup-stream'):
            return plistlib.loads(response.body)
        return {}

    async def events(self, port, callback):
        from pyatv.auth.hap_channel import setup_channel
        if type(port) is not int or not 1 <= port <= 65535 or self.verifier is None:
            raise ValueError('invalid event setup')
        self.stage[0] = 'event-connect'
        self.event_transport, _ = await asyncio.wait_for(setup_channel(
            event_factory(callback), self.verifier, self.connection.remote_ip, port,
            'Events-Salt', 'Events-Read-Encryption-Key', 'Events-Write-Encryption-Key'), self.timeout)

    async def baseline(self, url, hold):
        from pyatv.protocols.raop.protocols import StreamContext
        from pyatv.protocols.raop.protocols.airplayv2 import AirPlayV2
        context = StreamContext()
        context.credentials = self.credentials
        protocol = AirPlayV2(context, self.rtsp)
        try:
            self.stage[0] = 'baseline-v2-play'
            response = await asyncio.wait_for(protocol.play_url(self.timing_port, url), self.timeout)
            if response.code != 200:
                raise RuntimeError('baseline rejected')
            self.report('baseline-http-accepted', receiver_playback='unverified')
            await asyncio.sleep(hold)
        finally:
            feedback = protocol._feedback_task
            protocol.teardown()
            if feedback:
                await asyncio.wait_for(asyncio.gather(feedback, return_exceptions=True), self.timeout)

    def close(self):
        for transport in (self.event_transport, self.timing_transport):
            if transport:
                transport.close()
        self.event_transport = self.timing_transport = None
        self.connection.close()
        self.rtsp.requests.clear()


def uid():
    return str(uuid4()).upper()


class Session:
    def __init__(self, wire, timeout=10):
        self.wire = wire
        self.timeout = timeout
        self.headers = {'User-Agent': 'AirPlay/870.14.1',
                        'Content-Type': 'application/x-apple-binary-plist',
                        'X-Apple-ProtocolVersion': '1',
                        'X-Apple-Session-ID': uid(), 'X-Apple-StreamID': '1'}
        self.item_id = uid()
        self.started = False
        self.playing = asyncio.Event()
        self.finished = asyncio.Event()

    def on_event(self, data):
        if not isinstance(data, dict) or data.get('type') != 'playbackState':
            return
        params = data.get('params', {})
        state = params.get('playbackState') if isinstance(params, dict) else None
        state = state or data.get('name')
        if state == 'playing':
            self.started = True
            self.playing.set()
        elif state == 'stopped' and self.started:
            self.finished.set()

    async def call(self, stage, body=None):
        return await asyncio.wait_for(self.wire.request(stage, body, dict(self.headers)), self.timeout)

    async def run(self, timing_port, url, duration):
        try:
            async with asyncio.timeout(duration):
                await self.start(timing_port, url)
                await asyncio.wait_for(self.playing.wait(), self.timeout)
                while not self.finished.is_set():
                    try:
                        await asyncio.wait_for(self.finished.wait(), 2)
                    except TimeoutError:
                        await self.call('feedback')
        finally:
            self.wire.close()

    async def start(self, timing_port, url):
        await self.call('authenticate')
        base = await self.call('setup-base', {
            'deviceID': 'AA:BB:CC:DD:EE:FF',
            'sessionUUID': self.headers['X-Apple-Session-ID'],
            'sessionCorrelationUUID': uid(), 'timingPort': timing_port,
            'timingProtocol': 'NTP', 'isMultiSelectAirPlay': True,
            'groupContainsGroupLeader': False, 'macAddress': 'AA:BB:CC:DD:EE:FF',
            'model': 'iPhone14,3', 'name': 'pyatv', 'osBuildVersion': '20F66',
            'osName': 'iPhone OS', 'osVersion': '16.5', 'senderSupportsRelay': False,
            'sourceVersion': '690.7.1', 'statsCollectionEnabled': False})
        await asyncio.wait_for(self.wire.events(base['eventPort'], self.on_event), self.timeout)
        await self.call('info')
        await self.call('record')
        result = await self.call('setup-stream', {'streams': [{
            'clientUUID': uid(), 'clientTypeUUID': 'A6B27562-B43A-4F2D-B75F-82391E250194',
            'channelID': uid() + '-RCS-1', 'controlType': 1, 'type': 130}]})
        stream_id = result['streams'][0]['streamID']
        if type(stream_id) is not int or not 0 <= stream_id < 2**64:
            raise ValueError('invalid stream ID')
        self.headers['X-Apple-StreamID'] = str(stream_id)
        item = {'uuid': self.item_id}
        for command in [
            {'type': 'insertPlayQueueItem', 'item': {**item, 'mediaType': 'file', 'Content-Location': url}},
            {'type': 'setProperty', 'value': True, 'property': 'isInterestedInDateRange', 'item': item},
            {'type': 'setProperty', 'value': 1, 'property': 'actionAtItemEnd'},
            {'type': 'setRate', 'rate': 1.0},
        ]:
            await self.call('command', plistlib.dumps({'params': {'data': plistlib.dumps(command, fmt=plistlib.FMT_BINARY)}}, fmt=plistlib.FMT_BINARY))


if __name__ == '__main__':
    raise SystemExit(main())
