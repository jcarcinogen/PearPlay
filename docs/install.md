# Install PearPlay locally

PearPlay is experimental and manually installed. Linux Chrome playback is the verified path. macOS has a native-host installer and discovery adapter; end-to-end playback remains unverified. Brave and Edge are not verified targets.

## Before you start

- Google Chrome, Git, Python 3.11+ and `uv` available on your machine.
- An Apple TV on the same network. Use only media you are authorized to access.
- A stable location for the checkout. The native launcher refers to its absolute path; moving or deleting it breaks the registration.
- A machine-local Python environment. Do not share a venv or pairing credentials between operating systems.

The following commands are for your deliberate installation. They download source and dependencies. The brand refresh itself installs nothing.

## 1. Get the source and runtime

From the directory where you keep projects:

```sh
git clone https://github.com/jcarcinogen/PearPlay.git
cd PearPlay
uv venv --python 3.11 "$HOME/.local/share/pearplay/venv"
uv pip install --python "$HOME/.local/share/pearplay/venv/bin/python" -r requirements.txt
```

`requirements.txt` pins `pyatv==0.18.0`. It does not install pytest. The standard-library helper tests do not require a live TV or pyatv for their injected boundaries, but real discovery/playback require the pinned runtime. Do not run the installer as root.

## 2. Load the extension

Open `chrome://extensions`, turn on **Developer mode**, choose **Load unpacked** and select this checkout’s `extension/` folder. Copy the exact extension ID displayed by Chrome: 32 lowercase letters from `a` through `p`. The installer rejects placeholder text and malformed IDs.

## 3. Register the native helper

Run from the checkout. Replace the placeholder with your actual extension ID.

### Linux Chrome

```sh
EXTENSION_ID="paste_your_extension_id_here"
PY="$HOME/.local/share/pearplay/venv/bin/python"
CONFIG_PARENT="$HOME/.config"
"$PY" helper/install.py install --extension-id "$EXTENSION_ID" \
  --browser chrome --config-parent "$CONFIG_PARENT" --python "$PY"
```

The installer writes under `google-chrome/NativeMessagingHosts` beneath that configuration parent. It does not install packages, services or firewall rules. When multicast discovery is empty, the helper can use an existing `avahi-browse` installation before trying unicast discovery.

### macOS Chrome — experimental

```sh
EXTENSION_ID="paste_your_extension_id_here"
PY="$HOME/.local/share/pearplay/venv/bin/python"
CONFIG_PARENT="$HOME/Library/Application Support"
"$PY" helper/install.py install --extension-id "$EXTENSION_ID" \
  --browser chrome --config-parent "$CONFIG_PARENT" --python "$PY"
```

The installer writes under `Google/Chrome/NativeMessagingHosts`. Registration is not a discovery or playback test. **Python must be allowed to access the local network.** In the recorded development setup, the uv-managed interpreter was blocked when Chrome launched it, and scans returned empty. The proven workaround on that machine used an already-granted Python executable plus the venv’s site-packages via the installer’s optional `--pythonpath` argument.

That machine-specific workaround is documented in [helper/README.md](../helper/README.md#macos-chrome-unpacked-install); it is not a universal macOS installation recipe. If discovery remains empty, inspect macOS Local Network permissions and the interpreter Chrome actually launches. Do not copy or replace an interpreter binary to change its identity. Using a different granted interpreter requires compatible Python versions and an absolute site-packages path. Retain the exact `--python` and `--pythonpath` arguments for a later uninstall.

The discovery adapter falls back to `dns-sd` when Avahi is absent. It filters for Apple TV IPv4 addresses. This does not establish macOS playback support.

### Restart Chrome

Fully quit and reopen Chrome after the initial native-host registration. Reloading the extension alone is not enough. For later extension-only edits, reload the extension and then the webpage.

The configuration parent is not Chrome’s `Default` profile folder. Custom `--user-data-dir` launches may look for native hosts under a different tree: see the [isolated-browser evidence](../tests/browser/README.md#important-configuration-lookup-result). Do not automate a daily profile for testing.

## 4. Use the popup

1. Open the video’s page in Chrome. Allow website access on a click. This version’s Find videos button requires all-sites access; the per-site grant does not yet enable it.
2. Play the video, choose **Find videos**, then choose a video. If needed, expand **Video not showing up?** and reload/look again.
3. Choose **Connect helper**, then **Find Apple TVs**. Select a receiver. The connection/address details include an optional literal address fallback.
4. Press **Send to Apple TV**. If pairing is requested, look at the TV and enter its PIN in the masked popup field. Do not put PINs, credentials or media URLs in bug reports.
5. Confirm moving video and audible sound yourself. Only then choose the optional local-pause confirmation.

TV pause/resume are unavailable. **End helper session** closes local transport and **does not confirm that the TV stopped**. Use the **physical remote** if playback continues.

## Linux timing and network troubleshooting

The tested Linux host required inbound UDP timing on port 49170 from the selected Apple TV. A local administrator should scope any needed firewall exception to that receiver, not the entire internet or LAN. Do not disable the firewall or blindly paste an example IP into a rule. This guide intentionally supplies no broad allow command. PearPlay does not modify firewall or DNS settings.

A visible receiver in discovery is not proof that its media or timing path works. An HTTP success or protocol playing event is not proof of TV picture and sound. Verify both on the actual receiver.

## Uninstall native-host registration

Use the exact original extension ID, Python path, optional Python path override, source location and configuration parent. Repeat the registration command with `uninstall` in place of `install`:

```sh
"$PY" helper/install.py uninstall --extension-id "$EXTENSION_ID" \
  --browser chrome --config-parent "$CONFIG_PARENT" --python "$PY"
```

If the original install included `--pythonpath`, include the identical argument. Only matching PearPlay-owned manifest/launcher files are removed. Modified or unknown files, pairing credentials, source and the venv remain. Remove the unpacked extension separately from `chrome://extensions`. See the helper documentation before separately removing stored pairing data; never recursively delete a state directory containing unknown files.

## Evidence and scope

Installer arguments and path handling: [helper/install.py](../helper/install.py). Native contract, identity checks, state meaning and privacy: [contract/v1.md](../contract/v1.md). Human playback results: [STATUS.md](../STATUS.md), newest first. These are manual instructions reviewed against source; this refresh did not perform a fresh daily-profile installation on either platform.
