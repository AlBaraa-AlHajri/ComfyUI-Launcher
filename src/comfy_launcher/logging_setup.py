"""UTF-8 logs with bounded retention and useful startup diagnostics."""

import logging
from collections import deque
from datetime import date
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import app_data


class ServerRotatingHandler(RotatingFileHandler):
    """Apply the ten-file total retention limit during long-running server sessions too."""

    def doRollover(self) -> None:
        # Count all days together after rotating. / احتساب جميع الأيام بعد تدوير السجل.
        super().doRollover()
        prune_server_logs()


def logs_dir() -> Path:
    """Create and return the writable log directory."""
    path = app_data() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def setup_logging() -> None:
    """Keep ten launcher log files, including the current file."""
    handler = RotatingFileHandler(
        logs_dir() / "launcher.log", maxBytes=2_000_000, backupCount=9, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)


def server_log() -> tuple[logging.Logger, Path]:
    """Rotate large daily server logs and keep the ten most recent files in total."""
    path = logs_dir() / f"comfyui_{date.today().isoformat()}.log"
    logger = logging.getLogger("comfyui.output")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    for old in logger.handlers[:]:
        old.close()
        logger.removeHandler(old)
    handler = ServerRotatingHandler(path, maxBytes=5_000_000, backupCount=9, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    prune_server_logs()
    return logger, path


def prune_server_logs() -> None:
    """Bound daily and size-based history together, preserving the newest logs."""
    files = sorted(
        logs_dir().glob("comfyui_*.log*"), key=lambda item: item.stat().st_mtime, reverse=True
    )
    for path in files[10:]:
        try:
            path.unlink()
        except OSError:
            logging.getLogger(__name__).warning("Cannot prune %s", path)


def tail(path: Path | None, count: int = 40) -> str:
    """Read only a bounded tail into memory, tolerating interrupted Unicode writes."""
    if path is None:
        return ""
    try:
        with path.open(encoding="utf-8", errors="replace") as stream:
            return "".join(deque(stream, maxlen=count))
    except OSError:
        return ""
