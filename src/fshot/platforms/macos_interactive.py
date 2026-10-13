"""Bounded, non-activating virtual-display preview with native mouse forwarding."""
from __future__ import annotations

import math
import logging
import threading
import time

from PySide6.QtCore import QEventLoop, QObject, QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from fshot.capture import CaptureRect, _escape_pressed
from fshot.platforms import macos
from fshot.platforms.macos_virtual import (
    _await_native, capture_rect, raise_window, resolve_display, target_bounds,
)

log = logging.getLogger(__name__)
_WINDOW_LOCATION_API = None


def window_location_api():
    """Isolate the unsupported CG local-coordinate API required for direct post.

    Global CGEventSetLocation does not update this separate coordinate pair.
    Fail explicitly on systems without the symbols rather than drop clicks.
    """
    global _WINDOW_LOCATION_API
    if _WINDOW_LOCATION_API is None:
        import objc
        from Foundation import NSBundle

        functions = {}
        try:
            objc.loadBundleFunctions(
                NSBundle.bundleWithPath_("/System/Library/Frameworks/CoreGraphics.framework"),
                functions, [
                    ("CGEventSetWindowLocation", b"v^{__CGEvent=}{CGPoint=dd}"),
                    ("CGEventGetWindowLocation", b"{CGPoint=dd}^{__CGEvent=}"),
                ], skip_undefined=False)
        except (ImportError, AttributeError, objc.error) as exc:
            raise RuntimeError("This macOS version does not support window-local mouse forwarding.") from exc
        _WINDOW_LOCATION_API = functions
    return _WINDOW_LOCATION_API


def stamp_window_location(event, bounds: CaptureRect):
    """Set top-left window-relative points without changing global location."""
    _appkit, quartz = macos._frameworks()
    point = quartz.CGEventGetLocation(event)
    local = (point.x - bounds.left, point.y - bounds.top)
    functions = window_location_api()
    functions["CGEventSetWindowLocation"](event, local)
    actual = functions["CGEventGetWindowLocation"](event)
    if abs(actual.x - local[0]) > 0.01 or abs(actual.y - local[1]) > 0.01:
        raise RuntimeError("Could not set the forwarded event's window-local coordinates.")
    return local


def process_serial_number(pid):
    """Resolve the native process queue used by AppKit mouse delivery."""
    import ApplicationServices as services

    status, serial = services.GetProcessForPID(pid, None)
    if status != 0:
        raise RuntimeError(f"Could not resolve the target mouse event queue ({status}).")
    return serial


class Notifications(QObject):
    ready = Signal()


class FrameMailbox:
    """Only the newest owned image can be pending; native buffers are not retained."""

    def __init__(self):
        self.lock = threading.Lock()
        self.latest = None
        self.failure = None
        self.closed = False
        self.pending = False
        self.notifications = Notifications()

    def publish(self, image=None, error=None):
        with self.lock:
            if self.closed:
                return
            self.latest = image
            if error is not None:
                self.failure = error
            notify = not self.pending
            self.pending = True
        if notify:
            self.notifications.ready.emit()

    def take(self):
        with self.lock:
            self.pending = False
            if self.failure is not None:
                raise RuntimeError(str(self.failure))
            image, self.latest = self.latest, None
            return image

    def close(self):
        with self.lock:
            self.closed = True
            self.latest = None


_OUTPUT_CLASS = None


def stream_output_class():
    """Register once, lazily; Windows/offscreen tests do not load native frameworks."""
    global _OUTPUT_CLASS
    if _OUTPUT_CLASS is not None:
        return _OUTPUT_CLASS
    import objc
    import ScreenCaptureKit as sck
    from Foundation import NSObject

    class FShotStreamOutput(NSObject, protocols=[objc.protocolNamed("SCStreamOutput"),
                                                objc.protocolNamed("SCStreamDelegate")]):
        def stream_didOutputSampleBuffer_ofType_(self, stream, sample, type_):
            frames = self.frames
            if frames is not None and type_ == sck.SCStreamOutputTypeScreen:
                frames.receive(sample)

        def stream_didStopWithError_(self, stream, error):
            frames = self.frames
            if frames is not None:
                frames.mailbox.publish(error=error)

    _OUTPUT_CLASS = FShotStreamOutput
    return _OUTPUT_CLASS


