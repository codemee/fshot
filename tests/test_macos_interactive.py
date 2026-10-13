import sys
from types import SimpleNamespace

from PIL import Image
import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QColor

from fshot.capture import CaptureRect
from fshot.settings import CaptureSettings, CaptureMode
from fshot.platforms import macos_interactive as interactive
from fshot.platforms import macos_virtual as virtual


RECT = CaptureRect(1920, 0, 1920, 1080)
DISPLAY = virtual.Display("virtual", 70, "FShot-4K", RECT, CaptureRect(1920, 25, 1920, 1030), 3840, 2160)
OWNER = CaptureRect(1920, 25, 900, 600)
TARGET = virtual.Target(object(), 123, 456)
PREVIEW = CaptureRect(0, 0, 960, 540)


def test_mouse_mapping_uses_points_and_clamps_negative_origin():
    rect = CaptureRect(-1920, 0, 1920, 1080)
    preview = CaptureRect(100, 100, 960, 540)
    assert interactive.preview_position((610, 220), preview, rect) == (-900, 240)
    assert interactive.preview_position((1200, 0), preview, rect, clamp=True) == (-1, 0)
    assert interactive.preview_position((1200, 0), preview, rect) is None


def test_latest_frame_mailbox_has_one_notification_and_ignores_frames_after_close(qt_app):
    mailbox = interactive.FrameMailbox()
    notifications = []
    mailbox.notifications.ready.connect(lambda: notifications.append(True))
    mailbox.publish(image="old")
    mailbox.publish(image="new")
    assert notifications == [True]
    assert mailbox.take() == "new"
    mailbox.publish(error=RuntimeError("stream failed"))
    with pytest.raises(RuntimeError, match="stream failed"):
        mailbox.take()
    mailbox.close()
    mailbox.publish(image="late")
    assert mailbox.latest is None


def test_native_buffer_is_copied_before_unlock(qt_app, monkeypatch):
    raw = bytearray([0, 0, 255, 255] * 4)
    locks = []

    def unlock(buffer, flags):
        locks.append("unlock")
        raw[:] = bytes([255, 0, 0, 255] * 4)

    quartz = SimpleNamespace(
        kCVPixelBufferLock_ReadOnly=1,
        CVPixelBufferLockBaseAddress=lambda *args: (locks.append("lock") or 0),
        CVPixelBufferGetWidth=lambda buffer: 2,
        CVPixelBufferGetHeight=lambda buffer: 2,
        CVPixelBufferGetBytesPerRow=lambda buffer: 8,
        CVPixelBufferGetBaseAddress=lambda buffer: SimpleNamespace(as_buffer=lambda count: raw),
        CVPixelBufferUnlockBaseAddress=unlock,
    )
    monkeypatch.setitem(sys.modules, "CoreMedia", SimpleNamespace(
        CMSampleBufferIsValid=lambda sample: True,
        CMSampleBufferGetSampleAttachmentsArray=lambda *args: [{"status": 0}],
        CMSampleBufferGetImageBuffer=lambda sample: "buffer",
    ))
    monkeypatch.setitem(sys.modules, "ScreenCaptureKit", SimpleNamespace(SCStreamFrameInfoStatus="status", SCFrameStatusComplete=0))
    monkeypatch.setattr(interactive.macos, "_frameworks", lambda: (None, quartz))
    frames = interactive.PreviewFrames(DISPLAY, QSize(2, 2), 2)
    frames.receive("sample")
    image = frames.mailbox.take()
    assert image.pixelColor(0, 0) == QColor("red")
    assert image.devicePixelRatio() == 2
    assert locks == ["lock", "unlock"]


