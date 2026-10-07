import sys
from types import SimpleNamespace

import pytest

from fshot.capture import CaptureRect
from fshot import virtual_screen as virtual


DISPLAY = virtual.Display("virtual-4k", CaptureRect(-3840, 0, 3840, 2160), is_virtual=True)


def test_resolve_keeps_native_pixels_and_rejects_topology_changes(monkeypatch):
    monkeypatch.setattr(virtual, "displays", lambda: [DISPLAY])
    assert virtual.resolve_display(DISPLAY) == CaptureRect(-3840, 0, 3840, 2160)
    monkeypatch.setattr(virtual, "displays", lambda: [
        virtual.Display(DISPLAY.device, CaptureRect(1920, 0, 1920, 1080)),
    ])
    with pytest.raises(RuntimeError, match="configuration changed"):
        virtual.resolve_display(DISPLAY)
    monkeypatch.setattr(virtual, "displays", lambda: [])
    with pytest.raises(RuntimeError, match="no longer connected"):
        virtual.resolve_display(DISPLAY)


@pytest.mark.parametrize("failure", [None, "capture", "move"])
def test_window_restored_on_success_capture_failure_and_partial_move(monkeypatch, failure):
    events = []
    frame = [CaptureRect(20, 30, 800, 600)]
    placement = (0, 3, (0, 0), (0, 0), (20, 30, 820, 630))

    def move(*args):
        events.append(("move", args))
        if failure == "move":
            raise RuntimeError("move failed")
        _, _, left, top, width, height, _ = args
        frame[0] = CaptureRect(left, top, width, height)

    gui = SimpleNamespace(
        IsWindow=lambda hwnd: True,
        IsIconic=lambda hwnd: False,
        GetWindowRect=lambda hwnd: (
            frame[0].left, frame[0].top,
            frame[0].left+frame[0].width, frame[0].top+frame[0].height,
        ),
        GetWindowPlacement=lambda hwnd: placement,
        ShowWindow=lambda *args: events.append(("show", args)),
        SetWindowPos=move,
        SetWindowPlacement=lambda *args: events.append(("restore", args)),
    )
    con = SimpleNamespace(SW_RESTORE=9, SW_SHOWNORMAL=1, SWP_NOZORDER=4, HWND_TOP=0, SWP_NOACTIVATE=16, SWP_SHOWWINDOW=64, SW_MAXIMIZE=3)
    monkeypatch.setitem(sys.modules, "win32gui", gui)
    monkeypatch.setitem(sys.modules, "win32con", con)
    monkeypatch.setitem(sys.modules, "win32api", SimpleNamespace(
        MonitorFromWindow=lambda *args: 1,
        GetMonitorInfo=lambda handle: {"Monitor": (0, 0, 1920, 1080)},
    ))
    monkeypatch.setattr(virtual, "displays", lambda: [DISPLAY])
    monkeypatch.setattr(virtual, "_window_rect", lambda hwnd: frame[0])

    def run():
        with virtual.moved_window(42, DISPLAY):
            if failure == "capture":
                raise RuntimeError("capture failed")

    if failure:
        with pytest.raises(RuntimeError, match=failure):
            run()
    else:
        run()
    assert events[-1] == ("restore", (42, placement))
    assert ("move", (42, 0, -3840, 0, 1600, 1200, 80)) in events
    assert ("show", (42, con.SW_MAXIMIZE)) not in events


def test_desktop_capture_does_not_move_any_window(monkeypatch):
    monkeypatch.setitem(sys.modules, "win32gui", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "win32con", SimpleNamespace())
    monkeypatch.setattr(virtual, "displays", lambda: [DISPLAY])
    with virtual.moved_window(None, DISPLAY):
        pass


