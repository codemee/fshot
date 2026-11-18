"""Capture Windows virtual displays with optional, separately confirmed provisioning."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import time
import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout,
)

from fshot.capture import CaptureRect, _window_rect, _window_target_from_hwnd
from fshot.settings import CaptureMode, CaptureSettings, virtual_repaint_seconds
from fshot.qt_image import pil_to_qimage


@dataclass(frozen=True)
class Display:
    device: str
    rect: CaptureRect
    work_rect: CaptureRect | None = None
    is_virtual: bool = False


def virtual_display_devices() -> set[str]:
    """Identify known virtual display adapters by their Windows driver names."""
    import win32api

    devices = set()
    index = 0
    while True:
        try:
            adapter = win32api.EnumDisplayDevices(None, index)
        except win32api.error:
            break
        index += 1
        name = adapter.DeviceString.casefold()
        if any(marker in name for marker in (
            "virtual display", "virtual monitor", "indirect display", "iddsample", "parsec",
        )):
            devices.add(adapter.DeviceName)
    return devices


def displays() -> list[Display]:
    import win32api

    result = []
    virtual_devices = virtual_display_devices()
    for handle, _dc, _rect in win32api.EnumDisplayMonitors():
        info = win32api.GetMonitorInfo(handle)
        left, top, right, bottom = info["Monitor"]
        wl, wt, wr, wb = info["Work"]
        result.append(Display(
            info["Device"], CaptureRect(left, top, right-left, bottom-top),
            CaptureRect(wl, wt, wr-wl, wb-wt),
            info["Device"] in virtual_devices,
        ))
    return result


def resolve_display(display: Display) -> CaptureRect:
    for current in displays():
        if current.device == display.device:
            if current.rect != display.rect or current.work_rect != display.work_rect:
                raise RuntimeError("Display configuration changed. Select the display again.")
            return current.rect
    raise RuntimeError("The selected display is no longer connected.")


def windows() -> list[tuple[int, str]]:
    import os
    import win32gui
    import win32process

    result = []

    def visit(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                return
            if win32gui.GetClassName(hwnd) in {
                "TopLevelWindowForOverflowXamlIsland", "NotifyIconOverflowWindow",
                "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW",
            }:
                return
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            if right <= left or bottom <= top:
                return
            title = win32gui.GetWindowText(hwnd)
            _thread, process = win32process.GetWindowThreadProcessId(hwnd)
            if title and process != os.getpid() and not win32gui.GetWindow(hwnd, 4):
                result.append((hwnd, title))
        except Exception:
            # A window can close between enumeration and querying its details.
            return

    win32gui.EnumWindows(visit, None)
    return result


def window_capture_rect(hwnd: int | None, display: Display) -> CaptureRect:
    screen = resolve_display(display)
    if hwnd is None:
        return screen
    rect = _window_rect(hwnd)
    if rect is None:
        raise RuntimeError("The selected window is no longer visible.")
    if rect.intersect(screen) != rect:
        logging.getLogger(__name__).warning(
            "Virtual window outside display: hwnd=%s window=%s display=%s", hwnd, rect, screen,
        )
        raise RuntimeError("The window does not fit inside the selected display.")
    return rect


def _wait_for_window_update(seconds: float = 0.15, hwnd: int | None = None) -> None:
    """Stop early when native bounds stabilize; retain the upper wait limit."""
    started = time.monotonic()
    deadline = started + seconds
    previous = None
    stable_samples = 0
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if hwnd is not None:
            current = _window_rect(hwnd)
            stable_samples = stable_samples + 1 if current is not None and current == previous else 0
            previous = current
            if stable_samples >= 3 and time.monotonic()-started >= 0.04:
                return
        time.sleep(0.01)


def _place_window(hwnd: int, target: CaptureRect) -> None:
    import win32con
    import win32gui

    for _ in range(3):
        frame = _window_rect(hwnd)
        if frame is None:
            raise RuntimeError("The selected window has closed.")
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        win32gui.SetWindowPos(
            hwnd, win32con.HWND_TOP,
            target.left - (frame.left-left), target.top - (frame.top-top),
            target.width + (right-left-frame.width), target.height + (bottom-top-frame.height),
            win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
        )
        _wait_for_window_update(hwnd=hwnd)
        if _window_rect(hwnd) == target:
            break


def proportional_size(original: CaptureRect, source: CaptureRect, destination: CaptureRect) -> tuple[int, int]:
    """Preserve the fraction of screen width and height occupied by a window."""
    if original.is_empty or source.is_empty or destination.is_empty:
        raise ValueError("Window or display area is empty.")
    return (
        max(1, round(original.width * destination.width / source.width)),
        max(1, round(original.height * destination.height / source.height)),
    )


def automatic_display(tr) -> Display:
    available = [display for display in displays() if display.is_virtual]
    if not available:
        raise RuntimeError(tr("virtual_screen_missing"))
    return max(available, key=lambda item: (item.rect.width * item.rect.height, item.device))


class VirtualCaptureSession:
    """Shortcut captures without the selection list or preview dialog."""

    def __init__(self):
        self.last = None
        self.last_region = None

    def active_target(self):
        import win32gui

        return _window_target_from_hwnd(win32gui.GetForegroundWindow())

    def capture(self, service, mode, settings, tr, target=None, frozen=None, *, region_selection=None):
        if mode == CaptureMode.FULLSCREEN:
            image = service._capture_rect_for_mode(mode, service._current_screen_rect(), settings)
            if image is not None:
                self.last = (mode, None)
            return image
        display = automatic_display(tr)
        if mode == CaptureMode.WINDOW_UNDER_CURSOR:
            # Freeze before the selector takes focus; delay applies only to the
            # eventual capture on the destination, rather than twice.
            frozen = frozen or service._freeze_desktop(CaptureSettings())
            target = service._select_window_target(frozen)
            if target is None:
                return None
        elif mode in {CaptureMode.ACTIVE_WINDOW, CaptureMode.REGION} and target is None:
            raise RuntimeError(tr("virtual_target_unavailable"))
        image = self._capture_target(service, display, target, settings, tr,
                                     interactive=mode in {CaptureMode.ACTIVE_WINDOW, CaptureMode.REGION},
                                     region=mode == CaptureMode.REGION)
        if image is not None and mode == CaptureMode.REGION:
            from fshot.virtual_region import crop_snapshot

            image, selection = crop_snapshot(image, tr, region_selection)
            if image is not None:
                self.last_region = selection
        if image is not None:
            self.last = (mode, target)
        return image

    def repeat(self, service, settings, tr):
        if self.last is None:
            return None
        _mode, target = self.last
        if _mode == CaptureMode.FULLSCREEN:
            return self.capture(service, _mode, settings, tr)
        if target is not None and target.resolve() is None:
            return None
        if _mode == CaptureMode.REGION:
            return self.capture(service, _mode, settings, tr, target, region_selection=self.last_region)
        return self._capture_target(service, automatic_display(tr), target, settings, tr, interactive=_mode == CaptureMode.ACTIVE_WINDOW)

    def _capture_target(self, service, display, target, settings, tr, *, interactive=False, region=False):
        started = time.perf_counter()
        hwnd = target.owner_hwnd if target is not None else None
        logging.getLogger(__name__).warning(
            "Virtual capture selection: owner=%s source=%s whole_window=%s original=%s destination=%s",
            hwnd, target.source_hwnd if target is not None else None,
            target.is_window if target is not None else None,
            target.rect if target is not None else None, display.rect,
        )
        if target is not None and hwnd is None:
            raise RuntimeError(tr("virtual_owner_unavailable"))
        if target is not None and target.resolve() is None:
            raise RuntimeError(tr("virtual_control_unavailable"))
        with moved_window(hwnd, display, settings.virtual_repaint_seconds) as destination:
            logging.getLogger(__name__).warning("Virtual capture move ready: %.3fs", time.perf_counter()-started)
            QApplication.processEvents()
            # moved_window has already allowed the target's renderer to resize
            # before any countdown, interactive preview or final capture.
            if interactive and settings.delay_seconds > 0:
                from fshot.virtual_interactive import delayed_interactive_capture

                if region:
                    return delayed_interactive_capture(service, display, target, settings, tr, region=True)
                return delayed_interactive_capture(service, display, target, settings, tr)
            if settings.delay_seconds > 0 and service._countdown(settings.delay_seconds):
                return None
            if hwnd is not None:
                actual = _window_rect(hwnd)
                if actual is not None and actual.intersect(display.rect) != actual:
                    # Some applications apply WM_DPICHANGED's suggested rectangle
                    # after the initial move. Reapply the recorded destination.
                    _place_window(hwnd, destination)
            owner_rect = window_capture_rect(hwnd, display)
            rect = owner_rect
            if target is not None:
                live_rect = target.resolve()
                if live_rect is None:
                    raise RuntimeError(tr("virtual_control_unavailable"))
                if not target.is_window:
                    rect = live_rect.intersect(owner_rect)
                    if rect is None:
                        raise RuntimeError(tr("virtual_control_unavailable"))
            if hwnd is not None:
                import win32gui
                import win32con

                hit = win32gui.WindowFromPoint((rect.left+rect.width//2, rect.top+rect.height//2))
                root = win32gui.GetAncestor(hit, win32con.GA_ROOT) if hit else None
                if root != hwnd:
                    raise RuntimeError(tr("virtual_target_obscured"))
            logging.getLogger(__name__).warning(
                "Virtual capture output: owner=%s owner_rect=%s capture_rect=%s", hwnd, owner_rect, rect,
            )
            if region:
                rect = resolve_display(display)
            image = service._grab_rect(rect)
            logging.getLogger(__name__).warning("Virtual capture image ready: %.3fs (configured delay=%s)", time.perf_counter()-started, settings.delay_seconds)
            if settings.include_cursor:
                service._draw_cursor(image, rect)
            return image


@contextmanager
def moved_window(hwnd: int | None, display: Display, repaint_seconds: float = 1.5):
    """Always restore placement, including when preview or capture raises."""
    import win32con
    import win32gui

    rect = resolve_display(display)
    if hwnd is None:
        yield None
        return
    if not win32gui.IsWindow(hwnd):
        raise RuntimeError("The selected window has closed.")
    placement = win32gui.GetWindowPlacement(hwnd)
    original_outer = win32gui.GetWindowRect(hwnd)
    original = _window_rect(hwnd)
    if original is None or win32gui.IsIconic(hwnd):
        raise RuntimeError("Restore the selected window before capturing it.")
    import win32api

    monitor = win32api.MonitorFromWindow(hwnd, 2)
    sl, st, sr, sb = win32api.GetMonitorInfo(monitor)["Monitor"]
    width, height = proportional_size(original, CaptureRect(sl, st, sr-sl, sb-st), rect)
    target = display.work_rect or rect
    if width > target.width or height > target.height:
        raise RuntimeError("The proportional window size exceeds the destination work area. Resize the source window first.")
    try:
        if placement[1] != win32con.SW_SHOWNORMAL:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            _wait_for_window_update(hwnd=hwnd)
            # Complete the monitor/DPI transition before applying the final
            # size. Restored applications can otherwise lay out at the old DPI
            # or overwrite the resize with WM_DPICHANGED's suggested bounds.
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOP, target.left, target.top, 0, 0,
                win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
            )
            _wait_for_window_update(hwnd=hwnd)
        destination = CaptureRect(target.left, target.top, width, height)
        _place_window(hwnd, destination)
        actual = _window_rect(hwnd)
        if actual is not None and actual.intersect(rect) != actual:
            # Q-Dir can relocate/resize itself when its invisible resize border
            # overlaps the adjacent physical monitor. Retry with the outer
            # top-left inside the destination, keeping the proportional size.
            left, top, _right, _bottom = win32gui.GetWindowRect(hwnd)
            inset_x = max(0, actual.left-left)
            inset_y = max(0, actual.top-top)
            if (inset_x or inset_y) and width+inset_x <= target.width and height+inset_y <= target.height:
                destination = CaptureRect(target.left+inset_x, target.top+inset_y, width, height)
                _place_window(hwnd, destination)
        # Native bounds can stabilize before the application's renderer has
        # resized its surface, even for normal windows. All moved-window modes
        # share this buffer; do not finish it early based on native bounds.
        repaint_seconds = virtual_repaint_seconds(repaint_seconds)
        if repaint_seconds > 0:
            _wait_for_window_update(repaint_seconds)
        window_capture_rect(hwnd, display)
        yield destination
    finally:
        if win32gui.IsWindow(hwnd):
            win32gui.SetWindowPlacement(hwnd, placement)
            _wait_for_window_update(hwnd=hwnd)
            if placement[1] == win32con.SW_SHOWNORMAL:
                left, top, right, bottom = original_outer
                win32gui.SetWindowPos(
                    hwnd, 0, left, top, right-left, bottom-top,
                    win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE,
                )
            else:
                # The first placement crosses back to the source DPI, which
                # can scale rcNormalPosition. Reapply it at the original DPI
                # so a later user restore retains the saved normal size.
                win32gui.SetWindowPlacement(hwnd, placement)


def capture_display(service, settings, tr):
    """Select, preview and capture at native pixel resolution on Windows."""
    display = automatic_display(tr)
    selector = QDialog()
    selector.setWindowTitle(tr("virtual_screen_capture"))
    layout = QVBoxLayout(selector)
    help_text = QLabel(tr("virtual_screen_help"))
    help_text.setWordWrap(True)
    layout.addWidget(help_text)
    form = QFormLayout()
    r = display.rect
    screen_label = QLabel(f"{display.device} — {r.width} × {r.height}")
    window_choice = QComboBox()
    window_choice.addItem(tr("virtual_screen_desktop"), None)
    for hwnd, title in windows():
        window_choice.addItem(title, hwnd)
    form.addRow(tr("virtual_screen_display"), screen_label)
    form.addRow(tr("virtual_screen_window"), window_choice)
    layout.addLayout(form)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(selector.accept)
    buttons.rejected.connect(selector.reject)
    layout.addWidget(buttons)
    if selector.exec() != QDialog.DialogCode.Accepted:
        return None
    hwnd = window_choice.currentData()
    import win32api
    monitor = win32api.MonitorFromWindow(int(selector.winId()), 2)
    if win32api.GetMonitorInfo(monitor)["Device"] == display.device:
        raise RuntimeError(tr("virtual_screen_separate"))
    preview = QDialog()
    preview.setWindowTitle(tr("virtual_screen_preview"))
    layout = QVBoxLayout(preview)
    hint = QLabel(tr("virtual_screen_preview_help"))
    hint.setWordWrap(True)
    layout.addWidget(hint)
    frame = QLabel()
    frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(frame, 1)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("virtual_screen_take"))
    buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
    buttons.accepted.connect(preview.accept)
    buttons.rejected.connect(preview.reject)
    layout.addWidget(buttons)
    # Keep the preview on the screen used for selection. It cannot cover the target.
    preview_screen = selector.screen()
    if preview_screen is not None:
        geometry = preview_screen.availableGeometry()
        preview.resize(min(900, geometry.width()*3//4), min(650, geometry.height()*3//4))
        preview.move(geometry.center() - preview.rect().center())
    errors = []

    def refresh():
        try:
            image = service._grab_rect(window_capture_rect(hwnd, display))
            frame.setPixmap(QPixmap.fromImage(pil_to_qimage(image)).scaled(
                frame.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        except Exception as exc:
            errors.append(exc)
            preview.reject()

    timer = QTimer(preview)
    timer.setInterval(500)
    timer.timeout.connect(refresh)
    with moved_window(hwnd, display, settings.virtual_repaint_seconds):
        try:
            timer.start()
            accepted = preview.exec() == QDialog.DialogCode.Accepted
        finally:
            timer.stop()
            preview.hide()
        if errors:
            raise errors[0]
        if not accepted:
            return None
        # Delay is applied after the preview has closed; grab original pixels.
        if settings.delay_seconds > 0 and service._countdown(settings.delay_seconds):
            return None
        rect = window_capture_rect(hwnd, display)
        image = service._grab_rect(rect)
        if settings.include_cursor:
            service._draw_cursor(image, rect)
        return image
