"""Headless server startup, schema-aware health checks and owned-tree shutdown."""

import logging
import os
import re
import socket
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from itertools import chain
from pathlib import Path

import psutil
import requests

from .config import Config
from .logging_setup import prune_server_logs, server_log
from .paths import worker_script
from .winjob import Job

LOG = logging.getLogger(__name__)
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class StartupError(RuntimeError):
    """A failed startup with bounded diagnostic output for the error dialog."""


class PortBusy(RuntimeError):
    """A non-ComfyUI service is listening on the requested port."""


def build_args(config: Config) -> list[str]:
    """Make launcher-managed flags authoritative without modifying stored preferences."""
    args: list[str] = []
    skip = False
    for arg in config.extra_args:
        if skip:
            skip = False
            continue
        if arg == "--port":
            skip = True
        elif arg in ("--auto-launch", "--disable-auto-launch") or arg.startswith("--port="):
            continue
        else:
            args.append(arg)
    return [*args, "--port", str(config.port), "--disable-auto-launch"]


def build_command(config: Config) -> list[str]:
    """Use argument arrays so spaces, quotes and Arabic paths never invoke a shell."""
    return [
        config.python_exe,
        "-u",
        str(worker_script()),
        str(Path(config.comfy_dir) / "main.py"),
        *build_args(config),
    ]


def health_check(port: int, timeout: float = 1.0) -> bool:
    """Recognize ComfyUI's JSON schema instead of mistaking an arbitrary HTTP 200 for ready."""
    try:
        with requests.Session() as session:
            session.trust_env = False  # Loopback must bypass proxies. / تجنب البروكسي للفحص المحلي.
            with session.get(
                f"http://127.0.0.1:{port}/system_stats",
                timeout=timeout,
                allow_redirects=False,
                stream=True,
            ) as response:
                if response.status_code != 200:
                    return False
                body = bytearray()
                for chunk in response.iter_content(8192):
                    body.extend(chunk)
                    if len(body) > 1_000_000:
                        return False
                import json

                data = json.loads(body)
                return (
                    isinstance(data, dict)
                    and isinstance(data.get("system"), dict)
                    and isinstance(data.get("devices"), list)
                    and {"os", "python_version"}.issubset(data["system"])
                )
    except (requests.RequestException, ValueError, OSError):
        return False


def port_available(port: int) -> bool:
    """Check the actual local bind, including exclusive Windows listener semantics."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if os.name == "nt":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False


def next_free_port(port: int) -> int:
    """Skip Windows reserved port ranges and wrap only into non-privileged ports."""
    for candidate in chain(range(port + 1, 65536), range(1024, port)):
        if port_available(candidate):
            return candidate
    raise StartupError("No available local server port. Review network settings and retry.")


class Server:
    """A controller serialized by the app worker; stop cancellation is thread-safe."""

    def __init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None
        self.job: Job | None = None
        self.attached = False
        self.cancel = threading.Event()
        self.lines: deque[str] = deque(maxlen=40)
        self.log_path: Path | None = None
        self.reader: threading.Thread | None = None

    def start(self, config: Config, status: Callable[[str], None]) -> bool:
        """Return True on readiness, False on cancellation; never run on Tk's thread."""
        self.lines.clear()
        status("checking")
        if health_check(config.port):
            self.attached = not self.running()
            LOG.info("Reusing existing ComfyUI on port %s", config.port)
            return True
        self.attached = False
        config.validate()
        if not port_available(config.port):
            raise PortBusy(str(config.port))
        if self.cancel.is_set():
            return False
        status("starting")
        logger, self.log_path = server_log()
        environment = os.environ.copy()
        environment.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONUNBUFFERED="1")
        # Custom nodes may resolve pip or Python from PATH. / العقد قد تبحث عن Python عبر PATH.
        interpreter_dir = Path(config.python_exe).parent
        environment["PATH"] = str(interpreter_dir) + os.pathsep + environment.get("PATH", "")
        if (interpreter_dir.parent / "pyvenv.cfg").is_file():
            environment["VIRTUAL_ENV"] = str(interpreter_dir.parent)
        else:
            environment.pop("VIRTUAL_ENV", None)
        # Frozen Python variables must not leak into the venv. / منع تسرب إعدادات الحزمة للبيئة.
        for key in ("PYTHONHOME", "PYTHONPATH", "_MEIPASS2"):
            environment.pop(key, None)
        try:
            self.job = Job()
            self.process = subprocess.Popen(
                build_command(config),
                cwd=config.comfy_dir,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            self.job.assign(self.process.pid)
            assert self.process.stdin is not None
            self.process.stdin.write("start\n")
            self.process.stdin.flush()
            self.reader = threading.Thread(target=self._capture, args=(logger,), daemon=True)
            self.reader.start()
            LOG.info("Started owned ComfyUI pid=%s port=%s", self.process.pid, config.port)
            status("waiting")
            deadline = time.monotonic() + config.startup_timeout
            while time.monotonic() < deadline:
                if self.cancel.is_set():
                    self.stop()
                    return False
                if self.process.poll() is not None:
                    self.reader.join(timeout=2)
                    raise StartupError(
                        f"ComfyUI exited with code {self.process.returncode}.\n\n"
                        + "".join(self.lines)
                    )
                if health_check(config.port) and self.process.poll() is None:
                    return True
                self.cancel.wait(0.4)
            raise StartupError(
                f"Startup exceeded {config.startup_timeout} seconds.\n\n" + "".join(self.lines)
            )
        except Exception:
            self.stop()
            raise

    def _capture(self, logger: logging.Logger) -> None:
        """Continuously drain the pipe to prevent a verbose server deadlocking startup."""
        assert self.process is not None and self.process.stdout is not None
        try:
            for line in self.process.stdout:
                line = ANSI_ESCAPE.sub("", line)
                self.lines.append(line)
                logger.info(line.rstrip("\r\n"))
        except (OSError, ValueError):
            LOG.exception("Server log reader stopped")
        finally:
            prune_server_logs()

    def stop(self, timeout: float = 10.0) -> None:
        """Interrupt cooperatively, then terminate/kill surviving owned descendants."""
        process = self.process
        if process is None:
            return  # External servers remain user-owned. / الخادم الخارجي يبقى تحت إدارة المستخدم.
        tracked: list[psutil.Process] = []
        try:
            parent = psutil.Process(process.pid)
            tracked = parent.children(recursive=True) + [parent]
        except psutil.NoSuchProcess:
            pass
        try:
            if process.poll() is None and process.stdin:
                try:
                    process.stdin.write("stop\n")
                    process.stdin.flush()
                except (OSError, ValueError):
                    LOG.warning("Cooperative shutdown pipe unavailable")
            _, alive = psutil.wait_procs(tracked, timeout=timeout)
            for item in alive:
                try:
                    item.terminate()
                except psutil.NoSuchProcess:
                    pass
            _, alive = psutil.wait_procs(alive, timeout=2)
            for item in alive:
                try:
                    item.kill()
                except psutil.NoSuchProcess:
                    pass
        finally:
            if self.job:
                self.job.close()
                self.job = None
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            if self.reader:
                self.reader.join(timeout=2)
            for stream in (process.stdin, process.stdout):
                if stream:
                    stream.close()
            self.process = None
            LOG.info("Owned server and process tree stopped")

    def running(self) -> bool:
        """Inspect only the owned process, without performing network I/O on the UI thread."""
        return self.process is not None and self.process.poll() is None
