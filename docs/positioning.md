# PearPlay positioning

## Audience and alternative

A desktop Chrome user with an AirPlay TV who wants a compatible website video on the TV without mirroring the desktop. Linux has published helper 0.2.8 downloads and prior owner-confirmed playback; Mac and Windows Chrome helpers are active development previews, not public consumer releases. Safari extension development is paused. Alternatives include desktop mirroring, Safari's native AirPlay on macOS and other desktop senders. No comparative speed/quality/compatibility claim is established here.

## One-line promise

**Your browser's video. Your Apple TV.**

Pair it with: “Compatible streams, sent directly. Cross-platform development preview; separate local helper required.” Put published Linux availability and Mac/Windows preview qualifications near the first call to action. Never imply every website or platform works.

## Three genuine differences

1. **The TV fetches the stream.** Native Messaging carries control, not media. No cloud relay, desktop mirroring, re-encoding or cookie transfer. This does not guarantee any resolution or universally compatible codec/site.
2. **One deliberate browser handoff.** You grant access, choose the video/receiver and send; source changes must not silently switch your choice. Setup checks a local connection on open; discovery is a separate click. Browser playback stays with website controls.
3. **Local helper, local pairing.** One helper/session per OS user. Linux registrations are separate; Mac Chrome/Brave share one native-host registration and disconnect affects both. Windows Chrome uses per-user HKCU and current-user DPAPI state, not portable cross-OS pairing. No PearPlay account is required.

Sources: `contract/v1.md`, current extension/helper sources and newest `STATUS.md`. Source architecture facts, unit/DOM fixtures, native-browser acceptance and human playback are different evidence classes.

## Honest limitations

- HTTP(S) receiver-fetchable media only. `blob:`, DRM, cookies, geography and access controls are not bypassed. PearPlay does not block ads.
- Linux Chrome has prior picture-and-sound confirmation; Brave/Chromium have owner-reported playback without separately recorded audio/stream details. The new candidate still requires its own browser/OS matrix. Mac/Windows human picture/audio is not established. LG HLS remains parked/unresolved.
- A local native helper is a separate installation. Mac app/pkg signing/notarization and Windows packaged/native-OS acceptance remain gates; source-only files or ad-hoc signing do not establish a consumer installer. Do not bypass security to make an unsigned preview run.
- “Sent” or helper-reported “Playing” is not TV picture/sound evidence. End helper session is local teardown, not a universal TV-stop guarantee; use the physical remote if needed. TV pause/resume/timeline/Picture in Picture and Safari's native picker are not Chrome helper features.
- Preserve accurate all-sites discovery-permission wording for the final UI; do not promise per-site-only discovery unless the implementation and tests establish it.

## Release and claims boundaries

[STATUS](../STATUS.md) is chronological; newest evidence supersedes conflicting historical checkpoints. Published Linux 0.2.8, the reported Store transition, separately prepared 0.2.9 ZIP and local 0.3.0 candidate must not be conflated. The old “Linux only / Mac paused” documents are historical, not the present intent.

Prefer “no PearPlay account or cloud relay” over “no server.” “No telemetry” describes the audited first-party control path, not zero browser/dependency/TV/provider network activity. HTTP media means not all transfers are encrypted. See [claims](claims.md), [privacy](privacy.md) and [preview gates](cross-platform-preview.md).

## Tone and visual direction

- Calm, specific, plain language. No implied universal compatibility or superiority.
- Popup: compact 400×600 candidate, video/TV selection first, clear setup/recovery and readable keyboard focus. Retain stale-source and async-action safety rather than copying Safari-only features.
- Landing: one promise, real interface capture with example-data qualification, direct-fetch explanation, honest platform matrix, installation and checklist.
- Pear/play identity, forest ink, warm off-white and pear-lime accent; no Apple/AirPlay mark or implied affiliation. Original code is MIT; third-party notices remain. Working name is not trademark-cleared.
- Parent owns new artwork/store composites/landing regeneration. Isolated synthetic captures are UI evidence, never a human-TV or macOS/Windows playback claim. No private browser chrome, signed URLs, real receiver names, PINs or credentials in captures.
