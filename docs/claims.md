# Public claims and evidence

**Linux only. Mac support is coming soon.**

This is the claims ledger for the refreshed README, landing page and editable social/store art. `STATUS.md` is authoritative for human playback observations; its current scope and latest playback sections supersedes contradictory historical checkpoints below. No new TV trial took place during this refresh. UI fixtures and protocol events are not playback evidence.

Source file references remain stable as lines move. The current landing source is `assets/landing/page.html`; `docs/index.html` is regenerated from it. Raster exports inherit the claims of their editable HTML source. “Verified” below always identifies what kind of verification occurred.

## Claim ledger

| Public claim / qualification | Where it appears | Evidence source | Verdict / boundary |
|---|---|---|---|
| “Your browser’s video. Your Apple TV.” | README; landing 3–5,17; social-preview.html 1; positioning | `contract/v1.md`; `STATUS.md` | Positioning promise, always accompanied by compatible-stream and Linux-only qualifications; not every website. |
| Compatible HTTP(S) media is fetched directly by Apple TV; Native Messaging carries control, not media | README; landing 17–18; store listing sources 1; feature-direct.svg 1 | `contract/v1.md`; `extension/worker.mjs`; `helper/native.py` | Source/contract fact, supported by the bounded live result. |
| No screen mirroring, re-encode/transcode or Mac media relay for Linux | README; landing 17–18 | `STATUS.md`; `helper/README.md`; `contract/v1.md` | Architecture, not a comparative quality or latency claim. |
| No promised resolution or universal website compatibility | README; landing 17–18,37 | `STATUS.md`; `extension/core.mjs`; `contract/v1.md` | Explicit limitation. URLs and format filtering do not prove codec or site support. |
| No PearPlay account or cloud service required | README; landing 18,38 | `STATUS.md`; `extension/worker.mjs`; `helper/native.py`; `helper/install.py` | First-party source/architecture audit. Origin-site accounts and network requests remain outside this claim. |
| Explicit grant, stream and receiver choice; Send initiates handoff | README; landing 17,19; listing sources 1 | `contract/v1.md`; `extension/popup.js`; `extension/worker.mjs` | Existing behavior retained. A sole candidate or receiver can be selected automatically; sending is never automatic. |
| Website access is requested on a click, not silently at installation | README; landing 19,37 | `extension/manifest.json`; `extension/popup.js`; `extension/worker.mjs` | Permissions contract; protected by `tests/extension/ui.test.mjs` and worker tests. |
| This version requires all-sites access; the per-site grant alone does not enable discovery | README; landing 19,37; install guide; popup access details | `extension/popup.js` | Known limitation, plainly disclosed in the README limitations, usage and FAQ. Not fixed or hidden by this refresh. |
| Browser playback stays under website controls; no automatic pause from the popup | README; landing 19,37 | `extension/popup.js`; `tests/extension/ui.test.mjs`; `extension/worker.mjs`; `extension/content.js` | Browser pause/resume UI and popup wiring removed at owner request. No automatic pause added. Lower-level explicit-confirmation checks remain tested, but are not presented as popup features. |
| Linux Chrome extension/helper FOX 13 video and audible sound | README; landing 17,20; social and listing footer | `STATUS.md` | Human-confirmed on the recorded receiver/path, not re-tested here. |
| FOX pre-roll-to-program transition on the tested stream | README; landing 20,37 | `STATUS.md` | Human-confirmed on that pre-roll. Do not reuse older “not observed” rows as the latest verdict. |
| PearPlay does not block ads | README; landing 20,37 | `STATUS.md`; `extension/worker.mjs`; `extension/manifest.json` | No ad-blocking feature; network observation is not blocking. No claim that every ad path works. |
| End helper session stopped one FOX trial and recast worked | landing 20 | `STATUS.md` | Human-confirmed bounded result. Not a general receiver-stop guarantee. |
| End helper session does not confirm TV stop; physical remote fallback | README; landing 20,37; popup; install guide | `contract/v1.md`; `helper/native.py`; `helper/README.md` | Safety-critical qualification preserved. Source stops local transport with unverified evidence. |
| TV pause/resume are unavailable | README; landing 20,37; listing footer; popup | `STATUS.md`; `helper/native.py`; `helper/README.md` | Unsupported, not a shipped control; hidden legacy buttons are removed from keyboard traversal. |
| Public HLS video/audio via the earlier command adapter | landing 20 | `STATUS.md` | Human-confirmed CLI path. Not presented as a new extension/browser trial. |
| Pairing credentials persist locally; reconnect without another PIN | README; landing 18,38 | `STATUS.md`; `helper/native.py`; `spikes/001-airplay/pearplay.py` | Human observation plus source. Single-receiver store; no multi-receiver credential-vault promise. |
| 0700 credential directory / 0600 credential file | landing 38; install guide | `STATUS.md`; `spikes/001-airplay/pearplay.py` | Enforced directory/file checks and atomic write; not a claim that credentials are encrypted at rest. |
| PIN not persisted by extension; submitted for pairing with a masked field | README; install guide; popup | `extension/popup.html`; `extension/popup.js`; `extension/worker.mjs`; `contract/v1.md` | Source fact. Render/test fixtures use no real PIN and do not prove authentication. |
| Signed URLs are transient, not put in logs/reports/marketing | README; install guide | `contract/v1.md`; `extension/core.mjs`; `helper/native.py`; render fixture | Source policy/implementation: memory-only candidate URLs, sanitized helper logging. No assertion about browser/OS forensic memory. |
| Linux only. Mac support is coming soon. | README, landing, store listing, popup and setup | `STATUS.md`; `extension/setup.mjs`; `extension/popup.js`; `tests/extension/platform-scope.test.mjs`; `assets/evidence/linux-only-platform.json` | Current product scope, not an estimated release date. Mac work is paused; no Mac downloads or active setup flow. |
| Brave integration and Chromium TV playback unverified; Linux Chrome is the playback baseline | README; landing 17,20; listing footer | `STATUS.md`; `tests/browser/README.md`; `extension/manifest.json` | Brave integration remains unverified. Linux Chromium helper connection/removal checks are separately recorded in `assets/evidence/helper-onboarding-verification.md`; TV playback remains unverified. Edge is not an installer target. |
| Invalid/expired-stream and broader receiver lifecycle trials remain open | README; landing 20,37 | `STATUS.md`; `contract/v1.md` | Unverified, plainly labeled; observed FOX stop/recast does not close the wider matrix. |
| `blob:` cannot be handed off; browser cookies are not transferred | README; landing 37 | `extension/core.mjs`; `extension/content.js`; `contract/v1.md` | HTTP(S)-only validation and URL-only control contract. |
| No DRM, geography or access-control bypass | README; landing 37; install guide | `contract/v1.md`; `extension/core.mjs`; `STATUS.md` | Deliberate scope: receiver fetch must succeed under the source’s controls. Not a universal geo-failure detector. |
| Experimental manual installation; unpacked MV3 extension + local Python helper | README; landing 17,21–36; install guide | `extension/manifest.json`; `helper/README.md`; `helper/install.py`; `requirements.txt:1–3` | Source-backed setup. No store package/release claim. |
| Python 3.11+, pinned pyatv 0.18.0; machine-local venv; installer changes no packages/firewall | README; landing 21–36; install guide | `helper/README.md`; `requirements.txt:2`; `helper/install.py` | Manual commands reviewed against source; no new dependency installed in this refresh. `uv` is the chosen setup tool, not a helper runtime dependency. |
| Receiver-scoped UDP timing 49170 was required on the tested Linux host | README; install guide | `STATUS.md`; `helper/native.py` | Host-specific evidence, not a universal network rule. No firewall changed here. |
| Mac runtime and signing work is preserved but paused | Archived Mac guides and STATUS history | `docs/mac-runtime-identity.md`; `docs/mac-terminal-install.md` | Historical research only; not a Linux release gate or active workaround. |
| Uninstall removes exact owned registration, preserves unknown files/credentials/source/venv | README; install guide | `helper/install.py`; `helper/README.md`; `tests/browser/README.md` | Source and historical isolated integration evidence, plus current offline tests. |
| No telemetry endpoint in audited first-party extension/helper | README; landing 38 | See privacy audit below | Narrow source audit, not a promise of zero browser/dependency/site network activity. |
| Independent and unaffiliated with Apple; working name not trademark-cleared | README; landing footer | `docs/positioning.md` (brand policy); pre-refresh README recorded working-name status | Project identity declaration, not trademark clearance or third-party endorsement. No Apple/AirPlay mark used. |
| MIT license for original project code | README; landing footer | Root `LICENSE`, selected by owner; adapter notices retained | Does not replace third-party licenses or trademark rights. |
| Real extension screenshots; example data, not live playback | README; landing 17; listing captions | `scripts/render-brand-assets.mjs`; `tests/browser/brand-fixture.js`; `assets/evidence/render-verification.json` | Headless Chrome renders the actual unpacked popup document. Browser/native responses are synthetic; not an actual action-popup transport or TV trial. |

