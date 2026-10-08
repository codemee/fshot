from types import SimpleNamespace

from PIL import Image
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from fshot.capture import (
    CaptureRect,
    CaptureService,
    RegionSelector,
    WindowCaptureTarget,
    WindowSelector,
    _FrozenDesktop,
    _cancel_windows_menu_mode,
    _uia_target_at_point,
)
from fshot.settings import CaptureMode, CaptureSettings


def _image() -> Image.Image:
    return Image.new("RGB", (1, 1))


def test_repeat_region_reuses_the_previous_coordinates(monkeypatch):
    monkeypatch.setattr("fshot.capture.sys.platform", "win32")
    service = CaptureService()
    selected = CaptureRect(12, 34, 200, 100)
    desktop = _FrozenDesktop(CaptureRect(0, 0, 400, 300), Image.new("RGB", (400, 300), "red"))
    captured = []
    monkeypatch.setattr(
        service,
        "_freeze_desktop",
        lambda _settings: (_ for _ in ()).throw(AssertionError("desktop was frozen twice")),
    )
    monkeypatch.setattr(service, "_select_region", lambda _frozen: selected)
    monkeypatch.setattr(
        service,
        "_capture_rect_for_mode",
        lambda mode, rect, _settings: captured.append((mode, rect)) or _image(),
    )

    first = service.capture(CaptureMode.REGION, CaptureSettings(), desktop)
    service.repeat(CaptureSettings())

    assert first.size == (200, 100)
    assert first.getpixel((0, 0)) == (255, 0, 0)
    assert captured == [(CaptureMode.REGION, selected)]


def test_repeat_selected_window_tracks_it_and_silently_stops_after_it_disappears(monkeypatch):
    monkeypatch.setattr("fshot.capture.sys.platform", "win32")
    service = CaptureService()
    original = CaptureRect(10, 20, 300, 200)
    moved = CaptureRect(100, 120, 300, 200)
    resolutions = iter((moved, None))
    target = WindowCaptureTarget(original, lambda: next(resolutions))
    desktop = _FrozenDesktop(CaptureRect(0, 0, 500, 400), Image.new("RGB", (500, 400)))
    captured = []
    monkeypatch.setattr(
        service,
        "_freeze_desktop",
        lambda _settings: (_ for _ in ()).throw(AssertionError("desktop was frozen twice")),
    )
    monkeypatch.setattr(service, "_select_window_target", lambda frozen: target)
    monkeypatch.setattr(
        service,
        "_capture_rect_for_mode",
        lambda mode, rect, _settings: captured.append((mode, rect)) or _image(),
    )

    first = service.capture(CaptureMode.WINDOW_UNDER_CURSOR, CaptureSettings(), desktop)
    assert service.repeat(CaptureSettings()) is not None
    assert service.repeat(CaptureSettings()) is None

    assert first.size == (300, 200)
    assert captured == [(CaptureMode.WINDOW_UNDER_CURSOR, moved)]


def test_frozen_desktop_crop_uses_virtual_screen_coordinates():
    image = Image.new("RGB", (4, 3), "black")
    image.putpixel((2, 1), (10, 20, 30))
    frozen = _FrozenDesktop(CaptureRect(-2, -1, 4, 3), image)

    cropped = frozen.crop(CaptureRect(0, 0, 1, 1))

    assert cropped is not None
    assert cropped.size == (1, 1)
    assert cropped.getpixel((0, 0)) == (10, 20, 30)


