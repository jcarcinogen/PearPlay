#!/bin/bash
# Downloaded source-runtime installer; review before running. No sudo is used.
set -euo pipefail
# Keep legacy removal, but do not revive the fragile source/Python identity.
if [[ "${1:-install}" != remove ]]; then
  printf '%s\n' 'Use the packaged PearPlay Setup.app Mac preview, not this historical source-runtime installer. Unsigned previews are for local testing only; consumer releases require Apple signing and notarization.' >&2
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
printf '%s\n' 'PearPlay will disconnect its owned shared Chrome/Brave registration. Existing runtime and saved TV pairing will be preserved.'
exec "$UV" run --no-project --no-config --python 3.11 "$HERE/scripts/macos_setup.py" --uv "$UV" "$@"
