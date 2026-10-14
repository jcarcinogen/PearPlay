# PearPlay privacy policy

**Privacy policy for PearPlay’s cross-platform experimental release.**

This policy describes PearPlay extension and helper 0.3.3 for desktop Chrome on Linux, macOS and Windows. Install the extension from the Chrome Web Store; native helpers are separately installed from GitHub releases. Refer to the release and installation pages for current downloads. Mac and Windows helpers are unsigned experimental software. Safari extension development is paused. See [preview evidence and gates](cross-platform-preview.md).

## What PearPlay does with data

PearPlay finds compatible media on pages for which you grant access. It processes video resource addresses, relevant page/video titles and frame/navigation information to offer a choice of video. Resource addresses can contain temporary authorization tokens. The extension keeps a bounded discovery session and session-only interface state, including the selected jump interval. Browser-video controls read playback position, duration, seek ranges, pause/mute and Picture in Picture state from the selected video and apply your requested actions. During supported TV sessions, the helper processes session-bound pause/resume commands and receiver playback events, including read-only position and duration. The worker keeps the original media/frame/document identity and active cast context in memory across popup reopening and tab switching; media addresses are not saved in persistent browser storage. Deliberate Mute browser video targets only that original source and current cast session. Muting and restoration are not automatic. It does not offer a browsing-history collection service.

When you select a receiver and send a video, PearPlay passes the selected media address to its native helper and the selected AirPlay receiver. The receiver fetches the media from its original provider. That provider can observe the receiver's requests and network address under its own policy. PearPlay supports HTTP as well as HTTPS media and does not promise that every media transfer is encrypted.

Receiver discovery processes local-network addresses, identifiers and advertised capabilities. The extension saves the preferred receiver identifier in local browser storage and selects it only after rediscovery; it does not automatically discover or start playback when the popup opens. If a receiver requests pairing, you type its displayed PIN into a masked PearPlay field. The helper stores the resulting pairing credentials in OS-user-local PearPlay state: restricted filesystem permissions on Linux/Mac; current-user DPAPI protection and user-local access controls in the Windows preview. Windows state is not portable to another user/computer/OS, and pairings should not be copied across operating systems. The PIN is not intended to be retained or logged. Pairing information is not automatically erased when you remove the extension or disconnect the helper.

## Developer services and third parties

The audited first-party extension/helper control path contains no PearPlay account, advertising service, analytics uploader or cloud relay. It does not upload discovery sessions or pairing credentials to the developer. This is not a promise of no network activity: local discovery/control, browser/download/update services, dependencies, the media provider and receiver still use networks. Helpers are separately installed; source-based Linux setup may contact Python/dependency distribution services. Mac/Windows candidate checks, signing/notarization or hosting services are separate from telemetry and remain subject to their own policies.

Optional support links open external services only when clicked. Their policies apply after you open them. Support images are bundled locally, not fetched as tracking pixels by the extension.

## Your controls

You choose whether to install the separate helper, grant website access, discover receivers, pair a TV and send a video. Opening Helper setup checks the local native connection; it does not automatically discover, pair or send. Find my TV explicitly starts network discovery. Revoke site permissions through your browser. Disconnect/remove the native helper using its platform installation guide; removing the extension alone does not remove native software or saved pairing. Mac Chrome/Brave share native-host registration, so disconnecting it affects both. Windows registration is per-user HKCU, not a machine-wide service. Removal preserves unrelated or modified files and saved pairing. Do not submit PINs, pairing files, private addresses or signed media URLs in public bug reports.

## Contact

For privacy questions, contact the maintainer through [PearPlay GitHub Issues](https://github.com/jcarcinogen/PearPlay/issues). Issues are public: do not include PINs, pairing files, private network details, or signed media URLs. GitHub’s own privacy policy applies when you use that service.

## Policy changes

Effective date: October 14, 2026. Changes to data handling will be reflected here with an updated effective date. Review this policy and the release notes when updating PearPlay.
