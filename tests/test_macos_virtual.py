from types import SimpleNamespace

from PIL import Image
import pytest

from fshot.capture import CaptureRect
from fshot.platforms import macos_virtual as virtual
from fshot.settings import CaptureMode, CaptureSettings


SOURCE = virtual.Display("source", 1, "Built-in", CaptureRect(0, 0, 1440, 900),
                         CaptureRect(0, 25, 1440, 850), 2880, 1800)
DESTINATION = virtual.Display("virtual", 2, "Virtual", CaptureRect(-1920, 0, 1920, 1080),
                              CaptureRect(-1920, 25, 1920, 1030), 3840, 2160)
ORIGINAL = CaptureRect(30, 50, 720, 450)
TARGET = virtual.Target(object(), 123, 456)


def test_hidpi_placement_uses_points_and_capture_uses_pixels():
    destination = virtual.destination_rect(ORIGINAL, SOURCE, DESTINATION)
    assert destination == CaptureRect(-1920, 25, 960, 540)
    assert virtual.pixel_size(destination, DESTINATION) == (1920, 1080)


@pytest.mark.parametrize("outcome", ["success", "capture_error", "partial_move"])
def test_original_geometry_restored_after_success_and_failures(monkeypatch, outcome):
    frame = [ORIGINAL]
    moves = []
    monkeypatch.setattr(virtual, "displays", lambda: [SOURCE, DESTINATION])
    monkeypatch.setattr(virtual, "validate_window", lambda target: None)
    monkeypatch.setattr(virtual, "target_bounds", lambda target: frame[0])

    def place(target, rect):
        moves.append(rect)
        frame[0] = rect
        if outcome == "partial_move" and len(moves) == 1:
            raise RuntimeError("partial move")

    monkeypatch.setattr(virtual, "place_window", place)
    monkeypatch.setattr(virtual, "wait_for_bounds", lambda target, expected: None)

    def run():
        with virtual.moved_window(TARGET, DESTINATION):
            if outcome == "capture_error":
                raise RuntimeError("capture failed")

    if outcome != "success":
        with pytest.raises(RuntimeError):
            run()
    else:
        run()
    assert len(moves) == 2
    assert frame[0] == ORIGINAL


def test_changed_or_disconnected_display_is_rejected(monkeypatch):
    monkeypatch.setattr(virtual, "displays", lambda: [])
    with pytest.raises(RuntimeError, match="no longer connected"):
        virtual.resolve_display(DESTINATION)
    monkeypatch.setattr(virtual, "displays", lambda: [
        virtual.Display("virtual", 2, "Virtual", DESTINATION.rect, DESTINATION.work_rect, 1920, 1080)
    ])
    with pytest.raises(RuntimeError, match="configuration changed"):
        virtual.resolve_display(DESTINATION)


def test_oversized_window_is_rejected_before_move():
    with pytest.raises(RuntimeError, match="work area"):
        virtual.destination_rect(SOURCE.rect, SOURCE, DESTINATION)


@pytest.mark.parametrize("outcome", ["success", "cancel", "error"])
def test_capture_session_restores_window_and_only_remembers_success(monkeypatch, outcome):
    frame = [ORIGINAL]
    moves = []
    monkeypatch.setattr(virtual, "displays", lambda: [SOURCE, DESTINATION])
    monkeypatch.setattr(virtual, "QSettings", lambda: SimpleNamespace(value=lambda *args: "virtual"))
    monkeypatch.setattr(virtual, "validate_window", lambda target: None)
    monkeypatch.setattr(virtual, "target_bounds", lambda target: frame[0])
    monkeypatch.setattr(virtual, "wait_for_bounds", lambda *args: None)
    monkeypatch.setattr(virtual, "raise_window", lambda target: None)
    monkeypatch.setattr(virtual.macos, "_window_target_at_point", lambda *args: (None, 456, 123))

    def place(target, rect):
        moves.append(rect)
        frame[0] = rect

    def capture(*args):
        if outcome == "error":
            raise RuntimeError("capture failed")
        return Image.new("RGB", (1920, 1080))

    monkeypatch.setattr(virtual, "place_window", place)
    monkeypatch.setattr(virtual, "capture_rect", capture)
    service = SimpleNamespace(_countdown=lambda seconds: outcome == "cancel")
    settings = CaptureSettings(delay_seconds=1)
    session = virtual.VirtualCaptureSession()
    if outcome == "error":
        with pytest.raises(RuntimeError, match="capture failed"):
            session.capture(service, CaptureMode.WINDOW_UNDER_CURSOR, settings, lambda key: key, TARGET)
    else:
        result = session.capture(service, CaptureMode.WINDOW_UNDER_CURSOR, settings, lambda key: key, TARGET)
        assert (result is not None) == (outcome == "success")
    assert moves[-1] == ORIGINAL
    assert (session.last is not None) == (outcome == "success")


