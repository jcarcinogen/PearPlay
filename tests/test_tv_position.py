"""Receiver position is evidence, never a promise that seeking is supported."""
import asyncio
import plistlib
import pytest
from test_tv_control import fixture


def cm(value, scale=1000, flags=1, epoch=0):
    return dict(value=value, timescale=scale, flags=flags, epoch=epoch)


def info(position=3500):
    return dict(position=cm(position), duration=cm(33000), rate=1.0,
                seekableTimeRanges=[dict(start=cm(0), duration=cm(33000))])


def test_correlated_position_response_is_not_http_ack_or_seek_capability():
    async def check():
        session, control, wire, writes, _ = fixture()
        task = asyncio.create_task(control.refresh_position())
        await asyncio.sleep(0)
        assert not task.done()
        payload = plistlib.loads(plistlib.loads(writes[-1][1])['params']['data'])
        assert payload['type'] == 'playbackInfo' and payload['kind'] == 'request'
        session.on_event(dict(kind='response', messageID=payload['messageID']+1, info=info(9000)))
        assert control.timeline() is None
        session.on_event(dict(kind='response', messageID=payload['messageID'], info=info()))
        await task
        result = control.timeline()
        assert result['position'] == 3.5 and result['duration'] == 33
        assert result['seekable'] == [dict(start=0, end=33)]
        assert result['canSeek'] is False and result['rate'] == 1
        assert result['ageMs'] >= 0
        await control.refresh_position()
        assert len(writes) == 1  # Fresh status requests do not flood the wire.
        control.close()
        assert control.timeline() is None
    asyncio.run(check())


@pytest.mark.parametrize('field,value', [
    ('position', cm(1,0)), ('position', cm(1,1,flags=0)),
    ('position', cm(1,1,flags=5)), ('position', cm(1,1,epoch=1)),
    ('position', cm(-1)), ('position', cm(True)),
    ('position', cm(float('nan'))), ('rate', float('nan')),
    ('rate', 99), ('duration', cm(-1)),
])
def test_invalid_receiver_time_is_not_displayed(field,value):
    async def check():
        session, control, wire, writes, _ = fixture()
        task=asyncio.create_task(control.refresh_position())
        await asyncio.sleep(0)
        command=plistlib.loads(plistlib.loads(writes[-1][1])['params']['data'])
        data=info(); data[field]=value
        session.on_event(dict(kind='response',messageID=command['messageID'],info=data))
        await task
        assert control.timeline() is None
        assert control.available  # Bad optional metadata must not break playback.
    asyncio.run(check())


def test_missing_response_disables_metadata_not_playback_and_late_event_is_ignored():
    async def check():
        session,control,wire,writes,_=fixture(.01)
        await control.refresh_position()
        assert control.timeline() is None and control.available and not wire.closed
        command=plistlib.loads(plistlib.loads(writes[-1][1])['params']['data'])
        session.on_event(dict(kind='response',messageID=command['messageID'],info=info()))
        await control.refresh_position()
        assert control.timeline() is None and len(writes)==1
    asyncio.run(check())


def test_interrupted_position_write_closes_ambiguous_fifo_connection():
    async def check():
        session,control,wire,writes,_=fixture(.01)
        async def never(*args): await asyncio.Event().wait()
        wire.request=never
        await control.refresh_position()
        assert wire.closed and not control.available
    asyncio.run(check())


def test_stale_and_pause_transition_invalidate_snapshot():
    async def check():
        session,control,wire,writes,_=fixture()
        task=asyncio.create_task(control.refresh_position())
        await asyncio.sleep(0)
        command=plistlib.loads(plistlib.loads(writes[-1][1])['params']['data'])
        session.on_event(dict(kind='response',messageID=command['messageID'],info=info()))
        await task
        control._position_at -= 11
        assert control.timeline() is None
        session.on_event({'type':'playbackState','name':'paused'})
        assert control.timeline() is None
    asyncio.run(check())
