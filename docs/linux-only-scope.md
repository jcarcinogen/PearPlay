# PearPlay Linux-only scope update — extension 0.2.4

**Linux only. Mac support is coming soon.** No release date is promised.

## Changed

- Popup/setup compatibility handling stops on Mac before helper, download or site-query activity. Linux download filtering rejects legacy Mac catalog entries. Extension version is 0.2.4.
- New Mac Terminal installs and non-Linux helper builds stop before setup/build side effects. Historical Mac functions/tests and receipt-guarded removal remain; no installed runtime or pairing was removed.
- README, install/helper guides, store listing/readiness/privacy drafts, positioning/claims, landing page, marketing sources and regenerated screenshots now agree on Linux-only scope. Mac signing/playback are not Linux release blockers.
- Mac research and previous evidence are visibly archived rather than erased. Current project guidance and the Stuff design prompt were aligned.
- Current Stuff kit is `PearPlay Installer Test/0.2.4/`: extension 0.2.4, unchanged Linux helper 0.2.3, isolated-fixture extension, draft-only ZIP and matching privacy/readiness drafts. Old mixed-platform artifacts are preserved byte-for-byte under `archive/0.2.3/`, with a redirect at the old entry point.

## Executed verification

| Check | Actual result |
|---|---|
| `python3.11 -m unittest discover -s tests -q` | 65 tests passed |
| `node --test tests/extension/*.test.mjs tests/brand.test.mjs` | 38 tests passed |
| `node tests/browser/platform-scope.mjs` | Actual isolated Mac Chrome popup/setup show coming soon, hide install/cast, issue zero helper/download requests, no console exceptions |
| `./scripts/render-brand-assets.sh` | Chrome 153.0.8010.53; 18 captures; 13 checked page views; zero console errors and zero remote page requests |
| Visual review | Store composite, hero and social caption readable and unclipped; no personal data |
| Draft ZIP / fixture / package audit | ZIP byte-matches current extension; fixture differs only in identity/catalog; two artifact checksums verified; Linux helper unchanged; privacy/readiness copies match |
| `git diff --check` | Passed |
| Independent code review | No concrete security or logic findings; see `assets/evidence/linux-only-review.json` |

Mac negative-control verification is not resumed Mac installation/playback testing. Marketing renders use actual extension documents with synthetic Linux platform/browser/native boundaries on a Mac rendering host, not live TV or Linux native integration evidence. No new TV trial or native installation was performed.

The shell's default `python3` resolved to Apple CLT 3.9 and produced three existing asyncio timeout incompatibilities; rerunning the full suite with the documented Python 3.11 command passed. No interpreter or dependency changes were made. Documentation delegation summaries were not accepted as evidence: missing edits were detected from actual files, corrected directly, and checked by the platform-copy regression and renderer.

## Remaining release work

Fresh non-Omarchy Linux validation; cross-version package upgrade; Linux Brave/Chromium playback before those claims; verified store identity/public key; real published Linux downloads and privacy URL; final release-artifact checks and explicit submission approval. Mac work remains paused and separate.

No commit, push, public release, Pages deployment or Web Store submission was performed. Existing installed helpers, saved pairing, daily browser settings and security settings were left untouched.
