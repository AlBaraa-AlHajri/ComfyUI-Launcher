"""Isolated storage and a real loopback ComfyUI-shaped child server for lifecycle tests."""

import socket
import sys
from pathlib import Path

import pytest

from comfy_launcher.config import Config


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never read or overwrite the user's actual launcher configuration during tests."""
    monkeypatch.setenv("COMFY_LAUNCHER_HOME", str(tmp_path / "launcher data بيانات"))


@pytest.fixture
def free_port() -> int:
    """Ask the operating system for an unused loopback port."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def config(tmp_path: Path, free_port: int) -> Config:
    """Create an actual script in a path with spaces and Arabic characters."""
    folder = tmp_path / "Comfy UI تجربة"
    folder.mkdir()
    (folder / "main.py").write_text(
        """import argparse
import json
import signal
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int)
parser.add_argument("--child", action="store_true")
parser.add_argument("--ignore-stop", action="store_true")
args, unknown = parser.parse_known_args()
if args.ignore_stop:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
if args.child:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
    Path("child.pid").write_text(str(child.pid), encoding="utf-8")
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"system": {"os": "nt", "python_version": "3.11"},
                                    "devices": []}).encode())
    def log_message(self, *args):
        pass
print("جاهز / Unicode log ready", flush=True)
try:
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever(poll_interval=0.1)
except KeyboardInterrupt:
    Path("graceful.txt").write_text("stopped", encoding="utf-8")
""",
        encoding="utf-8",
    )
    return Config(
        comfy_dir=str(folder),
        python_exe=sys.executable,
        port=free_port,
        startup_timeout=5,
        open_browser_on_start=False,
    )
