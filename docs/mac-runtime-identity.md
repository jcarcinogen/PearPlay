# Mac runtime identity and signing gate — development preview reopened

> Scott explicitly reopened the Mac/Windows/Linux Chrome product in October 2026; Safari is paused. Mac packaged development builds are enabled again. Unsigned Mac previews are local test artifacts, not a production consumer release. Existing installed runtimes, browser profiles and pairing remain untouched.

## Current 0.3.0 Mac preview

Built on arm64 macOS 27.0.1 using the approved private Python 3.11.15 environment, pyatv 0.18.0 and PyInstaller 6.21.0. The production extension identity is `eoadahoncjfpnennmkjifohclbafjkol`; no fixture key or fixture catalog is substituted. `development:true` remains explicit, and no diagnostic opt-in is enabled during verification.

Durable kit: `/Volumes/IronWolf/Stuff/PearPlay/Cross-platform Preview/Mac/`.

- Package: `pearplay-helper-0.3.0-darwin-arm64-development.pkg`, SHA256 `498a06bf521168324996dddd09b86f314e37473d7034e9037e97f1a1b73e9e6c`.
- Named self-contained app: `/Applications/PearPlay Setup.app` in the package, identifier `com.pearplay.helper`, executable `Contents/MacOS/PearPlayHelper`. The package was **not installed**. Native messaging was tested against its expanded payload in cache.
- Expanded dependency self-test passes and reports version 0.3.0, dependencies loaded, network not used. Strict deep codesign verification passes. The app is ad-hoc signed with no TeamIdentifier; the `.pkg` has no signature. Gatekeeper rejects both (exit 3), as expected. No security override, quarantine change or privacy reset was used.
- All **969 packaged payload entries** match staged bytes, modes and symlink targets. No installer scripts. Project and Python licenses plus **69 notice files** are included; inventory covers **41 build-environment distributions**, including build/test tools, not a claim that all 41 are imported by the app.
- Official headless Google Chrome 155.0.8059.40 with an owned disposable profile and normal sandbox settings passes real setup/native missing → ready → full restart-ready → removed/missing. Repeated connect/repair, exact allowlist/runtime path, hello 0.3.0, idle status, explicit shared removal and cleanup pass. No discovery, pairing or playback. This is Chrome/native evidence, not native GUI or receiver acceptance.
- Focused verification: **39 passed, 15 skipped, 2 subtests**. Linux package staging regressions pass; Debian-native execution tests skip on Mac. Full pytest was genuinely executed: after fixing the obsolete version assertion, **467 passed, 15 skipped, 40 subtests, 1 failure**, repeated in a serial full run. The existing standalone transport cancellation-cleanup test also fails in isolation. See `MAC-BLOCKER.md`; no test was weakened and the parent-owned transport was not edited.
- Runtime/build/package/browser reports, source hashes, license inventory, full test logs and `MAC-HANDOFF.md` are in the kit. `MAC-GUI-PATCH.md` lists remaining app.py integration for its owner. Rebuild and repeat artifact verification if app.py/native.py or other frozen inputs change; the builder now detects source drift during the build.

### Shared Mac registration

Chrome and Brave use the same `Google/Chrome/NativeMessagingHosts` directory on Mac. `install.host_dir` expresses this, while `install.browser_dir` stays browser-specific for detection. Setup offers one **Google Chrome and Brave (shared connection)** item, explicitly warning that connecting/disconnecting affects both browsers. Direct removal requires both browsers selected or an explicit `shared_disconnect` acknowledgment; foreign/modified/symlinked registrations remain preserved. Chromium is separate. Synthetic filesystem lifecycle tests cover shared repair, conflicts, guarded removal and preservation. No new Brave browser runtime test is claimed for 0.3.0.

### Release and installation limits

Developer ID application signing, installer signing and notarization are still required for production builds. No signing credentials were accessed and nothing was published. The unsigned preview is ready as a packaged engineering artifact, **not a Gatekeeper-approved or all-tests-green consumer candidate**. Do not provide security-bypass steps. A clean-machine download/install, native setup GUI, Local Network consent/retry and persistence across updates, Brave runtime, and watched video/audio remain separate gates.

The historical Terminal/source-runtime installer remains closed to new installs, with wording directing users to the packaged preview. Its receipt-/exact-byte-guarded removal path remains available and explains the shared Chrome/Brave effect. Generic Python identity is not reopened as the recommended consumer route.

## Historical 0.2.x research (retained, superseded where noted)


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

**Historical registration gap, repaired in the 0.3.0 source above:** the earlier installer treated Brave's profile folder as its native-host location and offered misleading independent controls. Shared host mapping, separate detection and guarded disconnect lifecycle tests are now implemented. The earlier corrected Brave runtime result remains historical evidence, not a 0.3.0 installer or browser acceptance claim.

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

The historical artifacts above are not the current preview. Current gates are listed in the 0.3.0 section: parent-owned transport cleanup failure and app GUI integration first, then signed/notarized clean-machine installation and permission/update/receiver acceptance if Scott authorizes those stages. Preserve current installation and saved pairing until a replacement is explicitly ready.
