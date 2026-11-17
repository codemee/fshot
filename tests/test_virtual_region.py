from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QDialog

from fshot import virtual_region as region
from fshot import virtual_screen as virtual
from fshot.capture import CaptureRect
from fshot.settings import CaptureMode, CaptureSettings


def test_preview_maps_letterbox_reverse_drag_and_edges_to_native_pixels(qt_app):
    view = region.RegionPreview(Image.new("RGB", (3840, 2160)), lambda key: key)
    try:
        view.resize(1000, 800)
        area = view.image_area()
        view.start = QPoint(area.x()+area.width(), area.y()+area.height())
        view.end = area.topLeft()
        assert view.selection_box() == (0, 0, 3840, 2160)
        assert view.pixel_point(QPoint(-100, -100)) == QPoint(0, 0)
        view.start = view.end
        assert view.selection_box() is None
    finally:
        view.close()


def test_snapshot_crop_uses_original_pixels_and_repeat_rejects_new_size(qt_app, monkeypatch):
    image = Image.new("RGB", (3840, 2160), "red")
    image.putpixel((100, 200), (0, 255, 0))
    def select(view):
        view.box = (100, 200, 1100, 800)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(region.RegionPreview, "exec", select)
    output, saved = region.crop_snapshot(image, lambda key: key)
    assert output.size == (1000, 600)
    assert output.getpixel((0, 0)) == (0, 255, 0)
    monkeypatch.setattr(region.RegionPreview, "exec", lambda _: pytest.fail("repeat must reuse region"))
    assert region.crop_snapshot(image, lambda key: key, saved)[0].size == (1000, 600)
    with pytest.raises(RuntimeError, match="virtual_region_changed"):
        region.crop_snapshot(Image.new("RGB", (1920, 1080)), lambda key: key, saved)


@pytest.mark.parametrize("cancel", [False, True])
def test_region_restores_before_selection_and_keeps_history_on_cancel(qt_app, monkeypatch, cancel):
    display = virtual.Display("virtual", CaptureRect(-3840, 0, 3840, 2160), is_virtual=True)
    target = SimpleNamespace(owner_hwnd=5, source_hwnd=5, is_window=True,
                             rect=CaptureRect(0, 0, 800, 600), resolve=lambda: CaptureRect(-3840, 0, 1600, 1200))
    events = []
    @contextmanager
    def moved(hwnd, destination):
        events.append("move")
        try:
            yield display.rect
        finally:
            events.append("restore")
    def delayed(service, destination, selected, settings, tr, *, region=False):
        assert region
        events.append("freeze")
        return Image.new("RGB", (3840, 2160))
    def select(view):
        assert events == ["move", "freeze", "restore"]
        view.box = (0, 0, 1000, 500)
        return QDialog.DialogCode.Rejected if cancel else QDialog.DialogCode.Accepted
    monkeypatch.setattr(virtual, "automatic_display", lambda _: display)
    monkeypatch.setattr(virtual, "moved_window", moved)
    monkeypatch.setattr(virtual, "_wait_for_window_update", lambda *_: None)
    monkeypatch.setattr("fshot.virtual_interactive.delayed_interactive_capture", delayed)
    monkeypatch.setattr(region.RegionPreview, "exec", select)
    session = virtual.VirtualCaptureSession()
    session.last = (CaptureMode.FULLSCREEN, None)
    result = session.capture(None, CaptureMode.REGION, CaptureSettings(delay_seconds=3), lambda key: key, target)
    if cancel:
        assert result is None
        assert session.last == (CaptureMode.FULLSCREEN, None)
    else:
        assert result.size == (1000, 500)
        assert session.last == (CaptureMode.REGION, target)
        assert session.repeat(None, CaptureSettings(delay_seconds=3), lambda key: key).size == (1000, 500)
