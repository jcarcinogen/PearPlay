# PearPlay status

## Live Chrome FOX result — video, audio, stop, and restart human-confirmed

Chrome extension → Linux native helper → command-mode AirPlay on the Living Room Apple TV:

- Initial FOX cast: moving video and audible sound (human-confirmed).
- No ad observed even with Pi-hole blocking disabled; transition compatibility remains unverified.
- After Scott physically stopped the TV, leftover helper state was `error`/`unverified`. Popup stop then reported `stopped`/`unverified`.
- Recast `c35` (equivalent live masters sharing the same 720p–270p ladder): video and sound confirmed.
- Helper End session: Scott confirmed the Apple TV actually stopped.
- Recast `c39` after that stop: Scott confirmed video playing. He then restored Pi-hole blocking and deleted the temporary UDP 49170 rule while that stream was still playing.

Isolated Chrome PID 7736 / root `/home/scott/.cache/pearplay-live.tt628lkk` may still be running. Do not claim Brave, ad transitions, or invalid/expired-stream behavior. Pause/resume remain unsupported.

## Previous verification — Chrome integration passed, TV gate was pending

Actual Google Chrome 152.0.7977.82 on Acer, isolated headless profile with sandbox enabled: unpacked extension `gndkmajngklgjkcmbolddaodljgoabma`, action popup → worker → native helper hello/status succeeded. Pause/resume correctly rejected as unsupported. Real loopback DOM MP4 and network HLS/MP4 discovery passed (synthetic bodies, NOT playback). Install exact bytes/modes and ownership-safe uninstall verified; fresh native connection then reported host not found. Unknown sentinels preserved, extension registration removed, owned Chrome processes confirmed absent. Evidence: [tests/browser/README.md](tests/browser/README.md) and its evidence JSON.

Latest rerun: **16 Node tests passed; 46 Python tests plus 24 subtests passed on Acer**. Command spike unchanged. Candidate filtering now excludes recognized segments/DASH/WebM and shows hostname/format without signed paths/queries. Browser/helper/contract sources were synchronized for the final Chrome run.

Still pending: actual FOX cast through extension/helper, visible video/audio and observed ad/program transition with Pi-hole temporarily disabled; invalid/expired stream and receiver lifecycle live checks; Brave. Stop only ends helper transport, not verified receiver stop; pause/resume unavailable. Ask Scott to make TV available and approve narrow timing firewall rule before live tests. Brave remains on hold, not removed from original two-browser completion criteria.

The older checkpoint below is retained as history; its Chrome-not-tested and earlier test totals are superseded by this section.

## Gate: PARTIAL — transport proven; extension/helper built; Chrome/TV integration not live-verified

Architecture: Linux helper on the Acer sends a receiver-fetchable HTTP(S) URL over AirPlay. No Mac relay, mirroring, cloud, transcode, or Omarchy dependency. Mini `~/Projects/PearPlay` is source of truth; Acer is the Linux test host. Session model GPT-6-astra; Hermes global default unchanged.

Paused 2026-09-10 evening at Scott’s request. Resume by loading `linux-airplay-sender`, `browser-extensions`, `test-driven-development`, `modern-javascript`. Do not claim Chrome or Brave integration until isolated-browser evidence exists.

## Temporary firewall rule — removed per Scott

Scott reports deleting the receiver-only UDP 49170 rule commented `PearPlay temporary timing test`. This has not been independently verified with privileged UFW output. UFW remains required protection; ask before restoring a narrow timing rule for another live test. Do not disable UFW.

## What works (human-confirmed on TV)

- Pairing with on-screen PIN; credentials in `~/.local/state/pearplay/credentials.json` (directory 0700, file 0600). Reconnect without a second PIN.
- After the timing-port allow rule, AirPlay sessions reach the TV (no longer stuck on the home screen).
- **Public HLS (Apple bipbop), command-mode adapter:** Scott saw video and heard the bip/bop audio.
- **FOX 13 Seattle live, command-mode adapter, ~3 minutes:** Scott reported the stream played well with both video and audio. Playlist was captured in isolated Chromium (not daily Brave/Chrome), passed on stdin, never stored in the repo. CLI exited `TimeoutError` at `--duration 180` while playback was still the observed success; that timeout is a hold limit, not a visual failure.
- Unicast discovery: Living Room Apple TV 4K (gen 3), tvOS 26.6, AppleTV14,1.
- Missing-receiver and no-session status paths return sanitized errors.

## What is built but not live-verified

- Shared contract: `contract/v1.md`. Native host `com.pearplay.helper`.
- Linux helper: `helper/native.py`, reversible installer `helper/install.py`. Wraps `spikes/002-command` Backend/Session, **not** stock `play_url`. Pause/resume return `unsupported` and are omitted from capabilities. Stop closes local transport only (`stopped`/`unverified`).
- MV3 extension: `extension/` (popup, service worker, content discovery, Native Messaging). User selects candidate and receiver. Local pause only after explicit “I confirm TV video and audio.” Optional host permission gates `webRequest`; listeners attach only after grant and detach on revoke.
- Mini automated: `python3.11 -m unittest discover -s tests -q` → 34 tests OK. `node --test tests/extension/*.test.mjs` → 11 passed. Apple CLT `python3` (3.9) is the wrong interpreter for helper port tests.
- Acer isolated helper copy previously: 46 passed, 24 subtests. Live Acer tree may lag Mini `extension/` / `helper/` until rsync.
- Chrome is the integration baseline. Brave install is on hold (Scott asked; Shields would confound site capture). Chromium is not a substitute for reporting Chrome or Brave.

