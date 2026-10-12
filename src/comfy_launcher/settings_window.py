"""Localized first-run and settings editor with reversible, validated saves."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .config import COMMON_FLAGS, Config, find_python, format_args, parse_args
from .i18n import tr
from .paths import resource
from .splash import BACKGROUND, MUTED, PANEL, button, center_window


class SettingsWindow(ctk.CTkToplevel):
    """A scrollable editor that never mutates active server settings until Save."""

    def __init__(
        self,
        parent: ctk.CTk,
        config: Config,
        save: Callable[[Config], None],
        first_run: bool = False,
    ) -> None:
        super().__init__(parent, fg_color=BACKGROUND)
        self.config_value, self.on_save, self.lang = config, save, config.language
        self.title(tr("first_run" if first_run else "settings", self.lang))
        self.geometry("720x800")
        self.minsize(630, 580)
        self.after(200, lambda: self.iconbitmap(str(resource("assets/icon.ico"))))
        self.entries: dict[str, ctk.CTkEntry] = {}
        self.flags: dict[str, ctk.BooleanVar] = {}
        anchor = "e" if self.lang == "ar" else "w"
        body = ctk.CTkScrollableFrame(self, fg_color=BACKGROUND)
        body.pack(fill="both", expand=True, padx=22, pady=(18, 8))
        body.grid_columnconfigure(0, weight=1)

        def label(text: str) -> None:
            ctk.CTkLabel(
                body, text=text, anchor=anchor, font=("Segoe UI", 14), text_color=MUTED
            ).pack(fill="x", pady=(12, 5))

        for name in ("comfy_dir", "python_exe"):
            label(tr(name, self.lang))
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x")
            entry = ctk.CTkEntry(row, height=36, fg_color=PANEL)
            entry.insert(0, getattr(config, name))
            entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self.entries[name] = entry
            button(
                row,
                tr("browse", self.lang),
                lambda key=name: self._browse(key),
                width=90,
                height=36,
            ).pack(side="right")
        for key, value in (("port", config.port), ("timeout", config.startup_timeout)):
            label(tr(key, self.lang))
            entry = ctk.CTkEntry(body, height=34, fg_color=PANEL)
            entry.insert(0, str(value))
            entry.pack(fill="x")
            self.entries[key] = entry
        label(tr("browser", self.lang))
        self.browser = ctk.CTkOptionMenu(
            body, values=["chrome", "edge", "default"], fg_color=PANEL, button_color="#51426A"
        )
        self.browser.set(config.browser)
        self.browser.pack(fill="x")
        label(tr("language", self.lang))
        self.language = ctk.CTkOptionMenu(
            body, values=["العربية", "English"], fg_color=PANEL, button_color="#51426A"
        )
        self.language.set("العربية" if config.language == "ar" else "English")
        self.language.pack(fill="x")
        self.options: dict[str, ctk.BooleanVar] = {}
        for key, field in (
            ("app_mode", "app_mode"),
            ("open_on_start", "open_browser_on_start"),
            ("minimize", "minimize_to_tray"),
        ):
            variable = ctk.BooleanVar(value=getattr(config, field))
            self.options[field] = variable
            ctk.CTkCheckBox(
                body, text=tr(key, self.lang), variable=variable, font=("Segoe UI", 14)
            ).pack(anchor=anchor, pady=(14, 0))
        label(tr("flags", self.lang))
        remaining = list(config.extra_args)
        for flag in COMMON_FLAGS:
            parts = flag.split()
            selected = False
            for index in range(len(remaining)):
                if remaining[index : index + len(parts)] == parts:
                    # Preserve custom --listen addresses. / حفظ عنوان الاستماع المخصص.
                    if flag == "--listen" and index + 1 < len(remaining):
                        if not remaining[index + 1].startswith("--"):
                            continue
                    del remaining[index : index + len(parts)]
                    selected = True
                    break
            variable = ctk.BooleanVar(value=selected)
            self.flags[flag] = variable
            ctk.CTkCheckBox(body, text=flag, variable=variable).pack(anchor="w", pady=5)
        ctk.CTkLabel(
            body,
            text=tr("flags_help", self.lang),
            wraplength=600,
            justify="right" if self.lang == "ar" else "left",
            text_color=MUTED,
        ).pack(fill="x", pady=(8, 0))
        label(tr("extra", self.lang))
        self.extra = ctk.CTkEntry(body, height=36, fg_color=PANEL)
        self.extra.insert(0, format_args(remaining))
        self.extra.pack(fill="x", pady=(0, 14))
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(4, 18))
        button(footer, tr("save", self.lang), self._save, primary=True).pack(side="right", padx=5)
        button(footer, tr("cancel", self.lang), self.destroy).pack(side="right", padx=5)
        self.after(100, self.lift)
        self.after(100, lambda: center_window(self))

    def _browse(self, key: str) -> None:
        """Accept either the ComfyUI folder or the outer portable package directory."""
        if key == "comfy_dir":
            value = filedialog.askdirectory(parent=self, title=tr(key, self.lang))
            if value:
                selected = Path(value)
                if (
                    not (selected / "main.py").is_file()
                    and (selected / "ComfyUI/main.py").is_file()
                ):
                    selected /= "ComfyUI"
                value = str(selected)
                python = find_python(selected)
                if python:
                    self.entries["python_exe"].delete(0, "end")
                    self.entries["python_exe"].insert(0, str(python))
        else:
            value = filedialog.askopenfilename(
                parent=self,
                title=tr(key, self.lang),
                filetypes=[("Python", "*.exe"), ("All", "*.*")],
            )
        if value:
            self.entries[key].delete(0, "end")
            self.entries[key].insert(0, value)

    def _save(self) -> None:
        """Validate a fresh snapshot before committing any user preference."""
        # Cancel leaves the running configuration untouched. / الإلغاء لا يغيّر الإعدادات الحالية.
        try:
            args = [
                part
                for flag, variable in self.flags.items()
                if variable.get()
                for part in flag.split()
            ]
            args.extend(parse_args(self.extra.get()))
            config = replace(
                self.config_value,
                comfy_dir=self.entries["comfy_dir"].get().strip(),
                python_exe=self.entries["python_exe"].get().strip(),
                extra_args=args,
                port=int(self.entries["port"].get()),
                startup_timeout=int(self.entries["timeout"].get()),
                browser=self.browser.get(),
                language="ar" if self.language.get() == "العربية" else "en",
                **{key: variable.get() for key, variable in self.options.items()},
            )
            config.validate()
            self.on_save(config)
        except (ValueError, OSError) as error:
            messagebox.showerror(tr("invalid", self.lang), str(error), parent=self)
            return
        self.destroy()
