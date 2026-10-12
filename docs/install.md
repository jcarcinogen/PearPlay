# Install PearPlay

**Cross-platform experimental release.** Helper 0.3.1 is available for Mac Apple silicon, Windows x64, Debian/Ubuntu x64 and Arch/Omarchy x64. Fedora retains helper 0.2.8. Mac and Windows packages are unsigned; Windows security policy may block installation. Do not disable security protections or remove quarantine. See the [Mac installation guide with screenshots](mac-install.md) for Apple’s per-item approval flow and stop conditions, and the [Windows guide](windows-helper.md). Safari extension development remains paused.

## Guided setup

The extension opens a setup tab on first installation. Use **Helper setup** in the popup to reopen it. A successful check is a local helper handshake, not TV playback. Choose **Find my TV** only when you want network discovery.

The Linux package supplies Python and dependencies. Open **PearPlay Setup**, select your browser, **fully quit and reopen it**, then choose **Check connection**. Later launches offer repair and disconnection. Website permissions remain separate.

Use the **[0.3.1 release](https://github.com/jcarcinogen/PearPlay/releases/tag/v0.3.1)** for Mac, Windows, Debian and Arch; the **[0.2.8 release](https://github.com/jcarcinogen/PearPlay/releases/tag/v0.2.8)** still supplies Fedora:

- [Ubuntu/Debian x86_64 `.deb`](https://github.com/jcarcinogen/PearPlay/releases/download/v0.3.1/pearplay-helper-0.3.1-linux-x86_64.deb): Ubuntu 22.04 baseline, glibc 2.35+.
- [Arch/Omarchy x86_64 package](https://github.com/jcarcinogen/PearPlay/releases/download/v0.3.1/pearplay-helper-0.3.1-linux-x86_64.pkg.tar.zst): glibc 2.35+.

[Fedora 44 x86_64 RPM](https://github.com/jcarcinogen/PearPlay/releases/download/v0.2.8/pearplay-helper-0.2.8-linux-x86_64.rpm) is also published, requiring glibc 2.43+. See [Fedora instructions and limits](fedora-install.md). No Linux ARM package is offered. Packages are unsigned: use the trusted GitHub release, compare each package with its own release’s `SHA256SUMS`, and use normal package-manager authentication without disabling security. Checksums detect mismatched bytes; they are not a signing certificate.

Install **[PearPlay 0.3.1 from the Chrome Web Store](https://chromewebstore.google.com/detail/pearplay/eoadahoncjfpnennmkjifohclbafjkol)**, then pin it to the toolbar. The public Details page was verified showing version 0.3.1, updated October 12, 2026. Developer mode and an unpacked source folder are not needed for Store installation. Load unpacked remains a developer option only. The packaged helper requires no Python setup or manual extension-ID command.

End casting and quit browsers before updating the package. Chrome Web Store updates do not update the helper. Disconnect browsers before package removal; saved TV pairing is preserved. Modified or unknown registrations are never overwritten or deleted. Remove a legacy source registration using its original installer before switching helper types.

Chrome is the Linux picture-and-sound baseline. Brave and Chromium have prior owner-reported playback, with audio/stream details not separately recorded; these are not new candidate tests. Snap/Flatpak browsers, beta/dev channels and custom layouts are not supported installer targets. Mac Chrome/Brave share one native-host registration (disconnect affects both); Chromium is separate. Windows candidate targets per-user Chrome/HKCU and DPAPI, not portable cross-OS pairing.

## Graphical `.deb` installation — verified Xubuntu route

Historical helper 0.2.5 graphical evidence (not a new 0.2.8/0.3.0 GUI pass): the tested Xubuntu route was:

1. In the file manager, right-click the downloaded PearPlay `.deb` and choose **Open With → App Center**.
2. Choose **Install**. Read the third-party-package warning and proceed only with a package you obtained from the trusted PearPlay release. Approve the normal administrator prompt if your system requires one; no security setting needs to be disabled.
3. Wait for **Installed**, then open **PearPlay Setup** from the applications menu, select Chrome, and **fully quit and reopen Chrome** before **Check connection**.

This route passed on the Xubuntu 26.04.1 live desktop using its already-installed App Center. No additional package manager or changed default association was needed. GDebi was the desktop's default, but its elevated window failed in that live session; use the tested App Center route instead. Other Debian/Ubuntu desktops may offer a different graphical installer. If no package installer is available, follow that distribution's package-install instructions rather than extracting the `.deb` as an archive. This is not a universal no-terminal Linux-install claim.

### Terminal alternatives

Ubuntu/Debian, after downloading the matching package:

```sh
cd ~/Downloads
sudo apt install ./pearplay-helper-0.3.1-linux-x86_64.deb
```

### Arch / Omarchy — step-by-step installation

Without a graphical package installer, use the **Terminal** app. Do not extract the downloaded file.

1. Click **Download for Arch / Omarchy** in PearPlay’s setup page. Save it in **Downloads**, keeping its original filename.
2. Open **Terminal**, paste this whole command, and press Enter:

   ```sh
   sudo pacman -U "$HOME/Downloads/pearplay-helper-0.3.1-linux-x86_64.pkg.tar.zst"
   ```

3. If asked, type your computer password and press Enter. **Nothing appears while you type the password—that is normal.** Review the installation prompt, then type **Y** and press Enter to continue. Wait until installation finishes.
4. Open **PearPlay Setup** from the app launcher and select your browser.
5. **Fully quit and reopen the browser.** Closing only a tab or reloading the extension is not enough. Open PearPlay’s **Helper setup** and click **Check connection**.

If Terminal says the file cannot be found, check that it is in Downloads and has the filename shown above. If installation fails for another reason, stop and seek help; do not disable package-signature checks.

For the Arch command above, move the package into Downloads first if your browser saved it elsewhere. For Ubuntu/Debian’s relative-path command, open a terminal in the download folder. Then open **PearPlay Setup**, select your browser, and **fully quit and reopen it**. To remove the packaged helper, first use PearPlay Setup to disconnect browsers, then remove `pearplay-helper` with your normal package manager. Saved TV pairing remains.

## Source installation — Linux developer fallback

These source-install commands apply to Linux only. The [Mac/Windows preview](cross-platform-preview.md#start-with-the-right-helper) uses supplied tested platform artifacts, not this Linux shell/venv path. The old Mac Terminal installer is historical, not the resumed app/pkg route.

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

### Other registered browsers

Repeat the registration command with `--browser brave` or `--browser chromium`, using the same Python environment. Unpacked extension IDs may differ by browser or path; use that browser’s actual ID. A published Web Store install uses the listing’s stable ID.

| Browser | Linux directory beneath configuration parent |
|---|---|
| Chrome | `google-chrome` |
| Brave | `BraveSoftware/Brave-Browser` |
| Chromium | `chromium` |

A browser installed later can be connected by reopening PearPlay Setup; installing another copy of the helper is unnecessary. If another browser is casting or pairing, end its helper session there first. No browser can stop another browser’s session through its own helper process.

### Restart Chrome

**Fully quit and reopen Chrome after the initial native-host registration.** Reloading the extension alone is not enough. For later extension-only edits, reload the extension and then the webpage.

The configuration parent is not Chrome’s `Default` profile folder. Custom `--user-data-dir` launches may look for native hosts under a different tree: see the [isolated-browser evidence](../tests/browser/README.md#important-configuration-lookup-result). Do not automate a daily profile for testing.

## 4. Use the popup

1. Open the video’s page in Chrome. Allow website access on a click. This version’s Find videos button requires all-sites access; the per-site grant does not yet enable it.
2. Play the video, choose **Find videos**, then choose a video. If needed, expand **Video not showing up?** and reload/look again.
3. Choose **Connect helper**, then **Find Apple TVs**. Select a receiver. The connection/address details include an optional literal address fallback.
4. Press **Send to Apple TV**. If pairing is requested, look at the TV and enter its PIN in the masked popup field. Do not put PINs, credentials or media URLs in bug reports.
5. Confirm moving video and audible sound yourself. Then use the website’s own controls if you want to pause the browser video.

Helper 0.3.1 supports Pause TV / Resume TV for supported authenticated Apple TV sessions. TV seeking, timeline, jumps and volume remain unavailable. **End helper session** closes local transport and **does not confirm that the TV stopped**. Use the **physical remote** if playback continues.

## Linux timing and network troubleshooting

The tested Linux host required inbound UDP timing on port 49170 from the selected Apple TV on the authenticated command route. No-PIN V1 receivers may not require this timing path. A local administrator should scope any needed firewall exception to that receiver, not the entire internet or LAN. Do not disable the firewall or blindly paste an example IP into a rule. This guide intentionally supplies no broad allow command; installation does not create firewall rules.

**Linux scoped assistance:** compatible helper/extension versions can expose **TV firewall permission** for timing-required receivers. Saved UFW settings can be checked without administrator access; an explicit permission change requests normal administrator approval for that selected receiver and UDP 49170 only. You may cancel it. Existing administrator rules remain; other firewalls need manual review. Source/extracted diagnostic helpers cannot perform privileged changes. The newest STATUS/package evidence supersedes older blanket "unreleased" helper claims; a new cross-platform candidate still needs its own acceptance. Mac and Windows do not inherit Linux UFW management.

A saved UFW rule is not proof that packets arrive, and a missing exact rule does not mean traffic is blocked: a broader existing rule may already allow it. No firewall permission fixes an unsupported video or incompatible TV.

A visible receiver in discovery is not proof that its media or timing path works. An HTTP success or protocol playing event is not proof of TV picture and sound. Verify both on the actual receiver.

## Uninstall native-host registration

Use the exact original extension ID, Python path, optional Python path override, source location and configuration parent. Repeat the registration command with `uninstall` in place of `install`:

```sh
"$PY" helper/install.py uninstall --extension-id "$EXTENSION_ID" \
  --browser chrome --config-parent "$CONFIG_PARENT" --python "$PY"
```

If the original install included `--pythonpath`, include the identical argument. Only matching PearPlay-owned manifest/launcher files are removed. Modified or unknown files, pairing credentials, source and the venv remain. Remove the unpacked extension separately from `chrome://extensions`. See the helper documentation before separately removing stored pairing data; never recursively delete a state directory containing unknown files.

## Evidence and scope

Installer arguments and path handling: [helper/install.py](../helper/install.py). Native contract, identity checks, state meaning and privacy: [contract/v1.md](../contract/v1.md). Human playback results: [STATUS.md](../STATUS.md), newest first. These docs/setup changes performed no daily-profile installation, credential access or TV trial. Native platform artifact evidence remains separate from the cross-platform intent.
