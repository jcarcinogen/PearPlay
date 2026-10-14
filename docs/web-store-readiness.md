# PearPlay 0.3.3 — release decision checklist

Production item: `eoadahoncjfpnennmkjifohclbafjkol` ([Chrome Web Store](https://chromewebstore.google.com/detail/pearplay/eoadahoncjfpnennmkjifohclbafjkol)). Reuse this identity.

The bounded Mac official Apple TV owner gate and Windows 0.3.3 branded installation/native connection checks are complete. Mac, Windows, Debian and Arch candidates are built; Fedora 44 also has helper 0.3.3 with verified RPM/container installation and frozen native checks, not new desktop or receiver acceptance. TV seeking stays disabled. See [claims](claims.md) for precise artifact, synthetic, receiver and owner-policy boundaries.

For a separate release decision, use the checksum-verified final ZIP and helper files, matching catalog URLs/hashes, synchronized installation/privacy/listing copy, and actual shipping UI images. Helper assets and Pages/privacy must be published and anonymous downloads/bytes verified before users receive an extension whose Setup points to them. No new receiver matrix is required; preserve explicit unverified-platform/receiver and unsigned-installer caveats.

Windows trusted signing remains unavailable; owner installation after his explicit policy choice does not prove acceptance on protected end-user PCs. Mac remains unsigned/not notarized. Linux 0.3.3 has a glibc 2.39 baseline. Chrome's test-clip hardware decoding fault is separate from helper/TV acceptance.

[Submission procedure](store-submission.md) · [Listing](store-listing.md) · [Privacy](privacy.md) · [Release scope](cross-platform-preview.md)
