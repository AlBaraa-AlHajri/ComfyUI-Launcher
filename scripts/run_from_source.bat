@echo off
setlocal
cd /d "%~dp0.."
if not exist ".build-venv\Scripts\pythonw.exe" (
    echo Run scripts\build.bat once to prepare Python 3.11 and dependencies.
    exit /b 1
)
set "PYTHONPATH=%CD%\src"
start "" ".build-venv\Scripts\pythonw.exe" -m comfy_launcher %*
exit /b 0
