# Chrome Web Store readiness — cross-platform development preview

Current candidate: extension 0.3.0, permanent identity `eoadahoncjfpnennmkjifohclbafjkol`, published Linux helper 0.2.8 catalog only. Mac/Windows helper candidates are active, without public URLs or human-observed playback claims. Safari extension development is paused. This work authorizes no commit, push, submission or publication.

Newest [STATUS](../STATUS.md) supersedes the 0.2.7-era material below: Linux 0.2.8 was published with matching anonymous downloads and recorded exact-package/native/watched evidence; Scott reports submitting/publishing Store 0.2.8 without independent public-version confirmation; 0.2.9 follow-up ZIP was prepared separately. Existing frozen release kits are historical and must not be overwritten.

## Current candidate gates

- [ ] Exact final source/ZIP version, permanent key/ID, permissions and native origin allowlist reconciled.
- [ ] Platform-native helper artifacts/checksums, clean install/restart/repair/update/disconnect/removal and fresh missing negative controls for each advertised OS/browser/architecture. Mac Chrome/Brave registration is shared; Windows targets per-user Chrome HKCU and user-local DPAPI, not portable pairing.
- [ ] Mac Developer ID Application/Installer signing, notarization, Gatekeeper-approved clean download/install and Local Network consent/deny/retry/update persistence. Ad-hoc signing is not a consumer pass. No quarantine removal/security bypass.
- [ ] Windows bundled installer/native Chrome/HKCU/ACL/DPAPI evidence and normal unsigned-block/distribution-signing handling, without SmartScreen/Defender bypass.
- [ ] Human TV picture/audio/spinner/stop/recast/restart-pairing checks per new platform. Prior Linux Chrome/Brave/Chromium owner confirmation is retained, not a new candidate test; LG HLS remains unresolved.
- [ ] Real Mac/Windows URLs added only after independently verified publication and anonymous downloaded hashes. Final production catalog/ZIP excludes fixture keys and `localInstallerTest`. Unpublished platforms show unavailable links.
- [ ] Parent-owned premium art/landing generated from final actual UI, privacy/description/reviewer instructions aligned and final self-service checklist exercised. Synthetic captures remain labeled UI evidence.
- [ ] New explicit owner authorization before any source/release/Store publication, then exact target/dashboard/public read-back.

Single purpose: send a user-selected compatible browser video URL to a user-selected AirPlay TV through an explicitly installed local helper. The permission explanations below remain a starting inventory, not final declarations. Opening onboarding sends a local connection check; TV discovery is a deliberate click. Disclose all-sites access accurately, HTTP support, local URL/title/receiver/pairing processing and direct receiver fetch. No telemetry is not no network. Current draft: [listing](store-listing.md), [privacy](privacy.md), [preview gates](cross-platform-preview.md).

## Historical 0.2.7 preparation record — superseded, not current instructions

The remainder preserves the earlier evidence/acceptance ledger as history. Its then-current versions, paused-Mac wording, incomplete gates and upload instructions do not apply to the resumed cross-platform candidate. Do not rerun historical upload or installer steps from it.

**Historical 0.2.7 scope was Linux-only, with Mac work deferred and excluded from Linux release gates.** This is not the current candidate scope.

## Deliverables and identity

The final upload artifact is `pearplay-0.2.7.zip` in `Stuff/PearPlay/Web Store/0.2.7/`. Its manifest is at the ZIP root. It excludes helpers, Python, build caches, tests, fixture keys and the local installer-rehearsal flag. It contains the verified Store public key and the matching Linux helper download catalog. Extension 0.2.7 uses the separately versioned, unchanged helper 0.2.5. Scott approved submission/publication, but dashboard Google sign-in currently blocks this session; actual 0.2.7 submission/publication remains unverified. The public Store page was checked and lists existing version 0.2.6, updated September 27, 2026.

