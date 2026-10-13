"""Virtual capture on macOS with AX window/control identity and native pixels.

Window/display rectangles are Quartz points. Only capture output is in pixels.
Native frameworks are loaded lazily so Windows never imports them.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import ctypes
import threading
import time
import uuid

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from fshot.capture import CaptureRect
from fshot.settings import CaptureMode
from fshot.platforms import macos


DISPLAY_KEY = "capture/macos_virtual_display_uuid"


def display_uuid(display_id: int) -> str:
    # Quartz does not export this public ColorSync function. Read its CFUUID
    # through the C ABI instead of persisting display IDs, which can change.
    graphics = ctypes.CDLL("/System/Library/Frameworks/ColorSync.framework/ColorSync")
    core = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    graphics.CGDisplayCreateUUIDFromDisplayID.argtypes = [ctypes.c_uint32]
    graphics.CGDisplayCreateUUIDFromDisplayID.restype = ctypes.c_void_p

    class UUIDBytes(ctypes.Structure):
        _fields_ = [("bytes", ctypes.c_ubyte * 16)]

    core.CFUUIDGetUUIDBytes.argtypes = [ctypes.c_void_p]
    core.CFUUIDGetUUIDBytes.restype = UUIDBytes
    core.CFRelease.argtypes = [ctypes.c_void_p]
    core.CFRelease.restype = None
    reference = graphics.CGDisplayCreateUUIDFromDisplayID(display_id)
    if not reference:
        raise RuntimeError("Could not identify the selected display.")
    try:
        return str(uuid.UUID(bytes=bytes(core.CFUUIDGetUUIDBytes(reference).bytes)))
    finally:
        core.CFRelease(reference)


@dataclass(frozen=True)
class Display:
    identifier: str
    display_id: int
    name: str
    rect: CaptureRect
    work_rect: CaptureRect
    pixel_width: int
    pixel_height: int


@dataclass(frozen=True)
class Target:
    element: object
    pid: int
    window_id: int
    control: object | None = None


def displays() -> list[Display]:
    appkit, quartz = macos._frameworks()
    primary_height = quartz.CGDisplayBounds(quartz.CGMainDisplayID()).size.height
    result = []
    for screen in appkit.NSScreen.screens():
        display_id = int(screen.deviceDescription()["NSScreenNumber"])
        if quartz.CGDisplayMirrorsDisplay(display_id) != quartz.kCGNullDirectDisplay:
            continue
        bounds = quartz.CGDisplayBounds(display_id)
        rect = CaptureRect(round(bounds.origin.x), round(bounds.origin.y),
                           round(bounds.size.width), round(bounds.size.height))
        usable = screen.visibleFrame()
        work = CaptureRect(round(usable.origin.x),
                           round(primary_height - usable.origin.y - usable.size.height),
                           round(usable.size.width), round(usable.size.height))
        mode = quartz.CGDisplayCopyDisplayMode(display_id)
        identifier = display_uuid(display_id)
        result.append(Display(identifier, display_id, str(screen.localizedName()), rect, work,
                              int(quartz.CGDisplayModeGetPixelWidth(mode)),
                              int(quartz.CGDisplayModeGetPixelHeight(mode))))
    return result


def resolve_display(saved: Display) -> Display:
    current = next((item for item in displays() if item.identifier == saved.identifier), None)
    if current is None:
        raise RuntimeError("The selected display is no longer connected.")
    if current != saved:
        raise RuntimeError("Display configuration changed. Select the display again.")
    return current


def choose_display(parent, settings: QSettings, tr) -> bool:
    import ScreenCaptureKit as sck

    if not hasattr(sck, "SCScreenshotManager"):
        raise RuntimeError(tr("mac_virtual_version"))
    if not macos.accessibility_allowed() or not macos.screen_recording_allowed():
        raise RuntimeError(tr("mac_virtual_permissions"))
    _appkit, quartz = macos._frameworks()
    choices = [item for item in displays() if item.display_id != quartz.CGMainDisplayID()
               and item.pixel_width >= 3840 and item.pixel_height >= 2160]
    if not choices:
        answer = QMessageBox.question(
            parent, "FShot", tr("mac_virtual_create_question"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        from fshot.platforms.macos_virtual_setup import ensure_display

        created = ensure_display(parent, settings, tr)
        settings.setValue(DISPLAY_KEY, created.identifier)
        return True
    labels = [f"{item.name} — {item.pixel_width} × {item.pixel_height} px "
              f"({item.rect.width} × {item.rect.height} pt) [{item.display_id}]" for item in choices]
    labels.append(tr("mac_virtual_create_option"))
    saved = settings.value(DISPLAY_KEY, "")
    initial = next((i for i, item in enumerate(choices) if item.identifier == saved), 0)
    label, accepted = QInputDialog.getItem(parent, tr("virtual_screen_display"),
                                          tr("mac_virtual_choose"), labels, initial, False)
    if not accepted:
        return False
    if label == labels[-1]:
        from fshot.platforms.macos_virtual_setup import ensure_display

        created = ensure_display(parent, settings, tr)
        settings.setValue(DISPLAY_KEY, created.identifier)
        return True
    settings.setValue(DISPLAY_KEY, choices[labels.index(label)].identifier)
    return True


def active_target() -> Target | None:
    import ApplicationServices as ax

    system = ax.AXUIElementCreateSystemWide()
    application = macos._ax_attribute(system, ax.kAXFocusedApplicationAttribute, ax)
    if application is None:
        return None
    window = macos._ax_attribute(application, ax.kAXFocusedWindowAttribute, ax)
    if window is None:
        return None
    error, pid = ax.AXUIElementGetPid(window, None)
    bounds = macos._ax_element_bounds(window, ax)
    if error != ax.kAXErrorSuccess or bounds is None:
        return None
    _appkit, quartz = macos._frameworks()
    candidates = []
    for info in quartz.CGWindowListCopyWindowInfo(
            quartz.kCGWindowListOptionOnScreenOnly | quartz.kCGWindowListExcludeDesktopElements,
            quartz.kCGNullWindowID) or ():
        if info.get(quartz.kCGWindowOwnerPID) == pid and info.get(quartz.kCGWindowLayer) == 0:
            frame = info.get(quartz.kCGWindowBounds)
            if frame and macos._bounds_tuple(frame) == bounds:
                candidates.append(int(info[quartz.kCGWindowNumber]))
    # Do not guess another window in the same application.
    return Target(window, int(pid), candidates[0]) if len(candidates) == 1 else None


def target_bounds(target: Target) -> CaptureRect | None:
    import ApplicationServices as ax

    if macos._window_for_id(target.window_id, target.pid) is None:
        return None
    error, pid = ax.AXUIElementGetPid(target.element, None)
    if error != ax.kAXErrorSuccess or pid != target.pid:
        return None
    bounds = macos._ax_element_bounds(target.element, ax)
    return CaptureRect(*bounds) if bounds else None


def _owner_element(native: macos.MacCaptureTarget):
    """Match an AX window to the selected CGWindowID, never the focused window."""
    import ApplicationServices as ax

    bounds = macos._window_for_id(native.window_id, native.owner_pid)
    if bounds is None:
        return None
    application = ax.AXUIElementCreateApplication(native.owner_pid)
    windows = macos._ax_attribute(application, ax.kAXWindowsAttribute, ax) or ()
    matches = [window for window in windows if macos._ax_element_bounds(window, ax) == bounds]
    return matches[0] if len(matches) == 1 else None


def _belongs_to_window(element, owner, pid: int) -> bool:
    import ApplicationServices as ax

    _appkit, quartz = macos._frameworks()
    error, actual_pid = ax.AXUIElementGetPid(element, None)
    if error != ax.kAXErrorSuccess or actual_pid != pid:
        return False
    window = macos._ax_attribute(element, ax.kAXWindowAttribute, ax)
    if window is not None:
        return bool(quartz.CFEqual(window, owner))
    current = element
    for _ in range(64):
        if current is None:
            return False
        if quartz.CFEqual(current, owner):
            return True
        current = macos._ax_attribute(current, ax.kAXParentAttribute, ax)
    return False


def target_from_selection(selected) -> Target:
    import ApplicationServices as ax

    native = selected.native_target
    if not isinstance(native, macos.MacCaptureTarget):
        raise RuntimeError("The selected target has no macOS window identity.")
    owner = _owner_element(native)
    if owner is None:
        raise RuntimeError("The selected target has no unique movable owning window.")
    control = native.element
    if control is not None:
        if not _belongs_to_window(control, owner, native.owner_pid):
            raise RuntimeError("The selected control does not belong to its recorded window.")
        role = macos._ax_attribute(control, ax.kAXRoleAttribute, ax)
        # Selecting the window frame/title bar means capturing the whole window.
        if role in {"AXWindow", "AXTitleBar"}:
            control = None
    return Target(owner, native.owner_pid, native.window_id, control)


def selected_bounds(target: Target) -> CaptureRect | None:
    """Read current AX geometry after layout; do not scale old control bounds."""
    import ApplicationServices as ax

    owner = target_bounds(target)
    if owner is None:
        return None
    if target.control is None:
        return owner
    if not _belongs_to_window(target.control, target.element, target.pid):
        return None
    if macos._ax_attribute(target.control, "AXHidden", ax):
        return None
    bounds = macos._ax_element_bounds(target.control, ax)
    return CaptureRect(*bounds).intersect(owner) if bounds else None


def raise_window(target: Target) -> None:
    import ApplicationServices as ax

    result = ax.AXUIElementPerformAction(target.element, ax.kAXRaiseAction)
    if result != ax.kAXErrorSuccess:
        raise RuntimeError("Could not bring the selected window forward.")


def validate_window(target: Target) -> None:
    import ApplicationServices as ax

    for attribute in (ax.kAXPositionAttribute, ax.kAXSizeAttribute):
        error, writable = ax.AXUIElementIsAttributeSettable(target.element, attribute, None)
        if error != ax.kAXErrorSuccess or not writable:
            raise RuntimeError("The target window cannot be moved or resized.")
    for attribute in (ax.kAXMinimizedAttribute, "AXFullScreen"):
        if macos._ax_attribute(target.element, attribute, ax):
            raise RuntimeError("Restore the target from minimized or full-screen mode first.")


def place_window(target: Target, rect: CaptureRect) -> None:
    import ApplicationServices as ax

    for attribute, kind, value in (
        (ax.kAXSizeAttribute, ax.kAXValueCGSizeType, (rect.width, rect.height)),
        (ax.kAXPositionAttribute, ax.kAXValueCGPointType, (rect.left, rect.top)),
    ):
        result = ax.AXUIElementSetAttributeValue(target.element, attribute, ax.AXValueCreate(kind, value))
        if result != ax.kAXErrorSuccess:
            raise RuntimeError(f"Could not update target window ({attribute}: {result}).")


def wait_for_bounds(target: Target, expected: CaptureRect) -> None:
    deadline = time.monotonic() + 1.5
    stable = 0
    while time.monotonic() < deadline:
        QApplication.processEvents()
        current = target_bounds(target)
        if current is None:
            raise RuntimeError("The target window has closed.")
        stable = stable + 1 if current == expected else 0
        if stable >= 3:
            return
        time.sleep(0.02)
    raise RuntimeError("The application did not accept the requested window geometry.")


def destination_rect(original: CaptureRect, source: Display, destination: Display) -> CaptureRect:
    width = max(1, round(original.width * destination.rect.width / source.rect.width))
    height = max(1, round(original.height * destination.rect.height / source.rect.height))
    work = destination.work_rect
    if width > work.width or height > work.height:
        raise RuntimeError("The proportional window size exceeds the destination work area.")
    return CaptureRect(work.left, work.top, width, height)


@contextmanager
def moved_window(target: Target, display: Display):
    validate_window(target)
    original = target_bounds(target)
    if original is None:
        raise RuntimeError("The target window has closed.")
    current = displays()
    source = max(current, key=lambda item: _intersection_area(item.rect, original), default=None)
    if source is None or _intersection_area(source.rect, original) == 0:
        raise RuntimeError("The source display could not be found.")
    resolve_display(display)
    if source.identifier == display.identifier:
        raise RuntimeError("Keep the target window on a different display before capture.")
    destination = destination_rect(original, source, display)
    try:
        place_window(target, destination)
        wait_for_bounds(target, destination)
        yield destination
    finally:
        if target_bounds(target) is not None:
            place_window(target, original)
            wait_for_bounds(target, original)


def _intersection_area(a: CaptureRect, b: CaptureRect) -> int:
    clipped = a.intersect(b)
    return clipped.width * clipped.height if clipped is not None else 0


def pixel_size(rect: CaptureRect, display: Display) -> tuple[int, int]:
    return (max(1, round(rect.width * display.pixel_width / display.rect.width)),
            max(1, round(rect.height * display.pixel_height / display.rect.height)))


def _await_native(start):
    """Bounded wait; callbacks may run on a native worker thread."""
    done = threading.Event()
    result = []

    def complete(value, error):
        result.append((value, error))
        done.set()

    start(complete)
    deadline = time.monotonic() + 10
    while not done.wait(0.01):
        QApplication.processEvents()
        if time.monotonic() >= deadline:
            raise RuntimeError("ScreenCaptureKit timed out.")
    value, error = result[0]
    if error is not None or value is None:
        raise RuntimeError(f"ScreenCaptureKit failed: {error}")
    return value


def capture_rect(display: Display, rect: CaptureRect, include_cursor: bool) -> Image.Image:
    import io
    import ScreenCaptureKit as sck

    appkit, quartz = macos._frameworks()
    if not hasattr(sck, "SCScreenshotManager"):
        raise RuntimeError("Virtual display capture requires macOS 14 or later.")
    resolve_display(display)
    if rect.intersect(display.rect) != rect:
        raise RuntimeError("The target window left the selected display.")
    content = _await_native(lambda callback:
        sck.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
            False, True, callback))
    native = next((item for item in content.displays() if item.displayID() == display.display_id), None)
    if native is None:
        raise RuntimeError("The selected display is not available for capture.")
    filter_ = sck.SCContentFilter.alloc().initWithDisplay_excludingWindows_(native, [])
    config = sck.SCStreamConfiguration.alloc().init()
    width, height = pixel_size(rect, display)
    config.setWidth_(width)
    config.setHeight_(height)
    config.setSourceRect_(quartz.CGRectMake(rect.left - display.rect.left,
                                         rect.top - display.rect.top, rect.width, rect.height))
    config.setShowsCursor_(include_cursor)
    image = _await_native(lambda callback:
        sck.SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_(filter_, config, callback))
    rep = appkit.NSBitmapImageRep.alloc().initWithCGImage_(image)
    data = rep.representationUsingType_properties_(appkit.NSBitmapImageFileTypePNG, {})
    if data is None:
        raise RuntimeError("Could not decode the captured image.")
    output = Image.open(io.BytesIO(bytes(data))).convert("RGB")
    if output.size != (width, height):
        raise RuntimeError("ScreenCaptureKit returned an unexpected pixel size.")
    return output


class VirtualCaptureSession:
    def __init__(self):
        self.last = None

    def active_target(self):
        return active_target()

    def capture(self, service, mode, settings, tr, target=None, frozen=None):
        if mode == CaptureMode.FULLSCREEN:
            # Preserve ordinary full-screen behavior, without moving a window.
            image = service.capture(mode, settings)
        elif mode == CaptureMode.REGION:
            raise RuntimeError(tr("virtual_region_unsupported"))
        else:
            if mode == CaptureMode.WINDOW_UNDER_CURSOR and target is None:
                selected = service._select_window_target(frozen)
                if selected is None:
                    return None
                target = target_from_selection(selected)
            if target is None:
                raise RuntimeError(tr("virtual_target_unavailable"))
            identifier = QSettings().value(DISPLAY_KEY, "")
            display = next((item for item in displays() if item.identifier == identifier), None)
            if display is None:
                raise RuntimeError(tr("mac_virtual_missing"))
            with moved_window(target, display) as rect:
                if mode == CaptureMode.WINDOW_UNDER_CURSOR:
                    raise_window(target)
                    QApplication.processEvents()
                if settings.delay_seconds > 0 and service._countdown(settings.delay_seconds):
                    return None
                resolve_display(display)
                if target_bounds(target) != rect:
                    raise RuntimeError(tr("virtual_target_unavailable"))
                capture_bounds = selected_bounds(target) if target.control is not None else rect
                if capture_bounds is None:
                    raise RuntimeError(tr("virtual_control_unavailable"))
                visible = macos._window_target_at_point(capture_bounds.left + capture_bounds.width // 2,
                                                        capture_bounds.top + capture_bounds.height // 2)
                if visible is None or visible[1:] != (target.window_id, target.pid):
                    raise RuntimeError(tr("virtual_target_obscured"))
                image = capture_rect(display, capture_bounds, settings.include_cursor)
        if image is not None:
            self.last = (mode, target)
        return image

    def repeat(self, service, settings, tr):
        if self.last is None:
            return None
        mode, target = self.last
        if target is not None and target_bounds(target) is None:
            return None
        if target is not None and target.control is not None and selected_bounds(target) is None:
            return None
        return self.capture(service, mode, settings, tr, target)
