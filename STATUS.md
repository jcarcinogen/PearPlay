# PearPlay status

**Current scope: Linux-only release target. Chrome and Brave are requested Linux targets. Mac support is coming soon. Mac tasks are paused and are NOT blockers for Linux release.**

## Production identity, Ubuntu VM and Xubuntu live playback — 0.2.5 candidate

The supplied Web Store public key derives exactly to **`eoadahoncjfpnennmkjifohclbafjkol`**. The manifest and release catalog now pin that identity, and production helper builds reject missing, malformed or mismatched public keys. The fixture key remains separate. Extension and helper versions are 0.2.5; Linux packages include the original project's MIT notice. These changes are not yet committed or published.

A disposable **Ubuntu 24.04.5 LTS x86_64** VM now runs on Acer with QEMU/KVM, an Xfce desktop and real Google Chrome **154.0.8037.57**. KVM enabled status, graphical desktop control and Chrome namespace/seccomp sandbox were verified. Canonical source is mounted **read-only** at the same path through 9p; no second working checkout was created. Builds and test profiles remain guest-local.

Built a production-ID-bound `.deb` on **glibc 2.39**, installed it with APT, opened the actual PearPlay Setup desktop entry, selected Chrome and verified the connected dialog plus exact production native-host allowlist. Real isolated Chrome passed missing-host → connected hello/status → repeat registration → removal/fresh missing-host. System package removal removed the payload; reinstall restored it and preserved the GUI-created registration. The project's MIT notice matched exactly. **68 Python tests and 38 extension/brand tests passed.** Evidence: `assets/evidence/ubuntu-0.2.5-installer.json`; package and full reports: `Stuff/PearPlay Installer Test/0.2.5/ubuntu/`.

**Limits:** the VM uses QEMU user-mode NAT. Avahi returned no LAN receiver advertisements. No VM pairing or playback is claimed, no host firewall/bridge change was made, and Acer's existing browser/pairing were not used by this test. APT installation is not a double-click package-manager pass. The existing Acer 0.2.3 human-confirmed playback remains separate evidence. First-boot vendor-data formatting was corrected; after reboot cloud-init reports done with no errors or recoverable warnings.

Independent read-only review found no blockers in production identity/key validation, fixture separation, MIT payload notice, version alignment or production browser-test mode. Parent verification remains 68 Python tests, 38 extension/brand tests, brand-asset checks and clean diff whitespace. See `assets/evidence/production-identity-0.2.5-review.json`; this source review is not transport or release approval.

### Same-LAN live-USB result

The Acer's Xubuntu live session reports **Ubuntu 26.04.1 LTS / glibc 2.43**, not the VM's 24.04 baseline. The exact Ubuntu-built production 0.2.5 `.deb` was installed with APT into the live overlay. Real headed Chrome 154.0.8037.57, with its sandbox verified and an isolated profile, passed missing-host → actual graphical Chrome registration → browser restart → connected helper 0.2.5. The native manifest authorizes only `eoadahoncjfpnennmkjifohclbafjkol`. The setup page found both Apple TV and the other AirPlay video receiver on the physical LAN.

The actual extension toolbar popup collected a public Mux HLS sample, selected the Apple TV and initiated fresh pairing. Scott entered the TV PIN directly in PearPlay, paired, pressed Send to TV, and **confirmed moving video and audible TV sound**. Readback subsequently reported `playing` with `protocol` evidence and no error. Sender pairing was absent before the test; afterward its file was owner-owned, regular, single-link and mode 0600. No PIN or credential contents were read. Existing installed-system pairing was not used or reset.

Both internal NVMe drives remained unmounted, and the firewall stayed inactive as it was on arrival. Native-window captures were black, so GUI visibility is human-confirmed rather than screenshot-proven. The live SSH configuration had omitted its drop-in Include; this was corrected and effective key-only authentication plus a fresh connection verified. Chrome/helper were left running after the successful cast. Evidence: `assets/evidence/xubuntu-live-0.2.5.json`; readable report: `Stuff/PearPlay Installer Test/0.2.5/xubuntu-live/RESULT.md`.

