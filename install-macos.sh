#!/bin/bash
# Downloaded source-runtime installer; review before running. No sudo is used.
set -euo pipefail
# New Mac installs are paused; preserve safe removal for existing testers.
if [[ "${1:-install}" != remove ]]; then
  printf '%s\n' 'PearPlay is Linux only. Mac support is coming soon.' >&2
  exit 2
fi
if [[ "$(uname -s)" != Darwin || "$(id -u)" == 0 ]]; then
  printf '%s\n' 'Run this in your normal Mac account, without sudo.' >&2
  exit 2
fi
HERE="$(cd -- "$(dirname -- "$0")" && pwd -P)"
UV="$(command -v uv || true)"
if [[ -z "$UV" && -x "$HOME/.local/bin/uv" ]]; then UV="$HOME/.local/bin/uv"; fi
if [[ -z "$UV" ]]; then
  printf '%s\n' 'Install uv using https://docs.astral.sh/uv/getting-started/installation/ and run this command again.' >&2
  exit 1
fi
printf '%s\n' 'PearPlay will disconnect its owned Chrome registration. Existing runtime and saved TV pairing will be preserved.'
exec "$UV" run --no-project --no-config --python 3.11 "$HERE/scripts/macos_setup.py" --uv "$UV" "$@"
