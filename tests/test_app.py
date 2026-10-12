"""Exercise real Tk/pystray dispatch and process ownership through the complete coordinator."""

import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from comfy_launcher.config import Config, save_config


@pytest.mark.skipif(os.name != "nt", reason="Windows UI and tray lifecycle")
def test_tray_start_stop_restart_exit(config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    """Invoke actual tray menu items and verify readiness and cleanup between transitions."""
    from comfy_launcher.app import App
    from comfy_launcher.single_instance import SingleInstance

    config.minimize_to_tray = False
    config.open_browser_on_start = False
    save_config(config)
    browser = MagicMock()
    monkeypatch.setattr("comfy_launcher.app.open_browser", browser)
    instance = SingleInstance()
    app = App(instance)
    app.root.withdraw()
    failures = []
    phase = 0
    first_pid = None
    deadline = time.monotonic() + 25

    def tick() -> None:
        nonlocal phase, first_pid
        try:
            if time.monotonic() > deadline:
                raise AssertionError(f"Timed out in phase {phase}")
            items = list(app.tray.icon.menu)
            if phase == 0 and app.active and not app.busy:
                app.root.relabel("en")
                assert "elapsed" in app.root.elapsed.cget("text")
                app.root.relabel("ar")
                first_pid = app.server.process.pid
                items[0](app.tray.icon)
                phase = 1
            elif phase == 1 and browser.called:
                items[2](app.tray.icon)
                phase = 2
            elif phase == 2 and app.root.key == "stopped" and not app.busy:
                assert app.server.process is None
                assert Path(config.comfy_dir, "graceful.txt").is_file()
                items[1](app.tray.icon)
                phase = 3
            elif phase == 3 and app.active and not app.busy:
                assert app.server.process.pid != first_pid
                items[-1](app.tray.icon)
                phase = 4
                return
        except Exception as error:
            failures.append(error)
            app.action("exit")
            return
        app.root.after(100, tick)

    app.root.after(100, tick)
    app.run()
    assert not failures, failures
    assert phase == 4
    assert app.server.process is None and app.server.job is None
