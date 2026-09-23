#!/usr/bin/env python3
"""Offline checks for delivered brand assets; uses the already-installed Pillow."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from PIL import Image

root = Path(__file__).resolve().parents[1]
report = {"icons": [], "contrast": [], "claims_references": 0, "privacy_findings": []}
for size in (16, 32, 48, 128, 1024):
    name = "icon.png" if size == 1024 else f"icon{size}.png"
    with Image.open(root / "extension/icons" / name) as image:
        assert image.size == (size, size)
        rgba = image.convert("RGBA")
        alpha_band = rgba.getchannel("A")
        alpha = [alpha_band.getpixel(p) for p in ((0, 0), (size-1, 0), (0, size-1), (size-1, size-1))]
        assert alpha == [0, 0, 0, 0], (name, alpha)
        assert rgba.getchannel("A").getextrema() == (0, 255)
        report["icons"].append({"file": name, "size": size, "corner_alpha": alpha})

def luminance(color):
    rgb = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    linear = [n/12.92 if n <= .04045 else ((n+.055)/1.055)**2.4 for n in rgb]
    return sum(n*w for n, w in zip(linear, (.2126, .7152, .0722)))

palette = (root / "assets/brand/palette.md").read_text()
for label, fg, bg, declared in re.findall(r"\| ([^|]+) \| `(#\w{6})` \| `(#\w{6})` \| ([\d.]+):1 \|", palette):
    low, high = sorted((luminance(fg), luminance(bg)))
    ratio = (high+.05)/(low+.05)
    assert abs(ratio-float(declared)) < .011, label
    assert ratio >= (3 if "border" in label else 4.5), (label, ratio)
    report["contrast"].append({"pair": label, "ratio": round(ratio, 3)})
assert len(report["contrast"]) >= 10

claims = (root / "docs/claims.md").read_text()
for name, span in re.findall(r"`([\w./-]+\.(?:md|mjs|js|html|py|json)):(\d[\d,–-]*)`", claims):
    path = root/name
    assert path.is_file(), name
    lines = len(path.read_text().splitlines())
    assert all(1 <= int(n) <= lines for n in re.findall(r"\d+", span)), (name, span, lines)
    report["claims_references"] += 1

manifest = (root / "extension/manifest.json").read_bytes()
baseline = subprocess.check_output(["git", "show", "6ce73e1:extension/manifest.json"], cwd=root)
current, original = json.loads(manifest), json.loads(baseline)
assert current["version"] == "0.2.0"
original["version"] = current["version"]
assert current == original, "Manifest identity or permissions changed"
report["manifest_sha256"] = hashlib.sha256(manifest).hexdigest()

for path in [root/"README.md", *root.glob("docs/*"), *root.glob("assets/**/*.html"), *root.glob("assets/**/*.svg")]:
    if path.suffix not in (".md", ".html", ".svg"):
        continue
    text = path.read_text()
    # Public repo/tip handles are deliberate links. Never accept private local paths or LAN IPs.
    if re.search(r"(?:/Users/|/home/)[A-Za-z0-9_-]+/|\b192\.168\.\d+\.\d+\b|\b10\.\d+\.\d+\.\d+\b", text):
        report["privacy_findings"].append(str(path.relative_to(root)))
assert not report["privacy_findings"], report["privacy_findings"]

site = (root / "docs/index.html").read_text()
assert not re.search(r'(?:src|srcset)=["\'](?:https?:)?//|@import|url\(["\']?https?://', site)
assert not re.search(r'<script[^>]+src=|<link[^>]+rel=["\']stylesheet', site)
assert "{{" not in site
assert (root / "docs/.nojekyll").is_file()
report["social_preview_bytes"] = (root/"assets/landing/social-preview.png").stat().st_size
assert report["social_preview_bytes"] < 1_000_000
report["site_remote_load_refs"] = []
print(json.dumps(report, indent=2))
