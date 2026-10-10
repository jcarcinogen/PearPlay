# Windows helper 0.3.0 — unsigned engineering preview

## Scope

The Windows x64 helper reuses PearPlay's pinned pyatv 0.18.0 transport and native protocol. It is not a new AirPlay implementation. Chrome's production extension ID is `eoadahoncjfpnennmkjifohclbafjkol`; the installed manifest permits exactly `chrome-extension://eoadahoncjfpnennmkjifohclbafjkol/`. The frozen entry point rejects different origins and argument-based extension-ID overrides. Chrome's optional `--parent-window=N` is accepted, validated, and ignored (no browser HWND access).

The installer is a per-user, self-contained PyInstaller executable containing the entire frozen native host, Python runtime, dependencies, licenses and build metadata. End users do not need Python. It writes no administrator, machine-wide, firewall, SmartScreen, Defender or execution-policy settings. Chrome is the only registered browser in this preview; Brave/Chromium/Safari registration is not implemented on Windows.

## Install and maintain

Run `pearplay-helper-0.3.0-windows-x86_64-unsigned.exe` as the ordinary signed-in Windows user. Double-click presents a native Yes/No confirmation for install/upgrade and a completion message. It deliberately uses a console-subsystem bootloader: Windows native messaging requires inherited stdin/stdout, which a windowless PyInstaller helper does not reliably provide. A console may therefore be visible during setup. The native host remains a console executable, with no setup dialog on Chrome's native invocation.

Terminal actions (replace the file path with the downloaded installer):

    .\pearplay-helper-0.3.0-windows-x86_64-unsigned.exe install
    .\pearplay-helper-0.3.0-windows-x86_64-unsigned.exe repair
    .\pearplay-helper-0.3.0-windows-x86_64-unsigned.exe upgrade
    .\pearplay-helper-0.3.0-windows-x86_64-unsigned.exe connect
    .\pearplay-helper-0.3.0-windows-x86_64-unsigned.exe disconnect
    .\pearplay-helper-0.3.0-windows-x86_64-unsigned.exe uninstall
    .\pearplay-helper-0.3.0-windows-x86_64-unsigned.exe self-test
    .\pearplay-helper-0.3.0-windows-x86_64-unsigned.exe verify-payload

`install` refuses an existing receipt. `repair` requires the same version and restores missing recorded files. `upgrade` allows the same/newer version and refuses downgrades. Both refuse changed or foreign files rather than merge unknown code into the runtime. Fully end casting before any maintenance. An active pairing/playback lease blocks maintenance. Close other running helper/setup processes if Windows refuses to replace an in-use executable.

`disconnect` removes only matching registrations, leaving the helper and pairing. `connect` requires the recorded payload to be intact. `uninstall` removes only unchanged, receipt-owned files and matching registry keys. Changed and foreign files are preserved and reported; a receipt is retained when changed owned files remain. It never recursively deletes the PearPlay tree. It always preserves saved TV pairing. The downloaded installer is not installed into its own removal target and is not deleted by uninstall; retain it for maintenance, then remove that download yourself if desired. There is no Apps & Features/uninstall shortcut in this preview.

Fully quit and reopen Chrome after registration changes, then use the extension's Check connection action. Registry registration alone is not proof that Chrome connected.

This build is unsigned. Windows may warn or block it. Do not disable SmartScreen/Defender, change execution policy, or use an elevation workaround. A signed consumer release and owner-observed GUI/Chrome testing remain release gates.

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

Windows discovery uses pyatv's existing multicast/unicast scan. No Avahi/Bonjour service or firewall exception is installed. If existing network policy blocks discovery/playback, this helper reports the failure; it does not change security policy. Windows responses advertise `firewallSupport: false` and reject firewall operations. Receiver scanning, pairing, playback, stop and timing/event-channel behavior still require actual owner/receiver acceptance tests.

## Build from source

Build natively on Windows x64; PyInstaller is not a Windows cross-compiler. Keep source canonical and build from an explicit test/build staging snapshot with no Git checkout or secrets. Use a new output directory outside source. The Python builder inventories installed tools/dependencies first; PowerShell/.NET/IExpress are not required because PyInstaller supplies the self-contained installer.

An isolated Python 3.11 environment requires:

    pyatv==0.18.0
    PyInstaller==6.21.0
    pytest==9.0.2

With an existing isolated Python:

    C:\path\to\venv\Scripts\python.exe scripts\build_windows_helper.py --inventory
    C:\path\to\venv\Scripts\python.exe -m pytest -q tests\test_windows_source.py tests\test_windows_installer.py tests\test_windows_native.py
    C:\path\to\venv\Scripts\python.exe scripts\build_windows_helper.py --output C:\path\outside\source\new-build

The optional `scripts/build_windows_helper.ps1` inventories tools and can prepare an isolated environment using an explicitly supplied existing/approved uv executable. It never downloads/installs a global tool or changes script policy. If policy blocks the PowerShell driver, leave it blocked: direct uv/Python executable commands are the independent supported build path. Do not invoke a script-execution-policy bypass.

Direct isolated uv environment setup, if dependencies/runtime installation has been explicitly authorized:

    set UV_CACHE_DIR=C:\path\to\work\uv-cache
    set UV_PYTHON_INSTALL_DIR=C:\path\to\work\python
    set UV_PYTHON_BIN_DIR=C:\path\to\work\bin
    C:\path\to\approved\uv.exe venv --python 3.11 --managed-python --no-project C:\path\to\work\venv
    C:\path\to\approved\uv.exe pip install --python C:\path\to\work\venv\Scripts\python.exe pyatv==0.18.0 PyInstaller==6.21.0 pytest==9.0.2

The builder freezes and exercises the native host, tests CR/LF-bearing frame headers, bounded oversize rejection, compiled-origin override rejection and EOF exit, embeds/verifies the exact ZIP, then requires real Win32 fixture tests. Those install the actual frozen payload into a random fixture directory, register a random HKCU test key (not Chrome), run the installed executable, repair a missing executable, perform same-version upgrade/uninstall, and verify fixture DPAPI pairing survives. Every build saves dependency/license metadata, source hashes, artifact SHA-256 and an explicit `chrome_tested:false` / `receiver_tested:false` report. A failed gate does not produce a successful build report.

## Evidence and remaining gates

Read the durable `WINDOWS-HANDOFF.md` and `build-report.json` beside the preview artifact for the actual commands, hashes and results. Portable source tests are not Win32 execution evidence; the Win32 fixture log and frozen executable smoke results are separate. Do not publish this preview as a signed or TV-verified release.
