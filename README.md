# PearPlay

[![Tip with X Money](tip-with-x-money.svg)](https://x.com/scottito22)

Linux-first website video AirPlay sender. **FOX 13 Seattle live video+audio have been confirmed on the Living Room Apple TV through the Chrome extension and Linux helper, including helper stop and recast.** Public HLS was previously confirmed via the CLI spike. An actual ad/program transition and Brave remain unverified. PearPlay is a working name, not trademark-cleared.

## Current result

The Acer helper can discover the Apple TV, pair with an on-screen PIN, and store credentials outside the repository. On this LAN, inbound UDP timing must be allowed (temporary UFW rule on port 49170). With that in place, the experimental `/command` adapter (sanitized from pyatv PR #2846) played Apple bipbop HLS and FOX 13 Seattle live with visible video and audible sound. Upstream `play_url` still only buffered. See [STATUS.md](STATUS.md).

A successful HTTP response is not proof of playback. Human confirmation of video and audio is.

## Architecture

- Distro-independent Python helper: pyatv 0.18.0 plus a bounded experimental adapter, now also `helper/` Native Messaging (`com.pearplay.helper`).
- Brave/Chrome Manifest V3 extension in `extension/`: user-triggered source discovery, tab/frame-associated media candidates, explicit receiver selection. Chrome is the live-test baseline; Brave is not installed.
- Chrome Native Messaging is control only; never media transport. Contract: [contract/v1.md](contract/v1.md).
- Receiver fetches compatible HTTP(S) media directly. No transcode, Mac relay, cloud, or Omarchy dependency.
- Pairing secrets live in `~/.local/state/pearplay/` (directory 0700, file 0600). Signed media URLs stay transient and must never enter logs or reports.

## Linux setup (Acer, per-user, reversible)

Source of truth is the Mini's `~/Projects/PearPlay`. The Acer copy is a test tree. Do not sync `.venv` or credentials.

```sh
uv venv --python /usr/bin/python3 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m pytest tests -q
```

No system packages beyond Python 3, `uv`, and LAN access to the Apple TV. Do not run as root. This host's UFW default INPUT DROP blocks AirPlay timing unless a narrow UDP allow exists.

## Extension/helper prototype

See [helper/README.md](helper/README.md) for exact-ID per-user setup/uninstall and [tests/browser/README.md](tests/browser/README.md) for real Chrome evidence. Match installer `--config-parent ROOT/browser` with Chrome `--user-data-dir ROOT/browser/google-chrome`; a separate XDG_CONFIG_HOME alone was insufficient. Test profiles only; never use daily profiles for automation.

The helper's End session control stopped this FOX trial on the Apple TV (human-confirmed). That is not a general guarantee for every stream. TV pause/resume are unsupported. No local video is automatically paused; explicit user confirmation is required. Brave and an observed ad/program transition remain open.

## Run

Unicast discovery is required; multicast `pyatv.scan` returned nothing.

```sh
cd ~/Projects/PearPlay
.venv/bin/python spikes/001-airplay/pearplay.py scan --host RECEIVER_IP
.venv/bin/python spikes/001-airplay/pearplay.py pair --host RECEIVER_IP
```

Working playback path (experimental):

```sh
.venv/bin/python spikes/002-command/command.py --host RECEIVER_IP --sample hls --mode command --timing-port 49170 --timeout 15 --duration 60
```

Arbitrary authorized URLs only via stdin (never as a CLI argument):

```sh
.venv/bin/python spikes/002-command/command.py --host RECEIVER_IP --stdin --mode command --timing-port 49170 --timeout 15 --duration 180 < /path/outside/repository/private-url-input
```

`--duration` is a hold limit. Exiting with `TimeoutError` after confirmed playback means the helper stopped waiting, not that the TV failed.

Do not invoke upstream `atvremote` on Python 3.14; it crashes with `There is no current event loop`.

## Uninstall

Removes only PearPlay-owned files (`credentials.json`, `control.sock`) from `~/.local/state/pearplay/`. Unknown files are preserved.

```sh
.venv/bin/python spikes/001-airplay/pearplay.py uninstall
rm -rf ~/Projects/PearPlay/.venv
```

Also delete the temporary UFW timing rule if it is still present. Never `rm -rf ~/.local/state/pearplay` while unknown files may exist.

## Source and deployment

Mini `~/Projects/PearPlay` is authoritative. Acer `~/Projects/PearPlay` is the Linux test copy. No GitHub repository, commits, extension publication, or extra system packages are authorized.

Respect DRM, access control, geographic restrictions, and normal ad delivery. A `blob:` URL is not receiver-fetchable.
