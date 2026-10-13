from __future__ import annotations

import threading
import os
from collections.abc import Callable
from dataclasses import dataclass

from PIL import Image


def _frameworks():
    try:
        import AppKit
        import Quartz
    except ImportError as exc:  # pragma: no cover - installation guard
        raise RuntimeError("macOS support requires the PyObjC AppKit and Quartz frameworks") from exc
    return AppKit, Quartz


def screen_recording_allowed(request: bool = False) -> bool:
    _appkit, quartz = _frameworks()
    if request and hasattr(quartz, "CGRequestScreenCaptureAccess"):
        return bool(quartz.CGRequestScreenCaptureAccess())
    if hasattr(quartz, "CGPreflightScreenCaptureAccess"):
        return bool(quartz.CGPreflightScreenCaptureAccess())
    return True


def accessibility_allowed(request: bool = False) -> bool:
    _frameworks()
    import ApplicationServices as accessibility

    options = {accessibility.kAXTrustedCheckOptionPrompt: bool(request)}
    return bool(accessibility.AXIsProcessTrustedWithOptions(options))


def active_window_bounds() -> tuple[int, int, int, int] | None:
    appkit, quartz = _frameworks()
    import ApplicationServices as accessibility

    system = accessibility.AXUIElementCreateSystemWide()
    result, application = accessibility.AXUIElementCopyAttributeValue(
        system,
        accessibility.kAXFocusedApplicationAttribute,
        None,
    )
    if result == accessibility.kAXErrorSuccess and application is not None:
        result, window = accessibility.AXUIElementCopyAttributeValue(
            application,
            accessibility.kAXFocusedWindowAttribute,
            None,
        )
        if result == accessibility.kAXErrorSuccess and window is not None:
            bounds = _ax_element_bounds(window, accessibility)
            if bounds is not None:
                return bounds

    frontmost = appkit.NSWorkspace.sharedWorkspace().frontmostApplication()
    if frontmost is None:
        return None
    pid = frontmost.processIdentifier()
    windows = quartz.CGWindowListCopyWindowInfo(
        quartz.kCGWindowListOptionOnScreenOnly | quartz.kCGWindowListExcludeDesktopElements,
        quartz.kCGNullWindowID,
    )
    candidates = []
    for window in windows or ():
        if (
            window.get(quartz.kCGWindowOwnerPID) != pid
            or window.get(quartz.kCGWindowLayer, 0) != 0
        ):
            continue
        bounds = window.get(quartz.kCGWindowBounds)
        if bounds:
            candidates.append(_bounds_tuple(bounds))
    return max(candidates, key=lambda rect: rect[2] * rect[3], default=None)


@dataclass(frozen=True)
class MacCaptureTarget:
    element: object | None
    window_id: int
    owner_pid: int


def rect_at_point(x: int, y: int) -> tuple[int, int, int, int] | None:
    """Return the smallest accessible element at a global Quartz point."""
    selected = capture_target_at_point(x, y)
    return selected[0] if selected is not None else None


def capture_target_at_point(
    x: int, y: int
) -> tuple[tuple[int, int, int, int], MacCaptureTarget] | None:
    """Return bounds and a stable native identity for the selected target."""
    _frameworks()
    import ApplicationServices as accessibility

    window = _window_target_at_point(x, y)
    if window is None:
        return None
    containing_window, window_id, owner_pid = window
    # Hit-test the underlying application, not the system-wide root: the
    # selection overlay belongs to FShot and otherwise hides its AX controls.
    application = accessibility.AXUIElementCreateApplication(owner_pid)
    result, element = accessibility.AXUIElementCopyElementAtPosition(application, float(x), float(y), None)
    if result == accessibility.kAXErrorSuccess and element is not None:
        pid_result, pid = accessibility.AXUIElementGetPid(element, None)
        if pid_result == accessibility.kAXErrorSuccess and pid == owner_pid and pid != os.getpid():
            rect = _ax_element_bounds(element, accessibility)
            if rect is not None and containing_window is not None:
                rect = _intersect_rects(rect, containing_window)
            # Chrome can return its bottom-left link URL status bubble for a
            # hit-test performed over the link. A valid hit-test target must
            # geometrically contain the queried cursor point.
            if rect is not None and not _tuple_rect_contains(rect, x, y):
                return containing_window, MacCaptureTarget(None, window_id, owner_pid)
            if rect is not None and rect[2] >= 3 and rect[3] >= 3:
                return rect, MacCaptureTarget(element, window_id, owner_pid)
    return containing_window, MacCaptureTarget(None, window_id, owner_pid)


