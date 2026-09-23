# PearPlay positioning

## Audience and alternative

A desktop Chrome user with an Apple TV on the same network who wants a compatible website video on the TV without mirroring the desktop. Linux is the proven playback source; macOS currently has an installer and discovery adapter, not a recorded end-to-end playback verdict. Alternatives include screen mirroring, Safari AirPlay on macOS, and paid desktop senders. No comparative speed, quality, or compatibility claim is established here.

## One-line promise

**Your browser’s video. Your Apple TV.**

Always pair this promise with: “Compatible streams, sent directly. Linux playback verified in Chrome; macOS playback unverified.” Never imply every website works.

## Three genuine differences

1. **The TV fetches the stream.** Native Messaging carries control, not media. PearPlay does not relay or re-encode the stream or transfer browser cookies. This preserves the source stream rather than guaranteeing any resolution. Evidence: `contract/v1.md:3`, `STATUS.md:28`.
2. **A Linux route to Apple TV.** Chrome → Linux helper → Apple TV has human-confirmed FOX video and audio, including an observed pre-roll-to-program transition. This is a bounded result, not universal site support. Evidence: `STATUS.md:3–14`.
3. **A deliberate handoff, local to your devices.** You initiate access and sending, choose a video/receiver, and control browser playback with the website’s own player. Pairing credentials stay in a local 0700 directory / 0600 file. Evidence: `contract/v1.md:26–41`, `STATUS.md:38–49`, `extension/popup.js:150–165`.

## Three honest limitations

1. **The URL must work on the receiver.** HTTP(S) media only; a blob URL cannot be handed off. Cookies are not transferred. DRM, geography and other access controls are not bypassed. No ad blocking. Evidence: `contract/v1.md:3,24–28`, `STATUS.md:8,28,59`, URL validation in `extension/core.mjs`.
2. **Compatibility is deliberately narrow.** Linux Chrome FOX playback is human-confirmed. macOS supplies an installer/discovery adapter; playback remains unverified. Brave and Edge are unverified. Invalid/expired-stream and broader receiver-lifecycle behavior remain open. Evidence: `STATUS.md:3–24,52–64`, `helper/README.md:3–11`, `extension/manifest.json`.
3. **It is still an experimental, manually installed product.** Requires an unpacked extension and local Python helper. TV pause/resume are unavailable. End helper session is not a guarantee the TV stopped; the physical remote is the fallback. The current popup gates Find videos on all-sites permission even though a per-site grant control exists. Preserve and disclose that limitation rather than promising effective per-site discovery. Evidence: `helper/README.md:13–34,124–138`, `extension/popup.js:60–66,151–165`.

## Claims boundaries

`STATUS.md` is chronological: the newest result at the top supersedes contradictory historical checkpoints below. The confirmed stop/recast and pre-roll transition apply to that FOX trial, not every stream. Public HLS audio/video was verified through the command adapter, not asserted as a new popup test. A protocol “playing” event is never human playback proof.

Prefer “no account or cloud service required” over “no server”: there is a local native helper, and origin sites and Apple TV still communicate over the network. “No telemetry” must be backed by a source audit of the extension/helper, not assumed from the brief. Do not present the macOS network-permission workaround for one development machine as a universal installer recipe. No license is selected by this refresh.

## Tone and visual direction

- Plain, specific, calm. Sentence case headings; no superlatives, hype, exclamation marks, or implied universal compatibility.
- Distinguish “helper reports playing” from “playing on your TV.” Keep the physical-remote warning visible; do not add automatic browser pausing.
- The popup is an **Operate** surface: video and TV selection lead; setup and recovery remain clear and reachable.
- The landing page is a **Decide / Learn** surface: one promise, a real product capture, a direct-fetch explanation, then evidence and installation.
- Pear silhouette retained; broad leaf and play aperture, no Apple/AirPlay symbol. A two-tone mark rather than a glossy app tile.
- Palette direction: forest ink, warm off-white, pear-lime accent. System typography chosen for native legibility and offline operation. Measured token pairs belong in `assets/brand/palette.md`.
- All imagery comes from isolated headless Chrome. Example receivers and titles are synthetic; captures are UI evidence, not a live TV or macOS playback claim.
