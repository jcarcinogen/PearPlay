# PearPlay 0.2.4 — Web Store draft preparation

**Linux only. Mac support is coming soon.**

## Current publication scope

The owner approved the MIT license, committing/pushing the source, and publishing the project website and privacy policy. This is not approval to submit the extension for review or publish a consumer helper package. Root LICENSE covers original project code; existing third-party notices remain applicable.

- Website: https://jcarcinogen.github.io/PearPlay/
- Privacy: https://jcarcinogen.github.io/PearPlay/privacy.html
- Support: https://github.com/jcarcinogen/PearPlay/issues
- Dashboard: https://chrome.google.com/webstore/devconsole

Verify the website/privacy HTTP responses after Pages deploys. The privacy page is a static HTML rendering of docs/privacy.md; update both together whenever the policy changes.

## First dashboard step — establish the identity

1. Scott signs into the Chrome Web Store Developer Dashboard himself.
2. Look for an existing **PearPlay** item and reuse it. Do not select Open Autofill or create a duplicate PearPlay item.
3. If PearPlay does not exist, upload `pearplay-0.2.4-DRAFT-ONLY.zip` as a new unpublished item. Upload alone does not submit it for review.
4. Open **Package → View public key**. Record the exact Item ID and public key. The public key is not a password or private signing key.
5. Stop before **Submit for review** or **Publish**. Share the Item ID and public key with Hermes so the helper can be bound to the verified store identity.

The earlier unpacked extension IDs and installer-rehearsal fixture ID are not proof of the permanent store ID. The draft ZIP intentionally has no fixture key, no localInstallerTest flag, and no public helper downloads.

## Listing assets and text

Use `docs/store-listing.md` for the description, excluding its internal publication-prerequisites paragraph. `extension/manifest.json` supplies the name and short description. `docs/web-store-readiness.md` supplies the single-purpose statement and permission explanations.

- Store icon: `extension/icons/icon128.png` (128 × 128).
- Screenshots: `assets/store/listing-light.png` and `listing-dark.png` (1280 × 800).
- Images use isolated, synthetic UI; they are not new playback evidence.
- The listing must disclose the separate Linux helper and qualified compatibility. Do not claim general smart-TV, Linux distro, Brave or Chromium playback support.
- Complete data-use disclosures against the final package. Local processing still counts as handling user data; do not select a blanket “no user data” assertion. HTTP media is supported, so do not promise all transfers are encrypted.

## Final-release gates, after identity verification

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
