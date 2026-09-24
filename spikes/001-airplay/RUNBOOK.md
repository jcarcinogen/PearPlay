# AirPlay transport gate (upstream pyatv 0.18.0)

**Verdict: PARTIAL — pairing and discovery work; live video/audio failed on AirPlay 2 SETUP.** Offline tests pass. Parent/user must observe both moving video and audible audio. No extension or UI is implemented.

Live evidence (Acer → Living Room Apple TV 4K gen 3, tvOS 26.6): pairing succeeded; `play_url` never reached `/play`. pyatv 0.18.0 AirPlay 2 `_setup_base` timed out. `--sample mp4` now uses MDN CC0 H.264+AAC (Google Big Buck Bunny is HTTP 403 here). `prepare_connect` forces AirPlay 1 for the next live check; that path has not been sent to the TV.

## Linux usage after parent deploys source

From `~/Projects/PearPlay` on Acer, use the existing `.venv` (Python 3.14.7, pyatv 0.18.0). Do not invoke `atvremote`; this CLI uses `asyncio.run`.

```sh
.venv/bin/python spikes/001-airplay/pearplay.py scan
# If multicast is empty, replace RECEIVER_IP with the receiver address:
.venv/bin/python spikes/001-airplay/pearplay.py scan --host RECEIVER_IP
.venv/bin/python spikes/001-airplay/pearplay.py pair --host RECEIVER_IP
.venv/bin/python spikes/001-airplay/pearplay.py play --host RECEIVER_IP --sample mp4 --play-timeout 120
.venv/bin/python spikes/001-airplay/pearplay.py play --host RECEIVER_IP --sample hls --play-timeout 120
```

Pair requires exactly one receiver; `--identifier` can disambiguate the identifier shown by scan. PIN is read with `getpass` from the terminal, preserves leading zeros, and refuses the echoed-input fallback. Network pairing stages have `--timeout` (default 15 seconds); waiting for the human to enter the PIN is intentionally interactive, not timed.

`--stdin` accepts **one newline-delimited HTTP(S) URL**. It does not decode, trim, reorder, or normalize the URL. Userinfo, local paths, controls, whitespace, bad ports, and backslashes are rejected. URLs never appear in CLI arguments, logs, or JSON events. Use a trusted producer piped to stdin or protected input redirection; do not put a signed URL in a shell command/history. Example with a preexisting private input file outside the repository:

```sh
.venv/bin/python spikes/001-airplay/pearplay.py play --host RECEIVER_IP --stdin < /path/outside/repository/private-url-input
```

During playback, from another terminal on **the same Linux host and user**:

```sh
.venv/bin/python spikes/001-airplay/pearplay.py status
.venv/bin/python spikes/001-airplay/pearplay.py stop
```

These control the active PearPlay process via a private Unix socket. A fresh upstream AirPlay-only connection cannot stop another connection's stream: its `remote_control.stop()` only cancels that connection's local play task. Therefore stop/status deliberately do not create a misleading fresh receiver connection. `status` reports local pending-call state, not receiver media metadata. `stop-request-accepted` acknowledges the local controller accepted stop; it does not prove the TV stopped. There is no general remote-control/Companion pairing in this spike.

## Result semantics

- `play-call-started`: invocation beginning; HTTP acceptance is **unknown**.
- `play-call-returned`: upstream coroutine returned, **not proof of accepted HTTP request, displayed video, or audio**. pyatv can return after polling finds no media.
- Public `play_url` provides no accepted-request callback and stays open for the entire media duration. We do not patch private transport internals to fabricate one.
- `--play-timeout` defaults to 900 seconds. A finite 120-second test may cut a working long video short. Timeout exits 1 with `stage=play`, `type=TimeoutError`; it is not a passing transport result.
- Ctrl-C closes resources and exits 130; visual receiver state remains unverified.
- Exit 0: requested local operation completed. Exit 1: operational failure, timeout, missing receiver/session, unsupported runtime. Exit 2: invalid input. None is a visual/audio verdict.
- AirPlay pairing credentials are reused by identifier when reconnecting; `--host` is a discovery fallback, not an override of stored receiver identity.

## Security and scope

Only `~/.local/state/pearplay/credentials.json` stores credentials. Directory is 0700, file 0600, same-user owned, one-link regular file. Writes use an exclusive temporary file, fsync, and atomic replace. Ancestors are opened with `O_NOFOLLOW`; symlinks, unsafe existing modes, malformed/oversized configs, and a state directory inside the source repository are rejected. XDG/CLI configuration-path overrides are intentionally absent. Pairing again replaces the one saved receiver.

`control.sock` is 0600 in that directory and normally removed on exit. A stale socket after SIGKILL causes a safe failure; the operator must confirm no PearPlay process remains before removing that specific socket. The CLI never automatically deletes a preexisting socket/symlink. No credential or URL is sent over this socket.

Upstream logging and stdout/stderr are suppressed while the API runs. Errors expose only an allowlisted exception type, fixed stage, and numeric HTTP status when available. AirPlay's exact `AuthenticationError('status code: NNN')` form is parsed narrowly; raw exceptions are never printed. Discovery omits names and arbitrary service properties and emits only IP, constrained identifier, protocol, count.

No fork or PR 2846 patch was applied. No commits, repository initialization, system installation, or author-initiated TV actions occurred.

## Offline verification

Source of truth: `<checkout>/PearPlay` on Mini. All tests use fake receivers and temporary private homes; no scan/pair/play/stop reaches a TV.

```sh
# Mini, stdlib only (actual python3 was Apple CLT Python 3.9):
python3 -m unittest discover -s tests -q
# Acer existing project venv, after parent deployment:
.venv/bin/python -m pytest tests -q
```

Verified on Acer Python 3.14.7 / pyatv 0.18.0: **17 tests passed, 12 subtests passed**. Mini: **17 tests passed**. Development used vertical RED/GREEN slices for URL framing, storage, scan, sanitized failures, pair, play lifecycle, sample timeout, control, argument/runtime guards, interruption, and safety regressions. Additional regressions cover absent receiver, malformed config, failed atomic replace, and unsuccessful pairing.

Acer test-only copy used `/tmp/pearplay-offline.17wuG6/`; this is not deployment. The existing Acer project `.venv` was untouched. Python 3.14 auto-unlinks Unix-server sockets on close; tests caught the resulting duplicate-unlink failure, now tolerated without hiding playback timeouts.

## API evidence / sources

- https://pyatv.dev/development/scan_pair_and_connect/
- https://pyatv.dev/development/stream/
- Installed Acer pyatv 0.18.0 signatures and sources inspected for `scan`, `pair`, `connect`, `PairingHandler`, `AppleTV.close`, `AirPlayStream.play_url`, `AirPlayPlayer`, `AirPlayRemoteControl.stop`, `HttpError`.
- MP4 uses pyatv's documented Google BigBuckBunny URL.
- HLS uses Apple's public bipbop_4x3 variant playlist.

Next gate: parent performs approved live sample tests and records observed video/audio, actual safe error event, and receiver response before browser work resumes.
