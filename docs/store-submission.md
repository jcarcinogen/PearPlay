# PearPlay 0.2.5 — Web Store upload preparation

**Linux only. Mac support is coming soon.**

## Current publication scope

The owner approved the MIT license, committing/pushing the source, and publishing the project website and privacy policy. The Linux helper preview release is now also authorized. This is not approval to submit the extension to Google for review or publish its Store listing. Root LICENSE covers original project code; existing third-party notices remain applicable.

- Website: https://jcarcinogen.github.io/PearPlay/
- Privacy: https://jcarcinogen.github.io/PearPlay/privacy.html
- Support: https://github.com/jcarcinogen/PearPlay/issues
- Dashboard: https://chrome.google.com/webstore/devconsole

Verify the website/privacy HTTP responses after Pages deploys. The privacy page is a static HTML rendering of docs/privacy.md; update both together whenever the policy changes.

## Upload to the verified existing item

1. Scott signs into the Chrome Web Store Developer Dashboard himself.
2. Open **PearPlay**, Item ID **`eoadahoncjfpnennmkjifohclbafjkol`**. Do not select Open Autofill or create a duplicate item.
3. Under **Package**, upload **`pearplay-0.2.5.zip`** from `Stuff/PearPlay Web Store/0.2.5/`. Do not upload a helper package or the old DRAFT-ONLY ZIP.
4. Confirm version **0.2.5** and the unchanged Item ID. Add the supplied icon/screenshots and reconcile listing/privacy fields with the final source. If upload is locked, inspect the existing publication state rather than creating a new item.
5. Stop before **Submit for review** or **Publish**. Submission requires explicit approval; keep automatic publication disabled for the first review.

The Store public key was verified to derive to this Item ID. The final ZIP retains that public key and the production download catalog; it excludes fixture keys, localInstallerTest, helpers, Python, tests, credentials and caches. The helper release is separate from the unpublished Store listing.

## Listing assets and text

Use `docs/store-listing.md` for the description, excluding its internal submission note. `extension/manifest.json` supplies the name and short description. `docs/web-store-readiness.md` supplies the single-purpose statement and permission explanations.

- Store icon: `extension/icons/icon128.png` (128 × 128).
- Screenshots: `assets/store/listing-light.png` and `listing-dark.png` (1280 × 800).
- Images use isolated, synthetic UI; they are not new playback evidence.
- The listing must disclose the separate Linux helper and qualified compatibility. Do not claim general smart-TV, Linux distro, Brave or Chromium playback support.
- Complete data-use disclosures against the final package. Local processing still counts as handling user data; do not select a blanket “no user data” assertion. HTTP media is supported, so do not promise all transfers are encrypted.

## Final verification and submission gates

- Build the Linux helper with the verified store ID, never the rehearsal fixture ID.
- Exercise cross-version upgrade and the requested clean non-Omarchy Linux installation. Existing Acer Chrome playback is recorded separately in STATUS.md.
- Publish real matching helper artifacts and checksums; verify downloaded bytes; populate extension/releases.json with only those verified URLs and supported targets.
- Repeat the clean-install journey with the exact extension/helper identity and final ZIP.
- Reconcile privacy, permissions, reviewer instructions, a working authorized sample, and screenshots against that build.
- Get Scott’s explicit submission approval, with automatic publication disabled for the first review.

Mac signing and playback are not Linux release gates. Mac work stays paused.

## Official references

- https://developer.chrome.com/docs/webstore/publish
- https://developer.chrome.com/docs/extensions/reference/manifest/key
