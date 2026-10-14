# Helper onboarding

For this experimental cross-platform preview, use the existing platform packages and [installation guide](install.md). Linux connects Chrome, Brave and Chromium separately. Mac Chrome and Brave share a native-host registration; Chromium is separate. Windows targets current-user Chrome through HKCU and protects saved pairing with DPAPI. Python is bundled. Fully quit and restart the browser after connecting. A successful Check connection establishes native messaging, not discovery or playback.

For builds, use the [three-platform CI](helper-ci.md) and existing builders. Check exact artifact bytes, source hashes, production identity, registration and cleanup. Never treat fixture or hosted results as owner/receiver acceptance. Do not silently install tools or bypass OS protections.

PearPlay 0.3.3 retains the active TV session across popup reopening and tab switching, remembers a preferred TV by rediscovered identity, and provides deliberate original-source-only browser mute. The Web Store updates only the extension; update the separate helper to 0.3.3 for read-only TV progress, keeping saved pairing.
