# Real isolated Chrome/native smoke evidence

These are Acer-specific CDP integration probes, not unit-test mocks. They use Node 26 built-in WebSocket/fetch and installed Google Chrome 152.0.7977.82. No packages are needed. They do not scan, pair, start, or stop a TV. Synthetic MP4 bodies are deliberately not playable media: this verifies URL discovery, not decoding or playback.

## Verified result

- Unpacked source `/home/scott/Projects/PearPlay/extension` loaded using `Extensions.loadUnpacked`; actual ID `gndkmajngklgjkcmbolddaodljgoabma`.
- Real action popup opened with `Extensions.triggerAction` against a CDP **tab** target. Opening popup.html as a normal tab is correctly rejected by worker authorization and is not an equivalent test.
- Persistent real native port: hello/status returned idle, evidence none, capabilities hello/discover/start/status/stop. Pause/resume returned unsupported. The actual popup -> worker -> Native route also succeeded for hello/status; unsupported operations became ACTION_FAILED/HELPER_ERROR as implemented.
- Synthetic loopback page: one DOM MP4 candidate, then a distinct network HLS candidate, then a distinct network MP4 candidate; disable cleared collection. No candidate URL or response was injected into extension internals. Tests used actual video currentSrc and real fetch/webRequest events.
- Optional loopback permission was read back as `http://127.0.0.1/*`. developerPrivate.addHostPermission alone did not populate optional origins; a real chrome.permissions.request under CDP userGesture completed the grant.
- Sandbox page reported namespace, PID/network namespace and Seccomp-BPF sandbox enabled: “You are adequately sandboxed.” CDP socket was loopback-only.
- Exact manifest/launcher bytes and 0600/0700 modes were read back. Uninstall removed owned files, preserved unknown test sentinels, and a fresh real native connection then returned host-not-found. Extension uninstall was read back as an empty Extensions.getExtensions result.
- An initial Mini/Acer source mismatch in native.mjs, core.mjs and popup.html was caught. The authoritative Mini extension was rsynced, and native plus candidate tests rerun. `evidence/source-hashes.json` verifies final extension/helper/contract equality.

## Important configuration lookup result

With `XDG_CONFIG_HOME=ROOT/xdg` and `--user-data-dir=ROOT/profile`, installing under `ROOT/xdg/google-chrome/NativeMessagingHosts` returned “Specified native messaging host not found.” A host installed directly beneath the actual user-data tree succeeded.

The verified layout was:

```
--config-parent ROOT/browser
--user-data-dir ROOT/browser/google-chrome
XDG_CONFIG_HOME=ROOT/xdg
```

Do not infer native-host lookup from XDG_CONFIG_HOME when overriding user-data-dir. No production installer change was needed for this aligned layout.

## Artifacts and scope

Acer isolated root: `/home/scott/.cache/pearplay-browser.ONYwEh` (0700 creation). `profile` is a test-only symlink to `browser/google-chrome` for the CDP helper's DevToolsActivePort lookup, never an installer target. Chrome was always launched with the real directory path.

Owned Chrome PIDs 4093, 5126, and 6207 were closed and verified absent. The isolated profile, Chrome logs and unknown sentinels remain for inspection; native manifests/launchers and PearPlay extension registration are removed. No daily profiles, Brave, credentials, TV actions, packages, firewall, Pi-hole or git operations were used. Chrome itself performed normal component background activity despite disable-background-networking; this test does not claim Chrome had zero external network traffic.

Local evidence JSON files retain real tool results. `install-uninstall.json` covers all three temporary config-parent experiments; `install-uninstall-latest.json` covers the final authoritative-source run. `final.json` records post-uninstall host failure, sandbox status and extension removal. `closed.json` records process absence.

## Probe usage (explicit isolated setup only)

Scripts assume the Acer source path and verified unpacked ID above. Never point ROOT to a daily configuration. Launch an owned Chrome with a fresh root and:

```
--headless=new --user-data-dir=ROOT/browser/google-chrome
--remote-debugging-address=127.0.0.1 --remote-debugging-port=0
--enable-unsafe-extension-debugging --no-first-run
--no-default-browser-check --disable-background-networking
```

Create the test-only ROOT/profile link for cdp.mjs, or adapt its DevToolsActivePort path. Use helper/install.py with the actual extension ID and config-parent ROOT/browser and the existing project venv. Then run `node tests/browser/probe.mjs ROOT` and `node tests/browser/candidates.mjs ROOT` on Acer. The candidate probe asserts its outcomes and closes its loopback fixture server. The native probe saves raw responses for assertions/inspection.

`verify_uninstall.py ROOT browser` verifies exact owned files and invokes the real installer uninstall function. It deliberately preserves unknown sentinels. `finalize.mjs ROOT` expects the helper already uninstalled, verifies host-not-found, checks sandbox, removes the test extension, reads back removal and closes the owned browser. Recheck process absence afterward.
