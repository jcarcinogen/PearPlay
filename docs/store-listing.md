# Chrome Web Store listing draft — 0.3.1

**FLATPAK-INSTALLED VERSIONS OF GOOGLE CHROME AND CHROMIUM ARE NOT SUPPORTED.** On Linux use your distribution’s native browser package format.

PearPlay sends compatible browser video directly to Apple TV—without screen mirroring, re-encoding or a cloud relay. A separate PearPlay Helper is required for TV playback. No PearPlay account.

Choose a video, find your Apple TV, pair if asked, then Send to TV. Pairing never sends video automatically. Finding TVs is deliberate, not repeated every time you open the popup. Website access is requested when you click; all-sites access is currently required to find videos.

Before casting, control the selected browser video: play/pause, timeline, 5/10/15/30-second jumps, mute and Picture in Picture. These are browser controls, not TV seeking. During casting the browser transport is hidden. End helper session closes the helper connection; if the TV keeps playing, use its remote.

Pause TV / Resume TV are available with helper 0.3.1 and a supported authenticated Apple TV session. The older Fedora helper does not provide these controls. TV timeline, seeking, jump and volume controls are not implemented.

Browser controls have been checked in Chrome on macOS, Windows and Linux. Apple TV picture and sound have owner-confirmed checks on Mac and Windows. Windows pause/resume and End helper session were owner-tested with a newer helper candidate. Prior playback has been user-confirmed through the extension and helper in Linux Chrome, Brave and Chromium on tested streams. Chrome video and audible sound were separately confirmed. Audio and broader stream compatibility in Brave and Chromium have not been separately documented. These checks are not a promise that every site, browser or receiver works. LG live HLS remains unresolved; other AirPlay TV compatibility varies.

Helper downloads: Mac Apple silicon, Windows x86_64, Ubuntu/Debian x86_64 and Arch/Omarchy x86_64 helper 0.3.1; Fedora 44 retains helper 0.2.8. Python is bundled. No Intel Mac or Linux/Windows ARM installers. Windows setup and maintenance are fully branded. Mac and Windows builds are unsigned experimental software: Windows security policy may block installation, including on the test computer. Stop if blocked; never disable OS protections. Mac builds are not Apple Developer ID signed or notarized. Trusted Windows signing is pending.

Only receiver-fetchable HTTP(S) streams can be sent to TV. Browser-only video URLs may work with browser controls but cannot be sent directly. Cookies, DRM, geography and access restrictions are not bypassed. PearPlay does not block ads. Not every website works.

Mac Chrome and Brave share one helper connection, including disconnection. Linux supports separate Chrome, Brave and Chromium connections. Windows targets the current user’s Chrome. Pairings stay local to that OS user; Windows uses DPAPI. Pair separately on each OS. Safari extension development is paused.

No first-party telemetry uploader or cloud media relay. Your browser, dependencies, media provider and TV still communicate over the network. Optional X Money and Ko-fi support links open external services only when clicked; their badge images are bundled locally.

---

Internal submission note — omit this section from listing: reuse item `eoadahoncjfpnennmkjifohclbafjkol`. Upload the final 0.3.1 ZIP only after public-download, Pages and ZIP checks in the release kit pass. GitHub publication and Store approval are separate. Screenshots use actual final extension DOM with safe synthetic example data, not receiver telemetry.
