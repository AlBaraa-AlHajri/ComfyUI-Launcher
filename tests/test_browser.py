"""Browser fallback and registry precedence without opening user windows."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from comfy_launcher import browser
from comfy_launcher.config import Config


def test_registry_hkcu_precedes_hklm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    executable = tmp_path / "Chrome مثال.exe"
    executable.touch()
    registry = MagicMock()
    registry.HKEY_CURRENT_USER, registry.HKEY_LOCAL_MACHINE = 1, 2
    registry.KEY_READ, registry.KEY_WOW64_64KEY, registry.KEY_WOW64_32KEY = 4, 8, 16
    registry.QueryValueEx.return_value = (f'"{executable}"', 1)
    monkeypatch.setattr(browser, "winreg", registry)
    assert browser.detect_browser("chrome") == executable
    assert registry.OpenKey.call_args.args[0] == registry.HKEY_CURRENT_USER
    assert registry.OpenKey.call_count == 1


def test_common_path_after_registry_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = MagicMock()
    registry.OpenKey.side_effect = OSError("missing")
    monkeypatch.setattr(browser, "winreg", registry)
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    executable = tmp_path / "Microsoft/Edge/Application/msedge.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    assert browser.detect_browser("edge") == executable


def test_chrome_falls_back_to_edge(config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser, "focus_app", lambda _: False)
    monkeypatch.setattr(
        browser, "detect_browser", lambda name: Path("edge.exe") if name == "edge" else None
    )
    spawn = MagicMock()
    monkeypatch.setattr(browser.subprocess, "Popen", spawn)
    assert browser.open_browser(config) == "edge"
    command = spawn.call_args.args[0]
    assert f"--app={config.url}" in command
    assert "--window-size=1600,950" in command
    assert spawn.call_args.kwargs.get("shell", False) is False


def test_default_fallback(config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser, "focus_app", lambda _: False)
    monkeypatch.setattr(browser, "detect_browser", lambda _: None)
    opened = MagicMock(return_value=True)
    monkeypatch.setattr(browser.webbrowser, "open", opened)
    assert browser.open_browser(config) == "default"
    opened.assert_called_once_with(config.url, new=2)


def test_existing_window_is_focused(config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser, "focus_app", lambda _: True)
    spawn = MagicMock()
    monkeypatch.setattr(browser.subprocess, "Popen", spawn)
    assert browser.open_browser(config) == "focused"
    spawn.assert_not_called()


def test_default_failure_is_actionable(config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    config.browser = "default"
    monkeypatch.setattr(browser.webbrowser, "open", lambda *_, **kwargs: False)
    with pytest.raises(OSError, match="browser"):
        browser.open_browser(config)
