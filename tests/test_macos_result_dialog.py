"""Compile the actual Mac result dialog without displaying UI or changing TCC."""
import subprocess
import sys

import pytest

from helper import app


@pytest.mark.skipif(sys.platform != 'darwin', reason='native AppleScript compiler')
def test_mac_result_dialog_compiles_unicode_warning_and_results(tmp_path, monkeypatch):
    calls = []
    real_run = subprocess.run
    monkeypatch.setattr(app.subprocess, 'run', lambda args, **kwargs: calls.append(args))
    app.dialog('Unsigned preview — local testing only.\nGoogle Chrome: connected\nBrave: connected\n“Example”')
    script = calls[0][-1]
    compiled = real_run(
        ['/usr/bin/osacompile', '-o', str(tmp_path/'result.scpt'), '-'],
        input=script, capture_output=True, text=True,
    )
    assert compiled.returncode == 0, compiled.stderr
    assert (tmp_path/'result.scpt').is_file()