**Graphical-install follow-up passed:** after Scott approved ending the test and removing the live-session helper, the pre-existing App Center installed the exact `.deb` from a verified package-absent state. Actual Thunar **Open With → App Center** was exercised; App Center's Install and third-party-warning confirmation buttons led to Installed. Package database/logs and `dpkg --verify` agreed. Pairing and browser-registration inode/size/mtime/mode were unchanged, and restarted Chrome connected to helper 0.2.5 and discovered the Apple TV. Chrome is now connected and idle; playback was not repeated after this installation.

**Correction and limits:** the actual XFCE default is GDebi, not Engrampa; the earlier association query lacked the desktop's XDG environment. GDebi's elevated window failed before any package transaction with a GTK display-connection error; no authentication/display workaround was attempted. App Center required no additional installation or default change. Dependencies already existed, the normal installed-system password prompt was not exercised, and the extension remains unpacked rather than Store-installed. App Center's generic unknown-publisher/license and zero-size metadata can be polished separately. See `assets/evidence/xubuntu-gui-install-0.2.5.json` and the documented graphical route in `docs/install.md`.

### Arch production upgrade — verified on Omarchy Acer

Built the production-ID 0.2.5 x86_64 Arch package on glibc 2.44 and upgraded the installed 0.2.3-1 package with local sudo approval. The first artifact exposed an inherited-umask defect: root-owned `build.json` was 0600, although owner-run pre-install smoke passed. A regression test failed before the fix. Linux staging now normalizes directories/executables to 0755 and data to 0644, skipping symlinks and leaving source payloads untouched. The corrected artifact was rebuilt under umask 077; archive permissions, unprivileged installed self-test and `pacman -Qkk` passed (869 files, zero altered).

Real isolated Chrome 153.0.8010.47 passed missing-host → connected helper 0.2.5 → repeat connect → removal → fresh missing-host. Three actual setup-page discovery scans found Apple TV and the other video receiver with its compatibility-unverified label. The old fixture-bound Chrome registration was explicitly migrated using exact-byte ownership checks to authorize only the production ID; this is a test migration, not an automatic consumer migration feature. Existing saved pairing remained byte-identical and mode 0600 before and after all checks. All test Chrome/helper processes closed; firewall and daily browser session were untouched. No playback trial was performed in this upgrade pass.

**69 Python and 38 extension/brand tests pass.** Independent review of the permissions fix found no blocking security or logic issues. Corrected package SHA256: `aa2008cfb1107ff12a203f7d87fef80854d88618a741ca16026311fb8e24be93`. Evidence: `assets/evidence/arch-upgrade-0.2.5.json`; verified package/checksums/report: `Stuff/PearPlay Installer Test/0.2.5/arch/`. Private rollback/pairing backups remain Acer-local. The package is unsigned and unpublished; the extension was unpacked rather than Store-installed.

Remaining: Linux Brave/Chromium playback before those claims, published download assets/catalog and final store ZIP, reconciled dashboard disclosures, and explicit submission approval. Do not create a second store listing. Mac support is coming soon; Mac work remains paused.

## Historical Linux-only scope update — extension 0.2.4

This checkpoint is superseded by the production-identity/Ubuntu evidence above; retain its earlier measurements without treating its pending gates as current facts.

Mac compatibility work is paused, with no promised date. Extension popup/setup now stop on Mac before helper requests, site queries or download lookup. Legacy Mac download entries are filtered out. New Mac Terminal installs and non-Linux helper builds stop with the coming-soon message; receipt-guarded removal and historical internals remain available. No existing installed helper, runtime, TV pairing, firewall or daily browser configuration was changed.

Current local kit: `/Volumes/IronWolf/Stuff/PearPlay Installer Test/0.2.4/`. Extension is 0.2.4; Linux helper remains the unchanged tested 0.2.3 package. The former mixed-platform kit is preserved byte-for-byte under `archive/0.2.3/`; its previous entry point redirects to the current kit. The fixture ID remains separate from the supplied PearPlay ID `hljhooeofdjbikkhbklccnlnladdbkfb`; production dashboard/public-key verification is still a release gate.

Python 3.11 regression suite: 65 tests passed. Extension Node suite: 34 passed. Actual isolated Mac Chrome 153 negative-control checks passed for both popup and setup: coming-soon copy, hidden install/cast flow, zero helper/download requests and zero console exceptions. This is proof of the unsupported-platform boundary, not resumed Mac compatibility testing. Independent code review returned no concrete security or logic findings; `assets/evidence/linux-only-review.json` records its scope. Rendering/brand verification is recorded separately in `assets/evidence/render-verification.json` and the current scope report.