def test_virtual_region_selection_remains_unsupported():
    session = virtual.VirtualCaptureSession()
    with pytest.raises(RuntimeError, match="virtual_region_unsupported"):
        session.capture(None, CaptureMode.REGION, CaptureSettings(), lambda key: key)


@pytest.mark.parametrize("control", [False, True])
def test_selection_reads_live_control_bounds_and_repeats_same_identity(qt_app, monkeypatch, control):
    from dataclasses import replace

    frame = [ORIGINAL]
    cropped = []
    selected = object()
    target = replace(TARGET, control=object() if control else None)
    monkeypatch.setattr(virtual, "QSettings", lambda: SimpleNamespace(value=lambda *args: "virtual"))
    monkeypatch.setattr(virtual, "displays", lambda: [SOURCE, DESTINATION])
    monkeypatch.setattr(virtual, "validate_window", lambda target: None)
    monkeypatch.setattr(virtual, "wait_for_bounds", lambda *args: None)
    monkeypatch.setattr(virtual, "target_bounds", lambda target: frame[0])
    monkeypatch.setattr(virtual, "place_window", lambda target, rect: frame.__setitem__(0, rect))
    monkeypatch.setattr(virtual, "target_from_selection", lambda result: target if result is selected else None)
    monkeypatch.setattr(virtual, "raise_window", lambda target: None)
    monkeypatch.setattr(virtual.macos, "_window_target_at_point", lambda *args: (None, 456, 123))

    def live_bounds(target):
        # Simulates a responsive layout moving the selected control after resize.
        r = frame[0]
        return CaptureRect(r.left + 100, r.top + 80, 200, 40)

    monkeypatch.setattr(virtual, "selected_bounds", live_bounds)
    monkeypatch.setattr(virtual, "capture_rect", lambda display, rect, cursor:
                        (cropped.append(rect) or Image.new("RGB", virtual.pixel_size(rect, display))))
    selections = []
    service = SimpleNamespace(_select_window_target=lambda frozen: (selections.append(frozen) or selected))
    session = virtual.VirtualCaptureSession()
    image = session.capture(service, CaptureMode.WINDOW_UNDER_CURSOR, CaptureSettings(), lambda key: key,
                            frozen="saved snapshot")
    moved = virtual.destination_rect(ORIGINAL, SOURCE, DESTINATION)
    expected = CaptureRect(moved.left + 100, moved.top + 80, 200, 40) if control else moved
    assert cropped == [expected]
    assert image.size == virtual.pixel_size(expected, DESTINATION)
    assert frame[0] == ORIGINAL
    assert session.last == (CaptureMode.WINDOW_UNDER_CURSOR, target)
    session.repeat(service, CaptureSettings(), lambda key: key)
    assert cropped == [expected, expected]
    assert selections == ["saved snapshot"]


def test_selection_cancel_does_not_move_or_replace_previous_capture(monkeypatch):
    session = virtual.VirtualCaptureSession()
    session.last = (CaptureMode.ACTIVE_WINDOW, TARGET)
    service = SimpleNamespace(_select_window_target=lambda frozen: None)
    monkeypatch.setattr(virtual, "moved_window", lambda *args: pytest.fail("window moved after cancel"))
    assert session.capture(service, CaptureMode.WINDOW_UNDER_CURSOR, CaptureSettings(), lambda key: key) is None
    assert session.last == (CaptureMode.ACTIVE_WINDOW, TARGET)


