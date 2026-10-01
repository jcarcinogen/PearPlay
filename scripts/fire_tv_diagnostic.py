#!/usr/bin/env python3
"""Isolated Fire TV AirScreen V1 trial. No install, PIN, or automatic cast."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hls_diagnostic as trial

trial.ARCHIVE_NAME = 'PearPlay-FireTV-V1-runtime.tar.gz'
trial.EXPECTED_SHA256 = '91539b28e50cedf9ae6e742409665dedde7f46d714f2c1dfe8b1f79d5cba76d1'
TARGET = '09:83:C3:B6:91:02@192.168.50.95'
_original_environment = trial.capture_environment
_original_page = trial.control_page


def environment(*args, **kwargs):
    env = _original_environment(*args, **kwargs)
    env['PEARPLAY_DIAGNOSTIC_V1_RECEIVER'] = TARGET
    return env


def page(seconds, media='mp4', origin=None):
    text = _original_page(seconds, media, origin)
    text = text.replace(f' — {seconds} seconds', ' — Fire TV trial')
    text = text.replace(f'Only the startup wait is {seconds} seconds; command/network timeouts are unchanged.', 'This trial sends once and holds the connection until you close the test browser. It does not claim playback from the command response.')
    text = text.replace('then the LG and Send. Enter a PIN only in PearPlay\'s masked field if requested, then Send again.',
                        'then Apple TV (192.168.50.95) and Send. This is AirScreen. No PIN should be requested; stop if it asks.')
    return text.replace('<h1>', '<p><strong>Fire TV V1 experiment: leave firewall settings alone. The popup may stay Connecting even while the TV plays. Watch and listen; close this test browser once the result is clear.</strong></p><h1>', 1)


trial.capture_environment = environment
trial.control_page = page

if __name__ == '__main__':
    raise SystemExit(trial.main())