class PreviewFrames:
    def __init__(self, display, size: QSize, dpr: float):
        self.display, self.size, self.dpr = display, size, dpr
        self.mailbox = FrameMailbox()
        self.stream = None
        self.output = None
        self.queue = None
        self.start_requested = False

    def start(self):
        import ScreenCaptureKit as sck
        import CoreMedia
        import libdispatch

        _appkit, quartz = macos._frameworks()
        resolve_display(self.display)
        content = _await_native(lambda callback:
            sck.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
                False, True, callback))
        native = next((item for item in content.displays() if item.displayID() == self.display.display_id), None)
        if native is None:
            raise RuntimeError("The virtual display is unavailable for preview.")
        filter_ = sck.SCContentFilter.alloc().initWithDisplay_excludingWindows_(native, [])
        config = sck.SCStreamConfiguration.alloc().init()
        config.setWidth_(self.size.width())
        config.setHeight_(self.size.height())
        config.setPixelFormat_(quartz.kCVPixelFormatType_32BGRA)
        config.setShowsCursor_(False)
        config.setMinimumFrameInterval_(CoreMedia.CMTimeMake(1, 30))
        config.setQueueDepth_(3)
        self.output = stream_output_class().alloc().init()
        self.output.frames = self
        self.stream = sck.SCStream.alloc().initWithFilter_configuration_delegate_(filter_, config, self.output)
        self.queue = libdispatch.dispatch_queue_create(b"fshot.preview", None)
        success, error = self.stream.addStreamOutput_type_sampleHandlerQueue_error_(
            self.output, sck.SCStreamOutputTypeScreen, self.queue, None)
        if not success:
            raise RuntimeError(f"Could not attach the preview stream: {error}")
        self.start_requested = True
        _await_native(lambda callback: self.stream.startCaptureWithCompletionHandler_(
            lambda error: callback(True, error)))

    def receive(self, sample):
        import CoreMedia
        import ScreenCaptureKit as sck

        _appkit, quartz = macos._frameworks()
        try:
            if self.mailbox.closed or not CoreMedia.CMSampleBufferIsValid(sample):
                return
            attachments = CoreMedia.CMSampleBufferGetSampleAttachmentsArray(sample, False)
            if attachments and int(attachments[0].get(sck.SCStreamFrameInfoStatus, -1)) != sck.SCFrameStatusComplete:
                return
            buffer = CoreMedia.CMSampleBufferGetImageBuffer(sample)
            if buffer is None:
                return
            flags = quartz.kCVPixelBufferLock_ReadOnly
            if quartz.CVPixelBufferLockBaseAddress(buffer, flags) != 0:
                raise RuntimeError("Could not read the preview frame.")
            try:
                width = quartz.CVPixelBufferGetWidth(buffer)
                height = quartz.CVPixelBufferGetHeight(buffer)
                stride = quartz.CVPixelBufferGetBytesPerRow(buffer)
                pointer = quartz.CVPixelBufferGetBaseAddress(buffer)
                if pointer is None:
                    return
                # Copy before unlocking: Qt must never paint a recycled CV buffer.
                image = QImage(pointer.as_buffer(stride * height), width, height, stride,
                               QImage.Format.Format_ARGB32).copy()
                image.setDevicePixelRatio(self.dpr)
            finally:
                quartz.CVPixelBufferUnlockBaseAddress(buffer, flags)
            self.mailbox.publish(image=image)
        except Exception as exc:
            self.mailbox.publish(error=exc)

    def stop(self):
        self.mailbox.close()
        try:
            if self.stream is not None and self.start_requested:
                _await_native(lambda callback: self.stream.stopCaptureWithCompletionHandler_(
                    lambda error: callback(True, error)))
        finally:
            if self.output is not None:
                self.output.frames = None
            self.stream = self.output = self.queue = None