def test_freeze_desktop_counts_down_before_capture_and_uses_freeze_time_cursor(monkeypatch):
    monkeypatch.setattr("fshot.capture.sys.platform", "win32")
    service = CaptureService()
    rect = CaptureRect(0, 0, 2, 2)
    image = Image.new("RGB", (2, 2))
    windows = (WindowCaptureTarget(rect, lambda: rect, owner_hwnd=123, is_window=True),)
    events = []
    monkeypatch.setattr(
        "fshot.capture._snapshot_windows_targets",
        lambda: events.append(("windows",)) or windows,
    )
    monkeypatch.setattr(service, "_countdown", lambda seconds: events.append(("countdown", seconds)))
    monkeypatch.setattr(service, "_fullscreen_rect", lambda: events.append(("rect",)) or rect)
    monkeypatch.setattr(service, "_grab_rect", lambda value: events.append(("grab", value)) or image)
    monkeypatch.setattr(
        service,
        "_draw_cursor",
        lambda value, bounds: events.append(("cursor", value, bounds)),
    )

    frozen = service._freeze_desktop(CaptureSettings(include_cursor=True, delay_seconds=3))

    assert frozen == _FrozenDesktop(rect, image, windows=windows)
    assert events == [
        ("countdown", 3),
        ("rect",),
        ("grab", rect),
        ("cursor", image, rect),
        ("windows",),
    ]


def test_delayed_region_cancel_stops_before_freeze_and_selection(monkeypatch):
    monkeypatch.setattr("fshot.capture.sys.platform", "win32")
    service = CaptureService()
    monkeypatch.setattr(service, "_countdown", lambda _seconds: True)
    monkeypatch.setattr(
        service,
        "_fullscreen_rect",
        lambda: (_ for _ in ()).throw(AssertionError("desktop should not be captured")),
    )
    monkeypatch.setattr(
        service,
        "_select_region",
        lambda _frozen: (_ for _ in ()).throw(AssertionError("selector should not open")),
    )

    image = service.capture(CaptureMode.REGION, CaptureSettings(delay_seconds=3))

    assert image is None
    assert service._last_capture is None


def test_region_selector_poll_cancels_without_keyboard_focus(qt_app, monkeypatch):
    selector = RegionSelector()
    monkeypatch.setattr("fshot.capture._escape_pressed", lambda: True)

    selector.poll()

    assert selector.cancelled
    selector.deleteLater()
    qt_app.processEvents()


def test_window_selector_consumes_release_and_uses_its_position(qt_app, monkeypatch):
    selector = WindowSelector(Image.new("RGB", (2, 2)))
    selected = WindowCaptureTarget(CaptureRect(10, 20, 30, 40), lambda: None)
    release_point = QPoint(25, 35)
    monkeypatch.setattr(
        selector,
        "_target_at_point",
        lambda point, use_uia: selected if point == release_point and use_uia else None,
    )
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(1, 1),
        QPointF(release_point),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    selector.mouseReleaseEvent(event)

    assert event.isAccepted()
    assert selector.target is selected
    assert selector.target_rect == selected.rect
    selector.deleteLater()
    qt_app.processEvents()


def test_window_selector_prefers_frozen_transient_target(qt_app, monkeypatch):
    menu = WindowCaptureTarget(CaptureRect(10, 10, 80, 100), lambda: None)
    item = WindowCaptureTarget(CaptureRect(10, 30, 80, 20), lambda: None)
    selector = WindowSelector(Image.new("RGB", (2, 2)), (menu, item))
    monkeypatch.setattr("fshot.capture.sys.platform", "win32")

    selected = selector._target_at_point(QPoint(20, 35), use_uia=True)

    assert selected is item
    selector.deleteLater()
    qt_app.processEvents()


def test_uia_top_level_window_uses_native_dwm_target(monkeypatch):
    native = WindowCaptureTarget(CaptureRect(10, 20, 300, 200), lambda: None)
    element = SimpleNamespace(
        CurrentIsOffscreen=False,
        CurrentBoundingRectangle=SimpleNamespace(left=2, top=12, right=318, bottom=228),
        CurrentControlType=50032,
        CurrentNativeWindowHandle=123,
    )
    automation = SimpleNamespace(ElementFromPoint=lambda _point: element)
    monkeypatch.setattr("fshot.capture.sys.platform", "win32")
    monkeypatch.setattr(
        "fshot.capture._uia_automation", lambda: (automation, lambda x, y: (x, y))
    )
    monkeypatch.setattr(
        "fshot.capture._window_target_from_hwnd",
        lambda hwnd: native if hwnd == 123 else None,
    )

    assert _uia_target_at_point(QPoint(50, 60)) is native


