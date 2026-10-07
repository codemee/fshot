from __future__ import annotations

import sys
import time
import math
import os
from collections.abc import Callable
from ctypes import POINTER, Structure, byref, c_int, c_uint, c_void_p, memset, sizeof, string_at
from ctypes.wintypes import BOOL, BYTE, DWORD, HBITMAP, HDC, HGDIOBJ, HICON, HWND, LONG, RECT, WORD
from dataclasses import dataclass

import mss
from PIL import Image, ImageGrab
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from fshot.qt_image import pil_to_qimage
from fshot.settings import CaptureMode, CaptureSettings

if sys.platform == "win32":
    from ctypes import windll

    import win32api
    import win32con
    import win32gui
    import win32process
    DWMWA_EXTENDED_FRAME_BOUNDS = 9
    CURSOR_SHOWING = 1
    DI_NORMAL = 3
    BI_RGB = 0
    DIB_RGB_COLORS = 0
else:  # pragma: no cover - platform branch
    windll = None
    win32api = None
    win32con = None
    win32gui = None
    win32process = None
    DWMWA_EXTENDED_FRAME_BOUNDS = None
    CURSOR_SHOWING = None
    DI_NORMAL = None
    BI_RGB = None
    DIB_RGB_COLORS = None


class BITMAPINFOHEADER(Structure):
    _fields_ = [
        ("biSize", DWORD),
        ("biWidth", LONG),
        ("biHeight", LONG),
        ("biPlanes", WORD),
        ("biBitCount", WORD),
        ("biCompression", DWORD),
        ("biSizeImage", DWORD),
        ("biXPelsPerMeter", LONG),
        ("biYPelsPerMeter", LONG),
        ("biClrUsed", DWORD),
        ("biClrImportant", DWORD),
    ]


class RGBQUAD(Structure):
    _fields_ = [
        ("rgbBlue", BYTE),
        ("rgbGreen", BYTE),
        ("rgbRed", BYTE),
        ("rgbReserved", BYTE),
    ]


class BITMAPINFO(Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]


class ICONINFO(Structure):
    _fields_ = [
        ("fIcon", BOOL),
        ("xHotspot", DWORD),
        ("yHotspot", DWORD),
        ("hbmMask", HBITMAP),
        ("hbmColor", HBITMAP),
    ]


class GUITHREADINFO(Structure):
    _fields_ = [
        ("cbSize", DWORD),
        ("flags", DWORD),
        ("hwndActive", HWND),
        ("hwndFocus", HWND),
        ("hwndCapture", HWND),
        ("hwndMenuOwner", HWND),
        ("hwndMoveSize", HWND),
        ("hwndCaret", HWND),
        ("rcCaret", RECT),
    ]


_UIA_AUTOMATION = None
_UIA_POINT = None


def _cancel_windows_menu_mode() -> None:
    """End the foreground thread's live native menu after its snapshot is saved."""
    if sys.platform != "win32" or win32gui is None or win32process is None or windll is None:
        return
    try:
        foreground = win32gui.GetForegroundWindow()
        if not foreground:
            return
        thread_id, _process_id = win32process.GetWindowThreadProcessId(foreground)
        info = GUITHREADINFO()
        info.cbSize = sizeof(GUITHREADINFO)
        candidates: list[int] = []
        if windll.user32.GetGUIThreadInfo(thread_id, byref(info)):
            candidates.extend((info.hwndMenuOwner, info.hwndActive))
        candidates.append(foreground)
        seen: set[int] = set()
        for candidate in candidates:
            hwnd = int(candidate or 0)
            if not hwnd or hwnd in seen:
                continue
            seen.add(hwnd)
            win32gui.SendMessageTimeout(
                hwnd,
                win32con.WM_CANCELMODE,
                0,
                0,
                win32con.SMTO_ABORTIFHUNG,
                100,
            )
    except Exception:
        # Some elevated or protected applications reject cross-process window
        # queries. Selection can still continue with the frozen overlay.
        return


@dataclass(frozen=True)
class CaptureRect:
    left: int
    top: int
    width: int
    height: int

    @classmethod
    def from_qrect(cls, rect: QRect) -> "CaptureRect":
        normalized = rect.normalized()
        return cls(normalized.x(), normalized.y(), normalized.width(), normalized.height())

    @property
    def is_empty(self) -> bool:
        return self.width <= 0 or self.height <= 0

    def to_mss(self) -> dict[str, int]:
        return {"left": self.left, "top": self.top, "width": self.width, "height": self.height}

    def intersect(self, other: "CaptureRect") -> "CaptureRect | None":
        left = max(self.left, other.left)
        top = max(self.top, other.top)
        right = min(self.left + self.width, other.left + other.width)
        bottom = min(self.top + self.height, other.top + other.height)
        if right <= left or bottom <= top:
            return None
        return CaptureRect(left, top, right - left, bottom - top)


@dataclass
class WindowCaptureTarget:
    rect: CaptureRect
    resolver: Callable[[], CaptureRect | None]
    owner_hwnd: int | None = None
    is_window: bool = False
    source_hwnd: int | None = None

    def resolve(self) -> CaptureRect | None:
        try:
            rect = self.resolver()
        except Exception:
            return None
        return rect if rect is not None and not rect.is_empty else None


@dataclass(frozen=True)
class _LastCapture:
    mode: CaptureMode
    rect: CaptureRect | None = None
    window_target: WindowCaptureTarget | None = None


@dataclass(frozen=True)
class _FrozenDesktop:
    rect: CaptureRect
    image: Image.Image
    targets: tuple[WindowCaptureTarget, ...] = ()
    windows: tuple[WindowCaptureTarget, ...] = ()

    def crop(self, rect: CaptureRect) -> Image.Image | None:
        clipped = rect.intersect(self.rect)
        if clipped is None or clipped.is_empty:
            return None
        left = clipped.left - self.rect.left
        top = clipped.top - self.rect.top
        return self.image.crop((left, top, left + clipped.width, top + clipped.height))


