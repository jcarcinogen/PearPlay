# PearPlay 0.3.1 — cross-platform experimental release

Chrome extension and helpers are separate downloads. Use the [0.3.1 release](https://github.com/jcarcinogen/PearPlay/releases/tag/v0.3.1) and compare exact SHA256 values; old assets are never replaced in place. Store approval is separate from GitHub publication.

## Downloads

- Mac Apple silicon: unsigned 0.3.1 development PKG and ad-hoc app, not Developer ID signed/notarized.
- Windows x64: unsigned 0.3.1 fully branded per-user installer. Smart App Control/Application Control may block it, including on the owner PC. Stop if blocked; signing via SignPath is pending.
- Ubuntu/Debian x64: 0.3.1 DEB, Ubuntu 22.04/glibc 2.35+ baseline.
- Arch/Omarchy x64: 0.3.1 package, glibc 2.35+.
- Fedora 44 x64: retains [helper 0.2.8](https://github.com/jcarcinogen/PearPlay/releases/tag/v0.2.8), glibc 2.43+; no new RPM and no new TV pause/resume controls.

No Intel Mac or Linux/Windows ARM installer. Safari is paused. Flatpak/Snap browsers are unsupported.

## Controls and evidence

Before casting: browser play/pause, timeline, 5/10/15/30-second jumps, mute and Picture in Picture. Actual Chrome browser-control checks exist on Mac, Windows and Linux. During a TV session these browser controls are hidden and cannot control the TV.

Send to TV and End helper session are supported. Helper 0.3.1 also exposes Pause TV / Resume TV only for a supported authenticated Apple TV session. TV seek, timeline, jumps and volume are not implemented. Ending a helper session is not a universal guarantee that the TV stops; use its remote if it continues.

Prior owner observations cover Apple TV picture/sound on Mac/Windows and prior Linux playback; Windows pause/resume/end were tested with an earlier candidate. No new receiver observation is claimed for the final packages. LG HLS remains unresolved; other receiver compatibility is not generally established.

All three helper builds passed [hosted CI](https://github.com/jcarcinogen/PearPlay/actions/runs/38166068566). Windows exact-installer lifecycle, registry/receipt/hash checks and initial branded frozen GUI passed on hosted Windows, not under the owner PC’s policy. Mac expanded-package and isolated native Chrome checks are distinct from privileged system installation and protected owner-profile consent. Arch payload parity is not a new pacman installation claim. [Current evidence](../STATUS.md).

## Install and safety

Use a real package rather than a source-only kit. Keep your computer and TV on the same trusted network. Pairing is not portable between OS users or computers. Only human observation establishes picture and sound; use the physical remote if session ending leaves playback running.

Follow the [Mac guide](mac-install.md), [Windows guide](windows-helper.md) or [Linux guide](install.md). Keep OS/firewall protections enabled. Do not remove quarantine or disable Gatekeeper, SmartScreen, Defender, Application Control or package-signature checks. Stop on malware/damage warnings or a Windows policy block.

End casting and fully quit browsers before helper updates. Open PearPlay Setup, connect your browser, fully restart it, then Check connection. Mac Chrome/Brave share registration; Linux browser connections are separate. Pairing PINs belong only in PearPlay’s masked field. Pairing never automatically sends video.

Pairing stays OS-user-local; Windows uses DPAPI. No account, cloud relay or first-party telemetry uploader. Media providers and TVs still use the network. Only receiver-fetchable HTTP(S) media can be sent; cookies, DRM and access restrictions are not bypassed.

[README](../README.md) · [Privacy](privacy.md)
