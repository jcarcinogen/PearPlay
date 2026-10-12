# Windows helper 0.3.1 — unsigned engineering preview

## Scope

The Windows x64 helper reuses PearPlay's pinned pyatv 0.18.0 transport and native protocol. It is not a new AirPlay implementation. Chrome's production extension ID is `eoadahoncjfpnennmkjifohclbafjkol`; the installed manifest permits exactly `chrome-extension://eoadahoncjfpnennmkjifohclbafjkol/`. The frozen entry point rejects different origins and argument-based extension-ID overrides. Chrome's optional `--parent-window=N` is accepted, validated, and ignored (no browser HWND access).

The installer is a per-user, self-contained PyInstaller executable containing the entire frozen native host, Python runtime, dependencies, licenses and build metadata. End users do not need Python. It writes no administrator, machine-wide, firewall, SmartScreen, Defender or execution-policy settings. Chrome is the only registered browser in this preview; Brave/Chromium/Safari registration is not implemented on Windows.

## Install and maintain

Download `pearplay-helper-0.3.1-windows-x86_64-unsigned.exe` and the checksums from the [0.3.1 release](https://github.com/jcarcinogen/PearPlay/releases/tag/v0.3.1). End casting and fully close Chrome first. Run as your ordinary signed-in Windows user; no administrator access is requested.

The branded PearPlay window offers **Install / update**, **Repair installation**, **Connect Chrome**, **Disconnect Chrome**, and **Remove helper**. Select an action, choose Continue, read the confirmation and confirm. Saved TV pairing is kept. Buttons and closing are disabled during a transaction. Fully quit and reopen Chrome after changes, then use **Check connection** in the extension. Registration alone is not proof of connection or playback.

Repair restores missing owned files of the same version. Update permits the same or newer version, never a downgrade. Unknown or changed files are not overwritten. Removal deletes only unchanged receipt-owned files and reports preserved files; it never recursively deletes the PearPlay tree or saved pairing. Keep the downloaded installer for future maintenance. There is no Apps & Features entry in this preview.

Every shipped executable is windowed and branded, including manual native-host and maintenance launch. Native messaging uses inherited pipes without allocating a console. The installed native host offers Connect/Disconnect; use the downloaded installer for repair, update or removal.

**Unsigned Windows builds can be blocked by Smart App Control or Application Control. This occurred on the owner’s test PC. Stop if blocked; do not disable security, elevate to evade a block, or try an alternate executable.** Hosted Windows builds, exact-installer tests and GUI observations are distinct from acceptance under your PC’s policy. The SignPath Foundation application was declined because the project did not yet meet its public-visibility criteria. Trusted Windows signing is not currently available. No SignPath sponsorship is claimed.

For deliberate automation, the same installer accepts explicit `install`, `repair`, `upgrade`, `connect`, `disconnect`, `uninstall`, `self-test`, or `verify-payload` actions when stdout is redirected/captured. With no action, it opens the confirmation UI. Ordinary users should use the branded window, not a terminal.

## Executable branding

The installer, maintenance executable and native host embed the original colored PearPlay ICO at 16/24/32/48/64/128/256 pixels. Build gates verify the PE resources, GUI subsystem, native framing and initial frozen window title/icon/cancel. Real Tk confirmation/progress/result tests use fixture operations; this does not claim a successful owner-policy installation.

## Exact owned locations

Locations are resolved with Win32 `SHGetKnownFolderPath(FOLDERID_LocalAppData)`; `LOCALAPPDATA` environment changes are not accepted as a state-path override.

    <LocalAppData>\PearPlay\helper\runtime\...
    <LocalAppData>\PearPlay\helper\com.pearplay.helper.json
    <LocalAppData>\PearPlay\helper\install-receipt.json
    <LocalAppData>\PearPlay\state\credentials.dpapi
    <LocalAppData>\PearPlay\state\helper.lock

Chrome registration is the default `REG_SZ` value of:

    HKCU\Software\Google\Chrome\NativeMessagingHosts\com.pearplay.helper

Both 32-bit and 64-bit views are checked/registered and read back. Foreign values, extra values/subkeys, registrations to a different target, unreceipted files, or changed file hashes cause refusal. No browser profile/history files are read.

## Security boundary

* Windows stdin and stdout use CRT binary mode. A dedicated daemon reader thread feeds a bounded two-chunk queue; the event loop remains available for playback/control work. EOF closes the host and active tasks. Partial frames retain the existing ten-second timeout and 65,536-byte frame limit. A stalled pipe does not leave an asyncio executor thread preventing process shutdown.
* Pairing credentials use current-user DPAPI (`CryptProtectData`/`CryptUnprotectData`), UI forbidden, application-specific entropy, and bounded input/output. Machine-scoped encryption and plaintext legacy fallbacks are absent. Failed decrypt/schema validation fails closed.
* PearPlay-owned directories/files have an explicit protected DACL granting full access only to the token user's SID and SYSTEM, with that user as owner. Existing inherited/extra grants are refused, not silently repaired with chmod.
* Each ancestor is opened with `FILE_FLAG_OPEN_REPARSE_POINT`; reparse points, UNC/device/relative/ADS/alias paths, non-fixed/non-NTFS volumes, and multi-link files are rejected. Ancestor handles omit `FILE_SHARE_DELETE` and stay held during operations, preventing ancestor rename/replacement.
* A share-mode-zero handle on the never-unlinked `helper.lock` is the actual cross-process lease. A second process receives a sharing violation/busy; process death releases the kernel handle. This is not an advisory JSON marker.
* Pairing is outside the installer-owned helper tree. Installer tests use generated fixture credentials only.
* ZIP input is bounded, checks original (pre-Windows-normalization) names, rejects traversal/ADS/device names, duplicate case-insensitive names, symlinks, encryption and file/directory collisions.

The boundary does not defend against malware already running as the same Windows user, administrators, SYSTEM, or a modified unsigned installer supplied by an attacker. DPAPI protection is not a substitute for authenticating a release. Cross-user decrypt rejection follows the Windows DPAPI boundary but was not exercised with a second OS account in this work.

Ordinary installation failures attempt rollback and verify registry/files/receipt readbacks. `transaction.json` remains if a transaction or rollback is interrupted. Later maintenance fails closed rather than guessing ownership. Automated power-loss recovery is not supplied: preserve the journal/receipt and seek engineering review; do not delete unknown files or remove the journal merely to force installation.

Windows discovery uses pyatv's existing multicast/unicast scan. No Avahi/Bonjour service or firewall exception is installed. If existing network policy blocks discovery/playback, this helper reports the failure; it does not change security policy. Windows responses advertise `firewallSupport: false` and reject firewall operations. Recorded Windows Chrome/Apple TV owner checks cover scanning, pairing, picture/sound and physical pause/resume/session ending on tested streams; broader receiver and stream behavior is not generally verified.

## Build from source and verification

The [helper workflow](../.github/workflows/helpers.yml) builds on Windows x64 using official Python 3.13.16 with complete Tk, pyatv 0.18.0, PyInstaller 6.21.0 and pytest 9.0.2. Managed Windows Python 3.11.15 was found to lack a required Tk theme; binary/protocol success alone did not prove GUI startup. Do not skip the GUI gates.

Use an existing approved environment: `python scripts/build_windows_helper.py --output <new-directory-outside-source>`. The builder does not install tools or bypass security. See [CI documentation](helper-ci.md).

Native gates cover DPAPI/ACLs, receipt/hash/registration readback, frozen native framing and origin rejection, real Tk fixture states, and exact frozen initial windows with clean cancel. On disposable hosted Windows only, the exact shipping installer is exercised through install, repair, update, disconnect, reconnect and removal. No owner registry is used for that test. Build reports distinguish native/hosted acceptance from real Chrome, receiver and owner-policy evidence.