@pytest.mark.parametrize("outcome", ["capture", "recover_focus", "cancel", "input_error", "focus_error", "capture_error", "startup_error"])
def test_preview_countdown_and_cleanup(qt_app, monkeypatch, outcome):
    events = []
    monkeypatch.setattr(interactive, "_escape_pressed", lambda: False)
    monkeypatch.setattr(interactive, "target_bounds", lambda target: OWNER)
    monkeypatch.setattr(interactive, "visible_windows", lambda pid: [])
    monkeypatch.setattr(interactive, "resolve_display", lambda display: display)
    monkeypatch.setattr(interactive, "capture_bounds", lambda *args: OWNER)
    target_application = SimpleNamespace(activateWithOptions_=lambda options: True)
    appkit = SimpleNamespace(
        NSRunningApplication=SimpleNamespace(runningApplicationWithProcessIdentifier_=lambda pid: target_application),
        NSApplicationActivateIgnoringOtherApps=1,
    )
    monkeypatch.setattr(interactive, "raise_window", lambda target: None)
    monkeypatch.setattr(interactive.macos, "_frameworks", lambda: (appkit, SimpleNamespace(
        CGEventCreate=lambda source: None,
        CGEventGetLocation=lambda event: SimpleNamespace(x=10, y=10),
    )))
    focused = []

    def focus(*args):
        focused.append(True)
        if outcome == "recover_focus" and len(focused) == 1:
            return False
        return not (outcome == "focus_error" and len(focused) >= 3)

    monkeypatch.setattr(interactive, "focus_matches", focus)

    class Frames:
        def __init__(self, *args):
            self.mailbox = interactive.FrameMailbox()
            self.closed = False

        def start(self):
            if outcome == "startup_error":
                raise RuntimeError("stream startup failed")
            events.append("frame-ready")
            self.mailbox.publish(image=QImage(20, 20, QImage.Format.Format_ARGB32))

        def stop(self):
            if not self.closed:
                events.append("stream-stop")
            self.closed = True
            self.mailbox.close()

    class Mouse:
        def __init__(self, *args):
            self.failure = RuntimeError("input failed") if outcome == "input_error" else None
            self.cancelled = outcome == "cancel"
            self.position = (2000, 100)
            self.pointer = self.position

        def start(self):
            assert "frame-ready" in events
            events.append("mouse-start")

        def freeze(self):
            events.append("mouse-freeze")

        def stop(self):
            events.append("mouse-stop")

    def capture(display, rect, cursor):
        assert "stream-stop" in events
        assert "mouse-freeze" in events
        assert rect == OWNER
        events.append("native-capture")
        if outcome == "capture_error":
            raise RuntimeError("capture failed")
        return Image.new("RGB", (1800, 1200))

    monkeypatch.setattr(interactive, "PreviewFrames", Frames)
    monkeypatch.setattr(interactive, "MouseProxy", Mouse)
    monkeypatch.setattr(interactive, "capture_rect", capture)
    tr = lambda key, **values: key
    if outcome in {"input_error", "focus_error", "capture_error", "startup_error"}:
        with pytest.raises(RuntimeError):
            interactive.delayed_interactive_capture(None, DISPLAY, TARGET, CaptureSettings(delay_seconds=0.01), tr)
    else:
        result = interactive.delayed_interactive_capture(None, DISPLAY, TARGET, CaptureSettings(delay_seconds=0.01), tr)
        assert (result is not None) == (outcome in {"capture", "recover_focus"})
    assert "mouse-stop" in events
    assert "stream-stop" in events
    if outcome not in {"capture", "recover_focus", "capture_error"}:
        assert "native-capture" not in events


def test_active_delay_routes_to_preview_and_restores_window(qt_app, monkeypatch):
    from contextlib import contextmanager

    restored = []

    @contextmanager
    def moved(*args):
        try:
            yield OWNER
        finally:
            restored.append(True)

    monkeypatch.setattr(virtual, "QSettings", lambda: SimpleNamespace(value=lambda *args: "virtual"))
    monkeypatch.setattr(virtual, "displays", lambda: [DISPLAY])
    monkeypatch.setattr(virtual, "moved_window", moved)
    monkeypatch.setattr(interactive, "delayed_interactive_capture", lambda *args: Image.new("RGB", (1800, 1200)))
    session = virtual.VirtualCaptureSession()
    assert session.capture(None, CaptureMode.ACTIVE_WINDOW, CaptureSettings(delay_seconds=1),
                           lambda key: key, TARGET).size == (1800, 1200)
    assert restored == [True]
    assert session.last == (CaptureMode.ACTIVE_WINDOW, TARGET)


