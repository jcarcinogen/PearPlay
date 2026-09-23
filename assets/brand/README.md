# PearPlay brand and reproducible assets

## Identity

The pear-plus-play idea stays: a broad pear silhouette, a substantial leaf and a dark play aperture. A dark outline defines it on light toolbars; the pear fill defines it on dark ones. There is no background tile, Apple mark, AirPlay mark or browser-vendor logo.

- `mark.svg`: editable mark, transparent 1024 canvas.
- `app-icon.svg`: editable 1024 app-icon master, same geometry.
- `mark-small.svg`: optical 16px master. The body and play aperture are deliberately larger than a mechanical downsample; the leaf is simplified. The first downsample was too small to read confidently.
- `wordmark.svg`: horizontal, editable text; light-surface use.
- `palette.md`: palette, system typography choices and measured WCAG contrast.
- `icon-legibility.html` → `icon-legibility.png`: actual 16/32/48/128 PNGs at native size and enlarged on white, gray, dark and saturated blue. The enlarged copies use nearest-neighbor scaling to expose pixels, not smooth away problems.

## Regenerate

From the repository root:

```sh
./scripts/render-brand-assets.sh
```

No install, CDN, build service or network fetch is used. Required **existing** tools on the render machine:

- Node 24+ (built-in WebSocket/fetch; no npm package).
- Google Chrome with the `Extensions.loadUnpacked` CDP API. Verified here with Chrome 153 on macOS, sandbox enabled (no `--no-sandbox`).
- `rsvg-convert` (verified 2.62.3) for transparent SVG icon and feature-art PNGs.
- `python3.11` with the already-installed `markdown` module for a local rendering of the actual README. It is a renderer dependency, not a PearPlay runtime requirement.

Override installed executable locations with `CHROME`, `RSVG_CONVERT` and `PYTHON`. Missing tools fail rather than downloading replacements. Linux Chrome is discoverable by the script, but the published captures in this refresh are from macOS Chrome only. They do not establish macOS playback support. Never point automation at a daily browser profile.

The generator starts its own headless Chrome with a fresh directory under `TMPDIR` (the current session uses its managed scratch directory), binds debugging to loopback, loads the unpacked extension, and injects `tests/browser/brand-fixture.js` before the real `extension/popup.js` runs. It never rewrites the popup DOM to invent a UI and never starts the real native helper. It uses synthetic browser/native responses with `Living Room`, `192.0.2.10` and an example title; no receiver IDs, signed media URLs, accounts, pairing codes or credentials are captured. The pairing UI test submits an empty fixture value; it does not test live authentication.

**Scope of evidence:** real extension document rendering and UI event-handler behavior; not a native-message transport or TV integration test. These fixtures do not claim that an actual browser action-popup handshake or playback succeeded. The separate existing worker/native tests protect those contracts offline, and `STATUS.md` records historical human TV observations.

## Editable sources and generated outputs

| Source | Generated deliverable |
|---|---|
| `app-icon.svg` / `mark-small.svg` | `extension/icons/icon.png`, `icon16.png`, `icon32.png`, `icon48.png`, `icon128.png`; `assets/store/icon-1024.png` |
| Real `extension/popup.html` + `popup.js`, fixture boundary only | `assets/store/popup-{light,dark}.png` (full document), `popup-{light,dark}-viewport.png` (360×600) |
| `assets/store/listing-{light,dark}.html` | 1280×800 listing composites around the real viewport captures |
| `assets/landing/hero.html` | 1280×800 `hero.png`; real popup plus schematic art |
| `assets/landing/social-preview.html` | 1280×640 `social-preview.png`, copied to `docs/social-preview.png` for Pages metadata |
| `assets/landing/feature-direct.svg` | `feature-direct.png` |
| `assets/landing/page.html` | Self-contained `docs/index.html`: mark and screenshots embedded as data URLs, inline CSS/JS |
| Actual `README.md` | `assets/landing/readme.html` and `assets/evidence/readme.png` |
| Live pages and exercised popup states | `assets/evidence/*.png` and `render-verification.json` |

Edit `assets/landing/page.html`, then regenerate; `docs/index.html` is a ready-to-open, ready-to-host artifact, with no client-side build step. `docs/.nojekyll` disables Jekyll processing. Important landing copy is live HTML, not raster text. The social/listing export copy remains editable in its source HTML.

All new or replaced PNGs from this refresh are regenerated. The pre-existing root `tip-with-x-money.svg` and its old PNG counterpart are reused, not regenerated or redesigned.

## Checks performed by the renderer

- Every enabled visible popup control is reached with actual Tab key events; a 3px focus ring is checked. Collapsed details are opened for this traversal. Disabled controls are tested when their relevant state enables them.
- Popup handlers exercise grants, scanning/recovery, selections, helper connection/status, send/end, local confirmation/resume, the masked pairing UI and address Enter. Protocol responses are explicitly synthetic.
- Real idle/working/empty/error/protocol-playing UI captures. Local pause is asserted absent before explicit confirmation.
- Screenshots at 360px without horizontal overflow; mobile landing at 390px in both schemes, desktop at 1440px.
- Runtime errors, console errors, broken images and HTTP(S) page resource requests fail the run. Chrome component background activity is outside the page-network assertion.
- Copy buttons are checked with injected clipboard success and denial boundaries; denial selects the exact command and tells the user how to copy it. It does not silently claim clipboard success.
- Extension registration is removed from the owned test profile, then Chrome is closed and only its freshly created profile directory is deleted.

Additional checks:

```sh
node --test tests/extension
node --test tests/brand.test.mjs
python3.11 -m unittest discover -s tests -p 'test_helper*.py' -q
python3.11 scripts/verify-brand-assets.py
```

The last command uses the already-installed Pillow module (12.3.0 here). It measures alpha and palette contrast, validates citation ranges, checks the unchanged manifest against the pre-refresh commit, and audits marketing source for private paths/IPs and remote load references. It is an offline artifact check, not a live-TV test.

The render evidence JSON lists resource references and tested controls. `docs/refresh-report.md` records real command outputs, the repeat-render comparison, privacy boundaries and the publishing handoff. Repeated generation is byte-stable with the same browser, fonts, operating system and rasterizer; cross-platform font rasterization is not promised to be byte-identical.
