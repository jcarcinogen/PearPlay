# Helper onboarding and packaging

**Linux only. Mac support is coming soon.** No Mac release date is promised. Mac work is paused and does not block Linux release.

## Current delivery decision

- **Linux:** a self-contained Python/pyatv helper in a native distro package. Open PearPlay Setup to connect browsers. First launch selects browsers; subsequent launches offer maintenance.
- **Mac:** no current installer or download. Source/runtime/signing experiments remain archived for a future explicit decision to resume; do not replace security settings or reuse another application's permitted Python.
- A Web Store extension cannot silently install its native helper; installation is an explicit separate step.

The existing Web Store item's public key was verified to derive to `eoadahoncjfpnennmkjifohclbafjkol`. The current manifest, release catalog and production 0.2.5 helper pin that identity; `extension/releases.json` lists the matching x86_64 `.deb` and Arch downloads at the [0.2.5 preview release](https://github.com/jcarcinogen/PearPlay/releases/tag/v0.2.5). The extension is not yet submitted or public in the Web Store. The earlier development ID `hljhooeofdjbikkhbklccnlnladdbkfb` is historical, not this store item's ID. The rehearsal fixture ID `iojhjdcndgfoalcialdlgklfdnlpmobf` and `tests/browser/fixture-key.json` must never become the production allowlist/key.

## Boundaries

No login agent, persistent HTTP listener, cloud relay, firewall/DNS changes, privileged browser registration or wildcard extension origins. Canonical source remains on IronWolf; installed payloads, venvs, build outputs and credentials are machine-local.

The Linux package manager owns the shared payload. Browser registrations are per OS user and protected by exact-byte/mode ownership checks. Unknown or modified files are preserved. The payload path stays stable across package updates. End casting before maintenance; disconnect browsers before removing the package. Saved TV pairing is not automatically erased.

## Linux build

Use the target distro's machine-local venv with PyInstaller and `pyatv==0.18.0`:

```sh
python scripts/build_helper.py --extension-id YOUR_EXACT_EXTENSION_ID --development --output /absolute/machine-local/new-build-directory
```

This is a developer command, not consumer onboarding. Build reports include artifact SHA-256, dependency versions/notices and smoke results. Linux packages declare Zenity, distro Avahi utilities and the build host's glibc floor. Verify Avahi service availability and receiver-scoped network requirements on a clean desktop.

Do not convert Acer's glibc 2.44 Arch artifact into a generic Ubuntu package. Build `.deb` on the chosen Debian/Ubuntu baseline. Unavailable formats remain explicit gaps. Fedora and other distributions need separate evidence. The current builder rejects non-Linux hosts before creating build output; retained Mac internals are not a release route.

## Graphical installation evidence

The Xubuntu 26.04.1 live desktop's existing App Center installed the production `.deb` from a verified package-absent state: file manager **Open With → App Center**, **Install**, confirm the normal third-party-package warning, then **Installed**. Package database/logs and payload integrity agreed, saved pairing and registration metadata were unchanged, and restarted Chrome connected to helper 0.2.5 and discovered the Apple TV. No additional installer, changed default association or security workaround was used. Dependencies already existed; normal installed-system password authentication and a pristine dependency-download run remain outside this result.

The native XFCE default is GDebi. Its elevated window failed before installation with a GTK display-connection error in this live session, so do not advertise its route as passing. An earlier `engrampa.desktop` result came from an incomplete SSH environment, not the desktop's actual association. Evidence: `assets/evidence/xubuntu-gui-install-0.2.5.json`; consumer steps: [Install PearPlay](install.md#graphical-deb-installation--verified-xubuntu-route).

## Release gates

1. Unit tests and real isolated Chrome missing → connected → repair → remove → fresh host-not-found checks.
2. Linux package install/restart/repair/update/remove with human-confirmed discovery, pairing, moving video and audible sound. Acer 0.2.3 evidence is in STATUS; removal/reinstall is not a cross-version upgrade test. LG discovery is not LG playback support.
3. Independent Linux Brave/Chromium verification before claiming playback in those browsers. Chrome remains the verified baseline.
4. Non-Omarchy Linux: disposable Ubuntu VM/live distro, native Google Chrome, separately built `.deb` and LAN-reachable networking. Default VM NAT may hide multicast. Keep packaging-only results distinct from TV playback.
5. Verified production store identity, real published Linux downloads/checksums, final catalog, privacy disclosures, current screenshots and Scott's explicit submission approval.

`localInstallerTest:true` is limited to the generated fixture extension. It displays supplied package steps without inventing download URLs. Draft store ZIPs contain neither the fixture key nor that flag. Extension/helper 0.2.5 are the current production-ID candidates; 0.2.4 scope work and 0.2.3 Acer packages are historical checkpoints. The 0.2.3 → 0.2.5 Arch upgrade passed package integrity, installed unprivileged self-test, real Chrome connection/discovery and unchanged pairing checks. No new playback trial was performed during that upgrade. The `.deb` has separate Ubuntu VM and Xubuntu live graphical-install/playback evidence. See STATUS.md.

## Paused Mac archive

[Runtime identity/signing research](mac-runtime-identity.md) and [historical Terminal rehearsal](mac-terminal-install.md) preserve prior findings. They are not current install guides. New Mac install/build entry points stop with “Mac support is coming soon.” Receipt-guarded removal remains available for an existing installation, but this scope change uninstalls nothing.

Only if Scott explicitly reopens Mac work: revisit identifiable runtime, shared Chrome/Brave native-host paths, Apple signing/notarization, clean-machine consent, updates and human-observed playback. No signing purchase or Mac test is required for the Linux release.