## What failed or is incomplete

- First SETUP timeouts were **Acer UFW blocking inbound NTP timing**, not proven tvOS incompatibility. Attribution corrected after journal evidence.
- Baseline AirPlay v2 `play_url` with port 49170: HTTP accepted, TV showed a black buffering spinner for public MP4 and HLS. Not visual success.
- Forced AirPlay v1: `ConnectionLostError`, no picture.
- Public MP4 (MDN flower, 5.055s H.264+AAC): command-mode showed the flower video; Scott heard no sound. Too short to treat as an audio failure.
- Google Big Buck Bunny sample is HTTP 403 from Acer.
- FOX ad/program transition: Scott saw uninterrupted streaming and no ad. Apple TV uses Pi-hole DNS with enabled ad/tracker lists; this is a possible confounder, not evidence that an ad was blocked. Repeat from a fresh browser session with DNS blocking temporarily disabled on the relevant clients, then restore it. Wait for an actually observed transition; elapsed time alone is not proof.
- Stop/restart of an active FOX session: not live-tested (duration timeout ended the helper).
- Isolated Chrome load + Native Messaging hello/status: started 2026-09-10, stopped before evidence. No extension ID recorded.
- Brave: binary still absent; do not install unless Scott asks again.
- Uninstall: offline tests pass; not run against live credentials or a live native-host install.
- Acer Chrome verification child was interrupted; leftover `/tmp` isolated configs on Acer may exist and should be inspected, not assumed gone.

## Compatibility table

| Capability | Automated/offline | Actual receiver / browser | Verdict |
|---|---|---|---|
| Acer SSH / isolated venv | Commands succeeded | N/A | Verified |
| pyatv multicast discovery | Returned zero | Not detected | Fallback needed |
| Avahi + pyatv unicast discovery | Device/model/software | Advertisement only | Discovery only |
| Pairing + credential persist | Tests pass | PIN pairing succeeded; 0700/0600 | Verified |
| Reconnect without new PIN | Tests pass | Stored credentials reused | Verified |
| Timing UDP through UFW 49170 | Kernel blocks on random ports | SETUP proceeded after allow | Required for this host |
| Baseline v2 `play_url` + fixed timing | HTTP accepted | Buffering spinner, no A/V | Failed visually |
| AirPlay v1 `play_url` | Connect helper tests pass | ConnectionLostError; no A/V | Failed |
| Public MP4 command-mode | Tests pass | Flower video; no confirmed sound | Partial (clip 5s) |
| Public HLS command-mode | Tests pass | Video + audible bip/bop | Verified |
| FOX 13 live video + audio | Stdin URL tests pass | Played well, video and audio | Verified (CLI spike) |
| FOX ad/program transition | N/A | No ad observed; Pi-hole enabled | Not verified |
| Stop/restart live session | Helper local tests pass | Not live-tested on FOX | Partial |
| Invalid/expired media | Missing receiver timeout | Not a media-expiry test | Partial |
| Helper protocol / install | Mini 34 tests; Acer copy 46+24 | No live native host | Offline only |
| Chrome native messaging | Node 11 tests | Isolated Chrome load interrupted | Untested live |
| Brave native messaging | N/A | Browser not found | Untested |
| Uninstall owned state only | Tests pass | Not run live | Offline only |

## Dependencies and commands

- pyatv 0.18.0, Acer Python 3.14.7, pytest 9.1.1; Mini helper tests need python3.11, not Apple CLT 3.9
- Experimental adapter: `spikes/002-command/` (sanitized subset of PR #2846, head `8848ad3fd9ae46b8eb733bfc667b536a28f04c5a`, unmerged). No raw HTTP logging, no biplist, no global monkeypatch. Working playback remains `--mode command --timing-port 49170`.
- FOX capture: isolated Playwright Chromium, hosts only in reports (`foxvideo-fts.akamaized.net` master playlist, HTTP 200, no ENDLIST).

## Resume next

1. Rsync Mini `extension/`, `helper/`, `contract/`, `tests/` to Acer (no `.venv`, credentials, spikes overwrite). Confirm spike `command.py` hash still `259ab4a03dc36e284b568bb9d93d9a170a4df2e19d82075f8c0af61730d29906`.
2. Isolated Chrome `--user-data-dir` must match installer `CONFIG_PARENT/google-chrome` so NativeMessagingHosts is found. Never daily profile.
3. Load unpacked, record exact `[a-p]{32}` ID, install native host, prove hello/status, then synthetic candidate selection. No discover/play until Scott makes the TV available.
4. Ask before restoring UDP 49170 and before temporarily disabling Pi-hole for a FOX recast.
5. Brave remains optional and later; Shields off if used.