def capture_target_bounds(target: MacCaptureTarget) -> tuple[int, int, int, int] | None:
    """Resolve a previously selected target, returning None after it disappears."""
    _frameworks()
    import ApplicationServices as accessibility

    window = _window_for_id(target.window_id, target.owner_pid)
    if window is None:
        return None
    if target.element is None:
        return window
    pid_result, pid = accessibility.AXUIElementGetPid(target.element, None)
    if pid_result != accessibility.kAXErrorSuccess or pid != target.owner_pid:
        return None
    rect = _ax_element_bounds(target.element, accessibility)
    if rect is None:
        return None
    return _intersect_rects(rect, window)


def window_at_point(x: int, y: int) -> tuple[int, int, int, int] | None:
    target = _window_target_at_point(x, y)
    return target[0] if target is not None else None


def _window_target_at_point(
    x: int, y: int
) -> tuple[tuple[int, int, int, int], int, int] | None:
    _appkit, quartz = _frameworks()
    windows = quartz.CGWindowListCopyWindowInfo(
        quartz.kCGWindowListOptionOnScreenOnly | quartz.kCGWindowListExcludeDesktopElements,
        quartz.kCGNullWindowID,
    )
    for window in windows or ():
        if window.get(quartz.kCGWindowLayer, 0) != 0:
            continue
        if window.get(quartz.kCGWindowOwnerPID) == os.getpid():
            continue
        bounds = window.get(quartz.kCGWindowBounds)
        if not bounds:
            continue
        left, top, width, height = _bounds_tuple(bounds)
        if left <= x < left + width and top <= y < top + height:
            return (
                (left, top, width, height),
                int(window.get(quartz.kCGWindowNumber, 0)),
                int(window.get(quartz.kCGWindowOwnerPID, 0)),
            )
    return None


def _window_for_id(window_id: int, owner_pid: int) -> tuple[int, int, int, int] | None:
    _appkit, quartz = _frameworks()
    windows = quartz.CGWindowListCopyWindowInfo(
        quartz.kCGWindowListOptionOnScreenOnly | quartz.kCGWindowListExcludeDesktopElements,
        quartz.kCGNullWindowID,
    )
    for window in windows or ():
        if (
            int(window.get(quartz.kCGWindowNumber, 0)) != window_id
            or int(window.get(quartz.kCGWindowOwnerPID, 0)) != owner_pid
            or window.get(quartz.kCGWindowLayer, 0) != 0
        ):
            continue
        bounds = window.get(quartz.kCGWindowBounds)
        return _bounds_tuple(bounds) if bounds else None
    return None


def current_cursor_image() -> tuple[Image.Image, int, int, int, int] | None:
    appkit, _quartz = _frameworks()
    cursor = appkit.NSCursor.currentSystemCursor()
    if cursor is None:
        return None
    ns_image = cursor.image()
    data = ns_image.TIFFRepresentation()
    if data is None:
        return None
    import io

    image = Image.open(io.BytesIO(bytes(data))).convert("RGBA")
    logical_size = ns_image.size()
    target_size = (max(1, round(logical_size.width)), max(1, round(logical_size.height)))
    if image.size != target_size:
        image = image.resize(target_size, Image.Resampling.LANCZOS)
    hotspot = cursor.hotSpot()
    location = appkit.NSEvent.mouseLocation()
    # AppKit mouse coordinates start at the bottom-left; Quartz/Qt capture
    # coordinates start at the top-left of the global display space.
    max_y = max(
        screen.frame().origin.y + screen.frame().size.height
        for screen in appkit.NSScreen.screens()
    )
    return image, round(hotspot.x), round(hotspot.y), round(location.x), round(max_y - location.y)


def _ax_element_bounds(element, quartz) -> tuple[int, int, int, int] | None:
    result, position = quartz.AXUIElementCopyAttributeValue(element, quartz.kAXPositionAttribute, None)
    if result != quartz.kAXErrorSuccess:
        return None
    result, size = quartz.AXUIElementCopyAttributeValue(element, quartz.kAXSizeAttribute, None)
    if result != quartz.kAXErrorSuccess:
        return None
    pos = quartz.AXValueGetValue(position, quartz.kAXValueCGPointType, None)
    dimensions = quartz.AXValueGetValue(size, quartz.kAXValueCGSizeType, None)
    if not pos or not dimensions:
        return None
    if isinstance(pos, tuple) and len(pos) == 2 and isinstance(pos[0], bool):
        if not pos[0]:
            return None
        pos = pos[1]
    if (
        isinstance(dimensions, tuple)
        and len(dimensions) == 2
        and isinstance(dimensions[0], bool)
    ):
        if not dimensions[0]:
            return None
        dimensions = dimensions[1]
    pos_x, pos_y = (pos.x, pos.y) if hasattr(pos, "x") else pos
    width, height = (
        (dimensions.width, dimensions.height)
        if hasattr(dimensions, "width")
        else dimensions
    )
    rect = round(pos_x), round(pos_y), round(width), round(height)
    return rect if rect[2] >= 3 and rect[3] >= 3 else None