class RegionSelector(QWidget):
    def __init__(self, frozen_desktop: Image.Image | None = None) -> None:
        super().__init__(None)
        self.start: QPoint | None = None
        self.end: QPoint | None = None
        self.selected_rect: QRect | None = None
        self.cancelled = False
        self.native_rect: CaptureRect | None = None
        self.native_desktop: QRect | None = None
        self.peers: list[RegionSelector] = [self]
        self.frozen_desktop = pil_to_qimage(frozen_desktop) if frozen_desktop is not None else None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setGeometry(_virtual_screen_rect())

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        if self.frozen_desktop is not None:
            painter.drawImage(self.rect(), self.frozen_desktop)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))
        if self.start and self.end:
            if self.native_rect is not None:
                bounds = self.native_rect
                def local(point):
                    return QPoint(
                        round((point.x()-bounds.left) * self.width()/bounds.width),
                        round((point.y()-bounds.top) * self.height()/bounds.height),
                    )
                rect = QRect(local(self.start), local(self.end)).normalized()
            else:
                rect = QRect(self.mapFromGlobal(self.start), self.mapFromGlobal(self.end)).normalized()
            if self.frozen_desktop is None:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                painter.fillRect(rect, QColor(0, 0, 0, 0))
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            else:
                painter.save()
                painter.setClipRect(rect)
                painter.drawImage(self.rect(), self.frozen_desktop)
                painter.restore()
            painter.setPen(QPen(QColor("#ff922b"), 2))
            painter.drawRect(rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.start = self._event_point(event)
            self.end = self.start
            self._sync_selection()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.start:
            self.end = self._event_point(event)
            self._sync_selection()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.start:
            self.end = self._event_point(event)
            self.selected_rect = QRect(self.start, self.end).normalized().intersected(
                self.native_desktop if self.native_desktop is not None else self.geometry()
            )
            self._finish_selection()

    def _event_point(self, event: QMouseEvent) -> QPoint:
        if self.native_rect is not None and win32api is not None:
            return QPoint(*win32api.GetCursorPos())
        return event.globalPosition().toPoint()

    def _sync_selection(self) -> None:
        for peer in self.peers:
            peer.start, peer.end = self.start, self.end
            peer.update()

    def _finish_selection(self) -> None:
        for peer in self.peers:
            peer.selected_rect = self.selected_rect
            peer.cancelled = self.cancelled
            peer.close()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled = True
            self._finish_selection()

    def poll(self) -> None:
        if _escape_pressed():
            self.cancelled = True
            self._finish_selection()
        elif self.native_rect is not None and self.start is not None:
            # The pressed overlay owns mouse capture even when dragging to
            # another monitor. Use native coordinates for all peer overlays.
            self.end = QPoint(*win32api.GetCursorPos())
            self._sync_selection()


class WindowSelector(QWidget):
    def __init__(
        self,
        frozen_desktop: Image.Image | None = None,
        frozen_targets: tuple[WindowCaptureTarget, ...] = (),
        frozen_windows: tuple[WindowCaptureTarget, ...] = (),
    ) -> None:
        super().__init__(None)
        self.target_rect: CaptureRect | None = None
        self.target: WindowCaptureTarget | None = None
        self._last_query_at = 0.0
        self._uia_target_cache: dict[int, tuple[WindowCaptureTarget, ...]] = {}
        self.cancelled = False
        self.native_rect: CaptureRect | None = None
        self.peers: list[WindowSelector] = [self]
        self.frozen_desktop = pil_to_qimage(frozen_desktop) if frozen_desktop is not None else None
        self.frozen_targets = frozen_targets
        self.frozen_windows = frozen_windows
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setGeometry(_virtual_screen_rect())

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        if self.frozen_desktop is not None:
            painter.drawImage(self.rect(), self.frozen_desktop)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 40))
        if self.target_rect is not None:
            if self.native_rect is not None:
                screen = self.native_rect
                target = self.target_rect
                rect = QRect(
                    round((target.left-screen.left)*self.width()/screen.width),
                    round((target.top-screen.top)*self.height()/screen.height),
                    round(target.width*self.width()/screen.width),
                    round(target.height*self.height()/screen.height),
                )
            else:
                top_left = self.mapFromGlobal(QPoint(self.target_rect.left, self.target_rect.top))
                rect = QRect(top_left, QSize(self.target_rect.width, self.target_rect.height))
            rect = rect.intersected(self.rect().adjusted(1, 1, -2, -2))
            if self.frozen_desktop is not None:
                painter.save()
                painter.setClipRect(rect)
                painter.drawImage(self.rect(), self.frozen_desktop)
                painter.restore()
            painter.fillRect(rect, QColor(255, 146, 43, 35))
            pen_width = 3
            painter.setPen(QPen(QColor("#ff922b"), pen_width))
            # QPainter centers strokes on the rectangle edge. Inset the
            # outline so the selection indicator never spills outside the
            # selected window/control bounds.
            inset = (pen_width + 1) // 2
            outline = rect.adjusted(inset, inset, -inset, -inset)
            if not outline.isEmpty():
                painter.drawRect(outline)
        painter.setPen(QPen(QColor("#f8f9fa"), 2))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Click a window or control, Esc to cancel")

    def poll(self) -> None:
        if sys.platform == "darwin":
            self._poll_macos()
            return
        if win32api is None:
            return
        if win32api.GetAsyncKeyState(0x1B) & 0x8000:
            self.cancelled = True
            self._finish_selection()
            return
        point_tuple = win32api.GetCursorPos()
        point = QPoint(point_tuple[0], point_tuple[1])
        now = time.monotonic()
        if now - self._last_query_at >= 0.04:
            self._last_query_at = now
            target = self._target_at_point(point, use_uia=True)
            rect = target.rect if target is not None else None
            self.target = target
            if rect != self.target_rect:
                self.target_rect = rect
                self._sync_target()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            point = QPoint(*win32api.GetCursorPos()) if self.native_rect is not None else event.globalPosition().toPoint()
            self.target = self._target_at_point(point, use_uia=True)
            self.target_rect = self.target.rect if self.target is not None else None
            event.accept()
            self._finish_selection()
            return
        super().mouseReleaseEvent(event)

    def _sync_target(self) -> None:
        for peer in self.peers:
            peer.target, peer.target_rect = self.target, self.target_rect
            peer.update()

    def _finish_selection(self) -> None:
        for peer in self.peers:
            peer.target, peer.target_rect = self.target, self.target_rect
            peer.cancelled = self.cancelled
            peer.close()

    def _poll_macos(self) -> None:
        from AppKit import NSEvent
        import Quartz

        if Quartz.CGEventSourceKeyState(Quartz.kCGEventSourceStateCombinedSessionState, 53):
            self.cancelled = True
            self.close()
            return
        buttons = int(NSEvent.pressedMouseButtons())
        point = QCursor.pos()
        now = time.monotonic()
        if now - self._last_query_at >= 0.04:
            self._last_query_at = now
            target = self._target_at_point(point, use_uia=True)
            rect = target.rect if target is not None else None
            self.target = target
            if rect != self.target_rect:
                self.target_rect = rect
                self.update()
        if buttons & 1:
            return

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled = True
            self._finish_selection()

    def _target_at_point(
        self, point: QPoint, use_uia: bool, temporary: bool = False
    ) -> WindowCaptureTarget | None:
        if self.native_rect is not None and not _rect_contains(self.native_rect, point):
            for peer in self.peers:
                if peer.native_rect is not None and _rect_contains(peer.native_rect, point):
                    return peer._target_at_point(point, use_uia, temporary)
            return None
        if sys.platform == "darwin":
            from fshot.platforms.macos import capture_target_at_point, capture_target_bounds

            selected = capture_target_at_point(point.x(), point.y())
            if selected is None:
                return None
            bounds, native_target = selected
            return WindowCaptureTarget(
                CaptureRect(*bounds),
                lambda: _capture_rect_from_bounds(capture_target_bounds(native_target)),
            )
        surface = next((window for window in self.frozen_windows if _rect_contains(window.rect, point)), None)
        frozen = [
            target for target in self.frozen_targets if _rect_contains(target.rect, point)
            and (surface is None or (target.source_hwnd or target.owner_hwnd) == surface.owner_hwnd)
        ]
        if frozen:
            return min(frozen, key=lambda target: target.rect.width * target.rect.height)
        # Hit-test the window identities and Z-order saved with the image. A
        # popup disappearing on focus loss must not expose a different target.
        if self.frozen_windows:
            if surface is None:
                return None
            hwnd = surface.owner_hwnd
            if hwnd is None or surface.resolve() is None:
                return surface
            if hwnd not in self._uia_target_cache:
                self._uia_target_cache[hwnd] = _uia_targets_for_hwnd(hwnd)
            matches = [target for target in self._uia_target_cache[hwnd] if _rect_contains(target.rect, point)]
            return min(matches, key=lambda target: target.rect.width * target.rect.height) if matches else surface
        return _window_target_below_overlay(
            point,
            int(self.winId()),
            self._uia_target_cache if use_uia else None,
        )


