from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QApplication

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
VK_SPACE = 0x20
VK_LWIN = 0x5B
VK_RWIN = 0x5C
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WH_KEYBOARD_LL = 13

HOTKEY_ID = 0x5B0D


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)


class _HotkeyEventFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type, message):
        try:
            if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
                msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    self._callback()
        except (TypeError, ValueError):
            pass
        return False


class _KeyboardHookThread(threading.Thread):
    def __init__(self, callback, on_error, on_win_release):
        super().__init__(daemon=True, name="SpotlightGlobalHotkey")
        self._callback = callback
        self._on_error = on_error
        self._on_win_release = on_win_release
        self._ready = threading.Event()
        self._thread_id = 0
        self._hook = None
        self._proc = None
        self._win_down = False
        self._space_down = False
        self._swallow_space = False
        self._swallow_win_up = False
        self._ok = False

    def start_with_timeout(self) -> bool:
        super().start()
        self._ready.wait(2.0)
        return self._ok

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)

    def run(self) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,
            HOOKPROC,
            wintypes.HINSTANCE,
            wintypes.DWORD,
        ]
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.CallNextHookEx.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short

        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        def low_level_proc(n_code, w_param, l_param):
            try:
                if n_code == 0:
                    kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    is_down = w_param in (WM_KEYDOWN, WM_SYSKEYDOWN)
                    is_up = w_param in (WM_KEYUP, WM_SYSKEYUP)

                    if kb.vkCode in (VK_LWIN, VK_RWIN):
                        if is_up and self._swallow_win_up:
                            self._swallow_win_up = False
                            self._win_down = False
                            self._on_win_release(kb.vkCode)
                            return 1
                        self._win_down = is_down
                        if is_down:
                            self._swallow_win_up = False
                    elif kb.vkCode == VK_SPACE:
                        if is_down and not self._space_down:
                            self._space_down = True
                            win_down = (
                                self._win_down
                                or bool(user32.GetAsyncKeyState(VK_LWIN) & 0x8000)
                                or bool(user32.GetAsyncKeyState(VK_RWIN) & 0x8000)
                            )
                            if win_down:
                                self._swallow_space = True
                                self._swallow_win_up = True
                                self._callback()
                        elif is_up:
                            self._space_down = False

                        if self._swallow_space:
                            if is_up:
                                self._swallow_space = False
                            return 1
            except Exception as exc:  # pragma: no cover - defensive hook guard
                self._on_error(exc)

            return user32.CallNextHookEx(self._hook, n_code, w_param, l_param)

        try:
            self._proc = HOOKPROC(low_level_proc)
            self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, None, 0)
            if not self._hook:
                self._on_error(ctypes.get_last_error())
                return
            self._ok = True
            self._ready.set()

            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            if self._hook:
                user32.UnhookWindowsHookEx(self._hook)
            self._ready.set()


class HotkeyManager(QObject):
    activated = Signal()
    released = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode: str | None = None
        self.error: str | None = None
        self._filter: _HotkeyEventFilter | None = None
        self._hook: _KeyboardHookThread | None = None
        self.released.connect(self._unstick_win)
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._user32.RegisterHotKey.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            wintypes.UINT,
            wintypes.UINT,
        ]
        self._user32.RegisterHotKey.restype = wintypes.BOOL
        self._user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        self._user32.keybd_event.argtypes = [
            wintypes.BYTE,
            wintypes.BYTE,
            wintypes.DWORD,
            ctypes.c_size_t,
        ]
        self._user32.keybd_event.restype = None

    def _fire(self) -> None:
        self.activated.emit()

    def _hook_error(self, error) -> None:
        self.error = f"{self.error or ''} {error}".strip()

    def _unstick_win(self, vk: int) -> None:
        # A tecla Win física foi engolida; uma soltura sintética faria o
        # Iniciar abrir. Intercala uma tecla inócua para virar um combo.
        keyev = self._user32.keybd_event
        keyev(0x87, 0, 0, 0)
        keyev(0x87, 0, 0x0002, 0)
        keyev(vk, 0, 0x0002, 0)

    def start(self) -> bool:
        if self.mode:
            return True

        registered = bool(
            self._user32.RegisterHotKey(
                None, HOTKEY_ID, MOD_WIN | MOD_NOREPEAT, VK_SPACE
            )
        )
        if registered:
            self.mode = "register"
            self._filter = _HotkeyEventFilter(self._fire)
            app = QApplication.instance()
            if app is not None:
                app.installNativeEventFilter(self._filter)
            return True

        self.error = f"RegisterHotKey failed ({ctypes.get_last_error()})"

        hook = _KeyboardHookThread(self._fire, self._hook_error, self.released.emit)
        if hook.start_with_timeout():
            self._hook = hook
            self.mode = "hook"
            return True

        self.mode = None
        if not self.error:
            self.error = "keyboard hook unavailable"
        return False

    def stop(self) -> None:
        if self.mode == "register":
            try:
                self._user32.UnregisterHotKey(None, HOTKEY_ID)
            except OSError:
                pass
            app = QApplication.instance()
            if app is not None and self._filter is not None:
                app.removeNativeEventFilter(self._filter)
            self._filter = None
        elif self.mode == "hook" and self._hook is not None:
            self._hook.stop()
            self._hook = None
        self.mode = None
