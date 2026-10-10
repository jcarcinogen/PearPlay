# Mac installation image provenance

The Apple images below were retrieved over HTTPS from the URLs embedded in [Apple Support article 102445](https://support.apple.com/en-us/102445). They are Apple’s macOS Sequoia **example** screenshots—not captures of PearPlay, not proof of installation acceptance, and not original PearPlay artwork. © Apple; shown for instructional context. The original Apple files are retained unchanged. `apple-unverified-annotated.png` is a derivative with a red outline added around Done for clarity; the example app name and warning text are unchanged. `apple-open-anyway-annotated.png` is a derivative with a red arrow and rectangle added around Open Anyway. The original Apple screenshot has no red annotation.

| Local file | Pixels | SHA256 | Original |
|---|---|---|---|
| `apple-unverified.png` | 520×464 | `8f6c4c672bba2c770aec3736ee2b0389563a6978386f95c636ad43f1457e3c6b` | [Apple PNG](https://cdsassets.apple.com/live/7WUAS350/images/macos/sequoia/macos-sequoia-app-not-opened-could-not-verify-free-from-malware.png) |
| `apple-open-anyway.png` | 1430×1226 | `3048b460a1e0d94325c17d91e80c196b95c267c3df7b7b1257900f3304061edb` | [Apple PNG](https://cdsassets.apple.com/live/7WUAS350/images/macos/sequoia/macos-sequoia-system-settings-privacy-and-security-open-app-anyway.png) |

`pearplay-setup.png` is a real screenshot of the unmodified candidate setup document in an isolated official Chrome profile, with no fixture API responses and no installed helper. Its capture script and machine-readable evidence are in the candidate kit’s `Mac/Guide/`. It is a UI capture, not native installation or receiver acceptance.

Current macOS guidance was also checked against [Apple’s unknown-developer user guide](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unknown-developer-mh40616/mac). Its UI sequence can include an extra Open control, and it describes the roughly one-hour availability of Open Anyway. The installation guide acknowledges those version differences.
