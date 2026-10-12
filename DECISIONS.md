# Design decisions

1. **The second specification takes precedence.** The attached lime C is a reference,
   not a shipped asset. This project uses an original two-input workflow graph feeding
   a play node. `assets/icon.svg` is the hand-written source of truth. Pillow reads its
   geometry and renders at 4096 pixels before downsampling to 1024 and smaller sizes.

2. **ComfyUI stays independent.** The launcher never installs, updates or changes
   ComfyUI, models, CUDA, PyTorch or its environment. A compatible existing installation
   is required. The console screenshot contains environment warnings; changing those
   packages is outside this launcher's scope.

3. **Configuration is per-user.** Settings, logs and a browser app profile live under
   `%APPDATA%\ComfyUI-Launcher`. Personal paths occur only in generated local config;
   the explicitly requested common drive paths occur only in first-run discovery.
   `COMFY_LAUNCHER_HOME` overrides storage for tests and isolated diagnostics.

4. **Graceful Windows shutdown needs a bootstrap.** On Windows, psutil's `terminate()`
   uses TerminateProcess and is not cooperative. A process created with
   `CREATE_NO_WINDOW` cannot receive ordinary console control events. We therefore call
   the configured environment's `python.exe` directly with a small standard-library
   `worker.py`. It sets `sys.argv` and `sys.path`, then executes the unchanged ComfyUI
   `main.py` through `runpy`. The private stdin pipe requests a main-thread
   `KeyboardInterrupt`; this allows ComfyUI's normal shutdown handling. After ten
   seconds, psutil terminates remaining descendants, waits two seconds, then kills
   survivors. A kill-on-close Windows Job Object prevents orphans even if the launcher
   crashes. The child waits for successful Job Object assignment before running any
   ComfyUI code. Extensions stuck in native code may require forced termination.
   See [psutil's Windows behavior](https://psutil.readthedocs.io/en/stable/#psutil.Process.terminate).
   The control listener polls `PeekNamedPipe` before reading: holding a blocking CRT
   stdin read during NumPy/PyTorch DLL initialization caused a real Windows startup
   deadlock in verification. Python helpers launched by custom nodes inherit a local
   `Popen` wrapper that adds `CREATE_NO_WINDOW`. The selected interpreter's directory
   is prepended to PATH so custom nodes can resolve their environment tools.

5. **Externally started servers remain externally owned.** A valid `/system_stats`
   response is reused. Stop and Restart explain that the existing terminal owns the
   server; Exit closes only this launcher. This preserves sessions that were already
   running. The first instance stays in the tray so settings and shortcuts remain
   available. Duplicate launcher invocations signal the first via a named event and
   exit. Repeated opens focus the existing browser app window where Windows permits.

6. **App windows have a dedicated per-port browser profile.** This avoids altering the
   user's normal tabs and allows reliable process-to-window association. Chrome and
   Edge logins, extensions and cookies from the normal profile are not inherited.
   App mode and automatic browser opening can each be disabled. Default-browser mode
   delegates tab reuse to the chosen browser.

7. **Discovery is bounded.** We inspect common paths, nearby directories and folders
   whose names contain `comfy` at local fixed-drive roots, to a depth of two. We avoid
   recursive scans of every file and avoid slow/offline network drives. Other locations
   are selected through the first-run settings wizard's folder picker.

8. **Health checks identify ComfyUI.** A 200 response alone is insufficient: the response
   must have a `system` object containing `os` and `python_version`, plus a `devices`
   list. HTTP redirects, proxy settings and oversized responses are rejected. Explicit
   `--listen` addresses must retain IPv4 loopback access. Port availability is checked
   before spawning; a competing bind after the check is reported as startup failure.

9. **Preferences apply predictably.** Arabic is the default; English is selectable.
   Labels align right in Arabic, while file paths and command-line flags remain LTR.
   Native Segoe UI/Tk shaping is used; technical exception details and server logs retain
   their original language. `minimize_to_tray` from the first request and
   `open_browser_on_start` from the second are both supported. Language changes apply
   immediately; server and browser settings apply at the next start/restart. The active
   URL remains unchanged when the saved port is edited.

10. **Releases are unsigned onedir bundles.** Keep the EXE and `_internal` together.
    PyInstaller embeds product/version resources, the original ICO, Tk assets and the
    standalone bootstrap. UPX is disabled. Signing requires a publisher certificate and
    is not fabricated. SHA-256 verifies download integrity, not publisher identity.
    [PyInstaller packaging reference](https://pyinstaller.org/en/stable/spec-files.html).

11. **Logs have bounded retention.** Launcher logs rotate at 2 MB and keep ten files
    including the active file. ComfyUI output rotates at 5 MB into dated files; at
    startup and reader completion, history is pruned to the newest ten server files.
    Config writes are atomic, with a previous valid backup or a preserved corrupt file.

12. **Testing avoids the user's GPU workload.** Automated lifecycle tests use real
    hidden child processes serving the ComfyUI response shape, including cooperative,
    hung and descendant-producing processes. A separate real-installation check uses
    CPU mode on a different port. Existing ComfyUI sessions are not stopped by tests.
   Custom nodes may perform their own startup work, including installing missing
   dependencies. The core-isolation diagnostic uses `--disable-all-custom-nodes` to
   distinguish launcher readiness from a custom node waiting on network installation.
