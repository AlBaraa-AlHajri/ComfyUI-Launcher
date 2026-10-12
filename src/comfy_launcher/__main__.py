"""Windowed entry point and machine-readable packaging diagnostics."""

import argparse
import ctypes
import json
import logging
import os
import sys
from pathlib import Path

from comfy_launcher import __version__
from comfy_launcher.config import Config, detect_installation, load_config
from comfy_launcher.logging_setup import setup_logging
from comfy_launcher.paths import app_data, resource, worker_script


def self_test(report_path: Path | None = None) -> int:
    """Validate resources and available settings without starting ComfyUI or a browser."""
    from PIL import Image

    from comfy_launcher.browser import detect_browser

    report: dict[str, object] = {"version": __version__, "status": "passed"}
    try:
        saved = load_config()
        config = saved or detect_installation()
        (config or Config()).validate(check_paths=config is not None)
        report["installation"] = (
            "validated" if config else "not configured; first-run setup required"
        )
        report["browsers"] = {name: bool(detect_browser(name)) for name in ("chrome", "edge")}
        for name in ("icon.ico", "splash_logo.png", "tray_icon.png"):
            with Image.open(resource("assets/" + name)) as image:
                image.load()
                if name == "icon.ico":
                    expected = {(size, size) for size in (16, 20, 24, 32, 40, 48, 64, 128, 256)}
                    if image.ico.sizes() != expected:
                        raise ValueError("Incomplete ICO resolutions")
        if not worker_script().is_file():
            raise FileNotFoundError("Missing cooperative worker bootstrap")
    except Exception as error:
        logging.exception("Self-test failed")
        report.update(status="failed", error=str(error))
    target = report_path or app_data() / "self-test.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if sys.stdout:
        print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


def main() -> int:
    """Parse diagnostics before loading UI dependencies or acquiring the user mutex."""
    parser = argparse.ArgumentParser(description="Unofficial ComfyUI Launcher")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--self-test-report", type=Path)
    parser.add_argument("--settings", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()
    setup_logging()
    if args.self_test:
        return self_test(args.self_test_report)
    if os.name != "nt":
        raise OSError("The desktop launcher requires Windows 10 or Windows 11.")
    from comfy_launcher.app import App
    from comfy_launcher.single_instance import SingleInstance

    instance = SingleInstance()
    if not instance.primary:
        instance.activate()
        instance.close()
        return 0
    try:
        App(instance, show_settings=args.settings).run()
    finally:
        instance.close()
    return 0


def entrypoint() -> None:
    """Catch failures even before Tk exists; never leave a windowed failure invisible."""
    sys.excepthook = fatal_error
    try:
        raise SystemExit(main())
    except Exception as error:
        fatal_error(type(error), error, error.__traceback__)
        raise SystemExit(1) from error


def fatal_error(kind: type, error: BaseException, traceback: object) -> None:
    """Global last-resort handler for errors before the graphical event loop exists."""
    # Native message boxes remain available if Tk fails. / رسالة أصلية حتى لو تعذّر تحميل Tk.
    logging.error("Fatal launcher error", exc_info=(kind, error, traceback))
    if os.name == "nt":
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.MessageBoxW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint,
        ]
        user.MessageBoxW.restype = ctypes.c_int
        user.MessageBoxW(
            None,
            f"تعذّر تشغيل التطبيق / Launcher could not start\n\n{error}\n\n"
            f"Logs: {app_data() / 'logs'}",
            "ComfyUI Launcher",
            0x10,
        )


if __name__ == "__main__":
    entrypoint()