def preview_position(point, preview: CaptureRect, display: CaptureRect, *, clamp=False):
    """Map the real pointer in the preview to Quartz points, independent of DPR."""
    x, y = point
    if preview.is_empty or display.is_empty:
        return None
    if not clamp and not (preview.left <= x < preview.left + preview.width
                          and preview.top <= y < preview.top + preview.height):
        return None
    return (min(display.left + display.width - 1, max(display.left,
                display.left + (x - preview.left) * display.width / preview.width)),
            min(display.top + display.height - 1, max(display.top,
                display.top + (y - preview.top) * display.height / preview.height)))


def mouse_event_source():
    """Keep synthetic state separate and explicitly permit real input throughout."""
    _appkit, quartz = macos._frameworks()
    source = quartz.CGEventSourceCreate(quartz.kCGEventSourceStatePrivate)
    if source is None:
        raise RuntimeError("Could not create the mouse forwarding event source.")
    quartz.CGEventSourceSetLocalEventsSuppressionInterval(source, 0.0)
    allowed = (quartz.kCGEventFilterMaskPermitLocalMouseEvents
               | quartz.kCGEventFilterMaskPermitLocalKeyboardEvents
               | quartz.kCGEventFilterMaskPermitSystemDefinedEvents)
    for state in (quartz.kCGEventSuppressionStateSuppressionInterval,
                  quartz.kCGEventSuppressionStateRemoteMouseDrag):
        quartz.CGEventSourceSetLocalEventsFilterDuringSuppressionState(source, allowed, state)
    return source


def window_bound_event(event, window_id: int, source):
    """Bind AppKit's actual window number, not just Quartz hit-test annotations."""
    appkit, quartz = macos._frameworks()
    type_ = quartz.CGEventGetType(event)
    scroll = type_ == quartz.kCGEventScrollWheel
    native = appkit.NSEvent.mouseEventWithType_location_modifierFlags_timestamp_windowNumber_context_eventNumber_clickCount_pressure_(
        quartz.kCGEventMouseMoved if scroll else type_, (0, 0),
        quartz.CGEventGetFlags(event), quartz.CGEventGetTimestamp(event) / 1_000_000_000,
        window_id, None,
        quartz.CGEventGetIntegerValueField(event, quartz.kCGMouseEventNumber),
        quartz.CGEventGetIntegerValueField(event, quartz.kCGMouseEventClickState),
        quartz.CGEventGetDoubleValueField(event, quartz.kCGMouseEventPressure),
    )
    if native is None or native.CGEvent() is None:
        raise RuntimeError("Could not construct a window-bound mouse event.")
    bound = quartz.CGEventCreateCopy(native.CGEvent())
    if bound is None:
        raise RuntimeError("Could not copy the window-bound event.")
    quartz.CGEventSetType(bound, type_)
    if source is not None:
        quartz.CGEventSetSource(bound, source)
    quartz.CGEventSetFlags(bound, quartz.CGEventGetFlags(event))
    quartz.CGEventSetLocation(bound, quartz.CGEventGetLocation(event))
    for name in ("kCGMouseEventButtonNumber", "kCGMouseEventDeltaX", "kCGMouseEventDeltaY"):
        field = getattr(quartz, name)
        quartz.CGEventSetIntegerValueField(bound, field, quartz.CGEventGetIntegerValueField(event, field))
    if scroll:
        # NSEvent's mouse factory cannot create wheel events. A window-bound
        # template supplies routing, then public CG fields preserve wheel data.
        for name in ("kCGScrollWheelEventDeltaAxis1", "kCGScrollWheelEventDeltaAxis2", "kCGScrollWheelEventDeltaAxis3",
                     "kCGScrollWheelEventPointDeltaAxis1", "kCGScrollWheelEventPointDeltaAxis2", "kCGScrollWheelEventPointDeltaAxis3",
                     "kCGScrollWheelEventIsContinuous", "kCGScrollWheelEventScrollPhase",
                     "kCGScrollWheelEventMomentumPhase", "kCGScrollWheelEventScrollCount"):
            field = getattr(quartz, name, None)
            if field is not None:
                quartz.CGEventSetIntegerValueField(bound, field, quartz.CGEventGetIntegerValueField(event, field))
        for name in ("kCGScrollWheelEventFixedPtDeltaAxis1", "kCGScrollWheelEventFixedPtDeltaAxis2", "kCGScrollWheelEventFixedPtDeltaAxis3"):
            field = getattr(quartz, name, None)
            if field is not None:
                quartz.CGEventSetDoubleValueField(bound, field, quartz.CGEventGetDoubleValueField(event, field))
    if appkit.NSEvent.eventWithCGEvent_(bound).windowNumber() != window_id:
        raise RuntimeError("The forwarded event lost its target window identity.")
    return bound


