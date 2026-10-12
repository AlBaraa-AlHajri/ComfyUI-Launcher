"""Compact borderless status window; all widget methods run on Tk's main thread."""

import ctypes
import os
import time
from collections.abc import Callable

import customtkinter as ctk
from PIL import Image

from .i18n import tr
from .paths import resource

BACKGROUND = "#1E1828"
PANEL = "#2A2238"
ACCENT = "#D8FF3E"
MUTED = "#ACA2BC"


def center_window(window: ctk.CTk | ctk.CTkToplevel) -> None:
    """Keep new dialogs entirely on the primary screen rather than below their parent."""
    window.update_idletasks()
    x = max(0, (window.winfo_screenwidth() - window.winfo_width()) // 2)
    y = max(0, (window.winfo_screenheight() - window.winfo_height()) // 2 - 24)
    window.geometry(f"+{x}+{y}")


def button(
    parent: ctk.CTkBaseClass, text: str, command: Callable, primary: bool = False, **kwargs: object
) -> ctk.CTkButton:
    """Share accessible contrast and consistent button styling."""
    return ctk.CTkButton(
        parent,
        text=text,
        command=command,
        corner_radius=10,
        fg_color=ACCENT if primary else PANEL,
        text_color=BACKGROUND if primary else "#F5F1FA",
        hover_color="#BEDE36" if primary else "#3A304B",
        **kwargs,
    )


class Splash(ctk.CTk):
    """Draggable splash with elapsed time and explicit management controls."""

    def __init__(self, language: str, action: Callable[[str], None]) -> None:
        ctk.set_appearance_mode("dark")
        super().__init__(fg_color=BACKGROUND)
        self.lang = language
        self.action = action
        self.title("ComfyUI Launcher")
        self.geometry("500x550")
        self.resizable(False, False)
        self.overrideredirect(True)
        self.iconbitmap(str(resource("assets/icon.ico")))
        self.started = time.monotonic()
        self.elapsed_seconds = 0
        self.ticking = True
        self.key = "checking"
        self._drag = (0, 0)
        self.bind("<ButtonPress-1>", self._begin_drag)
        self.bind("<B1-Motion>", self._drag_to)
        self.protocol("WM_DELETE_WINDOW", lambda: action("exit"))
        ctk.CTkLabel(
            self, text="COMFYUI LAUNCHER", text_color=MUTED, font=("Segoe UI", 12, "bold")
        ).pack(pady=(24, 10))
        self.logo = ctk.CTkImage(Image.open(resource("assets/splash_logo.png")), size=(132, 132))
        ctk.CTkLabel(self, image=self.logo, text="").pack(pady=(4, 10))
        ctk.CTkLabel(self, text="ComfyUI Launcher", font=("Segoe UI", 27, "bold")).pack()
        self.subtitle = ctk.CTkLabel(
            self, text=tr("subtitle", language), text_color=MUTED, font=("Segoe UI", 14)
        )
        self.subtitle.pack(pady=(4, 20))
        self.status_label = ctk.CTkLabel(
            self, text=tr(self.key, language), text_color=ACCENT, font=("Segoe UI", 18)
        )
        self.status_label.pack()
        self.progress = ctk.CTkProgressBar(
            self, width=360, height=5, mode="indeterminate", progress_color=ACCENT, fg_color=PANEL
        )
        self.progress.pack(pady=14)
        self.progress.start()
        self.elapsed = ctk.CTkLabel(self, text="", text_color=MUTED, font=("Segoe UI", 12))
        self.elapsed.pack()
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(pady=(14, 8))
        self.open_button = button(
            controls,
            tr("open", language),
            lambda: action("open"),
            primary=True,
            width=190,
            height=36,
        )
        self.open_button.pack(side="left", padx=5)
        self.settings_button = button(
            controls, tr("settings", language), lambda: action("settings"), width=170, height=36
        )
        self.settings_button.pack(side="left", padx=5)
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(pady=4)
        self.hide_button = button(footer, tr("hide", language), lambda: action("hide"), width=180)
        self.hide_button.pack(side="left", padx=5)
        self.exit_button = button(footer, tr("exit", language), lambda: action("exit"), width=180)
        self.exit_button.pack(side="left", padx=5)
        self.after(50, self._center)
        self.after(60, self._taskbar_window)
        self.after(250, self._tick)

    def _center(self) -> None:
        self.geometry(
            f"+{(self.winfo_screenwidth() - self.winfo_width()) // 2}"
            f"+{(self.winfo_screenheight() - self.winfo_height()) // 2}"
        )

    def _taskbar_window(self) -> None:
        """Expose the borderless splash to Alt-Tab and accessibility window discovery."""
        if os.name != "nt":
            return
        from ctypes import wintypes as wt

        user = ctypes.WinDLL("user32", use_last_error=True)
        user.GetParent.argtypes, user.GetParent.restype = [wt.HWND], wt.HWND
        user.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
        user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
        user.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        window = user.GetParent(self.winfo_id())
        style = user.GetWindowLongPtrW(window, -20)
        # WS_EX_APPWINDOW without WS_EX_TOOLWINDOW. / إظهار النافذة كتطبيق عادي دون إطار.
        user.SetWindowLongPtrW(window, -20, (style & ~0x80) | 0x40000)

    def _begin_drag(self, event: object) -> None:
        self._drag = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _drag_to(self, event: object) -> None:
        self.geometry(f"+{event.x_root - self._drag[0]}+{event.y_root - self._drag[1]}")

    def _tick(self) -> None:
        if self.ticking:
            self.elapsed_seconds = int(time.monotonic() - self.started)
            self.elapsed.configure(text=tr("elapsed", self.lang, seconds=self.elapsed_seconds))
        self.after(250, self._tick)

    def status(self, key: str) -> None:
        """Apply a worker status update and stop animation when work has ended."""
        self.key = key
        self.status_label.configure(text=tr(key, self.lang))
        self.ticking = key not in ("ready", "stopped", "error")
        if self.ticking:
            self.progress.configure(mode="indeterminate")
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.progress.set(1 if key == "ready" else 0)

    def relabel(self, language: str) -> None:
        """Update existing controls immediately after a language change."""
        self.lang = language
        self.subtitle.configure(text=tr("subtitle", language))
        for widget, key in (
            (self.open_button, "open"),
            (self.settings_button, "settings"),
            (self.hide_button, "hide"),
            (self.exit_button, "exit"),
        ):
            widget.configure(text=tr(key, language))
        self.status(self.key)
        self.elapsed.configure(text=tr("elapsed", language, seconds=self.elapsed_seconds))
