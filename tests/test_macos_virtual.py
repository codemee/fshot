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
            session.capture(service, CaptureMode.ACTIVE_WINDOW, settings, lambda key: key, TARGET)
    else:
        result = session.capture(service, CaptureMode.ACTIVE_WINDOW, settings, lambda key: key, TARGET)
        assert (result is not None) == (outcome == "success")
    assert moves[-1] == ORIGINAL
    assert (session.last is not None) == (outcome == "success")


def test_stage_one_rejects_control_selection():
    session = virtual.VirtualCaptureSession()
    with pytest.raises(RuntimeError, match="mac_virtual_stage_one"):
        session.capture(None, CaptureMode.WINDOW_UNDER_CURSOR, CaptureSettings(), lambda key: key)


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