1. Open the existing **PearPlay** item `eoadahoncjfpnennmkjifohclbafjkol`. Do not create a second listing or confuse it with Open Autofill.
2. Upload the final ZIP under **Package** and confirm version 0.2.7. Reconcile the dashboard fields, then submit for review under Scott’s approval; publish the update after Google approves it.
3. **Completed:** Scott supplied Item ID `eoadahoncjfpnennmkjifohclbafjkol` and its Package public key. Format and SHA256-derived identity match exactly. Reuse this existing item; do not create another.
4. **Completed in candidate source:** the 0.2.5 manifest, release catalog and Ubuntu production helper use this identity. Real Chrome tests in the clean Ubuntu VM verified the matching ID, native allowlist, connection, repair and removal. Other release gates remain below.
5. Replace the draft ZIP with the final version only after matching helper downloads are actually published and verified. Rehearsal uses a dedicated fixture ID and does not establish the store ID.

## Product and permission explanations — draft

**Single purpose:** Send a user-selected, compatible browser video URL to a user-selected AirPlay receiver through an explicitly installed local helper.

| Permission | Purpose |
|---|---|
| `activeTab` | User-initiated access to the active page for video discovery. |
| `scripting` | Inject the bundled video-discovery script into permitted page frames. |
| `webRequest` | Observe permitted media request URLs and response headers to identify HLS/MP4; no blocking or advertising modification. |
| `webNavigation` | Track document/frame changes so stale video URLs are discarded rather than attributed to a new page. |
| `nativeMessaging` | Communicate with the separately installed PearPlay helper for connection checks, receiver discovery, pairing and selected playback. |
| `alarms` | Expire bounded discovery sessions. |
| `storage` | Session-only popup receiver/selection continuity. Recheck actual storage use before final submission. |
| optional `http://*/*`, `https://*/*` | Find compatible video resources across user-authorized sites and their media frames/CDNs. Host access is requested by the UI rather than granted at install. Current Find videos flow's broad-grant requirement must be accurately explained. |

No remotely hosted JavaScript is loaded by the extension. A separately downloaded native helper is not silently installed or executed by the Web Store extension. Historical 0.2.7 Store disclosure required a separate Linux helper package and offered no Mac installer or workaround. The current draft above adds explicitly qualified Mac/Windows candidate intent without fabricated public links.

## Privacy and reviewer instructions

Local-only processing is still user-data handling under Google's policy. Disclose video URLs (which may include access tokens), relevant page content/titles, receiver addresses/identifiers, pairing input and credentials. The selected media address is sent to the local helper/selected receiver; the receiver then fetches from the media provider. Do not say “no user data is processed” or “all traffic is encrypted”: HTTP media URLs are allowed.

Policy source: `docs/privacy.md`; publication target: https://jcarcinogen.github.io/PearPlay/privacy.html. Verify HTTP 200 and policy content before using this URL in the dashboard. Public contact is the project’s GitHub Issues page; no personal email address is published. Reconcile the policy with the final helper and extension before submission.

Reviewer flow: install extension → install matching helper → restart Chrome → Check connection → Find my TV → open an authorized compatible video → grant site access → Find videos → choose receiver → Send → enter TV PIN in popup if requested. A real AirPlay receiver on the local network is required. Explain missing-helper recovery without requiring access to this development checkout. Provide public sample media verified at release time, not a captured signed streaming URL.

## Release blockers / acceptance checklist

