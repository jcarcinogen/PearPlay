#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Existing tools only. CHROME, RSVG_CONVERT and PYTHON may select installed binaries.
node scripts/render-brand-assets.mjs "$@"
