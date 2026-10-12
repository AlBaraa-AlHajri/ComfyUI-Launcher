<p align="center"><img src="assets/icon_256.png" width="112" alt="Original workflow and play icon"></p>

# ComfyUI Launcher

Your workflows. One click. An unofficial Windows launcher for an **existing ComfyUI
installation**, with an Arabic/English interface and a quiet system-tray workflow.

[Download the latest Windows release](https://github.com/AlBaraa-AlHajri/ComfyUI-Launcher/releases/latest)
· [العربية](README.ar.md) · [Design decisions](DECISIONS.md)

![ComfyUI Launcher](assets/social_preview.png)

<p align="center"><img src="assets/screenshot-ar.jpg" width="400" alt="Verified Arabic launcher showing Ready"></p>

## What it does

- A small dark splash shows live startup status, progress and elapsed time.
- Starts your venv or official portable interpreter directly, with no console window.
- Waits for `/system_stats`, then opens Chrome as a 1600×950 app window.
- Falls back to Edge, then the Windows default browser.
- Reuses an existing ComfyUI server; duplicate launches focus the current app window.
- Tray controls: Open, Restart, Stop, logs, installation/output folders, Settings, About, Exit.
- Cooperative shutdown, timed process-tree cleanup and Windows Job Object containment.
- UTF-8 logs and configuration; supports Arabic and spaces in installation paths.
- Original, programmatically generated artwork; no Comfy Org logo is included.

## Requirements

Windows 10/11 x64 and an existing, working ComfyUI installation with a venv or portable
Python environment. Chrome is preferred; Edge/default browser can be used instead.
The downloadable launcher includes its own runtime. **It does not bundle ComfyUI,
models, GPU drivers or PyTorch, and it does not modify your ComfyUI environment.**

## Download and first run

1. Download `ComfyUI-Launcher-v1.0.0-win64.zip` and `SHA256SUMS.txt` from
   [Releases](https://github.com/AlBaraa-AlHajri/ComfyUI-Launcher/releases).
2. Extract the complete folder to a permanent location. Keep `_internal` beside the EXE.
3. Double-click `ComfyUI-Launcher.exe`. Common venv and portable locations are detected.
   If no installation is found, use Browse to select the folder containing `main.py`
   and its environment's `python.exe`, then Save.
4. The default is Arabic, port 8188, `--lowvram`, a 180-second timeout and Chrome app mode.
   After Ready, the splash hides to the tray. Right-click its icon for controls.
5. Optionally run the included `Create-Shortcut.ps1` with PowerShell to create Desktop
   and Start Menu shortcuts. For a source checkout, use `scripts/create_shortcut.ps1`.

To verify a ZIP's hash in PowerShell, compare the output to `SHA256SUMS.txt`:

```powershell
Get-FileHash -Algorithm SHA256 .\ComfyUI-Launcher-v1.0.0-win64.zip
```

If ComfyUI was already running, the launcher attaches without taking ownership. Stop
and Restart show an explanation; manage that server through its original terminal.
Once that server is stopped, exit and reopen the launcher to let it own the next start.

## Settings and arguments

Open Settings from the tray or launch `ComfyUI-Launcher.exe --settings`. Choose paths,
port, language, browser, app mode, browser auto-opening, timeout and tray behavior.
Common flags have checkboxes. Select only one memory mode. Advanced arguments use
Windows quoting, for example:

```text
--output-directory "E:\My Outputs\صور" --preview-method auto
```

The launcher controls `--port` and `--disable-auto-launch`; old `--auto-launch` and port
arguments in the advanced list are overridden. `--listen` exposes the server on the
network; explicit addresses must include `127.0.0.1` or `0.0.0.0` so the local readiness
probe can connect. Settings are validated before saving. Language applies immediately;
other changes apply at the next start or Restart.

Configuration: `%APPDATA%\ComfyUI-Launcher\config.json`. Supported keys are `comfy_dir`,
`python_exe`, `extra_args`, `port`, `browser`, `app_mode`, `startup_timeout`,
`open_browser_on_start`, `minimize_to_tray`, `language` and `schema_version`.
Browser app profiles and rotating UTF-8 logs are stored under the same directory.
Chrome app mode uses a separate profile; your regular Chrome cookies/extensions are
not automatically shared.

## Build and test from source

Install Git and Python **3.11 x64**, then:

```powershell
git clone https://github.com/AlBaraa-AlHajri/ComfyUI-Launcher.git
cd ComfyUI-Launcher
.\scripts\build.bat
.\scripts\run_from_source.bat
```

The build script creates `.build-venv`, installs pinned dependencies, generates icons,
runs Ruff and pytest, then builds `dist/ComfyUI-Launcher/ComfyUI-Launcher.exe` with
PyInstaller. If the Python Launcher (`py`) is absent, `python` must resolve to 3.11.

```powershell
.\.build-venv\Scripts\python.exe -m ruff check .
.\.build-venv\Scripts\python.exe -m pytest -q
$test = Start-Process .\dist\ComfyUI-Launcher\ComfyUI-Launcher.exe -ArgumentList '--self-test' -WindowStyle Hidden -Wait -PassThru
$test.ExitCode
Get-Content "$env:APPDATA\ComfyUI-Launcher\self-test.json"
.\scripts\create_shortcut.ps1
```

`--self-test` checks saved/discovered configuration, browser detection, icon sizes and
bundled bootstrap presence, without starting a server or opening a browser. On a clean
machine it reports that first-run setup is required while still verifying the package.
Use `--self-test-report "path with spaces\report.json"` to choose a report destination.
For isolated testing set `COMFY_LAUNCHER_HOME` to a temporary directory.

## Troubleshooting

| Symptom | What to check |
|---|---|
| SmartScreen says “Unknown publisher” | The community build is unsigned. Verify the release source and hash. If you trust this download, More info → Run anyway is Windows' available option. |
| Antivirus flags the package | Scan it, inspect the source or build locally. Report a false positive to the vendor; do not disable protection globally. |
| Port in use | A recognized ComfyUI server is reused. For another service, accept the offered free port or choose one in Settings. |
| Chrome not found | Edge app mode is tried next, then your default browser. Set a browser explicitly in Settings. |
| Startup fails or times out | Use Copy error/Open log/Retry. Check `main.py`, the selected interpreter, custom nodes and ComfyUI dependencies. Increase the timeout for a slow startup. |
| CUDA/PyTorch/triton warning | These are ComfyUI environment messages. The launcher captures them; it does not install or upgrade GPU packages. |
| Stop/Restart will not stop an existing server | That server was started elsewhere and is deliberately not owned by the launcher. |
| No tray icon visible | Check Windows' hidden-icons overflow. If tray creation fails, the management window remains visible. |
| Browser opens but a saved new port is not used | The running server keeps its original URL. Restart applies saved server preferences. |
| Corrupt config | The settings editor lets you replace it; the original is preserved as `config.invalid-*.json`. |

Logs live in `%APPDATA%\ComfyUI-Launcher\logs`: `launcher.log` and
`comfyui_YYYY-MM-DD.log`. Keep private paths and prompt/output contents out of public
bug reports; the Copy error action copies only when you press it.

## Publishing and artwork

CI runs Windows lint and tests on pushes and pull requests. A `v*.*.*` tag runs tests,
builds the executable, performs its self-test, and publishes the ZIP plus SHA-256 file
using GitHub Actions. See [PUBLISHING.md](PUBLISHING.md) for exact commands.

To set the repository's social preview, open GitHub Settings → General → Social preview
and upload `assets/social_preview.png`. Edit `assets/icon.svg`, then run
`python tools/make_icon.py` to regenerate every raster/ICO asset. Small-size previews are
included at `assets/preview_16.png`, `assets/preview_32.png` and `assets/small_size_preview.png`.

This is an **unofficial community project, not affiliated with Comfy Org**. ComfyUI
belongs to its respective authors. Launcher code and original artwork use the [MIT License](LICENSE).
