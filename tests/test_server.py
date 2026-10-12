"""Real hidden subprocess tests plus HTTP identity and startup failure regression cases."""

import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import psutil
import pytest

from comfy_launcher.config import Config
from comfy_launcher.server import (
    PortBusy,
    Server,
    StartupError,
    build_args,
    build_command,
    health_check,
    next_free_port,
    port_available,
)


def test_managed_flags_and_safe_command(config: Config) -> None:
    config.extra_args = [
        "--lowvram",
        "--auto-launch",
        "--port",
        "9000",
        "--port=9001",
        "--disable-auto-launch",
        "--output-directory",
        "نتائج with spaces",
    ]
    args = build_args(config)
    assert args.count("--port") == 1
    assert args.count("--disable-auto-launch") == 1
    assert "--auto-launch" not in args
    assert args[-3:] == ["--port", str(config.port), "--disable-auto-launch"]
    command = build_command(config)
    assert command[0] == config.python_exe
    assert str(Path(config.comfy_dir) / "main.py") in command
    assert "نتائج with spaces" in command


def test_busy_port_and_next_free(free_port: int) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", free_port))
        sock.listen()
        assert not port_available(free_port)
        alternative = next_free_port(free_port)
        assert alternative != free_port and port_available(alternative)
    assert port_available(free_port)


@pytest.mark.parametrize("payload", [{}, {"system": {}, "devices": []}, [1], "not JSON"])
def test_unrelated_http_200_is_not_comfyui(free_port: int, payload: object) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def log_message(self, *args: object) -> None:
            pass

    with HTTPServer(("127.0.0.1", free_port), Handler) as http:
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            assert not health_check(free_port)
        finally:
            http.shutdown()
            thread.join()


def test_real_start_graceful_stop_and_unicode_logs(config: Config) -> None:
    server = Server()
    statuses = []
    try:
        assert server.start(config, statuses.append)
        assert statuses == ["checking", "starting", "waiting"]
        assert health_check(config.port)
        pid = server.process.pid
    finally:
        server.stop(timeout=3)
    assert not psutil.pid_exists(pid)
    assert (Path(config.comfy_dir) / "graceful.txt").is_file()
    assert "جاهز" in server.log_path.read_text("utf-8")
    assert port_available(config.port)


def test_attach_does_not_spawn_or_stop_existing_server(config: Config) -> None:
    owner, attached = Server(), Server()
    try:
        assert owner.start(config, lambda _: None)
        assert attached.start(config, lambda _: None)
        assert attached.attached and attached.process is None
        attached.stop()
        assert health_check(config.port)
    finally:
        owner.stop(timeout=2)


def test_descendants_are_reaped(config: Config) -> None:
    config.extra_args = ["--child"]
    server = Server()
    try:
        assert server.start(config, lambda _: None)
        child_pid = int((Path(config.comfy_dir) / "child.pid").read_text("utf-8"))
        assert psutil.pid_exists(child_pid)
    finally:
        server.stop(timeout=0.5)
    assert not psutil.pid_exists(child_pid)


def test_uncooperative_process_is_forced_closed(config: Config) -> None:
    config.extra_args = ["--ignore-stop"]
    server = Server()
    try:
        assert server.start(config, lambda _: None)
        pid = server.process.pid
    finally:
        server.stop(timeout=0.2)
    assert not psutil.pid_exists(pid)
    assert port_available(config.port)


def test_early_exit_contains_log_tail(config: Config) -> None:
    Path(config.comfy_dir, "main.py").write_text(
        'print("startup failure سبب الفشل", flush=True)\nraise SystemExit(7)\n', encoding="utf-8"
    )
    server = Server()
    with pytest.raises(StartupError, match="startup failure"):
        server.start(config, lambda _: None)
    assert server.process is None and server.job is None


def test_timeout_cleans_process(config: Config) -> None:
    Path(config.comfy_dir, "main.py").write_text(
        "import time\nwhile True: time.sleep(0.05)\n", encoding="utf-8"
    )
    server = Server()
    with pytest.raises(StartupError, match="exceeded"):
        server.start(config, lambda _: None)
    assert server.process is None and server.job is None


@pytest.mark.skipif(os.name != "nt", reason="Windows CRT and pipe locking")
def test_control_listener_does_not_hold_crt_stdio_lock(config: Config) -> None:
    script = Path(config.comfy_dir, "main.py")
    script.write_text(
        'import ctypes, time\ntime.sleep(0.2)\nctypes.CDLL("ucrtbase")._flushall()\n'
        + script.read_text("utf-8"),
        encoding="utf-8",
    )
    server = Server()
    try:
        assert server.start(config, lambda _: None)
    finally:
        server.stop(timeout=2)


def test_cancel_before_spawn(config: Config) -> None:
    server = Server()
    server.cancel.set()
    assert not server.start(config, lambda _: None)
    assert server.process is None


def test_port_conflict_does_not_spawn(config: Config) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", config.port))
        sock.listen()
        server = Server()
        with pytest.raises(PortBusy):
            server.start(config, lambda _: None)
        assert server.process is None


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Objects")
def test_job_close_kills_descendants(config: Config) -> None:
    config.extra_args = ["--child"]
    server = Server()
    try:
        assert server.start(config, lambda _: None)
        child = psutil.Process(int(Path(config.comfy_dir, "child.pid").read_text("utf-8")))
        server.job.close()
        _, alive = psutil.wait_procs([child], timeout=4)
        assert not alive
    finally:
        server.stop(timeout=0.2)
