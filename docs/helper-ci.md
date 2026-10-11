# Hosted helper builds

`.github/workflows/helpers.yml` runs native builds on standard GitHub-hosted
Windows x64, macOS Apple Silicon and Ubuntu 22.04 x64 runners. It runs on relevant
pull requests and manual dispatch (once available on the default branch).

Outputs: unsigned Windows setup/maintenance EXEs, unsigned experimental Mac PKG,
and Linux DEB/Arch packages. RPM is not required or claimed by this workflow.

The workflow reuses existing builders, tests native behavior, checks source and
package hashes, and uploads candidates only when all gates for that platform pass.
Each candidate contains SHA256SUMS, source/build metadata, test logs and CI
provenance. Logs survive failures. Dependencies are installed in disposable hosted
venvs: pyatv 0.18.0, PyInstaller 6.21.0 and pytest 9.0.2. Resolved transitive versions
are recorded; bit-for-bit reproducibility is not claimed. Actions are SHA-pinned,
checkout credentials are not persisted and the token only reads repository content.

These are engineering artifacts, not automatically published releases. No signing
account, GitHub release, website update or Store submission is configured. A green
build is not owner-visible GUI installation, Chrome connection, TV playback or
Smart App Control acceptance. Existing Windows launch/branding blockers remain.
Mac deliberately remains unsigned/not notarized; normal first-run approval and
installation acceptance are separate. SignPath integration is a future step after
eligibility approval, not a property of this workflow.

To run after the workflow reaches main: Actions → Helper builds → Run workflow.
For review branches, open/update a PR. Download the corresponding platform artifact
from the run page and verify SHA256SUMS before considering release promotion.
Review and publication are manual. GitHub artifact retention is 14 days for
candidates and 7 days for diagnostic-only bundles; retain accepted evidence elsewhere.
