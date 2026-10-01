"""Strict no-auth admission and the upstream V1 URL sender; no fallback or polling."""
import asyncio
import re


def _bitmap(properties, names, *, features=False):
    values = []
    for name in names:
        if name not in properties:
            continue
        text = properties[name]
        pattern = r'0x[0-9a-fA-F]{1,8}(?:,0x[0-9a-fA-F]{1,8})?' if features else r'(?:0x)?[0-9a-fA-F]{1,8}'
        if not isinstance(text, str) or not re.fullmatch(pattern, text):
            return None
        words = [int(word, 16) for word in text.split(',')]
        values.append(words[0] | (words[1] << 32 if len(words) == 2 else 0))
    return values[0] if values and all(v == values[0] for v in values) else None


def route(service):
    """Return v1/pin or a fixed unsupported reason. Missing TXT is not evidence."""
    from pyatv.auth.hap_pairing import AuthenticationType
    from pyatv.const import PairingRequirement
    from pyatv.protocols.airplay.auth import extract_credentials
    from pyatv.protocols.airplay.utils import get_protocol_version, AirPlayMajorVersion
    from pyatv.settings import AirPlayVersion
    if getattr(service, 'enabled', True) is not True:
        return 'unsupported_access'
    properties = getattr(service, 'properties', {})
    features = _bitmap(properties, ('features', 'ft'), features=True)
    flags = _bitmap(properties, ('flags', 'sf'))
    if features is None or flags is None:
        return 'incomplete_advertisement'
    pw = properties.get('pw', 'false')
    if not isinstance(pw, str) or pw.lower() not in ('true', 'false'):
        return 'incomplete_advertisement'
    if (pw.lower() == 'true' or flags & 0x80 or getattr(service, 'requires_password', None) is not False
            or properties.get('acl', '0') != '0' or properties.get('act', '0') != '0'
            or getattr(service, 'pairing', None) in (PairingRequirement.Disabled, PairingRequirement.Unsupported)):
        return 'unsupported_access'
    if not features & ((1 << 0) | (1 << 33) | (1 << 49)):
        return 'unsupported_protocol'
    if flags & (0x200 | 0x8):
        return 'pin' if service.pairing == PairingRequirement.Mandatory else 'incomplete_advertisement'
    if service.pairing != PairingRequirement.NotNeeded:
        return 'incomplete_advertisement'
    try:
        if (not features & 1 or features & ((1 << 38) | (1 << 48))
                or get_protocol_version(service, AirPlayVersion.Auto) != AirPlayMajorVersion.AirPlayV1):
            return 'unsupported_protocol'
        if features & ((1 << 43) | (1 << 46)) or extract_credentials(service).type != AuthenticationType.Null:
            return 'unsupported_access'
    except (ValueError, TypeError):
        return 'incomplete_advertisement'
    return 'v1'


async def run(transport, service, args, notify):
    from pyatv.protocols.airplay.auth import extract_credentials
    from pyatv.protocols.raop.protocols import StreamContext
    from pyatv.protocols.raop.protocols.airplayv1 import AirPlayV1
    from pyatv.support.rtsp import RtspSession
    transport.playback_report('stage', stage='connect')
    connection = await asyncio.wait_for(transport.connect(args['host'], service.port), transport.timeout)
    closed = asyncio.Event()
    original = connection.connection_lost
    def connection_lost(error):
        try:
            original(error)
        finally:
            closed.set()
    # Per-connection only. pyatv otherwise clears transport without waking the hold.
    connection.connection_lost = connection_lost
    try:
        if connection.transport is None:
            raise ConnectionError('control connection closed')
        context = StreamContext()
        context.credentials = extract_credentials(service)
        protocol = AirPlayV1(context, RtspSession(connection))
        transport.playback_report('stage', stage='command')
        response = await asyncio.wait_for(protocol.play_url(0, args['url']), transport.timeout)
        transport.playback_report('http-response', stage='command', code=response.code)
        if response.code != 200:
            raise RuntimeError('V1 play rejected')
        session = dict(receiver=args['receiver'], host=args['host'], transport='airplay-v1', delivery='accepted', timingRequired=False)
        args.clear()
        if not closed.is_set():
            notify('connecting', 'unverified', session=session)
            await closed.wait()
        return 'unverified'
    finally:
        args.clear()
        connection.close()
        connection.connection_lost = original
