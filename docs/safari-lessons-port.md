# Safari lessons brought to Chrome

The Safari extension is paused. `spikes/003-safari-native/` is retained read-only; the Chrome candidate borrows its interaction/safety lessons, not its native AirPlay transport or feature set. Source references below describe what was inspected, not a new Safari or TV trial.

## What actually transfers

### 1. An async Play result belongs to one exact source

Safari's `extension/media.mjs` records an opaque document token, element record, source signature and stream object. `valid()` verifies the same record/document/connected element/source before controls. `play()` rechecks validity on both promise fulfillment and rejection: a changed element/source produces `VIDEO_CHANGED`, not success or a misleading autoplay-permission failure. `emptied` and `loadstart` permanently invalidate that record, even if the URL later looks unchanged. A scan retires old records/listeners.

Chrome's `extension/content.js` uses `WeakMap` element IDs and a numeric source epoch. `emptied`/`loadstart` increments the epoch, removes the live mapping and retires the ID. Before `localResume`, it captures the epoch and exact element/source; after the play promise settles it requires the connected element, live ID mapping, exact URL and unchanged epoch. That prevents an A → B → A source cycle from resurrecting a stale action. It neither retargets another video nor sends a corrective pause to a changed source.

`tests/extension/safari-lessons.test.mjs` covers source change, detached element, replacement element, source-restored invalidation and rejected resume with a changed source. `tests/extension/worker-lessons.test.mjs` separately exercises navigation/revalidation and stale local-control boundaries. These APIs/tests do not imply visible browser-play buttons or TV resume capability; website controls remain the user playback surface.

### 2. Keep deliberate selection, invalidate replacement

Safari's popup retains the chosen tab/frame/document/opaque-target identity, restores it only after tab/permission/status checks and reports stale/closed/permission failures without switching to a new video. `sameChoice` also guards a pending scrub action against a changed selection. That is a useful contract even though Chrome has a different URL-handoff architecture.

Chrome's `Sessions` in `extension/core.mjs` tracks document/frame identity, candidate/element/source and a `selectionLost` tombstone. Rescanning the exact chosen video preserves it. Removal, source replacement, document navigation or bounded candidate eviction clears an invalid choice and records selection loss. `popup.js` may initially choose a sole candidate only when there is no lost deliberate selection; it must not auto-select the sole replacement after loss. An unrelated frame navigation does not invalidate a still-valid choice in the original frame. Sending is always explicit and worker revalidation must succeed before native start.

Tests in `safari-lessons.test.mjs`, core/worker tests and the UI worker's `popup-lessons.test.mjs` exercise exact-preservation, lost-selection and no-retarget behavior. Do not claim all candidates are always manually selected; the first sole-candidate convenience is intentionally distinct from replacement selection.

### 3. Quiet refresh must not steal keyboard focus

Safari's `popup.mjs` refreshes status only while visible, ready, not closed, not busy and not scrubbing. Quiet polling holds the async busy guard but avoids disabling focused buttons; static SVG children remain intact while labels/glyph visibility changes. An in-flight refresh is awaited before committing a scrub; pagehide stops refresh and stale completion writes. `tests/browser-popup.mjs` checks focused Play and timeline controls, Tab traversal, keyboard seek and drag behavior in that Safari spike's browser harness.

Chrome's UI port serializes `refresh()` to one in-flight view, rejects racing actions and checks popup visibility/closed state before later writes. Its option renderer compares an identity/label/selection key before replacing option children, keeping unchanged selections stable across polling. Closing the popup prevents stale DOM/selection/session writes. The UI worker's popup-lessons tests cover quiet-refresh serialization, unchanged option objects, closed-popup completion and lost-selection controls. Browser-level keyboard focus and the final 400×600 state matrix remain the UI worker's evidence, not proof from this source review.

## Capability boundary — do not copy labels without their APIs

Safari uses WebKit-specific `webkitShowPlaybackTargetPicker`, wireless state and `webkitSetPresentationMode`/seekable timeline controls. Chrome's helper uses Native Messaging plus a selected HTTP(S) URL. Safari picker activation, browser-reported wireless playback, timeline, mute/seek, Picture in Picture and native TV pause/resume do not become Chrome helper capabilities merely by porting the visual layout.

The Chrome candidate retains its actual permission model, separate helper setup, Find TVs, masked PIN when required, explicit Send and End helper session. It does not transfer browser cookies, send `blob:` URLs, bypass DRM or automatically pause browser video. Use website controls and the TV remote. “Sent” and protocol Playing remain weaker than human picture/audio confirmation.

## Integration evidence and remaining checks

Focused onboarding tests exercise `mountSetup` against nodes drawn from the actual setup HTML, with injected browser/catalog/native responses for Linux/Mac/Windows. They validate links and deliberate setup discovery, not native OS playback. The full Node suite also exercises the UI/content/worker source regressions; exact latest counts/failures are in the docs handoff.

Keep final popup/browser acceptance with the UI worker: permissions denied/granted, empty/missing/ready, long labels, fresh masked PIN, accepted V1, unsupported receiver, page/source replacement, close/reopen, keyboard focus and action controls in 400×600. Parent owns art/landing generation and the final self-service TV checklist. Platform workers supply native artifacts and integration evidence; new Mac/Windows human playback remains unverified.
