"""Installation-independent resource and per-user storage paths."""

import os
import sys
from pathlib import Path


def app_data() -> Path:
    """Return writable user storage; allow isolated diagnostics and tests."""
    override = os.environ.get("COMFY_LAUNCHER_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path(os.environ.get("APPDATA", Path.home() / ".config")) / "ComfyUI-Launcher"


def resource(name: str) -> Path:
    """Resolve bundled files without depending on the current directory."""
    # PyInstaller stores resources inside _internal. / موارد الحزمة داخل مجلدها الداخلي.
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / name


def worker_script() -> Path:
    """Return the standalone, standard-library-only cooperative child bootstrap."""
    if getattr(sys, "frozen", False):
        return resource("worker.py")
    return Path(__file__).with_name("worker.py")