## Privacy audit

Scope: all first-party files under `extension/` and `helper/`, plus the secure Store implementation called by the helper. The source trace finds DOM/currentSrc collection (`extension/content.js`), in-memory candidate storage and label-only views (`extension/core.mjs`), Chrome Native Messaging (`extension/worker.mjs`, `extension/native.mjs`), receiver discovery (`helper/native.py`) and receiver connection (`helper/native.py`). The installer only writes the local native-host registration (`helper/install.py`).

No analytics/telemetry endpoint, account service or PearPlay cloud integration appears in that first-party path. Search covered HTTP URL literals, fetch/XHR/beacon calls, socket/HTTP imports and telemetry/analytics terms; matches were validated as permission patterns, URL parsing, user-selected media handling, native messaging or receiver transport. This does **not** audit Chrome internals, OS services, all transitive pyatv dependencies, the streaming origin or Apple TV. Do not convert it to “nothing on this computer ever phones home.”

Marketing images are sourced only from an isolated fresh Chrome profile and synthetic fixtures. Their display title and receiver are examples; the only address used is reserved documentation address `192.0.2.10`. No daily browser chrome, desktop, real receiver ID, credential, PIN or signed media URL is captured.

## Generated art and copy inventory

- `assets/store/listing-light.html` and `assets/store/listing-dark.html`: chosen video/TV, compatible direct handoff, Linux Chrome tested-stream verification, Mac support coming soon; Linux Brave/Chromium playback unverified, no TV pause/resume, real-popup/example-data qualification. These map to the corresponding ledger rows above.
- `assets/landing/social-preview.html`: promise, compatible direct handoff, Linux Chrome tested-stream verification and Mac support coming soon. Same ledger rows.
- `assets/landing/hero.html`: abstract brand mark, actual popup capture, schematic TV; no fabricated video or OS chrome. It is illustrative control-flow art, not the media path diagram.
- `assets/landing/feature-direct.svg:1`: source → receiver media path, supported by `contract/v1.md`.
- `assets/landing/readme.html` is generated directly from `README.md`; it carries no independently authored claims.
- A local Chrome Web Store description draft exists at `docs/store-listing.md`; no submission or public listing was created. Listing composites are local assets only.

## Evidence still needed

No new live Linux playback, daily-profile installation, real pairing, invalid/expired-media trial, Brave/Chromium test, or generalized receiver-stop trial was performed for this scope update. Mac work is paused and does not block Linux release. Keep those qualifications even if UI, contract or raster tests pass. The owner subsequently approved MIT and source/website publication. This does not establish a consumer helper release or Web Store availability; a social-preview upload remains separate.
