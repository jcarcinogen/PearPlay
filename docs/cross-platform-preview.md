# PearPlay 0.3.0 cross-platform preview

[Download the release and checksums](https://github.com/jcarcinogen/PearPlay/releases/tag/v0.3.0).

This free experimental release is tested for official Apple TV on Mac Chrome: pairing, public MP4 picture and sound, and stopping after ending the helper session were human-observed. Linux has prior Apple TV playback evidence. **Other AirPlay TVs: playback unverified.** Windows Chrome and playback are also unverified; testing follows release. Not every stream works.

## Downloads

| Computer | Helper |
|---|---|
| Mac Apple silicon | 0.3.0 `.pkg`, unsigned package/ad-hoc app, not Apple signed or notarized. No Intel Mac installer. |
| Windows x86_64 | 0.3.0 unsigned per-user `.exe`; native installer/security tests passed, Chrome/playback unverified. |
| Ubuntu/Debian x86_64 | 0.3.0 `.deb`; Ubuntu 24.04 / glibc 2.39+ baseline. |
| Fedora 44 x86_64 | Existing verified 0.2.8 `.rpm`, glibc 2.43+. |
| Arch/Omarchy x86_64 | Existing verified 0.2.8 `.pkg.tar.zst`, glibc 2.44+. |

No Linux/Windows ARM, Snap/Flatpak or browser beta/dev installer support. Safari extension work remains paused. Mac Brave shares Chrome registration but does not have a new watched-playback result. Windows Edge/Brave are not installer targets.

## Install and send

Use the actual release installer and checksum, not a source-only kit. Follow the [Mac screenshot guide](mac-install.md), [Windows guide](windows-helper.md) or [Linux installation guide](install.md). Keep Gatekeeper, SmartScreen, Defender and your firewall enabled. Do not remove quarantine or reset privacy permissions. A per-item Mac Open Anyway decision is voluntary; stop on malware/damage warnings. If Windows blocks the unsigned installer, stop rather than disabling protections.

Connect your browser in PearPlay Setup, fully quit/reopen it, then Check connection. Until Store 0.3.0 approval, extract the release extension ZIP and Load unpacked through chrome://extensions. Keep that folder in place; GitHub release does not update the Store automatically.

Keep computer and TV on the same trusted network. Allow websites, Find videos, select your stream, Find TVs and select Apple TV. Enter any pairing PIN only into PearPlay’s masked field. A failed attempt needs Show a new PIN. Pairing never automatically sends video.

Send to TV, check picture/sound, and stop duplicate browser playback with the site’s controls. End helper session closes its connection; if the TV keeps playing, use its physical remote. No popup TV pause/resume, timeline, seeking or volume controls are offered. Images depict this actual UI with example data, not live playback proof.

## Privacy and scope

Pairing stays OS-user-local; Windows uses DPAPI and user-local access controls. It is not portable between OSes/users/computers. Pair separately on each OS. No PearPlay account, cloud relay or first-party telemetry uploader. The media provider and TV still use the network. Directly fetchable HTTP(S) media only; no browser cookies, DRM or restriction bypass.

The earlier extensive candidate tests and repaired Mac build remain recorded in STATUS and the retained candidate kit. This release accepts the bounded official-Apple-TV owner result; broader receiver and Windows playback testing are follow-ups, not hidden passes. Signed/notarized distribution remains future work. Original candidate installers/checksums stay unchanged; the released Mac package uses the owner-installed dialog/registration/icon repair bytes.

[README](../README.md) · [Privacy](privacy.md) · [Latest status](../STATUS.md)
