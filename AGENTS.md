# ComfyUI Launcher

An unofficial Windows desktop launcher for an existing ComfyUI installation.
Keep this repository independent of ComfyUI and its Python environment.

## Layout

- `src/comfy_launcher`: UI, configuration, browser, process management and Windows APIs.
- `assets`: original workflow/play artwork and generated icons.
- `tools`: reproducible artwork and packaging helpers.
- `scripts`: Windows build, source launch and shortcut creation.
- `tests`: unit and real child-process lifecycle tests.

## Conventions

Use Python 3.11, type hints and docstrings. Explain non-trivial blocks with paired
English and Arabic comments. Use UTF-8, pathlib and argument lists without a shell.
Never store personal paths, credentials, machine logs or generated config in Git.
Keep Tk operations on the UI thread; send worker results through a queue.
Never stop a server the launcher did not create. Use Windows Job Objects for children.
Do not change ComfyUI, its packages, drivers or models while developing this launcher.

## Commands

- Run: `scripts\run_from_source.bat`
- Build: `scripts\build.bat`
- Test: `.build-venv\Scripts\python.exe -m pytest`
- Lint: `.build-venv\Scripts\python.exe -m ruff check .`
- Format: `.build-venv\Scripts\python.exe -m ruff format .`
- Packaged diagnostic: `dist\ComfyUI-Launcher\ComfyUI-Launcher.exe --self-test`

Validate icons, settings, startup, duplicate invocation and process shutdown before
publishing. Document significant tradeoffs in DECISIONS.md.
