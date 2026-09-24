# Installer 0.2.3 review disposition

> Historical verification snapshot. Current scope: **Linux only. Mac support is coming soon.** Mac procedures/results below are archived research, not active release gates. Follow current STATUS and docs/helper-onboarding.md for the Linux release.

Two independent read-only reviews were returned. The Mac terminal-core review reported no concrete findings in `scripts/macos_setup.py`, `install-macos.sh` and `helper/install.py`. The broader review inspected an earlier snapshot, before the Mac route change and subsequent installer tests. Its findings were evaluated against current source rather than accepted as authoritative.

| Broader finding | Disposition and evidence |
|---|---|
| Source-layout check breaks frozen package installation (`install.py:63`) | Not applicable to the frozen path. `plan(executable=...)` returns at line 59 before source validation. `app.py` passes `executable`. Real extracted Linux package registration/hello/status/removal succeeded in Chrome; see the test kit's `evidence/linux-chrome.json`. Retain source checks for the source-runtime path. |
| Unknown store ID and absent project license prevent production builds | Valid, already recorded release gates. Do not bypass them. Runtime `valid_build()` validates embedded build identity; it does not read the release catalog/license. Development builds have their explicitly separate fixture identity. |
| Generic source-installer errors block consumers | Generic errors remain a developer-fallback diagnostic limitation, not a demonstrated frozen-package failure. Packaged GUI surfaces per-browser conflict/preserved outcomes. Mac terminal installer prints a safe conflict/runtime-error explanation. More granular diagnostics are optional improvement; do not expose raw secrets or paths from protocol exceptions. |
| Documentation requires Git/source checkout for consumers | Earlier snapshot superseded. Current Linux package needs no checkout or Python setup. Mac archive copies its shipped source into a machine-local private runtime and needs no Git checkout or manual ID. Public downloads remain an actual release gate. |
| Mac signing/notarization blocks release | Superseded by Scott's explicit decision to use the Terminal source-runtime route. No signed Mac package is a deliverable. Local Network permission and TV playback remain independent unverified gates. |
| `network_tested:false` in build report | Intentional truthful scope: package construction performs dependency smoke tests, not discovery or playback. Preserve the distinction; record later network acceptance separately. |
| No frozen/helper GUI coverage | Current build performs frozen dependency smoke checks, and real Chrome exercises the extracted package. New first-launch/maintenance logic has a unit test with OS dialogs mocked. Human GUI interaction and real OS-package install/update/remove are still required; unit/browser checks do not substitute for them. |
| Zenity availability and browser detection | Linux package now declares Zenity and Avahi. Service availability and new-distro desktop behavior still need clean-system testing. Directory-only browser detection is intentional and avoids reading profile contents. |

No new implementation defect was established by these reviews after source/evidence verification. This is not a security certification or a consumer-release approval. The unresolved release gates remain in `docs/web-store-readiness.md`; joint live installation and playback tests are next. No code was changed merely to satisfy an unsupported review claim.