class CountdownOverlay(QWidget):
    def __init__(self, seconds: float) -> None:
        super().__init__(None)
        self.remaining = max(0, int(math.ceil(seconds)))
        self.cancelled = False
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.resize(150, 72)
        self._move_to_bottom_right()

    def set_remaining(self, seconds: int) -> None:
        self.remaining = max(0, seconds)
        self.update()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled = True
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 20, 20, 185))
        painter.drawRoundedRect(self.rect(), 12, 12)
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPointSize(26)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(self.remaining))

    def _move_to_bottom_right(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        geometry = screen.availableGeometry()
        margin = 24
        self.move(geometry.right() - self.width() - margin, geometry.bottom() - self.height() - margin)


class CaptureService:
    def __init__(self) -> None:
        self._last_capture: _LastCapture | None = None

    def prepare_frozen_selection(
        self, mode: CaptureMode, settings: CaptureSettings
    ) -> _FrozenDesktop | None:
        zero_delay_interactive = settings.delay_seconds <= 0 and (
            (
                sys.platform == "win32"
                and mode in {CaptureMode.REGION, CaptureMode.WINDOW_UNDER_CURSOR}
            )
            or (
                sys.platform == "darwin"
                and mode in {CaptureMode.REGION, CaptureMode.WINDOW_UNDER_CURSOR}
            )
        )
        if zero_delay_interactive:
            frozen = self._freeze_desktop(settings)
            if (
                frozen is not None
                and sys.platform == "win32"
                and mode == CaptureMode.WINDOW_UNDER_CURSOR
            ):
                return _FrozenDesktop(
                    frozen.rect,
                    frozen.image,
                    _snapshot_windows_transient_targets(),
                    frozen.windows,
                )
            return frozen
        return None

    def capture(
        self,
        mode: CaptureMode,
        settings: CaptureSettings,
        frozen_selection: _FrozenDesktop | None = None,
    ) -> Image.Image | None:
        if sys.platform == "darwin":
            from fshot.platforms.macos import screen_recording_allowed

            if not screen_recording_allowed(request=True):
                raise PermissionError(
                    "Screen Recording permission is required. Enable FShot (or its terminal) "
                    "in System Settings > Privacy & Security > Screen Recording."
                )
        frozen_modes = {CaptureMode.REGION, CaptureMode.WINDOW_UNDER_CURSOR}
        frozen = frozen_selection if mode in frozen_modes else None
        if frozen is None and sys.platform == "win32" and mode in frozen_modes:
            frozen = self._freeze_desktop(settings)
            if frozen is None:
                return None
            if mode == CaptureMode.WINDOW_UNDER_CURSOR:
                frozen = _FrozenDesktop(
                    frozen.rect,
                    frozen.image,
                    _snapshot_windows_transient_targets(),
                    frozen.windows,
                )

        window_target = None
        if mode == CaptureMode.WINDOW_UNDER_CURSOR:
            window_target = self._select_window_target(frozen)
            rect = window_target.rect if window_target is not None else None
        elif mode == CaptureMode.REGION:
            rect = self._select_region(frozen.image if frozen is not None else None)
        else:
            rect = self._rect_for_mode(mode)
        if rect is None or rect.is_empty:
            return None

        if frozen is not None:
            image = frozen.crop(rect)
            if image is None:
                return None
        else:
            image = self._capture_rect_for_mode(mode, rect, settings)
            if image is None:
                return None
        self._last_capture = _LastCapture(
            mode,
            rect=rect if mode == CaptureMode.REGION else None,
            window_target=window_target,
        )
        return image

    def repeat(self, settings: CaptureSettings) -> Image.Image | None:
        previous = self._last_capture
        if previous is None:
            return None
        if previous.mode == CaptureMode.REGION:
            rect = previous.rect
        elif previous.mode == CaptureMode.WINDOW_UNDER_CURSOR:
            rect = previous.window_target.resolve() if previous.window_target is not None else None
        else:
            rect = self._rect_for_mode(previous.mode)
        if rect is None or rect.is_empty:
            return None
        if (
            previous.mode == CaptureMode.WINDOW_UNDER_CURSOR
            and previous.window_target is not None
            and settings.delay_seconds > 0
        ):
            if self._countdown(settings.delay_seconds):
                return None
            rect = previous.window_target.resolve()
            if rect is None:
                return None
            settings = CaptureSettings(
                include_cursor=settings.include_cursor,
                delay_seconds=0,
            )
        return self._capture_rect_for_mode(previous.mode, rect, settings)

    def _capture_rect_for_mode(
        self, mode: CaptureMode, rect: CaptureRect, settings: CaptureSettings
    ) -> Image.Image | None:

        if settings.delay_seconds > 0 and self._countdown(settings.delay_seconds):
            return None

        if sys.platform == "darwin" and mode == CaptureMode.WINDOW_UNDER_CURSOR:
            image = self._grab_macos_selection_without_hover(rect)
        else:
            image = self._grab_rect(rect)
        if settings.include_cursor:
            self._draw_cursor(image, rect)
        return image

    def _grab_macos_selection_without_hover(self, rect: CaptureRect) -> Image.Image:
        """Hide transient browser link URLs and tooltips before capture."""
        original = QCursor.pos()
        # A point near the center of the native title bar is inside the target
        # window but outside its web content, even when the window is maximized.
        safe_point = QPoint(rect.left + rect.width // 2, rect.top + min(12, rect.height // 2))
        try:
            QCursor.setPos(safe_point)
            QApplication.processEvents()
            time.sleep(0.4)
            return self._grab_rect(rect)
        finally:
            QCursor.setPos(original)
            QApplication.processEvents()
            time.sleep(0.03)

    def _rect_for_mode(self, mode: CaptureMode) -> CaptureRect | None:
        if mode == CaptureMode.FULLSCREEN:
            return self._fullscreen_rect()
        if mode == CaptureMode.ACTIVE_WINDOW:
            return self._active_window_rect() or self._fullscreen_rect()
        return None

    def _fullscreen_rect(self) -> CaptureRect:
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            return CaptureRect(monitor["left"], monitor["top"], monitor["width"], monitor["height"])

    def _select_region(self, frozen_desktop: Image.Image | None = None) -> CaptureRect | None:
        selectors = self._screen_selectors(frozen_desktop)
        try:
            selector = selectors[0]
            for overlay in selectors:
                overlay.show()
            cursor_screen = QGuiApplication.screenAt(QCursor.pos())
            selector = next((overlay for overlay in selectors if overlay.screen() == cursor_screen), selector)
            selector.raise_()
            selector.activateWindow()
            selector.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
            QApplication.setActiveWindow(selector)
            QApplication.processEvents()
            while selector.isVisible():
                selector.poll()
                QApplication.processEvents()
                time.sleep(0.01)
            if selector.cancelled or selector.selected_rect is None:
                return None
            selected = CaptureRect.from_qrect(selector.selected_rect)
            return selected.intersect(self._fullscreen_rect())
        finally:
            self._dispose_selectors(selectors)

    @staticmethod
    def _dispose_selectors(selectors) -> None:
        for overlay in selectors:
            overlay.hide()
            overlay.peers = []
            if isinstance(overlay, WindowSelector):
                overlay._uia_target_cache.clear()
                overlay.frozen_targets = ()
                overlay.frozen_windows = ()
                overlay.target = None
            overlay.frozen_desktop = None
            overlay.deleteLater()

    def _screen_selectors(self, frozen_desktop: Image.Image | None, factory=RegionSelector):
        if sys.platform != "win32" or win32api is None:
            return [factory(frozen_desktop)]
        desktop = self._fullscreen_rect()
        native_monitors = {}
        for handle, _dc, _rect in win32api.EnumDisplayMonitors():
            info = win32api.GetMonitorInfo(handle)
            left, top, right, bottom = info["Monitor"]
            native_monitors[info["Device"]] = CaptureRect(left, top, right-left, bottom-top)
        selectors = []
        matched_devices: set[str] = set()
        for screen in QGuiApplication.screens():
            # QScreen.name() can be a friendly EDID name, not \\.\DISPLAYn.
            # Qt preserves native monitor origins on Windows while reporting
            # sizes in logical pixels. Match origin plus DPR-scaled size.
            geometry = screen.geometry()
            ratio = screen.devicePixelRatio()
            expected = CaptureRect(
                geometry.x(), geometry.y(),
                round(geometry.width()*ratio), round(geometry.height()*ratio),
            )
            candidates = [
                (device, bounds) for device, bounds in native_monitors.items()
                if device not in matched_devices and bounds.left == expected.left
                and bounds.top == expected.top
                and abs(bounds.width-expected.width) <= 1
                and abs(bounds.height-expected.height) <= 1
            ]
            if len(candidates) != 1:
                continue
            device, bounds = candidates[0]
            matched_devices.add(device)
            snapshot = None
            if frozen_desktop is not None:
                left, top = bounds.left-desktop.left, bounds.top-desktop.top
                snapshot = frozen_desktop.crop((left, top, left+bounds.width, top+bounds.height))
            overlay = factory(snapshot)
            overlay.native_rect = bounds
            overlay.native_desktop = QRect(desktop.left, desktop.top, desktop.width, desktop.height)
            # Each native window belongs to one QScreen, so Qt applies only that
            # screen's DPR. Never stretch the full desktop across mixed DPI.
            overlay.winId()
            overlay.windowHandle().setScreen(screen)
            overlay.setGeometry(geometry)
            selectors.append(overlay)
        if len(selectors) != len(native_monitors):
            # Fail explicitly instead of displaying an incorrectly scaled union.
            for overlay in selectors:
                overlay.deleteLater()
            raise RuntimeError("Unable to match Qt screens to Windows display positions and scale factors.")
        for overlay in selectors:
            overlay.peers = selectors
            if isinstance(overlay, WindowSelector):
                overlay._uia_target_cache = selectors[0]._uia_target_cache
        return selectors

    def _active_window_rect(self) -> CaptureRect | None:
        if sys.platform == "darwin":
            from fshot.platforms.macos import active_window_bounds

            bounds = active_window_bounds()
            return CaptureRect(*bounds) if bounds else None
        if win32gui is None:
            return None
        hwnd = win32gui.GetForegroundWindow()
        return _window_rect(hwnd)

    def _grab_rect(self, rect: CaptureRect) -> Image.Image:
        clipped = rect.intersect(self._fullscreen_rect())
        if clipped is None or clipped.is_empty:
            raise ValueError(f"Capture rectangle is outside the virtual screen: {rect}")
        try:
            with mss.mss() as sct:
                shot = sct.grab(clipped.to_mss())
                return Image.frombytes("RGB", shot.size, shot.rgb)
        except Exception:
            bbox = (
                clipped.left,
                clipped.top,
                clipped.left + clipped.width,
                clipped.top + clipped.height,
            )
            return ImageGrab.grab(bbox=bbox, all_screens=True).convert("RGB")

    def _draw_cursor(self, image: Image.Image, rect: CaptureRect) -> None:
        if sys.platform == "darwin":
            from fshot.platforms.macos import current_cursor_image

            try:
                cursor = current_cursor_image()
            except Exception:
                return
            if cursor:
                cursor_image, hotspot_x, hotspot_y, screen_x, screen_y = cursor
                paste_at = (
                    screen_x - rect.left - hotspot_x,
                    screen_y - rect.top - hotspot_y,
                )
                image.paste(cursor_image, paste_at, cursor_image)
            return
        if win32gui is None or win32api is None:
            return
        try:
            cursor = _current_cursor_image()
        except Exception:
            return
        if cursor is None:
            return
        cursor_image, hotspot_x, hotspot_y, screen_x, screen_y = cursor
        paste_x = screen_x - rect.left - hotspot_x
        paste_y = screen_y - rect.top - hotspot_y
        image.paste(cursor_image, (paste_x, paste_y), cursor_image)

    def _select_window_target(
        self, frozen_desktop: _FrozenDesktop | None = None
    ) -> WindowCaptureTarget | None:
        targets = frozen_desktop.targets if frozen_desktop is not None else ()
        frozen_windows = frozen_desktop.windows if frozen_desktop is not None else ()
        selectors = self._screen_selectors(
            frozen_desktop.image if frozen_desktop is not None else None,
            factory=lambda snapshot: WindowSelector(snapshot, targets, frozen_windows),
        )
        try:
            _cancel_windows_menu_mode()
            time.sleep(0.05)
            QApplication.processEvents()
            for overlay in selectors:
                overlay.show()
            cursor_screen = QGuiApplication.screenAt(QCursor.pos())
            selector = next((overlay for overlay in selectors if overlay.screen() == cursor_screen), selectors[0])
            selector.raise_()
            selector.activateWindow()
            QApplication.setActiveWindow(selector)
            QApplication.processEvents()
            while selector.isVisible():
                selector.poll()
                QApplication.processEvents()
                time.sleep(0.01)
            QApplication.processEvents()
            return None if selector.cancelled else selector.target
        finally:
            self._dispose_selectors(selectors)

    def _freeze_desktop(self, settings: CaptureSettings) -> _FrozenDesktop | None:
        if settings.delay_seconds > 0 and self._countdown(settings.delay_seconds):
            return None
        rect = self._fullscreen_rect()
        image = self._grab_rect(rect)
        if settings.include_cursor:
            self._draw_cursor(image, rect)
        windows = _snapshot_windows_targets() if sys.platform == "win32" else ()
        return _FrozenDesktop(rect, image, windows=windows)

    def _countdown(self, seconds: float) -> bool:
        overlay = CountdownOverlay(seconds)
        overlay.show()
        start = time.monotonic()
        total = max(0.0, seconds)
        cancelled = False
        while True:
            elapsed = time.monotonic() - start
            remaining = max(0, math.ceil(total - elapsed))
            overlay.set_remaining(remaining)
            QApplication.processEvents()
            if overlay.cancelled or _escape_pressed():
                cancelled = True
                break
            if elapsed >= total:
                break
            time.sleep(0.05)
        overlay.hide()
        QApplication.processEvents()
        time.sleep(0.05)
        return cancelled


def _window_rect(hwnd: int | None) -> CaptureRect | None:
    if not hwnd or win32gui is None:
        return None
    if not win32gui.IsWindowVisible(hwnd):
        return None
    dwm_rect = _dwm_window_rect(hwnd)
    if dwm_rect is not None:
        return dwm_rect
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    return CaptureRect(left, top, right - left, bottom - top)


def _window_rect_at_point(
    point: QPoint,
    exclude_hwnd: int | None = None,
    use_uia: bool = True,
) -> CaptureRect | None:
    target = _window_target_at_point(point, exclude_hwnd=exclude_hwnd, use_uia=use_uia)
    return target.rect if target is not None else None


def _window_target_at_point(
    point: QPoint,
    exclude_hwnd: int | None = None,
    use_uia: bool = True,
) -> WindowCaptureTarget | None:
    if win32gui is None:
        return None
    uia_target = _uia_target_at_point(point) if use_uia else None
    if uia_target is not None and not _looks_like_desktop_rect(uia_target.rect):
        return uia_target
    hwnd = _window_from_point(point, exclude_hwnd)
    if not hwnd:
        return None
    return _window_target_from_hwnd(hwnd)


def _window_target_from_hwnd(hwnd: int) -> WindowCaptureTarget | None:
    rect = _window_rect(hwnd)
    if rect is None:
        return None
    try:
        _thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
        class_name = win32gui.GetClassName(hwnd)
    except Exception:
        return None

    def resolve() -> CaptureRect | None:
        if win32gui is None or not win32gui.IsWindow(hwnd):
            return None
        try:
            _current_thread, current_process = win32process.GetWindowThreadProcessId(hwnd)
            if current_process != process_id or win32gui.GetClassName(hwnd) != class_name:
                return None
        except Exception:
            return None
        return _window_rect(hwnd)

    try:
        owner = win32gui.GetAncestor(hwnd, win32con.GA_ROOT) or hwnd
    except Exception:
        owner = hwnd
    return WindowCaptureTarget(rect, resolve, owner, owner == hwnd, owner)


def _snapshot_windows_targets() -> tuple[WindowCaptureTarget, ...]:
    """Pin top-level HWNDs in their original front-to-back order."""
    result = []
    seen = set()
    try:
        hwnd = win32gui.GetTopWindow(0)
        while hwnd and hwnd not in seen and len(seen) < 512:
            seen.add(hwnd)
            try:
                _thread, process = win32process.GetWindowThreadProcessId(hwnd)
                if process != os.getpid() and win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
                    if win32gui.GetClassName(hwnd) not in {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}:
                        target = _window_target_from_hwnd(hwnd)
                        if target is not None:
                            result.append(target)
            except Exception:
                pass
            hwnd = win32gui.GetWindow(hwnd, win32con.GW_HWNDNEXT)
    except Exception:
        pass
    return tuple(result)


def _window_target_below_overlay(
    point: QPoint,
    overlay_hwnd: int,
    uia_cache: dict[int, tuple[WindowCaptureTarget, ...]] | None,
) -> WindowCaptureTarget | None:
    hwnd = _window_from_point(point, overlay_hwnd)
    if not hwnd:
        return None
    if uia_cache is not None:
        try:
            root_hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT) or hwnd
        except Exception:
            root_hwnd = hwnd
        targets = uia_cache.get(root_hwnd)
        if targets is None:
            targets = _uia_targets_for_hwnd(root_hwnd)
            uia_cache[root_hwnd] = targets
        matches = [target for target in targets if _rect_contains(target.rect, point)]
        if matches:
            return min(matches, key=lambda target: target.rect.width * target.rect.height)
    return _window_target_from_hwnd(hwnd)


def _window_from_point(point: QPoint, exclude_hwnd: int | None = None) -> int | None:
    if win32gui is None or win32con is None:
        return None
    screen_point = (point.x(), point.y())
    hwnd = win32gui.WindowFromPoint(screen_point)
    if exclude_hwnd and _same_hwnd(hwnd, exclude_hwnd):
        hwnd = win32gui.GetWindow(hwnd, win32con.GW_HWNDNEXT)
        while hwnd:
            rect = _window_rect(hwnd)
            if rect and _rect_contains(rect, point):
                break
            hwnd = win32gui.GetWindow(hwnd, win32con.GW_HWNDNEXT)
    if not hwnd:
        return None
    return _deepest_child_at_point(hwnd, screen_point)


def _deepest_child_at_point(hwnd: int, screen_point: tuple[int, int]) -> int:
    if win32gui is None or win32con is None:
        return hwnd
    current = hwnd
    flags = win32con.CWP_SKIPINVISIBLE | win32con.CWP_SKIPDISABLED | win32con.CWP_SKIPTRANSPARENT
    while True:
        try:
            client_point = win32gui.ScreenToClient(current, screen_point)
            child = _real_child_window_from_point(current, client_point)
            if not child or _same_hwnd(child, current):
                child = win32gui.ChildWindowFromPointEx(current, client_point, flags)
        except Exception:
            return current
        if not child or _same_hwnd(child, current):
            return current
        current = child


def _real_child_window_from_point(hwnd: int, client_point: tuple[int, int]) -> int | None:
    try:
        ctypes.windll.user32.RealChildWindowFromPoint.restype = c_void_p
        ctypes.windll.user32.RealChildWindowFromPoint.argtypes = [c_void_p, wintypes.POINT]
        value = ctypes.windll.user32.RealChildWindowFromPoint(
            c_void_p(_handle_value(hwnd)),
            wintypes.POINT(client_point[0], client_point[1]),
        )
    except Exception:
        return None
    return int(value) if value else None


def _rect_contains(rect: CaptureRect, point: QPoint) -> bool:
    return (
        rect.left <= point.x() < rect.left + rect.width
        and rect.top <= point.y() < rect.top + rect.height
    )


def _same_hwnd(left: object, right: object) -> bool:
    return _handle_value(left) == _handle_value(right)


def _uia_rect_at_point(point: QPoint) -> CaptureRect | None:
    target = _uia_target_at_point(point)
    return target.rect if target is not None else None


def _uia_target_at_point(point: QPoint) -> WindowCaptureTarget | None:
    if sys.platform != "win32":
        return None
    try:
        automation, point_type = _uia_automation()
        element = automation.ElementFromPoint(point_type(point.x(), point.y()))
        if not element:
            return None
        return _uia_element_target(element)
    except Exception:
        return None


def _uia_automation():
    global _UIA_AUTOMATION, _UIA_POINT
    if _UIA_AUTOMATION is None or _UIA_POINT is None:
        import comtypes.client

        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import CUIAutomation, IUIAutomation, tagPOINT

        _UIA_AUTOMATION = comtypes.client.CreateObject(CUIAutomation, interface=IUIAutomation)
        _UIA_POINT = tagPOINT
    return _UIA_AUTOMATION, _UIA_POINT


def _uia_element_target(element, owner_hwnd: int | None = None) -> WindowCaptureTarget | None:
    initial = _uia_element_rect(element)
    if initial is None:
        return None
    # UIA top-level Window bounds can include the invisible resize frame.
    # Prefer the HWND/DWM path for the whole window while retaining UIA bounds
    # for controls inside it.
    if int(element.CurrentControlType) == 50032:  # UIA_WindowControlTypeId
        hwnd = int(element.CurrentNativeWindowHandle)
        native_target = _window_target_from_hwnd(hwnd) if hwnd else None
        if native_target is not None:
            if owner_hwnd is not None and native_target.owner_hwnd != owner_hwnd:
                return None
            return native_target
    if owner_hwnd is None:
        try:
            automation, _ = _uia_automation()
            ancestor = element
            for _ in range(32):
                native = int(ancestor.CurrentNativeWindowHandle)
                if native:
                    owner_hwnd = win32gui.GetAncestor(native, win32con.GA_ROOT) or native
                    break
                ancestor = automation.ControlViewWalker.GetParentElement(ancestor)
                if not ancestor:
                    break
        except Exception:
            pass
    resolver = _uia_control_resolver(element, owner_hwnd) if owner_hwnd else lambda: _uia_element_rect(element)
    return WindowCaptureTarget(initial, resolver, owner_hwnd, source_hwnd=owner_hwnd)


def _uia_control_resolver(element, owner_hwnd: int):
    """Reacquire a control after cross-monitor DPI changes recreate its UIA object."""
    def identity(control):
        return (
            str(control.CurrentAutomationId), int(control.CurrentControlType),
            str(control.CurrentClassName), str(control.CurrentName),
        )

    try:
        saved_identity = identity(element)
        saved_runtime = tuple(element.GetRuntimeId())
    except Exception:
        return lambda: None
    owner_target = _window_target_from_hwnd(owner_hwnd)

    def same_control(control) -> bool:
        try:
            current = identity(control)
            if saved_runtime:
                return tuple(control.GetRuntimeId()) == saved_runtime and current[:3] == saved_identity[:3]
            return bool(saved_identity[0]) and current == saved_identity
        except Exception:
            return False

    def resolve():
        owner = owner_target.resolve() if owner_target is not None else None
        if owner is None:
            return None
        # Most providers update the existing object on move. Avoid a complete
        # descendant query when the live control already has valid new bounds.
        allow_offscreen = saved_identity[1] not in {50009, 50011}
        live = _uia_element_rect(element, allow_offscreen=allow_offscreen) if same_control(element) else None
        if live is not None and live.intersect(owner) is not None:
            return live
        try:
            automation, _ = _uia_automation()
            root = automation.ElementFromHandle(owner_hwnd)
            condition = automation.CreatePropertyCondition(30003, saved_identity[1])
            for property_id, value in ((30011, saved_identity[0]), (30012, saved_identity[2]), (30005, saved_identity[3])):
                if value:
                    condition = automation.CreateAndCondition(condition, automation.CreatePropertyCondition(property_id, value))
            controls = root.FindAll(4, condition)
            matches = []
            deadline = time.monotonic() + 0.5
            if controls.Length > 128:
                return None
            for index in range(controls.Length):
                if time.monotonic() > deadline:
                    return None
                candidate = controls.GetElement(index)
                try:
                    current_identity = identity(candidate)
                    rect = _uia_element_rect(candidate, allow_offscreen=allow_offscreen)
                    if rect is None or rect.intersect(owner) is None:
                        continue
                    if same_control(candidate):
                        return rect
                    if saved_identity[0] and current_identity == saved_identity:
                        matches.append(rect)
                except Exception:
                    continue
            # Never guess by old coordinates: a layout change may place a
            # different control there. Only accept an unambiguous identity.
            if len(matches) == 1:
                return matches[0]
        except Exception:
            pass
        return None

    return resolve


def _uia_targets_for_hwnd(hwnd: int) -> tuple[WindowCaptureTarget, ...]:
    try:
        automation, _point_type = _uia_automation()
        root = automation.ElementFromHandle(hwnd)
        descendants = root.FindAll(4, automation.ControlViewCondition)
        elements = [root]
        elements.extend(descendants.GetElement(index) for index in range(descendants.Length))
        targets: list[WindowCaptureTarget] = []
        seen: set[CaptureRect] = set()
        for element in elements:
            target = _uia_element_target(element, hwnd)
            if target is None or target.rect in seen or _looks_like_desktop_rect(target.rect):
                continue
            seen.add(target.rect)
            targets.append(target)
        return tuple(targets)
    except Exception:
        return ()


def _snapshot_windows_transient_targets() -> tuple[WindowCaptureTarget, ...]:
    """Save menu/menu-item bounds before the live native menu is dismissed."""
    if sys.platform != "win32" or win32gui is None or win32process is None:
        return ()
    try:
        foreground = win32gui.GetForegroundWindow()
        if not foreground:
            return ()
        thread_id, _process_id = win32process.GetWindowThreadProcessId(foreground)
        windows = [foreground]

        def collect(hwnd, _extra) -> bool:
            if hwnd != foreground and win32gui.IsWindowVisible(hwnd):
                windows.append(hwnd)
            return True

        win32gui.EnumThreadWindows(thread_id, collect, None)
        automation, _point_type = _uia_automation()
        control_type_property = 30003
        menu_control_type = 50009
        menu_item_control_type = 50011
        menu_condition = automation.CreateOrCondition(
            automation.CreatePropertyCondition(control_type_property, menu_control_type),
            automation.CreatePropertyCondition(control_type_property, menu_item_control_type),
        )
        elements = []
        for hwnd in dict.fromkeys(windows):
            try:
                root = automation.ElementFromHandle(hwnd)
                matches = root.FindAll(4, menu_condition)  # TreeScope_Descendants
                elements.extend((matches.GetElement(index), hwnd) for index in range(matches.Length))
            except Exception:
                continue

        targets: list[WindowCaptureTarget] = []
        seen: set[CaptureRect] = set()
        for element, hwnd in elements:
            rect = _uia_element_rect(element)
            if rect is None or rect in seen or _looks_like_desktop_rect(rect):
                continue
            seen.add(rect)
            # Frozen menu/control targets need the same owner metadata as live
            # hit-test targets; otherwise virtual capture cannot move the app.
            try:
                owner = win32gui.GetAncestor(hwnd, win32con.GA_ROOTOWNER) or hwnd
            except Exception:
                owner = foreground
            target = _uia_element_target(element, owner)
            if target is not None:
                target.source_hwnd = hwnd
                targets.append(target)

        # Custom-drawn popup windows may not expose menu items through UIA.
        # Preserve their top-level bounds so the popup itself remains selectable.
        for hwnd in windows:
            if hwnd == foreground:
                continue
            rect = _window_rect(hwnd)
            if rect is None or rect in seen or _looks_like_desktop_rect(rect):
                continue
            seen.add(rect)
            try:
                owner = win32gui.GetAncestor(hwnd, win32con.GA_ROOTOWNER) or hwnd
            except Exception:
                owner = foreground
            targets.append(WindowCaptureTarget(rect, lambda hwnd=hwnd: _window_rect(hwnd), owner, source_hwnd=hwnd))
        return tuple(targets)
    except Exception:
        return ()


def _uia_element_rect(element, *, allow_offscreen: bool = False) -> CaptureRect | None:
    try:
        if not allow_offscreen and bool(element.CurrentIsOffscreen):
            return None
        rect = element.CurrentBoundingRectangle
        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width <= 1 or height <= 1:
            return None
        return CaptureRect(int(rect.left), int(rect.top), width, height)
    except Exception:
        return None


def _capture_rect_from_bounds(bounds: tuple[int, int, int, int] | None) -> CaptureRect | None:
    return CaptureRect(*bounds) if bounds is not None else None


def _looks_like_desktop_rect(rect: CaptureRect) -> bool:
    virtual = _virtual_capture_rect()
    width_delta = abs(rect.width - virtual.width)
    height_delta = abs(rect.height - virtual.height)
    return width_delta <= 4 and height_delta <= 4


def _virtual_capture_rect() -> CaptureRect:
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        return CaptureRect(monitor["left"], monitor["top"], monitor["width"], monitor["height"])


def _current_cursor_image() -> tuple[Image.Image, int, int, int, int] | None:
    if sys.platform != "win32" or win32gui is None or win32api is None:
        return None
    windll.user32.GetDC.restype = HDC
    windll.user32.GetDC.argtypes = [c_void_p]
    windll.user32.ReleaseDC.argtypes = [c_void_p, HDC]
    windll.user32.GetIconInfo.argtypes = [c_void_p, POINTER(ICONINFO)]
    windll.user32.DrawIconEx.argtypes = [HDC, c_int, c_int, c_void_p, c_int, c_int, c_uint, c_void_p, c_uint]
    windll.gdi32.CreateCompatibleDC.restype = HDC
    windll.gdi32.CreateCompatibleDC.argtypes = [HDC]
    windll.gdi32.CreateDIBSection.restype = HBITMAP
    windll.gdi32.CreateDIBSection.argtypes = [HDC, POINTER(BITMAPINFO), c_uint, POINTER(c_void_p), c_void_p, DWORD]
    windll.gdi32.SelectObject.restype = HGDIOBJ
    windll.gdi32.SelectObject.argtypes = [HDC, HGDIOBJ]
    windll.gdi32.DeleteObject.argtypes = [HGDIOBJ]
    windll.gdi32.DeleteDC.argtypes = [HDC]
    flags, hcursor, (screen_x, screen_y) = win32gui.GetCursorInfo()
    if flags != CURSOR_SHOWING or not hcursor:
        return None

    icon_info = ICONINFO()
    if not windll.user32.GetIconInfo(c_void_p(_handle_value(hcursor)), byref(icon_info)):
        return None

    width = max(16, win32api.GetSystemMetrics(13))
    height = max(16, win32api.GetSystemMetrics(14))
    size = width * height * 4
    screen_dc = windll.user32.GetDC(c_void_p(0))
    memory_dc = windll.gdi32.CreateCompatibleDC(screen_dc)
    bits = c_void_p()
    bitmap_info = BITMAPINFO()
    bitmap_info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
    bitmap_info.bmiHeader.biWidth = width
    bitmap_info.bmiHeader.biHeight = -height
    bitmap_info.bmiHeader.biPlanes = 1
    bitmap_info.bmiHeader.biBitCount = 32
    bitmap_info.bmiHeader.biCompression = BI_RGB
    bitmap = windll.gdi32.CreateDIBSection(
        screen_dc,
        byref(bitmap_info),
        DIB_RGB_COLORS,
        byref(bits),
        None,
        0,
    )
    if not bitmap:
        _delete_icon_bitmaps(icon_info)
        windll.gdi32.DeleteDC(memory_dc)
        windll.user32.ReleaseDC(c_void_p(0), screen_dc)
        return None

    old_bitmap = windll.gdi32.SelectObject(memory_dc, bitmap)
    memset(bits, 0, size)
    windll.user32.DrawIconEx(memory_dc, 0, 0, c_void_p(_handle_value(hcursor)), width, height, 0, None, DI_NORMAL)
    raw = string_at(bits, size)
    cursor_image = Image.frombuffer("RGBA", (width, height), raw, "raw", "BGRA", 0, 1).copy()

    windll.gdi32.SelectObject(memory_dc, old_bitmap)
    windll.gdi32.DeleteObject(bitmap)
    windll.gdi32.DeleteDC(memory_dc)
    windll.user32.ReleaseDC(c_void_p(0), screen_dc)
    _delete_icon_bitmaps(icon_info)
    return cursor_image, int(icon_info.xHotspot), int(icon_info.yHotspot), screen_x, screen_y


def _delete_icon_bitmaps(icon_info: ICONINFO) -> None:
    if icon_info.hbmMask:
        windll.gdi32.DeleteObject(icon_info.hbmMask)
    if icon_info.hbmColor:
        windll.gdi32.DeleteObject(icon_info.hbmColor)


def _dwm_window_rect(hwnd: int) -> CaptureRect | None:
    if sys.platform != "win32" or DWMWA_EXTENDED_FRAME_BOUNDS is None:
        return None
    rect = RECT()
    result = windll.dwmapi.DwmGetWindowAttribute(
        c_void_p(_handle_value(hwnd)),
        c_int(DWMWA_EXTENDED_FRAME_BOUNDS),
        byref(rect),
        c_int(sizeof(rect)),
    )
    if result != 0:
        return None
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return None
    return CaptureRect(rect.left, rect.top, width, height)


def _handle_value(handle: object) -> int:
    value = int(handle)
    bits = sizeof(c_void_p) * 8
    return value & ((1 << bits) - 1)


def _virtual_screen_rect() -> QRect:
    app = QGuiApplication.instance()
    if app is None:
        return QRect(0, 0, 0, 0)
    screens = app.screens()
    if not screens:
        return QRect(0, 0, 0, 0)
    rect = screens[0].geometry()
    for screen in screens[1:]:
        rect = rect.united(screen.geometry())
    return rect


def _escape_pressed() -> bool:
    if sys.platform == "win32" and win32api is not None:
        return bool(win32api.GetAsyncKeyState(0x1B) & 0x8000)
    if sys.platform == "darwin":
        try:
            import Quartz

            return bool(
                Quartz.CGEventSourceKeyState(
                    Quartz.kCGEventSourceStateCombinedSessionState,
                    53,
                )
            )
        except Exception:
            return False
    return False
