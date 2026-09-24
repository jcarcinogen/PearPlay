# PearPlay privacy policy

**Linux only. Mac support is coming soon.**

Effective September 23, 2026. This policy describes PearPlay extension 0.2.4 and its separate Linux helper. PearPlay is a development preview; a public Chrome Web Store release and matching consumer helper downloads are not yet available.

## What PearPlay does with data

PearPlay finds compatible media on pages for which you grant access. It processes video resource addresses, relevant page/video titles and frame/navigation information to offer a choice of video. Resource addresses can contain temporary authorization tokens. The extension keeps a bounded discovery session and session-only interface state; it does not offer a browsing-history collection service.

When you select a receiver and send a video, PearPlay passes the selected media address to its native helper and the selected AirPlay receiver. The receiver fetches the media from its original provider. That provider can observe the receiver's requests and network address under its own policy. PearPlay supports HTTP as well as HTTPS media and does not promise that every media transfer is encrypted.

Receiver discovery processes local-network addresses, identifiers and advertised capabilities. If a receiver requests pairing, you type its displayed PIN into a masked PearPlay field. The helper stores the resulting pairing credentials locally in the user's PearPlay state directory, with restricted filesystem permissions. The PIN is not intended to be retained or logged. Pairing information is not automatically erased when you remove the extension or disconnect the helper.

## Developer services and third parties

The current extension/helper contains no PearPlay account, advertising service, analytics uploader or cloud relay. It does not send discovery sessions or pairing credentials to the developer. Downloads and updates involve the hosting/package providers you choose. The current Linux helper is separately installed; source-based Linux setup may contact Python/dependency distribution services. Mac support is coming soon; Mac installation is paused.

Optional support links open external services only when clicked. Their policies apply after you open them. Support images are bundled locally, not fetched as tracking pixels by the extension.

## Your controls

You choose whether to install the separate helper, grant website access, discover receivers, pair a TV and send a video. Revoke site permissions through Chrome. Disconnect/remove the native helper using its installation guide; removing the extension alone does not remove native software or saved pairing. Removal commands preserve unrelated or modified files. Do not submit PINs, pairing files, private addresses or signed media URLs in public bug reports.

## Contact

For privacy questions, contact the maintainer through [PearPlay GitHub Issues](https://github.com/jcarcinogen/PearPlay/issues). Issues are public: do not include PINs, pairing files, private network details, or signed media URLs. GitHub’s own privacy policy applies when you use that service.

## Policy changes

Changes to data handling will be reflected here with an updated effective date. Review this policy and the release notes when updating PearPlay.
