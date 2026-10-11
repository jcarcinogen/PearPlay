# Claims and evidence

- Direct URL handoff/no re-encoding: extension/native control contract and helper transport; only receiver-fetchable HTTP(S) media. No DRM/cookie/access bypass.
- Cross-platform packages: [CI38166068566](https://github.com/jcarcinogen/PearPlay/actions/runs/38166068566), independently verified artifacts/source hashes. Windows exact installer lifecycle passed on hosted Windows; owner Application Control remains unresolved.
- Mac: arm64 package, frozen self-test and strict ad-hoc signature checks. Unsigned PKG and no notarization; normal system/owner consent is a separate boundary.
- Browser controls: real Chrome popup→worker→content tests exist for Mac, Windows and Linux. Synthetic UI captures supplement but do not replace these.
- Receiver results: earlier owner Apple TV picture/sound observations on Mac/Windows and prior Linux playback; Windows pause/resume/end observed on an earlier candidate. These are not final-package re-tests or universal compatibility.
- Privacy: local pairing storage (DPAPI on Windows), no first-party telemetry uploader/cloud relay; media provider, dependencies and TV still communicate. Optional support links contact third parties only when clicked.
- TV controls: helper0.3.1 session-bound pause/resume on supported authenticated Apple TV sessions; no seeking/timeline/jumps/volume. Use TV remote if End helper session leaves playback running.
- Store images: actual shipping DOM with synthetic example data, never personal account/receiver telemetry.

Consult [privacy](privacy.md), [release scope](cross-platform-preview.md), source tests and exact release-kit reports. Claims are limited to the recorded artifact/OS/path; a successful HTTP response or helper state is not human-observed playback.