def test_injected_mouse_events_bypass_proxy_and_esc_is_consumed(monkeypatch):
    quartz = SimpleNamespace(
        kCGEventTapDisabledByTimeout=-1, kCGEventTapDisabledByUserInput=-2,
        kCGEventSourceUserData="marker", kCGEventKeyDown=10, kCGKeyboardEventKeycode="key",
        CGEventGetIntegerValueField=lambda event, field: event.get(field, 0),
    )
    monkeypatch.setattr(interactive.macos, "_frameworks", lambda: (None, quartz))
    mouse = interactive.MouseProxy(RECT, PREVIEW, TARGET, OWNER)
    own_event = {"marker": mouse.MARKER}
    assert mouse._event(None, 1, own_event, None) is own_event
    assert mouse._event(None, 10, {"key": 53}, None) is None
    assert mouse.cancelled
    mouse._event(None, -1, {}, None)
    assert mouse.failure is not None
    assert mouse.stopped.is_set()


def test_mouse_forwarding_keeps_flags_and_releases_pressed_buttons_on_stop(monkeypatch):
    names = ["MouseMoved", "LeftMouseDragged", "RightMouseDragged", "OtherMouseDragged",
             "LeftMouseDown", "LeftMouseUp", "RightMouseDown", "RightMouseUp",
             "OtherMouseDown", "OtherMouseUp", "ScrollWheel", "KeyDown"]
    constants = {"kCGEvent" + name: i for i, name in enumerate(names)}
    posted = []
    released = []
    quartz = SimpleNamespace(**constants,
        kCGEventTapDisabledByTimeout=-1, kCGEventTapDisabledByUserInput=-2,
        kCGEventSourceUserData="marker", kCGKeyboardEventKeycode="key",
        kCGMouseEventDeltaX="dx", kCGMouseEventDeltaY="dy", kCGMouseEventButtonNumber="button",
        kCGMouseEventWindowUnderMousePointer="window", kCGMouseEventWindowUnderMousePointerThatCanHandleThisEvent="handler-window",
        kCGSessionEventTap=1,
        CGEventGetIntegerValueField=lambda event, field: event.get(field, 0),
        CGEventCreateCopy=lambda event: dict(event),
        CGEventGetType=lambda event: event.get("type", -10),
        CGEventSetLocation=lambda event, point: event.__setitem__("position", point),
        CGEventSetIntegerValueField=lambda event, field, value: event.__setitem__(field, value),
        CGEventPost=lambda *args: pytest.fail("global cursor must not be moved"),
        CGEventPostToPid=lambda *args: pytest.fail("use the native process event queue"),
        CGEventPostToPSN=lambda serial, event: (event.__setitem__("queue", serial), posted.append(event)),
        CGEventGetLocation=lambda event: SimpleNamespace(x=event.get("x", 235), y=event.get("y", 182.5)),
        CGEventCreateMouseEvent=lambda source, type_, position, button:
            {"type": type_, "position": position, "button": button},
        CFMachPortIsValid=lambda tap: True,
        CGEventTapEnable=lambda tap, enabled: released.append(("enabled", enabled)),
        CFMachPortInvalidate=lambda tap: released.append(("invalidate", tap)),
    )
    monkeypatch.setattr(interactive.macos, "_frameworks", lambda: (None, quartz))
    mouse = interactive.MouseProxy(RECT, PREVIEW, TARGET, OWNER)
    mouse.process_serial = "target-process-queue"
    monkeypatch.setattr(mouse, "_window_at_position", lambda point: 456)
    monkeypatch.setattr(interactive, "window_bound_event", lambda event, window_id, source: event)
    monkeypatch.setattr(interactive, "stamp_window_location", lambda event, bounds:
                        event.__setitem__("local", (event["position"][0] - bounds.left,
                                                   event["position"][1] - bounds.top)))
    quartz.kCGWindowNumber, quartz.kCGWindowBounds = "id", "bounds"
    monkeypatch.setattr(interactive, "visible_windows", lambda pid:
                        [{"id": 456, "bounds": {"X": 1920, "Y": 25, "Width": 900, "Height": 600}}])
    mouse.tap = "tap"
    physical = {"x": 235, "y": 182.5, "dx": 10, "dy": 20, "flags": "shift"}
    assert mouse._event(None, quartz.kCGEventLeftMouseDragged, physical, None) is physical
    assert physical == {"x": 235, "y": 182.5, "dx": 10, "dy": 20, "flags": "shift"}
    assert mouse.position == (2390, 365)
    assert posted[-1]["flags"] == "shift"
    assert (posted[-1]["dx"], posted[-1]["dy"]) == (20, 40)
    assert posted[-1]["marker"] == mouse.MARKER
    assert posted[-1]["window"] == posted[-1]["handler-window"] == 456
    assert posted[-1]["local"] == (470, 340)
    mouse._event(None, quartz.kCGEventLeftMouseDown, {"button": 0}, None)
    assert mouse.pressed == {0}
    # A drag leaving the image remains captured until its release, at the edge.
    drag = {"x": 1200, "y": 600, "button": 0}
    assert mouse._event(None, quartz.kCGEventLeftMouseDragged, drag, None) is drag
    assert mouse.position == (3839, 1079)
    assert mouse.pointer == mouse.position
    before = len(posted)
    mouse.freeze()
    mouse._event(None, quartz.kCGEventScrollWheel, {}, None)
    assert len(posted) == before
    mouse.stop()
    assert released == [("enabled", False), ("invalidate", "tap")]
    assert posted[-1]["type"] == quartz.kCGEventLeftMouseUp
    assert all(event["queue"] == "target-process-queue" for event in posted)
    assert not mouse.pressed
    # Ordinary input outside the preview is never redirected after release.
    mouse.frozen = False
    outside = {"x": -10, "y": -10}
    before = len(posted)
    assert mouse._event(None, quartz.kCGEventLeftMouseDown, outside, None) is outside
    assert len(posted) == before
    assert mouse.pointer is None


