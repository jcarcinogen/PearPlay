# PearPlay 0.2.7 — Web Store upload preparation

**Linux only. Mac support is coming soon.**

## Current publication scope

The owner approved the MIT license, committing/pushing the source, and publishing the project website and privacy policy. The Linux helper preview release is now also authorized. Scott subsequently approved committing/pushing and submitting/publishing extension 0.2.7, and submitted the 0.2.7 update for review from the dashboard on 2026-09-28; Google approval is pending and publication after approval is not yet done. The public Store page lists 0.2.6 (updated September 28, 2026), verified during this release preparation. Root LICENSE covers original project code; existing third-party notices remain applicable.

- Website: https://jcarcinogen.github.io/PearPlay/
- Privacy: https://jcarcinogen.github.io/PearPlay/privacy.html
- Support: https://github.com/jcarcinogen/PearPlay/issues
- Dashboard: https://chrome.google.com/webstore/devconsole

Verify the website/privacy HTTP responses after Pages deploys. The privacy page is a static HTML rendering of docs/privacy.md; update both together whenever the policy changes.

## Upload to the verified existing item

1. Scott signs into the Chrome Web Store Developer Dashboard himself.
2. Open **PearPlay**, Item ID **`eoadahoncjfpnennmkjifohclbafjkol`**. Do not select Open Autofill or create a duplicate item.
3. Under **Package**, upload **`pearplay-0.2.7.zip`** from `Stuff/PearPlay/Web Store/0.2.7/`. Do not upload a helper package or the old DRAFT-ONLY ZIP.
4. Confirm extension version **0.2.7** (helper remains **0.2.5**) and the unchanged Item ID. Add the supplied icon/screenshots and reconcile listing/privacy fields with the final source. If upload is locked, inspect the existing publication state rather than creating a new item.
5. Submission/publication is now approved by Scott. After the listing, privacy declarations and reviewer instructions match this package, use **Submit for review** for this update, then publish after approval (or use publication after approval if the dashboard offers it). Read back the dashboard status—upload, submission, approval and public availability are distinct states.

The Store public key was verified to derive to this Item ID. The final ZIP retains that public key and the production download catalog; it excludes fixture keys, localInstallerTest, helpers, Python, tests, credentials and caches. The helper release is separate from the Store extension. The existing public Store version is 0.2.6; this upload updates the same item to 0.2.7.

## Listing assets and text

Use `docs/store-listing.md` for the description, excluding its title and internal submission note. Keep the Flatpak Chrome warning as the very first line; use uppercase in the plain-text Store description rather than Markdown bold markers. `extension/manifest.json` supplies the name and short description. `docs/web-store-readiness.md` supplies the single-purpose statement and permission explanations.

- Store icon: `extension/icons/icon128.png` (128 × 128).
- Screenshots: `assets/store/listing-light.png` and `listing-dark.png` (1280 × 800).
- Images use isolated, synthetic UI; they are not new playback evidence.
- The listing must disclose the separate Linux helper and qualified compatibility. Do not claim general smart-TV, Linux distro, Brave or Chromium playback support.
- Complete data-use disclosures against the final package. Local processing still counts as handling user data; do not select a blanket “no user data” assertion. HTTP media is supported, so do not promise all transfers are encrypted.

## Extension-only 0.2.7 scope

This update retains published helper 0.2.5 downloads. It releases the compact popup, clearer static errors and full-browser-restart guidance; it does not deliver a new helper or an LG HLS fix. New helper discovery, diagnostic and privileged-firewall code is a source checkpoint only. Real packaged privilege/rollback, upgrade and platform-baseline tests remain prerequisites to shipping those helper changes. The 0.2.7 extension hides new firewall actions when the old helper does not advertise support.

## Final verification and submission gates

- Build the Linux helper with the verified store ID, never the rehearsal fixture ID.
- Exercise cross-version upgrade and the requested clean non-Omarchy Linux installation. Existing Acer Chrome playback is recorded separately in STATUS.md.
- Publish real matching helper artifacts and checksums; verify downloaded bytes; populate extension/releases.json with only those verified URLs and supported targets.
- Repeat the clean-install journey with the exact extension/helper identity and final ZIP.
- Reconcile privacy, permissions, reviewer instructions, a working authorized sample, and screenshots against that build.
- Scott’s submission/publication approval is recorded; verify each actual dashboard transition for the update to the already-public item.

Mac signing and playback are not Linux release gates. Mac work stays paused.

## Official references

- https://developer.chrome.com/docs/webstore/publish
- https://developer.chrome.com/docs/extensions/reference/manifest/key
