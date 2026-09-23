# Helper onboarding verification

## Verified locally

- JavaScript: `node --test tests/extension tests/brand.test.mjs` — 28 passing tests on macOS and Linux.
- Python: `python -m unittest discover -s tests -q` — 51 passing tests on macOS and Linux.
- Real native messaging with **extracted development package payloads**, isolated browser profiles and a dedicated public fixture extension key:
  - macOS Chrome 153.0.8010.53: missing → connected; helper version 0.2.0 and idle status; registration removal followed by a failed fresh native connection.
  - Linux Chrome 153.0.8010.47: same checks passed.
  - Linux Chromium 152.0.7977.82: same checks passed.
- `tests/browser/onboarding.mjs` checks setup-page layout overflow and uncaught exceptions. No receiver discovery, pairing or TV playback was performed.
- Asset renderer: 18 captures, 13 pages, zero console errors and zero remote page requests. `scripts/verify-brand-assets.py` passes icon, contrast, claim-reference bounds, privacy-pattern and offline-asset checks. Reference bounds are not a fresh audit of every claim.
- Actual popup and setup screenshot inspection: footer badge legible and unclipped; setup truthfully reports unpublished downloads. Captures contain synthetic device labels, not personal browser data.

## Limits and failures retained as release gates

- macOS Brave did not find the test-scoped helper registration. Its end-to-end integration is **not verified**; no daily-profile registration was altered to force a pass.
- macOS package is an unsigned/unnotarized development build. It is not a consumer-ready installer.
- The successful tests use package extraction, not a system-wide installer/update/uninstall run or a real first-time user's GUI flow.
- Debian/Ubuntu and Fedora package recipes have not been built/tested on their target distributions.
- macOS/Brave/Chromium TV playback, signing/notarization, permanent Web Store ID, project license and public release assets remain open.
- Second bounded independent review reported no security concerns or logic errors and no must-fix defects. The first review’s findings and source-based assessment are retained in `helper-onboarding-review-assessment.md`. This is not a release-security certification.

## Reproduction

Build a development helper with the ID in `tests/browser/fixture-key.json`, extract its package into a disposable directory, then run from the repo root:

```sh
PEARPLAY_BINARY='/absolute/path/to/extracted/PearPlayHelper' node tests/browser/onboarding.mjs
```

For Linux Chromium, also set `CHROME=/usr/bin/chromium PEARPLAY_BROWSER=chromium`. The fixture key is **test-only**, never a production allowlist entry. Ordinary unpacked installs have a different ID.

The X Money image is bundled at `extension/tip-with-x-money.png` and links to the explicitly requested public profile. No X request is needed to render the badge.
