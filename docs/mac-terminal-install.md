# Mac Terminal installation — 0.2.3 development rehearsal — archived / paused

> **Current scope: Linux only. Mac support is coming soon.** Mac work is paused, with no release date. The historical Mac procedures/results below are not current install instructions or Linux release blockers. Resume only if Scott explicitly reopens Mac work; current Mac install/build entry points refuse new work. Existing installed runtimes and pairing remain untouched.


This replaces the unsigned Mac app/package route. No sudo, signing certificate or Gatekeeper change is used. It connects **Google Chrome**. A private Python runtime and `pyatv==0.18.0` are installed for your user; internet access is required for missing dependencies.

## Install

For the delivered test kit, use the already-extracted `pearplay-helper-macos` folder. A future public download will extract to the same folder name in Downloads.

If uv is not installed, install it once with the official command (downloads and runs Astral's installer without changing your shell profile):

```sh
curl --proto '=https' --tlsv1.2 -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh
```

Then run the helper installer. For a download extracted in Downloads:

```sh
bash "$HOME/Downloads/pearplay-helper-macos/install-macos.sh"
```

For Scott's shared test kit instead:

```sh
bash "/Volumes/IronWolf/Stuff/PearPlay Installer Test/0.2.3/pearplay-helper-macos/install-macos.sh"
```

Use the matching test extension supplied with this development bundle. It has fixture ID `iojhjdcndgfoalcialdlgklfdnlpmobf`, **not a production Web Store identity**. Do not use the test bundle's key for the store upload.

After success, fully quit and reopen Chrome. Open PearPlay → Helper setup → Check connection. The helper itself is installed in `~/.local/share/pearplay-terminal/0.2.3/`; it does not run out of the download folder or shared project checkout. You may delete the download after successful installation, retaining these instructions.

The command does not scan, pair or play anything. When you choose Find my TV, allow Local Network access if macOS asks. If discovery is empty, inspect the Local Network permission for the actual runtime launched by Chrome; do not disable macOS security or substitute Hermes's permitted Python. Mac network discovery and playback through this installation remain separate acceptance tests.

## Repair, updates and removal

Repeat the install command for the same release to repair missing registration. Existing modified or unrelated files cause a safe refusal, not an overwrite. If a legacy developer helper is connected, first use its original uninstall command; preserve its original arguments for rollback.

Disconnect this release with:

```sh
bash "$HOME/.local/share/pearplay-terminal/0.2.3/source/install-macos.sh" remove
```

This removes only exact owned Chrome registration/launcher files. It **keeps** the runtime, saved TV pairing and unrelated files. It is not a full disk cleanup. Before installing a different helper version, disconnect the old version using its own command, then run the new release's installer. Never recursively delete a pairing directory to fix installation.

## What has and has not been exercised

The real installer created a fresh machine-local Python environment, installed dependencies, and passed Google Chrome native hello/status, repeated-install repair, removal and a fresh host-not-found check in an isolated browser configuration. Daily Chrome and saved pairing were not changed. The test used an existing uv installation; the official no-uv bootstrap has not been re-run on a fresh Mac.

This does not yet prove macOS Local Network permission, TV discovery, pairing or visible playback. The Mac package route is retired for this delivery; earlier unsigned `.pkg` files are not the user deliverable.

Official uv bootstrap reference: https://docs.astral.sh/uv/reference/installer/
