"""Tray callbacks communicate through a queue; they never touch Tk widgets."""

import logging
import threading
from collections.abc import Callable

import pystray
from PIL import Image

from .i18n import tr
from .paths import resource


class Tray:
    """Create one tray icon with a localized management menu."""

    def __init__(self, language: str, dispatch: Callable[[str], None]) -> None:
        self.dispatch = dispatch
        self.icon = pystray.Icon(
            "ComfyUI-Launcher",
            Image.open(resource("assets/icon.ico")),
            "ComfyUI Launcher",
            self._menu(language),
        )
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _menu(self, language: str) -> pystray.Menu:
        keys = ["open", "restart", "stop", "log", "folder", "output", "settings", "about", "exit"]

        def callback(key: str) -> Callable:
            def invoke(icon: pystray.Icon, item: pystray.MenuItem) -> None:
                self.dispatch(key)

            return invoke

        return pystray.Menu(
            *(
                pystray.MenuItem(tr(key, language), callback(key), default=key == "open")
                for key in keys
            )
        )

    def _run(self) -> None:
        try:
            self.icon.run(setup=lambda icon: self._ready(icon))
        except Exception:
            logging.getLogger(__name__).exception("Tray failed")
            self.dispatch("tray_error")

    def _ready(self, icon: pystray.Icon) -> None:
        icon.visible = True
        self.dispatch("tray_ready")

    def start(self) -> None:
        """Start the independent Windows tray message loop."""
        self.thread.start()

    def relabel(self, language: str) -> None:
        """Refresh menu text after settings change."""
        self.icon.menu = self._menu(language)
        self.icon.update_menu()

    def stop(self) -> None:
        """Remove the tray icon when the owned server has stopped."""
        self.icon.stop()
