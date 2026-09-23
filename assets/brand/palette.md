# PearPlay palette

Warm neutral surfaces, forest ink and pear-lime. No gradients or glossy tiles.

| Use | Foreground | Background | WCAG sRGB contrast |
|---|---|---|---|
| Light body | `#19271d` | `#f6f7f2` | 14.46:1 |
| Light surface | `#19271d` | `#ffffff` | 15.56:1 |
| Light muted | `#52604f` | `#f6f7f2` | 6.20:1 |
| Light surface muted | `#52604f` | `#ffffff` | 6.68:1 |
| Light primary | `#ffffff` | `#355b29` | 7.84:1 |
| Light border | `#76816c` | `#ffffff` | 4.10:1 |
| Dark body | `#f4f7ed` | `#111914` | 16.52:1 |
| Dark surface | `#f4f7ed` | `#1a251d` | 14.61:1 |
| Dark muted | `#bac7b2` | `#111914` | 10.15:1 |
| Dark surface muted | `#bac7b2` | `#1a251d` | 8.97:1 |
| Dark primary | `#172310` | `#c1e67a` | 11.58:1 |
| Dark border | `#819277` | `#1a251d` | 4.76:1 |
| Mark play | `#253c23` | `#c1e67a` | 8.50:1 |

Ratios computed with WCAG relative sRGB luminance: linearize each channel at 0.04045, weight 0.2126/0.7152/0.0722, then (lighter + 0.05)/(darker + 0.05). Text pairs exceed 4.5:1; borders are non-text and exceed 3:1 against their surface. Do not fade secondary text with opacity. Disabled controls remain readable, and state is described in words, not only color.

Light: background `#f6f7f2`, surface `#ffffff`, ink `#19271d`, secondary ink `#52604f`, primary `#355b29` with white text, border `#76816c`.
Dark: background `#111914`, surface `#1a251d`, ink `#f4f7ed`, secondary ink `#bac7b2`, primary `#c1e67a` with `#172310` text, border `#819277`.

The mark uses pear `#c1e67a`, outline/play `#253c23` and leaf `#355b29`. The dark outline defines it on light toolbars; the pear fill and leaf rim define it on dark ones. Preserve transparent corners and large solid areas. Native antialiasing is retained only on shape edges; there is no semi-transparent fill. SVG masters contain no raster content, scripts or remote fonts. `wordmark.svg` is intended for light surfaces; use the icon plus live light text on dark surfaces.

Typography: system-ui sans for the popup, chosen for familiar form controls and platform hinting at small sizes. Landing headlines use the same native family with tighter spacing; body text is restrained. Text remains HTML on the landing page, not baked into hero artwork. Editable social/store export sources use the installed system stack.