def test_control_disappearing_after_move_restores_owner(qt_app, monkeypatch):
    from contextlib import contextmanager
    from dataclasses import replace

    restored = []
    target = replace(TARGET, control=object())

    @contextmanager
    def moved(*args):
        try:
            yield ORIGINAL
        finally:
            restored.append(True)

    monkeypatch.setattr(virtual, "QSettings", lambda: SimpleNamespace(value=lambda *args: "virtual"))
    monkeypatch.setattr(virtual, "displays", lambda: [DESTINATION])
    monkeypatch.setattr(virtual, "moved_window", moved)
    monkeypatch.setattr(virtual, "raise_window", lambda target: None)
    monkeypatch.setattr(virtual, "target_bounds", lambda target: ORIGINAL)
    monkeypatch.setattr(virtual, "selected_bounds", lambda target: None)
    monkeypatch.setattr(virtual, "capture_rect", lambda *args: pytest.fail("missing control captured"))
    with pytest.raises(RuntimeError, match="virtual_control_unavailable"):
        virtual.VirtualCaptureSession().capture(
            None, CaptureMode.WINDOW_UNDER_CURSOR, CaptureSettings(), lambda key: key, target
        )
    assert restored == [True]


def test_selected_bounds_validates_owner_and_clips_live_control(monkeypatch):
    import sys
    from dataclasses import replace

    control = object()
    target = replace(TARGET, control=control)
    monkeypatch.setitem(sys.modules, "ApplicationServices", SimpleNamespace())
    monkeypatch.setattr(virtual, "target_bounds", lambda target: ORIGINAL)
    monkeypatch.setattr(virtual, "_belongs_to_window", lambda *args: True)
    monkeypatch.setattr(virtual.macos, "_ax_attribute", lambda *args: False)
    monkeypatch.setattr(virtual.macos, "_ax_element_bounds", lambda *args: (20, 60, 100, 40))
    assert virtual.selected_bounds(target) == CaptureRect(30, 60, 90, 40)
    monkeypatch.setattr(virtual, "_belongs_to_window", lambda *args: False)
    assert virtual.selected_bounds(target) is None


@pytest.mark.parametrize("role,whole_window", [("AXWindow", True), ("AXTitleBar", True), ("AXButton", False)])
def test_selection_maps_owner_and_distinguishes_window_from_control(monkeypatch, role, whole_window):
    import sys
    from fshot.capture import WindowCaptureTarget

    ax = SimpleNamespace(kAXRoleAttribute="role")
    monkeypatch.setitem(sys.modules, "ApplicationServices", ax)
    native = virtual.macos.MacCaptureTarget("control", 456, 123)
    selected = WindowCaptureTarget(ORIGINAL, lambda: ORIGINAL, native_target=native)
    monkeypatch.setattr(virtual, "_owner_element", lambda native: "owner")
    monkeypatch.setattr(virtual, "_belongs_to_window", lambda *args: True)
    monkeypatch.setattr(virtual.macos, "_ax_attribute", lambda *args: role)
    target = virtual.target_from_selection(selected)
    assert target.element == "owner"
    assert (target.window_id, target.pid) == (456, 123)
    assert (target.control is None) == whole_window
    monkeypatch.setattr(virtual, "_belongs_to_window", lambda *args: False)
    with pytest.raises(RuntimeError, match="does not belong"):
        virtual.target_from_selection(selected)


def test_obscured_target_is_not_captured_and_is_restored(monkeypatch):
    from contextlib import contextmanager

    restored = []

    @contextmanager
    def moved(*args):
        try:
            yield ORIGINAL
        finally:
            restored.append(True)

    monkeypatch.setattr(virtual, "QSettings", lambda: SimpleNamespace(value=lambda *args: "virtual"))
    monkeypatch.setattr(virtual, "displays", lambda: [DESTINATION])
    monkeypatch.setattr(virtual, "moved_window", moved)
    monkeypatch.setattr(virtual, "target_bounds", lambda target: ORIGINAL)
    monkeypatch.setattr(virtual.macos, "_window_target_at_point", lambda *args: (None, 789, 123))
    monkeypatch.setattr(virtual, "capture_rect", lambda *args: pytest.fail("wrong window captured"))
    with pytest.raises(RuntimeError, match="virtual_target_obscured"):
        virtual.VirtualCaptureSession().capture(
            None, CaptureMode.ACTIVE_WINDOW, CaptureSettings(), lambda key: key, TARGET
        )
    assert restored == [True]
