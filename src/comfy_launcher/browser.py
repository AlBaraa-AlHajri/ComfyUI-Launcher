"""Browser discovery, isolated app windows and repeat-launch focus."""

import ctypes
import logging
import os
import subprocess
import webbrowser
from ctypes import wintypes as wt
from pathlib import Path

import psutil

from .config import Config
from .paths import app_data

try:
    import winreg
except ImportError:
    winreg = None

LOG = logging.getLogger(__name__)


def detect_browser(name: str) -> Path | None:
    """Prefer HKCU, then HKLM App Paths in both registry views, then standard locations."""
    executable = "chrome.exe" if name == "chrome" else "msedge.exe"
    relative = (
        "Google/Chrome/Application/chrome.exe"
        if name == "chrome"
        else "Microsoft/Edge/Application/msedge.exe"
    )
    if winreg is not None:
        # Respect per-user installs before machine-wide browser registrations.
        # تقديم تثبيت المستخدم على تسجيل المتصفح العام للجهاز.
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    key_name = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\"
                    with winreg.OpenKey(
                        hive, key_name + executable, 0, winreg.KEY_READ | view
                    ) as key:
                        value, _ = winreg.QueryValueEx(key, None)
                    path = Path(os.path.expandvars(value.strip('"')))
                    if path.is_file():
                        return path
                except (OSError, TypeError, AttributeError):
                    continue
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        if base:
            path = Path(base) / relative
            if path.is_file():
                return path
    return None


def browser_command(executable: Path, config: Config) -> list[str]:
    """Build an isolated per-port app profile so repeated opens can focus the same window."""
    if not config.app_mode:
        return [str(executable), "--new-window", config.url]
    profile = app_data() / "browser-profiles" / str(config.port)
    return [
        str(executable),
        f"--app={config.url}",
        "--new-window",
        "--window-size=1600,950",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
    ]


def focus_app(config: Config) -> bool:
    """Restore a visible window belonging only to this launcher's per-port browser profile."""
    if os.name != "nt" or not config.app_mode:
        return False
    profile_flag = (
        f"--user-data-dir={app_data() / 'browser-profiles' / str(config.port)}".casefold()
    )
    pids: set[int] = set()
    for process in psutil.process_iter(["name", "cmdline", "pid"]):
        # Match only this profile; never focus unrelated user tabs.
        # مطابقة ملف التطبيق فقط دون التركيز على نوافذ المستخدم الأخرى.
        try:
            if process.info["name"].casefold() not in ("chrome.exe", "msedge.exe"):
                continue
            if profile_flag in [arg.casefold() for arg in process.info["cmdline"] or []]:
                pids.add(process.pid)
                pids.update(child.pid for child in process.children(recursive=True))
        except (psutil.Error, AttributeError):
            continue
    if not pids:
        return False
    user = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    signatures = {
        "EnumWindows": ([callback_type, wt.LPARAM], wt.BOOL),
        "IsWindowVisible": ([wt.HWND], wt.BOOL),
        "GetWindowThreadProcessId": ([wt.HWND, ctypes.POINTER(wt.DWORD)], wt.DWORD),
        "ShowWindow": ([wt.HWND, ctypes.c_int], wt.BOOL),
        "SetForegroundWindow": ([wt.HWND], wt.BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(user, name)
        function.argtypes, function.restype = args, result
    found: list[int] = []

    @callback_type
    def visit(hwnd: int, _: int) -> bool:
        pid = wt.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user.IsWindowVisible(hwnd):
            found.append(hwnd)
            return False
        return True

    user.EnumWindows(visit, 0)
    if found:
        user.ShowWindow(found[0], 9)
        user.SetForegroundWindow(found[0])
        return True
    return False


def open_browser(config: Config) -> str:
    """Focus an existing app, or try the preferred browser and available fallbacks."""
    if config.browser != "default":
        if focus_app(config):
            return "focused"
        order = ["chrome", "edge"] if config.browser == "chrome" else ["edge", "chrome"]
        for name in order:
            executable = detect_browser(name)
            if executable:
                try:
                    subprocess.Popen(
                        browser_command(executable, config),
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    LOG.info("Opened %s on port %s", name, config.port)
                    return name
                except OSError:
                    LOG.exception("Cannot start %s; trying fallback", name)
    if not webbrowser.open(config.url, new=2):
        raise OSError(
            "No browser could be opened. Install Chrome or Edge, or set a default browser."
        )
    return "default"