@pytest.mark.parametrize("outcome", ["capture", "cancel", "error"])
def test_preview_workflow_returns_native_image_and_restores_window(qt_app, monkeypatch, outcome):
    from PIL import Image
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QComboBox, QDialog
    from fshot.i18n import TRANSLATIONS
    from fshot.settings import CaptureSettings

    restored = []
    window_rect = [CaptureRect(10, 10, 800, 600)]

    def move(hwnd, order, left, top, width, height, flags):
        window_rect[0] = CaptureRect(left, top, width, height)

    def outer(hwnd):
        r = window_rect[0]
        return (r.left, r.top, r.left+r.width, r.top+r.height)

    placement = (0, 1, (0, 0), (0, 0), (10, 10, 800, 600))
    monkeypatch.setitem(sys.modules, "win32gui", SimpleNamespace(
        IsWindow=lambda hwnd: True,
        IsIconic=lambda hwnd: False,
        GetWindowRect=outer,
        GetWindowPlacement=lambda hwnd: placement,
        ShowWindow=lambda *args: None,
        SetWindowPos=move,
        SetWindowPlacement=lambda *args: restored.append(args),
    ))
    monkeypatch.setitem(sys.modules, "win32con", SimpleNamespace(
        SW_RESTORE=9, SW_SHOWNORMAL=1, SWP_NOZORDER=4, HWND_TOP=0, SWP_NOACTIVATE=16, SWP_SHOWWINDOW=64, SW_MAXIMIZE=3,
    ))
    monkeypatch.setitem(sys.modules, "win32api", SimpleNamespace(
        MonitorFromWindow=lambda *args: 1,
        GetMonitorInfo=lambda handle: {"Device": "physical-1080p", "Monitor": (0, 0, 1920, 1080)},
    ))
    monkeypatch.setattr(virtual, "displays", lambda: [DISPLAY])
    monkeypatch.setattr(virtual, "windows", lambda: [(42, "Test window")])
    monkeypatch.setattr(virtual, "_window_rect", lambda hwnd: window_rect[0])

    def dialog_exec(dialog):
        choices = dialog.findChildren(QComboBox)
        if choices:
            choices[0].setCurrentIndex(1)
            return QDialog.DialogCode.Accepted
        dialog.findChild(QTimer).timeout.emit()
        return QDialog.DialogCode.Accepted if outcome == "capture" else QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", dialog_exec)
    grabs, cursors, delays = [], [], []

    def grab(rect):
        grabs.append(rect)
        if outcome == "error":
            raise RuntimeError("driver capture failed")
        return Image.new("RGB", (rect.width, rect.height))

    service = SimpleNamespace(
        _grab_rect=grab,
        _draw_cursor=lambda image, rect: cursors.append(rect),
        _countdown=lambda seconds: delays.append(seconds) or False,
    )
    settings = CaptureSettings(include_cursor=True, delay_seconds=2)
    tr = lambda key: TRANSLATIONS["en"][key]
    if outcome == "error":
        with pytest.raises(RuntimeError, match="driver capture failed"):
            virtual.capture_display(service, settings, tr)
    else:
        result = virtual.capture_display(service, settings, tr)
        if outcome == "capture":
            target = CaptureRect(-3840, 0, 1600, 1200)
            assert result.size == (1600, 1200)
            assert grabs == [target, target]
            assert cursors == [target]
            assert delays == [2]
        else:
            assert result is None
            assert len(grabs) == 1
            assert not cursors and not delays
    assert restored == [(42, placement)]
    assert window_rect[0] == CaptureRect(10, 10, 800, 600)


def test_proportional_size_preserves_each_screen_fraction():
    original = CaptureRect(100, 200, 960, 540)
    assert virtual.proportional_size(original, CaptureRect(0, 0, 1920, 1080), DISPLAY.rect) == (1920, 1080)
    # A source screen with a different aspect ratio has different x/y factors.
    assert virtual.proportional_size(original, CaptureRect(0, 0, 1920, 1200), DISPLAY.rect) == (1920, 972)


def test_window_capture_rejects_partial_clipping(monkeypatch):
    monkeypatch.setattr(virtual, "displays", lambda: [DISPLAY])
    monkeypatch.setattr(virtual, "_window_rect", lambda hwnd: CaptureRect(-4000, 0, 800, 600))
    with pytest.raises(RuntimeError, match="does not fit"):
        virtual.window_capture_rect(42, DISPLAY)