Remaining Linux gates: fresh non-Omarchy distro verification, cross-version upgrade, Linux Brave/Chromium playback evidence before those claims, verified store identity/key, real published Linux downloads/privacy URL and explicit submission approval. Mac signing, consent and playback work do not block these.

## Historical checkpoints — not the current task list

Mac procedures and “next” steps below are paused historical records. Resume only if Scott explicitly reopens Mac work. Earlier incomplete Linux checkpoints are superseded by the later human-confirmed Acer results. Preserve measurements; do not treat old directions as current setup guidance.

## Named Mac runtime — local tests pass in Chrome and Brave; Apple signing gates distribution (PAUSED / ARCHIVAL)

The build now uses PyInstaller's native `.app` BUNDLE layout rather than hand-wrapping an onedir tree. The finished app is sealed as `com.pearplay.helper`, contains its own runtime and PearPlay Local Network description, and keeps license/data files out of code-signing directories. Strict recursive signature verification and dependency self-test pass. A regression failed before the layout fix and passed afterward; **62 Python and 31 JavaScript tests pass**. The actual development package was rebuilt successfully. Independent read-only review of the bundling/signing changes and regression tests reported no concrete security or logic findings; this does not close the Apple-signing or consumer-installation gates.

Isolated Chrome connected, found Apple TV and LG, and passed repeat-connect/repair, missing-host, status and removal checks. The initial Brave test was contaminated by Brave's deliberate fallback to the standard Chrome native-host directory: a no-registration negative control unexpectedly connected to the old installed helper. Those initial Brave results are discarded. A corrected probe used an exclusively created, random test-only native-host name, pointing directly to the new app and authorized only for the fixture extension. Actual isolated Brave passed missing → connected → two scans finding both receivers → fresh browser → two more successful scans → removed/missing. The temporary manifest was exact-content checked, deleted and verified absent; existing production registration hashes and pairing remained unchanged.

**Brave runtime works, but the consumer Mac Brave registration path still needs correction:** the current installer assumes Brave's own config folder is its native-host directory, whereas Brave's source deliberately overrides it to Chrome's standard directory. Shared connect/disconnect semantics and browser detection need explicit tests before release. Do not confuse the uniquely named diagnostic registration with a passing production Brave installer.

**Not release-ready:** the local ad-hoc app is rejected by Gatekeeper (`spctl` exit 3), and Apple TN3179 calls for Apple-issued signing for reliable permission identity. This Mac has no valid code-signing identities. No security setting was disabled, no borrowed interpreter was used, and no daily helper was replaced. Mac video/audio, fresh-machine consent, upgrade permission persistence and notarized downloads remain unverified. Scott requested the no-Apple attempt first, with an explanation if Apple identity is necessary; [Mac runtime identity and signing](docs/mac-runtime-identity.md) records the evidence and Developer ID Application / Installer / notarization steps (Apple program currently US$99/year). No enrollment, purchase, commit, push or publication occurred.

Machine-local development build and logs: `<local-scratch>/pearplay-owned-runtime-integrated/`. The tested fixture ID is `iojhjdcndgfoalcialdlgklfdnlpmobf`, never a production identity. Earlier Terminal-route and Chrome-only conclusions below are historical and superseded by this section.

## Mac Terminal rehearsal — connection passed, discovery blocked (2026-09-23)

