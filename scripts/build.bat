@echo off
setlocal
cd /d "%~dp0.."
if exist ".build-venv\Scripts\python.exe" goto install
where py >nul 2>nul
if not errorlevel 1 (
    py -3.11 -m venv .build-venv
) else (
    python -m venv .build-venv
)
if errorlevel 1 goto fail
:install
".build-venv\Scripts\python.exe" -c "import sys; assert sys.version_info[:2] == (3, 11), 'Build requires Python 3.11'"
if errorlevel 1 goto fail
".build-venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 goto fail
".build-venv\Scripts\python.exe" tools\make_icon.py
if errorlevel 1 goto fail
".build-venv\Scripts\python.exe" -m ruff check .
if errorlevel 1 goto fail
".build-venv\Scripts\python.exe" -m pytest
if errorlevel 1 goto fail
".build-venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean launcher.spec
if errorlevel 1 goto fail
echo Built dist\ComfyUI-Launcher\ComfyUI-Launcher.exe
exit /b 0
:fail
echo Build failed. Review the error above.
exit /b 1