def test_windows_menu_mode_is_cancelled_for_menu_owner_and_foreground(monkeypatch):
    sent = []

    def get_gui_thread_info(_thread_id, pointer):
        pointer._obj.hwndMenuOwner = 222
        pointer._obj.hwndActive = 111
        return True

    monkeypatch.setattr("fshot.capture.sys.platform", "win32")
    monkeypatch.setattr(
        "fshot.capture.win32gui",
        SimpleNamespace(
            GetForegroundWindow=lambda: 111,
            SendMessageTimeout=lambda *args: sent.append(args),
        ),
    )
    monkeypatch.setattr(
        "fshot.capture.win32process",
        SimpleNamespace(GetWindowThreadProcessId=lambda _hwnd: (12, 34)),
    )
    monkeypatch.setattr(
        "fshot.capture.windll",
        SimpleNamespace(user32=SimpleNamespace(GetGUIThreadInfo=get_gui_thread_info)),
    )
    monkeypatch.setattr(
        "fshot.capture.win32con",
        SimpleNamespace(WM_CANCELMODE=0x001F, SMTO_ABORTIFHUNG=0x0002),
    )

    _cancel_windows_menu_mode()

    assert [call[0] for call in sent] == [222, 111]


def test_zero_delay_interactive_selection_can_freeze_before_hotkey_returns(monkeypatch):
    monkeypatch.setattr("fshot.capture.sys.platform", "win32")
    service = CaptureService()
    frozen = _FrozenDesktop(CaptureRect(0, 0, 1, 1), _image())
    menu_target = WindowCaptureTarget(CaptureRect(0, 0, 1, 1), lambda: None)
    monkeypatch.setattr(service, "_freeze_desktop", lambda _settings: frozen)
    monkeypatch.setattr(
        "fshot.capture._snapshot_windows_transient_targets", lambda: (menu_target,)
    )

    prepared = service.prepare_frozen_selection(CaptureMode.REGION, CaptureSettings())
    delayed = service.prepare_frozen_selection(
        CaptureMode.REGION, CaptureSettings(delay_seconds=3)
    )
    fullscreen = service.prepare_frozen_selection(CaptureMode.FULLSCREEN, CaptureSettings())
    selected_window = service.prepare_frozen_selection(
        CaptureMode.WINDOW_UNDER_CURSOR, CaptureSettings()
    )

    assert prepared is frozen
    assert delayed is None
    assert fullscreen is None
    assert selected_window is not None
    assert selected_window.image is frozen.image
    assert selected_window.targets == (menu_target,)


def test_macos_zero_delay_interactive_selection_freezes_before_selector_takes_focus(
    monkeypatch,
):
    monkeypatch.setattr("fshot.capture.sys.platform", "darwin")
    service = CaptureService()
    frozen = _FrozenDesktop(CaptureRect(0, 0, 1, 1), _image())
    monkeypatch.setattr(service, "_freeze_desktop", lambda _settings: frozen)

    prepared = service.prepare_frozen_selection(CaptureMode.REGION, CaptureSettings())
    delayed = service.prepare_frozen_selection(
        CaptureMode.REGION, CaptureSettings(delay_seconds=3)
    )
    fullscreen = service.prepare_frozen_selection(CaptureMode.FULLSCREEN, CaptureSettings())
    selected_window = service.prepare_frozen_selection(
        CaptureMode.WINDOW_UNDER_CURSOR, CaptureSettings()
    )

    assert prepared is frozen
    assert delayed is None
    assert fullscreen is None
    assert selected_window is frozen


def test_repeat_before_any_successful_capture_does_nothing():
    assert CaptureService().repeat(CaptureSettings()) is None