- [x] Permanent PearPlay draft ID and public key verified; the Ubuntu 0.2.5 production build uses that ID only.
- [x] Owner selected MIT for original project code; root `LICENSE` added and existing adapter/dependency notices retained.
- [x] Acer 0.2.3 package install, restart, discovery, fresh-PIN and saved pairing, visible video/audio, disconnect/reconnect and removal/reinstall verified (see STATUS).
- [x] Arch cross-version upgrade 0.2.3-1 → production 0.2.5-1 verified on Omarchy Acer: installed unprivileged self-test, package integrity, isolated Chrome connection/repair/removal and three LAN discovery rounds passed; pairing byte-identical and mode 0600. Corrected restrictive-build-umask packaging defect has a regression test and independent review. Old development-ID registration was explicitly migrated with ownership checks, not automatically. No playback trial in this pass. Evidence: `assets/evidence/arch-upgrade-0.2.5.json`.
- [ ] Linux Brave/Chromium end-to-end behavior verified before claiming those browsers beyond registration support.
- [x] Ubuntu 24.04.5 x86_64/glibc 2.39 `.deb` built on the actual Ubuntu baseline; APT install, real graphical helper setup, sandboxed Google Chrome hello/status/repair/native-host removal and package remove/reinstall passed. Evidence: `assets/evidence/ubuntu-0.2.5-installer.json`.
- [x] Non-Omarchy same-LAN discovery and fresh-PIN playback: Xubuntu live USB (detected Ubuntu 26.04.1/glibc 2.43), production 0.2.5 `.deb`, isolated sandboxed Chrome, actual toolbar popup, user-confirmed moving Apple TV video/audio and protocol readback. Evidence: `assets/evidence/xubuntu-live-0.2.5.json`. The earlier VM NAT limitation remains a separate result; neither installed drive nor firewall was changed.
- [x] Graphical package-manager installation on Xubuntu 26.04.1: its pre-existing App Center installed the production `.deb` from package-absent state; UI, package database/logs, payload integrity and post-install Chrome connection/discovery passed. User pairing/registration metadata were preserved. Native XFCE defaults to GDebi, whose elevated window failed in this session; the earlier Engrampa default claim was an incomplete-SSH-environment error. Documented route: Open With → App Center. Dependencies were retained; this is not a universal distro/clean-reboot/authentication pass. Evidence: `assets/evidence/xubuntu-gui-install-0.2.5.json`. The extension was unpacked, not Store-installed.
- [x] Public v0.2.5 `.deb`, Arch package and checksums re-downloaded without authentication: HTTP 200 and exact tested hashes. Final catalog and exact Store ZIP verified in real isolated Linux Chrome. See `assets/evidence/public-downloads-0.2.5.json` and `final-zip-browser-0.2.5.json`.
- [x] Arch no-GUI `pacman -U` and Ubuntu/Debian `apt install` fallbacks are documented; no universal no-Terminal Linux install claim.
- [x] Fresh storefront screenshots regenerated from isolated synthetic UI and visually inspected; no personal data or clipped labels.
- [x] Draft listing and consumer copy restricted to verified Linux Chrome/Apple TV results; Brave/Chromium and LG playback not claimed.
- [x] Privacy policy 0.2.5 and website returned HTTP 200 with exact committed bytes.
- [ ] Actual dashboard disclosures/permission explanations reconciled with final source before submission.
- [x] Historical helper 0.2.5 release verification passed (69 Python/39 JS tests and matching public downloads).
- [x] Extension 0.2.7 independent source review passed; 375 Python tests +40 subtests and 61 JS tests passed. ZIP bytes/identity and all public helper hashes verified.
- [x] Exact unchanged 0.2.7 ZIP browser missing/ready/repair/remove acceptance passed: Google Chrome for Testing 154.0.8037.57 (temporary official linux64 bundle, since removed) and native Chromium 153.0.8010.52, both with installed helper 0.2.5; production download catalog, zero console exceptions, no receiver/firewall operations. The earlier blocked Acer attempt is preserved in `browser-verification.json` as history. Evidence: `final-zip-browser-0.2.7.json`, `final-zip-chrome-0.2.7.json`. Submitted by Scott from the dashboard 2026-09-28; pending Google approval.
- [x] Scott explicitly approved submission/publication of the 0.2.7 update. Existing version 0.2.6 is already public; approval to update it is not evidence that 0.2.7 submission occurred.

## Paused Mac work — not a Linux release gate

Mac research and old artifacts are preserved, but no Mac install, signing purchase, consent or playback test is scheduled. Resume only if Scott explicitly reopens Mac work. The current Ubuntu candidate is in `Stuff/PearPlay/Installer Test/0.2.5/ubuntu/`; the 0.2.4 and older mixed-platform kits are historical. The source and project website are authorized for publication separately; helper publication and the 0.2.7 Google review submission/publication are approved. Dashboard sign-in is still required to carry out and verify Store actions.

Official references:
- https://developer.chrome.com/docs/extensions/reference/manifest/key
- https://developer.chrome.com/docs/webstore/publish
- https://developer.chrome.com/docs/webstore/program-policies/user-data-faq
