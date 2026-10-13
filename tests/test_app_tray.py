from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QSystemTrayIcon

import fshot.app as app_module
from fshot.app import FShotApplication
from test_app_updates import _controller


@pytest.mark.parametrize("platform", ["darwin", "win32", "linux"])
def test_tray_menu_attachment_does_not_block_macos_double_click(qt_app, tmp_path, monkeypatch, platform):
    controller, _updater = _controller(qt_app, tmp_path, monkeypatch)
    monkeypatch.setattr(app_module.sys, "platform", platform)
    tray = controller._build_tray()
    assert (tray.contextMenu() is None) == (platform == "darwin")
    assert controller.check_updates_action in controller.tray_menu.actions()
    assert controller.exit_action in controller.tray_menu.actions()
    assert controller.tray_menu.parent() is controller.window
    if platform != "darwin":
        assert tray.contextMenu() is controller.tray_menu


@pytest.mark.parametrize("platform", ["darwin", "win32", "linux"])
@pytest.mark.parametrize("reason", list(QSystemTrayIcon.ActivationReason))
def test_tray_activation_routes_double_click_and_macos_context_without_ui(monkeypatch, platform, reason):
    monkeypatch.setattr(app_module.sys, "platform", platform)
    monkeypatch.setattr(app_module.QCursor, "pos", lambda: QPoint(120, 10))
    shown, menus = [], []
    controller = SimpleNamespace(show_window=lambda: shown.append(True),
                                 tray_menu=SimpleNamespace(popup=lambda point: menus.append(point)))
    FShotApplication._tray_activated(controller, reason)
    assert shown == ([True] if reason == QSystemTrayIcon.ActivationReason.DoubleClick else [])
    assert menus == ([QPoint(120, 10)] if platform == "darwin"
                     and reason == QSystemTrayIcon.ActivationReason.Context else [])
