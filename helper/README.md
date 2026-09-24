# PearPlay native helper (experimental)

**Linux only. Mac support is coming soon.** Mac compatibility work is paused.
Linux Chrome is the verified playback baseline; other browser playback needs separate verification.
No Mac relay, WebKit, AVPlayer, or screen mirroring.

Requires Python **3.11+**, the existing unmodified `pyatv==0.18.0` environment,
and this checkout in place. No dependency installation is performed. `hello`
and protocol tests do not import pyatv; discovery/playback fail safely if the
runtime dependency is absent or has the wrong version. On the Mini, run helper
tests with `python3.11`, never Apple CLT `python3` (3.9).

## Install / uninstall (explicit opt-in)

Do not run these against a daily browser profile during testing. Choose the
actual 32-character `[a-p]` extension ID from your unpacked extension.

```sh
PY="$HOME/.local/share/pearplay/venv/bin/python"
CONFIG_PARENT="/absolute/path/to/isolated-config"
EXTENSION_ID="replace_with_actual_extension_id"
"$PY" helper/install.py install --extension-id "$EXTENSION_ID" \
  --browser chrome --config-parent "$CONFIG_PARENT" --python "$PY"
```

`--config-parent` is the browser **configuration parent**, not `Default` or an
individual profile directory. The installer chooses the folder from the OS.
Linux Chrome uses `google-chrome/NativeMessagingHosts`; Brave uses
`BraveSoftware/Brave-Browser/NativeMessagingHosts`; Chromium uses
`chromium/NativeMessagingHosts`. The normal configuration parent is `$HOME/.config`.
An isolated browser must actually use the matching configuration tree.
Quit Chrome fully after initial registration; reloading the extension is not enough.

Mac install directions are retired. Prior runtime/signing findings are preserved
in [paused Mac research](../docs/mac-runtime-identity.md), not offered as a workaround.
Never borrow another app’s permitted interpreter or disable security to obtain access.

Repeat the exact command with `uninstall` instead of `install`. Installation
creates only a manifest and a shell launcher. Existing unequal files are
never overwritten. Uninstall removes only exact expected content with matching
ownership, mode, regular-file type and single link. Modified/unknown files,
directories, source, the interpreter/venv, and credentials are preserved.
Repeat the original ID, Python path, config parent and source location for
ownership comparison. No receipt, service, socket, packages or firewall rules
are installed. Missing source/runtime files do not prevent comparison/removal.

## Discover / pair manually

```sh
"$PY" helper/native.py discover --host 192.0.2.10
"$PY" helper/native.py pair --identifier AA:BB:CC:DD:EE:FF --host 192.0.2.10
```

These are documentation-only example addresses. Discovery without `--host`
tries pyatv multicast first. If that is empty, Linux uses `avahi-browse` when
that command exists. If `avahi-browse` is absent, the helper falls back to
`dns-sd` and keeps Apple TV IPv4 addresses only, then unicast-scans those
addresses. A pasted literal IP skips browse. Do not hardcode a receiver
address in source. Pairing
uses the existing spike's AirPlay pairing implementation and hidden `getpass`
PIN entry; echoed fallback is forbidden. It writes only the existing secure
single-receiver `~/.local/state/pearplay/credentials.json` Store (0700 directory,
0600 atomic file, no symlinks). Pairing another receiver replaces that one
record; do so only intentionally. `pairing_required` includes static CLI
instructions. Browser requests cannot pair, supply credentials or select
configuration paths.

## Native contract v1

Host name `com.pearplay.helper`. Use a persistent `connectNative` port, not
one-shot messaging. The launcher and helper enforce exactly
`chrome-extension://EXTENSION_ID/`; missing, different, extra or malformed
origins fail closed. Each native connection owns its Host and transport.

Request: `{v:1,id:"request_1",op:"hello",args:{}}`. IDs are nonempty ASCII
`[A-Za-z0-9_-]`, at most 64 characters. Only the four envelope keys are accepted.

- `hello`, `status`, `stop`, `pause`, `resume`: empty args only.
- `discover`: empty args, or `{host:"literal-IP"}`.
- `start`: exactly `{receiver:"discovered-identifier",host:"literal-IP",url:"https://…"}`.
  Both identifier and address must match discovery on this native connection;
  transport rescans and verifies the stored receiver identity before connecting.

UTF-8 JSON is framed with a four-byte little-endian unsigned size. Maximum
frame is 65536 bytes. Duplicates, non-finite numbers, unknown fields, invalid
UTF-8, truncated/oversized frames and malformed URLs fail closed. Partial
headers and bodies have 10-second deadlines; an idle port has no hold limit.
URLs are bounded to 16384 characters, not normalized, and kept in memory only.
Raw dependency logs, prints, exceptions and receiver names are not forwarded;
receiver labels are the static `Apple TV`, and scan responses are bounded.

Responses/events contain `v,id,ok,state,evidence,capabilities`, with static
`error` when needed. Asynchronous events use `id:"event"`. Capabilities are
exactly `hello,discover,start,status,stop`. `pause`/`resume` are recognized but
return `unsupported`: no unverified rate-control capability is advertised.

## What state means (important)

Playback uses **the existing `spikes/002-command/command.py` Backend and
Session**, encrypted upstream HAP/event channels, type-130 setup and the command
queue. It does not invoke stock `play_url` or modify spikes. UDP timing remains
49170, with no firewall changes. Setup/event waits are bounded; feedback and
transport stay alive until receiver completion, failure, stop or port EOF.

`playing` with `evidence:"protocol"` means a receiver playing event, **not moving
video or audible sound**. Visual/audio verification requires a human TV trial.

**Stop currently cancels and closes only this helper's transport.** It returns
`stopped` with `evidence:"unverified"`; it does not prove that the TV stopped.
Use the physical remote if needed. Restart accepts a fresh start after cleanup,
not a promise of receiver-side seamless switching. Pause/resume are unsupported.

An exclusive 0600 `helper.lock` under the secure Store directory prevents
concurrent helper playback/pairing. The inode is intentionally retained and
reused, never unlinked while another process could hold it. Locks are released
on cleanup/process exit. This coordinates helpers, not independently executed
old spikes or other AirPlay apps; do not run those concurrently.

## Offline verification

```sh
python3.11 -m unittest discover -s tests -p 'test_helper*.py' -q
# In an isolated copy on Linux using the existing project venv:
~/Projects/PearPlay/.venv/bin/python -m pytest tests -q
```

Tests exercise real framed subprocess launchers, exact-origin rejection,
reversible installation in temporary config directories, real command Session
with an injected network boundary, local-only stop/restart/EOF cleanup, locking,
secure Store fixtures, validation and sanitization. They do not contact a TV,
pair a real receiver, write real credentials or alter a browser configuration.
