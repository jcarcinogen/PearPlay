# PearPlay native helper — development preview

The Chrome extension/helper candidate targets Linux, Mac and Windows. Safari extension development is paused; no WebKit/AVPlayer/Mac relay or screen mirroring is part of this helper. See [cross-platform status](../docs/cross-platform-preview.md) for artifact versus source-only states and remaining gates.

Extension candidate 0.3.1 is unpublished. Existing public helpers are 0.3.0 for Mac, Windows and Debian, and 0.2.8 for Fedora/Arch. New same-version helper candidates are distinct unpublished artifacts. Mac and Windows Apple TV picture/sound have owner evidence; Windows pause/resume/end-session also passed. New Windows branded GUI distribution is blocked by Application Control; Mac remains unsigned/not notarized. Public Store 0.2.9 was verified during preparation. See current STATUS and exact hashes; historical checkpoints are not current gates.

## Runtime and installation

Source runtime requires Python 3.11+ and `pyatv==0.18.0` from requirements.txt. Packaged helpers bundle the runtime; users should not choose an arbitrary Python. Native hello/protocol validation is distinct from discovery/playback dependencies. Keep venvs/runtime/state machine-local, not shared across operating systems. Do not use Apple CLT Python 3.9 for the documented test path.

[Consumer installation](../docs/install.md) preserves Linux native package/checksum/security instructions. Mac/Windows setup requires a tested supplied candidate artifact and its exact guide, not guessed commands from a source-only checkout. Do not disable Gatekeeper, remove quarantine, or bypass SmartScreen/Defender. Historical Mac Terminal install is retired, not a fallback permission workaround.

## Source registration — isolated Linux developer opt-in

Do not run against a daily browser profile during tests. Use the actual 32-character `[a-p]` extension ID; production is `eoadahoncjfpnennmkjifohclbafjkol`. An isolated browser must use the corresponding configuration tree.

```sh
PY="$HOME/.local/share/pearplay/venv/bin/python"
CONFIG_PARENT="/absolute/path/to/isolated-config"
EXTENSION_ID="replace_with_actual_extension_id"
"$PY" helper/install.py install --extension-id "$EXTENSION_ID" \
  --browser chrome --config-parent "$CONFIG_PARENT" --python "$PY"
```

The configuration parent is not `Default` or an individual profile directory. Linux paths below it are `google-chrome/NativeMessagingHosts`, `BraveSoftware/Brave-Browser/NativeMessagingHosts` and `chromium/NativeMessagingHosts`. Normal Linux parent is `$HOME/.config`. Fully quit and reopen the browser after registration; reloading the extension is not enough.

Repeat the exact original arguments with `uninstall` instead of `install` to compare/remove owned source registration. Existing unequal/unknown files must not be overwritten or removed. Preserve ownership/mode/regular-file/single-link checks, original ID/runtime/source/config paths and any original Python-path override. Registration removal preserves source/runtime and pairing; it is not package removal or credential deletion.

## Platform registration and pairing boundaries

- Linux: separate browser registrations to a shared per-user helper/state.
- Mac: Chrome and Brave share the Chrome native-host location. Connect/disconnect affects both; do not represent them as independent registrations. Chromium is separate. `docs/mac-runtime-identity.md` is the Mac worker's current signing/identity evidence, not permission to bypass Apple protections.
- Windows: normal-user Chrome native-host keys in HKCU (not HKLM) and user-local installed files; DPAPI plus user-local access controls for pairing. POSIX permission semantics are not Windows security evidence. Exact installer/lifecycle/browser/DPAPI tests must run on Windows.

Pair independently on each OS. DPAPI-protected Windows pairing is not portable between users/machines/OSes; do not copy state into or out of Windows. Ordinary disconnect/removal preserves saved pairing and unrelated/changed files. Tests must not read/copy/delete real credentials. The popup's masked PIN is the user input route; never put PINs, credentials or signed URLs in logs/public reports.

## Native contract and transport

Host `com.pearplay.helper`; use persistent `connectNative`. Origin allowlist is exact `chrome-extension://EXTENSION_ID/`; malformed/different/missing origins fail closed. Requests use bounded framed UTF-8 JSON with version/id/op/args; strict schema, sizes, deadlines and URL/receiver identity checks live in [contract/v1.md](../contract/v1.md), `helper/native.py` and protocol tests. The helper must revalidate receiver identity before send, never silently downgrade an authenticated saved-pair route.

Current backend has authenticated command-adapter transport and an affirmatively eligible no-PIN AirPlay V1 route. Do not interpret V1 request acceptance as protocol playing. Optional accepted-session/timing/receiver-issue metadata preserves older-client compatibility; no-PIN paths must not demand irrelevant timing rules. Linux receiver-scoped timing/firewall assistance is separate from installing a helper, never a blanket firewall-disable instruction. See the newest [STATUS](../STATUS.md) and [install troubleshooting](../docs/install.md#linux-timing-and-network-troubleshooting).

`playing` with `evidence:"protocol"` is receiver-reported state, not moving video/audible sound. `Sent` means accepted handoff, not watched success. End helper session tears down local transport with unverified evidence; use the physical remote if playback continues. Newer helper candidates provide session-bound Pause TV / Resume TV only for supported authenticated Apple TV sessions. TV seeking/timeline, volume and Picture in Picture are not helper capabilities; browser Picture in Picture is separate. Safari's native picker is not exposed.

One helper playback/pairing session can be active per OS user. End it in the browser that owns it before switching browsers. Locks/leases coordinate helper instances, not arbitrary other AirPlay apps. Do not delete a lock inode or force another user's/session's state during maintenance.

## Verification

An existing Python 3.11+ environment can run the source helper tests:

```sh
python3.11 -m unittest discover -s tests -p 'test_helper*.py' -q
node --test tests/extension/*.test.mjs tests/brand.test.mjs
```

These are developer verification commands, not a statement this entire checkout currently passes or an instruction to install tools. Offline/injected protocol, filesystem, registry and transport tests differ from real frozen/runtime/native-browser and human-TV results. Source-only Windows mocks on Mac/Linux cannot establish native Windows DPAPI or installer success. New platform workers must supply exact artifact hashes and native reports; [release gates](../docs/helper-onboarding.md#release-gates) and the [self-service checklist](../docs/cross-platform-preview.md#self-service-tv-check--instructions-not-a-completed-result) remain explicit.
