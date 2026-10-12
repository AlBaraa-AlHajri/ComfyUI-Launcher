"""Main-thread UI coordinator with serialized background operations and queue dispatch."""

import logging
import os
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from . import __version__
from .browser import open_browser
from .config import Config, detect_installation, load_config, save_config
from .i18n import tr
from .logging_setup import logs_dir
from .paths import resource
from .server import PortBusy, Server, next_free_port
from .settings_window import SettingsWindow
from .single_instance import SingleInstance
from .splash import BACKGROUND, Splash, button, center_window
from .tray import Tray

LOG = logging.getLogger(__name__)


class App:
    """Keep lifecycle transitions serialized while the splash remains responsive."""

    def __init__(self, instance: SingleInstance, show_settings: bool = False) -> None:
        self.instance = instance
        self.config = Config()
        self.active: Config | None = None
        self.server = Server()
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="launcher-worker")
        self.busy, self.closing, self.tray_ready = True, False, False
        self.destroyed = False
        self.open_requested = False
        self.settings_dialog: SettingsWindow | None = None
        self.error_dialog: ctk.CTkToplevel | None = None
        self.root = Splash(self.config.language, self.action)
        self.root.report_callback_exception = self._tk_error
        threading.excepthook = self._thread_error
        self.tray = Tray(self.config.language, lambda action: self.post("action", action))
        self.tray.start()
        self.show_settings = show_settings
        self.root.after(100, self._drain)
        self.root.after(1000, self._monitor)
        self.pool.submit(self._initialize)

    def post(self, key: str, value: object = None) -> None:
        """Queue messages; worker and tray threads never call Tk, even through after()."""
        self.events.put((key, value))

    def _initialize(self) -> None:
        try:
            try:
                config = load_config()
            except (ValueError, OSError, TypeError):
                LOG.exception("Saved configuration is invalid")
                self.post("config_warning")
                config = None
            config = config or detect_installation()
            if config:
                config.validate()
                save_config(config)
            self.post("initialized", config)
        except Exception as error:
            LOG.exception("Environment discovery failed")
            self.post("error", str(error))

    def _drain(self) -> None:
        """Drain a bounded batch so status bursts never starve UI input."""
        # All cross-thread messages converge here. / تُعالَج رسائل الخيوط على خيط الواجهة فقط.
        try:
            for _ in range(100):
                try:
                    key, value = self.events.get_nowait()
                except queue.Empty:
                    break
                self._event(key, value)
            if self.instance.requested() and not self.closing:
                self.action("open")
        except Exception as error:
            LOG.exception("UI event failed")
            self._error(str(error))
        if not self.destroyed:
            self.root.after(100, self._drain)

    def _event(self, key: str, value: object) -> None:
        """Apply ordered state transitions and ignore stale updates during shutdown."""
        if self.closing and key != "closed":
            return
        if key == "action":
            self.action(str(value))
        elif key == "initialized":
            self.busy = False
            if value is None:
                self.settings(first_run=True)
            else:
                self.config = value
                self._relabel()
                if self.show_settings:
                    self.settings()
                self.start()
        elif key == "config_warning":
            messagebox.showwarning(
                "ComfyUI Launcher", tr("config_error", self.config.language), parent=self.root
            )
        elif key == "status":
            self.root.status(str(value))
        elif key == "ready":
            if self.server.cancel.is_set():
                return
            self.active = value
            self.busy = False
            self.root.status("ready")
            if self.active.open_browser_on_start or self.open_requested:
                self.open_requested = False
                self._browser()
            if self.config.minimize_to_tray and self.tray_ready:
                self.root.after(900, self._hide_if_ready)
        elif key == "port_busy":
            self.busy = False
            if messagebox.askyesno(
                "ComfyUI Launcher",
                tr("busy", self.config.language, port=self.config.port, next_port=value),
                parent=self.root,
            ):
                self.config = replace(self.config, port=value)
                save_config(self.config)
                self.start()
            else:
                self.root.status("stopped")
        elif key == "stopped":
            self.active = None
            self.busy = False
            self.root.status("stopped")
        elif key == "error":
            self.busy = False
            self._error(str(value))
        elif key == "browser_error":
            self.root.deiconify()
            messagebox.showerror("ComfyUI Launcher", str(value), parent=self.root)
        elif key == "closed":
            self.tray.stop()
            self.pool.shutdown(wait=False)
            self.instance.close()
            self.destroyed = True
            self.root.destroy()

    def _hide_if_ready(self) -> None:
        if self.root.key == "ready" and self.tray_ready and not self.closing:
            self.root.withdraw()

    def start(self, restart: bool = False) -> None:
        """Start or restart asynchronously using a snapshot of saved preferences."""
        if self.busy or self.closing:
            return
        self.busy = True
        self.server.cancel.clear()
        self.root.started = time.monotonic()
        self.root.elapsed_seconds = 0
        self.root.deiconify()
        self.root.status("checking")
        snapshot = replace(self.config, extra_args=list(self.config.extra_args))

        def work() -> None:
            try:
                if restart:
                    self.server.stop()
                if self.server.start(snapshot, lambda key: self.post("status", key)):
                    self.post("ready", snapshot)
                else:
                    self.post("stopped")
            except PortBusy:
                try:
                    self.post("port_busy", next_free_port(snapshot.port))
                except Exception as error:
                    self.post("error", str(error))
            except Exception as error:
                LOG.exception("Startup failed")
                self.post("error", str(error))

        self.pool.submit(work)

    def _browser(self) -> None:
        snapshot = replace(self.active or self.config)

        def work() -> None:
            try:
                open_browser(snapshot)
            except Exception as error:
                LOG.exception("Browser launch failed")
                self.post("browser_error", str(error))

        self.pool.submit(work)

    def action(self, action: str) -> None:
        """Handle tray and window controls, preserving ownership of externally started servers."""
        if self.closing:
            return
        if action == "tray_ready":
            self.tray_ready = True
        elif action == "tray_error":
            self.tray_ready = False
            self.root.deiconify()
            messagebox.showwarning(
                "ComfyUI Launcher", tr("tray_error", self.config.language), parent=self.root
            )
        elif action == "open":
            if self.busy:
                self.open_requested = True
                self.root.deiconify()
                self.root.lift()
            elif self.active is not None:
                self._browser()
            else:
                self.open_requested = True
                self.start()
        elif action in ("stop", "restart"):
            if self.server.attached:
                messagebox.showinfo(
                    "ComfyUI Launcher", tr("external", self.config.language), parent=self.root
                )
            elif action == "restart" and not self.busy:
                self.start(restart=True)
            elif action == "stop":
                self.server.cancel.set()
                self.busy = True
                self.root.deiconify()
                self.root.status("stopping")
                self.pool.submit(self._stop, False)
        elif action == "exit":
            self.closing = True
            self.server.cancel.set()
            self.root.deiconify()
            self.root.status("stopping")
            self.pool.submit(self._stop, True)
        elif action == "hide":
            if self.tray_ready:
                self.root.withdraw()
        elif action == "settings":
            self.settings()
        elif action == "about":
            messagebox.showinfo(
                tr("about", self.config.language),
                tr("about_text", self.config.language, version=__version__),
                parent=self.root,
            )
        elif action in ("log", "folder", "output"):
            self.pool.submit(self._open_path, action)

    def _stop(self, closing: bool) -> None:
        """Complete shutdown off the UI thread, even after an unexpected worker failure."""
        try:
            self.server.stop()
            self.post("closed" if closing else "stopped")
        except Exception as error:
            LOG.exception("Shutdown failed")
            if closing:
                # Job close is the final containment guarantee. / إغلاق المهمة يضمن تنظيف الأبناء.
                if self.server.job:
                    self.server.job.close()
                self.post("closed")
            else:
                self.post("error", str(error))

    def _open_path(self, action: str) -> None:
        try:
            config = self.active or self.config
            if action == "log":
                target = self.server.log_path or logs_dir() / "launcher.log"
            else:
                target = Path(config.comfy_dir)
                if action == "output":
                    target /= "output"
                    for index, arg in enumerate(config.extra_args):
                        if arg == "--output-directory" and index + 1 < len(config.extra_args):
                            target = Path(config.extra_args[index + 1])
                        elif arg.startswith("--output-directory="):
                            target = Path(arg.split("=", 1)[1])
                    if not target.is_absolute():
                        target = Path(config.comfy_dir) / target
            os.startfile(target)
        except Exception as error:
            LOG.exception("Cannot open requested path")
            self.post("browser_error", str(error))

    def settings(self, first_run: bool = False) -> None:
        """Allow only one editor and apply settings without moving the active server URL."""
        if self.settings_dialog and self.settings_dialog.winfo_exists():
            self.settings_dialog.lift()
            return

        def save(config: Config) -> None:
            save_config(config)
            self.config = config
            self._relabel()
            if first_run or self.active is None:
                self.start()
            else:
                messagebox.showinfo(
                    "ComfyUI Launcher", tr("saved", config.language), parent=self.settings_dialog
                )

        self.settings_dialog = SettingsWindow(self.root, self.config, save, first_run)

    def _relabel(self) -> None:
        self.root.relabel(self.config.language)
        self.tray.relabel(self.config.language)

    def _error(self, detail: str) -> None:
        """Present original diagnostic text with explicit copy, log and recovery actions."""
        self.root.deiconify()
        self.root.status("error")
        if self.error_dialog and self.error_dialog.winfo_exists():
            self.error_dialog.destroy()
        dialog = ctk.CTkToplevel(self.root, fg_color=BACKGROUND)
        self.error_dialog = dialog
        dialog.title(tr("error", self.config.language))
        dialog.geometry("800x530")
        dialog.after(100, lambda: center_window(dialog))
        dialog.after(200, lambda: dialog.iconbitmap(str(resource("assets/icon.ico"))))
        ctk.CTkLabel(
            dialog, text=tr("error_help", self.config.language), font=("Segoe UI", 16)
        ).pack(padx=20, pady=18)
        box = ctk.CTkTextbox(dialog, wrap="word", font=("Consolas", 12))
        box.pack(fill="both", expand=True, padx=20)
        box.insert("1.0", detail)
        box.configure(state="disabled")
        row = ctk.CTkFrame(dialog, fg_color="transparent")
        row.pack(pady=18)

        def copy() -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(detail)
            copy_button.configure(text=tr("copied", self.config.language))

        def retry() -> None:
            dialog.destroy()
            self.start()

        copy_button = button(row, tr("copy", self.config.language), copy, width=120)
        copy_button.pack(side="left", padx=4)
        button(row, tr("log", self.config.language), lambda: self.action("log"), width=120).pack(
            side="left", padx=4
        )
        button(row, tr("settings", self.config.language), self.settings, width=120).pack(
            side="left", padx=4
        )
        button(row, tr("retry", self.config.language), retry, primary=True, width=120).pack(
            side="left", padx=4
        )
        dialog.lift()

    def _monitor(self) -> None:
        """Check owned-process exit locally without blocking on an HTTP request."""
        if self.active and not self.busy and not self.closing and not self.server.attached:
            if not self.server.running():
                self.active = None
                self._error("ComfyUI stopped unexpectedly.\n\n" + "".join(self.server.lines))
                self.pool.submit(self.server.stop)
        self.root.after(1000, self._monitor)

    def _tk_error(self, kind: type, error: BaseException, traceback: object) -> None:
        LOG.error("Unhandled UI error", exc_info=(kind, error, traceback))
        self._error(str(error))

    def _thread_error(self, args: threading.ExceptHookArgs) -> None:
        LOG.error(
            "Unhandled worker error", exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
        )
        self.post("error", str(args.exc_value))

    def run(self) -> None:
        """Enter the main event loop and always release owned resources on final exit."""
        try:
            self.root.mainloop()
        finally:
            self.server.cancel.set()
            self.pool.shutdown(wait=True)
            self.server.stop()
            self.tray.stop()
            self.instance.close()