def _ax_attribute(element, attribute, accessibility):
    result, value = accessibility.AXUIElementCopyAttributeValue(element, attribute, None)
    return value if result == accessibility.kAXErrorSuccess else None


def _ax_ancestry_has_any_role(
    element,
    roles: set[object],
    accessibility,
    limit: int = 64,
) -> bool:
    current = element
    for _ in range(limit):
        if _ax_attribute(current, accessibility.kAXRoleAttribute, accessibility) in roles:
            return True
        current = _ax_attribute(current, accessibility.kAXParentAttribute, accessibility)
        if current is None:
            return False
    return False


def _ax_role_path(element, accessibility, limit: int = 64) -> tuple[object, ...]:
    roles = []
    current = element
    for _ in range(limit):
        roles.append(_ax_attribute(current, accessibility.kAXRoleAttribute, accessibility))
        current = _ax_attribute(current, accessibility.kAXParentAttribute, accessibility)
        if current is None:
            break
    return tuple(roles)


def _bounds_tuple(bounds) -> tuple[int, int, int, int]:
    return (
        round(bounds.get("X", 0)),
        round(bounds.get("Y", 0)),
        round(bounds.get("Width", 0)),
        round(bounds.get("Height", 0)),
    )


def _intersect_rects(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[0] + left[2], right[0] + right[2])
    y2 = min(left[1] + left[3], right[1] + right[3])
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2 - x1, y2 - y1


def _tuple_rect_contains(rect: tuple[int, int, int, int], x: int, y: int) -> bool:
    return rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]




@dataclass
class MacHotkeyListener:
    callback: Callable[[object], None]
    bindings: tuple[object, ...]

    def __post_init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._run_loop = None
        self._tap = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="FShotHotkeys", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._run_loop is not None:
            _appkit, quartz = _frameworks()
            quartz.CFRunLoopStop(self._run_loop)
        self._thread = None

    def _run(self) -> None:  # pragma: no cover - native event loop
        _appkit, quartz = _frameworks()
        mask = quartz.CGEventMaskBit(quartz.kCGEventKeyDown)
        self._tap = quartz.CGEventTapCreate(
            quartz.kCGSessionEventTap,
            quartz.kCGHeadInsertEventTap,
            quartz.kCGEventTapOptionDefault,
            mask,
            self._event_callback,
            None,
        )
        if self._tap is None:
            return
        source = quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        self._run_loop = quartz.CFRunLoopGetCurrent()
        quartz.CFRunLoopAddSource(self._run_loop, source, quartz.kCFRunLoopCommonModes)
        quartz.CGEventTapEnable(self._tap, True)
        quartz.CFRunLoopRun()

    def _event_callback(self, _proxy, event_type, event, _refcon):  # pragma: no cover - native callback
        _appkit, quartz = _frameworks()
        if event_type == quartz.kCGEventTapDisabledByTimeout:
            quartz.CGEventTapEnable(self._tap, True)
            return event
        flags = quartz.CGEventGetFlags(event)
        keycode = quartz.CGEventGetIntegerValueField(event, quartz.kCGKeyboardEventKeycode)
        key = {
            0: "a", 11: "b", 8: "c", 2: "d", 14: "e", 3: "f", 5: "g", 4: "h",
            34: "i", 38: "j", 40: "k", 37: "l", 46: "m", 45: "n", 31: "o", 35: "p",
            12: "q", 15: "r", 1: "s", 17: "t", 32: "u", 9: "v", 13: "w", 7: "x",
            16: "y", 6: "z",
        }.get(keycode)
        candidates = [item for item in self.bindings if item.letter.lower() == key]
        if not candidates:
            return event
        relevant = (
            quartz.kCGEventFlagMaskControl
            | quartz.kCGEventFlagMaskShift
            | quartz.kCGEventFlagMaskAlternate
        )
        actual = flags & relevant
        for combination in candidates:
            needed = (
                (quartz.kCGEventFlagMaskControl if combination.ctrl else 0)
                | (quartz.kCGEventFlagMaskShift if combination.shift else 0)
                | (quartz.kCGEventFlagMaskAlternate if combination.alt else 0)
            )
            if actual == needed:
                self.callback(combination)
                return None  # consume the shortcut instead of forwarding it
        return event
