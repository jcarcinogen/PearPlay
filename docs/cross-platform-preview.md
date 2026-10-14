# PearPlay 0.3.3 — cross-platform experimental release

Install PearPlay from the [Chrome Web Store](https://chromewebstore.google.com/detail/pearplay/eoadahoncjfpnennmkjifohclbafjkol). Install the separate helper for your computer from the [0.3.3 release](https://github.com/jcarcinogen/PearPlay/releases/tag/v0.3.3) and compare its SHA256. Store updates do not update or sign the helper.

## Downloads and platform limits

- Mac Apple silicon: unsigned 0.3.3 development PKG and ad-hoc app, not Developer ID signed/notarized. Keep Gatekeeper enabled; do not remove quarantine. The Mac guide describes optional human approval of the exact item and stop conditions.
- Windows x64: unsigned 0.3.3 fully branded per-user installer. Smart App Control/Application Control or SmartScreen may block it. Stop if blocked; trusted Windows signing is unavailable. A source-only kit is not an installable build. Installation writes no security settings.
- Ubuntu/Debian x64: 0.3.3 DEB, Ubuntu 24.04/glibc 2.39+ baseline.
- Arch/Omarchy x64: 0.3.3 package from the same frozen Linux payload, glibc 2.39+.
- Fedora 44 x64: [helper 0.3.3 RPM](https://github.com/jcarcinogen/PearPlay/releases/tag/v0.3.3), glibc 2.43+. Built inside an official Fedora container from the same verified Linux frozen stage; all 930 payload entries match, DNF install/rpm -V and frozen self-test/non-root native hello pass. No new graphical install, live discovery or physical TV acceptance.

No Intel Mac or Linux/Windows ARM installer. Safari development is paused. Flatpak/Snap browsers are unsupported. Keep the computer and TV on the same trusted private network.

## Controls and evidence

Before casting, the selected browser video has play/pause, timeline, 5/10/15/30-second jumps, mute and Picture in Picture. During casting these browser transport controls are hidden; they do not control the TV.

Pause TV / Resume TV require helper 0.3.1 or newer and a supported authenticated Apple TV session. Read-only TV progress requires helper 0.3.3. TV seeking, jumps and volume are unavailable. End helper session closes the connection, not a universal TV-stop guarantee; use the physical remote if playback continues.

The active cast remains visible when you reopen the popup or switch tabs. Mute browser video targets only the original browser video, not TV audio. Muting and restoration are never automatic. The preferred TV is remembered by identity and selected after rediscovery; media addresses are not saved.

Helper 0.3.3 and the matching extension have owner-observed Mac Chrome/official Apple TV MP4 checks for picture, sound, pause/resume, accurate progress, popup reopening/tab switching, browser-only mute and session ending. Chrome's platform decoder failed on the test clips with graphics acceleration enabled; the test used a temporary acceleration-off comparison, and the owner restored the setting afterward. This is not universal codec/stream compatibility.

Windows 0.3.3 has exact build-input hashes, frozen self-tests, native framing/origin checks, embedded payload/icon verification, owner-visible branded installation and 1,621 receipt-owned file plus registry readbacks. Chrome's matching extension connected. The SSH frozen-window probe timed out; owner visible-window evidence is recorded separately. Windows 0.3.3 receiver playback was not retested. Earlier Windows Apple TV picture/sound/pause/end observations remain historical.

Debian and Arch 0.3.3 packages have source/payload equivalence and extracted frozen self-tests, not new normal-environment installation or physical receiver acceptance. Prior Linux Chrome, Brave and Chromium playback remains separate; Chrome sound was separately confirmed. Other AirPlay TVs are playback unverified; LG live HLS remains unresolved.

## Pairing and updates

End casting and fully quit browsers before updating the helper. Use the new package or Windows Install / update, then reopen the browser and Check connection. Saved pairing is kept. Mac Chrome and Brave share registration, so disconnecting it affects both. Windows uses current-user DPAPI; pairing is not portable between OS users, computers or operating systems. No security disabling is required or recommended to users.
