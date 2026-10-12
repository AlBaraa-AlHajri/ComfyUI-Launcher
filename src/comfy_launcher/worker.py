"""Standard-library bootstrap run by ComfyUI's own interpreter, never the frozen EXE."""

import _thread
import ctypes
import os
import runpy
import subprocess
import sys
import threading
import time
from pathlib import Path


def hide_subprocesses() -> None:
    """Keep Python-spawned custom-node helpers from flashing console windows."""
    original = subprocess.Popen

    class QuietPopen(original):
        def __init__(self, *args: object, **kwargs: object) -> None:
            # Apply only inside this child, preserving the launcher process. / داخل الخادم فقط.
            kwargs["creationflags"] = (
                int(kwargs.get("creationflags", 0)) | subprocess.CREATE_NO_WINDOW
            )
            super().__init__(*args, **kwargs)

    subprocess.Popen = QuietPopen


def shutdown_listener() -> None:
    """Translate the private stdin pipe into a cooperative KeyboardInterrupt."""
    # No public shutdown socket or console is needed. / لا نحتاج منفذ إيقاف أو نافذة أوامر.
    if os.name == "nt":
        import msvcrt
        from ctypes import wintypes as wt

        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.PeekNamedPipe.argtypes = [
            wt.HANDLE,
            ctypes.c_void_p,
            wt.DWORD,
            ctypes.c_void_p,
            ctypes.POINTER(wt.DWORD),
            ctypes.c_void_p,
        ]
        api.PeekNamedPipe.restype = wt.BOOL
        handle = msvcrt.get_osfhandle(sys.stdin.fileno())
        # A blocking CRT stdin read can deadlock NumPy DLL loading on Windows.
        # القراءة المحجوبة من stdin قد توقف تحميل مكتبات NumPy في Windows.
        while True:
            available = wt.DWORD()
            if not api.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
                break
            if available.value:
                os.read(sys.stdin.fileno(), min(available.value, 4096))
                break
            time.sleep(0.1)
    else:
        sys.stdin.readline()
    _thread.interrupt_main()


def main() -> None:
    """Wait for Job Object assignment, then execute unmodified ComfyUI as __main__."""
    if sys.stdin.readline().strip() != "start":
        return
    if os.name == "nt":
        hide_subprocesses()
    main_file = Path(sys.argv[1]).resolve()
    sys.argv = [str(main_file), *sys.argv[2:]]
    sys.path.insert(0, str(main_file.parent))
    os.chdir(main_file.parent)
    threading.Thread(target=shutdown_listener, daemon=True).start()
    try:
        runpy.run_path(str(main_file), run_name="__main__")
    except KeyboardInterrupt:
        print("ComfyUI Launcher: cooperative shutdown complete.", flush=True)
    finally:
        # Flush logs before the parent checks process completion. / تفريغ السجل قبل إنهاء العملية.
        sys.stdout.flush()
        sys.stderr.flush()
        time.sleep(0.02)


if __name__ == "__main__":
    main()
