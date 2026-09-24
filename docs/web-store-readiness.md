# Chrome Web Store preparation — not submitted

**Linux only. Mac support is coming soon.** Mac compatibility work is paused and is not a Linux release blocker.

## Deliverables and identity

The final upload artifact is `pearplay-0.2.5.zip` in `Stuff/PearPlay Web Store/0.2.5/`. Its manifest is at the ZIP root. It excludes helpers, Python, build caches, tests, fixture keys and the local installer-rehearsal flag. It contains the verified Store public key and the matching Linux helper download catalog. This is an upload handoff, not Store submission approval.

1. Open the existing **PearPlay** draft `eoadahoncjfpnennmkjifohclbafjkol`. Do not create a second listing or confuse it with Open Autofill.
2. Upload the final ZIP under **Package** and confirm version 0.2.5. **Do not click Submit for Review or Publish.**
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

No remotely hosted JavaScript is loaded by the extension. A separately downloaded native helper is not silently installed or executed by the Web Store extension. Store disclosure must say a separate Linux helper package is required. Mac support is coming soon; no Mac installer or installation workaround is offered.

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
- [ ] Real download assets published, checksums verified and release catalog wired to matching OS/architecture/ID. No placeholder URLs.
- [x] Arch no-GUI `pacman -U` and Ubuntu/Debian `apt install` fallbacks are documented; no universal no-Terminal Linux install claim.
- [ ] Fresh storefront screenshots from isolated synthetic UI; no Scott personal information, daily browser UI, real tokens or private network details.
- [ ] Listing claims restricted to tested platforms/receivers; LG detection is not playback support.
- [ ] Privacy policy publicly accessible; dashboard disclosures/permission explanations reconciled with final source.
- [ ] Independent review findings resolved, final regression suite and exact release artifacts verified.
- [ ] Scott explicitly approves submission. Keep automatic publication disabled on first submission.

## Paused Mac work — not a Linux release gate

Mac research and old artifacts are preserved, but no Mac install, signing purchase, consent or playback test is scheduled. Resume only if Scott explicitly reopens Mac work. The current Ubuntu candidate is in `Stuff/PearPlay Installer Test/0.2.5/ubuntu/`; the 0.2.4 and older mixed-platform kits are historical. The source and project website are authorized for publication separately; helper publication is now approved, but Google review submission remains unapproved.

Official references:
- https://developer.chrome.com/docs/extensions/reference/manifest/key
- https://developer.chrome.com/docs/webstore/publish
- https://developer.chrome.com/docs/webstore/program-policies/user-data-faq
