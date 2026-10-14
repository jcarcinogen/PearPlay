# Chrome Web Store listing source — 0.3.3

**FLATPAK-INSTALLED VERSIONS OF GOOGLE CHROME AND CHROMIUM ARE NOT SUPPORTED.** On Linux use your distribution’s native browser package format.

PearPlay sends compatible browser video directly to Apple TV—without screen mirroring, re-encoding or a cloud relay. A separate PearPlay Helper is required for TV playback. No PearPlay account.

Choose a video, find your Apple TV, pair if asked, then Send to TV. Pairing never sends video automatically. Finding TVs is deliberate, not repeated every time you open the popup. Website access is requested when you click; all-sites access is currently required to find videos.

Before casting, control the selected browser video: play/pause, timeline, 5/10/15/30-second jumps, mute and Picture in Picture. These are browser controls, not TV seeking. During casting the browser transport is hidden. End helper session closes the helper connection; if the TV keeps playing, use its remote.

Pause TV / Resume TV are available with helper 0.3.1 or newer and a supported authenticated Apple TV session. Read-only TV progress requires helper 0.3.3. The active cast stays visible when you reopen PearPlay or switch tabs. Mute browser video silences only the original browser video, not the TV; muting/restoration are never automatic. Your preferred TV is selected after rediscovery, without saving media URLs. Fedora 44 helper 0.3.3 provides the same capability-gated controls. TV seeking, jumps and volume are not supported. The popup points older-helper users to Setup; Web Store updates do not update the helper. End casting and fully quit browsers, update the helper using its platform installer, reopen the browser and Check connection. Saved pairing is kept.

Browser controls have been checked in Chrome on macOS, Windows and Linux. Apple TV picture and sound have owner-confirmed checks on Mac and Windows. Windows pause/resume and End helper session were owner-tested with a newer helper candidate. Prior playback has been user-confirmed through the extension and helper in Linux Chrome, Brave and Chromium on tested streams. Chrome video and audible sound were separately confirmed. Audio and broader stream compatibility in Brave and Chromium have not been separately documented. These checks are not a promise that every site, browser or receiver works. LG live HLS remains unresolved; other AirPlay TV compatibility varies.

Helper downloads: Mac Apple silicon, Windows x86_64, Ubuntu/Debian x86_64 and Arch/Omarchy x86_64 helper 0.3.3; Fedora 44 also has helper 0.3.3 (glibc 2.43+). The 0.3.3 Debian/Arch packages require glibc 2.39+ (Ubuntu 24.04+ baseline). Python is bundled. No Intel Mac or Linux/Windows ARM installers. Windows setup and maintenance are fully branded. Mac and Windows builds are unsigned experimental software: Windows security policy may block installation, including on the test computer. Stop if blocked; never disable OS protections. Mac builds are not Apple Developer ID signed or notarized. Trusted Windows signing is not currently available.

Only receiver-fetchable HTTP(S) streams can be sent to TV. Browser-only video URLs may work with browser controls but cannot be sent directly. Cookies, DRM, geography and access restrictions are not bypassed. PearPlay does not block ads. Not every website works.

Mac Chrome and Brave share one helper connection, including disconnection. Linux supports separate Chrome, Brave and Chromium connections. Windows targets the current user’s Chrome. Pairings stay local to that OS user; Windows uses DPAPI. Pair separately on each OS. Safari extension development is paused.

No first-party telemetry uploader or cloud media relay. Your browser, dependencies, media provider and TV still communicate over the network. Optional X Money and Ko-fi support links open external services only when clicked; their badge images are bundled locally.

---

Maintainer note — omit this section from listing: reuse item `eoadahoncjfpnennmkjifohclbafjkol`. Editing this source does not change the live dashboard. The release handoff separately records publication and exact artifact verification. Screenshots show actual extension DOM with safe synthetic example data, not receiver telemetry.