def test_capture_includes_new_same_app_popup_but_not_old_or_distant_windows(monkeypatch):
    quartz = SimpleNamespace(kCGWindowNumber="id", kCGWindowBounds="bounds")
    monkeypatch.setattr(interactive.macos, "_frameworks", lambda: (None, quartz))
    monkeypatch.setattr(interactive, "target_bounds", lambda target: OWNER)
    monkeypatch.setattr(interactive.macos, "_window_target_at_point", lambda *args: (None, 456, 123))
    monkeypatch.setattr(interactive, "visible_windows", lambda pid: [
        {"id": 456, "bounds": {"X": 1920, "Y": 25, "Width": 900, "Height": 600}},
        {"id": 789, "bounds": {"X": 2750, "Y": 100, "Width": 300, "Height": 300}},
        {"id": 800, "bounds": {"X": 3500, "Y": 700, "Width": 200, "Height": 200}},
        {"id": 999, "bounds": {"X": 1920, "Y": 0, "Width": 1000, "Height": 1000}},
    ])
    assert interactive.capture_bounds(TARGET, DISPLAY, {456, 999}) == CaptureRect(1920, 25, 1130, 600)
    monkeypatch.setattr(interactive.macos, "_window_target_at_point", lambda *args: (None, 1234, 999))
    with pytest.raises(RuntimeError, match="covered"):
        interactive.capture_bounds(TARGET, DISPLAY, {456, 999})


