"""Validated, atomic configuration and bounded installation discovery."""

import ctypes
import json
import os
import shlex
import shutil
import string
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .paths import app_data

MEMORY_FLAGS = {"--lowvram", "--normalvram", "--highvram", "--cpu", "--novram", "--gpu-only"}
COMMON_FLAGS = [
    "--lowvram",
    "--normalvram",
    "--highvram",
    "--cpu",
    "--listen",
    "--preview-method auto",
]


@dataclass
class Config:
    """Portable user preferences; installation paths are discovered on first run."""

    comfy_dir: str = ""
    python_exe: str = ""
    extra_args: list[str] = field(default_factory=lambda: ["--lowvram"])
    port: int = 8188
    browser: str = "chrome"
    app_mode: bool = True
    startup_timeout: int = 180
    open_browser_on_start: bool = True
    minimize_to_tray: bool = True
    language: str = "ar"
    schema_version: int = 1

    @property
    def url(self) -> str:
        """Return a loopback URL independent of the configured listening interfaces."""
        return f"http://127.0.0.1:{self.port}"

    def validate(self, check_paths: bool = True) -> None:
        """Reject malformed settings before a process or browser is launched."""
        # Reject booleans masquerading as integers in JSON. / رفض القيم المنطقية مكان الأرقام.
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("Port must be an integer between 1 and 65535.")
        if type(self.startup_timeout) is not int or not 5 <= self.startup_timeout <= 3600:
            raise ValueError("Startup timeout must be between 5 and 3600 seconds.")
        if self.browser not in ("chrome", "edge", "default") or self.language not in ("ar", "en"):
            raise ValueError("Unsupported browser or language.")
        for name in ("app_mode", "open_browser_on_start", "minimize_to_tray"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be true or false.")
        if not isinstance(self.extra_args, list) or any(
            not isinstance(arg, str) or "\x00" in arg for arg in self.extra_args
        ):
            raise ValueError("extra_args must be a list of strings without null characters.")
        if len(MEMORY_FLAGS.intersection(self.extra_args)) > 1:
            raise ValueError("Select only one memory mode: low / normal / high VRAM / CPU.")
        # The health probe requires IPv4 loopback access. / فحص الجاهزية يحتاج عنوان الجهاز المحلي.
        for index, arg in enumerate(self.extra_args):
            address = None
            if arg.startswith("--listen="):
                address = arg.split("=", 1)[1]
            elif arg == "--listen" and index + 1 < len(self.extra_args):
                following = self.extra_args[index + 1]
                if not following.startswith("--"):
                    address = following
            if address and not {"127.0.0.1", "0.0.0.0"}.intersection(address.split(",")):
                raise ValueError("--listen must include 127.0.0.1 or 0.0.0.0 for health checks.")
        if not isinstance(self.comfy_dir, str) or not isinstance(self.python_exe, str):
            raise ValueError("Installation paths must be strings.")
        if check_paths:
            if not (Path(self.comfy_dir) / "main.py").is_file():
                raise ValueError("Select the ComfyUI folder containing main.py.")
            if not Path(self.python_exe).is_file():
                raise ValueError("Select an existing environment python.exe.")


def config_path() -> Path:
    """Return the per-user JSON filename."""
    return app_data() / "config.json"


def load_config(path: Path | None = None) -> Config | None:
    """Load old configurations with additive defaults, retaining the original on failure."""
    target = path or config_path()
    if not target.exists():
        return None
    data = json.loads(target.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object.")
    if data.get("schema_version", 0) not in (0, 1):
        raise ValueError("This configuration requires a newer launcher.")
    known = {item.name for item in fields(Config)}
    config = Config(**{key: value for key, value in data.items() if key in known})
    config.schema_version = 1
    config.validate(check_paths=False)
    return config


def save_config(config: Config, path: Path | None = None) -> None:
    """Atomically replace JSON and retain the last valid file as a backup."""
    config.validate()
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Same-directory replacement survives partial writes. / الاستبدال الذري يمنع تلف الإعدادات.
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(asdict(config), stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if target.exists():
            try:
                load_config(target)
            except (ValueError, OSError, TypeError):
                backup = target.with_name(f"config.invalid-{time.time_ns()}.json")
            else:
                backup = target.with_suffix(".json.bak")
            shutil.copy2(target, backup)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def find_python(comfy: Path) -> Path | None:
    """Find a sibling or internal venv, or the official embedded interpreter."""
    for base in (comfy.parent, comfy):
        for relative in (
            "venv/Scripts/python.exe",
            ".venv/Scripts/python.exe",
            "python_embeded/python.exe",
            "python_embedded/python.exe",
        ):
            candidate = base / relative
            if candidate.is_file():
                return candidate.resolve()
    return None


def detect_installation() -> Config | None:
    """Search likely locations, then local drive roots two levels deep without recursion."""
    # Personal defaults appear only in this discovery list. / المسارات الافتراضية هنا فقط للاكتشاف.
    candidates = [
        Path("D:/ComfyUI/ComfyUI"),
        Path("C:/ComfyUI/ComfyUI"),
        Path("C:/ComfyUI"),
        Path.home() / "ComfyUI",
    ]
    for base in (Path.cwd(), Path(__file__).resolve().parents[2], Path.home() / "Downloads"):
        candidates.extend([base, base / "ComfyUI", base.parent / "ComfyUI"])
    for candidate in candidates:
        python = find_python(candidate)
        if (candidate / "main.py").is_file() and python:
            return Config(comfy_dir=str(candidate.resolve()), python_exe=str(python))
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
        kernel.GetDriveTypeW.restype = ctypes.c_uint
        for drive in string.ascii_uppercase:
            root = Path(f"{drive}:/")
            if kernel.GetDriveTypeW(str(root) + "\\") != 3:
                # Skip removable/network drives. / تجاهل أقراص الشبكة والأقراص القابلة للإزالة.
                continue
            try:
                for folder in root.iterdir():
                    if "comfy" not in folder.name.casefold() or not folder.is_dir():
                        continue
                    for candidate in (folder, folder / "ComfyUI"):
                        python = find_python(candidate)
                        if (candidate / "main.py").is_file() and python:
                            return Config(comfy_dir=str(candidate), python_exe=str(python))
            except OSError:
                continue
    return None


def parse_args(text: str) -> list[str]:
    """Parse Windows quoting without stripping backslashes from Unicode paths."""
    if not text.strip():
        return []
    if os.name != "nt":
        return shlex.split(text)
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    count = ctypes.c_int()
    argv = shell.CommandLineToArgvW("launcher " + text, ctypes.byref(count))
    if not argv:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return [argv[index] for index in range(1, count.value)]
    finally:
        kernel.LocalFree(argv)


def format_args(args: list[str]) -> str:
    """Display a safely round-trippable command line in the settings field."""
    return subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)
