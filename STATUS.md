# PearPlay 0.3.1 release status

Cross-platform experimental release: Chrome extension 0.3.1 and native helper 0.3.1 for Windows x64, Mac Apple silicon, Debian/Ubuntu x64 and Arch/Omarchy x64. Fedora keeps its separately versioned 0.2.8 RPM. Safari/UI-Lab work is deferred and preserved separately, not part of this release. Earlier working logs and dirty source are byte-verified in the maintainer’s release archive.

## Build evidence

[Three-platform CI run 38166068566](https://github.com/jcarcinogen/PearPlay/actions/runs/38166068566) built helper inputs from commit `03dedfbe0c03dd6ed7bde14b8d55cb7618e3846b`. Downloaded artifact checksums, source hashes and cross-platform shared inputs were independently verified.

- Windows: 92 native tests. Exact frozen installer install → repair → update → disconnect → connect → uninstall passed on a disposable hosted user with receipt, payload hashes, registry, manifest and native protocol readback. All three initial frozen Windows windows were captured branded; confirmation/progress/result states have real Tk fixture tests.
- Mac: 557 passed, 38 skipped, 48 subtests. Exact expanded shipping PKG passes frozen self-test, arm64 and strict ad-hoc signature checks. Package is unsigned, app is not Developer ID signed/notarized. Expanded-package/isolated-browser evidence is not a normal system Installer or owner-profile TCC acceptance claim.
- Linux: 553 passed, 42 skipped, 48 subtests. DEB and Arch packages built from the same frozen payload on Ubuntu 22.04; minimum tested glibc 2.35. Exact DEB upgrade to 0.3.1 in the disposable Ubuntu VM passed; all 849 installed regular files/modes/UIDs/GIDs match the shipping DEB. All 847 runtime regular files are byte-identical between DEB and Arch. No new Fedora RPM or owner pacman-install claim.

## Known boundaries

Windows Application Control blocked an earlier unsigned candidate on the owner PC. Hosted success does not remove that policy block. SignPath application submitted; approval, integration and trusted signing are pending. Stop if Windows blocks the installer; never disable protections or switch execution routes to evade it.

Mac remains unsigned/experimental by explicit owner choice. Apple’s optional per-item approval is a user trust decision, not signing or notarization. Stop on malware/damage warnings or absent approval controls.

Prior Apple TV picture/sound checks exist on Mac and Windows, with prior Linux playback and Windows pause/resume/session-end checks. They are historical owner observations, not new final-artifact receiver tests. TV pause/resume is gated to helper 0.3.1 and supported authenticated Apple TV sessions. TV seeking, timeline, jumps and volume are unavailable; use the TV remote. LG HLS remains unresolved.

## Distribution

[0.3.1 downloads and immutable checksums](https://github.com/jcarcinogen/PearPlay/releases/tag/v0.3.1) · [Website](https://jcarcinogen.github.io/PearPlay/) · [Privacy](https://jcarcinogen.github.io/PearPlay/privacy.html)

GitHub publication is separate from Chrome Web Store review. Reuse item `eoadahoncjfpnennmkjifohclbafjkol`; the 0.3.1 Store update requires Scott’s upload/submission and Google review. The last independently observed public Store version during preparation was 0.2.9. No Store approval is claimed here.
