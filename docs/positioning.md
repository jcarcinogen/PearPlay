# PearPlay positioning

PearPlay sends a compatible website stream directly to an Apple TV without mirroring or re-encoding. It is an open-source Chrome extension plus an explicitly installed local helper, not a cloud media relay. No PearPlay account.

The audience is a desktop Chrome user on Linux, Mac or Windows. Mac and Windows helpers remain unsigned experimental software; Windows policy may block installation. Browser controls work before casting. TV pause/resume requires helper 0.3.1 or newer and a supported authenticated Apple TV session. Read-only TV progress requires helper 0.3.3. TV seeking, jumps and volume are unavailable. Safari development is paused.

Only receiver-fetchable HTTP(S) media can be sent. Browser cookies, DRM, geography and access restrictions are not bypassed. PearPlay does not block ads or promise every site/receiver works. LG HLS remains unresolved.

Use the actual 400×600 popup with safe example data for artwork. Preserve clear labels, keyboard focus, original colored branding and per-action permission/PIN recovery. Do not imply synthetic screenshots are live playback evidence.

PearPlay 0.3.3 retains the active TV session across popup reopening and tab switching, remembers a preferred TV by rediscovered identity, and provides deliberate original-source-only browser mute. The Web Store updates only the extension; update the separate helper to 0.3.3 for read-only TV progress, keeping saved pairing.
