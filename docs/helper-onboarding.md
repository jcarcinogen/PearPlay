# Helper onboarding and packaging

## Architecture decision

One self-contained helper payload per machine, separate user-scoped native-messaging registration for Chrome, Brave and Chromium. The Web Store extension ID is pinned at build time; development packages must be explicitly marked. No wildcard origins, remote executable code in the extension, login agent, HTTP listener, or cloud service.

Use the existing ownership-safe installer and flock-based playback lease. Registration repair only restores missing files or accepts exact owned bytes; unknown/modified files remain untouched. Payload upgrades belong to the OS package manager and retain a stable binary path. Pairing state stays outside the payload, shared by browsers under one OS user.

Use native OS dialogs (AppleScript on macOS, Zenity on Linux) for browser selection and repair/remove. The helper binary runs native messaging when invoked by a browser and setup when launched by the user. Linux packages require Zenity for graphical setup; native playback itself does not.

The extension opens a local setup tab on first install only. Its privileged API is restricted to handshake and explicit receiver discovery; it cannot start playback, pair, or install software. Missing helper and missing browser registration are indistinguishable from the extension and use shared recovery instructions. Public download links stay unavailable until a release catalog contains published, platform-specific assets for the actual extension ID.

## Verification and build workflow

See [the durable verification record](../assets/evidence/helper-onboarding-verification.md) for tested browser versions, exact scope and remaining gates. The tip badge is bundled locally at the bottom of the popup.

Build on the target OS in a dedicated machine-local Python environment with PyInstaller and the project's pyatv dependencies. Keep environments and build output outside the shared source checkout. Each build writes `dependency-versions.json`, third-party notices, smoke results and `build-report.json` with artifact hashes. These records describe the actual build; they do not claim bit-for-bit reproducible packages.

```sh
python scripts/build_helper.py --extension-id YOUR_EXACT_EXTENSION_ID --development --output /absolute/machine-local/new-build-directory
```

Use the public fixture ID from `tests/browser/fixture-key.json` for isolated browser tests only. For a regular unpacked install use its actual extension ID. Production builds require the permanent store ID in `extension/releases.json`, a project license, and on macOS the `--sign-app`, `--sign-installer` and `--notary-profile` options. No signed release has been exercised yet.

macOS emits a `.pkg` containing PearPlay Setup.app. Linux uses native `makepkg`, `dpkg-deb` or `rpmbuild` when available; unavailable formats are reported rather than substituted. Build Debian/Fedora artifacts on supported distribution baselines, not merely on a newer-glibc host.

## Release gates

- This Mac currently has no Developer ID signing identity. A local unsigned package is not a notarized consumer release.
- A permanent PearPlay Chrome Web Store ID has not been supplied. Development fixtures are not publishable IDs.
- Chrome is the playback baseline. Brave, Chromium, packaged macOS playback, distro-specific installation and sandboxed browser packages need separate evidence.
- Package builds must bundle Python and pyatv, include third-party notices, and pass native hello/status plus dependency smoke checks without touching the TV.
- No public release, network discovery, pairing, or casting is authorized in this implementation run.
