# Helper onboarding and packaging

**Cross-platform development preview: Linux, Mac and Windows Chrome. Safari extension development is paused.** See [platform/artifact status and TV checks](cross-platform-preview.md). This is active candidate guidance, not a release declaration.

## Current delivery decision

- Linux: self-contained Python/pyatv helper in native distro packages; published [helper 0.2.8](https://github.com/jcarcinogen/PearPlay/releases/tag/v0.2.8). Open PearPlay Setup to connect browsers. Preserve the native package-manager path and full browser restart.
- Mac: resumed self-contained app/pkg candidate with ad-hoc signing. Developer ID Application/Installer, notarization, normal Gatekeeper download/install and Local Network identity/consent remain consumer-distribution gates. No public installer URL. Never borrow another app's permitted runtime or bypass security.
- Windows: active per-user bundled installer and HKCU native-host/DPAPI implementation. Exact packaged/native-OS evidence must be attached to its candidate; source alone is not an installer. Chrome is the preview target, not a general Edge/Brave promise.
- A Web Store extension cannot silently install its native helper; installation is a separate explicit step. The setup tab checks connection once when opened and only discovers receivers on a deliberate Find my TV action.

The permanent Store ID/public key is `eoadahoncjfpnennmkjifohclbafjkol`. Current candidate manifest is 0.3.0; catalog lists only published Linux 0.2.8 downloads. Mac's actual arm64 engineering pkg and recorded expanded-runtime/isolated-Chrome evidence are linked in the preview guide; Gatekeeper rejects and native pkg installation/TV acceptance are not established. Any final integrated source changes require a fresh build/native verification. STATUS reports Scott's 0.2.8 Store submission/publication without independently verifying public approval/live version, and a prepared, unsubmitted 0.2.9 follow-up. Do not replace that with older 0.2.6/0.2.7-current claims. Historical unpacked ID `hljhooeofdjbikkhbklccnlnladdbkfb` and rehearsal ID `iojhjdcndgfoalcialdlgklfdnlpmobf` are not production identities.

## Registration and state boundaries

Native Messaging carries control, not media. The TV fetches the selected URL. No login agent/cloud relay is required. Browser registration is per OS user, not privileged browser-profile modification. Canonical source can stay on IronWolf; installed executable/runtime/venv/pairing state must be local to the target machine and OS.

Linux package manager owns the payload; Chrome, Brave and Chromium have separate native-host registrations. Mac Chrome and Brave intentionally share the Chrome native-host directory: connecting or disconnecting that host affects both, not independent browser toggles. Mac Chromium is separate. The Windows candidate uses per-user Chrome registry keys in HKCU, not HKLM.

Unknown/changed files must be preserved by maintenance. End casting and quit browsers before repair/update/disconnection. One playback/pairing session per OS user means switching browsers is not another independent session. Saved pairing is preserved by ordinary disconnect/package removal; Windows DPAPI data is user-local and not portable across OSes/users/machines. Do not copy pairing between systems.

## Build targets

Use existing platform builders; do not install tools silently or add a parallel installer. `scripts/build_helper.py` is the build entry point for Linux and resumed Mac. Exact Windows builder invocation/artifact names must come from the engineering handoff, not a guessed executable command. Candidate output is not public availability.

Linux developer example (requires already available target-distro build environment):

```sh
python scripts/build_helper.py --extension-id eoadahoncjfpnennmkjifohclbafjkol --development --output /absolute/machine-local/new-build-directory
```

This is a developer build, not consumer onboarding. Baseline-compatible Linux runtimes must be built separately: Ubuntu 24.04/glibc 2.39, Fedora 44/glibc 2.43, Arch/Omarchy/glibc 2.44. Do not relabel one Arch-built runtime as all distros. Build inventory must include licenses, exact artifact hashes and dependency versions/self-test. Mac architectures require matching app/pkg output and exact signing/identity checks; Windows needs a real bundled installer, registry/ACL/DPAPI and native-browser tests on Windows.

## Recorded Linux evidence

The newest STATUS sections record published Linux 0.2.8 assets and anonymously downloaded matching hashes; real Arch exact-package install/restore, Ubuntu repaired-DEB upgrade/rollback and Fedora-RPM lifecycle/native-browser checks; bounded human Apple TV MP4/HLS and AirScreen MP4/HLS results. These supersede earlier pending package gates, not every possible compatibility gap. Prior owner-confirmed Linux Chrome/Brave/Chromium playback remains evidence about those recorded trials, not a new 0.3.0 candidate pass.

Historical graphical evidence is retained: Xubuntu 26.04.1's pre-existing App Center installed helper 0.2.5 after its normal warning and opened the browser-selection flow. Native XFCE GDebi failed in that live session. Fedora GNOME Software installed the initial 0.2.5 RPM but graphical reinstall failed authorization; DNF fallback succeeded. Those are not pristine dependency-download, every-desktop or new-candidate GUI results. See [Install](install.md), [Fedora](fedora-install.md) and historical `assets/evidence/` records.

## Release gates

1. Offline source/security/version/production-origin validation, followed by exact frozen self-test and inventory/hash evidence.
2. Actual native install/restart/repair/update/disconnect/remove/fresh missing journey for each advertised OS/architecture/browser, preserving changed/unknown files and saved pairing.
3. Mac Developer ID signing/notarization/Gatekeeper-approved clean download/install, Local Network consent/deny/retry and update persistence; Windows normal unsigned-block behavior and distribution-signing plan, HKCU and DPAPI/ACL native acceptance.
4. Human-observed picture/audio, bounded startup/spinner, physical stop/recast and browser-restart pairing reuse on each intended OS/browser/receiver/media route. No Mac/Windows human playback is established here. LG HLS remains parked; Linux Brave/Chromium owner reports do not supply missing details or a fresh candidate test.
5. Exact final extension ZIP and helper compatibility, safe setup links and unsupported-OS negative controls. Add public catalog URLs only after verified publication/download; never fabricate Mac/Windows links or add `localInstallerTest` to production.
6. Parent-owned final TV checklist/artwork/landing regeneration, final privacy/permissions/reviewer reconciliation and separately authorized publication. No commit, push, Store action or release is performed by this workstream.

Fixture `localInstallerTest:true` remains isolated rehearsal-only. Historical release kits stay byte-for-byte intact. [Mac runtime identity](mac-runtime-identity.md) belongs to the Mac worker; [old Terminal rehearsal](mac-terminal-install.md) remains historical, not the resumed app/pkg route.
