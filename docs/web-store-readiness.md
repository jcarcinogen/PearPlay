# Chrome Web Store preparation — not submitted

**Linux only. Mac support is coming soon.** Mac compatibility work is paused and is not a Linux release blocker.

## Deliverables and identity

`pearplay-0.2.4-DRAFT-ONLY.zip` is a draft-upload artifact, not the final public release ZIP. Its manifest is at the ZIP root. It excludes helpers, Python, build caches, tests, fixture keys and the local installer-rehearsal flag. Public download links remain intentionally absent.

1. Inspect the publisher dashboard for an existing **PearPlay** draft first. Reuse it if present; do not create a second listing or confuse it with Open Autofill.
2. If none exists, upload this ZIP as a new unpublished item. **Do not click Submit for Review or Publish.**
3. Record the exact Item ID and the Package tab's public key. Verify the ID is 32 lowercase a–p characters. This user-account step remains pending; no PearPlay store ID has been verified in this run.
4. Apply that public key to development builds to match the listing, pin the exact ID into helper builds and the production release catalog, and repeat the clean installation tests with that identity.
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

- [ ] Permanent PearPlay draft ID and public key verified; production build uses that ID only.
- [x] Owner selected MIT for original project code; root `LICENSE` added and existing adapter/dependency notices retained.
- [x] Acer 0.2.3 package install, restart, discovery, fresh-PIN and saved pairing, visible video/audio, disconnect/reconnect and removal/reinstall verified (see STATUS).
- [ ] Cross-version Linux package upgrade verified.
- [ ] Linux Brave/Chromium end-to-end behavior verified before claiming those browsers beyond registration support.
- [ ] Non-Omarchy Linux clean test: native Google Chrome, package dependencies, Avahi, same-LAN discovery, pairing/playback and uninstall. Build `.deb` on the selected Ubuntu baseline, not the Acer's newer glibc.
- [ ] Real download assets published, checksums verified and release catalog wired to matching OS/architecture/ID. No placeholder URLs.
- [ ] For Arch desktops without a GUI package manager, explicitly document the small `pacman -U` step; do not advertise a universal no-Terminal Linux install.
- [ ] Fresh storefront screenshots from isolated synthetic UI; no Scott personal information, daily browser UI, real tokens or private network details.
- [ ] Listing claims restricted to tested platforms/receivers; LG detection is not playback support.
- [ ] Privacy policy publicly accessible; dashboard disclosures/permission explanations reconciled with final source.
- [ ] Independent review findings resolved, final regression suite and exact release artifacts verified.
- [ ] Scott explicitly approves submission. Keep automatic publication disabled on first submission.

## Paused Mac work — not a Linux release gate

Mac research and old artifacts are preserved, but no Mac install, signing purchase, consent or playback test is scheduled. Resume only if Scott explicitly reopens Mac work. The current local kit is `Stuff/PearPlay Installer Test/0.2.4/`; the old mixed-platform kit is archived. The source and project website are authorized for publication separately; no consumer helper release or Web Store submission is authorized by this checklist.

Official references:
- https://developer.chrome.com/docs/extensions/reference/manifest/key
- https://developer.chrome.com/docs/webstore/publish
- https://developer.chrome.com/docs/webstore/program-policies/user-data-faq
