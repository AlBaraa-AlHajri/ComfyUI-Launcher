# Verification record — 2026-10-12

Verified on Windows x64 with Python 3.11.9. Tests use isolated data directories and do
not overwrite the user's production configuration.

| Check | Result |
|---|---|
| Ruff lint and formatting | Passed |
| pytest | 58 cases, including real hidden process trees and Tk/tray dispatch |
| `scripts/build.bat` | Windowed PyInstaller onedir build completed |
| Packaged `--self-test` | Passed: installation, browser discovery, icons and bootstrap |
| Original ICO | All nine sizes verified; actual 16px and 32px previews inspected |
| Packaged GUI | Arabic splash, original logo, Ready status, elapsed counter and progress inspected |
| Settings | Arabic controls, paths, scrolling, on-screen Save/Cancel and English language change checked |
| Chrome | ComfyUI opened as an app window without browser tab/address bars |
| Duplicate packaged invocation | Second process exited with code 0; one launcher/server remained |
| Tray controls | Open, Stop, Restart and Exit exercised through actual pystray callbacks |
| Packaged Exit | Owned interpreter tree exited and the test server port was released |
| Real ComfyUI core | CPU and `--lowvram` startup/readiness/shutdown passed on isolated ports |
| External server ownership | Attachment opens the existing server; Stop does not terminate it |
| Unicode and spaces | Configuration, process arguments, paths and UTF-8 logs verified |
| Failure paths | Early exit, timeout, unrelated HTTP service, blocked port, cancellation and forced cleanup |

The real-installation core checks used `--disable-all-custom-nodes` to separate core
startup from ComfyUI-Manager's attempt to install missing dependencies. A run with
custom nodes enabled reached the Manager dependency-installation step and timed out;
that full custom-node startup is therefore **not claimed as verified**. No image
generation or model-quality test was performed. The normal launcher default remains
`--lowvram`, with custom nodes enabled.

Manual GUI inspection identified and fixed dialog placement and an elapsed-label
translation issue. Real ComfyUI verification identified and fixed a Windows CRT
stdin/DLL-loading deadlock; a regression test covers that lock interaction. Reserved
Windows port ranges and timed process cleanup are covered separately.

CI and release run results are available in the repository's GitHub Actions tab.
Releases remain unsigned; no claim of antivirus certification is made.