class MouseProxy:
    MARKER = 0x4653484F54

    def __init__(self, display: CaptureRect, preview: CaptureRect, target, initial: CaptureRect):
        self.display, self.preview, self.target = display, preview, target
        self.position = (initial.left + initial.width / 2, initial.top + initial.height / 2)
        self.over_preview = False
        self.failure = None
        self.cancelled = False
        self.frozen = False
        self.pressed = set()
        self.button_windows = {}
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.stopped = threading.Event()
        self.thread = None
        self.tap = None
        self.run_loop = None
        self.source = None
        self.event_source = None
        self.process_serial = None

    def start(self):
        appkit, quartz = macos._frameworks()
        if appkit.NSEvent.pressedMouseButtons():
            raise RuntimeError("Release the mouse buttons before starting the interactive preview.")
        self.event_source = mouse_event_source()
        self.process_serial = process_serial_number(self.target.pid)
        window_location_api()  # Check compatibility before consuming physical input.
        self.thread = threading.Thread(target=self._run, name="FShotMouseProxy", daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 3
        while not self.ready.wait(0.01):
            QApplication.processEvents()
            if time.monotonic() >= deadline:
                raise RuntimeError("Mouse forwarding could not start.")
        if self.failure is not None:
            raise RuntimeError(str(self.failure))

    @property
    def pointer(self):
        return self.position if self.over_preview else None

    def _window_at_position(self, position):
        _appkit, quartz = macos._frameworks()
        for info in visible_windows(self.target.pid):
            bounds = info.get(quartz.kCGWindowBounds)
            if bounds and macos._tuple_rect_contains(macos._bounds_tuple(bounds), *position):
                return int(info.get(quartz.kCGWindowNumber, 0))
        return 0

    def _route_event(self, event, window_id):
        _appkit, quartz = macos._frameworks()
        info = next((item for item in visible_windows(self.target.pid)
                     if item.get(quartz.kCGWindowNumber) == window_id), None)
        if info is None or not info.get(quartz.kCGWindowBounds):
            raise RuntimeError("The target mouse window disappeared before event dispatch.")
        bounds = CaptureRect(*macos._bounds_tuple(info[quartz.kCGWindowBounds]))
        event = window_bound_event(event, window_id, self.event_source)
        local = stamp_window_location(event, bounds)
        # Copies otherwise retain the physical preview's window annotation.
        for name in ("kCGMouseEventWindowUnderMousePointer",
                     "kCGMouseEventWindowUnderMousePointerThatCanHandleThisEvent"):
            field = getattr(quartz, name, None)
            if field is not None:
                quartz.CGEventSetIntegerValueField(event, field, window_id)
        quartz.CGEventSetIntegerValueField(event, quartz.kCGEventSourceUserData, self.MARKER)
        if quartz.CGEventGetType(event) in (quartz.kCGEventLeftMouseDown,
                                          quartz.kCGEventRightMouseDown,
                                          quartz.kCGEventOtherMouseDown):
            log.warning("FShot preview native coordinates: window=%s bounds=%s local=%s", window_id, bounds, local)
        # Use the process event queue, as in Hammerspoon's targeted event post.
        # Do not post globally: that would move the real pointer off the preview.
        quartz.CGEventPostToPSN(self.process_serial, event)

    def _run(self):
        _appkit, quartz = macos._frameworks()
        source = None
        try:
            events = (quartz.kCGEventMouseMoved, quartz.kCGEventLeftMouseDragged,
                      quartz.kCGEventRightMouseDragged, quartz.kCGEventOtherMouseDragged,
                      quartz.kCGEventLeftMouseDown, quartz.kCGEventLeftMouseUp,
                      quartz.kCGEventRightMouseDown, quartz.kCGEventRightMouseUp,
                      quartz.kCGEventOtherMouseDown, quartz.kCGEventOtherMouseUp,
                      quartz.kCGEventScrollWheel, quartz.kCGEventKeyDown)
            mask = sum(quartz.CGEventMaskBit(type_) for type_ in events)
            self.tap = quartz.CGEventTapCreate(quartz.kCGSessionEventTap, quartz.kCGHeadInsertEventTap,
                                             quartz.kCGEventTapOptionDefault, mask, self._event, None)
            if self.tap is None:
                raise RuntimeError("Mouse forwarding requires Accessibility/Input Monitoring permission.")
            source = quartz.CFMachPortCreateRunLoopSource(None, self.tap, 0)
            self.run_loop = quartz.CFRunLoopGetCurrent()
            quartz.CFRunLoopAddSource(self.run_loop, source, quartz.kCFRunLoopCommonModes)
            quartz.CGEventTapEnable(self.tap, True)
            self.ready.set()
            while not self.stopped.is_set():
                quartz.CFRunLoopRunInMode(quartz.kCFRunLoopDefaultMode, 0.05, False)
        except Exception as exc:
            self.failure = exc
        finally:
            self.ready.set()
            if self.tap is not None:
                quartz.CGEventTapEnable(self.tap, False)
                quartz.CFMachPortInvalidate(self.tap)
            if source is not None and self.run_loop is not None:
                quartz.CFRunLoopRemoveSource(self.run_loop, source, quartz.kCFRunLoopCommonModes)

    def _event(self, proxy, type_, event, refcon):
        _appkit, quartz = macos._frameworks()
        if type_ in (quartz.kCGEventTapDisabledByTimeout, quartz.kCGEventTapDisabledByUserInput):
            self.failure = RuntimeError("Mouse forwarding was disabled by macOS.")
            self.stopped.set()
            return event
        if quartz.CGEventGetIntegerValueField(event, quartz.kCGEventSourceUserData) == self.MARKER:
            return event
        if type_ == quartz.kCGEventKeyDown:
            if quartz.CGEventGetIntegerValueField(event, quartz.kCGKeyboardEventKeycode) == 53:
                self.cancelled = True
                return None
            return event
        try:
            with self.lock:
                motion = type_ in (quartz.kCGEventMouseMoved, quartz.kCGEventLeftMouseDragged,
                                   quartz.kCGEventRightMouseDragged, quartz.kCGEventOtherMouseDragged)
                if self.frozen:
                    return event if motion else None
                point = quartz.CGEventGetLocation(event)
                mapped = preview_position((point.x, point.y), self.preview, self.display,
                                          clamp=bool(self.pressed))
                down = type_ in (quartz.kCGEventLeftMouseDown, quartz.kCGEventRightMouseDown,
                                 quartz.kCGEventOtherMouseDown)
                if down:
                    log.warning("FShot preview click: type=%s physical=(%.1f,%.1f) preview=%s mapped=%s pid=%s",
                                type_, point.x, point.y, self.preview, mapped, self.target.pid)
                previous = self.position
                self.over_preview = mapped is not None
                if mapped is None:
                    return event  # Outside preview, physical input works normally.
                self.position = mapped
                button = quartz.CGEventGetIntegerValueField(event, quartz.kCGMouseEventButtonNumber)
                window_id = self.button_windows.get(button) or self._window_at_position(mapped)
                if down:
                    log.warning("FShot preview click target: window=%s queue=%s", window_id, self.process_serial)
                if not window_id:
                    return event if motion else None  # No unrelated app receives a preview click.
                forwarded = quartz.CGEventCreateCopy(event)
                if forwarded is None:
                    raise RuntimeError("Could not create a forwarded mouse event.")
                if self.event_source is not None:
                    flags = quartz.CGEventGetFlags(forwarded)
                    quartz.CGEventSetSource(forwarded, self.event_source)
                    quartz.CGEventSetFlags(forwarded, flags)
                quartz.CGEventSetLocation(forwarded, self.position)
                if motion:
                    # Location and delta must describe the same scaled motion;
                    # leaving the hardware delta would disagree on the target.
                    quartz.CGEventSetIntegerValueField(forwarded, quartz.kCGMouseEventDeltaX,
                                                      round(self.position[0] - previous[0]))
                    quartz.CGEventSetIntegerValueField(forwarded, quartz.kCGMouseEventDeltaY,
                                                      round(self.position[1] - previous[1]))
                self._route_event(forwarded, window_id)
                if down:
                    log.warning("FShot preview click submitted to process queue (delivery not acknowledged)")
                if type_ in (quartz.kCGEventLeftMouseDown, quartz.kCGEventRightMouseDown, quartz.kCGEventOtherMouseDown):
                    self.pressed.add(button)
                    self.button_windows[button] = window_id
                elif type_ in (quartz.kCGEventLeftMouseUp, quartz.kCGEventRightMouseUp, quartz.kCGEventOtherMouseUp):
                    self.pressed.discard(button)
                    self.button_windows.pop(button, None)
            # Let hardware motion update the real, visible physical pointer.
            # Consume preview clicks/wheel so the preview cannot steal focus.
            return event if motion else None
        except Exception as exc:
            self.failure = exc
            self.stopped.set()
            return event

    def _post_mouse(self, type_, position, button, window_id):
        _appkit, quartz = macos._frameworks()
        event = quartz.CGEventCreateMouseEvent(self.event_source, type_, position, button)
        if event is None:
            raise RuntimeError("Could not create a mouse event.")
        self._route_event(event, window_id)

    def freeze(self):
        with self.lock:
            self.frozen = True

    def stop(self):
        self.stopped.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
        _appkit, quartz = macos._frameworks()
        # Disable even if the run-loop worker did not exit within the bound.
        if self.tap is not None and quartz.CFMachPortIsValid(self.tap):
            quartz.CGEventTapEnable(self.tap, False)
            quartz.CFMachPortInvalidate(self.tap)
        errors = []
        for button in tuple(self.pressed):
            type_ = {0: quartz.kCGEventLeftMouseUp, 1: quartz.kCGEventRightMouseUp}.get(
                button, quartz.kCGEventOtherMouseUp)
            try:
                self._post_mouse(type_, self.position, button,
                                 self.button_windows.get(button, self.target.window_id))
            except Exception as exc:
                errors.append(exc)
        self.pressed.clear()
        self.button_windows.clear()
        if errors:
            raise RuntimeError("Could not fully restore mouse input: " + str(errors[0]))


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
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.winId()
        self.windowHandle().setScreen(screen)
        geometry = screen.availableGeometry()
        self.resize(max(200, geometry.width() - 64), max(160, geometry.height() - 64))
        self.move(geometry.center() - self.rect().center())

    def image_area(self):
        area = self.rect().adjusted(12, 64, -12, -12)
        scale = min(area.width() / self.display.width, area.height() / self.display.height)
        width, height = round(self.display.width * scale), round(self.display.height * scale)
        return QRect(area.center().x() - width // 2, area.center().y() - height // 2, width, height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#202124"))
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(self.rect().adjusted(12, 8, -12, -8), Qt.AlignmentFlag.AlignTop,
                         self.tr("mac_interactive_hint", seconds=self.remaining))
        area = self.image_area()
        if self.image is not None:
            painter.drawImage(area, self.image)
        if self.pointer is not None:
            x = area.left() + round((self.pointer[0] - self.display.left) * area.width() / self.display.width)
            y = area.top() + round((self.pointer[1] - self.display.top) * area.height() / self.display.height)
            for color, width in (("#000000", 4), ("#ffffff", 2)):
                painter.setPen(QPen(QColor(color), width))
                painter.drawLine(x - 7, y, x + 7, y)
                painter.drawLine(x, y - 7, x, y + 7)


def visible_windows(pid):
    _appkit, quartz = macos._frameworks()
    return [item for item in quartz.CGWindowListCopyWindowInfo(
        quartz.kCGWindowListOptionOnScreenOnly | quartz.kCGWindowListExcludeDesktopElements,
        quartz.kCGNullWindowID) or () if item.get(quartz.kCGWindowOwnerPID) == pid]


def capture_bounds(target, display, baseline) -> CaptureRect:
    _appkit, quartz = macos._frameworks()
    owner = target_bounds(target)
    if owner is None or owner.intersect(display.rect) != owner:
        raise RuntimeError("The target window has disappeared or left the virtual display.")
    hit = macos._window_target_at_point(owner.left + owner.width // 2, owner.top + owner.height // 2)
    if hit is None or hit[2] != target.pid or (hit[1] != target.window_id and hit[1] in baseline):
        raise RuntimeError("The target window is covered by another window.")
    rects = [owner]
    for item in visible_windows(target.pid):
        if item.get(quartz.kCGWindowNumber) in baseline:
            continue
        raw = item.get(quartz.kCGWindowBounds)
        if not raw:
            continue
        rect = CaptureRect(*macos._bounds_tuple(raw))
        # New same-app popups intersecting the owner or its menu-bar band can
        # extend beyond the main frame. Unrelated distant windows are excluded.
        if rect.intersect(display.rect) is not None and (
            rect.intersect(owner) is not None or rect.top < display.work_rect.top
        ):
            rects.append(rect)
    left, top = min(r.left for r in rects), min(r.top for r in rects)
    right, bottom = max(r.left + r.width for r in rects), max(r.top + r.height for r in rects)
    return CaptureRect(left, top, right - left, bottom - top).intersect(display.rect)


def focus_matches(target, baseline) -> bool:
    import ApplicationServices as ax

    appkit, quartz = macos._frameworks()
    front = appkit.NSWorkspace.sharedWorkspace().frontmostApplication()
    if front is None or front.processIdentifier() != target.pid:
        return False
    application = ax.AXUIElementCreateApplication(target.pid)
    window = macos._ax_attribute(application, ax.kAXFocusedWindowAttribute, ax)
    if window is None or quartz.CFEqual(window, target.element):
        return True
    bounds = macos._ax_element_bounds(window, ax)
    return bounds is not None and any(
        item.get(quartz.kCGWindowNumber) not in baseline
        and macos._bounds_tuple(item.get(quartz.kCGWindowBounds, {})) == bounds
        for item in visible_windows(target.pid) if item.get(quartz.kCGWindowBounds)
    )


def draw_preview_cursor(image, rect, display, position):
    """Compose the mapped cursor; the physical cursor remains on another screen."""
    if position is None or not (rect.left <= position[0] < rect.left + rect.width
                                and rect.top <= position[1] < rect.top + rect.height):
        return
    from PIL import Image

    cursor = macos.current_cursor_image()
    if cursor is None:
        return
    bitmap, hotspot_x, hotspot_y, _physical_x, _physical_y = cursor
    sx, sy = display.pixel_width / display.rect.width, display.pixel_height / display.rect.height
    bitmap = bitmap.resize((max(1, round(bitmap.width * sx)), max(1, round(bitmap.height * sy))),
                           Image.Resampling.LANCZOS)
    x = round((position[0] - rect.left - hotspot_x) * sx)
    y = round((position[1] - rect.top - hotspot_y) * sy)
    image.paste(bitmap, (x, y), bitmap)


def delayed_interactive_capture(service, display, target, settings, tr):
    appkit, quartz = macos._frameworks()
    point = quartz.CGEventGetLocation(quartz.CGEventCreate(None))
    if display.rect.left <= point.x < display.rect.left + display.rect.width and \
            display.rect.top <= point.y < display.rect.top + display.rect.height:
        raise RuntimeError(tr("virtual_interactive_screen"))
    screen = QGuiApplication.screenAt(QPoint(round(point.x), round(point.y)))
    if screen is None:
        raise RuntimeError(tr("virtual_interactive_screen"))
    owner = target_bounds(target)
    if owner is None:
        raise RuntimeError(tr("virtual_control_unavailable"))
    baseline = {item.get(quartz.kCGWindowNumber) for item in visible_windows(target.pid)}
    view = InteractiveMirror(display.rect, screen, tr)
    area = view.image_area()
    dpr = view.devicePixelRatioF()
    frames = PreviewFrames(display, QSize(round(area.width() * dpr), round(area.height() * dpr)), dpr)
    preview_origin = view.mapToGlobal(area.topLeft())
    preview_rect = CaptureRect(preview_origin.x(), preview_origin.y(), area.width(), area.height())
    mouse = MouseProxy(display.rect, preview_rect, target, owner)
    loop = QEventLoop()
    timer = QTimer(view)
    timer.setTimerType(Qt.TimerType.PreciseTimer)
    timer.setInterval(16)
    result, errors = [], []
    first_frame = None
    started = None
    last_display_check = last_target_check = 0
    closed = False
    exit_requested = False

    def quit_preview():
        nonlocal exit_requested
        exit_requested = True
        loop.quit()

    qt_application = QApplication.instance()
    qt_application.aboutToQuit.connect(quit_preview)

    def present():
        nonlocal first_frame
        if closed:
            return
        try:
            image = frames.mailbox.take()
            if image is not None:
                view.image = image
                if first_frame is None:
                    first_frame = time.monotonic()
                view.update()
        except Exception as exc:
            errors.append(exc)
            loop.quit()

    def refresh():
        nonlocal last_target_check, last_display_check
        try:
            if exit_requested:
                loop.quit()
                return
            if mouse.failure is not None:
                raise RuntimeError(tr("mac_interactive_input") + "\n" + str(mouse.failure))
            if mouse.cancelled or _escape_pressed():
                loop.quit()
                return
            now = time.monotonic()
            remaining = settings.delay_seconds - (now - started)
            if now - last_target_check >= 0.2 or remaining <= 0:
                if target_bounds(target) is None or not focus_matches(target, baseline):
                    raise RuntimeError(tr("virtual_interactive_focus"))
                last_target_check = now
            if now - last_display_check >= 1 or remaining <= 0:
                resolve_display(display)
                last_display_check = now
            pointer, seconds = mouse.pointer, max(0, math.ceil(remaining))
            if pointer != view.pointer or seconds != view.remaining:
                view.pointer, view.remaining = pointer, seconds
                view.update()
            if remaining <= 0:
                # Native waits process Qt events; prevent a second final capture
                # from re-entering this timeout callback during stream shutdown.
                timer.stop()
                mouse.freeze()
                frames.stop()
                rect = capture_bounds(target, display, baseline)
                image = capture_rect(display, rect, False)
                if settings.include_cursor:
                    draw_preview_cursor(image, rect, display, mouse.pointer)
                result.append(image)
                loop.quit()
        except Exception as exc:
            errors.append(exc)
            loop.quit()

    timer.timeout.connect(refresh)
    frames.mailbox.notifications.ready.connect(present, Qt.ConnectionType.QueuedConnection)
    try:
        frames.start()
        deadline = time.monotonic() + 10
        while first_frame is None:
            present()
            QApplication.processEvents()
            if errors:
                raise errors[0]
            if exit_requested or _escape_pressed():
                return None
            if time.monotonic() >= deadline:
                raise RuntimeError("The preview did not produce a frame.")
            time.sleep(0.01)
        if errors:
            raise errors[0]
        if exit_requested:
            return None
        view.remaining = math.ceil(settings.delay_seconds)
        view.show()
        QApplication.processEvents()
        # Native window placement may settle only after show(). Map that final
        # geometry, not the pre-show widget's tentative origin.
        origin = view.mapToGlobal(view.image_area().topLeft())
        actual_area = view.image_area()
        mouse.preview = CaptureRect(origin.x(), origin.y(), actual_area.width(), actual_area.height())
        if not focus_matches(target, baseline):
            target_application = appkit.NSRunningApplication.runningApplicationWithProcessIdentifier_(target.pid)
            if target_application is None or not target_application.activateWithOptions_(appkit.NSApplicationActivateIgnoringOtherApps):
                raise RuntimeError(tr("virtual_interactive_focus"))
            raise_window(target)
            QApplication.processEvents()
        if not focus_matches(target, baseline):
            raise RuntimeError(tr("virtual_interactive_focus"))
        mouse.start()
        started = time.monotonic()
        timer.start()
        loop.exec()
    finally:
        closed = True
        timer.stop()
        try:
            mouse.stop()
        finally:
            try:
                frames.stop()
            finally:
                try:
                    qt_application.aboutToQuit.disconnect(quit_preview)
                except (RuntimeError, TypeError):
                    pass  # Qt may already be shutting down; input is released.
                frames.mailbox.notifications.ready.disconnect(present)
                view.hide()
                view.image = None
                view.deleteLater()
    if errors:
        raise errors[0]
    return result[0] if result else None
