"""Windows named mutex and activation event, with correctly typed native handles."""

import ctypes
import hashlib
from ctypes import wintypes as wt

from .paths import app_data


class SingleInstance:
    """Hold a per-user mutex and signal the first instance from duplicate invocations."""

    def __init__(self) -> None:
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        for name, args, result in (
            ("CreateMutexW", [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR], wt.HANDLE),
            ("CreateEventW", [ctypes.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR], wt.HANDLE),
            ("SetEvent", [wt.HANDLE], wt.BOOL),
            ("WaitForSingleObject", [wt.HANDLE, wt.DWORD], wt.DWORD),
            ("CloseHandle", [wt.HANDLE], wt.BOOL),
        ):
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result
        digest = hashlib.sha256(str(app_data()).casefold().encode("utf-8")).hexdigest()[:24]
        name = "Local\\ComfyUI-Launcher-" + digest
        # Create the event first, removing the duplicate-start race. / إنشاء الحدث أولاً يمنع السباق.
        self.event = self.api.CreateEventW(None, False, False, name + "-activate")
        if not self.event:
            raise ctypes.WinError(ctypes.get_last_error())
        self.mutex = self.api.CreateMutexW(None, False, name)
        error = ctypes.get_last_error()
        if not self.mutex:
            self.api.CloseHandle(self.event)
            raise ctypes.WinError(error)
        self.primary = error != 183

    def activate(self) -> None:
        """Ask the primary UI to focus its browser, without spawning a second server."""
        if not self.api.SetEvent(self.event):
            raise ctypes.WinError(ctypes.get_last_error())

    def requested(self) -> bool:
        """Consume an activation request without blocking Tk."""
        return self.api.WaitForSingleObject(self.event, 0) == 0

    def close(self) -> None:
        """Close owned native handles; the mutex disappears with the final handle."""
        for name in ("mutex", "event"):
            handle = getattr(self, name, None)
            if handle:
                self.api.CloseHandle(handle)
                setattr(self, name, None)
