"""Windows session-local activation, without importing Qt in a second process."""
from __future__ import annotations

import ctypes
from ctypes import wintypes


class WindowsInstance:
    def __init__(self, name: str = "Local\\FShot.Desktop.v1") -> None:
        self._handles = []
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        for function, arguments, result in (
            ("CreateEventW", [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
            ("CreateMutexW", [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
            ("SetEvent", [wintypes.HANDLE], wintypes.BOOL),
            ("WaitForSingleObject", [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            ("CloseHandle", [wintypes.HANDLE], wintypes.BOOL),
        ):
            native = getattr(self._kernel, function)
            native.argtypes = arguments
            native.restype = result
        try:
            # Create the event first so concurrent launches cannot lose activation.
            self._event = self._kernel.CreateEventW(None, False, False, name + ".activate")
            self._keep(self._event)
            mutex = self._kernel.CreateMutexW(None, False, name + ".mutex")
            existed = ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
            self._keep(mutex)
            self.primary = not existed
        except BaseException:
            self.close()
            raise

    def _keep(self, handle) -> None:
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self._handles.append(handle)

    def activate(self) -> None:
        # Transfer foreground permission from the user-launched second process.
        ctypes.windll.user32.AllowSetForegroundWindow(wintypes.DWORD(-1))
        if not self._kernel.SetEvent(self._event):
            raise ctypes.WinError(ctypes.get_last_error())

    def activation_pending(self) -> bool:
        result = self._kernel.WaitForSingleObject(self._event, 0)
        if result == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        return result == 0

    def close(self) -> None:
        for handle in reversed(self._handles):
            self._kernel.CloseHandle(handle)
        self._handles.clear()