def test_mouse_cleanup_attempts_every_release_even_after_one_failure(monkeypatch):
    quartz = SimpleNamespace(kCGEventLeftMouseUp=1, kCGEventRightMouseUp=2,
                             kCGEventOtherMouseUp=3, kCGEventMouseMoved=4)
    monkeypatch.setattr(interactive.macos, "_frameworks", lambda: (None, quartz))
    mouse = interactive.MouseProxy(RECT, PREVIEW, TARGET, OWNER)
    mouse.pressed = {0, 1}
    attempts = []

    def post(type_, position, button, window_id):
        attempts.append((type_, position, button))
        if type_ == 1:
            raise RuntimeError("release failed")

    monkeypatch.setattr(mouse, "_post_mouse", post)
    with pytest.raises(RuntimeError, match="fully restore"):
        mouse.stop()
    assert {type_ for type_, position, button in attempts} == {1, 2}
    assert not mouse.pressed


def test_synthetic_source_does_not_suppress_hardware_input(monkeypatch):
    configured = []
    quartz = SimpleNamespace(
        kCGEventSourceStatePrivate=-1,
        CGEventSourceCreate=lambda state: "private-source" if state == -1 else None,
        CGEventSourceSetLocalEventsSuppressionInterval=lambda source, seconds: configured.append(("interval", seconds)),
        kCGEventFilterMaskPermitLocalMouseEvents=1,
        kCGEventFilterMaskPermitLocalKeyboardEvents=2,
        kCGEventFilterMaskPermitSystemDefinedEvents=4,
        kCGEventSuppressionStateSuppressionInterval=0,
        kCGEventSuppressionStateRemoteMouseDrag=1,
        CGEventSourceSetLocalEventsFilterDuringSuppressionState=lambda source, mask, state:
            configured.append(("filter", mask, state)),
    )
    monkeypatch.setattr(interactive.macos, "_frameworks", lambda: (None, quartz))
    assert interactive.mouse_event_source() == "private-source"
    assert configured == [("interval", 0.0), ("filter", 7, 0), ("filter", 7, 1)]


def test_mouse_queue_resolution_checks_native_status(monkeypatch):
    calls = []
    service = SimpleNamespace(GetProcessForPID=lambda pid, output:
                              (calls.append((pid, output)) or (0, "queue")))
    monkeypatch.setitem(sys.modules, "ApplicationServices", service)
    assert interactive.process_serial_number(123) == "queue"
    assert calls == [(123, None)]
    service.GetProcessForPID = lambda pid, output: (-600, None)
    with pytest.raises(RuntimeError, match="event queue"):
        interactive.process_serial_number(123)


def test_mapped_cursor_is_composited_in_native_pixels(monkeypatch):
    monkeypatch.setattr(interactive.macos, "current_cursor_image", lambda:
                        (Image.new("RGBA", (2, 2), "red"), 1, 1, 10, 20))
    image = Image.new("RGB", (1800, 1200), "black")
    interactive.draw_preview_cursor(image, OWNER, DISPLAY, (1930, 45))
    assert image.getpixel((18, 38)) == (255, 0, 0)
    assert image.getpixel((17, 37)) == (0, 0, 0)


