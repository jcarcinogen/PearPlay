<img src="assets/brand/mark.svg" width="64" height="64" alt="PearPlay">

# PearPlay

### Your browser’s video. Your Apple TV.

Send a compatible stream directly to your TV—not a mirror of your desktop or a re-encoded copy. **Linux playback is verified in Chrome on a tested FOX stream. macOS playback is unverified.**

[![Tip with X Money](tip-with-x-money.svg)](https://x.com/scottito22)

[Install locally](#install) · [What is verified](#what-is-verified-today) · [How it works](#how-it-works) · [Product page source](docs/index.html)

<img src="assets/landing/hero.png" width="960" alt="PearPlay mark, a real extension popup capture using example data, and a schematic TV">

*Real popup, example data. The capture demonstrates the interface, not live playback.*

## What it does

PearPlay connects a desktop Chrome extension to a small, local Python helper. You choose a video and an Apple TV; PearPlay passes the media URL to the receiver. **The TV fetches the stream from the site.** Native Messaging carries control, not media.

- No screen mirroring, transcode, Mac relay for Linux, or PearPlay cloud service.
- No PearPlay account. Pairing credentials stay on your machine.
- An explicit handoff: grant access, choose what to send and where, then press Send. Local video does not pause automatically.

This is experimental software, not a Chrome Web Store release or an “every website” sender. **The extension requires a separate PearPlay Helper.** Its first-run setup tab checks the connection and explains installation or repair. Packaged installers are currently local development builds, not published downloads.

One packaged helper can be registered for Chrome, Brave and Chromium under the same OS user. Install the extension separately in each browser. Registration support is not a blanket playback compatibility claim; see the [onboarding verification and release gates](docs/helper-onboarding.md).

## How it works

1. **Allow and find.** On the video’s page, grant access on a click, play the video and choose **Find videos**. This version requires all-sites access for discovery.
2. **Choose the video and TV.** Select the stream, connect the helper and find Apple TVs on your network. Choose the receiver and pair if asked.
3. **Send and confirm.** Press **Send to Apple TV**. Check the TV for moving video and audible sound before pausing the browser video with the website’s own controls.

## What is verified today

| Path | Recorded evidence |
|---|---|
| Linux + Chrome extension + helper → Apple TV | FOX 13 live video and audible sound, human-confirmed |
| FOX pre-roll → program | Observed through the popup path with Apple TV DNS blocking enabled; PearPlay does not block ads |
| End helper session and recast | TV stopped in that FOX trial and recasting worked—not a universal stop guarantee |
| Public HLS command adapter | Video and audio human-confirmed through the earlier CLI path |
| Pairing and reconnect | Local credential storage and reconnect without another PIN confirmed |

A successful HTTP response or a helper “playing” event is not proof of picture and sound. Read the **newest entry first** in [STATUS.md](STATUS.md); older checkpoints are retained as history. [Claim-by-claim evidence](docs/claims.md) distinguishes source facts, automated checks and human TV observations.

### What is not done yet

- **macOS playback:** the native-host installer and discovery adapter are built; there is no recorded end-to-end playback verdict in `STATUS.md`.
- **Other browsers:** Linux Chromium has packaged-helper handshake/uninstall evidence, not TV playback evidence. Brave integration remains a release gate. Edge is not an installer target. Chrome is the playback baseline.
- **Broader failure/lifecycle trials:** invalid or expired streams and receiver lifecycle behavior are not fully live-verified.
- **Site-only discovery:** a per-site grant exists in the popup, but Find videos remains disabled without all-sites access.

## Honest limits

The Apple TV must be able to fetch an HTTP(S) media URL directly. A `blob:` URL is not a usable handoff; browser cookies are not transferred. PearPlay does not bypass DRM, geography or access controls, and does not block ads. Use media you are authorized to access. A source URL is not a promise of a particular resolution or compatibility.

**TV pause/resume are unavailable.** **End helper session** closes the helper connection and **does not confirm that the TV stopped**. Use the **physical remote** if playback continues. Use the website’s own controls for browser playback. PearPlay does not pause it automatically.

## Install

You need Chrome, Python 3.11+, `uv`, an Apple TV on the same network, and a checkout kept in place. These commands are instructions for a new installation; running them downloads the source and pinned runtime dependency.

```sh
git clone https://github.com/jcarcinogen/PearPlay.git
cd PearPlay
uv venv --python 3.11 "$HOME/.local/share/pearplay/venv"
uv pip install --python "$HOME/.local/share/pearplay/venv/bin/python" -r requirements.txt
```

Open `chrome://extensions`, enable Developer mode and load the checkout’s `extension/` directory. Copy its actual extension ID. Then register the native host:

```sh
EXTENSION_ID="paste_your_extension_id_here"
PY="$HOME/.local/share/pearplay/venv/bin/python"
# Linux:
CONFIG_PARENT="$HOME/.config"
# macOS instead:
# CONFIG_PARENT="$HOME/Library/Application Support"
"$PY" helper/install.py install --extension-id "$EXTENSION_ID" \
  --browser chrome --config-parent "$CONFIG_PARENT" --python "$PY"
```

Fully quit and reopen Chrome after the first registration. The helper installer does not install dependencies or change your firewall. On the tested Linux host, receiver-scoped inbound UDP timing on port 49170 was required. On macOS, Python Local Network permission can prevent discovery even after registration succeeds; **the generic macOS path is experimental, not a verified playback recipe**.

Read the [complete Linux/macOS install and uninstall guide](docs/install.md) before troubleshooting. Uninstall registration with the identical command using `uninstall` instead of `install`; unknown files, credentials, source and the Python environment are preserved.

## Privacy

The extension talks to a local native helper; media travels from the origin site to the Apple TV. Pairing credentials live in `~/.local/state/pearplay/credentials.json`, inside a `0700` directory with a `0600` file. The pairing PIN is submitted once and not persisted by the extension. Signed media URLs are transient, not copied into marketing assets or logs.

No telemetry endpoint or PearPlay account/cloud integration is present in the audited first-party extension/helper sources. That is a source-audit statement, not a claim that Chrome, dependencies or the origin site make no network requests. Local control does not make a stream anonymous. See the [audit scope and citations](docs/claims.md#privacy-audit).

## Inside PearPlay

- [Control contract and trust boundaries](contract/v1.md)
- [Native helper and installer details](helper/README.md)
- [Browser integration evidence](tests/browser/README.md)
- [Latest TV observations and historical checkpoints](STATUS.md)
- [Tests](tests/) · [Command adapter spike](spikes/002-command/README.md)
- [Brand sources and reproducible rendering](assets/brand/README.md) · [Positioning](docs/positioning.md)

No project-wide `LICENSE` has been selected. The experimental command adapter retains its [own license and provenance](spikes/002-command/LICENSE.md); that is not a license for the whole repository. The working name is not trademark-cleared.

---

PearPlay is independent and unaffiliated with Apple.
