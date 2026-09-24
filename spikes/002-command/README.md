# 002: bounded `/command` experiment + fixed-port v2 control

## Verdict: PARTIAL — offline verified; receiver trial NOT performed

Question: after ruling out blocked inbound NTP timing, does authenticated stream
130 plus `/command` work where the original `/play` path does not?

**Run the fixed-port baseline first.** Parent observed active UFW with DROP input
and blocked UDP packets from the receiver to previous random timing ports. This
is a concrete competing explanation for SETUP timeouts. tvOS incompatibility is
not established. Parent reports Scott added a temporary receiver-only inbound UDP
49170 rule. This artifact neither inspects nor changes firewall rules.

## Manual commands (parent only, Acer, existing venv)

Copy this directory beside unchanged `spikes/001-airplay/` before use. No installs
needed on Acer. Requires Python >=3.11 and unmodified pyatv==0.18.0; runtime rejects
other declared versions. The guard does not hash installed source files.

```sh
cd ~/Projects/PearPlay
.venv/bin/python spikes/002-command/command.py --host 192.0.2.10 --sample mp4 --mode baseline-v2 --timing-port 49170 --timeout 15 --duration 30
# Only if baseline is insufficient and the user approves the next trial:
.venv/bin/python spikes/002-command/command.py --host 192.0.2.10 --sample mp4 --mode command --timing-port 49170 --timeout 15 --duration 60
# HLS: same command with --sample hls
```

`baseline-v2` directly instantiates upstream AirPlayV2, without MRP tunnel or the
001 forced-v1 setting, and passes the explicitly bound timing port. Its request
payloads/authentication/headers remain upstream. It holds the connection for
`duration` seconds after HTTP acceptance; it does NOT poll for completion or claim
visual success. Start operation is bounded by `timeout`.

`command` performs verify -> base SETUP -> encrypted event connection -> info ->
RECORD -> stream 130 SETUP -> four nested binary-plist `/command` requests.
Each request/connect and initial playing-state wait is bounded by `timeout`;
`duration` bounds the entire command session. It requires a playing event before
accepting stopped as completion; missing events/time limit are failures. Feedback
is sent every two seconds after startup while waiting. No replay/retry after a
potentially accepted command. No message-response waiter race or unbounded queue.

Both modes bind UDP 49170 by default and print `timing-bound` with only its numeric
port. Port conflict fails; no fallback to a random port. Ctrl-C/timeouts close TCP,
event, timing transports; baseline cancels and joins upstream feedback. Closing is
NOT proof that receiver playback stopped: use the physical TV remote as needed.
No stop RPC, pairing, credential writes, external-control socket or teardown
command is implemented. Parent must arrange removal of Scott's temporary rule.

Store and fixed public MDN flower MP4 / Apple bipbop HLS are imported from 001.
Only the saved receiver identifier is selected by targeted scan. No arbitrary URL
argument or signed URL is accepted. The CLI suppresses all upstream Python
logging and stdout/stderr to /dev/null; reports contain static stages, safe numeric
HTTP codes/port, and generic failures, never bodies, headers, credentials, names,
URLs, exception text or traceback. Importing the module is not a sandbox: launch
through main, not embedded into an app with unrelated logging requirements.

## Research: full PR diff and installed upstream inspected

GitHub API PR2846, open/unmerged, head
`8848ad3fd9ae46b8eb733bfc667b536a28f04c5a`, base
`d64a63f4aebeab8181426a4b6ae3a73d86b2b6f7`.
Source: https://github.com/postlund/pyatv/pull/2846
Full diff retrieved via `gh api repos/postlund/pyatv/pulls/2846 -H 'Accept: application/vnd.github.diff'`.
Compared to Acer's installed 0.18.0 AirPlayV2, RTSP, HAP verify/channel and timing
source; upstream v0.18.0 MIT license retained in LICENSE.md.

Relevant changes in PR:
- Adds stream type 130 setup, `/command` nested plist insertPlayQueueItem,
  isInterestedInDateRange, actionAtItemEnd=1, setRate=1.
- Corrects `X-Apple-Stream-ID` to `X-Apple-StreamID`, uses returned stream ID,
  changes command User-Agent to 870.14.1, and adds sessionCorrelationUUID.
- Event playback states replace `/playback-info` polling.
- Also adds biplist, auth sequence-template support, proxy changes, unsafe HTTP
  prints, module-global IDs/header mutation and potentially endless waits.
  Those unrelated/unsafe portions are NOT copied.

**Encryption is not newly enabled by this PR:** upstream verify_connection already
derives Control-Salt read/write keys and installs HAP encrypt/decrypt processors.
The PR leaves that function unchanged. Both use the same event HKDF labels.
The changed command HEADERS are used on `/command`, not base SETUP. RTSP SETUP
still uses upstream RTSP user-agent 550.10 and its own monotonically increasing
CSeq. The adapter intentionally retains this distinction, original auth and base
SETUP identity metadata; it does not claim the late command-header change fixes
an earlier SETUP hang. Correlation UUID is a real earlier payload difference but
not demonstrated causal. No encryption downgrade or global pyatv monkeypatch.

Unlike PR, session, client, item and channel IDs are generated per session; the
clientTypeUUID is kept as a protocol type constant. Exact acceptable channelID
format remains an interoperability uncertainty. No hardcoded captured sender ID
is reused for channelID. stdlib plistlib handles binary/XML; exotic plist values
that motivated biplist in the PR remain unverified. Event payload limit is 1 MiB;
malformed events close the event channel and the bounded startup/session expires.

## Verification and gaps

Offline RED/GREEN tracer slices exercised protocol ordering, unique IDs, timeout
and cancellation cleanup, missing/playing/stopped events, real loopback UDP bind
and release, dependency guard, baseline feedback cancellation, secure Store wiring
with fake credentials, HTTP error rejection, event HTTP ACK/decode/size limits,
upstream encrypted-channel arguments, hostile stream-ID rejection and CLI secret
suppression. Test doubles never connect to the TV. Real loopback bind uses an
available ephemeral port in tests, not the receiver or firewall test port.

Final full-suite execution: Mini Python 3.11.16 and Acer existing venv Python
3.14.7 each returned **32 passed, 12 subtests passed** (12 new command tests plus
20 existing tests). CLI --help executed on both. Acer tests run in a temporary
/tmp sandbox with the existing project venv; the live
project is NOT deployed by this subagent. No pairing/play/stop/scan against a real
receiver was executed. The private-API adapter is disposable, not production.
HTTP acceptance/event states remain protocol evidence only; video AND audio need
human confirmation. Do not build browser integration until the transport gate is
actually validated.