@pytest.mark.skipif(sys.platform != "darwin", reason="native AppKit in-memory roundtrip")
@pytest.mark.parametrize("right_up", [False, True])
def test_right_click_event_really_binds_appkit_window_number(right_up):
    import Quartz as q
    import AppKit as a

    source = interactive.mouse_event_source()
    type_ = q.kCGEventRightMouseUp if right_up else q.kCGEventRightMouseDown
    original = q.CGEventCreateMouseEvent(source, type_, (2000, 100), 1)
    q.CGEventSetIntegerValueField(original, q.kCGMouseEventClickState, 2)
    q.CGEventSetFlags(original, q.kCGEventFlagMaskShift)
    # The previous implementation's annotations do not bind NSEvent.window.
    q.CGEventSetIntegerValueField(original, q.kCGMouseEventWindowUnderMousePointer, 123)
    q.CGEventSetIntegerValueField(original, q.kCGMouseEventWindowUnderMousePointerThatCanHandleThisEvent, 123)
    assert a.NSEvent.eventWithCGEvent_(original).windowNumber() == 0
    bound = interactive.window_bound_event(original, 123, source)
    native = a.NSEvent.eventWithCGEvent_(bound)
    assert native.windowNumber() == 123
    assert q.CGEventGetType(bound) == type_
    assert q.CGEventGetIntegerValueField(bound, q.kCGMouseEventButtonNumber) == 1
    assert q.CGEventGetIntegerValueField(bound, q.kCGMouseEventClickState) == 2
    assert q.CGEventGetFlags(bound) == q.kCGEventFlagMaskShift
    assert q.CGEventGetLocation(bound) == q.CGEventGetLocation(original)


@pytest.mark.skipif(sys.platform != "darwin", reason="native AppKit in-memory roundtrip")
def test_wheel_event_keeps_window_number_delta_and_scroll_phase():
    import Quartz as q
    import AppKit as a

    source = interactive.mouse_event_source()
    original = q.CGEventCreateScrollWheelEvent(source, q.kCGScrollEventUnitPixel, 2, 5, -2)
    q.CGEventSetIntegerValueField(original, q.kCGScrollWheelEventScrollPhase, 2)
    bound = interactive.window_bound_event(original, 123, source)
    assert a.NSEvent.eventWithCGEvent_(bound).windowNumber() == 123
    assert q.CGEventGetType(bound) == q.kCGEventScrollWheel
    for field in (q.kCGScrollWheelEventDeltaAxis1, q.kCGScrollWheelEventDeltaAxis2,
                  q.kCGScrollWheelEventScrollPhase, q.kCGScrollWheelEventIsContinuous):
        assert q.CGEventGetIntegerValueField(bound, field) == q.CGEventGetIntegerValueField(original, field)


@pytest.mark.skipif(sys.platform != "darwin", reason="native coordinate storage, no events posted")
@pytest.mark.parametrize("origin", [(1920, 25), (-1920, -400)])
@pytest.mark.parametrize("kind", ["left", "right", "wheel"])
def test_forwarded_event_has_both_global_and_window_local_coordinates(origin, kind):
    import Quartz as q

    bounds = CaptureRect(*origin, 900, 600)
    position = (bounds.left + 80, bounds.top + 200)
    if kind == "wheel":
        original = q.CGEventCreateScrollWheelEvent(None, q.kCGScrollEventUnitPixel, 2, 5, -2)
        q.CGEventSetLocation(original, position)
    else:
        original = q.CGEventCreateMouseEvent(None,
                    q.kCGEventLeftMouseDown if kind == "left" else q.kCGEventRightMouseDown,
                    position, 0 if kind == "left" else 1)
    event = interactive.window_bound_event(original, 123, None)
    assert interactive.stamp_window_location(event, bounds) == (80, 200)
    actual = interactive.window_location_api()["CGEventGetWindowLocation"](event)
    assert (actual.x, actual.y) == (80, 200)
    global_ = q.CGEventGetLocation(event)
    assert (global_.x, global_.y) == position


def test_bad_native_window_location_is_not_silently_dispatched(monkeypatch):
    monkeypatch.setattr(interactive.macos, "_frameworks", lambda: (None, SimpleNamespace(
        CGEventGetLocation=lambda event: SimpleNamespace(x=2000, y=225))))
    monkeypatch.setattr(interactive, "window_location_api", lambda: {
        "CGEventSetWindowLocation": lambda event, local: None,
        "CGEventGetWindowLocation": lambda event: SimpleNamespace(x=-1, y=-1),
    })
    with pytest.raises(RuntimeError, match="window-local"):
        interactive.stamp_window_location(object(), CaptureRect(1920, 25, 900, 600))
