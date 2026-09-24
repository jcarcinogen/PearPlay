# Mac runtime identity and signing gate — archived / paused

> **Current scope: Linux only. Mac support is coming soon.** Mac work is paused, with no release date. The historical Mac procedures/results below are not current install instructions or Linux release blockers. Resume only if Scott explicitly reopens Mac work; current Mac install/build entry points refuse new work. Existing installed runtimes and pairing remain untouched.


## Verdict

PearPlay now has a locally built, self-contained `PearPlay Setup.app` whose signed bundle identifier is `com.pearplay.helper`. Its main executable is `PearPlayHelper`, not an external Python interpreter. The runtime and dependencies stay inside the app, and the signed Info.plist includes the PearPlay Local Network explanation.

**Local development tests pass; consumer distribution is blocked.** Ad-hoc signing is not Apple-issued identity. The tested app passes strict recursive signature verification but fails Gatekeeper assessment. Apple TN3179 specifically recommends an Apple-issued identity for reliable Local Network permission tracking. Do not treat a working local build as a downloadable consumer release.

No Gatekeeper, quarantine, Local Network database, firewall, DNS or security settings were disabled or reset. No borrowed Hermes runtime, private entitlement or library-validation exception was used. No production helper was replaced. No commit, push or publication was performed.

## Implementation and verification

- Reuse PyInstaller's native `BUNDLE` layout, with the console bootloader retained for browser native-messaging stdin/stdout.
- Keep data and third-party licenses in `Contents/Resources`, with PyInstaller's normal code/data cross-links preserved. The prior hand-wrapped directory failed `codesign` because data directories were interpreted as nested code.
- Seal the completed app after adding license resources, using explicit identifier `com.pearplay.helper`. Verify recursively and run the dependency self-test again after signing.
- Retain the production build gate requiring application signing, installer signing and notarization credentials. Local development builds remain clearly labelled development.
- Regression test failed before the layout change and passes after it. Full suites: 62 Python tests and 31 JavaScript tests passed.
- Actual packaged-development build succeeded on arm64 macOS. `codesign --verify --deep --strict` and the bundled dependency self-test passed. `spctl --assess --type execute` returned rejected (exit 3).
- **Chrome:** actual isolated Google Chrome 153.0.8010.53 connected and found Apple TV plus another video-capable receiver (LG, compatibility unverified). Discovery also passed after restarting the test browser. Missing helper, repeated connect/repair, hello/status, removal and fresh host-not-found tests passed.
- **Brave:** actual isolated Brave (Chromium engine 153.0.8010.53) passed a uniquely named test-host negative control, connection, two discovery rounds, restart, two more discovery rounds, and post-removal host-not-found. All four discovery rounds found both receivers. Test-host cleanup and unchanged existing registration were verified.
- No pairing or playback was attempted in these tests. Human-confirmed Mac video/audio remains a separate gate. Cross-version permission persistence and a fresh Mac download/install remain untested.

### Important Brave registration finding

Brave on macOS deliberately uses the standard Chrome native-host directory, independently of its disposable browser profile. The first naive Brave probe therefore reached the existing Chrome helper; its handshake and empty scans are **invalid evidence about the new runtime**. A missing-host negative control caught this.

The corrected test used a random `com.pearplay.test_…` host manifest in the standard host directory, authorized only for the public fixture extension, with the copied test extension referencing that unique name. It pointed directly to the new app executable. It was created exclusively, read back, removed only after exact-content verification, and verified absent. Existing `com.pearplay.helper` manifest/launcher hashes were unchanged. No daily browser tabs or settings were touched.

**Consumer Brave installer registration remains an explicit follow-up:** `helper/install.py` currently treats Brave's configuration folder as its native-host location. Do not claim the current Brave checkbox installs correctly on macOS. Correct the shared Chrome/Brave host-location and disconnect semantics, with separate browser-detection paths and lifecycle tests, before shipping. This does not invalidate the corrected runtime test.

Reference: [Brave native-host directory override](https://github.com/brave/brave-core/blob/master/app/brave_main_delegate.cc).

## How Scott obtains the required Apple signing identity

1. Enroll in the [Apple Developer Program](https://developer.apple.com/programs/enroll/). Apple currently lists **US$99 per membership year**. Free Xcode/Apple Account access does not include Developer ID distribution and notarization. Do not enroll or pay automatically.
2. In **Certificates, Identifiers & Profiles → Certificates → +**, request **Developer ID Application**. Follow Apple's Certificate Signing Request instructions using Keychain Access on the build Mac. Download and open the resulting `.cer` to install it alongside its private key in Keychain.
3. For the existing `.pkg` workflow, also create **Developer ID Installer**. This signs the installer; it does not replace signing the application and its bundled libraries. A future notarized DMG/app delivery would use Developer ID Application without the Installer certificate, but that delivery route is not built here.
4. Configure notarization credentials locally in Keychain using `xcrun notarytool store-credentials` and its secure interactive prompts, following Apple's guide. Keep passwords, API keys and signing private keys out of chat, the repository and shared IronWolf source. Never export them into the test kit.
5. Build the helper with the actual, verified Chrome Web Store extension ID and the real certificate identity names. The repository builder accepts `--sign-app`, `--sign-installer` and `--notary-profile`; these are existing release inputs. It signs bundled code with the application identity and hardened runtime, signs the package, submits it for notarization and staples/validates the package ticket. **This Apple-signed path is not yet exercised on this Mac: no valid signing identities were available.**
6. Verify the signed app, TeamIdentifier, hardened runtime, package signature, successful notarization and Gatekeeper acceptance. Then download the actual release through a browser and test it on a clean Mac with security settings unchanged, in both Chrome and Brave, including deny/retry and permission persistence after update. Notarization does not replace testing.

Expected consumer journey: download and open a recognized installer, connect the browsers, then approve the ordinary PearPlay Local Network request. No Python selection, security override, quarantine removal or privacy reset should be required. That journey remains a release goal, not a completed claim.

### Official sources

- [Apple TN3179: Local Network privacy, build-time identity requirements](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy#Build-time-considerations)
- [Apple membership comparison and price](https://developer.apple.com/support/compare-memberships/)
- [Create Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates/)
- [Customize the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow)

## Local artifacts and honest resume point

The current development-only app/package and raw verification logs are machine-local at:

`<local-scratch>/pearplay-owned-runtime-integrated/`

These are scratch artifacts, not public downloads; scratch may be pruned. Rebuild using `scripts/build_helper.py` in a machine-local environment with `pyinstaller==6.21.0` and `pyatv==0.18.0`. The rehearsal build used fixture ID `iojhjdcndgfoalcialdlgklfdnlpmobf`, **not a production allowlist**. The frozen executable's build UUID is derived by PyInstaller from the frozen payload; do not borrow a generic Python executable or manually randomize an installed binary.

Next gates: obtain Apple credentials only if Scott chooses this cost; correct Mac Brave shared-host registration; rebuild with the verified store identity/license; prove notarized download/install, clean-machine permissions, update persistence and human-observed video/audio in both browsers. Preserve current installation and saved pairing until that replacement is explicitly ready.
