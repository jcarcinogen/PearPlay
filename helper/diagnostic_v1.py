"""Opt-in, receiver-pinned V1 URL experiment. Not a production fallback."""
import asyncio
from pyatv.auth.hap_pairing import AuthenticationType
from pyatv.const import PairingRequirement
from pyatv.protocols.airplay.auth import extract_credentials
from pyatv.protocols.airplay.utils import get_protocol_version, AirPlayMajorVersion
from pyatv.settings import AirPlayVersion
from pyatv.protocols.raop.protocols import StreamContext
from pyatv.protocols.raop.protocols.airplayv1 import AirPlayV1
from pyatv.support.rtsp import RtspSession


async def run(transport, args, notify):
    transport.playback_report('stage', stage='receiver-scan')
    device = await transport.resolve_receiver(args['receiver'], args['host'])
    service = device.get_service(transport.api.Protocol.AirPlay)
    credentials = extract_credentials(service)
    if (service.pairing != PairingRequirement.NotNeeded or service.requires_password
            or credentials.type != AuthenticationType.Null
            or get_protocol_version(service, AirPlayVersion.Auto) != AirPlayMajorVersion.AirPlayV1):
        raise ValueError('receiver does not qualify for no-auth V1 trial')
    transport.playback_report('stage', stage='connect')
    connection = await asyncio.wait_for(transport.connect(args['host'], service.port), transport.timeout)
    try:
        context = StreamContext()
        context.credentials = credentials
        protocol = AirPlayV1(context, RtspSession(connection))
        transport.playback_report('stage', stage='command')
        # V1 play_url does not use timing_server_port. No UDP listener is needed.
        response = await asyncio.wait_for(protocol.play_url(0, args['url']), transport.timeout)
        transport.playback_report('http-response', stage='command', code=response.code)
        if response.code != 200:
            raise RuntimeError('V1 play rejected')
        args.clear()
        # ACK is not playing. Keep the session until the human closes the browser
        # or ends the helper session; no polling/retries/finite playback cutoff.
        notify('connecting', 'unverified')
        await asyncio.Future()
    finally:
        connection.close()
