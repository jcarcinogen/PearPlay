# Fedora 44 GNOME — RPM installation

**Linux x86_64 only. The verified Fedora RPM is published in the [0.2.5 helper preview](https://github.com/jcarcinogen/PearPlay/releases/tag/v0.2.5). The Chrome Web Store offers extension 0.2.5; 0.2.6 is the pending extension update.** Requires glibc 2.43+. Mac support is coming soon.

## What was verified

On Fedora 44 Workstation / GNOME, glibc 2.43, with SELinux enforcing and firewalld active:

- GNOME Software opened the local RPM, displayed its MIT license and third-party warning, and installed it after normal local administrator authentication.
- The installed **PearPlay Setup** desktop entry opened the actual browser-selection dialog. Chromium alone was selected in an isolated configuration tree. Connect, repeat/repair, and Disconnect browsers worked; repair left the exact registration unchanged.
- Fedora's native Chromium 153.0.8010.52 (not the Flatpak) loaded the production-identity unpacked extension, connected to installed helper 0.2.5, and reported missing after disconnection and after package removal. Fresh isolated profiles proved the missing-host negative control. The browser sandbox remained enabled.
- Three actual setup-page **Find my TV** scans found the Apple TV and another video-capable receiver; the latter remained labelled compatibility unverified. No PIN, pairing, or playback was attempted.
- GNOME Software removed the package; the RPM database and executable path confirmed absence. Graphical reinstall failed with **“Failed to run transaction: Not authorized.”** The normal `sudo dnf install` fallback then reinstalled the same RPM. Installed integrity, unprivileged self-test, graphical reconnection, and real Chromium connection passed afterward.
- The RPM has 853 root-owned entries, no install/remove scriptlets, and no user-profile or credential files. Directories/executables are 0755; data is 0644. The installed native manifest is user-owned and 0600.

This is not a Store installation, Brave test, Flatpak test, cross-version upgrade, or TV playback verdict. Initial GNOME Software package transactions used the preceding candidate. After review found an additional executable license file, the final RPM was rebuilt and its full install/remove/reinstall lifecycle repeated with DNF; all 703 installed regular files matched the final staging bytes, and its actual graphical setup plus headed Chromium discovery passed again. Graphical package-manager reinstall on the final artifact is not claimed. A handshake and receiver discovery do not establish moving video or audible sound. Existing Zenity and Avahi dependencies were already installed; their fresh installation was not exercised.

## Install the supplied RPM

Download [the Fedora RPM](https://github.com/jcarcinogen/PearPlay/releases/download/v0.2.5/pearplay-helper-0.2.5-linux-x86_64.rpm) and its [checksum](https://github.com/jcarcinogen/PearPlay/releases/download/v0.2.5/pearplay-helper-0.2.5-linux-x86_64.rpm.sha256). Both public downloads were retrieved without authentication and matched the tested local bytes.

1. Compare `sha256sum pearplay-helper-0.2.5-linux-x86_64.rpm` with `pearplay-helper-0.2.5-linux-x86_64.rpm.sha256` (the local test kit also includes `SHA256SUMS.txt`).
2. In Files, open the RPM with **Software Install / GNOME Software**. The verified invocation is `gnome-software --local-filename=/absolute/path/to/pearplay-helper-0.2.5-linux-x86_64.rpm`; the desktop's `application/x-rpm` association is `gnome-software-local-file-packagekit.desktop`. The file-manager double-click itself was not automated in this test.
3. Choose **Install**, review the third-party-package warning, and approve normal administrator authentication. The package is unsigned; a checksum checks bytes, not publisher identity. Do not disable signature checks, SELinux, or the firewall.
4. Open **PearPlay Setup** from the applications menu. Select only the browser you intend to connect. Fully quit/reopen that browser, then choose **Check connection** in the extension's Helper setup page.

If GNOME Software reports an authorization failure, confirm that the package is absent with `rpm -q pearplay-helper`, then use the normal terminal path from the download directory:

```sh
sudo dnf install ./pearplay-helper-0.2.5-linux-x86_64.rpm
```

Do not extract the RPM and register its temporary executable: the package manager owns the stable `/opt/pearplay/PearPlayHelper/PearPlayHelper` path. The RPM also owns the desktop entry and icon. Browser registrations belong to the signed-in user, never root.

### Browser requirements

Use a native RPM browser. Acer's pre-existing Chromium and Google Chrome were Flatpaks and were deliberately not used; Fedora's native Chromium was installed alongside them for this test. Snap/Flatpak native messaging remains unsupported. No Flatpak override, host-spawn bridge, or personal-profile workaround is supplied.

Until the Store item is public, use **Load unpacked** with this repository's `extension/`. Its pinned public key supplies production identity `eoadahoncjfpnennmkjifohclbafjkol`. The current source catalog offers **Download for Fedora**. Reload the unpacked extension at `chrome://extensions`, then reopen Helper setup after updating source. Existing Store ZIPs are not automatically updated by a source catalog edit.

Brave was not opened, automated, registered, or used for verification. A later Brave test must first establish that it is a native browser, without changing its personal data. Browser connection is not Brave playback certification.

## Repair and removal

End any active cast and fully quit the affected browser before maintenance.

- **Repair:** open PearPlay Setup → **Connect or repair browsers**, select the intended browser, and restart it. Matching registration is reused; unknown or changed files are preserved, not overwritten.
- **Disconnect:** open PearPlay Setup → **Disconnect browsers**, select the intended browser. Saved TV pairing remains. A fresh native connection should now report missing.
- **Remove the package:** after disconnection, use GNOME Software → **Uninstall**, or:

```sh
sudo dnf --setopt=clean_requirements_on_remove=False remove pearplay-helper
```

The option avoids removing dependencies as part of this bounded operation. Package removal does not delete browser data or pairing. Reinstall the same RPM, reopen PearPlay Setup, select the browser, and fully restart it. Removing the extension alone does not remove the helper.

## Reproduce the Fedora build and checks

Keep the canonical checkout on its shared volume and venv/build/test output machine-local. The target is Fedora 44 x86_64, not an older-Fedora compatibility claim. The existing RPM branch is reused, not a parallel installer implementation.

```sh
# Build prerequisites need normal administrator approval.
sudo dnf --setopt=install_weak_deps=False install rpm-build nodejs chromium
python3 -m venv "$HOME/.cache/pearplay-fedora/venv"
"$HOME/.cache/pearplay-fedora/venv/bin/python" -m pip install -r requirements.txt pyinstaller pytest
mkdir -p "$HOME/.cache/pearplay-fedora/tmp"
export TMPDIR="$HOME/.cache/pearplay-fedora/tmp" PYTHONDONTWRITEBYTECODE=1
umask 077
# --output must name a new directory outside the source tree.
"$HOME/.cache/pearplay-fedora/venv/bin/python" scripts/build_helper.py \
  --extension-id eoadahoncjfpnennmkjifohclbafjkol \
  --output "$HOME/.cache/pearplay-fedora/build"

RPM="$HOME/.cache/pearplay-fedora/build/pearplay-helper-0.2.5-linux-x86_64.rpm"
python3 tests/verify_fedora_rpm.py "$RPM"
# After approved installation, run this WITHOUT sudo:
python3 tests/verify_fedora_rpm.py "$RPM" --installed
"$HOME/.cache/pearplay-fedora/venv/bin/python" -m pytest -p no:cacheprovider tests -q
node --test tests/extension/*.test.mjs tests/brand.test.mjs
CHROME=/usr/bin/chromium-browser PEARPLAY_BROWSER=chromium PEARPLAY_PRODUCTION=1 \
  PEARPLAY_BINARY=/opt/pearplay/PearPlayHelper/PearPlayHelper \
  node tests/browser/onboarding.mjs
```

The automatic onboarding test uses generated rehearsal UI with the production identity and no invented public Fedora URL. The separate headed GNOME rehearsal used the unchanged production `extension/` source and real dialogs. Both are unpacked-extension tests.

CIFS can synthesize executable bits on all source files. The builder now explicitly normalizes bundled Python/JSON/PNG data and LICENSE to 0644 while preserving actual executable modes and avoiding symlink targets/source mutation. The regression test and the original RPM both failed before the fix; the rebuilt package passed.

See [STATUS.md](../STATUS.md) and `assets/evidence/fedora-44-0.2.5.json` for the result, local artifact hash, and remaining release gates.
