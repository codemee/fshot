"""Windows delayed capture with a non-activating mirror and mouse input proxy."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import math
import threading
import time

from PySide6.QtCore import QEventLoop, QObject, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from fshot.capture import CaptureRect, _window_rect


class PreviewNotifications(QObject):
    ready = Signal()


class PreviewFrames:
    """Capture off the UI thread with a bounded, latest-frame-only mailbox."""

    def __init__(self, display: CaptureRect, size: QSize, dpr: float):
        self.monitor = {"left": display.left, "top": display.top,
                        "width": display.width, "height": display.height}
        self.size, self.dpr = QSize(size), dpr
        self.stopped = threading.Event()
        self.lock = threading.Lock()
        self.latest = None
        self.failure = None
        self.notifications = PreviewNotifications()
        self.notification_pending = False
        self.thread = threading.Thread(target=self._run, name="fshot-preview", daemon=True)

    def _frame(self, capture):
        shot = capture.grab(self.monitor)
        # MSS already supplies BGRA. Avoid Pillow conversions and scale only once.
        image = QImage(shot.raw, shot.width, shot.height, shot.width*4, QImage.Format.Format_RGB32)
        if image.size() == self.size:
            image = image.copy()
        else:
            image = image.scaled(self.size, Qt.AspectRatioMode.IgnoreAspectRatio,
                                 Qt.TransformationMode.FastTransformation)
        image.setDevicePixelRatio(self.dpr)
        return image

    def initial_frame(self):
        import mss

        with mss.mss() as capture:
            return self._frame(capture)

    def _run(self):
        import mss

        try:
            # MSS owns thread-local native handles; never share them with the UI.
            with mss.mss() as capture:
                while not self.stopped.is_set():
                    started = time.monotonic()
                    image = self._frame(capture)
                    with self.lock:
                        self.latest = image
                        notify = not self.notification_pending
                        self.notification_pending = True
                    if notify:
                        self.notifications.ready.emit()
                    self.stopped.wait(max(0, 1/30-(time.monotonic()-started)))
        except Exception as exc:
            with self.lock:
                self.failure = exc
            self.notifications.ready.emit()

    def take_latest(self):
        with self.lock:
            self.notification_pending = False
            if self.failure is not None:
                raise self.failure
            image, self.latest = self.latest, None
            return QImage(image) if image is not None else None

    def stop(self):
        self.stopped.set()
        if self.thread.ident is not None:
            self.thread.join(timeout=1)


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class _HOOK_DATA(ctypes.Structure):
    _fields_ = [("pt", _POINT), ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("extra", ctypes.c_size_t)]


class _MOUSE_INPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("extra", ctypes.c_size_t)]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mouse", _MOUSE_INPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("data", _INPUT_UNION)]


class MouseProxy:
    """Keep the real pointer on the virtual display; paint its mirror locally.

    Physical mouse motion is translated using the mirror's scale. Injected
    events are never recaptured. The hook exists only for the bounded countdown.
    """

    def __init__(self, display: CaptureRect, desktop: CaptureRect, view, initial: CaptureRect):
        import win32api

        self.display, self.desktop, self.view = display, desktop, view
        self.original_cursor = win32api.GetCursorPos()
        self.position = [initial.left + initial.width/2, initial.top + initial.height/2]
        self.anchor = tuple(self.position)
        self.pending = []
        self.pressed = set()
        self.failure = None
        self.hook = None
        self.scale = max(0.01, view.image_area().width()*view.devicePixelRatioF()/display.width)
        self.user32 = ctypes.windll.user32
        self.callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t)
        self.callback = self.callback_type(self._mouse_event)
        self.user32.SetWindowsHookExW.argtypes = [ctypes.c_int, self.callback_type, ctypes.c_void_p, wintypes.DWORD]
        self.user32.SetWindowsHookExW.restype = ctypes.c_void_p
        self.user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t]
        self.user32.CallNextHookEx.restype = ctypes.c_ssize_t
        self.user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        self.user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
        self.user32.SendInput.restype = wintypes.UINT
        self.timer = QTimer(view)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(4)
        self.timer.timeout.connect(self.flush)

    def start(self):
        kernel = ctypes.windll.kernel32
        kernel.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel.GetModuleHandleW.restype = ctypes.c_void_p
        self.hook = self.user32.SetWindowsHookExW(14, self.callback, kernel.GetModuleHandleW(None), 0)
        if not self.hook:
            raise ctypes.WinError()
        self._send(0x0001 | 0x8000 | 0x4000, 0, self.position)
        self.view.set_pointer(tuple(self.position))
        self.timer.start()

    def _mouse_event(self, code, message, pointer):
        if code != 0:
            return self.user32.CallNextHookEx(self.hook, code, message, pointer)
        data = ctypes.cast(pointer, ctypes.POINTER(_HOOK_DATA)).contents
        if data.flags & 1:  # LLMHF_INJECTED: do not intercept our own SendInput.
            return self.user32.CallNextHookEx(self.hook, code, message, pointer)
        try:
            if message == 0x0200:  # WM_MOUSEMOVE
                self.position[0] += (data.pt.x-self.anchor[0])/self.scale
                self.position[1] += (data.pt.y-self.anchor[1])/self.scale
                self.position[0] = min(self.display.left+self.display.width-1, max(self.display.left, self.position[0]))
                self.position[1] = min(self.display.top+self.display.height-1, max(self.display.top, self.position[1]))
                self.anchor = (data.pt.x, data.pt.y)
                # Coalesce movement, but preserve button/wheel ordering.
                event = (0x0001 | 0x8000 | 0x4000, 0, tuple(self.position))
                if self.pending and self.pending[-1][0] == event[0]:
                    self.pending[-1] = event
                else:
                    self.pending.append(event)
            else:
                buttons = {0x0201: 0x0002, 0x0202: 0x0004,
                           0x0204: 0x0008, 0x0205: 0x0010,
                           0x0207: 0x0020, 0x0208: 0x0040,
                           0x020B: 0x0080, 0x020C: 0x0100}
                flags = buttons.get(message)
                extra = (data.mouseData >> 16) & 0xFFFF
                if message == 0x020A:
                    flags, extra = 0x0800, ctypes.c_short(extra).value & 0xFFFFFFFF
                elif message == 0x020E:
                    flags, extra = 0x1000, ctypes.c_short(extra).value & 0xFFFFFFFF
                elif message not in (0x020B, 0x020C):
                    extra = 0
                if flags is not None:
                    self.pending.append((flags, extra, tuple(self.position)))
                    # Flush on the next event-loop turn, outside the native hook.
                    # Keep earlier movement before clicks and wheel events.
                    QTimer.singleShot(0, self.flush)
        except Exception as exc:
            self.failure = exc
        return 1  # Physical mouse input is redirected until countdown ends.

    def _send(self, flags, extra, position):
        item = _INPUT()
        mouse = item.data.mouse
        mouse.dx = round((position[0]-self.desktop.left)*65535/max(1, self.desktop.width-1))
        mouse.dy = round((position[1]-self.desktop.top)*65535/max(1, self.desktop.height-1))
        mouse.flags = flags
        mouse.mouseData = extra
        if self.user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(item)) != 1:
            raise RuntimeError(self.view.tr("virtual_interactive_input"))
        if flags & 0x0001:
            self.anchor = (round(position[0]), round(position[1]))

    def flush(self):
        if not self.pending:
            return
        events, self.pending = self.pending, []
        try:
            for flags, extra, position in events:
                self._send(flags, extra, position)
                if flags in (0x0002, 0x0008, 0x0020, 0x0080):
                    self.pressed.add((flags, extra))
                elif flags in (0x0004, 0x0010, 0x0040, 0x0100):
                    self.pressed.discard((flags//2, extra))
            self.view.set_pointer(tuple(self.position))
        except Exception as exc:
            self.failure = exc

    def stop(self):
        import win32api

        self.timer.stop()
        try:
            self.timer.timeout.disconnect(self.flush)
        except (RuntimeError, TypeError):
            pass
        if self.hook:
            self.user32.UnhookWindowsHookEx(self.hook)
            self.hook = None
        self.pending.clear()
        try:
            for flags, extra in self.pressed:
                self._send(flags*2, extra, self.position)
        finally:
            self.pressed.clear()
            win32api.SetCursorPos(self.original_cursor)


class InteractiveMirror(QWidget):
    def __init__(self, display: CaptureRect, screen, tr):
        super().__init__()
        self.display, self.tr = display, tr
        self.image = None
        self.pointer = None
        self.remaining = 0
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.winId()
        self.windowHandle().setScreen(screen)
        geometry = screen.availableGeometry()
        self.resize(max(200, geometry.width()-64), max(160, geometry.height()-64))
        self.move(geometry.center()-self.rect().center())
        import win32con
        import win32gui

        hwnd = int(self.winId())
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | 0x08000000)  # WS_EX_NOACTIVATE

    def image_area(self):
        available = self.rect().adjusted(12, 64, -12, -12)
        scale = min(available.width()/self.display.width, available.height()/self.display.height)
        width, height = round(self.display.width*scale), round(self.display.height*scale)
        return QRect(available.center().x()-width//2, available.center().y()-height//2, width, height)

    def set_pointer(self, position):
        if self.pointer == position:
            return
        area = self.image_area()
        for point in (self.pointer, position):
            if point is not None:
                x = area.left() + round((point[0]-self.display.left)*area.width()/self.display.width)
                y = area.top() + round((point[1]-self.display.top)*area.height()/self.display.height)
                self.update(QRect(x-10, y-10, 21, 21))
        self.pointer = position

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#202124"))
        if event.rect().top() < 64:
            painter.setPen(QColor("#ffffff"))
            font = QFont()
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(self.rect().adjusted(12, 8, -12, -8), Qt.AlignmentFlag.AlignTop,
                             self.tr("virtual_interactive_hint", seconds=self.remaining))
        area = self.image_area()
        if self.image is not None:
            painter.drawImage(area, self.image)
        if self.pointer is not None:
            x = area.left() + round((self.pointer[0]-self.display.left)*area.width()/self.display.width)
            y = area.top() + round((self.pointer[1]-self.display.top)*area.height()/self.display.height)
            painter.setPen(QPen(QColor("#000000"), 4))
            painter.drawLine(x-7, y, x+7, y)
            painter.drawLine(x, y-7, x, y+7)
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawLine(x-7, y, x+7, y)
            painter.drawLine(x, y-7, x, y+7)


def _capture_bounds(hwnd, display: CaptureRect, baseline) -> CaptureRect:
    """Include menus and newly opened owned popups outside the main frame."""
    import win32con
    import win32gui
    import win32process

    owner = _window_rect(hwnd)
    if owner is None:
        raise RuntimeError("The target window is no longer visible.")
    rects = [owner]
    _thread, process = win32process.GetWindowThreadProcessId(hwnd)

    def visit(candidate, _):
        try:
            if candidate == hwnd or not win32gui.IsWindowVisible(candidate):
                return True
            _candidate_thread, candidate_process = win32process.GetWindowThreadProcessId(candidate)
            if candidate_process != process:
                return True
            menu = win32gui.GetClassName(candidate) == "#32768"
            owned = win32gui.GetAncestor(candidate, win32con.GA_ROOTOWNER) == hwnd
            if menu or (owned and candidate not in baseline):
                bounds = _window_rect(candidate)
                if bounds is not None and bounds.intersect(display) is not None:
                    rects.append(bounds)
        except Exception:
            pass
        return True

    win32gui.EnumWindows(visit, None)
    left, top = min(r.left for r in rects), min(r.top for r in rects)
    right = max(r.left+r.width for r in rects)
    bottom = max(r.top+r.height for r in rects)
    bounds = CaptureRect(left, top, right-left, bottom-top).intersect(display)
    if bounds is None:
        raise RuntimeError("The target window left the virtual display.")
    return bounds


def delayed_interactive_capture(service, display, target, settings, tr):
    import win32api
    import win32gui
    from fshot.virtual_screen import resolve_display

    hwnd = target.owner_hwnd
    point = QCursor.pos()
    screen = QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()
    if screen is None:
        raise RuntimeError(tr("virtual_interactive_screen"))
    real_monitor = win32api.MonitorFromPoint(win32api.GetCursorPos(), 2)
    if win32api.GetMonitorInfo(real_monitor)["Device"] == display.device:
        raise RuntimeError(tr("virtual_interactive_screen"))
    baseline = set()
    def remember_visible(candidate, _):
        if win32gui.IsWindowVisible(candidate):
            baseline.add(candidate)
        return True

    win32gui.EnumWindows(remember_visible, None)
    view = InteractiveMirror(display.rect, screen, tr)
    owner = _window_rect(hwnd)
    if owner is None:
        view.deleteLater()
        raise RuntimeError(tr("virtual_control_unavailable"))
    mouse = MouseProxy(display.rect, service._fullscreen_rect(), view, owner)
    dpr = view.devicePixelRatioF()
    area = view.image_area()
    frames = PreviewFrames(display.rect, QSize(round(area.width()*dpr), round(area.height()*dpr)), dpr)
    loop = QEventLoop()
    timer = QTimer(view)
    timer.setTimerType(Qt.TimerType.PreciseTimer)
    timer.setInterval(16)
    result, failures = [], []
    started = None
    last_display_check = 0
    last_target_check = 0
    closed = False

    def present_latest():
        if closed:
            return
        try:
            image = frames.take_latest()
            if image is not None:
                view.image = image
                view.update(view.image_area())
        except Exception as exc:
            failures.append(exc)
            loop.quit()

    def refresh():
        nonlocal last_display_check, last_target_check
        try:
            if mouse.failure is not None:
                raise mouse.failure
            if win32api.GetAsyncKeyState(0x1B) & 0x8000:
                loop.quit()
                return
            import win32con

            foreground = win32gui.GetForegroundWindow()
            if foreground != hwnd and win32gui.GetAncestor(foreground, win32con.GA_ROOTOWNER) != hwnd:
                raise RuntimeError(tr("virtual_interactive_focus"))
            now = time.monotonic()
            remaining = settings.delay_seconds-(now-started)
            if now-last_target_check >= 0.2 or remaining <= 0:
                if target.resolve() is None:
                    raise RuntimeError(tr("virtual_control_unavailable"))
                last_target_check = now
            if now-last_display_check >= 1 or remaining <= 0:
                resolve_display(display)
                last_display_check = now
            seconds = max(0, math.ceil(remaining))
            if seconds != view.remaining:
                view.remaining = seconds
                view.update(QRect(0, 0, view.width(), 64))
            if remaining <= 0:
                mouse.timer.stop()
                mouse.flush()
                if mouse.failure is not None:
                    raise mouse.failure
                frames.stop()
                rect = _capture_bounds(hwnd, display.rect, baseline)
                image = service._grab_rect(rect)
                if settings.include_cursor:
                    service._draw_cursor(image, rect)
                result.append(image)
                loop.quit()
                return
        except Exception as exc:
            failures.append(exc)
            loop.quit()

    timer.timeout.connect(refresh)
    frames.notifications.ready.connect(present_latest, Qt.ConnectionType.QueuedConnection)
    try:
        view.image = frames.initial_frame()
        view.remaining = math.ceil(settings.delay_seconds)
        view.show()
        QApplication.processEvents()
        if win32gui.GetForegroundWindow() != hwnd:
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception as exc:
                raise RuntimeError(tr("virtual_interactive_focus")) from exc
        if win32gui.GetForegroundWindow() != hwnd:
            raise RuntimeError(tr("virtual_interactive_focus"))
        mouse.start()
        started = time.monotonic()
        frames.thread.start()
        timer.start()
        loop.exec()
    finally:
        closed = True
        timer.stop()
        timer.timeout.disconnect(refresh)
        try:
            mouse.stop()
        finally:
            frames.stop()
            frames.notifications.ready.disconnect(present_latest)
            view.hide()
            view.image = None
            view.deleteLater()
    if failures:
        raise failures[0]
    return result[0] if result else None