Scott installed the official standalone uv after the first command could not find it (Hermes's private uv was not a consumer prerequisite). The original Mac developer registration was exact-byte checked, backed up under `~/.local/state/pearplay-install-backups/before-terminal-t740axw7/`, and removed without touching pairing or the old runtime. The delivered 0.2.3 test extension uses fixture ID `iojhjdcndgfoalcialdlgklfdnlpmobf`.

The user's Terminal installer emitted only its generic preservation error. TCC logs at the failure timestamp identify Terminal as responsible for the uv Python process and deny `kTCCServiceSystemPolicyAppDataDetailed` access. The delivered `terminal-build.json` exists and is readable from Hermes; a reviewer's missing-build-file hypothesis was rejected. Running the same installer from Hermes succeeded and exact Chrome registration/launcher bytes were verified. Scott then confirmed Chrome's helper connection, but Find my TV returned no receivers and no Local Network prompt appeared. This is NOT a passing consumer Terminal installation or Mac playback test.

The installed private runtime (not Hermes's interpreter) discovers Apple TV and LG when launched from Hermes. A disposable real-Chrome profile pointing at that same installed runtime reproduces the ready handshake followed by empty discovery. Direct `/usr/bin/dns-sd` from Hermes sees both TVs. Therefore discovery is launch-context dependent; CLI success is not Chrome evidence. The uv Python has ad-hoc identity `-` and shares a Mach-O UUID with the separately signed Hermes Python; nehelper logs repeatedly mention the Hermes Python identity while processing the Chrome scan window. Apple TN3179 warns of unreliable identity tracking with ad-hoc signatures and shared executable UUIDs. This is a plausible identity/privacy issue, not a proven fix; no binaries were copied, signed or substituted and no permissions, firewall, DNS, or pairing were changed. System Settings was opened read-only to inspect Local Network.

Scott checked Local Network settings: four Google Chrome entries were present and all enabled. A further read-only native-host probe using the exact installed private Python found six Bonjour advertisements through DNSServiceBrowse with no policy-error callback in both launch contexts. However, a TCP connection to the discovered Apple TV's AirPlay port succeeded outside Chrome and returned macOS errno 65 (EHOSTUNREACH) from the Chrome-launched helper; the normal helper returned two receivers outside Chrome and zero inside. UDP socket connect alone succeeded in both contexts and is not proof of UDP delivery. This narrows the failure to direct LAN networking in the browser-launched process, not absent Bonjour advertisements or a visibly disabled Chrome switch. Shared runtime UUID/ad-hoc identity remains a strong hypothesis, not experimentally isolated causation. Probe files live in Hermes scratch and alter no production registration, permissions, signatures or pairing.

A disposable uv CPython 3.11.15 build with a different Mach-O UUID initially reproduced the same Chrome-child TCP errno 65 and empty discovery. Scott then reported allowing Python to find networks. After that approval, the disposable 3.11.15 Chrome native child discovered both receivers and connected to the Apple TV TCP port successfully, while a fresh isolated Chrome using the installed 3.11.16 still returned no receivers. Permission consent for the independent runtime is now demonstrated; it did not unlock the installed runtime. Scott subsequently confirmed that both visible Python 3.11 entries and every other Local Network entry were enabled. A fresh isolated-Chrome retest still reported helper ready but no TVs. Do not ask for more toggle changes or treat visible enabled switches as proof that macOS recognizes the installed executable correctly. The installed runtime identity issue remains unresolved; the successful temporary build is diagnostic evidence, not a deployable fix. No production Python downgrade or signature change was made. The temporary probe reused the installed 3.11 site-packages, stayed in scratch, and is not a deployable helper.

Source now catches `PermissionError` separately with errno and conditional App Data guidance instead of suggesting a conflicting helper. A regression test failed before this change and passed after; full verification: **61 Python tests and 31 JavaScript tests passed**. The delivered kit and installed receipt-guarded source are deliberately unchanged, so this diagnostic improvement is not deployed yet. Next: check the actual Chrome Local Network permission, reproduce the Terminal operation under the user's consent context, and only rebuild/reinstall a revised bundle after preserving the current receipt/registration lifecycle. No Mac discovery/playback pass, release, commit or push is claimed.

## Acer packaged-install rehearsal — user reports playback started

Scott removed the previous extension and fully quit Chrome. The old source-based Chrome registration/launcher were removed with the ownership-safe uninstaller after exact-byte verification; rollback copies are in Acer `~/.cache/pearplay-before-installer-1zkdm6o1/`. Existing pairing and source venv were retained.

Scott then installed the development package, opened PearPlay Setup, deselected Brave/Chromium and connected Chrome. After restarting Chrome, the extension reported connected. The setup-page scan initially found only Apple TV; the later playback-popup scan showed both Apple TV and LG C5. On the FOX test page, Scott had to allow all websites before Find videos worked, selected a stream and reported TV playback started without a PIN. This confirms the broad-site-permission onboarding requirement and reuse of existing pairing, **not fresh pairing**. Scott explicitly confirmed **moving video and audible sound on the Apple TV** for this installed-package trial. Scott also confirmed that **End helper session stopped TV playback** in this trial; this is observed behavior on this receiver, not a universal stop guarantee. For the fresh-pairing test, after Scott ended playback and quit Chrome, the agent verified no Chrome/helper processes remained and atomically moved the active `credentials.json` into Acer `<private pairing backup>/credentials.json` (backup directory 0700, credentials 0600), preserving the original file and verifying the active path absent. Scott then confirmed the sender-side fresh-pairing flow: entered the TV PIN in PearPlay, pressed Send to TV again, and observed moving video with audible sound on the Apple TV. Fresh PIN pairing and post-pair playback therefore pass for this installed-package trial; receiver-side pairing records were not reset. The second Send action is part of the observed onboarding flow, not automatic playback after pairing. Scott subsequently followed the stop → fully quit/reopen Chrome → recast sequence and confirmed successful casting without another PIN, verifying reuse of the newly saved pairing across the browser restart. Scott then ran PearPlay Setup → Connect or repair browsers with Chrome selected and reported connected again. This verifies the user-visible repeat-connect path. Scott then used Disconnect browsers for Chrome, reopened Chrome, and reported that the extension could not connect to the helper—the expected disconnected state. Scott then reconnected Chrome through PearPlay Setup, restarted Chrome and confirmed that the extension reported PearPlay Helper connected. Recovery from deliberately removed registration therefore passes. Scott disconnected Chrome and removed the system package with pacman. SSH verification confirmed the package absent from pacman, `/opt/pearplay/PearPlayHelper`, the desktop launcher, Chrome manifest and legacy launcher absent, and the newly saved pairing file still present with mode 0600. Scott reinstalled the same package, reconnected Chrome and confirmed casting with moving video and audible sound without another PIN. The install → fresh pairing → restart/reconnect → disconnect/recover → package removal → reinstall cycle therefore passes on Acer with pairing preserved as designed. A different-version upgrade remains untested. LG playback is not established. No new firewall/DNS changes were made by the agent during this trial.

## Installer rehearsal 0.2.3 — Linux package + Mac Terminal, not release-ready

Scott chose to drop the signed Mac package route rather than pursue Developer ID signing/notarization. The Mac deliverable is `install-macos.sh` + `scripts/macos_setup.py`, shipped with a source-runtime bundle and build-time identity. It installs a private Python 3.11/pyatv environment, uses exact registration ownership checks, refuses changed source/runtime paths and connects Chrome. Repeat installs repair missing registration. Remove disconnects Chrome while preserving runtime and pairing; a different-version update requires disconnecting the old release first. No Gatekeeper/TCC bypass or existing Hermes interpreter is used.

Linux 0.2.3 was built on Acer with its native makepkg. The package includes Python/pyatv and declares Zenity, Avahi and glibc >= 2.44. First-launch setup goes straight to browser selection. No system pacman install was performed; real OS upgrade/remove still needs the human test. Experimental Mac `.pkg` code and a scratch build remain historical, not the requested delivery route.

Verification on Mini and Acer: **60 Python tests and 31 JavaScript tests passed**. Real isolated Google Chrome 153.0.8010.53 on Mac exercised the actual Terminal installer, private-runtime dependency install, repeated install, hello/status 0.2.3, removal and a fresh host-not-found. Chrome 153.0.8010.47 on Acer passed the same native checks using the extracted Linux package. No daily browser registration, pairing, firewall, DNS, discovery or playback was changed by these installer tests. Mac used an existing uv executable; the no-uv bootstrap is documented, not fresh-machine tested. Independent read-only review of `scripts/macos_setup.py`, `install-macos.sh` and the existing registration installer reported no concrete security, data-loss or logic findings. The broader audit was checked against current source and evidence: its frozen-source-path claim does not apply to the executable registration branch; Mac-signing and development-only-documentation findings were superseded by the terminal route. Permanent store identity, license, real system/GUI installation and network/playback remain valid release gates. See `assets/evidence/installer-0.2.3-review.md`; no new implementation defect was established.

Test artifacts and read-back-verified checksums: `/Volumes/IronWolf/Stuff/PearPlay Installer Test/0.2.3/`. `START-HERE.md` gives the Acer → Mac → non-Omarchy test sequence. `extension-test/` uses fixture ID `iojhjdcndgfoalcialdlgklfdnlpmobf`, explicitly not the production ID. The draft-upload ZIP contains no fixture key or localInstallerTest flag. See `docs/web-store-readiness.md`, `docs/mac-terminal-install.md` and `docs/privacy.md`.

Remaining: joint clean user installs, actual discovery/pairing/video/audio, a disposable Ubuntu/live-distro test and baseline-built `.deb`, permanent PearPlay draft identity, owner license decision, published helper assets, final download catalog, public privacy page/screenshots and explicit submission approval. No VM was provisioned and nothing was committed, pushed, released or submitted. Preserve earlier discovery/onboarding work in this dirty checkout.

## Discovery repair — Apple TV and LG advertisement verified

Extension 0.2.2 merges multicast scanning with Avahi on every Linux discovery, including partial multicast results. It retains resolved records at the browse deadline and filters non-Apple-TV receivers by advertised video feature bits (V1, play queue, or V2), not simply by the presence of an AirPlay service. Audio-only and screen-mirroring-only receivers are excluded. Non-Apple-TV video receivers are explicitly labelled compatibility unverified; detection does not prove pairing or playback.

Acer live native discovery returned the Apple TV plus the LG C5 in three consecutive scans (~5.4 seconds each), excluding the Sonos speaker. Real isolated Chrome 153.0.8010.47 setup-page Find my TV → worker → native helper → LAN discovery returned both receivers in three further rounds (5.33, 5.13, 5.18 seconds). No pairing, playback, firewall or daily-profile changes were performed. `tests/browser/live-discovery.mjs` is opt-in and uses an isolated fixture extension/registration; it does not claim toolbar-popup coverage. LG playback and macOS broadened discovery remain unverified.

New regression checks cover partial multicast, silent unicast with resolved advertisements, audio-only exclusion, browse timeout output preservation, receiver limit, scan failures, safe receiver labels and the separate 25-second extension discovery deadline (helper deadline: 20 seconds). Earlier onboarding fixes remain uncommitted alongside this change.

## Live Chrome FOX result — video, audio, stop, and restart human-confirmed

Chrome extension → Linux native helper → command-mode AirPlay on the Living Room Apple TV:

- Initial FOX cast: moving video and audible sound (human-confirmed).
- 2026-09-12 Acer Chrome unpacked popup: pre-roll ads before the FOX stream AirPlayed to the Living Room Apple TV **with Pi-hole blocking still enabled on the Apple TV**. Same-host Fastly HLS; Pi-hole on the TV cannot strip in-stream ads on an allowed CDN. Ad→program transition on this path is human-confirmed for that pre-roll. Do not treat this as a reason to block ads.
- After Scott physically stopped the TV, leftover helper state was `error`/`unverified`. Popup stop then reported `stopped`/`unverified`.
- Recast `c35` (equivalent live masters sharing the same 720p–270p ladder): video and sound confirmed.
- Helper End session: Scott confirmed the Apple TV actually stopped.
- Recast `c39` after that stop: Scott confirmed video playing. He then restored Pi-hole blocking and deleted the temporary UDP 49170 rule while that stream was still playing.

Isolated Chrome PID 7736 / root `<isolated-browser-cache>` may still be running. Do not claim Brave or invalid/expired-stream behavior. Pause/resume remain unsupported. FOX pre-roll ads on AirPlay with ATV Pi-hole on are confirmed 2026-09-12.

## Previous verification — Chrome integration passed, TV gate was pending

Actual Google Chrome 152.0.7977.82 on Acer, isolated headless profile with sandbox enabled: unpacked extension `gndkmajngklgjkcmbolddaodljgoabma`, action popup → worker → native helper hello/status succeeded. Pause/resume correctly rejected as unsupported. Real loopback DOM MP4 and network HLS/MP4 discovery passed (synthetic bodies, NOT playback). Install exact bytes/modes and ownership-safe uninstall verified; fresh native connection then reported host not found. Unknown sentinels preserved, extension registration removed, owned Chrome processes confirmed absent. Evidence: [tests/browser/README.md](tests/browser/README.md) and its evidence JSON.

Latest rerun: **16 Node tests passed; 46 Python tests plus 24 subtests passed on Acer**. Command spike unchanged. Candidate filtering now excludes recognized segments/DASH/WebM and shows hostname/format without signed paths/queries. Browser/helper/contract sources were synchronized for the final Chrome run.

Still pending: actual FOX cast through extension/helper, visible video/audio and observed ad/program transition with Pi-hole temporarily disabled; invalid/expired stream and receiver lifecycle live checks; Brave. Stop only ends helper transport, not verified receiver stop; pause/resume unavailable. Ask Scott to make TV available and approve narrow timing firewall rule before live tests. Brave remains on hold, not removed from original two-browser completion criteria.

The older checkpoint below is retained as history; its Chrome-not-tested and earlier test totals are superseded by this section.

## Gate: PARTIAL — transport proven; extension/helper built; Chrome/TV integration not live-verified

Architecture: Linux helper on the Acer sends a receiver-fetchable HTTP(S) URL over AirPlay. No Mac relay, mirroring, cloud, transcode, or Omarchy dependency. Mini `~/Projects/PearPlay` is source of truth; Acer is the Linux test host. Session model GPT-6-astra; Hermes global default unchanged.

Paused 2026-09-10 evening at Scott’s request. Resume by loading `linux-airplay-sender`, `browser-extensions`, `test-driven-development`, `modern-javascript`. Do not claim Chrome or Brave integration until isolated-browser evidence exists.

## Temporary firewall rule — removed per Scott

Scott reports deleting the receiver-only UDP 49170 rule commented `PearPlay temporary timing test`. This has not been independently verified with privileged UFW output. UFW remains required protection; ask before restoring a narrow timing rule for another live test. Do not disable UFW.

## What works (human-confirmed on TV)

- Pairing with on-screen PIN; credentials in `~/.local/state/pearplay/credentials.json` (directory 0700, file 0600). Reconnect without a second PIN.
- After the timing-port allow rule, AirPlay sessions reach the TV (no longer stuck on the home screen).
- **Public HLS (Apple bipbop), command-mode adapter:** Scott saw video and heard the bip/bop audio.
- **FOX 13 Seattle live, command-mode adapter, ~3 minutes:** Scott reported the stream played well with both video and audio. Playlist was captured in isolated Chromium (not daily Brave/Chrome), passed on stdin, never stored in the repo. CLI exited `TimeoutError` at `--duration 180` while playback was still the observed success; that timeout is a hold limit, not a visual failure.
- Unicast discovery: Living Room Apple TV 4K (gen 3), tvOS 26.6, AppleTV14,1.
- Missing-receiver and no-session status paths return sanitized errors.

## What is built but not live-verified

- Shared contract: `contract/v1.md`. Native host `com.pearplay.helper`.
- Linux helper: `helper/native.py`, reversible installer `helper/install.py`. Wraps `spikes/002-command` Backend/Session, **not** stock `play_url`. Pause/resume return `unsupported` and are omitted from capabilities. Stop closes local transport only (`stopped`/`unverified`).
- MV3 extension: `extension/` (popup, service worker, content discovery, Native Messaging). User selects candidate and receiver. Local pause only after explicit “I confirm TV video and audio.” Optional host permission gates `webRequest`; listeners attach only after grant and detach on revoke.
- Mini automated: `python3.11 -m unittest discover -s tests -q` → 34 tests OK. `node --test tests/extension/*.test.mjs` → 11 passed. Apple CLT `python3` (3.9) is the wrong interpreter for helper port tests.
- Acer isolated helper copy previously: 46 passed, 24 subtests. Live Acer tree may lag Mini `extension/` / `helper/` until rsync.
- Chrome is the integration baseline. Brave install is on hold (Scott asked; Shields would confound site capture). Chromium is not a substitute for reporting Chrome or Brave.

## What failed or is incomplete

- First SETUP timeouts were **Acer UFW blocking inbound NTP timing**, not proven tvOS incompatibility. Attribution corrected after journal evidence.
- Baseline AirPlay v2 `play_url` with port 49170: HTTP accepted, TV showed a black buffering spinner for public MP4 and HLS. Not visual success.
- Forced AirPlay v1: `ConnectionLostError`, no picture.
- Public MP4 (MDN flower, 5.055s H.264+AAC): command-mode showed the flower video; Scott heard no sound. Too short to treat as an audio failure.
- Google Big Buck Bunny sample is HTTP 403 from Acer.
- FOX ad/program transition: Scott saw uninterrupted streaming and no ad. Apple TV uses Pi-hole DNS with enabled ad/tracker lists; this is a possible confounder, not evidence that an ad was blocked. Repeat from a fresh browser session with DNS blocking temporarily disabled on the relevant clients, then restore it. Wait for an actually observed transition; elapsed time alone is not proof.
- Stop/restart of an active FOX session: not live-tested (duration timeout ended the helper).
- Isolated Chrome load + Native Messaging hello/status: started 2026-09-10, stopped before evidence. No extension ID recorded.
- Brave: binary still absent; do not install unless Scott asks again.
- Uninstall: offline tests pass; not run against live credentials or a live native-host install.
- Acer Chrome verification child was interrupted; leftover `/tmp` isolated configs on Acer may exist and should be inspected, not assumed gone.

## Compatibility table

| Capability | Automated/offline | Actual receiver / browser | Verdict |
|---|---|---|---|
| Acer SSH / isolated venv | Commands succeeded | N/A | Verified |
| pyatv multicast discovery | Returned zero | Not detected | Fallback needed |
| Avahi + pyatv unicast discovery | Device/model/software | Advertisement only | Discovery only |
| Pairing + credential persist | Tests pass | PIN pairing succeeded; 0700/0600 | Verified |
| Reconnect without new PIN | Tests pass | Stored credentials reused | Verified |
| Timing UDP through UFW 49170 | Kernel blocks on random ports | SETUP proceeded after allow | Required for this host |
| Baseline v2 `play_url` + fixed timing | HTTP accepted | Buffering spinner, no A/V | Failed visually |
| AirPlay v1 `play_url` | Connect helper tests pass | ConnectionLostError; no A/V | Failed |
| Public MP4 command-mode | Tests pass | Flower video; no confirmed sound | Partial (clip 5s) |
| Public HLS command-mode | Tests pass | Video + audible bip/bop | Verified |
| FOX 13 live video + audio | Stdin URL tests pass | Played well, video and audio | Verified (CLI spike) |
| FOX ad/program transition | N/A | No ad observed; Pi-hole enabled | Not verified |
| Stop/restart live session | Helper local tests pass | Not live-tested on FOX | Partial |
| Invalid/expired media | Missing receiver timeout | Not a media-expiry test | Partial |
| Helper protocol / install | Mini 34 tests; Acer copy 46+24 | No live native host | Offline only |
| Chrome native messaging | Node 11 tests | Isolated Chrome load interrupted | Untested live |
| Brave native messaging | N/A | Browser not found | Untested |
| Uninstall owned state only | Tests pass | Not run live | Offline only |

## Dependencies and commands

- pyatv 0.18.0, Acer Python 3.14.7, pytest 9.1.1; Mini helper tests need python3.11, not Apple CLT 3.9
- Experimental adapter: `spikes/002-command/` (sanitized subset of PR #2846, head `8848ad3fd9ae46b8eb733bfc667b536a28f04c5a`, unmerged). No raw HTTP logging, no biplist, no global monkeypatch. Working playback remains `--mode command --timing-port 49170`.
- FOX capture: isolated Playwright Chromium, hosts only in reports (`foxvideo-fts.akamaized.net` master playlist, HTTP 200, no ENDLIST).

## Resume next

1. Rsync Mini `extension/`, `helper/`, `contract/`, `tests/` to Acer (no `.venv`, credentials, spikes overwrite). Confirm spike `command.py` hash still `259ab4a03dc36e284b568bb9d93d9a170a4df2e19d82075f8c0af61730d29906`.
2. Isolated Chrome `--user-data-dir` must match installer `CONFIG_PARENT/google-chrome` so NativeMessagingHosts is found. Never daily profile.
3. Load unpacked, record exact `[a-p]{32}` ID, install native host, prove hello/status, then synthetic candidate selection. No discover/play until Scott makes the TV available.
4. Ask before restoring UDP 49170 and before temporarily disabling Pi-hole for a FOX recast.
5. Brave remains optional and later; Shields off if used.
